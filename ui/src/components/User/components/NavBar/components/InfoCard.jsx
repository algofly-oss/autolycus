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
    const controller = new AbortController();
    const refresh = () => {
      axios
        .get(apiRoutes.diskUsage, { signal: controller.signal })
        .then((res) => setDiskStatus(res.data))
        .catch(() => {});
    };
    refresh();
    // Other users and applications share this drive too.
    const timer = setInterval(refresh, 30000);

    const onDiskUsage = (data) => {
      if (data) {
        setDiskStatus(data);
      }
    };
    socket.on(socketRoutes.stcDiskUsage, onDiskUsage);

    return () => {
      controller.abort();
      clearInterval(timer);
      socket.off(socketRoutes.stcDiskUsage, onDiskUsage);
    };
  }, [socket]);

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
    (diskStatus.drive_total || diskStatus.total)>0 ? ((diskStatus.drive_used ?? diskStatus.used)/(diskStatus.drive_total || diskStatus.total))*100 : 0;
  const normalizedUsage = Math.min(Math.max(usagePercentage, 0), 100);
  const driveUsage = normalizedUsage;
  const drivePercentageLabel=`${driveUsage.toFixed(1)}%`;

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

  const usedLabel = bytesToHumanReadable(diskStatus?.app_used || 0);
  const driveUsedLabel = bytesToHumanReadable(diskStatus?.drive_used ?? diskStatus?.used ?? 0);
  const driveTotalLabel = bytesToHumanReadable(diskStatus?.drive_total || diskStatus?.total || 0);
  const freeLabel = bytesToHumanReadable(diskStatus?.free || 0);
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
        label={
          <div className="w-48 text-xs">
            <div className="mb-2 flex items-center justify-between text-[11px] font-medium"><span className="opacity-60">Drive storage</span><span className="tabular-nums">{drivePercentageLabel} used</span></div>
            <div role="progressbar" aria-label="Overall drive space occupied" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Number(driveUsage.toFixed(1))} className="mb-2 h-1 overflow-hidden rounded-full bg-neutral-500/20"><div className="h-full rounded-full bg-blue-500" style={{width:`${driveUsage}%`}}/></div>
            <div className="flex justify-between gap-3"><span className="opacity-60">Used</span><span className="font-medium tabular-nums">{driveUsedLabel}</span></div>
            <div className="mt-1 flex justify-between gap-3"><span className="opacity-60">Total</span><span className="tabular-nums">{driveTotalLabel}</span></div>
            <div className="mt-1 flex justify-between gap-3"><span className="opacity-60">Free</span><span className="tabular-nums">{freeLabel}</span></div>
            <div className="mt-2 flex justify-between gap-3 border-t border-neutral-500/20 pt-2"><span className="opacity-60">Autolycus</span><span className="tabular-nums">{usedLabel}</span></div>
          </div>
        }
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
            padding: "9px 11px",
            borderRadius: 8,
            boxShadow: "0 4px 16px rgba(0, 0, 0, 0.14)",
          },
          arrow: {
            backgroundColor: isDarkTheme ? "#171717" : "#ffffff",
            borderColor: isDarkTheme ? "#33363b" : "#e5e5e5",
          },
        }}
      >
        <div
          className="hidden h-10 w-10 items-center justify-center rounded-md text-neutral-700 transition-colors hover:bg-zinc-200 md:flex dark:text-neutral-300 dark:hover:bg-zinc-900"
          aria-label={`Drive ${drivePercentageLabel} occupied, ${driveUsedLabel} of ${driveTotalLabel}; Autolycus uses ${usedLabel}`}
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

      <div className="flex items-center space-x-2" title={`Drive: ${driveUsedLabel} / ${driveTotalLabel} · ${drivePercentageLabel} used`}>
        <StorageGauge />
        <div className="py-0.5">
          <p
            className={`inline-block`}
            style={{
              color: activeSegment?.color,
            }}
          >
            {driveUsedLabel}
          </p>
          {" / "}
          <p className="inline-block">
            {driveTotalLabel}
          </p>
        </div>
      </div>
    </div>
  );
}
