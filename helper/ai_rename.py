from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.error
import urllib.request

from config import Config

_WASTE_PATTERNS = [
    r"https?://\S+",
    r"www\.\S+",
    r"@[A-Za-z0-9_]+",
    r"#[A-Za-z0-9_]+",
    r"\b(?:www|http|https)\b",
    r"\b(?:telegram|t\.me|joinchat|contact|subscribe|watch online)\b",
    r"\b(?:uploaded by|encoded by|rip by|re-encoded by)\b.*$",
    r"\b(?:x264|x265|h[.]264|h[.]265|hevc|av1|avc|10bit|8bit|hdr10\+?|dv|dolby[ .-]?vision)\b",
    r"\b(?:web[ .-]?dl|web[ .-]?rip|bluray|brrip|webrip|hdtv|dvdrip|remux|proper|repack)\b",
    r"\b(?:480p|576p|720p|1080p|1440p|2160p|4k|8k)\b",
    r"\b(?:aac(?:[- .]?\d[.]?\d)?|ddp?\d?(?:[.]\d)?|ac3|eac3|dts(?:-hd)?|truehd|flac|opus|mp3)\b",
]


def _safe_stem(value: str) -> str:
    value = str(value or "").strip()
    value = re.sub(r"[\x00-\x1f\x7f]", "", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r'[\\/:*?"<>|]', " ", value)
    value = re.sub(r"\s*[-_.]{2,}\s*", " - ", value)
    value = re.sub(r"\s+", " ", value).strip(" .-_")
    return value[:240]


def heuristic_auto_name(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(str(filename or "")))[0]
    text = stem.replace("_", " ").replace(".", " ")
    text = re.sub(r"[\[\]{}()]+", " ", text)
    text = re.sub(r"[-]{2,}", " ", text)
    for pattern in _WASTE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\bS\s*(\d{1,2})\s*[-._ ]?E(?:P|pisode)?\s*(\d{1,4})\b",
        r"S\1E\2",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:episode|ep)\s*[-._ ]?\s*(\d{1,4})\b",
        r"Episode \1",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b(\d{1,2})x(\d{1,4})\b", r"S\1E\2", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -_.")
    return _safe_stem(text) or _safe_stem(stem) or "AniToon"


def _extract_output_text(data: dict) -> str:
    direct = data.get("output_text")
    if direct:
        return str(direct).strip()
    for item in data.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") == "output_text" and content.get("text"):
                return str(content.get("text")).strip()
    return ""



def extract_template_values(filename: str) -> dict[str, str]:
    original = os.path.basename(str(filename or ""))
    stem, ext = os.path.splitext(original)
    clean = heuristic_auto_name(original)

    season = ""
    episode = ""
    year = ""
    resolution = ""
    language = ""

    match = re.search(r"\bS(\d{1,2})\b", stem, re.I)
    if match:
        season = f"S{match.group(1)}"
    match = re.search(r"\b(?:E|EP|Episode)\s*[-._ ]?\s*(\d{1,4})\b", stem, re.I)
    if match:
        episode = f"E{match.group(1)}"
    match = re.search(r"\b(19\d{2}|20\d{2})\b", stem)
    if match:
        year = match.group(1)
    match = re.search(r"\b(2160p|1440p|1080p|720p|576p|480p|4k|8k)\b", stem, re.I)
    if match:
        resolution = match.group(1)

    languages = {
        "english": "English", "japanese": "Japanese", "korean": "Korean",
        "chinese": "Chinese", "hindi": "Hindi", "telugu": "Telugu",
        "tamil": "Tamil", "malayalam": "Malayalam", "french": "French",
        "german": "German", "spanish": "Spanish", "italian": "Italian",
        "portuguese": "Portuguese", "russian": "Russian", "arabic": "Arabic",
    }
    lowered = stem.lower()
    for key, label in languages.items():
        if re.search(r"\b" + re.escape(key) + r"\b", lowered):
            language = label
            break

    return {
        "name": stem,
        "filename": original,
        "ext": ext.lstrip("."),
        "title": clean,
        "season": season,
        "episode": episode,
        "year": year,
        "resolution": resolution,
        "language": language,
    }


def apply_permanent_template(template: str, filename: str) -> str:
    values = extract_template_values(filename)
    rendered = str(template or "").strip()
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    # Clean empty placeholder remnants and whitespace without changing the
    # user's meaningful text.
    rendered = re.sub(r"\s+", " ", rendered)
    rendered = re.sub(r"\s*[-|:_/]+\s*[-|:_/]+", " - ", rendered)
    rendered = rendered.strip(" .-_|:")
    return _safe_stem(rendered) or _safe_stem(values["name"]) or "AniToon"
async def ai_auto_name(filename: str) -> str:
    fallback = heuristic_auto_name(filename)
    api_key = getattr(Config, "OPENAI_API_KEY", "").strip()
    if not api_key:
        return fallback

    model = getattr(Config, "OPENAI_RENAME_MODEL", "gpt-5.6-sol").strip() or "gpt-5.6-sol"
    source = os.path.basename(str(filename or ""))
    prompt = (
        "Clean this media filename for a Telegram anime/media rename bot.\n"
        "Return ONLY the final filename stem, with no extension and no quotes.\n"
        "Remove junk such as @handles, #hashtags, URLs, uploader/release group names, "
        "subscription/contact text, repeated separators, codec/encoding labels, bitrate, "
        "file-host words, and other meaningless release noise.\n"
        "Keep meaningful information such as the actual title, season/episode, year, "
        "part number, and useful language information when it is genuinely part of the title.\n"
        "Use normal spaces and clean capitalization. Do not invent information.\n\n"
        f"Original filename: {source}"
    )
    body = {
        "model": model,
        "input": prompt,
        "max_output_tokens": 120,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        def _request() -> str:
            with urllib.request.urlopen(request, timeout=25) as response:
                return response.read().decode("utf-8", errors="replace")

        raw = await asyncio.to_thread(_request)
        data = json.loads(raw)
        result = _safe_stem(_extract_output_text(data))
        result = re.sub(r"^['\`]+|['\`]+$", "", result).strip()
        result = re.sub(r"\.[A-Za-z0-9]{1,6}$", "", result).strip(" .-_")
        return _safe_stem(result) or fallback
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        return fallback
