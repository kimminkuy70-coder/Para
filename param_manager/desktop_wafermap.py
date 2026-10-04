"""Web UI adapter for Wafer Map 수정하기 (`wafermap`).

Flow (one file at a time, so a long folder never blocks the engine):
  wm_scan(root, mode)        → TXT(또는 편집한 Excel) 목록 + 메타(WAFER/DEVICE/LOT/크기/Bin)
  wm_start(ids, output)      → 선택 파일마다 결과 경로를 미리 정한 작업 계획(변환은 아직)
  wm_convert(index)          → 그 파일 하나를 변환(원본 로직 그대로) · Excel/TXT 저장 · 맵 데이터 반환
  wm_image(index, kind, data)→ 화면이 canvas 로 그린 맵 PNG 를 엔진이 정한 경로에 저장
  wm_reset()                 → 작업 취소·초기화

안전: 원본은 **읽기만** 한다(변환은 늘 새 파일 `_Map_Edit.xlsx` / `_Converted.txt`). 결과 PNG 경로는
엔진이 만들며 UI 는 경로를 주지 못한다. 기본 저장 위치는 원본과 같은 폴더(원본 도구 v6 동작 그대로),
또는 사용자가 고른 폴더(하위 구조 유지). 둘 다 `extra_roots` 로 등록해 `open_path` 로 열 수 있게 한다.
"""
from __future__ import annotations

import base64
import binascii
import threading
from collections import Counter
from pathlib import Path

from . import wafermap, desktop_progress

MAX_OUTPUT = 3_900_000          # map PNG the UI produced; must fit the 4 MB IPC frame as base64
SUFFIXES = {'txt': ('.txt',), 'excel': ('.xlsx', '.xlsm')}


