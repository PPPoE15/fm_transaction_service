#!/usr/bin/env bash
# Публикация вызывается только после CI, под общей блокировкой target в workflow.
set -euo pipefail
if [[ "${GITHUB_EVENT_NAME:-}" != push || "${CI_RESULT:-}" != success ]]; then
  echo "Publication requires successful push CI" >&2
  exit 1
fi
: "${IMAGE:?}" "${GITHUB_SHA:?}" "${GITHUB_REF_NAME:?}"
[[ "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]]
case "$GITHUB_REF_NAME" in dev|master) ;; *) exit 1 ;; esac
version="${IMAGE}:${GITHUB_REF_NAME}-${GITHUB_SHA}"
error_file=$(mktemp)
trap 'rm -f "$error_file"' EXIT

# Не пересобираем существующую версию: базовый образ и apt-пакеты могли измениться.
if digest_json=$(docker buildx imagetools inspect "$version" --format '{{json .Manifest.Digest}}' 2>"$error_file"); then
  :
elif grep -Eq '(: not found$|manifest unknown)' "$error_file"; then
  docker buildx build . --file Dockerfile --target "$GITHUB_REF_NAME" \
    --platform linux/amd64 --tag "$version" \
    --label "org.opencontainers.image.revision=$GITHUB_SHA" --push
  digest_json=$(docker buildx imagetools inspect "$version" --format '{{json .Manifest.Digest}}')
else
  cat "$error_file" >&2
  exit 1
fi

export VERSION="$version" DIGEST_JSON="$digest_json"
digest=$(python3 -c 'import json, os; print(json.loads(os.environ["DIGEST_JSON"]))')
[[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]
# Тег ветки указывает на проверенную версию, в том числе при повторном запуске CI.
docker buildx imagetools create --prefer-index=false --tag "$IMAGE:$GITHUB_REF_NAME" "$IMAGE@$digest"
printf 'Обновлён тег %s:%s -> %s\n' "$IMAGE" "$GITHUB_REF_NAME" "$digest"

python3 - <<'PY'
import json
import os
import re
from pathlib import Path

digest = json.loads(os.environ['DIGEST_JSON'])
if not isinstance(digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
    raise SystemExit('Некорректный digest образа')
metadata = {
    'image': f"{os.environ['IMAGE']}@{digest}",
    'tag': os.environ['VERSION'],
    'sha': os.environ['GITHUB_SHA'],
    'environment': os.environ['GITHUB_REF_NAME'],
}
Path('publication.json').write_text(json.dumps(metadata, indent=2) + '\n')
with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
    output.write(f'digest={digest}\n')
    for key, value in metadata.items():
        output.write(f'{key}={value}\n')
with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
    summary.write('### Опубликованный образ\n```json\n' + json.dumps(metadata, indent=2) + '\n```\n')
PY
