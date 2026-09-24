import asyncio
from datetime import datetime, timedelta
import time
import uuid

import motor.motor_asyncio
from pymongo import ReturnDocument

from config import Config


DB_NAME = "AniToon_Promax_DB"
DEFAULT_METADATA_NAME = "AniToon Official"


class Database:
    def __init__(self, uri: str, database_name: str = DB_NAME):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(
            uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
            maxPoolSize=Config.DB_MAX_POOL_SIZE,
            minPoolSize=Config.DB_MIN_POOL_SIZE,
            waitQueueTimeoutMS=Config.DB_WAIT_QUEUE_TIMEOUT_MS,
            maxConnecting=4,
        )
        self.db = self._client[database_name]
        self.col = self.db.user
        self.subscriptions = self.db.subscriptions
        self.usage = self.db.usage
        self.advanced_usage = self.db.advanced_usage
        self.payments = self.db.payments
        self.clones = self.db.clones
        self.force_sub_requests = self.db.force_sub_requests
        self.support_requests = self.db.support_requests
        self.jobs = self.db.jobs

    async def ensure_performance_indexes(self):
        """Ensure hot-path query indexes exist without blocking bot startup."""
        indexes = [
            self.col.create_index("id", name="user_id_idx"),
            self.subscriptions.create_index([("user_id", 1), ("bot_id", 1)], name="subscription_user_bot_idx"),
            self.usage.create_index([("user_id", 1), ("bot_id", 1), ("date", 1)], name="usage_user_bot_date_idx"),
            self.advanced_usage.create_index(
                [("user_id", 1), ("bot_id", 1), ("date", 1), ("feature", 1)],
                name="advanced_usage_lookup_idx",
            ),
            self.jobs.create_index([("bot_id", 1), ("state", 1), ("created_at", 1)], name="jobs_recovery_lookup_idx"),
            self.clones.create_index("bot_id", name="clone_bot_id_idx"),
        ]
        results = await asyncio.gather(*indexes, return_exceptions=True)
        failures = [result for result in results if isinstance(result, Exception)]
        if failures:
            for failure in failures:
                # Never make the bot unavailable just because an optional index
                # cannot be created on a restricted MongoDB deployment.
                print(f"Database performance index warning: {failure}")
            return False
        return True

    @staticmethod
    def new_user(user_id: int) -> dict:
        return {"id": int(user_id), "join_date": datetime.utcnow(), "thumb": None, "caption": None, "rename_mode": "manual", "rename_template": "", "thumbnail_mode": "none", "language": None, "audio_name": DEFAULT_METADATA_NAME, "sub_name": DEFAULT_METADATA_NAME, "audio_prefix": None, "audio_language": None, "audio_suffix": "", "subtitle_prefix": None, "subtitle_language": None, "subtitle_suffix": "", "is_banned": False}

    async def add_user(self, user_id: int):
        await self.col.update_one({"id": int(user_id)}, {"$setOnInsert": self.new_user(user_id)}, upsert=True)

    async def get_or_create_user(self, user_id: int):
        """Fetch a user or create it atomically in one MongoDB round trip."""
        return await self.col.find_one_and_update(
            {"id": int(user_id)},
            {"$setOnInsert": self.new_user(user_id)},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    async def is_user_exist(self, user_id: int) -> bool:
        return await self.col.count_documents({"id": int(user_id)}, limit=1) > 0

    async def get_user_data(self, user_id: int):
        return await self.col.find_one({"id": int(user_id)})

    async def total_users_count(self) -> int:
        return await self.col.count_documents({})

    def get_all_users(self):
        return self.col.find({})

    async def get_subscription(self, user_id: int, bot_id: int) -> dict:
        user_id, bot_id = int(user_id), int(bot_id)
        record = await self.subscriptions.find_one({"user_id": user_id, "bot_id": bot_id})
        if not record:
            return {"user_id": user_id, "bot_id": bot_id, "plan": "free", "expires_at": None, "stars_paid": 0}
        plan_key, expires_at = record.get("plan", "free"), record.get("expires_at")
        if plan_key != "free" and expires_at and expires_at <= datetime.utcnow():
            await self.subscriptions.update_one({"user_id": user_id, "bot_id": bot_id}, {"$set": {"plan": "free", "expires_at": None}})
            record["plan"], record["expires_at"], record["stars_paid"] = "free", None, 0
        return record

    async def set_plan(self, user_id: int, bot_id: int, plan_key: str, stars_paid: int = 0, payment_id: str | None = None):
        from helper.plans import get_plan
        user_id, bot_id = int(user_id), int(bot_id)
        plan, now = get_plan(plan_key), datetime.utcnow()
        if plan_key == "free":
            expires_at = None
        else:
            current = await self.subscriptions.find_one({"user_id": user_id, "bot_id": bot_id})
            current_expiry = current.get("expires_at") if current else None
            start = current_expiry if current_expiry and current_expiry > now else now
            expires_at = start + timedelta(days=plan.days)
        await self.subscriptions.update_one({"user_id": user_id, "bot_id": bot_id}, {"$set": {"user_id": user_id, "bot_id": bot_id, "plan": plan_key, "expires_at": expires_at, "stars_paid": int(stars_paid), "payment_id": payment_id, "updated_at": now}}, upsert=True)

    async def get_usage(self, user_id: int, bot_id: int) -> int:
        today = datetime.utcnow().date().isoformat()
        record = await self.usage.find_one({"user_id": int(user_id), "bot_id": int(bot_id), "date": today})
        return int(record.get("bytes", 0)) if record else 0

    async def update_usage(self, user_id: int, bot_id: int, bytes_count: int):
        today = datetime.utcnow().date().isoformat()
        await self.usage.update_one({"user_id": int(user_id), "bot_id": int(bot_id), "date": today}, {"$inc": {"bytes": int(bytes_count)}}, upsert=True)

    async def get_advanced_usage(self, user_id: int, bot_id: int, feature: str) -> int:
        today = datetime.utcnow().date().isoformat()
        record = await self.advanced_usage.find_one({
            "user_id": int(user_id),
            "bot_id": int(bot_id),
            "date": today,
            "feature": str(feature),
        })
        return int(record.get("count", 0)) if record else 0

    async def consume_advanced_usage(self, user_id: int, bot_id: int, feature: str, limit: int) -> int:
        """Atomically consume one daily advanced-feature use without crossing the limit."""
        user_id, bot_id, feature, limit = int(user_id), int(bot_id), str(feature), max(1, int(limit))
        today = datetime.utcnow().date().isoformat()
        identity = {
            "user_id": user_id,
            "bot_id": bot_id,
            "date": today,
            "feature": feature,
        }

        # Ensure the daily feature document exists. This is intentionally
        # separate from the increment so concurrent first-use requests cannot
        # create duplicate usage documents.
        await self.advanced_usage.update_one(
            identity,
            {"$setOnInsert": {**identity, "count": 0, "created_at": datetime.utcnow()}},
            upsert=True,
        )

        result = await self.advanced_usage.update_one(
            {**identity, "count": {"$lt": limit}},
            {"$inc": {"count": 1}},
        )
        if not result.modified_count:
            return 0

        record = await self.advanced_usage.find_one(identity, {"count": 1})
        return int(record.get("count", 0)) if record else 0

    async def create_support_request(
        self,
        user_id: int,
        bot_id: int,
        user_text: str,
        user_name: str = "",
        username: str | None = None,
        prompt_message_id: int | None = None,
    ) -> str:
        request_id = uuid.uuid4().hex[:10]
        now = datetime.utcnow()
        document = {
            "request_id": request_id,
            "user_id": int(user_id),
            "bot_id": int(bot_id),
            "user_name": str(user_name or ""),
            "username": str(username or "").lstrip("@") or None,
            "message": str(user_text or "").strip()[:4000],
            "status": "open",
            "created_at": now,
            "updated_at": now,
        }
        if prompt_message_id:
            document["prompt_message_id"] = int(prompt_message_id)
        await self.support_requests.insert_one(document)
        return request_id

    async def get_support_request(self, request_id: str):
        return await self.support_requests.find_one({"request_id": str(request_id)})

    async def list_support_requests(self, limit: int = 10):
        cursor = (
            self.support_requests
            .find({"status": "open"})
            .sort("created_at", -1)
            .limit(max(1, int(limit)))
        )
        return [item async for item in cursor]

    async def save_support_reply(self, request_id: str, owner_text: str, bot_message_id: int | None = None):
        data = {
            "owner_reply": str(owner_text or "").strip()[:4000],
            "owner_replied_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        if bot_message_id:
            data["last_bot_message_id"] = int(bot_message_id)
        await self.support_requests.update_one(
            {"request_id": str(request_id)},
            {"$set": data},
        )

    async def close_support_request(self, request_id: str):
        await self.support_requests.update_one(
            {"request_id": str(request_id)},
            {"$set": {"status": "closed", "updated_at": datetime.utcnow()}},
        )

    async def reopen_support_request(self, request_id: str):
        await self.support_requests.update_one(
            {"request_id": str(request_id)},
            {"$set": {"status": "open", "updated_at": datetime.utcnow()}},
        )

    async def ensure_support_indexes(self):
        try:
            await self.support_requests.create_index(
                [("status", 1), ("created_at", -1)],
                name="support_open_created",
            )
            await self.support_requests.create_index(
                "request_id",
                unique=True,
                name="support_request_id_unique",
            )
            return True
        except Exception:
            return False

    async def mark_force_sub_request(self, user_id: int, chat_id: int):
        await self.force_sub_requests.update_one({"user_id": int(user_id), "chat_id": int(chat_id)}, {"$set": {"user_id": int(user_id), "chat_id": int(chat_id), "requested_at": datetime.utcnow()}}, upsert=True)

    async def has_force_sub_request(self, user_id: int, chat_id: int) -> bool:
        return bool(await self.force_sub_requests.find_one({"user_id": int(user_id), "chat_id": int(chat_id)}, {"_id": 1}))

    async def clear_force_sub_request(self, user_id: int, chat_id: int):
        await self.force_sub_requests.delete_one({"user_id": int(user_id), "chat_id": int(chat_id)})

    async def set_language(self, user_id: int, language: str | None):
        from helper.i18n import is_valid_language
        value = str(language or "").strip().lower()
        if value and not is_valid_language(value):
            raise ValueError("Invalid language")
        await self.col.update_one({"id": int(user_id)}, {"$set": {"language": value or None}}, upsert=True)
        try:
            from helper.i18n import remember_language
            remember_language(int(user_id), value or None)
        except Exception:
            pass

    async def get_language(self, user_id: int) -> str | None:
        user = await self.col.find_one({"id": int(user_id)}, {"language": 1})
        value = str(user.get("language") or "").strip().lower() if user else ""
        return value or None

    async def set_thumbnail(self, user_id: int, file_id: str | None):
        await self.col.update_one({"id": int(user_id)}, {"$set": {"thumb": file_id}}, upsert=True)

    async def get_thumbnail(self, user_id: int):
        user = await self.col.find_one({"id": int(user_id)}, {"thumb": 1})
        return user.get("thumb") if user else None

    async def set_thumbnail_mode(self, user_id: int, mode: str):
        mode = str(mode).strip().lower()
        if mode not in {"none", "auto", "custom"}:
            raise ValueError("Invalid thumbnail mode")
        await self.col.update_one({"id": int(user_id)}, {"$set": {"thumbnail_mode": mode}}, upsert=True)

    async def get_thumbnail_mode(self, user_id: int) -> str:
        user = await self.col.find_one({"id": int(user_id)}, {"thumbnail_mode": 1})
        mode = str(user.get("thumbnail_mode", "none") if user else "none").strip().lower()
        return mode if mode in {"none", "auto", "custom"} else "none"
    async def set_small_images_free(self, enabled: bool):
        await self.db.settings.update_one(
            {"key": "free_small_images"},
            {"$set": {"key": "free_small_images", "enabled": bool(enabled)}},
            upsert=True,
        )

    async def get_small_images_free(self) -> bool:
        record = await self.db.settings.find_one({"key": "free_small_images"})
        return bool(record.get("enabled", False)) if record else False

    async def set_paid_preview_message(self, message_id: int | None):
        await self.db.settings.update_one(
            {"key": "paid_preview_message"},
            {"$set": {"key": "paid_preview_message", "message_id": int(message_id) if message_id else None}},
            upsert=True,
        )

    async def get_paid_preview_message(self) -> int | None:
        record = await self.db.settings.find_one({"key": "paid_preview_message"})
        if not record or record.get("message_id") is None:
            return None
        return int(record["message_id"])

    async def set_paid_preview_gallery(self, gallery_id: str, owner_id: int, file_ids: list[str]):
        await self.db.settings.update_one(
            {"key": f"paid_preview_gallery:{gallery_id}"},
            {"$set": {
                "key": f"paid_preview_gallery:{gallery_id}",
                "owner_id": int(owner_id),
                "file_ids": [str(x) for x in file_ids],
            }},
            upsert=True,
        )

    async def get_paid_preview_gallery(self, gallery_id: str, owner_id: int):
        record = await self.db.settings.find_one(
            {"key": f"paid_preview_gallery:{gallery_id}", "owner_id": int(owner_id)}
        )
        return list(record.get("file_ids", [])) if record else []

    async def clear_paid_preview_galleries(self, owner_id: int) -> int:
        """Delete only temporary paid-preview gallery records for this owner."""
        result = await self.db.settings.delete_many({
            "owner_id": int(owner_id),
            "key": {"$regex": r"^paid_preview_gallery:"},
        })
        return int(getattr(result, "deleted_count", 0) or 0)

    async def set_paid_photo_waiting(self, waiting: bool):
        await self.db.settings.update_one(
            {"key": "paid_photo_waiting"},
            {"$set": {"key": "paid_photo_waiting", "waiting": bool(waiting)}},
            upsert=True,
        )

    async def get_paid_photo_waiting(self) -> bool:
        record = await self.db.settings.find_one({"key": "paid_photo_waiting"})
        return bool(record.get("waiting", False)) if record else False

    async def set_paid_media_offset(self, offset: int):
        await self.db.settings.update_one(
            {"key": "paid_media_offset"},
            {"$set": {"key": "paid_media_offset", "offset": int(offset)}},
            upsert=True,
        )

    async def get_paid_media_offset(self) -> int | None:
        record = await self.db.settings.find_one({"key": "paid_media_offset"})
        if not record or record.get("offset") is None:
            return None
        return int(record["offset"])

    async def set_caption(self, user_id: int, caption: str | None):
        await self.col.update_one({"id": int(user_id)}, {"$set": {"caption": caption}}, upsert=True)

    async def get_caption(self, user_id: int):
        user = await self.col.find_one({"id": int(user_id)}, {"caption": 1})
        return user.get("caption") if user else None

    async def set_rename_mode(self, user_id: int, mode: str):
        mode = str(mode).strip().lower()
        if mode not in {"manual", "auto", "permanent"}:
            raise ValueError("Invalid rename mode")
        await self.col.update_one({"id": int(user_id)}, {"$set": {"rename_mode": mode}}, upsert=True)

    async def get_rename_mode(self, user_id: int) -> str:
        user = await self.col.find_one({"id": int(user_id)}, {"rename_mode": 1})
        mode = str(user.get("rename_mode", "manual") if user else "manual").strip().lower()
        return mode if mode in {"manual", "auto", "permanent"} else "manual"

    async def set_rename_template(self, user_id: int, template: str | None):
        value = str(template or "").strip()
        await self.col.update_one({"id": int(user_id)}, {"$set": {"rename_template": value}}, upsert=True)

    async def get_rename_template(self, user_id: int) -> str:
        user = await self.col.find_one({"id": int(user_id)}, {"rename_template": 1})
        return str(user.get("rename_template", "") if user else "").strip()
    async def set_audio_name(self, user_id: int, audio_name: str):
        await self.col.update_one({"id": int(user_id)}, {"$set": {"audio_name": str(audio_name)}}, upsert=True)

    async def set_subtitle_name(self, user_id: int, subtitle_name: str):
        await self.col.update_one({"id": int(user_id)}, {"$set": {"sub_name": str(subtitle_name)}}, upsert=True)

    async def set_metadata(self, user_id: int, audio_name: str, subtitle_name: str):
        await self.col.update_one({"id": int(user_id)}, {"$set": {"audio_name": str(audio_name), "sub_name": str(subtitle_name)}}, upsert=True)

    async def set_metadata_parts(self, user_id: int, *, audio_prefix: str, audio_language: str, audio_suffix: str = "", subtitle_prefix: str, subtitle_language: str, subtitle_suffix: str = ""):
        audio_prefix, audio_language, audio_suffix = str(audio_prefix or "").strip(), str(audio_language or "").strip(), str(audio_suffix or "").strip()
        subtitle_prefix, subtitle_language, subtitle_suffix = str(subtitle_prefix or "").strip(), str(subtitle_language or "").strip(), str(subtitle_suffix or "").strip()
        audio_name = " ".join(x for x in (audio_prefix, audio_language, audio_suffix) if x)
        sub_name = " ".join(x for x in (subtitle_prefix, subtitle_language, subtitle_suffix) if x)
        await self.col.update_one(
            {"id": int(user_id)},
            {"$set": {
                "audio_prefix": audio_prefix,
                "audio_language": audio_language,
                "audio_suffix": audio_suffix,
                "subtitle_prefix": subtitle_prefix,
                "subtitle_language": subtitle_language,
                "subtitle_suffix": subtitle_suffix,
                "audio_name": audio_name,
                "sub_name": sub_name,
            }},
            upsert=True,
        )

    async def ban_user(self, user_id: int):
        await self.col.update_one({"id": int(user_id)}, {"$set": {"is_banned": True}}, upsert=True)

    async def unban_user(self, user_id: int):
        await self.col.update_one({"id": int(user_id)}, {"$set": {"is_banned": False}}, upsert=True)

    async def payment_exists(self, charge_id: str) -> bool:
        return bool(await self.payments.find_one({"charge_id": charge_id}, {"_id": 1}))

    async def record_payment(self, user_id: int, bot_id: int, plan_key: str, stars: int, charge_id: str) -> bool:
        if await self.payment_exists(charge_id):
            return False
        await self.payments.insert_one({
            "user_id": int(user_id),
            "bot_id": int(bot_id),
            "plan": plan_key,
            "stars": int(stars),
            "charge_id": str(charge_id),
            "activation_status": "pending",
            "created_at": datetime.utcnow(),
        })
        return True

    async def get_payment(self, charge_id: str):
        return await self.payments.find_one({"charge_id": str(charge_id)})

    async def mark_payment_activated(self, charge_id: str):
        await self.payments.update_one(
            {"charge_id": str(charge_id)},
            {"$set": {"activation_status": "activated", "activated_at": datetime.utcnow()}},
        )
    async def ensure_job_indexes(self):
        """Keep recoverable jobs self-cleaning without per-request delete queries."""
        try:
            await self.jobs.create_index("expires_at", expireAfterSeconds=0, name="job_recovery_expires_ttl")
            return True
        except Exception:
            return False

    async def save_job(self, job_data: dict):
        data = dict(job_data)
        try:
            created_at = float(data.get("created_at") or time.time())
            data["expires_at"] = datetime.utcfromtimestamp(created_at) + timedelta(days=Config.JOB_RECOVERY_RETENTION_DAYS)
        except Exception:
            pass
        await self.jobs.update_one({"job_id": str(data["job_id"])}, {"$set": data}, upsert=True)

    async def delete_job(self, job_id: str):
        await self.jobs.delete_one({"job_id": str(job_id)})
    async def delete_job(self, job_id: str):
        await self.jobs.delete_one({"job_id": str(job_id)})

    async def get_pending_jobs(self, bot_id: int):
        cursor = self.jobs.find({"bot_id": int(bot_id), "state": {"$nin": ["completed", "cancelled"]}})
        return [item async for item in cursor]

    async def cleanup_stale_jobs(self, days: int | None = None) -> int:
        """Remove unfinished jobs only after the full recovery retention window."""
        retention_days = max(1, int(days if days is not None else Config.JOB_RECOVERY_RETENTION_DAYS))
        cutoff = time.time() - (retention_days * 24 * 60 * 60)
        result = await self.jobs.delete_many({
            "created_at": {"$lt": cutoff},
            "state": {"$nin": ["completed", "cancelled"]},
        })
        return int(getattr(result, "deleted_count", 0) or 0)

    async def add_clone(self, owner_id: int, bot_id: int, bot_username: str | None, bot_name: str | None, bot_token: str):
        now = datetime.utcnow()
        await self.clones.update_one({"bot_id": int(bot_id)}, {"$set": {"owner_id": int(owner_id), "bot_id": int(bot_id), "bot_username": bot_username, "bot_name": bot_name, "bot_token": bot_token, "status": "online", "updated_at": now}, "$setOnInsert": {"created_at": now}}, upsert=True)

    async def get_clone(self, owner_id: int):
        return await self.clones.find_one({"owner_id": int(owner_id)})

    async def get_clone_by_bot_id(self, bot_id: int):
        return await self.clones.find_one({"bot_id": int(bot_id)})

    def get_all_clones(self):
        return self.clones.find({})

    async def set_clone_status(self, bot_id: int, status: str):
        await self.clones.update_one({"bot_id": int(bot_id)}, {"$set": {"status": status, "updated_at": datetime.utcnow()}})

    async def remove_clone(self, bot_id: int):
        await self.clones.delete_one({"bot_id": int(bot_id)})


db = Database(Config.DATABASE_URL, DB_NAME)
