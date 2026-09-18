from __future__ import annotations

from config import Config


def is_owner(user_id: int | str | None) -> bool:
    """
    Return True only when the supplied Telegram user ID
    matches the configured OWNER_ID.
    """

    if user_id is None:
        return False

    if not Config.OWNER_ID:
        return False

    try:
        return int(user_id) == int(Config.OWNER_ID)
    except (TypeError, ValueError):
        return False


def is_admin(user_id: int | str | None) -> bool:
    """
    Backward-compatible alias.

    Old code calling is_admin() now means OWNER ONLY.
    There is no separate admin role.
    """
    return is_owner(user_id)
