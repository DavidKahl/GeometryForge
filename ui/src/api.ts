import * as THREE from 'three';

export type Artifact={path:string;sha256:string};
export type Measurements={bbox_mm?:number[];volume_mm3?:number;bed_mm?:number[];checks?:Record<string,boolean>;triangles?:number;materials?:number};
export type Part={reused:boolean;artifacts:Artifact[];measurements?:Measurements};
export type Filament={slot:number;name?:string;colour:string;material?:string;preset?:string;used_for?:string};
export type Kit={artifacts:Artifact[];parts:Record<string,number[]>;filaments:Record<string,Filament>;bambu?:{skipped?:string;machine?:string;process?:string;files?:Record<string,{plates:number;instances:number}>}};
export type Material={id:string;base_color?:number[];roughness?:number;metallic?:number;blend_mode?:string;textures:Record<string,{path:string;preview_path?:string;color_space:string}>};
export type Backend={parts:Record<string,Part>;checks:Record<string,{passed:boolean;reused:boolean}>;native?:Artifact;changed_parts:string[];rebuilt_parts:string[];kit?:Kit;target?:string;game?:{manifest:string;package_id:string;package_safe:boolean;materials:Record<string,Material>;artifacts:Artifact[]}};
export type Target={status:string;backends:Record<string,Backend>;failures:string[];settings?:{profile?:string;conversion_notes?:string[]}};
export type Run={id:string;parent:string|null;status:string;backends:Record<string,Backend>;targets?:Record<string,Target>;failures:string[];decisions?:{print?:{filaments?:Filament[]}}};
export type Project={path:string;title:string;archived:boolean};
export type Context={safe_point:string|null;safe_point_label:string;issues:string[];backends:Record<string,{stale:boolean;working_changed:boolean}>;targets?:Record<string,{safe_point:string|null;stale:boolean}>;unreal?:{safe_import?:string}};
export type Calibration={position_mm:number[];target_mm:number[];up:number[];ortho_scale_mm?:number;projection?:string;resolution:number[];rms_px?:number;status?:string};
export type Reference={path:string;view:string;kind:'clean'|'calibrated'|'identity';camera:string|null;calibration:Calibration|null};
export type ImportEvidence={id:string;run:string;backend:string;status:string;package_id:string;coverage?:{commandlet?:boolean;rendered_review?:boolean;performance_measured?:boolean};review?:{screenshot:string;profiler_csv:string[]};failures:string[]};
export type MeshInfo={role:string;lod:number;materialIds:string[];pivot:number[];sockets:{name:string;position_mm:number[];world_position_mm?:number[]}[]};
export type Loaded={name:string;part:Part;geometries:THREE.BufferGeometry[];filaments:number[];rotation:number[];meshInfo:MeshInfo[];game?:Backend['game']};

let token='';
export const session={key:''};

