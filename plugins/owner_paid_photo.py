from __future__ import annotations

import os
import shutil
import time
import uuid

from pyrogram import Client, StopPropagation, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from helper.database import db
from helper.paid_preview import enhance_preview_jpeg, get_paid_preview_bytes, get_paid_preview_gallery_bytes
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

        class_name = type(obj).__name__
        raw_bytes = getattr(obj, "bytes", None)
        if isinstance(raw_bytes, (bytes, bytearray)) and raw_bytes:
            # Telegram's cached/stripped preview variants contain the actual
            # thumbnail bytes. Return them directly.
            if class_name in {"PhotoCachedSize", "PhotoStrippedSize"}:
                return bytes(raw_bytes)

        # Some generated wrappers expose the thumbnail one level deeper.
        for attr in (
            "thumb",
            "photo",
            "media",
            "extended_media",
            "raw",
            "_raw",
        ):
            child = getattr(obj, attr, None)
            if isinstance(child, (list, tuple)):
                for item in child:
                    result = walk(item)
                    if result:
                        return result
            else:
                result = walk(child)
                if result:
                    return result

        return None

    return walk(value)


def _show_thumbnail_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👁 Show Thumbnail", callback_data="owner:paid_preview:show")],
    ])


async def _process_paid_gallery(client, message: Message, progress: Message, preview_data_list: list[bytes]):
    work_dir = os.path.join(
        "downloads",
        "owner_paid_photo",
        f"gallery_{uuid.uuid4().hex}",
    )
    os.makedirs(work_dir, exist_ok=True)

    paths = []
    try:
        total = len(preview_data_list)
        for index, raw_data in enumerate(preview_data_list, 1):
            await progress.edit_text(
                f"🆓 **Free Preview Mode**\\n\\n"
                f"🖼 Enhancing image **{index}/{total}** toward 4K...\\n"
                "🔎 Improving text visibility..."
            )
            enhanced = enhance_preview_jpeg(raw_data, target_edge=3840)
            if not enhanced:
                raise RuntimeError(f"Could not enhance preview image {index}.")
            path = os.path.join(work_dir, f"preview_{index}.jpg")
            with open(path, "wb") as handle:
                handle.write(enhanced)
            paths.append(path)

        # Send the three images as a normal Telegram media group.
        sent_messages = await client.send_media_group(
            chat_id=message.chat.id,
            media=paths,
        )

        file_ids = []
        for sent in sent_messages:
            photo = getattr(sent, "photo", None)
            if photo:
                file_ids.append(str(photo[-1].file_id))

        if len(file_ids) != total:
            raise RuntimeError("Telegram did not return all gallery file IDs.")

        gallery_id = uuid.uuid4().hex[:16]
        await db.set_paid_preview_gallery(
            gallery_id,
            message.from_user.id,
            file_ids,
        )

        buttons = [
            [
                InlineKeyboardButton(
                    f"🖼 Image {index}",
                    callback_data=f"owner:paid_gallery:{gallery_id}:{index}",
                )
            ]
            for index in range(1, total + 1)
        ]

        await message.reply_text(
            f"✅ **{total} preview images created in 4K size.**\\n\\n"
            "These images are **not saved as file/video thumbnails**.\\n"
            "Tap a button to view an individual image:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

        await db.set_paid_photo_waiting(False)
        await progress.delete()

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
            "🔎 Reading all free preview images..."
        )

        try:
            previews = await get_paid_preview_gallery_bytes(
                client,
                int(message.chat.id),
                int(message.id),
            )

            if not previews:
                await progress.edit_text(
                    "❌ **Free preview images are not available.**\n\n"
                    "Telegram did not provide usable preview data."
                )
                await db.set_paid_photo_waiting(False)
                raise StopPropagation

            # The gallery path is deliberately independent from the user's
            # thumbnail settings. These images are never stored as thumbnails.
            if len(previews) >= 3:
                await _process_paid_gallery(client, message, progress, previews[:3])
            else:
                # For one/two previews, return them normally as a small gallery
                # too; still do not modify the thumbnail setting.
                await _process_paid_gallery(client, message, progress, previews)

        except StopPropagation:
            raise
        except Exception as exc:
            await db.set_paid_photo_waiting(False)
            try:
                await progress.edit_text(
                    "❌ **Could not create the preview images.**\n\n"
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


@Client.on_callback_query(
    filters.regex(r"^owner:paid_preview:show$"),
    group=-10001,
)
async def owner_paid_preview_show(client, callback_query):
    if not Config.OWNER_ID or int(callback_query.from_user.id) != int(Config.OWNER_ID):
        await callback_query.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    try:
        thumb = await db.get_thumbnail(callback_query.from_user.id)
        if not thumb:
            await callback_query.answer(
                "Custom thumbnail is not available.",
                show_alert=True,
            )
            raise StopPropagation

        await callback_query.answer("Loading thumbnail…")
        await client.send_photo(
            callback_query.from_user.id,
            thumb,
            caption="🖼 **Current Custom Thumbnail**",
        )
    except Exception as exc:
        await callback_query.answer(
            f"Could not show thumbnail: {str(exc)[:160]}",
            show_alert=True,
        )

    raise StopPropagation


@Client.on_callback_query(
    filters.regex(r"^owner:paid_gallery:[a-f0-9]{16}:[123]$"),
    group=-10001,
)
async def owner_paid_gallery_show(client, callback_query):
    if not Config.OWNER_ID or int(callback_query.from_user.id) != int(Config.OWNER_ID):
        await callback_query.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    try:
        parts = callback_query.data.split(":")
        gallery_id = parts[2]
        index = int(parts[3]) - 1

        file_ids = await db.get_paid_preview_gallery(
            gallery_id,
            callback_query.from_user.id,
        )

        if index < 0 or index >= len(file_ids):
            await callback_query.answer("Image is no longer available.", show_alert=True)
            raise StopPropagation

        await callback_query.answer(f"Loading image {index + 1}…")
        await client.send_photo(
            callback_query.from_user.id,
            file_ids[index],
            caption=f"🖼 **Preview Image {index + 1}**",
        )
    except Exception as exc:
        await callback_query.answer(
            f"Could not show image: {str(exc)[:160]}",
            show_alert=True,
        )

    raise StopPropagation
