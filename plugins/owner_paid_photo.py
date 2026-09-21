from pyrogram import Client, StopPropagation, filters
from pyrogram.types import Message

from config import Config
from helper.database import db

FREE_IMAGE_LIMIT = 20 * 1024 * 1024


async def _is_owner_waiting(message: Message) -> bool:
    if not Config.OWNER_ID or int(message.from_user.id) != int(Config.OWNER_ID):
        return False
    return await db.get_paid_photo_waiting()


def _get_paid_photo(message: Message):
    paid = getattr(message, "paid_media", None)
    if not paid:
        return None

    for media in getattr(paid, "extended_media", []) or []:
        # A purchased paid-media photo is exposed as a normal Photo object
        # inside PaidMedia.extended_media. Preview-only media is not usable.
        if getattr(media, "file_id", None):
            size = int(getattr(media, "file_size", 0) or 0)
            if size <= 0 or size > FREE_IMAGE_LIMIT:
                continue
            return media
    return None


@Client.on_message(
    filters.private & filters.create(
        lambda _, __, message: bool(getattr(message, "paid_media", None))
    ),
    group=-10000,
)
async def owner_paid_photo_message(client, message: Message):
    if not await _is_owner_waiting(message):
        return

    paid_photo = _get_paid_photo(message)

    if paid_photo is None:
        await message.reply_text(
            "❌ This paid photo is not unlocked or is larger than 20 MB.\n\n"
            "Send an unlocked paid photo up to 20 MB."
        )
        return

    progress = await message.reply_text(
        "⏳ **Paid photo received**\n\n"
        "🔄 Processing...\n"
        "⬇️ Reading the unlocked photo..."
    )

    try:
        await client.send_photo(
            chat_id=message.chat.id,
            photo=paid_photo.file_id,
            caption=message.caption,
        )

        await db.set_paid_photo_waiting(False)

        try:
            await progress.edit_text(
                "⏳ **Paid photo received**\n\n"
                "📤 Sending free photo...\n"
                "✅ Stars payment layer removed from this copy."
            )
        except Exception:
            pass

    except Exception:
        await db.set_paid_photo_waiting(False)
        try:
            await progress.edit_text(
                "❌ Could not send the free photo.\n\n"
                "Please send the unlocked paid photo again."
            )
        except Exception:
            await message.reply_text(
                "❌ Could not send the free photo. Please send it again."
            )

    raise StopPropagation
