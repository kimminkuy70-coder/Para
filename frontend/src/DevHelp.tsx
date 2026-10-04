import {useEffect,useRef} from 'react';

/* 개발자 기능 ? 설명 창(설정 › 정보 · Batch Report 안내 막대 · 끄기 확인창에서 연다). */
export function DevHelp({open,onClose}:{open:boolean;onClose:()=>void}){
  const ref=useRef<HTMLDialogElement>(null);
  useEffect(()=>{const d=ref.current;if(!d)return;if(open&&!d.open)d.showModal();if(!open&&d.open)d.close();},[open]);
  return <dialog className="edit-dialog wide devhelp" ref={ref} aria-labelledby="devHelpTitle" onClose={onClose}>
    <h3 id="devHelpTitle">개발자 기능은 뭐가 다른가요?</h3>
    <p className="lead"><b>같은 wafer가 Pass를 2번 이상 받았을 때, 어느 Batch Report의 Scanned · Bad · Good을 쓸지 사람이 직접 고르고 저장하는 기능</b>입니다. 끄면 고르는 화면만 닫힙니다. <b>결과 숫자는 켜고 끄는 것만으로는 바뀌지 않습니다</b> — 저장한 선택만 결과에 쓰입니다.</p>
    <h4>켜고 끌 때 달라지는 것</h4>
    <div className="table-scroll" style={{maxHeight:'none'}}><table className="t-compact"><thead><tr><th>항목</th><th>꺼짐 (기본 · 일반 사용자)</th><th>켜짐 (개발자 기능)</th></tr></thead><tbody>
      <tr><td>Lot 창 › Lot · wafer 취합</td><td>중복 Pass wafer는 추천(가장 나중 Pass)을 쓰고 <span className="rectag">추천</span> · <span className="tag-man">사람 선택</span> 표시만 보여 줍니다. 고칠 수 없습니다.</td><td>중복 Pass wafer마다 <b>쓸 Batch Report를 고르는 상자</b>가 나오고, <b>[선택 저장]</b> · <b>[이 Lot 추천으로 되돌리기]</b> 버튼이 생깁니다.</td></tr>
      <tr><td>Batch Report 찾기 · 취합</td><td>같은 wafer가 여러 장이면 <b>최신 스캔으로 자동 취합</b>합니다(Pass가 있으면 가장 나중 Pass, 저장된 사람 선택이 있으면 그것).</td><td>Pass가 2번 이상인 wafer가 있으면 <b>고르는 창</b>이 먼저 뜹니다(기본 선택 = 추천). 결과에 '개발자 직접 선택 n건'이 적힙니다.</td></tr>
      <tr><td>Batch Report 화면 위 안내 막대</td><td>저장된 사람 선택이 있을 때만 '저장된 사람 선택 n건 적용 중'을 보여 줍니다.</td><td>항상 보이며, 저장 안 한 선택이 있으면 [저장] · [버리기] 버튼이 나옵니다.</td></tr>
      <tr><td>저장 안 한 선택</td><td>생기지 않습니다.</td><td>고르기만 하고 저장하지 않은 선택은 <b>그 Lot 창의 미리 보기에만</b> 반영되고 다른 화면 숫자에는 들어가지 않습니다('저장 전' 표시).</td></tr>
      <tr><td>결과 숫자 (Dice 합계 · Yield · 가동률 · WPH)</td><td className="same" colSpan={2}>같습니다 — 추천 + 저장된 사람 선택. 켜고 끄는 것만으로는 바뀌지 않고, [선택 저장]을 눌렀을 때만 바뀝니다.</td></tr>
    </tbody></table></div>
    <h4>실수를 막는 장치</h4>
    <ul><li>저장 안 한 선택이 있는 채로 끄려 하면 <b>저장하고 끄기 / 버리고 끄기 / 취소</b>를 묻습니다.</li>
      <li><b>조사 중에는 켜고 끌 수 없습니다</b> — 조사를 시작할 때의 기준으로 끝까지 계산합니다.</li>
      <li>모든 결과(Lot 창 · 찾기 · 취합 결과 · Excel 첫 줄)에 <b>선택 기준</b>을 적습니다: 추천 / + 저장된 사람 선택 n건 / + 개발자 직접 선택 n건.</li>
      <li>찾기 · 취합 결과를 직접 선택으로 만든 뒤 개발자 기능을 끄면 경고와 함께 <b>[추천으로 다시 취합]</b>을 보여 줍니다.</li></ul>
    <h4>언제 쓰나요</h4>
    <ul><li>같은 wafer를 Pass 후 다시 스캔했는데 <b>가장 나중 Pass가 아닌 스캔을 써야 할 때</b>(예: 확인용으로 다시 스캔했거나 조건을 바꿔 스캔한 경우).</li>
      <li>일반 사용자는 켤 필요가 없습니다 — 추천(가장 나중 Pass)이 기본입니다.</li></ul>
    <h4>어디에 저장되나요</h4>
    <ul><li>[선택 저장]을 누르면 이 PC의 로컬 Cache(<code>batch_lot_choices.json</code>)에 남습니다. <b>PC마다 따로</b>이므로 다른 PC는 추천 기준 숫자가 나오며, 차이는 결과의 '선택 기준'으로 보입니다.</li>
      <li>켜고 끄는 곳: <b>설정 › 정보 › 개발자 기능</b>.</li></ul>
    <div className="dialog-actions"><button type="button" className="primary" onClick={()=>ref.current?.close()}>닫기</button></div>
  </dialog>;
}

/** 저장 안 한 선택이 있는 채로 끄려 할 때: 저장하고 끄기 / 버리고 끄기 / 취소. */
export function DevOff({open,count,onSave,onDrop,onCancel,onHelp}:{open:boolean;count:number;onSave:()=>void;onDrop:()=>void;onCancel:()=>void;onHelp:()=>void}){
  const ref=useRef<HTMLDialogElement>(null);
  useEffect(()=>{const d=ref.current;if(!d)return;if(open&&!d.open)d.showModal();if(!open&&d.open)d.close();},[open]);
  return <dialog className="edit-dialog" ref={ref} aria-labelledby="devOffTitle" onClose={onCancel}>
    <h3 id="devOffTitle">저장하지 않은 선택이 있습니다</h3>
    <p className="sub">개발자 기능에서 고쳤지만 저장하지 않은 중복 Pass 선택이 {count}건 있습니다.</p>
    <p className="sub">개발자 기능을 끄면 직접 고치는 화면이 닫히므로, 저장할지 버릴지 먼저 정해 주세요. 이미 저장된 선택은 그대로 적용됩니다. <button type="button" className="linklike" onClick={onHelp}>개발자 기능이 뭐가 다른가요?</button></p>
    <div className="dialog-actions"><button type="button" onClick={()=>ref.current?.close()}>취소(켜 둔 채로)</button><button type="button" onClick={onDrop}>버리고 끄기</button>
      <button type="button" className="primary" style={{minWidth:0}} onClick={onSave}>저장하고 끄기</button></div>
  </dialog>;
}
