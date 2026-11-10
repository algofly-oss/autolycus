import { ProfileSwitcher } from "@/shared/MediaProfiles";
import { HiOutlineHome, HiHome } from "react-icons/hi";
import { RiSearchLine, RiSearchEyeLine } from "react-icons/ri";
import { RiSettings4Line, RiSettings4Fill } from "react-icons/ri";
import DarkThemeToggle from "./components/DarkThemeToggle";
import InfoCard from "./components/InfoCard";
import Logout from "./components/Logout";

export default function UserNavBar({tab,setTab}) {
 return <div className="flex h-full min-h-0 min-w-0 flex-1 md:w-full md:flex-col md:justify-between">
   <div className="flex w-full items-center justify-around md:flex-col md:justify-start md:gap-4">
    {[["Home",HiOutlineHome,HiHome],["Search",RiSearchLine,RiSearchEyeLine],["Settings",RiSettings4Line,RiSettings4Fill]].map(([label,Outline,Filled])=><button key={label} type="button" aria-label={label} title={label} onClick={()=>setTab(label)} className={`flex h-10 w-10 items-center justify-center rounded-md transition-colors ${tab===label?"bg-blue-600 text-white":"text-neutral-600 hover:bg-zinc-200 dark:text-neutral-300 dark:hover:bg-zinc-900"}`}>{tab===label?<Filled size={24}/>:<Outline size={24}/>}</button>)}
    <ProfileSwitcher collapsed />
   </div>
   <div className="hidden flex-col items-center gap-2 md:flex"><InfoCard collapsed/><DarkThemeToggle collapsed/><Logout collapsed/></div>
 </div>;
}
