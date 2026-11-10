import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../ui/src/shared/usePlayerEdgeControls.js',import.meta.url),'utf8').replace(/^import .*\n/,'').replace('export default function','function');
const events=new Map(),attributes=new Map(),toggles=[];let dismissals=0,cleanup;
const root={getBoundingClientRect:()=>({left:100,right:900}),setAttribute:(key,value)=>attributes.set(key,value),removeAttribute:key=>attributes.delete(key),addEventListener:(key,fn)=>events.set(key,fn),removeEventListener:key=>events.delete(key)};
vm.runInNewContext(source+';usePlayerEdgeControls({current:root},value=>toggles.push(value),()=>dismiss());',{root,toggles,dismiss:()=>dismissals++,useRef:value=>({current:value}),useEffect:fn=>{cleanup=fn();}});
const move=(x,pointerType='mouse',buttons=0)=>events.get('pointermove')({clientX:x,pointerType,buttons});
for(const x of [101,899]){
 move(x);assert.equal(attributes.has('data-pointer-edge'),true);assert.equal(toggles.at(-1),false);
 move(x);move(x<500?115:885);assert.equal(attributes.has('data-pointer-edge'),true,'edge movement must not flicker');
 move(500);assert.equal(attributes.has('data-pointer-edge'),false);assert.equal(toggles.at(-1),true);
}
assert.equal(dismissals,2);
move(101,'touch');move(899,'pen');move(101,'mouse',1);assert.equal(attributes.has('data-pointer-edge'),false,'touch and dragging must stay unchanged');
move(101);events.get('keydown')();assert.equal(attributes.has('data-pointer-edge'),false,'keyboard use reveals controls');
move(899);cleanup();assert.equal(attributes.has('data-pointer-edge'),false);assert.equal(events.size,0);
console.log('PASS: both mouse edges hide overlays; moving inward and keyboard use restore them; touch and dragging unchanged.');
