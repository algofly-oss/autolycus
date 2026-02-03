import React, {
  useState,
  useEffect,
  useContext,
  useMemo,
  useCallback,
} from "react";
import axios from "axios";
import apiRoutes from "@/shared/routes/apiRoutes";
import TorrentCard from "./TorrentCard";
import { SocketContext } from "@/shared/contexts/socket";
import socketRoutes from "@/shared/routes/socketRoutes";
import Pagination from "./Pagination";

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100, 200];

export default function TorrentList({ state, onPathChange }) {
  const socket = useContext(SocketContext);
  const [torrentList, setTorrentList] = useState([]);
  const [currentPage, setCurrentPage] = useState(() => {
    const storedPage = state?.get("torrentListPage");
    const parsedPage = Number(storedPage);
    return Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : 1;
  });
  const [pageSize, setPageSize] = useState(() => {
    const storedSize = state?.get("torrentListPageSize");
    const parsedSize = Number(storedSize);
    if (Number.isFinite(parsedSize) && PAGE_SIZE_OPTIONS.includes(parsedSize)) {
      return parsedSize;
    }
    return PAGE_SIZE_OPTIONS[0];
  });
  const [totalTorrents, setTotalTorrents] = useState(0);
  const [pageInput, setPageInput] = useState("1");

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil((totalTorrents || 0) / pageSize)),
    [pageSize, totalTorrents]
  );

  const rangeStart = totalTorrents === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const rangeEnd = Math.min(totalTorrents, currentPage * pageSize);

  const fetchTorrents = useCallback(async () => {
    try {
      const response = await axios.get(apiRoutes.listTorrents, {
        params: { page: currentPage, page_size: pageSize },
      });

      const responseData = response.data || {};
      const retrievedTorrents = Array.isArray(responseData)
        ? responseData
        : Array.isArray(responseData.data)
        ? responseData.data
        : [];

      const meta = responseData.meta || {};
      const total =
        typeof meta.total === "number" ? meta.total : retrievedTorrents.length;
      const computedPages = Math.max(1, Math.ceil((total || 0) / pageSize));
      const sortedTorrents = [...retrievedTorrents].sort((a, b) => {
        if (a.is_finished === b.is_finished) {
          return 0;
        }
        return a.is_finished ? 1 : -1;
      });

      setTotalTorrents(total);

      if (currentPage > computedPages) {
        setTorrentList([]);
        setCurrentPage(computedPages);
        return;
      }

      setTorrentList(sortedTorrents);
    } catch (error) {
      console.error("Error fetching torrents:", error);
    }
  }, [currentPage, pageSize]);

  useEffect(() => {
    fetchTorrents();
  }, [fetchTorrents]);

  useEffect(() => {
    const handleSocketUpdate = () => fetchTorrents();
    socket.on(socketRoutes.stcTorrentAddedOrRemoved, handleSocketUpdate);

    return () => {
      socket.off(socketRoutes.stcTorrentAddedOrRemoved, handleSocketUpdate);
    };
  }, [socket, fetchTorrents]);

  const handlePageInputChange = (value) => {
    if (value === "" || /^\d+$/.test(value)) {
      setPageInput(value);
    }
  };

  const applyPageInput = () => {
    if (!pageInput) {
      setPageInput(String(currentPage));
      return;
    }

    const parsedPage = Number(pageInput);
    if (Number.isNaN(parsedPage)) {
      setPageInput(String(currentPage));
      return;
    }

    const clampedPage = Math.min(Math.max(parsedPage, 1), totalPages);
    if (clampedPage !== currentPage) {
      setCurrentPage(clampedPage);
    } else {
      setPageInput(String(currentPage));
    }
  };

  useEffect(() => {
    setPageInput(String(currentPage));
  }, [currentPage]);

  useEffect(() => {
    state?.set("torrentListPage", currentPage);
  }, [state, currentPage]);

  useEffect(() => {
    state?.set("torrentListPageSize", pageSize);
  }, [state, pageSize]);

  const handlePageSizeChange = (value) => {
    const parsedSize = Number(value);
    if (Number.isNaN(parsedSize) || parsedSize <= 0) {
      return;
    }
    setPageSize(parsedSize);
    setCurrentPage(1);
  };

  const handlePageButtonClick = (pageNumber) => {
    const clamped = Math.min(Math.max(pageNumber, 1), totalPages);
    if (clamped !== currentPage) {
      setCurrentPage(clamped);
    }
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
    torrentList.forEach((torrent) => {
      socket.on(
        socketRoutes.stcTorrentPropsUpdate +
          `/${torrent?.info_hash || torrent?.url_hash}`,
        (data) => {
          if (data?.info_hash || data?.url_hash) {
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

  const shouldShowPagination = torrentList.length > 0;

  return (
    <div className="mt-5 flex flex-col gap-1.5 pb-[4rem] md:pb-4">
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
      {shouldShowPagination && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          pageInput={pageInput}
          pageSize={pageSize}
          pageSizeOptions={PAGE_SIZE_OPTIONS}
          rangeStart={rangeStart}
          rangeEnd={rangeEnd}
          totalItems={totalTorrents}
          onPageButtonClick={handlePageButtonClick}
          onPageInputChange={handlePageInputChange}
          onApplyPageInput={applyPageInput}
          onPageSizeChange={handlePageSizeChange}
        />
      )}
    </div>
  );
}
