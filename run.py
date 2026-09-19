"""Run the AniToon health server and Telegram bot under a small supervisor.

The supervisor keeps either child process alive if it crashes. This helps with
transient Telegram/network/process failures. Render itself still controls the
service lifecycle, so a free Render service can still be restarted or spun
down by the platform.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("AniToonSupervisor")

CHILD_COMMANDS = {
    "health-server": [sys.executable, "app.py"],
    "telegram-bot": [sys.executable, "bot.py"],
}

children: dict[str, subprocess.Popen] = {}
restart_delay: dict[str, float] = {name: 2.0 for name in CHILD_COMMANDS}
_stopping = False


def _terminate_all() -> None:
    global _stopping
    if _stopping:
        return

    _stopping = True
    for name, process in list(children.items()):
        if process.poll() is None:
            log.info("Stopping %s...", name)
            try:
                process.terminate()
            except OSError:
                pass

    deadline = time.monotonic() + 10.0
    for name, process in list(children.items()):
        if process.poll() is None:
            try:
                process.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                log.warning("%s did not stop gracefully; killing it.", name)
                try:
                    process.kill()
                except OSError:
                    pass


def _signal_handler(signum, _frame) -> None:
    _terminate_all()
    raise SystemExit(128 + signum)


def _start_child(name: str) -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    command = CHILD_COMMANDS[name]

    log.info("Starting %s: %s", name, " ".join(command))
    children[name] = subprocess.Popen(command, env=env)
    restart_delay[name] = 2.0


def main() -> int:
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    for name in CHILD_COMMANDS:
        _start_child(name)

    try:
        while not _stopping:
            for name in CHILD_COMMANDS:
                process = children.get(name)
                if process is None:
                    _start_child(name)
                    continue

                code = process.poll()
                if code is None:
                    continue

                # Keep the deployment alive and recover from a child crash.
                delay = restart_delay[name]
                log.error(
                    "%s exited with code %s. Restarting in %.1f seconds.",
                    name,
                    code,
                    delay,
                )
                children.pop(name, None)
                if _stopping:
                    break

                time.sleep(delay)
                if _stopping:
                    break

                restart_delay[name] = min(delay * 2.0, 30.0)
                _start_child(name)

            time.sleep(1.0)

        return 0
    finally:
        _terminate_all()


if __name__ == "__main__":
    raise SystemExit(main())
