export const QUALITY_OPTIONS = ["auto", "original", "2160p", "1440p", "1080p", "720p", "480p", "360p", "240p", "144p"];
export const qualityLabel = value => value === "auto" ? "Auto" : value === "original" ? "Original" : value === "2160p" ? "2160p · 4K" : value;

// Conservative file-based adaptation; every switch replaces the source at the
// current position. No transcoding, segment generation or speculative downloads.
export function adaptiveQuality({ versions, active, buffer, stalledFor, stableFor, sinceSwitch, throughput, duration, lowBufferFor=0 }) {
  const ladder = [...versions].sort((a,b) => a.quality === "original" ? -1 : b.quality === "original" ? 1 : b.height-a.height);
  const index = ladder.findIndex(item => item.quality === active);
  if (index < 0 || sinceSwitch < 30) return null;
  const currentBitrate=duration>0 ? ladder[index].size/duration : 0;
  const underfed=buffer<4 && lowBufferFor>=6 && throughput>0 && currentBitrate>0 && throughput<currentBitrate*.9;
  if (((buffer < 3 && stalledFor >= 2) || underfed) && index < ladder.length-1) return ladder[index+1].quality;
  if (index > 0 && buffer >= 12 && stableFor >= 45 && sinceSwitch >= 60) {
    const higher = ladder[index-1];
    const needed = duration > 0 ? higher.size/duration : Infinity;
    if (throughput > needed*1.8) return higher.quality;
  }
  return null;
}
