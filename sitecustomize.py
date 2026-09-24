"""Early startup performance tuning for the AniToon deployment.

This module is loaded automatically by Python before the application starts.
It keeps performance tuning in one place without changing the public bot code.
"""

import asyncio
import functools
import inspect
import io
import math
import os
from hashlib import md5
from pathlib import PurePath


def _install_uvloop():
    """Use uvloop when available; safely keep asyncio on unsupported hosts."""
    try:
        import uvloop
        uvloop.install()
    except Exception:
        pass


def _patch_pyrogram_transmissions():
    """Increase Pyrogram's per-client transmission semaphore safely."""
    try:
        from pyrogram import Client
    except Exception:
        return

    if getattr(Client.__init__, "_anitoon_fast", False):
        return

    original_init = Client.__init__

    def fast_init(self, *args, **kwargs):
        kwargs.setdefault(
            "max_concurrent_transmissions",
            max(1, int(os.getenv("MAX_CONCURRENT_TRANSMISSIONS", "16"))),
        )
        return original_init(self, *args, **kwargs)

    fast_init._anitoon_fast = True
    Client.__init__ = fast_init


def _patch_pyrogram_upload_workers():
    """Use more concurrent SaveBigFilePart workers for large Telegram uploads.

    Pyrofork 2.3.x internally uses four upload workers for files above 10 MiB.
    AniToon keeps the same MTProto protocol and part size, but makes the worker
    count configurable so fast networks can keep more data in flight.
    """
    try:
        from pyrogram import Client, StopTransmission, raw
        from pyrogram.methods.advanced.save_file import SaveFile
        from pyrogram.session import Session
        import pyrogram
    except Exception:
        return

    if getattr(SaveFile.save_file, "_anitoon_parallel_upload", False):
        return

    original = SaveFile.save_file

    async def fast_save_file(
        self,
        path,
        file_id=None,
        file_part=0,
        progress=None,
        progress_args=(),
    ):
        async with self.save_file_semaphore:
            if path is None:
                return None

            async def worker(session):
                while True:
                    data = await queue.get()
                    if data is None:
                        return
                    try:
                        await session.invoke(data)
                    except Exception:
                        # Keep the upstream behavior: log the exception and let
                        # the upload finish/cleanup path continue.
                        import logging
                        logging.getLogger("AniToonUpload").exception("Telegram upload part failed")

            part_size = 512 * 1024

            if isinstance(path, (str, PurePath)):
                fp = open(path, "rb")
            elif isinstance(path, io.IOBase):
                fp = path
            else:
                raise ValueError(
                    "Invalid file. Expected a file path as string or a binary "
                    "(not text) file pointer"
                )

            file_name = getattr(fp, "name", "file.jpg")
            fp.seek(0, io.SEEK_END)
            file_size = fp.tell()
            fp.seek(0)

            if file_size == 0:
                raise ValueError("File size equals to 0 B")

            file_size_limit_mib = 4000 if self.me.is_premium else 2000
            if file_size > file_size_limit_mib * 1024 * 1024:
                raise ValueError(
                    f"Can't upload files bigger than {file_size_limit_mib} MiB"
                )

            file_total_parts = int(math.ceil(file_size / part_size))
            is_big = file_size > 10 * 1024 * 1024
            configured_workers = max(
                2,
                min(
                    12,
                    int(os.getenv("UPLOAD_PARALLEL_WORKERS", "8")),
                ),
            )
            workers_count = configured_workers if is_big else 1
            is_missing_part = file_id is not None
            file_id = file_id or self.rnd_id()
            md5_sum = md5() if not is_big and not is_missing_part else None

            session = Session(
                self,
                await self.storage.dc_id(),
                await self.storage.auth_key(),
                await self.storage.test_mode(),
                is_media=True,
            )
            workers = []
            queue = asyncio.Queue(max(2, workers_count))

            try:
                await session.start()

                # This is intentionally a single shared MTProto media session,
                # matching Pyrofork's upstream implementation. Multiple async
                # workers keep upload.SaveBigFilePart requests in flight without
                # creating cross-DC authorization races.
                workers = [
                    self.loop.create_task(worker(session))
                    for _ in range(workers_count)
                ]

                fp.seek(part_size * file_part)

                while True:
                    chunk = fp.read(part_size)
                    if not chunk:
                        if not is_big and not is_missing_part:
                            md5_sum = "".join(
                                [hex(i)[2:].zfill(2) for i in md5_sum.digest()]
                            )
                        break

                    if is_big:
                        rpc = raw.functions.upload.SaveBigFilePart(
                            file_id=file_id,
                            file_part=file_part,
                            file_total_parts=file_total_parts,
                            bytes=chunk,
                        )
                    else:
                        rpc = raw.functions.upload.SaveFilePart(
                            file_id=file_id,
                            file_part=file_part,
                            bytes=chunk,
                        )

                    await queue.put(rpc)

                    if is_missing_part:
                        return

                    if not is_big and not is_missing_part:
                        md5_sum.update(chunk)

                    file_part += 1

                    if progress:
                        func = functools.partial(
                            progress,
                            min(file_part * part_size, file_size),
                            file_size,
                            *progress_args,
                        )
                        if inspect.iscoroutinefunction(progress):
                            await func()
                        else:
                            await self.loop.run_in_executor(self.executor, func)

            except StopTransmission:
                raise
            except Exception:
                import logging
                logging.getLogger("AniToonUpload").exception(
                    "Telegram file upload failed"
                )
            else:
                if is_big:
                    return raw.types.InputFileBig(
                        id=file_id,
                        parts=file_total_parts,
                        name=file_name,
                    )
                return raw.types.InputFile(
                    id=file_id,
                    parts=file_total_parts,
                    name=file_name,
                    md5_checksum=md5_sum,
                )
            finally:
                for _ in workers:
                    await queue.put(None)

                if workers:
                    await asyncio.gather(*workers)

                await session.stop()

                if isinstance(path, (str, PurePath)):
                    fp.close()

    fast_save_file._anitoon_parallel_upload = True
    SaveFile.save_file = fast_save_file

    # Client.save_file resolves through the same method in supported Pyrofork
    # versions, but patch it explicitly for compatibility with method binding.
    try:
        Client.save_file = fast_save_file
    except Exception:
        pass

    import logging
    logging.getLogger("AniToonUpload").info(
        "Parallel upload workers enabled: %s",
        max(2, min(12, int(os.getenv("UPLOAD_PARALLEL_WORKERS", "8")))),
    )


_install_uvloop()
_patch_pyrogram_transmissions()
_patch_pyrogram_upload_workers()
