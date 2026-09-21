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
    """Return a Telegram-safe JPEG thumbnail and its temporary path."""
    if not source:
        return None, None

    os.makedirs(job.work_dir, exist_ok=True)
    raw = os.path.join(job.work_dir, f".thumb_raw_{tag}")
    final = os.path.join(job.work_dir, f".thumb_{tag}.jpg")

    try:
        if local:
            shutil.copy2(source, raw)
            raw_path = raw
        else:
            result = await client.download_media(source, file_name=raw)
            raw_path = result if isinstance(result, str) and os.path.isfile(result) else raw

        if not os.path.isfile(raw_path):
            return None, None

        # Telegram thumbnail limits are small, but keep the best possible
        # dimensions/quality before falling back to smaller encodings.
        for size in (320, 300, 280, 256, 224, 192, 160):
            for quality in (2, 4, 6, 8, 10, 14, 18, 24, 30):
                cmd = [
                    "ffmpeg", "-y",
                    "-i", raw_path,
                    "-vf",
                    f"scale={size}:{size}:force_original_aspect_ratio=decrease",
                    "-frames:v", "1",
                    "-q:v", str(quality),
                    final,
                ]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.communicate()

                if (
                    proc.returncode == 0
                    and os.path.isfile(final)
                    and 0 < os.path.getsize(final) <= 190 * 1024
                ):
                    if raw_path != final:
                        try:
                            os.remove(raw_path)
                        except OSError:
                            pass
                    return final, final

        if raw_path != final:
            try:
                os.remove(raw_path)
            except OSError:
                pass
        return None, None
    except Exception:
        try:
            if os.path.isfile(raw):
                os.remove(raw)
        except OSError:
            pass
        return None, None


async def _video_frame_thumbnail(job, media_path: str):
    """Extract a frame from the actual processed video file."""
    if not media_path or not os.path.isfile(media_path):
        return None, None

    try:
        from helper.ffmpeg import get_video_info

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


async def resolve_thumbnail(client, job, media_path: str, duration: float = 0):
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
    auto_frame, auto_temp = await _video_frame_thumbnail(job, media_path)
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
