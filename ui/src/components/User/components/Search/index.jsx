import { useRef, useState, useMemo, useEffect } from "react";
import Fuse from "fuse.js";
import { FiSearch } from "react-icons/fi";
import apiRoutes from "@/shared/routes/apiRoutes";
import useToast from "@/shared/hooks/useToast";
import axios from "axios";
import SearchBar from "./components/SearchBar";
import SortFilters from "./components/SortFilters";
import TorrentResults from "./components/TorrentResults";
import {
  DEFAULT_SORT_DIR,
  INITIAL_SORT,
  MOBILE_BREAKPOINT,
  SORT_KEYS,
  sortResults,
} from "./utils";

const useIsMobileWidth = () => {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.innerWidth <= MOBILE_BREAKPOINT;
  });

  useEffect(() => {
    const checkWidth = () => {
      setIsMobile(window.innerWidth <= MOBILE_BREAKPOINT);
    };
    checkWidth();
    window.addEventListener("resize", checkWidth);
    return () => window.removeEventListener("resize", checkWidth);
  }, []);

  return isMobile;
};

const useResultsOffset = (filtersRef, watchKey) => {
  useEffect(() => {
    if (typeof document === "undefined") return;
    const element = filtersRef.current;
    if (!element) return;

    const updateOffset = () => {
      const rect = element.getBoundingClientRect();
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

    updateOffset();

    const ro = new ResizeObserver(updateOffset);
    ro.observe(element);

    return () => ro.disconnect();
  }, [filtersRef, watchKey]);
};

const Search = ({ torrentSearchState }) => {
  const [firstLoadFinished, setFirstLoadFinished] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [sourceOrder, setSourceOrder] = useState([]);
  const [reorderPulse, setReorderPulse] = useState(false);
  const [scrollOffset, setScrollOffset] = useState(0);
  const [scrollResetKey, setScrollResetKey] = useState(0);

  const [sort, setSortState] = useState(INITIAL_SORT);
  const sortRef = useRef(INITIAL_SORT);
  const prevLoadingRef = useRef(false);

  const updateSort = (nextSort) => {
    sortRef.current = nextSort;
    setSortState(nextSort);
  };

  const [activeSource, setActiveSource] = useState("All");
  const [titleFilter, setTitleFilter] = useState("");
  const resultsKey = `${activeSource}-${sort.key}-${sort.dir}-${titleFilter}`;
  const abortRef = useRef(null);
  const filtersRef = useRef(null);
  const searchSessionRef = useRef(0);
  const skipFilterResetRef = useRef(true);
  const toast = useToast();
  const isMobile = useIsMobileWidth();

  useEffect(() => {
    let searchResults = torrentSearchState.get("results") || [];
    if (!query && !results?.length) {
      setQuery(torrentSearchState.get("query"));
      setTitleFilter(torrentSearchState.get("titleFilter"));
      const savedSort = torrentSearchState.get("sort");
      const sortValue =
        savedSort?.key && savedSort?.dir ? savedSort : INITIAL_SORT;
      sortRef.current = sortValue;
      setSortState(sortValue);
      setActiveSource(torrentSearchState.get("activeSource"));
      setResults(searchResults);
      const savedScrollOffset = torrentSearchState.get("scrollOffset");
      if (Number.isFinite(savedScrollOffset)) {
        setScrollOffset(savedScrollOffset);
      }
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
    if (!firstLoadFinished) return;
    if (skipFilterResetRef.current) {
      skipFilterResetRef.current = false;
      return;
    }
    setScrollOffset(0);
    setScrollResetKey((k) => k + 1);
  }, [activeSource, titleFilter, firstLoadFinished]);

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
        scrollOffset: scrollOffset,
      });
    }
  }, [scrollOffset]);

  useEffect(() => {
    if (firstLoadFinished) {
      torrentSearchState.set({
        activeSource: activeSource,
        sort: sort,
      });
    }
  }, [activeSource, sort]);

  useEffect(() => {
    const wasLoading = prevLoadingRef.current;
    prevLoadingRef.current = loading;

    if (wasLoading && !loading && results.length > 0) {
      setReorderPulse(true);
      const timeout = setTimeout(() => setReorderPulse(false), 220);
      return () => clearTimeout(timeout);
    }
  }, [loading, results.length]);

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
      magnet = item?.Details;
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
    if (loading) {
      return ["All", ...sourceOrder];
    }

    const sorted = Object.entries(sourceCounts)
      .sort(([trackA, countA], [trackB, countB]) => {
        const countDiff = countB - countA;
        if (countDiff !== 0) return countDiff;
        return (trackA || "").localeCompare(trackB || "");
      })
      .map(([tracker]) => tracker);

    return ["All", ...sorted];
  }, [loading, sourceCounts, sourceOrder]);

  const fuse = useMemo(() => {
    return new Fuse(results, {
      keys: [
        { name: "Title", weight: 1 },
        { name: "Tracker", weight: 0.2 },
      ],
      threshold: 0.35,
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

  useResultsOffset(filtersRef, visibleResults.length);

  const handleSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed) return;

    setHasSearched(true);

    const searchId = (searchSessionRef.current += 1);

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setTitleFilter(trimmed);
    setResults([]);
    setSourceOrder([]);
    updateSort(INITIAL_SORT);
    setActiveSource("All");
    setScrollOffset(0);
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

          if (item?.Tracker) {
            setSourceOrder((prev) =>
              prev.includes(item.Tracker) ? prev : [...prev, item.Tracker]
            );
          }

          setResults((prev) =>
            sortResults([...prev, item], sortRef.current ?? sort)
          );
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") console.error(err);
    } finally {
      if (searchSessionRef.current === searchId) {
        setLoading(false);
      }
    }
  };

  const handleCancel = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
  };

  const handleSortChange = (key) => {
    const dir =
      sort.key === key
        ? sort.dir === "asc"
          ? "desc"
          : "asc"
        : DEFAULT_SORT_DIR[key] ?? "asc";
    const nextSort = { key, dir };
    updateSort(nextSort);
    setResults((r) => sortResults(r, nextSort));
  };

  return (
    <div className="flex justify-center -mt-4">
      <div className="mt-4 pb-16 md:pb-6 relative overflow-y-auto overflow-x-hidden 2xl:w-[82rem] w-full p-2 md:p-4 space-y-2 md:space-y-4">
        <SearchBar
          query={query}
          setQuery={setQuery}
          loading={loading}
          onSearch={handleSearch}
          onCancel={handleCancel}
        />

        {results.length > 0 && (
          <div ref={filtersRef}>
            <SortFilters
              sort={sort}
              onSortChange={handleSortChange}
              titleFilter={titleFilter}
              setTitleFilter={setTitleFilter}
              sources={sources}
              activeSource={activeSource}
              setActiveSource={setActiveSource}
              sourceCounts={sourceCounts}
              resultsCount={results.length}
              reorderPulse={reorderPulse}
            />
          </div>
        )}

        {loading && results.length === 0 && (
          <div className="py-10 flex justify-center">
            <div className="h-6 w-6 rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-white animate-spin" />
          </div>
        )}

        {visibleResults.length > 0 && (
          <div className="-mt-6 md:mt-0">
            <TorrentResults
              key={resultsKey}
              items={visibleResults}
              onCopy={handleCopyMagnet}
              onDownload={handleDownload}
              isMobile={isMobile}
              scrollOffset={scrollOffset}
              onScrollOffsetChange={setScrollOffset}
              scrollResetKey={scrollResetKey}
            />
          </div>
        )}

        {hasSearched && !loading && results.length === 0 && (
          <p className="py-10 text-center text-sm text-zinc-500">
            No results found
          </p>
        )}

        {!hasSearched &&
          !loading &&
          firstLoadFinished &&
          !results?.length > 0 && (
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
