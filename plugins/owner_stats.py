from __future__ import annotations

from datetime import datetime, timedelta

from pyrogram import Client, StopPropagation, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from helper.activity_log import purge_old_rename_activity, rename_activity_for_day
from helper.utils import humanbytes
from plugins.owner_action_router import owner_gate, clear_pending
from plugins.ui import edit_callback_message

_DETAIL_MESSAGES: dict[int, list[int]] = {}

def _window():
    today = datetime.utcnow().date()
    return today - timedelta(days=6), today

async def _clear_details(client, owner_id: int):
    for message_id in _DETAIL_MESSAGES.pop(int(owner_id), []):
        try:
            await client.delete_messages(int(owner_id), int(message_id))
        except Exception:
            pass

def _stats_markup(day: str, oldest: str, today: str) -> InlineKeyboardMarkup:
    rows = []
    if day > oldest:
        rows.append([InlineKeyboardButton('⬅️ Previous Day', callback_data=f'owner:stats:prev:{day}')])
    if day < today:
        rows.append([InlineKeyboardButton('➡️ Next Day', callback_data=f'owner:stats:next:{day}')])
    rows.append([InlineKeyboardButton('📅 Today', callback_data='owner:stats')])
    rows.append([InlineKeyboardButton('🔙 Owner Panel', callback_data='owner:panel')])
    return InlineKeyboardMarkup(rows)

async def _render_day(client, day: str):
    await purge_old_rename_activity()
    oldest_date, today_date = _window()
    oldest, today = oldest_date.isoformat(), today_date.isoformat()
    day = max(oldest, min(today, str(day)))
    bot_id = int(getattr(client, 'bot_id', 0) or 0)
    from helper.activity_log import rename_activity_for_day
    activities = await rename_activity_for_day(bot_id=bot_id, day=day)
    unique_users = len({int(item.get('user_id', 0) or 0) for item in activities})
    total_size = sum(int(item.get('file_size', 0) or 0) for item in activities)
    label = datetime.strptime(day, '%Y-%m-%d').strftime('%d %b %Y')
    summary = (
        '📊 **AniToon Statistics**\n\n'
        f'📅 **Date:** `{label}` (UTC)\n'
        f'👥 **Users who used the bot:** `{unique_users}`\n'
        f'📂 **Files completed:** `{len(activities)}`\n'
        f'📦 **Total processed:** `{humanbytes(total_size)}`\n\n'
        'The detailed file history is shown below.'
    )
    chunks = []
    current = ''
    for index, item in enumerate(activities, 1):
        user_name = str(item.get('user_name') or 'Unknown').strip()
        username = str(item.get('username') or '').strip()
        user_label = f'{user_name} (@{username})' if username else user_name
        created_at = item.get('created_at')
        completed_at = item.get('completed_at')
        start_text = created_at.strftime('%H:%M:%S') if hasattr(created_at, 'strftime') else '--:--:--'
        finish_text = completed_at.strftime('%H:%M:%S') if hasattr(completed_at, 'strftime') else '--:--:--'
        before_name = str(item.get('original_name') or '-').replace('`', "'")
        after_name = str(item.get('new_name') or '-').replace('`', "'")
        entry = (
            f'**#{index}** 👤 `{user_label}`\n'
            f'🕐 Start: `{start_text}`  →  ✅ Finish: `{finish_text}`\n'
            f'📥 Before: `{before_name}`\n'
            f'📤 After: `{after_name}`\n\n'
        )
        if current and len(current) + len(entry) > 3300:
            chunks.append(current)
            current = ''
        current += entry
    if current:
        chunks.append(current)
    return summary, chunks, day, oldest, today

async def _show_day(client, cb, day: str):
    await _clear_details(client, cb.from_user.id)
    summary, chunks, day, oldest, today = await _render_day(client, day)
    await edit_callback_message(cb, summary, reply_markup=_stats_markup(day, oldest, today))
    ids = []
    for chunk in chunks:
        try:
            sent = await client.send_message(cb.from_user.id, chunk)
            ids.append(sent.id)
        except Exception:
            pass
    _DETAIL_MESSAGES[int(cb.from_user.id)] = ids

@Client.on_callback_query(filters.regex(r'^owner:stats$'), group=-500)
async def owner_stats(client, cb):
    if not owner_gate(client, cb.from_user.id):
        await cb.answer('Owner access only.', show_alert=True)
        raise StopPropagation
    clear_pending(cb.from_user.id)
    await cb.answer('Loading...')
    await _show_day(client, cb, datetime.utcnow().date().isoformat())
    raise StopPropagation

@Client.on_callback_query(filters.regex(r'^owner:stats:(prev|next):(\d{4}-\d{2}-\d{2})$'), group=-500)
async def owner_stats_navigation(client, cb):
    if not owner_gate(client, cb.from_user.id):
        await cb.answer('Owner access only.', show_alert=True)
        raise StopPropagation
    direction = cb.matches[0].group(1)
    current = datetime.strptime(cb.matches[0].group(2), '%Y-%m-%d').date()
    target = current + timedelta(days=1 if direction == 'next' else -1)
    oldest, today = _window()
    target = max(oldest, min(today, target))
    await cb.answer()
    await _show_day(client, cb, target.isoformat())
    raise StopPropagation