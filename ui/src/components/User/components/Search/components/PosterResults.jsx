import { memo, useEffect, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { FiClipboard, FiDownload, FiExternalLink, FiGlobe, FiArrowUpCircle } from "react-icons/fi";
import { formatBytes, formatCount } from "../utils";
import FileFallback from "../../Home/components/FileFallback";
import FileMenu from "../../Home/components/FileExplorer/components/FileMenu";
import { posterDescriptor, subscribePoster } from "../posterLookup";

const PosterCard = memo(function PosterCard({ item, rootRef, onCopy, onDownload, onItemHover, browserProxyBaseUrl }) {
  const elementRef = useRef(null);
  const [visible, setVisible] = useState(false);
  const [metadata, setMetadata] = useState(null);
  const [imageFailed, setImageFailed] = useState(false);
  const descriptor = posterDescriptor(item);
  const {key, name, kind, enabled} = descriptor;
  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;
    if (typeof IntersectionObserver === "undefined") { setVisible(true); return; }
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { setVisible(true); observer.disconnect(); }
    }, {root:rootRef.current, rootMargin:"120px"});
    observer.observe(element);
    return () => observer.disconnect();
  }, [rootRef]);
  useEffect(() => {
    setMetadata(null); setImageFailed(false);
    if (!visible || !enabled) return;
    return subscribePoster({key, name, kind}, setMetadata);
  }, [visible, enabled, key, name, kind]);
  const title = metadata?.title || item.parsed?.title || item.Title || "Untitled";
  const year = item.parsed?.year || metadata?.year;
  const quality = [item.parsed?.season ? `S${String(item.parsed.season).padStart(2, "0")}` : null, item.parsed?.episode ? `E${String(item.parsed.episode).padStart(2, "0")}` : null, item.parsed?.quality || item.parsed?.source, item.parsed?.codec].filter(Boolean).join(" · ");
  const source = item.Details || item.Link || item.Url || item.URL;
  const imdb = metadata?.imdb_url || `https://www.imdb.com/find/?q=${encodeURIComponent(`${title} ${year || ""}`.trim())}&s=tt`;
  const hasPoster = metadata?.poster_url && !imageFailed;
  const displayTitle = `${title}${year ? ` (${Array.isArray(year) ? year.join(" / ") : year})` : ""}`;
  const actions = [
    {name:"Copy magnet", action:"copy", icon:FiClipboard},
    {name:"Download", action:"download", icon:FiDownload},
    ...(source ? [{name:"Open source", action:"source", icon:FiExternalLink}] : []),
    ...(source && browserProxyBaseUrl ? [{name:"Open source via Tor", action:"tor", icon:FiGlobe}] : []),
    {name:"IMDb", action:"imdb", icon:FiExternalLink},
  ];
  const handleAction = (action) => {
    if (action === "copy") return onCopy(item);
    if (action === "download") return onDownload(item);
    const url = action === "source" ? source : action === "tor" ? `${browserProxyBaseUrl}/tor/${source}` : imdb;
    try {
      const target = new URL(url, window.location.origin);
      if (["http:", "https:"].includes(target.protocol)) window.open(target.href, "_blank", "noopener,noreferrer");
    } catch { /* A malformed source link must not break the action menu. */ }
  };
  return (
    <article ref={elementRef} data-search-poster-card className="group flex w-full min-w-0 flex-col text-neutral-950 dark:text-white"
      onMouseEnter={() => onItemHover?.(item)} onFocus={() => onItemHover?.(item)}>
      <div className="group/poster relative w-full overflow-hidden rounded-md bg-neutral-200 transition-[box-shadow,filter] group-hover:shadow-lg group-hover:shadow-blue-500/20 group-hover:brightness-110 dark:bg-neutral-900 dark:group-hover:shadow-blue-950/40" style={{aspectRatio:"2 / 3"}}>
        <div className="absolute inset-0.5 overflow-hidden rounded-[5px] bg-neutral-200 ring-1 ring-neutral-200 dark:bg-neutral-900 dark:ring-neutral-800">
          <FileFallback />
          {hasPoster ? <img src={metadata.poster_url} alt={`${title} poster`} loading="lazy" decoding="async" className="relative h-full w-full object-cover" onError={() => setImageFailed(true)} /> : null}
          <div className={`absolute inset-x-0 bottom-0 h-24 ${hasPoster ? "bg-gradient-to-t from-black/95 via-black/55 to-transparent" : "bg-gradient-to-t from-black/35 via-black/10 to-transparent dark:from-black/85 dark:via-black/35"}`} />
          <div className={`absolute inset-x-0 bottom-0 flex h-24 flex-col justify-end p-2 ${hasPoster ? "text-white [text-shadow:0_2px_14px_rgba(0,0,0,1),0_1px_3px_rgba(0,0,0,1)]" : "text-neutral-950 dark:text-white dark:[text-shadow:0_2px_12px_rgba(0,0,0,0.85)]"}`}>
            <h3 className="line-clamp-2 max-h-8 break-words text-xs font-semibold leading-4" title={item.Title}>{displayTitle}</h3>
            <div className={`mt-0.5 flex min-h-4 min-w-0 items-center gap-1.5 text-[11px] leading-4 ${hasPoster ? "text-neutral-300" : "text-neutral-500 dark:text-neutral-500"}`}>
              {item.parsed?.resolution ? <><span className="shrink-0">{item.parsed.resolution}</span><span aria-hidden="true">·</span></> : null}
              <span className="truncate" title={quality || item.Title}>{quality || item.Tracker || ""}</span>
            </div>
            <div className={`flex min-h-4 min-w-0 items-center gap-1.5 text-[11px] leading-4 ${hasPoster ? "text-neutral-300" : "text-neutral-500 dark:text-neutral-500"}`}>
              <span className="flex shrink-0 items-center gap-1" title="Seeders"><FiArrowUpCircle size={11} />{item.Seeders == null ? "—" : formatCount(item.Seeders)}</span>
              <span aria-hidden="true">·</span><span className="shrink-0">{formatBytes(item.Size)}</span>
              <span className="hidden min-w-0 truncate xl:inline" title={item.Tracker}>{item.Tracker ? `· ${item.Tracker}` : ""}</span>
            </div>
          </div>
          <div className="absolute right-1 top-1 z-30">
            <FileMenu item={item} actions={actions} onAction={handleAction} ariaLabel="Search result actions"
              targetClassName="flex h-11 w-11 items-center justify-center rounded-md text-white transition-colors hover:bg-black/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500 md:h-7 md:w-7"
              iconClassName="h-3.5 w-3.5 rotate-90 text-white [filter:drop-shadow(0_2px_5px_rgba(0,0,0,0.95))_drop-shadow(0_0_2px_rgba(0,0,0,0.9))]"
              itemClassName="min-h-[44px]" />
          </div>
        </div>
      </div>
    </article>
  );
});

