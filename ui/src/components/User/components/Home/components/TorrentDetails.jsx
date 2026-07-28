import React, { useEffect, useState } from "react";
import { formatFileSize, getQuality } from "@/shared/utils/fileUtils";
import { formatTimeRemaining } from "@/shared/utils/timeUtils";
import { FiDownload } from "react-icons/fi";
import useToast from "@/shared/hooks/useToast";
import reactState from "@/shared/hooks/reactState";
import { MdContentCopy } from "react-icons/md";
import {
  CLIPBOARD_COPY_STATUS,
  copyTextToClipboard,
} from "@/shared/utils/clipboard";
import FileFallback from "./FileFallback";

export default function TorrentDetails({ torrent }) {
  const torrentState = reactState({});
  const toast = useToast();

  useEffect(() => {
    if (!torrent) {
      return;
    }

    torrentState.set({
      remainingBytes: torrent.total_bytes - torrent.downloaded_bytes,
      timeLeftSeconds:
        torrent.download_speed > 0
          ? (torrent.total_bytes - torrent.downloaded_bytes) /
          torrent.download_speed
          : 0,
      torrentProgress: torrent?.progress,
      latestTorrentData: {},
      downloadedBytes: torrent?.downloaded_bytes,
      downloadSpeed: torrent?.download_speed,
    });
  }, [torrent]);

  if (!torrent) {
    return (
      <div className="p-6 text-gray-500 dark:text-gray-400">
        <h2 className="text-lg font-semibold text-gray-700 dark:text-gray-200">
          Torrent Details
        </h2>
        <p className="mt-3 text-sm leading-relaxed">
          Hover a torrent to preview its quality, magnet, and transfer
          information here.
        </p>
      </div>
    );
  }

  const { resolution, source } = getQuality(torrent.name);
  const posterUrl = torrent?.media_metadata?.poster_url;
  const imdbUrl = torrent?.media_metadata?.imdb_url;

  const copyMagnetToClipBoard = async () => {
    if (!torrent?.magnet) {
      toast.error("Magnet not found");
      return;
    }

    const status = await copyTextToClipboard(torrent.magnet);

    if (status === CLIPBOARD_COPY_STATUS.COPIED) {
      toast.success("Magnet copied to clipboard");
    } else if (status === CLIPBOARD_COPY_STATUS.MANUAL) {
      toast.success("Magnet opened for manual copy");
    } else {
      toast.error("Failed to copy magnet");
    }
  };

  const copyImdbToClipBoard = async () => {
    if (!imdbUrl) {
      toast.error("IMDb URL not found");
      return;
    }

    const status = await copyTextToClipboard(imdbUrl);

    if (status === CLIPBOARD_COPY_STATUS.COPIED) {
      toast.success("IMDb URL copied to clipboard");
    } else if (status === CLIPBOARD_COPY_STATUS.MANUAL) {
      toast.success("IMDb URL opened for manual copy");
    } else {
      toast.error("Failed to copy IMDb URL");
    }
  };

  return (
    <div className="p-6 text-gray-800 dark:text-gray-200">
      <div className="relative mb-5 w-full overflow-hidden rounded-lg" style={{ aspectRatio: "2 / 3" }}>
        <FileFallback />
        {posterUrl ? (
          <img
            src={posterUrl}
            alt=""
            className="relative h-full w-full rounded-lg object-cover"
            loading="lazy"
            onError={(event) => {
              event.currentTarget.style.display = "none";
            }}
          />
        ) : null}
        </div>

      <h2 className="mb-6 break-words text-lg font-semibold leading-6 text-gray-900 dark:text-gray-100">
        {torrent.name}
      </h2>

      {/* Progress Bar for downloading torrents */}
      {/* {!torrent.is_finished && (
        <div className="mb-6">
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
            <div
              className="bg-blue-500 h-2.5 rounded-full transition-all duration-300"
              style={{ width: `${torrent?.progress}%` }}
            ></div>
          </div>
          <div className="text-sm text-center mt-2">
            {torrentState.get("torrentProgress")}%
          </div>
        </div>
      )} */}

      {/* Quality Information */}
      {resolution && source && <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-2">
          Quality Info
        </h3>
        <div className="grid grid-cols-2 gap-4">
          {resolution && (
            <div>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Resolution
              </span>
              <p className="font-medium">{resolution}</p>
            </div>
          )}
          {source && (
            <div>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Source
              </span>
              <p className="font-medium">{source}</p>
            </div>
          )}
        </div>
      </div>}

      {/* Magnet URI */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400">
          Magnet URI
        </h3>
        <div className="flex items-center space-x-2 mb-2">
          <span
            className="flex-1 text-sm truncate font-medium"
            title={torrent.magnet} // Tooltip to show the full URI on hover
          >
            {torrent.magnet}
          </span>
          <MdContentCopy onClick={copyMagnetToClipBoard} className="cursor-pointer"/>
        </div>
      </div>

      {imdbUrl ? (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400">
            IMDb
          </h3>
          <div className="flex items-center space-x-2 mb-2">
            <a
              href={imdbUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 truncate text-sm font-medium transition-colors hover:text-blue-600 dark:hover:text-blue-300"
              title={imdbUrl}
            >
              {imdbUrl}
            </a>
            <MdContentCopy
              onClick={copyImdbToClipBoard}
              className="cursor-pointer"
            />
          </div>
        </div>
      ) : null}

      {/* Transfer Information */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-2">
          Transfer Info
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Total Size
            </span>
            <p className="font-medium">{formatFileSize(torrent.total_bytes)}</p>
          </div>
          <div>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Downloaded
            </span>
            <p className="font-medium">
              {formatFileSize(torrentState.get("downloadedBytes"))}
            </p>
          </div>
          {!torrent.is_finished && (
            <>
              <div>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  Download Speed
                </span>
                <div className="flex items-center gap-2">
                  <FiDownload className="text-green-500" />
                  <p className="font-medium">
                    {formatFileSize(torrentState.get("downloadSpeed"))}/s
                  </p>
                </div>
              </div>
              <div>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  Time Remaining
                </span>
                <p className="font-medium">
                  {formatTimeRemaining(torrentState.get("timeLeftSeconds"))}
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
