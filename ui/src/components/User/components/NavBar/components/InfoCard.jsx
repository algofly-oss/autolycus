import {
  MdDownloading,
  MdOutlineDownloadDone,
  MdDataSaverOff,
} from "react-icons/md";

export default function InfoCard() {
  return (
    <div className="bg-zinc-200 dark:bg-zinc-900 p-4 rounded-lg text-sm">
      <div className="flex items-center space-x-2">
        <MdDownloading size={20} />
        <p className="py-0.5">{4} Active</p>
      </div>

      <div className="flex items-center space-x-2">
        <MdOutlineDownloadDone size={20} />
        <p className="py-0.5">{2} Finished</p>
      </div>

      <div className="flex items-center space-x-2">
        <MdDataSaverOff size={20} />
        <div className="py-0.5">
          <p className="inline-block text-red-500">4.85 GB</p>
          {" / "}
          <p className="inline-block">5.00 GB</p>
        </div>
      </div>
    </div>
  );
}
