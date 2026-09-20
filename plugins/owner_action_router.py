
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from pyrogram import Client, StopPropagation, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from helper.database import db
from helper.job_state import jobs
from helper.plans import PLANS, Plan
from helper.utils import humanbytes
from plugins.ui import edit_callback_message


OWNER_FILTER = [int(Config.OWNER_ID)] if Config.OWNER_ID else [0]
PENDING: dict[int, dict[str, Any]] = {}


def is_owner(user_id: int | str | None) -> bool:
    if user_id is None or not Config.OWNER_ID:
        return False
    try:
        return int(user_id) == int(Config.OWNER_ID)
    except (TypeError, ValueError):
        return False


def owner_gate(client, user_id: int) -> bool:
    return bool(getattr(client, "is_main_bot", False)) and is_owner(user_id)


def clear_pending(user_id: int) -> None:
    PENDING.pop(int(user_id), None)


def set_pending(user_id: int, action: str, **data: Any) -> None:
    PENDING[int(user_id)] = {"action": action, **data}


def owner_panel_markup() -> InlineKeyboardMarkup:
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


def plans_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆓 Free", callback_data="owner:myplan:free")],
        [InlineKeyboardButton("⚡ Pro", callback_data="owner:myplan:pro")],
        [InlineKeyboardButton("💎 Premium", callback_data="owner:myplan:premium")],
        [InlineKeyboardButton("👑 Ultra", callback_data="owner:myplan:ultra")],
        [InlineKeyboardButton("🔙 Owner Panel", callback_data="owner:panel")],
    ])


def stars_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Pro", callback_data="owner:star:pro")],
        [InlineKeyboardButton("💎 Premium", callback_data="owner:star:premium")],
        [InlineKeyboardButton("👑 Ultra", callback_data="owner:star:ultra")],
        [InlineKeyboardButton("🔙 Plans", callback_data="owner:plans")],
    ])


def limits_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Pro", callback_data="owner:limit:pro")],
        [InlineKeyboardButton("💎 Premium", callback_data="owner:limit:premium")],
        [InlineKeyboardButton("👑 Ultra", callback_data="owner:limit:ultra")],
        [InlineKeyboardButton("🔙 Plans", callback_data="owner:plans")],
    ])


def set_stars(plan_key: str, stars: int) -> Plan:
    key = str(plan_key).lower()
    if key not in {"pro", "premium", "ultra"}:
        raise ValueError("Invalid plan")
    value = int(stars)
    if not 1 <= value <= 100000:
        raise ValueError("Stars must be between 1 and 100000")
    old = PLANS[key]
    plan = Plan(key=old.key, name=old.name, stars=value, daily_limit=old.daily_limit, days=old.days)
    PLANS[key] = plan
    return plan


def set_limit(plan_key: str, gb: float) -> Plan:
    key = str(plan_key).lower()
    if key not in {"pro", "premium", "ultra"}:
        raise ValueError("Invalid plan")
    value = float(gb)
    if not 0 < value <= 100000:
        raise ValueError("GB value must be greater than 0 and at most 100000")
    old = PLANS[key]
    plan = Plan(key=old.key, name=old.name, stars=old.stars, daily_limit=int(value * 1024**3), days=old.days)
    PLANS[key] = plan
    return plan


async def statistics_text(client) -> str:
    bot_id = int(getattr(client, "bot_id", 0) or 0)
    try:
        users = await db.total_users_count()
    except Exception:
        users = 0

    try:
        live_jobs = [
            job for job in await jobs.get_all_jobs()
            if int(getattr(job, "bot_id", 0) or 0) == bot_id
            and bool(getattr(job, "active", False))
        ]
    except Exception:
        live_jobs = []

    clones = 0
    try:
        async for _ in db.get_all_clones():
            clones += 1
    except Exception:
        pass

    usage = 0
    try:
        today = datetime.utcnow().date().isoformat()
        async for row in db.usage.find({"bot_id": bot_id, "date": today}, {"bytes": 1}):
            usage += int(row.get("bytes", 0) or 0)
    except Exception:
        pass

    return (
        "📊 AniToon Statistics\n\n"
        f"👥 Total Users: {users}\n"
        f"🟢 Active / Queued Jobs: {len(live_jobs)}\n"
        f"🤖 Registered Clone Bots: {clones}\n"
        f"📦 Today's Usage: {humanbytes(usage)}\n"
        f"📋 Max Active Jobs: {Config.MAX_ACTIVE_JOBS}\n"
        f"📤 Transfer Concurrency: {Config.MAX_CONCURRENT_TRANSMISSIONS}\n"
        f"🎬 FFmpeg Concurrency: {Config.MAX_CONCURRENT_PROCESSING}"
    )


