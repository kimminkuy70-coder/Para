"""Single serialized investigation, reusable by manual and daily UI paths."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
from datetime import date, datetime
from pathlib import Path

from . import __version__, batchreport, batchreport_output as output, batchreport_store as store, batchsaved, batchview, lotreport, wph, wph_html

RUN_LOCK = threading.Lock()
LOT_HTML = 'BatchReport_Lot추적.html'
FILES = ('BatchReport_분석.html', LOT_HTML, 'BatchReport_분석.xlsx')


def fingerprint(targets, options, overrides, collection):
    """결과 파일을 다시 만들 필요가 있는지 판단하는 지문(이슈 #12).

    읽은 Batch Report(내용 해시) · 조사 범위 · 옵션 · 사람 선택 · 읽기 오류/알림 · 날짜 · 앱 버전이 모두 같으면
    결과 파일(HTML · Excel)도 같으므로 지난 조사 폴더를 그대로 쓴다. 날짜를 넣어 '오늘까지' 계산이 바뀌는 날은 다시 만든다."""
    body = {
        'v': __version__, 'day': date.today().isoformat(), 'targets': targets, 'options': options,
        'overrides': overrides, 'records': sorted((r['id'], r.get('digest', ''), r['cached_only']) for r in collection['records']),
        'errors': [(e['machine'], e['source_file'], e['error']) for e in collection['errors']],
        'notices': list(collection.get('notices', [])),
    }
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def _previous(base, mark):
    """지문이 같은 가장 최근 조사 폴더(결과 파일이 모두 남아 있을 때만)."""
    try:
        dirs = sorted((d for d in base.glob('조사_*') if d.is_dir() and not d.is_symlink()), key=lambda d: d.name, reverse=True)
    except OSError:
        return None
    for d in dirs[:1]:                        # 가장 최근 것 하나만 비교(그 사이 다른 범위를 조사했으면 새로 만든다)
        try:
            saved = json.loads((d / '조사설정.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        if saved.get('fingerprint') == mark and all((d / f).is_file() for f in FILES):
            return d
    return None


def run(root, targets, options, progress=None, host_gap=2.0, cancel=None, overrides=None):
    """조사 1회. 저장된 결과 파일(Lot 추적 HTML · 분석 HTML/Excel · 가동률 대시보드)은 앱 화면과 같은 `batchview.View`
    (저장된 사람 선택 overrides 포함)로 만든다(이슈 #7 — 기준은 프로그램). 그 View 를 돌려줘 화면이 다시 계산하지 않게 한다."""
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
        if progress:
            progress('화면용 Lot · 가동률 · WPH 를 계산하는 중…')
        view = batchview.View(collection['records'], overrides=overrides)
        machines = list(dict.fromkeys(t['machine'] for t in targets))
        rows = []
        for record in collection['records']:
            row = wph.extract_row(record['report'])
            row['machine'] = record['machine']
            rows.append(row)
        mark = fingerprint(targets, options, overrides, collection)
        previous = _previous(base, mark) if options.get('reuse', True) else None
        if previous is not None:
            # 새 Batch Report · 바뀐 것이 없다 — 지난 결과 파일을 그대로 쓴다(Excel/HTML 을 다시 만들지 않음, 이슈 #12).
            if progress:
                progress('새 Batch Report가 없어 지난 결과 파일을 그대로 씁니다')
            dashboard = base / '대시보드' / '가동률_대시보드.html'
            has_dash = 'M02' in options['metrics'] and dashboard.is_file()
            return {'outdir': str(previous), 'html': str(previous / FILES[0]), 'lots': str(previous / LOT_HTML),
                    'xlsx': str(previous / FILES[2]), 'dashboard': str(dashboard) if has_dash else '',
                    'dashboard_error': '' if has_dash or 'M02' not in options['metrics'] else '대시보드 파일 없음 — 다음 새 조사에서 만듭니다',
                    'result': result, 'collection': collection, 'rows': rows, 'view': view, 'reused_output': True}
        saved = batchsaved.Saved(view.payload(), machines=machines, scope=collection['scope'])
        notices = [f"{e['machine']} / {e['source_file']}: {e['error']}" for e in collection['errors']] + list(collection.get('notices', []))
        store.checkpoint(cancel)
        staging = Path(tempfile.mkdtemp(prefix='.진행중_', dir=base))
        output.atomic_text(staging / 'BatchReport_분석.html', batchsaved.build_html(saved, lot_file=LOT_HTML, notices=notices))
        if progress:
            progress('Lot 추적 HTML 을 만드는 중…')
        output.atomic_text(staging / LOT_HTML, lotreport.build_html(view.model, collection['scope'], view=view))
        if progress:
            progress('분석 Excel과 기존 WPH 산출물을 만드는 중…')
        batchsaved.write_excel(staging / 'BatchReport_분석.xlsx', saved, notices)
        for machine in dict.fromkeys(t['machine'] for t in targets):
            reports = [r['report'] for r in collection['records'] if r['machine'] == machine]
            errors = [(e['source_file'], e['error']) for e in collection['errors'] if e['machine'] == machine]
            text = wph._compose_text(reports, machine, '선택 범위 누적', '', errors)
            output.atomic_text(staging / wph.text_filename(machine, '누적'), text)
        if 'M01' in options['metrics']:
            wph.write_wph_excel(str(staging / 'WPH_통합.xlsx'), rows, valid_wafers=options['valid_wafers'], parse_errors=collection['errors'])
            computed = wph_html.compute(rows, collection['errors'], valid_wafers=options['valid_wafers'])
            wph_html.write_html(staging / 'WPH_통합.html', computed, title='WPH 통합 결과', by_recipe=options.get('by_recipe', True))
        output.atomic_text(staging / '조사설정.json', json.dumps({'targets': targets, 'options': options, 'fingerprint': mark}, ensure_ascii=False, indent=2))
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
                output.atomic_text(dashboard, batchsaved.build_html(saved, dashboard=True, notices=notices))
            except OSError as exc:
                dashboard_error = str(exc)
        return {'outdir': str(outdir), 'html': str(outdir / 'BatchReport_분석.html'), 'lots': str(outdir / LOT_HTML),
                'xlsx': str(outdir / 'BatchReport_분석.xlsx'),
                'dashboard': str(dashboard) if 'M02' in options['metrics'] and not dashboard_error else '',
                'dashboard_error': dashboard_error, 'result': result, 'collection': collection,
                'rows': rows, 'view': view, 'reused_output': False}
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)  # only our locally-created temp dir
        RUN_LOCK.release()
