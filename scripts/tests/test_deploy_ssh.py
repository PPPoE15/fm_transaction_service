from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('deploy_ssh', Path(__file__).parents[1] / 'deploy-ssh.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SSHTest(unittest.TestCase):
    def setUp(self):
        self.env = dict(DEPLOY_HOST='example.com', DEPLOY_USER='deploy', DEPLOY_PORT='22',
                        DEPLOY_ROOT='/srv/fm/dev', DEPLOY_ENVIRONMENT='dev', DEPLOY_COMPONENT='ui',
                        DEPLOY_IMAGE='pppoe15/fm-ui@sha256:' + 'a' * 64,
                        GITHUB_SHA='a' * 40, GITHUB_RUN_NUMBER='123')

    def test_request_pins_digest_and_monotonic_workflow_generation(self):
        request, command = module.prepare(self.env, '/tmp/credentials')
        self.assertEqual(request['image'], self.env['DEPLOY_IMAGE'])
        self.assertEqual(request['generation'], 123)
        self.assertIn('StrictHostKeyChecking=yes', command)
        self.assertIn('BatchMode=yes', command)
        self.assertIn('IdentitiesOnly=yes', command)
        self.assertIn('UserKnownHostsFile=/tmp/credentials/known_hosts', command)
        self.assertEqual(command[-1], 'python3 /srv/fm/dev/release.py /srv/fm/dev')

    def test_image_namespace_is_not_masked_as_a_secret(self):
        root = Path(__file__).parents[2]
        workflows = ''.join(p.read_text() for p in (root / '.github/workflows').glob('*.yml'))
        self.assertNotIn('secrets.DOCKERHUB_USERNAME', workflows)

    def test_deploy_failure_explains_transport_and_controller_errors(self):
        """Объясняет причины отказа без публикации сырого SSH-вывода."""
        for code, stderr, expected in (
                (255, 'Host key verification failed. PRIVATE', 'DEPLOY_KNOWN_HOSTS'),
                (255, 'PRIVATE: Permission denied (publickey).', 'DEPLOY_KEY'),
                (255, 'ssh: connect to host PRIVATE: Connection timed out', 'timed out'),
                (1, 'PRIVATE\nCommand failed; inspect protected server log 1794194800000000000.log',
                 'logs/1794194800000000000.log'),
                (1, 'PRIVATE\nHTTPS smoke failed: /transaction/categories', 'HTTPS smoke'),
                (1, 'PRIVATE', 'exit 1')):
            with self.subTest(code=code, expected=expected):
                message = module.describe_failure(code, stderr)
                self.assertIn(expected, message)
                self.assertNotIn('PRIVATE', message)

    def test_success_reports_progress_and_only_verified_response_fields(self):
        """Выводит результат проверки и не переносит лишние поля ответа в Actions."""
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / 'summary'
            env = dict(self.env, DEPLOY_KEY='PRIVATE-KEY', DEPLOY_KNOWN_HOSTS='PRIVATE-HOST',
                       GITHUB_STEP_SUMMARY=str(summary))
            response = {'environment': 'dev', 'images': {
                component: self.env['DEPLOY_IMAGE']
                for component in ('ui', 'auth', 'transaction', 'postgres', 'caddy')},
                'extra': 'PRIVATE-SERVER-DATA'}
            remote = subprocess.CompletedProcess([], 0, stdout=json.dumps(response), stderr='PRIVATE-STDERR')
            output = io.StringIO()
            with patch.dict(os.environ, env, clear=True), patch.object(
                    module.subprocess, 'run', return_value=remote), redirect_stdout(output):
                module.main()
            self.assertIn('[1/3] Validating', output.getvalue())
            self.assertIn('[3/3] Server confirmed', output.getvalue())
            self.assertIn('Result: success', summary.read_text())
            self.assertNotIn('PRIVATE', output.getvalue() + summary.read_text())

    def test_rejects_command_injection_and_mutable_images(self):
        for key, value in [('DEPLOY_ROOT', '/srv/fm/dev;id'), ('DEPLOY_HOST', '-oProxyCommand=id'),
                           ('DEPLOY_USER', 'deploy root'), ('DEPLOY_PORT', '22;id'),
                           ('DEPLOY_IMAGE', 'pppoe15/fm-ui:dev'), ('DEPLOY_ENVIRONMENT', 'test')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.prepare(dict(self.env, **{key: value}), '/tmp/credentials')


if __name__ == '__main__':
    unittest.main()
