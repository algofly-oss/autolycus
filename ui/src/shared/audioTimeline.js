// Positive delay means the alternate soundtrack starts later in the main video.
export const donorTime = (videoTime, delay=0, rate=1) => Math.max(0,(videoTime-delay)*rate);
export const videoTime = (audioTime, delay=0, rate=1) => audioTime/rate+delay;

// Correlate bounded, low-rate energy fingerprints. Reject silence, ambiguous
// repetitions and unrelated recordings instead of inventing a sync offset.
export function alignEnvelopes(reference, donor, {frequency=20,maxOffset=20}={}) {
  const limit=Math.round(maxOffset*frequency),scores=[];
  for(let lag=-limit;lag<=limit;lag++) {
    const begin=Math.max(0,-lag),end=Math.min(reference.length,donor.length-lag);
    if(end-begin<frequency*4)continue;
    let a=0,b=0,aa=0,bb=0,ab=0;
    for(let i=begin;i<end;i++){const x=reference[i],y=donor[i+lag];a+=x;b+=y;aa+=x*x;bb+=y*y;ab+=x*y;}
    const n=end-begin,variance=(aa-a*a/n)*(bb-b*b/n);
    if(variance<=1e-10)continue;
    scores.push({lag,score:(ab-a*b/n)/Math.sqrt(variance)});
  }
  scores.sort((a,b)=>b.score-a.score);
  const best=scores[0],rival=best&&scores.find(row=>Math.abs(row.lag-best.lag)>frequency);
  if(!best || best.score<.72 || (rival && best.score-rival.score<.08))return null;
  return {delay:-best.lag/frequency,confidence:best.score};
}