export default function PosterResults({ items, onCopy, onDownload, onItemHover, scrollOffset, onScrollOffsetChange, scrollResetKey, browserProxyBaseUrl }) {
  const rootRef = useRef(null);
  const [columns, setColumns] = useState(2);
  const scrollTimer = useRef(null);
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const resize = () => setColumns(window.innerWidth >= 1536 ? 8 : window.innerWidth >= 1024 ? 6 : window.innerWidth >= 640 ? 5 : 2);
    resize();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", resize);
      return () => { window.removeEventListener("resize", resize); window.clearTimeout(scrollTimer.current); };
    }
    const observer = new ResizeObserver(resize);
    observer.observe(root);
    return () => { observer.disconnect(); window.clearTimeout(scrollTimer.current); };
  }, []);
  const virtualizer = useVirtualizer({count:Math.ceil(items.length / columns), getScrollElement:() => rootRef.current, estimateSize:() => 300, overscan:1});
  useEffect(() => {
    if (rootRef.current) rootRef.current.scrollTop = Number.isFinite(scrollOffset) ? scrollOffset : 0;
    // Restore only on entry/reset; scrolling updates the shared offset independently.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scrollResetKey]);
  return (
    <div ref={rootRef} data-search-poster-grid className="h-[calc(100vh-var(--results-offset))] overflow-auto rounded-lg pb-16 pr-1 md:pb-0 light-scrolbar dark:dark-scrollbar"
      onScroll={(event) => { const top = event.currentTarget.scrollTop; window.clearTimeout(scrollTimer.current); scrollTimer.current = window.setTimeout(() => onScrollOffsetChange?.(top), 140); }}>
      <div className="relative w-full" style={{height:virtualizer.getTotalSize()}}>
        {virtualizer.getVirtualItems().map((row) => (
          <div key={row.key} data-index={row.index} ref={virtualizer.measureElement} className="absolute left-0 top-0 grid w-full gap-x-2.5 px-1 pb-4 pt-1" style={{gridTemplateColumns:`repeat(${columns}, minmax(0, 1fr))`, transform:`translateY(${row.start}px)`}}>
            {items.slice(row.index * columns, (row.index + 1) * columns).map((item, index) => <PosterCard key={item.SearchResultKey || `${item.InfoHash || item.Details || item.Title}-${index}`} item={item} rootRef={rootRef} onCopy={onCopy} onDownload={onDownload} onItemHover={onItemHover} browserProxyBaseUrl={browserProxyBaseUrl} />)}
          </div>
        ))}
      </div>
    </div>
  );
}
