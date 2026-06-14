import { HiOutlineHome, HiHome } from "react-icons/hi";
import { RiSearchLine, RiSearchEyeLine } from "react-icons/ri";
import { RiSettings4Line, RiSettings4Fill } from "react-icons/ri";
import DarkThemeToggle from "./components/DarkThemeToggle";
import InfoCard from "./components/InfoCard";
import Logout from "./components/Logout";

const NavBarItem = ({ tab, setTab, Icon, IconFilled, text, collapsed }) => {
  if (collapsed) {
    return (
      <button
        type="button"
        className={
          "flex h-10 w-10 cursor-pointer items-center justify-center rounded-md transition-colors " +
          (tab === text
            ? "md:bg-blue-600 md:text-white"
            : "md:bg-transparent hover:md:bg-zinc-200 hover:md:dark:bg-zinc-900")
        }
        onClick={() => setTab(text)}
        title={text}
        aria-label={text}
      >
        {tab === text ? <IconFilled size={24} /> : <Icon size={24} />}
      </button>
    );
  }

  return (
    <div
      className={
        "md:pl-4 p-3 rounded-md cursor-pointer flex items-center md:space-x-4 hover:md:bg-zinc-200 hover:md:dark:bg-zinc-900 " +
        (tab === text
          ? "md:bg-zinc-200 md:dark:bg-zinc-900"
          : "md:bg-transparent")
      }
      onClick={() => {
        setTab(text);
      }}
    >
      <div
        className="-ml-4 h-6 w-1 bg-blue-500 dark:bg-blue-700 rounded-r-lg hidden md:block"
        style={{
          opacity: tab === text ? "100" : "0",
        }}
      />
      {tab === text ? <IconFilled size={30} /> : <Icon size={30} />}
      <p className="hidden md:block text-sm mt-1">{text}</p>
    </div>
  );
};

export default function UserNavBar({ tab, setTab, collapsed = false }) {
  if (collapsed) {
    return (
      <div className="flex h-full w-full md:flex-col md:justify-between">
        <div className="flex w-full justify-around md:flex-col md:items-center md:justify-start md:space-y-4">
          <NavBarItem
            tab={tab}
            setTab={setTab}
            Icon={HiOutlineHome}
            IconFilled={HiHome}
            text="Home"
            collapsed={collapsed}
          />

          <NavBarItem
            tab={tab}
            setTab={setTab}
            Icon={RiSearchLine}
            IconFilled={RiSearchEyeLine}
            text="Search"
            collapsed={collapsed}
          />

          <NavBarItem
            tab={tab}
            setTab={setTab}
            Icon={RiSettings4Line}
            IconFilled={RiSettings4Fill}
            text="Settings"
            collapsed={collapsed}
          />
        </div>

        <div className="hidden flex-col items-center gap-2 md:flex">
          <InfoCard collapsed={collapsed} />
          <DarkThemeToggle collapsed={collapsed} />
          <Logout collapsed={collapsed} />
        </div>
      </div>
    );
  }

  return (
    <div className="w-full md:-mt-2">
      <div className="flex md:flex-col md:space-y-2 md:space-x-0 w-full justify-around">
        <NavBarItem
          tab={tab}
          setTab={setTab}
          Icon={HiOutlineHome}
          IconFilled={HiHome}
          text="Home"
          collapsed={collapsed}
        />

        <NavBarItem
          tab={tab}
          setTab={setTab}
          Icon={RiSearchLine}
          IconFilled={RiSearchEyeLine}
          text="Search"
          collapsed={collapsed}
        />

        <NavBarItem
          tab={tab}
          setTab={setTab}
          Icon={RiSettings4Line}
          IconFilled={RiSettings4Fill}
          text="Settings"
          collapsed={collapsed}
        />
      </div>

      {/* visible only on large screens */}
      <div className="hidden md:flex flex-col">
        <div className="w-full border-t border-neutral-200 dark:border-neutral-800 my-4" />
        <InfoCard />
        <DarkThemeToggle />
        <div className="w-full border-t border-neutral-200 dark:border-neutral-800 my-4" />
        <Logout />
      </div>
    </div>
  );
}
