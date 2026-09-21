from __future__ import annotations

import os
import shutil
import time
import uuid

from pyrogram import Client, StopPropagation, filters
from pyrogram.types import Message

from config import Config
from helper.database import db
from helper.utils import humanbytes, progress_for_pyrogram

FREE_IMAGE_LIMIT = 20 * 1024 * 1024


def _paid_photo_from_message(message: Message):
    paid_media = getattr(message, "paid_media", None)
    if not paid_media:
        return None

    for media in getattr(paid_media, "extended_media", []) or []:
        # Purchased paid media exposes the unlocked image as a normal
        # Photo object. Preview-only paid media has no reusable file_id.
        file_id = getattr(media, "file_id", None)
        if file_id:
            return media
    return None


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
        await message.reply_text(
            "❌ **This paid photo is still locked.**\n\n"
            "Open/unlock the paid photo in Telegram first, then send it here again."
        )
        return

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
