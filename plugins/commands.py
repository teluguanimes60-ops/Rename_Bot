"""Public bot command handlers."""

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from helper.database import db
from helper.i18n import t
from language.strings import tr
from plugins.ui import language_keyboard, thumbnail_menu, permanent_thumbnail_menu\nfrom language.strings import localize_markup


async def _language(user_id: int) -> str:
    return await db.get_language(user_id) or "en"


@Client.on_message(filters.private & filters.command("help"), group=-90)
async def command_help(client, message):
    lang = await _language(message.from_user.id)
    text = (
        "🛠 **AniToon Help**\n\n"
        "Send a document, video or audio to start processing.\n"
        "Use the buttons in the bot menu to choose your action.\n\n"
        "⚙️ **Available commands**\n"
        "• \`/start\`\n"
        "• \`/help\`\n"
        "• \`/cancel\`\n"
        "• \`/clone\`\n"
        "• \`/rename\`\n"
        "• \`/thumbnail\`\n"
        "• \`/plan\`\n"
        "• \`/language\`"
    )
    await message.reply_text(text)


@Client.on_message(filters.private & filters.command("rename"), group=-89)
async def command_rename(client, message):
    lang = await _language(int(message.from_user.id))
    await message.reply_text(
        f"✏️ **{tr(lang, 'Rename Page')}**\n\n"
        "📤 Send me a video, document, or audio file.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"🔙 {tr(lang, 'Home')}", callback_data="start")
        ]]),
    )


@Client.on_message(filters.private & filters.command("thumbnail"), group=-88)
async def command_thumbnail(client, message):
    user_id = int(message.from_user.id)
    lang = await _language(user_id)
    has_thumbnail = bool(await db.get_thumbnail(user_id))
    await message.reply_text(
        f"🖼 **{tr(lang, 'Thumbnail Page')}**\n\nChoose your thumbnail mode.",
        reply_markup=localize_markup(thumbnail_menu(), lang),
    )
    if has_thumbnail:
        await message.reply_text(
            f"🖼 **{tr(lang, 'Custom Thumbnail')}**\n\n"
            "Your saved thumbnail is available below.",
            reply_markup=localize_markup(permanent_thumbnail_menu(True), lang),
        )


@Client.on_message(filters.private & filters.command("plan"), group=-87)
async def command_plan(client, message):
    if not getattr(client, "is_main_bot", False):
        return await message.reply_text("Plans are available through the main bot.")
    from plugins.premium import send_plan_menu
    await send_plan_menu(client, message.from_user.id, int(getattr(client, "bot_id", 0)))


@Client.on_message(filters.private & filters.command("language"), group=-86)
async def command_language(client, message):
    user_id = int(message.from_user.id)
    lang = await _language(user_id)
    await message.reply_text(
        f"{t(lang, 'select_title')}\n\n{t(lang, 'select_prompt')}",
        reply_markup=language_keyboard(),
    )
