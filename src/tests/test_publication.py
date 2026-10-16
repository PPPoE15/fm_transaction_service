"""Проверки контракта публикации без обращения к реестру и секретам."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64


def test_workflow_gates_publication() -> None:
    """Публикация зависит от обязательных проверок того же запуска."""
    workflow = (ROOT / ".github/workflows/lint-and-test.yml").read_text()
    assert "needs: lint-and-test" in workflow
    assert "github.event_name == 'push'" in workflow
    assert "needs.lint-and-test.result == 'success'" in workflow
    assert "github.ref == 'refs/heads/dev'" in workflow
    assert "github.ref == 'refs/heads/master'" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "ref: ${{ github.sha }}" in workflow
    assert "pull_request: {}" in workflow
    ci, publication = workflow.split("  publish:")
    assert "secrets." not in ci
    assert "secrets.DOCKERHUB_TOKEN" in publication
    for command in (
        "ruff check --config=pyproject.toml src/",
        "ruff format --config=pyproject.toml src/ --check",
        "mypy --config-file=pyproject.toml src/",
        "poetry run pytest",
    ):
        assert command in ci
    assert not (ROOT / ".github/workflows/docker-image.yml").exists()


@pytest.mark.parametrize("target", ["dev", "master"])
@pytest.mark.parametrize("registry", ["existing", "missing", "unavailable"])
def test_publication_script(tmp_path: Path, target: str, registry: str) -> None:
    """Оба target публикуются один раз, ошибки реестра останавливают процесс."""
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/bin/bash\n"
        'echo "$*" >> "$CALLS"\n'
        'if [[ "$*" == *"imagetools inspect"* ]]; then\n'
        '  if [[ "$REGISTRY" == unavailable ]]; then echo "unauthorized" >&2; exit 1; fi\n'
        '  if [[ "$REGISTRY" == missing && ! -e "$BUILT" ]]; then\n'
        '    echo "ERROR: not found" >&2; exit 1\n'
        "  fi\n"
        '  printf \'"%s"\\n\' "$DIGEST"\n'
        'elif [[ "$*" == *"buildx build"* ]]; then touch "$BUILT"; fi\n'
    )
    docker.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "IMAGE": "example/fm_transaction_service",
        "GITHUB_SHA": SHA,
        "GITHUB_REF_NAME": target,
        "GITHUB_OUTPUT": str(tmp_path / "outputs"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        "CALLS": str(tmp_path / "calls"),
        "BUILT": str(tmp_path / "built"),
        "REGISTRY": registry,
        "CI_RESULT": "success",
        "GITHUB_EVENT_NAME": "push",
        "DIGEST": DIGEST,
    }
    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(  # noqa: S603 — запускается скрипт репозитория с подменённым Docker.
        [bash, str(ROOT / "scripts/publish-image.sh")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if registry == "unavailable":
        assert result.returncode != 0
        assert "buildx build" not in (tmp_path / "calls").read_text()
        return
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "calls").read_text()
    version = f"example/fm_transaction_service:{target}-{SHA}"
    assert version in calls
    assert ("buildx build" in calls) == (registry == "missing")
    if registry == "missing":
        assert f"--target {target}" in calls
        assert f"--tag {version}" in calls
    metadata = json.loads((tmp_path / "publication.json").read_text())
    assert metadata == {
        "image": f"example/fm_transaction_service@{DIGEST}",
        "tag": version,
        "sha": SHA,
        "environment": target,
    }
    assert f"image=example/fm_transaction_service@{DIGEST}" in (tmp_path / "outputs").read_text()


@pytest.mark.parametrize(
    ("event", "result"),
    [("push", "failure"), ("push", "cancelled"), ("push", "skipped"), ("pull_request", "success")],
)
def test_reject_unverified_publication(tmp_path: Path, event: str, result: str) -> None:
    """Скрипт не обращается к Docker для PR или неуспешного CI."""
    bash = shutil.which("bash")
    assert bash is not None
    completed = subprocess.run(  # noqa: S603 — фиксированный скрипт репозитория.
        [bash, str(ROOT / "scripts/publish-image.sh")],
        cwd=tmp_path,
        env={
            **os.environ,
            "CI_RESULT": result,
            "GITHUB_EVENT_NAME": event,
            "IMAGE": "example/fm_transaction_service",
            "GITHUB_SHA": SHA,
            "GITHUB_REF_NAME": "dev",
            "PATH": str(tmp_path),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "Publication requires successful push CI" in completed.stderr
