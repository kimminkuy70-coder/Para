"""Worker lifecycle tests; not Windows/OneDrive integration certification."""
import io
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager.desktop_ipc import Session


class DocumentWorkerTests(unittest.TestCase):
    def test_slow_document_does_not_block_contract_and_rejects_mutations(self):
        for method, attribute, params in (
                ('document_open', 'open', {'kind': 'ip'}),
                ('document_edit', 'edit', {}),
                ('document_append', 'append', {})):
            with self.subTest(method=method):
                output = io.BytesIO()
                session = Session(output)
                started, proceed, closed = threading.Event(), threading.Event(), threading.Event()
                def slow(*args):
                    started.set()
                    if not proceed.wait(5):
                        raise RuntimeError('test timeout')
                    return {'snapshot': 'finished'}
                def send(i, name, values):
                    session.handle(dict(version=1, id=i, method=name, params=values))
                with patch.object(session.documents, attribute, side_effect=slow):
                    try:
                        send(1, method, params)
                        self.assertTrue(started.wait(2))
                        send(2, 'contract', {})
                        send(3, 'document_page', {'snapshot': 'old'})
                        send(4, 'analyze', {'records': []})
                        send(5, 'recipe_open', {})
                        send(6, 'shutdown', {})
                        closer = threading.Thread(target=lambda: (session.close(), closed.set()))
                        closer.start()
                        self.assertFalse(closed.wait(.05))
                    finally:
                        proceed.set()
                        session.close()
                        if 'closer' in locals():
                            closer.join(2)
                events = [json.loads(line) for line in output.getvalue().splitlines()]
                self.assertEqual(events[0]['event'], 'accepted')
                self.assertTrue(any(e['id']==2 and e['event']=='completed' for e in events))
                for i in (3,4,5):
                    self.assertTrue(any(e['id']==i and e['event']=='error' for e in events))
                self.assertEqual(events[-1]['document']['snapshot'], 'finished')
                self.assertFalse(session.worker.is_alive())

    def test_error_clears_busy_and_sanitizes_os_details(self):
        output = io.BytesIO()
        session = Session(output)
        self.addCleanup(session.close)
        with patch.object(session.documents, 'open', side_effect=OSError('private-password-path')):
            session.handle(dict(version=1,id=1,method='document_open',params={'kind':'ip'}))
            session.worker.join(2)
        self.assertFalse(session.running)
        self.assertNotIn(b'private-password-path', output.getvalue())
        with patch.object(session.documents, 'open', return_value={'snapshot':'retry'}):
            session.handle(dict(version=1,id=2,method='document_open',params={'kind':'ip'}))
            session.worker.join(2)
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(events[-1]['document']['snapshot'], 'retry')


if __name__ == '__main__':
    unittest.main()
