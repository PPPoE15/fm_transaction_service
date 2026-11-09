#!/usr/bin/env python3
"""SSH-клиент CD. Синхронная копия в трёх репозиториях приложений (FM-66)."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def prepare(env, directory):
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


def main():
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix='fm-deploy-') as directory:
        request, command = prepare(os.environ, directory)
        for filename, key in (('key', 'DEPLOY_KEY'), ('known_hosts', 'DEPLOY_KNOWN_HOSTS')):
            value = os.environ.get(key, '')
            if not value.strip():
                raise ValueError('Missing SSH credential: ' + key)
            Path(directory, filename).write_text(value.rstrip() + '\n')
        result = subprocess.run(command, input=json.dumps(request), text=True,
                                capture_output=True, timeout=1800)
        # Серверные логи не копируем в Actions: они могут содержать данные приложения.
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write('\n### SSH deployment\n\n```json\n' + json.dumps(request, indent=2) + '\n```\n')
            summary.write('Result: ' + ('success' if result.returncode == 0 else 'failed; inspect server logs') + '\n')
            if result.returncode == 0:
                response = json.loads(result.stdout)
                summary.write('```json\n' + json.dumps(response, indent=2) + '\n```\n')
        if result.returncode:
            raise SystemExit('Deployment failed; inspect protected server logs and pending.json')


if __name__ == '__main__':
    main()
