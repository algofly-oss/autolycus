import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/router";
import Fuse from "fuse.js";
import SearchBar from "./components/SearchBar";
import SortFilters from "./components/SortFilters";
import TorrentResults from "./components/TorrentResults";
import PosterResults from "./components/PosterResults";
import {
  useBrowserProxyBaseUrl,
  useIsMobileWidth,
  usePersistedSearchState,
  useReorderPulse,
  useResultsOffset,
  useScrollResetOnFilterChange,
  useSearchStateHydration,
  useTorrentActions,
  useTorrentSearchStream,
  useSearchViewMode,
} from "./hooks";
import {
  ALL_SOURCES,
  FUSE_OPTIONS,
  normalizeSearchText,
  filterByTitle,
  getNextSort,
  getOrderedSources,
  getSavedSort,
  getSourceCounts,
  INITIAL_SORT,
  sortResults,
} from "./utils";

const Search = ({ torrentSearchState }) => {
  const router = useRouter();
  const { viewMode, changeView, saving: savingView } = useSearchViewMode();
  const [activeSource, setActiveSource] = useState(ALL_SOURCES);
  const [firstLoadFinished, setFirstLoadFinished] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [searchStatus, setSearchStatus] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [scrollOffset, setScrollOffset] = useState(0);
  const [scrollResetKey, setScrollResetKey] = useState(0);
  const [sort, setSortState] = useState(INITIAL_SORT);
  const [sourceOrder, setSourceOrder] = useState([]);
  const [titleFilter, setTitleFilter] = useState("");
  const [titleFilterEdited, setTitleFilterEdited] = useState(false);

  const filtersRef = useRef(null);
  const sortRef = useRef(INITIAL_SORT);
  const openedUrlSearchRef = useRef(null);
  const urlQuery = Array.isArray(router.query.q)
    ? router.query.q[0]
    : router.query.q;

  const browserProxyBaseUrl = useBrowserProxyBaseUrl();
  const isMobile = useIsMobileWidth();
  const reorderPulse = useReorderPulse(loading, results.length);

  const updateSort = useCallback((nextSort) => {
    sortRef.current = nextSort;
    setSortState(nextSort);
  }, []);

  useSearchStateHydration({
    getSavedSort,
    query,
    resultsLength: results?.length,
    setActiveSource,
    setFirstLoadFinished,
    setQuery,
    setResults,
    setScrollOffset,
    setTitleFilter,
    setTitleFilterEdited,
    torrentSearchState,
    updateSort,
    urlQuery,
  });

  usePersistedSearchState({
    activeSource,
    firstLoadFinished,
    query,
    results,
    scrollOffset,
    sort,
    titleFilter,
    titleFilterEdited,
    torrentSearchState,
  });

  useScrollResetOnFilterChange({
    activeSource,
    firstLoadFinished,
    setScrollOffset,
    setScrollResetKey,
    titleFilter,
  });

  const sourceCounts = useMemo(() => getSourceCounts(results), [results]);

  const sources = useMemo(
    () => getOrderedSources({ loading, sourceCounts, sourceOrder }),
    [loading, sourceCounts, sourceOrder],
  );

  const fuse = useMemo(() => new Fuse(results, { ...FUSE_OPTIONS, getFn: (item, path) => path.join(".") === "SearchTitle" ? normalizeSearchText(item.Title) : item.Title }), [results]);

  const visibleResults = useMemo(
    () => filterByTitle({ activeSource, fuse, results, titleFilter, allowPrefix: titleFilterEdited }),
    [activeSource, fuse, results, titleFilter, titleFilterEdited],
  );

  const resultsKey = `${activeSource}-${sort.key}-${sort.dir}-${titleFilter}`;

  useResultsOffset(filtersRef, visibleResults.length);

  const { handleCopyMagnet, handleDownload } = useTorrentActions();
  const { handleCancel, handleSearch } = useTorrentSearchStream({
    query,
    setSearchStatus,
    setActiveSource,
    setHasSearched,
    setLoading,
    setResults,
    setScrollOffset,
    setSourceOrder,
    setTitleFilter,
    setTitleFilterEdited,
    sort,
    sortRef,
    updateSort,
  });

  const handleSearchFromInput = useCallback(() => {
    const trimmedQuery = query?.trim();
    if (!trimmedQuery) return;

    openedUrlSearchRef.current = trimmedQuery;
    if (router.isReady && urlQuery !== trimmedQuery) {
      router.push(
        {
          pathname: router.pathname,
          query: { ...router.query, tab: "search", q: trimmedQuery },
        },
        undefined,
        { shallow: true, scroll: false },
      );
    }

    handleSearch();
  }, [handleSearch, query, router, urlQuery]);

  useEffect(() => {
    if (!router.isReady || !firstLoadFinished || !urlQuery) return;
    if (openedUrlSearchRef.current === urlQuery) return;

    if (query !== urlQuery) {
      setQuery(urlQuery);
      return;
    }

    openedUrlSearchRef.current = urlQuery;
    handleSearch();
  }, [firstLoadFinished, handleSearch, query, router.isReady, urlQuery]);

  const handleSortChange = useCallback(
    (key) => {
      const nextSort = getNextSort(sort, key);
      updateSort(nextSort);
      setResults((currentResults) => sortResults(currentResults, nextSort));
    },
    [sort, updateSort],
  );

  const ResultsView = viewMode === "grid" ? PosterResults : TorrentResults;

  const showLoadingIndicator = loading && results.length === 0;
  const showResults = visibleResults.length > 0;
  const showNoResults = hasSearched && !loading && visibleResults.length === 0;
  const showEmptySearch =
    !hasSearched && !loading && firstLoadFinished && !results?.length;

  return (
    <div className="flex justify-center -mt-4">
      <div className="mt-4 pb-16 md:pb-6 relative overflow-y-auto overflow-x-hidden 2xl:w-[82rem] w-full p-2 md:p-4 space-y-2 md:space-y-4">
        <div className="flex items-center gap-2">
          <div className="min-w-0 flex-1">
            <SearchBar
              query={query}
              setQuery={setQuery}
              loading={loading}
              onSearch={handleSearchFromInput}
              onCancel={handleCancel}
            />
          </div>
        </div>

        {searchStatus && <p role="status" className="text-xs text-zinc-500">{searchStatus}</p>}

        <div ref={filtersRef}>
            <SortFilters
              sort={sort}
              onSortChange={handleSortChange}
              titleFilter={titleFilter}
              setTitleFilter={(value) => { setTitleFilter(value); setTitleFilterEdited(true); }}
              sources={sources}
              activeSource={activeSource}
              setActiveSource={setActiveSource}
              sourceCounts={sourceCounts}
              resultsCount={results.length}
              reorderPulse={reorderPulse}
              viewMode={viewMode}
              onViewModeChange={changeView}
              savingView={savingView}
            />
        </div>

        {showLoadingIndicator && (
          <div className="py-10 flex justify-center">
            <div className="h-6 w-6 rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-white animate-spin" />
          </div>
        )}

        {showResults && (
          <div className="mt-0">
            <ResultsView
              key={`${viewMode}-${resultsKey}`}
              items={visibleResults}
              onCopy={handleCopyMagnet}
              onDownload={handleDownload}
              isMobile={isMobile}
              scrollOffset={scrollOffset}
              onScrollOffsetChange={setScrollOffset}
              scrollResetKey={scrollResetKey}
              browserProxyBaseUrl={browserProxyBaseUrl}
              onItemHover={(item) => {
                torrentSearchState.set({ hoveredResult: item });
              }}
            />
          </div>
        )}

        {showNoResults && (
          <p className="py-10 text-center text-sm text-zinc-500">
            {results.length ? "No titles match your filters. Adjust the title filter or source." : "No results found"}
          </p>
        )}

        {showEmptySearch && (
          <div className="flex flex-col items-center justify-center py-12 sm:py-16 text-gray-500 dark:text-gray-400">
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
