import { useRef, useState, useMemo, useEffect, use } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import Fuse from "fuse.js";
import {
  FiSearch,
  FiX,
  FiArrowUp,
  FiArrowDown,
  FiClipboard,
  FiDownload,
} from "react-icons/fi";
import apiRoutes from "@/shared/routes/apiRoutes";
import useToast from "@/shared/hooks/useToast";
import axios from "axios";

const formatBytes = (bytes) => {
  if (!bytes || isNaN(bytes)) return "—";
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let value = Number(bytes);
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[i]}`;
};

const formatDate = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

const formatCount = (num) => {
  if (!num || isNaN(num)) return "0";
  if (num < 1000) return String(num);

  const units = ["k", "M", "B"];
  let value = num;
  let i = -1;

  while (value >= 1000 && i < units.length - 1) {
    value /= 1000;
    i++;
  }

  return `${value >= 10 ? Math.round(value) : value.toFixed(1)}${units[i]}`;
};

const SORT_KEYS = {
  name: "name",
  seeds: "seeds",
  size: "size",
  date: "date",
};

const DEFAULT_SORT_DIR = {
  [SORT_KEYS.name]: "asc",
  [SORT_KEYS.date]: "desc",
  [SORT_KEYS.seeds]: "desc",
  [SORT_KEYS.size]: "desc",
};

const sortResults = (data, { key = SORT_KEYS.name, dir = "asc" } = {}) => {
  const factor = dir === "asc" ? 1 : -1;

  return [...data].sort((a, b) => {
    switch (key) {
      case SORT_KEYS.name:
        return factor * (a.Title || "").localeCompare(b.Title || "");
      case SORT_KEYS.seeds:
        return factor * ((a.Seeders ?? 0) - (b.Seeders ?? 0));
      case SORT_KEYS.size:
        return factor * ((a.Size ?? 0) - (b.Size ?? 0));
      case SORT_KEYS.date: {
        const aTime = a.PublishDate ? Date.parse(a.PublishDate) : 0;
        const bTime = b.PublishDate ? Date.parse(b.PublishDate) : 0;
        return factor * (aTime - bTime);
      }
      default:
        return 0;
    }
  });
};

function VirtualizedResults({ items, onCopy, onDownload, filtersRef }) {
  const parentRef = useRef(null);

  const rowVirtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80,
    overscan: 6,
  });

  const updateOffset = () => {
    if (!filtersRef.current) return;

    const rect = filtersRef.current.getBoundingClientRect();
    const distancePx = rect.bottom;

    const rootFontSize = parseFloat(
      getComputedStyle(document.documentElement).fontSize
    );

    const distanceRem = distancePx / rootFontSize;

    document.documentElement.style.setProperty(
      "--results-offset",
      `${distanceRem + 2.5}rem`
    );
  };

  useEffect(() => {
    if (!filtersRef.current) return;

    updateOffset();

    const ro = new ResizeObserver(updateOffset);
    ro.observe(filtersRef.current);

    return () => ro.disconnect();
  }, []);

  return (
    <div
      ref={parentRef}
      className={`h-[calc(100vh-var(--results-offset))] overflow-auto light-scrolbar dark:dark-scrollbar pr-1 rounded-lg`}
    >
      <ul
        className="relative w-full"
        style={{ height: rowVirtualizer.getTotalSize() }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const item = items[virtualRow.index];

          return (
            <li
              key={virtualRow.key}
              className="absolute left-0 w-full p-4 rounded-md
                         bg-neutral-50 dark:bg-black
                         hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
              style={{
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <p className="font-semibold leading-snug">{item.Title}</p>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => onCopy(item)}
                    className="p-1.5 rounded-md bg-zinc-200 hover:bg-zinc-300
                             dark:bg-zinc-900 dark:hover:bg-zinc-700 transition"
                    title="Copy magnet link"
                  >
                    <FiClipboard size={14} />
                  </button>

                  <button
                    onClick={() => onDownload(item)}
                    className="p-1.5 rounded-md bg-blue-500 text-white
                             hover:bg-blue-600 transition"
                    title="Download"
                  >
                    <FiDownload size={14} />
                  </button>
                </div>
              </div>

              <div className="text-xs text-zinc-500 flex gap-4 flex-wrap mt-1">
                {item?.Seeders !== undefined && <span>🌱 {item.Seeders}</span>}
                {item?.Size && <span>📦 {formatBytes(item.Size)}</span>}
                {item?.PublishDate && (
                  <span>📅 {formatDate(item.PublishDate)}</span>
                )}
                {item?.Tracker && (
                  <a
                    href={item.Details}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-blue-500 transition"
                  >
                    🔎 {item.Tracker}
                  </a>
                )}
                {item?.Details && (
                  <a
                    href={`https://www.imdb.com/find/?q=${item.Title?.slice(
                      0,
                      20
                    )}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-blue-500 transition"
                  >
                    🌐 IMDB
                  </a>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const Search = ({ torrentSearchState }) => {
  const [firstLoadFinished, setFirstLoadFinished] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const [sort, setSort] = useState({
    key: SORT_KEYS.name,
    dir: "asc",
  });

  const [activeSource, setActiveSource] = useState("All");
  const [titleFilter, setTitleFilter] = useState("");
  const abortRef = useRef(null);
  const filtersRef = useRef(null);
  const toast = useToast();

  useEffect(() => {
    let searchResults = torrentSearchState.get("results") || [];
    if (!query && !results?.length) {
      setQuery(torrentSearchState.get("query"));
      setTitleFilter(torrentSearchState.get("titleFilter"));
      setSort(torrentSearchState.get("sort"));
      setActiveSource(torrentSearchState.get("activeSource"));
      setResults(searchResults);
    }
    setFirstLoadFinished(true);
  }, []);

  useEffect(() => {
    if (firstLoadFinished) {
      torrentSearchState.set({
        query: query,
      });
    }
  }, [query]);

  useEffect(() => {
    if (firstLoadFinished) {
      torrentSearchState.set({
        titleFilter: titleFilter,
      });
    }
  }, [titleFilter]);

  useEffect(() => {
    if (firstLoadFinished) {
      torrentSearchState.set({
        results: results,
      });
    }
  }, [results]);

  useEffect(() => {
    if (firstLoadFinished) {
      torrentSearchState.set({
        activeSource: activeSource,
        sort: sort,
      });
    }
  }, [activeSource, sort]);

  const extractMagnet = (item) => {
    let toastPrefix = "Magnet";
    let magnet = item?.MagnetUri;
    if (!magnet && item?.InfoHash) {
      magnet = `magnet:?xt=urn:btih:${
        item?.InfoHash || ""
      }&tr=udp%3A%2F%2Ftracker.coppersurfer.tk%3A6969%2Fannounce&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A6969%2Fannounce&tr=udp%3A%2F%2F9.rarbg.to%3A2710%2Fannounce&tr=udp%3A%2F%2F9.rarbg.me%3A2780%2Fannounce&tr=udp%3A%2F%2F9.rarbg.to%3A2730%2Fannounce&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337&tr=http%3A%2F%2Fp4p.arenabg.com%3A1337%2Fannounce&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce&tr=udp%3A%2F%2Ftracker.tiny-vps.com%3A6969%2Fannounce&tr=udp%3A%2F%2Fopen.stealth.si%3A80%2Fannounce`;
      toastPrefix = "InfoHash";
    }
    if (!magnet && item?.Details) {
      magnet = item?.Details; // Website URL
      toastPrefix = "URL";
    }

    return { magnet, toastPrefix };
  };

  const handleCopyMagnet = (item) => {
    console.log(item);
    let { magnet, toastPrefix } = extractMagnet(item);

    if (magnet) {
      const el = document.createElement("textarea");
      el.value = magnet;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      toast.success(`${toastPrefix} copied to clipboard`);
    } else {
      toast.error(`Magnet not Found`);
    }
  };

  const handleDownload = async (item) => {
    let { magnet, toastPrefix } = extractMagnet(item);
    if (magnet && toastPrefix !== "URL") {
      try {
        await axios.post(apiRoutes.addMagnet, { magnet: magnet });
        toast.success(`Added to Download Queue`);
      } catch (err) {
        console.error("Add magnet error:", err);
        toast.error("Failed to add torrent");
      }
    } else {
      toast.error(`Magnet not Found`);
    }
  };

  const sourceCounts = useMemo(() => {
    const map = {};
    results.forEach((r) => {
      if (!r.Tracker) return;
      map[r.Tracker] = (map[r.Tracker] || 0) + 1;
    });
    return map;
  }, [results]);

  const sources = useMemo(() => {
    const sorted = Object.entries(sourceCounts)
      .sort((a, b) => b[1] - a[1])
      .map(([tracker]) => tracker);

    return ["All", ...sorted];
  }, [sourceCounts]);

  const fuse = useMemo(() => {
    return new Fuse(results, {
      keys: [
        { name: "Title", weight: 1 },
        { name: "Tracker", weight: 0.2 },
      ],
      threshold: 0.35, // lower = stricter
      ignoreLocation: true,
      minMatchCharLength: 2,
      useExtendedSearch: true,
    });
  }, [results]);

  const visibleResults = useMemo(() => {
    let data =
      activeSource === "All"
        ? results
        : results.filter((r) => r.Tracker === activeSource);

    if (!titleFilter?.trim()) return data;

    const res = fuse.search(titleFilter);

    return res
      .map((r) => r.item)
      .filter((r) =>
        activeSource === "All" ? true : r.Tracker === activeSource
      );
  }, [results, activeSource, titleFilter, fuse]);

  const handleSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed) return;

    setHasSearched(true);

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setResults([]);
    setSort({
      key: SORT_KEYS.name,
      dir: "asc",
    });
    setActiveSource("All");
    setLoading(true);

    try {
      const res = await fetch(
        `${apiRoutes.searchTorrent}?query=${encodeURIComponent(trimmed)}`,
        {
          method: "POST",
          credentials: "include",
          signal: controller.signal,
        }
      );

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;
          const item = JSON.parse(line);

          setResults((prev) => sortResults([...prev, item], sort));
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
  };

  const handleSortChange = (key) => {
    setSort((prev) => {
      const dir =
        prev.key === key
          ? prev.dir === "asc"
            ? "desc"
            : "asc"
          : DEFAULT_SORT_DIR[key] ?? "asc";

      setResults((r) => sortResults(r, { key, dir }));
      return { key, dir };
    });
  };

  const SortButton = ({ label, value }) => {
    const active = sort.key === value;
    const Icon = sort.dir === "asc" ? FiArrowUp : FiArrowDown;

    return (
      <button
        onClick={() => handleSortChange(value)}
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

  return (
    <div className="flex justify-center">
      <div className="mt-4 pb-16 md:pb-6 relative overflow-y-auto overflow-x-hidden 2xl:w-[82rem] w-full p-4 space-y-4">
        {/* Search Bar */}
        <div className="flex w-full h-[3.2rem] rounded-lg overflow-hidden">
          <div className="relative flex-1">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              // disabled={loading}
              placeholder="Search torrent here"
              className="w-full h-full px-4 pr-10 text-sm bg-zinc-100 dark:bg-black text-zinc-900 dark:text-zinc-100 outline-none"
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                aria-label="Clear search"
              >
                <FiX size={16} />
              </button>
            )}
          </div>
          <button
            onClick={loading ? handleCancel : handleSearch}
            className={`w-12 flex items-center justify-center text-white ${
              loading
                ? "bg-red-600 dark:bg-red-700"
                : "bg-blue-600 dark:bg-blue-700"
            }`}
          >
            {loading ? (
              <div className="relative w-5 h-5 flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border-2 border-white/40 border-t-white animate-spin" />
                <FiX className="relative z-10" />
              </div>
            ) : (
              <FiSearch />
            )}
          </button>
        </div>

        {/* Sort + Source Filters */}
        {results.length > 0 && (
          <div ref={filtersRef}>
            <div className="flex space-x-2">
              <div className="flex flex-wrap gap-2 w-max">
                <SortButton label="Name" value={SORT_KEYS.name} />
                <SortButton label="Seeds" value={SORT_KEYS.seeds} />
                <SortButton label="Size" value={SORT_KEYS.size} />
                <SortButton label="Upload Date" value={SORT_KEYS.date} />
              </div>

              <div className="border-l my-0.5 dark:border-neutral-800" />

              <div className="flex w-max rounded-full overflow-hidden">
                <input
                  value={titleFilter}
                  onChange={(e) => setTitleFilter(e.target.value)}
                  placeholder="Filter results by title"
                  className="w-full px-3 text-xs bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 rounded-full outline-none"
                />
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mt-2">
              {sources.map((src) => {
                const count =
                  src === "All" ? results.length : sourceCounts[src] ?? 0;

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
        )}

        {/* Loader */}
        {loading && results.length === 0 && (
          <div className="py-10 flex justify-center">
            <div className="h-6 w-6 rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-white animate-spin" />
          </div>
        )}

        {/* Results */}
        {visibleResults.length > 0 && (
          <VirtualizedResults
            items={visibleResults}
            onCopy={handleCopyMagnet}
            onDownload={handleDownload}
            filtersRef={filtersRef}
          />
        )}

        {/* No Results */}
        {hasSearched && !loading && results.length === 0 && (
          <p className="py-10 text-center text-sm text-zinc-500">
            No results found
          </p>
        )}

        {!hasSearched && !loading && firstLoadFinished && (
          <div className="flex flex-col items-center justify-center py-12 sm:py-16 text-gray-500 dark:text-gray-400">
            <FiSearch className="w-10 h-10 sm:w-12 sm:h-12 mb-4" />
            <h3 className="text-base sm:text-lg font-semibold mb-2">
              Search for Torrents
            </h3>
            <p className="text-sm sm:text-base text-center max-w-sm">
              Enter your search term above to find torrents
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Search;
