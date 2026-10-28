import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import bridge


class Response(io.BytesIO):
    def __init__(self, data, length=None):
        super().__init__(data)
        self.headers = {'Content-Length': str(len(data) if length is None else length)}


class BridgeTests(unittest.TestCase):
    def test_hame_endpoint_is_loopback_only(self):
        for value in ['http://127.0.0.1:8088', 'http://[::1]:8089/']:
            with patch.dict(os.environ, {'HAME_BRIDGE_URL': value}):
                self.assertEqual(bridge.hame_url(), value.rstrip('/'))
        for value in ['https://example.com', 'http://example.com', 'http://127.0.0.1/path',
                      'http://user:pass@127.0.0.1', 'http://127.0.0.1?key=secret']:
            with patch.dict(os.environ, {'HAME_BRIDGE_URL': value}):
                with self.assertRaises(ValueError):
                    bridge.hame_url()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.store = bridge.Store(self.home)
        self.store.set('thread_id', 'dedicated-test-thread')
        self.spec = bridge.validate_spec({'url': 'https://example.com/file', 'filename': 'file.txt'})

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_submission_idempotence_and_authorization(self):
        one = bridge.submit(self.store, self.spec, 'test-1')
        two = bridge.submit(self.store, self.spec, 'test-1')
        self.assertEqual(one, two)
        with self.assertRaises(ValueError):
            bridge.submit(self.store, {**self.spec, 'filename': 'other'}, 'test-1')

    def test_recovery_never_reexecutes_or_resends_uncertain(self):
        bridge.submit(self.store, self.spec, 'running')
        bridge.submit(self.store, self.spec, 'sending')
        self.store.update('running', state='running')
        self.store.update('sending', state='completed', result=bridge.dumps({'verified': True}), notification='sending')
        self.store.db.close()
        self.store = bridge.Store(self.home)
        self.store.recover()
        self.assertEqual(self.store.task('running')['state'], 'needs_attention')
        self.assertEqual(self.store.task('sending')['notification'], 'needs_attention')
        self.assertTrue(self.store.task('sending')['result']['verified'])

    def test_download_integrity_and_no_overwrite(self):
        content = b'HAME bridge test\n'
        spec = {**self.spec, 'sha256': hashlib.sha256(content).hexdigest()}
        with patch('urllib.request.OpenerDirector.open', return_value=Response(content)):
            result = bridge.download(self.home, spec, 'valid')
        self.assertTrue(result['verified'])
        self.assertEqual(Path(result['path']).read_bytes(), content)
        with self.assertRaises(FileExistsError):
            bridge.download(self.home, spec, 'again')

    def test_bad_hash_does_not_publish(self):
        with patch('urllib.request.OpenerDirector.open', return_value=Response(b'bad')):
            with self.assertRaises(ValueError):
                bridge.download(self.home, {**self.spec, 'sha256': '0'*64}, 'bad-hash')
        self.assertFalse((self.home/'downloads'/'file.txt').exists())
        self.assertTrue((self.home/'downloads'/'.bad-hash.partial').exists())

    def test_size_limit_and_truncation(self):
        for data, length, limit in [(b'123', 3, 2), (b'123', 5, 10)]:
            with self.subTest(length=length):
                with patch('urllib.request.OpenerDirector.open', return_value=Response(data, length)):
                    with self.assertRaises(ValueError):
                        bridge.download(self.home, {**self.spec, 'max_bytes': limit}, str(length))
        self.assertFalse((self.home/'downloads'/'file.txt').exists())

    def test_path_and_url_validation(self):
        for name in ['../escape', 'C:\\escape', 'nul.txt', 'file.', 'a/b', '.partial']:
            with self.assertRaises(ValueError):
                bridge.validate_spec({**self.spec, 'filename': name})
        for url in ['file:///x', 'http://example.com', 'https://u:p@example.com', 'https://example.com/?token=secret']:
            with self.assertRaises(ValueError):
                bridge.validate_spec({**self.spec, 'url': url})

    def test_worker_records_failure_and_notifies_correct_thread(self):
        bridge.submit(self.store, self.spec, 'fail')
        captured = []
        def notifier(store, task):
            captured.append(task)
            store.update(task['id'], notification='notified')
        with patch('bridge.hame', side_effect=ConnectionError('secret')), patch('bridge.notify', side_effect=notifier):
            bridge.worker(self.store, once=True)
        task = self.store.task('fail')
        self.assertEqual(task['state'], 'failed')
        self.assertEqual(task['notification'], 'notified')
        self.assertEqual(captured[0]['thread_id'], 'dedicated-test-thread')
        self.assertNotIn('secret', json.dumps(task))

    def test_callback_failure_is_not_retried(self):
        bridge.submit(self.store, self.spec, 'done', ['completed'])
        self.store.update('done', state='completed', notification='notification_pending', result='{}')
        with patch('bridge.notify', side_effect=ConnectionError()) as notifier:
            bridge.worker(self.store, once=True)
            bridge.worker(self.store, once=True)
        self.assertEqual(notifier.call_count, 1)
        self.assertEqual(self.store.task('done')['notification'], 'needs_attention')

    def test_success_default_does_not_open_codex_even_after_restart(self):
        bridge.submit(self.store, self.spec, 'quiet')
        with patch('bridge.hame', return_value={'action': 'download'}), patch('bridge.download', return_value={'verified': True}), patch('bridge.RPC') as rpc:
            bridge.worker(self.store, once=True)
            self.store.db.close()
            self.store = bridge.Store(self.home)
            bridge.worker(self.store, once=True)
        rpc.assert_not_called()
        task = self.store.task('quiet')
        self.assertEqual(task['state'], 'completed')
        self.assertEqual(task['notification'], 'suppressed')
        self.assertTrue(task['result']['verified'])

    def test_explicit_success_callback(self):
        bridge.submit(self.store, self.spec, 'requested', ['completed'])
        with patch('bridge.hame', return_value={}), patch('bridge.download', return_value={'verified': True}), patch('bridge.notify') as notify:
            bridge.worker(self.store, once=True)
        notify.assert_called_once()

    def test_recovery_notifies_attention_by_default(self):
        bridge.submit(self.store, self.spec, 'interrupted')
        self.store.update('interrupted', state='running')
        with patch('bridge.notify') as notify:
            bridge.worker(self.store, once=True)
        self.assertEqual(notify.call_args.args[1]['state'], 'needs_attention')

    def test_empty_policy_and_invalid_policy(self):
        bridge.submit(self.store, self.spec, 'silent', [])
        with patch('bridge.hame', side_effect=ConnectionError()), patch('bridge.RPC') as rpc:
            bridge.worker(self.store, once=True)
        rpc.assert_not_called()
        self.assertEqual(self.store.task('silent')['notification'], 'suppressed')
        for value in ('completed', ['invalid'], [42]):
            with self.assertRaises(ValueError):
                bridge.submit(self.store, self.spec, 'invalid', value)
        with self.assertRaises(ValueError):
            bridge.submit(self.store, self.spec, 'silent', ['completed'])

    def test_worker_exclusive_lock(self):
        with bridge.worker_lock(self.home):
            with self.assertRaises(RuntimeError):
                with bridge.worker_lock(self.home):
                    pass

    def test_hame_cannot_change_authorized_action(self):
        payload = json.dumps({'choices': [{'message': {'content': '{"action":"shell","command":"bad"}'}}]}).encode()
        with patch('urllib.request.OpenerDirector.open', return_value=Response(payload)):
            with self.assertRaises(ValueError):
                bridge.hame(self.spec, 'test')


if __name__ == '__main__':
    unittest.main()
