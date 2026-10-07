import {el,natural} from './api';

export type Diff='changed'|'same'|'onlyA'|'onlyB';
export type Row={name:string;reused:boolean;diff?:Diff};
export type PartsState={selection:Set<string>;hidden:Set<string>;filter:string;collapsed:Set<string>;isolated:string[]|null};
export type PartsHandlers={select(names:string[],mode:'replace'|'toggle'|'add'):void;setHidden(names:string[],hidden:boolean):void;isolate(names:string[]):void};

// Parts that differ only by a numeric suffix (aft_fin_1..4) are grouped so they can be picked together.
export const baseName=(name:string)=>name.replace(/[_-]?\d+$/,'')||name;
export function groups(names:string[]){
  const map=new Map<string,string[]>();for(const n of [...names].sort(natural)){const b=baseName(n);map.set(b,[...(map.get(b)??[]),n])}
  return [...map].flatMap(([base,members])=>members.length>1?[{base,members}]:members.map(m=>({base:m,members:[m]})));
}

const DIFF_LABEL:Record<Diff,string>={changed:'changed vs B',same:'identical in B',onlyA:'not in B',onlyB:'only in B'};
let anchor:string|undefined;

export function renderParts(host:HTMLElement,rows:Row[],state:PartsState,h:PartsHandlers){
  const filter=state.filter.trim().toLowerCase(),byName=new Map(rows.map(r=>[r.name,r]));
  const matches=(n:string)=>!filter||n.toLowerCase().includes(filter);
  const order:string[]=[];
  const leaf=(row:Row)=>{
    order.push(row.name);const only=row.diff==='onlyB';
    const eye=el('input',{type:'checkbox',checked:!state.hidden.has(row.name),title:'Show or hide (H)',disabled:only||!!state.isolated});eye.setAttribute('aria-label',`Show ${row.name}`);
    eye.onclick=e=>e.stopPropagation();eye.onchange=()=>h.setHidden([row.name],!eye.checked);
    const iso=el('button',{class:'iso icon',title:'Isolate in its own view (I)',textContent:'⛶',disabled:only});iso.setAttribute('aria-label',`Isolate ${row.name}`);
    iso.onclick=e=>{e.stopPropagation();h.isolate([row.name])};
    const dot=el('span',{class:'dot '+(row.diff??(row.reused?'reused':'updated')),title:row.diff?DIFF_LABEL[row.diff]:row.reused?'reused from an earlier run':'built in this run'});
    const node=el('div',{class:'part-row'+(state.selection.has(row.name)?' selected':'')+(only?' only-b':'')+(state.isolated?.includes(row.name)?' isolated':'')},eye,el('span',{class:'part-name',textContent:row.name,title:row.name}),dot,iso);
    node.dataset.part=row.name;node.tabIndex=only?-1:0;
    if(!only){
      node.onclick=e=>{if(e.shiftKey&&anchor){const a=order.indexOf(anchor),b=order.indexOf(row.name);if(a>=0&&b>=0){h.select(order.slice(Math.min(a,b),Math.max(a,b)+1),e.ctrlKey||e.metaKey?'add':'replace');return}}
        anchor=row.name;h.select([row.name],e.ctrlKey||e.metaKey?'toggle':'replace')};
      node.ondblclick=()=>h.isolate([row.name]);
      node.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();node.click()}};
    }
    return node;
  };
  const nodes:HTMLElement[]=[];
  for(const g of groups(rows.map(r=>r.name))){
    const visible=g.members.filter(m=>matches(m)||matches(g.base));if(!visible.length)continue;
    if(g.members.length===1){nodes.push(leaf(byName.get(g.members[0])!));continue}
    const shown=g.members.filter(m=>!state.hidden.has(m)).length,open=!!filter||!state.collapsed.has(g.base);
    const chev=el('button',{class:'chev icon',textContent:open?'▾':'▸',title:open?'Collapse':'Expand'});chev.setAttribute('aria-expanded',String(open));
    chev.onclick=e=>{e.stopPropagation();state.collapsed[open?'add':'delete'](g.base);renderParts(host,rows,state,h)};
    const eye=el('input',{type:'checkbox',checked:shown===g.members.length,indeterminate:shown>0&&shown<g.members.length,title:'Show or hide the group',disabled:!!state.isolated,className:'group-eye'});
    eye.setAttribute('aria-label',`Show ${g.base} group`);eye.onclick=e=>e.stopPropagation();eye.onchange=()=>h.setHidden(g.members,!eye.checked);
    const iso=el('button',{class:'iso icon',title:'Isolate the group',textContent:'⛶'});iso.onclick=e=>{e.stopPropagation();h.isolate(g.members.filter(m=>byName.get(m)?.diff!=='onlyB'))};
    const picked=g.members.filter(m=>state.selection.has(m)).length;
    const head=el('div',{class:'group-row'+(picked===g.members.length?' selected':picked?' partial':'')},chev,eye,el('span',{class:'part-name'},g.base,el('small',{textContent:` ×${g.members.length}`})),iso);
    head.title='Click to select the whole group';head.tabIndex=0;
    head.onclick=e=>h.select(g.members.filter(m=>byName.get(m)?.diff!=='onlyB'),e.ctrlKey||e.metaKey?'add':'replace');
    head.ondblclick=()=>h.isolate(g.members);head.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();head.click()}};
    const group=el('div',{class:'part-group'},head);if(open)group.append(el('div',{class:'members'},...visible.map(m=>leaf(byName.get(m)!))));
    nodes.push(group);
  }
  host.replaceChildren(...(nodes.length?nodes:[el('p',{class:'muted pad',textContent:rows.length?'No parts match the filter.':'No parts in this run.'})]));
}
