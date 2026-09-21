"""Snapshot comparison and explicit metadata edits. No equipment value writes."""
import os
from pathlib import Path
import tempfile
from uuid import uuid4

import openpyxl
from . import collate, engine, locking, namestore, workdirs
from .desktop_batch import read_json


class DesktopRecipe:
    def __init__(self, config_path=None):
        self.config_path = config_path or Path.home()/'.pi_param_manager.json'
        self.version = None
        self.rows = []

    def safe_path(self, path):
        value = Path(path).absolute()
        if value.is_symlink() or not value.resolve().is_relative_to(self.root.resolve()):
            raise ValueError('공유 문서 경로를 확인하세요')
        return str(value)

    def open(self):
        self.version, self.rows = None, []
        cfg = read_json(self.config_path)
        if not cfg.get('save_dir'):
            return dict(version=None, recipes=[], machines=[], source='')
        self.root = Path(cfg['save_dir']).absolute()
        path = workdirs.latest_collate(str(self.root))
        if not path:
            return dict(version=None, recipes=[], machines=[], source='')
        self.path = self.safe_path(path)
        before = locking.file_stamp(self.path)
        sheets, self.machines = collate.load_collation(self.path)
        if before != locking.file_stamp(self.path):
            raise ValueError('조회 중 취합 파일이 변경되었습니다. 다시 열어 주세요.')
        self.stamp = before
        self.name_path = self.safe_path(namestore.name_path(str(self.root)))
        self.name_stamp = locking.file_stamp(self.name_path) or (0, 0)
        self.names = namestore.load(self.name_path)
        if self.name_stamp != (locking.file_stamp(self.name_path) or (0, 0)):
            raise ValueError('조회 중 색상 파일이 변경되었습니다. 다시 열어 주세요.')
        self.rows = [(sheet, row) for sheet, rows in sheets.items() for row in rows]
        self.version = uuid4().hex
        return dict(version=self.version, recipes=list(sheets), machines=self.machines, source=Path(path).name)

    def check(self, params, allowed):
        if set(params)-allowed or not self.version or params.get('snapshot') != self.version:
            raise ValueError('비교 화면을 새로고침하세요')

    def page(self, params):
        self.check(params, {'snapshot','recipe','query','offset','limit','machine_offset','machine_limit','selected_machine'})
        recipe, query = params.get('recipe',''), params.get('query','')
        if not isinstance(recipe,str) or not isinstance(query,str) or len(query)>256:
            raise ValueError('검색 조건을 확인하세요')
        offset, limit = params.get('offset',0), params.get('limit',100)
        start, count = params.get('machine_offset',0), params.get('machine_limit',12)
        for v, low, high in ((offset,0,10000000),(limit,1,100),(start,0,100000),(count,1,12)):
            if type(v) is not int or not low<=v<=high:
                raise ValueError('표 조회 범위를 확인하세요')
        matches = [(i,s,r) for i,(s,r) in enumerate(self.rows) if (not recipe or s==recipe)
                   and (not query or query.casefold() in ' '.join(engine._s(r.get(k)) for k in engine.META_FIELDS).casefold())]
        selected = params.get('selected_machine', self.machines[0] if self.machines else '')
        if selected not in self.machines:
            raise ValueError('기준 호기를 선택하세요')
        color = namestore.make_color_lookup(self.names)
        rows=[]
        # Selected value is separate from the requested 12 comparison columns.
        machines=self.machines[start:start+count]
        for i,s,r in matches[offset:offset+limit]:
            alg, name = engine._s(r.get('Alg')), engine._s(r.get('Parameter'))
            rows.append(dict(id=i,recipe=s,variant=engine._s(r.get('Recipe')),zone=engine._s(r.get('Zone')),
                alg=alg,name=name,note=engine._s(r.get('비고')),
                color=color(alg,name) or namestore.default_color(alg,name),value=engine._s(r.get(selected)),
                values={m:engine._s(r.get(m)) for m in machines}))
        return dict(rows=rows,total=len(matches),machines=machines,offset=offset,machine_total=len(self.machines))

    def edit(self, params):
        self.check(params, {'snapshot','row','kind','value'})
        index, kind, value = params.get('row'),params.get('kind'),params.get('value')
        if type(index) is not int or not 0<=index<len(self.rows) or kind not in ('color','note') or not isinstance(value,str) or len(value)>4000:
            raise ValueError('색상 또는 비고만 수정할 수 있습니다')
        self.safe_path(self.path)
        if workdirs.latest_collate(str(self.root)) != self.path or locking.file_stamp(self.path) != self.stamp:
            raise ValueError('새 취합본 또는 다른 사용자의 변경이 있습니다. 새로고침하세요.')
        sheet, row = self.rows[index]
        user=engine.current_user()
        if kind=='color':
            self.safe_path(self.name_path)
            color=namestore.normalize_color(value)
            alg,name=engine._s(row.get('Alg')),engine._s(row.get('Parameter'))
            original=namestore.resolve_original(self.names,alg,name)
            namestore.save_selected(self.name_path,[{'alg':alg,'ext':{'key':original},'name':name,'color':color}],user,self.name_stamp)
        else:
            previous=locking.status(self.path,user)
            acquired=locking.acquire(self.path,user)
            if not acquired.editable:
                raise ValueError(locking.holder_message(acquired,'비고'))
            wb=None; temporary=None
            try:
                check=locking.check_before_save(self.path,user,self.stamp)
                if not check['ok']: raise ValueError(check['reason'])
                wb=openpyxl.load_workbook(self.path)
                ws=wb[sheet]
                heads=[engine._s(c.value).strip() for c in ws[1]]
                key=('PI','Recipe','Zone','Alg','Parameter')
                idx={h:heads.index(h) for h in (*key,'비고')}
                wanted=tuple(engine._s(row.get(k)) for k in key)
                cells=[cells for cells in ws.iter_rows(min_row=2) if tuple(engine._s(cells[idx[k]].value) for k in key)==wanted]
                if len(cells)!=1: raise ValueError('동일 항목이 여러 개입니다. 기존 프로그램에서 비고를 확인하세요.')
                cell=cells[0][idx['비고']];cell.value=value;cell.data_type='s'
                fd,temporary=tempfile.mkstemp(prefix='.rev1-note-',suffix='.xlsx',dir=Path(self.path).parent)
                os.close(fd);wb.save(temporary)
                check=locking.check_before_save(self.path,user,self.stamp)
                if not check['ok'] or locking.file_stamp(self.path)!=self.stamp:
                    raise ValueError(check['reason'] or '저장 직전 문서가 변경되었습니다.')
                os.replace(temporary,self.path);temporary=None
            finally:
                if wb: wb.close()
                if temporary and os.path.exists(temporary): os.unlink(temporary)
                if previous.status!='mine':locking.release(self.path,user)
        return self.open()
