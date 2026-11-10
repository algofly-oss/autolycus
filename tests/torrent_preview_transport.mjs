import assert from 'node:assert/strict';
import fs from 'node:fs';
const {createMediaTransport}=await import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync('ui/src/shared/mediaTransport.js')).toString('base64'));
globalThis.location={href:'http://localhost/'};
const url='/api/torrent/preview/'+ 'a'.repeat(48)+'/file/0';
async function scenario(statuses) {
 let calls=0;
 globalThis.fetch=async target=>String(target).endsWith('/info')?new Response(JSON.stringify({size:4,direct:false}),{status:200}):(++calls,new Response(statuses[calls-1]===206?new Uint8Array([1,2,3,4]):JSON.stringify({detail:statuses[calls-1]===404?'Preview expired or not found':'Peers could not supply this part of the video in time'}),{status:statuses[calls-1]}));
 const transport=await createMediaTransport(url);
 return {transport,calls:()=>calls};
}
let test=await scenario([503,206]);
assert.deepEqual([...await test.transport.read(0,4)],[1,2,3,4]);assert.equal(test.calls(),2);test.transport.close();
test=await scenario([503,503,503]);await assert.rejects(test.transport.read(0,4),/Peers could not supply/);assert.equal(test.calls(),3);test.transport.close();
test=await scenario([404]);await assert.rejects(test.transport.read(0,4),/preview expired/);assert.equal(test.calls(),1);test.transport.close();
console.log('PASS: temporary torrent range failure recovers; retries stop after three requests; expired previews explain recovery');