export async function api(url:string,method='GET',body?:unknown){
  const response=await fetch('/api'+url,{method,headers:{'Content-Type':'application/json','X-GeometryForge-Token':token},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();if(!response.ok)throw Error(data.error||data.detail||'Request failed');return data;
}
export async function startSession(){token=(await api('/session')).token}
export const artifactURL=(path:string,inline=false)=>`/api/projects/${session.key}/artifact?path=${encodeURIComponent(path)}${inline?'&inline=1':''}`;
export const fileName=(path:string)=>path.split('/').pop()!;
export const find=(part:Part|undefined,suffix:string)=>part?.artifacts.find(a=>a.path.endsWith(suffix));

// Natural order keeps aft_fin_2 before aft_fin_10.
export const natural=new Intl.Collator(undefined,{numeric:true}).compare;

// Geometry is cached per artifact URL: switching runs, backends or views never re-downloads a part.
const geometryCache=new Map<string,Promise<{geometries:THREE.BufferGeometry[];filaments:number[];rotation:number[];meshInfo:MeshInfo[]}>>();
export function clearCache(){for(const entry of geometryCache.values())void entry.then(e=>e.geometries.forEach(g=>g.dispose()),()=>{});geometryCache.clear()}
// Parts load as compact binary meshes (geometryforge/viewer_mesh.py): detailed design evidence is hundreds of megabytes of
// JSON, which a browser cannot parse, while the binary buffers map straight into BufferAttributes.
export const meshURL=(path:string)=>`/api/projects/${session.key}/mesh?path=${encodeURIComponent(path)}`;
type MeshEntry={role?:string;filament?:number;print_rotation_deg?:number[];matrix_world?:number[][];materials:(string|null)[];
  metadata:{lod?:number;sockets?:MeshInfo['sockets']};groups?:number[][];buffers:Record<string,[number,number]>};
function geometry(path:string){
  const url=meshURL(path);let entry=geometryCache.get(url);
  if(!entry){
    entry=fetch(url).then(r=>{if(!r.ok)throw Error(`Could not load ${fileName(path)}`);return r.arrayBuffer()}).then(data=>{
      if(new TextDecoder().decode(new Uint8Array(data,0,4))!=='GFM1')throw Error(`${fileName(path)} is not a viewer mesh`);
      const length=new DataView(data).getUint32(4,true);
      const objects:MeshEntry[]=JSON.parse(new TextDecoder().decode(new Uint8Array(data,8,length))).objects;
      const base=8+length+((4-(8+length)%4)%4);
      const floats=(slice:[number,number])=>new Float32Array(data,base+slice[0],slice[1]);
      const geometries=objects.map(obj=>{const g=new THREE.BufferGeometry();const b=obj.buffers;
        g.setAttribute('position',new THREE.BufferAttribute(floats(b.position),3));
        if(b.index){g.setIndex(new THREE.BufferAttribute(new Uint32Array(data,base+b.index[0],b.index[1]),1));g.computeVertexNormals()}
        else{
          g.setAttribute('normal',new THREE.BufferAttribute(floats(b.normal),3));
          if(b.uv)g.setAttribute('uv',new THREE.BufferAttribute(floats(b.uv),2));
          if(b.tangent)g.setAttribute('tangent',new THREE.BufferAttribute(floats(b.tangent),4));
          for(const [start,count,material] of obj.groups??[])g.addGroup(start,count,material);
          if(obj.matrix_world)g.applyMatrix4(new THREE.Matrix4().set(...obj.matrix_world.flat() as Parameters<THREE.Matrix4['set']>));
        }
        g.computeBoundingBox();return g});
      const meshInfo=objects.map(obj=>{const matrix=obj.matrix_world?new THREE.Matrix4().set(...obj.matrix_world.flat() as Parameters<THREE.Matrix4['set']>):new THREE.Matrix4();return {role:obj.role??'printable',lod:obj.metadata?.lod??0,materialIds:obj.materials.map(m=>m??''),pivot:obj.matrix_world?.map(r=>r[3]).slice(0,3)??[0,0,0],sockets:(obj.metadata?.sockets??[]).map(s=>({...s,world_position_mm:new THREE.Vector3().fromArray(s.position_mm).applyMatrix4(matrix).toArray()}))}});
      return {geometries,filaments:objects.map(o=>o.filament??1),rotation:objects[0]?.print_rotation_deg??[0,0,0],meshInfo};
    });
    entry.catch(()=>geometryCache.delete(url));geometryCache.set(url,entry);
  }
  return entry;
}

export async function loadParts(backend:Backend,progress:(done:number,total:number)=>void){
  const names=Object.keys(backend.parts).sort(natural).filter(n=>find(backend.parts[n],'/assembly.json'));
  const result=new Map<string,Loaded>();let done=0,next=0;progress(0,names.length);
  const worker=async()=>{while(next<names.length){const name=names[next++];const part=backend.parts[name];
    const {geometries,filaments,rotation,meshInfo}=await geometry(find(part,'/assembly.json')!.path);result.set(name,{name,part,geometries,filaments,rotation,meshInfo,game:backend.game});progress(++done,names.length)}};
  await Promise.all(Array.from({length:Math.min(6,names.length)},worker));
  return new Map(names.filter(n=>result.has(n)).map(n=>[n,result.get(n)!]));
}

export function runTime(id:string){
  const m=/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z/.exec(id);if(!m)return id;
  const date=new Date(Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5],+m[6]));
  return date.toLocaleDateString(undefined,{month:'short',day:'numeric'})+' · '+date.toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'});
}
export const shortId=(id:string)=>id.split('-').pop()!;
export function el<K extends keyof HTMLElementTagNameMap>(tag:K,props:Partial<HTMLElementTagNameMap[K]>&{class?:string}={},...children:(Node|string)[]){
  const node=document.createElement(tag);const {class:cls,...rest}=props;if(cls)node.className=cls;Object.assign(node,rest);node.append(...children);return node;
}
