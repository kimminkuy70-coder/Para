"""Desktop history adapter: compare two saved collation files (이력 확인).

Fully local and read-only — lists the collation workbooks under save_dir,
compares two of them with the tested history.diff_files, and pages the changed
cells. The UI selects files by opaque id, never by path. Equipment value-update
(SMB collection) is a separate concern and is not performed here.
"""
from pathlib import Path
from uuid import uuid4

from . import history, locking, workdirs
from .desktop_batch import read_json


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
        if set(params) != {"catalog", "old", "new"} or params.get("catalog") != self.catalog_id or not self.catalog_id:
            raise ValueError("파일 목록을 새로고침한 뒤 두 파일을 선택하세요")
        old_id, new_id = params.get("old"), params.get("new")
        if old_id not in self.entries or new_id not in self.entries or old_id == new_id:
            raise ValueError("서로 다른 취합 파일 2개를 선택하세요")
        paths = []
        for i in (old_id, new_id):
            path, stamp = self.entries[i]
            self._safe(path)
            if locking.file_stamp(path) != stamp:
                raise ValueError("취합 파일이 변경되었습니다. 목록을 새로고침하세요.")
            paths.append(path)
        d = history.diff_files(paths[0], paths[1])
        self.result = d
        self.snapshot = uuid4().hex
        return dict(snapshot=self.snapshot, machines=d.machines,
                    changes=len(d.changes), added=len(d.added_rows), removed=len(d.removed_rows),
                    old=Path(paths[0]).name, new=Path(paths[1]).name)

    def page(self, params):
        if set(params) - {"snapshot", "offset", "limit", "kind", "query"} or params.get("snapshot") != self.snapshot or not self.snapshot:
            raise ValueError("비교 결과를 다시 생성하세요")
        offset, limit = params.get("offset", 0), params.get("limit", 100)
        if type(offset) is not int or not 0 <= offset <= 10000000 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("조회 범위를 확인하세요")
        kind, query = params.get("kind", ""), params.get("query", "")
        if kind not in ("", "값변경", "추가", "삭제") or not isinstance(query, str) or len(query) > 256:
            raise ValueError("검색 조건을 확인하세요")
        q = query.casefold()
        rows = [c for c in self.result.changes
                if (not kind or c.kind == kind)
                and (not q or q in (c.param + " " + c.recipe + " " + c.zone + " " + c.alg + " " + c.machine).casefold())]
        return dict(total=len(rows), offset=offset, rows=[
            dict(sheet=c.sheet, recipe=c.recipe, zone=c.zone, alg=c.alg, param=c.param,
                 machine=c.machine, old=c.old, new=c.new, kind=c.kind)
            for c in rows[offset:offset + limit]])