class DesktopWaferMap:
    extra_roots: list = []      # output folders DesktopOpen may open (source folder or a chosen folder)

    def __init__(self, config=None):
        self.config = config
        self.root = None
        self.mode = 'txt'
        self.items = []
        self.job = None
        self.cancel = threading.Event()

    # ------------------------------------------------------------ helpers
    def _item(self, params, key='index'):
        job = self.job
        if not job:
            raise ValueError('진행 중인 작업이 없습니다')
        i = params.get(key)
        if type(i) is not int or not 0 <= i < len(job['items']):
            raise ValueError('파일 번호를 확인하세요')
        return job['items'][i]

    def _register_root(self, root: Path):
        if str(root) not in DesktopWaferMap.extra_roots:
            DesktopWaferMap.extra_roots.append(str(root))

    # ------------------------------------------------------------ steps
    def scan(self, params):
        root = params.get('root')
        mode = params.get('mode', 'txt')
        if set(params) - {'root', 'mode'} or mode not in SUFFIXES \
                or not isinstance(root, str) or not root.strip() or len(root) > 1024:
            raise ValueError('폴더와 변환 방향을 확인하세요')
        path = Path(root.strip())
        if not path.is_dir():
            raise ValueError('폴더를 찾을 수 없습니다. 장비 공유는 탐색기로 먼저 연결하세요.')
        self.cancel.clear()
        files = wafermap.discover(path, SUFFIXES[mode])
        items = []
        for p in files:
            if self.cancel.is_set():
                break
            if len(items) % 20 == 1:
                desktop_progress.report(f'파일 분석 중 — {len(items)}/{len(files)}  ({p.name})')
            rel = str(p.relative_to(path))
            try:
                if mode == 'txt':
                    d = wafermap.parse_txt(p)
                    cnt = Counter(x for r in d['rows'] for x in r)
                    bins = {k: cnt[k] for k in sorted(cnt) if k not in ('000', '___')}
                    items.append(dict(id=len(items), valid=True, path=str(p), relative=rel,
                                      wafer=d['meta'].get('WAFER', p.stem), device=d['meta'].get('DEVICE', ''),
                                      lot=d['meta'].get('LOT', ''), size=f"{d['row_count']}x{d['col_count']}",
                                      bins=bins, error=''))
                else:
                    items.append(dict(id=len(items), valid=True, path=str(p), relative=rel, wafer=p.stem,
                                      device='', lot='', size='Excel', bins={}, error=''))
            except Exception as exc:  # noqa: BLE001 - 한 파일 오류가 목록 전체를 막지 않게
                items.append(dict(id=len(items), valid=False, path=str(p), relative=rel, wafer=p.stem,
                                  device='', lot='', size='-', bins={}, error=str(exc)))
        self.root, self.mode, self.items = path, mode, items
        return dict(root=str(path), mode=mode, items=items,
                    valid=sum(1 for x in items if x['valid']), total=len(items))

    def _target(self, source: Path, output_root):
        """Result path (원본 도구 `_target`). 사용자 폴더면 원본 하위 구조를 유지해 같은 이름이 겹치지 않게 한다."""
        name = source.stem + ('_Map_Edit.xlsx' if self.mode == 'txt' else '_Converted.txt')
        if output_root is None:
            return source.with_name(name)
        folder = output_root / source.parent.relative_to(self.root)
        folder.mkdir(parents=True, exist_ok=True)
        return folder / name

    def start(self, params):
        if set(params) - {'ids', 'output'} or not isinstance(params.get('ids'), list):
            raise ValueError('변환할 파일을 확인하세요')
        if self.root is None:
            raise ValueError('먼저 폴더에서 파일을 찾으세요')
        ids = params['ids']
        if not ids or len(ids) > 2000 or any(type(i) is not int or not 0 <= i < len(self.items) for i in ids):
            raise ValueError('변환할 파일을 목록에서 고르세요')
        chosen = [self.items[i] for i in ids if self.items[i]['valid']]
        if not chosen:
            raise ValueError('정상 파일을 선택하세요')
        raw = params.get('output') or ''
        if not isinstance(raw, str) or len(raw) > 1024:
            raise ValueError('저장 위치를 확인하세요')
        if raw.strip():
            output_root = Path(raw.strip()).absolute()
            try:
                output_root.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ValueError(f'저장 위치를 만들 수 없습니다: {exc}') from exc
            self._register_root(output_root)
        else:
            output_root = None
            self._register_root(Path(self.root))     # results sit next to the source files
        self.cancel.clear()
        items = []
        for x in chosen:
            target = self._target(Path(x['path']), output_root)
            paths = {mode: str(path) for (mode, _, _), (_, path)
                     in zip(wafermap.IMAGE_KINDS, wafermap.image_paths(wafermap.image_base(target)))}
            items.append(dict(src=x['path'], relative=x['relative'], wafer=x['wafer'], lot=x.get('lot', ''),
                              device=x.get('device', ''), output=str(target), image_paths=paths,
                              result=None, map=None, images_done=set()))
        self.job = dict(mode=self.mode, source_root=str(self.root),
                        output_root=str(output_root) if output_root else '', items=items)
        return self.view()

    def view(self, params=None):
        job = self.job
        if not job:
            return dict(job=None)
        return dict(job=dict(
            mode=job['mode'], source_root=job['source_root'], output_root=job['output_root'],
            items=[dict(src=it['src'], relative=it['relative'], wafer=it['wafer'], lot=it['lot'],
                        device=it['device'], output=it['output'], result=it['result']) for it in job['items']]))

    def convert(self, params):
        if set(params) != {'index'}:
            raise ValueError('변환할 파일을 확인하세요')
        it = self._item(params)
        convert = wafermap.txt_to_excel if self.job['mode'] == 'txt' else wafermap.excel_to_txt
        made = convert(Path(it['src']), Path(it['output']))
        it['result'] = dict(output=made['output'], output_name=Path(made['output']).name,
                            source_type='TXT' if self.job['mode'] == 'txt' else 'Excel',
                            output_type='Excel' if self.job['mode'] == 'txt' else 'TXT',
                            folder=str(Path(made['output']).parent))
        it['map'] = made['map']
        it['images_done'] = set()
        return dict(index=params['index'], output=made['output'], output_name=it['result']['output_name'],
                    folder=it['result']['folder'], map=made['map'])

    def image(self, params):
        if set(params) != {'index', 'kind', 'data'} or params.get('kind') not in ('code', 'meaning'):
            raise ValueError('저장할 맵 이미지를 확인하세요')
        it = self._item(params)
        if not it['map']:
            raise ValueError('먼저 파일을 변환하세요')
        data = params.get('data')
        if not isinstance(data, str) or len(data) > MAX_OUTPUT * 4 // 3 + 8:
            raise ValueError('이미지 데이터를 확인하세요')
        try:
            raw = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError('이미지 데이터를 확인하세요') from exc
        if not wafermap.png_size(raw):
            raise ValueError('PNG 이미지가 아닙니다')
        target = Path(it['image_paths'][params['kind']])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        it['images_done'].add(params['kind'])
        return dict(saved=params['kind'], path=str(target))

    def reset(self, params):
        if params:
            raise ValueError('초기화 요청을 확인하세요')
        self.cancel.set()
        self.job = None
        return dict(job=None)
