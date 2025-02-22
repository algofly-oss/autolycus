import { formatFileSize, getFileType } from "@/shared/utils/fileUtils";
import FileIcon from "./FileIcon";
import FileMenu from "./FileMenu";
import { FiCopy, FiTrash2, FiDownload } from "react-icons/fi";
import { BsBoxArrowRight } from "react-icons/bs";
import { FaRegFileArchive } from "react-icons/fa";
import { MdDriveFileRenameOutline } from "react-icons/md";
import { RiMovie2Line } from "react-icons/ri";
import { useContext, useEffect, useState } from "react";
import socketRoutes from "@/shared/routes/socketRoutes";
import { SocketContext } from "@/shared/contexts/socket";
import axios from "axios";
import apiRoutes from "@/shared/routes/apiRoutes";
import ProgressBar from "@/shared/components/ProgressBar/ProgressBar";
import { formatTimeRemaining } from "@/shared/utils/timeUtils";

const FileItem = ({
  item,
  handleFileAction,
  initialPath,
  handleItemClick,
  fetchData,
}) => {
  const socket = useContext(SocketContext);
  const [transcodingProgress, setTranscodingProgress] = useState({
    progress: 0,
    eta: 0,
  });

  const actions = [
    { name: "Copy", icon: FiCopy, action: "copy" },
    { name: "Move", icon: BsBoxArrowRight, action: "move" },
    { name: "Delete", icon: FiTrash2, action: "delete" },
    { name: "Rename", icon: MdDriveFileRenameOutline, action: "rename" },
    ...(item.is_directory
      ? [{ name: "Archive", icon: FaRegFileArchive, action: "archive" }]
      : [{ name: "Download", icon: FiDownload, action: "download" }]),
    ...(getFileType(item.name) === "video"
      ? [
          {
            name: "Transcode",
            icon: RiMovie2Line,
            action: "transcode",
            subMenu: [
              { name: "360p", action: "transcode_360p" },
              { name: "480p", action: "transcode_480p" },
              { name: "720p", action: "transcode_720p" },
              { name: "1080p", action: "transcode_1080p" },
            ],
          },
        ]
      : []),
  ];

  useEffect(() => {
    const controller = new AbortController();
    const signal = controller.signal;

    const fetchProgress = async () => {
      try {
        if (item.is_transcoding) {
          const response = await fetch(
            `${apiRoutes.transcodeProgress}?path=${initialPath}/${item.name}&stream=true`,
            { method: "POST", signal }
          );

          if (response.ok) {
            try {
              const data = await response.json();
              console.log(data);
              if (data === 1) {
                // TODO: instead of fetching again, we can also update the state to set `is_transcoding = False`
                fetchData();
              }
            } catch (responseError) {
              if (responseError.message === "Failed to fetch") {
                fetchProgress();
              } else if (
                responseError.message === "The user aborted a request."
              ) {
                // console.log("fetch aborted");
              } else {
                console.log(responseError.message);
              }
            }
          }
        }
      } catch (error) {}
    };

    fetchProgress();

    return () => {
      controller.abort();
    };
  }, [item.is_transcoding, initialPath, item.name]);

  useEffect(() => {
    if (item.is_transcoding) {
      const socketRoute = `${socketRoutes.stcTranscodingProgress}/${initialPath}/${item.name}`;
      socket.on(socketRoute, (data) => {
        if (data) {
          setTranscodingProgress(data);
        }
      });
      return () => {
        socket.off(socketRoute);
      };
    }
  }, []);

  return (
    <div
      key={item.name}
      onClick={() => handleItemClick(item)}
      className="py-4 px-4 rounded-lg border dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
    >
      <div className="flex items-center gap-3">
        <FileIcon item={item} />
        <div className="truncate flex w-full items-center justify-between">
          <div className="flex flex-col w-[95%]">
            <div className="font-medium truncate">{item.name}</div>

            {item.is_transcoding ? (
              <div className="mt-2">
                <ProgressBar
                  progress={transcodingProgress.progress}
                  showLabel={false}
                  progress_height={"h-1.5"}
                />
                <div className="text-sm text-gray-500 mt-1">
                  {transcodingProgress.progress}% - Time Remaining{" "}
                  {formatTimeRemaining(transcodingProgress.eta)}
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-500">
                {formatFileSize(item.size)}
              </div>
            )}
          </div>
          <div className="w-[5%]">
            <FileMenu
              item={item}
              onAction={handleFileAction}
              actions={actions}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default FileItem;