def plans_text() -> str:
    lines = ["💎 AniToon Plans", ""]
    for key in ("free", "pro", "premium", "ultra"):
        plan = PLANS[key]
        duration = f"{plan.days} days" if plan.days else "No expiry"
        lines.extend([
            f"{plan.name}",
            f"⭐ Stars: {plan.stars}",
            f"📦 Daily limit: {humanbytes(plan.daily_limit)}",
            f"📅 Duration: {duration}",
            "",
        ])
    lines.extend([
        "/plans or /ownerplans — view plans",
        "/stars — open Stars editor",
        "/ownerstars <plan> <stars> — change Stars",
        "/ownerlimit <plan> <gb> — change daily limit",
    ])
    return "\n".join(lines)


def stars_text() -> str:
    return (
        "⭐ AniToon Stars\n\n"
        f"⚡ Pro: {PLANS['pro'].stars} ⭐\n"
        f"💎 Premium: {PLANS['premium'].stars} ⭐\n"
        f"👑 Ultra: {PLANS['ultra'].stars} ⭐\n\n"
        "Choose a plan to change its Stars price."
    )


def limits_text() -> str:
    return (
        "📦 AniToon Daily Limits\n\n"
        f"⚡ Pro: {humanbytes(PLANS['pro'].daily_limit)}\n"
        f"💎 Premium: {humanbytes(PLANS['premium'].daily_limit)}\n"
        f"👑 Ultra: {humanbytes(PLANS['ultra'].daily_limit)}\n\n"
        "Choose a plan to change its daily limit."
    )


async def bot_details_text(client) -> str:
    try:
        me = await client.get_me()
        bot_name = me.first_name or "-"
        username = f"@{me.username}" if me.username else "No username"
        bot_id = int(me.id)
    except Exception:
        bot_name = "Unknown"
        username = f"@{getattr(client, 'bot_username', '')}" if getattr(client, "bot_username", None) else "Unknown"
        bot_id = int(getattr(client, "bot_id", 0) or 0)

    clones: list[str] = []
    try:
        async for clone in db.get_all_clones():
            clones.append(
                f"• @{clone.get('bot_username') or 'unknown'}"
                f" — {clone.get('bot_id', '-')}"
                f" — {clone.get('status', 'unknown')}"
            )
    except Exception:
        pass

    clone_text = "\n".join(clones) if clones else "No registered clone bots."
    force_sub_count = len([x for x in Config.FORCE_SUB.split(",") if x.strip()])

    return (
        "🤖 AniToon Bot Details\n\n"
        f"📛 Name: {bot_name}\n"
        f"🔗 Username: {username}\n"
        f"🆔 Bot ID: {bot_id}\n"
        "🐍 Python: 3.11\n"
        "📚 Pyrogram: 2.0.106\n"
        f"⚙️ Workers: {Config.PYROGRAM_WORKERS}\n"
        f"📋 Max Active Jobs: {Config.MAX_ACTIVE_JOBS}\n"
        f"📤 Transfers: {Config.MAX_CONCURRENT_TRANSMISSIONS}\n"
        f"🎬 Processing: {Config.MAX_CONCURRENT_PROCESSING}\n"
        f"🤖 Clone Engine: {'ON' if Config.IS_CLONE_ALLOWED else 'OFF'}\n"
        f"🔒 Force-Sub Channels: {force_sub_count}\n\n"
        "📋 Registered Clones\n"
        f"{clone_text}"
    )


async def broadcast_message(source_message, status_message=None) -> tuple[int, int]:
    if source_message is None:
        raise ValueError("Reply to the message you want to broadcast.")

    success = 0
    failed = 0
    processed = 0

    async for user in db.get_all_users():
        user_id = user.get("id")
        if not user_id:
            continue

        try:
            await source_message.copy(chat_id=int(user_id))
            success += 1
        except FloodWait as exc:
            await asyncio.sleep(max(1, int(exc.value)))
            try:
                await source_message.copy(chat_id=int(user_id))
                success += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1

        processed += 1

        if status_message and processed % 25 == 0:
            try:
                await status_message.edit_text(
                    "📣 Broadcasting...\n\n"
                    f"✅ Sent: {success}\n"
                    f"❌ Failed: {failed}\n"
                    f"📊 Processed: {processed}"
                )
            except Exception:
                pass

        await asyncio.sleep(0.05)

    return success, failed


