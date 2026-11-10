import assert from 'node:assert/strict';
import fs from 'node:fs';
const source=fs.readFileSync(new URL('../ui/src/shared/playbackQuality.js',import.meta.url),'utf8');
const {adaptiveQuality}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const versions=[{quality:'original',size:10000000},{quality:'720p',height:720,size:6000000},{quality:'480p',height:480,size:3000000}];
const state={versions,active:'original',buffer:1,stalledFor:3,stableFor:0,sinceSwitch:40,throughput:0,duration:100};
assert.equal(adaptiveQuality(state),'720p');
assert.equal(adaptiveQuality({...state,sinceSwitch:10}),null);
assert.equal(adaptiveQuality({...state,active:'480p'}),null);
assert.equal(adaptiveQuality({...state,active:'720p',buffer:15,stalledFor:0,stableFor:50,sinceSwitch:65,throughput:200000}),'original');
assert.equal(adaptiveQuality({...state,active:'720p',buffer:15,stalledFor:0,stableFor:50,sinceSwitch:65,throughput:10000}),null);
assert.equal(adaptiveQuality({...state,active:'720p',buffer:15,stalledFor:0,stableFor:30,sinceSwitch:65,throughput:200000}),null);
console.log('PASS: conservative adaptation steps down on sustained stalls, upgrades with measured headroom and stable buffer, cooldown prevents oscillation');

assert.equal(adaptiveQuality({...state,active:"original",buffer:2,stalledFor:0,lowBufferFor:8,throughput:1000}),"720p");
assert.equal(adaptiveQuality({...state,buffer:2,stalledFor:0,lowBufferFor:8,throughput:200000}),null);
