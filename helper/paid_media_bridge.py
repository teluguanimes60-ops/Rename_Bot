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
        # Telegram may reject deletion of an incoming user message. The free
        # copy is already delivered, so deletion failure is non-fatal.
        pass


def _extract_paid_photo(message: dict):
    paid = message.get("paid_media")
    if not isinstance(paid, dict):
        return None

    items = paid.get("paid_media") or []
    if not isinstance(items, list):
        return None

    best = None
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "photo":
            continue
        photos = item.get("photo") or []
        if not isinstance(photos, list):
            continue
        for photo in photos:
            if not isinstance(photo, dict) or not photo.get("file_id"):
                continue
            size = int(photo.get("file_size") or 0)
            if size and size > FREE_IMAGE_LIMIT:
                continue
            if best is None:
                best = photo
            else:
                best_size = int(best.get("file_size") or 0)
                best_area = int(best.get("width") or 0) * int(best.get("height") or 0)
                area = int(photo.get("width") or 0) * int(photo.get("height") or 0)
                if size > best_size or (not size and area > best_area):
                    best = photo

    if not best:
        return None

    size = int(best.get("file_size") or 0)
    # Only auto-free when Telegram tells us the actual photo size and it is
    # definitely within the owner's 20 MB limit.
    if not size or size > FREE_IMAGE_LIMIT:
        return None
    return str(best["file_id"]), size


async def handle_paid_media_update(update: dict) -> bool:
    message = update.get("message")
    if not isinstance(message, dict):
        return False

    paid = message.get("paid_media")
    if not isinstance(paid, dict):
        return False

    from helper.database import db

    if not await db.get_small_images_free():
        return False

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return False

    extracted = _extract_paid_photo(message)
    if not extracted:
        log.info(
            "Paid media received but no accessible photo <=20 MB was available; "
            "message_id=%s chat_id=%s",
            message.get("message_id"),
            chat_id,
        )
        return False

    file_id, size = extracted
    try:
        await _send_free_photo(
            chat_id=int(chat_id),
            photo_file_id=file_id,
            caption=message.get("caption"),
        )
        await _delete_source_message(
            chat_id=int(chat_id),
            message_id=int(message.get("message_id") or 0),
        )
        log.info(
            "Paid photo unwrapped successfully: chat_id=%s message_id=%s size=%d",
            chat_id,
            message.get("message_id"),
            size,
        )
        return True
    except Exception:
        log.exception(
            "Failed to resend paid photo as free photo: chat_id=%s message_id=%s",
            chat_id,
            message.get("message_id"),
        )
        return False


async def run_paid_media_bridge(stop_event: asyncio.Event):
    """Poll the Bot API for paid-media messages and unwrap eligible photos."""
    offset = None
    log.info("Paid-media bridge started (20 MB owner setting).")

    while not stop_event.is_set():
        try:
            result = await _get_updates(offset)
            updates = result.get("result") or []

            for update in updates:
                update_id = int(update.get("update_id", 0))
                offset = update_id + 1
                try:
                    await handle_paid_media_update(update)
                except Exception:
                    log.exception("Unhandled paid-media update error: update_id=%s", update_id)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            message = str(exc)
            if "Conflict" in message:
                log.error(
                    "Paid-media bridge stopped by Telegram 409 Conflict. "
                    "Another Bot API getUpdates/webhook consumer is active."
                )
                return
            log.exception("Paid-media bridge polling error")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=3)
            except asyncio.TimeoutError:
                pass

    log.info("Paid-media bridge stopped.")
