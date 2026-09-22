from __future__ import annotations

import asyncio
import os
import shutil
import time

from pyrogram import Client, StopPropagation, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from helper.activity_log import log_rename_request, mark_rename_completed
from helper.cancel_manager import register_task, unregister_task
from helper.database import db
from helper.ffmpeg import convert_media, inspect_media_streams
from helper.job_state import jobs
from helper.job_transfer import download_job, send_completion_notice
from helper.message_cleanup import protect_result, protect_transfer_message
from helper.utils import AniToonTransferCancelled, clear_transfer_cancel, humanbytes, progress_for_pyrogram, reset_progress
from plugins.file_action_fix import _deliver_output
from plugins.rename import _base_without_extension, _extension, _safe_filename
NAME_ACTIONS = {"custom_name", "convert_name"}


async def _find_name_job(user_id: int, message=None):
    jobs_for_user = await jobs.get_user_jobs(user_id)
    reply_id = getattr(getattr(message, "reply_to_message", None), "id", None) if message else None
    if reply_id:
        for job in jobs_for_user:
            if getattr(job, "selected_action", None) in NAME_ACTIONS and not job.extra.get("name_submitted"):
                if int((job.extra or {}).get("rename_prompt_message_id", 0) or 0) == int(reply_id):
                    return job
    for job in jobs_for_user:
        if getattr(job, "selected_action", None) in NAME_ACTIONS and not job.extra.get("name_submitted"):
            return job
    return None


async def _download_source(client, message, job, status):
    source = (job.extra or {}).get("source_message") or (job.extra or {}).get("file_id")
    if not source:
        chat_id = getattr(getattr(message, "chat", None), "id", None) or int(job.user_id)
        source = await client.get_messages(chat_id, job.source_message_id)
    if not source:
        raise RuntimeError("Original file could not be located")
    return await download_job(client, source, job, status)


def _initial_download_text(expected_size: int) -> str:
    total = max(0, int(expected_size or 0))
    return "📥 **Download Progress**\n" + "░" * 24 + " 0.00%\n\n" + f"📦 Size: `0 B` / `{humanbytes(total)}`\n🚀 Speed: `0 B/s`\n⏱ ETA: calculating..."


async def _log_rename_activity(job, new_name: str):
    source = (job.extra or {}).get("source_message")
    user = getattr(source, "from_user", None)
    user_name = (
        str(getattr(user, "first_name", "") or "").strip()
        or str(getattr(user, "last_name", "") or "").strip()
        or "Unknown"
    )
    first = str(getattr(user, "first_name", "") or "").strip()
    last = str(getattr(user, "last_name", "") or "").strip()
    if first and last:
        user_name = f"{first} {last}"
    username = getattr(user, "username", None)
    output_format = _extension(new_name)
    await log_rename_request(
        bot_id=int(job.bot_id),
        job_id=job.job_id,
        user_id=int(job.user_id),
        user_name=user_name,
        username=username,
        original_name=job.original_name,
        new_name=new_name,
        file_size=int((job.extra or {}).get("telegram_file_size", 0) or 0),
        output_format=output_format,
    )


async def _delete_message_safely(client, chat_id, message_id):
    if message_id:
        try: await client.delete_messages(chat_id, int(message_id))
        except Exception: pass


async def _new_transfer_status(client, message, job, expected_size):
    text = _initial_download_text(expected_size)
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("⏸️ Pause", callback_data=f"transfer:pause:{job.job_id}"), InlineKeyboardButton("❌ Cancel", callback_data=f"transfer:cancel:{job.job_id}")]])
    chat = getattr(message, "chat", None)
    if chat is not None and getattr(chat, "id", None):
        status = await message.reply_text(text, reply_markup=markup)
    else:
        status = await client.send_message(job.user_id, text, reply_markup=markup)
    await protect_transfer_message(status)
    reset_progress(job.job_id)
    return status


