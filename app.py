from flask import Flask
import os
import time

app = Flask(__name__)

HEARTBEAT_FILE = os.environ.get(
    "ANITOON_HEARTBEAT_FILE",
    "/tmp/anitoon_1bot_heartbeat",
)
HEARTBEAT_TIMEOUT = max(
    15,
    int(os.environ.get("ANITOON_HEARTBEAT_TIMEOUT", "45")),
)


def _bot_is_healthy() -> bool:
    """Return True only while the Telegram bot has a fresh connectivity heartbeat."""
    try:
        age = time.time() - os.path.getmtime(HEARTBEAT_FILE)
        return 0 <= age <= HEARTBEAT_TIMEOUT
    except (FileNotFoundError, OSError):
        return False


@app.route("/")
def health_check():
    if not _bot_is_healthy():
        return "AniToon_1Bot: Telegram service temporarily offline 🔴", 503
    return "AniToon_1Bot: All Systems Operational 🟢"


@app.route("/health")
def health():
    if not _bot_is_healthy():
        return "BOT_OFFLINE", 503
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
