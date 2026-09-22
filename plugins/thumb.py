from pyrogram import Client, filters
import os
import shutil
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from helper.database import db


# ============================================================
# SAVE THUMBNAIL
# ============================================================

@Client.on_message(
    filters.private & (filters.photo | filters.document),
    group=-9000,
)
async def save_photo(client, message: Message):
    """Save the next user-sent image only during an Add/Replace thumbnail flow."""
    user = message.from_user
    if not user:
        return

    user_id = int(user.id)
    user_data = await db.get_user_data(user_id) or {}
    pending = str(user_data.get("thumbnail_pending") or "").strip().lower()
    if pending not in {"add", "replace"}:
        # Never consume ordinary photos/documents as thumbnails.
        return

    photo = getattr(message, "photo", None)
    document = getattr(message, "document", None)

    # Accept normal Telegram photos and image/* documents. The UI asks for a
    # photo, but accepting an image document makes the flow more reliable.
    if photo is not None:
        file_id = getattr(photo, "file_id", None)
    elif document is not None and str(getattr(document, "mime_type", "") or "").lower().startswith("image/"):
        file_id = getattr(document, "file_id", None)
    else:
        file_id = None

    if not file_id:
        try:
            await message.reply_text(
                "❌ Please send an image/photo while Replace Thumbnail is active."
            )
        except Exception:
            pass
        return

    try:
        await db.set_thumbnail(user_id, str(file_id))
        await db.set_thumbnail_mode(user_id, "custom")
        prompt_id = user_data.get("thumbnail_prompt_message_id")

        await db.col.update_one(
            {"id": user_id},
            {
                "$unset": {
                    "thumbnail_pending": "",
                    "thumbnail_prompt_message_id": "",
                }
            },
        )

        try:
            await message.delete()
        except Exception:
            pass

        title = "Added" if pending == "add" else "Replaced"
        success_text = (
            f"✅ **Thumbnail {title} Successfully!**\n\n"
            "This image is now your permanent custom thumbnail for all processed files and videos."
        )

        # Edit the same Thumbnail Setup message.
        if prompt_id:
            try:
                await client.edit_message_text(
                    user_id,
                    int(prompt_id),
                    success_text,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Back", callback_data="settings_thumb")]
                    ]),
                )
            except Exception:
                # The thumbnail is already saved even if Telegram cannot edit
                # the old setup message.
                pass

        # This photo has been fully handled; do not let another media handler
        # process it as an unrelated file.
        from pyrogram import StopPropagation
        raise StopPropagation

    except StopPropagation:
        raise
    except Exception as exc:
        try:
            await db.col.update_one(
                {"id": user_id},
                {"$unset": {"thumbnail_pending": ""}},
            )
        except Exception:
            pass
        try:
            await message.reply_text(
                "❌ **Failed to save thumbnail.**\n\n"
                f"`{str(exc)[:1000]}`",
            )
        except Exception:
            pass


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
                "🚫 **Thumbnail Not Changed**\n\nYour current permanent thumbnail, if any, remains active."
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
            "✅ **Thumbnail Added Successfully!**\n\n"
            "This image is now your permanent thumbnail for all processed files and videos."
            if action == "add"
            else
            "✅ **Thumbnail Replaced Successfully!**\n\n"
            "The new image is now your permanent thumbnail for all processed files and videos."
        )
        await callback_query.message.edit_text(result_text)
    except Exception as exc:
        try:
            await callback_query.message.edit_text(
                "❌ **Failed to save image as thumbnail.**\n\n"
                f"`{str(exc)[:1000]}`"
            )
        except Exception:
            pass
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@Client.on_callback_query(
    filters.regex(r"^thumb_manage:(add|replace)$"),
    group=-11000,
)
async def thumbnail_manage_callback(client: Client, callback_query):
    user_id = int(callback_query.from_user.id)
    requested_action = callback_query.matches[0].group(1)

    # Acknowledge immediately so Telegram never leaves the button spinning
    # while MongoDB/state preparation is running.
    await callback_query.answer(
        "✅ Now send the image."
        if requested_action == "add"
        else "✅ Now send the replacement image."
    )

    try:
        action = requested_action
        if action == "replace" and not await db.get_thumbnail(user_id):
            # Protect against a stale Replace button after the thumbnail was deleted.
            action = "add"

        label = "replace" if action == "replace" else "add"
        message_id = int(callback_query.message.id)

        # Persist the pending action and the exact settings-page message used
        # for the in-place setup screen.
        await db.add_user(user_id)
        await db.col.update_one(
            {"id": user_id},
            {
                "$set": {
                    "thumbnail_pending": label,
                    "thumbnail_prompt_message_id": message_id,
                }
            },
            upsert=True,
        )

        await callback_query.message.edit_text(
            "🖼 **Send the image now.**\n\n"
            + (
                "This image will replace your current permanent thumbnail."
                if label == "replace"
                else "This image will be saved as your permanent thumbnail for all processed files and videos."
            )
            + "\n\n📌 **Send the photo as an image (not as a file/document).**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="settings_thumb")]
            ]),
        )
    except Exception:
        # The callback is already acknowledged. Keep the UI usable rather than
        # leaving Telegram with a silent/spinning button.
        try:
            await callback_query.message.edit_text(
                "❌ **Could not open thumbnail setup.**\n\n"
                "Please press **Add/Replace Thumbnail** again.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="settings_thumb")]
                ]),
            )
        except Exception:
            pass



# ============================================================
# VIEW THUMBNAIL
# ============================================================


async def set_thumbnail_command(
    client: Client,
    message: Message,
):
    await db.col.update_one(
        {"id": int(message.from_user.id)},
        {"$set": {"thumbnail_pending": "add"}},
        upsert=True,
    )
    await message.reply_text(
        "🖼️ **Send me an image now.**\n\n"
        "The bot will automatically download and save it as your permanent thumbnail for all files and videos."
    )


# ============================================================
# DELETE THUMBNAIL
# ============================================================