@Client.on_callback_query(filters.regex(r"^owner:stats$"), group=-400)
async def owner_stats_button(client, cb):
    if not owner_gate(client, cb.from_user.id):
        await cb.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    clear_pending(cb.from_user.id)
    await cb.answer("Loading...")
    await edit_callback_message(
        cb,
        await statistics_text(client),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="owner:stats")],
            [InlineKeyboardButton("🔙 Owner Panel", callback_data="owner:panel")],
        ]),
    )
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^owner:plans$"), group=-400)
async def owner_plans_button(client, cb):
    if not owner_gate(client, cb.from_user.id):
        await cb.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    clear_pending(cb.from_user.id)
    await cb.answer()
    await edit_callback_message(cb, plans_text(), reply_markup=plans_markup())
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^owner:stars$"), group=-400)
async def owner_stars_button(client, cb):
    if not owner_gate(client, cb.from_user.id):
        await cb.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    clear_pending(cb.from_user.id)
    await cb.answer()
    await edit_callback_message(cb, stars_text(), reply_markup=stars_markup())
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^owner:limits$"), group=-400)
async def owner_limits_button(client, cb):
    if not owner_gate(client, cb.from_user.id):
        await cb.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    clear_pending(cb.from_user.id)
    await cb.answer()
    await edit_callback_message(cb, limits_text(), reply_markup=limits_markup())
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^owner:plan:(pro|premium|ultra)$"), group=-400)
async def owner_plan_button(client, cb):
    if not owner_gate(client, cb.from_user.id):
        await cb.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    key = cb.matches[0].group(1)
    plan = PLANS[key]
    clear_pending(cb.from_user.id)
    await cb.answer()
    await edit_callback_message(
        cb,
        f"{plan.name}\n\n"
        f"⭐ Stars: {plan.stars}\n"
        f"📦 Daily limit: {humanbytes(plan.daily_limit)}\n"
        f"📅 Duration: {plan.days} days",
        reply_markup=plans_markup(),
    )
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^owner:star:(pro|premium|ultra)$"), group=-400)
async def owner_star_button(client, cb):
    if not owner_gate(client, cb.from_user.id):
        await cb.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    key = cb.matches[0].group(1)
    plan = PLANS[key]
    set_pending(cb.from_user.id, "stars", plan=key)
    await cb.answer()
    await edit_callback_message(
        cb,
        f"⭐ Change {plan.name} Stars\n\n"
        f"Current: {plan.stars} Stars\n\n"
        "Send only the new Stars number.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="owner:stars")]
        ]),
    )
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^owner:limit:(pro|premium|ultra)$"), group=-400)
async def owner_limit_button(client, cb):
    if not owner_gate(client, cb.from_user.id):
        await cb.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    key = cb.matches[0].group(1)
    plan = PLANS[key]
    set_pending(cb.from_user.id, "limit", plan=key)
    await cb.answer()
    await edit_callback_message(
        cb,
        f"📦 Change {plan.name} Daily Limit\n\n"
        f"Current: {humanbytes(plan.daily_limit)}\n\n"
        "Send the new limit in GB.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="owner:limits")]
        ]),
    )
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^owner:bots$"), group=-400)
async def owner_bots_button(client, cb):
    if not owner_gate(client, cb.from_user.id):
        await cb.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    clear_pending(cb.from_user.id)
    await cb.answer()
    await edit_callback_message(
        cb,
        await bot_details_text(client),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="owner:bots")],
            [InlineKeyboardButton("🔙 Owner Panel", callback_data="owner:panel")],
        ]),
    )
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^owner:broadcast$"), group=-400)
async def owner_broadcast_button(client, cb):
    if not owner_gate(client, cb.from_user.id):
        await cb.answer("Owner access only.", show_alert=True)
        raise StopPropagation

    set_pending(cb.from_user.id, "broadcast")
    await cb.answer()
    await edit_callback_message(
        cb,
        "📣 Broadcast Users\n\n"
        "Reply to the message you want to broadcast, then send any reply.\n\n"
        "This is the same operation as the /broadcast command.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="owner:panel")]
        ]),
    )
    raise StopPropagation


