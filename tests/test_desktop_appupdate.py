"""Web app self-update: zip publish to the program folder, check, verified staging, swap script."""
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from param_manager import desktop_appupdate as au, desktop_package, updater


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
        script = Path(out["script"]).read_bytes().decode("cp949")
        self.assertIn('move "%APP%" "%PREV%.tmp"', script)                            # rename = exit signal
        self.assertNotIn("timeout", script.lower())
        self.assertNotIn("tasklist", script.lower())
        self.assertTrue(out["script"].startswith(str(self.local)))

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
