import {alignEnvelopes} from './audioTimeline';

async function decoder(track) {
  const codec=await track.getCodec();
  if(codec==='ac3'||codec==='eac3')(await import('@mediabunny/ac3')).registerAc3Decoder();
  if(codec==='dts')(await import('@mediabunny/dts')).registerDtsDecoder();
  if(!await track.canDecode())throw new Error('Audio alignment is unavailable for this track. Use manual sync.');
}
async function envelope(media,track,start,seconds,signal) {
  await decoder(track);
  const frequency=20,result=new Float32Array(Math.ceil(seconds*frequency)),counts=new Uint32Array(result.length);
  for await(const sample of new media.bunny.AudioSampleSink(track).samples(start,start+seconds)) {
    try {
      if(signal.aborted)throw new DOMException('Cancelled','AbortError');
      const data=new Float32Array(sample.numberOfFrames);sample.copyTo(data,{planeIndex:0,format:'f32-planar'});
      for(let i=0;i<data.length;i+=16){const bin=Math.floor((sample.timestamp+i/sample.sampleRate-start)*frequency);if(bin>=0&&bin<result.length){result[bin]+=data[i]*data[i];counts[bin]++;}}
    }finally{sample.close();}
  }
  for(let i=0;i<result.length;i++)result[i]=counts[i]?Math.sqrt(result[i]/counts[i]):0;
  return result;
}
export async function autoAlignAudio(main,donor,trackId,signal) {
  const track=donor.audio.find(row=>row.id===trackId)||donor.audio[0];
  if(!main.audio[0]||!track)throw new Error('Choose an audio track first.');
  // Two short windows, at most 80 seconds decoded per file. No whole-movie PCM.
  const duration=Math.min(main.duration || 0,donor.duration || 0);
  const first=Math.max(0,Math.min(60,duration/8)),second=Math.max(first,Math.min(first+300,duration-45));
  const anchors=[];
  for(const start of [...new Set([first,second])]) {
    if(signal.aborted)throw new DOMException('Cancelled','AbortError');
    const [a,b]=await Promise.all([envelope(main,main.audio[0],start,40,signal),envelope(donor,track,start,40,signal)]);
    const match=alignEnvelopes(a,b,{maxOffset:15});
    if(match)anchors.push({start,...match});
  }
  if(!anchors.length)throw new Error('No reliable match found. Different edits or dubbed audio may need manual sync.');
  let rate=1,delay=anchors[0].delay;
  if(anchors.length===2&&anchors[1].start-anchors[0].start>60){
    const a=anchors[0],b=anchors[1];rate=1-(b.delay-a.delay)/(b.start-a.start);
    if(rate<.94||rate>1.06)throw new Error('The recordings differ too much for reliable automatic sync. Use manual sync.');
    delay=a.start-(a.start-a.delay)/rate;
  }
  return {rate:Math.round(rate*100000)/100000,delay:Math.round(delay*100)/100};
}
