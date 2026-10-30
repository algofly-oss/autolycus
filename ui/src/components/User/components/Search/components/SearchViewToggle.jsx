import { FiGrid, FiList } from "react-icons/fi";

export default function SearchViewToggle({ viewMode, onChange, saving }) {
  return (
    <div role="group" aria-label="Search result view" aria-busy={saving} className="flex shrink-0 items-center gap-0.5">
      {[["list", "List view", FiList], ["grid", "Thumbnail view", FiGrid]].map(([mode, title, Icon]) => (
        <button key={mode} type="button" title={title} aria-label={title} aria-pressed={viewMode === mode}
          disabled={saving} onClick={() => onChange(mode)}
          className={`flex h-11 w-11 items-center justify-center rounded-lg transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-zinc-400 md:h-7 md:w-7 md:rounded-full ${viewMode === mode ? "bg-zinc-200 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100" : "text-zinc-500 hover:bg-zinc-100 dark:text-zinc-500 dark:hover:bg-zinc-800/50"}`}>
          <Icon size={15} />
        </button>
      ))}
    </div>
  );
}
