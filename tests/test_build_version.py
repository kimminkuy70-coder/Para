"""Verify entered versions and old/new release compatibility without Windows."""
import importlib.util
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from param_manager import updater

spec = importlib.util.spec_from_file_location('set_version', ROOT / 'tools/set_version.py')
version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        version.INIT_PY = str(Path(tmp) / '__init__.py')
        version.VERSION_INFO = str(Path(tmp) / 'version_info.txt')
        Path(version.INIT_PY).write_text('__version__ = "4.0.3"\n')
        for entered, expected in [('8.0', '8.0'), ('v8.1.2', '8.1.2'), ('9.0', '9.0')]:
            version.main([entered])
            assert version.current_version() == expected
            resource = Path(version.VERSION_INFO).read_text()
            assert f"filevers={version.quad(expected)}" in resource
            assert updater.exe_filename(expected) in resource
            assert f"ProductVersion', '{expected}'" in resource
        for bad in ['8.0.0.0.1', '65536.0', '8.x', '']:
            try:
                version.normalize(bad)
            except SystemExit:
                pass
            else:
                raise AssertionError(bad)
        old = Path(tmp) / 'Camtek_AOI_Parameter_manage_v8.0.exe'
        old.write_bytes(b'old release')
        assert updater.is_published_exe(old.name)
        assert updater.version_of_filename(old.name) == (8, 0)
        assert updater.version_of_filename(updater.exe_filename('8.1')) > (8, 0)
    print('PASS: entered version, PE metadata, future versions, legacy filename compatibility')


if __name__ == '__main__':
    main()
