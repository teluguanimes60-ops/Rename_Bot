from __future__ import annotations

from dataclasses import dataclass
import re

from helper.database import db

DEFAULT_PREFIX = "@anitoon_edit"
DEFAULT_AUDIO_LANGUAGE = "Japanese"
DEFAULT_SUBTITLE_LANGUAGE = "English"

LANGUAGE_NAMES = {
    "en": "English", "eng": "English",
    "ja": "Japanese", "jpn": "Japanese",
    "ko": "Korean", "kor": "Korean",
    "zh": "Chinese", "zho": "Chinese", "chi": "Chinese",
    "hi": "Hindi", "hin": "Hindi",
    "te": "Telugu", "tel": "Telugu",
    "ta": "Tamil", "tam": "Tamil",
    "ml": "Malayalam", "mal": "Malayalam",
    "fr": "French", "fra": "French",
    "de": "German", "deu": "German",
    "es": "Spanish", "spa": "Spanish",
    "it": "Italian", "ita": "Italian",
    "pt": "Portuguese", "por": "Portuguese",
    "ru": "Russian", "rus": "Russian",
    "ar": "Arabic", "ara": "Arabic",
}

def language_name(language: str | None, fallback: str) -> str:
    value = str(language or "").strip()
    return LANGUAGE_NAMES.get(value.lower(), value if value and value.lower() != "und" else fallback)


@dataclass(frozen=True)
class MetadataSettings:
    audio_prefix: str = DEFAULT_PREFIX
    audio_language: str = DEFAULT_AUDIO_LANGUAGE
    audio_suffix: str = ""
    subtitle_prefix: str = DEFAULT_PREFIX
    subtitle_language: str = DEFAULT_SUBTITLE_LANGUAGE
    subtitle_suffix: str = ""

    @property
    def audio_name(self) -> str:
        return _join(self.audio_prefix, self.audio_language, self.audio_suffix)

    @property
    def subtitle_name(self) -> str:
        return _join(self.subtitle_prefix, self.subtitle_language, self.subtitle_suffix)


def _clean_language(value: object, fallback: str) -> str:
    value = str(value or "").strip()
    return value or fallback


def _clean_affix(value: object) -> str:
    return str(value or "").strip()


def _join(prefix: str, language: str, suffix: str) -> str:
    return " ".join(
        part for part in (
            _clean_affix(prefix),
            _clean_language(language, DEFAULT_AUDIO_LANGUAGE),
            _clean_affix(suffix),
        )
        if part
    ).strip()


def _legacy_parts(
    value: object,
    default_prefix: str,
    default_language: str,
) -> tuple[str, str, str]:
    text = str(value or "").strip()
    if not text or text == "AniToon Official":
        return default_prefix, default_language, ""

    # Old data stored "[AniToon] Japanese" in one field.
    if text.lower().startswith("[anitoon]"):
        remainder = text[len("[AniToon]"):].strip()
        return default_prefix, remainder or default_language, ""

    if text.startswith("[") and "]" in text:
        end = text.find("]") + 1
        return text[:end].strip(), text[end:].strip() or default_language, ""

    # If an old value only contains a language, keep it and use the new
    # default prefix.
    if " " not in text:
        return default_prefix, text, ""

    return default_prefix, text, ""


async def get_metadata(user_id: int) -> MetadataSettings:
    await db.add_user(user_id)
    user = await db.get_user_data(user_id) or {}

    ap, al, asuf = _legacy_parts(
        user.get("audio_name"),
        DEFAULT_PREFIX,
        DEFAULT_AUDIO_LANGUAGE,
    )
    sp, sl, ssuf = _legacy_parts(
        user.get("sub_name"),
        DEFAULT_PREFIX,
        DEFAULT_SUBTITLE_LANGUAGE,
    )

    return MetadataSettings(
        audio_prefix=(
            str(user.get("audio_prefix")).strip()
            if user.get("audio_prefix") is not None
            else ap
        ),
        audio_language=_clean_language(
            user.get("audio_language"),
            al,
        ),
        audio_suffix=_clean_affix(
            user.get("audio_suffix", asuf)
        ),
        subtitle_prefix=(
            str(user.get("subtitle_prefix")).strip()
            if user.get("subtitle_prefix") is not None
            else sp
        ),
        subtitle_language=_clean_language(
            user.get("subtitle_language"),
            sl,
        ),
        subtitle_suffix=_clean_affix(
            user.get("subtitle_suffix", ssuf)
        ),
    )


