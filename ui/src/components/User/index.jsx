import { useState } from "react";
import UserNavBar from "./components/NavBar";
import { BiMeteor } from "react-icons/bi";
import Home from "./components/Home";
import { useRouter } from "next/router";
import uiRoutes from "@/shared/routes/uiRoutes";

export default function UserHome() {
  const router = useRouter();
  const [tab, setTab] = useState("Home");

  return (
    <div className="flex">
      <div
        className="bg-neutral-100 dark:bg-black flex items-center w-full md:px-4 fixed inset-x-0 bottom-0 z-10 h-16
        md:relative md:block md:h-screen md:w-96 2xl:w-[25%]- 2xl:w-[30rem] md:p-4 md:overflow-y-auto md:light-scrollbar dark:md:dark-scrollbar"
      >
        <div
          className="hidden md:flex space-x-3 items-center mt-2 mb-6 dark:text-neutral-300 cursor-pointer-"
          onClick={() => {
            // router.push(uiRoutes.root);
          }}
        >
          <BiMeteor size={40} />
          <p className="font-bold md:text-lg">Autolycus</p>
        </div>
        <UserNavBar tab={tab} setTab={setTab} />
      </div>
      <div className="w-full md:h-screen md:overflow-y-auto md:light-scrollbar dark:md:dark-scrollbar">
        {tab === "Home" && <Home />}
      </div>
      <div className="hidden lg:block w-[26rem] 2xl:w-[25%]- 2xl:w-[30rem] h-screen bg-neutral-100 dark:bg-black overflow-y-hidden md:light-scrollbar dark:md:dark-scrollbar"></div>
    </div>
  );
}
