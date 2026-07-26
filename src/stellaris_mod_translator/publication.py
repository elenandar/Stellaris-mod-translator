"""Fail-closed atomic publication for a newly created candidate directory."""

from __future__ import annotations

import ctypes
import errno
import os
from pathlib import Path
import sys


_RENAME_EXCL = 0x00000004


class AtomicPublicationUnavailable(RuntimeError):
    """The host does not expose the required no-replace primitive."""


class DestinationExistsError(RuntimeError):
    """The destination appeared before the atomic publication step."""


def atomic_publish_directory_no_replace(source: Path, destination: Path) -> None:
    """Atomically rename ``source`` without replacing any destination object."""
    if sys.platform != "darwin":
        raise AtomicPublicationUnavailable("renamex_np(RENAME_EXCL) is unavailable")

    library = ctypes.CDLL(None, use_errno=True)
    try:
        renamex_np = library.renamex_np
    except AttributeError as exc:
        raise AtomicPublicationUnavailable(
            "renamex_np(RENAME_EXCL) is unavailable"
        ) from exc

    renamex_np.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
    renamex_np.restype = ctypes.c_int
    result = renamex_np(
        os.fsencode(source),
        os.fsencode(destination),
        _RENAME_EXCL,
    )
    if result == 0:
        return

    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise DestinationExistsError("destination already exists")
    if error_number in {errno.ENOTSUP, errno.EOPNOTSUPP}:
        raise AtomicPublicationUnavailable(
            "renamex_np(RENAME_EXCL) is unsupported"
        )
    raise OSError(
        error_number,
        os.strerror(error_number),
        os.fspath(destination),
    )
