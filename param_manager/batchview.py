"""Batch Report 화면(가동률 조사 및 분석 · 찾기 · 취합)에 보낼 데이터 (헤드리스).

사용자가 프로토타입(`tools/batch_prototype`)으로 검토한 계산을 실제 앱으로 옮긴 것이다.
Lot 규칙은 `lotmodel` 을 그대로 쓰고, 여기서는 화면이 그릴 값만 만든다.

- `View(records, overrides)` — 조사 결과 1회분. `payload()` 가 화면에 한 번에 보내는 요약
  (Batch Report 요약 · Lot 요약 · 가동률 일 단위 · 재스캔 전 대기 · WPH 재료),
  `lot(li)` · `raw(g)` 는 누를 때만 보내는 상세(전송 한도 4MB 때문에 원문 행은 요약에 넣지 않는다).
- 가동률: Batch Time ÷ Dice 있는 행 수 = wafer 1장 몫. 최종 결과로 쓰는 wafer 몫 = 유효 스캔,
  Error 난 wafer 와 이미 Pass 한 wafer 를 다시 스캔한 몫 = Error·중복 스캔(wafer 마다 자기 Error 원문,
  연쇄는 앞 Error 원문). 같은 호기에서 같은 Lot 을 다시 스캔하기까지 장비가 아무것도 스캔하지 않은
  시간 = 재스캔 전 대기(앞 Batch Report 의 Error wafer 원문 비율로 나눔). 자정을 넘긴 시간은 날마다 나눈다.
- WPH: 정상 스캔 = Lot 을 한 번에 25매 모두 Pass 한 Batch Report, 실제 = Lot·공정 단계마다
  최종 Pass wafer ÷ 그 Lot 에 쓴 모든 Batch Time.
- 중복 Pass 는 추천(가장 나중 Pass) + **저장된 사람 선택(overrides)** 으로만 정한다. 화면의 개발자 기능
  토글은 여기에 들어오지 않는다(켜고 끄는 것만으로 숫자가 바뀌면 안 된다 — CLAUDE.md).

파일 접근은 `write_excel`(로컬 결과 폴더, 경로는 호출자가 정함) 하나뿐이다.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, time, timedelta

from . import lotmodel as lm, lotreport

DUP = 'Pass 다시 스캔(중복)'          # 이미 Pass 한 wafer 를 다시 스캔한 몫
SPLIT = '오류 없이 나눠 스캔'          # Error 없이 같은 Lot 을 나눠 스캔한 사이 대기
FULL = lm.FULL_SLOTS


def stamp(value):
    return value.strftime('%Y-%m-%d %H:%M') if value else ''


def day_parts(start, end):
    """[start, end] 를 달력 날짜별로 나눈 [(YYYY-MM-DD, 비율)]. 길이가 없으면 시작일 하나."""
    if not start:
        return []
    if not end or end <= start:
        return [(start.strftime('%Y-%m-%d'), 1.0)]
    total = (end - start).total_seconds()
    out, cur = [], start
    while cur < end:
        stop = min(datetime.combine(cur.date() + timedelta(days=1), time.min), end)
        out.append((cur.strftime('%Y-%m-%d'), (stop - cur).total_seconds() / total))
        cur = stop
    return out


def _span(a):
    start = a['start']
    if not start:
        return None, None
    end = a['end'] if a['end'] and a['end'] > start else start + timedelta(seconds=a['batch_sec'] or 0)
    return start, end


def _reason(row):
    """wafer 행의 Error 원문(첫 문구). 앞 Error 뒤 연쇄(Aborted/Skipped)는 그 앞 Error 문구로."""
    return (row['phrase'] if row['kind'] == '원인' else row['trigger_phrase']) or '(빈 칸)'


def _first_error(a):
    for row in a['rows']:
        if not row['pass']:
            return row['status'] or '(빈 칸)'
    return ''


def _stats(a):
    s = dict(n=len(a['rows']), ok=0, err=0, chain=0)
    ph, cph = Counter(), Counter()
    for row in a['rows']:
        if row['pass']:
            s['ok'] += 1
        elif row['kind'] == '연쇄':
            s['chain'] += 1
            cph[row['phrase'] or '(빈 칸)'] += 1
        else:
            s['err'] += 1
            ph[row['phrase'] or '(빈 칸)'] += 1
    return s, ph, cph


def _num(value):
    return None if value is None else (int(value) if float(value).is_integer() else round(value, 3))


class View:
    """조사 1회분(또는 찾기 1회분)의 Lot 모델 + 화면용 계산."""

    def __init__(self, records, overrides=None, hits=None):
        self.records = list(records)
        self.overrides = dict(overrides or {})
        self.model = lm.build(self.records, self.overrides)
        by_id = {}
        for lot in self.model['lots']:
            for b in lot['bunches']:
                for a in b['attempts']:
                    by_id[a['id']] = a
        for a in self.model['excluded']:
            by_id[a['id']] = a
        self.A = [by_id[r['id']] for r in self.records]
        self.index = {a['id']: g for g, a in enumerate(self.A)}
        self.place = {}                                   # g → (lot, bunch, 위치)
        for li, lot in enumerate(self.model['lots']):
            for bi, b in enumerate(lot['bunches']):
                for p, a in enumerate(b['attempts']):
                    self.place[self.index[a['id']]] = (li, bi, p)
        self.hits = sorted(self.index[h] for h in (hits or ()) if h in self.index)
        self._payload = None

    # ------------------------------------------------------------------ 요약(한 번에 보냄)
    def payload(self):
        if self._payload is None:
            self._payload = self._build()
        return self._payload

    def _build(self):
        R = []
        for g, (record, a) in enumerate(zip(self.records, self.A)):
            s, _, _ = _stats(a)
            li, bi, _ = self.place.get(g, (None, None, None))
            R.append(dict(f=a['file'], m=a['machine'], sm=a['sm'], code=a['code'] or '', job=a['job'], setup=a['setup'],
                          step=a['step'], s=stamp(a['start']), e=stamp(a['end']), sec=a['batch_sec'] or 0,
                          lot=li, b=bi, n=s['n'], ok=s['ok'], err=s['err'], chain=s['chain'], fe=_first_error(a)))
        lots = []
        for li, lot in enumerate(self.model['lots']):
            bunches, causes, per = [], Counter(), {}
            for b in lot['bunches']:
                bunches.append(dict(att=[self.index[a['id']] for a in b['attempts']], step=b['step'], s=stamp(b['start']),
                                    e=stamp(b['end']), moved=b['moved'], machines=b['machines'], sec=b['batch_sec']))
                for w in b['wafers']:
                    if not w['cause']:
                        continue
                    causes[w['cause']] += 1
                    p = per.setdefault(w['cause'], [0, False])
                    p[0] += 1
                    p[1] = p[1] or w['verdict'] == lm.UNRESOLVED
            re_ = sum(w['verdict'] == lm.RECOVERED for b in lot['bunches'] for w in b['wafers'])
            saved = sum(w['overridden'] for b in lot['bunches'] for w in b['wafers'])
            lots.append(dict(key=lot['key'], label=lot['label'], code=lot['code'], lot_id=lot['lot_id'] or '',
                             sms=lot['sms'], jobs=lot['jobs'], machines=lot['machines'], n=lot['attempts'],
                             s=stamp(lot['start']), e=stamp(lot['end']), state=lot['state'], open=lot['unresolved'],
                             re=re_, dup=lot['duplicates'], moved=lot['moved'], saved=saved,
                             multi=any(len(b['attempts']) > 1 for b in lot['bunches']),
                             causes=[[k, n] for k, n in causes.most_common(3)],
                             cz=[[k, v[0], v[1]] for k, v in per.items()], bunches=bunches))
        starts = [r['s'] for r in R if r['s']]
        days, waits = self._utilization()
        return dict(R=R, lots=lots, excluded=[self.index[a['id']] for a in self.model['excluded']],
                    B=days, waits=waits, C=self._wph(), hits=self.hits,
                    range=[min(starts)[:10], max(starts)[:10]] if starts else ['', ''],
                    saved=sum(lot['saved'] for lot in lots),
                    criteria=[[t, d, e] for t, d, e in lotreport.CRITERIA])

    # ------------------------------------------------------------------ 가동률 · 원인
    def _utilization(self):
        busy = defaultdict(list)
        for a in self.A:
            s, e = _span(a)
            if s and e and e > s:
                busy[a['machine']].append((s, e))
        for m, spans in busy.items():
            merged = []
            for s0, e0 in sorted(spans):
                if merged and s0 <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], e0))
                else:
                    merged.append((s0, e0))
            busy[m] = merged

        def idle(machine, s0, e0):
            used = sum(max(0.0, (min(e0, b) - max(s0, a)).total_seconds()) for a, b in busy[machine] if a < e0 and b > s0)
            return max(0.0, (e0 - s0).total_seconds() - used)

        days = defaultdict(lambda: dict(valid=0.0, dropped=0.0, wait=0.0, check=0.0, rec=defaultdict(float),
                                        err=defaultdict(lambda: [0.0, 0.0, set(), 0])))
        waits = []
        for li, lot in enumerate(self.model['lots']):
            for b in lot['bunches']:
                picked = {(w['pick'], c['order']) for w in b['wafers'] if w['pick'] is not None
                          for c in w['cells'] if c['attempt'] == w['pick'] and c['pass']}
                for p, a in enumerate(b['attempts']):
                    start, end = _span(a)
                    if start and a['batch_sec']:
                        self._spread_attempt(days, li, a, p, picked, day_parts(start, end))
                    if p + 1 >= len(b['attempts']):
                        continue
                    nxt = b['attempts'][p + 1]
                    if nxt['machine'] != a['machine'] or not a['end'] or not nxt['start'] or nxt['start'] <= a['end']:
                        continue
                    waits.append(dict(m=a['machine'], s=stamp(a['end']), e=stamp(nxt['start']), li=li,
                                      g=self.index[a['id']]))
                    # 재스캔 전 대기는 앞 Batch Report 의 Error 행 원문 비율로 나눈다(한 장에 Error 가 여럿이어도 구분).
                    bad = Counter(_reason(r) for r in a['rows'] if not r['pass'])
                    if not bad:
                        bad = Counter({DUP if any(r['pass'] for r in nxt['rows']) else SPLIT: 1})
                    total = sum(bad.values())
                    for day, frac in day_parts(a['end'], nxt['start']):
                        seg_s = max(a['end'], datetime.fromisoformat(day + ' 00:00'))
                        seg_e = min(nxt['start'], datetime.fromisoformat(day + ' 00:00') + timedelta(days=1))
                        gap = idle(a['machine'], seg_s, seg_e)
                        d = days[(day, a['machine'])]
                        d['wait'] += gap
                        for reason, n in bad.items():
                            e = d['err'][reason]
                            e[1] += gap * n / total
                            e[2].add(li)
        for a in self.model['excluded']:
            start, end = _span(a)
            if start and a['batch_sec']:
                for day, frac in day_parts(start, end):
                    days[(day, a['machine'])]['check'] += a['batch_sec'] * frac
        out = [dict(d=d, m=m, valid=round(v['valid']), dropped=round(v['dropped']), wait=round(v['wait']),
                    check=round(v['check']), rec={k: round(x) for k, x in v['rec'].items()},
                    err={k: [round(x[0]), round(x[1]), sorted(x[2]), x[3]] for k, x in v['err'].items()})
               for (d, m), v in sorted(days.items())]
        return out, waits

    @staticmethod
    def _spread_attempt(days, li, a, p, picked, parts):
        sec = a['batch_sec']
        scanned = [r for r in a['rows'] if r['scanned'] is not None]
        recipe = f"{a['job']} · {a['step']}"
        valid, dropped, err = 0.0, 0.0, defaultdict(lambda: [0.0, 0])
        if scanned:
            share = sec / len(scanned)
            for r in a['rows']:
                has = r['scanned'] is not None
                if has and (p, r['order']) in picked:
                    valid += share
                elif r['pass'] and not has:
                    continue
                else:
                    # Error wafer 수는 Dice 없는 행도 센다. 시간 몫은 Dice 있는 행만.
                    e = err[DUP if r['pass'] else _reason(r)]
                    e[1] += 1
                    if has:
                        dropped += share
                        e[0] += share
        else:
            # Dice 있는 행이 하나도 없으면 Batch Time 전부를 Error 행 원문 비율로 나눈다.
            bad = Counter(_reason(r) for r in a['rows'] if not r['pass'])
            dropped = sec
            total = sum(bad.values())
            for reason, n in (bad.items() if bad else [(SPLIT, 0)]):
                e = err[reason]
                e[0] += sec * (n / total if total else 1)
                e[1] += n
        for k, (day, frac) in enumerate(parts):
            d = days[(day, a['machine'])]
            d['valid'] += valid * frac
            d['dropped'] += dropped * frac
            if valid:
                d['rec'][recipe] += valid * frac
            for reason, (t, n) in err.items():
                e = d['err'][reason]
                e[0] += t * frac
                e[2].add(li)
                if k == 0:
                    e[3] += n                    # wafer 수는 스캔 시작일에 한 번만

    # ------------------------------------------------------------------ WPH
    def _wph(self):
        base, eff = [], []
        for li, lot in enumerate(self.model['lots']):
            for bi, b in enumerate(lot['bunches']):
                if len(b['attempts']) == 1:
                    a = b['attempts'][0]
                    if len(a['rows']) == FULL and all(r['pass'] for r in a['rows']) and (a['batch_sec'] or 0) > 0:
                        base.append(dict(m=a['machine'], r=f"{a['job']} · {a['step']}", d=stamp(a['start'])[:10],
                                         w=FULL, s=a['batch_sec'], g=self.index[a['id']], lot=li))
                sec = sum(a['batch_sec'] or 0 for a in b['attempts'])
                if sec <= 0:
                    continue
                valid = sum(1 for w in b['wafers'] if w['pick'] is not None)
                eff.append(dict(m=b['machines'][-1], r=f"{b['attempts'][-1]['job']} · {b['step']}",
                                d=stamp(b['start'])[:10], w=valid, s=sec, n=len(b['attempts']), lot=li, b=bi))
        return dict(base=base, eff=eff)

    # ------------------------------------------------------------------ 누를 때만 보내는 상세
    def lot(self, li):
        if type(li) is not int or not 0 <= li < len(self.model['lots']):
            raise ValueError('Lot 을 찾지 못했습니다. 조사를 다시 시작하세요.')
        lot = self.model['lots'][li]
        bunches, stats = [], {}
        for b in lot['bunches']:
            wafers = []
            for w in b['wafers']:
                cells, rec = [], None
                for c in w['cells']:
                    row = b['attempts'][c['attempt']]['rows'][c['order'] - 1]
                    cells.append([c['attempt'], c['status'] or '(빈 칸)', c['pass'], c['kind'] == '연쇄',
                                  _num(row['scanned']), _num(row['bad']), _num(row['good'])])
                    if c['pass']:
                        rec = c['attempt']
                wafers.append(dict(k=w['key'], slot=w['slot'], id=w['wafer_id'], v=w['verdict'], pick=w['pick'],
                                   rec=rec, ov=w['overridden'], cause=w['cause'], chain=w['chain_only'], cells=cells))
            bunches.append(dict(wafers=wafers))
            for a in b['attempts']:
                _, ph, cph = _stats(a)
                stats[self.index[a['id']]] = dict(ph=ph.most_common(), cph=cph.most_common())
        return dict(li=li, bunches=bunches, stats=stats)

    def raw(self, g):
        if type(g) is not int or not 0 <= g < len(self.records):
            raise ValueError('Batch Report 를 찾지 못했습니다. 조사를 다시 시작하세요.')
        record = self.records[g]
        report = record['report']
        headers = list(report['wafers'][0].keys()) if report.get('wafers') else []
        return dict(g=g, f=report.get('file_name', ''), m=record['machine'], folder=record.get('source_folder', ''),
                    meta=[list(kv) for kv in report.get('metadata', [])], h=headers,
                    rows=[[w.get(k, '') for k in headers] for w in report.get('wafers', [])])

    def choice_key(self, li, bi, wafer_key):
        """화면의 (Lot, 공정 단계 줄, wafer) → lotmodel overrides 키 (묶음 key, wafer key)."""
        try:
            b = self.model['lots'][li]['bunches'][bi]
        except (IndexError, TypeError):
            raise ValueError('Lot 을 찾지 못했습니다. 조사를 다시 시작하세요.') from None
        w = next((w for w in b['wafers'] if w['key'] == wafer_key), None)
        if w is None:
            raise ValueError('wafer 를 찾지 못했습니다. 조사를 다시 시작하세요.')
        return b, w

    # ------------------------------------------------------------------ 찾기 · 취합
    def aggregate(self, reports):
        """고른 Batch Report 를 Lot · 공정 단계별로 모아 wafer 마다 후보 행을 만든다.

        추천 = 저장된 사람 선택(그 Batch Report 를 골랐을 때) → 가장 나중 Pass → 가장 나중 스캔.
        """
        if not isinstance(reports, list) or not reports or len(reports) > 5000 or any(
                type(g) is not int or not 0 <= g < len(self.A) for g in reports):
            raise ValueError('취합할 Batch Report 를 고르세요')
        groups = {}
        for g in sorted(set(reports), key=lambda g: (self.A[g]['start'] or datetime.max, g)):
            if g not in self.place:
                continue                                   # 점검 스캔은 취합하지 않는다
            li, bi, _ = self.place[g]
            groups.setdefault((li, bi), []).append(g)
        out = []
        for (li, bi), att in groups.items():
            b = self.model['lots'][li]['bunches'][bi]
            chosen = {w['key']: b['attempts'][w['pick']]['id'] for w in b['wafers'] if w['overridden'] and w['pick'] is not None}
            id_slots = {r['wafer_id']: r['slot'] for g in att for r in self.A[g]['rows']
                        if r['slot'] is not None and lm.is_real_id(r['wafer_id'])}
            cells = defaultdict(list)
            for g in att:
                for r in self.A[g]['rows']:
                    cells[lm._key(r, id_slots)].append(dict(g=g, status=r['status'] or '(빈 칸)', ok=r['pass'],
                                                            id=r['wafer_id'], sc=_num(r['scanned']), bad=_num(r['bad']),
                                                            good=_num(r['good'])))
            wafers = {}
            for key in sorted(cells, reverse=True):
                c = cells[key]
                rec = max((j for j, x in enumerate(c) if x['ok']), default=len(c) - 1)
                saved = chosen.get(key)
                hit = next((j for j, x in enumerate(c) if self.A[x['g']]['id'] == saved and x['ok']), None)
                wafers[key] = dict(cells=c, rec=hit if hit is not None else rec, auto=rec, saved=hit is not None)
            out.append(dict(li=li, bi=bi, att=att, keys=list(wafers), w=wafers))
        if not out:
            raise ValueError('Lot 으로 모인 Batch Report 를 골라 주세요(점검 스캔은 취합하지 않습니다).')
        return out


def write_excel(path, title, stamp_text, lot_rows, wafer_rows):
    """Lot 취합 · wafer 시트 두 장. 1행 = 선택 기준(사람이 결과의 기준을 알 수 있게)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    lot_head = ['Lot', '공정 단계(Recipe(s))', '기간', '호기', 'Batch Report', 'wafer', 'Pass', 'Pass 없음',
                'Scanned', 'Bad', 'Good', 'Yield (%)']
    wafer_head = ['Lot', '공정 단계(Recipe(s))', '슬롯', 'Wafer ID', '결과(쓰는 Batch Report 원문)', 'wafer 결과',
                  '쓰는 Batch Report', '호기', '스캔 시작', 'Scanned', 'Bad', 'Good', 'Yield (%)', '원본 폴더']
    wb = Workbook()
    wb.remove(wb.active)
    for name, head, rows in (('Lot 취합', lot_head, lot_rows), ('wafer', wafer_head, wafer_rows)):
        ws = wb.create_sheet(name)
        ws.append([f'{title} · 선택 기준: {stamp_text}'])
        ws.append(head)
        for row in rows:
            ws.append(list(row))
        for cells in ws.iter_rows():
            for cell in cells:
                if isinstance(cell.value, str):
                    cell.data_type = 's'           # 원문에서 온 글자는 수식으로 해석하지 않는다
        ws['A1'].font = Font(bold=True, color='183047')
        for cell in ws[2]:
            cell.font = Font(color='FFFFFF', bold=True)
            cell.fill = PatternFill('solid', fgColor='183047')
        for i in range(1, len(head) + 1):
            ws.column_dimensions[get_column_letter(i)].width = 22
        ws.freeze_panes = 'A3'
    wb.save(path)
