import React, { useState } from "react";
import { BsCircleFill } from "react-icons/bs";
import { formatFileSize, getQuality } from "@/shared/utils/fileUtils";
import { formatTimeRemaining } from "@/shared/utils/timeUtils";
import { RxResume, RxPause } from "react-icons/rx";
import axios from "axios";
import apiRoutes from "@/shared/routes/apiRoutes";
import FileMenu from "./FileExplorer/components/FileMenu";
import { FiTrash2 } from "react-icons/fi";
import useToast from "@/shared/hooks/useToast";
import { AnimatePresence } from "framer-motion";
import TorrentDeleteDialog from "./TorrentDeleteDialog";
import { BiCopy } from "react-icons/bi";
import {
  CLIPBOARD_COPY_STATUS,
  copyTextToClipboard,
} from "@/shared/utils/clipboard";

const extractEpisodeInfo = (value) => {
  const text = String(value || "");
  const seasonEpisodeMatch = text.match(/\bS(\d{1,2})E(\d{1,3})\b/i);
  if (seasonEpisodeMatch) {
    return `S${seasonEpisodeMatch[1].padStart(2, "0")}E${seasonEpisodeMatch[2].padStart(2, "0")}`;
  }

  const seasonMatch = text.match(/\bS(?:eason)?[\s._-]*(\d{1,2})\b/i);
  if (seasonMatch) {
    return `S${seasonMatch[1].padStart(2, "0")}`;
  }

  return null;
};

const extractYearInfo = (value) => {
  const match = String(value || "").match(/\b(19\d{2}|20\d{2})\b/);
  return match ? match[1] : null;
};

const extractLanguageInfo = (value) => {
  const text = String(value || "").toLowerCase();
  const languages = [
    ["hindi", "Hindi"],
    ["english", "English"],
    ["kannada", "Kannada"],
    ["tamil", "Tamil"],
    ["telugu", "Telugu"],
    ["malayalam", "Malayalam"],
    ["marathi", "Marathi"],
    ["bengali", "Bengali"],
    ["punjabi", "Punjabi"],
    ["gujarati", "Gujarati"],
    ["urdu", "Urdu"],
    ["japanese", "Japanese"],
    ["korean", "Korean"],
    ["chinese", "Chinese"],
    ["spanish", "Spanish"],
    ["french", "French"],
    ["german", "German"],
    ["russian", "Russian"],
    ["italian", "Italian"],
    ["latino", "Latino"],
  ];

  const found = languages
    .filter(([keyword]) => new RegExp(`\\b${keyword}\\b`, "i").test(text))
    .map(([, label]) => label);

  if (found.length >= 2 && /\b(dual|multi)\s*audio\b/i.test(value || "")) {
    return `${found.slice(0, 2).join(" + ")} Audio`;
  }

  return found.slice(0, 2).join(" + ") || null;
};

const compactDisplayTitle = (title, episodeInfo, languageInfo) =>
  [title, episodeInfo, languageInfo]
    .filter(Boolean)
    .join(" ");

function posterProgressStyle(progress = 0, paused = false) {
  const value = Math.min(Math.max(Math.round(progress || 0), 0), 100);
  if (value <= 0 && !paused) return undefined;

  const color = paused ? "#eab308" : "#3b82f6";
  const muted = "rgba(115,115,115,0.24)";

  return {
    background: `conic-gradient(from 0deg, ${color} 0deg ${value * 3.6}deg, ${muted} ${value * 3.6}deg 360deg)`,
  };
}

function PosterFallback() {
  return (
    <div className="absolute inset-0 bg-neutral-200 dark:bg-neutral-900" />
  );
}

function PosterProgressRing({ progress, isPaused }) {
  const style = posterProgressStyle(progress, isPaused);

  if (!style) return null;

  return (
    <div
      className="pointer-events-none absolute inset-0 z-0 rounded-[7px]"
      style={style}
    />
  );
}

