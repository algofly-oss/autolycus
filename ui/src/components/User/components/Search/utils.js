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

export const normalizeSearchText = (value) => String(value || "")
  .normalize("NFKD").replace(/\p{M}/gu, "")
  .toLowerCase()
  .replace(/dualaudio(?=hindi)/g, "dual audio ")
  .replace(/([a-z])(?=\d{3,4}p)/g, "$1 ")
  .replace(/[._-]+/g, " ").replace(/\s+/g, " ").trim();

export const FUSE_OPTIONS = {
  keys: [
    { name: "Title", weight: 1 },
    { name: "SearchTitle", weight: 1 },
  ],
  threshold: 0.35,
  ignoreLocation: true,
  minMatchCharLength: 2,
  useExtendedSearch: false,
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
        return factor * ((Number(a.Seeders) || 0) - (Number(b.Seeders) || 0))
          || (Number(b.SearchRelevance) || 0) - (Number(a.SearchRelevance) || 0);
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

const queryWords = (value) => normalizeSearchText(value).match(/[\p{L}\p{N}]+(?:\+\+|#)?/gu) || [];

const titleWords = (value) => {
  const text = normalizeSearchText(value);
  return [...new Set([
    ...(text.match(/[\p{L}\p{N}]+(?:\+\+|#)?/gu) || []),
    ...(text.match(/\d+/g) || []),
    ...[...text.matchAll(/(?:^|[^a-z0-9])(s\d{1,2}(?:e\d{1,3})?)(?![a-z0-9])/gi)].map((match) => match[1]),
  ])];
};

// Permit one edit only in long words; short terms must match whole words.
const similarWord = (query, word) => {
  if (query === word) return true;
  if (/\d/.test(query + word) || query.length < 6 || word.length < 6 || Math.abs(query.length - word.length) > 1) return false;
  let i = 0, j = 0, edits = 0;
  while (i < query.length && j < word.length) {
    if (query[i] === word[j]) { i++; j++; continue; }
    if (++edits > 1) return false;
    if (query.length === word.length && query[i] === word[j + 1] && query[i + 1] === word[j]) {
      i += 2; j += 2; continue;
    }
    if (query.length >= word.length) i++;
    if (word.length >= query.length) j++;
  }
  return edits + (query.length - i) + (word.length - j) <= 1;
};

const matchWords = (required, available, allowPrefix = false) => {
  return required.length > 0 && required.every((word) => available.some((candidate) => {
    if (allowPrefix && candidate.startsWith(word)) return true;
    // S01 should include S01E01 releases, while years and short words stay exact.
    if (/^s\d{1,2}$/i.test(word) && /^s\d{1,2}(?:e\d{1,3})?$/i.test(candidate)) {
      return Number(word.slice(1)) === Number(candidate.match(/^s(\d+)/i)[1]);
    }
    return similarWord(word, candidate);
  }));
};

const matchesVersions = (title, query) => {
  const versions = String(query).match(/\d+(?:\.\d+)+/g) || [];
  if (!versions.length) return true;
  const candidates = (String(title).match(/\d+(?:[.\s_-]+\d+)+/g) || [])
    .map((candidate) => candidate.split(/[.\s_-]+/));
  return versions.every((version) => {
    const parts = version.split(".");
    return candidates.some((candidate) => candidate.some((_, start) =>
      parts.every((part, index) => candidate[start + index] === part)));
  });
};

export const matchesTitleWords = (title, query) => matchWords(queryWords(query), titleWords(title)) && matchesVersions(title, query);

const titleWordCache = new WeakMap();
const cachedTitleWords = (item) => {
  const cached = titleWordCache.get(item);
  if (cached?.title === item.Title) return cached.words;
  const words = titleWords(item.Title);
  titleWordCache.set(item, { title: item.Title, words });
  return words;
};

export const filterByTitle = ({ activeSource, fuse, results, titleFilter, allowPrefix = false }) => {
  if (!titleFilter?.trim()) return filterBySource(results, activeSource);

  const required = queryWords(titleFilter);
  const tokens = required.filter((word) => word.length >= FUSE_OPTIONS.minMatchCharLength);
  const matches = new Set((tokens.length ? fuse.search({ $and: tokens.map((word) => ({ $or: [{ Title: word }, { SearchTitle: word }] })) }) : results.map((item) => ({ item }))).map((result) => result.item));
  return filterBySource(results, activeSource).filter((result) => matches.has(result) && matchWords(required, cachedTitleWords(result), allowPrefix) && matchesVersions(result.Title, titleFilter));
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

const canonicalHash = (value) => {
  const hash = String(value || "").trim();
  if (/^[a-f0-9]{40}$/i.test(hash)) return hash.toLowerCase();
  if (!/^[a-z2-7]{32}$/i.test(hash)) return null;
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const bits = [...hash.toUpperCase()].map((char) => alphabet.indexOf(char).toString(2).padStart(5, "0")).join("");
  return bits.match(/.{8}/g).map((byte) => parseInt(byte, 2).toString(16).padStart(2, "0")).join("");
};

export const extractMagnet = (item) => {
  if (item?.MagnetUri) {
    try {
      const url = new URL(item.MagnetUri.replace(/&amp;/g, "&"));
      if (url.protocol === "magnet:") {
        for (const topic of url.searchParams.getAll("xt")) {
          const hash = /^urn:btih:/i.test(topic) && canonicalHash(topic.slice(9));
          if (hash) {
            url.searchParams.delete("xt");
            const extra = url.searchParams.toString();
            return `magnet:?xt=urn:btih:${hash}${extra ? "&" + extra : ""}`;
          }
        }
      }
    } catch { /* Fall back to a valid info hash or server resolution. */ }
  }
  const hash = canonicalHash(item?.InfoHash);
  return hash ? `magnet:?xt=urn:btih:${hash}${FALLBACK_TRACKERS}` : null;
};

export const appendUniqueSource = (sources, tracker) => {
  if (!tracker || sources.includes(tracker)) return sources;
  return [...sources, tracker];
};

// Replace cached rows as fresh batches arrive, retaining separate indexer sources.
export const mergeSearchResults = (existing, incoming) => {
  const rows = [...existing];
  const positions = new Map(rows.map((item, index) => [item.SearchResultKey, index]).filter(([key]) => key));
  for (const item of incoming) {
    const key = item.SearchResultKey;
    if (key && positions.has(key)) rows[positions.get(key)] = item;
    else {
      if (key) positions.set(key, rows.length);
      rows.push(item);
    }
  }
  return rows;
};
