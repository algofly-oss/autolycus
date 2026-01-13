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
    info = parse(name)

    # --- Clean title ---
    raw_title = info.get("title", "")
    raw_title = re.sub(r"^www\.[^ ]+\s*-\s*", "", raw_title, flags=re.I)
    raw_title = re.sub(r"[^\w\s.-]", "", raw_title)
    title = sanitize(raw_title)

    filetype = sanitize(info.get("filetype").lower()) if info.get("filetype") else None

    # --- Season / Episode ---
    season = first_int(info.get("season"))
    episode = first_int(info.get("episode"))

    se_part = None
    if season is not None and episode is not None:
        se_part = f"S{season:02d}.E{episode:02d}"
    elif season is not None:
        se_part = f"S{season:02d}"

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
