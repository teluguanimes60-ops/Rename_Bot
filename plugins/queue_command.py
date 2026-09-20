from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message

from config import Config
from helper.job_state import jobs
from helper.utils import humanbytes


def _is_owner(user_id: int) -> bool:
    return int(user_id) == int(Config.OWNER_ID)


def _status(job) -> str:
    if not getattr(job, "active", True):
        return "⏸️ Paused"
    extra = getattr(job, "extra", {}) or {}
    if extra.get("processing"):
        return "⚙️ Processing"
    action = getattr(job, "selected_action", None)
    if action:
        return f"⏳ Waiting: {action}"
    return "⏳ Waiting for action"


def _job_size(job) -> int:
    extra = getattr(job, "extra", {}) or {}
    return int(extra.get("telegram_file_size", 0) or 0)


def _job_sort_key(job):
    return getattr(job, "queued_at", 0) or 0


def _format_job(index: int, job, include_identity: bool = False) -> list[str]:
    name = getattr(job, "original_name", None) or "Unknown"
    size = humanbytes(_job_size(job))
    status = _status(job)
    action = getattr(job, "selected_action", None) or "Not selected"
    output_ext = getattr(job, "output_ext", None) or "-"
    lines = [
        f"**#{index}** {status}",
        f"📄 `{name}`",
        f"📦 `{size}`",
        f"🔧 Action: `{action}`",
        f"🎯 Output: `{output_ext}`",
    ]
    if include_identity:
        lines.extend([
            f"👤 User: `{getattr(job, 'user_id', 0)}`",
            f"🤖 Bot: `{getattr(job, 'bot_id', 0)}`",
            f"🆔 Job: `{getattr(job, 'job_id', '-')}`",
        ])
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return lines


