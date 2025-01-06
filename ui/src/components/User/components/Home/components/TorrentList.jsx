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
      state.set("hoveredTorrentInfoHash", torrent?.info_hash);
      onPathChange(torrent.save_dir);
    }
  };

  useEffect(() => {
    if (state.get("hoveredTorrentInfoHash")) {
      let hoveredTorrent = torrentList.find(
        (torrent) => torrent.info_hash === state.get("hoveredTorrentInfoHash")
      );
      state.set("hoveredTorrent", hoveredTorrent || null);
    } else {
      state.set("hoveredTorrent", null);
    }
  }, [state.get("hoveredTorrentInfoHash"), torrentList]);

  return (
    <div className="mt-5 flex flex-col gap-1.5">
      {torrentList.map((torrent) => (
        <div
          key={torrent.id}
          onClick={() => handleTorrentClick(torrent)}
          onMouseEnter={() =>
            state.set("hoveredTorrentInfoHash", torrent?.info_hash)
          }
          onMouseLeave={() => state.set("hoveredTorrentInfoHash", null)}
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
