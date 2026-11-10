// Seek tracks are siblings of the ARIA slider thumb, and must not toggle playback.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../ui/src/shared/usePlayerGestures.js',import.meta.url),'utf8')
  .replace(/^import .*\n/,'').replace('export default function','function');
const listeners=new Map(),timers=new Map();let timerId=0,captured=null;
const video={paused:false,currentTime:20,volume:1,playbackRate:1,style:{},pause(){this.paused=true;},play(){this.paused=false;return Promise.resolve();}};
const root={addEventListener:(name,fn)=>listeners.set(name,fn),removeEventListener(){},getBoundingClientRect:()=>({left:0,top:0,width:100,height:100}),hasAttribute:()=>false,setPointerCapture:id=>{captured=id;},hasPointerCapture:id=>captured===id,releasePointerCapture:()=>{captured=null;},removeAttribute(){},style:{removeProperty(){}}};
vm.runInNewContext(source+';usePlayerGestures({current:root},{current:video},()=>{},()=>{},()=>{},video);',{
  root,video,useEffect:fn=>fn(),useRef:value=>({current:value}),useState:()=>[null,()=>{}],
  window:{addEventListener(){},removeEventListener(){}},document:{addEventListener(){},removeEventListener(){}},performance:{now:()=>1000},
  setTimeout:fn=>{timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id),
});
function click(slider){
 const event={pointerType:'mouse',button:0,pointerId:1,clientX:50,clientY:90,target:{closest:selector=>slider&&selector.includes('.media-slider')?{}:null},preventDefault(){},stopPropagation(){}};
 listeners.get('pointerdown')(event);listeners.get('pointerup')(event);
}
function flush(){const pending=[...timers.values()];timers.clear();pending.forEach(fn=>fn());}
click(true);flush();assert.equal(video.paused,false,'clicking the seek track must keep playing');
click(false);click(true);flush();assert.equal(video.paused,false,'seeking must cancel a pending video tap');
click(false);flush();assert.equal(video.paused,true,'a normal video tap must still pause');
click(true);flush();assert.equal(video.paused,true,'seeking while paused must stay paused');
console.log('PASS: seek clicks preserve playback and cancel delayed taps; normal video taps still work.');
