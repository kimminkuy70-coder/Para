"""Web app self-update: zip publish to the program folder, check, verified staging, swap helper (no script)."""
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from param_manager import desktop_appupdate as au, desktop_package, desktop_swap, updater


def make_package(base, version, marker="a"):
    root = Path(base) / f"pkg_{version}_{marker}"
    (root / "sidecar").mkdir(parents=True)
    (root / "Camtek_AOI_manager.exe").write_bytes(b"app" + marker.encode())
    (root / "sidecar" / "Camtek_AOI_engine.exe").write_bytes(b"engine")
    (root / "sidecar" / "lib.dll").write_bytes(b"x" * 100)
    desktop_package.create(root, version)
    return root


class AppUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rev1-appupd-"))
        self.save = self.tmp / "OneDriveLike" / "docs"
        self.save.mkdir(parents=True)
        self.local = self.tmp / "local"
        self.cfg = self.tmp / "c.json"
        self.cfg.write_text(json.dumps({"save_dir": str(self.save), "local_dir": str(self.local)}), encoding="utf-8")
        self.adapter = au.DesktopAppUpdate(self.cfg)

    def publish(self, version, marker="a"):
        return self.adapter.publish({"path": str(make_package(self.tmp, version, marker)), "notes": f"v{version}"})

    def test_publish_is_one_zip_next_to_save_dir_and_keeps_two(self):
        for v in ("8.1.0", "8.2.0", "8.3.0"):
            self.publish(v)
        program = self.save.parent / "프로그램"                     # sibling of the save folder
        zips = sorted(n for n in os.listdir(program) if n.endswith(".zip"))
        self.assertEqual(zips, ["Camtek_AOI_manager_web_v8.2.0.zip", "Camtek_AOI_manager_web_v8.3.0.zip"])
        manifest = json.loads((program / au.WEB_MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual((manifest["version"], manifest["kind"]), ("8.3.0", "web"))
        self.assertFalse((program / updater.MANIFEST_NAME).exists())  # tkinter manifest untouched
        self.adapter.publish({"path": str(self.tmp / "pkg_8.3.0_a"), "notes": ""})   # same package again: fine
        with self.assertRaises(ValueError):                        # same version, different files
            self.publish("8.3.0", marker="b")
        bad = make_package(self.tmp, "8.4.0", "c")
        (bad / "sidecar" / "lib.dll").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            self.adapter.publish({"path": str(bad), "notes": ""})

    def test_check_and_skip(self):
        with patch.object(au, "__version__", "8.0"):
            self.assertFalse(self.adapter.check({})["newer"])
            self.publish("8.1.0")
            out = self.adapter.check({})
            self.assertEqual((out["newer"], out["available"], out["skipped"]), (True, "8.1.0", False))
            self.adapter.skip({"version": "8.1.0"})
            self.assertTrue(self.adapter.check({})["skipped"])

    def test_prepare_stages_verified_package_and_script(self):
        self.publish("8.1.0")
        install = self.tmp / "apps" / "Camtek_AOI_manager"
        (install / "sidecar").mkdir(parents=True)
        (install / "Camtek_AOI_manager.exe").write_bytes(b"old")
        with patch.object(au, "__version__", "8.0"), patch.object(au, "install_dir", return_value=install):
            with self.assertRaises(ValueError):                   # no save folder → no manifest
                au.prepare("", str(self.local))
            out = au.prepare(str(self.save), str(self.local))
        staged = Path(out["staged"])
        self.assertEqual(staged, install.parent / "Camtek_AOI_manager.new")
        self.assertTrue((staged / "sidecar" / "Camtek_AOI_engine.exe").is_file())
        self.assertEqual((install / "Camtek_AOI_manager.exe").read_bytes(), b"old")   # untouched until exit
        # Para #31: no .bat/.cmd/.ps1 written (Defender flagged web_update.bat as Trojan:Script/Wacatac).
        temp = Path(out["temp"])
        self.assertTrue(str(temp).startswith(str(self.local)))
        self.assertEqual([p for p in temp.rglob("*") if p.suffix.lower() in (".bat", ".cmd", ".ps1", ".vbs")], [])
        helper = Path(out["helper"])
        self.assertEqual(helper, temp / "swapper" / "Camtek_AOI_engine.exe")       # copy of the NEW engine
        self.assertEqual(helper.read_bytes(), b"engine")
        self.assertEqual(Path(out["plan"]), helper.parent.parent / desktop_swap.PLAN)  # where the helper looks
        plan = desktop_swap.read_plan(out["plan"])
        self.assertEqual((plan["install"], plan["staged"]), (install, staged))
        with patch.object(au.subprocess, "Popen") as popen:
            au.launch(out)
        self.assertEqual(popen.call_args.args[0], [out["helper"], "--apply-update"])

    def test_swap_helper_renames_folders_and_restarts(self):
        apps = self.tmp / "apps"
        install, staged, prev = apps / "App", apps / "App.new", apps / "App.prev"
        for folder, marker in ((install, b"old"), (staged, b"new"), (prev, b"older")):
            folder.mkdir(parents=True)
            (folder / "Camtek_AOI_manager.exe").write_bytes(marker)
        desktop_swap.write_plan(self.tmp, install, staged, prev, 5)
        plan = desktop_swap.read_plan(self.tmp / desktop_swap.PLAN)
        started = []
        self.assertEqual(desktop_swap.swap(plan, sleep=lambda s: None, start=started.append), 0)
        self.assertEqual((install / "Camtek_AOI_manager.exe").read_bytes(), b"new")
        self.assertEqual((prev / "Camtek_AOI_manager.exe").read_bytes(), b"old")     # one rollback copy
        self.assertFalse(staged.exists())
        self.assertEqual(started, [install / "Camtek_AOI_manager.exe"])
        # App never exits (rename keeps failing) → staged copy dropped, nothing started.
        staged.mkdir()
        (staged / "Camtek_AOI_manager.exe").write_bytes(b"newer")
        plan = desktop_swap.read_plan(self.tmp / desktop_swap.PLAN)
        started.clear()
        with patch.object(desktop_swap.os, "rename", side_effect=OSError("busy")):
            self.assertEqual(desktop_swap.swap(plan, sleep=lambda s: None, start=started.append), 2)
        self.assertFalse(staged.exists())
        self.assertEqual(started, [])
        self.assertEqual((install / "Camtek_AOI_manager.exe").read_bytes(), b"new")

    def test_swap_plan_accepts_only_the_fixed_rename_pattern(self):
        apps = self.tmp / "apps"
        install = apps / "App"
        (apps / "App.new").mkdir(parents=True)
        (apps / "App.new" / "Camtek_AOI_manager.exe").write_bytes(b"new")
        for staged, prev in ((apps / "Other", apps / "App.prev"), (apps / "App.new", self.tmp / "elsewhere")):
            desktop_swap.write_plan(self.tmp, install, staged, prev)
            with self.assertRaises(ValueError):
                desktop_swap.read_plan(self.tmp / desktop_swap.PLAN)
        (self.tmp / desktop_swap.PLAN).write_text(json.dumps({"install": "C:/x", "staged": "", "prev": "", "wait": 1, "cmd": "x"}))
        with self.assertRaises(ValueError):
            desktop_swap.read_plan(self.tmp / desktop_swap.PLAN)

    def test_prepare_rejects_tampered_or_unsafe_zip(self):
        release = self.publish("8.1.0")
        program = self.save.parent / "프로그램"
        install = self.tmp / "apps" / "Camtek_AOI_manager"
        (install / "sidecar").mkdir(parents=True)
        (install / "Camtek_AOI_manager.exe").write_bytes(b"old")
        zpath = program / release["filename"]
        with zipfile.ZipFile(zpath, "a") as zf:                  # changed after publishing
            zf.writestr("../escape.txt", "x")
        with patch.object(au, "__version__", "8.0"), patch.object(au, "install_dir", return_value=install):
            with self.assertRaises(ValueError):                   # size/sha no longer match
                au.prepare(str(self.save), str(self.local))
            # Even if the manifest is re-signed, a path escaping the folder is refused.
            manifest = json.loads((program / au.WEB_MANIFEST).read_text(encoding="utf-8"))
            manifest.update(sha256=updater.file_sha256(str(zpath)), size=os.path.getsize(zpath))
            (program / au.WEB_MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ValueError):
                au.prepare(str(self.save), str(self.local))
        self.assertFalse((install.parent / "Camtek_AOI_manager.new").exists())
        self.assertFalse((self.tmp / "apps" / "escape.txt").exists())

    def test_dev_run_cannot_apply_and_default_local_root(self):
        with patch.object(au, "install_dir", return_value=None):
            with self.assertRaises(ValueError):
                au.prepare(str(self.save), str(self.local))
        with patch.object(au, "install_dir", return_value=self.tmp / "apps" / "X"):
            self.assertEqual(au.default_local_root(), au.localdirs.appdata_root())
            self.assertTrue(au.inside_install(self.tmp / "apps" / "X" / "CamtekAOI"))


if __name__ == "__main__":
    unittest.main()
