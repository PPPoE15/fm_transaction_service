import importlib.util
from pathlib import Path
import unittest

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

    def test_rejects_command_injection_and_mutable_images(self):
        for key, value in [('DEPLOY_ROOT', '/srv/fm/dev;id'), ('DEPLOY_HOST', '-oProxyCommand=id'),
                           ('DEPLOY_USER', 'deploy root'), ('DEPLOY_PORT', '22;id'),
                           ('DEPLOY_IMAGE', 'pppoe15/fm-ui:dev'), ('DEPLOY_ENVIRONMENT', 'test')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.prepare(dict(self.env, **{key: value}), '/tmp/credentials')


if __name__ == '__main__':
    unittest.main()
