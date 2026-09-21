from __future__ import annotations

import os
import shutil
import time
import uuid

from pyrogram import Client, StopPropagation, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from helper.database import db
from helper.paid_preview import get_paid_preview_bytes
from helper.utils import humanbytes, progress_for_pyrogram

FREE_IMAGE_LIMIT = 20 * 1024 * 1024


def _paid_media_entries(message: Message):
    paid_media = getattr(message, "paid_media", None)
    if not paid_media:
        return []
    return list(getattr(paid_media, "extended_media", []) or [])

def _paid_photo_from_message(message: Message):
    for media in _paid_media_entries(message):
        file_id = getattr(media, "file_id", None)
        if file_id:
            return media
    return None


def _preview_thumb_from_message(message: Message):
    for media in _paid_media_entries(message):
        thumb = getattr(media, "thumb", None)
        if thumb is not None:
            return thumb

        raw_media = getattr(media, "raw", None)
        raw_thumb = getattr(raw_media, "thumb", None)
        if raw_thumb is not None:
            return raw_thumb
    return None


def _preview_bytes(value):
    seen = set()

    def walk(obj):
        if obj is None or id(obj) in seen:
            return None
        seen.add(id(obj))

        raw_bytes = getattr(obj, "bytes", None)
        if isinstance(raw_bytes, (bytes, bytearray)) and raw_bytes:
            return bytes(raw_bytes)

        for attr in ("thumb", "photo", "media", "raw"):
            child = getattr(obj, attr, None)
            result = walk(child)
            if result:
                return result
        return None

    return walk(value)


def _show_thumbnail_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👁 Show Thumbnail", callback_data="view_thumb")],
    ])


async def _save_paid_preview_thumbnail(client, message: Message):
    thumb = _preview_thumb_from_message(message)

    preview_file_id = getattr(thumb, "file_id", None) if thumb is not None else None
    if preview_file_id:
        await db.set_thumbnail(message.from_user.id, str(preview_file_id))
        await db.set_thumbnail_mode(message.from_user.id, "custom")
        return str(preview_file_id)

    preview_data = _preview_bytes(thumb) if thumb is not None else None

    # Pyrofork may expose Telegram's preview constructor without the cached
    # bytes on the high-level object. Read the same message through a
    # read-only MTProto client so PhotoCachedSize/PhotoStrippedSize previews
    # can be converted to a normal JPEG. No purchase/unlock is performed.
    if not preview_data:
        preview_data = await get_paid_preview_bytes(
            client,
            int(message.chat.id),
            int(message.id),
        )

    if not preview_data:
        return None

    work_dir = os.path.join("downloads", "owner_paid_photo", f"preview_{uuid.uuid4().hex}")
    os.makedirs(work_dir, exist_ok=True)
    preview_path = os.path.join(work_dir, "paid_preview.jpg")

    try:
        with open(preview_path, "wb") as handle:
            handle.write(preview_data)

        sent = await client.send_photo(
            chat_id=message.chat.id,
            photo=preview_path,
            caption="👁 Telegram free preview saved as Custom Thumbnail.",
        )
        saved_file_id = getattr(getattr(sent, "photo", None), "file_id", None)
        if not saved_file_id:
            return None

        await db.set_thumbnail(message.from_user.id, str(saved_file_id))
        await db.set_thumbnail_mode(message.from_user.id, "custom")
        try:
            await sent.delete()
        except Exception:
            pass
        return str(saved_file_id)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

@Client.on_message(filters.private, group=-10000)
async def owner_paid_photo_message(client, message: Message):
    if not message.from_user:
        return

    if not Config.OWNER_ID or int(message.from_user.id) != int(Config.OWNER_ID):
        return

    if not await db.get_paid_photo_waiting():
        return

    if not getattr(message, "paid_media", None):
        return

    paid_photo = _paid_photo_from_message(message)

    if paid_photo is None:
        progress = await message.reply_text(
            "🆓 **Free Preview Mode**\n\n"
            "🔎 Reading the free preview thumbnail..."
        )

        try:
            saved = await _save_paid_preview_thumbnail(client, message)
            if not saved:
                await progress.edit_text(
                    "❌ **Preview thumbnail is not available.**\n\n"
                    "Telegram did not provide usable preview data for this photo."
                )
                await db.set_paid_photo_waiting(False)
                raise StopPropagation

            await db.set_paid_photo_waiting(False)
            await progress.edit_text(
                "✅ **Preview saved as Custom Thumbnail.**\n\n"
                "🖼 This thumbnail will now be used for your processed files and videos.",
                reply_markup=_show_thumbnail_markup(),
            )
        except StopPropagation:
            raise
        except Exception as exc:
            await db.set_paid_photo_waiting(False)
            try:
                await progress.edit_text(
                    "❌ **Could not save the preview thumbnail.**\n\n"
                    f"{str(exc)[:800]}"
                )
            except Exception:
                pass
        raise StopPropagation

    work_dir = os.path.join("downloads", "owner_paid_photo", uuid.uuid4().hex)
    os.makedirs(work_dir, exist_ok=True)
    output_path = os.path.join(work_dir, "free_photo.jpg")

    progress = await message.reply_text(
        "⏳ **Paid photo received**\n\n"
        "🔄 Processing...\n"
        "⬇️ Downloading the image..."
    )

    try:
        known_size = int(getattr(paid_photo, "file_size", 0) or 0)
        if known_size > FREE_IMAGE_LIMIT:
            raise ValueError(
                f"This photo is {humanbytes(known_size)}, which is above the 20 MB limit."
            )

        downloaded = await client.download_media(
            paid_photo,
            file_name=output_path,
            progress=progress_for_pyrogram,
            progress_args=(
                "📥 Downloading",
                progress,
                time.time(),
                f"owner_paid_{message.id}",
            ),
        )
        if not downloaded or not os.path.isfile(downloaded):
            raise RuntimeError("Telegram did not provide the unlocked photo file.")

        actual_size = os.path.getsize(downloaded)
        if actual_size <= 0:
            raise RuntimeError("The downloaded photo is empty.")
        if actual_size > FREE_IMAGE_LIMIT:
            raise ValueError(
                f"The downloaded photo is {humanbytes(actual_size)}, which is above the 20 MB limit."
            )

        try:
            await progress.edit_text(
                f"⏳ **Paid photo received**\n\n"
                f"✅ Image downloaded: `{humanbytes(actual_size)}`\n"
                "📤 Creating a new free photo..."
            )
        except Exception:
            pass

        # Re-upload the downloaded file instead of reusing the paid-media
        # message. Telegram therefore receives a brand-new normal photo.
        await client.send_photo(
            chat_id=message.chat.id,
            photo=downloaded,
            caption=message.caption,
        )

        await db.set_paid_photo_waiting(False)

        try:
            await progress.edit_text(
                "✅ **Free photo created successfully.**\n\n"
                "⭐ The returned image is a new normal photo with no paid-media layer."
            )
        except Exception:
            pass

    except Exception as exc:
        await db.set_paid_photo_waiting(False)
        try:
            await progress.edit_text(
                "❌ **Paid photo processing failed.**\n\n"
                f"`{str(exc)[:800]}`"
            )
        except Exception:
            try:
                await message.reply_text(
                    "❌ **Paid photo processing failed.**\n\n"
                    f"`{str(exc)[:800]}`"
                )
            except Exception:
                pass
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    raise StopPropagation
