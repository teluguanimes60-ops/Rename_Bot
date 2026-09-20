from __future__ import annotations

from pyrogram import Client, StopPropagation, filters
from pyrogram.types import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Message

from helper.database import db
from helper.metadata import MetadataSettings, get_metadata, reset_metadata, update_metadata_part
from plugins.ui import edit_callback_message


def metadata_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎵 Set Audio", callback_data="meta:audio")],
        [InlineKeyboardButton("📜 Set Subtitle", callback_data="meta:subtitle")],
        [InlineKeyboardButton("🔄 Reset Defaults", callback_data="reset_metadata")],
        [InlineKeyboardButton("🔙 Back", callback_data="settings")],
    ])


def _show(value: str) -> str:
    return value if str(value or "").strip() else "None"


def _text(settings: MetadataSettings) -> str:
    return (
        "🏷 **Metadata Settings**\n\n"
        "🎵 **Audio tracks:** Language is detected from each track automatically.\n"
        f"Prefix: `{_show(settings.audio_prefix)}`  •  Suffix: `{_show(settings.audio_suffix)}`\n\n"
        "📜 **Subtitle tracks:** Language is detected from each track automatically.\n"
        f"Prefix: `{_show(settings.subtitle_prefix)}`  •  Suffix: `{_show(settings.subtitle_suffix)}`\n\n"
        "The language name is kept visible in the final audio/subtitle track title.\n"
        "Example: `@anitoon_edit English` or `@anitoon_edit Japanese Dub`.\n\n"
        "Choose **Set Audio** or **Set Subtitle** to change only the Prefix or Suffix."
    )

def _section_text(kind: str, settings: MetadataSettings) -> str:
    if kind == "audio":
        prefix, suffix = settings.audio_prefix, settings.audio_suffix
        title = "🎵 **Audio Metadata**"
        example = _show(settings.audio_name)
    else:
        prefix, suffix = settings.subtitle_prefix, settings.subtitle_suffix
        title = "📜 **Subtitle Metadata**"
        example = _show(settings.subtitle_name)
    return (
        f"{title}\n\n"
        "Language: **Auto-detected per track**\n"
        f"Prefix: `{_show(prefix)}`\n"
        f"Suffix: `{_show(suffix)}`\n\n"
        f"Example final title: `{example}`\n\n"
        "Your prefix/suffix are applied around the real language name in every matching track.\n"
        "Send `-` to remove a prefix or suffix."
    )

def _section_keyboard(kind: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏷 Change Prefix", callback_data=f"metaedit:{kind}:prefix")],
        [InlineKeyboardButton("🏷 Change Suffix", callback_data=f"metaedit:{kind}:suffix")],
        [
            InlineKeyboardButton("🚫 Remove Prefix", callback_data=f"metaclear:{kind}:prefix"),
            InlineKeyboardButton("🚫 Remove Suffix", callback_data=f"metaclear:{kind}:suffix"),
        ],
        [InlineKeyboardButton("🔙 Metadata", callback_data="metadata_settings")],
    ])


async def show_metadata(client: Client, chat_id: int, message: Message | None = None):
    settings = await get_metadata(int(chat_id))
    text = _text(settings)
    if message:
        await message.reply_text(text, reply_markup=metadata_keyboard())
    else:
        await client.send_message(int(chat_id), text, reply_markup=metadata_keyboard())


@Client.on_message(filters.private & filters.command(["metadata", "metasettings"]), group=-3000)
async def metadata_settings(client: Client, message: Message):
    await show_metadata(client, message.from_user.id, message)
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^metadata_settings$"), group=-3000)
async def cb_metadata_settings(client: Client, cb):
    await cb.answer()
    await edit_callback_message(cb, _text(await get_metadata(cb.from_user.id)), reply_markup=metadata_keyboard())
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^meta:(audio|subtitle)$"), group=-3000)
async def cb_metadata_section(client: Client, cb):
    kind = cb.matches[0].group(1)
    await cb.answer()
    await edit_callback_message(cb, _section_text(kind, await get_metadata(cb.from_user.id)), reply_markup=_section_keyboard(kind))
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^metaedit:(audio|subtitle):(prefix|suffix)$"), group=-3000)
async def cb_metadata_edit(client: Client, cb):
    kind = cb.matches[0].group(1)
    field = cb.matches[0].group(2)
    settings = await get_metadata(cb.from_user.id)
    if kind == "audio":
        value = {
            "prefix": settings.audio_prefix,
            "suffix": settings.audio_suffix,
        }[field]
    else:
        value = {
            "prefix": settings.subtitle_prefix,
            "suffix": settings.subtitle_suffix,
        }[field]
    await cb.answer()
    prompt = await client.send_message(
        cb.from_user.id,
        f"⌨️ **Change {kind.title()} {field.title()}**\n\n"
        f"Current: `{_show(value)}`\n\n"
        "Send the new value. Send `-` to remove the Prefix or Suffix.",
        reply_markup=ForceReply(selective=True),
    )
    await db.col.update_one(
        {"id": int(cb.from_user.id)},
        {"$set": {"metadata_prompt": {"kind": kind, "field": field, "message_id": prompt.id}}},
        upsert=True,
    )
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^metaclear:(audio|subtitle):(prefix|suffix)$"), group=-3000)
async def cb_metadata_clear(client: Client, cb):
    kind = cb.matches[0].group(1)
    field = cb.matches[0].group(2)
    settings = await update_metadata_part(cb.from_user.id, kind, field, "")
    await cb.answer(f"{field.title()} removed ✅", show_alert=True)
    await edit_callback_message(cb, _section_text(kind, settings), reply_markup=_section_keyboard(kind))
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^reset_metadata$"), group=-3000)
async def cb_reset_meta(client: Client, cb):
    settings = await reset_metadata(cb.from_user.id)
    await cb.answer("Metadata reset ✅", show_alert=True)
    await edit_callback_message(cb, _text(settings), reply_markup=metadata_keyboard())
    raise StopPropagation


@Client.on_message(filters.private & filters.text & filters.reply, group=-3000)
async def handle_meta_replies(client: Client, message: Message):
    user_id = int(message.from_user.id)
    user = await db.get_user_data(user_id) or {}
    prompt = user.get("metadata_prompt")
    reply = message.reply_to_message
    if not prompt or not reply or int(prompt.get("message_id", 0) or 0) != int(reply.id):
        return
    value = (message.text or "").strip()
    kind = str(prompt.get("kind", ""))
    field = str(prompt.get("field", ""))
    if field in {"prefix", "suffix"} and value == "-":
        value = ""

    try:
        settings = await update_metadata_part(user_id, kind, field, value)
    except Exception as exc:
        await message.reply_text(f"❌ `{str(exc)[:500]}`")
        return
    await db.col.update_one({"id": user_id}, {"$unset": {"metadata_prompt": ""}})
    await message.reply_text(_section_text(kind, settings), reply_markup=_section_keyboard(kind))
    raise StopPropagation