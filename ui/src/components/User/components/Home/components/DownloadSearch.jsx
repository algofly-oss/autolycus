import { useEffect, useState } from "react";
import { FiGrid, FiList, FiX } from "react-icons/fi";

const TYPE_OPTIONS = [
  { value: "torrent", label: "Torrents" },
  { value: "folder", label: "Folders" },
  { value: "file", label: "Files" },
  { value: "all", label: "All items" },
];

const EXTENSION_OPTIONS = [
  { value: "", label: "Any ext" },
  { value: "mp4", label: "MP4" },
  { value: "mkv", label: "MKV" },
  { value: "avi", label: "AVI" },
  { value: "mp3", label: "MP3" },
  { value: "zip", label: "ZIP" },
  { value: "srt", label: "SRT" },
  { value: "txt", label: "TXT" },
  { value: "pdf", label: "PDF" },
];

const SORT_OPTIONS = [
  { value: "modified:desc", label: "Newest" },
  { value: "modified:asc", label: "Oldest" },
  { value: "name:asc", label: "Name A-Z" },
  { value: "name:desc", label: "Name Z-A" },
  { value: "size:desc", label: "Largest" },
  { value: "size:asc", label: "Smallest" },
];

const controlClass =
  "h-12 rounded-lg border-0 bg-zinc-100 px-3 text-xs text-neutral-800 outline-none ring-0 focus:outline-none focus:ring-0 dark:bg-black dark:text-neutral-100 dark:[color-scheme:dark]";

export default function DownloadSearch({
  viewMode,
  setViewMode,
  showViewToggle = true,
  onSearchChange,
}) {
  const [query, setQuery] = useState("");
  const [type, setType] = useState("torrent");
  const [extension, setExtension] = useState("");
  const [sort, setSort] = useState("modified:desc");

  const hasSearch = Boolean(query.trim() || type !== "torrent" || extension);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      onSearchChange?.({
        active: hasSearch,
        query: query.trim(),
        itemType: type,
        extension,
        sort,
      });
    }, 250);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [query, type, extension, sort, hasSearch, onSearchChange]);

  const clearSearch = () => {
    setQuery("");
    setType("torrent");
    setExtension("");
    setSort("modified:desc");
  };

  return (
    <div className="no-scrollbar mt-2 flex min-w-0 flex-wrap items-center gap-2 md:flex-nowrap md:overflow-x-auto">
      <div className="relative w-full min-w-[7.5rem] basis-full md:flex-1 md:basis-[10rem] md:min-w-[10rem] lg:basis-[14rem]">
        <input
          type="text"
          value={query}
          placeholder="Search Files by Metadata"
          className={`${controlClass} w-full pr-9 md:text-sm`}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") clearSearch();
          }}
        />
        {hasSearch ? (
          <button
            type="button"
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-neutral-500 hover:bg-neutral-200 dark:hover:bg-neutral-900"
            onClick={clearSearch}
            aria-label="Clear download search"
          >
            <FiX size={15} />
          </button>
        ) : null}
      </div>

      <select
        className={`${controlClass} min-w-0 flex-1 basis-[5.5rem] sm:w-[9rem] sm:flex-none`}
        value={type}
        onChange={(event) => setType(event.target.value)}
      >
        {TYPE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      <select
        className={`${controlClass} min-w-0 flex-1 basis-[4.75rem] sm:w-[7rem] sm:flex-none`}
        value={extension}
        onChange={(event) => setExtension(event.target.value)}
      >
        {EXTENSION_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      <select
        className={`${controlClass} min-w-0 flex-1 basis-[5rem] sm:w-[7.5rem] sm:flex-none`}
        value={sort}
        onChange={(event) => setSort(event.target.value)}
      >
        {SORT_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      {showViewToggle ? (
        <div className="ml-0 flex h-12 shrink-0 items-center gap-1 rounded-lg bg-zinc-100 p-1 sm:ml-auto dark:bg-black">
          <button
            type="button"
            className={`flex h-10 w-10 items-center justify-center rounded-md transition ${
              viewMode === "list"
                ? "bg-blue-600 text-white"
                : "text-neutral-600 hover:bg-neutral-200 dark:text-neutral-300 dark:hover:bg-neutral-900"
            }`}
            onClick={() => setViewMode("list")}
            title="List view"
            aria-label="List view"
          >
            <FiList size={17} />
          </button>
          <button
            type="button"
            className={`flex h-10 w-10 items-center justify-center rounded-md transition ${
              viewMode === "grid"
                ? "bg-blue-600 text-white"
                : "text-neutral-600 hover:bg-neutral-200 dark:text-neutral-300 dark:hover:bg-neutral-900"
            }`}
            onClick={() => setViewMode("grid")}
            title="Thumbnail view"
            aria-label="Thumbnail view"
          >
            <FiGrid size={17} />
          </button>
        </div>
      ) : null}
    </div>
  );
}
