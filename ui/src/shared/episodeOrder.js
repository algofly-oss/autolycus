// Episode metadata comes from the same PTN parser as public-link titles.
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
const normalize = value => String(value || "").normalize("NFKC").replace(/[._\s-]+/g, " ").trim().toLocaleLowerCase();

export function sortEpisodes(entries) {
  return entries.map(entry => {
    const info = entry.episodeInfo;
    const directory = entry.path.split("/").slice(0, -1).join("/");
    return { entry, info, group: normalize(info?.series || directory) };
  }).sort((a, b) => {
    const group = collator.compare(a.group, b.group);
    if (group) return group;
    if (a.info && b.info) {
      const season = (a.info.season ?? 1) - (b.info.season ?? 1);
      if (season) return season;
      const episode = a.info.episode - b.info.episode;
      if (episode) return episode;
    } else if (!!a.info !== !!b.info) return a.info ? -1 : 1;
    return collator.compare(a.entry.label, b.entry.label) || collator.compare(a.entry.path, b.entry.path);
  }).map(item => item.entry);
}
