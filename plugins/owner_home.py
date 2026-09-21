from pyrogram import Client, StopPropagation, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from plugins.owner_action_router import clear_pending


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
        [InlineKeyboardButton("🖼 Remove Paid Stars Photo", callback_data="owner:paid_photo")],
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


async def _owner_home_text(client, user_id: int) -> str:
    bot_id = int(getattr(client, "bot_id", 0) or 0)
    try:
        from helper.database import db
        from helper.plans import get_plan
        from helper.utils import humanbytes
        subscription = await db.get_subscription(user_id, bot_id)
        plan = get_plan(subscription.get("plan", "free"))
        used = await db.get_usage(user_id, bot_id)
        plan_name = plan.name
        used_text = humanbytes(used)
        remaining_text = humanbytes(max(plan.daily_limit - used, 0))
    except Exception:
        plan_name, used_text, remaining_text = "🆓 Free", "0 B", "10 GB"

    try:
        user = await client.get_users(user_id)
        first_name = user.first_name or "Owner"
    except Exception:
        first_name = "Owner"

    return (
        "🔥 **Welcome to AniToon Bot** 🔥\n\n"
        f"👋 Hello **{first_name}**!\n\n"
        f"💎 **Plan:** {plan_name}\n"
        f"📊 **Used today:** `{used_text}`\n"
        f"📦 **Remaining:** `{remaining_text}`\n\n"
        "⚡ Fast processing • Clean filenames • Advanced media tools"
    )


async def show_owner_home(client, message):
    await message.edit_text(
        await _owner_home_text(client, int(message.from_user.id)),
        reply_markup=owner_keyboard(),
    )


@Client.on_message(filters.private & filters.command("start"), group=-300)
async def owner_start_page(client, message):
    if not getattr(client, "is_main_bot", False) or not is_owner(message.from_user.id):
        return
    clear_pending(message.from_user.id)
    await message.reply_text(
        await _owner_home_text(client, int(message.from_user.id)),
        reply_markup=owner_keyboard(),
    )
    raise StopPropagation




@Client.on_callback_query(filters.regex(r"^owner:paid_photo$"), group=-300)
async def owner_paid_photo_page(client, callback_query):
    if not getattr(client, "is_main_bot", False) or not is_owner(callback_query.from_user.id):
        await callback_query.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    from helper.database import db
    clear_pending(callback_query.from_user.id)
    await db.set_paid_photo_waiting(True)
    await callback_query.answer()
    await callback_query.message.edit_text(
        "🖼 **Remove Paid Stars from Photo**\n\n"
        "Send one paid Stars photo now.\n\n"
        "The bot will process it and send it back to you as a normal free photo.\n\n"
        "✅ Only photos up to 20 MB are accepted.\n"
        "⏳ Processing progress will be shown.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="owner:paid_photo:cancel")]
        ]),
    )
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^owner:paid_photo:cancel$"), group=-300)
async def owner_paid_photo_cancel(client, callback_query):
    if not getattr(client, "is_main_bot", False) or not is_owner(callback_query.from_user.id):
        await callback_query.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    from helper.database import db
    await db.set_paid_photo_waiting(False)
    clear_pending(callback_query.from_user.id)
    await callback_query.answer()
    await show_owner_home(client, callback_query.message)
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
    await show_owner_home(client, callback_query.message)
    raise StopPropagation
