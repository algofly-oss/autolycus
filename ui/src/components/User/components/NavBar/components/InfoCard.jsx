import { useEffect, useState, useContext } from "react";
import { MdDownloading, MdOutlineDownloadDone } from "react-icons/md";
import axios from "axios";
import apiRoutes from "@/shared/routes/apiRoutes";
import socketRoutes from "@/shared/routes/socketRoutes";
import { SocketContext } from "@/shared/contexts/socket";
import useTheme from "@/shared/hooks/useTheme";

export default function InfoCard() {
  const theme = useTheme();
  const socket = useContext(SocketContext);
  const [diskStatus, setDiskStatus] = useState({ total: 0, used: 0 });
  const [downloadStatus, setDownloadStatus] = useState({
    active_downloads: 0,
    finished_downloads: 0,
  });

  // Disk Usage Status
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

  // Download Status
  useEffect(() => {
    axios
      .get(apiRoutes.downloadStatusTorrent)
      .then((res) => {
        setDownloadStatus(res?.data);
      })
      .catch((err) => {});

    socket.on(socketRoutes.stcDownloadStatus, (data) => {
      if (data) {
        setDownloadStatus(data);
      }
    });

    return () => {
      socket.off(socketRoutes.stcDownloadStatus);
    };
  }, []);

  const bytesToHumanReadable = (size) => {
    if (size === 0) return "0 B";
    const i = Math.floor(Math.log(size) / Math.log(1024));
    return `${(size / Math.pow(1024, i)).toFixed(2)} ${
      ["B", "KB", "MB", "GB", "TB"][i]
    }`;
  };

  // Calculate percentage used
  const usagePercentage =
    diskStatus.total > 0 ? (diskStatus.used / diskStatus.total) * 100 : 0;

  // Calculate circle circumference and dash offset
  const radius = 8;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset =
    circumference - (usagePercentage / 100) * circumference;

  return (
    <div className="bg-zinc-200 dark:bg-zinc-900 p-4 rounded-lg text-sm">
      <div className="flex items-center space-x-2">
        <MdDownloading size={20} />
        <p className="py-0.5">{downloadStatus.active_downloads} Active</p>
      </div>

      <div className="flex items-center space-x-2">
        <MdOutlineDownloadDone size={20} />
        <p className="py-0.5">{downloadStatus.finished_downloads} Finished</p>
      </div>

      <div className="flex items-center space-x-2">
        <svg width="20" height="20" viewBox="0 0 20 20">
          {/* Background circle */}
          <circle
            cx="10"
            cy="10"
            r={radius}
            fill="none"
            stroke={theme?.isDarkTheme ? "#c3c4c7" : "#282829"}
            strokeWidth="2"
          />
          {/* Progress circle */}
          <circle
            cx="10"
            cy="10"
            r={radius}
            fill="none"
            stroke={
              usagePercentage > 90
                ? "#ef4444" // Red for high usage
                : usagePercentage > 75
                ? "#f59e0b" // Amber for medium usage
                : "#10b981" // Green for low usage
            }
            strokeWidth="2"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            transform="rotate(-90 10 10)"
          />
        </svg>
        <div className="py-0.5">
          <p
            className={`inline-block ${
              usagePercentage > 90
                ? "text-red-600"
                : usagePercentage > 75
                ? "text-yellow-500"
                : "text-green-500"
            }`}
          >
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
