
from pyrogram import Client, StopPropagation, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from helper.owner_action_router import clear_pending
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def is_owner(user_id: int) -> bool:
    return bool(Config.OWNER_ID and int(user_id) == int(Config.OWNER_ID))


def owner_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛠 Help", callback_data="help"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
        ],
        [InlineKeyboardButton("✏️ Rename", callback_data="start_rename")],
        [
            InlineKeyboardButton(
                "🤖 Create Your Own Clone Bot",
                callback_data="create_clone",
            )
        ],
        [InlineKeyboardButton("👑 Owner Panel", callback_data="owner:panel")],
    ])


def panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistics", callback_data="owner:stats")],
        [
            InlineKeyboardButton("💎 Plans", callback_data="owner:plans"),
            InlineKeyboardButton("⭐ Stars", callback_data="owner:stars"),
        ],
        [InlineKeyboardButton("🤖 Bot Details", callback_data="owner:bots")],
        [InlineKeyboardButton("📣 Broadcast", callback_data="owner:broadcast")],
        [InlineKeyboardButton("🔙 Home", callback_data="start")],
    ])


async def show_owner_home(message):
    await message.edit_text(
        "🔥 **Welcome to AniToon Bot** 🔥\n\n"
        "👑 **Owner access detected**\n"
        "⚡ Unlimited owner access\n\n"
        "Use the owner controls below.",
        reply_markup=owner_keyboard(),
    )


@Client.on_message(filters.private & filters.command("start"), group=-300)
async def owner_start_page(client, message):
    if not getattr(client, "is_main_bot", False) or not is_owner(message.from_user.id):
        return
    clear_pending(message.from_user.id)
    await message.reply_text(
        "🔥 **Welcome to AniToon Bot** 🔥\n\n"
        "👑 **Owner access detected**\n"
        "⚡ Unlimited owner access\n\n"
        "Use the owner controls below.",
        reply_markup=owner_keyboard(),
    )
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^owner:panel$"), group=-300)
async def owner_panel_entry(client, callback_query):
    if not getattr(client, "is_main_bot", False) or not is_owner(callback_query.from_user.id):
        await callback_query.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    clear_pending(callback_query.from_user.id)
    await callback_query.answer()
    await callback_query.message.edit_text(
        "👑 **AniToon Owner Panel**\n\n"
        "Use a button below or the matching owner command.",
        reply_markup=panel_keyboard(),
    )
    raise StopPropagation


@Client.on_callback_query(
    filters.regex(r"^owner:(stats|plans|bots|broadcast)$"),
    group=-300,
)
async def owner_panel_fallback(client, callback_query):
    if not getattr(client, "is_main_bot", False) or not is_owner(callback_query.from_user.id):
        await callback_query.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    await callback_query.answer()
    action = callback_query.matches[0].group(1)

    text = {
        "stats": "📊 **Statistics**\n\nUse /users or /stats.",
        "plans": "💎 **Plans**\n\nUse /plans or /ownerplans.",
        "bots": "🤖 **Bot Details**\n\nUse /botdetails or /ownerbots.",
        "broadcast": "📣 **Broadcast**\n\nReply to a message and use /broadcast.",
    }[action]

    await callback_query.message.edit_text(
        text,
        reply_markup=panel_keyboard(),
    )
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^start$"), group=-300)
async def owner_home_callback(client, callback_query):
    if not getattr(client, "is_main_bot", False) or not is_owner(callback_query.from_user.id):
        return

    clear_pending(callback_query.from_user.id)
    await callback_query.answer()
    await show_owner_home(callback_query.message)
    raise StopPropagation
