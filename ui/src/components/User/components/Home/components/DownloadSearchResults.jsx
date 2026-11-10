import { Fragment, useContext, useEffect, useState, useCallback } from "react";
import axios from "axios";
import { FiFile, FiFolder } from "react-icons/fi";
import { BsCircleFill } from "react-icons/bs";
import apiRoutes from "@/shared/routes/apiRoutes";
import { formatFileSize, getQuality } from "@/shared/utils/fileUtils";
import useInfinitePages from "@/shared/useInfinitePages";
import InfiniteMediaList from "@/shared/InfiniteMediaList";
import TorrentCard from "./TorrentCard";
import { SocketContext } from "@/shared/contexts/socket";
import socketRoutes from "@/shared/routes/socketRoutes";
import FileFallback from "./FileFallback";

const getResultKey = result => result.id || result.relative_path;
const getTorrentKey = (torrent) => torrent?.info_hash || torrent?.url_hash || torrent?.torrent_id;

function ResultIcon({ type }) {
  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-neutral-200/70 text-neutral-600 dark:bg-neutral-900 dark:text-neutral-400">
      {type === "directory" ? <FiFolder size={19} /> : <FiFile size={19} />}
    </div>
  );
}

const extractYear = (value) => {
  const match = String(value || "").match(/\b((?:19|20)\d{2})\b/);
  return match ? match[1] : null;
};

function SearchGridCard({ result, onClick }) {
  const metadata = result?.media_metadata;
  const posterUrl = metadata?.poster_url;
  const { resolution, source } = getQuality(result.name);
  const title = result.name;
  const isTorrentCard = Boolean(result.is_torrent_root);
  const typeLabel =
    result.item_type === "directory" ? (isTorrentCard ? "Torrent" : "Folder") : "File";
  const sizeLabel = result.size ? formatFileSize(result.size || 0) : null;
  const qualityItems = [
    metadata?.year || extractYear(result.name),
    metadata?.quality?.resolution || resolution,
    metadata?.quality?.source || source,
  ].filter(Boolean);
  const metaItems = [
    ...(isTorrentCard && sizeLabel
      ? [qualityItems[0], qualityItems[1], sizeLabel]
      : [
          ...qualityItems,
          sizeLabel ||
            (isTorrentCard
              ? "Torrent"
              : result.item_type === "directory"
              ? "Folder"
              : null),
        ]),
  ].filter(Boolean);

  return (
    <button
      type="button"
      className="group flex w-full min-w-0 flex-col text-left text-neutral-900 dark:text-white"
      onClick={onClick}
    >
      <div
        className="relative w-full overflow-hidden rounded-md bg-neutral-200 ring-1 ring-neutral-200 transition-[box-shadow,filter] group-hover:shadow-lg group-hover:shadow-blue-500/20 group-hover:brightness-110 dark:bg-neutral-900 dark:ring-neutral-800 dark:group-hover:shadow-blue-950/40"
        style={{ aspectRatio: "2 / 3" }}
      >
        <FileFallback />
        {posterUrl ? (
          <img
            src={posterUrl}
            alt=""
            className="relative h-full w-full object-cover"
            loading="lazy"
            onError={(event) => {
              event.currentTarget.style.display = "none";
            }}
          />
        ) : null}
        <div
          className={`absolute bottom-0 left-0 right-0 h-24 ${
            posterUrl
              ? "bg-gradient-to-t from-black/95 via-black/55 to-transparent"
              : "bg-gradient-to-t from-black/35 via-black/10 to-transparent dark:from-black/85 dark:via-black/35"
          }`}
        />
        <div
          className={`absolute bottom-0 left-0 right-0 flex h-24 flex-col justify-end p-2 ${
            posterUrl
              ? "text-white [text-shadow:0_2px_14px_rgba(0,0,0,1),0_1px_3px_rgba(0,0,0,1)]"
              : "text-neutral-900 dark:text-white dark:[text-shadow:0_2px_12px_rgba(0,0,0,0.85)]"
          }`}
        >
          <p className="h-12 overflow-hidden text-xs font-semibold leading-4 [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:3]">
            {title}
          </p>
          <div
            className={`mt-1 flex h-4 min-w-0 items-center gap-1.5 text-[11px] ${
              posterUrl ? "text-neutral-300" : "text-neutral-500 dark:text-neutral-500"
            }`}
          >
            {metaItems.slice(0, 3).map((item, index) => (
              <Fragment key={`${item}-${index}`}>
                {index > 0 ? (
                  <BsCircleFill className="h-1 w-1 shrink-0" />
                ) : null}
                <span className="min-w-0 truncate">{item}</span>
              </Fragment>
            ))}
          </div>
        </div>
        {!isTorrentCard ? (
          <div
            className={`absolute left-2 top-2 rounded px-1.5 py-0.5 text-[11px] font-semibold capitalize backdrop-blur ${
              posterUrl
                ? "bg-black/65 text-white"
                : "bg-neutral-100/85 text-neutral-700 dark:bg-black/70 dark:text-neutral-200"
            }`}
          >
            {typeLabel}
          </div>
        ) : null}
      </div>

      {!isTorrentCard ? (
        <div className="flex flex-1 flex-col pt-2">
          <div className="text-xs font-medium text-neutral-500 dark:text-neutral-500">
            {result.torrent_title || "Download"}
          </div>
        </div>
      ) : null}
    </button>
  );
}

