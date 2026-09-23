from __future__ import annotations


from pyrogram import Client, StopPropagation, filters
from pyrogram.types import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from helper.database import db
from plugins.owner_action_router import is_owner as owner_user


def _owner_gate(client, user_id: int) -> bool:
    return bool(getattr(client, "is_main_bot", False)) and owner_user(user_id)


async def _bot_id(client) -> int:
    bot_id = int(getattr(client, "bot_id", 0) or 0)
    if bot_id <= 0:
        try:
            bot_id = int((await client.get_me()).id)
            client.bot_id = bot_id
        except Exception:
            bot_id = 0
    return bot_id


def _request_buttons(request_id: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ Reply to User", callback_data=f"owner:support:reply:{request_id}")],
        [InlineKeyboardButton("✅ Close Request", callback_data=f"owner:support:close:{request_id}")],
        [InlineKeyboardButton("🔙 All Help Requests", callback_data="owner:support")],
    ])


def _request_text(request: dict) -> str:
    username = "@{}".format(request.get("username")) if request.get("username") else "No username"
    return (
        f"📨 **User Help Request #{request.get('request_id', '-')}**\\n\\n"
        f"👤 **User:** {request.get('user_name') or 'Unknown'}\\n"
        f"🔗 **Username:** {username}\n"
        f"🆔 **User ID:** `{request.get('user_id', '-')}`\\n"
        f"🤖 **Bot ID:** `{request.get('bot_id', '-')}`\\n\\n"
        "💬 **Problem:**\n"
        f"{request.get('message') or '(empty)'}"
    )


async def _send_owner_notification(client, request: dict):
    owner_id = int(Config.OWNER_ID or 0)
    if owner_id <= 0:
        return
    try:
        await client.send_message(
            owner_id,
            _request_text(request),
            reply_markup=_request_buttons(request["request_id"]),
        )
    except Exception:
        pass


@Client.on_callback_query(filters.regex(r"^owner_help$"), group=-4500)
async def owner_help_button(client, callback_query):
    await callback_query.answer()
    prompt = await callback_query.message.reply_text(
        "👤 **Contact Owner**\n\n"
        "Tell the owner about your problem, error, payment issue, or any question about AniToon.\n\n"
        "📝 Send your complete message now.",
        reply_markup=ForceReply(selective=True),
    )
    await db.support_requests.update_one(
        {"user_id": int(callback_query.from_user.id), "status": "awaiting_user"},
        {"$set": {
            "prompt_message_id": int(prompt.id),
            "bot_id": await _bot_id(client),
            "updated_at": __import__("datetime").datetime.utcnow(),
        }, "$setOnInsert": {"user_id": int(callback_query.from_user.id)}},
        upsert=True,
    )
    raise StopPropagation


