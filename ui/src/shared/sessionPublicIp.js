import axios from "axios";
import apiRoutes from "./routes/apiRoutes";

export const PUBLIC_IP_REFRESH_INTERVAL_MS = 10 * 60 * 1000;

const PUBLIC_IP_CACHE_KEY = "autolycus:public-ip-cache:v1";
const PUBLIC_IP_SYNC_KEY = "autolycus:public-ip-session-sync:v1";

const PUBLIC_IP_PROVIDERS = [
  { url: "https://ifconfig.me/ip", responseType: "text" },
  { url: "https://ifconfig.co/json", responseType: "json", field: "ip" },
  { url: "https://api.ipify.org?format=json", responseType: "json" },
  { url: "https://api64.ipify.org?format=json", responseType: "json" },
  { url: "https://ipinfo.io/json", responseType: "json", field: "ip" },
];

const readStoredJson = (key) => {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(window.localStorage.getItem(key) || "null");
  } catch (error) {
    return null;
  }
};

const writeStoredJson = (key, value) => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {}
};

const looksLikeIpAddress = (value) => {
  const ip = String(value || "").trim();
  if (!ip || ip.length > 64 || /\s/.test(ip)) return false;

  const ipv4Part = "(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)";
  const ipv4Regex = new RegExp(`^${ipv4Part}(\\.${ipv4Part}){3}$`);
  if (ipv4Regex.test(ip)) return true;

  return ip.includes(":") && /^[0-9a-f:.]+$/i.test(ip);
};

const parsePublicIpResponse = async (response, responseType, field) => {
  if (!response.ok) return "";
  if (responseType === "text") {
    return (await response.text()).trim();
  }

  const data = await response.json();
  return String(field ? data?.[field] : data?.ip || "").trim();
};

const fetchWithTimeout = async (url, responseType, field) => {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 3500);
  try {
    const response = await fetch(url, {
      cache: "no-store",
      signal: controller.signal,
    });
    return await parsePublicIpResponse(response, responseType, field);
  } finally {
    window.clearTimeout(timeoutId);
  }
};

export const getPublicIpForSession = async ({ force = false } = {}) => {
  if (typeof window === "undefined") return "";

  const now = Date.now();
  const cached = readStoredJson(PUBLIC_IP_CACHE_KEY);
  if (
    !force &&
    cached?.ip &&
    Number(cached?.fetchedAt || 0) > now - PUBLIC_IP_REFRESH_INTERVAL_MS
  ) {
    return String(cached.ip);
  }

  for (const provider of PUBLIC_IP_PROVIDERS) {
    try {
      const ip = await fetchWithTimeout(
        provider.url,
        provider.responseType,
        provider.field
      );
      if (looksLikeIpAddress(ip)) {
        writeStoredJson(PUBLIC_IP_CACHE_KEY, { ip, fetchedAt: Date.now() });
        return ip;
      }
    } catch (error) {}
  }

  return "";
};

export const syncCurrentSessionPublicIp = async ({
  username,
  force = false,
  notify = true,
} = {}) => {
  if (typeof window === "undefined") {
    return { ok: false, error: "Public IP sync is only available in the browser." };
  }

  const userKey = username || "current";
  const syncKey = `${PUBLIC_IP_SYNC_KEY}:${userKey}`;
  const now = Date.now();
  const lastSync = readStoredJson(syncKey);

  if (
    !force &&
    Number(lastSync?.sentAt || 0) > now - PUBLIC_IP_REFRESH_INTERVAL_MS
  ) {
    return { ok: true, skipped: true, ip: lastSync?.ip || "" };
  }

  try {
    const ip = await getPublicIpForSession({ force });
    if (!ip) {
      return {
        ok: false,
        error: "Could not resolve your public IP from the browser.",
      };
    }

    const latestSync = readStoredJson(syncKey);
    if (
      !force &&
      latestSync?.ip === ip &&
      Number(latestSync?.sentAt || 0) >
        Date.now() - PUBLIC_IP_REFRESH_INTERVAL_MS
    ) {
      return { ok: true, skipped: true, ip };
    }

    await axios.patch(apiRoutes.updateCurrentSessionIp, { ip });
    writeStoredJson(syncKey, { ip, sentAt: Date.now() });

    if (notify) {
      window.dispatchEvent(
        new CustomEvent("autolycus:session-public-ip-updated")
      );
    }

    return { ok: true, ip };
  } catch (error) {
    return {
      ok: false,
      error:
        error?.response?.data?.detail ||
        "Could not update the current session public IP.",
    };
  }
};
