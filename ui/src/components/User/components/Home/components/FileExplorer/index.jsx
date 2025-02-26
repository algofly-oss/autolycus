import React, { useEffect, useState } from "react";
import axios from "axios";
import { FiArrowLeft, FiLoader } from "react-icons/fi";
import { getFileType } from "@/shared/utils/fileUtils";
import apiRoutes from "@/shared/routes/apiRoutes";
import useToast from "@/shared/hooks/useToast";
import Breadcrumbs from "./components/Breadcrumbs";
import DeleteDialog from "./components/DeleteDialog";
import VideoPlayer from "./components/VideoPlayer";
import { AnimatePresence } from "framer-motion";
import RenameDialog from "./components/RenameDialog";
import FileItem from "./components/FileItem";

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
        const path = `${initialPath}/${renameDialog.item.name}`.replace(
          /^\/downloads\/*/,
          ""
        );
        await axios.post(
          `${apiRoutes.renameFile}?source_path=${encodeURIComponent(
            path
          )}&new_name=${newName}`
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
        {deleteDialog.open && (
          <DeleteDialog
            open={deleteDialog.open}
            item={deleteDialog.item}
            onClose={() => setDeleteDialog({ open: false, item: null })}
            onDelete={handleDelete}
          />
        )}
      </AnimatePresence>

      <VideoPlayer
        open={videoPlayer.open}
        url={videoPlayer.url}
        name={videoPlayer.name}
        onClose={() => setVideoPlayer({ open: false, url: "", name: "" })}
      />

      <AnimatePresence>
        {renameDialog.open && (
          <RenameDialog
            open={renameDialog.open}
            item={renameDialog.item}
            onClose={() => setRenameDialog({ open: false, item: null })}
            onRename={handleRename}
          />
        )}
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
          <FileItem
            key={item.name}
            item={item}
            initialPath={initialPath}
            handleItemClick={handleItemClick}
            fetchData={fetchData}
            setCopiedItem={setCopiedItem}
            setDeleteDialog={setDeleteDialog}
            setRenameDialog={setRenameDialog}
            setArchiving={setArchiving}
          />
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
