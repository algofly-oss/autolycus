import { useEffect, useState } from "react";
import { FiExternalLink } from "react-icons/fi";
import { MdContentCopy } from "react-icons/md";
import useToast from "@/shared/hooks/useToast";
import { getQuality } from "@/shared/utils/fileUtils";
import {
  CLIPBOARD_COPY_STATUS,
  copyTextToClipboard,
} from "@/shared/utils/clipboard";
import { formatBytes, formatDate } from "../utils";

const TRACKERS =
  "&tr=udp%3A%2F%2Ftracker.coppersurfer.tk%3A6969%2Fannounce&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A6969%2Fannounce&tr=udp%3A%2F%2F9.rarbg.to%3A2710%2Fannounce&tr=udp%3A%2F%2F9.rarbg.me%3A2780%2Fannounce&tr=udp%3A%2F%2F9.rarbg.to%3A2730%2Fannounce&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337&tr=http%3A%2F%2Fp4p.arenabg.com%3A1337%2Fannounce&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce&tr=udp%3A%2F%2Ftracker.tiny-vps.com%3A6969%2Fannounce&tr=udp%3A%2F%2Fopen.stealth.si%3A80%2Fannounce";

const buildSourceUrl = (item) => item?.Details || item?.Link || item?.Url || item?.URL;

const buildProxiedUrl = (url, browserProxyBaseUrl) => {
  if (!url || !browserProxyBaseUrl) return null;
  return `${browserProxyBaseUrl}/tor/${url}`;
};

const buildMagnet = (item) => {
  if (item?.MagnetUri) return item.MagnetUri;
  if (item?.InfoHash) return `magnet:?xt=urn:btih:${item.InfoHash}${TRACKERS}`;
  return null;
};

const DetailField = ({ label, value }) => (
  <div>
    <span className="text-sm text-gray-500 dark:text-gray-400">{label}</span>
    <p className="font-medium break-words">{value || "—"}</p>
  </div>
);

export default function SearchResultDetails({ item }) {
  const [browserProxyBaseUrl, setBrowserProxyBaseUrl] = useState("");
  const toast = useToast();

  useEffect(() => {
    if (typeof window === "undefined") return;
    setBrowserProxyBaseUrl(window.location.origin);
  }, []);

  if (!item) {
    return (
      <div className="p-6 text-gray-500 dark:text-gray-400">
        <h2 className="text-lg font-semibold text-gray-700 dark:text-gray-200">
          Search Details
        </h2>
        <p className="mt-3 text-sm leading-relaxed">
          Hover a search result to preview its source, size, availability, and
          links here.
        </p>
      </div>
    );
  }

  const title = item?.Title || "Untitled";
  const sourceUrl = buildSourceUrl(item);
  const proxiedSourceUrl = buildProxiedUrl(sourceUrl, browserProxyBaseUrl);
  const magnet = buildMagnet(item);
  const { resolution, source } = getQuality(title);
  const seeders =
    item?.Seeders || item?.Seeders === 0 ? String(item.Seeders) : "—";
  const peers = item?.Peers || item?.Peers === 0 ? String(item.Peers) : "—";

  const copyMagnetToClipboard = async () => {
    if (!magnet) {
      toast.error("Magnet not found");
      return;
    }

    const status = await copyTextToClipboard(magnet);

    if (status === CLIPBOARD_COPY_STATUS.COPIED) {
      toast.success("Magnet copied to clipboard");
    } else if (status === CLIPBOARD_COPY_STATUS.MANUAL) {
      toast.success("Magnet opened for manual copy");
    } else {
      toast.error("Failed to copy magnet");
    }
  };

  return (
    <div className="p-6 text-gray-800 dark:text-gray-200">
      <h2 className="text-xl font-bold mb-6 break-words">{title}</h2>

      {(resolution || source) && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-2">
            Quality Info
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <DetailField label="Resolution" value={resolution} />
            <DetailField label="Source" value={source} />
          </div>
        </div>
      )}

      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-2">
          Availability
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <DetailField label="Seeders" value={seeders} />
          <DetailField label="Peers" value={peers} />
          <DetailField label="Size" value={formatBytes(item?.Size)} />
          <DetailField label="Published" value={formatDate(item?.PublishDate)} />
        </div>
      </div>

      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-2">
          Source
        </h3>
        <div className="space-y-2 text-sm">
          <DetailField label="Tracker" value={item?.Tracker} />
          {sourceUrl && (
            <div className="flex flex-wrap gap-3 pt-1">
              <a
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-500 hover:text-blue-600 transition"
              >
                <FiExternalLink size={14} />
                Open source
              </a>
              {proxiedSourceUrl && (
                <a
                  href={proxiedSourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-purple-500 hover:text-purple-600 transition"
                >
                  🌍 Proxy
                </a>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400">
          Magnet URI
        </h3>
        <div className="flex items-center space-x-2 mb-2">
          <span className="flex-1 text-sm truncate font-medium" title={magnet || ""}>
            {magnet || "—"}
          </span>
          {magnet && (
            <MdContentCopy
              onClick={copyMagnetToClipboard}
              className="cursor-pointer"
            />
          )}
        </div>
      </div>
    </div>
  );
}
