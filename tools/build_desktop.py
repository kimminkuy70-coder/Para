"""Windows development build; offline dependency caches must be prepared first.

Uses a fresh staging tree, never changes the working source version or publishes
an operational update. Output is a complete portable folder, never an exe alone.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from desktop_bundle import create, verify, version
from desktop_inventory import generate

ROOT = Path(__file__).resolve().parents[1]


def run(args, cwd):
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)


def build(app_version):
    app_version = version(app_version)
    if sys.platform != 'win32':
        raise SystemExit('Build on Windows with approved Python, Node, Rust MSVC and WebView2 SDK.')
    if os.environ.get('CONDA_PREFIX') or 'conda' in sys.version.lower():
        raise SystemExit('Use the approved python.org interpreter; conda builds are not supported.')
    npm = shutil.which('npm.cmd')
    if not npm or not shutil.which('cargo'):
        raise SystemExit('Install the approved Node and Rust MSVC build prerequisites first.')
    output = ROOT/'dist'/f'Camtek_AOI_manager_v{app_version}'
    if output.exists():
        raise SystemExit('Output already exists; choose a new version or archive the old build yourself.')
    (ROOT/'build').mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='desktop-', dir=ROOT/'build'))
    print('Staging:', stage)
    ignore = shutil.ignore_patterns('__pycache__','*.pyc','node_modules','target','gen','dist','sidecar')
    shutil.copytree(ROOT/'param_manager',stage/'param_manager',ignore=ignore)
    shutil.copytree(ROOT/'frontend',stage/'frontend',ignore=ignore)
    shutil.copytree(ROOT/'tools',stage/'tools',ignore=ignore)
    # Stamps only the isolated source copy, including the sidecar PE version.
    run([sys.executable,stage/'tools/set_version.py',app_version],stage)
    native = stage/'frontend/src-tauri'
    cfg = json.loads((native/'tauri.conf.json').read_text(encoding='utf-8'))
    cfg['version']=app_version
    (native/'tauri.conf.json').write_text(json.dumps(cfg,indent=2),encoding='utf-8')
    cargo=native/'Cargo.toml'
    cargo.write_text(re.sub(r'^version = "[^"]+"',f'version = "{app_version}"',cargo.read_text(),count=1,flags=re.M))
    lock=native/'Cargo.lock'
    lock.write_text(re.sub(r'(name = "camtek-aoi-manager"\nversion = ")[^"]+',r'\g<1>'+app_version,lock.read_text(),count=1))
    run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--console',
         '--name','Camtek_AOI_engine','--paths',stage,'--version-file',stage/'tools/version_info.txt',
         '--add-data',str(stage/'param_manager/data')+';param_manager/data',
         stage/'tools/desktop_engine_entry.py'],stage)
    shutil.copytree(stage/'dist/Camtek_AOI_engine',native/'sidecar')
    # Cached development dependencies only; no implicit runtime or build downloads.
    run([npm,'ci','--offline','--ignore-scripts'],stage/'frontend')
    run([npm,'run','tauri','--','build','--no-bundle','--ci','--','--locked','--offline'],stage/'frontend')
    exe=native/'target/release/camtek-aoi-manager.exe'
    if not exe.is_file():raise SystemExit('Native executable missing; no package produced.')
    package=stage/'package';package.mkdir()
    shutil.copy2(exe,package/'Camtek_AOI_manager.exe')
    shutil.copytree(native/'sidecar',package/'sidecar')
    shutil.copy2(ROOT/'docs/REV1_PACKAGING.md',package/'READ_BEFORE_USE.md')
    shutil.copy2(ROOT/'docs/WEB_UI_초기설정.md',package/'초기설정.md')
    shutil.copy2(ROOT/'docs/WEB_UI_기존자료_연동.md',package/'기존자료_연동.md')
    generate(stage, package/'licenses')
    (package/'licenses/python-build-environment.txt').write_text(
        subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True),encoding='utf-8')
    create(package,app_version);verify(package)
    output.parent.mkdir(exist_ok=True)
    shutil.copytree(package,output)
    verify(output)
    print('Development package:',output)
    print('NOT deployed. Keep the complete folder. Windows acceptance gates remain mandatory.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version',help='MAJOR.MINOR.PATCH, for example 8.1.0')
    args=parser.parse_args();build(args.version)