@Client.on_message(filters.private & filters.text & ~filters.command(["start", "help", "support", "paysupport"]), group=-4400)
async def receive_user_support(client, message: Message):
    if not message.from_user:
        return
    reply = message.reply_to_message
    if not reply:
        return
    user_id = int(message.from_user.id)
    bot_id = await _bot_id(client)
    pending = await db.support_requests.find_one({
        "user_id": user_id,
        "bot_id": bot_id,
        "status": "awaiting_user",
        "prompt_message_id": int(reply.id),
    })
    if pending:
        text = (message.text or "").strip()
        if not text:
            return
        await db.support_requests.delete_many({"user_id": user_id, "bot_id": bot_id, "status": "awaiting_user"})
        request_id = await db.create_support_request(
            user_id=user_id,
            bot_id=bot_id,
            user_text=text,
            user_name=message.from_user.first_name or "",
            username=message.from_user.username,
            prompt_message_id=reply.id,
        )
        request = await db.get_support_request(request_id)
        await message.reply_text(
            f"✅ **Help request sent to the owner.**\n\nRequest ID: `{request_id}`\n\n"
            "The owner can reply to you directly through this bot.",
        )
        await _send_owner_notification(client, request)
        raise StopPropagation

    # Continue an existing support conversation when the user replies to the
    # bot message that contained the owner's latest response.
    existing = await db.support_requests.find_one({
        "user_id": user_id,
        "status": "open",
        "last_bot_message_id": int(reply.id),
    })
    if not existing:
        return
    text = (message.text or "").strip()
    if not text:
        return
    await db.support_requests.update_one(
        {"request_id": existing["request_id"]},
        {"$set": {
            "user_last_reply": text[:4000],
            "user_replied_at": __import__("datetime").datetime.utcnow(),
            "updated_at": __import__("datetime").datetime.utcnow(),
        }},
    )
    owner_id = int(Config.OWNER_ID or 0)
    if owner_id > 0:
        await client.send_message(
            owner_id,
            f"💬 **New reply from User #{existing['request_id']}**\\n\\n{text[:4000]}",
            reply_markup=_request_buttons(existing["request_id"]),
        )
    await message.reply_text("✅ **Your message was sent to the owner.**")
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^owner:support$"), group=-400)
async def owner_support_list(client, callback_query):
    if not _owner_gate(client, callback_query.from_user.id):
        await callback_query.answer("Owner access only.", show_alert=True)
        raise StopPropagation
    await callback_query.answer()
    requests = await db.list_support_requests(limit=10)
    if not requests:
        await callback_query.message.edit_text(
            "📨 **User Help Requests**\n\n✅ No open help requests.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="owner:support")],
                [InlineKeyboardButton("🔙 Owner Panel", callback_data="owner:panel")],
            ]),
        )
        raise StopPropagation
    rows = []
    for item in requests:
        label = str(item.get("user_name") or item.get("username") or item.get("user_id") or "User")
        problem = " ".join(str(item.get("message") or "").split())[:45]
        rows.append([InlineKeyboardButton(f"📨 {label}: {problem}", callback_data=f"owner:support:view:{item['request_id']}")])
    rows.append([InlineKeyboardButton("🔄 Refresh", callback_data="owner:support")])
    rows.append([InlineKeyboardButton("🔙 Owner Panel", callback_data="owner:panel")])
    await callback_query.message.edit_text("📨 **User Help Requests**\n\nSelect a request:", reply_markup=InlineKeyboardMarkup(rows))
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^owner:support:view:([0-9a-f]+)$"), group=-400)
async def owner_support_view(client, callback_query):
    if not _owner_gate(client, callback_query.from_user.id):
        await callback_query.answer("Owner access only.", show_alert=True)
        raise StopPropagation
    request_id = callback_query.matches[0].group(1)
    request = await db.get_support_request(request_id)
    await callback_query.answer()
    if not request or request.get("status") != "open":
        await callback_query.message.edit_text("❌ **This help request is no longer open.**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 All Help Requests", callback_data="owner:support")]]))
        raise StopPropagation
    await callback_query.message.edit_text(_request_text(request), reply_markup=_request_buttons(request_id))
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^owner:support:reply:([0-9a-f]+)$"), group=-400)
async def owner_support_reply_button(client, callback_query):
    if not _owner_gate(client, callback_query.from_user.id):
        await callback_query.answer("Owner access only.", show_alert=True)
        raise StopPropagation
    request_id = callback_query.matches[0].group(1)
    request = await db.get_support_request(request_id)
    if not request or request.get("status") != "open":
        await callback_query.answer("Request closed or not found.", show_alert=True)
        raise StopPropagation
    await callback_query.answer()
    prompt = await callback_query.message.reply_text(
        f"↩️ **Reply to User #{request_id}**\n\nSend your message now.",
        reply_markup=ForceReply(selective=True),
    )
    await db.support_requests.update_one(
        {"request_id": request_id},
        {"$set": {"owner_prompt_message_id": int(prompt.id), "updated_at": __import__("datetime").datetime.utcnow()}},
    )
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^owner:support:close:([0-9a-f]+)$"), group=-400)
async def owner_support_close(client, callback_query):
    if not _owner_gate(client, callback_query.from_user.id):
        await callback_query.answer("Owner access only.", show_alert=True)
        raise StopPropagation
    request_id = callback_query.matches[0].group(1)
    await db.close_support_request(request_id)
    await callback_query.answer("Closed")
    await callback_query.message.edit_text("✅ **Help request closed.**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 All Help Requests", callback_data="owner:support")]]))
    raise StopPropagation


@Client.on_message(filters.private & filters.text & filters.user([int(Config.OWNER_ID)] if Config.OWNER_ID else [0]), group=-4300)
async def receive_owner_support_reply(client, message: Message):
    if not _owner_gate(client, message.from_user.id):
        return
    reply = message.reply_to_message
    if not reply:
        return
    request = await db.support_requests.find_one({
        "request_id": {"$exists": True},
        "status": "open",
        "owner_prompt_message_id": int(reply.id),
    })
    if not request:
        return
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return
    user_id = int(request["user_id"])
    try:
        sent = await client.send_message(
            user_id,
            f"👤 **Owner Reply — Request #{request['request_id']}**\\n\\n{text[:4000]}\\n\\n↩️ Reply to this message to continue the conversation.",
            reply_markup=ForceReply(selective=True),
        )
    except Exception as exc:
        await message.reply_text(f"❌ Could not message the user.\n\n`{str(exc)[:700]}`")
        return
    await db.save_support_reply(request["request_id"], text, sent.id)
    await message.reply_text(f"✅ **Reply sent to User #{request['request_id']}.**")
    raise StopPropagation


@Client.on_message(filters.private & filters.command(["support", "paysupport"]), group=-4200)
async def support_commands(client, message: Message):
    await message.reply_text(
        "👤 **AniToon Support**\n\n"
        "Use the Help → Owner Help button to contact the owner about bot problems, payment issues, or questions.",
    )
    raise StopPropagation
