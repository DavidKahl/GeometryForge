import {el,runTime,shortId,type Run} from './api';

export type RunsHandlers={open(run:Run):void;compare(run:Run|undefined):void};

export function renderRuns(host:HTMLElement,runs:Run[],a:Run|undefined,b:Run|undefined,safe:string|null,h:RunsHandlers){
  host.replaceChildren(...runs.map(run=>{
    const isA=run.id===a?.id,isB=run.id===b?.id;
    const badges=el('span',{class:'badges'},el('span',{class:'pill '+run.status,textContent:run.status}));
    if(run.id===safe)badges.append(el('span',{class:'pill safe',textContent:'SAFE POINT'}));
    if(isA)badges.append(el('span',{class:'pill role',textContent:'A · open'}));if(isB)badges.append(el('span',{class:'pill role b',textContent:'B · compared'}));
    const card=el('div',{class:'run'+(isA?' selected':'')+(isB?' compared':''),tabIndex:0,title:run.id},
      el('div',{class:'run-head'},el('strong',{textContent:runTime(run.id)}),el('code',{textContent:shortId(run.id)})),badges);
    card.dataset.run=run.id;
    const parts=Object.values(run.backends)[0]?Object.keys(Object.values(run.backends)[0].parts).length:0;
    card.append(el('span',{class:'meta muted',textContent:`${Object.keys(run.backends).join(' + ')||'no backend'} · ${parts} parts`+(run.parent?` · from ${shortId(run.parent)}`:'')}));
    if(run.failures?.length)card.append(el('span',{class:'failure',textContent:run.failures[0],title:run.failures.join('\n')}));
    if(!isA){const cmp=el('button',{class:'compare small'+(isB?' active':''),textContent:isB?'Stop comparing':'Compare with A',title:isB?'Leave comparison':'Show this run beside the open run'});
      cmp.onclick=e=>{e.stopPropagation();h.compare(isB?undefined:run)};card.append(cmp)}
    card.onclick=e=>(e.ctrlKey||e.metaKey)&&!isA?h.compare(run):h.open(run);
    card.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();h.open(run)}};
    return card;
  }));
}
