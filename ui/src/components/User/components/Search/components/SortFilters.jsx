import { FiArrowUp, FiArrowDown, FiX } from "react-icons/fi";
import SearchViewToggle from "./SearchViewToggle";
import { formatCount, SORT_KEYS } from "../utils";

const SortButton = ({ label, value, sort, onSortChange, className = "" }) => {
  const active = sort.key === value;
  const Icon = sort.dir === "asc" ? FiArrowUp : FiArrowDown;

  return (
    <button
      onClick={() => onSortChange(value)}
      className={`flex items-center gap-1 px-3 h-7 rounded-full text-[11px] font-medium whitespace-nowrap transition ${className}
        ${
          active
            ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-black"
            : "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
        }
      `}
    >
      {label}
      {active && <Icon size={12} />}
    </button>
  );
};

const SortFilters = ({
  sort,
  onSortChange,
  titleFilter,
  setTitleFilter,
  sources,
  activeSource,
  setActiveSource,
  sourceCounts,
  resultsCount,
  reorderPulse,
  viewMode,
  onViewModeChange,
  savingView,
}) => (
  <div>
    <div className="flex flex-col md:flex-row md:space-x-2 gap-2 md:gap-0">
      {resultsCount > 0 && <div className="flex w-full flex-nowrap gap-2 md:w-max md:flex-wrap">
        <SortButton
          label="Name"
          value={SORT_KEYS.name}
          sort={sort}
          onSortChange={onSortChange}
          className="flex-1 min-w-0 justify-center md:flex-none"
        />
        <SortButton
          label="Seeds"
          value={SORT_KEYS.seeds}
          sort={sort}
          onSortChange={onSortChange}
          className="flex-1 min-w-0 justify-center md:flex-none"
        />
        <SortButton
          label="Size"
          value={SORT_KEYS.size}
          sort={sort}
          onSortChange={onSortChange}
          className="flex-1 min-w-0 justify-center md:flex-none"
        />
        <SortButton
          label="Upload Date"
          value={SORT_KEYS.date}
          sort={sort}
          onSortChange={onSortChange}
          className="flex-1 min-w-0 justify-center md:flex-none"
        />
      </div>}

      {resultsCount > 0 && <div className="hidden md:block border-l my-0.5 dark:border-neutral-800" />}

      <div className="flex min-w-0 items-center gap-2">
        <div className="relative flex h-11 min-w-0 flex-1 overflow-hidden rounded-lg md:h-7 md:w-48 md:flex-none md:rounded-full">
          <input value={titleFilter} onChange={(event) => setTitleFilter(event.target.value)}
            placeholder="Filter results by title" aria-label="Filter results by title"
            className="w-full min-w-0 bg-zinc-200 px-3 pr-7 text-[11px] text-zinc-700 outline-none dark:bg-zinc-800 dark:text-zinc-300" />
          {titleFilter ? <button type="button" onClick={() => setTitleFilter("")} aria-label="Clear title filter"
            className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"><FiX size={12} /></button> : null}
        </div>
        <span role="separator" aria-orientation="vertical" className="h-5 shrink-0 border-l dark:border-neutral-800" />
        <SearchViewToggle viewMode={viewMode} onChange={onViewModeChange} saving={savingView} />
      </div>
    </div>

    {resultsCount > 0 && <div
      className={`mt-2 flex gap-2 overflow-x-auto no-scrollbar pb-1 md:flex-wrap md:overflow-visible ${
        reorderPulse ? "bubble-reorder" : ""
      }`}
    >
      {sources.map((src) => {
        const count = src === "All" ? resultsCount : sourceCounts[src] ?? 0;

        return (
          <button
            key={src}
            onClick={() => setActiveSource(src)}
            className={`flex items-center gap-1 px-3 h-7 rounded-full text-[11px] font-medium whitespace-nowrap transition flex-shrink-0 md:flex-shrink
              ${
                activeSource === src
                  ? "bg-blue-600 text-white"
                  : "bg-zinc-200 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300"
              }
            `}
          >
            <span>{src}</span>
            <span className="opacity-70">({formatCount(count)})</span>
          </button>
        );
      })}
    </div>}
  </div>
);

export default SortFilters;
