"""Release policy, HTTP failures, per-user cache, and nonblocking menu checks; no real network."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

import checkout
from TauFW.Framework import version


class VersionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'version.json'
        self.data = json.loads(version.MANIFEST_PATH.read_text())
        self.data['version'] = '0.1.0'
        self.path.write_text(json.dumps(self.data))
        self.now = 1_000_000.0
        clock = mock.patch.object(version.time, 'time', side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        environment = mock.patch.dict(os.environ, TAUFW_NO_VERSION_CHECK='', XDG_CACHE_HOME=str(self.root / 'user'))
        environment.start()
        self.addCleanup(environment.stop)

    def checker(self, cache_dir=None):
        return version.VersionChecker(self.path, self.root / 'cache' if cache_dir is None else cache_dir)

    def test_notification_policy_ignores_only_the_last_number(self):
        for installed, latest, expected in (
            ('0.1.0', '0.1.0', False), ('1.1.0', '1.1.1', False), ('1.1.9', '1.1.0', False),
            ('1.1.0', '1.2.3', True), ('0.9.9', '0.10.1', True), ('1.99.0', '2.0.8', True),
            ('2.0.0', '1.99.9', False), ('0.3.0', '0.2.9', False),
        ):
            with self.subTest(installed=installed, latest=latest):
                self.assertEqual(version.is_newer_version(installed, latest), expected)

    def test_local_metadata_and_construction_do_not_start_http_or_write_cache(self):
        with mock.patch.object(version, '_fetch_manifest') as fetch:
            self.assertEqual(version.current_version(self.path), '0.1.0')
            self.assertEqual(self.checker().status(start=False)['status'], 'unchecked')
        fetch.assert_not_called()
        self.assertFalse((self.root / 'cache').exists())

    def test_invalid_local_manifest_is_unavailable_and_never_requests(self):
        for data in ({}, dict(self.data, schema_version=True), dict(self.data, schema_version=2),
                     dict(self.data, project='Other'), dict(self.data, version='1.2.3-rc.1'),
                     dict(self.data, version='01.2.3'), dict(self.data, update_manifest_url='http://example.org/a')):
            with self.subTest(data=data), mock.patch.object(version, '_fetch_manifest') as fetch:
                self.path.write_text(json.dumps(data))
                self.assertEqual(self.checker().status()['status'], 'unavailable')
                fetch.assert_not_called()

    def test_http_reads_a_bounded_json_document_with_timeout(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = self.data['update_manifest_url']
        response.read.return_value = json.dumps(dict(self.data, version='0.2.3')).encode()
        with mock.patch.object(version, 'urlopen', return_value=response) as request:
            self.assertEqual(version._fetch_manifest(self.data['update_manifest_url'])['version'], '0.2.3')
        self.assertEqual(request.call_args.kwargs['timeout'], version.HTTP_TIMEOUT)
        response.read.assert_called_once_with(version.MAX_MANIFEST_BYTES + 1)
        for raw in (b'<html>login</html>', b'{}', b' ' * (version.MAX_MANIFEST_BYTES + 1)):
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                version._manifest(raw)

    def test_cache_is_recompared_with_the_local_version_and_scoped_by_source(self):
        with mock.patch.object(version, '_fetch_manifest', return_value={'version': '0.2.3'}) as fetch:
            self.assertTrue(self.checker().check()['available'])
            self.assertTrue(self.checker().status()['available'])  # fresh cache does not request again
            fetch.assert_called_once_with(self.data['update_manifest_url'])
            self.path.write_text(json.dumps(dict(self.data, version='0.3.0')))
            self.assertFalse(self.checker().status()['available'])
            fetch.assert_called_once()
        self.path.write_text(json.dumps(dict(self.data, update_manifest_url='https://gitlab.example.org/manifest')))
        self.assertEqual(self.checker().status(start=False)['status'], 'unchecked')

    def test_failed_recheck_keeps_last_known_update_and_backs_off(self):
        checker = self.checker()
        with mock.patch.object(version, '_fetch_manifest', return_value={'version': '0.2.3'}):
            checker.check()
        self.now += version.SUCCESS_TTL
        with mock.patch.object(version, '_fetch_manifest', side_effect=TimeoutError('offline')) as fetch:
            result = checker.check()
            self.assertEqual(result['status'], 'unavailable')
            self.assertTrue(result['available'])
            self.assertTrue(result['stale'])
            self.assertEqual(result['latest'], '0.2.3')
            self.now += version.FAILURE_TTL - 1
            self.assertFalse(self.checker().status()['checking'])
            fetch.assert_called_once()

    def test_a_due_check_runs_once_off_the_caller_thread(self):
        checker = self.checker()
        with mock.patch.object(version, '_fetch_manifest', return_value={'version': '0.1.9'}):
            checker.check()
        self.now += version.SUCCESS_TTL
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        caller = threading.get_ident()
        original = checker._refresh

        def fetch(source):
            self.assertNotEqual(threading.get_ident(), caller)
            entered.set()
            if not release.wait(2):
                raise TimeoutError('test did not release HTTP')
            return {'version': '0.2.3'}

        def refresh():
            try:
                original()
            finally:
                finished.set()

        with mock.patch.object(version, '_fetch_manifest', side_effect=fetch) as request, \
                mock.patch.object(checker, '_refresh', side_effect=refresh):
            try:
                self.assertTrue(checker.status()['checking'])
                self.assertTrue(entered.wait(2))
                for _ in range(3):
                    self.assertTrue(checker.status()['checking'])
                request.assert_called_once()
            finally:
                release.set()
                self.assertTrue(finished.wait(2))
        self.assertEqual(checker.status()['status'], 'available')

    def test_offline_switch_and_readonly_or_corrupt_cache_are_nonfatal(self):
        with mock.patch.dict(os.environ, TAUFW_NO_VERSION_CHECK='1'), \
                mock.patch.object(version, '_fetch_manifest') as fetch:
            self.assertEqual(self.checker().status()['status'], 'disabled')
            self.assertEqual(self.checker().check()['status'], 'disabled')
            fetch.assert_not_called()
        blocked = self.root / 'not-a-directory'
        blocked.write_text('keep')
        with mock.patch.object(version, '_fetch_manifest', return_value={'version': '0.2.1'}):
            self.assertTrue(self.checker(cache_dir=blocked).check()['available'])
            checker = self.checker()
            checker.check()
            checker._cache_path.write_text('broken JSON')
            self.assertEqual(self.checker().status(start=False)['status'], 'unchecked')

    def test_version_cli_is_local_unless_check_is_explicit(self):
        spec = importlib.util.spec_from_file_location('version_cli', checkout.TAUFW_SCRIPT)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with mock.patch.object(version, '_fetch_manifest', return_value={'version': '0.2.3'}) as fetch, \
                mock.patch.object(version, 'MANIFEST_PATH', self.path), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(['version']), 0)
            fetch.assert_not_called()
            self.assertIn('TauFW 0.1.0', output.getvalue())
            self.assertEqual(cli.main(['version', '--check']), 0)
            fetch.assert_called_once()
            self.assertIn('New version available: 0.2.3', output.getvalue())


if __name__ == '__main__':
    unittest.main()
