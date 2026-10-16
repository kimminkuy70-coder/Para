"""Wafer Map 전용판(특수 버전): 다른 기능이 패키지에 들어가지 않는지 · 엔진이 Wafer Map 요청만 받는지 · 빌드 설정.

사용자 결정(2026-10-16): 다른 기능은 배포하기 어려워 Wafer Map 변환만 따로 만든다. 그래서
  ① 엔진(`wafermap_ipc`)이 import 하는 프로그램 모듈은 허용 목록뿐이고, 나머지는 빌드 때 명시적으로 뺀다
  ② 엔진은 Wafer Map 요청 외의 이름(Recipe · Batch Report · 자동 업데이트 …)을 거절한다
  ③ 화면 번들은 `wafermap_main.tsx` 에서 시작해 Wafer Map 화면만 import 한다
  ④ 실행 파일 이름 · 식별자 · 엔진 이름 · 중복 실행 뮤텍스가 본 앱과 다르다(동시에 켜도 서로 막지 않음).
변환 결과(바이트 보존 등)는 `tests/test_wafermap.py` 가 본다.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import wafermap_edition as edition  # noqa: E402
from param_manager import wafermap_ipc, singleinst  # noqa: E402
from param_manager.desktop_wafermap import DesktopWaferMap  # noqa: E402

try:
    import openpyxl  # noqa: F401
    HAVE_OPENPYXL = True
except ImportError:
    HAVE_OPENPYXL = False


def run_engine(root, requests):
    """`python -m param_manager.wafermap_ipc` 에 요청을 차례로 보내고 각 요청의 마지막 응답을 돌려준다."""
    env = dict(os.environ, LOCALAPPDATA=str(Path(root) / "local"), PYTHONUTF8="1", PYTHONPATH=str(ROOT))
    proc = subprocess.Popen([sys.executable, "-m", "param_manager.wafermap_ipc"], cwd=ROOT, env=env,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    replies = []
    try:
        for rid, (method, params) in enumerate(requests, start=1):
            proc.stdin.write((json.dumps(dict(version=1, id=rid, method=method, params=params)) + "\n").encode())
            proc.stdin.flush()
            while True:
                message = json.loads(proc.stdout.readline())
                if message["event"] in ("completed", "error"):
                    replies.append(message)
                    break
    finally:
        proc.stdin.close()
        proc.wait(30)
    return replies


class ModuleScopeTests(unittest.TestCase):
    def test_engine_imports_only_the_allowlist(self):
        # 실제로 import 해서 확인(가장 확실): 엔진을 불러온 뒤 sys.modules 의 프로그램 모듈.
        code = ("import sys; import param_manager.wafermap_ipc; "
                "print(sorted(m for m in sys.modules if m.startswith('param_manager')))")
        out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True,
                             env=dict(os.environ, PYTHONPATH=str(ROOT))).stdout
        loaded = {m.split(".", 1)[1] if "." in m else "__init__" for m in eval(out)}  # noqa: S307 - our own output
        self.assertTrue(loaded <= edition.ALLOWED, loaded - edition.ALLOWED)

    def test_static_closure_outside_allowlist_is_excluded(self):
        # PyInstaller 처럼 정적으로 따라가면 함수 안 늦은 import(desktop_progress → localdirs → workdirs)도 잡힌다.
        # 그런 모듈은 모두 빌드 제외 목록에 있어야 한다.
        import modulefinder
        # 외부 패키지(site-packages)는 보지 않는다 — 프로그램 모듈만 따지면 되고, namespace 패키지에서 modulefinder 가 멈춘다.
        stdlib = [p for p in sys.path if p and "site-packages" not in p and "dist-packages" not in p]
        finder = modulefinder.ModuleFinder(path=[str(ROOT)] + stdlib)
        finder.run_script(str(ROOT / "tools" / "wafermap_engine_entry.py"))
        found = {m.split(".", 1)[1] for m in finder.modules if m.startswith("param_manager.")}
        excluded = {m.split(".", 1)[1] for m in edition.excluded_modules()}
        self.assertTrue(found - edition.ALLOWED, "늦은 import 가 하나도 안 잡히면 검사 자체가 잘못된 것")
        self.assertEqual(found - edition.ALLOWED - excluded, set())

    def test_every_other_program_module_is_excluded(self):
        excluded = {m.split(".", 1)[1] for m in edition.excluded_modules()}
        self.assertEqual(excluded | edition.ALLOWED, set(edition.program_modules()))
        self.assertFalse(excluded & edition.ALLOWED)
        for other in ("desktop_ipc", "collector", "batchview", "commonality", "desktop_appupdate", "updater",
                      "localdirs", "workdirs", "watcher", "colorgray", "equip_app"):
            self.assertIn(other, excluded)
        args = edition.exclude_args()
        self.assertEqual(args[::2], ["--exclude-module"] * (len(args) // 2))
        self.assertIn("tkinter", args)

    def test_bundle_check_reads_noarchive_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "_internal" / "param_manager"
            pkg.mkdir(parents=True)
            for name in edition.ALLOWED:
                (pkg / f"{name}.pyc").write_bytes(b"")
            self.assertEqual(edition.main(["check", tmp]), 0)
            (pkg / "collector.pyc").write_bytes(b"")
            self.assertEqual(edition.main(["check", tmp]), 1)

    def test_engine_has_no_update_shell_or_network_code(self):
        src = (ROOT / "param_manager" / "wafermap_ipc.py").read_text(encoding="utf-8")
        for word in ("appupdate", "updater", ".bat", "cmd.exe", "shell=True", "net use", "socket", "urllib", "http"):
            self.assertNotIn(word, src, word)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        DesktopWaferMap.extra_roots = []

    def tearDown(self):
        self.tmp.cleanup()
        DesktopWaferMap.extra_roots = []

    def test_contract_lists_only_wafer_map_methods(self):
        contract, config = run_engine(self.root, [("contract", {}), ("configuration", {})])
        self.assertEqual(set(contract["methods"]), set(wafermap_ipc.METHODS))
        self.assertTrue(all(m.startswith("wm_") or m in ("contract", "configuration", "open_path", "diag_client")
                            for m in contract["methods"]))
        self.assertEqual(config["product"], "Wafer Map 변환")
        self.assertEqual(config["version"], 1, "protocol version stays 1 (app version is app_version)")
        self.assertTrue(config["local_root"].endswith("CamtekAOI_WaferMap"))

    def test_other_features_are_refused_by_name(self):
        others = ["investigate", "batch_view", "recipe_open", "formnew_collect", "update_collect", "cmrun_copy",
                  "appupdate_apply", "appupdate_publish", "config_set_save_dir", "pwatch_run", "cgm_scan", "shutdown"]
        replies = run_engine(self.root, [(m, {}) for m in others])
        self.assertEqual([r["code"] for r in replies], ["invalid_request"] * len(others))

    def test_unexpected_params_are_refused(self):
        (reply,) = run_engine(self.root, [("wm_scan", {"root": str(self.root), "mode": "txt", "shell": "x"})])
        self.assertEqual(reply["code"], "invalid_request")

    @unittest.skipUnless(HAVE_OPENPYXL, "openpyxl 필요")
    def test_txt_to_excel_flow_keeps_source(self):
        from test_wafermap import sample_txt
        src = self.root / "W01.txt"
        src.write_bytes(sample_txt("\r\n"))
        scan, = run_engine(self.root, [("wm_scan", {"root": str(self.root), "mode": "txt"})])
        self.assertEqual(scan["wafermap"]["valid"], 1)
        ids = [i["id"] for i in scan["wafermap"]["items"] if i["valid"]]
        _, start, convert = run_engine(self.root, [("wm_scan", {"root": str(self.root), "mode": "txt"}),
                                                   ("wm_start", {"ids": ids, "output": ""}),
                                                   ("wm_convert", {"index": 0})])
        self.assertEqual(convert["event"], "completed", convert)
        self.assertTrue(Path(convert["wafermap"]["output"]).is_file())
        self.assertEqual(src.read_bytes(), sample_txt("\r\n"), "원본 보존")

    def test_open_path_only_inside_this_conversion(self):
        outside = self.root / "other.xlsx"
        outside.write_bytes(b"x")
        with self.assertRaises(ValueError):
            wafermap_ipc.resolve_openable(str(outside))
        DesktopWaferMap.extra_roots.append(str(self.root))
        self.assertEqual(wafermap_ipc.resolve_openable(str(outside)), outside.absolute())
        script = self.root / "run.bat"
        script.write_text("echo")
        with self.assertRaises(ValueError):
            wafermap_ipc.resolve_openable(str(script))


class BuildConfigTests(unittest.TestCase):
    def test_entry_uses_its_own_engine_and_mutex(self):
        src = (ROOT / "tools" / "wafermap_engine_entry.py").read_text(encoding="utf-8")
        self.assertIn("from param_manager import wafermap_ipc", src)
        self.assertNotIn("desktop_ipc", src)
        frame = int(eval(re.search(r"MAX_FRAME = ([0-9 *]+)", src).group(1)))  # noqa: S307 - literal
        self.assertEqual(frame, wafermap_ipc.MAX_FRAME)
        mutex = re.search(r'MUTEX_NAME = r"([^"]+)"', src).group(1)
        self.assertNotEqual(mutex, singleinst.MUTEX_NAME)
        self.assertTrue(mutex.startswith("Local\\"))

    def test_native_shell_overlay(self):
        native = ROOT / "frontend" / "src-tauri"
        base = json.loads((native / "tauri.conf.json").read_text(encoding="utf-8"))
        over = json.loads((native / "tauri.wafermap.conf.json").read_text(encoding="utf-8"))
        self.assertNotEqual(over["identifier"], base["identifier"])       # own WebView2 data · own app
        self.assertEqual(over["productName"], "Wafer Map 변환")
        self.assertEqual(over["build"]["frontendDist"], "../dist-wafermap")
        self.assertIn("build:wafermap", over["build"]["beforeBuildCommand"])
        self.assertEqual(over["app"]["windows"][0]["title"], "Wafer Map 변환")
        self.assertIn("wafermap = []", (native / "Cargo.toml").read_text(encoding="utf-8"))
        rust = (native / "src" / "desktop.rs").read_text(encoding="utf-8")
        self.assertIn('"Camtek_AOI_WaferMap_engine.exe"', rust)
        self.assertIn('"param_manager.wafermap_ipc"', rust)
        self.assertIn('if cfg!(feature = "wafermap") { return Ok(()); }', (native / "src" / "lib.rs").read_text(encoding="utf-8"))

    def test_frontend_bundle_starts_from_wafer_map_only(self):
        src = ROOT / "frontend" / "src"
        seen, todo = set(), ["wafermap_main"]
        while todo:
            name = todo.pop()
            if name in seen:
                continue
            seen.add(name)
            path = next(p for p in (src / f"{name}.tsx", src / f"{name}.ts") if p.exists())
            todo += re.findall(r"from '\./([A-Za-z_]+)'", path.read_text(encoding="utf-8"))
        self.assertEqual(seen, {"wafermap_main", "desktop", "ui", "WaferMap", "RowPick", "OpenPath"})
        html = (ROOT / "frontend" / "wafermap" / "index.html").read_text(encoding="utf-8")
        self.assertIn("../src/wafermap_main.tsx", html)
        self.assertNotIn("main.tsx\"", html.replace("wafermap_main.tsx\"", ""))
        vite = (ROOT / "frontend" / "vite.wafermap.config.ts").read_text(encoding="utf-8")
        self.assertIn("root:'wafermap'", vite)
        self.assertIn("outDir:'../dist-wafermap'", vite)

    def test_user_facing_texts_say_wafer_map_and_credit_the_developer(self):
        # 사용자 지시(2026-10-16): 프로그램 문구는 'Wafer Map 변환'(본 앱 이름을 쓰지 않음), 왼쪽 아래에 개발자 표시.
        texts = {p: (ROOT / p).read_text(encoding="utf-8") for p in (
            "frontend/src/wafermap_main.tsx", "frontend/wafermap/index.html", "frontend/src-tauri/tauri.wafermap.conf.json",
            "param_manager/wafermap_ipc.py", "docs/WAFERMAP_사용법.md", "docs/release_notes/wafermap-v1.0.0.md")}
        for path, text in texts.items():
            self.assertNotIn("Manager", text, path)
            self.assertNotIn("Camtek AOI", text, path)
        self.assertIn("<title>Wafer Map 변환</title>", texts["frontend/wafermap/index.html"])
        self.assertIn("개발: 김민규", texts["frontend/src/wafermap_main.tsx"])
        self.assertIn("<footer><span>Wafer Map 변환", texts["frontend/src/wafermap_main.tsx"])   # footer 왼쪽 칸
        self.assertIn("<WaferMap standalone/>", texts["frontend/src/wafermap_main.tsx"])
        wf = (ROOT / ".github" / "workflows" / "build-desktop.yml").read_text(encoding="utf-8")
        self.assertIn('--title "Wafer Map 변환 v$ver"', wf)

    def test_workflow_builds_the_edition_only(self):
        wf = (ROOT / ".github" / "workflows" / "build-desktop.yml").read_text(encoding="utf-8")
        self.assertIn("tools/wafermap_engine_entry.py", wf)
        self.assertNotIn("tools/desktop_engine_entry.py", wf)
        self.assertIn("tools/wafermap_edition.py excludes", wf)
        self.assertIn('tools/wafermap_edition.py check', wf)
        self.assertIn("--features wafermap", wf)
        self.assertIn("tauri.wafermap.conf.json", wf)
        self.assertIn('"wafermap-v*.*.*"', wf)
        self.assertIn("--latest=false", wf)                 # the main app's release stays "Latest"
        self.assertNotIn("desktop_bundle.py", wf)            # no self-update manifest
        self.assertNotIn("--add-data", wf)                   # no param_manager/data in the edition
        self.assertIn("SHA256SUMS.txt", wf)
        self.assertTrue((ROOT / "docs" / "WAFERMAP_사용법.md").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
