import os


class Config:
    # =========================
    # TELEGRAM
    # =========================

    API_ID = int(os.getenv("API_ID", "0"))

    API_HASH = os.getenv(
        "API_HASH",
        ""
    ).strip()

    BOT_TOKEN = os.getenv(
        "BOT_TOKEN",
        ""
    ).strip()


    # =========================
    # DATABASE
    # =========================

    DATABASE_URL = (
        os.getenv("DATABASE_URL")
        or os.getenv("MONGO_URI")
        or ""
    ).strip()


    # =========================
    # BOT INFORMATION
    # =========================

    MAIN_BOT_USERNAME = (
        os.getenv(
            "MAIN_BOT_USERNAME",
            ""
        )
        .strip()
        .lstrip("@")
    )

    LOG_CHANNEL = int(
        os.getenv(
            "LOG_CHANNEL",
            "0"
        )
    )


    # =========================
    # FIXED APPLICATION SETTINGS
    # =========================

    ARCHIVE_CHANNEL_ID = -1004491486679

    START_PIC = ""

    PORT = 10000


    # =========================
    # PYROGRAM
    # =========================

    PYROGRAM_WORKERS = max(8, int(os.getenv("PYROGRAM_WORKERS", "16")))


    # =========================
    # JOB / QUEUE SETTINGS
    # =========================

    # Unfinished jobs remain recoverable across deployments for one week.
    JOB_RECOVERY_RETENTION_DAYS = max(1, int(os.getenv("JOB_RECOVERY_RETENTION_DAYS", "7")))

    MAX_ACTIVE_JOBS = 50

    MAX_CONCURRENT_TRANSMISSIONS = max(1, int(os.getenv("MAX_CONCURRENT_TRANSMISSIONS", "3")))

    MAX_CONCURRENT_PROCESSING = max(1, int(os.getenv("MAX_CONCURRENT_PROCESSING", "2")))


    # =========================
    # FFMPEG
    # =========================

    FFMPEG_PRESET = "ultrafast"

    FFMPEG_THREADS = 0


    # =========================
    # PROGRESS
    # =========================

    PROGRESS_UPDATE_INTERVAL = 1.5

    COMPLETED_STR = os.getenv(
        "COMPLETED_STR",
        "▰"
    )

    REMAINING_STR = os.getenv(
        "REMAINING_STR",
        "▱"
    )


    # =========================
    # FORCE SUBSCRIBE
    # =========================

    FORCE_SUB = os.getenv(
        "FORCE_SUB",
        ""
    ).strip()

    FORCE_SUB_LINKS = os.getenv(
        "FORCE_SUB_LINKS",
        ""
    ).strip()

    FORCE_SUB_PRIVATE_LINK = os.getenv(
        "FORCE_SUB_PRIVATE_LINK",
        ""
    ).strip()


    # =========================
    # CLONE SYSTEM
    # =========================

    IS_CLONE_ALLOWED = (
        os.getenv(
            "IS_CLONE_ALLOWED",
            "true"
        ).lower()
        in {
            "true",
            "1",
            "yes",
            "on",
        }
    )


    # =========================
    # OWNER ONLY
    # =========================

    _owner_raw = os.getenv(
        "OWNER_ID",
        ""
    ).strip()

    if not _owner_raw:
        _legacy_admin = os.getenv(
            "ADMIN",
            ""
        ).split()

        if (
            _legacy_admin
            and _legacy_admin[0]
            .lstrip("-")
            .isdigit()
        ):
            _owner_raw = _legacy_admin[0]
        else:
            _owner_raw = "0"

    OWNER_ID = int(
        _owner_raw or "0"
    )

    # Compatibility field for older modules.
    # Authorization is still OWNER ONLY through helper.admin_access.
    ADMIN = []


    # =========================
    # FILE SIZE LIMIT
    # =========================

    # =========================
    # OPTIONAL AI RENAME
    # =========================

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_RENAME_MODEL = os.getenv("OPENAI_RENAME_MODEL", "gpt-5.6-sol").strip() or "gpt-5.6-sol"
    MAX_FILE_SIZE_BYTES = (
        2
        * 1024
        * 1024
        * 1024
    )


    @classmethod
    def validate(cls) -> list[str]:
        missing = []

        if cls.API_ID <= 0:
            missing.append("API_ID")

        if not cls.API_HASH:
            missing.append("API_HASH")

        if not cls.BOT_TOKEN:
            missing.append("BOT_TOKEN")

        if not cls.DATABASE_URL:
            missing.append("DATABASE_URL")

        return missing
