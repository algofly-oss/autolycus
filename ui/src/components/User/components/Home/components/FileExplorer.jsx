import apiRoutes from "@/shared/routes/apiRoutes";
import axios from "axios";
import React, { useEffect, useState } from "react";
import {
  FiFolder,
  FiFile,
  FiArrowLeft,
  FiLoader,
  FiFilm,
  FiMusic,
  FiImage,
  FiFileText,
  FiCopy,
  FiMove,
  FiTrash2,
  FiDownload,
} from "react-icons/fi";
import { formatFileSize, getFileType } from "@/shared/utils/fileUtils";
import { GoKebabHorizontal } from "react-icons/go";
import { Menu, Modal, Button, Text } from "@mantine/core";
import useToast from "@/shared/hooks/useToast";

function FileMenu({ item, onAction }) {
  const actions = [
    { name: "Copy", icon: FiCopy, action: "copy" },
    { name: "Move", icon: FiMove, action: "move" },
    { name: "Delete", icon: FiTrash2, action: "delete" },
    { name: "Download", icon: FiDownload, action: "download" },
  ];

  return (
    <Menu shadow="md" width={200} position="bottom-end" withinPortal>
      <Menu.Target>
        <button
          className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full"
          onClick={(e) => e.stopPropagation()}
        >
          <GoKebabHorizontal className="w-4 h-4 rotate-90" />
        </button>
      </Menu.Target>

      <Menu.Dropdown>
        {actions.map((action) => (
          <Menu.Item
            key={action.name}
            icon={<action.icon size={14} />}
            onClick={(e) => {
              e.stopPropagation();
              onAction(action.action, item);
            }}
          >
            {action.name}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}

export default function FileExplorer({ initialPath, onPathChange }) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [videoPlayer, setVideoPlayer] = useState({
    open: false,
    url: "",
    name: "",
  });
  const [deleteDialog, setDeleteDialog] = useState({ open: false, item: null });
  const toast = useToast();

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError("");
      if (initialPath) {
        try {
          // console.log("initialPath", initialPath);
          const encodedPath = encodeURIComponent(
            initialPath.replace(/^\/downloads\/*/, "")
          );
          const response = await axios.get(
            `${apiRoutes.browseFiles}?path=${encodedPath}`
          );
          setItems(response.data);
          // console.log("Items information: ", response.data)
        } catch (err) {
          setError(err.message);
        } finally {
          setLoading(false);
        }
      }
    };

    fetchData();
  }, [initialPath]);

  function handleItemClick(item) {
    if (item.is_directory) {
      onPathChange(`${initialPath}/${item.name}`);
    } else {
      const fileType = getFileType(item.name);
      if (fileType === "video") {
        // Construct the video URL using the current path and filename
        const videoPath = encodeURIComponent(
          `${initialPath}/${item.name}`.replace(/^\/downloads\/*/, "")
        );
        const videoUrl = `${apiRoutes.streamFile}?path=${videoPath}`;
        setVideoPlayer({ open: true, url: videoUrl, name: item.name });
      } else {
        toast.error("Can not read this file...");
      }
    }
  }

  function handleGoBack() {
    if (!initialPath.includes("/")) return;
    const newPath = initialPath.substring(0, initialPath.lastIndexOf("/"));
    onPathChange(newPath || "/downloads");
  }

  // Get appropriate icon based on file type
  function getFileIcon(item) {
    if (item.is_directory) {
      return <FiFolder size={24} className="text-blue-500" />;
    }

    const fileType = getFileType(item.name);
    switch (fileType) {
      case "video":
        return <FiFilm size={24} className="text-purple-500" />;
      case "audio":
        return <FiMusic size={24} className="text-green-500" />;
      case "image":
        return <FiImage size={24} className="text-pink-500" />;
      case "document":
        return <FiFileText size={24} className="text-orange-500" />;
      default:
        return <FiFile size={24} className="text-gray-500" />;
    }
  }

  // Create breadcrumb items from the path, excluding /downloads/{id}
  const pathParts = initialPath.split("/").filter(Boolean);
  // Find the index after "downloads" to start showing breadcrumbs
  const startIndex = pathParts.findIndex((part) => part === "downloads") + 1;
  const visibleParts = pathParts.slice(startIndex);
  const breadcrumbs = visibleParts.map((part, index) => {
    // Reconstruct the full path for navigation while showing only the visible part
    const fullPath = "/" + pathParts.slice(0, startIndex + index + 1).join("/");
    return { name: part, path: fullPath };
  });

  const handleFileAction = async (action, item) => {
    switch (action) {
      case "copy":
        // TODO: Implement copy functionality
        console.log("Copy", item);
        break;
      case "move":
        // TODO: Implement move functionality
        console.log("Move", item);
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

          // Create a temporary link element and trigger download
          const link = document.createElement("a");
          link.href = downloadUrl;
          link.download = item.name; // Set the download filename
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);

          toast.success("Download started");
        } catch (err) {
          toast.error("Failed to start download");
        }
        break;
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

  return (
    <div className="mt-6">
      {/* Delete Confirmation Dialog */}
      <Modal
        opened={deleteDialog.open}
        onClose={() => setDeleteDialog({ open: false, item: null })}
        title="Confirm Delete"
        size="sm"
        centered
      >
        <Text size="sm" mb="lg">
          Are you sure you want to delete{" "}
          <strong>{deleteDialog.item?.name}</strong>?
          {deleteDialog.item?.is_directory &&
            " This will delete all contents inside the folder."}
        </Text>
        <div className="flex justify-end gap-4">
          <Button
            variant="default"
            onClick={() => setDeleteDialog({ open: false, item: null })}
          >
            Cancel
          </Button>
          <Button color="red" onClick={handleDelete}>
            Delete
          </Button>
        </div>
      </Modal>

      {/* Video Player Modal */}
      <Modal
        opened={videoPlayer.open}
        onClose={() => setVideoPlayer({ open: false, url: "", name: "" })}
        title={videoPlayer.name}
        size="xl"
        centered
      >
        <video className="w-full" controls autoPlay src={videoPlayer.url}>
          Your browser does not support the video tag.
        </video>
      </Modal>

      {/* Navigation header */}
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={handleGoBack}
          className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-full transition-colors"
          title="Go back"
        >
          <FiArrowLeft size={20} />
        </button>

        {/* Path breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 overflow-x-auto">
          <span>/</span>
          {breadcrumbs.map((crumb, index) => (
            <React.Fragment key={crumb.path}>
              {index === 0 ? "" : <span>/</span>}
              <span
                className="hover:text-blue-500 cursor-pointer whitespace-nowrap"
                onClick={() => onPathChange(crumb.path)}
              >
                {crumb.name}
              </span>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Loading and Error states */}
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

      {/* File/Folder Grid */}
      <div className="flex flex-col gap-2">
        {items.map((item) => (
          <div
            key={item.name}
            onClick={() => handleItemClick(item)}
            className="py-4 px-4 rounded-lg border dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
          >
            <div className="flex items-center gap-3">
              {getFileIcon(item)}
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

      {/* Empty state */}
      {!loading && !error && items.length === 0 && (
        <div className="text-center p-8 text-gray-500">
          This folder is empty
        </div>
      )}
    </div>
  );
}
