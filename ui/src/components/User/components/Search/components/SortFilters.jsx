import { FiArrowUp, FiArrowDown, FiX } from "react-icons/fi";
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
}) => (
  <div>
    <div className="flex flex-col md:flex-row md:space-x-2 gap-2 md:gap-0">
      <div className="flex w-full flex-nowrap gap-2 md:w-max md:flex-wrap">
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
      </div>

      {/* Separator only on desktop */}
      <div className="hidden md:block border-l my-0.5 dark:border-neutral-800" />

      {/* On mobile: Title filter sits below sort row */}
      <div className="relative flex w-full min-w-0 rounded-full overflow-hidden h-7 md:max-h-10 md:hidden">
        <input
          value={titleFilter}
          onChange={(e) => setTitleFilter(e.target.value)}
          placeholder="Filter results by title"
          className="w-full min-w-0 px-3 pr-7 text-[11px] bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 rounded-full outline-none"
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

      {/* On desktop: Title filter in separate bubble after separator */}
      <div className="hidden md:relative md:flex md:w-max md:rounded-full md:overflow-hidden md:h-7 md:max-h-10">
        <input
          value={titleFilter}
          onChange={(e) => setTitleFilter(e.target.value)}
          placeholder="Filter results by title"
          className="w-full px-3 pr-7 text-[11px] bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 rounded-full outline-none"
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

    <div
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
    </div>
  </div>
);

export default SortFilters;
