import { FiArrowUp, FiArrowDown, FiX } from "react-icons/fi";
import { formatCount, SORT_KEYS } from "../utils";

const SortButton = ({ label, value, sort, onSortChange }) => {
  const active = sort.key === value;
  const Icon = sort.dir === "asc" ? FiArrowUp : FiArrowDown;

  return (
    <button
      onClick={() => onSortChange(value)}
      className={`flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium transition
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
}) => (
  <div>
    <div className="flex space-x-2">
      <div className="flex flex-wrap gap-2 w-max">
        <SortButton label="Name" value={SORT_KEYS.name} sort={sort} onSortChange={onSortChange} />
        <SortButton label="Seeds" value={SORT_KEYS.seeds} sort={sort} onSortChange={onSortChange} />
        <SortButton label="Size" value={SORT_KEYS.size} sort={sort} onSortChange={onSortChange} />
        <SortButton label="Upload Date" value={SORT_KEYS.date} sort={sort} onSortChange={onSortChange} />
      </div>

      <div className="border-l my-0.5 dark:border-neutral-800" />

      <div className="relative flex w-max rounded-full overflow-hidden">
        <input
          value={titleFilter}
          onChange={(e) => setTitleFilter(e.target.value)}
          placeholder="Filter results by title"
          className="w-full px-3 pr-7 text-xs bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 rounded-full outline-none"
        />
        {titleFilter ? (
          <button
            type="button"
            onClick={() => setTitleFilter("")}
            aria-label="Clear title filter"
            className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
          >
            <FiX size={12} />
          </button>
        ) : null}
      </div>
    </div>

    <div className={`flex flex-wrap gap-2 mt-2 ${reorderPulse ? "bubble-reorder" : ""}`}>
      {sources.map((src) => {
        const count = src === "All" ? resultsCount : sourceCounts[src] ?? 0;

        return (
          <button
            key={src}
            onClick={() => setActiveSource(src)}
            className={`flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium transition
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
    </div>
  </div>
);

export default SortFilters;
