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
  { key = SORT_KEYS.name, dir = "asc" } = {}
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
