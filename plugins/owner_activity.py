from __future__ import annotations

from datetime import datetime

from pyrogram import Client, filters

from config import Config
from helper.activity_log import log_rename_request, recent_rename_activity
from helper.admin_access import is_owner
from helper.job_state import jobs
from helper.utils import humanbytes


def _owner_filter():
    return filters.user(int(Config.OWNER_ID)) if Config.OWNER_ID else filters.user(0)


def _display_user(name: str, username: str | None, user_id: int) -> str:
    name = (name or "Unknown").replace("`", "'")
    tag = f"@{username}" if username else "no username"
    return f"{name} ({tag}) — `{user_id}`"


def _job_status(job) -> str:
    return f"`{job.selected_action or 'waiting for action'}`"


@Client.on_message(filters.private & filters.text & filters.reply, group=-1300)
async def capture_owner_rename_activity(client, message):
    """Persist rename requests before the normal rename handler consumes them."""
    try:
        job = await jobs.get_user_job(message.from_user.id)
        if not job or job.selected_action not in {"custom_name", "convert_name"}:
            return
        reply_id = getattr(message.reply_to_message, "id", None)
        prompt_id = int((job.extra or {}).get("rename_prompt_message_id", 0) or 0)
        if prompt_id and reply_id and int(reply_id) != prompt_id:
            return
        text = (message.text or "").strip()
        if not text:
            return
        ext = job.output_ext or ""
        new_name = text
        if ext and not new_name.lower().endswith("." + ext.lower()):
            new_name = f"{new_name.rsplit('.', 1)[0] if '.' in new_name else new_name}.{ext}"
        user = message.from_user
        full_name = " ".join(x for x in [user.first_name, user.last_name] if x).strip() or "Unknown"
        await log_rename_request(bot_id=int(getattr(client, "bot_id", 0)), job_id=job.job_id, user_id=int(user.id), user_name=full_name, username=user.username, original_name=job.original_name, new_name=new_name, file_size=int((job.extra or {}).get("telegram_file_size", 0) or 0), output_format=ext or job.mime_type or "")
    except Exception:
        return

