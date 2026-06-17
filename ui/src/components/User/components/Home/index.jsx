import { useState, useEffect, useRef } from "react";
import { useDispatch, useSelector } from "react-redux";
import axios from "axios";
import AddTorrent from "./components/AddTorrent";
import DownloadSearch from "./components/DownloadSearch";
import DownloadSearchResults from "./components/DownloadSearchResults";
import TorrentList from "./components/TorrentList";
import FileExplorer from "./components/FileExplorer";
import apiRoutes from "@/shared/routes/apiRoutes";
import { authActions, authSelector } from "@/redux/features/authSlice";

const VIEW_MODES = new Set(["list", "grid"]);

export default function Home({ state }) {
  const dispatch = useDispatch();
  const user = useSelector(authSelector);
  const savedViewMode = user?.preferences?.home_view_mode;
  const appliedSavedViewModeRef = useRef(false);
  const [currentPath, setCurrentPath] = useState(null);
  const [selectedFileName, setSelectedFileName] = useState(null);
  const [viewMode, setViewMode] = useState(() => {
    const stateViewMode = state?.get("homeViewMode");
    return VIEW_MODES.has(stateViewMode) ? stateViewMode : "list";
  });
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

  useEffect(() => {
    if (appliedSavedViewModeRef.current || !VIEW_MODES.has(savedViewMode)) {
      return;
    }

    appliedSavedViewModeRef.current = true;
    if (savedViewMode !== viewMode) {
      setViewMode(savedViewMode);
      state?.set("homeViewMode", savedViewMode);
    }
  }, [savedViewMode, state, viewMode]);

  const handleViewModeChange = async (nextViewMode) => {
    if (!VIEW_MODES.has(nextViewMode)) {
      return;
    }

    setViewMode(nextViewMode);
    state?.set("homeViewMode", nextViewMode);

    try {
      const response = await axios.patch(apiRoutes.updatePreferences, {
        home_view_mode: nextViewMode,
      });
      if (response?.data?.preferences) {
        dispatch(
          authActions.updateAccountInfo({
            preferences: response.data.preferences,
          })
        );
      }
    } catch (error) {}
  };

  return (
    <div className="flex justify-center h-full min-h-0">
      <div className="pt-2 px-2 md:px-4 xl:pt-4 relative 2xl:w-[80rem] w-full h-full min-h-0 flex flex-col">
        <AddTorrent />
        <DownloadSearch
          viewMode={viewMode}
          setViewMode={handleViewModeChange}
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
