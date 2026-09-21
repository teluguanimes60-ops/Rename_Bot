from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from config import Config

log = logging.getLogger("AniToon.paid_media")

FREE_IMAGE_LIMIT = 20 * 1024 * 1024


def _api_url(method: str) -> str:
    token = str(Config.BOT_TOKEN or "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not configured")
    return f"https://api.telegram.org/bot{token}/{method}"


def _request(method: str, params: dict | None = None, timeout: int = 25) -> dict:
    data = urllib.parse.urlencode(params or {}).encode("utf-8")
    request = urllib.request.Request(
        _api_url(method),
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
    result = json.loads(raw)
    if not result.get("ok"):
        raise RuntimeError(result.get("description") or f"Telegram {method} failed")
    return result


async def _get_updates(offset: int | None):
    params = {
        "limit": 100,
        "timeout": 20,
        "allowed_updates": json.dumps(["message"], separators=(",", ":")),
    }
    if offset is not None:
        params["offset"] = int(offset)
    return await asyncio.to_thread(_request, "getUpdates", params, 25)


async def _send_free_photo(chat_id: int, photo_file_id: str, caption: str | None = None):
    params = {
        "chat_id": int(chat_id),
        "photo": str(photo_file_id),
    }
    if caption:
        params["caption"] = str(caption)[:1024]
    return await asyncio.to_thread(_request, "sendPhoto", params, 25)


async def _delete_source_message(chat_id: int, message_id: int):
    try:
        await asyncio.to_thread(
            _request,
            "deleteMessage",
            {"chat_id": int(chat_id), "message_id": int(message_id)},
            15,
        )
    except Exception:
        # Deletion is best-effort. The important part is the free resend.
        pass


def _paid_media_from_message(message: dict) -> dict | None:
    paid = message.get("paid_media")
    if isinstance(paid, dict):
        return paid

    # When the owner sends a forwarded/replied paid post to the bot, Telegram
    # can expose the paid media through ExternalReplyInfo.
    external = message.get("external_reply")
    if isinstance(external, dict):
        paid = external.get("paid_media")
        if isinstance(paid, dict):
            return paid

    return None


def _extract_free_photo(message: dict):
    paid = _paid_media_from_message(message)
    if not paid:
        return None

    items = paid.get("paid_media") or []
    if not isinstance(items, list):
        return None

    best = None
    best_size = 0
    best_area = 0

    for item in items:
        if not isinstance(item, dict) or item.get("type") not in {"photo", "live_photo"}:
            continue

        if item.get("type") == "photo":
            photos = item.get("photo") or []
        else:
            live = item.get("live_photo") or {}
            photos = live.get("photo") or []

        if not isinstance(photos, list):
            continue

        for photo in photos:
            if not isinstance(photo, dict) or not photo.get("file_id"):
                continue

            size = int(photo.get("file_size") or 0)
            area = int(photo.get("width") or 0) * int(photo.get("height") or 0)

            # A preview has no downloadable file_id. For a real unlocked paid
            # photo Telegram supplies PhotoSize entries with file_id.
            if size and size > FREE_IMAGE_LIMIT:
                continue

            if best is None or (size > best_size) or (size == best_size and area > best_area):
                best = photo
                best_size = size
                best_area = area

    if not best or not best.get("file_id"):
        return None

    # Only unwrap when Telegram gives us a definite <=20 MB file size.
    if best_size <= 0 or best_size > FREE_IMAGE_LIMIT:
        return None

    return str(best["file_id"]), best_size


async def handle_paid_media_update(update: dict) -> bool:
    message = update.get("message")
    if not isinstance(message, dict):
        return False

    from helper.database import db

    if not await db.get_small_images_free():
        return False

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return False

    owner = message.get("from") or {}
    owner_id = owner.get("id")
    if not Config.OWNER_ID or int(owner_id or 0) != int(Config.OWNER_ID):
        return False

    extracted = _extract_free_photo(message)
    if not extracted:
        log.info(
            "Owner paid photo not accessible as a full image or is over 20 MB; "
            "message_id=%s",
            message.get("message_id"),
        )
        return False

    file_id, size = extracted
    message_id = int(message.get("message_id") or 0)

    try:
        await _send_free_photo(
            chat_id=int(chat_id),
            photo_file_id=file_id,
            caption=message.get("caption"),
        )
        log.info(
            "Owner paid photo resent as free photo: chat_id=%s message_id=%s size=%d",
            chat_id,
            message_id,
            size,
        )
        return True
    except Exception:
        log.exception(
            "Failed to resend owner paid photo as free photo: chat_id=%s message_id=%s",
            chat_id,
            message_id,
        )
        return False


async def run_paid_media_bridge(stop_event: asyncio.Event):
    """Watch Bot API message updates for the owner-only paid-photo unwrap."""
    from helper.database import db

    offset = await db.get_paid_media_offset()
    log.info(
        "Paid-media bridge started: owner=%s limit=%dMB enabled=%s",
        Config.OWNER_ID or "-",
        FREE_IMAGE_LIMIT // (1024 * 1024),
        await db.get_small_images_free(),
    )

    while not stop_event.is_set():
        try:
            result = await _get_updates(offset)
            updates = result.get("result") or []

            for update in updates:
                update_id = int(update.get("update_id", 0))
                offset = update_id + 1
                await db.set_paid_media_offset(offset)

                try:
                    await handle_paid_media_update(update)
                except Exception:
                    log.exception(
                        "Unhandled paid-media update error: update_id=%s",
                        update_id,
                    )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            message = str(exc)
            if "Conflict" in message:
                log.error(
                    "Paid-media bridge stopped: Telegram reported a 409 Conflict. "
                    "Another Bot API getUpdates/webhook consumer is active."
                )
                return

            log.exception("Paid-media bridge polling error")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=3)
            except asyncio.TimeoutError:
                pass

    log.info("Paid-media bridge stopped.")
