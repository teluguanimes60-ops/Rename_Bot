from __future__ import annotations

from pyrogram import Client, StopPropagation, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from helper.database import db
from helper.plans import PLANS
from helper.utils import humanbytes
from plugins.owner_action_router import owner_gate, clear_pending
from plugins.ui import edit_callback_message


def _owner_plans_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🆓 Free', callback_data='owner:myplan:free')],
        [InlineKeyboardButton('⚡ Pro', callback_data='owner:myplan:pro')],
        [InlineKeyboardButton('💎 Premium', callback_data='owner:myplan:premium')],
        [InlineKeyboardButton('👑 Ultra', callback_data='owner:myplan:ultra')],
        [InlineKeyboardButton('🔙 Owner Panel', callback_data='owner:panel')],
    ])


async def _owner_plans_text(client, user_id: int):
    bot_id = int(getattr(client, 'bot_id', 0) or 0)
    subscription = await db.get_subscription(int(user_id), bot_id)
    current = PLANS.get(subscription.get('plan', 'free'), PLANS['free'])
    duration = 'No expiry' if not current.days else f'{current.days} days'
    return (
        '💎 **AniToon Plans**\n\n'
        f'👤 **Your current plan:** {current.name}\n'
        f'📦 **Daily limit:** `{humanbytes(current.daily_limit)}`\n'
'
        f'📅 **Duration:** `{duration}`\n\n'
        'Choose Free, Pro, Premium, or Ultra to switch your owner account plan without Stars.'
    )


@Client.on_callback_query(filters.regex(r'^owner:plans$'), group=-500)
async def owner_plans_override(client, cb):
    if not owner_gate(client, cb.from_user.id):
        await cb.answer('Owner access only.', show_alert=True)
        raise StopPropagation
    clear_pending(cb.from_user.id)
    await cb.answer()
    await edit_callback_message(cb, await _owner_plans_text(client, cb.from_user.id), reply_markup=_owner_plans_markup())
    raise StopPropagation


@Client.on_callback_query(filters.regex(r'^owner:myplan:(free|pro|premium|ultra)$'), group=-500)
async def owner_set_plan(client, cb):
    if not owner_gate(client, cb.from_user.id):
        await cb.answer('Owner access only.', show_alert=True)
        raise StopPropagation
    key = cb.matches[0].group(1)
    await db.set_plan(
        user_id=int(cb.from_user.id),
        bot_id=int(getattr(client, 'bot_id', 0) or 0),
        plan_key=key,
        stars_paid=0,
        payment_id='owner_manual',
    )
    clear_pending(cb.from_user.id)
    await cb.answer(f'Your plan changed to {PLANS[key].name}.', show_alert=True)
    await edit_callback_message(cb, await _owner_plans_text(client, cb.from_user.id), reply_markup=_owner_plans_markup())
    raise StopPropagation