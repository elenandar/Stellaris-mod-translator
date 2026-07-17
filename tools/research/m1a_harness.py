#!/usr/bin/env python3
"""M1A research-only, fail-closed filesystem and byte evidence spike.

This module deliberately does not translate, normalize, or expose source text.
It keeps the bytes it reads in memory, returns them unchanged for the identity
round trip, and emits only aggregate/redacted evidence.  Candidate writes need
an explicitly sealed disposable root that is disjoint from every protected
root supplied by the caller.

The code is intentionally Python 3.9 standard-library only.  It is evidence
for M1A, not the production parser, CLI, or publisher planned for later gates.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import unicodedata
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


UTF8_BOM = b"\xef\xbb\xbf"
READ_CHUNK_SIZE = 64 * 1024
DEFAULT_MAX_SOURCE_BYTES = 64 * 1024 * 1024
MANIFEST_NAME = "manifest.json"
STAGED_MANIFEST_NAME = ".m1a-manifest.pending"
PAYLOAD_NAME_TEMPLATE = "payload-{index:06d}.bin"
REDACTED_SCHEMA = "m1a-redacted-evidence-v1"
CANDIDATE_SCHEMA = "m1a-research-candidate-v1"
CONTENT_GENERATION_SCHEMA = "m1a-content-generation-v1"
CANDIDATE_SOURCE_SCHEMA = "m1a-candidate-source-v1"
_FORMATTING_CODE_ALLOWLIST = frozenset({"Y"})

_ERROR_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class HarnessError(RuntimeError):
    """A deliberately path- and content-free failure."""

    def __init__(self, code: str) -> None:
        if not _ERROR_CODE_RE.fullmatch(code):
            code = "INTERNAL_ERROR"
        self.code = code
        super().__init__(code)


class SimulatedCrash(BaseException):
    """Test-only abrupt-stop signal; build code intentionally does not catch it."""

    def __init__(self, checkpoint: str) -> None:
        self.checkpoint = checkpoint
        super().__init__("SIMULATED_CRASH")


@dataclass(frozen=True)
class MarkupCounts:
    placeholders: int = 0
    icons: int = 0
    formatting_spans: int = 0
    scripted_localisation: int = 0
    unknown_or_ambiguous: int = 0

    def add(self, other: "MarkupCounts") -> "MarkupCounts":
        return MarkupCounts(
            placeholders=self.placeholders + other.placeholders,
            icons=self.icons + other.icons,
            formatting_spans=self.formatting_spans + other.formatting_spans,
            scripted_localisation=(
                self.scripted_localisation + other.scripted_localisation
            ),
            unknown_or_ambiguous=(
                self.unknown_or_ambiguous + other.unknown_or_ambiguous
            ),
        )

    def public_dict(self) -> Dict[str, int]:
        return {
            "formatting_spans": self.formatting_spans,
            "icons": self.icons,
            "placeholders": self.placeholders,
            "scripted_localisation": self.scripted_localisation,
            "unknown_or_ambiguous": self.unknown_or_ambiguous,
        }


@dataclass(frozen=True)
class FormatInventory:
    byte_count: int
    sha256: str
    utf8_valid: bool
    bom_at_start: bool
    hidden_bom_count: int
    newline_style: str
    final_newline: bool
    line_count: int
    language_header_lines: int
    comment_lines: int
    blank_lines: int
    whitespace_lines: int
    entry_lines: int
    version_suffix_occurrences: int
    quoted_value_occurrences: int
    escape_occurrences: int
    escaped_newline_occurrences: int
    escaped_quote_occurrences: int
    escaped_backslash_occurrences: int
    unknown_escape_occurrences: int
    empty_value_occurrences: int
    duplicate_key_groups: int
    duplicate_key_occurrences: int
    malformed_lines: int
    unknown_lines: int
    opaque_constructs: int
    markup: MarkupCounts

    def public_dict(self) -> Dict[str, Any]:
        return {
            "blank_lines": self.blank_lines,
            "bom_at_start": self.bom_at_start,
            "byte_count": self.byte_count,
            "comment_lines": self.comment_lines,
            "duplicate_key_groups": self.duplicate_key_groups,
            "duplicate_key_occurrences": self.duplicate_key_occurrences,
            "empty_value_occurrences": self.empty_value_occurrences,
            "entry_lines": self.entry_lines,
            "escape_occurrences": self.escape_occurrences,
            "escaped_backslash_occurrences": self.escaped_backslash_occurrences,
            "escaped_newline_occurrences": self.escaped_newline_occurrences,
            "escaped_quote_occurrences": self.escaped_quote_occurrences,
            "final_newline": self.final_newline,
            "hidden_bom_count": self.hidden_bom_count,
            "language_header_lines": self.language_header_lines,
            "line_count": self.line_count,
            "malformed_lines": self.malformed_lines,
            "markup": self.markup.public_dict(),
            "newline_style": self.newline_style,
            "opaque_constructs": self.opaque_constructs,
            "quoted_value_occurrences": self.quoted_value_occurrences,
            "sha256": self.sha256,
            "unknown_lines": self.unknown_lines,
            "unknown_escape_occurrences": self.unknown_escape_occurrences,
            "utf8_valid": self.utf8_valid,
            "version_suffix_occurrences": self.version_suffix_occurrences,
            "whitespace_lines": self.whitespace_lines,
        }


@dataclass(frozen=True)
class ResearchDocument:
    """Opaque raw bytes plus aggregate observations; identity render only."""

    inventory: FormatInventory
    _raw: bytes = field(repr=False)

    def render_identity(self) -> bytes:
        return self._raw


@dataclass(frozen=True)
class _EntryObservation:
    key: Optional[str]
    version_suffix: bool
    quoted: bool
    escape_count: int
    empty_value: bool
    malformed: bool
    unknown: bool
    markup: MarkupCounts
    escaped_newlines: int = 0
    escaped_quotes: int = 0
    escaped_backslashes: int = 0
    unknown_escapes: int = 0


def _newline_style(data: bytes) -> str:
    crlf = data.count(b"\r\n")
    bare_lf = data.count(b"\n") - crlf
    bare_cr = data.count(b"\r") - crlf
    kinds = sum(value > 0 for value in (crlf, bare_lf, bare_cr))
    if kinds == 0:
        return "none"
    if kinds > 1:
        return "mixed"
    if crlf:
        return "CRLF"
    if bare_lf:
        return "LF"
    return "CR"


def _strip_line_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return line[:-2]
    if line.endswith("\r") or line.endswith("\n"):
        return line[:-1]
    return line


def _identifier_is_conservative(value: str) -> bool:
    if not value:
        return False
    return all(character.isascii() and (character.isalnum() or character in "_.-") for character in value)


def _observe_markup(value: str) -> MarkupCounts:
    # Escape semantics are not established by M1A public evidence.  Mask an
    # escaped delimiter and classify it as ambiguous instead of guessing.
    masked: List[str] = []
    escaped_markup = 0
    cursor = 0
    while cursor < len(value):
        if (
            value[cursor] == "\\"
            and cursor + 1 < len(value)
            and value[cursor + 1] in "$£[]§"
        ):
            masked.extend(("\\", "\x00"))
            escaped_markup += 1
            cursor += 2
            continue
        masked.append(value[cursor])
        cursor += 1
    observed = "".join(masked)
    placeholders = 0
    icons = 0
    scripted = 0
    formatting = 0
    unknown = escaped_markup
    formatting_depth = 0
    cursor = 0
    while cursor < len(observed):
        character = observed[cursor]
        if character in "$£":
            end = observed.find(character, cursor + 1)
            if end < 0:
                unknown += 1
                break
            inner = observed[cursor + 1 : end]
            valid_payload = bool(inner) and all(
                item.isascii() and (item.isalnum() or item in "_.:-")
                for item in inner
            )
            if valid_payload:
                if character == "$":
                    placeholders += 1
                else:
                    icons += 1
            else:
                unknown += 1
            cursor = end + 1
            continue
        if character == "[":
            end = observed.find("]", cursor + 1)
            if end < 0:
                unknown += 1
                break
            inner = observed[cursor + 1 : end]
            valid_payload = bool(inner) and all(
                item.isascii() and (item.isalnum() or item in "_.:-")
                for item in inner
            )
            if valid_payload:
                scripted += 1
            else:
                unknown += 1
            cursor = end + 1
            continue
        if character == "]":
            unknown += 1
            cursor += 1
            continue
        if character == "§":
            if cursor + 1 >= len(observed):
                unknown += 1
                break
            code = observed[cursor + 1]
            if code == "!":
                if formatting_depth:
                    formatting_depth -= 1
                    formatting += 1
                else:
                    unknown += 1
            elif code in _FORMATTING_CODE_ALLOWLIST:
                formatting_depth += 1
            else:
                unknown += 1
            cursor += 2
            continue
        cursor += 1
    unknown += formatting_depth
    return MarkupCounts(
        placeholders=placeholders,
        icons=icons,
        formatting_spans=formatting,
        scripted_localisation=scripted,
        unknown_or_ambiguous=unknown,
    )


def _observe_entry(body: str) -> _EntryObservation:
    stripped = body.lstrip(" \t")
    if stripped == body:
        return _EntryObservation(None, False, False, 0, False, False, True, MarkupCounts())

    colon = stripped.find(":")
    if colon <= 0:
        return _EntryObservation(None, False, False, 0, False, False, True, MarkupCounts())
    key = stripped[:colon]
    if not _identifier_is_conservative(key):
        return _EntryObservation(None, False, False, 0, False, False, True, MarkupCounts())

    remainder = stripped[colon + 1 :]
    suffix_length = 0
    while (
        suffix_length < len(remainder)
        and remainder[suffix_length].isascii()
        and remainder[suffix_length].isdigit()
    ):
        suffix_length += 1
    version_suffix = suffix_length > 0
    remainder = remainder[suffix_length:].lstrip(" \t")
    if not remainder.startswith('"'):
        return _EntryObservation(key, version_suffix, False, 0, False, True, False, MarkupCounts())

    escaped = False
    escape_count = 0
    escaped_newlines = 0
    escaped_quotes = 0
    escaped_backslashes = 0
    unknown_escapes = 0
    closing_quote = -1
    cursor = 1
    while cursor < len(remainder):
        character = remainder[cursor]
        if escaped:
            escaped = False
            cursor += 1
            continue
        if character == "\\":
            escaped = True
            escape_count += 1
            if cursor + 1 >= len(remainder):
                unknown_escapes += 1
            else:
                escaped_character = remainder[cursor + 1]
                if escaped_character == "n":
                    escaped_newlines += 1
                elif escaped_character == '"':
                    escaped_quotes += 1
                elif escaped_character == "\\":
                    escaped_backslashes += 1
                else:
                    unknown_escapes += 1
            cursor += 1
            continue
        if character == '"':
            closing_quote = cursor
            break
        cursor += 1

    if closing_quote < 0:
        return _EntryObservation(key, version_suffix, True, escape_count, False, True, False, MarkupCounts())

    trailing = remainder[closing_quote + 1 :].strip(" \t")
    if trailing:
        return _EntryObservation(key, version_suffix, True, escape_count, False, True, False, MarkupCounts())

    value = remainder[1:closing_quote]
    markup = _observe_markup(value)
    return _EntryObservation(
        key=key,
        version_suffix=version_suffix,
        quoted=True,
        escape_count=escape_count,
        empty_value=(value == ""),
        malformed=False,
        unknown=False,
        markup=markup,
        escaped_newlines=escaped_newlines,
        escaped_quotes=escaped_quotes,
        escaped_backslashes=escaped_backslashes,
        unknown_escapes=unknown_escapes,
    )


def inspect_bytes(data: bytes) -> ResearchDocument:
    """Observe bytes without transforming them or exposing text spans."""

    raw = bytes(data)
    digest = hashlib.sha256(raw).hexdigest()
    bom_at_start = raw.startswith(UTF8_BOM)
    hidden_bom_count = raw[len(UTF8_BOM) if bom_at_start else 0 :].count(UTF8_BOM)
    final_newline = raw.endswith((b"\n", b"\r"))
    raw_lines = raw.splitlines(keepends=True)

    try:
        text = raw.decode("utf-8")
        utf8_valid = True
    except UnicodeDecodeError:
        text = ""
        utf8_valid = False

    language_headers = 0
    comments = 0
    blanks = 0
    whitespace_lines = 0
    entries = 0
    suffixes = 0
    quoted = 0
    escapes = 0
    escaped_newlines = 0
    escaped_quotes = 0
    escaped_backslashes = 0
    unknown_escapes = 0
    empty_values = 0
    malformed = 0
    unknown = 0
    opaque = 0
    markup = MarkupCounts()
    key_counts: Dict[str, int] = {}

    if utf8_valid:
        lines = text.splitlines(keepends=True)
        for index, raw_line in enumerate(lines):
            body = _strip_line_ending(raw_line)
            if index == 0 and body.startswith("\ufeff"):
                body = body[1:]
            if body != body.strip(" \t"):
                whitespace_lines += 1
            stripped = body.strip(" \t")
            if not stripped:
                blanks += 1
                continue
            if stripped.startswith("#"):
                comments += 1
                continue
            if (
                body == stripped
                and stripped.startswith("l_")
                and stripped.endswith(":")
                and _identifier_is_conservative(stripped[:-1])
            ):
                language_headers += 1
                continue

            observation = _observe_entry(body)
            if observation.unknown:
                unknown += 1
                opaque += 1
                continue
            if observation.malformed:
                malformed += 1
                opaque += 1
                continue
            entries += 1
            suffixes += int(observation.version_suffix)
            quoted += int(observation.quoted)
            escapes += observation.escape_count
            escaped_newlines += observation.escaped_newlines
            escaped_quotes += observation.escaped_quotes
            escaped_backslashes += observation.escaped_backslashes
            unknown_escapes += observation.unknown_escapes
            empty_values += int(observation.empty_value)
            markup = markup.add(observation.markup)
            opaque += observation.markup.unknown_or_ambiguous + observation.unknown_escapes
            if observation.key is not None:
                key_counts[observation.key] = key_counts.get(observation.key, 0) + 1
    else:
        unknown = len(raw_lines) if raw_lines else int(bool(raw))
        opaque = unknown

    duplicate_groups = sum(count > 1 for count in key_counts.values())
    duplicate_occurrences = sum(count for count in key_counts.values() if count > 1)
    inventory = FormatInventory(
        byte_count=len(raw),
        sha256=digest,
        utf8_valid=utf8_valid,
        bom_at_start=bom_at_start,
        hidden_bom_count=hidden_bom_count,
        newline_style=_newline_style(raw),
        final_newline=final_newline,
        line_count=len(raw_lines),
        language_header_lines=language_headers,
        comment_lines=comments,
        blank_lines=blanks,
        whitespace_lines=whitespace_lines,
        entry_lines=entries,
        version_suffix_occurrences=suffixes,
        quoted_value_occurrences=quoted,
        escape_occurrences=escapes,
        escaped_newline_occurrences=escaped_newlines,
        escaped_quote_occurrences=escaped_quotes,
        escaped_backslash_occurrences=escaped_backslashes,
        unknown_escape_occurrences=unknown_escapes,
        empty_value_occurrences=empty_values,
        duplicate_key_groups=duplicate_groups,
        duplicate_key_occurrences=duplicate_occurrences,
        malformed_lines=malformed,
        unknown_lines=unknown,
        opaque_constructs=opaque,
        markup=markup,
    )
    return ResearchDocument(inventory=inventory, _raw=raw)


@dataclass(frozen=True)
class _GenerationSignature:
    device: int
    inode: int
    mode: int
    size: int
    mtime_ns: int
    ctime_ns: int

    @classmethod
    def from_stat(cls, metadata: os.stat_result) -> "_GenerationSignature":
        return cls(
            device=metadata.st_dev,
            inode=metadata.st_ino,
            mode=stat.S_IFMT(metadata.st_mode),
            size=metadata.st_size,
            mtime_ns=metadata.st_mtime_ns,
            ctime_ns=metadata.st_ctime_ns,
        )

    def opaque_digest(self, content_sha256: str) -> str:
        material = (
            f"{self.device}:{self.inode}:{self.mode}:{self.size}:"
            f"{self.mtime_ns}:{self.ctime_ns}:{content_sha256}"
        ).encode("ascii")
        return hashlib.sha256(material).hexdigest()


ReadHook = Callable[[str, int, int], None]
ReadFunction = Callable[[int, int, int, int], bytes]


def _path_has_traversal(path: Path) -> bool:
    return any(part == ".." for part in path.parts)


def _canonical_source_file(path_value: os.PathLike[str]) -> Path:
    path = Path(path_value)
    if not path.is_absolute() or _path_has_traversal(path):
        raise HarnessError("AMBIGUOUS_SOURCE_PATH")
    try:
        raw_metadata = os.lstat(str(path))
        if stat.S_ISLNK(raw_metadata.st_mode):
            raise HarnessError("SOURCE_SYMLINK_REJECTED")
        canonical = path.resolve(strict=True)
        canonical_metadata = os.lstat(str(canonical))
    except HarnessError:
        raise
    except OSError:
        raise HarnessError("SOURCE_UNAVAILABLE")
    if stat.S_ISLNK(canonical_metadata.st_mode):
        raise HarnessError("SOURCE_SYMLINK_REJECTED")
    if not stat.S_ISREG(canonical_metadata.st_mode):
        raise HarnessError("UNSUPPORTED_SOURCE_TYPE")
    return canonical


def _default_reader(fd: int, requested: int, _pass_index: int, _chunk_index: int) -> bytes:
    return os.read(fd, requested)


def _call_read_hook(
    hook: Optional[ReadHook], event: str, pass_index: int = 0, chunk_index: int = 0
) -> None:
    if hook is not None:
        hook(event, pass_index, chunk_index)


def _read_fd_pass(
    fd: int,
    expected_size: int,
    chunk_size: int,
    pass_index: int,
    reader: ReadFunction,
    hook: Optional[ReadHook],
) -> bytes:
    chunks: List[bytes] = []
    total = 0
    chunk_index = 0
    while True:
        piece = reader(fd, chunk_size, pass_index, chunk_index)
        if not isinstance(piece, bytes):
            raise HarnessError("INVALID_READER_RESULT")
        if not piece:
            break
        chunks.append(piece)
        total += len(piece)
        if total > expected_size:
            raise HarnessError("GENERATION_MISMATCH")
        _call_read_hook(hook, "after_chunk", pass_index, chunk_index)
        chunk_index += 1
    return b"".join(chunks)


@dataclass(frozen=True)
class StableRead:
    byte_count: int
    sha256: str
    generation_sha256: str
    _data: bytes = field(repr=False)

    @property
    def data(self) -> bytes:
        return self._data


def read_stable_file(
    path: os.PathLike[str],
    *,
    max_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
    chunk_size: int = READ_CHUNK_SIZE,
    hook: Optional[ReadHook] = None,
    reader: ReadFunction = _default_reader,
) -> StableRead:
    """Read twice through one descriptor and abort on any observed generation drift."""

    if max_bytes <= 0 or chunk_size <= 0:
        raise HarnessError("INVALID_READ_LIMIT")
    canonical = _canonical_source_file(path)
    try:
        before_path = _GenerationSignature.from_stat(os.lstat(str(canonical)))
        _call_read_hook(hook, "after_metadata")
        flags = os.O_RDONLY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(canonical), flags)
    except HarnessError:
        raise
    except OSError:
        raise HarnessError("SOURCE_OPEN_FAILED")

    try:
        opened = _GenerationSignature.from_stat(os.fstat(fd))
        if opened != before_path:
            raise HarnessError("GENERATION_MISMATCH")
        if opened.mode != stat.S_IFREG:
            raise HarnessError("UNSUPPORTED_SOURCE_TYPE")
        if opened.size > max_bytes:
            raise HarnessError("SOURCE_SIZE_LIMIT")
        _call_read_hook(hook, "after_open")

        first = _read_fd_pass(fd, opened.size, chunk_size, 1, reader, hook)
        after_first = _GenerationSignature.from_stat(os.fstat(fd))
        if after_first != opened:
            raise HarnessError("GENERATION_MISMATCH")
        if len(first) != opened.size:
            raise HarnessError("PARTIAL_READ")
        _call_read_hook(hook, "after_first_pass")

        os.lseek(fd, 0, os.SEEK_SET)
        second = _read_fd_pass(fd, opened.size, chunk_size, 2, reader, hook)
        after_second = _GenerationSignature.from_stat(os.fstat(fd))
        if after_second != opened:
            raise HarnessError("GENERATION_MISMATCH")
        if len(second) != opened.size:
            raise HarnessError("PARTIAL_READ")
        if first != second:
            raise HarnessError("GENERATION_MISMATCH")
        _call_read_hook(hook, "before_path_recheck")

        try:
            after_path_raw = os.lstat(str(canonical))
        except OSError:
            raise HarnessError("GENERATION_MISMATCH")
        if stat.S_ISLNK(after_path_raw.st_mode):
            raise HarnessError("GENERATION_MISMATCH")
        after_path = _GenerationSignature.from_stat(after_path_raw)
        if after_path != opened:
            raise HarnessError("GENERATION_MISMATCH")
        digest = hashlib.sha256(first).hexdigest()
        return StableRead(
            byte_count=len(first),
            sha256=digest,
            generation_sha256=opened.opaque_digest(digest),
            _data=first,
        )
    except HarnessError:
        raise
    except OSError:
        raise HarnessError("SOURCE_READ_FAILED")
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def _opaque_path_id(path: Path) -> str:
    digest = hashlib.sha256(os.fsencode(str(path))).hexdigest()
    return "src-" + digest[:16]


def _normalise_relative_path(value: str) -> Tuple[str, str]:
    if not value or "\\" in value or "\x00" in value:
        raise HarnessError("INVALID_RELATIVE_PATH")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise HarnessError("INVALID_RELATIVE_PATH")
    normalised = relative.as_posix()
    reserved = {
        unicodedata.normalize("NFC", MANIFEST_NAME).casefold(),
        unicodedata.normalize("NFC", STAGED_MANIFEST_NAME).casefold(),
    }
    if unicodedata.normalize("NFC", normalised).casefold() in reserved:
        raise HarnessError("RESERVED_RELATIVE_PATH")
    collision_key = unicodedata.normalize("NFC", normalised).casefold()
    return normalised, collision_key


@dataclass(frozen=True)
class SourceRequest:
    path: Path = field(repr=False)
    relative_path: str = field(repr=False)


@dataclass(frozen=True)
class SnapshotBlob:
    opaque_source_id: str
    relative_path: str = field(repr=False)
    byte_count: int
    sha256: str
    generation_sha256: str
    content_generation_sha256: str
    inventory: FormatInventory
    _data: bytes = field(repr=False)

    @property
    def data(self) -> bytes:
        return self._data


def _content_generation_sha256(byte_count: int, content_sha256: str) -> str:
    """Return metadata-independent identity for accepted immutable bytes."""

    record = {
        "schema": CONTENT_GENERATION_SCHEMA,
        "sha256": content_sha256,
        "size": byte_count,
    }
    encoded = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def snapshot_sources(
    requests: Sequence[SourceRequest],
    *,
    max_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
    hook_factory: Optional[Callable[[int], Optional[ReadHook]]] = None,
    reader_factory: Optional[Callable[[int], ReadFunction]] = None,
) -> Tuple[SnapshotBlob, ...]:
    """Create in-memory content-addressed blobs after generation-stable reads."""

    prepared: List[Tuple[Path, str]] = []
    collision_keys: Dict[str, bool] = {}
    structural_keys: List[Tuple[str, ...]] = []
    parent_spellings: Dict[Tuple[str, ...], Tuple[str, ...]] = {}
    for request in requests:
        normalised, collision_key = _normalise_relative_path(request.relative_path)
        if collision_key in collision_keys:
            raise HarnessError("DUPLICATE_RELATIVE_PATH")
        relative = PurePosixPath(normalised)
        raw_parts = tuple(relative.parts)
        key_parts = tuple(
            unicodedata.normalize("NFC", part).casefold() for part in raw_parts
        )
        for depth in range(1, len(key_parts)):
            key_prefix = key_parts[:depth]
            raw_prefix = raw_parts[:depth]
            previous = parent_spellings.get(key_prefix)
            if previous is not None and previous != raw_prefix:
                raise HarnessError("AMBIGUOUS_RELATIVE_PATH")
            parent_spellings[key_prefix] = raw_prefix
        for existing in structural_keys:
            common = min(len(existing), len(key_parts))
            if existing[:common] == key_parts[:common] and len(existing) != len(key_parts):
                raise HarnessError("RELATIVE_PATH_TYPE_CONFLICT")
        collision_keys[collision_key] = True
        structural_keys.append(key_parts)
        prepared.append((Path(request.path), normalised))

    canonical_prepared: List[Tuple[Path, str]] = []
    source_identities: Dict[Tuple[int, int], bool] = {}
    for path, relative_path in prepared:
        canonical = _canonical_source_file(path)
        try:
            metadata = os.lstat(str(canonical))
        except OSError:
            raise HarnessError("SOURCE_UNAVAILABLE")
        identity = (metadata.st_dev, metadata.st_ino)
        if identity in source_identities:
            raise HarnessError("SOURCE_IDENTITY_ALIAS")
        source_identities[identity] = True
        canonical_prepared.append((canonical, relative_path))

    snapshots: List[SnapshotBlob] = []
    for index, (canonical, relative_path) in enumerate(canonical_prepared):
        hook = hook_factory(index) if hook_factory is not None else None
        reader = reader_factory(index) if reader_factory is not None else _default_reader
        stable = read_stable_file(
            canonical,
            max_bytes=max_bytes,
            hook=hook,
            reader=reader,
        )
        document = inspect_bytes(stable.data)
        snapshots.append(
            SnapshotBlob(
                opaque_source_id=_opaque_path_id(canonical),
                relative_path=relative_path,
                byte_count=stable.byte_count,
                sha256=stable.sha256,
                generation_sha256=stable.generation_sha256,
                content_generation_sha256=_content_generation_sha256(
                    stable.byte_count, stable.sha256
                ),
                inventory=document.inventory,
                _data=stable.data,
            )
        )
    return tuple(snapshots)


def _combined_snapshot_hash(blobs: Sequence[SnapshotBlob]) -> str:
    records = sorted(
        (
            blob.opaque_source_id,
            blob.sha256,
            blob.generation_sha256,
            blob.byte_count,
        )
        for blob in blobs
    )
    encoded = json.dumps(records, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def snapshot_manifest(blobs: Sequence[SnapshotBlob]) -> str:
    """Return one opaque generation hash suitable for pre/post comparison."""

    return _combined_snapshot_hash(blobs)


def _aggregate_inventory(blobs: Sequence[SnapshotBlob]) -> Dict[str, Any]:
    styles: Dict[str, int] = {"CR": 0, "CRLF": 0, "LF": 0, "mixed": 0, "none": 0}
    totals: Dict[str, int] = {
        "blank_lines": 0,
        "comment_lines": 0,
        "duplicate_key_groups": 0,
        "duplicate_key_occurrences": 0,
        "empty_value_occurrences": 0,
        "entry_lines": 0,
        "escape_occurrences": 0,
        "escaped_backslash_occurrences": 0,
        "escaped_newline_occurrences": 0,
        "escaped_quote_occurrences": 0,
        "hidden_bom_count": 0,
        "language_header_lines": 0,
        "line_count": 0,
        "malformed_lines": 0,
        "opaque_constructs": 0,
        "quoted_value_occurrences": 0,
        "unknown_lines": 0,
        "unknown_escape_occurrences": 0,
        "version_suffix_occurrences": 0,
        "whitespace_lines": 0,
    }
    markup = MarkupCounts()
    files_with_bom = 0
    files_with_final_newline = 0
    utf8_valid_files = 0
    for blob in blobs:
        inventory = blob.inventory
        styles[inventory.newline_style] += 1
        files_with_bom += int(inventory.bom_at_start)
        files_with_final_newline += int(inventory.final_newline)
        utf8_valid_files += int(inventory.utf8_valid)
        for key in totals:
            totals[key] += int(getattr(inventory, key))
        markup = markup.add(inventory.markup)
    result: Dict[str, Any] = dict(totals)
    result.update(
        {
            "files_with_bom": files_with_bom,
            "files_with_final_newline": files_with_final_newline,
            "markup": markup.public_dict(),
            "newline_styles": styles,
            "utf8_invalid_files": len(blobs) - utf8_valid_files,
            "utf8_valid_files": utf8_valid_files,
        }
    )
    return result


def redacted_evidence(blobs: Sequence[SnapshotBlob]) -> Dict[str, Any]:
    return {
        "combined_generation_sha256": _combined_snapshot_hash(blobs),
        "file_count": len(blobs),
        "inventory": _aggregate_inventory(blobs),
        "schema": REDACTED_SCHEMA,
        "status": "ok",
        "total_bytes": sum(blob.byte_count for blob in blobs),
    }


@dataclass(frozen=True)
class LeakageCheck:
    checked_sequence_count: int
    leak_detected: bool

    def public_dict(self) -> Dict[str, Any]:
        return {
            "checked_sequence_count": self.checked_sequence_count,
            "leak_detected": self.leak_detected,
        }


def leakage_check(
    public_bytes: bytes,
    forbidden_sequences: Iterable[bytes],
    *,
    minimum_length: int = 4,
) -> LeakageCheck:
    """Check for exact forbidden sequences without returning the matched value."""

    checked = 0
    detected = False
    for sequence in forbidden_sequences:
        candidate = bytes(sequence)
        if len(candidate) < minimum_length:
            continue
        checked += 1
        if candidate in public_bytes:
            detected = True
    return LeakageCheck(checked_sequence_count=checked, leak_detected=detected)


def render_redacted_evidence(
    blobs: Sequence[SnapshotBlob],
    *,
    additional_forbidden: Iterable[bytes] = (),
) -> Tuple[bytes, LeakageCheck]:
    payload = json.dumps(
        redacted_evidence(blobs),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii") + b"\n"
    forbidden = [blob.data for blob in blobs]
    forbidden.extend(additional_forbidden)
    result = leakage_check(payload, forbidden)
    if result.leak_detected:
        raise HarnessError("LEAKAGE_DETECTED")
    return payload, result


def _canonical_existing_directory(path_value: os.PathLike[str], role: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute() or _path_has_traversal(path):
        raise HarnessError("AMBIGUOUS_ROOT_PATH")
    try:
        supplied = os.lstat(str(path))
        if stat.S_ISLNK(supplied.st_mode):
            raise HarnessError("ROOT_SYMLINK_REJECTED")
        canonical = path.resolve(strict=True)
        metadata = os.lstat(str(canonical))
    except HarnessError:
        raise
    except OSError:
        raise HarnessError("ROOT_UNAVAILABLE")
    if stat.S_ISLNK(metadata.st_mode):
        raise HarnessError("ROOT_SYMLINK_REJECTED")
    if not stat.S_ISDIR(metadata.st_mode):
        raise HarnessError("ROOT_NOT_DIRECTORY")
    if role not in ("write", "protected"):
        raise HarnessError("INTERNAL_ERROR")
    return canonical


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _roots_alias(left: Path, right: Path) -> bool:
    if _paths_overlap(left, right):
        return True
    left_parts = tuple(
        unicodedata.normalize("NFC", part).casefold() for part in left.parts
    )
    right_parts = tuple(
        unicodedata.normalize("NFC", part).casefold() for part in right.parts
    )
    common = min(len(left_parts), len(right_parts))
    if left_parts[:common] == right_parts[:common]:
        return True
    try:
        left_metadata = os.lstat(str(left))
        right_metadata = os.lstat(str(right))
    except OSError:
        raise HarnessError("ROOT_UNAVAILABLE")
    if (left_metadata.st_dev, left_metadata.st_ino) == (
        right_metadata.st_dev,
        right_metadata.st_ino,
    ):
        return True
    return False


def assert_root_sets_disjoint(
    write_roots: Sequence[os.PathLike[str]],
    protected_roots: Sequence[os.PathLike[str]],
) -> Tuple[Tuple[Path, ...], Tuple[Path, ...]]:
    canonical_writes = tuple(
        _canonical_existing_directory(root, "write") for root in write_roots
    )
    canonical_protected = tuple(
        _canonical_existing_directory(root, "protected") for root in protected_roots
    )
    for index, left in enumerate(canonical_writes):
        for right in canonical_writes[index + 1 :]:
            if _roots_alias(left, right):
                raise HarnessError("WRITE_ROOT_OVERLAP")
        for protected in canonical_protected:
            if _roots_alias(left, protected):
                raise HarnessError("PROTECTED_ROOT_OVERLAP")
    return canonical_writes, canonical_protected


@dataclass(frozen=True)
class _ProtectedRootIdentity:
    canonical: Path = field(repr=False)
    device: int
    inode: int

    def verify(self) -> None:
        try:
            metadata = os.lstat(str(self.canonical))
            if (
                stat.S_ISLNK(metadata.st_mode)
                or not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_dev != self.device
                or metadata.st_ino != self.inode
                or self.canonical.resolve(strict=True) != self.canonical
            ):
                raise HarnessError("PROTECTED_ROOT_GENERATION_MISMATCH")
        except HarnessError:
            raise
        except OSError:
            raise HarnessError("PROTECTED_ROOT_GENERATION_MISMATCH")


@dataclass(frozen=True)
class DisposableRootSeal:
    canonical: Path = field(repr=False)
    device: int
    inode: int
    opaque_root_id: str
    protected_roots: Tuple[_ProtectedRootIdentity, ...] = field(repr=False)

    def verify(self) -> None:
        try:
            metadata = os.lstat(str(self.canonical))
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise HarnessError("OUTPUT_ROOT_GENERATION_MISMATCH")
            if metadata.st_dev != self.device or metadata.st_ino != self.inode:
                raise HarnessError("OUTPUT_ROOT_GENERATION_MISMATCH")
            if self.canonical.resolve(strict=True) != self.canonical:
                raise HarnessError("OUTPUT_ROOT_GENERATION_MISMATCH")
            for protected in self.protected_roots:
                protected.verify()
                if _paths_overlap(self.canonical, protected.canonical):
                    raise HarnessError("PROTECTED_ROOT_OVERLAP")
        except HarnessError:
            raise
        except OSError:
            raise HarnessError("OUTPUT_ROOT_GENERATION_MISMATCH")


def seal_disposable_root(
    output_root: os.PathLike[str],
    protected_roots: Sequence[os.PathLike[str]],
) -> DisposableRootSeal:
    writes, canonical_protected = assert_root_sets_disjoint([output_root], protected_roots)
    canonical = writes[0]
    metadata = os.lstat(str(canonical))
    opaque_id = "root-" + hashlib.sha256(os.fsencode(str(canonical))).hexdigest()[:16]
    return DisposableRootSeal(
        canonical=canonical,
        device=metadata.st_dev,
        inode=metadata.st_ino,
        opaque_root_id=opaque_id,
        protected_roots=tuple(
            _ProtectedRootIdentity(
                canonical=protected,
                device=os.lstat(str(protected)).st_dev,
                inode=os.lstat(str(protected)).st_ino,
            )
            for protected in canonical_protected
        ),
    )


ProtocolHook = Callable[[str, int], None]


@dataclass(frozen=True)
class CandidateBuildResult:
    file_count: int
    manifest_sha256: str
    tree_sha256: str
    reused: bool

    def public_dict(self) -> Dict[str, Any]:
        return {
            "file_count": self.file_count,
            "manifest_sha256": self.manifest_sha256,
            "reused": self.reused,
            "tree_sha256": self.tree_sha256,
        }


def _candidate_layout(
    blobs: Sequence[SnapshotBlob],
) -> Tuple[Tuple[str, SnapshotBlob], ...]:
    ordered = sorted(blobs, key=lambda item: item.relative_path.encode("utf-8"))
    return tuple(
        (PAYLOAD_NAME_TEMPLATE.format(index=index), blob)
        for index, blob in enumerate(ordered)
    )


def _candidate_source_id(relative_path: str) -> str:
    normalised, _collision_key = _normalise_relative_path(relative_path)
    record = {
        "logical_path": normalised,
        "schema": CANDIDATE_SOURCE_SCHEMA,
    }
    encoded = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return "src-" + hashlib.sha256(encoded).hexdigest()


def _candidate_manifest_bytes(blobs: Sequence[SnapshotBlob]) -> bytes:
    source_order = [
        {
            "generation": blob.content_generation_sha256,
            "opaque_id": _candidate_source_id(blob.relative_path),
            "position": position,
        }
        for position, blob in enumerate(blobs)
    ]
    source_order_digest = hashlib.sha256(
        json.dumps(
            source_order,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
    ).hexdigest()
    records = [
        {
            "generation": blob.content_generation_sha256,
            "logical_path": blob.relative_path,
            "sha256": blob.sha256,
            "size": blob.byte_count,
            "source": _candidate_source_id(blob.relative_path),
            "storage": storage,
        }
        for storage, blob in _candidate_layout(blobs)
    ]
    manifest = {
        "file_count": len(records),
        "files": records,
        "policy_id": "synthetic-only",
        "profile_id": "stellaris-4.4.6-research",
        "schema": CANDIDATE_SCHEMA,
        "source_order": source_order,
        "source_order_digest": source_order_digest,
    }
    return json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii") + b"\n"


def _write_all(fd: int, data: bytes) -> None:
    position = 0
    while position < len(data):
        written = os.write(fd, data[position:])
        if written <= 0:
            raise OSError(errno.EIO, "write failed")
        position += written


def _open_sealed_root_fd(seal: DisposableRootSeal) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(str(seal.canonical), flags)
        metadata = os.fstat(fd)
        if (
            metadata.st_dev != seal.device
            or metadata.st_ino != seal.inode
            or not stat.S_ISDIR(metadata.st_mode)
        ):
            os.close(fd)
            raise HarnessError("OUTPUT_ROOT_GENERATION_MISMATCH")
        return fd
    except HarnessError:
        raise
    except OSError:
        raise HarnessError("OUTPUT_ROOT_GENERATION_MISMATCH")


def _write_root_file_exclusive(root_fd: int, name: str, data: bytes) -> None:
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise HarnessError("INVALID_CANDIDATE_STORAGE_NAME")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(name, flags, 0o600, dir_fd=root_fd)
    except FileExistsError:
        raise HarnessError("CANDIDATE_TARGET_EXISTS")
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise HarnessError("CANDIDATE_TARGET_INVALID")
        _write_all(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def _list_root_files(root_fd: int) -> Tuple[str, ...]:
    try:
        names = os.listdir(root_fd)
        collision_keys: Set[str] = set()
        for name in names:
            key = unicodedata.normalize("NFC", name).casefold()
            if key in collision_keys:
                raise HarnessError("CANDIDATE_NAME_COLLISION")
            collision_keys.add(key)
            metadata = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode):
                raise HarnessError("CANDIDATE_SYMLINK_REJECTED")
            if not stat.S_ISREG(metadata.st_mode):
                raise HarnessError("CANDIDATE_UNSUPPORTED_ENTRY")
            if metadata.st_nlink != 1:
                raise HarnessError("CANDIDATE_HARDLINK_REJECTED")
        return tuple(sorted(names, key=lambda item: item.encode("utf-8")))
    except HarnessError:
        raise
    except OSError:
        raise HarnessError("CANDIDATE_INSPECTION_FAILED")


def _read_root_file(root_fd: int, name: str) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(name, flags, dir_fd=root_fd)
        try:
            opened = _GenerationSignature.from_stat(os.fstat(fd))
            opened_raw = os.fstat(fd)
            if not stat.S_ISREG(opened_raw.st_mode) or opened_raw.st_nlink != 1:
                raise HarnessError("CANDIDATE_HARDLINK_REJECTED")
            if opened.size > DEFAULT_MAX_SOURCE_BYTES:
                raise HarnessError("CANDIDATE_INSPECTION_LIMIT")
            data = _read_fd_pass(fd, opened.size, READ_CHUNK_SIZE, 1, _default_reader, None)
            after = _GenerationSignature.from_stat(os.fstat(fd))
            if after != opened or len(data) != opened.size:
                raise HarnessError("CANDIDATE_MISMATCH")
        finally:
            os.close(fd)
        entry = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        if _GenerationSignature.from_stat(entry) != opened or entry.st_nlink != 1:
            raise HarnessError("CANDIDATE_MISMATCH")
        return data
    except HarnessError:
        raise
    except OSError:
        raise HarnessError("CANDIDATE_INSPECTION_FAILED")


def _actual_payload_tree(
    root_fd: int,
    layout: Sequence[Tuple[str, SnapshotBlob]],
    *,
    extra_names: Sequence[str] = (),
) -> str:
    expected_names = {name for name, _blob in layout}
    expected_names.update(extra_names)
    if set(_list_root_files(root_fd)) != expected_names:
        raise HarnessError("CANDIDATE_MISMATCH")
    records: List[Dict[str, Any]] = []
    for name, blob in layout:
        payload = _read_root_file(root_fd, name)
        digest = hashlib.sha256(payload).hexdigest()
        if len(payload) != blob.byte_count or digest != blob.sha256:
            raise HarnessError("CANDIDATE_MISMATCH")
        records.append({"sha256": digest, "size": len(payload), "storage": name})
    encoded = json.dumps(
        records,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _manifest_describes_complete_tree(root_fd: int) -> bool:
    try:
        raw = _read_root_file(root_fd, MANIFEST_NAME)
        value = json.loads(raw.decode("ascii"))
        if not isinstance(value, dict) or value.get("schema") != CANDIDATE_SCHEMA:
            return False
        records = value.get("files")
        if not isinstance(records, list) or value.get("file_count") != len(records):
            return False
        expected = {MANIFEST_NAME}
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                return False
            storage = PAYLOAD_NAME_TEMPLATE.format(index=index)
            if record.get("storage") != storage:
                return False
            logical_path = record.get("logical_path")
            if not isinstance(logical_path, str):
                return False
            normalised, _collision_key = _normalise_relative_path(logical_path)
            if normalised != logical_path:
                return False
            size = record.get("size")
            digest = record.get("sha256")
            if (
                not isinstance(size, int)
                or isinstance(size, bool)
                or size < 0
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
            ):
                return False
            payload = _read_root_file(root_fd, storage)
            if len(payload) != size or hashlib.sha256(payload).hexdigest() != digest:
                return False
            expected.add(storage)
        return set(_list_root_files(root_fd)) == expected
    except (HarnessError, UnicodeDecodeError, json.JSONDecodeError):
        return False


def candidate_state(seal: DisposableRootSeal) -> str:
    seal.verify()
    root_fd = _open_sealed_root_fd(seal)
    try:
        files = _list_root_files(root_fd)
        if not files:
            return "empty"
        if MANIFEST_NAME in files and _manifest_describes_complete_tree(root_fd):
            return "complete"
        return "incomplete"
    finally:
        os.close(root_fd)
        seal.verify()


def _call_protocol_hook(
    hook: Optional[ProtocolHook], checkpoint: str, item_index: int = -1
) -> None:
    if hook is not None:
        hook(checkpoint, item_index)


def _validate_existing_candidate(
    seal: DisposableRootSeal,
    blobs: Sequence[SnapshotBlob],
    manifest_bytes: bytes,
    *,
    reused: bool,
) -> CandidateBuildResult:
    seal.verify()
    root_fd = _open_sealed_root_fd(seal)
    try:
        layout = _candidate_layout(blobs)
        tree_sha256 = _actual_payload_tree(
            root_fd,
            layout,
            extra_names=(MANIFEST_NAME,),
        )
        if _read_root_file(root_fd, MANIFEST_NAME) != manifest_bytes:
            raise HarnessError("CANDIDATE_MISMATCH")
        if not _manifest_describes_complete_tree(root_fd):
            raise HarnessError("CANDIDATE_MISMATCH")
    finally:
        os.close(root_fd)
        seal.verify()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    return CandidateBuildResult(
        file_count=len(blobs),
        manifest_sha256=manifest_sha256,
        tree_sha256=tree_sha256,
        reused=reused,
    )


def build_candidate(
    seal: DisposableRootSeal,
    blobs: Sequence[SnapshotBlob],
    *,
    hook: Optional[ProtocolHook] = None,
) -> CandidateBuildResult:
    """Build a deterministic candidate only inside a pre-authorized root.

    ``manifest.json`` is written last and is the sole completion marker.  A
    pre-commit crash or write failure therefore leaves an explicitly incomplete
    disposable tree; a rerun refuses that tree instead of silently repairing it.
    """

    seal.verify()
    # Revalidate all relative paths and collisions even for caller-created blobs.
    seen: Dict[str, PurePosixPath] = {}
    path_keys: List[Tuple[str, ...]] = []
    parent_spellings: Dict[Tuple[str, ...], Tuple[str, ...]] = {}
    for blob in blobs:
        normalised, collision_key = _normalise_relative_path(blob.relative_path)
        if normalised != blob.relative_path or collision_key in seen:
            raise HarnessError("DUPLICATE_RELATIVE_PATH")
        relative = PurePosixPath(normalised)
        raw_parts = tuple(relative.parts)
        key_parts = tuple(
            unicodedata.normalize("NFC", part).casefold() for part in raw_parts
        )
        for depth in range(1, len(key_parts)):
            key_prefix = key_parts[:depth]
            raw_prefix = raw_parts[:depth]
            previous = parent_spellings.get(key_prefix)
            if previous is not None and previous != raw_prefix:
                raise HarnessError("AMBIGUOUS_RELATIVE_PATH")
            parent_spellings[key_prefix] = raw_prefix
        for existing in path_keys:
            common = min(len(existing), len(key_parts))
            if existing[:common] == key_parts[:common] and len(existing) != len(key_parts):
                raise HarnessError("RELATIVE_PATH_TYPE_CONFLICT")
        seen[collision_key] = relative
        path_keys.append(key_parts)

    manifest_bytes = _candidate_manifest_bytes(blobs)
    state = candidate_state(seal)
    if state == "complete":
        return _validate_existing_candidate(
            seal,
            blobs,
            manifest_bytes,
            reused=True,
        )
    if state == "incomplete":
        raise HarnessError("INCOMPLETE_BUILD_PRESENT")

    root_fd = _open_sealed_root_fd(seal)
    try:
        _call_protocol_hook(hook, "after_preflight")
        seal.verify()
        layout = _candidate_layout(blobs)
        for index, (storage, blob) in enumerate(layout):
            seal.verify()
            _call_protocol_hook(hook, "before_payload_write", index)
            seal.verify()
            _write_root_file_exclusive(root_fd, storage, blob.data)
            _call_protocol_hook(hook, "after_payload_write", index)
            seal.verify()

        os.fsync(root_fd)
        _actual_payload_tree(root_fd, layout)
        _call_protocol_hook(hook, "after_payload_validation")
        seal.verify()
        _write_root_file_exclusive(
            root_fd, STAGED_MANIFEST_NAME, manifest_bytes
        )
        _call_protocol_hook(hook, "after_manifest_stage")
        seal.verify()
        _actual_payload_tree(
            root_fd,
            layout,
            extra_names=(STAGED_MANIFEST_NAME,),
        )
        if _read_root_file(root_fd, STAGED_MANIFEST_NAME) != manifest_bytes:
            raise HarnessError("CANDIDATE_MISMATCH")
        os.fsync(root_fd)
        os.replace(
            STAGED_MANIFEST_NAME,
            MANIFEST_NAME,
            src_dir_fd=root_fd,
            dst_dir_fd=root_fd,
        )
        os.fsync(root_fd)
        seal.verify()
        _call_protocol_hook(hook, "after_manifest_commit")
        seal.verify()
    except HarnessError:
        raise
    except OSError as error:
        if error.errno == errno.ENOSPC:
            raise HarnessError("DISK_FULL")
        raise HarnessError("CANDIDATE_WRITE_FAILED")
    finally:
        try:
            os.close(root_fd)
        except OSError:
            pass

    return _validate_existing_candidate(
        seal,
        blobs,
        manifest_bytes,
        reused=False,
    )


def _controlled_error_payload(code: str) -> bytes:
    if not _ERROR_CODE_RE.fullmatch(code):
        code = "INTERNAL_ERROR"
    return json.dumps(
        {"code": code, "status": "blocked"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii") + b"\n"


def _inspect_cli(paths: Sequence[str], max_bytes: int) -> int:
    requests = [
        SourceRequest(path=Path(path), relative_path=f"opaque/{index:06d}.yml")
        for index, path in enumerate(paths)
    ]
    blobs = snapshot_sources(requests, max_bytes=max_bytes)
    forbidden: List[bytes] = []
    for path in paths:
        encoded = os.fsencode(path)
        forbidden.append(encoded)
        forbidden.append(os.path.basename(encoded))
    payload, leakage = render_redacted_evidence(
        blobs,
        additional_forbidden=forbidden,
    )
    if leakage.leak_detected:
        raise HarnessError("LEAKAGE_DETECTED")
    sys.stdout.buffer.write(payload)
    return 0


class _RedactedArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise HarnessError("INVALID_ARGUMENTS")


def _argument_parser() -> argparse.ArgumentParser:
    parser = _RedactedArgumentParser(
        description="M1A research-only aggregate inventory; never prints source text or paths"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect", help="inspect explicit regular files")
    inspect_parser.add_argument("files", nargs="+", help=argparse.SUPPRESS)
    inspect_parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_SOURCE_BYTES,
        help="per-file byte limit",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _argument_parser().parse_args(argv)
        if args.command == "inspect":
            return _inspect_cli(args.files, args.max_bytes)
        raise HarnessError("UNKNOWN_COMMAND")
    except HarnessError as error:
        sys.stdout.buffer.write(_controlled_error_payload(error.code))
        return 2
    except KeyboardInterrupt:
        sys.stdout.buffer.write(_controlled_error_payload("INTERRUPTED"))
        return 2
    except SystemExit as error:
        # argparse uses SystemExit(0) for --help; its static help has no inputs.
        return int(error.code)
    except BaseException:
        # No traceback or exception text: both can contain private paths/content.
        sys.stdout.buffer.write(_controlled_error_payload("UNEXPECTED_FAILURE"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
