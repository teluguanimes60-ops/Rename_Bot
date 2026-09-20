from __future__ import annotations

import asyncio
import os
import shutil
import struct
import time

from pyrogram import Client
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from helper.cancel_manager import register_task, unregister_task
from helper.job_state import Job, jobs
from helper.message_cleanup import protect_transfer_message
from helper.utils import AniToonTransferCancelled, humanbytes, progress_for_pyrogram, reset_progress, request_transfer_resume, set_transfer_runtime


def cancel_markup(job_id: str):
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"transfer:cancel:{job_id}")]])


async def _show_processing(status: Message | None):
    if status is not None:
        await protect_transfer_message(status)


async def _delete_rename_source(client: Client, job: Job) -> None:
    if getattr(job, "selected_action", None) not in {"rename_output_choice", "rename_format", "custom_name", "convert_name"}:
        return
    message_id = getattr(job, "source_message_id", None)
    if not message_id:
        return
    try:
        await client.delete_messages(job.user_id, int(message_id))
    except Exception:
        pass


def _needs_faststart(path: str) -> bool:
    """Return True when MP4 has mdat before moov and therefore needs fast-start remux."""
    if not path.lower().endswith(".mp4"):
        return False
    try:
        with open(path, "rb") as stream:
            offset = 0
            saw_mdat = False
            file_size = os.path.getsize(path)
            for _ in range(256):
                stream.seek(offset)
                header = stream.read(8)
                if len(header) < 8:
                    return False
                size, atom = struct.unpack(">I4s", header)
                header_size = 8
                if size == 1:
                    extended = stream.read(8)
                    if len(extended) < 8:
                        return False
                    size = struct.unpack(">Q", extended)[0]
                    header_size = 16
                elif size == 0:
                    return False
                if size < header_size or offset + size > file_size:
                    return False
                atom = atom.decode("latin1")
                if atom == "mdat":
                    saw_mdat = True
                elif atom == "moov":
                    return saw_mdat
                offset += size
                if offset >= file_size:
                    return False
    except (OSError, ValueError, struct.error):
        return False
    return False


async def download_job(client: Client, message: Message, job: Job, status: Message) -> int:
    if os.path.isfile(job.input_path) and os.path.getsize(job.input_path) > 0:
        actual = os.path.getsize(job.input_path)
        await jobs.update(job.job_id, extra={**job.extra, "downloaded_size": actual})
        await _delete_rename_source(client, job)
        await protect_transfer_message(status)
        return actual

    expected_size = int(job.extra.get("telegram_file_size", 0) or 0)
    source = job.extra.get("source_message") or job.extra.get("file_id") or message
    os.makedirs(job.work_dir, exist_ok=True)

    media = (
        getattr(source, "video", None)
        or getattr(source, "document", None)
        or getattr(source, "audio", None)
    )
    duration = getattr(media, "duration", None) if media is not None else None
    if duration:
        set_transfer_runtime(job.job_id, duration)

    request_transfer_resume(job.job_id)
    task = await register_task(job.job_id)
    acquired = False
    try:
        from helper.utils import is_transfer_cancelled
        if is_transfer_cancelled(job.job_id):
            raise AniToonTransferCancelled("Transfer cancelled by user")
        await jobs.acquire()
        acquired = True
        reset_progress(job.job_id)
        started = time.time()
        if expected_size:
            await progress_for_pyrogram(0, expected_size, "Downloading", status, started, job.job_id)
        result = await client.download_media(
            message=source,
            file_name=job.input_path,
            progress=progress_for_pyrogram,
            progress_args=("Downloading", status, started, job.job_id),
        )
        if is_transfer_cancelled(job.job_id):
            raise AniToonTransferCancelled("Transfer cancelled by user")
        path = result if isinstance(result, str) and os.path.isfile(result) else job.input_path
        if path != job.input_path and os.path.isfile(path):
            os.replace(path, job.input_path)
        if not os.path.isfile(job.input_path):
            raise RuntimeError("Telegram download completed but the local file was not found")
        actual = os.path.getsize(job.input_path)
        if expected_size and actual != expected_size:
            raise RuntimeError(f"Incomplete download: expected {humanbytes(expected_size)}, got {humanbytes(actual)}")
        await jobs.update(job.job_id, extra={**job.extra, "downloaded_size": actual})
        await progress_for_pyrogram(actual, expected_size or actual, "Downloading", status, started, job.job_id)
        await _delete_rename_source(client, job)
        await protect_transfer_message(status)
        return actual
    except AniToonTransferCancelled:
        try:
            await status.edit_text("❌ **Processing cancelled.**")
        except Exception:
            pass
        raise
    except asyncio.CancelledError:
        await jobs.remove(job.job_id)
        shutil.rmtree(job.work_dir, ignore_errors=True)
        raise
    except FloodWait:
        raise
    finally:
        await unregister_task(job.job_id, task)
        if acquired:
            jobs.release()


