import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
spec = importlib.util.spec_from_file_location('bundle',Path(__file__).resolve().parents[1]/'tools/desktop_bundle.py')
bundle = importlib.util.module_from_spec(spec); spec.loader.exec_module(bundle)

class PackageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        (self.root/'sidecar').mkdir()
        for name in bundle.REQUIRED:(self.root/name).write_bytes(b'fixture-not-executable')

    def test_integrity_and_damage(self):
        bundle.create(self.root,'8.1.0');self.assertFalse(bundle.verify(self.root)['deployment_approved'])
        (self.root/'sidecar/Camtek_AOI_engine.exe').write_bytes(b'changed')
        with self.assertRaises(ValueError):bundle.verify(self.root)

    def test_no_exe_only_or_extra_files(self):
        bundle.create(self.root,'8.1.0');(self.root/'extra.txt').write_text('unexpected')
        with self.assertRaises(ValueError):bundle.verify(self.root)
        (self.root/'sidecar/Camtek_AOI_engine.exe').unlink()
        with self.assertRaises(ValueError):bundle.inventory(self.root)

    def test_no_overwrite_or_links(self):
        bundle.create(self.root,'8.1.0')
        with self.assertRaises(FileExistsError):bundle.create(self.root,'8.2.0')
        try:(self.root/'linked').symlink_to(self.root/'Camtek_AOI_manager.exe')
        except OSError:self.skipTest('symlink not available')
        with self.assertRaises(ValueError):bundle.inventory(self.root)

    def test_version_validation(self):
        for value in ('8.0','../8.1.0','01.2.3','1.2.65536'):
            with self.assertRaises(ValueError):bundle.version(value)

if __name__=='__main__':unittest.main()
