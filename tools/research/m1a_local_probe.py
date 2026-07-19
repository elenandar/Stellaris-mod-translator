#!/usr/bin/env python3
"""Sanitized, auto-discovered local M1A evidence collector.

The CLI deliberately accepts no source paths.  It discovers only the public,
standard macOS locations for the current Stellaris/Steam installation, keeps
all names and source bytes inside this process, and emits one fixed-schema JSON
document containing aggregate evidence.  It never opens launcher SQLite as a
database: the file is byte-read only, because a live SQLite reader may touch
WAL shared state and its schema/order contract is not documented for M1A.

This is Python 3.9 standard-library research tooling, not the M2 product CLI.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.research import m1a_harness as harness


SCHEMA = "m1a-local-redacted-evidence-v2"
EXPECTED_VERSION = "4.4.6"
EXPECTED_CHECKSUM = "fdde"
STEAM_APP_ID = "281990"
MIN_PRIVATE_LINE_BYTES = 4
MIN_PRIVATE_TOKEN_BYTES = 64
MIN_PRIVATE_PATH_BYTES = 8
MAX_OBSERVED_FILE_BYTES = 64 * 1024 * 1024
PUBLIC_BLOCKERS = frozenset(
    {
        "ACTIVE_ORDER_METADATA_UNAVAILABLE",
        "CONCURRENT_SAME_UID_PATH_RACE_UNPROVEN",
        "CROSS_FILE_GENERATION_COHERENCE_UNPROVEN",
        "DEPENDENCY_GRAPH_UNPROVEN",
        "DESCRIPTOR_SCHEMA_UNSUPPORTED",
        "EFFECTIVE_LOAD_ORDER_UNPROVEN",
        "EXPORT_POLICY_UNRESOLVED",
        "FORMAT_PROFILE_HAS_BLOCKERS",
        "GAME_ROOT_UNAVAILABLE",
        "GAME_VERSION_UNVERIFIED",
        "LAUNCHER_DB_SCHEMA_UNREAD",
        "LAUNCHER_DB_METADATA_UNAVAILABLE",
        "LOCAL_SOURCE_CONTENT_NOT_FOLLOWED",
        "REPLACE_LAYER_SEMANTICS_UNPROVEN",
        "STEAM_LIBRARY_METADATA_INVALID",
        "WORKSHOP_ROOT_UNAVAILABLE",
    }
)
_CODE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_PUBLIC_PATH_COMPONENTS = frozenset(
    {
        b"application support",
        b"common",
        b"content",
        b"descriptor.mod",
        b"documents",
        b"dlc_load.json",
        b"launcher-v2",
        b"launcher-settings.json",
        b"launcher-v2.sqlite",
        b"libraryfolders.vdf",
        b"localisation",
        b"paradox interactive",
        b"steam",
        b"steamapps",
        b"stellaris",
        b"users",
        b"workshop",
    }
)


class ProbeError(RuntimeError):
    """Path-, value-, and content-free collector failure."""

    def __init__(self, code: str) -> None:
        if not _CODE.fullmatch(code):
            code = "UNEXPECTED_FAILURE"
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _JsonObject:
    pairs: Tuple[Tuple[str, Any], ...]


@dataclass(frozen=True)
class LocatedFile:
    role: str
    source_id: str
    path: Path = field(repr=False)
    path_id: str


@dataclass(frozen=True)
class _PrivateInputFingerprints:
    observed_file_count: int
    nonempty_file_count: int
    file_hashes: FrozenSet[bytes] = field(repr=False)
    line_hashes: FrozenSet[bytes] = field(repr=False)
    token_hashes: FrozenSet[bytes] = field(repr=False)


@dataclass(frozen=True)
class Discovery:
    game_roots: Tuple[Path, ...] = field(repr=False)
    workshop_roots: Tuple[Path, ...] = field(repr=False)
    documents_roots: Tuple[Path, ...] = field(repr=False)
    launcher_roots: Tuple[Path, ...] = field(repr=False)
    localisation: Tuple[LocatedFile, ...] = field(repr=False)
    descriptors: Tuple[LocatedFile, ...] = field(repr=False)
    active_load_files: Tuple[LocatedFile, ...] = field(repr=False)
    version_files: Tuple[LocatedFile, ...] = field(repr=False)
    launcher_databases: Tuple[LocatedFile, ...] = field(repr=False)
    discovery_metadata_files: Tuple[LocatedFile, ...] = field(repr=False)
    discovery_metadata_reads: Tuple[Tuple[str, harness.StableRead], ...] = field(
        repr=False
    )
    discovery_metadata_fingerprints: _PrivateInputFingerprints = field(repr=False)
    private_path_values: Tuple[bytes, ...] = field(repr=False)
    steam_library_metadata_valid: bool
    workshop_source_ids: Tuple[str, ...]
    workshop_source_count: int
    local_descriptor_count: int
    localisation_replace_directory_count: int

    @property
    def observed_files(self) -> Tuple[LocatedFile, ...]:
        return tuple(
            sorted(
                self.localisation
                + self.descriptors
                + self.active_load_files
                + self.version_files
                + self.launcher_databases
                + self.discovery_metadata_files,
                key=lambda item: item.path_id,
            )
        )

    @property
    def protected_roots(self) -> Tuple[Path, ...]:
        values = (
            self.game_roots
            + self.workshop_roots
            + self.documents_roots
            + self.launcher_roots
        )
        unique: Dict[str, Path] = {}
        for value in values:
            unique[str(value)] = value
        return tuple(unique[key] for key in sorted(unique))


def _opaque(domain: str, value: bytes) -> str:
    digest = hashlib.sha256(domain.encode("ascii") + b"\0" + value).hexdigest()
    return digest


def _path_id(path: Path) -> str:
    return _opaque("path", os.fsencode(str(path)))


def _source_id(path: Path) -> str:
    return _opaque("source", os.fsencode(str(path)))


def _add_private_path_value(values: Set[bytes], value: bytes) -> None:
    if (
        len(value) >= MIN_PRIVATE_PATH_BYTES
        and value.lower() not in _PUBLIC_PATH_COMPONENTS
    ):
        values.add(value)


def _add_private_path(values: Set[bytes], path: Path) -> None:
    encoded = os.fsencode(str(path))
    if len(encoded) >= MIN_PRIVATE_PATH_BYTES:
        values.add(encoded)
    for component in path.parts:
        _add_private_path_value(values, os.fsencode(component))


def _absolute_unaliased(path: Path, expected_mode: str) -> Optional[Path]:
    if (
        not path.is_absolute()
        or ".." in path.parts
        or "\x00" in os.fspath(path)
    ):
        raise ProbeError("AMBIGUOUS_SOURCE_PATH")
    try:
        metadata = os.lstat(str(path))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        raise ProbeError("SOURCE_ENUMERATION_FAILED")
    try:
        current = Path(path.anchor)
        for component in path.parts[1:]:
            current = current / component
            component_metadata = os.lstat(str(current))
            if stat.S_ISLNK(component_metadata.st_mode):
                raise ProbeError("SOURCE_SYMLINK_REJECTED")
        if stat.S_ISLNK(metadata.st_mode):
            raise ProbeError("SOURCE_SYMLINK_REJECTED")
        if expected_mode == "directory" and not stat.S_ISDIR(metadata.st_mode):
            raise ProbeError("UNSUPPORTED_SOURCE_TYPE")
        if expected_mode == "file" and not stat.S_ISREG(metadata.st_mode):
            raise ProbeError("UNSUPPORTED_SOURCE_TYPE")
        canonical = path.resolve(strict=True)
        canonical_metadata = os.lstat(str(canonical))
        if canonical != path or stat.S_ISLNK(canonical_metadata.st_mode):
            raise ProbeError("AMBIGUOUS_SOURCE_PATH")
        if (metadata.st_dev, metadata.st_ino) != (
            canonical_metadata.st_dev,
            canonical_metadata.st_ino,
        ):
            raise ProbeError("AMBIGUOUS_SOURCE_PATH")
        return canonical
    except ProbeError:
        raise
    except OSError:
        raise ProbeError("SOURCE_ENUMERATION_FAILED")


def _canonical_directory(path: Path) -> Optional[Path]:
    return _absolute_unaliased(path, "directory")


def _regular_file(path: Path) -> Optional[Path]:
    return _absolute_unaliased(path, "file")


def _quoted_values(line: str) -> Tuple[str, ...]:
    values: List[str] = []
    current: List[str] = []
    quoted = False
    escaped = False
    for character in line:
        if not quoted:
            if character == '"':
                quoted = True
                current = []
            continue
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == '"':
            values.append("".join(current))
            quoted = False
        else:
            current.append(character)
    return tuple(values)


def _steamapps_candidates(
    home: Path,
) -> Tuple[
    Tuple[Path, ...],
    Tuple[Tuple[Path, harness.StableRead], ...],
    Tuple[bytes, ...],
    bool,
    _PrivateInputFingerprints,
]:
    default = home / "Library" / "Application Support" / "Steam" / "steamapps"
    candidates: Dict[str, Path] = {str(default): default}
    metadata_reads: List[Tuple[Path, harness.StableRead]] = []
    private_path_values: Set[bytes] = set()
    metadata_valid = True
    file_hashes: Set[bytes] = set()
    line_hashes: Set[bytes] = set()
    token_hashes: Set[bytes] = set()
    nonempty_file_count = 0
    library_file = _regular_file(default / "libraryfolders.vdf")
    if library_file is not None:
        stable = harness.read_stable_file(
            library_file,
            max_bytes=8 * 1024 * 1024,
        )
        metadata_reads.append((library_file, stable))
        if stable.data:
            nonempty_file_count = 1
            file_hashes.add(hashlib.sha256(stable.data).digest())
        line_hashes.update(_line_fingerprints(stable.data))
        token_hashes.update(_token_fingerprints(stable.data))
        try:
            text = stable.data.decode("utf-8")
        except UnicodeDecodeError:
            metadata_valid = False
            text = None
        parsed_libraries: List[Tuple[Path, bytes]] = []
        if text is not None:
            for line in text.splitlines():
                values = _quoted_values(line)
                if len(values) >= 2 and values[0].casefold() == "path":
                    library_root = Path(values[1])
                    if not library_root.is_absolute() or ".." in library_root.parts:
                        metadata_valid = False
                        parsed_libraries = []
                        break
                    parsed_libraries.append((library_root, os.fsencode(values[1])))
        if metadata_valid:
            for library_root, encoded in parsed_libraries:
                _add_private_path_value(private_path_values, encoded)
                candidate = library_root / "steamapps"
                candidates[str(candidate)] = candidate
    found: Dict[str, Path] = {}
    for candidate in candidates.values():
        canonical = _canonical_directory(candidate)
        if canonical is not None:
            found[str(canonical)] = canonical
    return (
        tuple(found[key] for key in sorted(found)),
        tuple(metadata_reads),
        tuple(sorted(private_path_values)),
        metadata_valid,
        _PrivateInputFingerprints(
            observed_file_count=len(metadata_reads),
            nonempty_file_count=nonempty_file_count,
            file_hashes=frozenset(file_hashes),
            line_hashes=frozenset(line_hashes),
            token_hashes=frozenset(token_hashes),
        ),
    )


def _walk_regular_files(root: Path, selector: Any) -> Tuple[Path, ...]:
    found: List[Path] = []

    def on_error(_error: OSError) -> None:
        raise ProbeError("SOURCE_ENUMERATION_FAILED")

    try:
        for current, directories, files in os.walk(
            str(root), followlinks=False, onerror=on_error
        ):
            current_path = Path(current)
            kept: List[str] = []
            for directory in directories:
                candidate = current_path / directory
                metadata = os.lstat(str(candidate))
                if stat.S_ISLNK(metadata.st_mode):
                    raise ProbeError("SOURCE_SYMLINK_REJECTED")
                if stat.S_ISDIR(metadata.st_mode):
                    kept.append(directory)
            directories[:] = kept
            for filename in files:
                candidate = current_path / filename
                if not selector(candidate):
                    continue
                regular = _regular_file(candidate)
                if regular is None:
                    raise ProbeError("UNSUPPORTED_SOURCE_TYPE")
                found.append(regular)
    except ProbeError:
        raise
    except OSError:
        raise ProbeError("SOURCE_ENUMERATION_FAILED")
    return tuple(sorted(found, key=lambda path: os.fsencode(str(path))))


def _located(role: str, source: Path, path: Path) -> LocatedFile:
    try:
        canonical_source = source.resolve(strict=True)
        canonical_path = path.resolve(strict=True)
        canonical_path.relative_to(canonical_source)
    except (OSError, ValueError):
        raise ProbeError("AMBIGUOUS_SOURCE_PATH")
    return LocatedFile(
        role=role,
        source_id=_source_id(canonical_source),
        path=canonical_path,
        path_id=_path_id(canonical_path),
    )


def discover(home: Path) -> Discovery:
    (
        steamapps,
        steam_metadata_reads,
        discovered_private_paths,
        steam_library_metadata_valid,
        discovery_metadata_fingerprints,
    ) = _steamapps_candidates(home)
    steam_metadata_paths = tuple(path for path, _stable in steam_metadata_reads)
    game_roots: List[Path] = []
    workshop_roots: List[Path] = []
    localisation: List[LocatedFile] = []
    descriptors: List[LocatedFile] = []
    version_files: List[LocatedFile] = []
    workshop_source_count = 0
    workshop_source_ids: List[str] = []
    replace_directory_count = 0
    private_path_values: Set[bytes] = set(discovered_private_paths)

    for steam_root in steamapps:
        game_root = _canonical_directory(steam_root / "common" / "Stellaris")
        if game_root is not None:
            game_roots.append(game_root)
            loc_root = _canonical_directory(game_root / "localisation")
            if loc_root is not None:
                if _canonical_directory(loc_root / "replace") is not None:
                    replace_directory_count += 1
                for path in _walk_regular_files(
                    loc_root, lambda item: item.suffix.casefold() == ".yml"
                ):
                    relative = path.relative_to(loc_root)
                    role = (
                        "official_replace"
                        if relative.parts and relative.parts[0].casefold() == "replace"
                        else "official"
                    )
                    localisation.append(_located(role, game_root, path))
                    _add_private_path_value(private_path_values, os.fsencode(path.name))
            settings = _regular_file(game_root / "launcher-settings.json")
            if settings is not None:
                version_files.append(_located("version_metadata", game_root, settings))

        workshop_root = _canonical_directory(
            steam_root / "workshop" / "content" / STEAM_APP_ID
        )
        if workshop_root is None:
            continue
        workshop_roots.append(workshop_root)
        try:
            children = sorted(
                tuple(os.scandir(str(workshop_root))), key=lambda item: os.fsencode(item.name)
            )
        except OSError:
            raise ProbeError("SOURCE_ENUMERATION_FAILED")
        for child in children:
            try:
                if child.is_symlink():
                    raise ProbeError("SOURCE_SYMLINK_REJECTED")
                if not child.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                raise ProbeError("SOURCE_ENUMERATION_FAILED")
            source_root = _canonical_directory(Path(child.path))
            if source_root is None:
                raise ProbeError("AMBIGUOUS_SOURCE_PATH")
            workshop_source_count += 1
            workshop_source_ids.append(_source_id(source_root))
            child_name = os.fsencode(child.name)
            _add_private_path_value(private_path_values, child_name)
            descriptor = _regular_file(source_root / "descriptor.mod")
            if descriptor is not None:
                descriptors.append(_located("workshop_descriptor", source_root, descriptor))
            loc_root = _canonical_directory(source_root / "localisation")
            if loc_root is None:
                continue
            if _canonical_directory(loc_root / "replace") is not None:
                replace_directory_count += 1
            for path in _walk_regular_files(
                loc_root, lambda item: item.suffix.casefold() == ".yml"
            ):
                relative = path.relative_to(loc_root)
                role = (
                    "workshop_replace"
                    if relative.parts and relative.parts[0].casefold() == "replace"
                    else "workshop"
                )
                localisation.append(_located(role, source_root, path))
                _add_private_path_value(private_path_values, os.fsencode(path.name))

    documents = _canonical_directory(home / "Documents" / "Paradox Interactive" / "Stellaris")
    documents_roots: List[Path] = []
    active_load_files: List[LocatedFile] = []
    local_descriptor_count = 0
    if documents is not None:
        documents_roots.append(documents)
        active = _regular_file(documents / "dlc_load.json")
        if active is not None:
            active_load_files.append(_located("active_load", documents, active))
        mod_root = _canonical_directory(documents / "mod")
        if mod_root is not None:
            for descriptor in _walk_regular_files(
                mod_root,
                lambda item: item.parent == mod_root
                and item.suffix.casefold() == ".mod",
            ):
                descriptors.append(_located("local_descriptor", mod_root, descriptor))
                local_descriptor_count += 1
                _add_private_path_value(private_path_values, os.fsencode(descriptor.name))

    launcher_parent = _canonical_directory(
        home / "Library" / "Application Support" / "Paradox Interactive"
    )
    launcher_roots: List[Path] = []
    launcher_databases: List[LocatedFile] = []
    if launcher_parent is not None:
        launcher_roots.append(launcher_parent)
        database_candidates: List[Path] = list(
            (
            launcher_parent / "launcher-v2" / "launcher-v2.sqlite",
            launcher_parent / "launcher-v2.sqlite",
            )
        )
        for database in database_candidates:
            regular = _regular_file(database)
            if regular is not None:
                launcher_databases.append(
                    _located("launcher_database", launcher_parent, regular)
                )

    def unique_paths(values: Iterable[Path]) -> Tuple[Path, ...]:
        unique = {str(value): value for value in values}
        return tuple(unique[key] for key in sorted(unique))

    def unique_files(values: Iterable[LocatedFile]) -> Tuple[LocatedFile, ...]:
        unique = {value.path_id: value for value in values}
        return tuple(unique[key] for key in sorted(unique))

    discovery_metadata = tuple(
        LocatedFile(
            role="steam_library_metadata",
            source_id=_source_id(path.parent),
            path=path,
            path_id=_path_id(path),
        )
        for path in steam_metadata_paths
    )
    discovery_metadata = unique_files(discovery_metadata)
    discovery_read_by_path = {
        _path_id(path): stable for path, stable in steam_metadata_reads
    }

    for located in (
        localisation
        + descriptors
        + active_load_files
        + version_files
        + launcher_databases
    ):
        encoded_name = os.fsencode(located.path.name)
        _add_private_path_value(private_path_values, encoded_name)

    private_paths: List[Path] = [home]
    private_paths.extend(steamapps)
    private_paths.extend(game_roots)
    private_paths.extend(workshop_roots)
    private_paths.extend(documents_roots)
    private_paths.extend(launcher_roots)
    private_paths.extend(steam_metadata_paths)
    private_paths.extend(
        located.path
        for located in (
            localisation
            + descriptors
            + active_load_files
            + version_files
            + launcher_databases
        )
    )
    for private_path in private_paths:
        _add_private_path(private_path_values, private_path)

    return Discovery(
        game_roots=unique_paths(game_roots),
        workshop_roots=unique_paths(workshop_roots),
        documents_roots=unique_paths(documents_roots),
        launcher_roots=unique_paths(launcher_roots),
        localisation=unique_files(localisation),
        descriptors=unique_files(descriptors),
        active_load_files=unique_files(active_load_files),
        version_files=unique_files(version_files),
        launcher_databases=unique_files(launcher_databases),
        discovery_metadata_files=discovery_metadata,
        discovery_metadata_reads=tuple(
            (located.path_id, discovery_read_by_path[located.path_id])
            for located in discovery_metadata
        ),
        discovery_metadata_fingerprints=discovery_metadata_fingerprints,
        private_path_values=tuple(sorted(private_path_values)),
        steam_library_metadata_valid=steam_library_metadata_valid,
        workshop_source_ids=tuple(sorted(workshop_source_ids)),
        workshop_source_count=workshop_source_count,
        local_descriptor_count=local_descriptor_count,
        localisation_replace_directory_count=replace_directory_count,
    )


def _empty_inventory() -> Dict[str, Any]:
    return {
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
        "files_with_bom": 0,
        "files_with_final_newline": 0,
        "hidden_bom_count": 0,
        "language_header_lines": 0,
        "line_count": 0,
        "malformed_lines": 0,
        "newline_styles": {"CR": 0, "CRLF": 0, "LF": 0, "mixed": 0, "none": 0},
        "opaque_constructs": 0,
        "quoted_value_occurrences": 0,
        "unknown_escape_occurrences": 0,
        "unknown_lines": 0,
        "utf8_invalid_files": 0,
        "utf8_valid_files": 0,
        "version_suffix_occurrences": 0,
        "whitespace_lines": 0,
        "markup": {
            "formatting_spans": 0,
            "icons": 0,
            "placeholders": 0,
            "scripted_localisation": 0,
            "unknown_or_ambiguous": 0,
        },
    }


def _add_inventory(total: Dict[str, Any], inventory: harness.FormatInventory) -> None:
    public = inventory.public_dict()
    for key in tuple(total):
        if key in ("markup", "newline_styles") or key.startswith("files_") or key.startswith("utf8_"):
            continue
        total[key] += int(public[key])
    total["files_with_bom"] += int(inventory.bom_at_start)
    total["files_with_final_newline"] += int(inventory.final_newline)
    total["utf8_valid_files"] += int(inventory.utf8_valid)
    total["utf8_invalid_files"] += int(not inventory.utf8_valid)
    total["newline_styles"][inventory.newline_style] += 1
    markup = inventory.markup.public_dict()
    for key in total["markup"]:
        total["markup"][key] += int(markup[key])


def _header_class(data: bytes, header_line_count: int) -> str:
    if header_line_count != 1:
        return "missing_or_multiple"
    payload = data[len(harness.UTF8_BOM) :] if data.startswith(harness.UTF8_BOM) else data
    physical_lines = harness._split_physical_lines(payload)
    first = physical_lines[0].rstrip(b"\r\n").strip() if physical_lines else b""
    if first == b"l_english:":
        return "english"
    if first == b"l_russian:":
        return "russian"
    if (
        first.startswith(b"l_")
        and first.endswith(b":")
        and first[2:-1]
        and all(
            byte < 128
            and (
                chr(byte).isalnum()
                or chr(byte) in "_.-"
            )
            for byte in first[2:-1]
        )
    ):
        return "other"
    return "misplaced"


def _entry_key_hashes(data: bytes) -> Tuple[str, ...]:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return ()
    keys: List[str] = []
    for index, raw_line in enumerate(harness._split_physical_lines(data)):
        line = harness._strip_line_ending(raw_line.decode("utf-8"))
        if index == 0 and line.startswith("\ufeff"):
            line = line[1:]
        if harness._has_unsupported_line_codepoint(line):
            continue
        observation = harness._observe_entry(line)
        if observation.unknown or observation.malformed or observation.key is None:
            continue
        keys.append(
            _opaque("localisation-key", observation.key.encode("utf-8"))
        )
    return tuple(keys)


_ASCII_PRIVATE_TOKEN = re.compile(rb"[A-Za-z0-9_][A-Za-z0-9_.:-]*")
_UNICODE_PRIVATE_TOKEN = re.compile(r"[\w][\w.:'’-]*", re.UNICODE)
_PUBLIC_HEADER_LINE = re.compile(rb"l_[A-Za-z0-9_.-]+:")


def _line_fingerprints(
    data: bytes,
    *,
    exclude_public_language_header: bool = False,
) -> Set[bytes]:
    result: Set[bytes] = set()
    for index, line in enumerate(harness._split_physical_lines(data)):
        if line.endswith(b"\r\n"):
            physical_line = line[:-2]
        elif line.endswith((b"\r", b"\n")):
            physical_line = line[:-1]
        else:
            physical_line = line
        stripped = physical_line.strip()
        header_candidate = physical_line
        if index == 0 and header_candidate.startswith(harness.UTF8_BOM):
            header_candidate = header_candidate[len(harness.UTF8_BOM) :]
        if (
            len(stripped) >= MIN_PRIVATE_LINE_BYTES
            and not (
                exclude_public_language_header
                and index == 0
                and _PUBLIC_HEADER_LINE.fullmatch(header_candidate) is not None
            )
        ):
            result.add(hashlib.sha256(stripped).digest())
    return result


def _token_fingerprints(data: bytes) -> Set[bytes]:
    result: Set[bytes] = set()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        for line in data.splitlines():
            matches = list(_ASCII_PRIVATE_TOKEN.finditer(line))
            for match in matches:
                token = match.group(0)
                if len(token) >= MIN_PRIVATE_TOKEN_BYTES and (
                    any(not chr(byte).isalpha() for byte in token)
                    or len(token) >= 32
                ):
                    result.add(hashlib.sha256(token).digest())
        return result
    for line in text.splitlines():
        matches = list(_UNICODE_PRIVATE_TOKEN.finditer(line))
        for match in matches:
            token = match.group(0)
            encoded = token.encode("utf-8")
            if len(encoded) >= MIN_PRIVATE_TOKEN_BYTES and (
                any(not character.isalpha() for character in token)
                or len(encoded) >= 32
            ):
                result.add(hashlib.sha256(encoded).digest())
    return result


def _private_input_fingerprints(
    expected_files: Sequence[LocatedFile],
    raw_by_path: Dict[str, bytes],
    *,
    preparsed: Optional[_PrivateInputFingerprints] = None,
) -> _PrivateInputFingerprints:
    file_hashes: Set[bytes] = set()
    line_hashes: Set[bytes] = set()
    token_hashes: Set[bytes] = set()
    nonempty_file_count = 0
    localisation_roles = {
        "official",
        "official_replace",
        "workshop",
        "workshop_replace",
    }
    for located in expected_files:
        data = raw_by_path.get(located.path_id)
        if not isinstance(data, bytes):
            raise ProbeError("SOURCE_UNAVAILABLE")
        if data:
            nonempty_file_count += 1
            file_hashes.add(hashlib.sha256(data).digest())
        line_hashes.update(
            _line_fingerprints(
                data,
                exclude_public_language_header=located.role in localisation_roles,
            )
        )
        token_hashes.update(_token_fingerprints(data))
    if preparsed is not None and (
        preparsed.observed_file_count > len(expected_files)
        or preparsed.nonempty_file_count > nonempty_file_count
        or not preparsed.file_hashes.issubset(file_hashes)
        or not preparsed.line_hashes.issubset(line_hashes)
        or not preparsed.token_hashes.issubset(token_hashes)
    ):
        raise ProbeError("GENERATION_MISMATCH")
    return _PrivateInputFingerprints(
        observed_file_count=len(expected_files),
        nonempty_file_count=nonempty_file_count,
        file_hashes=frozenset(file_hashes),
        line_hashes=frozenset(line_hashes),
        token_hashes=frozenset(token_hashes),
    )


def _quoted_values_checked(value: str) -> Tuple[Tuple[str, ...], str, bool]:
    values: List[str] = []
    residual: List[str] = []
    current: List[str] = []
    quoted = False
    escaped = False
    for character in value:
        if not quoted:
            if character == '"':
                quoted = True
                current = []
                residual.append("Q")
            else:
                residual.append(character)
            continue
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == '"':
            values.append("".join(current))
            quoted = False
        else:
            current.append(character)
    return tuple(values), "".join(residual), not quoted and not escaped


def _descriptor_evidence(
    data: bytes,
    private_values: Set[bytes],
) -> Dict[str, Any]:
    known = {
        "name",
        "path",
        "dependencies",
        "picture",
        "tags",
        "version",
        "supported_version",
        "remote_file_id",
        "replace_path",
    }
    fields = {field: 0 for field in sorted(known)}
    unknown_fields = 0
    dependency_values = 0
    replace_localisation = 0
    unsupported_syntax = 0
    unterminated_blocks = 0
    invalid_utf8 = False
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {
            "field_occurrences": fields,
            "unknown_field_occurrences": 0,
            "dependency_value_count": 0,
            "replace_localisation_count": 0,
            "unsupported_syntax_occurrences": 0,
            "unterminated_block_count": 0,
            "invalid_utf8": True,
        }
    active_block: Optional[str] = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if active_block is not None:
            values, residual, balanced = _quoted_values_checked(line)
            if not balanced or re.fullmatch(r"\s*(?:Q\s*)*(?:}\s*)?", residual) is None:
                unsupported_syntax += 1
            for value in values:
                encoded = value.encode("utf-8")
                if len(encoded) >= MIN_PRIVATE_PATH_BYTES:
                    private_values.add(encoded)
                if active_block == "dependencies":
                    dependency_values += 1
            if "}" in residual:
                active_block = None
            continue
        if "=" not in line:
            unsupported_syntax += 1
            continue
        field_name, value_text = line.split("=", 1)
        field_name = field_name.strip()
        valid_field_name = bool(field_name) and all(
            character.isascii()
            and (character.isalnum() or character == "_")
            for character in field_name
        )
        if field_name in known:
            fields[field_name] += 1
        elif valid_field_name:
            unknown_fields += 1
        else:
            unsupported_syntax += 1

        values, residual, balanced = _quoted_values_checked(value_text)
        for value in values:
            encoded = value.encode("utf-8")
            if len(encoded) >= MIN_PRIVATE_PATH_BYTES:
                private_values.add(encoded)

        if not balanced:
            unsupported_syntax += 1
            continue
        if field_name in ("dependencies", "tags"):
            if re.fullmatch(r"\s*{\s*(?:Q\s*)*(?:}\s*)?", residual) is None:
                unsupported_syntax += 1
            if "}" not in residual:
                active_block = field_name
            if field_name == "dependencies":
                dependency_values += len(values)
        elif field_name in known:
            if re.fullmatch(r"\s*Q\s*", residual) is None or len(values) != 1:
                unsupported_syntax += 1
        elif valid_field_name:
            # Unknown fields are blockers regardless, but their syntax must not
            # silently disappear from the aggregate evidence.
            if not residual.strip():
                unsupported_syntax += 1

        if field_name == "replace_path":
            for value in values:
                if value.casefold() == "localisation" or value.casefold().startswith(
                    "localisation/"
                ):
                    replace_localisation += 1
    if active_block is not None:
        unsupported_syntax += 1
        unterminated_blocks += 1
    return {
        "field_occurrences": fields,
        "unknown_field_occurrences": unknown_fields,
        "dependency_value_count": dependency_values,
        "replace_localisation_count": replace_localisation,
        "unsupported_syntax_occurrences": unsupported_syntax,
        "unterminated_block_count": unterminated_blocks,
        "invalid_utf8": invalid_utf8,
    }


def _merge_descriptor_evidence(total: Dict[str, Any], item: Dict[str, Any]) -> None:
    total["descriptor_count"] += 1
    total["invalid_utf8_count"] += int(item["invalid_utf8"])
    total["unknown_field_occurrences"] += int(item["unknown_field_occurrences"])
    total["dependency_value_count"] += int(item["dependency_value_count"])
    total["replace_localisation_count"] += int(item["replace_localisation_count"])
    total["unsupported_syntax_occurrences"] += int(
        item["unsupported_syntax_occurrences"]
    )
    total["unterminated_block_count"] += int(item["unterminated_block_count"])
    for key, value in item["field_occurrences"].items():
        total["field_occurrences"][key] += int(value)


def _seed_json_private_strings(value: Any, private_values: Set[bytes]) -> None:
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        if len(encoded) >= MIN_PRIVATE_PATH_BYTES:
            private_values.add(encoded)
        return
    if isinstance(value, list):
        for item in value:
            _seed_json_private_strings(item, private_values)
        return
    if isinstance(value, _JsonObject):
        for _key, item in value.pairs:
            _seed_json_private_strings(item, private_values)
        return
    if isinstance(value, dict):
        for item in value.values():
            _seed_json_private_strings(item, private_values)


def _json_has_duplicate_keys(value: Any) -> bool:
    if isinstance(value, _JsonObject):
        keys = [key for key, _item in value.pairs]
        return len(keys) != len(set(keys)) or any(
            _json_has_duplicate_keys(item) for _key, item in value.pairs
        )
    if isinstance(value, list):
        return any(_json_has_duplicate_keys(item) for item in value)
    return False


def _active_load_evidence(data: bytes, private_values: Set[bytes]) -> Dict[str, Any]:
    try:
        parsed = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=lambda pairs: _JsonObject(tuple(pairs)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            "present": True,
            "valid_json": False,
            "enabled_count": 0,
            "enabled_unique": False,
            "stored_order_digest": None,
            "disabled_dlc_count": 0,
        }
    _seed_json_private_strings(parsed, private_values)
    duplicate_keys = _json_has_duplicate_keys(parsed)
    value = dict(parsed.pairs) if isinstance(parsed, _JsonObject) else parsed
    allowed_fields = {"enabled_mods", "disabled_dlcs"}
    valid = (
        isinstance(value, dict)
        and "enabled_mods" in value
        and set(value).issubset(allowed_fields)
        and not duplicate_keys
    )
    enabled = value.get("enabled_mods") if isinstance(value, dict) else None
    disabled = value.get("disabled_dlcs", []) if isinstance(value, dict) else None
    if not isinstance(enabled, list) or not all(isinstance(item, str) for item in enabled):
        enabled = []
        valid = False
    if not isinstance(disabled, list) or not all(
        isinstance(item, str) for item in disabled
    ):
        disabled = []
        valid = False
    opaque_order: List[str] = []
    for item in enabled:
        encoded = item.encode("utf-8")
        opaque_order.append(_opaque("active-order", encoded))
    encoded_order = json.dumps(opaque_order, separators=(",", ":")).encode("ascii")
    return {
        "present": True,
        "valid_json": valid,
        "enabled_count": len(enabled),
        "enabled_unique": len(set(opaque_order)) == len(opaque_order),
        "stored_order_digest": hashlib.sha256(encoded_order).hexdigest(),
        "disabled_dlc_count": len(disabled),
    }


def _version_matches(data: bytes) -> bool:
    try:
        parsed = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=lambda pairs: _JsonObject(tuple(pairs)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(parsed, _JsonObject) or _json_has_duplicate_keys(parsed):
        return False
    value = dict(parsed.pairs)
    if set(value) != {"rawVersion", "checksum"}:
        return False
    version = value.get("rawVersion")
    checksum = value.get("checksum")
    return (
        isinstance(version, str)
        and isinstance(checksum, str)
        and version.strip().casefold().removeprefix("v") == EXPECTED_VERSION
        and checksum.strip().casefold() == EXPECTED_CHECKSUM
    )


def _manifest_digest(records: Sequence[Dict[str, Any]]) -> str:
    encoded = json.dumps(
        sorted(records, key=lambda record: record["path_id"]),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _discovery_topology_digest(discovery: Discovery) -> str:
    root_records: List[Dict[str, Any]] = []
    for role, roots in (
        ("game", discovery.game_roots),
        ("workshop", discovery.workshop_roots),
        ("documents", discovery.documents_roots),
        ("launcher", discovery.launcher_roots),
    ):
        for root in roots:
            try:
                metadata = os.lstat(str(root))
            except OSError:
                raise ProbeError("SOURCE_ENUMERATION_FAILED")
            root_records.append(
                {
                    "device": metadata.st_dev,
                    "inode": metadata.st_ino,
                    "path_id": _path_id(root),
                    "role": role,
                }
            )
    value = {
        "local_descriptor_count": discovery.local_descriptor_count,
        "steam_library_metadata_valid": discovery.steam_library_metadata_valid,
        "observed": [
            {"path_id": item.path_id, "role": item.role, "source_id": item.source_id}
            for item in discovery.observed_files
        ],
        "replace_directory_count": discovery.localisation_replace_directory_count,
        "roots": sorted(root_records, key=lambda item: (item["role"], item["path_id"])),
        "workshop_source_ids": list(discovery.workshop_source_ids),
    }
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _run_generation_digest(
    records: Sequence[Dict[str, Any]], discovery: Discovery
) -> str:
    encoded = (
        _manifest_digest(records) + ":" + _discovery_topology_digest(discovery)
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _repository_files(root: Path) -> Tuple[Path, ...]:
    excluded = {".git", "__pycache__", ".venv", ".pytest_cache", ".ruff_cache"}
    found: List[Path] = []
    try:
        stack = [root]
        while stack:
            current = stack.pop()
            with os.scandir(str(current)) as iterator:
                entries = sorted(
                    tuple(iterator), key=lambda item: os.fsencode(item.name)
                )
            for entry in entries:
                candidate = current / entry.name
                metadata = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(metadata.st_mode):
                    raise ProbeError("REPOSITORY_SCAN_FAILED")
                if stat.S_ISDIR(metadata.st_mode):
                    if entry.name not in excluded:
                        stack.append(candidate)
                    continue
                if not stat.S_ISREG(metadata.st_mode):
                    raise ProbeError("REPOSITORY_SCAN_FAILED")
                if metadata.st_size > 16 * 1024 * 1024:
                    raise ProbeError("REPOSITORY_SCAN_LIMIT")
                found.append(candidate)
    except ProbeError:
        raise
    except OSError:
        raise ProbeError("REPOSITORY_SCAN_FAILED")
    return tuple(sorted(found, key=lambda path: os.fsencode(str(path))))


def _leakage_evidence(
    repository_root: Path,
    fingerprints: _PrivateInputFingerprints,
    private_values: Set[bytes],
) -> Dict[str, Any]:
    match_tokens: Set[bytes] = set()
    checked_files = 0
    for candidate in _repository_files(repository_root):
        try:
            data = harness.read_stable_file(
                candidate,
                max_bytes=16 * 1024 * 1024,
            ).data
        except harness.HarnessError:
            raise ProbeError("REPOSITORY_SCAN_FAILED")
        checked_files += 1
        if data:
            digest = hashlib.sha256(data).digest()
            if digest in fingerprints.file_hashes:
                match_tokens.add(b"file\0" + digest)
        for line in harness._split_physical_lines(data):
            stripped = line.rstrip(b"\r\n").strip()
            if len(stripped) >= MIN_PRIVATE_LINE_BYTES:
                digest = hashlib.sha256(stripped).digest()
                if digest in fingerprints.line_hashes:
                    match_tokens.add(b"line\0" + digest)
        for digest in _token_fingerprints(data):
            if digest in fingerprints.token_hashes:
                match_tokens.add(b"token\0" + digest)
        for value in private_values:
            if value in data:
                match_tokens.add(b"value\0" + hashlib.sha256(value).digest())
    return {
        "checked_repository_files": checked_files,
        "private_input_file_count": fingerprints.observed_file_count,
        "nonempty_private_input_file_count": fingerprints.nonempty_file_count,
        "source_file_fingerprint_count": len(fingerprints.file_hashes),
        "source_line_fingerprint_count": len(fingerprints.line_hashes),
        "source_token_fingerprint_count": len(fingerprints.token_hashes),
        "private_identifier_count": len(private_values),
        "match_count": len(match_tokens),
        "exact_file_match_count": sum(
            token.startswith(b"file\0") for token in match_tokens
        ),
        "exact_line_match_count": sum(
            token.startswith(b"line\0") for token in match_tokens
        ),
        "token_match_count": sum(
            token.startswith(b"token\0") for token in match_tokens
        ),
        "private_value_match_count": sum(
            token.startswith(b"value\0") for token in match_tokens
        ),
        "passed": not match_tokens,
        "minimum_line_bytes": MIN_PRIVATE_LINE_BYTES,
        "minimum_token_bytes": MIN_PRIVATE_TOKEN_BYTES,
    }


def _synthetic_candidate_evidence(
    repository_root: Path,
    protected_roots: Sequence[Path],
    *,
    temporary_parent: Optional[Path] = None,
) -> Dict[str, Any]:
    fixture_root = (repository_root / "fixtures" / "m1a" / "candidate").resolve(strict=True)
    requests = (
        harness.SourceRequest(
            fixture_root / "source-a.yml", "localisation/opaque-a.yml"
        ),
        harness.SourceRequest(
            fixture_root / "source-b.yml", "localisation/opaque-b.yml"
        ),
    )
    blobs = harness.snapshot_sources(requests)
    temporary_parent = (
        Path(tempfile.gettempdir()).resolve(strict=True)
        if temporary_parent is None
        else temporary_parent.resolve(strict=True)
    )
    harness.assert_root_sets_disjoint([temporary_parent], tuple(protected_roots) + (fixture_root,))
    with tempfile.TemporaryDirectory(prefix="m1a-candidate-a-", dir=str(temporary_parent)) as first_dir:
        with tempfile.TemporaryDirectory(prefix="m1a-candidate-b-", dir=str(temporary_parent)) as second_dir:
            first_root = Path(first_dir).resolve(strict=True)
            second_root = Path(second_dir).resolve(strict=True)
            harness.assert_root_sets_disjoint(
                [first_root, second_root], tuple(protected_roots) + (fixture_root,)
            )
            first = harness.build_candidate(
                harness.seal_disposable_root(first_root, tuple(protected_roots) + (fixture_root,)),
                blobs,
            )
            second = harness.build_candidate(
                harness.seal_disposable_root(second_root, tuple(protected_roots) + (fixture_root,)),
                blobs,
            )
            return {
                "build_count": 2,
                "manifest_sha256": first.manifest_sha256,
                "tree_sha256": first.tree_sha256,
                "identical": (
                    first.manifest_sha256 == second.manifest_sha256
                    and first.tree_sha256 == second.tree_sha256
                ),
                "temporary_parent_disjoint": True,
                "active_path_writes": 0,
            }


def collect_evidence(
    *,
    home: Path,
    repository_root: Path,
    candidate_temporary_parent: Optional[Path] = None,
    between_discovery_hook: Optional[Any] = None,
) -> Dict[str, Any]:
    first_discovery = discover(home)
    blockers: Set[str] = {
        "CONCURRENT_SAME_UID_PATH_RACE_UNPROVEN",
        "CROSS_FILE_GENERATION_COHERENCE_UNPROVEN",
        "EFFECTIVE_LOAD_ORDER_UNPROVEN",
        "EXPORT_POLICY_UNRESOLVED",
        "REPLACE_LAYER_SEMANTICS_UNPROVEN",
    }
    if not first_discovery.game_roots:
        blockers.add("GAME_ROOT_UNAVAILABLE")
    if not first_discovery.workshop_roots:
        blockers.add("WORKSHOP_ROOT_UNAVAILABLE")
    if not first_discovery.steam_library_metadata_valid:
        blockers.add("STEAM_LIBRARY_METADATA_INVALID")
    if not first_discovery.active_load_files:
        blockers.add("ACTIVE_ORDER_METADATA_UNAVAILABLE")
    if first_discovery.local_descriptor_count:
        blockers.add("LOCAL_SOURCE_CONTENT_NOT_FOLLOWED")
    if first_discovery.launcher_databases:
        blockers.add("LAUNCHER_DB_SCHEMA_UNREAD")
    else:
        blockers.add("LAUNCHER_DB_METADATA_UNAVAILABLE")

    expected_files = first_discovery.observed_files
    identities: Dict[Tuple[int, int], bool] = {}
    opened_identities: Dict[Tuple[int, int], bool] = {}
    first_records: List[Dict[str, Any]] = []
    first_stable: Dict[str, Tuple[str, str, int, Tuple[int, int]]] = {}
    raw_by_path: Dict[str, bytes] = {}
    preparsed_reads = dict(first_discovery.discovery_metadata_reads)
    for located in expected_files:
        try:
            metadata = os.lstat(str(located.path))
        except OSError:
            raise ProbeError("SOURCE_UNAVAILABLE")
        identity = (metadata.st_dev, metadata.st_ino)
        if identity in identities:
            raise ProbeError("SOURCE_IDENTITY_ALIAS")
        identities[identity] = True
        stable = harness.read_stable_file(
            located.path,
            max_bytes=MAX_OBSERVED_FILE_BYTES,
        )
        if stable.identity in opened_identities:
            raise ProbeError("SOURCE_IDENTITY_ALIAS")
        if stable.identity != identity:
            raise ProbeError("GENERATION_MISMATCH")
        preparsed = preparsed_reads.get(located.path_id)
        if preparsed is not None and (
            stable.sha256 != preparsed.sha256
            or stable.generation_sha256 != preparsed.generation_sha256
            or stable.byte_count != preparsed.byte_count
            or stable.identity != preparsed.identity
            or stable.data != preparsed.data
        ):
            raise ProbeError("GENERATION_MISMATCH")
        opened_identities[stable.identity] = True
        first_stable[located.path_id] = (
            stable.sha256,
            stable.generation_sha256,
            stable.byte_count,
            stable.identity,
        )
        raw_by_path[located.path_id] = stable.data
        first_records.append(
            {
                "path_id": located.path_id,
                "role": located.role,
                "source_id": located.source_id,
                "sha256": stable.sha256,
                "generation": stable.generation_sha256,
                "size": stable.byte_count,
            }
        )

    fingerprints = _private_input_fingerprints(
        expected_files,
        raw_by_path,
        preparsed=first_discovery.discovery_metadata_fingerprints,
    )

    inventory = _empty_inventory()
    headers = {
        "english": 0,
        "russian": 0,
        "other": 0,
        "misplaced": 0,
        "missing_or_multiple": 0,
    }
    corpus_by_role: Dict[str, Dict[str, int]] = {}
    cohorts = {
        "development": {
            "file_count": 0,
            "byte_count": 0,
            "roundtrip_failures": 0,
            "inventory": _empty_inventory(),
        },
        "holdout": {
            "file_count": 0,
            "byte_count": 0,
            "roundtrip_failures": 0,
            "inventory": _empty_inventory(),
        },
    }
    roundtrip_failures = 0
    key_sources: Dict[str, Set[str]] = {}
    key_occurrences: Dict[str, int] = {}
    key_source_files: Dict[Tuple[str, str], Set[str]] = {}
    key_source_occurrences: Dict[Tuple[str, str], int] = {}
    private_values: Set[bytes] = set(first_discovery.private_path_values)
    descriptor_total = {
        "descriptor_count": 0,
        "invalid_utf8_count": 0,
        "unknown_field_occurrences": 0,
        "dependency_value_count": 0,
        "replace_localisation_count": 0,
        "unsupported_syntax_occurrences": 0,
        "unterminated_block_count": 0,
        "field_occurrences": {
            field: 0
            for field in (
                "dependencies",
                "name",
                "path",
                "picture",
                "remote_file_id",
                "replace_path",
                "supported_version",
                "tags",
                "version",
            )
        },
    }
    active_evidence = {
        "present": False,
        "valid_json": False,
        "enabled_count": 0,
        "enabled_unique": False,
        "stored_order_digest": None,
        "disabled_dlc_count": 0,
    }
    version_verified = False

    for located in expected_files:
        data = raw_by_path[located.path_id]
        if located.role in (
            "official",
            "official_replace",
            "workshop",
            "workshop_replace",
        ):
            document = harness.inspect_bytes(data)
            _add_inventory(inventory, document.inventory)
            if document.render_identity() != data:
                roundtrip_failures += 1
            headers[_header_class(data, document.inventory.language_header_lines)] += 1
            role = corpus_by_role.setdefault(located.role, {"file_count": 0, "byte_count": 0})
            role["file_count"] += 1
            role["byte_count"] += len(data)
            cohort_name = "holdout" if bytes.fromhex(document.inventory.sha256)[0] <= 51 else "development"
            cohorts[cohort_name]["file_count"] += 1
            cohorts[cohort_name]["byte_count"] += len(data)
            cohorts[cohort_name]["roundtrip_failures"] += int(
                document.render_identity() != data
            )
            _add_inventory(cohorts[cohort_name]["inventory"], document.inventory)
            for key_hash in _entry_key_hashes(data):
                key_sources.setdefault(key_hash, set()).add(located.source_id)
                key_occurrences[key_hash] = key_occurrences.get(key_hash, 0) + 1
                source_key = (key_hash, located.source_id)
                key_source_files.setdefault(source_key, set()).add(located.path_id)
                key_source_occurrences[source_key] = (
                    key_source_occurrences.get(source_key, 0) + 1
                )
        elif "descriptor" in located.role:
            item = _descriptor_evidence(data, private_values)
            _merge_descriptor_evidence(descriptor_total, item)
        elif located.role == "active_load":
            active_evidence = _active_load_evidence(data, private_values)
        elif located.role == "version_metadata":
            version_verified = version_verified or _version_matches(data)

    if not version_verified:
        blockers.add("GAME_VERSION_UNVERIFIED")
    if not active_evidence["valid_json"]:
        blockers.add("ACTIVE_ORDER_METADATA_UNAVAILABLE")
    if (
        descriptor_total["invalid_utf8_count"]
        or descriptor_total["unknown_field_occurrences"]
        or descriptor_total["unsupported_syntax_occurrences"]
        or descriptor_total["unterminated_block_count"]
    ):
        blockers.add("DESCRIPTOR_SCHEMA_UNSUPPORTED")
    if descriptor_total["dependency_value_count"]:
        blockers.add("DEPENDENCY_GRAPH_UNPROVEN")

    format_blocker_count = (
        inventory["utf8_invalid_files"]
        + (len(first_discovery.localisation) - inventory["files_with_bom"])
        + inventory["hidden_bom_count"]
        + inventory["newline_styles"]["mixed"]
        + inventory["newline_styles"]["CR"]
        + inventory["malformed_lines"]
        + inventory["unknown_lines"]
        + inventory["unknown_escape_occurrences"]
        + inventory["markup"]["unknown_or_ambiguous"]
        + headers["misplaced"]
        + headers["missing_or_multiple"]
    )
    if format_blocker_count:
        blockers.add("FORMAT_PROFILE_HAS_BLOCKERS")

    first_manifest = _run_generation_digest(first_records, first_discovery)
    del raw_by_path

    if between_discovery_hook is not None:
        between_discovery_hook()
    second_discovery = discover(home)
    if [item.path_id for item in second_discovery.observed_files] != [
        item.path_id for item in expected_files
    ]:
        raise ProbeError("GENERATION_MISMATCH")
    second_records: List[Dict[str, Any]] = []
    second_identities: Dict[Tuple[int, int], bool] = {}
    second_preparsed_reads = dict(second_discovery.discovery_metadata_reads)
    for located in second_discovery.observed_files:
        stable = harness.read_stable_file(
            located.path,
            max_bytes=MAX_OBSERVED_FILE_BYTES,
        )
        if stable.identity in second_identities:
            raise ProbeError("SOURCE_IDENTITY_ALIAS")
        second_identities[stable.identity] = True
        preparsed = second_preparsed_reads.get(located.path_id)
        if preparsed is not None and (
            stable.sha256 != preparsed.sha256
            or stable.generation_sha256 != preparsed.generation_sha256
            or stable.byte_count != preparsed.byte_count
            or stable.identity != preparsed.identity
            or stable.data != preparsed.data
        ):
            raise ProbeError("GENERATION_MISMATCH")
        observed = (
            stable.sha256,
            stable.generation_sha256,
            stable.byte_count,
            stable.identity,
        )
        if first_stable.get(located.path_id) != observed:
            raise ProbeError("GENERATION_MISMATCH")
        second_records.append(
            {
                "path_id": located.path_id,
                "role": located.role,
                "source_id": located.source_id,
                "sha256": stable.sha256,
                "generation": stable.generation_sha256,
                "size": stable.byte_count,
            }
        )
    second_manifest = _run_generation_digest(second_records, second_discovery)
    if first_manifest != second_manifest:
        raise ProbeError("GENERATION_MISMATCH")

    cross_source_groups = sum(len(sources) > 1 for sources in key_sources.values())
    cross_source_occurrences = sum(
        key_occurrences[key]
        for key, sources in key_sources.items()
        if len(sources) > 1
    )
    same_source_cross_file_groups = sum(
        len(paths) > 1 for paths in key_source_files.values()
    )
    same_source_cross_file_occurrences = sum(
        key_source_occurrences[source_key]
        for source_key, paths in key_source_files.items()
        if len(paths) > 1
    )
    leakage = _leakage_evidence(
        repository_root,
        fingerprints,
        private_values,
    )
    if not leakage["passed"]:
        return {
            "schema": SCHEMA,
            "status": "blocked",
            "code": "LEAKAGE_DETECTED",
            "leakage": leakage,
        }
    candidate = _synthetic_candidate_evidence(
        repository_root,
        first_discovery.protected_roots,
        temporary_parent=candidate_temporary_parent,
    )
    if not candidate["identical"]:
        raise ProbeError("CANDIDATE_NONDETERMINISTIC")

    corpus_file_count = len(first_discovery.localisation)
    corpus_byte_count = sum(value["byte_count"] for value in corpus_by_role.values())
    blockers = {code for code in blockers if code in PUBLIC_BLOCKERS}
    return {
        "schema": SCHEMA,
        "status": "ok",
        "environment": {
            "expected_game_version": EXPECTED_VERSION,
            "expected_checksum": EXPECTED_CHECKSUM,
            "local_version_metadata_verified": version_verified,
            "game_root_count": len(first_discovery.game_roots),
            "workshop_root_count": len(first_discovery.workshop_roots),
            "python_standard_library_only": True,
        },
        "corpus": {
            "file_count": corpus_file_count,
            "byte_count": corpus_byte_count,
            "by_role": corpus_by_role,
            "cohorts": cohorts,
            "roundtrip_pass_count": corpus_file_count - roundtrip_failures,
            "roundtrip_failure_count": roundtrip_failures,
            "generation_sha256": first_manifest,
            "pre_post_manifest_equal": True,
            "observed_file_count_including_metadata": len(expected_files),
        },
        "inventory": inventory,
        "language_headers": headers,
        "duplicates": {
            "same_source_cross_file_key_groups": same_source_cross_file_groups,
            "same_source_cross_file_occurrences": same_source_cross_file_occurrences,
            "cross_source_key_groups": cross_source_groups,
            "cross_source_occurrences": cross_source_occurrences,
        },
        "descriptors": {
            **descriptor_total,
            "workshop_source_count": first_discovery.workshop_source_count,
            "local_descriptor_count": first_discovery.local_descriptor_count,
            "local_source_content_followed": False,
        },
        "replace_layer": {
            "directory_count": first_discovery.localisation_replace_directory_count,
            "localisation_file_count": sum(
                item.role in ("official_replace", "workshop_replace")
                for item in first_discovery.localisation
            ),
            "current_version_precedence_proven": False,
        },
        "playset": {
            **active_evidence,
            "stored_order_is_effective_engine_order": False,
            "collision_winner_proven": False,
        },
        "launcher": {
            "database_file_count": len(first_discovery.launcher_databases),
            "database_bytes_in_source_manifest": bool(
                first_discovery.launcher_databases
            ),
            "database_opened_as_sqlite": False,
            "schema_semantics_proven": False,
            "source_writes": 0,
        },
        "candidate": candidate,
        "leakage": leakage,
        "containment": {
            "protected_root_count": len(first_discovery.protected_roots),
            "source_write_attempts": 0,
            "launcher_write_attempts": 0,
            "active_path_write_attempts": 0,
        },
        "format_blocker_count": format_blocker_count,
        "blockers": sorted(blockers),
    }


def _controlled_failure(code: str) -> Dict[str, Any]:
    if not _CODE.fullmatch(code):
        code = "UNEXPECTED_FAILURE"
    return {"schema": SCHEMA, "status": "blocked", "code": code}


class _RedactedArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise ProbeError("INVALID_ARGUMENTS")


def _parser() -> argparse.ArgumentParser:
    parser = _RedactedArgumentParser(
        description="M1A local aggregate evidence; accepts no private source paths"
    )
    parser.add_argument("command", choices=("collect",))
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command != "collect":
            raise ProbeError("UNKNOWN_COMMAND")
        repository_root = Path(__file__).resolve().parents[2]
        evidence = collect_evidence(home=Path.home(), repository_root=repository_root)
        sys.stdout.write(
            json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            + "\n"
        )
        return 0 if evidence.get("status") == "ok" else 2
    except ProbeError as error:
        sys.stdout.write(
            json.dumps(
                _controlled_failure(error.code),
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        return 2
    except (KeyboardInterrupt, SystemExit):
        sys.stdout.write(
            json.dumps(
                _controlled_failure("INTERRUPTED"),
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        return 2
    except BaseException:
        sys.stdout.write(
            json.dumps(
                _controlled_failure("UNEXPECTED_FAILURE"),
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
