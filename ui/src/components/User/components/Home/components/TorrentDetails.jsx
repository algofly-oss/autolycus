import React from "react";
import { formatFileSize, getQuality } from "@/shared/utils/fileUtils";
import { formatTimeRemaining } from "@/shared/utils/timeUtils";
import { FiDownload } from "react-icons/fi";
import { MdContentCopy } from "react-icons/md";
import useToast from "@/shared/hooks/useToast";

export default function TorrentDetails({ torrent }) {
  if (!torrent) {
    return null;
  }
  const toast = useToast();
  const { resolution, source } = getQuality(torrent.name);
  const remainingBytes = torrent.total_bytes - torrent.downloaded_bytes;
  const timeLeftSeconds =
    torrent.download_speed > 0 ? remainingBytes / torrent.download_speed : 0;

  const copyMagnetToClipBoard = () => {
    if (torrent?.magnet) {
      const el = document.createElement("textarea");
      el.value = torrent?.magnet;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      toast.success("Magnet copied to clipboard");
    }
  };

  return (
    <div className="p-6 text-gray-800 dark:text-gray-200">
      <toast.Toaster />
      <h2 className="text-xl font-bold mb-6 break-words">{torrent.name}</h2>

      {/* Progress Bar for downloading torrents */}
      {!torrent.is_finished && (
        <div className="mb-6">
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
            <div
              className="bg-blue-500 h-2.5 rounded-full transition-all duration-300"
              style={{ width: `${torrent?.progress}%` }}
            ></div>
          </div>
          <div className="text-sm text-center mt-2">{torrent?.progress}%</div>
        </div>
      )}

      {/* Quality Information */}
      <div className="mb-6">
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
      </div>

      {/* Transfer Information */}
      <div className="mb-6">
        <div className="flex items-center space-x-2 mb-2">
          <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400">
            Magnet URI
          </h3>
          <MdContentCopy
            size={15}
            className="cursor-pointer active:translate-y-0.5"
            onClick={copyMagnetToClipBoard}
          />
        </div>
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
              {formatFileSize(torrent.downloaded_bytes)}
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
                    {formatFileSize(torrent.download_speed)}/s
                  </p>
                </div>
              </div>
              <div>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  Time Remaining
                </span>
                <p className="font-medium">
                  {formatTimeRemaining(timeLeftSeconds)}
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
