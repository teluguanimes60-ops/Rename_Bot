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

    # Archive/log backup channel
    ARCHIVE_CHANNEL_ID = -1004491486679

    # Start image
    START_PIC = ""

    # Web/health server
    PORT = 10000


    # =========================
    # PYROGRAM
    # =========================

    PYROGRAM_WORKERS = 32


    # =========================
    # JOB / QUEUE SETTINGS
    # =========================

    MAX_ACTIVE_JOBS = 100

    MAX_CONCURRENT_TRANSMISSIONS = 3

    MAX_CONCURRENT_PROCESSING = 2


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
    #
    # Preferred:
    # OWNER_ID=123456789
    #
    # Backward compatibility:
    # If OWNER_ID is not set, the first
    # numeric value from ADMIN is used.
    #
    # ADMIN does NOT create multiple admins.
    #

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


    # =========================
    # FILE SIZE LIMIT
    # =========================
    #
    # Maximum incoming file:
    # 2 GiB
    #

    MAX_FILE_SIZE_BYTES = (
        2
        * 1024
        * 1024
        * 1024
    )
