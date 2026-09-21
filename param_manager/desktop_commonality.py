"""Read existing local Commonality results through opaque IDs, never UI paths."""
import os
from fnmatch import fnmatchcase
from pathlib import Path
import tempfile
from uuid import uuid4

from . import commonality as cm, engine, locking, workdirs
from .desktop_batch import DesktopBatch


class DesktopCommonality:
    def __init__(self, config_path=None):
        self.batch = DesktopBatch(config_path)
        self.catalog_id = self.snapshot = None
        self.files = {}

    def safe(self, path):
        path = Path(path).absolute()
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError('Commonality 로컬 폴더 밖의 경로입니다')
        for part in (path, *path.parents):
            if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
                raise ValueError('Commonality 연결 경로를 사용할 수 없습니다')
        return path

    def catalog(self):
        _, _, self.root, _ = self.batch.configuration()
        self.safe(self.root)
        candidates = set()
        # Manual legacy layout and automatic-watch layout; no equipment traversal.
        patterns = (f'Commonality/{workdirs.COMMONALITY_DIR}/*/*/조사_*.xlsx',
                    f'{workdirs.COMMONALITY_DIR}/*/*/조사_*.xlsx',
                    f'{workdirs.COMMONALITY_DIR}/자동감시/*/결과/감시조사_*.xlsx')
        for pattern in patterns:
            paths = [self.root]
            for segment in pattern.split('/'):
                following = []
                for parent in paths:
                    self.safe(parent)
                    if not parent.is_dir():
                        continue
                    for child in parent.iterdir():
                        if fnmatchcase(child.name, segment):
                            self.safe(child)
                            following.append(child)
                            if len(following) > 5000:
                                raise ValueError('결과 경로가 너무 많습니다. 기존 결과를 정리하세요.')
                paths = following
            for path in paths:
                self.safe(path)
                if path.is_file():
                    candidates.add(path)
                if len(candidates) > 5000:
                    raise ValueError('결과 파일이 5000개를 초과합니다. 기존 결과를 정리하세요.')
        self.files = {str(i): (p, locking.file_stamp(str(p)))
                      for i, p in enumerate(sorted(candidates, reverse=True))}
        self.catalog_id = uuid4().hex
        return dict(catalog=self.catalog_id, files=[
            dict(id=i, name=p.name, folder=str(p.parent.relative_to(self.root)))
            for i, (p, _) in self.files.items()])

    def compare(self, params):
        ids = params.get('files')
        if (set(params) != {'catalog', 'files'} or not self.catalog_id
                or params['catalog'] != self.catalog_id
                or not isinstance(ids, list) or not 1 <= len(ids) <= 100):
            raise ValueError('목록을 새로고침한 뒤 결과 파일을 1~100개 선택하세요')
        if any(not isinstance(i, str) or i not in self.files for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('등록된 결과 파일만 선택하세요')
        paths = []
        for i in ids:
            path, stamp = self.files[i]
            self.safe(path)
            if locking.file_stamp(str(path)) != stamp:
                raise ValueError('결과 파일이 변경되었습니다. 목록을 새로고침하세요.')
            paths.append(str(path))
        result = cm.build_comparison(paths)
        for i in ids:
            path, stamp = self.files[i]
            self.safe(path)
            if locking.file_stamp(str(path)) != stamp:
                raise ValueError('비교 중 결과 파일이 변경되었습니다. 다시 조사하세요.')
        self.result, self.snapshot = result, uuid4().hex
        return dict(snapshot=self.snapshot, total=len(result['rows']),
                    parameters=len(result['columns']) - 3, changed=len(result['changed_params']))

    def page(self, params):
        if (set(params) - {'snapshot', 'offset', 'limit', 'column', 'query', 'changed_only'}
                or not self.snapshot or params.get('snapshot') != self.snapshot):
            raise ValueError('비교 결과를 다시 생성하세요')
        offset, limit, column = params.get('offset', 0), params.get('limit', 100), params.get('column', 0)
        if (any(type(x) is not int or not 0 <= x <= 10000000 for x in (offset, column))
                or type(limit) is not int or not 1 <= limit <= 100):
            raise ValueError('조회 범위를 확인하세요')
        query, changed = params.get('query', ''), params.get('changed_only', False)
        if not isinstance(query, str) or len(query) > 256 or type(changed) is not bool:
            raise ValueError('검색 조건을 확인하세요')
        data = self.result
        columns = data['changed_params'] if changed else data['columns'][3:]
        columns = [c for c in columns if query.casefold() in c.casefold()]
        heads = data['columns'][:3] + columns[column:column + 12]
        return dict(headers=heads, total=len(data['rows']), parameter_total=len(columns), rows=[
            dict(id=i, values=[engine._s(row.get(c)) for c in heads],
                 outliers=[j for j, c in enumerate(heads) if (i, c) in data['outliers']],
                 fail=i in data['fail_rows'], low_match=i in data['low_rows'])
            for i, row in enumerate(data['rows'][offset:offset + limit], offset)])

    def export(self, params):
        if (set(params) != {'snapshot', 'changed_only'} or not self.snapshot
                or params['snapshot'] != self.snapshot or type(params['changed_only']) is not bool):
            raise ValueError('비교 결과를 다시 생성하세요')
        folder = self.safe(self.root / 'Commonality' / workdirs.COMMONALITY_COMPARE_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f'취합비교_rev1_{uuid4().hex}.xlsx'
        fd, temporary = tempfile.mkstemp(prefix='.rev1-', suffix='.xlsx', dir=folder)
        os.close(fd)
        try:
            cm.write_comparison(temporary, self.result, changed_only=params['changed_only'])
            self.safe(folder)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return dict(path=str(path))
