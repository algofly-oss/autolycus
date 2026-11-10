import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import UserNavBar from "./components/NavBar";
import { BiMeteor } from "react-icons/bi";
import Home from "./components/Home";
import useReactState from "@/shared/hooks/reactState";
import Search from "./components/Search";
import Settings from "./components/Settings";

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
  const state = useReactState({
    hoveredTorrent: null,
    activeTorrent: null,
    isFileView: false,
    hoveredTorrentInfoHash: null,
    torrentListPage: 1,
    torrentListPageSize: 50,
    torrentListCache: [],
    torrentListTotal: 0,
  });

  const torrentSearchState = useReactState({});
  const isHomeTab = tab === "Home";
  const isSearchTab = tab === "Search";
  const isSettingsTab = tab === "Settings";
  const queryPath = Array.isArray(router.query.path)
    ? router.query.path[0]
    : router.query.path;
  const filePath = queryPath
    ? `/downloads/${String(queryPath).replace(/^\/downloads\/*/, "")}`
    : null;

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
    nextQuery.tab = TAB_QUERY_VALUE[nextTab];

    router.push(
      {
        pathname: router.pathname,
        query: nextQuery,
      },
      undefined,
      { shallow: true, scroll: false }
    );
  };

  const handleFilePathChange = (nextPath) => {
    const nextQuery = { ...router.query, tab: TAB_QUERY_VALUE.Home };
    const relativePath = nextPath
      ? String(nextPath).replace(/^\/downloads\/*/, "")
      : "";

    if (relativePath) {
      nextQuery.path = relativePath;
    } else {
      delete nextQuery.path;
    }

    setTab("Home");
    router.push(
      { pathname: router.pathname, query: nextQuery },
      undefined,
      { shallow: true, scroll: false }
    );
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <nav aria-label="Main navigation" className="fixed inset-x-0 bottom-0 z-50 flex h-16 w-full items-center bg-neutral-100 px-2 dark:bg-black md:relative md:h-screen md:w-16 md:shrink-0 md:flex-col md:border-r md:border-neutral-200/70 md:py-4 dark:md:border-neutral-800/80">
        <Link href="/" aria-label="Autolycus home" title="Autolycus" className="hidden h-10 w-10 shrink-0 md:flex items-center justify-center rounded-md text-neutral-700 hover:bg-neutral-200 dark:text-neutral-300 dark:hover:bg-neutral-900 md:mb-4"><BiMeteor size={30}/></Link>
        <UserNavBar tab={tab} setTab={handleTabChange} collapsed />
      </nav>

      <div className="relative z-0 min-w-0 flex-1 h-screen overflow-hidden">
        <div
          className={`h-full ${isHomeTab ? "block" : "hidden"}`}
          aria-hidden={!isHomeTab}
        >
          <Home
            state={state}
            initialPath={filePath}
            onPathChange={handleFilePathChange}
          />
        </div>
        <div
          className={`h-full ${tab === "Search" ? "block" : "hidden"}`}
          aria-hidden={tab !== "Search"}
        >
          <Search torrentSearchState={torrentSearchState} />
        </div>
        <div
          className={`h-full overflow-hidden pb-20 md:pb-0 ${
            isSettingsTab ? "block" : "hidden"
          }`}
          aria-hidden={!isSettingsTab}
        >
          <Settings />
        </div>
      </div>

    </div>
  );
}
