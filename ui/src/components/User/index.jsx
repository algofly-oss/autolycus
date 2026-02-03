import { useEffect, useState } from "react";
import UserNavBar from "./components/NavBar";
import { BiMeteor } from "react-icons/bi";
import Home from "./components/Home";
import TorrentDetails from "./components/Home/components/TorrentDetails";
import reactState from "@/shared/hooks/reactState";
import Search from "./components/Search";

export default function UserHome() {
  const [tab, setTab] = useState("Home");
  const state = reactState({
    hoveredTorrent: null,
    isFileView: false,
    hoveredTorrentInfoHash: null,
    torrentListPage: 1,
    torrentListPageSize: 10,
  });

  const torrentSearchState = reactState({});

  useEffect(() => {
    if (tab !== "Home") {
      state.set("hoveredTorrent", null);
      state.set("hoveredTorrentInfoHash", null);
    }
  }, [tab]);

  return (
    <div className="flex h-screen overflow-hidden">
      <div
        className="bg-neutral-100 dark:bg-black flex items-center w-full md:px-4 fixed inset-x-0 bottom-0 z-10 h-16
        md:relative md:block md:h-screen md:w-96 2xl:w-[25%]- 2xl:w-[30rem] md:p-4 md:overflow-y-auto md:light-scrollbar dark:md:dark-scrollbar"
      >
        <div
          className="hidden md:flex space-x-3 items-center mt-2 mb-6 dark:text-neutral-300 cursor-pointer"
          onClick={() => {
            setTab("Home");
          }}
        >
          <BiMeteor size={40} />
          <p className="font-bold md:text-lg">Autolycus</p>
        </div>
        <UserNavBar tab={tab} setTab={setTab} />
      </div>

      <div className="w-full h-screen overflow-hidden relative">
        {tab === "Home" && <Home state={state} />}
        {tab === "Search" && <Search torrentSearchState={torrentSearchState} />}
      </div>
      <div className="hidden lg:block w-[26rem] 2xl:w-[25%]- 2xl:w-[30rem] h-screen bg-neutral-100 dark:bg-black overflow-y-auto md:light-scrollbar dark:md:dark-scrollbar">
        <TorrentDetails
          torrent={state.get("hoveredTorrent")}
          isFileView={state.get("isFileView")}
        />
      </div>
    </div>
  );
}
