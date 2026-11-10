"""Shared PTN-backed file identity for queues and public-link names.

File episode markers take precedence over pack/folder metadata. Parsing filenames
requires no media reads, probes, network lookups or model inference.
"""
from pathlib import PurePosixPath
import re
from .torrent_name_parser import parse, first_int, format_title


def media_filename(path, torrent_name=""):
    path = PurePosixPath(str(path))
    filename = path.name
    info = dict(parse(filename))
    # Nearest folder first. Pack episode ranges are never inherited.
    contexts = [dict(parse(part)) for part in reversed(path.parts[:-1]) if part not in ("/", "downloads") and not re.fullmatch(r"[a-fA-F0-9-]{24,64}", part)]
    pack = dict(parse(str(torrent_name))) if torrent_name else {}
    if pack:
        contexts.append(pack)
    season = first_int(info.get("season"))
    episode = first_int(info.get("episode"))
    if episode is None:
        # Bare numbered episodes are meaningful in a season folder; years and
        # resolution-only names must never become episode numbers.
        numbered = re.match(r"^(\d{1,3})(?:\s*[-_. ]\s*|$)", path.stem)
        if numbered and any(context.get("season") is not None for context in contexts):
            info["episode"] = episode = int(numbered[1])
            info["episodeName"] = re.sub(r"^\d{1,3}[ ._-]*", "", path.stem).strip()
            info.pop("title", None)
    if episode is not None and season is None:
        for context in contexts:
            if context.get("season") is not None:
                info["season"] = season = first_int(context["season"])
                break
    # PTN may classify the text after a leading episode marker as the series.
    # For "Episode 02 - Pilot", the folder/pack supplies the series instead.
    episode_first = re.match(r"^(?:S\d{1,2}[ ._-]*E\d+|\d{1,2}x\d+|(?:Episode|Ep|E)[ ._-]*\d+)", path.stem, re.I)
    if not info.get("title") or (episode is not None and episode_first):
        for context in ([pack] if pack else []) + contexts:
            title = context.get("title")
            if title and not re.fullmatch(r"(?:Season|S)\s*\d+", title, re.I):
                if episode_first and info.get("title") and info["title"] != title and not info.get("episodeName"):
                    info["episodeName"] = info["title"]
                info["title"] = title
                break
    for field in ("year", "resolution", "quality", "codec", "audio", "language"):
        if not info.get(field):
            for context in contexts:
                if context.get(field):
                    info[field] = context[field]
                    break
    if not info.get("title"):
        info["title"] = path.stem
    info["title"] = str(info["title"]).strip(" ._-")
    return info


def episode_identity(path):
    info = media_filename(path)
    episode = first_int(info.get("episode"))
    if episode is None:
        return None
    return {"series": info.get("title", ""), "season": first_int(info.get("season")),
            "episode": episode, "episodes": info.get("episode")}


def public_file_title(path, torrent_name=""):
    return format_title(media_filename(path, torrent_name))


def file_presentation(path):
    info = media_filename(path)
    episode = first_int(info.get("episode"))
    season = first_int(info.get("season"))
    identity = None
    title = info["title"]
    if episode is not None:
        identity = {"series": title, "season": season, "episode": episode, "episodes": info.get("episode")}
        values = info.get("episode")
        end = max(values) if isinstance(values, list) else episode
        number = (f"S{season:02d} " if season is not None else "") + f"E{episode:02d}"
        if end != episode:
            number += f"–E{end:02d}"
        parts = [title, number]
        episode_name = info.get("episodeName")
        if episode_name and episode_name.casefold() != title.casefold():
            parts.append(episode_name.strip(" ._-"))
        title = " · ".join(parts)
    elif info.get("year"):
        title += f" ({info['year']})"
    return {"episode_info": identity, "display_name": title}