async def _conversion_progress(current: float, total: float, status, job_id: str, label: str):
    if not total or status is None: return
    percent = max(0.0, min(99.9, (float(current) * 100.0) / float(total)))
    try:
        filled = max(0, min(24, int(percent / 100 * 24)))
        await status.edit_text("⚙️ **Processing**\n" + "█" * filled + "░" * (24 - filled) + f" {percent:.1f}%\n\n📂 `{label}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"transfer:cancel:{job_id}")]]))
    except Exception: pass


async def _convert_with_progress(job, status, output_path, output_format, label):
    async def report(current, total): await _conversion_progress(current, total, status, job.job_id, label)
    task = await register_task(job.job_id)
    try: return await convert_media(job.input_path, output_path, output_format, report)
    finally: await unregister_task(job.job_id, task)


async def _finish_delivery(client, message, job, status):
    await protect_result(status)
    chat_id = getattr(getattr(message, "chat", None), "id", None) or int(job.user_id)
    await _delete_message_safely(client, chat_id, (job.extra or {}).get("rename_prompt_message_id"))
    status_chat_id = getattr(getattr(status, "chat", None), "id", None) or int(job.user_id)
    await _delete_message_safely(client, status_chat_id, status.id)




async def run_name_job_serialized(client, message, job, processor):
    """Run a rename job only after all earlier rename jobs for this user finish."""
    queue_position = await jobs.user_queue_position(job.job_id)
    queue_message = None
    if queue_position > 0:
        queue_message = await message.reply_text(
            f"⏳ **Added to queue — position #{queue_position}**\n\n"
            "The previous file is still processing. This file will start automatically when its turn arrives."
        )

    user_lock = await jobs.user_lock(message.from_user.id)
    async with user_lock:
        current = await jobs.get(job.job_id)
        if not current:
            return None

        if queue_message:
            try:
                await queue_message.edit_text("▶️ **Your file is now starting...**")
            except Exception:
                pass

        task = await register_task(current.job_id)
        try:
            return await processor(current)
        finally:
            await unregister_task(current.job_id, task)


async def process_custom_name_job(client, message, job, name: str):
    """Process a rename job without changing the source video media data."""
    await jobs.update(job.job_id, extra={**job.extra, "processing": True, "state": "processing"})
    source_ext = _extension(job.original_name)
    video_mode = (job.extra or {}).get("rename_output_mode") == "video"

    safe_name = _safe_filename(name)
    if video_mode:
        # Normal rename never re-encodes or remuxes the source.
        safe_name = (
            f"{_base_without_extension(safe_name)}.{source_ext}"
            if source_ext
            else safe_name
        )
    else:
        if not _extension(safe_name) and source_ext:
            safe_name = f"{safe_name}.{source_ext}"
        elif _extension(safe_name) and source_ext:
            safe_name = f"{_base_without_extension(safe_name)}.{source_ext}"

    status = await _new_transfer_status(
        client,
        message,
        job,
        int((job.extra or {}).get("telegram_file_size", 0) or 0),
    )
    try:
        # _new_transfer_status already shows the download stage at 0%.
        # Start the activity write in parallel so MongoDB latency is hidden
        # behind the Telegram download.
        async def _log_activity_safely():
            try:
                await _log_rename_activity(job, safe_name)
            except Exception:
                # Activity logging must never block or break the file transfer.
                pass

        activity_task = asyncio.create_task(_log_activity_safely())
        await _download_source(client, message, job, status)

        output_path = os.path.join(job.work_dir, safe_name)
        os.replace(job.input_path, output_path)

        # MP4 is sent as a native Telegram video; other containers remain
        # untouched and are uploaded using Telegram's document message.
        results = await _deliver_output(
            client,
            job,
            output_path,
            safe_name,
            status,
        )

        if not results:
            raise RuntimeError("Telegram returned no uploaded result")

        # Logging is best-effort and deliberately happens after upload so
        # MongoDB latency can never make the transfer appear stuck at 100%.
        try:
            await activity_task
        except Exception:
            pass

        size = int(
            (job.extra or {}).get("downloaded_size", 0)
            or os.path.getsize(output_path)
        )
        await db.update_usage(job.user_id, job.bot_id, size)
        await mark_rename_completed(job.job_id)
        await send_completion_notice(client, job.user_id, results=results, parts=len(results))
        await _finish_delivery(client, message, job, status)
        return results
    except AniToonTransferCancelled:
        try:
            await status.edit_text("❌ **Processing cancelled.**")
        except Exception:
            pass
    except asyncio.CancelledError:
        try:
            await status.edit_text("❌ **Processing cancelled.**")
        except Exception:
            pass
        raise
    except Exception as exc:
        try:
            await status.edit_text(f"❌ **Rename failed**\n\n`{str(exc)[:1000]}`")
        except Exception:
            pass
    finally:
        clear_transfer_cancel(job.job_id)
        shutil.rmtree(job.work_dir, ignore_errors=True)
        await jobs.remove(job.job_id)

async def _process_named_job(client, message, job):
    action = job.selected_action
    text = message.text.strip()

    if action == "convert_name":
        ext = job.output_ext
        if not ext: raise RuntimeError("Output format is missing")
        name = _safe_filename(text)
        if _extension(name) != ext: name = f"{_base_without_extension(name)}.{ext}"
        status = await _new_transfer_status(client, message, job, int((job.extra or {}).get("telegram_file_size", 0) or 0))
        try:
            await _log_rename_activity(job, name)
            await _download_source(client, message, job, status)
            output_path = os.path.join(job.work_dir, name)
            if not await _convert_with_progress(job, status, output_path, ext, name): raise RuntimeError("FFmpeg conversion failed")
            results = await _deliver_output(client, job, output_path, name, status)
            if not results: raise RuntimeError("Telegram returned no uploaded result")
            size = int((job.extra or {}).get("downloaded_size", 0) or os.path.getsize(job.input_path))
            await db.update_usage(job.user_id, job.bot_id, size)
            await mark_rename_completed(job.job_id)
            await send_completion_notice(client, job.user_id, parts=len(results))
            await _finish_delivery(client, message, job, status)
        except AniToonTransferCancelled:
            try: await status.edit_text("❌ **Processing cancelled.**")
            except Exception: pass
        except asyncio.CancelledError:
            try: await status.edit_text("❌ **Processing cancelled.**")
            except Exception: pass
        except Exception as exc:
            try: await status.edit_text(f"❌ **Conversion failed**\n\n`{str(exc)[:1000]}`")
            except Exception: pass
        finally:
            clear_transfer_cancel(job.job_id); shutil.rmtree(job.work_dir, ignore_errors=True); await jobs.remove(job.job_id)
        return

    if action == "custom_name":
        source_ext = _extension(job.original_name)
        video_mode = (job.extra or {}).get("rename_output_mode") == "video"
        name = _safe_filename(text)
        if video_mode:
            if source_ext:
                name = f"{_base_without_extension(name)}.{source_ext}"
        else:
            if not _extension(name) and source_ext:
                name = f"{name}.{source_ext}"
            elif _extension(name) and source_ext:
                name = f"{_base_without_extension(name)}.{source_ext}"

        await process_custom_name_job(client, message, job, name)


@Client.on_message(filters.private & filters.text, group=-1200)
async def reliable_rename_reply(client, message):
    if not message.text or message.text.startswith("/"): return
    job = await _find_name_job(message.from_user.id, message)
    if not job: return
    text = message.text.strip()
    if not text:
        await _delete_message_safely(client, message.chat.id, message.id); raise StopPropagation
    await jobs.update(job.job_id, extra={**job.extra, "name_submitted": True, "submitted_name": text, "state": "queued"})
    await run_name_job_serialized(
        client,
        message,
        job,
        lambda current: _process_named_job(client, message, current),
    )
    raise StopPropagation
