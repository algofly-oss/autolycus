import { formatFileSize, getFileType } from "@/shared/utils/fileUtils";
import FileIcon from "./FileIcon";
import FileMenu from "./FileMenu";
import { FiCopy, FiTrash2, FiDownload, FiStopCircle } from "react-icons/fi";
import { HiOutlineLink } from "react-icons/hi";
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
import {
  CLIPBOARD_COPY_STATUS,
  copyTextToClipboard,
} from "@/shared/utils/clipboard";

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

const generatePublicKey = () => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `${Date.now().toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 14)}`;
};

const FileItem = ({
  item,
  initialPath,
  handleItemClick,
  fetchData,
  setCopiedItem,
  setDeleteDialog,
  setRenameDialog,
  isSelected = false,
}) => {
  const socket = useContext(SocketContext);
  const toast = useToast();
  const [transcodingProgress, setTranscodingProgress] = useState({
    progress: 0,
    eta: 0,
  });
  const [archiveOperation, setArchiveOperation] = useState(null);
  const itemArchiveOperation =
    item.archive_status === "queued" || item.archive_status === "running"
      ? {
          path: `${initialPath}/${item.name}`.replace(/^\/downloads\/*/, ""),
          label: item.is_directory ? "Creating ZIP" : "Extracting",
          progress: item.archive_progress || 0,
          eta: item.archive_eta || 0,
        }
      : null;
  const displayedArchiveOperation = archiveOperation || itemArchiveOperation;
  const sizeLabel =
    item.is_partial && item.total_size
      ? `${formatFileSize(item.size || 0)} / ${formatFileSize(item.total_size)}`
      : formatFileSize(item.size || 0);

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
      ...(getFileType(item.name) === "video"
        ? [
            {
              name: "Copy Link",
              icon: HiOutlineLink,
              action: "copy_link",
            },
          ]
        : []),
      ...(item.is_directory
        ? [{ name: "Archive", icon: FaRegFileArchive, action: "archive" }]
        : [
            ...(isArchiveFile(item.name)
              ? [{ name: "Extract", icon: FaRegFileArchive, action: "extract" }]
              : []),
            { name: "Download", icon: FiDownload, action: "download" },
          ]),
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

  const isArchiveFile = (name) =>
    /\.(7z|zip|rar|tar|gz|tgz|bz2|tbz|tbz2|xz|txz|zst|iso|cab|arj|lzh|lha|wim|xar|jar|apk|deb|rpm|cpio|dmg|vhd|vmdk)$/i.test(
      name
    );

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

  const generatePublicUrl = (initialPath, item) => {
    const filePath = `${initialPath}/${item?.name}`;
    const publicKey = item?.public_url_key || generatePublicKey();
    const url = `${window.location.origin}/api/files/public/${publicKey}`;

    copyTextToClipboard(url).then((status) => {
      if (status === CLIPBOARD_COPY_STATUS.COPIED) {
        toast.success("Link copied to clipboard");
      } else if (status === CLIPBOARD_COPY_STATUS.MANUAL) {
        toast.success("Link opened for manual copy");
      } else {
        toast.error("Failed to copy link");
      }
    });

    const payload = { path: filePath };
    if (!item?.public_url_key) {
      payload.key = publicKey;
    }

    axios
      .post(apiRoutes?.generatePublicUrl, payload)
      .catch((err) => {
        toast.error("Copied link could not be activated");
      });
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
      case "copy_link":
        generatePublicUrl(initialPath, item);
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
          const path = `${initialPath}/${item.name}`.replace(
            /^\/downloads\/*/,
            ""
          );
          const response = await axios.post(
            `${apiRoutes.archiveDir}?path=${encodeURIComponent(path)}`
          );
          setArchiveOperation({ path, label: "Creating ZIP", progress: 0 });
          toast.success(`ZIP creation started (${response.data.task_id})`);
        } catch (err) {
          toast.error(err.response?.data?.detail || "Failed to start ZIP creation");
        }
        break;
      case "extract":
        try {
          const path = `${initialPath}/${item.name}`.replace(
            /^\/downloads\/*/,
            ""
          );
          const response = await axios.post(
            `${apiRoutes.extractArchive}?path=${encodeURIComponent(path)}`
          );
          setArchiveOperation({ path, label: "Extracting", progress: 0 });
          toast.success(`Extraction started (${response.data.task_id})`);
        } catch (err) {
          toast.error(err.response?.data?.detail || "Failed to start extraction");
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
            `${apiRoutes.transcodeProgress}?path=${encodeURIComponent(
              `${initialPath}/${item.name}`
            )}&stream=true`,
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

  useEffect(() => {
    if (!archiveOperation && itemArchiveOperation) {
      setArchiveOperation(itemArchiveOperation);
    }
  }, [item.archive_status, item.name, initialPath]);

  useEffect(() => {
    if (!archiveOperation) return undefined;

    let active = true;
    const checkProgress = async () => {
      try {
        const response = await axios.get(
          `${apiRoutes.archiveProgress}?path=${encodeURIComponent(
            archiveOperation.path
          )}`
        );
        if (!active) return;
        const progress = response.data;
        setArchiveOperation((current) =>
          current
            ? {
                ...current,
                progress: progress.progress || 0,
                eta: progress.eta || 0,
              }
            : current
        );
        if (progress.status === "complete") {
          toast.success(`${archiveOperation.label} complete`);
          setArchiveOperation(null);
          fetchData();
        } else if (progress.status === "failed") {
          toast.error(progress.error || `${archiveOperation.label} failed`);
          setArchiveOperation(null);
          fetchData();
        }
      } catch {
        // The next poll normally succeeds; avoid flashing an error for a transient request.
      }
    };

    checkProgress();
    const interval = setInterval(checkProgress, 1000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [archiveOperation?.path]);

  return (
    <div
      key={item.name}
      onClick={() => handleItemClick(item)}
      className={`py-4 px-4 rounded-lg border cursor-pointer transition-colors ${
        isSelected
          ? "border-blue-500/50 bg-blue-500/10 dark:border-blue-400/40 dark:bg-blue-400/10"
          : "dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
      }`}
    >
      <div className="flex min-w-0 items-center gap-3">
        <FileIcon item={item} />
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="font-medium truncate">{item.name}</div>

            {item.is_transcoding ? (
              <div className="mt-2">
                <ProgressBar
                  progress={transcodingProgress.progress}
                  showLabel={false}
                  progress_height={"h-1.5"}
                />
                <div className="text-sm text-gray-500 mt-1">
                  {typeof transcodingProgress.progress === "number"
                    ? transcodingProgress.progress.toFixed(2)
                    : "0.00"}
                  % {"•"} ETA {formatTimeRemaining(transcodingProgress.eta)}{" "}
                  {"•"} {formatFileSize(transcodingProgress?.file_size)}
                </div>
              </div>
            ) : displayedArchiveOperation ? (
              <div className="mt-2">
                <ProgressBar
                  progress={Math.max(displayedArchiveOperation.progress || 0, 0.5)}
                  showLabel={false}
                  progress_height={"h-1.5"}
                />
                <div className="text-sm text-gray-500 mt-1">
                  {displayedArchiveOperation.label}{" "}
                  {displayedArchiveOperation.progress || 0}%
                  {displayedArchiveOperation.progress > 0 ? (
                    <>
                      {" • "} ETA {formatTimeRemaining(displayedArchiveOperation.eta || 0)}
                    </>
                  ) : (
                    " • Starting…"
                  )}
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-500">
                {sizeLabel}
                {item.is_partial ? (
                  <span className="ml-2 text-[11px] font-medium text-yellow-600 dark:text-yellow-400">
                    Downloading
                  </span>
                ) : null}
              </div>
            )}
          </div>
          <div
            className="flex h-8 w-8 shrink-0 items-center justify-center"
            onClick={(event) => event.stopPropagation()}
          >
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
