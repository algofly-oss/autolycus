import React, { useState, useEffect, useContext } from "react";
import axios from "axios";
import apiRoutes from "@/shared/routes/apiRoutes";
import TorrentCard from "./TorrentCard";
import { SocketContext } from "@/shared/contexts/socket";
import socketRoutes from "@/shared/routes/socketRoutes";

export default function TorrentList({ state, onPathChange }) {
  const socket = useContext(SocketContext);
  const [torrentList, setTorrentList] = useState([]);

  useEffect(() => {
    if (!torrentList?.length) {
      fetchTorrents();
    }

    socket.on(socketRoutes.stcTorrentAddedOrRemoved, (data) => {
      if (data) {
        fetchTorrents();
      }
    });

    return () => {
      socket.off(socketRoutes.stcTorrentAddedOrRemoved);
    };
  }, []);

  const fetchTorrents = () => {
    axios
      .get(apiRoutes.listTorrents)
      .then((response) => {
        const torrents = Array.isArray(response.data)
          ? response.data
          : Array.isArray(response.data.data)
          ? response.data.data
          : [];

        // Sort torrents: downloading first, then completed
        const sortedTorrents = torrents.sort((a, b) => {
          if (a.is_finished === b.is_finished) return 0;
          return a.is_finished ? 1 : -1;
        });

        setTorrentList(sortedTorrents);
      })
      .catch((error) => {
        console.error("Error fetching torrents:", error);
      });
  };

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

  useEffect(() => {
    // listen for torrent props update via socket.io for each torrent in torrentList
    torrentList.forEach((torrent) => {
      socket.on(
        socketRoutes.stcTorrentPropsUpdate +
          `/${torrent?.info_hash || torrent?.url_hash}`,
        (data) => {
          if (data?.info_hash || data?.url_hash) {
            // console.log("received progress data", data);
            setTorrentList((prevTorrentList) =>
              prevTorrentList.map((t) =>
                t.info_hash === data?.info_hash ? { ...t, ...data } : t
              )
            );
          }
        }
      );
    });

    return () => {
      torrentList.forEach((torrent) => {
        socket.off(
          socketRoutes.stcTorrentPropsUpdate + `/${torrent.info_hash}`
        );
      });
    };
  }, [torrentList?.length]);

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
