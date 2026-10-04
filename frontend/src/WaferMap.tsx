import {useRef,useState} from 'react';
import {desktop,errorText,pickFolder} from './desktop';
import {notify,fail,Stepper,StepNav} from './ui';
import {RowPick} from './RowPick';
import {OpenPath} from './OpenPath';

/* Wafer Map 수정하기 (Wafer Map Converter WebView2 v6 이식).
   엔진(param_manager/wafermap.py) = TXT↔Excel 변환(원본 로직 그대로, openpyxl 전용) · 파일 탐색.
   이 화면 = 맵 이미지(BinCode_Map · BinMeaning_Map PNG) 를 canvas 로 그린다
   (추가 패키지 금지라 numpy/matplotlib 대신 — Color·Gray 매칭과 같은 방식). */

type Item={id:number;valid:boolean;path:string;relative:string;wafer:string;device:string;lot:string;size:string;bins:Record<string,number>;error:string};
type Scan={root:string;mode:string;items:Item[];valid:number;total:number};
type ImgSpec={kind:string;mode:'code'|'meaning';path:string};
type MapData={wafer:string;row_count:number;col_count:number;rows:string[][];counts:Record<string,number>;
  present:string[];colors:Record<string,string>;unknown_color:string;mean:Record<string,string>;mean_ko:Record<string,string>;images:ImgSpec[]};
type JobItem={src:string;relative:string;wafer:string;lot:string;device:string;output:string;result:unknown};
type Job={mode:string;source_root:string;output_root:string;items:JobItem[]};
type Result={wafer:string;output:string;output_name:string;output_type:string;folder:string;
  images:{kind:string;path:string}[];preview:Record<string,string>};

const STEPS=['변환 방향·폴더','파일 선택','저장 위치','실행 검토','처리 진행','완료'];
const MODE_LABEL:Record<string,string>={txt:'TXT → Excel (맵을 열어 수정)',excel:'Excel → TXT (수정한 맵을 되돌림)'};

/** OffscreenCanvas → base64 PNG (one IPC message, ≤ 4 MB). */
async function pngB64(canvas:OffscreenCanvas){
  const buf=new Uint8Array(await (await canvas.convertToBlob({type:'image/png'})).arrayBuffer());
  let s='';for(let i=0;i<buf.length;i+=0x8000)s+=String.fromCharCode(...buf.subarray(i,i+0x8000));
  return btoa(s);
}
const hex=(m:MapData,code:string)=>'#'+(m.colors[code]||m.unknown_color);

/** 맵 한 장(Bin Code 또는 Bin Meaning). rows[0] = 맵 위쪽, 아래가 Notch 6시 방향.
    원본 create_images(matplotlib) 와 같은 그림을 canvas 로 그린다. */
