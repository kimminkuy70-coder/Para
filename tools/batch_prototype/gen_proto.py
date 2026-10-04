"""Batch Report 4개 기능 화면 프로토타입 (실자료 → 단일 HTML, 사용자 검토용).

    python tools/batch_prototype/gen_proto.py <Batch Report 폴더> [출력.html]

실제 앱 화면(frontend/src/styles.css)을 그대로 입혀 ① Lot 추적 ② 찾기·취합 ③ 가동률·원인 ④ WPH 의
UX 와 로직을 눌러 보게 한다. Lot 규칙은 param_manager.lotmodel 을 그대로 쓰고, ③·④ 계산은 구현 예정
로직을 여기서 미리 계산한다. **장비 접근·파일 저장 없음.** 실자료는 저장소에 넣지 않는다(인자로 지정).
"""
import json
import sys
from collections import defaultdict, Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from param_manager import wph, lotmodel as lm, lotreport  # noqa: E402

HERE = Path(__file__).resolve().parent
if len(sys.argv) < 2:
    raise SystemExit(__doc__)
SAMPLE = Path(sys.argv[1])
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd() / 'Batch Report 프로토타입.html'
MACHINE, ROOT = 'AOI-X', r'Y:\AOI-X'


def t(v):
    return v.strftime('%Y-%m-%d %H:%M') if v else ''


# 1) 원본 읽기(복사본 중복 제거 — 기존 store 와 같은 digest 원칙)
records, seen = [], set()
for path in sorted(SAMPLE.rglob('*.htm')):
    rep = wph.parse_report(path)
    digest = repr((rep['metadata'], rep['wafers']))
    if digest in seen:
        continue
    seen.add(digest)
    records.append({'id': str(len(records)), 'machine': MACHINE, 'source_folder': ROOT + r'\Reports', 'report': rep})

model = lm.build(records)
attempts = [lm.attempt(r) for r in records]
idx = {a['id']: i for i, a in enumerate(attempts)}

# 2) 시도(Batch Report) — 원문(메타·웨이퍼 표 그대로) + 계산값
R = []
for i, (rec, a) in enumerate(zip(records, attempts)):
    rep = rec['report']
    headers = list(rep['wafers'][0].keys()) if rep['wafers'] else []
    R.append({'f': rep['file_name'], 'm': a['machine'], 'sm': a['sm'], 'code': a['code'] or '', 'job': a['job'],
              'setup': a['setup'], 'step': a['step'], 's': t(a['start']), 'e': t(a['end']), 'sec': a['batch_sec'] or 0,
              'meta': rep['metadata'], 'h': headers, 'rows': [[w.get(k, '') for k in headers] for w in rep['wafers']],
              'slot': [r['slot'] for r in a['rows']], 'lot': None, 'b': None,
              'fdt': t(wph.parse_filename_datetime(rep['file_name']))})

# 3) Lot (lotmodel) — 시도는 전역 번호로
lots = []
for li, lot in enumerate(model['lots']):
    bunches = []
    for bi, b in enumerate(lot['bunches']):
        att = [idx[a['id']] for a in b['attempts']]
        for g in att:
            R[g]['lot'], R[g]['b'] = li, bi
        wafers = [{'k': w['key'], 'slot': w['slot'], 'id': w['wafer_id'], 'v': w['verdict'], 'pick': w['pick'],
                   'cause': w['cause'], 'chain': w['chain_only'],
                   'cells': [[c['attempt'], c['order'] - 1] for c in w['cells']]} for w in b['wafers']]
        bunches.append({'att': att, 'step': b['step'], 's': t(b['start']), 'e': t(b['end']), 'moved': b['moved'],
                        'machines': b['machines'], 'sec': b['batch_sec'], 'wafers': wafers})
    causes = Counter(w['cause'] for b in lot['bunches'] for w in b['wafers'] if w['cause'])
    lots.append({'key': lot['key'], 'label': lot['label'], 'code': lot['code'], 'lot_id': lot['lot_id'] or '',
                 'sms': lot['sms'], 'jobs': lot['jobs'], 'machines': lot['machines'], 'n': lot['attempts'],
                 's': t(lot['start']), 'e': t(lot['end']), 'state': lot['state'], 'open': lot['unresolved'],
                 'dup': lot['duplicates'], 'moved': lot['moved'],
                 'causes': [[k, n] for k, n in causes.most_common(3)], 'bunches': bunches})
excluded = [idx[a['id']] for a in model['excluded']]

# 4) B 가동률·원인 — 일 단위(호기별)
DUP = 'Pass 다시 스캔(중복)'
SPLIT = '오류 없이 나눠 스캔'
days = defaultdict(lambda: {'valid': 0.0, 'dropped': 0.0, 'wait': 0.0, 'check': 0.0, 'rec': defaultdict(float),
                            'err': defaultdict(lambda: [0.0, 0.0, set()]), 'lots': set()})


# 호기별 '스캔 중' 구간(모든 Batch Report). 재스캔 대기는 그 사이 장비가 다른 것도 안 스캔한 시간만.
busy = defaultdict(list)
for a in attempts:
    if a['start'] and a['end'] and a['end'] > a['start']:
        busy[a['machine']].append((a['start'], a['end']))
