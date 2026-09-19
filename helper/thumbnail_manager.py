from __future__ import annotations

import os

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
        return await db.get_thumbnail(job.user_id), None

    source = (job.extra or {}).get("source_message")
    source_thumb = _message_thumbnail_file_id(source)
    if source_thumb:
        return source_thumb, None

    lower = str(media_path or "").lower()
    image_exts = {".jpg", ".jpeg", ".png", ".webp"}
    if lower.endswith(image_exts) and os.path.isfile(media_path):
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
            return generated, generated

    return None, None
