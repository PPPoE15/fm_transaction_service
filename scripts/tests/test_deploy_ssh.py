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
                 '1794194800000000000.log'),
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
                    module, 'run_ssh', return_value=remote), redirect_stdout(output):
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


    def test_response_accepts_current_and_legacy_image_sets(self):
        """Принимает четыре образа FM-123 и прежние пять без потери digest."""
        request, _ = module.prepare(self.env, '/tmp/credentials')
        for components in (('ui', 'auth', 'transaction', 'postgres'),
                           ('ui', 'auth', 'transaction', 'postgres', 'caddy')):
            with self.subTest(components=components):
                response = {'environment': 'dev', 'images': {
                    component: request['image'] for component in components}}
                self.assertEqual(module.checked_response(json.dumps(response), request), response)

    def test_response_rejects_missing_extra_and_invalid_images(self):
        """Отклоняет неполные наборы, лишние компоненты и неподтверждённые digest."""
        request, _ = module.prepare(self.env, '/tmp/credentials')
        for legacy in (False, True):
            images = dict.fromkeys(('ui', 'auth', 'transaction', 'postgres'), request['image'])
            if legacy:
                images['caddy'] = request['image']
            variants = [dict(images, extra=request['image']), dict(images, ui='repo@sha256:' + 'b' * 64)]
            variants.extend({key: value for key, value in images.items() if key != missing}
                            for missing in ('ui', 'auth', 'transaction', 'postgres'))
            variants.extend(dict(images, **{key: 'repo:latest'}) for key in images)
            for invalid in variants:
                with self.subTest(images=invalid), self.assertRaises(ValueError):
                    module.checked_response(json.dumps({'environment': 'dev', 'images': invalid}), request)
            with self.assertRaises(ValueError):
                module.checked_response(json.dumps({'environment': 'master', 'images': images}), request)

    def test_smoke_errors_allow_only_known_paths_and_protocols(self):
        """Объясняет HTTP/HTTPS smoke, не раскрывая произвольный серверный вывод."""
        for protocol in ('HTTP', 'HTTPS'):
            for endpoint in ('/', '/auth/me', '/transaction/categories'):
                with self.subTest(protocol=protocol, endpoint=endpoint):
                    error = f'{protocol} smoke failed: {endpoint}'
                    self.assertEqual(module.describe_failure(1, 'PRIVATE\n' + error),
                                     f'Server controller: {error}. Check {protocol} access from the server.')
            for endpoint in ('/PRIVATE', '/auth/me?PRIVATE', '/ PRIVATE'):
                self.assertNotIn('PRIVATE', module.describe_failure(1, f'{protocol} smoke failed: {endpoint}'))


class LiveSSHTest(unittest.TestCase):
    """Проверяет реальную передачу SSH-журнала до завершения удалённой команды."""

    def test_streams_stderr_before_completion_and_keeps_json_response(self):
        """Первая строка видна, пока удалённый процесс ещё ждёт разрешения завершиться."""
        import sys
        import threading
        import time
        from contextlib import redirect_stderr

        with tempfile.TemporaryDirectory() as directory:
            gate = Path(directory) / 'finish'
            remote_code = (
                'import json,sys,time,pathlib; json.load(sys.stdin); '
                'print("pull started", end="", file=sys.stderr, flush=True); '
                f'gate=pathlib.Path({str(gate)!r}); '
                '\nwhile not gate.exists(): time.sleep(0.01)\n'
                'print("pull finished", file=sys.stderr, flush=True); print("{}")'
            )
            output = io.StringIO()
            results = []

            def run():
                """Запустить SSH-транспорт с реальным дочерним процессом."""
                results.append(module.run_ssh([sys.executable, '-u', '-c', remote_code], {}))

            with redirect_stderr(output):
                worker = threading.Thread(target=run)
                worker.start()
                try:
                    deadline = time.monotonic() + 5
                    while 'pull started' not in output.getvalue() and worker.is_alive() and time.monotonic() < deadline:
                        time.sleep(0.01)
                    self.assertIn('pull started', output.getvalue())
                    self.assertTrue(worker.is_alive())
                finally:
                    gate.touch()
                    worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(results[0].stdout.strip(), '{}')
            self.assertEqual(results[0].returncode, 0)
            self.assertIn('pull finished', output.getvalue())
            self.assertIn('pull finished', results[0].stderr)

    def test_failure_preserves_live_traceback_and_exit_status(self):
        """Ошибка SSH выводится полностью и остаётся доступной для итоговой диагностики."""
        import sys
        from contextlib import redirect_stderr

        output = io.StringIO()
        with redirect_stderr(output):
            result = module.run_ssh(
                [sys.executable, '-c', 'import sys; print("registry unavailable", file=sys.stderr); sys.exit(7)'], {})
        self.assertEqual(result.returncode, 7)
        self.assertIn('registry unavailable', output.getvalue())
        self.assertIn('registry unavailable', result.stderr)


if __name__ == '__main__':
    unittest.main()
