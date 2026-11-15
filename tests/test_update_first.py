"""v14.1.1 소유자: "프로그램 실행시 무조건 업데이트가 먼저 — batch restore 가 실행돼서 업데이트를 눌러도 기다리라고 떠".

엔진: 다른 작업(Batch Report 지난 결과 불러오기 · 감시 등)이 진행 중이어도 업데이트 받기(appupdate_apply)를 거절하지 않는다.
받기 = <home>/app.new 에 준비만(실행 중 파일 무변경, 적용은 다음 실행) — 같은 업데이트 두 번만 'appupdate' 자리가 막는다.
화면(시작 작업이 업데이트 확인 뒤에 도는 문)은 frontend/src/AppUpdate.tsx updateGate · Batch.tsx 가 쓰는 것을 글로 확인한다.
"""
import io
import json
import sys
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from param_manager import desktop_ipc  # noqa: E402


def frames(out):
    return [json.loads(l) for l in out.getvalue().decode().splitlines() if l.strip()]


def wait_for(out, rid, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        for f in frames(out):
            if f.get("id") == rid and f.get("event") in ("completed", "error"):
                return f
        time.sleep(0.02)
    raise AssertionError(f"no reply for {rid}: {frames(out)}")


class UpdateFirstTests(unittest.TestCase):
    def setUp(self):
        self.out = io.BytesIO()
        self.s = desktop_ipc.Session(self.out)
        self.release = threading.Event()
        self.calls = 0

        def fake_apply(params=None):
            self.calls += 1
            self.release.wait(5)
            return dict(version="14.9.9", source="github", pending=True)
        self.s.appupdate.apply = fake_apply

    def tearDown(self):
        self.release.set()
        self.s.busy.clear()
        self.s.close()

    def req(self, rid, method):
        self.s.handle({"version": desktop_ipc.VERSION, "id": rid, "method": method, "params": {}})

    def test_apply_runs_while_another_job_holds_a_slot(self):
        self.s.busy["batch"] = 99                     # Batch Report 지난 결과 불러오기가 도는 중
        self.s.busy["equipment"] = 98                 # 장비 읽기도
        self.req(1, "appupdate_apply")
        self.req(2, "appupdate_apply")                # 같은 업데이트 두 번은 막힘(받는 중)
        second = wait_for(self.out, 2)
        self.assertEqual(second["event"], "error")
        self.assertIn("업데이트", second.get("message", ""))
        self.release.set()
        first = wait_for(self.out, 1)
        self.assertEqual(first["event"], "completed", first)
        self.assertEqual(first["appupdate"]["version"], "14.9.9")
        self.assertEqual(self.calls, 1)
        self.assertEqual(self.s.busy.get("batch"), 99)   # 다른 작업 자리는 그대로

    def test_screen_starts_batch_restore_only_after_the_update_gate(self):
        upd = (ROOT / "frontend/src/AppUpdate.tsx").read_text(encoding="utf-8")
        batch = (ROOT / "frontend/src/Batch.tsx").read_text(encoding="utf-8")
        self.assertIn("export function updateGate()", upd)
        self.assertIn("void updateGate().then(restore)", batch)               # 지난 결과 불러오기 = 문 뒤
        self.assertIn("!isUpdateGateOpen()", batch)                          # 자동 분석 타이머도 문 뒤
        self.assertNotIn("disabled={busy||working", upd)                     # 다른 작업이 '지금 업데이트'를 막지 않음
        self.assertNotIn("disabled={busy} onClick={()=>void quit()}", upd)


if __name__ == "__main__":
    unittest.main(verbosity=1)
