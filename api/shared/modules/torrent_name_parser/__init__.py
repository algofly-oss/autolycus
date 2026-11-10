#!/usr/bin/env python
import sys


if sys.version_info.major == 3:
    import importlib

    re = importlib.import_module("re")

elif sys.version_info.major == 2:
    import pkgutil

    # Regex in python 2 is very slow so we check if the faster 'regex' library is available.
    faster_regex = pkgutil.find_loader("regex")
    if faster_regex is not None:
        re = faster_regex.load_module("regex")
    else:
        re = pkgutil.find_loader("re").load_module("re")

from .parse import PTN
import unicodedata


def parse(name, standardise=True, coherent_types=False):
    # Release sites prepend their domain to both torrent and file names.
    # Remove it before parsing so every metadata consumer gets the film title.
    domain = r"(?:https?://)?(?:www\.)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/)?"
    name = re.sub(r"^\s*(?:" + domain + r"\s+-\s+|\[" + domain + r"\]\s*(?:-\s*)?)", "", name, flags=re.I)
    return PTN().parse(name, standardise, coherent_types)


def sanitize(text):
    if not text:
        return None

    # normalize & drop emojis / non-ascii
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("ascii", "ignore").decode("ascii")

    # convert spaces to dots
    text = text.replace(" ", ".")

    # keep only url-safe chars
    text = re.sub(r"[^A-Za-z0-9._+-]", "", text)

    # collapse multiple dots
    text = re.sub(r"\.{2,}", ".", text)

    return text.strip(".")


def first_int(value):
    if value is None:
        return None
    if isinstance(value, list):
        return int(value[0]) if value else None
    return int(value)


def parse_title(name):
    return format_title(parse(name))


def format_title(info):

    # --- Clean title ---
    raw_title = info.get("title", "")
    raw_title = re.sub(r"^www\.[^ ]+\s*-\s*", "", raw_title, flags=re.I)
    raw_title = re.sub(r"[^\w\s.-]", "", raw_title)
    title = sanitize(raw_title)

    filetype = sanitize(info.get("filetype").lower()) if info.get("filetype") else None

    # --- Season / Episode ---
    season = first_int(info.get("season"))
    episode = first_int(info.get("episode"))

    se_part = f"S{season:02d}" if season is not None else ""
    if episode is not None:
        episodes = info.get("episode")
        values = sorted(set(int(value) for value in episodes)) if isinstance(episodes, list) else [episode]
        if len(values) > 1 and values == list(range(values[0], values[-1] + 1)):
            episode_part = f"E{values[0]:02d}-E{values[-1]:02d}"
        else:
            episode_part = ".".join(f"E{value:02d}" for value in values)
        se_part = ".".join(part for part in (se_part, episode_part) if part)

    parts = [
        title,
        se_part,
        sanitize(info.get("year")),
        sanitize(info.get("resolution")),
        sanitize(info.get("quality")),
        sanitize(info.get("codec")),
        sanitize(info.get("audio")),
        (
            "+".join(sanitize(lang) for lang in info["language"])
            if info.get("language")
            else None
        ),
        filetype,
    ]

    return ".".join(p for p in parts if p)