const TorrentCard = ({ torrentData, compact = false }) => {
  const {
    name,
    total_bytes,
    downloaded_bytes,
    download_speed,
    progress,
    is_finished,
    is_paused,
    info_hash,
  } = torrentData;

  const { resolution, source } = getQuality(name);
  const remainingBytes = total_bytes - downloaded_bytes;
  const timeLeftSeconds =
    download_speed > 0 ? remainingBytes / download_speed : 0;

  const toast = useToast();
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

  const resumeTorrent = () => {
    let postfix = `?info_hash=${info_hash}`;
    if (torrentData?.is_direct_download) {
      postfix = `?info_hash=url_hash_${torrentData?.url_hash}`;
    }

    axios
      .post(apiRoutes.resumeTorrent + postfix)
      .then((res) => {
        // console.log(res);
      })
      .catch((err) => {});
  };

  const pauseTorrent = () => {
    let postfix = `?info_hash=${info_hash}`;
    if (torrentData?.is_direct_download) {
      postfix = `?info_hash=url_hash_${torrentData?.url_hash}`;
    }

    axios
      .post(apiRoutes.pauseTorrent + postfix)
      .then((res) => {
        // console.log(res);
      })
      .catch((err) => {});
  };

  const handleDelete = async () => {
    let hash = info_hash;
    if (torrentData?.is_direct_download) {
      hash = `url_hash_${torrentData?.url_hash}`;
    }

    try {
      const res = await axios.post(apiRoutes.deleteTorrent, {
        info_hash: hash,
      });
      toast.success("Torrent deleted successfully");
      setIsDeleteDialogOpen(false);
    } catch (err) {
      toast.error("Failed to delete torrent");
      setIsDeleteDialogOpen(false);
    }
  };

  const copyMagnetToClipBoard = async () => {
    const text = torrentData?.magnet || torrentData?.url;
    if (!text) {
      toast.error("Magnet not found");
      return;
    }

    const status = await copyTextToClipboard(text);
    const label = torrentData?.magnet ? "Magnet" : "URL";

    if (status === CLIPBOARD_COPY_STATUS.COPIED) {
      toast.success(`${label} copied to clipboard`);
    } else if (status === CLIPBOARD_COPY_STATUS.MANUAL) {
      toast.success(`${label} opened for manual copy`);
    } else {
      toast.error(`Failed to copy ${label.toLowerCase()}`);
    }
  };

  const actions = [
    {
      name: torrentData?.is_direct_download ? "Copy URL" : "Copy Magnet",
      icon: BiCopy,
      action: "copy-magnet",
    },
    ...(!is_finished
      ? is_paused
        ? [{ name: "Resume", icon: RxResume, action: "resume" }]
        : [{ name: "Pause", icon: RxPause, action: "pause" }]
      : []),
    {
      name: "Delete Torrent",
      icon: FiTrash2,
      action: "delete",
    },
  ];

  const handleFileAction = (action) => {
    switch (action) {
      case "delete":
        setIsDeleteDialogOpen(true);
        break;
      case "pause":
        pauseTorrent();
        break;
      case "copy-magnet":
        copyMagnetToClipBoard();
        break;
      case "resume":
        resumeTorrent();
        break;
    }
  };

  const resolutionLabel = torrentData?.media_metadata?.quality?.resolution || resolution;
  const sourceLabel = torrentData?.media_metadata?.quality?.source || source;
  const yearLabel = torrentData?.media_metadata?.year || extractYearInfo(name);
  const totalSizeLabel =
    total_bytes || torrentData?.size || (is_finished && downloaded_bytes)
      ? formatFileSize(total_bytes || torrentData.size || downloaded_bytes)
      : null;
  const metadataItems = [
    resolutionLabel,
    is_finished ? totalSizeLabel : null,
    sourceLabel,
  ].filter(Boolean);
  const compactMetadataItems = !is_finished
    ? [
        `${Math.round(progress || 0)}%`,
        resolutionLabel,
        totalSizeLabel,
        sourceLabel,
      ].filter(Boolean)
    : [resolutionLabel, totalSizeLabel, sourceLabel].filter(Boolean);
  const compactEndLabel = sourceLabel;
  const compactInfoItems = compactMetadataItems.filter(
    (item) => item !== compactEndLabel
  );
  const transferSizeLabel =
    !is_finished && total_bytes
      ? `${formatFileSize(downloaded_bytes || 0)} / ${formatFileSize(total_bytes)}`
      : null;
  const parsedTitle = torrentData?.media_metadata?.title;
  const hasParsedTitle = parsedTitle && parsedTitle !== name;
  const parsedDisplayTitle = hasParsedTitle
    ? compactDisplayTitle(
        parsedTitle,
        yearLabel ? `(${yearLabel})` : null,
        extractEpisodeInfo(name),
        extractLanguageInfo(name)
      )
    : name;
  const posterUrl = torrentData?.media_metadata?.poster_url;
  const imdbUrl = torrentData?.media_metadata?.imdb_url;
  const torrentHash = (
    info_hash ||
    torrentData?.url_hash ||
    torrentData?.torrent_id ||
    ""
  )
    .toString();
  const torrentHashLabel = torrentHash.slice(0, 5);

  if (compact) {
    return (
      <>
        <div className="group flex w-full min-w-0 flex-col text-neutral-950 dark:text-white">
          <div
            className="group/poster relative w-full overflow-hidden rounded-md bg-neutral-200 transition-[box-shadow,filter] group-hover:shadow-lg group-hover:shadow-blue-500/20 group-hover:brightness-110 dark:bg-neutral-900 dark:group-hover:shadow-blue-950/40"
            style={{ aspectRatio: "2 / 3" }}
          >
            {!is_finished ? (
              <PosterProgressRing progress={progress} isPaused={is_paused} />
            ) : null}
            <div className="absolute inset-0.5 z-10 overflow-hidden rounded-[5px] bg-neutral-200 ring-1 ring-neutral-200 dark:bg-neutral-900 dark:ring-neutral-800">
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
                <p className="max-h-12 overflow-hidden text-xs font-semibold leading-4 [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:3]">
                  {parsedDisplayTitle}
                </p>
                <div
                  className={`mt-0.5 flex min-h-4 min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0 text-[11px] leading-4 ${
                    posterUrl ? "text-neutral-300" : "text-neutral-500 dark:text-neutral-500"
                  }`}
                >
                  {compactMetadataItems.length ? (
                    <>
                      {compactInfoItems.map((item, index) => (
                        <React.Fragment key={`${item}-${index}`}>
                          {index > 0 ? (
                            <BsCircleFill className="h-1 w-1 shrink-0" />
                          ) : null}
                          <span className="truncate">{item}</span>
                        </React.Fragment>
                      ))}
                      {compactEndLabel ? (
                        <span className="flex shrink-0 items-center gap-1.5">
                          {compactInfoItems.length ? (
                            <BsCircleFill className="h-1 w-1 shrink-0" />
                          ) : null}
                          <span>{compactEndLabel}</span>
                        </span>
                      ) : null}
                      {torrentHashLabel ? (
                        <span
                          className="flex shrink-0 items-center gap-1.5 font-mono font-semibold"
                          title={torrentHash}
                        >
                          {(compactInfoItems.length || compactEndLabel) ? (
                            <BsCircleFill className="h-1 w-1 shrink-0" />
                          ) : null}
                          <span>{torrentHashLabel}</span>
                        </span>
                      ) : null}
                    </>
                  ) : (
                    <>
                      <span className="truncate">Metadata pending</span>
                      {torrentHashLabel ? (
                        <span
                          className="flex shrink-0 items-center gap-1.5 font-mono font-semibold"
                          title={torrentHash}
                        >
                          <BsCircleFill className="h-1 w-1 shrink-0" />
                          <span>{torrentHashLabel}</span>
                        </span>
                      ) : null}
                    </>
                  )}
                </div>
              </div>
              <div
                className="absolute right-1 top-1 z-30 text-white [filter:drop-shadow(0_2px_5px_rgba(0,0,0,0.95))_drop-shadow(0_0_2px_rgba(0,0,0,0.9))]"
                onClick={(event) => event.stopPropagation()}
              >
                <FileMenu
                  item={torrentData}
                  onAction={handleFileAction}
                  actions={actions}
                />
              </div>
              {!is_finished ? (
                <div className="absolute inset-0 z-20 hidden bg-black/55 group-hover/poster:block" />
              ) : null}
              {!is_finished ? (
                <div className="absolute inset-0 z-20 hidden items-center justify-center group-hover/poster:flex">
                  <button
                    type="button"
                    className="flex h-10 w-10 items-center justify-center text-white [filter:drop-shadow(0_5px_18px_rgba(0,0,0,1))_drop-shadow(0_0_8px_rgba(0,0,0,1))]"
                    onClick={(event) => {
                      event.stopPropagation();
                      if (is_paused) {
                        resumeTorrent();
                      } else {
                        pauseTorrent();
                      }
                    }}
                    title={is_paused ? "Resume" : "Pause"}
                    aria-label={is_paused ? "Resume" : "Pause"}
                  >
                    {is_paused ? <RxResume size={24} /> : <RxPause size={24} />}
                  </button>
                </div>
              ) : null}
            </div>
          </div>

          <div className="h-0" aria-hidden="true" />
        </div>

        {isDeleteDialogOpen && (
          <AnimatePresence>
            <TorrentDeleteDialog
              open={isDeleteDialogOpen}
              item={torrentData}
              onClose={() => setIsDeleteDialogOpen(false)}
              onDelete={handleDelete}
            />
          </AnimatePresence>
        )}
      </>
    );
  }

  return (
    <>
      <div
        className={`relative overflow-hidden bg-neutral-100 hover:bg-blue-500/10 dark:bg-black dark:hover:bg-blue-400/10 border dark:border-neutral-800 rounded-xl p-3 flex flex-col gap-3 transition-[background-color,box-shadow] hover:shadow-md dark:hover:shadow-blue-950/20 ${
          compact ? "h-full min-h-[11rem]" : ""
        }`}
      >
        <div className="flex min-w-0 items-center gap-3">
          <div
            className="group relative h-16 w-11 shrink-0 overflow-hidden rounded-md bg-neutral-200 dark:bg-neutral-900"
          >
            {!is_finished ? (
              <PosterProgressRing progress={progress} isPaused={is_paused} />
            ) : null}
            <div className="absolute inset-0.5 z-10 overflow-hidden rounded-[5px] bg-neutral-200 ring-1 ring-neutral-200 dark:bg-neutral-900 dark:ring-neutral-800">
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
              {!is_finished ? (
                <div className="absolute inset-0 flex items-center justify-center group-hover:hidden">
                  <span className="text-[11px] font-semibold text-white [text-shadow:0_2px_8px_rgba(0,0,0,1),0_1px_2px_rgba(0,0,0,1)]">
                    {Math.round(progress || 0)}%
                  </span>
                </div>
              ) : null}
              {!is_finished ? (
                <div className="absolute inset-0 hidden bg-black/55 group-hover:block" />
              ) : null}
              {!is_finished ? (
                <div className="absolute inset-0 hidden items-center justify-center group-hover:flex">
                  <button
                    type="button"
                    className="flex h-7 w-7 items-center justify-center text-white [filter:drop-shadow(0_4px_14px_rgba(0,0,0,1))_drop-shadow(0_0_7px_rgba(0,0,0,1))]"
                    onClick={(event) => {
                      event.stopPropagation();
                      if (is_paused) {
                        resumeTorrent();
                      } else {
                        pauseTorrent();
                      }
                    }}
                    title={is_paused ? "Resume" : "Pause"}
                    aria-label={is_paused ? "Resume" : "Pause"}
                  >
                    {is_paused ? <RxResume size={16} /> : <RxPause size={16} />}
                  </button>
                </div>
              ) : null}
            </div>
          </div>
          <div className="flex min-h-[4rem] min-w-0 flex-1 flex-col justify-center">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <h3 className="truncate text-base font-semibold leading-5 dark:text-white">
                  {parsedDisplayTitle}
                </h3>
                {hasParsedTitle ? (
                  <p className="mt-0.5 truncate text-xs text-neutral-500 dark:text-neutral-500">
                    {name}
                  </p>
                ) : null}
              </div>
              <FileMenu
                item={torrentData}
                onAction={handleFileAction}
                actions={actions}
              />
            </div>
            <div className="mt-2 flex min-w-0 items-center gap-2">
              <div className="min-w-0 flex-1">
                <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                  {!is_finished ? (
                    <button
                      type="button"
                      className={`group/status w-14 shrink-0 truncate rounded px-1.5 py-0.5 text-center text-[11px] font-semibold transition-colors active:opacity-80 ${
                        is_paused
                          ? "bg-rose-500/25 text-rose-800 hover:bg-emerald-500/25 hover:text-emerald-800 dark:bg-rose-500/20 dark:text-rose-300 dark:hover:bg-emerald-500/20 dark:hover:text-emerald-300"
                          : "bg-emerald-500/25 text-emerald-800 hover:bg-rose-500/25 hover:text-rose-800 dark:bg-emerald-500/20 dark:text-emerald-300 dark:hover:bg-rose-500/20 dark:hover:text-rose-300"
                      }`}
                      onClick={(event) => {
                        event.stopPropagation();
                        if (is_paused) {
                          resumeTorrent();
                        } else {
                          pauseTorrent();
                        }
                      }}
                      title={is_paused ? "Resume" : "Pause"}
                      aria-label={is_paused ? "Resume" : "Pause"}
                    >
                      <span className="group-hover/status:hidden">
                        {is_paused ? "Paused" : "Active"}
                      </span>
                      <span className="hidden group-hover/status:inline">
                        {is_paused ? "Resume" : "Pause"}
                      </span>
                    </button>
                  ) : null}
                  {transferSizeLabel ? (
                    <span className="max-w-[12rem] truncate rounded bg-neutral-200/70 px-1.5 py-0.5 text-[11px] font-medium text-neutral-600 dark:bg-neutral-900 dark:text-neutral-400">
                      {transferSizeLabel}
                    </span>
                  ) : null}
                  {metadataItems.slice(0, is_finished ? 4 : 2).map((item, index) => (
                    <span
                      key={`${item}-${index}`}
                      className="max-w-[9rem] truncate rounded bg-neutral-200/70 px-1.5 py-0.5 text-[11px] font-medium text-neutral-600 dark:bg-neutral-900 dark:text-neutral-400"
                    >
                      {item}
                    </span>
                  ))}
                  {imdbUrl ? (
                    <a
                      href={imdbUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0 rounded bg-neutral-200/70 px-1.5 py-0.5 text-[11px] font-semibold text-neutral-600 transition-colors hover:bg-blue-500/15 hover:text-blue-700 dark:bg-neutral-900 dark:text-neutral-400 dark:hover:bg-blue-500/20 dark:hover:text-blue-300"
                      onClick={(event) => event.stopPropagation()}
                      title="Open IMDb"
                    >
                      IMDB
                    </a>
                  ) : null}
                  {!is_finished && !is_paused ? (
                    <span className="max-w-[9rem] shrink-0 truncate rounded bg-neutral-200/70 px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-neutral-600 dark:bg-neutral-900 dark:text-neutral-400">
                      {formatFileSize(download_speed || 0)}/s
                    </span>
                  ) : null}
                  {!is_finished ? (
                    <span className="max-w-[9rem] truncate rounded bg-neutral-200/70 px-1.5 py-0.5 text-[11px] font-medium text-neutral-600 dark:bg-neutral-900 dark:text-neutral-400">
                      {formatTimeRemaining(timeLeftSeconds)}
                    </span>
                  ) : null}
                  {torrentHashLabel ? (
                    <span
                      className="shrink-0 rounded bg-neutral-200/70 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-neutral-600 dark:bg-neutral-900 dark:text-neutral-400"
                      title={torrentHash}
                    >
                      {torrentHashLabel}
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {isDeleteDialogOpen && (
        <AnimatePresence>
          <TorrentDeleteDialog
            open={isDeleteDialogOpen}
            item={torrentData}
            onClose={() => setIsDeleteDialogOpen(false)}
            onDelete={handleDelete}
          />
        </AnimatePresence>
      )}
    </>
  );
};

export default TorrentCard;
