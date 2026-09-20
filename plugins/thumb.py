from pyrogram import Client, filters
import os
import shutil
from pyrogram.types import Message

from helper.database import db


# ============================================================
# SAVE THUMBNAIL
# ============================================================

@Client.on_message(
    filters.private & filters.photo
)
async def save_photo(
    client: Client,
    message: Message,
):
    """Download the photo, validate it, and make it the active permanent thumbnail."""
    user_id = int(message.from_user.id)

    if not await db.is_user_exist(user_id):
        await db.add_user(user_id)

    status = await message.reply_text(
        "🔄 **AniToon: Downloading image and saving it as your thumbnail...**"
    )

    work_dir = os.path.join("thumbnails", str(user_id))
    os.makedirs(work_dir, exist_ok=True)
    temp_path = os.path.join(work_dir, f"new_{message.id}.jpg")

    try:
        old_thumbnail = await db.get_thumbnail(user_id)

        # Download the image first so the bot validates the actual photo before
        # making it active. The persistent value remains Telegram's file_id,
        # so the thumbnail survives application/container restarts.
        downloaded = await client.download_media(
            message,
            file_name=temp_path,
        )
        downloaded_path = downloaded if isinstance(downloaded, str) else temp_path

        if not os.path.isfile(downloaded_path) or os.path.getsize(downloaded_path) <= 0:
            raise RuntimeError("The image could not be downloaded correctly.")

        # Replace the previous permanent thumbnail with the new photo.
        await db.set_thumbnail(user_id, str(message.photo.file_id))
        await db.set_thumbnail_mode(user_id, "custom")

        if old_thumbnail:
            result_text = (
                "✅ **Image Saved Successfully for Thumbnail!**\n\n"
                "Your new image has replaced the previous permanent thumbnail.\n"
                "It will be used automatically for your files and videos."
            )
        else:
            result_text = (
                "✅ **Image Saved Successfully for Thumbnail!**\n\n"
                "This image is now your permanent thumbnail and will be used automatically for your files and videos."
            )

        await status.edit_text(result_text)

    except Exception as exc:
        try:
            await status.edit_text(
                "❌ **Failed to save image as thumbnail.**\n\n"
                f"`{str(exc)[:1000]}`"
            )
        except Exception:
            pass
    finally:
        # The permanent thumbnail is stored as a Telegram file_id in MongoDB;
        # the local downloaded copy is only temporary validation data.
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass

# ============================================================
# VIEW THUMBNAIL
# ============================================================

@Client.on_message(
    filters.private
    & filters.command(
        ["setthumb", "set_thumb"]
    )
)
async def set_thumbnail_command(
    client: Client,
    message: Message,
):
    await message.reply_text(
        "🖼️ **Send me an image now.**\n\n"
        "The bot will automatically download and save it as your permanent thumbnail for all files and videos."
    )


@Client.on_message(
    filters.private
    & filters.command(
        ["viewthumb", "view_thumb", "showthumb"]
    )
)
async def view_thumbnail(
    client: Client,
    message: Message,
):
    """
    Displays the user's currently saved thumbnail.
    """

    user_id = message.from_user.id

    thumb = await db.get_thumbnail(
        user_id
    )

    if thumb:
        await message.reply_photo(
            photo=thumb,
            caption=(
                "🖼️ **Your Current Custom Thumbnail**\n\n"
                "Use `/delthumb` to remove it."
            ),
        )

    else:
        await message.reply_text(
            "❌ **No Custom Thumbnail Set**\n\n"
            "Send me any image to save it as your permanent thumbnail."
        )


# ============================================================
# DELETE THUMBNAIL
# ============================================================

@Client.on_message(
    filters.private
    & filters.command(
        ["delthumb", "del_thumb", "deletethumb"]
    )
)
async def delete_thumbnail(
    client: Client,
    message: Message,
):
    """
    Removes the user's saved thumbnail.
    """

    user_id = message.from_user.id

    await db.set_thumbnail(
        user_id,
        None,
    )
    await db.set_thumbnail_mode(user_id, "none")

    await message.reply_text(
        "🗑️ **Custom Thumbnail Deleted.**\n\n"
        "Your files will now use automatically generated "
        "or original thumbnails."
    )
