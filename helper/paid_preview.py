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


def enhance_preview_jpeg(data: bytes, target_edge: int = 4096) -> bytes | None:
    """Create a memory-safe high-resolution preview suitable for Render free-tier RAM."""
    if not data:
        return None

    try:
        import io
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps

        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")

            # Keep the output useful while preventing 8K-sized intermediate
            # arrays from exhausting a small Render instance.
            max_pixels = 12_000_000
            width, height = image.size
            long_edge = max(width, height)
            scale = 1.0
            if long_edge < target_edge:
                scale = float(target_edge) / float(long_edge)

            new_width = max(1, int(round(width * scale)))
            new_height = max(1, int(round(height * scale)))
            pixels = new_width * new_height
            if pixels > max_pixels:
                pixel_scale = (max_pixels / float(pixels)) ** 0.5
                new_width = max(1, int(round(new_width * pixel_scale)))
                new_height = max(1, int(round(new_height * pixel_scale)))

            if (new_width, new_height) != image.size:
                image = image.resize(
                    (new_width, new_height),
                    Image.Resampling.LANCZOS,
                )

            # Lightweight enhancement without allocating several full-size
            # OpenCV/LAB buffers at once.
            image = ImageOps.autocontrast(image, cutoff=1)
            image = ImageEnhance.Contrast(image).enhance(1.10)
            image = image.filter(
                ImageFilter.UnsharpMask(radius=1.2, percent=135, threshold=3)
            )

            for quality in (92, 88, 84, 80, 76):
                out = io.BytesIO()
                image.save(
                    out,
                    format="JPEG",
                    quality=quality,
                    optimize=True,
                    progressive=True,
                )
                encoded = out.getvalue()
                if len(encoded) <= 9 * 1024 * 1024:
                    return encoded

            return encoded if encoded else None
    except Exception:
        return None


async def get_paid_preview_gallery_bytes(
    pyrogram_client,
    chat_id: int,
    message_id: int,
) -> list[bytes]:
    """Return every unpaid paid-media preview in the same Telegram message."""
    client = await _get_telethon_client()
    if client is None:
        return []

    entity = await _telethon_entity(
        pyrogram_client,
        int(chat_id),
    )
    if entity is None:
        return []

    telegram_message = await client.get_messages(
        entity,
        ids=int(message_id),
    )
    if telegram_message is None:
        return []

    media = getattr(telegram_message, "media", None)
    if type(media).__name__ != "MessageMediaPaidMedia":
        return []

    previews = []
    for extended in getattr(media, "extended_media", None) or []:
        if type(extended).__name__ != "MessageExtendedMediaPreview":
            continue
        data = _cached_thumbnail_bytes(getattr(extended, "thumb", None))
        if data:
            previews.append(data)

    return previews


async def get_paid_preview_bytes(pyrogram_client, chat_id: int, message_id: int) -> bytes | None:
    previews = await get_paid_preview_gallery_bytes(
        pyrogram_client,
        chat_id,
        message_id,
    )
    return previews[0] if previews else None
