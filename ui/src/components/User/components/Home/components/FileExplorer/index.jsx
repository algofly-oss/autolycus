import React, { useEffect, useState } from "react";
import axios from "axios";
import { FiArrowLeft, FiLoader } from "react-icons/fi";
import { formatFileSize, getFileType } from "@/shared/utils/fileUtils";
import apiRoutes from "@/shared/routes/apiRoutes";
import useToast from "@/shared/hooks/useToast";
import Breadcrumbs from "./components/Breadcrumbs";
import FileMenu from "./components/FileMenu";
import FileIcon from "./components/FileIcon";
import DeleteDialog from "./components/DeleteDialog";
import VideoPlayer from "./components/VideoPlayer";
import { AnimatePresence } from "framer-motion";
import RenameDialog from "./components/RenameDialog";

export default function FileExplorer({ initialPath, onPathChange }) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [videoPlayer, setVideoPlayer] = useState({
    open: false,
    url: "",
    name: "",
  });
  const [deleteDialog, setDeleteDialog] = useState({ open: false, item: null });
  const [renameDialog, setRenameDialog] = useState({ open: false, item: null });
  const [copiedItem, setCopiedItem] = useState(null);
  const [pasting, setPasting] = useState(false);
  const toast = useToast();

  useEffect(() => {
    fetchData();
  }, [initialPath]);

  const fetchData = async () => {
    setLoading(true);
    setError("");
    if (initialPath) {
      try {
        const encodedPath = encodeURIComponent(
          initialPath.replace(/^\/downloads\/*/, "")
        );
        const response = await axios.get(
          `${apiRoutes.browseFiles}?path=${encodedPath}`
        );
        setItems(response.data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
  };

  const handleItemClick = (item) => {
    if (item.is_directory) {
      onPathChange(`${initialPath}/${item.name}`);
    } else {
      const fileType = getFileType(item.name);
      if (fileType === "video") {
        const videoPath = encodeURIComponent(
          `${initialPath}/${item.name}`.replace(/^\/downloads\/*/, "")
        );
        const videoUrl = `${apiRoutes.streamFile}?path=${videoPath}`;
        setVideoPlayer({ open: true, url: videoUrl, name: item.name });
      } else {
        toast.error("Can not read this file...");
      }
    }
  };

  const handleGoBack = () => {
    const pathParts = initialPath.split("/");
    if (pathParts.length === 4 && pathParts[1] === "downloads") {
      onPathChange("/downloads");
    } else {
      const newPath = initialPath.substring(0, initialPath.lastIndexOf("/"));
      onPathChange(newPath || "/downloads");
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
          const downloadUrl = `${apiRoutes.streamFile
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
    }
  };

  const handlePaste = async () => {
    if (!copiedItem) return;

    setPasting(true);
    try {
      const sourcePath = `${copiedItem.sourcePath}/${copiedItem.name}`.replace(
        /^\/downloads\/*/,
        ""
      );
      const destinationPath = `${initialPath}/${copiedItem.name}`.replace(
        /^\/downloads\/*/,
        ""
      );

      console.log("sourcePath", sourcePath);
      console.log("destinationPath", destinationPath);

      const apiEndpoint =
        copiedItem.action === "copy" ? apiRoutes.copyFile : apiRoutes.moveFile;
      const response = await axios.post(
        `${apiEndpoint}?source_path=${encodeURIComponent(
          sourcePath
        )}&destination_path=${encodeURIComponent(
          destinationPath
        )}&is_directory=${copiedItem.is_directory}`
      );

      if (response.status === 200) {
        toast.success(
          `Item ${copiedItem.action === "copy" ? "copied" : "moved"
          } successfully`
        );
        setCopiedItem(null);
        fetchData();
      } else {
        toast.error(`Failed to ${copiedItem.action} item`);
      }
    } catch (err) {
      toast.error(`Failed to ${copiedItem.action} item`);
    } finally {
      setPasting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteDialog.item) return;

    try {
      const path = `${initialPath}/${deleteDialog.item.name}`.replace(
        /^\/downloads\/*/,
        ""
      );
      await axios.delete(
        `${apiRoutes.deleteFile}?path=${encodeURIComponent(path)}`
      );

      // Remove the item from the list
      setItems(items.filter((item) => item.name !== deleteDialog.item.name));

      // Show success notification
      toast.success(`${deleteDialog.item.name} has been deleted`);
    } catch (err) {
      // Show error notification
      toast.error(err.message);
    } finally {
      setDeleteDialog({ open: false, item: null });
    }
  };

  const handleRename = async (newName) => {
    if (newName) {
      try {
        const extension = renameDialog.item.name.split('.').pop();
        const baseName = newName.split('.').slice(0, -1).join('.');
        const newFullName = `${baseName}.${extension}`;
        const path = `${initialPath}/${renameDialog.item.name}`.replace(
          /^\/downloads\/*/,
          ""
        );
        await axios.post(
          `${apiRoutes.renameFile}?source_path=${encodeURIComponent(
            path
          )}&new_name=${newFullName}`
        );
        toast.success("Item renamed successfully");
        fetchData();
      } catch (err) {
        toast.error("Failed to rename item");
      } finally {
        setRenameDialog({ open: false, item: null });
      }
    }
  };

  return (
    <div className="mt-6">
      {archiving && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black opacity-80 z-40"></div>
          <div className="relative z-50 flex gap-3 items-center bg-transparent p-4">
            <p className="text-lg font-semibold">Archiving, Please wait...</p>
            <FiLoader className="animate-spin w-8 h-8" />
          </div>
        </div>
      )}

      {pasting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black opacity-80 z-40"></div>
          <div className="relative z-50 flex gap-3 items-center bg-transparent p-4">
            <p className="text-lg font-semibold">Pasting, Please wait...</p>
            <FiLoader className="animate-spin w-8 h-8" />
          </div>
        </div>
      )}

      <AnimatePresence>

        {deleteDialog.open && <DeleteDialog
          open={deleteDialog.open}
          item={deleteDialog.item}
          onClose={() => setDeleteDialog({ open: false, item: null })}
          onDelete={handleDelete}
        />}
      </AnimatePresence>


      <VideoPlayer
        open={videoPlayer.open}
        url={videoPlayer.url}
        name={videoPlayer.name}
        onClose={() => setVideoPlayer({ open: false, url: "", name: "" })}
      />

      <AnimatePresence>
        {renameDialog.open && <RenameDialog
          open={renameDialog.open}
          item={renameDialog.item}
          onClose={() => setRenameDialog({ open: false, item: null })}
          onRename={handleRename}
        />}
      </AnimatePresence>

      <div className="flex items-center gap-1 mb-6">
        <button
          onClick={handleGoBack}
          className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-full transition-colors"
          title="Go back"
        >
          <FiArrowLeft size={20} />
        </button>

        <Breadcrumbs initialPath={initialPath} onPathChange={onPathChange} />

        {copiedItem && !pasting && initialPath != copiedItem?.sourcePath && (
          <button
            onClick={handlePaste}
            className="group ml-auto p-2 px-3 text-center text-xs rounded-full bg-blue-500/20 text-blue-500 dark:bg-blue-700/20 dark:text-blue-500 min-w-fit"
          >
            <p className="group-hover:drop-shadow-[0_0_10px_rgba(59,130,246,0.5)]">
              {copiedItem.action === "copy" ? "Paste Here" : "Move Here"}
            </p>
          </button>
        )}
      </div>

      {loading && (
        <div className="flex items-center justify-center p-8">
          <FiLoader className="animate-spin w-8 h-8" />
        </div>
      )}
      {error && (
        <div className="text-red-500 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-2">
        {items.map((item) => (
          <div
            key={item.name}
            onClick={() => handleItemClick(item)}
            className="py-4 px-4 rounded-lg border dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
          >
            <div className="flex items-center gap-3">
              <FileIcon item={item} />
              <div className="truncate flex w-full items-center justify-between">
                <div className="flex flex-col">
                  <div className="font-medium">{item.name}</div>
                  <div className="text-sm text-gray-500">
                    {formatFileSize(item.size)}
                  </div>
                </div>
                <FileMenu item={item} onAction={handleFileAction} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {!loading && !error && items.length === 0 && (
        <div className="text-center p-8 text-gray-500">
          This folder is empty
        </div>
      )}
    </div>
  );
}
