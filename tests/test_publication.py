from __future__ import annotations

import errno
from pathlib import Path

import pytest

from stellaris_mod_translator import publication
from stellaris_mod_translator.publication import AtomicPublicationUnavailable


class FakeRename:
    argtypes: object = None
    restype: object = None

    def __call__(self, source: bytes, destination: bytes, flags: int) -> int:
        return -1


class FakeLibrary:
    renamex_np = FakeRename()


@pytest.mark.parametrize("error_number", [errno.ENOTSUP, errno.EOPNOTSUPP])
def test_unsupported_renamex_np_error_is_mapped(
    monkeypatch: pytest.MonkeyPatch,
    error_number: int,
) -> None:
    monkeypatch.setattr(publication.sys, "platform", "darwin")
    monkeypatch.setattr(
        publication.ctypes, "CDLL", lambda *args, **kwargs: FakeLibrary()
    )
    monkeypatch.setattr(
        publication.ctypes, "get_errno", lambda: error_number
    )

    with pytest.raises(AtomicPublicationUnavailable, match="unsupported"):
        publication.atomic_publish_directory_no_replace(
            Path("/tmp/source"), Path("/tmp/destination")
        )