export default function DownloadSearchResults({
  state,
  scrollRef,
  query,
  itemType,
  extension,
  sort,
  viewMode,
  onPathChange,
}) {
  const socket = useContext(SocketContext);
  const fetchPage=useCallback(async(offset,signal)=>{
    const {data}=await axios.get(apiRoutes.searchFiles,{params:{q:query,item_type:itemType,extension,sort,limit:50,offset},signal});
    return {items:data.data||[],total:data.meta?.estimated_total_hits||0};
  },[query,itemType,extension,sort]);
  const pages=useInfinitePages(fetchPage,getResultKey,{onReset:()=>{if(scrollRef.current)scrollRef.current.scrollTop=0;}});
  const {items:results}=pages;
  const [range,setRange]=useState([0,20]);
  const onRange=useCallback((start,end)=>setRange(old=>old[0]===start&&old[1]===end?old:[start,end]),[]);
  const visibleKeys=results.slice(range[0],range[1]).map(getResultKey).join(',');

  useEffect(() => {
    const torrentResults = results.slice(range[0],range[1]).filter((result) => result.is_torrent_root);

    torrentResults.forEach((torrent) => {
      const torrentKey = getTorrentKey(torrent);
      if (!torrentKey) return;

      socket.on(socketRoutes.stcTorrentPropsUpdate + `/${torrentKey}`, (data) => {
        if (data?.info_hash || data?.url_hash) {
          pages.update((prevResults) =>
            prevResults.map((result) =>
              result.is_torrent_root && getTorrentKey(result) === getTorrentKey(data)
                ? { ...result, ...data }
                : result
            )
          );
        }
      });
    });

    return () => {
      torrentResults.forEach((torrent) => {
        const torrentKey = getTorrentKey(torrent);
        if (!torrentKey) return;
        socket.off(socketRoutes.stcTorrentPropsUpdate + `/${torrentKey}`);
      });
    };
  }, [visibleKeys, socket, pages.update]);

  const navigateToResult = (result) => {
    const relativePath = String(result?.relative_path || "");
    if (!relativePath) return;

    if (result.item_type === "directory") {
      onPathChange(
        `/downloads/${
          result.is_torrent_root ? result.directory_path || relativePath : relativePath
        }`
      );
      return;
    }

    const directoryPath = relativePath.split("/").slice(0, -1).join("/");
    onPathChange(`/downloads/${directoryPath}`, result.name);
  };

  const handleTorrentClick = (torrent) => {
    state?.set({
      hoveredTorrentInfoHash: getTorrentKey(torrent),
      activeTorrent: torrent,
    });
    navigateToResult(torrent);
  };

  const handleTorrentMouseEnter = (torrent) => {
    state?.set({
      hoveredTorrentInfoHash: getTorrentKey(torrent),
      hoveredTorrent: torrent,
    });
  };

  const renderTorrentResult = (result, compact) => (
    <div
      key={result.id}
      onClick={() => handleTorrentClick(result)}
      onMouseEnter={() => handleTorrentMouseEnter(result)}
      className={`cursor-pointer ${compact ? "w-full min-w-0" : "rounded-xl"}`}
    >
      <TorrentCard torrentData={result} compact={compact} />
    </div>
  );

  return <InfiniteMediaList {...pages} scrollRef={scrollRef} viewMode={viewMode} mobileColumns={3} itemKey={getResultKey} onRange={onRange} renderItem={result=>result.is_torrent_root?renderTorrentResult(result,viewMode==='grid'):viewMode==='grid'?<SearchGridCard result={result} onClick={()=>navigateToResult(result)}/>:<button type="button" className="flex w-full min-w-0 items-center gap-3 rounded-xl border border-neutral-200 bg-neutral-100 p-3 text-left dark:border-neutral-800 dark:bg-black" onClick={()=>navigateToResult(result)}>
    <ResultIcon type={result.item_type}/><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{result.name}</p><p className="mt-1 truncate text-xs opacity-75">{result.torrent_title||'Download'}</p></div><span className="shrink-0 text-xs opacity-75">{formatFileSize(result.size||0)}</span>
  </button>}/>;
}
