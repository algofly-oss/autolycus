export default function WatchProgressBar({ progress }) {
  if (!progress || !(progress.duration > 0) || progress.position <= 0) return null;
  const percent = progress.completed ? 100 : Math.min(100,progress.position/progress.duration*100);
  return <div className="watch-progress-bar" role="progressbar" aria-label="Watched" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(percent)} title={progress.aggregate?`${Math.round(percent)}% watched · ${progress.watched_count} of ${progress.files_count} videos completed`:`${Math.round(percent)}% watched`}>
    <div style={{width:`${percent}%`}} />
  </div>;
}
