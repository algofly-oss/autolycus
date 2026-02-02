import { FiClipboard, FiDownload } from "react-icons/fi";
import { useRef, useEffect } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import apiRoutes from "@/shared/routes/apiRoutes";
import { formatBytes, formatDate, truncateText } from "../utils";

const TorrentCardContent = ({ item, onCopy, onDownload }) => (
  <>
    <div className="flex items-start justify-between gap-3">
      <p className="font-semibold leading-snug text-sm">
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
          href={`${apiRoutes?.searchImdbRedirect}?q=${
            item?.parsed?.title
              ? `${item?.parsed?.title} ${item?.parsed?.year || ""}`
              : item.Title?.slice(0, 20)
          }`}
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

const VirtualizedResults = ({
  items,
  onCopy,
  onDownload,
  scrollOffset,
  onScrollOffsetChange,
}) => {
  const parentRef = useRef(null);
  const restoringRef = useRef(false);
  const rafRef = useRef(null);

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
    const offset = Number.isFinite(scrollOffset) ? scrollOffset : 0;
    restoringRef.current = true;
    requestAnimationFrame(() => {
      rowVirtualizer.scrollToOffset(offset, { align: "start" });
      requestAnimationFrame(() => {
        restoringRef.current = false;
      });
    });
  }, [rowVirtualizer, scrollOffset]);

  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <div
      ref={parentRef}
      onScroll={() => {
        if (!parentRef.current || !onScrollOffsetChange) return;
        if (restoringRef.current) return;
        const nextOffset = parentRef.current.scrollTop;
        if (rafRef.current) cancelAnimationFrame(rafRef.current);
        rafRef.current = requestAnimationFrame(() => {
          onScrollOffsetChange(nextOffset);
          rafRef.current = null;
        });
      }}
      className={`h-[calc(100vh-var(--results-offset))] overflow-auto light-scrolbar dark:dark-scrollbar pr-1 rounded-lg`}
    >
      <ul className="relative w-full" style={{ height: rowVirtualizer.getTotalSize() }}>
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const item = items[virtualRow.index];

          return (
            <li
              key={virtualRow.key}
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
              <TorrentCardContent item={item} onCopy={onCopy} onDownload={onDownload} />
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
  scrollOffset,
  onScrollOffsetChange,
}) => {
  const parentRef = useRef(null);
  const restoringRef = useRef(false);
  const rafRef = useRef(null);

  useEffect(() => {
    if (!parentRef.current) return;
    const offset = Number.isFinite(scrollOffset) ? scrollOffset : 0;
    restoringRef.current = true;
    requestAnimationFrame(() => {
      if (parentRef.current) parentRef.current.scrollTop = offset;
      requestAnimationFrame(() => {
        restoringRef.current = false;
      });
    });
  }, [scrollOffset]);

  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <div
      ref={parentRef}
      onScroll={() => {
        if (!parentRef.current || !onScrollOffsetChange) return;
        if (restoringRef.current) return;
        const nextOffset = parentRef.current.scrollTop;
        if (rafRef.current) cancelAnimationFrame(rafRef.current);
        rafRef.current = requestAnimationFrame(() => {
          onScrollOffsetChange(nextOffset);
          rafRef.current = null;
        });
      }}
      className={`h-[calc(100vh-var(--results-offset))] overflow-auto light-scrolbar dark:dark-scrollbar pr-1 rounded-lg`}
    >
      <ul className="flex flex-col gap-2">
        {items.map((item, index) => (
          <li
            key={getTorrentKey(item, index)}
            className="w-full p-4 rounded-md
                     bg-neutral-50 dark:bg-black
                     hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
          >
            <TorrentCardContent item={item} onCopy={onCopy} onDownload={onDownload} />
          </li>
        ))}
      </ul>
    </div>
  );
};

const TorrentResults = ({
  items,
  onCopy,
  onDownload,
  isMobile,
  scrollOffset,
  onScrollOffsetChange,
}) => {
  if (!items?.length) return null;

  return isMobile ? (
    <PlainResults
      items={items}
      onCopy={onCopy}
      onDownload={onDownload}
      scrollOffset={scrollOffset}
      onScrollOffsetChange={onScrollOffsetChange}
    />
  ) : (
    <VirtualizedResults
      items={items}
      onCopy={onCopy}
      onDownload={onDownload}
      scrollOffset={scrollOffset}
      onScrollOffsetChange={onScrollOffsetChange}
    />
  );
};

export default TorrentResults;
