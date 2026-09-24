from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from config import Config
from helper.database import db


@dataclass
class Job:
    job_id: str
    user_id: int
    bot_id: int
    source_message_id: int
    work_dir: str
    input_path: str
    original_name: str
    mime_type: str | None = None
    detected_name: str | None = None
    selected_action: str | None = None
    output_ext: str | None = None
    active: bool = True
    queued_at: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    extra: dict[str, Any] = field(default_factory=dict)


class JobManager:
    def __init__(self, max_active: int = 100):
        self.max_active = max(1, int(max_active))
        self._semaphore = asyncio.Semaphore(self.max_active)
        # A separate lock per user prevents one user's jobs from racing each
        # other, without serializing unrelated users globally.
        self._user_locks: dict[int, asyncio.Lock] = {}
        self._jobs: dict[str, Job] = {}
        self._user_jobs: dict[int, list[str]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _persist_extra(extra: dict[str, Any]) -> dict[str, Any]:
        allowed = {}
        for key, value in (extra or {}).items():
            if key in {"source_message", "user_data"}:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                allowed[key] = value
            elif isinstance(value, dict):
                allowed[key] = JobManager._persist_extra(value)
            elif isinstance(value, list):
                allowed[key] = [v for v in value if isinstance(v, (str, int, float, bool)) or v is None]
        return allowed

    def _record(self, job: Job) -> dict[str, Any]:
        extra = self._persist_extra(job.extra)
        return {
            "job_id": job.job_id, "user_id": int(job.user_id), "bot_id": int(job.bot_id),
            "source_message_id": int(job.source_message_id), "work_dir": job.work_dir,
            "input_path": job.input_path, "original_name": job.original_name,
            "mime_type": job.mime_type, "detected_name": job.detected_name,
            "selected_action": job.selected_action, "output_ext": job.output_ext,
            "active": bool(job.active), "queued_at": float(job.queued_at),
            "created_at": float(job.created_at), "extra": extra,
            "state": str(extra.get("state") or ("processing" if extra.get("processing") else "queued")),
        }

    async def register(self, job: Job) -> bool:
        async with self._lock:
            user_id = int(job.user_id)
            self._jobs[job.job_id] = job
            self._user_jobs.setdefault(user_id, []).append(job.job_id)
            self._user_locks.setdefault(user_id, asyncio.Lock())
            await db.save_job(self._record(job))
            return True

    async def get(self, job_id: str) -> Job | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def get_all_jobs(self) -> list[Job]:
        async with self._lock:
            return list(self._jobs.values())

    async def get_user_jobs(self, user_id: int) -> list[Job]:
        async with self._lock:
            ids = list(self._user_jobs.get(int(user_id), []))
            return [self._jobs[job_id] for job_id in ids if job_id in self._jobs]

    async def get_user_job(self, user_id: int) -> Job | None:
        async with self._lock:
            ids = self._user_jobs.get(int(user_id), [])
            current = [self._jobs[job_id] for job_id in ids if job_id in self._jobs]
            for job in current:
                if job.selected_action:
                    return job
            return current[0] if current else None

    async def update(self, job_id: str, **values: Any) -> Job | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for key, value in values.items():
                setattr(job, key, value)
            await db.save_job(self._record(job))
            return job

    async def remove(self, job_id: str) -> None:
        async with self._lock:
            job = self._jobs.pop(job_id, None)
            if not job:
                return
            queue = self._user_jobs.get(job.user_id, [])
            try:
                queue.remove(job_id)
            except ValueError:
                pass
            if queue:
                self._user_jobs[job.user_id] = queue
            else:
                self._user_jobs.pop(job.user_id, None)
                self._user_locks.pop(job.user_id, None)
            await db.delete_job(job_id)

    async def restore_from_db(self, bot_id: int) -> list[Job]:
        """Restore unfinished jobs from MongoDB without duplicating in-memory jobs.

        A restored job is returned for automatic recovery when it contains
        enough information to resume. Jobs that are already actively
        processing in this process are left alone.
        """
        records = await db.get_pending_jobs(int(bot_id))
        restored = []
        async with self._lock:
            for item in records:
                job_id = str(item.get("job_id") or "")
                if not job_id:
                    continue

                existing = self._jobs.get(job_id)
                if existing is not None and existing.extra.get("processing"):
                    continue

                job = Job(
                    job_id=job_id,
                    user_id=int(item["user_id"]),
                    bot_id=int(item["bot_id"]),
                    source_message_id=int(item.get("source_message_id", 0) or 0),
                    work_dir=str(item.get("work_dir") or ""),
                    input_path=str(item.get("input_path") or ""),
                    original_name=str(item.get("original_name") or "file"),
                    mime_type=item.get("mime_type"),
                    detected_name=item.get("detected_name"),
                    selected_action=item.get("selected_action"),
                    output_ext=item.get("output_ext"),
                    active=bool(item.get("active", True)),
                    queued_at=float(item.get("queued_at", time.time())),
                    created_at=float(item.get("created_at", time.time())),
                    extra=dict(item.get("extra") or {}),
                )
                job.extra.pop("source_message", None)
                job.extra.pop("user_data", None)
                job.extra["processing"] = False
                job.extra["state"] = "queued"

                self._jobs[job.job_id] = job
                self._user_jobs.setdefault(job.user_id, [])
                if job.job_id not in self._user_jobs[job.user_id]:
                    self._user_jobs[job.user_id].append(job.job_id)
                self._user_locks.setdefault(job.user_id, asyncio.Lock())
                restored.append(job)

            for ids in self._user_jobs.values():
                ids.sort(key=lambda jid: self._jobs[jid].queued_at)

        return sorted(restored, key=lambda item: item.queued_at)

    async def position(self, job_id: str) -> int:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return 0
            waiting = sorted(
                (item for item in self._jobs.values() if item.active and item.selected_action),
                key=lambda item: item.queued_at,
            )
            for index, item in enumerate(waiting, start=1):
                if item.job_id == job_id:
                    return index
        return 0

    async def user_queue_position(self, job_id: str) -> int:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return 0
            ids = self._user_jobs.get(job.user_id, [])
            try:
                index = ids.index(job_id)
            except ValueError:
                return 0
            earlier = 0
            for prior_id in ids[:index]:
                prior = self._jobs.get(prior_id)
                if prior and prior.active and prior.selected_action:
                    earlier += 1
            return earlier

    async def user_lock(self, user_id: int) -> asyncio.Lock:
        async with self._lock:
            return self._user_locks.setdefault(int(user_id), asyncio.Lock())

    async def acquire(self):
        await self._semaphore.acquire()

    def release(self):
        self._semaphore.release()


jobs = JobManager(max_active=Config.MAX_ACTIVE_JOBS)
