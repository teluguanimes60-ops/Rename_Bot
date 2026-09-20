from __future__ import annotations

import logging
from datetime import datetime, timedelta

from helper.database import db

log = logging.getLogger("AniToon.activity")
_ACTIVITY_INDEX_READY = False


async def ensure_activity_indexes():
    global _ACTIVITY_INDEX_READY
    if _ACTIVITY_INDEX_READY:
        return True
    try:
        await db.db.file_activity.create_index(
            "completed_at",
            expireAfterSeconds=7 * 24 * 60 * 60,
            sparse=True,
            name="rename_activity_completed_ttl",
        )
        _ACTIVITY_INDEX_READY = True
        log.info("Rename activity indexes ready")
        return True
    except Exception:
        # Retry on the next call instead of permanently marking the index as ready.
        log.exception("Could not create rename activity TTL index")
        return False


async def purge_old_rename_activity():
    await ensure_activity_indexes()
    cutoff = datetime.utcnow() - timedelta(days=7)
    try:
        result = await db.db.file_activity.delete_many({
            "$or": [
                {"completed_at": {"$lt": cutoff}},
                {"status": "requested", "created_at": {"$lt": cutoff}},
            ]
        })
        deleted = int(getattr(result, "deleted_count", 0) or 0)
        if deleted:
            log.info("Purged %s old rename activity records", deleted)
        return deleted
    except Exception:
        log.exception("Could not purge old rename activity")
        return 0


async def log_rename_request(
    *,
    bot_id: int,
    job_id: str,
    user_id: int,
    user_name: str,
    username: str | None,
    original_name: str,
    new_name: str,
    file_size: int,
    output_format: str | None = None,
):
    """Record a rename request without ever breaking the actual file job."""
    await ensure_activity_indexes()
    await purge_old_rename_activity()
    now = datetime.utcnow()
    try:
        await db.db.file_activity.update_one(
            {"job_id": str(job_id)},
            {"$set": {
                "job_id": str(job_id),
                "bot_id": int(bot_id),
                "user_id": int(user_id),
                "user_name": str(user_name or "Unknown"),
                "username": str(username or "").lstrip("@"),
                "original_name": str(original_name),
                "new_name": str(new_name),
                "file_size": int(file_size or 0),
                "output_format": str(output_format or ""),
                "status": "requested",
                "created_at": now,
            }},
            upsert=True,
        )
        log.info(
            "Rename requested job=%s user=%s format=%s size=%s",
            job_id, user_id, output_format or "-", file_size,
        )
        return True
    except Exception:
        # Activity logging must never stop a rename/conversion job.
        log.exception("Could not write rename activity job=%s", job_id)
        return False


async def mark_rename_completed(job_id: str):
    await ensure_activity_indexes()
    try:
        result = await db.db.file_activity.update_one(
            {"job_id": str(job_id)},
            {"$set": {
                "status": "completed",
                "completed_at": datetime.utcnow(),
            }},
        )
        if int(getattr(result, "matched_count", 0) or 0):
            log.info("Rename completed job=%s", job_id)
        else:
            log.warning("Rename completion record missing job=%s", job_id)
        return bool(getattr(result, "matched_count", 0))
    except Exception:
        log.exception("Could not mark rename activity completed job=%s", job_id)
        return False


async def rename_activity_for_day(*, bot_id: int, day) -> list[dict]:
    """Return completed rename activity for one UTC calendar day."""
    await ensure_activity_indexes()
    await purge_old_rename_activity()
    day = str(day)
    start = datetime.strptime(day, "%Y-%m-%d")
    end = start + timedelta(days=1)
    cursor = (
        db.db.file_activity.find(
            {
                "bot_id": int(bot_id),
                "status": "completed",
                "completed_at": {"$gte": start, "$lt": end},
            }
        )
        .sort("completed_at", 1)
    )
    return [item async for item in cursor]


async def recent_rename_activity(*, bot_id: int, hours: int = 24, limit: int = 100):
    await purge_old_rename_activity()
    since = datetime.utcnow() - timedelta(hours=max(1, int(hours)))
    cursor = db.db.file_activity.find(
        {"bot_id": int(bot_id), "created_at": {"$gte": since}}
    ).sort("created_at", -1).limit(max(1, int(limit)))
    return [item async for item in cursor]
