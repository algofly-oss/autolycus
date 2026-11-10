export function privateAddress(value=''){
 const v=value.replace(/^\[|\]$/g,'').toLowerCase();
 if(v==='::1'||v.startsWith('fc')||v.startsWith('fd')||v.startsWith('fe80:'))return v.includes(':');
 const parts=v.split('.').map(Number);if(parts.length!==4||parts.some(p=>!Number.isInteger(p)||p<0||p>255))return false;
 return parts[0]===10||parts[0]===127||(parts[0]===192&&parts[1]===168)||(parts[0]===172&&parts[1]>=16&&parts[1]<=31)||(parts[0]===169&&parts[1]===254);
}
export function mediaConnection(stats,direct,hostname,bytes={}){
 if(!direct)return {kind:privateAddress(hostname)?'local':'proxy',label:privateAddress(hostname)?'Local network':'Public proxy',bytes};
 const transport=stats.find(s=>s.type==='transport'&&s.selectedCandidatePairId);
 const pair=stats.find(s=>s.id===transport?.selectedCandidatePairId)||stats.find(s=>s.type==='candidate-pair'&&s.state==='succeeded'&&(s.nominated||s.selected));
 const remote=stats.find(s=>s.id===pair?.remoteCandidateId);
 const local=privateAddress(remote?.address||remote?.ip||'');
 return {kind:local?'local':'direct',label:local?'Local network':'Direct connection',bytes};
}
