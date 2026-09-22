import {useEffect,useState} from 'react';
import {desktop,pickFolder} from './desktop';
import {Stepper,StepNav,notify,fail} from './ui';

type State={save_dir:string;local_dir:string;report_paths:Record<string,string>;scanresult_roots:Record<string,string>};
const STEPS=['저장폴더','배치 Report 폴더','Scanresult 루트'];

export function Settings(){
  const [step,setStep]=useState(0);
  const [st,setSt]=useState<State>();
  const [saveDir,setSaveDir]=useState('');
  const [busy,setBusy]=useState(false);
  const [rMachine,setRMachine]=useState(''),[rPath,setRPath]=useState('');
  const [sMachine,setSMachine]=useState(''),[sPath,setSPath]=useState('');

  async function load(){
    try{await desktop.connect();const r=(await desktop.request('config_state').promise).config as State;
      setSt(r);setSaveDir(r.save_dir||'');}
    catch(e){fail(e);}
  }
  useEffect(()=>{void load();},[]);

  async function browse(set:(v:string)=>void){
    const p=await pickFolder();
    if(p)set(p); else notify('폴더 선택이 취소되었거나 데스크톱 앱이 아닙니다. 경로를 직접 붙여넣어 주세요.','info');
  }
  async function saveSave(){
    if(!saveDir.trim())return;
    setBusy(true);
    try{const r=(await desktop.request('config_set_save_dir',{path:saveDir.trim()}).promise).config as {save_dir:string;created:string[]};
      notify('저장폴더 저장 완료'+(r.created?.length?` · 초기 파일 생성: ${r.created.join(', ')}`:''),'ok');
      await load();setStep(1);}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  async function req(method:string,params:object,ok:string,after?:()=>void){
    setBusy(true);
    try{const r=(await desktop.request(method,params).promise).config as State;setSt(r);notify(ok,'ok');after&&after();}
    catch(e){fail(e);}finally{setBusy(false);}
  }

  const reportRows=Object.entries(st?.report_paths||{});
  const scanRows=Object.entries(st?.scanresult_roots||{});
  return <section className="panel">
    <div className="section-heading"><div><span className="step">SETTINGS</span><h2>설정 마법사</h2></div>
      <button disabled={busy} onClick={load}>새로고침</button></div>
    <p className="hint">웹 앱과 기존 프로그램은 <b>같은 설정 파일</b>을 공유합니다. 경로는 [📁 찾기]로 고르거나 직접 붙여넣을 수 있습니다.</p>
    <Stepper labels={STEPS} current={step} onJump={setStep}/>

    <div className="step-body">
    {step===0&&<>
      <h3>1) 저장폴더 지정 <span className="hint" style={{fontWeight:400}}>— 필수</span></h3>
      <p className="hint">모든 산출물(양식·취합·문서)이 이 폴더 아래 저장됩니다. 처음 지정하면 장비 IP·참고자료·특이사항 초기 파일이 자동 생성됩니다.</p>
      <div className="form-filter" style={{marginTop:14}}>
        <label className="field" style={{flex:1,minWidth:280}}>저장폴더 경로
          <input value={saveDir} placeholder="예: D:\\AOI\\저장폴더" maxLength={4096} onChange={e=>setSaveDir(e.target.value)}/></label>
        <button onClick={()=>browse(setSaveDir)}>📁 찾기</button>
        <button className="primary" disabled={busy||!saveDir.trim()} onClick={saveSave}>저장</button></div>
      {st?.save_dir&&<p className="hint">현재 저장폴더: <code>{st.save_dir}</code></p>}
    </>}

    {step===1&&<>
      <h3>2) 호기별 배치 Report 폴더 등록</h3>
      <p className="hint">배치 리포트 분석에서 각 호기의 batch report(.htm)가 쌓이는 폴더입니다. 나중에 등록해도 됩니다.</p>
      {reportRows.length>0&&<table className="tbl" style={{marginTop:12}}><tbody>{reportRows.map(([m,p])=><tr key={m}>
        <td style={{width:110,fontWeight:700}}>{m}</td><td><code>{p}</code></td>
        <td style={{width:60}}><button className="linklike" disabled={busy} onClick={()=>req('config_remove',{kind:'report',machine:m},'삭제됨')}>삭제</button></td></tr>)}</tbody></table>}
      <div className="form-filter" style={{marginTop:12}}>
        <label className="field" style={{width:150}}>호기<input value={rMachine} placeholder="AOI-21" maxLength={64} onChange={e=>setRMachine(e.target.value)}/></label>
        <label className="field" style={{flex:1,minWidth:240}}>폴더<input value={rPath} placeholder="예: P:\\AOI-21\\Reports" maxLength={4096} onChange={e=>setRPath(e.target.value)}/></label>
        <button onClick={()=>browse(setRPath)}>📁 찾기</button>
        <button className="primary" disabled={busy||!rMachine.trim()||!rPath.trim()} onClick={()=>req('config_set_report_path',{machine:rMachine.trim(),path:rPath.trim()},'Report 폴더 등록',()=>{setRMachine('');setRPath('');})}>추가</button></div>
    </>}

    {step===2&&<>
      <h3>3) 호기별 Commonality Scanresult 루트 등록</h3>
      <p className="hint">Commonality 조사에서 그 호기의 Scanresult(백업본 포함)가 있는 상위 폴더입니다. 나중에 등록해도 됩니다.</p>
      {scanRows.length>0&&<table className="tbl" style={{marginTop:12}}><tbody>{scanRows.map(([m,p])=><tr key={m}>
        <td style={{width:110,fontWeight:700}}>{m}</td><td><code>{p}</code></td>
        <td style={{width:60}}><button className="linklike" disabled={busy} onClick={()=>req('config_remove',{kind:'scanresult',machine:m},'삭제됨')}>삭제</button></td></tr>)}</tbody></table>}
      <div className="form-filter" style={{marginTop:12}}>
        <label className="field" style={{width:150}}>호기<input value={sMachine} placeholder="AOI-9" maxLength={64} onChange={e=>setSMachine(e.target.value)}/></label>
        <label className="field" style={{flex:1,minWidth:240}}>폴더<input value={sPath} placeholder="예: W:\\AOI-9" maxLength={4096} onChange={e=>setSPath(e.target.value)}/></label>
        <button onClick={()=>browse(setSPath)}>📁 찾기</button>
        <button className="primary" disabled={busy||!sMachine.trim()||!sPath.trim()} onClick={()=>req('config_set_scanresult_root',{machine:sMachine.trim(),path:sPath.trim()},'Scanresult 루트 등록',()=>{setSMachine('');setSPath('');})}>추가</button></div>
    </>}
    </div>

    <StepNav step={step} total={STEPS.length} onBack={()=>setStep(s=>s-1)}
      onNext={()=>step<STEPS.length-1?setStep(s=>s+1):notify('설정을 마쳤습니다. 상단 탭에서 기능을 사용하세요.','ok')}
      nextLabel={step<STEPS.length-1?'다음':'완료'} busy={busy}/>
  </section>;
}
