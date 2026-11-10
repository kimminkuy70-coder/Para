"""배포 zip 의 엔진(sidecar)에 배치 스크립트 문구가 들어가지 않는지 (Para #58).

v12.9.30 · v12.9.31 zip 을 Windows Defender 가 `Trojan:Script/Wacatac.F!ml` 로 막았다.
zip 안에는 스크립트 파일이 없지만, PyInstaller 가 넣은 `updater.pyc` 에 tkinter 판의
자기 삭제 .bat 문구(`@echo off` · `ping -n` · `start ""` · `del "%~f0"`)가 문자열로 들어 있었다.
(Para #31 에서 막힌 `web_update.bat` 과 같은 모양.) 그 문구는 `updater_bat.py`(tkinter 전용)로
옮겼다. 엔진 진입점에서 import 되는 우리 모듈에 다시 들어오면 이 시험이 실패한다.
"""
from __future__ import annotations

import ast
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(ROOT, "tools", "desktop_engine_entry.py")

# 악성 배치 · 스크립트의 전형적인 문구. 주석(#)은 pyc 에 안 들어가지만 docstring 과 문자열은 들어간다.
MARKERS = re.compile(
    r'%~f0|@echo off|rmdir /s|ping -n|ping 127\.0\.0\.1|start ""|del /q|'
    r'powershell|-EncodedCommand|ExecutionPolicy|schtasks|wscript|cscript|reg add',
    re.IGNORECASE)


def _imports(path: str, package: str) -> set[str]:
    """그 파일이 import 하는 param_manager 모듈 이름(함수 안 import 포함 — PyInstaller 도 다 묶는다)."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), path)
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names if a.name.startswith("param_manager"))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package if node.level == 1 else package.rsplit(".", node.level - 1)[0]
                mod = f"{base}.{node.module}" if node.module else base
            else:
                mod = node.module or ""
            if not mod.startswith("param_manager"):
                continue
            out.add(mod)
            out.update(f"{mod}.{a.name}" for a in node.names)
    return out


def _engine_modules() -> dict[str, str]:
    """엔진 진입점에서 닿는 param_manager 모듈 {이름: 경로}. 외부 패키지는 보지 않는다."""
    found: dict[str, str] = {}
    todo = list(_imports(ENTRY, "param_manager"))
    while todo:
        name = todo.pop()
        if name in found:
            continue
        rel = name.replace(".", os.sep)
        for cand in (os.path.join(ROOT, rel + ".py"), os.path.join(ROOT, rel, "__init__.py")):
            if os.path.isfile(cand):
                found[name] = cand
                pkg = name if cand.endswith("__init__.py") else name.rsplit(".", 1)[0]
                todo.extend(_imports(cand, pkg))
                break
        if "." in name:                      # 부모 패키지 __init__ 도 묶인다
            todo.append(name.rsplit(".", 1)[0])
    return found


class SidecarNoScriptsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = _engine_modules()

    def test_engine_closure_found(self):
        # 진입점 분석이 실제로 돌았는지(빈 결과로 통과하지 않게)
        self.assertIn("param_manager.desktop_ipc", self.modules)
        self.assertIn("param_manager.desktop_appupdate", self.modules)

    def test_legacy_bat_module_not_bundled(self):
        self.assertIn("param_manager.updater", self.modules)
        self.assertNotIn("param_manager.updater_bat", self.modules)
        self.assertNotIn("param_manager.equip_app", self.modules)

    def test_no_script_text_in_bundled_modules(self):
        hits = {}
        for name, path in sorted(self.modules.items()):
            with open(path, encoding="utf-8", errors="ignore") as fh:
                found = sorted({m.group(0).lower() for m in MARKERS.finditer(fh.read())})
            if found:
                hits[name] = found
        self.assertEqual(hits, {}, "엔진에 묶이는 모듈에 배치 · 스크립트 문구가 있음")


if __name__ == "__main__":
    unittest.main()