function renderMap(m:MapData,mode:'code'|'meaning'):OffscreenCanvas{
  const cc=Math.max(1,m.col_count),rc=Math.max(1,m.row_count);
  const cell=Math.max(4,Math.min(22,Math.round(1100/Math.max(cc,rc))));
  const padL=54,padT=78,padB=108,legendGap=30;
  const entries=m.present.map(code=>({color:hex(m,code),count:m.counts[code]||0,
    label:mode==='code'?`Bin ${code}`:(m.mean[code]||('Unknown Bin '+code))}));
  const probe=new OffscreenCanvas(8,8).getContext('2d')!;probe.font='14px sans-serif';
  let legendW=160;for(const e of entries)legendW=Math.max(legendW,Math.ceil(probe.measureText(`${e.label} (${e.count})`).width)+66);
  const gridW=cc*cell,gridH=rc*cell;
  const W=padL+gridW+legendGap+legendW+16,H=Math.max(padT+gridH+padB,padT+(entries.length+2)*26+40);
  const c=new OffscreenCanvas(W,H),g=c.getContext('2d')!;
  g.fillStyle='#fff';g.fillRect(0,0,W,H);
  g.fillStyle='#1F2A37';g.font='bold 20px sans-serif';g.textAlign='left';g.textBaseline='alphabetic';
  g.fillText(`${m.wafer}  ${mode==='code'?'Bin Code Map':'Bin Meaning Map'} | Notch 6 o'clock`,padL,36);
  const ox=padL,oy=padT;
  for(let r=0;r<rc;r++)for(let col=0;col<cc;col++){g.fillStyle=hex(m,m.rows[r][col]);g.fillRect(ox+col*cell,oy+r*cell,cell,cell);}
  g.strokeStyle='#BCD0C0';g.lineWidth=cell>=8?0.5:0.3;g.beginPath();
  for(let col=0;col<=cc;col++){g.moveTo(ox+col*cell,oy);g.lineTo(ox+col*cell,oy+gridH);}
  for(let r=0;r<=rc;r++){g.moveTo(ox,oy+r*cell);g.lineTo(ox+gridW,oy+r*cell);}
  g.stroke();
  g.strokeStyle='#8AA0A8';g.lineWidth=1;g.strokeRect(ox+0.5,oy+0.5,gridW,gridH);
  g.fillStyle='#556070';g.font='11px sans-serif';g.textBaseline='middle';
  g.textAlign='center';for(let col=0;col<cc;col+=10)g.fillText(String(col),ox+col*cell+cell/2,oy+gridH+16);
  g.textAlign='right';for(let r=0;r<rc;r+=10)g.fillText(String(rc-1-r),ox-6,oy+r*cell+cell/2);
  g.textAlign='center';g.fillText('Col (0-based, left to right)',ox+gridW/2,oy+gridH+42);
  g.save();g.translate(16,oy+gridH/2);g.rotate(-Math.PI/2);g.fillText('Row (0-based, bottom to top)',0,0);g.restore();
  const nx=ox+gridW/2,ny=oy+gridH;
  g.beginPath();g.moveTo(nx-10,ny+24);g.lineTo(nx+10,ny+24);g.lineTo(nx,ny+4);g.closePath();
  g.fillStyle='#fff';g.fill();g.strokeStyle='#263238';g.lineWidth=1.4;g.stroke();
  g.fillStyle='#263238';g.font='bold 12px sans-serif';g.fillText("Notch 6'",nx,ny+42);
  const lx=ox+gridW+legendGap,ly=oy+8;
  g.textAlign='left';g.fillStyle='#1F4E78';g.font='bold 15px sans-serif';g.fillText('범례',lx,ly);
  g.font='14px sans-serif';
  entries.forEach((e,i)=>{const y=ly+28+i*26;g.fillStyle=e.color;g.fillRect(lx,y-9,18,18);
    g.strokeStyle='#999';g.lineWidth=1;g.strokeRect(lx+0.5,y-8.5,18,18);
    g.fillStyle='#222';g.fillText(`${e.label} (${e.count})`,lx+26,y);});
  return c;
}

