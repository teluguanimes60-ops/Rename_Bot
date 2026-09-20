from __future__ import annotations

import os
import asyncio

from helper.database import db
from helper.ffmpeg import take_screenshot


def _message_thumbnail_file_id(source) -> str | None:
    media = (
        getattr(source, "video", None)
        or getattr(source, "document", None)
        or getattr(source, "audio", None)
    )
    if media is None:
        return None
    thumbs = getattr(media, "thumbs", None) or []
    if not thumbs:
        return None
    file_id = getattr(thumbs[0], "file_id", None)
    return str(file_id) if file_id else None

async def _normalize_thumbnail(client, job, source, tag: str):
    if not source:
        return None, None
    raw = os.path.join(job.work_dir, f".thumb_raw_{tag}.jpg")
    final = os.path.join(job.work_dir, f".thumb_{tag}.jpg")
    try:
        os.makedirs(job.work_dir, exist_ok=True)
        result = await client.download_media(source, file_name=raw)
        raw_path = result if isinstance(result, str) and os.path.isfile(result) else raw
        if not os.path.isfile(raw_path):
            return None, None
        for quality in (5, 8, 12, 16, 20, 25):
            cmd = ["ffmpeg","-y","-i",raw_path,"-vf","scale=320:320:force_original_aspect_ratio=decrease","-frames:v","1","-q:v",str(quality),final]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await proc.communicate()
            if proc.returncode == 0 and os.path.isfile(final) and os.path.getsize(final) <= 200 * 1024:
                if raw_path != final:
                    try: os.remove(raw_path)
                    except OSError: pass
                return final, final
        return (final, final) if os.path.isfile(final) else (None, None)
    except Exception:
        return None, None

async def resolve_thumbnail(client, job, media_path: str, duration: float = 0):
    """Return (thumbnail, temporary_path).

    none   -> no thumbnail
    custom -> saved Telegram photo file_id
    auto   -> source Telegram thumbnail, otherwise a generated video frame,
              otherwise a local image file when the output itself is an image
    """
    mode = await db.get_thumbnail_mode(job.user_id)

    if mode == "none":
        return None, None

    if mode == "custom":
        return await _normalize_thumbnail(client, job, await db.get_thumbnail(job.user_id), "custom")

    source = (job.extra or {}).get("source_message")
    source_thumb = _message_thumbnail_file_id(source)
    if source_thumb:
        return source_thumb, None

    lower = str(media_path or "").lower()
    image_exts = {".jpg", ".jpeg", ".png", ".webp"}
    if lower.endswith(tuple(image_exts)) and os.path.isfile(media_path):
        return media_path, None

    if duration <= 0 and os.path.isfile(media_path):
        try:
            from helper.ffmpeg import get_video_info
            duration, _width, _height = await get_video_info(media_path)
        except Exception:
            duration = 0

    if duration > 0 and os.path.isfile(media_path):
        temp = os.path.join(
            job.work_dir,
            f".auto_thumb_{job.job_id}.jpg",
        )
        generated = await take_screenshot(media_path, temp, duration)
        if generated and os.path.isfile(generated):
            normalized, temp = await _normalize_thumbnail(client, job, generated, "auto")
            try:
                if generated != normalized and os.path.isfile(generated): os.remove(generated)
            except OSError: pass
            return normalized, temp

    return None, None