@Client.on_message(
    filters.private & filters.text & filters.user(OWNER_FILTER),
    group=-450,
)
async def owner_pending_text(client, message):
    if not owner_gate(client, message.from_user.id):
        return

    pending = PENDING.get(message.from_user.id)
    if not pending:
        return

    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    action = pending.get("action")

    if action == "broadcast":
        if not message.reply_to_message:
            await message.reply_text(
                "❌ Reply to the message you want to broadcast.",
                quote=True,
            )
            return

        clear_pending(message.from_user.id)
        status = await message.reply_text("📣 Broadcast Started...")
        try:
            success, failed = await broadcast_message(
                message.reply_to_message,
                status,
            )
            await status.edit_text(
                "📣 Broadcast Complete\n\n"
                f"✅ Sent: {success}\n"
                f"❌ Failed: {failed}"
            )
        except Exception as exc:
            await status.edit_text(
                "❌ Broadcast failed\n\n"
                f"{str(exc)[:1000]}"
            )
        raise StopPropagation

    if action == "stars":
        try:
            plan = set_stars(str(pending.get("plan", "")), int(text))
        except (ValueError, TypeError):
            await message.reply_text(
                "❌ Stars must be a number from 1 to 100000.",
                quote=True,
            )
            return

        clear_pending(message.from_user.id)
        await message.reply_text(
            f"✅ {plan.name} is now {plan.stars} Stars.",
            reply_markup=stars_markup(),
        )
        raise StopPropagation

    if action == "limit":
        try:
            plan = set_limit(str(pending.get("plan", "")), float(text))
        except (ValueError, TypeError):
            await message.reply_text(
                "❌ Enter a valid daily limit in GB.",
                quote=True,
            )
            return

        clear_pending(message.from_user.id)
        await message.reply_text(
            f"✅ {plan.name} daily limit is now {humanbytes(plan.daily_limit)}.",
            reply_markup=limits_markup(),
        )
        raise StopPropagation


@Client.on_message(
    filters.private
    & filters.command([
        "users", "stats", "statistics",
        "plans", "ownerplans",
        "stars",
        "ownerstars",
        "ownerlimit",
        "bots", "botdetails", "ownerbots",
        "broadcast",
    ])
    & filters.user(OWNER_FILTER),
    group=-450,
)
async def owner_management_commands(client, message):
    if not owner_gate(client, message.from_user.id):
        return

    command = (message.command[0] or "").lower()
    clear_pending(message.from_user.id)

    if command in {"users", "stats", "statistics"}:
        await message.reply_text(
            await statistics_text(client),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="owner:stats")],
                [InlineKeyboardButton("🔙 Owner Panel", callback_data="owner:panel")],
            ]),
        )
        raise StopPropagation

    if command in {"plans", "ownerplans"}:
        await message.reply_text(plans_text(), reply_markup=plans_markup())
        raise StopPropagation

    if command == "stars":
        await message.reply_text(stars_text(), reply_markup=stars_markup())
        raise StopPropagation

    if command == "ownerstars":
        if len(message.command) != 3:
            await message.reply_text("Usage: /ownerstars <pro|premium|ultra> <stars>")
            raise StopPropagation
        try:
            plan = set_stars(message.command[1], int(message.command[2]))
        except (ValueError, TypeError):
            await message.reply_text("❌ Invalid Stars value.")
            raise StopPropagation
        await message.reply_text(
            f"✅ {plan.name} is now {plan.stars} Stars.",
            reply_markup=stars_markup(),
        )
        raise StopPropagation

    if command == "ownerlimit":
        if len(message.command) != 3:
            await message.reply_text("Usage: /ownerlimit <pro|premium|ultra> <gb>")
            raise StopPropagation
        try:
            plan = set_limit(message.command[1], float(message.command[2]))
        except (ValueError, TypeError):
            await message.reply_text("❌ Invalid GB value.")
            raise StopPropagation
        await message.reply_text(
            f"✅ {plan.name} daily limit is now {humanbytes(plan.daily_limit)}.",
            reply_markup=limits_markup(),
        )
        raise StopPropagation

    if command in {"bots", "botdetails", "ownerbots"}:
        await message.reply_text(
            await bot_details_text(client),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="owner:bots")],
                [InlineKeyboardButton("🔙 Owner Panel", callback_data="owner:panel")],
            ]),
        )
        raise StopPropagation

    if command == "broadcast":
        if message.reply_to_message:
            status = await message.reply_text("📣 Broadcast Started...")
            try:
                success, failed = await broadcast_message(
                    message.reply_to_message,
                    status,
                )
                await status.edit_text(
                    "📣 Broadcast Complete\n\n"
                    f"✅ Sent: {success}\n"
                    f"❌ Failed: {failed}"
                )
            except Exception as exc:
                await status.edit_text(
                    "❌ Broadcast failed\n\n"
                    f"{str(exc)[:1000]}"
                )
        else:
            set_pending(message.from_user.id, "broadcast")
            await message.reply_text(
                "📣 Broadcast Mode\n\n"
                "Reply to the message you want to broadcast, then send any reply."
            )
        raise StopPropagation
