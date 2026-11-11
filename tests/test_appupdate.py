"""v13 update: GitHub release feed (main) + OneDrive (backup), staged as app.new (docs/V13_계획.md 4-1)."""
import json
import os
import re
import runpy
import shutil
import sys
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from param_manager import deploy, desktop_appupdate as au  # noqa: E402

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
 <entry><updated>2026-11-12T01:00:00Z</updated><link rel="alternate" href="https://github.com/kimminkuy70-coder/Para/releases/tag/v13.0.10"/>
  <title>v13.0.10</title><content type="html">&lt;h2&gt;고친 것&lt;/h2&gt;&lt;ul&gt;&lt;li&gt;A&lt;/li&gt;&lt;/ul&gt;</content></entry>
 <entry><updated>2026-11-11T01:00:00Z</updated><link rel="alternate" href="https://github.com/kimminkuy70-coder/Para/releases/tag/v13.0.9"/><title>x</title><content type="html">old</content></entry>
 <entry><link rel="alternate" href="https://github.com/kimminkuy70-coder/Para/releases/tag/v13.1.0-rc1"/><title>rc</title></entry>
 <entry><link rel="alternate" href="https://github.com/kimminkuy70-coder/Para/releases/tag/v12.9.40"/><title>v12</title></entry>
</feed>""".encode("utf-8")


def source_zip(dest: Path, version: str, extra: dict | None = None, top="Para-13.9.9") -> Path:
    """A GitHub-style tag zip (one top folder) holding the deploy files with `version`."""
    work = dest.parent / ("src_" + dest.stem)
    for rel in deploy.files(ROOT):
        (work / top / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, work / top / rel)
    init = work / top / "param_manager" / "__init__.py"
    init.write_text(re.sub(r'^__version__ = "[^"]+"', f'__version__ = "{version}"', init.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")
    for rel, data in (extra or {}).items():
        (work / top / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / top / rel).write_bytes(data)
    with zipfile.ZipFile(dest, "w") as z:
        for f in (work / top).rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(work).as_posix())
    shutil.rmtree(work)
    return dest


class FeedTest(unittest.TestCase):
    def test_only_plain_v13_tags_newest_first_with_text_notes(self):
        e = au.parse_feed(FEED)
        self.assertEqual([x["tag"] for x in e], ["v13.0.10", "v13.0.9"])   # 10 > 9, rc and v12 ignored
        self.assertIn("고친 것", e[0]["notes"])
        self.assertNotIn("<", e[0]["notes"])

    def test_version_compare(self):
        self.assertTrue(au.is_newer("13.0.10", "13.0.9"))
        self.assertFalse(au.is_newer("13.0.0", "13.0.0"))

    def test_only_github_hosts_over_https(self):
        for url in ("http://github.com/x", "https://evil.example/x", "https://api.github.com/x"):
            with self.assertRaises(ValueError):
                au._get(url, 1, 10)
        h = au._Redirects()
        with self.assertRaises(urllib.error.URLError):
            h.redirect_request(mock.Mock(), None, 302, "", {}, "https://evil.example/a.zip")

    def test_tls_is_verified(self):
        opener = au._opener()
        https = [h for h in opener.handlers if h.__class__.__name__ == "HTTPSHandler"][0]
        self.assertEqual(https._context.verify_mode, __import__("ssl").CERT_REQUIRED)
        self.assertTrue(https._context.check_hostname)

    def test_no_user_details_in_request(self):
        self.assertEqual(au.USER_AGENT, "Para-Updater")
        self.assertEqual(au.FEED, "https://github.com/kimminkuy70-coder/Para/releases.atom")


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.home = t / "home"
        (self.home / "app").mkdir(parents=True)
        self.save = t / "share" / "docs"
        self.save.mkdir(parents=True)
        self.cfg = t / "c.json"
        self.cfg.write_text(json.dumps({"save_dir": str(self.save), "local_dir": str(t / "local")}), encoding="utf-8")
        self.env = mock.patch.dict(os.environ, {"PARA_APP_HOME": str(self.home)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def adapter(self, version="13.9.9", extra=None, top=None):
        a = au.DesktopAppUpdate(self.cfg)
        tag = "v" + version
        feed = FEED.replace(b"v13.0.10", tag.encode())
        a.fetch_feed = lambda: feed
        z = source_zip(Path(self.tmp.name) / f"{tag}.zip", version, extra, top=top or f"Para-{version}")
        a.download = lambda _tag, dest: shutil.copyfile(z, dest)
        return a

    def test_check_then_apply_stages_app_new_that_the_start_file_swaps_in(self):
        a = self.adapter()
        r = a.check()
        self.assertEqual((r["available"], r["newer"], r["source"], r["installed"]), ("13.9.9", True, "github", True))
        out = a.apply()
        self.assertEqual(out, {"version": "13.9.9", "source": "github", "pending": True})
        # nothing restarts by itself: the next check reports the download as waiting for a restart
        r2 = a.check()
        self.assertEqual((r2["pending"], r2["pending_ready"]), ("13.9.9", True))
        new = self.home / "app.new"
        self.assertTrue((new / "param_manager" / "launcher.py").is_file())
        self.assertEqual(sorted(deploy.files(new)), sorted(deploy.files(ROOT)))
        self.assertFalse((self.home / "app.new.part").exists())
        self.assertFalse(list((Path(self.tmp.name) / "local").rglob("source.zip")))   # Temp cleaned
        start = runpy.run_path(str(ROOT / "Camtek_AOI_manager.pyw"), run_name="para_start_test")
        start["_swap"](str(self.home))
        self.assertIn('"13.9.9"', (self.home / "app" / "param_manager" / "__init__.py").read_text(encoding="utf-8"))

    def test_executable_inside_is_refused(self):
        a = self.adapter(extra={"vendor/x.exe": b"MZ"})
        a.check()
        with self.assertRaisesRegex(ValueError, "실행 파일"):
            a.apply()
        self.assertFalse((self.home / "app.new").exists())

    def test_tag_and_program_version_must_match(self):
        a = self.adapter()
        a.fetch_feed = lambda: FEED.replace(b"v13.0.10", b"v13.9.8")
        a.check()
        with self.assertRaisesRegex(ValueError, "버전"):
            a.apply()

    def test_zip_path_escape_refused(self):
        bad = Path(self.tmp.name) / "bad.zip"
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("../evil.py", "x")
        with self.assertRaises(ValueError):
            au._safe_extract(bad, Path(self.tmp.name) / "x")

    def test_source_copy_never_self_updates(self):
        a = self.adapter()
        with mock.patch.dict(os.environ, {"PARA_APP_HOME": ""}):
            os.environ.pop("PARA_APP_HOME")
            self.assertFalse(a.check()["installed"])
            with self.assertRaisesRegex(ValueError, "소스 폴더"):
                a.apply()

    def test_onedrive_backup_when_github_unreachable(self):
        a = self.adapter("13.9.9")
        pub = a.publish({"path": str(source_zip(Path(self.tmp.name) / "p.zip", "13.9.9")), "notes": "노트"})
        folder = Path(au.program_dir(str(self.save)))
        self.assertEqual(folder, self.save.parent / "프로그램")
        self.assertEqual(sorted(p.name for p in folder.iterdir()), sorted([au.MANIFEST, pub["file"]]))
        a.fetch_feed = lambda: (_ for _ in ()).throw(OSError("offline"))
        r = a.check()
        self.assertEqual((r["source"], r["available"], r["changelog"]), ("onedrive", "13.9.9", "노트"))
        self.assertIn("GitHub", r["error"])
        a.apply()
        self.assertTrue((self.home / "app.new" / "param_manager" / "launcher.py").is_file())
        # a half-synced file (size/SHA mismatch) is refused
        shutil.rmtree(self.home / "app.new")
        with open(folder / pub["file"], "ab") as fh:
            fh.write(b"x")
        a.check()
        with self.assertRaises(ValueError):
            a.apply()

    def test_publish_refuses_non_v13_and_prune_keeps_two(self):
        a = self.adapter()
        with self.assertRaisesRegex(ValueError, "v13"):
            a.publish({"path": str(source_zip(Path(self.tmp.name) / "old.zip", "12.9.40", top="Para-12"))})
        folder = Path(au.program_dir(str(self.save)))
        folder.mkdir(parents=True)
        for v in ("13.0.1", "13.0.2", "13.0.10"):
            (folder / f"{au.ZIP_PREFIX}{v}{au.ZIP_SUFFIX}").write_bytes(b"z")
        (folder / "someone_else.zip").write_bytes(b"z")
        au.prune(folder, f"{au.ZIP_PREFIX}13.0.10{au.ZIP_SUFFIX}")
        self.assertEqual(sorted(p.name for p in folder.iterdir()),
                         sorted(["someone_else.zip", f"{au.ZIP_PREFIX}13.0.10{au.ZIP_SUFFIX}", f"{au.ZIP_PREFIX}13.0.2{au.ZIP_SUFFIX}"]))


if __name__ == "__main__":
    unittest.main()
