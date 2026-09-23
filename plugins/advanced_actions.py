from __future__ import annotations

import os
import re
import shutil
import time
import tempfile

from pyrogram import Client, StopPropagation, filters
from pyrogram.types import Message

from helper.ffmpeg import get_video_info, inspect_media_streams
from helper.job_state import jobs
from helper.job_transfer import cancel_markup, download_job
from helper.utils import AniToonTransferCancelled, clear_transfer_cancel, progress_for_pyrogram
from plugins.ui import advanced_menu
from helper.advanced_quota import advanced_quota_status, consume_advanced_use, feature_label


def _safe(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', (value or '').strip())
    return value[:220] or 'output'




async def _advanced_status(job, feature: str):
    return await advanced_quota_status(job.user_id, job.bot_id, feature)


async def _require_advanced_use(job, feature: str, message) -> bool:
    allowed, _used, _limit = await consume_advanced_use(job.user_id, job.bot_id, feature)
    if allowed:
        return True
    used, limit, plan_name = await _advanced_status(job, feature)
    label = feature_label(feature)
    text = (
        "🚫 **Daily Advanced Limit Reached**\n\n"
        f"🛠 **Option:** {label}\n"
        f"💎 **Plan:** {plan_name}\n"
        f"📊 **Used today:** `{used}/{limit}`\n\n"
        "This advanced option is available again after the daily reset.\n"
        "💎 Upgrade your plan for a higher daily Advanced limit."
    )
    try:
        await message.edit_text(text, reply_markup=advanced_menu(job.job_id))
    except Exception:
        try:
            await message.reply_text(text, reply_markup=advanced_menu(job.job_id))
        except Exception:
            pass
    return False


async def _show_advanced_limit_alert(job, feature: str, message) -> bool:
    used, limit, plan_name = await _advanced_status(job, feature)
    if used < limit:
        return True
    label = feature_label(feature)
    await message.edit_text(
        "🚫 **Daily Advanced Limit Reached**\n\n"
        f"🛠 **Option:** {label}\n"
        f"💎 **Plan:** {plan_name}\n"
        f"📊 **Used today:** `{used}/{limit}`\n\n"
        "This advanced option is available again after the daily reset.\n"
        "💎 Upgrade your plan for a higher daily Advanced limit.",
        reply_markup=advanced_menu(job.job_id),
    )
    return False

async def _job(cb):
    job = await jobs.get(cb.matches[0].group(1))
    if not job or job.user_id != cb.from_user.id:
        await cb.answer('Job expired or not owned by you.', show_alert=True)
        return None
    return job


async def _run_ffmpeg(*args):
    import asyncio
    process = await asyncio.create_subprocess_exec(
        'ffmpeg', '-y', *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(stderr.decode(errors='ignore')[-1800:] or 'FFmpeg failed')


async def _ensure_downloaded(client, job, message):
    if os.path.isfile(job.input_path) and os.path.getsize(job.input_path) > 0:
        return
    source = await client.get_messages(job.user_id, job.source_message_id)
    if not source:
        raise RuntimeError('Original file message is no longer available.')
    await download_job(client, source, job, message)


async def _send_document(client, job, path, caption):
    return await client.send_document(
        job.user_id,
        path,
        caption=caption,
        progress=progress_for_pyrogram,
        progress_args=('Uploading', None, time.time(), job.job_id),
    )


async def _send_video(client, job, path, caption):
    duration, width, height = await get_video_info(path)
    if not duration or not width or not height:
        raise RuntimeError('Output is not a valid video.')
    return await client.send_video(
        job.user_id,
        path,
        caption=caption,
        duration=max(1, int(duration)),
        width=width,
        height=height,
        supports_streaming=True,
        progress=progress_for_pyrogram,
        progress_args=('Uploading', None, time.time(), job.job_id),
    )


async def _cleanup_job(client, job, keep_source=False):
    clear_transfer_cancel(job.job_id)
    if not keep_source:
        for mid in (job.source_message_id, job.extra.get('prompt_message_id')):
            if mid:
                try:
                    await client.delete_messages(job.user_id, mid)
                except Exception:
                    pass
    shutil.rmtree(job.work_dir, ignore_errors=True)
    await jobs.remove(job.job_id)


async def _partial_media_probe(client, source, total_size: int) -> str:
    """Create a small sparse probe from a few Telegram media chunks."""
    total_size = int(total_size or 0)
    if total_size <= 0:
        raise RuntimeError('Telegram did not provide a usable file size.')
    chunk_size = 1024 * 1024
    head_bytes = min(4 * chunk_size, total_size)
    tail_bytes = min(4 * chunk_size, max(0, total_size - head_bytes))
    path = tempfile.mktemp(prefix='anitoon_probe_', suffix='.media')
    fd = None
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o600)
        os.ftruncate(fd, total_size)

        async def fetch(offset_chunk: int, limit_chunks: int, target_offset: int, wanted: int):
            received = 0
            async for data in client.stream_media(source, offset=offset_chunk, limit=limit_chunks):
                if not data:
                    continue
                take = min(len(data), max(0, wanted - received))
                if take <= 0:
                    break
                os.pwrite(fd, data[:take], target_offset + received)
                received += take
                if received >= wanted:
                    break
            return received

        head_chunks = (head_bytes + chunk_size - 1) // chunk_size
        if await fetch(0, head_chunks, 0, head_bytes) < head_bytes:
            raise RuntimeError('Could not read the Telegram media header.')

        if tail_bytes > 0:
            tail_start = max(0, total_size - tail_bytes)
            tail_chunk = tail_start // chunk_size
            aligned_start = tail_chunk * chunk_size
            tail_wanted = total_size - aligned_start
            tail_chunks = (tail_wanted + chunk_size - 1) // chunk_size
            await fetch(tail_chunk, tail_chunks, aligned_start, tail_wanted)
        return path
    except Exception:
        try:
            if fd is not None:
                os.close(fd)
        except OSError:
            pass
        try:
            os.remove(path)
        except OSError:
            pass
        raise
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass

@Client.on_callback_query(filters.regex(r'^job:advinfo:([0-9a-f]+)$'), group=-4900)
async def media_info(client, cb):
    job = await _job(cb)
    if not job:
        raise StopPropagation
    await cb.answer('Reading media information...')
    if not await _require_advanced_use(job, 'media_info', cb.message):
        raise StopPropagation
    probe_path = None
    try:
        source = (job.extra or {}).get('source_message')
        if source is None:
            source = await client.get_messages(job.user_id, job.source_message_id)
        if not source:
            raise RuntimeError('Original Telegram message is no longer available.')
        media = (getattr(source, 'video', None) or getattr(source, 'document', None) or getattr(source, 'audio', None) or getattr(source, 'photo', None))
        if media is None:
            raise RuntimeError('No supported Telegram media was found in the original message.')

        filename = str(getattr(media, 'file_name', None) or job.original_name or f'file_{job.source_message_id}')
        size = int(getattr(media, 'file_size', 0) or (job.extra or {}).get('telegram_file_size', 0) or 0)
        duration = int(getattr(media, 'duration', 0) or 0)
        width = int(getattr(media, 'width', 0) or 0)
        height = int(getattr(media, 'height', 0) or 0)

        # Sample only a few MiB. A single stream is used to avoid the
        # AUTH_BYTES_INVALID problem caused by concurrent media sessions.
        probe_path = await _partial_media_probe(client, source, size)
        streams = await inspect_media_streams(probe_path)
        audio = [item for item in streams if item['type'] == 'audio']
        subtitles = [item for item in streams if item['type'] == 'subtitle']

        media_type = '🎬 Video' if getattr(source, 'video', None) else '🎵 Audio' if getattr(source, 'audio', None) else '🖼 Photo' if getattr(source, 'photo', None) else '📄 Document'
        lines = [
            'ℹ️ **Media Information**',
            '',
            f'📂 **Name:** `{filename}`',
            f'📦 **Size:** `{humanbytes(size)}`',
            f'🎞 **Type:** `{media_type}`',
        ]
        if width and height:
            lines.append(f'📐 **Resolution:** `{width} × {height}`')
        if duration:
            lines.append(f'⏱ **Duration:** `{duration // 60:02d}:{duration % 60:02d}`')

        lines.extend(['', f'🎵 **Audio Tracks:** `{len(audio)}`'])
        for index, item in enumerate(audio, 1):
            codec = str(item.get('codec') or 'unknown')
            language = str(item.get('language') or 'und')
            title = str(item.get('title') or '').strip()
            extra = f' — {title}' if title else ''
            lines.append(f'  🎵 A{index}: `{codec}` `{language}`{extra}')

        lines.extend(['', f'💬 **Subtitle Tracks:** `{len(subtitles)}`'])
        for index, item in enumerate(subtitles, 1):
            codec = str(item.get('codec') or 'unknown')
            language = str(item.get('language') or 'und')
            title = str(item.get('title') or '').strip()
            extra = f' — {title}' if title else ''
            lines.append(f'  💬 S{index}: `{codec}` `{language}`{extra}')

        lines.extend(['', '⚡ **Only a small part of the file was sampled; the complete file was not downloaded or uploaded.**'])
        await cb.message.edit_text('\n'.join(lines), reply_markup=advanced_menu(job.job_id))
    except Exception as exc:
        await cb.message.edit_text(f'❌ **Media Info failed**\n\n`{str(exc)[:1500]}`', reply_markup=advanced_menu(job.job_id))
    finally:
        if probe_path:
            try:
                os.remove(probe_path)
            except OSError:
                pass
    raise StopPropagation
@Client.on_callback_query(filters.regex(r'^job:extractaudio:([0-9a-f]+)$'), group=-4900)
async def extract_audio(client, cb):
    job = await _job(cb)
    if not job:
        raise StopPropagation
    await cb.answer('Extracting audio...')
    if not await _require_advanced_use(job, 'extract_audio', cb.message):
        raise StopPropagation
    try:
        await _ensure_downloaded(client, job, cb.message)
        streams = [x for x in await inspect_media_streams(job.input_path) if x['type'] == 'audio']
        if not streams:
            await cb.message.edit_text('❌ No audio tracks found.', reply_markup=advanced_menu(job.job_id))
            raise StopPropagation
        for n, stream in enumerate(streams, 1):
            out = os.path.join(job.work_dir, f'audio_{n}.m4a')
            title = _safe(stream['title'] or stream['language'] or f'Audio {n}')
            await _run_ffmpeg(
                '-i', job.input_path,
                '-map', f'0:{stream["index"]}',
                '-vn',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-metadata', f'title={title}',
                out,
            )
            await client.send_audio(
                job.user_id,
                out,
                title=title,
                performer='AniToon',
                caption=f'🎵 **Extracted Audio {n}**\n`{title}`',
                progress=progress_for_pyrogram,
                progress_args=('Uploading', None, time.time(), job.job_id),
            )
        await cb.message.edit_text('✅ **All audio tracks extracted successfully.**', reply_markup=advanced_menu(job.job_id))
    except AniToonTransferCancelled:
        await cb.message.edit_text('❌ **Extraction cancelled.**', reply_markup=advanced_menu(job.job_id))
    except Exception as exc:
        await cb.message.edit_text(f'❌ **Audio extraction failed**\n\n`{str(exc)[:1500]}`', reply_markup=advanced_menu(job.job_id))
    raise StopPropagation


@Client.on_callback_query(filters.regex(r'^job:extractsubtitle:([0-9a-f]+)$'), group=-4900)
async def extract_subtitles(client, cb):
    job = await _job(cb)
    if not job:
        raise StopPropagation
    await cb.answer('Extracting subtitles...')
    if not await _require_advanced_use(job, 'extract_subtitle', cb.message):
        raise StopPropagation
    try:
        await _ensure_downloaded(client, job, cb.message)
        streams = [x for x in await inspect_media_streams(job.input_path) if x['type'] == 'subtitle']
        if not streams:
            await cb.message.edit_text('❌ No subtitle tracks found.', reply_markup=advanced_menu(job.job_id))
            raise StopPropagation
        sent = 0
        for n, stream in enumerate(streams, 1):
            codec = (stream['codec'] or '').lower()
            text_codecs = {'subrip', 'ass', 'ssa', 'webvtt', 'mov_text', 'text'}
            if codec not in text_codecs:
                continue
            out = os.path.join(job.work_dir, f'subtitle_{n}.srt')
            title = _safe(stream['title'] or stream['language'] or f'Subtitle {n}')
            await _run_ffmpeg(
                '-i', job.input_path,
                '-map', f'0:{stream["index"]}',
                '-c:s', 'srt',
                out,
            )
            await _send_document(client, job, out, f'💬 **Extracted Subtitle {n}**\n`{title}`')
            sent += 1
        if not sent:
            raise RuntimeError('Only bitmap/image subtitles were found. Those cannot be converted to SRT automatically.')
        await cb.message.edit_text('✅ **All text subtitle tracks extracted successfully.**', reply_markup=advanced_menu(job.job_id))
    except AniToonTransferCancelled:
        await cb.message.edit_text('❌ **Subtitle extraction cancelled.**', reply_markup=advanced_menu(job.job_id))
    except Exception as exc:
        await cb.message.edit_text(f'❌ **Subtitle extraction failed**\n\n`{str(exc)[:1500]}`', reply_markup=advanced_menu(job.job_id))
    raise StopPropagation


@Client.on_callback_query(filters.regex(r'^job:addaudio:([0-9a-f]+)$'), group=-4900)
async def ask_audio(client, cb):
    job = await _job(cb)
    if not job:
        raise StopPropagation
    await cb.answer()
    if not await _show_advanced_limit_alert(job, 'add_audio', cb.message):
        raise StopPropagation
    await jobs.update(job.job_id, selected_action='advanced_add_audio')
    await cb.message.edit_text('➕ **Add Audio**\n\nSend the audio file now.', reply_markup=cancel_markup(job.job_id))
    raise StopPropagation


@Client.on_callback_query(filters.regex(r'^job:addsubtitle:([0-9a-f]+)$'), group=-4900)
async def ask_subtitle(client, cb):
    job = await _job(cb)
    if not job:
        raise StopPropagation
    await cb.answer()
    if not await _show_advanced_limit_alert(job, 'add_subtitle', cb.message):
        raise StopPropagation
    await jobs.update(job.job_id, selected_action='advanced_add_subtitle')
    await cb.message.edit_text('➕ **Add Subtitle**\n\nSend the subtitle file now.', reply_markup=cancel_markup(job.job_id))
    raise StopPropagation


@Client.on_message(filters.private & (filters.document | filters.audio), group=-4900)
async def receive_added_track(client, message: Message):
    job = await jobs.get_user_job(message.from_user.id)
    if not job or job.selected_action not in {'advanced_add_audio', 'advanced_add_subtitle'}:
        return
    media = message.document or message.audio
    if not media:
        return
    try:
        await _ensure_downloaded(client, job, message)
        feature = 'add_audio' if job.selected_action == 'advanced_add_audio' else 'add_subtitle'
        if not await _require_advanced_use(job, feature, message):
            raise StopPropagation
        added = await client.download_media(message, file_name=os.path.join(job.work_dir, 'added_track'))
        if not added or not os.path.isfile(added):
            raise RuntimeError('Could not download the additional track.')
        out = os.path.join(job.work_dir, 'advanced_added.mkv')
        if job.selected_action == 'advanced_add_audio':
            await _run_ffmpeg(
                '-i', job.input_path,
                '-i', added,
                '-map', '0',
                '-map', '1:a:0',
                '-c', 'copy',
                '-metadata:s:a:999', 'title=Added Audio',
                out,
            )
        else:
            await _run_ffmpeg(
                '-i', job.input_path,
                '-i', added,
                '-map', '0',
                '-map', '1:s:0',
                '-c', 'copy',
                '-metadata:s:s:999', 'title=Added Subtitle',
                out,
            )
        base = _safe(os.path.splitext(job.original_name)[0])
        final = os.path.join(job.work_dir, f'{base}_advanced.mkv')
        os.replace(out, final)
        await _send_document(client, job, final, '🛠 **Advanced processing complete.**')
        await _cleanup_job(client, job)
        try:
            await client.delete_messages(message.chat.id, message.id)
        except Exception:
            pass
    except AniToonTransferCancelled:
        await message.reply_text('❌ **Advanced operation cancelled.**')
        await _cleanup_job(client, job, keep_source=True)
    except Exception as exc:
        await message.reply_text(f'❌ **Advanced operation failed**\n\n`{str(exc)[:1500]}`')
    raise StopPropagation


@Client.on_callback_query(filters.regex(r'^job:trim:([0-9a-f]+)$'), group=-4900)
async def ask_trim(client, cb):
    job = await _job(cb)
    if not job:
        raise StopPropagation
    await cb.answer()
    await jobs.update(job.job_id, selected_action='advanced_trim')
    await cb.message.edit_text(
        '✂️ **Trim Video**\n\nSend `start | end` in seconds. Example: `10 | 120`',
        reply_markup=cancel_markup(job.job_id),
    )
    raise StopPropagation


@Client.on_message(filters.private & filters.text, group=-4900)
async def trim_input(client, message: Message):
    job = await jobs.get_user_job(message.from_user.id)
    if not job or job.selected_action != 'advanced_trim':
        return
    try:
        start_s, end_s = [float(x.strip()) for x in (message.text or '').split('|', 1)]
        if start_s < 0 or end_s <= start_s:
            raise ValueError('End time must be greater than start time.')
        await _ensure_downloaded(client, job, message)
        if not await _require_advanced_use(job, 'trim', message):
            raise StopPropagation
        base = _safe(os.path.splitext(job.original_name)[0])
        out = os.path.join(job.work_dir, f'{base}_trimmed.mp4')
        await _run_ffmpeg(
            '-ss', str(start_s),
            '-to', str(end_s),
            '-i', job.input_path,
            '-map', '0:v:0',
            '-map', '0:a?',
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-crf', '23',
            '-c:a', 'aac',
            '-movflags', '+faststart',
            '-pix_fmt', 'yuv420p',
            out,
        )
        await _send_video(client, job, out, '✂️ **Trimmed video**')
        await _cleanup_job(client, job)
        try:
            await client.delete_messages(message.chat.id, message.id)
        except Exception:
            pass
    except AniToonTransferCancelled:
        await message.reply_text('❌ **Trim cancelled.**')
        await _cleanup_job(client, job, keep_source=True)
    except Exception as exc:
        await message.reply_text(f'❌ **Trim failed**\n\n`{str(exc)[:1500]}`')
    raise StopPropagation
