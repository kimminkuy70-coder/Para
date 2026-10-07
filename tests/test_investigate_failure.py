"""이슈 #15: 조사 실패 원인 기록 · 원인별 문장 · 원문 내장 압축(스트리밍)."""
import base64
import gzip
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager import desktop_ipc as ipc, report_theme


class FakeView:
    def __init__(self, n):
        self.records = list(range(n))

    def raw(self, g):
        return dict(f=f'한글_{g}.htm', m=f'AOI-{g:02d}', meta=[['Batch Time', '01:00']], h=['No', 'Pass/Fail'],
                    rows=[[str(i), 'Pass'] for i in range(3)])


class RawBlob(unittest.TestCase):
    def test_streamed_blob_is_plain_gzip_json_in_order(self):
        view = FakeView(5)
        data = json.loads(gzip.decompress(base64.b64decode(report_theme.raw_blob(view))).decode('utf-8'))
        self.assertEqual(len(data), 5)
        self.assertEqual(data[3], ['한글_3.htm', 'AOI-03', [['Batch Time', '01:00']], ['No', 'Pass/Fail'],
                                   [['0', 'Pass'], ['1', 'Pass'], ['2', 'Pass']]])

    def test_empty_view(self):
        self.assertEqual(json.loads(gzip.decompress(base64.b64decode(report_theme.raw_blob(FakeView(0))))), [])


class Message(unittest.TestCase):
    def test_memory_error_names_the_cause(self):
        self.assertIn('메모리가 부족', ipc.investigation_message(MemoryError()))

    def test_engine_value_error_is_shown_as_is(self):
        self.assertEqual(ipc.investigation_message(ValueError('기존 Report 폴더 설정을 확인하세요')), '기존 Report 폴더 설정을 확인하세요')

    def test_os_error_hides_path(self):
        text = ipc.investigation_message(OSError(28, 'No space left on device', r'C:\secret\path'))
        self.assertIn('No space left on device', text)
        self.assertNotIn('secret', text)

    def test_unexpected_error_names_type(self):
        self.assertIn('KeyError', ipc.investigation_message(KeyError('x')))


if __name__ == '__main__':
    unittest.main()
