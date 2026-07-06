import { useCallback, useMemo, useRef, useState } from "react";
import Fuse from "fuse.js";
import SearchBar from "./components/SearchBar";
import SortFilters from "./components/SortFilters";
import TorrentResults from "./components/TorrentResults";
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
} from "./hooks";
import {
  ALL_SOURCES,
  FUSE_OPTIONS,
  filterByTitle,
  getNextSort,
  getOrderedSources,
  getSavedSort,
  getSourceCounts,
  INITIAL_SORT,
  sortResults,
} from "./utils";

const Search = ({ torrentSearchState }) => {
  const [activeSource, setActiveSource] = useState(ALL_SOURCES);
  const [firstLoadFinished, setFirstLoadFinished] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [scrollOffset, setScrollOffset] = useState(0);
  const [scrollResetKey, setScrollResetKey] = useState(0);
  const [sort, setSortState] = useState(INITIAL_SORT);
  const [sourceOrder, setSourceOrder] = useState([]);
  const [titleFilter, setTitleFilter] = useState("");

  const filtersRef = useRef(null);
  const sortRef = useRef(INITIAL_SORT);

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
    torrentSearchState,
    updateSort,
  });

  usePersistedSearchState({
    activeSource,
    firstLoadFinished,
    query,
    results,
    scrollOffset,
    sort,
    titleFilter,
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

  const fuse = useMemo(() => new Fuse(results, FUSE_OPTIONS), [results]);

  const visibleResults = useMemo(
    () => filterByTitle({ activeSource, fuse, results, titleFilter }),
    [activeSource, fuse, results, titleFilter],
  );

  const resultsKey = `${activeSource}-${sort.key}-${sort.dir}-${titleFilter}`;

  useResultsOffset(filtersRef, visibleResults.length);

  const { handleCopyMagnet, handleDownload } = useTorrentActions();
  const { handleCancel, handleSearch } = useTorrentSearchStream({
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
  });

  const handleSortChange = useCallback(
    (key) => {
      const nextSort = getNextSort(sort, key);
      updateSort(nextSort);
      setResults((currentResults) => sortResults(currentResults, nextSort));
    },
    [sort, updateSort],
  );

  const showFilters = results.length > 0;
  const showLoadingIndicator = loading && results.length === 0;
  const showResults = visibleResults.length > 0;
  const showNoResults = hasSearched && !loading && results.length === 0;
  const showEmptySearch =
    !hasSearched && !loading && firstLoadFinished && !results?.length;

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

        {showFilters && (
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

        {showLoadingIndicator && (
          <div className="py-10 flex justify-center">
            <div className="h-6 w-6 rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-white animate-spin" />
          </div>
        )}

        {showResults && (
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
              browserProxyBaseUrl={browserProxyBaseUrl}
              onItemHover={(item) => {
                torrentSearchState.set({ hoveredResult: item });
              }}
            />
          </div>
        )}

        {showNoResults && (
          <p className="py-10 text-center text-sm text-zinc-500">
            No results found
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
