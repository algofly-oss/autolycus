import { formatFileSize, getFileType } from "@/shared/utils/fileUtils";
import FileIcon from "./FileIcon";
import FileMenu from "./FileMenu";
import { FiCopy, FiTrash2, FiDownload, FiStopCircle } from "react-icons/fi";
import { BsBoxArrowRight } from "react-icons/bs";
import { FaRegFileArchive } from "react-icons/fa";
import { MdDriveFileRenameOutline } from "react-icons/md";
import { RiMovie2Line } from "react-icons/ri";
import { useContext, useEffect, useState } from "react";
import socketRoutes from "@/shared/routes/socketRoutes";
import { SocketContext } from "@/shared/contexts/socket";
import apiRoutes from "@/shared/routes/apiRoutes";
import ProgressBar from "@/shared/components/ProgressBar/ProgressBar";
import { formatTimeRemaining } from "@/shared/utils/timeUtils";
import axios from "axios";
import useToast from "@/shared/hooks/useToast";

const TRANSCODE_RESOLUTIONS = [
  { name: "Low 144p", action: "transcode_144p" },
  { name: "SD 240p", action: "transcode_240p" },
  { name: "SD 360p", action: "transcode_360p" },
  { name: "SD 480p", action: "transcode_480p" },
  { name: "HD 720p", action: "transcode_720p" },
  { name: "FHD 1080p", action: "transcode_1080p" },
  { name: "2K 1440p", action: "transcode_1440p" },
  { name: "4K 2160p", action: "transcode_2160p" },
];

const DEFAULT_ACTIONS = [
  { name: "Copy", icon: FiCopy, action: "copy" },
  { name: "Move", icon: BsBoxArrowRight, action: "move" },
  { name: "Delete", icon: FiTrash2, action: "delete" },
  { name: "Rename", icon: MdDriveFileRenameOutline, action: "rename" },
];

const FileItem = ({
  item,
  initialPath,
  handleItemClick,
  fetchData,
  setCopiedItem,
  setDeleteDialog,
  setRenameDialog,
  setArchiving,
}) => {
  const socket = useContext(SocketContext);
  const toast = useToast();
  const [transcodingProgress, setTranscodingProgress] = useState({
    progress: 0,
    eta: 0,
  });

  const getActions = () => {
    // if item is being transcoded, only show stop button
    if (item.is_transcoding) {
      return [
        {
          name: "Terminate",
          icon: FiStopCircle,
          action: "stop_transcode",
        },
      ];
    }

    // show normal actions based on file type
    return [
      ...DEFAULT_ACTIONS,
      ...(item.is_directory
        ? [{ name: "Archive", icon: FaRegFileArchive, action: "archive" }]
        : [{ name: "Download", icon: FiDownload, action: "download" }]),
      ...(getFileType(item.name) === "video" && !item.is_transcoding
        ? [
            {
              name: "Transcode",
              icon: RiMovie2Line,
              action: "transcode",
              subMenu: TRANSCODE_RESOLUTIONS,
            },
          ]
        : []),
    ];
  };

  const handleTranscode = async (resolution) => {
    try {
      const path = `${initialPath}/${item.name}`;
      await axios.post(
        `${apiRoutes.transcodeStart}?path=${encodeURIComponent(
          path
        )}&resolution=${resolution}`
      );
      toast.success("Transcoding started");
      fetchData();
    } catch (error) {
      toast.error("Failed to process transcoding request.");
    }
  };

  const handleStopTranscode = async () => {
    try {
      const path = `${initialPath}/${item.name}`;
      await axios.post(
        `${apiRoutes.transcodeStop}?path=${encodeURIComponent(path)}`
      );
      toast.success("Transcoding stopped");
      fetchData();
    } catch (error) {
      toast.error("Failed to stop transcoding.");
    }
  };

  const handleFileAction = async (action, item) => {
    switch (action) {
      case "copy":
        setCopiedItem({ ...item, sourcePath: initialPath, action: "copy" });
        toast.success("Item copied to clipboard");
        break;
      case "move":
        setCopiedItem({ ...item, sourcePath: initialPath, action: "move" });
        toast.success("Item ready to move");
        break;
      case "delete":
        setDeleteDialog({ open: true, item });
        break;
      case "download":
        try {
          const path = `${initialPath}/${item.name}`.replace(
            /^\/downloads\/*/,
            ""
          );
          const downloadUrl = `${
            apiRoutes.streamFile
          }?path=${encodeURIComponent(path)}&download=true`;

          const link = document.createElement("a");
          link.href = downloadUrl;
          link.download = item.name;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);

          toast.success("Download started");
        } catch (err) {
          toast.error("Failed to start download");
        }
        break;
      case "archive":
        try {
          setArchiving(true);
          const path = `${initialPath}/${item.name}`.replace(
            /^\/downloads\/*/,
            ""
          );

          await axios.post(
            `${apiRoutes.archiveDir}?path=${encodeURIComponent(path)}`
          );
          toast.success("Directory archived successfully");
        } catch (err) {
          toast.error("Failed to archive directory");
        } finally {
          setArchiving(false);
          fetchData();
        }
        break;
      case "rename":
        setRenameDialog({ open: true, item });
        break;
      case "stop_transcode":
        await handleStopTranscode();
        break;
      default:
        // Handle transcoding actions
        if (action.startsWith("transcode_")) {
          const resolution = action.split("_")[1];
          await handleTranscode(resolution);
        }
        break;
    }
  };

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
              if (data === 1) {
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
              actions={getActions()}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default FileItem;
