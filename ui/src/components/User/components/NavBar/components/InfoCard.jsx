import { useEffect, useState, useContext } from "react";
import { MdDownloading, MdOutlineDownloadDone } from "react-icons/md";
import axios from "axios";
import apiRoutes from "@/shared/routes/apiRoutes";
import socketRoutes from "@/shared/routes/socketRoutes";
import { SocketContext } from "@/shared/contexts/socket";
import useTheme from "@/shared/hooks/useTheme";
import { Tooltip, useMantineColorScheme } from "@mantine/core";

export default function InfoCard({ collapsed = false }) {
  const theme = useTheme();
  const { colorScheme } = useMantineColorScheme();
  const isDarkTheme = colorScheme === "dark";
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
  const normalizedUsage = Math.min(Math.max(usagePercentage, 0), 100);

  const segments = [
    { start: 0, end: 30, color: "#34C759" },
    { start: 30, end: 60, color: "#0A84FF" },
    { start: 60, end: 80, color: "#FF9F0A" },
    { start: 80, end: 100, color: "#FF3B30" },
  ];
  const getSegmentForValue = (value) => {
    if (!segments.length) return null;
    for (let i = 0; i < segments.length; i++) {
      if (value >= segments[i].start && value <= segments[i].end) {
        return segments[i];
      }
    }
    return segments[segments.length - 1] ?? segments[0];
  };

  const usedLabel = bytesToHumanReadable(diskStatus?.used || 0);
  const totalLabel = bytesToHumanReadable(diskStatus?.total || 0);
  const activeSegment = getSegmentForValue(normalizedUsage) ?? segments[0];

  const StorageGauge = ({ size = 20, strokeWidth = 2, radius = 8 }) => {
    const center = size / 2;
    const circumference = 2 * Math.PI * radius;

    return (
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={theme?.isDarkTheme ? "#ffffff" : "#000000"}
          strokeWidth={strokeWidth}
        />
        {segments.map((segment) => {
          const segmentFill = Math.max(
            0,
            Math.min(normalizedUsage, segment.end) - segment.start
          );
          if (segmentFill <= 0) return null;

          const segmentLength = (segmentFill / 100) * circumference;
          const segmentOffset =
            circumference - (segment.start / 100) * circumference;

          return (
            <circle
              key={`${segment.start}-${segment.end}`}
              cx={center}
              cy={center}
              r={radius}
              fill="none"
              stroke={segment.color}
              strokeWidth={strokeWidth}
              strokeDasharray={`${segmentLength} ${
                circumference - segmentLength
              }`}
              strokeDashoffset={segmentOffset}
              transform={`rotate(-90 ${center} ${center})`}
            />
          );
        })}
      </svg>
    );
  };

  if (collapsed) {
    return (
      <Tooltip
        label={`Storage: ${usedLabel} / ${totalLabel}`}
        position="right"
        openDelay={0}
        closeDelay={0}
        transitionDuration={0}
        withinPortal
        zIndex={1000}
        withArrow
        styles={{
          tooltip: {
            backgroundColor: isDarkTheme ? "#171717" : "#ffffff",
            border: `1px solid ${isDarkTheme ? "#33363b" : "#e5e5e5"}`,
            color: isDarkTheme ? "#ffffff" : "#171717",
          },
          arrow: {
            backgroundColor: isDarkTheme ? "#171717" : "#ffffff",
            borderColor: isDarkTheme ? "#33363b" : "#e5e5e5",
          },
        }}
      >
        <div
          className="hidden h-10 w-10 items-center justify-center rounded-md text-neutral-700 transition-colors hover:bg-zinc-200 md:flex dark:text-neutral-300 dark:hover:bg-zinc-900"
          aria-label={`Storage used ${usedLabel} of ${totalLabel}`}
        >
          <StorageGauge size={24} strokeWidth={2.5} radius={9} />
        </div>
      </Tooltip>
    );
  }

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
        <StorageGauge />
        <div className="py-0.5">
          <p
            className={`inline-block`}
            style={{
              color: activeSegment?.color,
            }}
          >
            {usedLabel}
          </p>
          {" / "}
          <p className="inline-block">
            {totalLabel}
          </p>
        </div>
      </div>
    </div>
  );
}
