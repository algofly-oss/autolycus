import { useState, useEffect } from "react";
import AddTorrent from "./components/AddTorrent";
import TorrentList from "./components/TorrentList";
import FileExplorer from "./components/FileExplorer";

export default function Home({ state }) {
  const [currentPath, setCurrentPath] = useState(null);

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
    <div className="flex justify-center">
      <div className="m-4 pb-16 md:pb-6 xl:m-8 relative overflow-y-auto overflow-x-hidden 2xl:w-[80rem] w-full">
        <AddTorrent />
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
  );
}
