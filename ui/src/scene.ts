import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

// A pane is one independent scene. Comparison draws two panes side by side with one shared camera,
// so orbiting either half keeps both runs aligned.
export type Pane={scene:THREE.Scene;root:THREE.Group;helpers:THREE.Group};

export function makePane():Pane{
  const scene=new THREE.Scene();scene.background=new THREE.Color('#0f1824');
  scene.add(new THREE.HemisphereLight(0xdbeaff,0x314151,2.6));
  const key=new THREE.DirectionalLight(0xffffff,2.6);key.position.set(80,-100,160);scene.add(key);
  const rim=new THREE.DirectionalLight(0x9fd8ff,.8);rim.position.set(-120,90,60);scene.add(rim);
  const root=new THREE.Group(),helpers=new THREE.Group();scene.add(root,helpers);
  return {scene,root,helpers};
}

export function disposePane(pane:Pane){
  for(const group of [pane.root,pane.helpers])group.traverse(o=>{const m=o as THREE.Mesh;if(!m.isMesh&&!(o as THREE.Line).isLine)return;
    if(o.userData.ownGeometry||group===pane.helpers)m.geometry.dispose();(Array.isArray(m.material)?m.material:[m.material]).forEach(x=>x.dispose())});
}

// Grid sized to the content: a 20 mm fin gets a fine grid, a 480 mm rocket a coarse one.
export function addGround(pane:Pane,box:THREE.Box3,bed?:number[]){
  const size=box.isEmpty()?new THREE.Vector3(100,100,100):box.getSize(new THREE.Vector3());
  const span=Math.max(size.x,size.y,bed?.[0]??0,bed?.[1]??0,20)*1.6;
  const step=Math.pow(10,Math.floor(Math.log10(span/10)));const extent=Math.ceil(span/step/2)*step*2;
  const grid=new THREE.GridHelper(extent,Math.round(extent/step),0x41556a,0x223142);grid.rotation.x=Math.PI/2;
  const center=box.isEmpty()?new THREE.Vector3():box.getCenter(new THREE.Vector3());
  grid.position.set(bed?0:center.x,bed?0:center.y,box.isEmpty()?0:box.min.z-.05);pane.helpers.add(grid);
  if(bed){const [w,d]=bed,points=[[-w/2,-d/2],[w/2,-d/2],[w/2,d/2],[-w/2,d/2]].map(([x,y])=>new THREE.Vector3(x,y,0));
    const outline=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:0x6fd3b8}));outline.name='bed';pane.helpers.add(outline)}
}

export class Viewer{
  renderer=new THREE.WebGLRenderer({antialias:true});
  camera=new THREE.PerspectiveCamera(40,1,.1,10000);
  controls:OrbitControls;
  panes:Pane[]=[];
  raycaster=new THREE.Raycaster();
  constructor(public host:HTMLElement){
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));host.prepend(this.renderer.domElement);
    this.camera.up.set(0,0,1);this.controls=new OrbitControls(this.camera,this.renderer.domElement);this.controls.enableDamping=true;
    new ResizeObserver(()=>{const r=host.getBoundingClientRect();this.renderer.setSize(r.width,r.height)}).observe(host);
    this.renderer.setAnimationLoop(()=>this.draw());
  }
  setPanes(panes:Pane[]){for(const pane of this.panes)if(!panes.includes(pane))disposePane(pane);this.panes=panes}
  draw(){
    this.controls.update();const size=this.renderer.getSize(new THREE.Vector2());const n=Math.max(this.panes.length,1),w=Math.floor(size.x/n);
    this.camera.aspect=w/Math.max(size.y,1);this.camera.updateProjectionMatrix();this.renderer.setScissorTest(n>1);
    this.panes.forEach((pane,i)=>{this.renderer.setViewport(i*w,0,w,size.y);this.renderer.setScissor(i*w,0,w,size.y);this.renderer.render(pane.scene,this.camera)});
  }
  contentBox(visibleOnly=true){const box=new THREE.Box3();for(const pane of this.panes)pane.root.traverse(o=>{if((o as THREE.Mesh).isMesh&&(!visibleOnly||visible(o)))box.expandByObject(o)});return box}
  fit(box=this.contentBox()){
    if(box.isEmpty())box=this.contentBox(false);if(box.isEmpty())return;
    const size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3());
    const fov=THREE.MathUtils.degToRad(this.camera.fov),radius=Math.max(size.length()/2,5);
    const distance=radius/Math.sin(Math.min(fov,fov*this.camera.aspect)/2)*1.05;
    this.controls.target.copy(center);this.camera.position.copy(center).add(new THREE.Vector3(1,-1.15,.75).normalize().multiplyScalar(distance));
    this.camera.near=distance/1000;this.camera.far=distance*100;this.camera.updateProjectionMatrix();this.controls.update();
  }
  saveCamera(){return {position:this.camera.position.clone(),target:this.controls.target.clone(),near:this.camera.near,far:this.camera.far}}
  restoreCamera(s:ReturnType<Viewer['saveCamera']>){this.camera.position.copy(s.position);this.controls.target.copy(s.target);this.camera.near=s.near;this.camera.far=s.far;this.camera.updateProjectionMatrix();this.controls.update()}
  // Returns the part under the pointer in whichever pane it is over.
  pick(event:{clientX:number;clientY:number}){
    const r=this.renderer.domElement.getBoundingClientRect(),n=Math.max(this.panes.length,1),w=r.width/n;
    const i=Math.min(n-1,Math.floor((event.clientX-r.left)/w)),pane=this.panes[i];if(!pane)return undefined;
    const ndc=new THREE.Vector2(((event.clientX-r.left-i*w)/w)*2-1,-((event.clientY-r.top)/r.height)*2+1);
    this.raycaster.setFromCamera(ndc,this.camera);
    const hit=this.raycaster.intersectObject(pane.root,true).find(h=>visible(h.object)&&h.object.userData.part);
    return hit?.object.userData.part as string|undefined;
  }
}

function visible(o:THREE.Object3D){for(let x:THREE.Object3D|null=o;x;x=x.parent)if(!x.visible)return false;return true}
