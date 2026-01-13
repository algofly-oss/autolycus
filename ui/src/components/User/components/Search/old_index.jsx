import React, { useState } from "react";
import axios from "axios";
import apiRoutes from "@/shared/routes/apiRoutes";
import useToast from "@/shared/hooks/useToast";
import SearchBar from "./components/SearchBar";
import SearchResults from "./components/SearchResults";

const Search = ({ torrentSearchState }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();

  const handleSearch = async (searchText) => {
    if (!searchText.trim()) {
      toast.error("Please enter a search term");
      return;
    }

    setLoading(true);
    setError("");
    torrentSearchState.set("results", []);

    try {
      const trimmedSearchText = searchText.trim().replace(/\s+/g, "+");
      const response = await axios.post(
        `${apiRoutes.searchTorrent}?query=${trimmedSearchText}`
      );

      if (response.data && Array.isArray(response?.data?.data)) {
        torrentSearchState.set("results", response?.data?.data);
      } else {
        torrentSearchState.set("results", []);
      }
    } catch (err) {
      console.error("Search error:", err);
      setError(err.response?.data?.detail || "Failed to search torrents");
      toast.error("Failed to search torrents");
    } finally {
      setLoading(false);
    }
  };

  const getMagnet = async (data) => {
    if (data?.magnet) {
      return data?.magnet;
    } else {
      try {
        let response = await axios.post(apiRoutes.getMagnet, {
          data: data,
        });
        return response.data?.magnet;
      } catch (error) {
        console.error("Error fetching magnet link:", error);
        toast.error("Failed to fetch magnet link");
        return null;
      }
    }
  };

  const handleTorrentClick = async (data) => {
    let magnet = await getMagnet(data);
    if (!magnet) {
      return;
    }

    try {
      await axios.post(apiRoutes.addMagnet, { magnet: magnet });
      toast.success("Torrent added successfully");
    } catch (err) {
      console.error("Add magnet error:", err);
      toast.error("Failed to add torrent");
    }
  };

  return (
    <div className="flex justify-center">
      <div className="m-4 pb-16 md:pb-6 xl:m-8 relative overflow-y-auto overflow-x-hidden 2xl:w-[80rem] w-full">
        <SearchBar onSearch={handleSearch} loading={loading} />
        <SearchResults
          results={torrentSearchState.get("results")}
          loading={loading}
          error={error}
          getMagnet={getMagnet}
          onTorrentClick={handleTorrentClick}
        />
      </div>
    </div>
  );
};

export default Search;