export function WaferMap(){
  const [step,setStep]=useState(0),[busy,setBusy]=useState(false);
  const [mode,setMode]=useState<'txt'|'excel'>('txt');
  const [root,setRoot]=useState(''),[scan,setScan]=useState<Scan>(),[picked,setPicked]=useState<string[]>([]);
  const [out,setOut]=useState<'source'|'custom'>('source'),[custom,setCustom]=useState('');
  const [job,setJob]=useState<Job>(),[progress,setProgress]=useState({done:0,total:0,text:''}),[log,setLog]=useState<string[]>([]);
  const [results,setResults]=useState<Result[]>([]),[errors,setErrors]=useState<{wafer:string;error:string}[]>([]);
  const [state,setState]=useState<'idle'|'running'|'complete'|'cancelled'|'error'>('idle');
  const [viewer,setViewer]=useState<{src:string;title:string}>();
  const stop=useRef(false);
  const byId=new Map((scan?.items||[]).map(i=>[String(i.id),i]));
  const addLog=(m:string)=>setLog(l=>[...l.slice(-249),`[${new Date().toLocaleTimeString('ko-KR',{hour12:false})}] ${m}`]);

  async function doScan(){
    if(!root.trim())return notify('폴더 경로를 입력하세요.','error');
    setBusy(true);setScan(undefined);setPicked([]);
    try{
      const r=(await desktop.request('wm_scan',{root:root.trim(),mode}).promise).wafermap as Scan;
      setScan(r);setPicked(r.items.filter(i=>i.valid).map(i=>String(i.id)));
      if(r.valid)notify(`${mode==='txt'?'TXT':'Excel'} 파일 ${r.valid}개를 찾았습니다.${r.total>r.valid?` (읽기 오류 ${r.total-r.valid}개 제외)`:''}`,'ok');
      else notify(mode==='txt'?'변환할 TXT 를 찾지 못했습니다. (_Converted.txt 는 제외합니다)':'변환할 Excel(_Map_Edit.xlsx) 을 찾지 못했습니다.','error');
      if(r.items.length)setStep(1);
    }catch(e){fail(e);}finally{setBusy(false);}
  }
  async function browse(set:(p:string)=>void){const p=await pickFolder();if(p)set(p);}

  async function run(){
    const ids=picked.map(id=>byId.get(id)?.id).filter((n):n is number=>n!=null);
    if(out==='custom'&&!custom.trim())return notify('저장 위치를 고르세요.','error');
    setBusy(true);stop.current=false;setResults([]);setErrors([]);setLog([]);setState('running');
    let plan:Job;
    try{plan=((await desktop.request('wm_start',{ids,output:out==='custom'?custom.trim():''}).promise).wafermap as {job:Job}).job;}
    catch(e){setBusy(false);setState('idle');return fail(e);}
    setJob(plan);setStep(4);
    const total=plan.items.length;let done=0;
    setProgress({done:0,total,text:'준비'});addLog(`결과 위치: ${plan.output_root||'원본 파일과 같은 폴더'}`);
    try{
      for(let i=0;i<plan.items.length;i++){
        if(stop.current)break;
        const it=plan.items[i];
        setProgress({done,total,text:`[${i+1}/${total}] ${it.wafer} 변환 중…`});
        try{
          const r=(await desktop.request('wm_convert',{index:i}).promise).wafermap as
            {output:string;output_name:string;folder:string;map:MapData};
          const preview:Record<string,string>={};
          for(const img of r.map.images){
            if(stop.current)break;
            const b64=await pngB64(renderMap(r.map,img.mode));
            await desktop.request('wm_image',{index:i,kind:img.mode,data:b64}).promise;
            preview[img.mode]='data:image/png;base64,'+b64;
          }
          setResults(x=>[...x,{wafer:it.wafer,output:r.output,output_name:r.output_name,folder:r.folder,
            output_type:plan.mode==='txt'?'Excel':'TXT',images:r.map.images.map(im=>({kind:im.kind,path:im.path})),preview}]);
          addLog(`${it.wafer} 완료 → ${r.output_name}`);
        }catch(e){addLog(`실패 ${it.wafer}: ${errorText(e)}`);setErrors(x=>[...x,{wafer:it.wafer,error:errorText(e)}]);}
        done++;setProgress(p=>({...p,done}));
      }
      setProgress(p=>({...p,done:stop.current?p.done:total,text:stop.current?'취소됨':'완료'}));
      setState(stop.current?'cancelled':'complete');setStep(5);
      notify(stop.current?'작업을 멈췄습니다. 변환한 파일까지 저장했습니다.':'Wafer Map 변환을 마쳤습니다.',stop.current?'info':'ok');
    }catch(e){setState('error');addLog('오류 '+errorText(e));fail(e);setStep(5);}
    finally{setBusy(false);}
  }
  async function restart(){
    await desktop.request('wm_reset').promise.catch(()=>undefined);
    setStep(0);setScan(undefined);setPicked([]);setJob(undefined);setResults([]);setErrors([]);setLog([]);
    setState('idle');setOut('source');setCustom('');setViewer(undefined);
  }

  const validCount=scan?.valid||0;
  const outText=out==='custom'?(custom||'(선택하지 않음)'):'원본 파일과 같은 폴더';
  const pct=progress.total?Math.round(progress.done/progress.total*1000)/10:0;
  const canNext=step===0?validCount>0:step===1?picked.length>0:step===2?(out==='source'||!!custom.trim()):true;

  return <section className="panel">
    <div className="section-heading"><div><span className="step">WAFER MAP</span><h2>Wafer Map 수정하기</h2></div>
      <span className="count">{scan?`파일 ${picked.length} / ${validCount}`:'원본 읽기 전용'}</span></div>
    <p className="hint">Wafer Map TXT 를 Excel 로 펼쳐 Bin Code die 를 고치고, <b>원본 그대로</b> 다시 TXT 로 되돌립니다.
      원본 TXT 는 건드리지 않고 <code>_Map_Edit.xlsx</code> · <code>_Converted.txt</code> 와 맵 이미지(PNG) 를 새로 만듭니다.
      손대지 않은 맵은 TXT→Excel→TXT 를 거쳐도 (헤더·빈 줄·줄바꿈·BOM 까지) 바이트가 동일합니다.
      헤더(머리말)는 Excel 의 <code>Header_Edit</code> 시트에서 <b>수정 값</b> 칸을 채울 때만 바뀝니다(맵 크기 ROWCT·COLCT 제외).</p>
    <Stepper labels={STEPS} current={step} onJump={i=>{if(!busy&&i<=3&&(i===0||validCount))setStep(i);}}/>
    <div className="step-body">
    {step===0&&<>
      <div className="out-choice" role="radiogroup" aria-label="변환 방향">
        {(['txt','excel'] as const).map(mo=>
          <div key={mo} className={'out-row'+(mode===mo?' on':'')}>
            <button type="button" role="radio" aria-checked={mode===mo} className={'out-pick'+(mode===mo?' on':'')}
              onClick={()=>{setMode(mo);setScan(undefined);setPicked([]);}}>{MODE_LABEL[mo]}</button>
            <span className="out-path">{mo==='txt'?'TXT 를 열어 색칠된 맵으로 → 수정 가이드 포함 Excel':'수정한 Excel(_Map_Edit.xlsx) → 원본 인코딩·줄바꿈 그대로 TXT'}</span>
          </div>)}
      </div>
      <p className="hint">Lot/폴더를 고르면 하위 폴더까지 재귀로 {mode==='txt'?'TXT':'수정한 Excel(_Map_Edit.xlsx)'} 을 모두 찾습니다.
        장비 공유 폴더는 탐색기(Win+R → <code>\\IP\c$</code>)로 먼저 연결해야 보입니다.</p>
      <div className="form-filter">
        <label className="field" style={{flex:1}}>폴더 경로<input aria-label="폴더 경로" value={root} onChange={e=>setRoot(e.target.value)} placeholder="예: D:\WaferMaps\LOT01"/></label>
        <button disabled={busy} onClick={()=>void browse(setRoot)}>📁 찾아보기…</button>
        <button className="primary" disabled={busy||!root.trim()} onClick={()=>void doScan()}>{busy?'찾는 중…':'파일 찾기'}</button>
      </div>
      {busy&&<p className="hint" role="status"><span className="spinner" aria-hidden="true"/> 하위 폴더에서 파일을 찾는 중입니다.
        <button onClick={()=>void desktop.request('wm_reset').promise.catch(()=>undefined)}>검색 취소</button></p>}
    </>}
    {step===1&&scan&&<>
      <p className="hint">변환할 파일을 고르세요. 기본은 정상 파일 전체 선택입니다. 읽기 오류가 난 파일은 회색으로 표시되며 고를 수 없습니다.</p>
      <RowPick label="변환할 파일" columns={mode==='txt'?['Wafer','크기','Bin(수량)','위치']:['파일','종류','위치']} value={picked} onChange={setPicked}
        rows={scan.items.map(i=>({id:String(i.id),disabled:!i.valid,title:i.error||i.path,
          cells:mode==='txt'
            ?[<b key="w">{i.wafer}</b>,i.valid?i.size:<span className="warn">오류</span>,
              i.valid?<span key="b">{Object.keys(i.bins).length?Object.entries(i.bins).map(([k,v])=>`${k}:${v}`).join('  '):'불량 없음'}</span>:<span className="hint">{i.error}</span>,
              <code key="p">{i.relative}</code>]
            :[<b key="w">{i.wafer}</b>,i.valid?'Excel':<span className="warn">오류</span>,<code key="p">{i.relative}</code>]}))}/>
    </>}
    {step===2&&<>
      <p className="hint">결과(Excel/TXT 와 맵 이미지 PNG 2장)를 어디에 저장할지 고르세요. 원본 TXT 는 어느 경우에도 바뀌지 않습니다.</p>
      <div className="out-choice" role="radiogroup" aria-label="결과 저장 위치">
        <div className={'out-row'+(out==='source'?' on':'')}>
          <button type="button" role="radio" aria-checked={out==='source'} className={'out-pick'+(out==='source'?' on':'')} onClick={()=>setOut('source')}>원본 파일과 같은 폴더 (기본)</button>
          <code className="out-path">각 파일 옆에 <b>{mode==='txt'?'_Map_Edit.xlsx':'_Converted.txt'}</b> 로 저장</code>
        </div>
        <div className={'out-row'+(out==='custom'?' on':'')}>
          <button type="button" role="radio" aria-checked={out==='custom'} className={'out-pick'+(out==='custom'?' on':'')} onClick={()=>setOut('custom')}>다른 폴더</button>
          <input className="out-path" aria-label="다른 폴더 경로" placeholder="폴더 경로를 입력하거나 [찾아보기] (원본 하위 구조 유지)" value={custom}
            onFocus={()=>setOut('custom')} onChange={e=>{setCustom(e.target.value);setOut('custom');}}/>
          <button type="button" onClick={()=>void browse(p=>{setCustom(p);setOut('custom');})}>📁 찾아보기…</button>
        </div>
      </div>
    </>}
    {step===3&&<>
      <table className="tbl watch-status" aria-label="실행 전 검토"><tbody>
        <tr><th>변환 방향</th><td>{MODE_LABEL[mode]}</td></tr>
        <tr><th>선택 폴더</th><td><code>{root}</code></td></tr>
        <tr><th>변환 파일</th><td>{picked.length}개</td></tr>
        <tr><th>결과 위치</th><td><code>{outText}</code></td></tr>
        <tr><th>맵 이미지</th><td>BinCode_Map · BinMeaning_Map (PNG, 결과와 같은 폴더)</td></tr>
        <tr><th>원본 보존</th><td>원본 {mode==='txt'?'TXT':'Excel'} 은 읽기만 하며 변경되지 않습니다.</td></tr></tbody></table>
      <div className="toolbar"><button className="primary" disabled={busy} onClick={()=>void run()}>▶ 변환 시작</button></div>
    </>}
    {step===4&&<>
      <p role="status" aria-live="polite"><b>{progress.text}</b></p>
      <div className="progress-bar" aria-label="처리 진행률" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><i style={{width:`${pct}%`}}/></div>
      <p className="hint">{progress.done} / {progress.total} 파일 · {pct}% — 이 화면을 벗어나도 계속 처리합니다(다른 탭 이동 가능).</p>
      <pre className="log-box" aria-label="처리 기록">{log.join('\n')}</pre>
      <div className="toolbar"><button className="danger" disabled={!busy} onClick={()=>{stop.current=true;notify('현재 파일까지 처리하고 멈춥니다.','info');}}>작업 취소</button></div>
    </>}
    {step===5&&<>
      <p><b className={state==='complete'?'st-on':'st-off'}>{state==='complete'?'완료':state==='cancelled'?'취소됨':'오류'}</b>
        {job&&<> · 성공 {results.length}{errors.length?` · 실패 ${errors.length}`:''}</>}</p>
      {job&&<OpenPath label="결과 폴더" path={job.output_root||job.source_root} folder/>}
      <table className="tbl" aria-label="파일별 결과"><thead><tr><th>Wafer</th><th>결과 파일</th><th>맵 이미지</th></tr></thead>
        <tbody>{results.map(r=><tr key={r.output}><td><b>{r.wafer}</b></td>
          <td><OpenPath label={r.output_name} path={r.output}/></td>
          <td className="wm-imgcell">{r.images.map(im=><span key={im.path}>
            {r.preview[im.kind]&&<button type="button" className="wm-thumbbtn" onClick={()=>setViewer({src:r.preview[im.kind],title:`${r.wafer} · ${im.kind==='code'?'Bin Code Map':'Bin Meaning Map'}`})}>
              <img src={r.preview[im.kind]} alt={im.kind} loading="lazy"/></button>}
            <OpenPath label={im.kind==='code'?'Bin Code':'Bin Meaning'} path={im.path}/></span>)}</td></tr>)}</tbody></table>
      {errors.length>0&&<table className="tbl" aria-label="변환 실패"><thead><tr><th>Wafer</th><th>오류</th></tr></thead>
        <tbody>{errors.map((e,i)=><tr key={i}><td>{e.wafer}</td><td className="warn">{e.error}</td></tr>)}</tbody></table>}
      {log.length>0&&<details><summary>처리 기록</summary><pre className="log-box">{log.join('\n')}</pre></details>}
      <div className="toolbar"><button className="primary" onClick={()=>void restart()}>새 작업</button></div>
    </>}
    </div>
    {step<3&&<StepNav step={step} total={4} busy={busy} nextDisabled={!canNext} nextLabel="다음"
      onBack={()=>setStep(s=>Math.max(0,s-1))} onNext={()=>setStep(s=>s+1)}/>}
    {step===3&&<div className="stepnav"><button className="btn" disabled={busy} onClick={()=>setStep(2)}>◀ 이전</button><span className="stepcount">4 / {STEPS.length}</span><span/></div>}
    {viewer&&<div className="wm-viewer" role="dialog" aria-label={viewer.title} onClick={()=>setViewer(undefined)}>
      <div className="wm-viewer-box" onClick={e=>e.stopPropagation()}><div className="wm-viewer-top"><b>{viewer.title}</b><button onClick={()=>setViewer(undefined)}>닫기 ✕</button></div>
        <img src={viewer.src} alt={viewer.title}/></div></div>}
  </section>;
}