for m in busy:
    merged = []
    for s0, e0 in sorted(busy[m]):
        if merged and s0 <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e0))
        else:
            merged.append((s0, e0))
    busy[m] = merged


def idle_seconds(machine, s0, e0):
    used = sum(max(0.0, (min(e0, b) - max(s0, a)).total_seconds()) for a, b in busy[machine] if a < e0 and b > s0)
    return max(0.0, (e0 - s0).total_seconds() - used)


def first_error(a):
    for r in a['rows']:
        if not r['pass']:
            return r['phrase'] or r['status'] or '(빈 칸)'
    return ''


for li, lot in enumerate(model['lots']):
    for b in lot['bunches']:
        picked = {(w['pick'], o) for w in b['wafers'] if w['pick'] is not None
                  for c in w['cells'] if c['attempt'] == w['pick'] and c['pass'] for o in [c['order']]}
        wafer_cause = {}
        for w in b['wafers']:
            for c in w['cells']:
                wafer_cause[(c['attempt'], c['order'])] = (c['pass'], w['cause'])
        for p, a in enumerate(b['attempts']):
            if not a['start'] or not a['batch_sec']:
                continue
            day = days[(a['start'].strftime('%Y-%m-%d'), a['machine'])]
            day['lots'].add(li)
            sec = a['batch_sec']
            scanned = [r for r in a['rows'] if r['scanned'] is not None]
            recipe = f"{a['job']} · {a['step']}"
            if scanned:
                share = sec / len(scanned)
                for r in scanned:
                    if (p, r['order']) in picked:
                        day['valid'] += share
                        day['rec'][recipe] += share
                    else:
                        reason = DUP if r['pass'] else (r['phrase'] if r['kind'] == '원인' else r['trigger_phrase']) or '(빈 칸)'
                        day['dropped'] += share
                        e = day['err'][reason]; e[0] += share; e[2].add(li)
            else:
                reason = first_error(a) or SPLIT
                day['dropped'] += sec
                e = day['err'][reason]; e[0] += sec; e[2].add(li)
            if p + 1 < len(b['attempts']):
                nxt = b['attempts'][p + 1]
                if a['end'] and nxt['start'] and nxt['start'] > a['end']:
                    gap = idle_seconds(a['machine'], a['end'], nxt['start'])
                    reason = first_error(a) or (DUP if any(r['pass'] for r in nxt['rows']) else SPLIT)
                    wday = days[(a['end'].strftime('%Y-%m-%d'), a['machine'])]
                    wday['wait'] += gap
                    e = wday['err'][reason]; e[1] += gap; e[2].add(li)
for g in excluded:
    a = attempts[g]
    if a['start'] and a['batch_sec']:
        days[(a['start'].strftime('%Y-%m-%d'), a['machine'])]['check'] += a['batch_sec']
B = [{'d': d, 'm': m, 'valid': round(v['valid']), 'dropped': round(v['dropped']), 'wait': round(v['wait']),
      'check': round(v['check']), 'lots': len(v['lots']),
      'rec': {k: round(x) for k, x in v['rec'].items()},
      'err': {k: [round(x[0]), round(x[1]), sorted(x[2])] for k, x in v['err'].items()}}
     for (d, m), v in sorted(days.items())]

# 5) C WPH — 기준(25행 모두 Pass 한 장) / 실효(묶음: Pass 웨이퍼 ÷ 모든 시도 시간)
base, eff = [], []
for a in attempts:
    if len(a['rows']) == lm.FULL_SLOTS and all(r['pass'] for r in a['rows']) and (a['batch_sec'] or 0) > 0 and a['code']:
        base.append({'m': a['machine'], 'r': f"{a['job']} · {a['step']}", 'd': t(a['start'])[:10],
                     'w': 25, 's': a['batch_sec']})
for li, lot in enumerate(model['lots']):
    for bi, b in enumerate(lot['bunches']):
        sec = sum(a['batch_sec'] or 0 for a in b['attempts'])
        if sec <= 0:
            continue
        valid = sum(1 for w in b['wafers'] if w['pick'] is not None)
        job = b['attempts'][-1]['job']
        eff.append({'m': b['machines'][-1], 'r': f"{job} · {b['step']}", 'd': t(b['start'])[:10], 'w': valid, 's': sec,
                    'n': len(b['attempts']), 'lot': li, 'b': bi})

DATA = {'machines': [{'id': MACHINE, 'root': ROOT}], 'R': R, 'lots': lots, 'excluded': excluded, 'B': B,
        'C': {'base': base, 'eff': eff}, 'criteria': lotreport.CRITERIA,
        'range': [min(r['s'] for r in R if r['s'])[:10], max(r['s'] for r in R if r['s'])[:10]]}
payload = json.dumps(DATA, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
css = (REPO / 'frontend' / 'src' / 'styles.css').read_text(encoding='utf-8')
template = (HERE / 'proto_template.html').read_text(encoding='utf-8')
page = template.replace('/*%%APPCSS%%*/', css).replace('/*%%DATA%%*/null', payload)
OUT.write_text(page, encoding='utf-8')
print(OUT, round(len(page) / 1e6, 2), 'MB', 'lots', len(lots), 'days', len(B), 'base', len(base), 'eff', len(eff))
