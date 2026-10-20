/* 메모 › 장비 IP 의 호기 고르기(#35) — 설정 › AOI 장비 호기 루트(CAMTEK · KLA)에서 호기 이름을 일일이 타이핑하지 않게
   메모(`장비 IP 주소.xlsx`)에 적힌 호기를 목록으로 보여 준다. 고르면 이름 칸만 채운다(폴더는 사람이 지정).
   목록 = 그 회사 장비종류 → 장비종류 미지정 순, 다른 회사로 적힌 호기와 이미 등록한 호기는 뺀다.
   엔진 `config_state` 의 `memo_machines`(읽기만, 파일이 그대로면 다시 열지 않음). */
export type MemoMachine={name:string;type:string};

export function MemoPick({memo,vendor,registered,onPick,disabled}:{memo?:MemoMachine[];vendor:'CAMTEK'|'KLA';
  registered:string[];onPick:(name:string)=>void;disabled?:boolean}){
  if(!memo)return null;
  const kind=(t:string)=>t.trim().toUpperCase();
  const free=memo.filter(m=>!registered.includes(m.name));
  const mine=free.filter(m=>kind(m.type)===vendor),blank=free.filter(m=>!kind(m.type));
  if(!memo.length)return <p className="hint" style={{width:'100%',margin:0}}>메모 › 장비 IP 에 호기를 적어 두면 여기서 골라 이름을 채울 수 있습니다.</p>;
  const opts=(list:MemoMachine[])=>list.map(m=><option key={m.name} value={m.name}>{m.name}</option>);
  return <label className="field" style={{width:190}}>메모(장비 IP)에서 고르기
    <select value="" disabled={disabled||!(mine.length+blank.length)} aria-label={`${vendor} 메모 장비 IP 에서 호기 고르기`}
      onChange={e=>{if(e.target.value)onPick(e.target.value);}}>
      <option value="">{mine.length+blank.length?`선택… (${mine.length+blank.length}대)`:'고를 호기 없음(모두 등록됨)'}</option>
      {mine.length>0&&<optgroup label={`장비종류 ${vendor==='KLA'?'KLA':'Camtek'}`}>{opts(mine)}</optgroup>}
      {blank.length>0&&<optgroup label="장비종류 미지정">{opts(blank)}</optgroup>}
    </select></label>;
}
