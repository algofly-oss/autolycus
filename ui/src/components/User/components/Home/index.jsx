import { useState, useEffect } from "react";
import AddTorrent from "./components/AddTorrent";
import FileList from "./components/FileList";
import FileExplorer from "./components/FileExplorer";

export default function Home({ state }) {
  const [currentPath, setCurrentPath] = useState(null);
  const [currentTorrent, setCurrentTorrent] = useState(null);

  const handlePathChange = (newPath) => {
    // If we're navigating to /downloads or an invalid path, clear the current path
    if (!newPath || newPath === '/downloads') {
      setCurrentPath(null);
      setCurrentTorrent(null);
      state.set('selectedTorrent', null);
      state.set('isFileView', false);
      return;
    }
    setCurrentPath(newPath);
    state.set('isFileView', true);
  };

  const handleTorrentHover = (torrent) => {
    if (!currentPath) {  // Only update hover state when in list view
      state.set('hoveredTorrent', torrent);
    }
  };

  const handleTorrentSelect = (torrent) => {
    setCurrentTorrent(torrent);
    state.set('selectedTorrent', torrent);
  };

  // Keep the selected torrent in details panel when in file browser view
  useEffect(() => {
    if (currentPath && currentTorrent) {
      state.set('selectedTorrent', currentTorrent);
    }
  }, [currentPath]);

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
          <FileList 
            onFileExplore={handlePathChange}
            onTorrentHover={handleTorrentHover}
            onTorrentSelect={handleTorrentSelect}
          />
        )}
      </div>
    </div>
  );
}
