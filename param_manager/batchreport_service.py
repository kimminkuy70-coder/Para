"""Single serialized investigation, reusable by manual and daily UI paths."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from . import batchreport, batchreport_output as output, batchreport_store as store, lotmodel, lotreport, wph, wph_html

RUN_LOCK = threading.Lock()
LOT_HTML = 'BatchReport_Lot추적.html'


def run(root, targets, options, progress=None, host_gap=2.0, cancel=None):
    if not RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("Batch Report 분석이 이미 실행 중입니다")
    staging = None
    try:
        base = store.local_root(root, [t['folder'] for t in targets]) / '배치분석'
        base.mkdir(parents=True, exist_ok=True)
        collection = store.collect(root, targets, progress, host_gap, cancel=cancel, reuse=options.get('reuse', True))
        collection['scope'] = ' / '.join(f"{t['machine']} · {t.get('query') or '(전체 검색어)'} · {t.get('start') or '처음'}~{t.get('end') or '끝'} · "
                                       + (f"선택 {len(t['names'])}개" if t.get('names') is not None else '전체/신규 포함') for t in targets)
        if progress:
            progress('배치 분석 지표를 계산하는 중…')
        store.checkpoint(cancel)
        result = batchreport.compute(collection['records'], selected=options['metrics'],
                                     valid_wafers=options['valid_wafers'])
        store.checkpoint(cancel)
        staging = Path(tempfile.mkdtemp(prefix='.진행중_', dir=base))
        report_html = output.build_html(result, collection)
        output.atomic_text(staging / 'BatchReport_분석.html', report_html)
        if progress:
            progress('Lot 추적(시도 → 묶음 → Lot)을 만드는 중…')
        # Lot 단위 추적: 한 Lot 이 여러 Batch Report·여러 호기로 나뉘는 것을 묶는다(lotmodel).
        output.atomic_text(staging / LOT_HTML, lotreport.build_html(lotmodel.build(collection['records']), collection['scope']))
        if progress:
            progress('분석 Excel과 기존 WPH 산출물을 만드는 중…')
        output.write_excel(staging / 'BatchReport_분석.xlsx', result, collection)
        rows = []
        for record in collection['records']:
            row = wph.extract_row(record['report'])
            row['machine'] = record['machine']
            rows.append(row)
        for machine in dict.fromkeys(t['machine'] for t in targets):
            reports = [r['report'] for r in collection['records'] if r['machine'] == machine]
            errors = [(e['source_file'], e['error']) for e in collection['errors'] if e['machine'] == machine]
            text = wph._compose_text(reports, machine, '선택 범위 누적', '', errors)
            output.atomic_text(staging / wph.text_filename(machine, '누적'), text)
        if 'M01' in options['metrics']:
            wph.write_wph_excel(str(staging / 'WPH_통합.xlsx'), rows, valid_wafers=options['valid_wafers'], parse_errors=collection['errors'])
            computed = wph_html.compute(rows, collection['errors'], valid_wafers=options['valid_wafers'])
            wph_html.write_html(staging / 'WPH_통합.html', computed, title='WPH 통합 결과', by_recipe=options.get('by_recipe', True))
        output.atomic_text(staging / '조사설정.json', json.dumps({'targets': targets, 'options': options}, ensure_ascii=False, indent=2))
        store.checkpoint(cancel)
        # Commit boundary: finish publication once begun; never forcibly interrupt.
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        outdir = base / ('조사_' + stamp)
        os.replace(staging, outdir)
        staging = None
        dashboard = base / '대시보드' / '가동률_대시보드.html'
        dashboard_error = ''
        if 'M02' in options['metrics']:
            try:
                output.atomic_text(dashboard, output.build_html(result, collection, dashboard=True))
            except OSError as exc:
                dashboard_error = str(exc)
        return {'outdir': str(outdir), 'html': str(outdir / 'BatchReport_분석.html'), 'lots': str(outdir / LOT_HTML),
                'xlsx': str(outdir / 'BatchReport_분석.xlsx'),
                'dashboard': str(dashboard) if 'M02' in options['metrics'] and not dashboard_error else '',
                'dashboard_error': dashboard_error, 'result': result, 'collection': collection,
                'rows': rows}
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)  # only our locally-created temp dir
        RUN_LOCK.release()
