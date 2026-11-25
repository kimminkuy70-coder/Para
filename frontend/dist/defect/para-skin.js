/* Para v14 Defect 분석: AOI Contrast Wizard(HTML rev6)를 프로그램 화면에 맞추는 겉모습 · 틀 — 분석 동작은 건드리지 않는다.
   프로그램(DefectAnalysis.tsx)이 iframe 에 para-skin.css 다음에 넣는다. 하는 일:
   - body 표시(pskin · pskin-big | pskin-diagram) → para-skin.css 가 적용
   - 화면 테마 = 늘 밝은 화면(프로그램과 같게). [화면 테마] · [사진을 같은 창에서 보기] 는 없앰(v14.1.6 소유자) — 새 창이 막히면 HTML 이 알아서 같은 창 칸으로 연다
   - 설명글 · Contrast 도움말 → [? 설명 보기] 체크로 켜고 끔
   - (v14.3.12 에서 Wafer Map 샘플 강조 칸은 없앰)
   - 브라우저 시절 문구 → 프로그램 문구
   - 스크롤 한 겹: 내용 높이를 프로그램에 알림(프로그램이 iframe 높이를 맞춤). 로딩창 · 같은 창 사진 칸은 프로그램이 알려 주는 '보이는 부분'에 맞춤
   2026-11-25(소유자 "프로그램에 제대로 이식"): 프로그램이 iframe 없이 화면 안(Shadow DOM, frontend/src/DefectHost.ts)에서 돌리면 paraHost 가 있다 —
   그때는 알림을 paraHost 로 바로 주고, 높이 · 보이는 부분 · focus 바꾸기는 프로그램(DefectHost)이 맡는다. */
