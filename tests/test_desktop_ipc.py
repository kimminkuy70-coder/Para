"""A1 protocol tests. Does not certify native Tauri/Windows integration."""
import io
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager import batchreport, desktop_ipc as ipc


def request(rid, method, **params):
    return dict(version=1, id=rid, method=method, params=params)


def sample():
    return [{"id": "r1", "machine": "AOI-01", "report": {
        "file_name": "한글.htm", "metadata": [["Wafers Scanned", "1"], ["Batch Time", "01:00:00"]],
        "wafers": [{"No": "1", "Pass/Fail": "Novel Error + Aborted.", "Recipe(s)": "R1"}]}}]


class Protocol(unittest.TestCase):
    def setUp(self):
        self.output = io.BytesIO()
        self.session = ipc.Session(self.output)

    def tearDown(self):
        self.session.close()

    def events(self):
        return [json.loads(line) for line in self.output.getvalue().splitlines()]

    def finish(self):
        self.session.worker.join(timeout=5)
        self.assertFalse(self.session.worker.is_alive())

    def test_contract_and_allowlist(self):
        self.session.handle(request(1, "contract"))
        self.assertEqual(set(self.events()[-1]["methods"]), ipc.METHODS)
        for i, method in enumerate(("shell", "read_file", "write_file", "eval"), 2):
            self.session.handle(request(i, method, path="C:/secret"))
            self.assertEqual(self.events()[-1]["event"], "error")

    def test_envelope_and_ids(self):
        for value in ([], {}, dict(request(1, "contract"), version=2),
                      request(1, "contract"), request(True, "contract"), request(2, "contract", extra=True)):
            self.session.handle(value)
            self.assertEqual(self.events()[-1]["event"], "error")

    def test_engine_parity_and_pagination(self):
        records = sample()
        expected = batchreport.compute(records, selected=["M03", "M10", "M11"])
        self.session.handle(request(1, "analyze", records=records, selected=["M03", "M10", "M11"]))
        self.finish()
        self.assertEqual(self.events()[-1]["summary"], expected["summary"])
        self.assertEqual([e["event"] for e in self.events()], ["accepted", "progress", "completed"])
        for i, table in enumerate(expected["tables"]):
            self.session.handle(request(i + 2, "table_page", job=1, table=i, offset=0, limit=1))
            self.assertEqual(self.events()[-1]["rows"], json.loads(ipc.encoded(table["rows"][:1])))
            self.assertEqual(self.events()[-1]["total"], len(table["rows"]))

    def test_invalid_records(self):
        bad = sample()
        bad[0]["source_folder"] = "//equipment/share"
        variants = [None, bad, sample() * 2, [{"id": "x", "machine": "m", "report": {}}]]
        for i, records in enumerate(variants, 1):
            self.session.handle(request(i, "analyze", records=records))
            self.assertEqual(self.events()[-1]["event"], "error")
            self.assertIsNone(self.session.job)

    def test_page_limits_and_release(self):
        self.session.handle(request(1, "analyze", records=sample()))
        self.finish()
        for i, params in enumerate(({"table": -1}, {"table": 0, "limit": 201}, {"table": 0, "offset": True}), 2):
            self.session.handle(request(i, "table_page", job=1, **params))
            self.assertEqual(self.events()[-1]["event"], "error")
        self.session.handle(request(5, "analyze", records=[]))
        self.assertEqual(self.events()[-1]["event"], "error")
        self.session.handle(request(6, "release", job=1))
        self.assertIsNone(self.session.result)
        self.session.handle(request(7, "analyze", records=[]))
        self.finish()
        self.assertEqual(self.events()[-1]["event"], "completed")

    def test_cancel_and_busy(self):
        entered, proceed = threading.Event(), threading.Event()
        def compute(*args, **kwargs):
            entered.set()
            if not proceed.wait(5):
                raise RuntimeError("test deadline")
            return batchreport.compute(*args, **kwargs)
        self.session.compute = compute
        self.session.handle(request(1, "analyze", records=sample()))
        try:
            self.assertTrue(entered.wait(5))
            self.session.handle(request(2, "release", job=1))
            self.assertEqual(self.events()[-1]["event"], "error")
            self.session.handle(request(3, "cancel", job=1))
            self.assertTrue(self.events()[-1]["cancellation_requested"])
        finally:
            proceed.set()
        self.finish()
        self.assertEqual(self.events()[-1]["event"], "cancelled")
        self.assertIsNone(self.session.result)

    def test_engine_error_does_not_leak_paths(self):
        def fail(*args, **kwargs):
            raise ValueError("C:/private/report password")
        self.session.compute = fail
        self.session.handle(request(1, "analyze", records=sample()))
        self.finish()
        self.assertEqual(self.events()[-1]["code"], "analysis_failed")
        self.assertNotIn(b"private", self.output.getvalue())

    def test_invalid_json_and_oversize_fail_closed(self):
        source = io.BytesIO(b"{invalid}\nNaN\n" + b"x" * (ipc.MAX_FRAME + 1) + b"\n" + ipc.encoded(request(1, "contract")))
        ipc.serve(source, self.output)
        self.assertEqual([e["code"] for e in self.events()], ["invalid_json", "invalid_json", "frame_too_large"])

    def test_process_utf8_shutdown_and_eof(self):
        for frames in ([request(1, "contract"), request(2, "shutdown")], [request(1, "contract")]):
            completed = subprocess.run([sys.executable, "-m", "param_manager.desktop_ipc"],
                input=b"".join(ipc.encoded(f) for f in frames), capture_output=True, timeout=10,
                cwd=Path(__file__).resolve().parents[1])
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(len(completed.stdout.splitlines()), len(frames))
            for line in completed.stdout.splitlines():
                self.assertEqual(json.loads(line)["event"], "completed")


if __name__ == "__main__":
    unittest.main()