async def save_metadata(
    user_id: int,
    settings: MetadataSettings,
) -> None:
    await db.set_metadata_parts(
        user_id,
        audio_prefix=settings.audio_prefix,
        audio_language=settings.audio_language,
        audio_suffix=settings.audio_suffix,
        subtitle_prefix=settings.subtitle_prefix,
        subtitle_language=settings.subtitle_language,
        subtitle_suffix=settings.subtitle_suffix,
    )


async def update_metadata_part(
    user_id: int,
    kind: str,
    field: str,
    value: str,
) -> MetadataSettings:
    current = await get_metadata(user_id)
    values = {
        "audio_prefix": current.audio_prefix,
        "audio_language": current.audio_language,
        "audio_suffix": current.audio_suffix,
        "subtitle_prefix": current.subtitle_prefix,
        "subtitle_language": current.subtitle_language,
        "subtitle_suffix": current.subtitle_suffix,
    }

    key = f"{kind}_{field}"
    if key not in values:
        raise ValueError("Invalid metadata field")

    values[key] = str(value).strip()

    if field == "language" and not values[key]:
        raise ValueError("Language cannot be empty")

    updated = MetadataSettings(**values)
    await save_metadata(user_id, updated)
    return updated




def _detect_language_from_title(title: str) -> str:
    text = str(title or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    for code, name in LANGUAGE_NAMES.items():
        if re.search(r"\b" + re.escape(name.lower()) + r"\b", lowered):
            return name
    return ""


def _track_language_name(tags: dict, fallback: str) -> tuple[str, str | None]:
    code = str((tags or {}).get("language") or "").strip()
    name = language_name(code, "")
    if not name:
        name = _detect_language_from_title((tags or {}).get("title"))
    if not name:
        name = fallback
    normalized_code = code if code and code.lower() != "und" else None
    return name, normalized_code


async def apply_metadata_to_media(input_file: str, output_file: str, settings: MetadataSettings) -> str | None:
    """Remux media without re-encoding and label every audio/subtitle track.

    Video/audio codecs are copied exactly. The only changes are stream metadata:
    language tags are preserved when present and the title becomes
    '<prefix> <Language> <suffix>'.
    """
    import asyncio
    import json
    import os

    if not os.path.isfile(input_file) or os.path.getsize(input_file) <= 0:
        return None

    cmd = ["ffmpeg", "-y", "-i", input_file, "-map", "0", "-c", "copy"]
    data = await _probe_local(input_file)
    audio_i = 0
    subtitle_i = 0

    for stream in data.get("streams", []):
        kind = stream.get("codec_type")
        if kind not in {"audio", "subtitle"}:
            continue

        tags = stream.get("tags") or {}
        fallback = "Unknown"
        language, code = _track_language_name(
            tags,
            fallback,
        )

        if kind == "audio":
            prefix, suffix = settings.audio_prefix, settings.audio_suffix
            spec = f"a:{audio_i}"
            audio_i += 1
        else:
            prefix, suffix = settings.subtitle_prefix, settings.subtitle_suffix
            spec = f"s:{subtitle_i}"
            subtitle_i += 1

        title = _join(prefix, language, suffix)
        cmd += [f"-metadata:s:{spec}", f"title={title}"]
        if code:
            cmd += [f"-metadata:s:{spec}", f"language={code}"]

    if audio_i == 0 and subtitle_i == 0:
        if os.path.abspath(input_file) != os.path.abspath(output_file):
            import shutil
            shutil.copy2(input_file, output_file)
        return output_file

    cmd.append(output_file)

    from helper.ffmpeg import _run_ffmpeg

    duration = 0.0
    try:
        duration = float(data.get("format", {}).get("duration", 0) or 0)
    except (TypeError, ValueError):
        duration = 0.0

    ok = await _run_ffmpeg(cmd, None, duration)
    if not ok or not os.path.isfile(output_file) or os.path.getsize(output_file) <= 0:
        return None
    return output_file


async def _probe_local(file_path: str) -> dict:
    import asyncio
    import json

    cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", file_path]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await process.communicate()
    try:
        return json.loads(stdout.decode(errors="ignore"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}

async def reset_metadata(user_id: int) -> MetadataSettings:
    settings = MetadataSettings()
    await save_metadata(user_id, settings)
    return settings
