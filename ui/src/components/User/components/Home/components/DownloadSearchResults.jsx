import { Fragment, useContext, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { FiFile, FiFolder, FiLoader } from "react-icons/fi";
import { BsCircleFill } from "react-icons/bs";
import apiRoutes from "@/shared/routes/apiRoutes";
import { formatFileSize, getQuality } from "@/shared/utils/fileUtils";
import Pagination from "./Pagination";
import TorrentCard from "./TorrentCard";
import { SocketContext } from "@/shared/contexts/socket";
import socketRoutes from "@/shared/routes/socketRoutes";

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];
const getTorrentKey = (torrent) => torrent?.info_hash || torrent?.url_hash || torrent?.torrent_id;

function ResultIcon({ type }) {
  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-neutral-200/70 text-neutral-600 dark:bg-neutral-900 dark:text-neutral-400">
      {type === "directory" ? <FiFolder size={19} /> : <FiFile size={19} />}
    </div>
  );
}

function PosterFallback() {
  return (
    <div className="absolute inset-0 bg-neutral-200 dark:bg-neutral-900" />
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
      className="group flex w-full min-w-0 flex-col text-left text-neutral-950 dark:text-white"
      onClick={onClick}
    >
      <div
        className="relative w-full overflow-hidden rounded-md bg-neutral-200 ring-1 ring-neutral-200 transition-[box-shadow,filter] group-hover:shadow-lg group-hover:shadow-blue-500/20 group-hover:brightness-110 dark:bg-neutral-900 dark:ring-neutral-800 dark:group-hover:shadow-blue-950/40"
        style={{ aspectRatio: "2 / 3" }}
      >
        {posterUrl ? (
          <img
            src={posterUrl}
            alt=""
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <PosterFallback />
        )}
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
              : "text-neutral-950 dark:text-white dark:[text-shadow:0_2px_12px_rgba(0,0,0,0.85)]"
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
  query,
  itemType,
  extension,
  sort,
  viewMode,
  onPathChange,
}) {
  const socket = useContext(SocketContext);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [totalItems, setTotalItems] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE_OPTIONS[0]);
  const [pageInput, setPageInput] = useState("1");

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(totalItems / pageSize)),
    [pageSize, totalItems]
  );
  const rangeStart = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const rangeEnd = Math.min(totalItems, currentPage * pageSize);

  useEffect(() => {
    setCurrentPage(1);
  }, [query, itemType, extension, sort]);

  useEffect(() => {
    let cancelled = false;

    const fetchResults = async () => {
      setLoading(true);

      try {
        const response = await axios.get(apiRoutes.searchFiles, {
          params: {
            q: query,
            item_type: itemType,
            extension,
            sort,
            limit: pageSize,
            offset: (currentPage - 1) * pageSize,
          },
        });

        if (!cancelled) {
          setResults(response?.data?.data || []);
          setTotalItems(response?.data?.meta?.estimated_total_hits || 0);
        }
      } catch (error) {
        if (!cancelled) {
          setResults([]);
          setTotalItems(0);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchResults();

    return () => {
      cancelled = true;
    };
  }, [query, itemType, extension, sort, currentPage, pageSize]);

  useEffect(() => {
    setPageInput(String(currentPage));
  }, [currentPage]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  useEffect(() => {
    const torrentResults = results.filter((result) => result.is_torrent_root);

    torrentResults.forEach((torrent) => {
      const torrentKey = getTorrentKey(torrent);
      if (!torrentKey) return;

      socket.on(socketRoutes.stcTorrentPropsUpdate + `/${torrentKey}`, (data) => {
        if (data?.info_hash || data?.url_hash) {
          setResults((prevResults) =>
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
  }, [results, socket]);

  const handlePageButtonClick = (pageNumber) => {
    setCurrentPage(Math.min(Math.max(pageNumber, 1), totalPages));
  };

  const handlePageInputChange = (value) => {
    if (value === "" || /^\d+$/.test(value)) {
      setPageInput(value);
    }
  };

  const applyPageInput = () => {
    if (!pageInput) {
      setPageInput(String(currentPage));
      return;
    }

    const parsedPage = Number(pageInput);
    if (Number.isNaN(parsedPage)) {
      setPageInput(String(currentPage));
      return;
    }

    setCurrentPage(Math.min(Math.max(parsedPage, 1), totalPages));
  };

  const handlePageSizeChange = (value) => {
    const parsedSize = Number(value);
    if (!PAGE_SIZE_OPTIONS.includes(parsedSize)) return;
    setPageSize(parsedSize);
    setCurrentPage(1);
  };

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

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-xl bg-neutral-100 p-8 text-sm text-neutral-500 dark:bg-black dark:text-neutral-400">
        <FiLoader className="animate-spin" size={18} />
        Searching downloads...
      </div>
    );
  }

  if (!results.length) {
    return (
      <div className="p-8 text-center text-sm text-neutral-500 dark:text-neutral-400">
        No matching downloads
      </div>
    );
  }

  if (viewMode === "grid") {
    return (
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-3 items-start gap-x-2.5 gap-y-4 px-1 pt-1 sm:grid-cols-5 lg:grid-cols-6 2xl:grid-cols-8">
          {results.map((result) =>
            result.is_torrent_root ? (
              renderTorrentResult(result, true)
            ) : (
              <SearchGridCard
                key={result.id}
                result={result}
                onClick={() => navigateToResult(result)}
              />
            )
          )}
        </div>
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          pageInput={pageInput}
          pageSize={pageSize}
          pageSizeOptions={PAGE_SIZE_OPTIONS}
          rangeStart={rangeStart}
          rangeEnd={rangeEnd}
          totalItems={totalItems}
          onPageButtonClick={handlePageButtonClick}
          onPageInputChange={handlePageInputChange}
          onApplyPageInput={applyPageInput}
          onPageSizeChange={handlePageSizeChange}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5 pr-1.5">
        {results.map((result) =>
          result.is_torrent_root ? (
            renderTorrentResult(result, false)
          ) : (
            <button
              type="button"
              key={result.id}
              className="flex w-full items-center gap-3 rounded-xl border border-neutral-200 bg-neutral-100 p-3 text-left transition hover:bg-blue-500/10 dark:border-neutral-800 dark:bg-black dark:hover:bg-blue-400/10"
              onClick={() => navigateToResult(result)}
            >
              <ResultIcon type={result.item_type} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold">{result.name}</p>
                <p className="mt-1 truncate text-xs opacity-75">
                  {result.torrent_title || "Download"}
                </p>
              </div>
              <span className="shrink-0 text-xs opacity-75">
                {formatFileSize(result.size || 0)}
              </span>
            </button>
          )
        )}
      </div>
      <Pagination
        currentPage={currentPage}
        totalPages={totalPages}
        pageInput={pageInput}
        pageSize={pageSize}
        pageSizeOptions={PAGE_SIZE_OPTIONS}
        rangeStart={rangeStart}
        rangeEnd={rangeEnd}
        totalItems={totalItems}
        onPageButtonClick={handlePageButtonClick}
        onPageInputChange={handlePageInputChange}
        onApplyPageInput={applyPageInput}
        onPageSizeChange={handlePageSizeChange}
      />
    </div>
  );
}
