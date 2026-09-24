import asyncio
import logging
import os
import shutil

from pyrogram import Client
from pyrogram.errors import FloodWait
from pyrogram.types import BotCommand, CallbackQuery, Message

from config import Config
from helper.clone_manager import CloneManager
from helper.message_cleanup import install_auto_cleanup
from helper.job_state import jobs
from helper.database import db
import helper.auto_queue  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

log = logging.getLogger("AniToon")

def install_runtime_localization():
    """Translate known bot UI text automatically for the selected user language."""
    from helper.i18n import localize_text, user_language
    from language.strings import localize_markup

    if getattr(Client, "_anitoon_localization_installed", False):
        return

    original_send_message = Client.send_message
    original_reply_text = Message.reply_text
    original_edit_text = Message.edit_text
    original_reply_caption = getattr(Message, "reply_caption", None)
    original_edit_caption = getattr(Message, "edit_caption", None)
    original_answer = CallbackQuery.answer

    async def _apply_markup(user_id, kwargs):
        markup = kwargs.get("reply_markup")
        if getattr(markup, "inline_keyboard", None):
            try:
                kwargs["reply_markup"] = localize_markup(
                    markup, await user_language(int(user_id))
                )
            except Exception:
                pass

    async def localized_send_message(self, chat_id, text=None, *args, **kwargs):
        if isinstance(text, str):
            text = await localize_text_async(chat_id, text)
        await _apply_markup(chat_id, kwargs)
        return await original_send_message(self, chat_id, text, *args, **kwargs)

    async def localized_reply_text(self, text=None, *args, **kwargs):
        if isinstance(text, str) and getattr(self, "from_user", None):
            text = await localize_text_async(self.from_user.id, text)
            await _apply_markup(self.from_user.id, kwargs)
        return await original_reply_text(self, text, *args, **kwargs)

    async def localized_edit_text(self, text=None, *args, **kwargs):
        if isinstance(text, str) and getattr(self, "from_user", None):
            text = await localize_text_async(self.from_user.id, text)
            await _apply_markup(self.from_user.id, kwargs)
        return await original_edit_text(self, text, *args, **kwargs)

    async def localized_reply_caption(self, caption=None, *args, **kwargs):
        if isinstance(caption, str) and getattr(self, "from_user", None):
            caption = await localize_text_async(self.from_user.id, caption)
        return await original_reply_caption(self, caption, *args, **kwargs)

    async def localized_edit_caption(self, caption=None, *args, **kwargs):
        if isinstance(caption, str) and getattr(self, "from_user", None):
            caption = await localize_text_async(self.from_user.id, caption)
        return await original_edit_caption(self, caption, *args, **kwargs)

    async def localized_answer(self, text=None, *args, **kwargs):
        if isinstance(text, str) and getattr(self, "from_user", None):
            text = await localize_text_async(self.from_user.id, text)
        return await original_answer(self, text, *args, **kwargs)

    async def localize_text_async(user_id, text):
        try:
            return localize_text(await user_language(int(user_id)), text)
        except Exception:
            return text

    Client.send_message = localized_send_message
    Message.reply_text = localized_reply_text
    Message.edit_text = localized_edit_text
    if original_reply_caption:
        Message.reply_caption = localized_reply_caption
    if original_edit_caption:
        Message.edit_caption = localized_edit_caption
    CallbackQuery.answer = localized_answer
    Client._anitoon_localization_installed = True


HEARTBEAT_FILE = os.environ.get("ANITOON_HEARTBEAT_FILE", "/tmp/anitoon_1bot_heartbeat")
CONNECTIVITY_CHECK_INTERVAL = max(10, int(os.environ.get("ANITOON_CONNECTIVITY_CHECK_INTERVAL", "15")))


BOT_COMMANDS = [
    BotCommand("start", "Open AniToon"),
    BotCommand("help", "Show help"),
    BotCommand("cancel", "Cancel current processing"),
    BotCommand("clone", "Create a clone bot"),
    BotCommand("rename", "Open rename page"),
    BotCommand("thumbnail", "Open thumbnail page"),
    BotCommand("plan", "Open plans"),
    BotCommand("language", "Change language"),
    BotCommand("support", "Contact AniToon owner"),
    BotCommand("paysupport", "Payment support"),
]


