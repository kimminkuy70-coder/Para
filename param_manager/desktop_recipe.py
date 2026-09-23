"""Snapshot comparison and explicit metadata edits. No equipment value writes."""
import os
from pathlib import Path
import tempfile
from uuid import uuid4

import json
import os as _os
import openpyxl
from . import (collate, shared_io, engine, exporter, localdirs, locking, namestore,
               refdata, rtp_parser as rtp, watcher, workdirs)
from .desktop_batch import DesktopBatch, read_json

VIEW_COLORS = '값확인_셀색상.json'   # same per-cell color store as the tkinter view
KEY_FIELDS = ('PI', 'Recipe', 'Zone', 'Alg', 'Parameter')
MAX_EXPORT_ROWS = 200000


def row_key(row):
    return tuple(engine._s(row.get(f)).strip() for f in KEY_FIELDS)


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
        if getattr(self, 'held', None) and self.held != self.path:
            self.close()            # a newer collation: release the old file's lock
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
        self.colors = self._load_colors()
        self.types = self._machine_types()
        self.version = uuid4().hex
        zones = {sheet: sorted({engine._s(r.get('Zone')).strip() for r in rows} - {''}) for sheet, rows in sheets.items()}
        self.last_catalog = dict(version=self.version, recipes=list(sheets), machines=self.machines, source=Path(path).name,
                                 path=self.path, zones=zones, machine_types=self.types, hide_kla=bool(cfg.get('hide_kla', True)))
        return self.last_catalog

    def _machine_types(self):
        try:
            path = self.safe_path(refdata.ip_path(str(self.root)))
            rows = refdata.load_ip(path) if Path(path).is_file() else []
        except (OSError, ValueError, KeyError):
            rows = []
        return {m: refdata.device_type_for(rows, m) for m in self.machines}

    def _colors_path(self):
        return self.safe_path(self.root / VIEW_COLORS)

    def _load_colors(self):
        try:
            path = self._colors_path()
            if Path(path).is_file() and Path(path).stat().st_size <= 8 * 1024 * 1024:
                with open(path, encoding='utf-8') as fh:
                    data = json.load(fh)
                return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(data, dict) else {}
        except (OSError, ValueError):
            pass
        return {}

    def check(self, params, allowed):
        if set(params)-allowed or not self.version or params.get('snapshot') != self.version:
            raise ValueError('비교 화면을 새로고침하세요')

    def page(self, params):
        self.check(params, {'snapshot','recipe','query','offset','limit','machine_offset','machine_limit','selected_machine','zone','hide_kla'})
        recipe, query, zone = params.get('recipe',''), params.get('query',''), params.get('zone','')
        hide_kla = params.get('hide_kla', False)
        if not isinstance(recipe,str) or not isinstance(query,str) or len(query)>256 or not isinstance(zone,str) or type(hide_kla) is not bool:
            raise ValueError('검색 조건을 확인하세요')
        offset, limit = params.get('offset',0), params.get('limit',100)
        start, count = params.get('machine_offset',0), params.get('machine_limit',12)
        for v, low, high in ((offset,0,10000000),(limit,1,100),(start,0,100000),(count,1,12)):
            if type(v) is not int or not low<=v<=high:
                raise ValueError('표 조회 범위를 확인하세요')
        matches = [(i,s,r) for i,(s,r) in enumerate(self.rows) if (not recipe or s==recipe)
                   and (not zone or engine._s(r.get('Zone')).strip()==zone)
                   and (not query or query.casefold() in ' '.join(engine._s(r.get(k)) for k in engine.META_FIELDS).casefold())]
        selected = params.get('selected_machine', self.machines[0] if self.machines else '')
        if selected not in self.machines:
            raise ValueError('기준 호기를 선택하세요')
        color = namestore.make_color_lookup(self.names)
        rows=[]
        # Selected value is separate from the requested 12 comparison columns.
        # KLA machines can be hidden from the comparison columns (tkinter hide_kla).
        visible=[m for m in self.machines if not (hide_kla and self.types.get(m,'').upper()=='KLA')]
        machines=visible[start:start+count]
        for i,s,r in matches[offset:offset+limit]:
            alg, name = engine._s(r.get('Alg')), engine._s(r.get('Parameter'))
            rows.append(dict(id=i,recipe=s,variant=engine._s(r.get('Recipe')),zone=engine._s(r.get('Zone')),
                alg=alg,name=name,note=engine._s(r.get('비고')),
                color=color(alg,name) or namestore.default_color(alg,name),value=engine._s(r.get(selected)),
                values={m:engine._s(r.get(m)) for m in machines},
                cells=self._cell_colors(r,[selected,*machines])))
        return dict(rows=rows,total=len(matches),machines=machines,offset=offset,machine_total=len(visible))

    def _cell_colors(self, row, machines):
        base='\x1f'.join(row_key(row))
        out={}
        for target in ('param','비고','zone',*machines):
            color=self.colors.get(base+'\x1f'+target)
            if color:
                out[target]=color
        return out

    def edit(self, params):
        self.check(params, {'snapshot','row','kind','value','target'})
        index, kind, value = params.get('row'),params.get('kind'),params.get('value')
        if type(index) is not int or not 0<=index<len(self.rows) or kind not in ('color','note','cell') or not isinstance(value,str) or len(value)>4000:
            raise ValueError('색상 또는 비고만 수정할 수 있습니다')
        if kind=='cell':
            return self._paint(index,params.get('target'),value)
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
            # Only the names file changed: reload it, not the collation/IP/colors (fewer OneDrive reads).
            self.name_stamp=locking.file_stamp(self.name_path) or (0,0)
            self.names=namestore.load(self.name_path)
        else:
            self._hold(user)
            wb=None
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
                check=locking.check_before_save(self.path,user,self.stamp)
                if not check['ok'] or locking.file_stamp(self.path)!=self.stamp:
                    raise ValueError(check['reason'] or '저장 직전 문서가 변경되었습니다.')
                # One write onto the collation; no temp workbook in the shared folder.
                from .desktop_batch import DesktopBatch
                shared_io.save_workbook(wb,self.path,str(DesktopBatch(self.config_path).configuration()[2]))
            finally:
                if wb: wb.close()
            row['비고']=value                  # memory, instead of reading the file back
            self.stamp=locking.file_stamp(self.path)
        return self._catalog()

    def _catalog(self):
        self.version=uuid4().hex
        return dict(self.last_catalog,version=self.version)

    def _hold(self, user):
        """Keep the collation's edit lock while Recipe 관리 is open instead of
        creating/deleting it around every note (each is an OneDrive event)."""
        if getattr(self,'held',None) not in (None,self.path):
            self.close()
        state=locking.acquire(self.path,user)
        if not state.editable:
            raise ValueError(locking.holder_message(state,'비고'))
        self.held=self.path

    def close(self):
        held=getattr(self,'held',None)
        if held:
            try:locking.release(held,engine.current_user())
            except OSError:pass
        self.held=None
        return dict(closed=True)

    def paint(self, params):
        """Apply a batch of cell colors with ONE write of 값확인_셀색상.json (the UI
        collects clicks and sends them together)."""
        self.check(params,{'snapshot','cells'})
        cells=params.get('cells')
        if not isinstance(cells,list) or not 1<=len(cells)<=500:
            raise ValueError('색칠할 칸을 확인하세요')
        colors=self._load_colors()   # re-read once: another user may have painted meanwhile
        for item in cells:
            if not isinstance(item,dict) or set(item)!={'row','target','color'}:
                raise ValueError('색칠할 칸을 확인하세요')
            index,target,value=item['row'],item['target'],item['color']
            if (type(index) is not int or not 0<=index<len(self.rows) or not isinstance(target,str)
                    or target not in ('param','비고','zone',*self.machines) or not isinstance(value,str)):
                raise ValueError('색칠할 칸을 선택하세요')
            color=namestore.normalize_color(value) if value else ''
            key='\x1f'.join(row_key(self.rows[index][1])+(target,))
            if color:colors[key]=color
            else:colors.pop(key,None)
        shared_io.write_json(self._colors_path(),colors)
        self.colors=colors
        return dict(version=self.version,painted=len(cells))

    def _paint(self, index, target, value):
        return self.paint(dict(snapshot=self.version,cells=[dict(row=index,target=target,color=value)]))

    # ---- export (tkinter 내보내기) ----------------------------------------
    def export(self, params):
        """Chosen recipes × machines (optionally the current Zone/search filter) to a
        readable Excel in the local result folder. Source files are never modified."""
        self.check(params, {'snapshot','recipes','machines','query','zone'})
        recipes, machines = params.get('recipes'), params.get('machines')
        query, zone = params.get('query',''), params.get('zone','')
        if (not isinstance(recipes,list) or not recipes or not isinstance(machines,list) or not machines
                or any(not isinstance(x,str) for x in recipes+machines)
                or not isinstance(query,str) or len(query)>256 or not isinstance(zone,str)):
            raise ValueError('내보낼 레시피와 호기를 하나 이상 고르세요')
        known={s for s,_ in self.rows}
        if set(recipes)-known or set(machines)-set(self.machines):
            raise ValueError('목록에 있는 레시피와 호기만 고를 수 있습니다')
        order=[m for m in self.machines if m in machines]
        records={}
        for sheet,row in self.rows:
            if sheet not in recipes or (zone and engine._s(row.get('Zone')).strip()!=zone):
                continue
            if query and query.casefold() not in ' '.join(engine._s(row.get(k)) for k in engine.META_FIELDS).casefold():
                continue
            rec={f:row.get(f) for f in engine.META_FIELDS}
            rec.update({m:row.get(m) for m in order})
            records.setdefault(sheet,[]).append(rec)
        count=sum(len(v) for v in records.values())
        if not count:
            raise ValueError('조건에 맞는 항목이 없습니다')
        if count>MAX_EXPORT_ROWS:
            raise ValueError('내보낼 항목이 너무 많습니다. 조건을 좁히세요.')
        folder=Path(DesktopBatch(self.config_path).configuration()[2])/'내보내기'
        for part in (folder,*folder.parents):
            if part.is_symlink() or (hasattr(part,'is_junction') and part.is_junction()):
                raise ValueError('로컬 결과 폴더의 연결 경로는 사용할 수 없습니다')
        folder.mkdir(parents=True,exist_ok=True)
        dest=folder/f'파라미터_내보내기_{workdirs.stamp()}.xlsx'
        fd,temporary=tempfile.mkstemp(prefix='.rev1-export-',suffix='.xlsx',dir=folder)
        _os.close(fd)
        try:
            exporter.write_export(temporary,records,order,title='내보내기')
            _os.replace(temporary,dest)
        finally:
            if _os.path.exists(temporary):_os.unlink(temporary)
        return dict(path=str(dest),rows=count,recipes=len(records),machines=len(order))

    # ---- recipe delete (tkinter 레시피 삭제) ------------------------------
    def _form_recipes(self):
        cfg=read_json(self.config_path)
        if not cfg.get('save_dir'):
            raise ValueError('먼저 저장폴더를 지정하세요')
        self.root=Path(cfg['save_dir']).absolute()
        return workdirs.list_recipes(str(self.root))

    def delete_preview(self, params):
        if set(params)!={'recipe'}:
            raise ValueError('삭제할 레시피를 선택하세요')
        recipes=self._form_recipes()
        recipe=params['recipe']
        if recipe=='':
            return dict(recipes=recipes)
        if recipe not in recipes:
            raise ValueError('등록된 레시피를 선택하세요')
        prev=workdirs.recipe_delete_preview(str(self.root),recipe)
        try:
            ws,_=watcher.load_settings(str(self.root))
            watched=[m for m,names in watcher.machine_recipes(ws).items() if any(rtp.norm_key(r)==rtp.norm_key(recipe) for r in names)]
        except Exception:  # noqa: BLE001 - informational only
            watched=[]
        return dict(recipes=recipes,recipe=recipe,versions=prev['versions'],files=prev['files'],
                    bytes=prev['bytes'],watched=watched,latest=Path(workdirs.latest_collate(str(self.root)) or '').name)

    def delete(self, params):
        """Move 양식/{레시피}/ to the local 삭제보관 (undoable), drop the recipe's sheet
        from the latest collation and from the watch settings. Past collations and
        변환계수.xlsx are kept, exactly as the tkinter delete (user decision 2026-08)."""
        if set(params)!={'recipe','confirm'}:
            raise ValueError('삭제할 레시피를 확인하세요')
        recipe=params['recipe']
        if recipe not in self._form_recipes():
            raise ValueError('등록된 레시피를 선택하세요')
        if params['confirm']!=recipe:
            raise ValueError('확인을 위해 레시피 이름을 정확히 입력하세요')
        src=self.root/workdirs.FORM_DIR/workdirs._sanitize(recipe)
        self.safe_path(src)
        busy=[f for dp,_d,files in _os.walk(src) for f in files if f.startswith('~$')]
        if busy:
            raise ValueError('양식 파일이 Excel에서 열려 있습니다. 닫고 다시 시도하세요: '+', '.join(sorted(set(busy))[:6]))
        local=Path(DesktopBatch(self.config_path).configuration()[2])
        user=engine.current_user()
        held=[]
        try:
            for name,work in ((f'양식_{recipe}',f'{recipe} 레시피 삭제'),(locking.GLOBAL_COLLATE,'레시피 삭제(취합 시트)')):
                state=locking.acquire_global(str(self.root),name,user)
                if not state.editable:
                    raise ValueError(locking.holder_message(state,work))
                held.append(name)
            vault=localdirs.new_deleted_slot(str(local),recipe)
            moved=workdirs.move_recipe_dir(str(self.root),recipe,vault)
            sheets=0
            latest=workdirs.latest_collate(str(self.root))
            note=''
            if latest:
                try:
                    sheets=collate.delete_recipe(self.safe_path(latest),recipe)
                except Exception:  # noqa: BLE001 - folder move is not rolled back (tkinter E117)
                    note='최신 취합본에서 시트를 지우지 못했습니다. 기존 프로그램에서 확인하세요.'
            watch={}
            try:
                ws,wst=watcher.load_settings(str(self.root))
                watch=watcher.drop_recipe(ws,recipe)
                watcher.save_settings(str(self.root),ws,wst)
                watcher.append_log(str(self.root),f'레시피 삭제 — {recipe}')
            except Exception:  # noqa: BLE001
                note=note or '자동 감시 설정 정리에 실패했습니다(삭제 자체는 완료).'
        finally:
            for name in held:
                locking.release_global(str(self.root),name,user)
        return dict(recipe=recipe,moved=moved or '',sheets=sheets,watch_machines=watch.get('machines',[]),
                    watch_empty=bool(watch.get('empty')),note=note)
