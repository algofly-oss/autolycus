import React, { useState, useEffect } from "react";
import axios from "axios";
import apiRoutes from "@/shared/routes/apiRoutes";
import TorrentCard from "./TorrentCard";

export default function TorrentList({ state, onPathChange }) {
  const [torrentList, setTorrentList] = useState([]);

  useEffect(() => {
    fetchTorrents();
    const interval = setInterval(fetchTorrents, 1000);
    return () => {
      clearInterval(interval);
    };
  }, []);

  async function fetchTorrents() {
    try {
      const response = await axios.get(apiRoutes.listTorrents);
      const torrents = Array.isArray(response.data)
        ? response.data
        : Array.isArray(response.data.data)
        ? response.data.data
        : [];

      // Sort torrents: downloading first, then completed
      const sortedTorrents = [...torrents].sort((a, b) => {
        if (a.is_finished === b.is_finished) return 0;
        return a.is_finished ? 1 : -1;
      });

      setTorrentList(sortedTorrents);
    } catch (error) {
      console.error("Error fetching torrents:", error);
    }
  }

  const handleTorrentClick = (torrent) => {
    if (torrent.is_finished) {
      state.set("hoveredTorrent_id", torrent?.info_hash);
      onPathChange(torrent.save_dir);
    }
  };

  useEffect(() => {
    if (state.get("hoveredTorrent_id")) {
      let hoveredTorrent = torrentList.find(
        (torrent) => torrent.info_hash === state.get("hoveredTorrent_id")
      );
      state.set("hoveredTorrent", hoveredTorrent || null);
    } else {
      state.set("hoveredTorrent", null);
    }
  }, [state.get("hoveredTorrent_id"), torrentList]);

  return (
    <div className="mt-5 flex flex-col gap-1.5">
      {torrentList.map((torrent) => (
        <div
          key={torrent.id}
          onClick={() => handleTorrentClick(torrent)}
          onMouseEnter={() =>
            state.set("hoveredTorrent_id", torrent?.info_hash)
          }
          onMouseLeave={() => state.set("hoveredTorrent_id", null)}
          className={`${
            torrent.is_finished ? "cursor-pointer" : ""
          } hover:bg-gray-50 dark:hover:bg-gray-900 rounded-xl transition-colors`}
        >
          <TorrentCard torrentData={torrent} />
        </div>
      ))}
    </div>
  );
}
