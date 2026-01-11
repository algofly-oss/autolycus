import { useRef, useState, useMemo } from "react";
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

const sortResults = (data, { key, dir }) => {
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

const Search = () => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const [sort, setSort] = useState({
    key: SORT_KEYS.name,
    dir: "asc",
  });

  const [activeSource, setActiveSource] = useState("All");
  const abortRef = useRef(null);
  const toast = useToast();

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

  const visibleResults = useMemo(() => {
    if (activeSource === "All") return results;
    return results.filter((r) => r.Tracker === activeSource);
  }, [results, activeSource]);

  const handleSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setResults([]);
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
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      {/* Search Bar */}
      <div className="flex w-full h-12 rounded-lg overflow-hidden">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          disabled={loading}
          placeholder="Search torrent here"
          className="flex-1 px-4 text-sm bg-zinc-100 dark:bg-black text-zinc-900 dark:text-zinc-100 outline-none"
        />
        <button
          onClick={loading ? handleCancel : handleSearch}
          className={`w-12 flex items-center justify-center text-white ${
            loading ? "bg-red-500" : "bg-blue-500"
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
        <>
          <div className="flex flex-wrap gap-2">
            <SortButton label="Name" value={SORT_KEYS.name} />
            <SortButton label="Seeds" value={SORT_KEYS.seeds} />
            <SortButton label="Size" value={SORT_KEYS.size} />
            <SortButton label="Upload Date" value={SORT_KEYS.date} />
          </div>

          <div className="flex flex-wrap gap-2">
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
        </>
      )}

      {/* Loader */}
      {loading && results.length === 0 && (
        <div className="py-10 flex justify-center">
          <div className="h-6 w-6 rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-white animate-spin" />
        </div>
      )}

      {/* Results */}
      {visibleResults.length > 0 && (
        <ul className="space-y-1">
          {visibleResults.map((item, i) => (
            <li
              key={i}
              className="p-4 rounded-md bg-white dark:bg-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="font-semibold leading-snug">{item.Title}</p>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleCopyMagnet(item)}
                    className="p-1.5 rounded-md bg-zinc-200 hover:bg-zinc-300
                               dark:bg-zinc-800 dark:hover:bg-zinc-700 transition"
                    title="Copy magnet link"
                  >
                    <FiClipboard size={14} />
                  </button>

                  <button
                    onClick={() => handleDownload(item)}
                    className="p-1.5 rounded-md bg-blue-500 text-white
                               hover:bg-blue-600 transition"
                    title="Download"
                  >
                    <FiDownload size={14} />
                  </button>
                </div>
              </div>

              <div className="text-xs text-zinc-500 flex gap-4 flex-wrap mt-1">
                {item.Seeders !== undefined && <span>🌱 {item.Seeders}</span>}
                {item.Size && <span>📦 {formatBytes(item.Size)}</span>}
                {item.PublishDate && (
                  <span>📅 {formatDate(item.PublishDate)}</span>
                )}
                {item.Tracker && <span>🔎 {item.Tracker}</span>}
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* No Results */}
      {!loading && results.length === 0 && (
        <p className="py-10 text-center text-sm text-zinc-500">
          No results found
        </p>
      )}
    </div>
  );
};

export default Search;
