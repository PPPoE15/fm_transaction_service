#!/usr/bin/env python3
"""SSH-клиент CD. Деплой приложения через общий серверный контроллер (FM-66)."""
from collections import deque
import codecs
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid


def prepare(env, directory):
    """Проверяет запрос и формирует команду с обязательной проверкой SSH-ключа сервера."""
    patterns = {
        'DEPLOY_HOST': r'[a-zA-Z0-9][a-zA-Z0-9.-]*',
        'DEPLOY_USER': r'[a-z_][a-z0-9_-]*',
        'DEPLOY_PORT': r'[0-9]{1,5}',
        'DEPLOY_ROOT': r'/[a-zA-Z0-9/_-]+',
        'DEPLOY_ENVIRONMENT': r'dev|master',
        'DEPLOY_COMPONENT': r'ui|auth|transaction',
        'DEPLOY_IMAGE': r'[a-z0-9][a-z0-9./_-]*@sha256:[0-9a-f]{64}',
        'GITHUB_SHA': r'[0-9a-f]{40}',
        'GITHUB_RUN_NUMBER': r'[1-9][0-9]*',
    }
    for key, pattern in patterns.items():
        if not re.fullmatch(pattern, env.get(key, '')):
            raise ValueError('Invalid deployment field: ' + key)
    if not 1 <= int(env['DEPLOY_PORT']) <= 65535:
        raise ValueError('Invalid SSH port')
    root = env['DEPLOY_ROOT'].rstrip('/')
    request = {'environment': env['DEPLOY_ENVIRONMENT'], 'component': env['DEPLOY_COMPONENT'],
               'image': env['DEPLOY_IMAGE'], 'sha': env['GITHUB_SHA'],
               'generation': int(env['GITHUB_RUN_NUMBER'])}
    command = ['ssh', '-T', '-p', env['DEPLOY_PORT'], '-i', directory + '/key',
               '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
               '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=20',
               '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=4',
               '-o', 'UserKnownHostsFile=' + directory + '/known_hosts',
               env['DEPLOY_USER'] + '@' + env['DEPLOY_HOST'],
               'python3 ' + root + '/release.py ' + root]
    return request, command


def run_ssh(command, request):
    """Передаёт весь stderr SSH в Actions сразу, сохраняя JSON-ответ и хвост диагностики."""
    errors = deque(maxlen=200)
    marker = 'deployment-' + uuid.uuid4().hex
    print('::stop-commands::' + marker, file=sys.stderr, flush=True)
    try:
        with tempfile.TemporaryFile(mode='w+t') as response:
            with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=response, stderr=subprocess.PIPE,
                                  bufsize=-1) as process:
                process.stdin.write(json.dumps(request).encode())
                process.stdin.close()
                decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
                while True:
                    chunk = process.stderr.read1(8192)
                    text = decoder.decode(chunk, final=not chunk)
                    sys.stderr.write(text)
                    sys.stderr.flush()
                    errors.append(text)
                    if not chunk:
                        break
                code = process.wait()
            response.seek(0)
            return subprocess.CompletedProcess(command, code, stdout=response.read(), stderr=''.join(errors))
    finally:
        print('\n::' + marker + '::', file=sys.stderr, flush=True)


