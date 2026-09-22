import {desktop} from './desktop';
import {fail} from './ui';

/** Ask the engine to open a produced file (or reveal it in Explorer). */
export async function openPath(path:string,reveal=false){
  try{await desktop.request('open_path',{path,reveal}).promise;}
  catch(e){fail(e);}
}

/** Read-only path field with [열기] / [폴더에서 보기] buttons. */
export function OpenPath({label,path,folder=false}:{label:string;path:string;folder?:boolean}){
  return <div className="open-path">
    <label className="field">{label}<input readOnly value={path} onFocus={e=>e.target.select()}/></label>
    <div className="open-actions">
      <button type="button" disabled={!path} onClick={()=>openPath(path)}>{folder?'폴더 열기':'열기'}</button>
      {!folder&&<button type="button" disabled={!path} onClick={()=>openPath(path,true)}>폴더에서 보기</button>}
    </div>
  </div>;
}
