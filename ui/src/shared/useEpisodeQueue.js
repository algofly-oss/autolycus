import { useEffect, useState } from "react";
import apiRoutes from "@/shared/routes/apiRoutes";
import { sortEpisodes } from "@/shared/episodeOrder";
import { getFileType } from "@/shared/utils/fileUtils";

// Browse names only: never probe or download the queued media.
export default function useEpisodeQueue(root, enabled=true) {
  const [state, setState] = useState({ entries: [], loading: true, limited: false });
  useEffect(() => {
    const controller = new AbortController();
    if(!enabled){setState({entries:[],loading:false,limited:false});return()=>controller.abort();}
    setState({ entries: [], loading: true, limited: false });
    const entries = [], visited = new Set();
    const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
    let limited = false;
    const base = (root || "").replace(/^\/downloads\/*/, "").replace(/\/+$/, "");
    async function visit(path, depth) {
      if (controller.signal.aborted) return;
      if (visited.size >= 64 || depth > 8 || entries.length >= 500) { limited = true; return; }
      if (visited.has(path)) return;
      visited.add(path);
      const response = await fetch(`${apiRoutes.browseFiles}?path=${encodeURIComponent(path)}&names_only=true`, { signal: controller.signal });
      if (!response.ok) throw new Error("Could not read episode folder");
      const items = (await response.json()).filter(item => item.name && !/[\/\\]/.test(item.name) && item.name !== "." && item.name !== "..").sort((a, b) => collator.compare(a.name, b.name));
      for (const item of items) {
        if (entries.length >= 500) { limited = true; break; }
        const variant = item.name.match(/^(.+)_(144|240|360|480|720|1080|1440|2160)p\.mp4$/i);
        const isAlternate = variant && items.some(source => !source.is_directory && getFileType(source.name) === "video" && source.name.replace(/\.[^.]+$/, "") === variant[1]);
        if (!item.is_directory && !isAlternate && getFileType(item.name) === "video") {
          const file = [path, item.name].filter(Boolean).join("/");
          entries.push({ path: file, name: item.name, episodeInfo: item.episode_info, displayName: item.display_name, label: base ? file.slice(base.length + 1) : file });
        }
      }
      for (const item of items) if (item.is_directory) await visit([path, item.name].filter(Boolean).join("/"), depth + 1);
    }
    visit(base, 0).then(() => {
      if (!controller.signal.aborted) setState({ entries: sortEpisodes(entries), loading: false, limited });
    }).catch(() => {
      if (!controller.signal.aborted) setState({ entries: sortEpisodes(entries), loading: false, limited: true });
    });
    return () => controller.abort();
  }, [root,enabled]);
  return state;
}