def describe_failure(code, stderr):
    """Добавляет краткое описание ошибки к уже показанному полному SSH-журналу."""
    if code == 255:
        diagnostic = stderr.lower()
        reasons = (
            (('could not resolve hostname', 'temporary failure in name resolution'), 'DNS lookup failed. Check DEPLOY_HOST.'),
            (('host key verification failed', 'remote host identification has changed'),
             'Host key verification failed. Check DEPLOY_KNOWN_HOSTS for the exact host and port.'),
            (('permission denied (', 'load key', 'invalid format', 'error in libcrypto'),
             'Authentication failed. Check DEPLOY_USER, DEPLOY_KEY and authorized_keys.'),
            (('connection timed out', 'operation timed out'),
             'Connection timed out. Check DEPLOY_HOST, DEPLOY_PORT and firewall.'),
            (('connection refused',), 'Connection refused. Check the SSH port and sshd.'),
            (('no route to host', 'network is unreachable'), 'Server unreachable. Check routing and firewall.'),
        )
        for signatures, message in reasons:
            if any(signature in diagnostic for signature in signatures):
                return 'SSH: ' + message
        return 'SSH connection failed or was interrupted (exit 255). Check access from GitHub Actions.'

    for line in reversed(stderr.splitlines()):
        if line in {
            'Invalid deployment request',
            'Image repository must match the installed component',
            'Incomplete deployment: operator recovery required (pending.json)',
            'Incomplete infrastructure deployment: operator recovery required',
            'Invalid active bundle: operator recovery required',
            'Stale or conflicting deployment',
            'Server environment mismatch',
        }:
            return 'Server controller: ' + line
        log = re.fullmatch(r'(Command|Compose config) failed; inspect (?:protected )?server log ([a-zA-Z0-9_.-]+\.log)', line)
        if log:
            return f'Server controller: {log[1]} failed. Deployment log: {log[2]} (output above).'
        smoke = re.fullmatch(r'(HTTPS?) smoke failed: (?:/|/auth/me|/transaction/categories)', line)
        if smoke:
            return 'Server controller: ' + line + f'. Check {smoke[1]} access from the server.'
    if code == 127:
        return 'Remote command unavailable. Check Python 3 on the server.'
    if code == 2 and "can't open file" in stderr and 'release.py' in stderr and '[Errno 2]' in stderr:
        return 'Server launcher missing. Check DEPLOY_ROOT and whether infrastructure bootstrap completed.'
    return f'Remote deployment command failed (exit {code}). See the complete deployment output above.'


def checked_response(stdout, request):
    """Оставляет в отчёте только окружение и проверенные digest запущенных образов."""
    response = json.loads(stdout)
    images = response['images']
    if (response['environment'] != request['environment']
            or set(images) not in ({'ui', 'auth', 'transaction', 'postgres'},
                                   {'ui', 'auth', 'transaction', 'postgres', 'caddy'})
            or images[request['component']] != request['image']
            or any(not re.fullmatch(r'[a-z0-9][a-z0-9./_-]*@sha256:[0-9a-f]{64}', image)
                   for image in images.values())):
        raise ValueError('Server confirmation does not match the request')
    return {'environment': response['environment'], 'images': images}


def main():
    """Показывает этапы запроса, результата SSH и подтверждения сервером."""
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix='fm-deploy-') as directory:
        print('[1/3] Validating deployment request and SSH credentials.', flush=True)
        try:
            request, command = prepare(os.environ, directory)
            for filename, key in (('key', 'DEPLOY_KEY'), ('known_hosts', 'DEPLOY_KNOWN_HOSTS')):
                value = os.environ.get(key, '')
                if not value.strip():
                    raise ValueError('Missing SSH credential: ' + key)
                Path(directory, filename).write_text(value.rstrip() + '\n')
        except ValueError as error:
            raise SystemExit(str(error)) from None

        print(f"[2/3] Connecting over verified SSH to deploy {request['component']} in "
              f"{request['environment']} (run {request['generation']}).", flush=True)
        print(f"Image: {request['image']} | Commit: {request['sha']}", flush=True)
        started = time.monotonic()
        response = None
        try:
            result = run_ssh(command, request)
            if result.returncode:
                error = describe_failure(result.returncode, result.stderr)
            else:
                try:
                    response = checked_response(result.stdout, request)
                except (ValueError, TypeError, KeyError):
                    error = 'SSH completed but the server returned an invalid deployment confirmation.'
                else:
                    error = None
        except OSError:
            error = 'Cannot start OpenSSH on the Actions runner.'

        elapsed = time.monotonic() - started
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write('\n### SSH deployment\n\n```json\n' + json.dumps(request, indent=2) + '\n```\n')
            summary.write(f'Duration: {elapsed:.1f} s\n\n')
            summary.write('Result: ' + (error or 'success') + '\n')
            if response is not None:
                summary.write('```json\n' + json.dumps(response, indent=2) + '\n```\n')
        if error:
            raise SystemExit(f'[3/3] Failed after {elapsed:.1f} s. {error}')
        print(f'[3/3] Server confirmed deployment after {elapsed:.1f} s.', flush=True)


if __name__ == '__main__':
    main()
