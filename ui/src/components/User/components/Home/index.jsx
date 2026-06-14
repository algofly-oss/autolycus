import { useState, useEffect } from "react";
import AddTorrent from "./components/AddTorrent";
import DownloadSearch from "./components/DownloadSearch";
import DownloadSearchResults from "./components/DownloadSearchResults";
import TorrentList from "./components/TorrentList";
import FileExplorer from "./components/FileExplorer";

export default function Home({ state }) {
  const [currentPath, setCurrentPath] = useState(null);
  const [selectedFileName, setSelectedFileName] = useState(null);
  const [viewMode, setViewMode] = useState(() => state?.get("homeViewMode") || "list");
  const [downloadSearch, setDownloadSearch] = useState({
    active: false,
    query: "",
    itemType: "",
    extension: "",
    sort: "modified:desc",
  });
  const isListView = !currentPath;

  const handlePathChange = (newPath) => {
    // If we're navigating to /downloads or an invalid path, clear the current path
    if (!newPath || newPath === "/downloads") {
      setCurrentPath(null);
      setSelectedFileName(null);
      state.set({
        activeTorrent: null,
        hoveredTorrent: null,
        hoveredTorrentInfoHash: null,
        isFileView: false,
      });
      return;
    }
    setCurrentPath(newPath);
    setSelectedFileName(null);
    state.set({ isFileView: true });
  };

  const handleSearchResultPathChange = (newPath, fileName = null) => {
    if (!newPath || newPath === "/downloads") {
      handlePathChange(newPath);
      return;
    }

    setCurrentPath(newPath);
    setSelectedFileName(fileName);
    state.set({ isFileView: true });
  };

  useEffect(() => {
    state?.set("homeViewMode", viewMode);
  }, [state, viewMode]);

  return (
    <div className="flex justify-center h-full min-h-0">
      <div className="pt-2 px-2 md:px-4 xl:pt-4 relative 2xl:w-[80rem] w-full h-full min-h-0 flex flex-col">
        <AddTorrent />
        <DownloadSearch
          viewMode={viewMode}
          setViewMode={setViewMode}
          showViewToggle={isListView}
          onSearchChange={setDownloadSearch}
        />
        <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden pb-[7rem] md:pb-6 mt-2 rounded-xl md:light-scrollbar dark:md:dark-scrollbar">
          {currentPath ? (
            <FileExplorer
              initialPath={currentPath}
              onPathChange={handlePathChange}
              selectedFileName={selectedFileName}
            />
          ) : downloadSearch.active ? (
            <DownloadSearchResults
              state={state}
              query={downloadSearch.query}
              itemType={downloadSearch.itemType}
              extension={downloadSearch.extension}
              sort={downloadSearch.sort}
              viewMode={viewMode}
              onPathChange={handleSearchResultPathChange}
            />
          ) : (
            <TorrentList
              state={state}
              onPathChange={handlePathChange}
              viewMode={viewMode}
            />
          )}
        </div>
      </div>
    </div>
  );
}