async def _send_with_floodwait_retry(send_callable, *args, **kwargs):
    """Send a Telegram media message, retrying FloodWait safely."""
    for attempt in range(3):
        try:
            return await send_callable(*args, **kwargs)
        except FloodWait as exc:
            wait_time = max(1, int(getattr(exc, "value", 1) or 1))
            if attempt >= 2:
                raise
            await asyncio.sleep(wait_time)
    raise RuntimeError("Telegram send retry loop ended unexpectedly")

async def _output_caption_for_job(job: Job, filename: str, size: int, duration: float = 0) -> str:
    default = f"✅ **AniToon Processed**\n\n📂 `{filename}`\n📦 `{humanbytes(size)}`"
    try:
        from helper.database import db
        saved = await db.get_caption(job.user_id)
    except Exception:
        saved = None
    if not saved:
        return default
    return str(saved).replace("{filename}", filename).replace("{filesize}", humanbytes(size)).replace("{duration}", str(int(duration)))

async def upload_job(client: Client, job: Job, path: str, filename: str, status: Message | None = None, *, as_video: bool = False, prepared_video: bool = False):
    """Upload a file. When as_video=True, send a real streamable Telegram video."""
    if not os.path.isfile(path) or os.path.getsize(path) <= 0:
        raise RuntimeError("Upload source is missing or empty")
    acquired = False
    task = await register_task(job.job_id)
    upload_path = path
    temporary_streamable = None
    temporary_thumbnail = None
    try:
        await jobs.acquire()
        acquired = True
        reset_progress(job.job_id)
        started = time.time()

        from helper.utils import is_transfer_cancelled
        if is_transfer_cancelled(job.job_id):
            raise AniToonTransferCancelled("Transfer cancelled by user")

        # Show the upload stage immediately, before Pyrogram starts reading
        # the local file. This makes video uploads behave like document
        # uploads instead of appearing frozen between processing and upload.
        try:
            initial_size = os.path.getsize(path)
            await progress_for_pyrogram(
                0,
                initial_size,
                "Uploading",
                status,
                started,
                job.job_id,
            )
        except Exception:
            pass

        # Do not remux, re-encode, resize, or otherwise alter the uploaded
        # video during a normal rename/upload. The original media path is
        # uploaded as-is so codec, resolution, bitrate and file size remain
        # unchanged. Explicit Convert/Trim/metadata operations may create a
        # new output before this stage.

        size = os.path.getsize(upload_path)
        caption = await _output_caption_for_job(job, filename, size)
        kwargs = {
            "progress": progress_for_pyrogram,
            "progress_args": ("Uploading", status, started, job.job_id),
            "caption": caption,
        }
        if as_video:
            from helper.ffmpeg import get_video_info
            duration, width, height = await get_video_info(upload_path)
            if duration <= 0 or width <= 0 or height <= 0:
                raise RuntimeError("Video metadata could not be read before upload")
            set_transfer_runtime(job.job_id, duration)
            kwargs.update({
                "caption": await _output_caption_for_job(job, filename, size, duration),
                "duration": max(1, int(round(duration))),
                "width": int(width),
                "height": int(height),
                "supports_streaming": True,
            })
            thumb = None
            temporary_thumbnail = None
            try:
                from helper.thumbnail_manager import resolve_thumbnail
                thumb, temporary_thumbnail = await resolve_thumbnail(
                    client,
                    job,
                    upload_path,
                    duration,
                )
            except Exception:
                thumb, temporary_thumbnail = None, None
            if thumb:
                kwargs["thumb"] = thumb
            try:
                # send_video creates Telegram's native video message. With
                # supports_streaming=True + fast-start MP4, Telegram clients
                # can begin playback while the recipient is downloading it.
                return await _send_with_floodwait_retry(
                    client.send_video,
                    job.user_id,
                    upload_path,
                    **kwargs,
                )
            except Exception as first_exc:
                # Retry without a custom thumbnail if Telegram rejects it.
                if thumb and "thumb" in str(first_exc).lower():
                    kwargs.pop("thumb", None)
                    try:
                        return await _send_with_floodwait_retry(
                            client.send_video,
                            job.user_id,
                            upload_path,
                            **kwargs,
                        )
                    except Exception as second_exc:
                        first_exc = second_exc

                # If native video upload is rejected, send the same file as a
                # document so the completed processing job is not lost.
                fallback_caption = await _output_caption_for_job(job, filename, size, duration)
                fallback_kwargs = {
                    "caption": (
                        fallback_caption
                        + "\n\n"
                        + "ℹ️ Telegram did not accept this file as a native video, so it was uploaded as a document."
                    ),
                    "progress": progress_for_pyrogram,
                    "progress_args": (
                        "Uploading",
                        status,
                        started,
                        job.job_id,
                    ),
                }
                try:
                    return await _send_with_floodwait_retry(
                        client.send_document,
                        job.user_id,
                        upload_path,
                        **fallback_kwargs,
                    )
                except Exception as fallback_exc:
                    raise RuntimeError(
                        f"Telegram video upload failed: {first_exc}; "
                        f"document fallback failed: {fallback_exc}"
                    ) from fallback_exc


        ext = os.path.splitext(filename)[1].lower()
        mime = (job.mime_type or "").lower()
        thumb = None
        temporary_thumbnail = None
        try:
            from helper.thumbnail_manager import resolve_thumbnail
            thumb, temporary_thumbnail = await resolve_thumbnail(
                client,
                job,
                upload_path,
                0,
            )
        except Exception:
            thumb, temporary_thumbnail = None, None
        if thumb:
            kwargs["thumb"] = thumb
        if mime.startswith("audio/") or ext in {".mp3", ".m4a", ".aac", ".flac", ".ogg", ".wav", ".opus"}:
            try:
                return await _send_with_floodwait_retry(
                    client.send_audio,
                    job.user_id,
                    upload_path,
                    **kwargs,
                )
            except Exception:
                if "thumb" not in kwargs:
                    raise
                kwargs.pop("thumb", None)
                return await _send_with_floodwait_retry(
                    client.send_audio,
                    job.user_id,
                    upload_path,
                    **kwargs,
                )
        try:
            return await _send_with_floodwait_retry(
                client.send_document,
                job.user_id,
                upload_path,
                **kwargs,
            )
        except Exception:
            if "thumb" not in kwargs:
                raise
            kwargs.pop("thumb", None)
            return await _send_with_floodwait_retry(
                client.send_document,
                job.user_id,
                upload_path,
                **kwargs,
            )
    finally:
        for _temp in (temporary_thumbnail, temporary_streamable):
            if _temp and _temp != path:
                try:
                    os.remove(_temp)
                except OSError:
                    pass
        await unregister_task(job.job_id, task)
        if acquired:
            jobs.release()


async def cancel_job(job_id: str, user_id: int, status: Message | None = None) -> bool:
    job = await jobs.get(job_id)
    if not job or job.user_id != user_id:
        return False
    from helper.utils import request_transfer_cancel
    request_transfer_cancel(job_id)
    if status:
        try:
            await status.edit_text("❌ **Cancelling processing...**")
        except Exception:
            pass
    return True
