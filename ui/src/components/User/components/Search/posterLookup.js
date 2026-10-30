import apiRoutes from "@/shared/routes/apiRoutes";

const cache = new Map();
const queue = [];
let active = 0;
const MAX_REQUESTS = 3;
const MAX_CACHE = 256;

export const posterDescriptor = (item) => {
  const categories = Array.isArray(item.Category) ? item.Category : [];
  const ids = categories.map((category) => Number(category?.ID ?? category?.id ?? category));
  const tv = ids.some((id) => id >= 5000 && id < 6000) || Boolean(item.parsed?.season || item.parsed?.episode);
  const movie = ids.some((id) => id >= 2000 && id < 3000);
  const other = ids.some((id) => id >= 1000 && id < 8000) && !tv && !movie;
  const title = item.parsed?.title || item.Title || "";
  const year = item.parsed?.year || "";
  return {key: JSON.stringify([String(title).toLowerCase(), year, tv ? "tv" : "movie"]), name: String(item.Title || "").slice(0, 500), kind: tv ? "tv" : "movie", enabled: !other && Boolean(title)};
};

const pump = () => {
  while (active < MAX_REQUESTS && queue.length) {
    const job = queue.shift();
    if (!job.users) { cache.delete(job.key); job.resolve(null); continue; }
    active++;
    job.started = true;
    fetch(apiRoutes.searchPoster, {method:"POST", credentials:"include", headers:{"Content-Type":"application/json"}, body:JSON.stringify({name:job.name, kind:job.kind})})
      .then((response) => response.ok ? response.json() : null)
      .catch(() => null)
      .then((data) => { job.done = true; job.expiresAt = Date.now() + (data?.poster_url ? 86400000 : 300000); job.resolve(data); })
      .finally(() => { active--; pump(); });
  }
};

// Shared requests avoid fetching the same film once per release/indexer card.
export const subscribePoster = (descriptor, receive) => {
  let entry = cache.get(descriptor.key);
  if (entry?.done && entry.expiresAt <= Date.now()) { cache.delete(descriptor.key); entry = null; }
  if (entry) { cache.delete(descriptor.key); cache.set(descriptor.key, entry); }
  if (!entry) {
    if (queue.length >= 64) { receive(null); return () => {}; }
    entry = {...descriptor, users:0, started:false, done:false};
    entry.promise = new Promise((resolve) => { entry.resolve = resolve; });
    cache.set(descriptor.key, entry);
    queue.push(entry);
    for (const [key, value] of cache) {
      if (cache.size <= MAX_CACHE) break;
      if (value.done && !value.users) cache.delete(key);
    }
  }
  entry.users++;
  let subscribed = true;
  entry.promise.then((data) => { if (subscribed) receive(data); });
  pump();
  return () => { subscribed = false; entry.users = Math.max(0, entry.users - 1); };
};
