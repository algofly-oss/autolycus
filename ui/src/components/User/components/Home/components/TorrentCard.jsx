import React, { useState } from "react";
import { BsCircleFill } from "react-icons/bs";
import { formatFileSize, getQuality } from "@/shared/utils/fileUtils";
import { formatTimeRemaining } from "@/shared/utils/timeUtils";
import InfoBlock from "./InfoBlock";
import ProgressBar from "@/shared/components/ProgressBar/ProgressBar";
import { RxResume, RxPause } from "react-icons/rx";
import axios from "axios";
import apiRoutes from "@/shared/routes/apiRoutes";
import FileMenu from "./FileExplorer/components/FileMenu";
import { FiTrash2 } from "react-icons/fi";
import useToast from "@/shared/hooks/useToast";
import DeleteDialog from "./FileExplorer/components/DeleteDialog";
import { AnimatePresence } from "framer-motion";
import TorrentDeleteDialog from "./TorrentDeleteDialog";
import { BiCopy } from "react-icons/bi";

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

  const toast = useToast();
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

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

  const handleDelete = async () => {
    try {
      const res = await axios.post(apiRoutes.deleteTorrent, {
        info_hash: torrentData.info_hash,
      });
      toast.success("Torrent deleted successfully");
      setIsDeleteDialogOpen(false);
    } catch (err) {
      toast.error("Failed to delete torrent");
      setIsDeleteDialogOpen(false);
    }
  };

  const copyMagnetToClipBoard = async () => {
    if (torrentData?.magnet) {
      const el = document.createElement("textarea");
      el.value = torrentData?.magnet;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      toast.success("Magnet copied to clipboard");
    }
  };

  const actions = [
    {
      name: "Copy Magnet",
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

  return (
    <>
      <div className="bg-neutral-100 hover:bg-blue-600 dark:bg-black hover:dark:bg-blue-700 hover:text-white border dark:border-neutral-800 rounded-xl p-3 flex flex-col gap-3">
        <div>
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold dark:text-white truncate">
              {name}
            </h3>
            <FileMenu
              item={torrentData}
              onAction={handleFileAction}
              actions={actions}
            />
          </div>
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
            <ProgressBar
              progress={progress}
              is_paused={is_paused}
              progress_height={"h-2.5"}
            />
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
