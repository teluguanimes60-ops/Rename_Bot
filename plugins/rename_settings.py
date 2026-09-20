from __future__ import annotations

from pyrogram import Client, StopPropagation, filters
from pyrogram.types import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Message

from helper.database import db
from plugins.ui import edit_callback_message

MODES = {
    "manual": "✏️ Manual — ask for a new name every time",
    "auto": "🤖 Auto Rename — clean the name automatically",
    "permanent": "🏷 Permanent Text — apply your saved template",
}


def settings_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Manual", callback_data="rename_mode:manual")],
        [InlineKeyboardButton("🤖 Auto Rename", callback_data="rename_mode:auto")],
        [InlineKeyboardButton("🏷 Permanent Text", callback_data="rename_mode:permanent")],
        [InlineKeyboardButton("🔙 Settings", callback_data="settings")],
    ])


async def page_text(user_id: int) -> str:
    mode = await db.get_rename_mode(user_id)
    template = await db.get_rename_template(user_id)
    template_text = f"\`{template}\`" if template else "\`Not set\`"
    return (
        "✏️ **Rename Settings**\n\n"
        f"Current mode: **{MODES.get(mode, MODES['manual'])}**\n\n"
        "🏷 **Permanent template:**\n"
        f"{template_text}\n\n"
        "**Permanent template placeholders:**\n"
        "`{name}` — original filename without extension\n"
        "`{filename}` — original full filename\n"
        "`{ext}` — original extension\n"
        "`{title}` — cleaned title\n"
        "`{season}` — detected season, e.g. S01\n"
        "`{episode}` — detected episode, e.g. E05\n"
        "`{year}` — detected year\n"
        "`{resolution}` — detected resolution\n"
        "`{language}` — detected language when present\n\n"
        "Examples:\n"
        "`{name} - Telugu Anime`\n"
        "`[AniToon] {title} {season}{episode}`\n"
        "`{title} {episode} - {language}`\n\n"        "Default for every user is **Manual** until changed here."
    )


async def show_settings(client: Client, user_id: int, message: Message | None = None):
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id)
    text = await page_text(user_id)
    if message is not None:
        await message.reply_text(text, reply_markup=settings_markup())
    else:
        await client.send_message(user_id, text, reply_markup=settings_markup())


@Client.on_callback_query(filters.regex(r"^rename_settings$"), group=-2900)
async def rename_settings_button(client, cb):
    await cb.answer()
    await edit_callback_message(
        cb,
        await page_text(cb.from_user.id),
        reply_markup=settings_markup(),
    )
    raise StopPropagation


@Client.on_callback_query(
    filters.regex(r"^rename_mode:(manual|auto|permanent)$"),
    group=-2900,
)
async def rename_mode_button(client, cb):
    mode = cb.matches[0].group(1)
    user_id = int(cb.from_user.id)

    if mode == "permanent":
        await cb.answer("Set your permanent message.", show_alert=True)
        prompt = await client.send_message(
            user_id,
            "🏷 **Set Your Permanent Rename Message**\\n\\n"
            "Send the permanent message/text you want to add to every renamed file.\\n\\n"
            "Example:\\n"
            "\\`{name} - Telugu Anime\\`\\n\\n"
            "**Available placeholders:**\\n"
            "\\`{name}\\` — original filename without extension\\n"
            "\\`{filename}\\` — original full filename\\n"
            "\\`{ext}\\` — original extension\\n"
            "\\`{title}\\` — cleaned title\\n"
            "\\`{season}\\` — detected season\\n"
            "\\`{episode}\\` — detected episode\\n"
            "\\`{year}\\` — detected year\\n"
            "\\`{resolution}\\` — detected resolution\\n"
            "\\`{language}\\` — detected language",
            reply_markup=ForceReply(selective=True),
        )
        await db.col.update_one(
            {"id": user_id},
            {"$set": {"rename_template_prompt": prompt.id}},
            upsert=True,
        )
        raise StopPropagation

    await db.set_rename_mode(user_id, mode)
    await cb.answer("Rename mode updated ✅", show_alert=True)
    await edit_callback_message(
        cb,
        await page_text(user_id),
        reply_markup=settings_markup(),
    )
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^rename_template$"), group=-2900)
async def rename_template_button(client, cb):
    await cb.answer()
    prompt = await client.send_message(
        cb.from_user.id,
        "🏷 **Permanent Rename Text**\n\n"
        "Send a template such as:\n"
        "\`{name} - Telugu Anime\`\n"
        "\`[AniToon] {name}\`\n\n"
        "Available: \`{name}\`, \`{filename}\`, \`{ext}\`, \`{title}\`, \`{season}\`, \`{episode}\`, \`{year}\`, \`{resolution}\`, \`{language}\`",
        reply_markup=ForceReply(selective=True),
    )
    await db.col.update_one(
        {"id": int(cb.from_user.id)},
        {"$set": {"rename_template_prompt": prompt.id}},
        upsert=True,
    )
    raise StopPropagation


@Client.on_message(
    filters.private & filters.text & filters.reply,
    group=-2900,
)
async def rename_template_reply(client, message: Message):
    user_id = int(message.from_user.id)
    user = await db.get_user_data(user_id) or {}
    prompt_id = user.get("rename_template_prompt")
    reply = message.reply_to_message

    if not prompt_id or not reply or int(reply.id) != int(prompt_id):
        return

    template = (message.text or "").strip()
    if not template:
        await message.reply_text("❌ Permanent text cannot be empty.")
        return
    if len(template) > 220:
        await message.reply_text("❌ Permanent text is too long. Keep it under 220 characters.")
        return

    await db.set_rename_template(user_id, template)
    await db.set_rename_mode(user_id, "permanent")
    await db.col.update_one(
        {"id": user_id},
        {"$unset": {"rename_template_prompt": ""}},
    )
    await message.reply_text(
        "✅ **Permanent rename text saved.**\n\n"
        f"\`{template}\`\n\n"
        "Mode automatically changed to **Permanent**.",
        reply_markup=settings_markup(),
    )
    raise StopPropagation


