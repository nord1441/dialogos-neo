from __future__ import annotations

import errno
import os
import time
from contextlib import contextmanager
from pathlib import Path


class LockTimeout(Exception):
    pass


@contextmanager
def profile_lock(lock_path: Path, timeout: float = 0.0):
    """Atomic-create lockfile based mutual exclusion.

    `timeout=0` -> raise immediately if held. Otherwise poll until acquired
    or `timeout` seconds elapse.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    fd: int | None = None
    while True:
        try:
            fd = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            os.write(fd, str(os.getpid()).encode())
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise LockTimeout(str(lock_path))
            time.sleep(0.05)
        except OSError as e:
            if e.errno == errno.EEXIST:
                if time.monotonic() >= deadline:
                    raise LockTimeout(str(lock_path))
                time.sleep(0.05)
                continue
            raise

    try:
        yield
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
