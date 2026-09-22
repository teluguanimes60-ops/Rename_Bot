from __future__ import annotations

import asyncio
import os
import shutil

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


async def _normalize_thumbnail(client, job, source, tag: str, *, local: bool = False):
    """Return a Telegram-safe JPEG thumbnail with minimal CPU/process overhead."""
    if not source:
        return None, None

    os.makedirs(job.work_dir, exist_ok=True)
    raw = os.path.join(job.work_dir, f".thumb_raw_{tag}")
    final = os.path.join(job.work_dir, f".thumb_{tag}.jpg")

    try:
        if local:
            shutil.copy2(source, raw)
        else:
            result = await client.download_media(source, file_name=raw)
            raw = result if isinstance(result, str) and os.path.isfile(result) else raw

        if not os.path.isfile(raw):
            return None, None

        from PIL import Image, ImageOps

        with Image.open(raw) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")

            # Telegram thumbnail dimensions are capped at 320x320. Resize once
            # with Pillow instead of launching many FFmpeg subprocesses.
            image.thumbnail((320, 320), Image.Resampling.LANCZOS)

            # Try a few quality levels; this normally succeeds in 1-2 encodes.
            encoded = None
            for quality in (88, 78, 68, 58, 48):
                image.save(
                    final,
                    format="JPEG",
                    quality=quality,
                    optimize=True,
                    progressive=True,
                )
                if 0 < os.path.getsize(final) <= 190 * 1024:
                    encoded = final
                    break

            if encoded is None:
                # Very detailed images can still exceed the size target.
                image.thumbnail((256, 256), Image.Resampling.LANCZOS)
                image.save(
                    final,
                    format="JPEG",
                    quality=55,
                    optimize=True,
                    progressive=True,
                )
                if 0 < os.path.getsize(final) <= 190 * 1024:
                    encoded = final

        if raw != final:
            try:
                os.remove(raw)
            except OSError:
                pass

        return (encoded, encoded) if encoded else (None, None)

    except Exception:
        for path in (raw, final):
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass
        return None, None


async def _video_frame_thumbnail(job, media_path: str, duration: float = 0, width: int = 0, height: int = 0):
    """Extract a frame from the actual processed video file."""
    if not media_path or not os.path.isfile(media_path):
        return None, None

    try:
        from helper.ffmpeg import get_video_info

        if duration <= 0 or width <= 0 or height <= 0:
            duration, width, height = await get_video_info(media_path)
        if width <= 0 or height <= 0:
            return None, None

        frame = os.path.join(job.work_dir, f".auto_thumb_{job.job_id}.jpg")
        generated = await take_screenshot(
            media_path,
            frame,
            max(float(duration or 0), 1.0),
        )
        if not generated or not os.path.isfile(generated):
            return None, None

        return generated, generated
    except Exception:
        return None, None


async def resolve_thumbnail(client, job, media_path: str, duration: float = 0, width: int = 0, height: int = 0):
    """Resolve the user's thumbnail mode for video/document uploads."""
    mode = await db.get_thumbnail_mode(job.user_id)

    if mode == "none":
        return None, None

    if mode == "custom":
        saved = await db.get_thumbnail(job.user_id)
        if not saved:
            return None, None

        normalized, temp = await _normalize_thumbnail(
            client,
            job,
            saved,
            "custom",
        )
        if normalized:
            return normalized, temp

        # Keep a saved Telegram file_id usable even if normalization temporarily
        # fails. Both send_video() and send_document() can use this directly.
        return saved, None

    # Auto Thumbnail: first extract a frame from the actual video being sent.
    # This means both "Convert into Video" and "Convert into File" receive a
    # thumbnail taken from that video's own contents.
    auto_frame, auto_temp = await _video_frame_thumbnail(job, media_path, duration, width, height)
    if auto_frame:
        normalized, temp = await _normalize_thumbnail(
            client,
            job,
            auto_frame,
            "auto",
            local=True,
        )
        if normalized:
            try:
                if auto_frame != normalized and os.path.isfile(auto_frame):
                    os.remove(auto_frame)
            except OSError:
                pass
            return normalized, temp
        return auto_frame, auto_temp

    # Non-video files cannot have a frame extracted. Use Telegram's source
    # preview thumbnail as the fallback when one exists.
    source = (job.extra or {}).get("source_message")
    source_thumb = _message_thumbnail_file_id(source)
    if source_thumb:
        normalized, temp = await _normalize_thumbnail(
            client,
            job,
            source_thumb,
            "source",
        )
        if normalized:
            return normalized, temp
        return source_thumb, None

    # An image file can itself be used as a thumbnail.
    lower = str(media_path or "").lower()
    if lower.endswith((".jpg", ".jpeg", ".png", ".webp")) and os.path.isfile(media_path):
        normalized, temp = await _normalize_thumbnail(
            client,
            job,
            media_path,
            "image",
            local=True,
        )
        return normalized, temp

    return None, None
