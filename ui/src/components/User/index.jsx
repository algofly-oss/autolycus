import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";
import UserNavBar from "./components/NavBar";
import { BiMeteor } from "react-icons/bi";
import Home from "./components/Home";
import TorrentDetails from "./components/Home/components/TorrentDetails";
import reactState from "@/shared/hooks/reactState";
import Search from "./components/Search";
import SearchResultDetails from "./components/Search/components/SearchResultDetails";
import Settings from "./components/Settings";

const NAV_COLLAPSED_STORAGE_KEY = "autolycus:nav-collapsed";
const TAB_QUERY_VALUE = {
  Home: "home",
  Search: "search",
  Settings: "settings",
};
const TAB_FROM_QUERY_VALUE = Object.entries(TAB_QUERY_VALUE).reduce(
  (tabs, [tab, queryValue]) => ({ ...tabs, [queryValue]: tab }),
  {}
);

export default function UserHome() {
  const router = useRouter();
  const [tab, setTab] = useState("Home");
  const [navReady, setNavReady] = useState(false);
  const [navCollapsed, setNavCollapsed] = useState(true);
  const state = reactState({
    hoveredTorrent: null,
    activeTorrent: null,
    isFileView: false,
    hoveredTorrentInfoHash: null,
    torrentListPage: 1,
    torrentListPageSize: 50,
    torrentListCache: [],
    torrentListTotal: 0,
  });

  const torrentSearchState = reactState({});
  const isHomeTab = tab === "Home";
  const isSearchTab = tab === "Search";
  const isSettingsTab = tab === "Settings";
  const isFileView = Boolean(state.get("isFileView"));
  const detailsTorrent = useMemo(
    () =>
      isFileView
        ? state.get("activeTorrent")
        : isHomeTab
        ? state.get("hoveredTorrent")
        : null,
    [
      isFileView,
      isHomeTab,
      state.value.activeTorrent,
      state.value.hoveredTorrent,
    ]
  );

  useEffect(() => {
    if (!isHomeTab) {
      state.set({
        hoveredTorrent: null,
        hoveredTorrentInfoHash: null,
      });
    }
  }, [isHomeTab]);

  useEffect(() => {
    if (!isSearchTab) {
      torrentSearchState.set({
        hoveredResult: null,
      });
    }
  }, [isSearchTab]);

  useEffect(() => {
    if (!router.isReady) return;

    const queryTab = Array.isArray(router.query.tab)
      ? router.query.tab[0]
      : router.query.tab;
    const nextTab =
      TAB_FROM_QUERY_VALUE[String(queryTab || "home").toLowerCase()] || "Home";

    setTab(nextTab);
  }, [router.isReady, router.query.tab]);

  const handleTabChange = (nextTab) => {
    setTab(nextTab);

    if (!router.isReady) return;

    const nextQuery = { ...router.query };
    if (nextTab === "Home") {
      delete nextQuery.tab;
    } else {
      nextQuery.tab = TAB_QUERY_VALUE[nextTab];
    }

    router.push(
      {
        pathname: router.pathname,
        query: nextQuery,
      },
      undefined,
      { shallow: true, scroll: false }
    );
  };

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedValue = window.localStorage.getItem(NAV_COLLAPSED_STORAGE_KEY);
    setNavCollapsed(storedValue === null ? true : storedValue === "true");
    setNavReady(true);
  }, []);

  const toggleNavCollapsed = () => {
    setNavCollapsed((currentValue) => {
      const nextValue = !currentValue;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(NAV_COLLAPSED_STORAGE_KEY, String(nextValue));
      }
      return nextValue;
    });
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <div
        className={`bg-neutral-100 dark:bg-black flex items-center w-full md:px-4 fixed inset-x-0 bottom-0 z-50 h-16
        ${
          navCollapsed
            ? "md:relative md:flex md:h-screen md:w-16 md:shrink-0 md:flex-col md:overflow-hidden md:border-r md:border-neutral-200/70 md:px-2 md:py-4 dark:md:border-neutral-800/80"
            : "md:relative md:block md:h-screen md:w-[17rem] md:shrink-0 md:border-r md:border-neutral-200/70 md:p-4 md:overflow-y-auto md:light-scrollbar dark:md:border-neutral-800/80 dark:md:dark-scrollbar"
        }`}
      >
        {navReady && (
          <>
            <div
              className={`hidden md:flex items-center dark:text-neutral-300 cursor-pointer ${
                navCollapsed
                  ? "mb-4 h-10 w-10 justify-center self-center"
                  : "space-x-3 mt-2 mb-6"
              }`}
              onClick={toggleNavCollapsed}
              title={navCollapsed ? "Expand navigation" : "Collapse navigation"}
            >
              <BiMeteor size={navCollapsed ? 32 : 40} />
              {!navCollapsed && <p className="font-bold md:text-lg">Autolycus</p>}
            </div>
            <UserNavBar
              tab={tab}
              setTab={handleTabChange}
              collapsed={navCollapsed}
            />
          </>
        )}
      </div>

      <div className="relative z-0 min-w-0 flex-1 h-screen overflow-hidden">
        <div
          className={`h-full ${isHomeTab ? "block" : "hidden"}`}
          aria-hidden={!isHomeTab}
        >
          <Home state={state} />
        </div>
        <div
          className={`h-full ${tab === "Search" ? "block" : "hidden"}`}
          aria-hidden={tab !== "Search"}
        >
          <Search torrentSearchState={torrentSearchState} />
        </div>
        <div
          className={`h-full overflow-y-auto pb-24 md:pb-0 md:light-scrollbar dark:md:dark-scrollbar ${
            isSettingsTab ? "block" : "hidden"
          }`}
          aria-hidden={!isSettingsTab}
        >
          <Settings />
        </div>
      </div>
      {!navCollapsed && (
        <div className="no-scrollbar hidden h-screen w-[17rem] shrink-0 overflow-y-auto bg-neutral-100 dark:bg-black lg:block">
          {isSearchTab ? (
            <SearchResultDetails item={torrentSearchState.get("hoveredResult")} />
          ) : isSettingsTab ? (
            <div className="p-4 text-neutral-700 dark:text-neutral-300">
              <div className="rounded-lg border border-neutral-200 bg-white p-5 dark:border-[#33363b] dark:bg-[#202124]">
                <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                  Account Settings
                </h2>
                <p className="mt-2 text-sm leading-6 text-neutral-500 dark:text-neutral-400">
                  Manage your profile picture, name, email, and password from the
                  settings page.
                </p>
              </div>
            </div>
          ) : (
            <TorrentDetails
              torrent={isHomeTab ? detailsTorrent : null}
              isFileView={isFileView}
            />
          )}
        </div>
      )}
    </div>
  );
}
