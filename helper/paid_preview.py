from __future__ import annotations

import asyncio
from typing import Any

from pyrogram import raw as pyrogram_raw

from config import Config

try:
    from telethon import TelegramClient, types as tele_types, utils as tele_utils
    from telethon.sessions import MemorySession
except ImportError:
    TelegramClient = None
    tele_types = None
    tele_utils = None
    MemorySession = None


_client = None
_client_lock = asyncio.Lock()


async def _get_telethon_client():
    global _client

    if TelegramClient is None:
        return None

    if _client is not None and _client.is_connected():
        return _client

    async with _client_lock:
        if _client is not None and _client.is_connected():
            return _client

        if not Config.API_ID or not Config.API_HASH or not Config.BOT_TOKEN:
            return None

        client = TelegramClient(
            MemorySession(),
            int(Config.API_ID),
            str(Config.API_HASH),
            receive_updates=False,
            flood_sleep_threshold=60,
        )
        await client.start(bot_token=str(Config.BOT_TOKEN))
        _client = client
        return _client


async def _telethon_entity(pyrogram_client, chat_id: int):
    peer = await pyrogram_client.resolve_peer(int(chat_id))

    if isinstance(peer, pyrogram_raw.types.InputPeerUser):
        return tele_types.InputPeerUser(
            user_id=int(peer.user_id),
            access_hash=int(peer.access_hash),
        )

    if isinstance(peer, pyrogram_raw.types.InputPeerChat):
        return tele_types.InputPeerChat(chat_id=int(peer.chat_id))

    if isinstance(peer, pyrogram_raw.types.InputPeerChannel):
        return tele_types.InputPeerChannel(
            channel_id=int(peer.channel_id),
            access_hash=int(peer.access_hash),
        )

    return None


def _cached_thumbnail_bytes(thumb: Any) -> bytes | None:
    if thumb is None:
        return None

    # Avoid depending on generated constructor attributes so this keeps
    # working across Telethon layer updates.
    name = type(thumb).__name__
    data = getattr(thumb, "bytes", None)
    if not isinstance(data, (bytes, bytearray)) or not data:
        return None

    if name == "PhotoStrippedSize":
        return tele_utils.stripped_photo_to_jpg(bytes(data))

    if name == "PhotoCachedSize":
        return bytes(data)

    return None


async def get_paid_preview_bytes(pyrogram_client, chat_id: int, message_id: int) -> bytes | None:
    """Fetch the same locked paid message through a read-only MTProto session.

    This reads Telegram's free preview only. It never invokes a purchase or
    paid-media unlock request.
    """
    client = await _get_telethon_client()
    if client is None:
        return None

    entity = await _telethon_entity(
        pyrogram_client,
        int(chat_id),
    )
    if entity is None:
        return None

    telegram_message = await client.get_messages(
        entity,
        ids=int(message_id),
    )
    if telegram_message is None:
        return None

    media = getattr(telegram_message, "media", None)
    if type(media).__name__ != "MessageMediaPaidMedia":
        return None

    for extended in getattr(media, "extended_media", None) or []:
        if type(extended).__name__ != "MessageExtendedMediaPreview":
            # Already purchased media is intentionally ignored here.
            continue

        data = _cached_thumbnail_bytes(getattr(extended, "thumb", None))
        if data:
            return data

    return None


async def close_paid_preview_client():
    global _client
    if _client is not None:
        try:
            await _client.disconnect()
        finally:
            _client = None


def enhance_preview_jpeg(data: bytes) -> bytes | None:
    """Create a clearer, text-oriented JPEG from Telegram's free preview."""
    if not data:
        return None

    try:
        import io
        import cv2
        import numpy as np
        from PIL import Image, ImageOps

        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)

        h, w = bgr.shape[:2]
        long_edge = max(h, w)
        target_edge = 1800
        if long_edge < target_edge:
            scale = target_edge / float(long_edge)
            bgr = cv2.resize(
                bgr,
                (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
                interpolation=cv2.INTER_LANCZOS4,
            )

        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=2.4, tileGridSize=(12, 12))
        l = clahe.apply(l)

        soft = cv2.GaussianBlur(l, (0, 0), 2.0)
        l = cv2.addWeighted(l, 1.65, soft, -0.65, 0)

        fine = cv2.GaussianBlur(l, (0, 0), 0.8)
        l = cv2.addWeighted(l, 1.25, fine, -0.25, 0)

        enhanced = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
        enhanced = cv2.fastNlMeansDenoisingColored(
            enhanced, None, 2, 2, 7, 21
        )

        rgb = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
        output = Image.fromarray(rgb)

        out = io.BytesIO()
        output.save(
            out,
            format="JPEG",
            quality=96,
            subsampling=0,
            optimize=True,
        )
        return out.getvalue()
    except Exception:
        return None
