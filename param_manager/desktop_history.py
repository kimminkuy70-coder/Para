"""Desktop history adapter: compare two saved collation files (이력 확인).

Fully local and read-only — lists the collation workbooks under save_dir,
compares two of them with the tested history.diff_files, and pages the changed
cells. The UI selects files by opaque id, never by path. Equipment value-update
(SMB collection) is a separate concern and is not performed here.
"""
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from . import history, locking, workdirs
from .desktop_batch import DesktopBatch, read_json

KINDS = ("", "값변경", "추가", "삭제", "행 추가", "행 삭제")
MAX_FILES = 10


class DesktopHistory:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path) if config_path else Path.home() / ".pi_param_manager.json"
        self.catalog_id = None
        self.snapshot = None
        self.entries = {}

    def _root(self):
        cfg = read_json(self.config_path)
        if not cfg.get("save_dir"):
            return None
        return Path(cfg["save_dir"]).absolute()

    def _safe(self, path):
        value = Path(path).absolute()
        if value.is_symlink() or not value.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("취합 파일 경로를 확인하세요")
        return str(value)

    def files(self):
        self.catalog_id, self.snapshot, self.entries = None, None, {}
        root = self._root()
        if root is None:
            return dict(save_dir=False, catalog=None, files=[])
        self.root = root
        paths = workdirs.list_collate_files(str(root))
        self.entries = {str(i): (self._safe(p), locking.file_stamp(p))
                        for i, p in enumerate(paths)}
        self.catalog_id = uuid4().hex
        return dict(save_dir=True, catalog=self.catalog_id,
                    files=[dict(id=i, name=Path(p).name) for i, (p, _) in self.entries.items()])

    def diff(self, params):
        """Compare collation files in order old → new.

        `old`/`new` compares two files; `files` (2~10 ids, oldest first) compares
        each consecutive pair like the tkinter multi-file history window.
        """
        keys = set(params)
        if not self.catalog_id or params.get("catalog") != self.catalog_id or keys not in (
                {"catalog", "old", "new"}, {"catalog", "files"}):
            raise ValueError("파일 목록을 새로고침한 뒤 두 파일을 선택하세요")
        ids = params["files"] if "files" in params else [params.get("old"), params.get("new")]
        if (not isinstance(ids, list) or not 2 <= len(ids) <= MAX_FILES
                or any(not isinstance(i, str) or i not in self.entries for i in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError(f"서로 다른 취합 파일을 2~{MAX_FILES}개 선택하세요")
        paths = []
        for i in ids:
            path, stamp = self.entries[i]
            self._safe(path)
            if locking.file_stamp(path) != stamp:
                raise ValueError("취합 파일이 변경되었습니다. 목록을 새로고침하세요.")
            paths.append(path)
        self.pairs = [(Path(a).name, Path(b).name, history.diff_files(a, b)) for a, b in zip(paths, paths[1:])]
        self.snapshot = uuid4().hex
        summary = [dict(index=i, old=o, new=n, changes=len(d.changes), added=len(d.added_rows),
                        removed=len(d.removed_rows)) for i, (o, n, d) in enumerate(self.pairs)]
        first = summary[0]
        return dict(snapshot=self.snapshot, machines=self.pairs[0][2].machines, pairs=summary,
                    changes=first["changes"], added=first["added"], removed=first["removed"],
                    old=first["old"], new=first["new"])

    def _pair(self, params, allowed):
        if set(params) - allowed or params.get("snapshot") != self.snapshot or not self.snapshot:
            raise ValueError("비교 결과를 다시 생성하세요")
        pair = params.get("pair", 0)
        if type(pair) is not int or not 0 <= pair < len(self.pairs):
            raise ValueError("비교 구간을 확인하세요")
        return self.pairs[pair]

    def page(self, params):
        _, _, diff = self._pair(params, {"snapshot", "pair", "offset", "limit", "kind", "query"})
        offset, limit = params.get("offset", 0), params.get("limit", 100)
        if type(offset) is not int or not 0 <= offset <= 10000000 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("조회 범위를 확인하세요")
        kind, query = params.get("kind", ""), params.get("query", "")
        if kind not in KINDS or not isinstance(query, str) or len(query) > 256:
            raise ValueError("검색 조건을 확인하세요")
        q = query.casefold()
        if kind in ("행 추가", "행 삭제"):
            # Whole rows that exist only in the new (added) or old (removed) file.
            source = diff.added_rows if kind == "행 추가" else diff.removed_rows
            items = [dict(sheet=r["sheet"], recipe=r["Recipe"], zone=r["Zone"], alg=r["Alg"],
                          param=r["Parameter"], machine="", old="", new="", kind=kind) for r in source]
        else:
            items = [dict(sheet=c.sheet, recipe=c.recipe, zone=c.zone, alg=c.alg, param=c.param,
                          machine=c.machine, old=c.old, new=c.new, kind=c.kind)
                     for c in diff.changes if not kind or c.kind == kind]
        rows = [r for r in items if not q or q in (
            r["param"] + " " + r["recipe"] + " " + r["zone"] + " " + r["alg"] + " " + r["machine"]).casefold()]
        return dict(total=len(rows), offset=offset, rows=rows[offset:offset + limit])

    def export(self, params):
        """변경내역 Excel (tkinter '변경내역 엑셀로 저장'). Written to the local result
        folder, not the shared save folder, so OneDrive writes do not grow."""
        old, new, diff = self._pair(params, {"snapshot", "pair"})
        _, _, root, _ = DesktopBatch(self.config_path).configuration()
        folder = Path(root) / "이력비교"
        for part in (folder, *folder.parents):
            if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
                raise ValueError("로컬 결과 폴더의 연결 경로는 사용할 수 없습니다")
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"변경내역_{workdirs.stamp()}.xlsx"
        fd, temporary = tempfile.mkstemp(prefix=".rev1-history-", suffix=".xlsx", dir=folder)
        os.close(fd)
        try:
            history.write_diff_excel(diff, temporary, old_label=old, new_label=new)
            os.replace(temporary, dest)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return dict(path=str(dest))
