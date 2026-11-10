import InfiniteMediaList from "@/shared/InfiniteMediaList";
import {requestPlayerFullscreen} from "@/shared/usePlayerFullscreen";
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { useRouter } from "next/router";
import useWatchProgress, { relativeMediaPath } from "@/shared/useWatchProgress";
import { FiArrowLeft, FiLoader } from "react-icons/fi";
import { getFileType } from "@/shared/utils/fileUtils";
import apiRoutes from "@/shared/routes/apiRoutes";
import useToast from "@/shared/hooks/useToast";
import Breadcrumbs from "./components/Breadcrumbs";
import DeleteDialog from "./components/DeleteDialog";
import dynamic from "next/dynamic";
import { AnimatePresence } from "framer-motion";
import RenameDialog from "./components/RenameDialog";
import FileItem from "./components/FileItem";
import FilePreview, { getPreviewType } from "./components/FilePreview";
const VideoPlayer = dynamic(() => import("./components/VideoPlayer"), { ssr: false, loading: () => <div role="status" aria-label="Loading video" style={{ position: "fixed", inset: 0, zIndex: 2000, background: "#000", display: "grid", placeItems: "center", color: "#aaa" }}><FiLoader size={28} className="animate-spin" /></div> });

const fileKey=item=>item.name;

export default function FileExplorer({
  scrollRef,
  initialPath,
  onPathChange,
  selectedFileName = null,
}) {
  const router = useRouter();
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [videoPlayer, setVideoPlayer] = useState({
    open: false,
    url: "",
    name: "",
  });
  const [filePreview, setFilePreview] = useState({
    open: false,
    url: "",
    name: "",
    type: "",
  });
  const [deleteDialog, setDeleteDialog] = useState({ open: false, item: null });
  const [renameDialog, setRenameDialog] = useState({ open: false, item: null });
  const [copiedItem, setCopiedItem] = useState(null);
  const [pasting, setPasting] = useState(false);
  const toast = useToast();
  const [visibleRange,setVisibleRange]=useState([0,20]);
  const onRange=useCallback((start,end)=>setVisibleRange(old=>old[0]===start&&old[1]===end?old:[start,end]),[]);
  const watched = useWatchProgress(items.slice(...visibleRange).map(item => ({path:relativeMediaPath(`${initialPath}/${item.name}`),directory:item.is_directory})));
  useEffect(() => {
    if(!router.isReady) return;
    const video = typeof router.query.video === "string" ? router.query.video : "";
    if(video) setVideoPlayer(current => current.open && new URL(current.url,location.href).searchParams.get("path")===video ? current : {open:true,url:`${apiRoutes.streamFile}?path=${encodeURIComponent(video)}`,name:video.split("/").pop(),queueRoot:initialPath});
    else setVideoPlayer(current => current.open ? {open:false,url:"",name:""} : current);
  },[router.isReady,router.query.video,initialPath]);
  function selectEpisode(entry) {
    setVideoPlayer(current=>({...current,url:`${apiRoutes.streamFile}?path=${encodeURIComponent(entry.path)}`,name:entry.name}));
    const query={...router.query,video:entry.path};delete query.t;
    router.replace({pathname:router.pathname,query},undefined,{shallow:true,scroll:false}).catch(()=>{});
  }


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
        requestPlayerFullscreen();
        setVideoPlayer({ open: true, url: videoUrl, name: item.name, queueRoot: initialPath });
        const query={...router.query,video:decodeURIComponent(videoPath)};delete query.t;
        router.push({pathname:router.pathname,query},undefined,{shallow:true,scroll:false}).catch(()=>{});
      } else {
        const previewType = getPreviewType(item.name);
        if (previewType) {
          const filePath = encodeURIComponent(
            `${initialPath}/${item.name}`.replace(/^\/downloads\/*/, "")
          );
          const fileUrl = `${apiRoutes.streamFile}?path=${filePath}`;
          setFilePreview({
            open: true,
            url: fileUrl,
            name: item.name,
            type: previewType,
          });
          return;
        }

        toast.error("Can not preview this file.");
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
          `Item ${
            copiedItem.action === "copy" ? "copied" : "moved"
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

      // The worker deletes in the background, so hide the queued item immediately.
      setItems(items.filter((item) => item.name !== deleteDialog.item.name));

      toast.success(`${deleteDialog.item.name} deletion started`);
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
    <div className="mt-5 pb-24 md:pb-0">
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

      {videoPlayer.open && <VideoPlayer
        open={videoPlayer.open}
        url={videoPlayer.url}
        name={videoPlayer.name}
        queueRoot={videoPlayer.queueRoot}
        onEpisodeSelect={selectEpisode}
        onClose={() => {
          const query={...router.query};delete query.video;delete query.t;
          router.replace({pathname:router.pathname,query},undefined,{shallow:true,scroll:false}).catch(()=>{});
          setVideoPlayer({ open: false, url: "", name: "" });
        }}
      />}

      <FilePreview
        open={filePreview.open}
        url={filePreview.url}
        name={filePreview.name}
        type={filePreview.type}
        onClose={() =>
          setFilePreview({ open: false, url: "", name: "", type: "" })
        }
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

      <InfiniteMediaList items={items} scrollRef={scrollRef} itemKey={fileKey} onRange={onRange} scrollToKey={selectedFileName} hasMore={false} renderItem={item=>(
          <FileItem watchProgress={watched[relativeMediaPath(`${initialPath}/${item.name}`)]}
            key={item.name}
            item={item}
            initialPath={initialPath}
            isSelected={selectedFileName === item.name}
            handleItemClick={handleItemClick}
            fetchData={fetchData}
            setCopiedItem={setCopiedItem}
            setDeleteDialog={setDeleteDialog}
            setRenameDialog={setRenameDialog}
          />
        )}/>

      {!loading && !error && items.length === 0 && (
        <div className="text-center p-8 text-gray-500">
          This folder is empty
        </div>
      )}
    </div>
  );
}