(() => {
  const d = document, B = d.body, mode = new URLSearchParams(location.search).get('mode') || 'big';
  const host = typeof paraHost === 'function' ? paraHost : null;   // eslint-disable-line no-undef
  const post = m => { if (host) { host(m); return; } try { parent.postMessage(Object.assign({paraDefect: mode}, m), location.origin); } catch (e) { /* 프로그램 밖 */ } };
  B.classList.add('pskin', mode === 'diagram' ? 'pskin-diagram' : 'pskin-big');
  d.documentElement.dataset.theme = 'light';
  // v14.1.6(소유자 "화면 테마, 사진을 같은 창에서 보기 삭제"): 단추 · 체크를 숨기고, 예전에 켜 둔 '같은 창에서 보기'도 끈다(새 창 우선, 막히면 같은 창 칸).
  const inWin = d.getElementById('inWin');
  if (inWin) { inWin.checked = false; try { localStorage.setItem('cw.inWin', '0'); } catch (e) { /* 기억 못 해도 지금은 꺼짐 */ } }

  // 설명글은 모두 [? 설명 보기] 체크로(소유자 2026-11-15 "설명글은 다 ? 체크박스로 빼"): 끄면(기본) 설명 문단 · Contrast 도움말을 숨기고,
  // 켜면 보인다. 어떤 글이 설명인지는 para-skin.css 의 목록. 두 탭(대규모 · 기본)이 같은 값을 쓴다(이 PC 에 기억).
  const HELP_KEY = 'para.defect.help', hd = d.querySelector('header'), help = d.querySelector('nav .help');
  const tg = d.createElement('label');
  tg.className = 'ptg'; tg.title = '켜면 화면의 설명글과 Contrast 도움말을 보여 줍니다(이 PC 에 기억)';
  tg.innerHTML = '<input type="checkbox" id="pHelp"><span class="q" aria-hidden="true">?</span> 설명 보기';
  if (hd) hd.insertBefore(tg, hd.querySelector('label'));
  const cb = tg.querySelector('input');
  const setHelp = on => { cb.checked = on; B.classList.toggle('pskin-help', on); };
  try { setHelp(localStorage.getItem(HELP_KEY) === '1'); } catch (e) { setHelp(false); }
  cb.addEventListener('change', () => { setHelp(cb.checked); try { localStorage.setItem(HELP_KEY, cb.checked ? '1' : '0'); } catch (e) { /* 기억 못 해도 지금 화면은 바뀜 */ } });
  addEventListener('storage', e => { if (e.key === HELP_KEY) setHelp(e.newValue === '1'); });
  if (help) {   // Contrast 도움말(왼쪽 막대) → 설명을 켜면 보이는 안내 칸
    const box = d.createElement('div'), t = help.querySelector('b');
    box.className = 'card pguide'; box.innerHTML = '<h3>Contrast 도움말</h3>'; if (t) t.remove();
    while (help.firstChild) box.append(help.firstChild);
    help.remove();
    const at = mode === 'diagram' ? null : d.querySelector('#step5 .b5tabs');
    if (at) at.after(box); else d.querySelector('main').prepend(box);
  }
  // v14.3.12: Wafer Map 샘플(기준) 강조 칸(v14.1.0)은 샘플 기능을 지워서 없앰 — 맵은 웨이퍼 맵 기준으로 바로 그린다.
  // 처음에는 안내글이다가 나중에 상태로 바뀌는 줄(맵 파일 비교 · 시뮬레이션 집합): 안내글인 동안만 설명으로 친다
  d.querySelectorAll('#mapSt, #vennNote').forEach(n => {
    const first = n.textContent, mark = () => n.classList.toggle('pinit', n.textContent === first);
    mark(); new MutationObserver(mark).observe(n, {childList: true, characterData: true, subtree: true});
  });
  // 글자 마디만 바꾼다(innerHTML 을 다시 쓰면 안의 입력 칸이 새로 만들어져 HTML 이 붙인 동작이 떨어진다)
  const say = (sel, from, to) => d.querySelectorAll(sel).forEach(n => {
    const w = d.createTreeWalker(n, NodeFilter.SHOW_TEXT);
    for (let t = w.nextNode(); t; t = w.nextNode()) if (t.nodeValue.includes(from)) { t.nodeValue = t.nodeValue.replace(from, to); return; }
  });
  say('#step1 .drop p.muted', '파일은 이 PC 브라우저 안에서만 읽습니다.', '프로그램이 고른 폴더를 직접 읽습니다(읽기 전용).');

  // ── 값 범위 = 양방향 막대 + 숫자 칸(소유자 2026-11-24, DESIGN.md 8-2 ④ — 대규모 5-1 ~ 5-3 · 기본 Step 3 · 4 같은 부품) ──
  // 숫자 칸(data-f="c0" · "c1" …)이 기준이다: 막대는 숫자 칸에 값을 적고 input 이벤트를 보낼 뿐이라 필터 계산은 HTML 그대로(fltBind 0.2초).
  // 막대 양 끝 = 그 필터가 거르는 자료의 실제 최소 · 최대(HTML fltSpan, [µm 로 보기] 단위). 손잡이를 끝까지 밀면 그 칸을 비움(= 제한 없음).
  // 막대 밖 값도 숫자 칸에 적을 수 있다(손잡이는 끝에 붙음). 키보드: ←→ 한 칸 · PageUp/Down 10칸 · Home/End.
  const BARS = new Set(), CNT = new Set();
  const repaint = () => BARS.forEach(p => p());
  const watchCnt = el => { if (!el || CNT.has(el)) return; CNT.add(el); new MutationObserver(repaint).observe(el, {childList: true, characterData: true, subtree: true}); };
  const nice = sp => { const e = Math.pow(10, Math.floor(Math.log10(sp / 200))); return [1, 2, 5, 10].map(m => m * e).find(x => sp / x <= 200); };
  function mountRange(lab) {
    if (lab.dataset.prs) return;
    const i0 = lab.querySelector('input[data-f$="0"]'), i1 = lab.querySelector('input[data-f$="1"]'), b = lab.querySelector('b');
    if (!i0 || !i1 || !b) return;
    lab.dataset.prs = '1';
    const k = i0.dataset.f.slice(0, -1), box = lab.closest('.pflt, .fgrid'), title = b.textContent.trim(), ins = [i0, i1];
    const tr = d.createElement('span'); tr.className = 'prs';
    tr.innerHTML = '<i class="prs-fill"></i><span class="prs-th" role="slider" tabindex="0"><i></i></span><span class="prs-th" role="slider" tabindex="0"><i></i></span>';
    b.after(tr);
    if (!lab.querySelector('[data-umu]')) { const u = d.createElement('span'); u.className = 'prs-u'; lab.append(u); }   // 단위 없는 줄도 막대 길이를 맞춤
    const fill = tr.querySelector('.prs-fill'), th = [...tr.querySelectorAll('.prs-th')];
    th[0].setAttribute('aria-label', title + ' 최소 막대'); th[1].setAttribute('aria-label', title + ' 최대 막대');
    let span = null, drag = -1, pos = [0, 1];
    const num = el => { const t = el.value.trim(); return t === '' || !isFinite(+t) ? null : +t; };
    const step = () => span && span[1] > span[0] ? nice(span[1] - span[0]) : 1;
    const dec = () => Math.max(0, -Math.floor(Math.log10(step())));
    const frac = v => span[1] > span[0] ? Math.min(1, Math.max(0, (v - span[0]) / (span[1] - span[0]))) : v < span[0] ? 0 : 1;
    function paint() {
      try { const R = window.__cw && window.__cw.fltSpan(box); span = R && R[k]; } catch (e) { span = null; }
      if (span && !(span[1] > span[0])) span = null;   // 값이 하나뿐이면 막대로 고를 것이 없음(숫자 칸은 그대로)
      const v = ins.map(num); tr.classList.toggle('off', !span); lab.classList.toggle('on', v[0] != null || v[1] != null);
      pos = [span && v[0] != null ? frac(v[0]) : 0, span && v[1] != null ? frac(v[1]) : 1];
      const L = p => `calc(${p * 100}% + ${10 - 20 * p}px)`;   // 손잡이 가운데 = 막대 안쪽 10px ~ 끝 10px
      th.forEach((t, j) => { t.style.left = L(pos[j]);
        t.setAttribute('aria-valuemin', span ? span[0] : 0); t.setAttribute('aria-valuemax', span ? span[1] : 0);
        t.setAttribute('aria-valuenow', v[j] != null ? v[j] : span ? span[j] : 0); t.setAttribute('aria-valuetext', v[j] == null ? '제한 없음' : String(v[j])); });
      fill.style.left = pos[0] ? L(pos[0]) : '0px'; fill.style.right = pos[1] < 1 ? L(1 - pos[1]) : '0px';
    }
    const put = (j, v) => {   // v = 값, null = 제한 없음
      const o = num(ins[1 - j]); if (v != null && o != null) v = j ? Math.max(v, o) : Math.min(v, o);
      const s = v == null ? '' : String(+v.toFixed(dec()));
      if (ins[j].value !== s) { ins[j].value = s; ins[j].dispatchEvent(new Event('input', {bubbles: true})); }
      paint(); };
    const at = x => { const r = tr.getBoundingClientRect(); return r.width > 20 ? (x - r.left - 10) / (r.width - 20) : 0; };
    const valAt = (j, f) => (j === 0 && f <= 0.001) || (j === 1 && f >= 0.999) ? null : span[0] + Math.round(Math.min(1, Math.max(0, f)) * (span[1] - span[0]) / step()) * step();
    tr.addEventListener('click', e => e.preventDefault());   // label 안: 막대를 눌러도 숫자 칸으로 가지 않게
    tr.addEventListener('pointerdown', e => {
      if (!span || e.button) return; e.preventDefault(); const f = at(e.clientX);
      drag = pos[0] === pos[1] ? (f < pos[0] ? 0 : 1) : Math.abs(f - pos[0]) <= Math.abs(f - pos[1]) ? 0 : 1;   // 가까운 손잡이
      tr.setPointerCapture(e.pointerId); tr.classList.add('drag'); th[drag].focus(); put(drag, valAt(drag, f)); });
    tr.addEventListener('pointermove', e => { if (drag >= 0) put(drag, valAt(drag, at(e.clientX))); });
    const up = () => { if (drag < 0) return; drag = -1; tr.classList.remove('drag'); };
    tr.addEventListener('pointerup', up); tr.addEventListener('pointercancel', up);
    th.forEach((t, j) => t.addEventListener('keydown', e => {
      e.stopPropagation();   // 목록 이동(↑↓ · Space = ☑) 으로 가지 않게
      if (!span) return; const s = step(), cur = num(ins[j]) != null ? num(ins[j]) : span[j]; let v;
      if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') v = cur - s; else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') v = cur + s;
      else if (e.key === 'PageDown') v = cur - 10 * s; else if (e.key === 'PageUp') v = cur + 10 * s;
      else if (e.key === 'Home') v = span[0]; else if (e.key === 'End') v = span[1]; else return;
      e.preventDefault(); if ((j === 0 && v <= span[0]) || (j === 1 && v >= span[1])) v = null; put(j, v); }));
    ins.forEach(el => { el.addEventListener('input', paint); el.addEventListener('change', paint); });
    BARS.add(paint);
    watchCnt(box && box.id === 'bigFlt' ? d.getElementById('bigCnt') : box && d.getElementById(box.id.replace(/Flt$/, 'Cnt')));
    paint();
  }
  const mountAll = n => { if (n.nodeType !== 1) return; if (n.matches('label.rng')) mountRange(n); else if (n.firstElementChild) n.querySelectorAll('label.rng').forEach(mountRange); };
  mountAll(B);
  new MutationObserver(ms => { for (const m of ms) for (const n of m.addedNodes) if (n.nodeType === 1 && !n.classList.contains('br') && !n.classList.contains('it')) mountAll(n); })
    .observe(B, {childList: true, subtree: true});

  // 페이지 한 겹 스크롤에서는 HTML 이 단계를 옮길 때 목록에 주는 포커스가 프로그램 페이지까지 끌어내린다 →
  // 포커스는 그대로 주되 화면은 움직이지 않고, 단계(스텝퍼)가 바뀌면 프로그램이 이 칸의 맨 위를 보여 준다.
  if (!host) {   // 화면 안(DefectHost)일 때는 DefectHost 가 이 칸 요소만 바꾼다(프로그램의 다른 focus 는 그대로)
    const focus0 = HTMLElement.prototype.focus;
    HTMLElement.prototype.focus = function (o) { return focus0.call(this, Object.assign({preventScroll: true}, o || {})); };
  }
  const steps = d.querySelectorAll('.b5tabs, nav');
  steps.forEach(n => new MutationObserver(() => post({stage: true})).observe(n, {subtree: true, attributes: true, attributeFilter: ['aria-pressed', 'aria-current']}));

  let last = -1, ov = false;
  const size = () => { if (host) return; const h = Math.ceil(B.getBoundingClientRect().height); if (h !== last) { last = h; post({height: h}); } };
  if (!host) new ResizeObserver(size).observe(B);
  new MutationObserver(() => { const on = !!d.querySelector('body > .ovw'); if (on !== ov) { ov = on; post({overlay: on}); } }).observe(B, {childList: true});
  addEventListener('message', e => {
    if (e.origin !== location.origin || !e.data || !e.data.paraView) return;
    const v = e.data.paraView, s = d.documentElement.style;
    s.setProperty('--vt', v.top + 'px'); s.setProperty('--vh', v.height + 'px');
  });
  scrollTo(0, 0); size(); post({ready: true});   // 넣기 전에 HTML 이 목록에 준 포커스로 iframe 안이 내려갔으면 되돌림
})();