class Bot(Client):
    def __init__(self):
        install_runtime_localization()
        super().__init__(
            name="AniToon_1Bot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=Config.PYROGRAM_WORKERS,
            max_concurrent_transmissions=Config.MAX_CONCURRENT_TRANSMISSIONS,
            plugins={"root": "plugins"},
        )
        self.is_main_bot = True
        self.is_clone_bot = False
        self.bot_id = 0
        self.bot_username = None
        self.clone_manager = None
        self._heartbeat_task = None
        self._connectivity_online = False
        self._broadcast_task = None
        self._shutting_down = False

    async def _setup_commands(self):
        try:
            await self.delete_bot_commands()
            await self.set_bot_commands(BOT_COMMANDS)
            log.info("Telegram command menu reset: %s public commands", len(BOT_COMMANDS))
        except Exception:
            log.exception("Could not update Telegram bot commands")


    async def _cleanup_stale_jobs(self):
        """Clean abandoned jobs only after the configured recovery window."""
        try:
            await db.ensure_job_indexes()
            await db.ensure_support_indexes()
            deleted = await db.cleanup_stale_jobs(days=Config.JOB_RECOVERY_RETENTION_DAYS)
            if deleted:
                log.info("Removed %s stale job records", deleted)
        except Exception:
            log.exception("Could not clean stale job records")

    async def _touch_heartbeat(self) -> None:
        try:
            parent = os.path.dirname(HEARTBEAT_FILE)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(HEARTBEAT_FILE, "a", encoding="utf-8"):
                pass
            os.utime(HEARTBEAT_FILE, None)
        except OSError:
            pass

    async def _clear_heartbeat(self) -> None:
        try:
            os.remove(HEARTBEAT_FILE)
        except FileNotFoundError:
            pass
        except OSError:
            pass

    async def _broadcast_status(self, text: str) -> None:
        """Best-effort lifecycle broadcast to all known users."""
        semaphore = asyncio.Semaphore(8)

        async def send_one(user_id: int):
            async with semaphore:
                for attempt in range(3):
                    try:
                        await self.send_message(int(user_id), text)
                        return
                    except FloodWait as exc:
                        if attempt >= 2:
                            return
                        await asyncio.sleep(max(1, int(getattr(exc, "value", 1) or 1)))
                    except Exception:
                        return

        batch = []
        try:
            async for user in db.get_all_users():
                if user.get("is_banned"):
                    continue
                user_id = int(user.get("id", 0) or 0)
                if not user_id:
                    continue
                batch.append(asyncio.create_task(send_one(user_id)))
                if len(batch) >= 40:
                    await asyncio.gather(*batch, return_exceptions=True)
                    batch.clear()
            if batch:
                await asyncio.gather(*batch, return_exceptions=True)
        except Exception:
            log.exception("Could not complete lifecycle broadcast")

    async def _announce_online(self, recover: bool = True) -> None:
        was_online = self._connectivity_online
        self._connectivity_online = True
        await self._touch_heartbeat()

        if not was_online:
            self._broadcast_task = asyncio.create_task(
                self._broadcast_status(
                    "✅ **AniToon Bot is back online!**\n\n"
                    "You can use the bot now. Any recoverable file job interrupted while the bot was offline will restart automatically."
                )
            )
        if recover:
            await self._recover_jobs()

    async def _connectivity_monitor(self) -> None:
        while not self._shutting_down:
            try:
                await self.get_me()
                await self._announce_online(recover=not self._connectivity_online)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._connectivity_online:
                    self._connectivity_online = False
                    await self._clear_heartbeat()
                    self._broadcast_task = asyncio.create_task(
                        self._broadcast_status(
                            "⚠️ **AniToon Bot is temporarily offline.**\n\n"
                            "Please wait while the connection is restored. Any recoverable file job is saved and will resume automatically."
                        )
                    )
                    log.warning("Telegram connectivity lost: %s", exc)
            try:
                await asyncio.sleep(CONNECTIVITY_CHECK_INTERVAL)
            except asyncio.CancelledError:
                raise

    async def _recover_jobs(self):
        recovered = await jobs.restore_from_db(self.bot_id)
        if not recovered:
            return

        resumable = [
            job for job in recovered
            if job.selected_action in {"custom_name", "convert_name"}
            and job.extra.get("name_submitted")
            and not job.extra.get("resume_in_progress")
        ]
        if not resumable:
            return

        users = sorted({int(job.user_id) for job in resumable})
        for user_id in users:
            try:
                await self.send_message(
                    user_id,
                    "🔄 **AniToon Bot is restoring your file...**\n\n"
                    "The bot was interrupted, but your file job was saved. Processing will restart automatically from the beginning.",
                )
            except Exception:
                pass

        for job in resumable:
            job.extra["resume_in_progress"] = True
            await jobs.update(job.job_id, extra=job.extra)
            asyncio.create_task(self._resume_one_job(job))

    async def _resume_one_job(self, job):
        try:
            shutil.rmtree(job.work_dir, ignore_errors=True)
            os.makedirs(job.work_dir, exist_ok=True)

            source = None
            if job.source_message_id:
                try:
                    source = await self.get_messages(job.user_id, job.source_message_id)
                except Exception:
                    source = None
            # The original Telegram message may have been cleaned up after
            # the first download. The persisted file_id can still identify
            # the same media for a fresh recovery download.
            if source is None:
                source = str(job.extra.get("file_id") or "").strip() or None
            if source is None:
                raise RuntimeError(
                    f"Original Telegram file is no longer recoverable for job {job.job_id}"
                )

            if job.selected_action == "custom_name":
                from plugins.rename_reply_responder import process_custom_name_job
                name = str(
                    job.extra.get("submitted_name")
                    or job.extra.get("auto_name")
                    or ""
                ).strip()
                if not name:
                    raise RuntimeError("Saved output name is missing")
                await process_custom_name_job(self, source, job, name)
                return

            if job.selected_action == "convert_name":
                from plugins.rename_reply_responder import process_convert_name_job
                name = str(job.extra.get("submitted_name") or "").strip()
                if not name:
                    raise RuntimeError("Saved conversion output name is missing")
                await process_convert_name_job(self, source, job, name)
                return

            raise RuntimeError(f"Unsupported recovery action: {job.selected_action}")
        except asyncio.CancelledError:
            job.extra["processing"] = False
            job.extra["resume_in_progress"] = False
            job.extra["state"] = "queued"
            await jobs.update(job.job_id, extra=job.extra)
            raise
        except Exception:
            job.extra["processing"] = False
            job.extra["resume_in_progress"] = False
            job.extra["state"] = "queued"
            await jobs.update(job.job_id, extra=job.extra)
            log.exception("Could not resume job %s", job.job_id)

    async def start(self):
        while True:
            try:
                await super().start()
                me = await self.get_me()
                self.bot_id = me.id
                self.bot_username = me.username
                self._shutting_down = False
                install_auto_cleanup(self)
                log.info("Main bot started: @%s (ID: %s)", me.username or "unknown", me.id)
                log.info("Telegram transfer concurrency: %s", Config.MAX_CONCURRENT_TRANSMISSIONS)
                # Run independent startup maintenance concurrently so the bot
                # can become responsive without waiting on MongoDB index checks.
                async def _activity_indexes():
                    try:
                        from helper.activity_log import ensure_activity_indexes
                        await ensure_activity_indexes()
                    except Exception:
                        log.exception("Could not initialize rename activity index")

                await asyncio.gather(
                    self._setup_commands(),
                    self._cleanup_stale_jobs(),
                    db.ensure_performance_indexes(),
                    _activity_indexes(),
                    return_exceptions=True,
                )

                await self._announce_online(recover=True)
                self._heartbeat_task = asyncio.create_task(self._connectivity_monitor())

                if Config.IS_CLONE_ALLOWED:
                    self.clone_manager = CloneManager(self)
                    await self.clone_manager.start_all()
                    log.info("Clone Engine: enabled")
                return
            except FloodWait as e:
                wait_time = int(getattr(e, "value", 0) or 0)
                log.error("Telegram FloodWait during startup: %s seconds", wait_time)
                if wait_time <= 0:
                    raise
                await asyncio.sleep(wait_time)
            except Exception:
                log.exception("Main bot startup failed")
                raise

    async def stop(self, *args):
        if self._shutting_down:
            return
        self._shutting_down = True

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            self._heartbeat_task = None

        await self._clear_heartbeat()

        try:
            await asyncio.wait_for(
                self._broadcast_status(
                    "⚠️ **AniToon Bot is temporarily offline.**\n\n"
                    "The bot is being stopped or restarted. Please wait. Any recoverable file job is saved and will resume automatically when the bot is back online."
                ),
                timeout=12,
            )
        except Exception:
            pass

        if self.clone_manager:
            await self.clone_manager.stop_all()
            self.clone_manager = None
        await super().stop()
        log.info("AniToon_1Bot stopped")



if __name__ == "__main__":
    Bot().run()
