from __future__ import annotations

from helper.database import db
from helper.plans import get_plan


FEATURE_LABELS = {
    "media_info": "ℹ️ Media Info",
    "extract_audio": "🎵 Extract All Audio",
    "extract_subtitle": "💬 Extract All Subtitle",
    "add_audio": "➕ Add Audio",
    "add_subtitle": "➕ Add Subtitle",
    "trim": "✂️ Trim Video",
}


def feature_label(feature: str) -> str:
    return FEATURE_LABELS.get(str(feature), str(feature).replace("_", " ").title())


def plan_advanced_limit(plan_key: str) -> int:
    """
    Advanced options use a per-feature daily limit:
    Free = 1, 10-Star = 10, 20-Star = 20, 30-Star = 30.
    """
    plan = get_plan(plan_key)
    return max(1, int(plan.stars or 0))


async def advanced_quota_status(user_id: int, bot_id: int, feature: str) -> tuple[int, int, str]:
    """Return today's usage, limit, and plan name without consuming a use."""
    subscription = await db.get_subscription(int(user_id), int(bot_id))
    plan = get_plan(subscription.get("plan", "free"))
    limit = plan_advanced_limit(plan.key)
    used = await db.get_advanced_usage(int(user_id), int(bot_id), str(feature))
    return int(used), int(limit), str(plan.name)


async def consume_advanced_use(user_id: int, bot_id: int, feature: str) -> tuple[bool, int, int]:
    """Atomically consume one daily use for one advanced feature."""
    subscription = await db.get_subscription(int(user_id), int(bot_id))
    plan = get_plan(subscription.get("plan", "free"))
    limit = plan_advanced_limit(plan.key)
    used = await db.consume_advanced_usage(int(user_id), int(bot_id), str(feature), limit)
    return bool(used), int(used), int(limit)
