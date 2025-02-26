import React from "react";
import {
  FiLoader,
  FiDownload,
  FiArrowUp,
  FiArrowDown,
  FiSearch,
  FiCopy,
} from "react-icons/fi";
import { MdMovie, MdLaptop, MdHelp, MdOutlineAudioFile } from "react-icons/md";
import { CgGames } from "react-icons/cg";
import { TbRating18Plus } from "react-icons/tb";
import useToast from "@/shared/hooks/useToast";
import axios from "axios";
import apiRoutes from "@/shared/routes/apiRoutes";

const getIconForType = (type) => {
  if (!type)
    return <MdHelp className="w-5 h-5 text-blue-500" aria-hidden="true" />;
  const baseType = type.split("(")[0].trim().toLowerCase();

  switch (baseType) {
    case "video":
      return <MdMovie className="w-5 h-5 text-blue-500" aria-hidden="true" />;
    case "applications":
      return <MdLaptop className="w-5 h-5 text-blue-500" aria-hidden="true" />;
    case "audio":
      return (
        <MdOutlineAudioFile
          className="w-5 h-5 text-blue-500"
          aria-hidden="true"
        />
      );
    case "games":
      return <CgGames className="w-5 h-5 text-blue-500" aria-hidden="true" />;
    case "porn":
      return (
        <TbRating18Plus className="w-5 h-5 text-blue-500" aria-hidden="true" />
      );
    default:
      return <MdHelp className="w-5 h-5 text-blue-500" aria-hidden="true" />;
  }
};

const SearchResults = ({
  results,
  loading,
  error,
  getMagnet,
  onTorrentClick,
}) => {
  const toast = useToast();

  const handleCopyToClipboard = async (data) => {
    let magnet = await getMagnet(data);
    if (!magnet) {
      return;
    }

    const el = document.createElement("textarea");
    el.value = magnet;
    document.body.appendChild(el);
    el.select();
    document.execCommand("copy");
    document.body.removeChild(el);
    toast.success("Magnet copied to clipboard");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <FiLoader className="animate-spin w-6 h-6" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8 text-red-500 text-sm sm:text-base">
        {error}
      </div>
    );
  }

  if (!results) {
    return (
      <div className="flex flex-col items-center justify-center py-12 sm:py-16 text-gray-500 dark:text-gray-400">
        <FiSearch className="w-10 h-10 sm:w-12 sm:h-12 mb-4" />
        <h3 className="text-base sm:text-lg font-semibold mb-2">
          Search for Torrents
        </h3>
        <p className="text-sm sm:text-base text-center max-w-xs">
          Enter your search term above to find torrents
        </p>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm sm:text-base">
        No results found
      </div>
    );
  }

  return (
    <div className="mt-4 bg-white dark:bg-zinc-900 rounded-lg divide-y divide-gray-200 dark:divide-zinc-700 shadow-sm">
      {results.map((torrent, index) => (
        <div
          key={index}
          className="p-3 sm:p-4 hover:bg-gray-50 dark:hover:bg-zinc-800"
        >
          <div className="flex flex-col sm:flex-row items-start gap-2 sm:gap-3">
            <div className="mt-1 shrink-0">{getIconForType(torrent.type)}</div>
            <div className="flex-1 w-full">
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-2 sm:gap-4">
                <h3 className="font-semibold text-sm sm:text-base md:text-lg mb-1 sm:mb-2 line-clamp-2">
                  {torrent.name}
                </h3>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => handleCopyToClipboard(torrent)}
                    className="flex items-center gap-1 sm:gap-2 px-2 sm:px-3 py-2 text-xs rounded-full border dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600 dark:text-white transition-colors"
                  >
                    <FiCopy
                      className="w-3 sm:w-4 h-3 sm:h-4"
                      aria-hidden="true"
                    />
                    <span className="hidden sm:inline">Copy</span>
                  </button>
                  <button
                    onClick={() => onTorrentClick(torrent)}
                    className="flex items-center gap-1 sm:gap-2 px-2 sm:px-3 py-2 text-xs rounded-full bg-blue-500 dark:bg-blue-700 hover:bg-blue-600 dark:hover:bg-blue-600 text-white transition-colors"
                  >
                    <FiDownload
                      className="w-3 sm:w-4 h-3 sm:h-4"
                      aria-hidden="true"
                    />
                    <span className="hidden sm:inline">Download</span>
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm sm:text-base">
                <span className="truncate">
                  <span className="text-xs sm:text-sm text-gray-400 dark:text-gray-500">
                    Type:
                  </span>
                  <span className="text-gray-700 dark:text-gray-200 ml-1">
                    {torrent.type}
                  </span>
                </span>
                <span className="truncate">
                  <span className="text-xs sm:text-sm text-gray-400 dark:text-gray-500">
                    Size:
                  </span>
                  <span className="text-gray-700 dark:text-gray-200 ml-1">
                    {torrent.size}
                  </span>
                </span>
                <span className="flex items-center gap-1 truncate">
                  <FiArrowUp
                    className="w-3 sm:w-4 h-3 sm:h-4 text-green-500 shrink-0"
                    aria-hidden="true"
                  />
                  <span className="text-xs sm:text-sm text-gray-400 dark:text-gray-500">
                    Seeds:
                  </span>
                  <span className="text-gray-700 dark:text-gray-200 truncate">
                    {torrent.seed}
                  </span>
                </span>
                <span className="flex items-center gap-1 truncate">
                  <FiArrowDown
                    className="w-3 sm:w-4 h-3 sm:h-4 text-red-500 shrink-0"
                    aria-hidden="true"
                  />
                  <span className="text-xs sm:text-sm text-gray-400 dark:text-gray-500">
                    Peers:
                  </span>
                  <span className="text-gray-700 dark:text-gray-200 truncate">
                    {torrent.leech}
                  </span>
                </span>
              </div>
              <div className="mt-1 sm:mt-2 text-xs sm:text-sm text-gray-400 dark:text-gray-500 flex justify-between items-center">
                <span>Created: {torrent.created}</span>
                <span className="text-blue-500 dark:text-blue-400">
                  Source: {torrent.source}
                </span>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default SearchResults;
