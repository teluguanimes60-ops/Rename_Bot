"""Reliable entry point for the Home -> Rename button."""

from __future__ import annotations

from pyrogram import Client, StopPropagation, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from helper.job_state import jobs
from plugins.ui import edit_callback_message, file_action_menu


def _force_sub_configured() -> bool:
    """Only run the force-sub gate when the owner actually configured it."""
    return bool(
        str(getattr(Config, "FORCE_SUB", "") or "").strip()
        or str(getattr(Config, "FORCE_SUB_LINKS", "") or "").strip()
    )


@Client.on_callback_query(filters.regex(r"^start_rename$"), group=-9000)
async def start_rename(client, callback_query):
    """Open Rename reliably and preserve an already-created file job."""
    user = callback_query.from_user
    if user is None:
        return await callback_query.answer()

    # A callback must be acknowledged immediately so Telegram does not show
    # the button as stuck/loading while membership checks run.
    await callback_query.answer()

    if _force_sub_configured():
        try:
            from plugins.start import (
                FORCE_SUB_CHANNELS,
                get_force_sub_status,
                make_force_sub_text,
                make_force_sub_keyboard,
            )

            joined_count, missing, failed = await get_force_sub_status(
                client,
                user.id,
            )

            if missing or failed or joined_count != len(FORCE_SUB_CHANNELS):
                text = make_force_sub_text(
                    joined_count,
                    len(missing),
                    len(failed),
                )
                await edit_callback_message(
                    callback_query,
                    text,
                    reply_markup=make_force_sub_keyboard(missing, failed),
                )
                raise StopPropagation
        except StopPropagation:
            raise
        except Exception:
            # Do not leave the user with an apparently dead Rename button.
            await edit_callback_message(
                callback_query,
                "⚠️ **Channel verification failed.**\n\n"
                "Please try again, or send your file and use the Rename button "
                "from the file action menu.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Home", callback_data="start")]]
                ),
            )
            raise StopPropagation

    # If a file is already registered, take the user straight to its actions.
    try:
        job = await jobs.get_user_job(int(user.id))
    except Exception:
        job = None

    if job is not None:
        await edit_callback_message(
            callback_query,
            "✅ **Your file is ready. Choose an action:**",
            reply_markup=file_action_menu(job.job_id),
        )
        raise StopPropagation

    await edit_callback_message(
        callback_query,
        "✏️ **Rename File**\n\n"
        "📤 Send me a video, document, or audio file.\n\n"
        "After the file is received, tap **✏️ Rename** and enter the new filename.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Home", callback_data="start")]]
        ),
    )
    raise StopPropagation
