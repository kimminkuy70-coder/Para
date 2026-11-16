/* Para v14 Defect 분석: AOI Contrast Wizard(HTML rev6)를 프로그램 화면에 맞추는 겉모습 · 틀 — 분석 동작은 건드리지 않는다.
   프로그램(DefectAnalysis.tsx)이 iframe 에 para-skin.css 다음에 넣는다. 하는 일:
   - body 표시(pskin · pskin-big | pskin-diagram) → para-skin.css 가 적용
   - 화면 테마 = 늘 밝은 화면(프로그램과 같게). [화면 테마] · [사진을 같은 창에서 보기] 는 없앰(v14.1.6 소유자) — 새 창이 막히면 HTML 이 알아서 같은 창 칸으로 연다
   - 설명글 · Contrast 도움말 → [? 설명 보기] 체크로 켜고 끔
   - Wafer Map 샘플(기준) → Step 2 맨 위 강조 칸
   - 브라우저 시절 문구 → 프로그램 문구
   - 스크롤 한 겹: 내용 높이를 프로그램에 알림(프로그램이 iframe 높이를 맞춤). 로딩창 · 같은 창 사진 칸은 프로그램이 알려 주는 '보이는 부분'에 맞춤 */
(() => {
  const d = document, B = d.body, mode = new URLSearchParams(location.search).get('mode') || 'big';
  const post = m => { try { parent.postMessage(Object.assign({paraDefect: mode}, m), location.origin); } catch (e) { /* 프로그램 밖 */ } };
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
  // Wafer Map 샘플(기준)이 가장 중요(소유자 2026-11-15 "wafer map 샘플을 제일 상단으로 올리고 박스 표기해서 강조해"):
  // Step 2 맨 위 강조 칸으로 옮긴다 — 요소를 옮기기만 해서 HTML 이 붙인 동작(고르기 · 지우기 · 상태 글)은 그대로.
  const smpRow = d.getElementById('mapBtn') && d.getElementById('mapBtn').closest('.row'), s2 = d.getElementById('step2');
  if (smpRow && s2) {
    const box = d.createElement('div'), lbl = smpRow.querySelector(':scope > b'), st = d.getElementById('mapSt');
    box.className = 'card psample'; box.setAttribute('aria-label', 'Wafer Map 샘플 (기준)');
    box.innerHTML = '<div class="psample-h"><h3>Wafer Map 샘플 (기준)</h3><span class="pbadge">중요</span></div>';
    if (lbl) lbl.remove();
    d.getElementById('mapBtn').classList.add('pri');
    box.append(smpRow);
    const help = d.getElementById('mapSmpHelp'); if (help) box.append(help);
    if (st && st.closest('.row')) box.append(st.closest('.row'));
    s2.querySelector('h2').after(box);
  }
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

  // 페이지 한 겹 스크롤에서는 HTML 이 단계를 옮길 때 목록에 주는 포커스가 프로그램 페이지까지 끌어내린다 →
  // 포커스는 그대로 주되 화면은 움직이지 않고, 단계(스텝퍼)가 바뀌면 프로그램이 이 칸의 맨 위를 보여 준다.
  const focus0 = HTMLElement.prototype.focus;
  HTMLElement.prototype.focus = function (o) { return focus0.call(this, Object.assign({preventScroll: true}, o || {})); };
  const steps = d.querySelectorAll('.b5tabs, nav');
  steps.forEach(n => new MutationObserver(() => post({stage: true})).observe(n, {subtree: true, attributes: true, attributeFilter: ['aria-pressed', 'aria-current']}));

  let last = -1, ov = false;
  const size = () => { const h = Math.ceil(B.getBoundingClientRect().height); if (h !== last) { last = h; post({height: h}); } };
  new ResizeObserver(size).observe(B);
  new MutationObserver(() => { const on = !!d.querySelector('body > .ovw'); if (on !== ov) { ov = on; post({overlay: on}); } }).observe(B, {childList: true});
  addEventListener('message', e => {
    if (e.origin !== location.origin || !e.data || !e.data.paraView) return;
    const v = e.data.paraView, s = d.documentElement.style;
    s.setProperty('--vt', v.top + 'px'); s.setProperty('--vh', v.height + 'px');
  });
  scrollTo(0, 0); size(); post({ready: true});   // 넣기 전에 HTML 이 목록에 준 포커스로 iframe 안이 내려갔으면 되돌림
})();
