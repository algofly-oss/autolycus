import { useState, useEffect } from "react";
import AddTorrent from "./components/AddTorrent";
import TorrentList from "./components/TorrentList";
import FileExplorer from "./components/FileExplorer";

export default function Home({ state }) {
  const [currentPath, setCurrentPath] = useState(null);
  const isListView = !currentPath;

  const handlePathChange = (newPath) => {
    // If we're navigating to /downloads or an invalid path, clear the current path
    if (!newPath || newPath === "/downloads") {
      setCurrentPath(null);
      state.set("hoveredTorrent", null);
      state.set("isFileView", false);
      return;
    }
    setCurrentPath(newPath);
    state.set("isFileView", true);
  };

  return (
    <div className="flex justify-center h-full min-h-0">
      <div className="pt-2 px-2 md:px-4 xl:pt-4 relative 2xl:w-[80rem] w-full h-full min-h-0 flex flex-col">
        <AddTorrent />
        <div className="overflow-y-auto overflow-x-hidden no-scrollbar flex-1 min-h-0 pb-[7rem] md:pb-6 mt-2 rounded-xl">
          {currentPath ? (
            <FileExplorer
              initialPath={currentPath}
              onPathChange={handlePathChange}
            />
          ) : (
            <TorrentList state={state} onPathChange={handlePathChange} />
          )}
        </div>
      </div>
    </div>
  );
}
