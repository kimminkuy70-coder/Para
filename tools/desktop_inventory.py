"""Generate a lockfile inventory and installed license notices for build review.

Not a legal approval or a binary-derived SBOM. Missing metadata is recorded, not
invented. Run in the exact build environment and review before distribution.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tomllib


def generate(root, destination):
    root=Path(root);destination=Path(destination);components=[];notices=[];missing=[]
    lock=json.loads((root/'frontend/package-lock.json').read_text())
    for path,item in sorted(lock['packages'].items()):
        if not path:continue
        name=item.get('name') or path.split('node_modules/')[-1]
        installed=root/'frontend'/path
        license_value=item.get('license')
        package=installed/'package.json'
        if package.exists():license_value=license_value or json.loads(package.read_text()).get('license')
        components.append(dict(ecosystem='npm',name=name,version=item['version'],license=license_value,
                               integrity=item.get('integrity'),development=bool(item.get('dev')),path=path))
        if not license_value:missing.append('npm:'+name+'@'+item['version'])
        if installed.is_dir():
            for file in installed.iterdir():
                if file.is_file() and file.name.lower().startswith(('license','licence','copying','notice')):
                    notices.append((name+'@'+item['version']+'/'+file.name,file.read_text(errors='replace')))
    cargo=Path(os.environ.get('CARGO_HOME',Path.home()/'.cargo'))/'registry/src'
    for item in tomllib.loads((root/'frontend/src-tauri/Cargo.lock').read_text())['package']:
        if not item.get('source'):continue
        name=item['name'];ver=item['version'];matches=list(cargo.glob('*/'+name+'-'+ver))
        metadata={}
        if matches:metadata=tomllib.loads((matches[0]/'Cargo.toml').read_text()).get('package',{})
        license_value=metadata.get('license') or metadata.get('license-file')
        components.append(dict(ecosystem='cargo',name=name,version=ver,license=license_value,sha256=item.get('checksum')))
        if not license_value:missing.append('cargo:'+name+'@'+ver)
        if matches:
            for file in matches[0].iterdir():
                if file.is_file() and file.name.lower().startswith(('license','licence','copying','notice')):
                    notices.append((name+'@'+ver+'/'+file.name,file.read_text(errors='replace')))
    data={'schema_version':1,'scope':'npm and Cargo lockfiles; not Python, OS, WebView2 or final binary SBOM',
          'lock_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                         [root/'frontend/package-lock.json',root/'frontend/src-tauri/Cargo.lock']},
          'components':components,'missing_license_metadata':missing,'deployment_approved':False}
    destination.mkdir(parents=True,exist_ok=True)
    (destination/'dependency-inventory.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    (destination/'THIRD_PARTY_NOTICES.txt').write_text('\n\n'.join('=== '+label+' ===\n'+body for label,body in notices),encoding='utf-8')
    print(f'{len(components)} components; {len(missing)} missing license metadata; build review required')
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    args=parser.parse_args();generate(Path(__file__).resolve().parents[1],args.destination)
