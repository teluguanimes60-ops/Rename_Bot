from pyrogram import Client, filters
import os
import shutil
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from helper.database import db


# ============================================================
# SAVE THUMBNAIL
# ============================================================

@Client.on_message(
    filters.private & filters.photo
)
async def save_photo(client: Client, message: Message):
    """Ask whether a received image should be added/replaced as the permanent thumbnail."""
    user_id = int(message.from_user.id)
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id)

    has_thumbnail = bool(await db.get_thumbnail(user_id))
    action = "replace" if has_thumbnail else "add"
    prompt = (
        "🖼 **Image Received**\\n\\n"
        + (
            "Do you want to replace your current permanent thumbnail with this image?"
            if has_thumbnail
            else "Do you want to add this image as your permanent thumbnail?"
        )
    )
    await message.reply_text(
        prompt,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔄 Replace Thumbnail" if has_thumbnail else "➕ Add Thumbnail",
                    callback_data=f"thumb_choice:{action}:{message.id}",
                ),
                InlineKeyboardButton("🚫 No Thumbnail", callback_data=f"thumb_choice:no:{message.id}"),
            ]
        ]),
    )


@Client.on_callback_query(filters.regex(r"^thumb_choice:(add|replace|no):(\\d+)$"))
async def thumbnail_choice_callback(client: Client, callback_query):
    action = callback_query.matches[0].group(1)
    source_message_id = int(callback_query.matches[0].group(2))
    user_id = int(callback_query.from_user.id)
    try:
        source = await client.get_messages(user_id, source_message_id)
    except Exception:
        source = None

    if not source or not getattr(source, "photo", None):
        await callback_query.answer("The image message could not be found.", show_alert=True)
        return

    if action == "no":
        await callback_query.answer("Thumbnail not changed.")
        try:
            await callback_query.message.edit_text(
                "🚫 **Thumbnail Not Changed**\\n\\nYour current permanent thumbnail, if any, remains active."
            )
        except Exception:
            pass
        return

    await callback_query.answer("Saving thumbnail...")
    work_dir = os.path.join("thumbnails", str(user_id))
    os.makedirs(work_dir, exist_ok=True)
    temp_path = os.path.join(work_dir, f"new_{source_message_id}.jpg")

    try:
        await callback_query.message.edit_text(
            "🔄 **Downloading image and saving it as your permanent thumbnail...**"
        )
        downloaded = await client.download_media(source, file_name=temp_path)
        downloaded_path = downloaded if isinstance(downloaded, str) else temp_path
        if not os.path.isfile(downloaded_path) or os.path.getsize(downloaded_path) <= 0:
            raise RuntimeError("The image could not be downloaded correctly.")

        await db.set_thumbnail(user_id, str(source.photo.file_id))
        await db.set_thumbnail_mode(user_id, "custom")

        result_text = (
            "✅ **Thumbnail Added Successfully!**\\n\\n"
            "This image is now your permanent thumbnail for all processed files and videos."
            if action == "add"
            else
            "✅ **Thumbnail Replaced Successfully!**\\n\\n"
            "The new image is now your permanent thumbnail for all processed files and videos."
        )
        await callback_query.message.edit_text(result_text)
    except Exception as exc:
        try:
            await callback_query.message.edit_text(
                "❌ **Failed to save image as thumbnail.**\\n\\n"
                f"`{str(exc)[:1000]}`"
            )
        except Exception:
            pass
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@Client.on_callback_query(filters.regex(r"^thumb_manage:(add|replace)$"))
async def thumbnail_manage_callback(client: Client, callback_query):
    action = callback_query.matches[0].group(1)
    user_id = int(callback_query.from_user.id)
    has_thumbnail = bool(await db.get_thumbnail(user_id))
    if action == "replace" and not has_thumbnail:
        action = "add"
    label = "replace" if action == "replace" else "add"
    await callback_query.answer(
        "Send the image you want to replace your thumbnail with."
        if label == "replace"
        else "Send the image you want to add as your thumbnail."
    )
    await client.send_message(
        user_id,
        "🖼 **Send the image now.**\\n\\n"
        + (
            "This image will replace your current permanent thumbnail."
            if label == "replace"
            else "This image will be saved as your permanent thumbnail for all processed files and videos."
        )
    )


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
