"""v13 program update: GitHub release tag (main) · OneDrive `프로그램/` folder (backup).

Owner decision 2026-11-10 (docs/V13_계획.md 4-1, 12): the only internet access the program
makes is here — checking for a new release and downloading its source zip from
github.com/kimminkuy70-coder/Para — and only:
  * one repository, release tags `v13.x.y` only (no branch tips, no pre-release suffixes)
  * TLS certificate checked (Windows certificate store via the ssl default context); never disabled
  * no token, no account, no personal data in the request (public repository)
  * redirects only to github.com / codeload.github.com
  * the download is applied only when a person presses [지금 업데이트]
  * a downloaded tree holding any executable or script file is refused (`deploy.forbidden`)
The OneDrive route keeps the v12 rules: copy to local Temp once, check size + SHA-256, never
write to OneDrive on the receiving PC.

Apply = copy the deploy files (`deploy.files`) of the new tree into `<home>/app.new`
(built as `app.new.part`, renamed when complete). The start file swaps it in before any
module loads; the launcher restarts on the same address so the open window reconnects.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import ssl
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path

from . import __version__, deploy, localdirs
from .desktop_batch import read_json

REPO = "kimminkuy70-coder/Para"
FEED = f"https://github.com/{REPO}/releases.atom"
TAG_ZIP = "https://github.com/" + REPO + "/archive/refs/tags/{tag}.zip"
ALLOWED_HOSTS = {"github.com", "codeload.github.com"}
TAG_RE = re.compile(r"^v(13\.\d+\.\d+)$")
USER_AGENT = "Para-Updater"                     # generic; nothing about the user or PC
CHECK_TIMEOUT, DOWNLOAD_TIMEOUT = 15, 120
MAX_ZIP = 300 * 1024 * 1024
MAX_FILES = 30000
PROGRAM_DIRNAME = "프로그램"
MANIFEST = "버전정보_v13.json"                   # v12 uses 버전정보_web.json — separate names
ZIP_PREFIX = "Camtek_AOI_manager_v"
ZIP_SUFFIX = "_source.zip"
KEEP_VERSIONS = 2


# ---------------------------------------------------------------- versions / places
def parse_version(text) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", str(text or ""))[:4]) or (0,)


def is_newer(remote, local) -> bool:
    r, l = parse_version(remote), parse_version(local)
    n = max(len(r), len(l))
    return r + (0,) * (n - len(r)) > l + (0,) * (n - len(l))


def app_home() -> Path | None:
    """Install folder (set by the start file); None when run from a source copy."""
    home = os.environ.get("PARA_APP_HOME")
    return Path(home) if home else None


def inside_install(path) -> bool:
    home = app_home()
    if home is None:
        return False
    p, h = Path(path).absolute(), home.absolute()
    return p == h or h in p.parents


def program_dir(save_dir: str) -> str:
    """OneDrive publish folder: next to the save folder (docs), not inside it. Not created."""
    base = os.path.abspath(str(save_dir or "."))
    parent = os.path.dirname(base)
    if not parent or parent == base or not os.path.isdir(parent):
        return os.path.join(base, PROGRAM_DIRNAME)
    return os.path.join(parent, PROGRAM_DIRNAME)


# ---------------------------------------------------------------- GitHub
class _Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host = urllib.parse.urlsplit(newurl).hostname or ""
        if urllib.parse.urlsplit(newurl).scheme != "https" or host not in ALLOWED_HOSTS:
            raise urllib.error.URLError(f"redirect to {host} refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener():
    ctx = ssl.create_default_context()          # verifies; on Windows loads the system store
    return urllib.request.build_opener(urllib.request.ProxyHandler(), urllib.request.HTTPSHandler(context=ctx), _Redirects())


def _get(url: str, timeout: float, limit: int, sink=None) -> bytes:
    host = urllib.parse.urlsplit(url).hostname or ""
    if not url.startswith("https://") or host not in ALLOWED_HOSTS:
        raise ValueError(f"허용하지 않은 주소: {host}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _opener().open(req, timeout=timeout) as r:
        if sink is None:
            data = r.read(limit + 1)
            if len(data) > limit:
                raise ValueError("응답이 너무 큽니다")
            return data
        total = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                return b""
            total += len(chunk)
            if total > limit:
                raise ValueError("파일이 너무 큽니다")
            sink.write(chunk)


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_endtag(self, tag):
        if tag in ("p", "li", "h1", "h2", "h3", "br", "ul"):
            self.parts.append("\n")


def html_text(fragment: str, limit: int = 4000) -> str:
    t = _Text()
    t.feed(fragment or "")
    text = re.sub(r"\n{3,}", "\n\n", "".join(t.parts)).strip()
    return text[:limit]


def parse_feed(xml_bytes: bytes) -> list[dict]:
    """Release entries `[{tag, version, notes, at}]`, only plain `v13.x.y` tags, newest version first."""
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_bytes)
    out = []
    for e in root.findall("a:entry", ns):
        link = e.find("a:link", ns)
        href = link.get("href", "") if link is not None else ""
        tag = urllib.parse.unquote(href.rstrip("/").rsplit("/", 1)[-1])
        m = TAG_RE.match(tag)
        if not m:
            continue
        content = e.findtext("a:content", default="", namespaces=ns)
        out.append(dict(tag=tag, version=m.group(1), notes=html_text(content),
                        at=(e.findtext("a:updated", default="", namespaces=ns) or "")[:16].replace("T", " ")))
    return sorted(out, key=lambda r: parse_version(r["version"]), reverse=True)


def latest_github(fetch=None) -> dict | None:
    data = (fetch or (lambda: _get(FEED, CHECK_TIMEOUT, 2 * 1024 * 1024)))()
    entries = parse_feed(data)
    return dict(entries[0], source="github") if entries else None


# ---------------------------------------------------------------- OneDrive
def manifest_path(save_dir: str) -> str:
    return os.path.join(program_dir(save_dir), MANIFEST)


def latest_onedrive(save_dir: str) -> dict | None:
    if not save_dir:
        return None
    data = read_json(Path(manifest_path(save_dir)))
    if not isinstance(data, dict):
        return None
    m = re.fullmatch(r"13\.\d+\.\d+", str(data.get("version", "")))
    name = str(data.get("file", ""))
    if not m or not re.fullmatch(re.escape(ZIP_PREFIX) + r"13\.\d+\.\d+" + re.escape(ZIP_SUFFIX), name):
        return None
    return dict(tag="v" + data["version"], version=data["version"], notes=str(data.get("notes", ""))[:4000],
                at=str(data.get("published_at", "")), source="onedrive", file=name,
                size=int(data.get("size", 0) or 0), sha256=str(data.get("sha256", "")))


# ---------------------------------------------------------------- unpack + check a source zip
def _safe_extract(zip_path: Path, dest: Path) -> None:
    with zipfile.ZipFile(zip_path) as z:
        infos = z.infolist()
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > 4 * MAX_ZIP:
            raise ValueError("압축 파일이 너무 큽니다")
        base = dest.resolve()
        for i in infos:
            target = (dest / i.filename).resolve()
            if i.filename.startswith(("/", "\\")) or ".." in Path(i.filename).parts or base not in (target, *target.parents):
                raise ValueError("압축 파일 안 경로가 올바르지 않습니다")
        z.extractall(dest)


def tree_root(extracted: Path) -> Path:
    for cand in (extracted, *sorted(p for p in extracted.iterdir() if p.is_dir())):
        if (cand / "param_manager" / "launcher.py").is_file():
            return cand
    raise ValueError("Para 프로그램 파일이 아닙니다(param_manager/launcher.py 없음)")


def tree_version(root: Path) -> str:
    text = (root / "param_manager" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        raise ValueError("버전 정보를 찾지 못했습니다")
    return m.group(1)


def check_tree(root: Path, version: str) -> list[str]:
    files = deploy.files(root)
    bad = deploy.forbidden(files)
    if bad:
        raise ValueError("실행 파일이나 스크립트가 들어 있어 적용하지 않습니다: " + ", ".join(bad[:5]))
    for need in ("Camtek_AOI_manager.pyw", "frontend/dist/index.html", "param_manager/desktop_ipc.py"):
        if need not in files:
            raise ValueError(f"필요한 파일이 없습니다: {need}")
    if tree_version(root) != version:
        raise ValueError(f"태그({version})와 프로그램 버전({tree_version(root)})이 다릅니다")
    return files


def stage(root: Path, files: list[str], home: Path) -> Path:
    """Copy the deploy files to <home>/app.new (via .part, renamed when complete)."""
    part, ready = home / "app.new.part", home / "app.new"
    for p in (part, ready):
        shutil.rmtree(p, ignore_errors=True)
    for rel in files:
        dst = part / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, dst)
    os.replace(part, ready)
    return ready


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- engine adapter
class DesktopAppUpdate:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path) if config_path else Path.home() / ".pi_param_manager.json"
        self.fetch_feed = None          # tests inject (no network)
        self.download = None            # tests inject: (tag, Path) -> None
        self.last = None

    def _cfg(self):
        return read_json(self.config_path)

    def _local_root(self):
        return str(self._cfg().get("local_dir") or localdirs.default_root())

    def check(self, params=None):
        """Newest release from GitHub; if GitHub cannot be reached, the OneDrive folder."""
        save_dir = str(self._cfg().get("save_dir") or "")
        found, error = None, ""
        try:
            found = latest_github(self.fetch_feed)
        except Exception as exc:  # noqa: BLE001 - offline / blocked: fall back quietly
            error = f"GitHub 확인 실패: {type(exc).__name__}"
        if found is None:
            try:
                found = latest_onedrive(save_dir)
            except Exception:  # noqa: BLE001
                found = None
        self.last = found
        newer = bool(found and is_newer(found["version"], __version__))
        return dict(current=__version__, installed=app_home() is not None, available=(found or {}).get("version", ""),
                    newer=newer, changelog=(found or {}).get("notes", ""), published_at=(found or {}).get("at", ""),
                    source=(found or {}).get("source", ""), error=error,
                    program_dir=program_dir(save_dir) if save_dir else "")

    def _fetch_zip(self, info: dict, work: Path) -> Path:
        dest = work / "source.zip"
        if info["source"] == "github":
            if self.download:
                self.download(info["tag"], dest)
            else:
                with open(dest, "wb") as fh:
                    _get(TAG_ZIP.format(tag=urllib.parse.quote(info["tag"])), DOWNLOAD_TIMEOUT, MAX_ZIP, sink=fh)
            return dest
        src = Path(program_dir(str(self._cfg().get("save_dir") or ""))) / info["file"]
        if not src.is_file() or src.stat().st_size != info["size"]:
            raise ValueError("OneDrive 의 파일이 아직 다 내려받아지지 않았습니다. 잠시 뒤 다시 하십시오")
        shutil.copyfile(src, dest)                           # one copy to local Temp
        if sha256(dest) != info["sha256"]:
            raise ValueError("파일 확인(SHA-256)이 맞지 않습니다. 동기화가 끝난 뒤 다시 하십시오")
        return dest

    def apply(self, params=None):
        home = app_home()
        if home is None:
            raise ValueError("소스 폴더에서 실행 중이라 자동 업데이트를 하지 않습니다(git 으로 받으십시오)")
        info = self.last or (self.check() and self.last)
        if not info or not is_newer(info["version"], __version__):
            raise ValueError("새 버전이 없습니다")
        work = Path(localdirs.new_temp_run(self._local_root(), "업데이트"))
        try:
            zip_path = self._fetch_zip(info, work)
            _safe_extract(zip_path, work / "x")
            root = tree_root(work / "x")
            stage(root, check_tree(root, info["version"]), home)
        finally:
            localdirs.drop(str(work))
        return dict(version=info["version"], source=info["source"], restart=True)

    def publish(self, params):
        """Developer: put a source zip (GitHub 'Source code (zip)' of a v13 tag) in OneDrive 프로그램/."""
        save_dir = str(self._cfg().get("save_dir") or "")
        if not save_dir:
            raise ValueError("저장 폴더를 먼저 정하십시오")
        src = Path(str(params.get("path", "")))
        if src.suffix.lower() != ".zip" or not src.is_file():
            raise ValueError("v13 소스 zip 파일을 고르십시오")
        work = Path(localdirs.new_temp_run(self._local_root(), "게시"))
        try:
            local = work / "in.zip"
            shutil.copyfile(src, local)
            _safe_extract(local, work / "x")
            root = tree_root(work / "x")
            version = tree_version(root)
            if not re.fullmatch(r"13\.\d+\.\d+", version):
                raise ValueError(f"v13 프로그램이 아닙니다(버전 {version})")
            check_tree(root, version)
            name = f"{ZIP_PREFIX}{version}{ZIP_SUFFIX}"
            folder = Path(program_dir(save_dir))
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(local, folder / name)            # one copy into OneDrive
            manifest = dict(version=version, file=name, size=local.stat().st_size, sha256=sha256(local),
                            notes=str(params.get("notes", ""))[:4000], published_at=time.strftime("%Y-%m-%d %H:%M"))
            # one direct write (no temp file inside the shared folder — OneDrive rule)
            (folder / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
            prune(folder, name)
            return dict(manifest, program_dir=str(folder))
        finally:
            localdirs.drop(str(work))

    def open_dir(self, params=None):
        save_dir = str(self._cfg().get("save_dir") or "")
        folder = program_dir(save_dir)
        if os.name == "nt" and os.path.isdir(folder):
            os.startfile(folder)  # noqa: S606 - our publish folder only
        return dict(program_dir=folder)


def prune(folder: Path, keep: str) -> list[str]:
    """Keep the newest KEEP_VERSIONS of our zips (by version); never touch other files."""
    pat = re.compile(re.escape(ZIP_PREFIX) + r"(13\.\d+\.\d+)" + re.escape(ZIP_SUFFIX))
    ours = sorted((p for p in folder.iterdir() if pat.fullmatch(p.name)),
                  key=lambda p: parse_version(pat.fullmatch(p.name).group(1)), reverse=True)
    removed = []
    for p in ours[KEEP_VERSIONS:]:
        if p.name != keep:
            p.unlink(missing_ok=True)
            removed.append(p.name)
    return removed

