export const SORT_KEYS = {
  name: "name",
  seeds: "seeds",
  size: "size",
  date: "date",
};

export const DEFAULT_SORT_DIR = {
  [SORT_KEYS.name]: "asc",
  [SORT_KEYS.date]: "desc",
  [SORT_KEYS.seeds]: "desc",
  [SORT_KEYS.size]: "desc",
};

export const MOBILE_BREAKPOINT = 768;

export const INITIAL_SORT = {
  key: SORT_KEYS.seeds,
  dir: "desc",
};

export const ALL_SOURCES = "All";
export const REORDER_PULSE_MS = 220;
export const RESULTS_OFFSET_PADDING_REM = 2.5;

const FALLBACK_TRACKERS =
  "&tr=udp%3A%2F%2Ftracker.coppersurfer.tk%3A6969%2Fannounce" +
  "&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A6969%2Fannounce" +
  "&tr=udp%3A%2F%2F9.rarbg.to%3A2710%2Fannounce" +
  "&tr=udp%3A%2F%2F9.rarbg.me%3A2780%2Fannounce" +
  "&tr=udp%3A%2F%2F9.rarbg.to%3A2730%2Fannounce" +
  "&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337" +
  "&tr=http%3A%2F%2Fp4p.arenabg.com%3A1337%2Fannounce" +
  "&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce" +
  "&tr=udp%3A%2F%2Ftracker.tiny-vps.com%3A6969%2Fannounce" +
  "&tr=udp%3A%2F%2Fopen.stealth.si%3A80%2Fannounce";

export const FUSE_OPTIONS = {
  keys: [
    { name: "Title", weight: 1 },
    { name: "Tracker", weight: 0.2 },
  ],
  threshold: 0.35,
  ignoreLocation: true,
  minMatchCharLength: 2,
  useExtendedSearch: true,
};

export const formatBytes = (bytes) => {
  if (!bytes || isNaN(bytes)) return "—";
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let value = Number(bytes);
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[i]}`;
};

export const formatDate = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

export const formatCount = (num) => {
  if (!num || isNaN(num)) return "0";
  if (num < 1000) return String(num);

  const units = ["k", "M", "B"];
  let value = num;
  let i = -1;

  while (value >= 1000 && i < units.length - 1) {
    value /= 1000;
    i++;
  }

  return `${value >= 10 ? Math.round(value) : value.toFixed(1)}${units[i]}`;
};

export const truncateText = (text, length = 100) => {
  if (typeof text !== "string") return "";
  return text.length > length ? text.slice(0, length) + "..." : text;
};

export const sortResults = (
  data,
  { key = SORT_KEYS.name, dir = "asc" } = {},
) => {
  const factor = dir === "asc" ? 1 : -1;

  return [...data].sort((a, b) => {
    switch (key) {
      case SORT_KEYS.name:
        return factor * (a.Title || "").localeCompare(b.Title || "");
      case SORT_KEYS.seeds:
        return factor * ((a.Seeders ?? 0) - (b.Seeders ?? 0));
      case SORT_KEYS.size:
        return factor * ((a.Size ?? 0) - (b.Size ?? 0));
      case SORT_KEYS.date: {
        const aTime = a.PublishDate ? Date.parse(a.PublishDate) : 0;
        const bTime = b.PublishDate ? Date.parse(b.PublishDate) : 0;
        return factor * (aTime - bTime);
      }
      default:
        return 0;
    }
  });
};

export const getSavedSort = (torrentSearchState) => {
  const savedSort = torrentSearchState.get("sort");
  return savedSort?.key && savedSort?.dir ? savedSort : INITIAL_SORT;
};

export const getSourceCounts = (results) =>
  results.reduce((counts, result) => {
    if (!result.Tracker) return counts;
    counts[result.Tracker] = (counts[result.Tracker] || 0) + 1;
    return counts;
  }, {});

export const getOrderedSources = ({ loading, sourceCounts, sourceOrder }) => {
  if (loading) return [ALL_SOURCES, ...sourceOrder];

  const sortedSources = Object.entries(sourceCounts)
    .sort(([trackA, countA], [trackB, countB]) => {
      const countDiff = countB - countA;
      if (countDiff !== 0) return countDiff;
      return (trackA || "").localeCompare(trackB || "");
    })
    .map(([tracker]) => tracker);

  return [ALL_SOURCES, ...sortedSources];
};

const filterBySource = (results, activeSource) => {
  if (activeSource === ALL_SOURCES) return results;
  return results.filter((result) => result.Tracker === activeSource);
};

export const filterByTitle = ({ activeSource, fuse, results, titleFilter }) => {
  if (!titleFilter?.trim()) return filterBySource(results, activeSource);

  return fuse
    .search(titleFilter)
    .map((result) => result.item)
    .filter((result) =>
      activeSource === ALL_SOURCES ? true : result.Tracker === activeSource,
    );
};

export const getNextSort = (currentSort, key) => {
  const dir =
    currentSort.key === key
      ? currentSort.dir === "asc"
        ? "desc"
        : "asc"
      : (DEFAULT_SORT_DIR[key] ?? "asc");

  return { key, dir };
};

export const extractMagnet = (item) => {
  if (item?.MagnetUri) return item.MagnetUri;
  if (!item?.InfoHash) return null;
  return `magnet:?xt=urn:btih:${item.InfoHash}${FALLBACK_TRACKERS}`;
};

export const appendUniqueSource = (sources, tracker) => {
  if (!tracker || sources.includes(tracker)) return sources;
  return [...sources, tracker];
};
