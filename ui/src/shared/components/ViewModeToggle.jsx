import { FiGrid, FiList } from "react-icons/fi";

export default function ViewModeToggle({ viewMode, onChange, saving = false, label = "View", className = "" }) {
  return (
    <div role="group" aria-label={label} aria-busy={saving}
      className={`flex h-12 shrink-0 items-center gap-1 rounded-lg bg-zinc-100 p-1 dark:bg-black ${className}`}>
      {[["list", "List view", FiList], ["grid", "Thumbnail view", FiGrid]].map(([mode, title, Icon]) => (
        <button key={mode} type="button" title={title} aria-label={title} aria-pressed={viewMode === mode}
          disabled={saving} onClick={() => onChange(mode)}
          className={`flex h-10 w-10 items-center justify-center rounded-md transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500 ${viewMode === mode ? "bg-blue-600 text-white" : "text-neutral-600 hover:bg-neutral-200 dark:text-neutral-300 dark:hover:bg-neutral-900"}`}>
          <Icon size={17} />
        </button>
      ))}
    </div>
  );
}
