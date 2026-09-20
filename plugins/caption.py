from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from helper.database import db


# ============================================================
# DELETE BUTTON
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^del_caption$")
)
async def cb_del_caption(
    client: Client,
    callback_query,
):
    await db.set_caption(
        callback_query.from_user.id,
        None,
    )

    await callback_query.answer(
        "Caption deleted 🗑️",
        show_alert=True,
    )

    from plugins.ui import edit_callback_message

    await edit_callback_message(
        callback_query,
        "🗑️ **Custom Caption has been removed.**",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⚙️ Settings",
                        callback_data="settings",
                    )
                ]
            ]
        ),
    )


# ============================================================
# CAPTION HELP BUTTON
# ============================================================

@Client.on_callback_query(
    filters.regex(r"^help_caption$")
)
async def cb_help_caption(
    client: Client,
    callback_query,
):
    await callback_query.answer()

    from plugins.ui import edit_callback_message

    await edit_callback_message(
        callback_query,
        "💡 **Custom Caption Help**\n\n"
        "**Available placeholders:**\n\n"
        "• `{filename}` — File name\n"
        "• `{filesize}` — File size\n"
        "• `{duration}` — Video duration\n\n"
        "**Example:**\n"
        "`🎥 File: {filename}`\n"
        "`📦 Size: {filesize}`\n"
        "`⏱️ Duration: {duration}`",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📝 Set Caption",
                        callback_data="set_caption_help",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="settings_caption",
                    )
                ],
            ]
        ),
    )
