import { FiClipboard, FiDownload } from "react-icons/fi";
import { useRef, useEffect, useState, useCallback } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { formatBytes, formatDate, truncateText } from "../utils";

const buildImdbSearchUrl = (item) => {
  const title = item?.parsed?.title
    ? `${item.parsed.title} ${item?.parsed?.year || ""}`.trim()
    : item?.Title;

  if (!title) return null;

  return `https://www.imdb.com/find/?q=${encodeURIComponent(title)}&s=tt`;
};

const buildProxiedUrl = (url, browserProxyBaseUrl) => {
  if (!url || !browserProxyBaseUrl) return null;
  return `${browserProxyBaseUrl}/tor/${url}`;
};

const TorrentCardContent = ({
  item,
  onCopy,
  onDownload,
  browserProxyBaseUrl,
}) => {
  const imdbSearchUrl = buildImdbSearchUrl(item);
  const sourceUrl = item.Details || item.Link || item.Url || item.URL;
  const proxiedSourceUrl = buildProxiedUrl(sourceUrl, browserProxyBaseUrl);

  return (
    <>
      <div className="flex items-start justify-between gap-3 min-w-0">
        <p className="min-w-0 flex-1 font-semibold leading-snug text-sm break-all">
          {truncateText(item?.Title) || "Untitled"}
        </p>

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
        {item?.PublishDate && <span>📅 {formatDate(item.PublishDate)}</span>}
        {item?.Tracker && (
          <span className="inline-flex items-center gap-1.5">
            <a
              href={sourceUrl || undefined}
              title={sourceUrl || undefined}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-blue-500 transition"
            >
              🔎 {item.Tracker}
            </a>
            {proxiedSourceUrl && (
              <a
                href={proxiedSourceUrl}
                title="Open via Tor proxy"
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Open ${item.Tracker} via Tor proxy`}
                className="hover:text-purple-500 transition"
              >
                🌍 Proxy
              </a>
            )}
          </span>
        )}
        {imdbSearchUrl && (
          <a
            href={imdbSearchUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-blue-500 transition"
          >
            🌐 IMDB
          </a>
        )}
      </div>
    </>
  );
};

const VirtualizedResults = ({
  items,
  onCopy,
  onDownload,
  onItemHover,
  scrollOffset,
  onScrollOffsetChange,
  scrollResetKey,
  browserProxyBaseUrl,
}) => {
  const parentRef = useRef(null);
  const restoringRef = useRef(false);
  const rafRef = useRef(null);
  const scrollSaveTimeoutRef = useRef(null);
  const lastScrollTopRef = useRef(0);
  const userScrollRef = useRef(false);
  const userScrollTimeoutRef = useRef(null);

  const rowVirtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 85,
    overscan: 6,
  });

  useEffect(() => {
    if (!parentRef.current) return;
    const ro = new ResizeObserver(() => {
      rowVirtualizer.measure();
    });
    ro.observe(parentRef.current);
    return () => ro.disconnect();
  }, [rowVirtualizer]);

  useEffect(() => {
    if (!parentRef.current) return;
    if (scrollResetKey !== undefined) userScrollRef.current = false;
    if (userScrollRef.current) return;
    const offset = Number.isFinite(scrollOffset) ? scrollOffset : 0;
    if (Math.abs(parentRef.current.scrollTop - offset) < 1) return;
    restoringRef.current = true;
    requestAnimationFrame(() => {
      rowVirtualizer.scrollToOffset(offset, { align: "start" });
      requestAnimationFrame(() => {
        restoringRef.current = false;
      });
    });
  }, [rowVirtualizer, scrollOffset, scrollResetKey]);

  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (userScrollTimeoutRef.current)
        clearTimeout(userScrollTimeoutRef.current);
      if (scrollSaveTimeoutRef.current)
        clearTimeout(scrollSaveTimeoutRef.current);
    };
  }, []);

  return (
    <div
      ref={parentRef}
      onScroll={() => {
        if (!parentRef.current || !onScrollOffsetChange) return;
        if (restoringRef.current) return;
        userScrollRef.current = true;
        if (userScrollTimeoutRef.current)
          clearTimeout(userScrollTimeoutRef.current);
        userScrollTimeoutRef.current = setTimeout(() => {
          userScrollRef.current = false;
        }, 120);
        lastScrollTopRef.current = parentRef.current.scrollTop;
        if (scrollSaveTimeoutRef.current)
          clearTimeout(scrollSaveTimeoutRef.current);
        scrollSaveTimeoutRef.current = setTimeout(() => {
          onScrollOffsetChange(lastScrollTopRef.current);
        }, 140);
      }}
      className={`h-[calc(100vh-var(--results-offset))] overflow-auto scroll-auto touch-scroll light-scrolbar dark:dark-scrollbar pr-1 rounded-lg`}
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
              onMouseEnter={() => onItemHover?.(item)}
              className="absolute left-0 w-full p-4 rounded-md
                        bg-neutral-50 dark:bg-black
                        hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
              ref={(el) => {
                if (el) rowVirtualizer.measureElement(el);
              }}
              style={{
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <TorrentCardContent
                item={item}
                onCopy={onCopy}
                onDownload={onDownload}
                browserProxyBaseUrl={browserProxyBaseUrl}
              />
            </li>
          );
        })}
      </ul>
    </div>
  );
};

const getTorrentKey = (item, index) =>
  item?.InfoHash || item?.Details || `${item?.Title ?? "torrent"}-${index}`;

const PlainResults = ({
  items,
  onCopy,
  onDownload,
  onItemHover,
  scrollOffset,
  onScrollOffsetChange,
  scrollResetKey,
  browserProxyBaseUrl,
  onReachEnd,
  onReachTop,
}) => {
  const parentRef = useRef(null);
  const restoringRef = useRef(false);
  const rafRef = useRef(null);
  const scrollSaveTimeoutRef = useRef(null);
  const lastScrollTopRef = useRef(0);
  const userScrollRef = useRef(false);
  const userScrollTimeoutRef = useRef(null);

  useEffect(() => {
    if (!parentRef.current) return;
    if (scrollResetKey !== undefined) userScrollRef.current = false;
    if (userScrollRef.current) return;
    const offset = Number.isFinite(scrollOffset) ? scrollOffset : 0;
    if (Math.abs(parentRef.current.scrollTop - offset) < 1) return;
    restoringRef.current = true;
    requestAnimationFrame(() => {
      if (parentRef.current) parentRef.current.scrollTop = offset;
      requestAnimationFrame(() => {
        restoringRef.current = false;
      });
    });
  }, [scrollOffset, scrollResetKey]);

  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (userScrollTimeoutRef.current)
        clearTimeout(userScrollTimeoutRef.current);
      if (scrollSaveTimeoutRef.current)
        clearTimeout(scrollSaveTimeoutRef.current);
    };
  }, []);

  return (
    <div
      ref={parentRef}
      onScroll={(event) => {
        if (!parentRef.current || !onScrollOffsetChange) return;
        if (restoringRef.current) return;
        userScrollRef.current = true;
        if (userScrollTimeoutRef.current)
          clearTimeout(userScrollTimeoutRef.current);
        userScrollTimeoutRef.current = setTimeout(() => {
          userScrollRef.current = false;
        }, 120);
        lastScrollTopRef.current = parentRef.current.scrollTop;
        if (scrollSaveTimeoutRef.current)
          clearTimeout(scrollSaveTimeoutRef.current);
        scrollSaveTimeoutRef.current = setTimeout(() => {
          onScrollOffsetChange(lastScrollTopRef.current);
        }, 140);

        const { scrollTop, clientHeight, scrollHeight } = event.currentTarget;
        if (scrollTop <= 160) {
          onReachTop?.();
        }
        if (scrollTop + clientHeight >= scrollHeight - 160) {
          onReachEnd?.();
        }
      }}
      className={`h-[calc(100vh-var(--results-offset))] overflow-auto scroll-auto touch-scroll light-scrolbar dark:dark-scrollbar pr-1 rounded-lg`}
    >
      <ul className="flex flex-col gap-2">
        {items.map((item, index) => (
          <li
            key={getTorrentKey(item, index)}
            onMouseEnter={() => onItemHover?.(item)}
            className="w-full rounded-md p-3 sm:p-4
                     bg-neutral-50 dark:bg-black
                     hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
          >
            <TorrentCardContent
              item={item}
              onCopy={onCopy}
              onDownload={onDownload}
              browserProxyBaseUrl={browserProxyBaseUrl}
            />
          </li>
        ))}
      </ul>
    </div>
  );
};

const MOBILE_RESULTS_PAGE_SIZE = 50;

const MobileResults = ({ items, ...props }) => {
  const [visibleCount, setVisibleCount] = useState(MOBILE_RESULTS_PAGE_SIZE);
  const loadingMoreRef = useRef(false);

  useEffect(() => {
    if (items.length === 0) {
      setVisibleCount(MOBILE_RESULTS_PAGE_SIZE);
    }
  }, [items.length]);

  useEffect(() => {
    loadingMoreRef.current = false;
  }, [visibleCount, items.length]);

  const visibleItems = items.slice(0, visibleCount);
  const hasMore = visibleItems.length < items.length;
  const loadMore = useCallback(() => {
    if (!hasMore || loadingMoreRef.current) return;
    loadingMoreRef.current = true;
    setVisibleCount((count) => count + MOBILE_RESULTS_PAGE_SIZE);
  }, [hasMore]);
  const releaseExtraResults = useCallback(() => {
    if (visibleCount > MOBILE_RESULTS_PAGE_SIZE) {
      setVisibleCount(MOBILE_RESULTS_PAGE_SIZE);
    }
  }, [visibleCount]);

  return (
    <>
      <PlainResults
        items={visibleItems}
        onReachEnd={loadMore}
        onReachTop={releaseExtraResults}
        {...props}
      />
      {hasMore ? (
        <button
          type="button"
          className="mt-3 w-full rounded-md border border-zinc-300 px-4 py-3 text-sm font-medium text-zinc-700 transition hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
          onClick={loadMore}
        >
          Load more results ({items.length - visibleItems.length} remaining)
        </button>
      ) : null}
    </>
  );
};

const TorrentResults = ({
  items,
  onCopy,
  onDownload,
  onItemHover,
  isMobile,
  scrollOffset,
  onScrollOffsetChange,
  scrollResetKey,
  browserProxyBaseUrl,
}) => {
  if (!items?.length) return null;

  return isMobile ? (
    <MobileResults
      items={items}
      onCopy={onCopy}
      onDownload={onDownload}
      onItemHover={onItemHover}
      scrollOffset={scrollOffset}
      onScrollOffsetChange={onScrollOffsetChange}
      scrollResetKey={scrollResetKey}
      browserProxyBaseUrl={browserProxyBaseUrl}
    />
  ) : (
    <VirtualizedResults
      items={items}
      onCopy={onCopy}
      onDownload={onDownload}
      onItemHover={onItemHover}
      scrollOffset={scrollOffset}
      onScrollOffsetChange={onScrollOffsetChange}
      scrollResetKey={scrollResetKey}
      browserProxyBaseUrl={browserProxyBaseUrl}
    />
  );
};

export default TorrentResults;
