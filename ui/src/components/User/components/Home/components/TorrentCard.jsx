import React from "react";
import { BsCircleFill } from "react-icons/bs";
import { formatFileSize, getQuality } from "@/shared/utils/fileUtils";
import { formatTimeRemaining } from "@/shared/utils/timeUtils";
import InfoBlock from "./InfoBlock";
import ProgressBar from "@/shared/components/ProgressBar/ProgressBar";
import { RxResume, RxPause } from "react-icons/rx";
import axios from "axios";
import apiRoutes from "@/shared/routes/apiRoutes";

const TorrentCard = ({ torrentData }) => {
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

  const resumeTorrent = () => {
    axios
      .post(apiRoutes.resumeTorrent + `?info_hash=${info_hash}`)
      .then((res) => {
        // console.log(res);
      })
      .catch((err) => {});
  };

  const pauseTorrent = () => {
    axios
      .post(apiRoutes.pauseTorrent + `?info_hash=${info_hash}`)
      .then((res) => {
        // console.log(res);
      })
      .catch((err) => {});
  };

  return (
    <div className="bg-neutral-100 hover:bg-blue-600 dark:bg-black hover:dark:bg-blue-700 hover:text-white border dark:border-neutral-800 rounded-xl p-3 flex flex-col gap-3">
      <div>
        <h3 className="text-lg font-semibold dark:text-white truncate">
          {name}
        </h3>
        <div className="flex items-center gap-2">
          {resolution && <span className="text-sm">{resolution}</span>}
          {resolution && source && (
            <BsCircleFill className="w-1 h-1 flex-shrink-0" />
          )}
          {source && <span className="text-sm">{source}</span>}
          {(resolution || source) && total_bytes && (
            <BsCircleFill className="w-1 h-1 flex-shrink-0" />
          )}
          {total_bytes && (
            <span className="text-sm">{formatFileSize(total_bytes)}</span>
          )}
        </div>
      </div>

      {!is_finished && (
        <>
          <ProgressBar progress={progress} is_paused={is_paused} />
          <div className="flex flex-1 w-full gap-3">
            {is_paused ? (
              <button
                className="flex-1 bg-green-500 dark:bg-green-700 rounded-lg p- cursor-pointer active:opacity-80"
                onClick={resumeTorrent}
              >
                <div className="flex items-center justify-center space-x-2 w-full h-full text-neutral-100 dark:text-neutral-200">
                  <RxResume size={22} />
                  <p className="text-lg">Resume</p>
                </div>
              </button>
            ) : (
              <button
                className="flex-1 bg-rose-500 dark:bg-rose-800 rounded-lg p- cursor-pointer active:opacity-80"
                onClick={pauseTorrent}
              >
                <div className="flex items-center justify-center space-x-1 w-full h-full text-neutral-100 dark:text-neutral-200">
                  <RxPause size={22} />
                  <p className="text-lg">Pause</p>
                </div>
              </button>
            )}

            <InfoBlock
              title="Speed"
              value={`${formatFileSize(download_speed)}/s`}
            />

            <InfoBlock
              title="Downloaded"
              value={formatFileSize(downloaded_bytes)}
            />
            <InfoBlock
              title="Time Remaining"
              value={formatTimeRemaining(timeLeftSeconds)}
            />
          </div>
        </>
      )}
    </div>
  );
};

export default TorrentCard;
