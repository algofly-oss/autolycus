import { useEffect, useState, useContext } from "react";
import {
  MdDownloading,
  MdOutlineDownloadDone,
  MdDataSaverOff,
} from "react-icons/md";
import axios from "axios";
import apiRoutes from "@/shared/routes/apiRoutes";
import socketRoutes from "@/shared/routes/socketRoutes";
import { SocketContext } from "@/shared/contexts/socket";

export default function InfoCard() {
  const socket = useContext(SocketContext);
  const [diskStatus, setDiskStatus] = useState({ total: 0, used: 0 });

  useEffect(() => {
    axios
      .get(apiRoutes.diskUsage)
      .then((res) => {
        setDiskStatus(res?.data);
      })
      .catch((err) => {});

    socket.on(socketRoutes.stcDiskUsage, (data) => {
      if (data) {
        setDiskStatus(data);
      }
    });

    return () => {
      socket.off(socketRoutes.stcDiskUsage);
    };
  }, []);

  const bytesToHumanReadable = (size) => {
    const i = Math.floor(Math.log(size) / Math.log(1024));
    return (
      (size / Math.pow(1024, i)).toFixed(2) * 1 +
      " " +
      ["B", "KB", "MB", "GB", "TB"][i]
    );
  };

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
          <p className="inline-block text-red-500">
            {bytesToHumanReadable(diskStatus?.used)}
          </p>
          {" / "}
          <p className="inline-block">
            {bytesToHumanReadable(diskStatus?.total)}
          </p>
        </div>
      </div>
    </div>
  );
}
