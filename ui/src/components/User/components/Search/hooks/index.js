import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import apiRoutes from "@/shared/routes/apiRoutes";
import useToast from "@/shared/hooks/useToast";
import {
  CLIPBOARD_COPY_STATUS,
  copyTextToClipboard,
} from "@/shared/utils/clipboard";
import {
  ALL_SOURCES,
  INITIAL_SORT,
  MOBILE_BREAKPOINT,
  REORDER_PULSE_MS,
  RESULTS_OFFSET_PADDING_REM,
  appendUniqueSource,
  extractMagnet,
  sortResults,
} from "../utils";

const getBrowserOrigin = () => {
  if (typeof window === "undefined") return "";
  return window.location.origin;
};

export const useBrowserProxyBaseUrl = () => {
  const [browserProxyBaseUrl, setBrowserProxyBaseUrl] = useState("");

  useEffect(() => {
    setBrowserProxyBaseUrl(getBrowserOrigin());
  }, []);

  return browserProxyBaseUrl;
};

export const useIsMobileWidth = () => {
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

export const useResultsOffset = (filtersRef, watchKey) => {
  useEffect(() => {
    if (
      typeof document === "undefined" ||
      typeof ResizeObserver === "undefined"
    ) {
      return;
    }

    const element = filtersRef.current;
    if (!element) return;

    const updateOffset = () => {
      const { bottom } = element.getBoundingClientRect();
      const rootFontSize = parseFloat(
        getComputedStyle(document.documentElement).fontSize,
      );

      document.documentElement.style.setProperty(
        "--results-offset",
        `${bottom / rootFontSize + RESULTS_OFFSET_PADDING_REM}rem`,
      );
    };

    updateOffset();

    const resizeObserver = new ResizeObserver(updateOffset);
    resizeObserver.observe(element);

    return () => resizeObserver.disconnect();
  }, [filtersRef, watchKey]);
};

export const useReorderPulse = (loading, resultCount) => {
  const [reorderPulse, setReorderPulse] = useState(false);
  const prevLoadingRef = useRef(false);

  useEffect(() => {
    const wasLoading = prevLoadingRef.current;
    prevLoadingRef.current = loading;

    if (wasLoading && !loading && resultCount > 0) {
      setReorderPulse(true);
      const timeout = setTimeout(
        () => setReorderPulse(false),
        REORDER_PULSE_MS,
      );

      return () => clearTimeout(timeout);
    }
  }, [loading, resultCount]);

  return reorderPulse;
};

export const usePersistedSearchState = ({
  activeSource,
  firstLoadFinished,
  query,
  results,
  scrollOffset,
  sort,
  titleFilter,
  torrentSearchState,
}) => {
  useEffect(() => {
    if (!firstLoadFinished) return;
    torrentSearchState.set({ query });
  }, [firstLoadFinished, query, torrentSearchState]);

  useEffect(() => {
    if (!firstLoadFinished) return;
    torrentSearchState.set({ titleFilter });
  }, [firstLoadFinished, titleFilter, torrentSearchState]);

  useEffect(() => {
    if (!firstLoadFinished) return;
    torrentSearchState.set({ results });
  }, [firstLoadFinished, results, torrentSearchState]);

  useEffect(() => {
    if (!firstLoadFinished) return;
    torrentSearchState.set({ scrollOffset });
  }, [firstLoadFinished, scrollOffset, torrentSearchState]);

  useEffect(() => {
    if (!firstLoadFinished) return;
    torrentSearchState.set({ activeSource, sort });
  }, [activeSource, firstLoadFinished, sort, torrentSearchState]);
};

export const useSearchStateHydration = ({
  getSavedSort,
  query,
  resultsLength,
  setActiveSource,
  setFirstLoadFinished,
  setQuery,
  setResults,
  setScrollOffset,
  setTitleFilter,
  torrentSearchState,
  updateSort,
  urlQuery,
}) => {
  const didHydrateRef = useRef(false);

  useEffect(() => {
    if (didHydrateRef.current) return;
    didHydrateRef.current = true;

    const savedResults = torrentSearchState.get("results") || [];

    if (!query && !resultsLength) {
      const savedScrollOffset = torrentSearchState.get("scrollOffset");

      setQuery(urlQuery || torrentSearchState.get("query"));
      setTitleFilter(torrentSearchState.get("titleFilter"));
      setActiveSource(torrentSearchState.get("activeSource") || ALL_SOURCES);
      setResults(savedResults);
      updateSort(getSavedSort(torrentSearchState));

      if (Number.isFinite(savedScrollOffset)) {
        setScrollOffset(savedScrollOffset);
      }
    }

    setFirstLoadFinished(true);
  }, [
    getSavedSort,
    query,
    resultsLength,
    setActiveSource,
    setFirstLoadFinished,
    setQuery,
    setResults,
    setScrollOffset,
    setTitleFilter,
    torrentSearchState,
    updateSort,
    urlQuery,
  ]);
};

export const useScrollResetOnFilterChange = ({
  activeSource,
  firstLoadFinished,
  setScrollOffset,
  setScrollResetKey,
  titleFilter,
}) => {
  const skipFilterResetRef = useRef(true);

  useEffect(() => {
    if (!firstLoadFinished) return;

    if (skipFilterResetRef.current) {
      skipFilterResetRef.current = false;
      return;
    }

    setScrollOffset(0);
    setScrollResetKey((key) => key + 1);
  }, [
    activeSource,
    firstLoadFinished,
    setScrollOffset,
    setScrollResetKey,
    titleFilter,
  ]);
};

export const useTorrentActions = () => {
  const toast = useToast();

  const resolveMagnet = useCallback(async (item) => extractMagnet(item), []);

  const handleCopyMagnet = useCallback(
    async (item) => {
      const magnet = await resolveMagnet(item);

      if (!magnet) {
        toast.error("Magnet not Found");
        return;
      }

      const status = await copyTextToClipboard(magnet);

      if (status === CLIPBOARD_COPY_STATUS.COPIED) {
        toast.success("Magnet copied to clipboard");
      } else if (status === CLIPBOARD_COPY_STATUS.MANUAL) {
        toast.success("Magnet opened for manual copy");
      } else {
        toast.error("Failed to copy magnet");
      }
    },
    [resolveMagnet, toast],
  );

  const handleDownload = useCallback(
    async (item) => {
      const magnet = await resolveMagnet(item);

      if (!magnet) {
        toast.error("Magnet not Found");
        return;
      }

      try {
        await axios.post(apiRoutes.addMagnet, { magnet });
        toast.success("Added to Download Queue");
      } catch (err) {
        console.error("Add magnet error:", err);
        toast.error("Failed to add torrent");
      }
    },
    [resolveMagnet, toast],
  );

  return { handleCopyMagnet, handleDownload };
};

export const useTorrentSearchStream = ({
  query,
  setActiveSource,
  setHasSearched,
  setLoading,
  setResults,
  setScrollOffset,
  setSourceOrder,
  setTitleFilter,
  sort,
  sortRef,
  updateSort,
}) => {
  const abortRef = useRef(null);
  const searchSessionRef = useRef(0);
  const pendingResultsRef = useRef([]);
  const flushTimerRef = useRef(null);

  const flushPendingResults = useCallback(() => {
    if (flushTimerRef.current) {
      window.clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }

    const pendingResults = pendingResultsRef.current;
    pendingResultsRef.current = [];
    if (!pendingResults.length) return;

    setResults((currentResults) =>
      sortResults([...currentResults, ...pendingResults], sortRef.current ?? sort),
    );
  }, [setResults, sort, sortRef]);

  const clearPendingResults = useCallback(() => {
    pendingResultsRef.current = [];
    if (flushTimerRef.current) {
      window.clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
  }, []);

  useEffect(
    () => () => {
      clearPendingResults();
    },
    [clearPendingResults],
  );

  const resetSearchState = useCallback(
    (initialTitleFilter) => {
      setTitleFilter(initialTitleFilter);
      setResults([]);
      setSourceOrder([]);
      updateSort(INITIAL_SORT);
      setActiveSource(ALL_SOURCES);
      setScrollOffset(0);
    },
    [
      setActiveSource,
      setResults,
      setScrollOffset,
      setSourceOrder,
      setTitleFilter,
      updateSort,
    ],
  );

  const handleSearch = useCallback(async () => {
    const trimmedQuery = query?.trim();
    if (!trimmedQuery) return;

    setHasSearched(true);
    clearPendingResults();
    resetSearchState(trimmedQuery);

    const searchId = (searchSessionRef.current += 1);
    abortRef.current?.abort();

    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);

    try {
      const response = await fetch(
        `${apiRoutes.searchTorrent}?query=${encodeURIComponent(trimmedQuery)}`,
        {
          method: "POST",
          credentials: "include",
          signal: controller.signal,
        },
      );

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        if (searchSessionRef.current !== searchId) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;

          const item = JSON.parse(line);
          setSourceOrder((prev) => appendUniqueSource(prev, item?.Tracker));
          pendingResultsRef.current.push(item);
          if (!flushTimerRef.current) {
            flushTimerRef.current = window.setTimeout(flushPendingResults, 100);
          }
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") console.error(err);
    } finally {
      if (searchSessionRef.current === searchId) {
        flushPendingResults();
        setLoading(false);
      }
    }
  }, [
    query,
    resetSearchState,
    setHasSearched,
    setLoading,
    setResults,
    setSourceOrder,
    sort,
    sortRef,
    clearPendingResults,
    flushPendingResults,
  ]);

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    clearPendingResults();
    setLoading(false);
  }, [clearPendingResults, setLoading]);

  return { handleCancel, handleSearch };
};
