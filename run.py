"""AniToon deployment bootstrap.

The active GitHub repo currently keeps the original source bundle as a Git blob.
On startup, restore only files that are missing, then launch the health server
and Telegram bot.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE_ARCHIVE = ROOT / "AniToon_1Bot-source.zip"

children: list[subprocess.Popen] = []
_stopping = False


def _restore_missing_source() -> None:
    if not SOURCE_ARCHIVE.exists():
        raise FileNotFoundError(
            f"Missing source bundle: {SOURCE_ARCHIVE.name}"
        )

    prefix = "AniToon_1Bot-main/"

    with zipfile.ZipFile(SOURCE_ARCHIVE, "r") as archive:
        for info in archive.infolist():
            name = info.filename

            if not name.startswith(prefix):
                continue
            if name.endswith("/"):
                continue

            relative = Path(name[len(prefix):])

            # Never copy Python cache files from the development bundle.
            if "__pycache__" in relative.parts:
                continue

            target = ROOT / relative
            if target.exists():
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)


def _terminate_all() -> None:
    global _stopping

    if _stopping:
        return

    _stopping = True

    for process in reversed(children):
        if process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    deadline = time.time() + 10

    for process in reversed(children):
        if process.poll() is None:
            try:
                process.wait(timeout=max(0.1, deadline - time.time()))
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except OSError:
                    pass


def _signal_handler(signum, _frame) -> None:
    _terminate_all()
    raise SystemExit(128 + signum)


def main() -> int:
    os.chdir(ROOT)

    _restore_missing_source()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    env = os.environ.copy()

    children.append(
        subprocess.Popen(
            [sys.executable, "app.py"],
            env=env,
            cwd=ROOT,
        )
    )
    children.append(
        subprocess.Popen(
            [sys.executable, "bot.py"],
            env=env,
            cwd=ROOT,
        )
    )

    try:
        while True:
            for process in children:
                code = process.poll()
                if code is not None:
                    _terminate_all()
                    return int(code) if code else 1

            time.sleep(1)
    finally:
        _terminate_all()


if __name__ == "__main__":
    raise SystemExit(main())
