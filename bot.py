import asyncio
import logging
import os
import shutil

from pyrogram import Client
from pyrogram.errors import FloodWait
from pyrogram.types import BotCommand

from config import Config
from helper.clone_manager import CloneManager
from helper.message_cleanup import install_auto_cleanup
from helper.job_state import jobs
import helper.auto_queue  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("AniToon")

BOT_COMMANDS = [
    BotCommand("start", "Open AniToon"),
    BotCommand("help", "Show help"),
    BotCommand("cancel", "Cancel current processing"),
    BotCommand("clone", "Create a clone bot"),
    BotCommand("rename", "Open rename page"),
    BotCommand("thumbnail", "Open thumbnail page"),
    BotCommand("plan", "Open plans"),
    BotCommand("language", "Change language"),
]


class Bot(Client):
    def __init__(self):
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

    async def _setup_commands(self):
        try:
            await self.delete_bot_commands()
            await self.set_bot_commands(BOT_COMMANDS)
            log.info("Telegram command menu reset: %s public commands", len(BOT_COMMANDS))
        except Exception:
            log.exception("Could not update Telegram bot commands")


    async def _recover_jobs(self):
        recovered = await jobs.restore_from_db(self.bot_id)
        if not recovered:
            return
        # Notify only users whose file is actually in the rename/processing
        # stage and can be restarted. Jobs still waiting for an action/name
        # must not receive an update message.
        processing_jobs = [
            job for job in recovered
            if job.selected_action == "custom_name" and job.extra.get("name_submitted")
        ]
        users = sorted({int(job.user_id) for job in processing_jobs})
        for user_id in users:
            try:
                await self.send_message(
                    user_id,
                    "🔄 **AniToon Bot is updating...**\n\n"
                    "Please wait. Your file will start again automatically from the beginning after the update."
                )
            except Exception:
                pass

        for job in processing_jobs:
            name = str(job.extra.get("submitted_name") or job.extra.get("auto_name") or "").strip()
            if name:
                asyncio.create_task(self._resume_one_job(job, name))

    async def _resume_one_job(self, job, name: str):
        from plugins.rename_reply_responder import process_custom_name_job
        try:
            # A deployment must restart the unfinished job from the beginning.
            # Remove any partial local download/output so the next transfer
            # starts from the original Telegram file again.
            shutil.rmtree(job.work_dir, ignore_errors=True)
            os.makedirs(job.work_dir, exist_ok=True)

            source = None
            if job.source_message_id:
                try:
                    source = await self.get_messages(job.user_id, job.source_message_id)
                except Exception:
                    source = None
            if source is None:
                log.error("Original source message %s not found for job %s", job.source_message_id, job.job_id)
                return

            await process_custom_name_job(self, source, job, name)
        except Exception:
            log.exception("Could not resume job %s", job.job_id)

    async def start(self):
        while True:
            try:
                await super().start()
                me = await self.get_me()
                self.bot_id = me.id
                self.bot_username = me.username
                install_auto_cleanup(self)
                log.info("Main bot started: @%s (ID: %s)", me.username or "unknown", me.id)
                log.info("Telegram transfer concurrency: %s", Config.MAX_CONCURRENT_TRANSMISSIONS)
                await self._setup_commands()
                await self._recover_jobs()
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
        if self.clone_manager:
            await self.clone_manager.stop_all()
            self.clone_manager = None
        await super().stop()
        log.info("AniToon_1Bot stopped")


if __name__ == "__main__":
    Bot().run()
