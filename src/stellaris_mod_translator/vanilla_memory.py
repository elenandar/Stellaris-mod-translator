"""Private, version-pinned contextual memory for vanilla localisation."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import tempfile
import unicodedata
from urllib.parse import quote

from .engine import SafetyError
from .package_reviewed_mod import (
    _paths_overlap,
    _physical_path_identity,
    _physical_paths_overlap,
)
from .parser import (
    Entry,
    ParseError,
    ParseResourceLimit,
    ParsedFile,
    _protected_tokens,
    parse_localisation,
)
from .publication import (
    AtomicPublicationUnavailable,
    DestinationExistsError,
    atomic_publish_directory_no_replace,
)


SCHEMA_VERSION = 3
APPLICATION_ID = 0x534D5437
DATABASE_NAME = "vanilla-memory.sqlite3"
REPORT_NAME = "build-report.json"
MAX_SOURCE_FILE_BYTES = 128 * 1024 * 1024
MAX_MANIFEST_ENTRIES_PER_ROOT = 4_096
MAX_SOURCE_DIRECTORIES_PER_ROOT = 2_048
MAX_REGULAR_FILES_PER_ROOT = 2_048
MAX_SOURCE_BYTES_PER_ROOT = 128 * 1024 * 1024
MAX_YML_SOURCE_FILES_PER_ROOT = 1_024
MAX_YML_SOURCE_FILES_TOTAL = 2_048
MAX_PARSED_LINES_PER_LANGUAGE = 1_500_000
MAX_PARSED_LINES_TOTAL = 3_000_000
MAX_OCCURRENCES_PER_LANGUAGE = 1_000_000
MAX_OCCURRENCES_TOTAL = 2_000_000
MAX_PROTECTED_TOKENS_TOTAL = 1_500_000
MAX_RECORD_QUARANTINES_TOTAL = 500_000
MAX_FILE_QUARANTINES_TOTAL = 16_384
MAX_GAME_VERSION_BYTES = 256
MAX_QUARANTINED_KEY_CANDIDATES = 2_000_000
_HEX = frozenset("0123456789abcdef")
_SQLITE_HEADER = b"SQLite format 3\0"
_LANGUAGES = ("english", "russian")
_ALIGNMENT_STATES = frozenset(
    {
        "strict_reference",
        "duplicate_key",
        "missing_counterpart",
        "version_mismatch",
        "protected_atom_mismatch",
    }
)
_PAIR_STATES = frozenset(
    {
        "strict_reference",
        "version_mismatch",
        "protected_atom_mismatch",
    }
)
_SQLITE_SIDECAR_SUFFIXES = (
    "-journal",
    "-wal",
    "-shm",
)
_PARSE_QUARANTINE_REASONS = frozenset(
    {
        "invalid_utf8",
        "hidden_bom",
        "nul_control",
        "c0_control",
        "c1_control",
        "unicode_format_control",
        "unicode_line_separator",
        "bare_cr",
        "mixed_newlines",
        "malformed_language_header",
        "missing_language_header",
        "multiple_language_headers",
        "english_header_not_first_line",
        "unsupported_escape",
        "ambiguous_markup",
        "unexpected_language_header",
        "unattributed_malformed_record",
        "parse_error",
    }
)
_RECORD_QUARANTINE_REASONS = frozenset(
    {
        "unsupported_escape",
        "ambiguous_markup",
        "malformed_syntax",
    }
)
_LOGICAL_DIGEST_DOMAIN = b"SMT_CONTEXTUAL_VANILLA_MEMORY_LOGICAL_V3"
_MANIFEST_DIGEST_DOMAIN = b"SMT_VANILLA_SOURCE_MANIFEST_V1"
_DATASET_DIGEST_DOMAIN = b"SMT_VANILLA_DATASET_V1"
_OCCURRENCE_ID_DOMAIN = b"SMT_VANILLA_OCCURRENCE_ID_V1"
_QUARANTINE_ID_DOMAIN = b"SMT_VANILLA_QUARANTINE_ID_V1"
_ALIGNMENT_ID_DOMAIN = b"SMT_VANILLA_ALIGNMENT_ID_V1"
_PAIR_ID_DOMAIN = b"SMT_VANILLA_REFERENCE_PAIR_ID_V1"
_TOKEN_SIGNATURE_DOMAIN = b"SMT_VANILLA_TOKEN_SIGNATURE_V1"
_KEY_OCCUPANCY_SCAN_CONTRACT = "ascii_line_key_occupancy_v1"
_SQLITE_CACHE_KIB = 64 * 1024


_SCHEMA = """
CREATE TABLE metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 3),
    application_id INTEGER NOT NULL CHECK (application_id = 1397576759),
    game_version TEXT NOT NULL CHECK (
        length(game_version) BETWEEN 1 AND 256
    ),
    build_status TEXT NOT NULL CHECK (
        build_status IN ('COMPLETE', 'COMPLETE_WITH_QUARANTINED_RECORDS')
    ),
    english_manifest_sha256 TEXT NOT NULL CHECK (
        length(english_manifest_sha256) = 64
    ),
    russian_manifest_sha256 TEXT NOT NULL CHECK (
        length(russian_manifest_sha256) = 64
    ),
    english_dataset_sha256 TEXT NOT NULL CHECK (
        length(english_dataset_sha256) = 64
    ),
    russian_dataset_sha256 TEXT NOT NULL CHECK (
        length(russian_dataset_sha256) = 64
    ),
    logical_digest TEXT NOT NULL CHECK (length(logical_digest) = 64),
    english_files INTEGER NOT NULL CHECK (english_files >= 0),
    russian_files INTEGER NOT NULL CHECK (russian_files >= 0),
    english_occurrences INTEGER NOT NULL CHECK (english_occurrences >= 0),
    russian_occurrences INTEGER NOT NULL CHECK (russian_occurrences >= 0),
    strict_eligible_pairs INTEGER NOT NULL CHECK (
        strict_eligible_pairs >= 0
    ),
    duplicate_key_occurrences INTEGER NOT NULL CHECK (
        duplicate_key_occurrences >= 0
    ),
    missing_counterparts INTEGER NOT NULL CHECK (
        missing_counterparts >= 0
    ),
    version_mismatches INTEGER NOT NULL CHECK (version_mismatches >= 0),
    protected_atom_mismatches INTEGER NOT NULL CHECK (
        protected_atom_mismatches >= 0
    ),
    malformed_record_units INTEGER NOT NULL CHECK (
        malformed_record_units >= 0
    ),
    malformed_file_units INTEGER NOT NULL CHECK (
        malformed_file_units >= 0
    ),
    quarantined_total INTEGER NOT NULL CHECK (quarantined_total >= 0),
    context_path_mismatches INTEGER NOT NULL CHECK (
        context_path_mismatches >= 0
        AND context_path_mismatches <= (
            strict_eligible_pairs
            + version_mismatches
            + protected_atom_mismatches
        )
    ),
    ambiguous_english_groups INTEGER NOT NULL CHECK (
        ambiguous_english_groups >= 0
    ),
    key_alias_groups INTEGER NOT NULL CHECK (key_alias_groups >= 0),
    source_mutations INTEGER NOT NULL CHECK (source_mutations = 0),
    ollama_calls INTEGER NOT NULL CHECK (ollama_calls = 0),
    CHECK (
        english_occurrences + russian_occurrences
        = 2 * (
            strict_eligible_pairs
            + version_mismatches
            + protected_atom_mismatches
        )
        + duplicate_key_occurrences
        + missing_counterparts
    ),
    CHECK (
        quarantined_total
        = duplicate_key_occurrences
        + missing_counterparts
        + 2 * version_mismatches
        + 2 * protected_atom_mismatches
        + malformed_record_units
        + malformed_file_units
    ),
    CHECK (
        (
            quarantined_total = 0
            AND build_status = 'COMPLETE'
        )
        OR (
            quarantined_total > 0
            AND build_status = 'COMPLETE_WITH_QUARANTINED_RECORDS'
        )
    )
) STRICT;

CREATE TABLE manifest_entries (
    language TEXT NOT NULL CHECK (language IN ('english', 'russian')),
    entry_kind TEXT NOT NULL CHECK (entry_kind IN ('directory', 'file')),
    relative_path TEXT NOT NULL,
    byte_count INTEGER CHECK (
        (entry_kind = 'directory' AND byte_count IS NULL)
        OR (entry_kind = 'file' AND byte_count >= 0)
    ),
    content_sha256 TEXT CHECK (
        (entry_kind = 'directory' AND content_sha256 IS NULL)
        OR (
            entry_kind = 'file'
            AND content_sha256 IS NOT NULL
            AND length(content_sha256) = 64
        )
    ),
    PRIMARY KEY (language, relative_path)
) STRICT, WITHOUT ROWID;

CREATE TABLE source_files (
    language TEXT NOT NULL CHECK (language IN ('english', 'russian')),
    relative_path TEXT NOT NULL,
    file_sha256 TEXT NOT NULL CHECK (length(file_sha256) = 64),
    byte_count INTEGER NOT NULL CHECK (byte_count >= 0),
    parse_state TEXT NOT NULL CHECK (
        parse_state IN ('parsed', 'quarantined')
    ),
    parse_reason TEXT,
    bom INTEGER CHECK (bom IS NULL OR bom IN (0, 1)),
    newline_style TEXT CHECK (
        newline_style IS NULL OR newline_style IN ('LF', 'CRLF')
    ),
    key_occupancy_scan_contract TEXT,
    key_occupancy_candidate_count INTEGER NOT NULL CHECK (
        key_occupancy_candidate_count >= 0
    ),
    occurrence_count INTEGER NOT NULL CHECK (occurrence_count >= 0),
    quarantine_count INTEGER NOT NULL CHECK (quarantine_count >= 0),
    PRIMARY KEY (language, relative_path),
    FOREIGN KEY (language, relative_path)
        REFERENCES manifest_entries(language, relative_path),
    CHECK (
        (
            parse_state = 'parsed'
            AND parse_reason IS NULL
            AND bom IS NOT NULL
            AND newline_style IS NOT NULL
            AND key_occupancy_scan_contract IS NULL
            AND key_occupancy_candidate_count = 0
        )
        OR (
            parse_state = 'quarantined'
            AND parse_reason IS NOT NULL
            AND bom IS NULL
            AND newline_style IS NULL
            AND key_occupancy_scan_contract
                = 'ascii_line_key_occupancy_v1'
            AND occurrence_count = 0
            AND quarantine_count = 1
        )
    )
) STRICT, WITHOUT ROWID;

CREATE TABLE quarantined_key_occupancy (
    language TEXT NOT NULL CHECK (language IN ('english', 'russian')),
    relative_path TEXT NOT NULL,
    key_hint TEXT NOT NULL,
    candidate_count INTEGER NOT NULL CHECK (candidate_count > 0),
    PRIMARY KEY (language, relative_path, key_hint),
    FOREIGN KEY (language, relative_path)
        REFERENCES source_files(language, relative_path)
) STRICT, WITHOUT ROWID;

CREATE TABLE occurrences (
    sequence INTEGER PRIMARY KEY CHECK (sequence >= 0),
    occurrence_id TEXT NOT NULL UNIQUE CHECK (length(occurrence_id) = 64),
    language TEXT NOT NULL CHECK (language IN ('english', 'russian')),
    relative_path TEXT NOT NULL,
    occurrence_ordinal INTEGER NOT NULL CHECK (occurrence_ordinal >= 0),
    line_number INTEGER NOT NULL CHECK (line_number >= 1),
    localisation_key TEXT NOT NULL,
    version_suffix TEXT,
    human_value TEXT NOT NULL,
    protected_signature_sha256 TEXT NOT NULL CHECK (
        length(protected_signature_sha256) = 64
    ),
    source_sha256 TEXT NOT NULL CHECK (length(source_sha256) = 64),
    value_sha256 TEXT NOT NULL CHECK (length(value_sha256) = 64),
    alignment_state TEXT NOT NULL CHECK (
        alignment_state IN (
            'strict_reference',
            'duplicate_key',
            'missing_counterpart',
            'version_mismatch',
            'protected_atom_mismatch'
        )
    ),
    diagnostic_reason TEXT,
    counterpart_occurrence_id TEXT,
    context_path_match INTEGER CHECK (
        context_path_match IS NULL OR context_path_match IN (0, 1)
    ),
    global_text_ambiguous INTEGER NOT NULL CHECK (
        global_text_ambiguous IN (0, 1)
    ),
    key_alias_risk INTEGER NOT NULL CHECK (key_alias_risk IN (0, 1)),
    reference_status TEXT NOT NULL CHECK (
        reference_status = 'REFERENCE_ONLY'
    ),
    editorially_approved INTEGER NOT NULL CHECK (
        editorially_approved = 0
    ),
    FOREIGN KEY (language, relative_path)
        REFERENCES source_files(language, relative_path),
    FOREIGN KEY (counterpart_occurrence_id)
        REFERENCES occurrences(occurrence_id)
        DEFERRABLE INITIALLY DEFERRED,
    UNIQUE (language, relative_path, occurrence_ordinal),
    CHECK (
        (
            alignment_state = 'strict_reference'
            AND diagnostic_reason IS NULL
            AND counterpart_occurrence_id IS NOT NULL
            AND context_path_match IS NOT NULL
        )
        OR (
            alignment_state IN (
                'version_mismatch',
                'protected_atom_mismatch'
            )
            AND diagnostic_reason IS NOT NULL
            AND counterpart_occurrence_id IS NOT NULL
            AND context_path_match IS NOT NULL
            AND global_text_ambiguous = 0
        )
        OR (
            alignment_state IN ('duplicate_key', 'missing_counterpart')
            AND diagnostic_reason IS NOT NULL
            AND counterpart_occurrence_id IS NULL
            AND context_path_match IS NULL
            AND global_text_ambiguous = 0
        )
    )
) STRICT;

CREATE TABLE protected_tokens (
    occurrence_id TEXT NOT NULL,
    token_ordinal INTEGER NOT NULL CHECK (token_ordinal >= 0),
    token_kind TEXT NOT NULL CHECK (
        token_kind IN (
            'escaped_quote',
            'escaped_backslash',
            'escaped_newline',
            'dollar_reference',
            'bracket_expression',
            'icon',
            'format_control'
        )
    ),
    exact_token TEXT NOT NULL,
    PRIMARY KEY (occurrence_id, token_ordinal),
    FOREIGN KEY (occurrence_id) REFERENCES occurrences(occurrence_id)
) STRICT, WITHOUT ROWID;

CREATE TABLE unique_alignments (
    alignment_id TEXT PRIMARY KEY CHECK (length(alignment_id) = 64),
    english_occurrence_id TEXT NOT NULL UNIQUE,
    russian_occurrence_id TEXT NOT NULL UNIQUE,
    alignment_state TEXT NOT NULL CHECK (
        alignment_state IN (
            'strict_reference',
            'version_mismatch',
            'protected_atom_mismatch'
        )
    ),
    path_family_match INTEGER NOT NULL CHECK (
        path_family_match IN (0, 1)
    ),
    global_text_ambiguous INTEGER NOT NULL CHECK (
        global_text_ambiguous IN (0, 1)
    ),
    FOREIGN KEY (english_occurrence_id)
        REFERENCES occurrences(occurrence_id),
    FOREIGN KEY (russian_occurrence_id)
        REFERENCES occurrences(occurrence_id),
    CHECK (
        alignment_state = 'strict_reference'
        OR global_text_ambiguous = 0
    )
) STRICT, WITHOUT ROWID;

CREATE TABLE reference_pairs (
    pair_id TEXT PRIMARY KEY CHECK (length(pair_id) = 64),
    alignment_id TEXT NOT NULL UNIQUE,
    english_occurrence_id TEXT NOT NULL UNIQUE,
    russian_occurrence_id TEXT NOT NULL UNIQUE,
    context_path_match INTEGER NOT NULL CHECK (
        context_path_match IN (0, 1)
    ),
    global_text_ambiguous INTEGER NOT NULL CHECK (
        global_text_ambiguous IN (0, 1)
    ),
    reference_status TEXT NOT NULL CHECK (
        reference_status = 'REFERENCE_ONLY'
    ),
    editorially_approved INTEGER NOT NULL CHECK (
        editorially_approved = 0
    ),
    FOREIGN KEY (alignment_id) REFERENCES unique_alignments(alignment_id),
    FOREIGN KEY (english_occurrence_id)
        REFERENCES occurrences(occurrence_id),
    FOREIGN KEY (russian_occurrence_id)
        REFERENCES occurrences(occurrence_id)
) STRICT, WITHOUT ROWID;

CREATE TABLE quarantine_records (
    sequence INTEGER PRIMARY KEY CHECK (sequence >= 0),
    quarantine_id TEXT NOT NULL UNIQUE CHECK (length(quarantine_id) = 64),
    language TEXT NOT NULL CHECK (language IN ('english', 'russian')),
    relative_path TEXT NOT NULL,
    quarantine_scope TEXT NOT NULL CHECK (
        quarantine_scope IN ('file', 'record')
    ),
    occurrence_ordinal INTEGER,
    line_number INTEGER,
    key_hint TEXT,
    source_sha256 TEXT NOT NULL CHECK (length(source_sha256) = 64),
    diagnostic_reason TEXT NOT NULL,
    FOREIGN KEY (language, relative_path)
        REFERENCES source_files(language, relative_path),
    CHECK (
        (
            quarantine_scope = 'file'
            AND occurrence_ordinal IS NULL
            AND line_number IS NULL
            AND key_hint IS NULL
        )
        OR (
            quarantine_scope = 'record'
            AND occurrence_ordinal >= 0
            AND line_number >= 1
            AND key_hint IS NOT NULL
        )
    )
) STRICT;

CREATE INDEX occurrences_key_language
    ON occurrences(localisation_key, language);
CREATE INDEX occurrences_alignment_state
    ON occurrences(alignment_state);
CREATE INDEX quarantine_reason
    ON quarantine_records(diagnostic_reason);
"""


@dataclass(frozen=True)
class _StatIdentity:
    device: int
    inode: int
    mode: int
    size: int
    modified_ns: int
    changed_ns: int
    link_count: int


@dataclass(frozen=True)
class _ManifestEntry:
    relative_path: str
    kind: str
    byte_count: int | None
    content_sha256: str | None
    identity: _StatIdentity


@dataclass(frozen=True)
class _SourceFile:
    language: str
    relative_path: str
    data: bytes
    sha256: str
    identity: _StatIdentity
    quarantined_key_occupancy: tuple[tuple[str, int], ...]
    parsed: ParsedFile | None
    parse_reason: str | None


@dataclass(frozen=True)
class _SourceSnapshot:
    root: Path
    language: str
    manifest_entries: tuple[_ManifestEntry, ...]
    source_files: tuple[_SourceFile, ...]
    manifest_sha256: str
    dataset_sha256: str
    root_identity: _StatIdentity


@dataclass
class _BuildResourceBudget:
    yml_source_files: int = 0
    parsed_lines: int = 0
    occurrences: int = 0
    protected_tokens: int = 0
    record_quarantines: int = 0
    file_quarantines: int = 0
    quarantined_key_candidates: int = 0


@dataclass(frozen=True)
class _Token:
    ordinal: int
    kind: str
    exact: str


@dataclass(frozen=True)
class _Occurrence:
    sequence: int
    occurrence_id: str
    language: str
    relative_path: str
    ordinal: int
    line_number: int
    key: str
    version_suffix: str | None
    value: str
    tokens: tuple[_Token, ...]
    protected_signature_sha256: str
    source_sha256: str
    value_sha256: str
    alignment_state: str = "missing_counterpart"
    diagnostic_reason: str | None = "missing_counterpart"
    counterpart_occurrence_id: str | None = None
    context_path_match: bool | None = None
    global_text_ambiguous: bool = False
    key_alias_risk: bool = False


@dataclass(frozen=True)
class _Quarantine:
    sequence: int
    quarantine_id: str
    language: str
    relative_path: str
    scope: str
    ordinal: int | None
    line_number: int | None
    key_hint: str | None
    source_sha256: str
    reason: str


@dataclass(frozen=True)
class _Alignment:
    alignment_id: str
    english_occurrence_id: str
    russian_occurrence_id: str
    state: str
    path_family_match: bool
    global_text_ambiguous: bool = False


@dataclass(frozen=True)
class _QuarantinedKeyOccupancy:
    language: str
    relative_path: str
    key_hint: str
    candidate_count: int


@dataclass(frozen=True)
class _MemoryRows:
    occurrences: tuple[_Occurrence, ...]
    quarantines: tuple[_Quarantine, ...]
    quarantined_key_occupancy: tuple[_QuarantinedKeyOccupancy, ...]
    alignments: tuple[_Alignment, ...]
    counts: dict[str, int]
    quarantine_by_reason: dict[str, int]


@dataclass(frozen=True)
class _DatabaseIdentity:
    stat: _StatIdentity
    sha256: str


@dataclass(frozen=True)
class _PublishedTreeIdentity:
    directory_device: int
    directory_inode: int
    files: tuple[tuple[str, _StatIdentity], ...]


class _SourceGenerationChanged(RuntimeError):
    pass


def build_vanilla_memory(
    english_root: Path,
    russian_root: Path,
    game_version: str,
    output: Path,
) -> dict[str, object]:
    """Build and atomically publish a private contextual reference memory."""
    try:
        return _build_vanilla_memory(
            english_root,
            russian_root,
            game_version,
            output,
        )
    except SafetyError:
        raise
    except (OSError, sqlite3.Error, UnicodeError, ValueError) as exc:
        raise SafetyError("vanilla_memory_build_failed") from exc


def inspect_vanilla_memory(database: Path) -> dict[str, object]:
    """Validate a memory through a strictly read-only connection."""
    try:
        validated = _validate_database_read_only(database)
        _validate_private_output_directory(
            database.absolute().parent,
            _build_report(validated),
        )
        return _public_inspection(validated)
    except SafetyError:
        raise
    except (OSError, sqlite3.Error, UnicodeError, ValueError) as exc:
        raise SafetyError("vanilla_memory_inspect_failed") from exc


def _build_vanilla_memory(
    english_root: Path,
    russian_root: Path,
    game_version: str,
    output: Path,
) -> dict[str, object]:
    version = _validated_game_version(game_version)
    english = _validated_source_root(english_root, "english")
    russian = _validated_source_root(russian_root, "russian")
    output_abs = _validated_output(english, russian, output)

    drift_seen = False
    for attempt in range(2):
        try:
            if attempt:
                _require_output_absent(output_abs)
            budget = _BuildResourceBudget()
            english_snapshot = _snapshot_source_tree(
                english, "english", budget
            )
            russian_snapshot = _snapshot_source_tree(
                russian, "russian", budget
            )
            return _build_snapshot_generation(
                english_snapshot,
                russian_snapshot,
                version,
                output_abs,
            )
        except _SourceGenerationChanged:
            drift_seen = True
            continue
    if drift_seen:
        raise SafetyError("source_generation_changed_after_retry")
    raise AssertionError("unreachable source generation state")


def _build_snapshot_generation(
    english: _SourceSnapshot,
    russian: _SourceSnapshot,
    game_version: str,
    output: Path,
) -> dict[str, object]:
    rows = _build_memory_rows(english, russian)
    temp = Path(
        tempfile.mkdtemp(
            prefix=f".{output.name}.tmp-",
            dir=output.parent,
        )
    )
    os.chmod(temp, 0o700)
    published = False
    try:
        database = temp / DATABASE_NAME
        _create_database(database, english, russian, game_version, rows)
        before_publication = _validate_database_read_only(
            database,
            require_complete_output=False,
        )
        report = _build_report(before_publication)
        _write_private_file(
            temp / REPORT_NAME,
            _canonical_report_bytes(report),
        )
        _validate_private_output_directory(temp, report)
        prepublication_budget = _BuildResourceBudget()
        _verify_source_snapshot(english, prepublication_budget)
        _verify_source_snapshot(russian, prepublication_budget)
        publication_identity = _published_tree_identity(temp)
        try:
            atomic_publish_directory_no_replace(temp, output)
        except DestinationExistsError as exc:
            raise SafetyError(
                "output_appeared_before_publication"
            ) from exc
        except AtomicPublicationUnavailable as exc:
            raise SafetyError("atomic_no_replace_unavailable") from exc
        published = True

        try:
            postpublication_budget = _BuildResourceBudget()
            _verify_source_snapshot(english, postpublication_budget)
            _verify_source_snapshot(russian, postpublication_budget)
            after_publication = _validate_database_read_only(
                output / DATABASE_NAME
            )
            if after_publication != before_publication:
                raise SafetyError("post_publication_database_mismatch")
            _validate_private_output_directory(output, report)
        except BaseException as exc:
            if not _rollback_owned_publication(
                output, publication_identity
            ):
                raise SafetyError(
                    "post_publication_rollback_unproven"
                ) from exc
            published = False
            raise
        return report
    except _SourceGenerationChanged:
        raise
    finally:
        if not published and temp.exists():
            shutil.rmtree(temp)


def _validated_game_version(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise SafetyError("game_version_invalid")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SafetyError("game_version_invalid") from exc
    if len(encoded) > MAX_GAME_VERSION_BYTES:
        raise SafetyError("game_version_invalid")
    if any(
        not char.isascii()
        or not (char.isalnum() or char in " ._()+-")
        for char in value
    ):
        raise SafetyError("game_version_invalid")
    return value


def _validated_source_root(path: Path, label: str) -> Path:
    lexical = path.absolute()
    try:
        value = lexical.lstat()
    except OSError as exc:
        raise SafetyError(f"{label}_root_unavailable") from exc
    if stat.S_ISLNK(value.st_mode):
        raise SafetyError(f"{label}_root_symlink")
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise SafetyError(f"{label}_root_unavailable") from exc
    if not stat.S_ISDIR(value.st_mode) or not resolved.is_dir():
        raise SafetyError(f"{label}_root_not_directory")
    return resolved


def _validated_output(
    english: Path,
    russian: Path,
    output: Path,
) -> Path:
    lexical = output.absolute()
    _require_output_absent(lexical)
    try:
        parent = lexical.parent.resolve(strict=True)
        parent_stat = lexical.parent.lstat()
    except OSError as exc:
        raise SafetyError("output_parent_unavailable") from exc
    if (
        stat.S_ISLNK(parent_stat.st_mode)
        or not stat.S_ISDIR(parent_stat.st_mode)
    ):
        raise SafetyError("output_parent_unsafe")
    resolved = parent / lexical.name
    named_paths = (
        ("english", english, True),
        ("russian", russian, True),
        ("output", resolved, False),
    )
    physical = {
        label: _physical_path_identity(
            path,
            label=f"vanilla_memory_{label}",
            must_exist=must_exist,
        )
        for label, path, must_exist in named_paths
    }
    for index, (left_label, left, _) in enumerate(named_paths):
        for right_label, right, _ in named_paths[index + 1 :]:
            if _paths_overlap(left, right) or _physical_paths_overlap(
                physical[left_label],
                physical[right_label],
            ):
                raise SafetyError("vanilla_memory_path_overlap")
    return resolved


def _require_output_absent(path: Path) -> None:
    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise SafetyError("output_state_unavailable") from exc
    raise SafetyError("output_must_not_exist")


def _snapshot_source_tree(
    root: Path,
    language: str,
    budget: _BuildResourceBudget | None = None,
) -> _SourceSnapshot:
    if language not in _LANGUAGES:
        raise AssertionError("unsupported source language")
    if budget is None:
        budget = _BuildResourceBudget()
    root_before = _stable_directory_identity(root, "source_root")
    manifest: list[_ManifestEntry] = []
    source_files: list[_SourceFile] = []
    directory_count = 0
    regular_file_count = 0
    source_bytes = 0
    yml_source_files = 0
    language_parsed_lines = 0
    language_occurrences = 0
    seen_physical: set[tuple[int, int]] = {
        (root_before.device, root_before.inode)
    }
    portable_paths: dict[
        tuple[str, ...], tuple[tuple[str, ...], str]
    ] = {}

    pending_directories = [root]
    while pending_directories:
        current_path = pending_directories.pop()
        _stable_directory_identity(current_path, "source_directory")
        try:
            entries = os.scandir(current_path)
        except FileNotFoundError as exc:
            raise _SourceGenerationChanged() from exc
        except OSError as exc:
            raise SafetyError("source_inventory_failed") from exc
        try:
            for entry in entries:
                path = current_path / entry.name
                relative = path.relative_to(root)
                try:
                    is_directory = entry.is_dir(follow_symlinks=False)
                except FileNotFoundError as exc:
                    raise _SourceGenerationChanged() from exc
                except OSError as exc:
                    raise SafetyError("source_inventory_failed") from exc
                if is_directory:
                    if directory_count >= MAX_SOURCE_DIRECTORIES_PER_ROOT:
                        raise SafetyError("source_directory_limit_exceeded")
                    if len(manifest) >= MAX_MANIFEST_ENTRIES_PER_ROOT:
                        raise SafetyError("manifest_entry_limit_exceeded")
                    identity = _stable_directory_identity(
                        path, "source_directory"
                    )
                    physical_key = (identity.device, identity.inode)
                    if physical_key in seen_physical:
                        raise SafetyError("source_physical_alias")
                    seen_physical.add(physical_key)
                    _admit_portable_path(
                        portable_paths,
                        relative,
                        "directory",
                    )
                    manifest.append(
                        _ManifestEntry(
                            relative_path=relative.as_posix(),
                            kind="directory",
                            byte_count=None,
                            content_sha256=None,
                            identity=identity,
                        )
                    )
                    directory_count += 1
                    pending_directories.append(path)
                    continue

                is_yml = path.suffix.lower() == ".yml"
                if regular_file_count >= MAX_REGULAR_FILES_PER_ROOT:
                    raise SafetyError("source_file_limit_exceeded")
                if len(manifest) >= MAX_MANIFEST_ENTRIES_PER_ROOT:
                    raise SafetyError("manifest_entry_limit_exceeded")
                if is_yml:
                    if yml_source_files >= MAX_YML_SOURCE_FILES_PER_ROOT:
                        raise SafetyError("source_yml_file_limit_exceeded")
                    if budget.yml_source_files >= MAX_YML_SOURCE_FILES_TOTAL:
                        raise SafetyError(
                            "source_yml_file_total_limit_exceeded"
                        )
                data, identity = _read_stable_regular_file(
                    path,
                    aggregate_bytes_remaining=(
                        MAX_SOURCE_BYTES_PER_ROOT - source_bytes
                    ),
                )
                source_bytes += len(data)
                regular_file_count += 1
                if is_yml:
                    yml_source_files += 1
                    budget.yml_source_files += 1
                physical_key = (identity.device, identity.inode)
                if physical_key in seen_physical:
                    raise SafetyError("source_hardlink_alias")
                seen_physical.add(physical_key)
                _admit_portable_path(portable_paths, relative, "file")
                digest = _sha256(data)
                manifest.append(
                    _ManifestEntry(
                        relative_path=relative.as_posix(),
                        kind="file",
                        byte_count=len(data),
                        content_sha256=digest,
                        identity=identity,
                    )
                )
                if not is_yml:
                    continue
                parsed: ParsedFile | None
                reason: str | None
                language_occurrence_remaining = (
                    MAX_OCCURRENCES_PER_LANGUAGE - language_occurrences
                )
                total_occurrence_remaining = (
                    MAX_OCCURRENCES_TOTAL - budget.occurrences
                )
                occurrence_limit_code = (
                    "source_occurrence_language_limit_exceeded"
                    if language_occurrence_remaining
                    <= total_occurrence_remaining
                    else "source_occurrence_total_limit_exceeded"
                )
                try:
                    candidate = parse_localisation(
                        data,
                        max_lines=min(
                            MAX_PARSED_LINES_PER_LANGUAGE
                            - language_parsed_lines,
                            MAX_PARSED_LINES_TOTAL - budget.parsed_lines,
                        ),
                        max_entries=min(
                            language_occurrence_remaining,
                            total_occurrence_remaining,
                        ),
                        max_diagnostics=(
                            MAX_RECORD_QUARANTINES_TOTAL
                            - budget.record_quarantines
                        ),
                        max_protected_tokens=(
                            MAX_PROTECTED_TOKENS_TOTAL
                            - budget.protected_tokens
                        ),
                    )
                except ParseResourceLimit as exc:
                    code = str(exc)
                    if code == "source_occurrence_limit_exceeded":
                        code = occurrence_limit_code
                    raise SafetyError(code) from exc
                except ParseError as exc:
                    parsed = None
                    reason = _safe_reason(str(exc), "parse_error")
                else:
                    if candidate.language != language:
                        parsed = None
                        reason = "unexpected_language_header"
                    elif any(
                        _diagnostic_key_hint(
                            candidate.lines[
                                _diagnostic_line(
                                    diagnostic,
                                    len(candidate.lines),
                                )
                                - 1
                            ]
                        )
                        is None
                        for diagnostic in candidate.diagnostics
                    ):
                        parsed = None
                        reason = "unattributed_malformed_record"
                    else:
                        parsed = candidate
                        reason = None
                if parsed is None:
                    if budget.file_quarantines >= MAX_FILE_QUARANTINES_TOTAL:
                        raise SafetyError("file_quarantine_limit_exceeded")
                    budget.file_quarantines += 1
                else:
                    next_language_lines = (
                        language_parsed_lines + len(parsed.lines)
                    )
                    next_lines = budget.parsed_lines + len(parsed.lines)
                    if (
                        next_language_lines
                        > MAX_PARSED_LINES_PER_LANGUAGE
                        or next_lines > MAX_PARSED_LINES_TOTAL
                    ):
                        raise SafetyError("source_line_limit_exceeded")
                    language_parsed_lines = next_language_lines
                    budget.parsed_lines = next_lines
                    language_occurrences += len(parsed.entries)
                    budget.occurrences += len(parsed.entries)
                    budget.protected_tokens += sum(
                        len(item.protected) for item in parsed.entries
                    )
                    budget.record_quarantines += len(parsed.diagnostics)
                quarantined_key_occupancy = (
                    _quarantined_file_key_inventory(
                        data,
                        max_candidates=(
                            MAX_QUARANTINED_KEY_CANDIDATES
                            - budget.quarantined_key_candidates
                        ),
                    )
                    if parsed is None
                    else ()
                )
                candidate_count = sum(
                    count for _, count in quarantined_key_occupancy
                )
                budget.quarantined_key_candidates += candidate_count
                source_files.append(
                    _SourceFile(
                        language=language,
                        relative_path=relative.as_posix(),
                        data=data,
                        sha256=digest,
                        identity=identity,
                        quarantined_key_occupancy=quarantined_key_occupancy,
                        parsed=parsed,
                        parse_reason=reason,
                    )
                )
        except FileNotFoundError as exc:
            raise _SourceGenerationChanged() from exc
        except OSError as exc:
            raise SafetyError("source_inventory_failed") from exc
        finally:
            entries.close()

    manifest.sort(key=lambda item: item.relative_path)
    source_files.sort(key=lambda item: item.relative_path)
    root_after = _stable_directory_identity(root, "source_root")
    if root_after != root_before:
        raise _SourceGenerationChanged()
    manifest_digest = _manifest_digest(language, manifest)
    dataset_digest = _dataset_digest(language, source_files)
    return _SourceSnapshot(
        root=root,
        language=language,
        manifest_entries=tuple(manifest),
        source_files=tuple(source_files),
        manifest_sha256=manifest_digest,
        dataset_sha256=dataset_digest,
        root_identity=root_after,
    )


def _verify_source_snapshot(
    expected: _SourceSnapshot,
    budget: _BuildResourceBudget | None = None,
) -> None:
    current = _snapshot_source_tree(
        expected.root,
        expected.language,
        budget,
    )
    if _source_generation_signature(current) != _source_generation_signature(
        expected
    ):
        raise _SourceGenerationChanged()


def _source_generation_signature(
    snapshot: _SourceSnapshot,
) -> tuple[object, ...]:
    return (
        snapshot.root_identity,
        snapshot.manifest_sha256,
        snapshot.dataset_sha256,
        tuple(
            (
                item.relative_path,
                item.kind,
                item.byte_count,
                item.content_sha256,
                item.identity,
            )
            for item in snapshot.manifest_entries
        ),
    )


def _stable_directory_identity(path: Path, label: str) -> _StatIdentity:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        before = path.lstat()
        descriptor = os.open(path, flags)
    except FileNotFoundError as exc:
        raise _SourceGenerationChanged() from exc
    except OSError as exc:
        raise SafetyError(f"{label}_unsafe") from exc
    try:
        opened = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after = path.lstat()
    except FileNotFoundError as exc:
        raise _SourceGenerationChanged() from exc
    except OSError as exc:
        raise SafetyError(f"{label}_unsafe") from exc
    identities = tuple(_stat_identity(value) for value in (before, opened, after))
    if (
        any(not stat.S_ISDIR(value.st_mode) for value in (before, opened, after))
    ):
        raise SafetyError(f"{label}_unsafe")
    if identities[0] != identities[1] or identities[1] != identities[2]:
        raise _SourceGenerationChanged()
    return identities[1]


def _read_stable_regular_file(
    path: Path,
    *,
    aggregate_bytes_remaining: int,
) -> tuple[bytes, _StatIdentity]:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        before_path = path.lstat()
        descriptor = os.open(path, flags)
    except FileNotFoundError as exc:
        raise _SourceGenerationChanged() from exc
    except OSError as exc:
        raise SafetyError("source_file_open_failed") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size < 0
            or before.st_size > MAX_SOURCE_FILE_BYTES
        ):
            raise SafetyError("source_file_unsafe")
        if before.st_size > aggregate_bytes_remaining:
            raise SafetyError("source_bytes_limit_exceeded")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise _SourceGenerationChanged()
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise _SourceGenerationChanged()
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after_path = path.lstat()
    except FileNotFoundError as exc:
        raise _SourceGenerationChanged() from exc
    except OSError as exc:
        raise SafetyError("source_file_state_unavailable") from exc
    identities = tuple(
        _stat_identity(value)
        for value in (before_path, before, after, after_path)
    )
    if any(identity != identities[0] for identity in identities[1:]):
        raise _SourceGenerationChanged()
    return b"".join(chunks), identities[0]


def _stat_identity(value: os.stat_result) -> _StatIdentity:
    return _StatIdentity(
        device=value.st_dev,
        inode=value.st_ino,
        mode=value.st_mode,
        size=value.st_size,
        modified_ns=value.st_mtime_ns,
        changed_ns=value.st_ctime_ns,
        link_count=value.st_nlink,
    )


def _admit_portable_path(
    known: dict[tuple[str, ...], tuple[tuple[str, ...], str]],
    relative: Path,
    kind: str,
) -> None:
    _require_relative_path_value(relative.as_posix())
    exact = relative.parts
    key = _portable_path_key(relative)
    existing = known.get(key)
    if existing is not None and existing != (exact, kind):
        raise SafetyError("source_portable_path_collision")
    for length in range(1, len(key)):
        prefix = key[:length]
        exact_prefix = exact[:length]
        previous = known.get(prefix)
        if previous is not None:
            previous_exact, previous_kind = previous
            if previous_kind == "file" or previous_exact != exact_prefix:
                raise SafetyError("source_portable_path_collision")
        else:
            known[prefix] = (exact_prefix, "directory")
    known[key] = (exact, kind)


def _portable_path_key(path: Path) -> tuple[str, ...]:
    return tuple(
        unicodedata.normalize("NFD", part).casefold()
        for part in path.parts
    )


def _manifest_digest(
    language: str,
    entries: list[_ManifestEntry] | tuple[_ManifestEntry, ...],
) -> str:
    rows = [
        (
            item.kind,
            item.relative_path,
            item.byte_count,
            item.content_sha256,
        )
        for item in entries
    ]
    return _semantic_digest(
        _MANIFEST_DIGEST_DOMAIN,
        [("language", language), *[("entry", row) for row in rows]],
    )


def _dataset_digest(
    language: str,
    files: list[_SourceFile] | tuple[_SourceFile, ...],
) -> str:
    rows = [
        (
            item.relative_path,
            len(item.data),
            item.sha256,
        )
        for item in files
    ]
    return _semantic_digest(
        _DATASET_DIGEST_DOMAIN,
        [("language", language), *[("file", row) for row in rows]],
    )


def _build_memory_rows(
    english: _SourceSnapshot,
    russian: _SourceSnapshot,
) -> _MemoryRows:
    occurrences: list[_Occurrence] = []
    quarantines: list[_Quarantine] = []
    limits = _BuildResourceBudget()
    language_occurrences: Counter[str] = Counter()
    quarantined_key_occupancy: list[
        _QuarantinedKeyOccupancy
    ] = []
    for snapshot in (english, russian):
        for source_file in snapshot.source_files:
            if source_file.parsed is None:
                assert source_file.parse_reason is not None
                if limits.file_quarantines >= MAX_FILE_QUARANTINES_TOTAL:
                    raise SafetyError("file_quarantine_limit_exceeded")
                candidate_count = sum(
                    count
                    for _, count in source_file.quarantined_key_occupancy
                )
                if (
                    limits.quarantined_key_candidates + candidate_count
                    > MAX_QUARANTINED_KEY_CANDIDATES
                ):
                    raise SafetyError(
                        "quarantined_key_candidate_limit_exceeded"
                    )
                limits.file_quarantines += 1
                limits.quarantined_key_candidates += candidate_count
                quarantines.append(
                    _make_quarantine(
                        sequence=len(quarantines),
                        language=snapshot.language,
                        relative_path=source_file.relative_path,
                        scope="file",
                        ordinal=None,
                        line_number=None,
                        key_hint=None,
                        source_sha256=source_file.sha256,
                        reason=source_file.parse_reason,
                    )
                )
                quarantined_key_occupancy.extend(
                    _QuarantinedKeyOccupancy(
                        language=snapshot.language,
                        relative_path=source_file.relative_path,
                        key_hint=key_hint,
                        candidate_count=candidate_count,
                    )
                    for key_hint, candidate_count in (
                        source_file.quarantined_key_occupancy
                    )
                )
                continue
            parsed = source_file.parsed
            for ordinal, entry in enumerate(parsed.entries):
                if (
                    language_occurrences[snapshot.language]
                    >= MAX_OCCURRENCES_PER_LANGUAGE
                ):
                    raise SafetyError(
                        "source_occurrence_language_limit_exceeded"
                    )
                if limits.occurrences >= MAX_OCCURRENCES_TOTAL:
                    raise SafetyError("source_occurrence_total_limit_exceeded")
                if (
                    limits.protected_tokens + len(entry.protected)
                    > MAX_PROTECTED_TOKENS_TOTAL
                ):
                    raise SafetyError("protected_token_limit_exceeded")
                tokens = tuple(
                    _Token(
                        ordinal=index,
                        kind=_token_kind(token.original),
                        exact=token.original,
                    )
                    for index, token in enumerate(entry.protected)
                )
                language_occurrences[snapshot.language] += 1
                limits.occurrences += 1
                limits.protected_tokens += len(tokens)
                suffix = _entry_version_suffix(parsed, entry)
                raw_line = parsed.lines[entry.line_index]
                occurrence_id = _stable_hash(
                    _OCCURRENCE_ID_DOMAIN,
                    (
                        snapshot.language,
                        source_file.relative_path,
                        ordinal,
                        entry.key,
                        suffix,
                    ),
                )
                occurrences.append(
                    _Occurrence(
                        sequence=len(occurrences),
                        occurrence_id=occurrence_id,
                        language=snapshot.language,
                        relative_path=source_file.relative_path,
                        ordinal=ordinal,
                        line_number=entry.line_index + 1,
                        key=entry.key,
                        version_suffix=suffix,
                        value=entry.value,
                        tokens=tokens,
                        protected_signature_sha256=_token_signature(tokens),
                        source_sha256=_sha256(raw_line),
                        value_sha256=_sha256(entry.value.encode("utf-8")),
                    )
                )
            for diagnostic_index, diagnostic in enumerate(
                parsed.diagnostics
            ):
                if (
                    limits.record_quarantines
                    >= MAX_RECORD_QUARANTINES_TOTAL
                ):
                    raise SafetyError("record_quarantine_limit_exceeded")
                line = _diagnostic_line(diagnostic, len(parsed.lines))
                raw_line = parsed.lines[line - 1]
                reason = _diagnostic_reason(diagnostic)
                key_hint = _diagnostic_key_hint(raw_line)
                if key_hint is None:
                    raise SafetyError("parser_diagnostic_key_unavailable")
                quarantines.append(
                    _make_quarantine(
                        sequence=len(quarantines),
                        language=snapshot.language,
                        relative_path=source_file.relative_path,
                        scope="record",
                        ordinal=len(parsed.entries) + diagnostic_index,
                        line_number=line,
                        key_hint=key_hint,
                        source_sha256=_sha256(raw_line),
                        reason=reason,
                    )
                )
                limits.record_quarantines += 1

    updated = {item.occurrence_id: item for item in occurrences}
    english_by_key: dict[str, list[_Occurrence]] = defaultdict(list)
    russian_by_key: dict[str, list[_Occurrence]] = defaultdict(list)
    for item in occurrences:
        target = (
            english_by_key
            if item.language == "english"
            else russian_by_key
        )
        target[item.key].append(item)
    english_quarantine_by_key: Counter[str] = Counter(
        item.key_hint
        for item in quarantines
        if item.language == "english" and item.key_hint is not None
    )
    russian_quarantine_by_key: Counter[str] = Counter(
        item.key_hint
        for item in quarantines
        if item.language == "russian" and item.key_hint is not None
    )
    for item in quarantined_key_occupancy:
        target = (
            english_quarantine_by_key
            if item.language == "english"
            else russian_quarantine_by_key
        )
        target[item.key_hint] += item.candidate_count

    alignments: list[_Alignment] = []
    for key in sorted(
        set(english_by_key)
        | set(russian_by_key)
        | set(english_quarantine_by_key)
        | set(russian_quarantine_by_key)
    ):
        english_group = english_by_key.get(key, [])
        russian_group = russian_by_key.get(key, [])
        english_occupancy = (
            len(english_group) + english_quarantine_by_key[key]
        )
        russian_occupancy = (
            len(russian_group) + russian_quarantine_by_key[key]
        )
        if english_occupancy > 1 or russian_occupancy > 1:
            reason = _duplicate_reason(
                english_occupancy, russian_occupancy
            )
            for item in (*english_group, *russian_group):
                updated[item.occurrence_id] = replace(
                    item,
                    alignment_state="duplicate_key",
                    diagnostic_reason=reason,
                    counterpart_occurrence_id=None,
                    context_path_match=None,
                )
            continue
        if (
            not english_group
            or not russian_group
            or english_quarantine_by_key[key]
            or russian_quarantine_by_key[key]
        ):
            reason = (
                "counterpart_quarantined"
                if english_quarantine_by_key[key]
                or russian_quarantine_by_key[key]
                else "missing_counterpart"
            )
            for item in (*english_group, *russian_group):
                updated[item.occurrence_id] = replace(
                    item,
                    alignment_state="missing_counterpart",
                    diagnostic_reason=reason,
                    counterpart_occurrence_id=None,
                    context_path_match=None,
                )
            continue

        english_item = english_group[0]
        russian_item = russian_group[0]
        path_match = (
            _path_family(english_item.relative_path, "english")
            == _path_family(russian_item.relative_path, "russian")
        )
        if english_item.version_suffix != russian_item.version_suffix:
            state = "version_mismatch"
            reason = "version_mismatch"
        elif english_item.tokens != russian_item.tokens:
            state = "protected_atom_mismatch"
            reason = "protected_atom_mismatch"
        else:
            state = "strict_reference"
            reason = None
        updated[english_item.occurrence_id] = replace(
            english_item,
            alignment_state=state,
            diagnostic_reason=reason,
            counterpart_occurrence_id=russian_item.occurrence_id,
            context_path_match=path_match,
        )
        updated[russian_item.occurrence_id] = replace(
            russian_item,
            alignment_state=state,
            diagnostic_reason=reason,
            counterpart_occurrence_id=english_item.occurrence_id,
            context_path_match=path_match,
        )
        alignments.append(
            _Alignment(
                alignment_id=_stable_hash(
                    _ALIGNMENT_ID_DOMAIN,
                    (
                        english_item.occurrence_id,
                        russian_item.occurrence_id,
                    ),
                ),
                english_occurrence_id=english_item.occurrence_id,
                russian_occurrence_id=russian_item.occurrence_id,
                state=state,
                path_family_match=path_match,
            )
        )

    alias_groups = _key_alias_groups(tuple(updated.values()))
    alias_keys = {
        key
        for group in alias_groups
        for key in group
    }
    if alias_keys:
        for occurrence_id, item in tuple(updated.items()):
            if item.key in alias_keys:
                updated[occurrence_id] = replace(
                    item, key_alias_risk=True
                )

    strict_by_english_value: dict[str, list[_Alignment]] = defaultdict(list)
    for alignment in alignments:
        if alignment.state != "strict_reference":
            continue
        english_item = updated[alignment.english_occurrence_id]
        strict_by_english_value[english_item.value].append(alignment)
    ambiguous_alignment_ids: set[str] = set()
    ambiguous_groups = 0
    for group in strict_by_english_value.values():
        russian_values = {
            updated[item.russian_occurrence_id].value
            for item in group
        }
        if len(russian_values) <= 1:
            continue
        ambiguous_groups += 1
        ambiguous_alignment_ids.update(item.alignment_id for item in group)

    final_alignments: list[_Alignment] = []
    for alignment in alignments:
        ambiguous = alignment.alignment_id in ambiguous_alignment_ids
        final = replace(
            alignment,
            global_text_ambiguous=ambiguous,
        )
        final_alignments.append(final)
        if ambiguous:
            for occurrence_id in (
                alignment.english_occurrence_id,
                alignment.russian_occurrence_id,
            ):
                updated[occurrence_id] = replace(
                    updated[occurrence_id],
                    global_text_ambiguous=True,
                )

    final_occurrences = tuple(
        replace(updated[item.occurrence_id], sequence=index)
        for index, item in enumerate(occurrences)
    )
    final_quarantines = tuple(
        replace(item, sequence=index)
        for index, item in enumerate(quarantines)
    )
    final_alignments.sort(
        key=lambda item: (
            item.english_occurrence_id,
            item.russian_occurrence_id,
        )
    )
    counts = _derive_counts(
        english,
        russian,
        final_occurrences,
        final_quarantines,
        tuple(final_alignments),
        ambiguous_groups=ambiguous_groups,
        key_alias_groups=len(alias_groups),
    )
    quarantine_by_reason = _quarantine_reason_counts(
        final_occurrences,
        final_quarantines,
        tuple(final_alignments),
    )
    if sum(quarantine_by_reason.values()) != counts["quarantined_total"]:
        raise SafetyError("quarantine_count_algebra_invalid")
    return _MemoryRows(
        occurrences=final_occurrences,
        quarantines=final_quarantines,
        quarantined_key_occupancy=tuple(
            quarantined_key_occupancy
        ),
        alignments=tuple(final_alignments),
        counts=counts,
        quarantine_by_reason=quarantine_by_reason,
    )


def _make_quarantine(
    *,
    sequence: int,
    language: str,
    relative_path: str,
    scope: str,
    ordinal: int | None,
    line_number: int | None,
    key_hint: str | None,
    source_sha256: str,
    reason: str,
) -> _Quarantine:
    quarantine_id = _stable_hash(
        _QUARANTINE_ID_DOMAIN,
        (
            language,
            relative_path,
            scope,
            ordinal,
            line_number,
            key_hint,
            source_sha256,
            reason,
        ),
    )
    return _Quarantine(
        sequence=sequence,
        quarantine_id=quarantine_id,
        language=language,
        relative_path=relative_path,
        scope=scope,
        ordinal=ordinal,
        line_number=line_number,
        key_hint=key_hint,
        source_sha256=source_sha256,
        reason=reason,
    )


def _entry_version_suffix(
    parsed: ParsedFile,
    entry: Entry,
) -> str | None:
    raw = parsed.lines[entry.line_index]
    body = raw
    if body.endswith(b"\r\n"):
        body = body[:-2]
    elif body.endswith(b"\n"):
        body = body[:-1]
    quote_index = entry.value_start - 1
    if quote_index < 0 or body[quote_index : quote_index + 1] != b'"':
        raise SafetyError("parser_version_suffix_unavailable")
    prefix = body[:quote_index]
    cursor = 0
    while cursor < len(prefix) and prefix[cursor] in b" \t":
        cursor += 1
    key_bytes = entry.key.encode("ascii")
    if prefix[cursor : cursor + len(key_bytes)] != key_bytes:
        raise SafetyError("parser_version_suffix_unavailable")
    cursor += len(key_bytes)
    while cursor < len(prefix) and prefix[cursor] in b" \t":
        cursor += 1
    if prefix[cursor : cursor + 1] != b":":
        raise SafetyError("parser_version_suffix_unavailable")
    cursor += 1
    version_start = cursor
    while cursor < len(prefix) and 48 <= prefix[cursor] <= 57:
        cursor += 1
    version = prefix[version_start:cursor]
    space_start = cursor
    while cursor < len(prefix) and prefix[cursor] in b" \t":
        cursor += 1
    if cursor != len(prefix) or cursor == space_start:
        raise SafetyError("parser_version_suffix_unavailable")
    return version.decode("ascii") if version else None


def _token_kind(value: str) -> str:
    if value == r"\"":
        return "escaped_quote"
    if value == r"\\":
        return "escaped_backslash"
    if value == r"\n":
        return "escaped_newline"
    if value.startswith("$"):
        return "dollar_reference"
    if value.startswith("["):
        return "bracket_expression"
    if value.startswith("£"):
        return "icon"
    if value.startswith("§"):
        return "format_control"
    raise SafetyError("protected_token_kind_unknown")


def _token_signature(tokens: tuple[_Token, ...]) -> str:
    return _stable_hash(
        _TOKEN_SIGNATURE_DOMAIN,
        tuple(
            (item.ordinal, item.kind, item.exact)
            for item in tokens
        ),
    )


def _diagnostic_line(
    diagnostic: dict[str, object],
    line_count: int,
) -> int:
    line = diagnostic.get("line")
    if type(line) is not int or line < 1 or line > line_count:
        raise SafetyError("parser_diagnostic_invalid")
    return line


def _diagnostic_reason(diagnostic: dict[str, object]) -> str:
    code = diagnostic.get("code")
    reason = diagnostic.get("reason")
    if code != "unsupported_entry":
        return "malformed_syntax"
    if reason is None:
        return "malformed_syntax"
    return _safe_reason(reason, "malformed_syntax")


def _diagnostic_key_hint(raw_line: bytes) -> str | None:
    body = raw_line
    if body.endswith(b"\r\n"):
        body = body[:-2]
    elif body.endswith(b"\n"):
        body = body[:-1]
    cursor = 0
    while cursor < len(body) and body[cursor] in b" \t":
        cursor += 1
    start = cursor
    while cursor < len(body):
        byte = body[cursor]
        if (
            48 <= byte <= 57
            or 65 <= byte <= 90
            or 97 <= byte <= 122
            or byte in b"_.-"
        ):
            cursor += 1
            continue
        break
    if cursor == start:
        return None
    key = body[start:cursor]
    while cursor < len(body) and body[cursor] in b" \t":
        cursor += 1
    if body[cursor : cursor + 1] != b":":
        return None
    return key.decode("ascii")


def _quarantined_file_key_inventory(
    data: bytes,
    *,
    max_candidates: int,
) -> tuple[tuple[str, int], ...]:
    """Count a conservative superset of supported line-anchored keys."""
    inventory: Counter[str] = Counter()
    candidate_total = 0
    start = 0
    cursor = 0
    segment_index = 0
    while start < len(data):
        cursor = start
        while cursor < len(data) and data[cursor] not in (10, 13):
            cursor += 1
        segment = data[start:cursor]
        if (
            segment_index == 0
            and segment.startswith(b"\xef\xbb\xbf")
        ):
            segment = segment[3:]
        key_hint = _diagnostic_key_hint(segment)
        if key_hint is None:
            pass
        else:
            inventory[key_hint] += 1
            candidate_total += 1
            if candidate_total > max_candidates:
                raise SafetyError(
                    "quarantined_key_candidate_limit_exceeded"
                )
        if cursor >= len(data):
            break
        if (
            data[cursor] == 13
            and cursor + 1 < len(data)
            and data[cursor + 1] == 10
        ):
            cursor += 2
        else:
            cursor += 1
        start = cursor
        segment_index += 1
    return tuple(sorted(inventory.items()))


def _safe_reason(value: object, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    allowed = _PARSE_QUARANTINE_REASONS | _RECORD_QUARANTINE_REASONS
    return value if value in allowed else fallback


def _duplicate_reason(english_count: int, russian_count: int) -> str:
    if english_count > 1 and russian_count > 1:
        return "duplicate_key_both"
    if english_count > 1:
        return "duplicate_key_english"
    return "duplicate_key_russian"


def _path_family(relative_path: str, language: str) -> tuple[str, ...]:
    path = PurePosixPath(relative_path)
    parts = list(path.parts)
    suffix = f"_l_{language}.yml"
    if parts and parts[-1].endswith(suffix):
        parts[-1] = parts[-1][: -len(suffix)] + ".yml"
    return tuple(parts)


def _key_alias_groups(
    occurrences: tuple[_Occurrence, ...],
) -> tuple[tuple[str, ...], ...]:
    groups: dict[str, set[str]] = defaultdict(set)
    for item in occurrences:
        groups[unicodedata.normalize("NFD", item.key).casefold()].add(
            item.key
        )
    return tuple(
        tuple(sorted(values))
        for _, values in sorted(groups.items())
        if len(values) > 1
    )


def _derive_counts(
    english: _SourceSnapshot,
    russian: _SourceSnapshot,
    occurrences: tuple[_Occurrence, ...],
    quarantines: tuple[_Quarantine, ...],
    alignments: tuple[_Alignment, ...],
    *,
    ambiguous_groups: int,
    key_alias_groups: int,
) -> dict[str, int]:
    state_counts = Counter(item.alignment_state for item in occurrences)
    pair_counts = Counter(item.state for item in alignments)
    malformed_records = sum(
        item.scope == "record" for item in quarantines
    )
    malformed_files = sum(item.scope == "file" for item in quarantines)
    strict_pairs = pair_counts["strict_reference"]
    version_pairs = pair_counts["version_mismatch"]
    atom_pairs = pair_counts["protected_atom_mismatch"]
    duplicate_occurrences = state_counts["duplicate_key"]
    missing_occurrences = state_counts["missing_counterpart"]
    quarantined_total = (
        duplicate_occurrences
        + missing_occurrences
        + 2 * version_pairs
        + 2 * atom_pairs
        + malformed_records
        + malformed_files
    )
    counts = {
        "english_files": len(english.source_files),
        "russian_files": len(russian.source_files),
        "english_occurrences": sum(
            item.language == "english" for item in occurrences
        ),
        "russian_occurrences": sum(
            item.language == "russian" for item in occurrences
        ),
        "strict_eligible_pairs": strict_pairs,
        "duplicate_key_occurrences": duplicate_occurrences,
        "missing_counterparts": missing_occurrences,
        "version_mismatches": version_pairs,
        "protected_atom_mismatches": atom_pairs,
        "malformed_record_units": malformed_records,
        "malformed_file_units": malformed_files,
        "quarantined_total": quarantined_total,
        "context_path_mismatches": sum(
            not item.path_family_match for item in alignments
        ),
        "ambiguous_english_groups": ambiguous_groups,
        "key_alias_groups": key_alias_groups,
        "source_mutations": 0,
        "ollama_calls": 0,
    }
    _validate_count_algebra(counts)
    return counts


def _validate_count_algebra(counts: dict[str, int]) -> None:
    expected_occurrences = (
        2
        * (
            counts["strict_eligible_pairs"]
            + counts["version_mismatches"]
            + counts["protected_atom_mismatches"]
        )
        + counts["duplicate_key_occurrences"]
        + counts["missing_counterparts"]
    )
    actual_occurrences = (
        counts["english_occurrences"]
        + counts["russian_occurrences"]
    )
    expected_quarantine = (
        counts["duplicate_key_occurrences"]
        + counts["missing_counterparts"]
        + 2 * counts["version_mismatches"]
        + 2 * counts["protected_atom_mismatches"]
        + counts["malformed_record_units"]
        + counts["malformed_file_units"]
    )
    if (
        actual_occurrences != expected_occurrences
        or counts["quarantined_total"] != expected_quarantine
        or counts["context_path_mismatches"]
        > (
            counts["strict_eligible_pairs"]
            + counts["version_mismatches"]
            + counts["protected_atom_mismatches"]
        )
    ):
        raise SafetyError("vanilla_memory_count_algebra_invalid")


def _quarantine_reason_counts(
    occurrences: tuple[_Occurrence, ...],
    quarantines: tuple[_Quarantine, ...],
    alignments: tuple[_Alignment, ...],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    counts["duplicate_key"] = sum(
        item.alignment_state == "duplicate_key" for item in occurrences
    )
    counts["missing_counterpart"] = sum(
        item.alignment_state == "missing_counterpart"
        for item in occurrences
    )
    counts["version_mismatch"] = 2 * sum(
        item.state == "version_mismatch" for item in alignments
    )
    counts["protected_atom_mismatch"] = 2 * sum(
        item.state == "protected_atom_mismatch" for item in alignments
    )
    for item in quarantines:
        counts[item.reason] += 1
    return {
        key: value
        for key, value in sorted(counts.items())
        if value
    }


def _create_database(
    path: Path,
    english: _SourceSnapshot,
    russian: _SourceSnapshot,
    game_version: str,
    rows: _MemoryRows,
) -> None:
    descriptor = os.open(
        path,
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA temp_store = MEMORY")
        connection.execute(f"PRAGMA cache_size = -{_SQLITE_CACHE_KIB}")
        connection.executescript(_SCHEMA)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")

        status = (
            "COMPLETE"
            if rows.counts["quarantined_total"] == 0
            else "COMPLETE_WITH_QUARANTINED_RECORDS"
        )
        metadata_values = (
            SCHEMA_VERSION,
            APPLICATION_ID,
            game_version,
            status,
            english.manifest_sha256,
            russian.manifest_sha256,
            english.dataset_sha256,
            russian.dataset_sha256,
            "0" * 64,
            rows.counts["english_files"],
            rows.counts["russian_files"],
            rows.counts["english_occurrences"],
            rows.counts["russian_occurrences"],
            rows.counts["strict_eligible_pairs"],
            rows.counts["duplicate_key_occurrences"],
            rows.counts["missing_counterparts"],
            rows.counts["version_mismatches"],
            rows.counts["protected_atom_mismatches"],
            rows.counts["malformed_record_units"],
            rows.counts["malformed_file_units"],
            rows.counts["quarantined_total"],
            rows.counts["context_path_mismatches"],
            rows.counts["ambiguous_english_groups"],
            rows.counts["key_alias_groups"],
            0,
            0,
        )
        connection.execute(
            "INSERT INTO metadata VALUES (1, "
            + ", ".join("?" for _ in metadata_values)
            + ")",
            metadata_values,
        )
        connection.executemany(
            """
            INSERT INTO manifest_entries VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot.language,
                    item.kind,
                    item.relative_path,
                    item.byte_count,
                    item.content_sha256,
                )
                for snapshot in (english, russian)
                for item in snapshot.manifest_entries
            ],
        )
        occurrence_counts = Counter(
            (item.language, item.relative_path)
            for item in rows.occurrences
        )
        quarantine_counts = Counter(
            (item.language, item.relative_path)
            for item in rows.quarantines
        )
        connection.executemany(
            """
            INSERT INTO source_files VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                _source_file_database_row(
                    item,
                    occurrence_counts[
                        (item.language, item.relative_path)
                    ],
                    quarantine_counts[
                        (item.language, item.relative_path)
                    ],
                )
                for snapshot in (english, russian)
                for item in snapshot.source_files
            ],
        )
        connection.executemany(
            """
            INSERT INTO quarantined_key_occupancy
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    item.language,
                    item.relative_path,
                    item.key_hint,
                    item.candidate_count,
                )
                for item in rows.quarantined_key_occupancy
            ],
        )
        connection.executemany(
            """
            INSERT INTO occurrences VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    item.sequence,
                    item.occurrence_id,
                    item.language,
                    item.relative_path,
                    item.ordinal,
                    item.line_number,
                    item.key,
                    item.version_suffix,
                    item.value,
                    item.protected_signature_sha256,
                    item.source_sha256,
                    item.value_sha256,
                    item.alignment_state,
                    item.diagnostic_reason,
                    item.counterpart_occurrence_id,
                    (
                        None
                        if item.context_path_match is None
                        else int(item.context_path_match)
                    ),
                    int(item.global_text_ambiguous),
                    int(item.key_alias_risk),
                    "REFERENCE_ONLY",
                    0,
                )
                for item in rows.occurrences
            ],
        )
        connection.executemany(
            """
            INSERT INTO protected_tokens VALUES (?, ?, ?, ?)
            """,
            [
                (
                    occurrence.occurrence_id,
                    token.ordinal,
                    token.kind,
                    token.exact,
                )
                for occurrence in rows.occurrences
                for token in occurrence.tokens
            ],
        )
        connection.executemany(
            """
            INSERT INTO unique_alignments VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.alignment_id,
                    item.english_occurrence_id,
                    item.russian_occurrence_id,
                    item.state,
                    int(item.path_family_match),
                    int(item.global_text_ambiguous),
                )
                for item in rows.alignments
            ],
        )
        strict_alignments = tuple(
            item
            for item in rows.alignments
            if item.state == "strict_reference"
        )
        connection.executemany(
            """
            INSERT INTO reference_pairs VALUES (
                ?, ?, ?, ?, ?, ?, 'REFERENCE_ONLY', 0
            )
            """,
            [
                (
                    _stable_hash(
                        _PAIR_ID_DOMAIN,
                        (
                            item.alignment_id,
                            item.english_occurrence_id,
                            item.russian_occurrence_id,
                        ),
                    ),
                    item.alignment_id,
                    item.english_occurrence_id,
                    item.russian_occurrence_id,
                    int(item.path_family_match),
                    int(item.global_text_ambiguous),
                )
                for item in strict_alignments
            ],
        )
        connection.executemany(
            """
            INSERT INTO quarantine_records VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    item.sequence,
                    item.quarantine_id,
                    item.language,
                    item.relative_path,
                    item.scope,
                    item.ordinal,
                    item.line_number,
                    item.key_hint,
                    item.source_sha256,
                    item.reason,
                )
                for item in rows.quarantines
            ],
        )
        logical_digest = _logical_digest(connection)
        connection.execute(
            "UPDATE metadata SET logical_digest = ? WHERE singleton = 1",
            (logical_digest,),
        )
        connection.commit()
    except BaseException:
        if connection is not None:
            try:
                connection.rollback()
            except sqlite3.Error:
                pass
        raise
    finally:
        if connection is not None:
            connection.close()
    os.chmod(path, 0o600)
    _require_sidecars_absent(path)


def _source_file_database_row(
    item: _SourceFile,
    occurrence_count: int,
    quarantine_count: int,
) -> tuple[object, ...]:
    if item.parsed is None:
        if (
            item.parse_reason is None
            or occurrence_count != 0
            or quarantine_count != 1
        ):
            raise SafetyError("source_file_quarantine_invalid")
        return (
            item.language,
            item.relative_path,
            item.sha256,
            len(item.data),
            "quarantined",
            item.parse_reason,
            None,
            None,
            _KEY_OCCUPANCY_SCAN_CONTRACT,
            sum(
                count
                for _, count in item.quarantined_key_occupancy
            ),
            0,
            1,
        )
    expected_quarantine = len(item.parsed.diagnostics)
    if quarantine_count != expected_quarantine:
        raise SafetyError("source_file_quarantine_invalid")
    return (
        item.language,
        item.relative_path,
        item.sha256,
        len(item.data),
        "parsed",
        None,
        int(item.parsed.bom),
        "CRLF" if item.parsed.newline == b"\r\n" else "LF",
        None,
        0,
        occurrence_count,
        quarantine_count,
    )


def _write_private_file(path: Path, data: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(descriptor, 0o600)
        written = 0
        while written < len(data):
            count = os.write(descriptor, data[written:])
            if count <= 0:
                raise SafetyError("private_file_write_failed")
            written += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _build_report(validated: dict[str, object]) -> dict[str, object]:
    counts = validated["counts"]
    hashes = validated["hashes"]
    assert isinstance(counts, dict)
    assert isinstance(hashes, dict)
    return {
        "schema_version": validated["schema_version"],
        "status": validated["build_status"],
        "game_version": validated["game_version"],
        "hashes": dict(hashes),
        "counts": dict(counts),
        "source_generations": "PASS",
        "source_mutations": 0,
        "ollama_calls": 0,
    }


def _canonical_report_bytes(report: dict[str, object]) -> bytes:
    return (
        json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _public_inspection(
    validated: dict[str, object],
) -> dict[str, object]:
    counts = validated["counts"]
    hashes = validated["hashes"]
    assert isinstance(counts, dict)
    assert isinstance(hashes, dict)
    return {
        "schema_version": validated["schema_version"],
        "game_version": validated["game_version"],
        "hashes": dict(hashes),
        "counts": dict(counts),
    }


def _validate_private_output_directory(
    root: Path,
    report: dict[str, object],
) -> None:
    try:
        root_value = root.lstat()
    except OSError as exc:
        raise SafetyError("private_output_unavailable") from exc
    if (
        not stat.S_ISDIR(root_value.st_mode)
        or stat.S_IMODE(root_value.st_mode) != 0o700
    ):
        raise SafetyError("private_output_mode_invalid")
    try:
        entries = sorted(
            root.iterdir(), key=lambda item: item.name
        )
    except OSError as exc:
        raise SafetyError("private_output_inventory_failed") from exc
    if [item.name for item in entries] != [REPORT_NAME, DATABASE_NAME]:
        raise SafetyError("private_output_inventory_invalid")
    for item in entries:
        try:
            value = item.lstat()
        except OSError as exc:
            raise SafetyError("private_output_inventory_failed") from exc
        if (
            not stat.S_ISREG(value.st_mode)
            or stat.S_IMODE(value.st_mode) != 0o600
            or value.st_nlink != 1
        ):
            raise SafetyError("private_output_file_mode_invalid")
    report_bytes, _ = _read_stable_private_file(
        root / REPORT_NAME,
        max_bytes=4 * 1024 * 1024,
    )
    if report_bytes != _canonical_report_bytes(report):
        raise SafetyError("build_report_mismatch")
    _require_sidecars_absent(root / DATABASE_NAME)
    for forbidden in (
        root,
    ):
        if os.fsencode(forbidden) in report_bytes:
            raise SafetyError("absolute_path_in_build_report")


def _published_tree_identity(root: Path) -> _PublishedTreeIdentity:
    directory = _stable_directory_identity(
        root, "publication_directory"
    )
    files: list[tuple[str, _StatIdentity]] = []
    try:
        entries = sorted(root.iterdir(), key=lambda item: item.name)
    except OSError as exc:
        raise SafetyError("publication_inventory_unavailable") from exc
    if [item.name for item in entries] != [REPORT_NAME, DATABASE_NAME]:
        raise SafetyError("publication_inventory_invalid")
    for path in entries:
        _, _, identity = _hash_stable_private_file(
            path,
            max_bytes=2 * 1024 * 1024 * 1024,
            prefix_bytes=0,
        )
        files.append((path.name, identity))
    return _PublishedTreeIdentity(
        directory_device=directory.device,
        directory_inode=directory.inode,
        files=tuple(files),
    )


def _rollback_owned_publication(
    output: Path,
    expected: _PublishedTreeIdentity,
) -> bool:
    rollback_root: Path | None = None
    isolated: Path | None = None
    moved = False
    try:
        rollback_root = Path(
            tempfile.mkdtemp(
                prefix=f".{output.name}.rollback-",
                dir=output.parent,
            )
        )
        os.chmod(rollback_root, 0o700)
        isolated = rollback_root / "owned-publication"
        try:
            atomic_publish_directory_no_replace(output, isolated)
        except (
            AtomicPublicationUnavailable,
            DestinationExistsError,
            OSError,
        ):
            return False
        moved = True
        try:
            isolated_identity = _published_tree_identity(isolated)
        except (OSError, SafetyError):
            isolated_identity = None
        if isolated_identity != expected:
            try:
                atomic_publish_directory_no_replace(isolated, output)
            except (
                AtomicPublicationUnavailable,
                DestinationExistsError,
                OSError,
            ):
                return False
            moved = False
            return False
        if not _remove_isolated_owned_publication(isolated, expected):
            return False
        moved = False
        rollback_root.rmdir()
        rollback_root = None
        try:
            output.lstat()
        except FileNotFoundError:
            return True
        return False
    except OSError:
        return False
    finally:
        if rollback_root is not None and not moved:
            try:
                rollback_root.rmdir()
            except OSError:
                pass


def _remove_isolated_owned_publication(
    isolated: Path,
    expected: _PublishedTreeIdentity,
) -> bool:
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    file_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    parent_descriptor: int | None = None
    directory_descriptor: int | None = None
    try:
        parent_descriptor = os.open(isolated.parent, directory_flags)
        directory_descriptor = os.open(
            isolated.name,
            directory_flags,
            dir_fd=parent_descriptor,
        )
        opened_directory = os.fstat(directory_descriptor)
        if (
            not stat.S_ISDIR(opened_directory.st_mode)
            or stat.S_IMODE(opened_directory.st_mode) != 0o700
            or opened_directory.st_dev != expected.directory_device
            or opened_directory.st_ino != expected.directory_inode
        ):
            return False
        names = sorted(os.listdir(directory_descriptor))
        if names != [name for name, _ in expected.files]:
            return False
        for name, identity in expected.files:
            descriptor = os.open(
                name,
                file_flags,
                dir_fd=directory_descriptor,
            )
            try:
                if _stat_identity(os.fstat(descriptor)) != identity:
                    return False
            finally:
                os.close(descriptor)
        for name, _ in expected.files:
            os.unlink(name, dir_fd=directory_descriptor)
        if os.listdir(directory_descriptor):
            return False
        os.fsync(directory_descriptor)
        current = os.stat(
            isolated.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            current.st_dev != expected.directory_device
            or current.st_ino != expected.directory_inode
        ):
            return False
        os.rmdir(isolated.name, dir_fd=parent_descriptor)
        return True
    except OSError:
        return False
    finally:
        if directory_descriptor is not None:
            os.close(directory_descriptor)
        if parent_descriptor is not None:
            os.close(parent_descriptor)


def _validate_database_read_only(
    path: Path,
    *,
    require_complete_output: bool = True,
) -> dict[str, object]:
    database = path.absolute()
    _require_database_envelope(
        database,
        require_complete_output=require_complete_output,
    )
    _require_sidecars_absent(database)
    sha256_before, header_before, stat_before = _hash_stable_private_file(
        database,
        max_bytes=2 * 1024 * 1024 * 1024,
        prefix_bytes=100,
    )
    if (
        len(header_before) < 100
        or not header_before.startswith(_SQLITE_HEADER)
        or header_before[18:20] != b"\x01\x01"
    ):
        raise SafetyError("database_header_mode_invalid")
    identity_before = _DatabaseIdentity(
        stat=stat_before,
        sha256=sha256_before,
    )
    connection: sqlite3.Connection | None = None
    validated: dict[str, object]
    try:
        uri = (
            "file:"
            + quote(os.fspath(database), safe="/")
            + "?mode=ro&immutable=1"
        )
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA trusted_schema = OFF")
        connection.execute("PRAGMA temp_store = MEMORY")
        connection.execute(f"PRAGMA cache_size = -{_SQLITE_CACHE_KIB}")
        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise SafetyError("database_not_query_only")
        _validate_database_structure(connection)
        _validate_database_resource_bounds(connection)
        _validate_database_integrity(connection)
        validated = _validate_database_rows(connection)
    except SafetyError:
        raise
    except sqlite3.Error as exc:
        raise SafetyError("vanilla_memory_database_invalid") from exc
    finally:
        if connection is not None:
            try:
                connection.close()
            except sqlite3.Error as exc:
                raise SafetyError("database_close_failed") from exc
    _require_sidecars_absent(database)
    sha256_after, _, stat_after = _hash_stable_private_file(
        database,
        max_bytes=2 * 1024 * 1024 * 1024,
        prefix_bytes=0,
    )
    identity_after = _DatabaseIdentity(
        stat=stat_after,
        sha256=sha256_after,
    )
    if identity_after != identity_before:
        raise SafetyError("database_changed_during_inspection")
    hashes = validated.get("hashes")
    if not isinstance(hashes, dict):
        raise AssertionError("validated hash mapping unavailable")
    hashes["database_sha256"] = identity_after.sha256
    return validated


def _require_database_envelope(
    path: Path,
    *,
    require_complete_output: bool,
) -> None:
    if path.name != DATABASE_NAME:
        raise SafetyError("database_name_invalid")
    try:
        parent = path.parent.lstat()
        value = path.lstat()
    except OSError as exc:
        raise SafetyError("database_unavailable") from exc
    if (
        not stat.S_ISDIR(parent.st_mode)
        or stat.S_IMODE(parent.st_mode) != 0o700
    ):
        raise SafetyError("database_parent_mode_invalid")
    if (
        not stat.S_ISREG(value.st_mode)
        or stat.S_IMODE(value.st_mode) != 0o600
        or value.st_nlink != 1
    ):
        raise SafetyError("database_file_unsafe")
    try:
        names = sorted(item.name for item in path.parent.iterdir())
    except OSError as exc:
        raise SafetyError("database_parent_inventory_failed") from exc
    expected = (
        [REPORT_NAME, DATABASE_NAME]
        if require_complete_output
        else [DATABASE_NAME]
    )
    if names != expected:
        raise SafetyError("database_parent_inventory_invalid")


def _require_sidecars_absent(path: Path) -> None:
    for suffix in _SQLITE_SIDECAR_SUFFIXES:
        sidecar = Path(os.fspath(path) + suffix)
        try:
            sidecar.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise SafetyError("database_sidecar_state_unavailable") from exc
        raise SafetyError("database_sidecar_present")


def _read_stable_private_file(
    path: Path,
    *,
    max_bytes: int,
) -> tuple[bytes, _StatIdentity]:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        before_path = path.lstat()
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise SafetyError("private_file_open_failed") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or before.st_size < 0
            or before.st_size > max_bytes
        ):
            raise SafetyError("private_file_unsafe")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise SafetyError("private_file_truncated")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise SafetyError("private_file_grew")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after_path = path.lstat()
    except OSError as exc:
        raise SafetyError("private_file_changed") from exc
    identities = tuple(
        _stat_identity(value)
        for value in (before_path, before, after, after_path)
    )
    if any(identity != identities[0] for identity in identities[1:]):
        raise SafetyError("private_file_changed")
    return b"".join(chunks), identities[0]


def _hash_stable_private_file(
    path: Path,
    *,
    max_bytes: int,
    prefix_bytes: int,
) -> tuple[str, bytes, _StatIdentity]:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        before_path = path.lstat()
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise SafetyError("private_file_open_failed") from exc
    digest = hashlib.sha256()
    prefix = bytearray()
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or before.st_size < 0
            or before.st_size > max_bytes
        ):
            raise SafetyError("private_file_unsafe")
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise SafetyError("private_file_truncated")
            digest.update(chunk)
            if len(prefix) < prefix_bytes:
                prefix.extend(chunk[: prefix_bytes - len(prefix)])
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise SafetyError("private_file_grew")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after_path = path.lstat()
    except OSError as exc:
        raise SafetyError("private_file_changed") from exc
    identities = tuple(
        _stat_identity(value)
        for value in (before_path, before, after, after_path)
    )
    if any(identity != identities[0] for identity in identities[1:]):
        raise SafetyError("private_file_changed")
    return digest.hexdigest(), bytes(prefix), identities[0]


def _validate_database_structure(connection: sqlite3.Connection) -> None:
    journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    if journal_mode != "delete":
        raise SafetyError("database_journal_mode_invalid")
    if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
        raise SafetyError("database_schema_version_unknown")
    if connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
        raise SafetyError("database_application_id_unknown")
    if _schema_signature(connection) != _expected_schema_signature():
        raise SafetyError("database_schema_signature_invalid")
    table_list = {
        row[1]: tuple(row)
        for row in connection.execute("PRAGMA table_list")
        if row[1] in _schema_table_names()
    }
    if set(table_list) != _schema_table_names():
        raise SafetyError("database_table_inventory_invalid")
    without_rowid = {
        "manifest_entries",
        "source_files",
        "quarantined_key_occupancy",
        "protected_tokens",
        "unique_alignments",
        "reference_pairs",
    }
    for name, row in table_list.items():
        expected_wr = int(name in without_rowid)
        if row[4] != expected_wr or row[5] != 1:
            raise SafetyError(f"database_{name}_table_mode_invalid")


def _validate_database_integrity(connection: sqlite3.Connection) -> None:
    integrity = connection.execute("PRAGMA integrity_check(1)")
    first = integrity.fetchone()
    if (
        first is None
        or tuple(first) != ("ok",)
        or integrity.fetchone() is not None
    ):
        raise SafetyError("database_integrity_check_failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise SafetyError("database_foreign_key_check_failed")


def _schema_table_names() -> set[str]:
    return {
        "metadata",
        "manifest_entries",
        "source_files",
        "quarantined_key_occupancy",
        "occurrences",
        "protected_tokens",
        "unique_alignments",
        "reference_pairs",
        "quarantine_records",
    }


def _validate_database_resource_bounds(
    connection: sqlite3.Connection,
) -> None:
    for language in _LANGUAGES:
        parameters = (language,)
        if _database_count(
            connection,
            "SELECT COUNT(*) FROM manifest_entries WHERE language = ?",
            parameters,
        ) > MAX_MANIFEST_ENTRIES_PER_ROOT:
            raise SafetyError("manifest_entry_limit_exceeded")
        if _database_count(
            connection,
            """
            SELECT COUNT(*) FROM manifest_entries
            WHERE language = ? AND entry_kind = 'directory'
            """,
            parameters,
        ) > MAX_SOURCE_DIRECTORIES_PER_ROOT:
            raise SafetyError("source_directory_limit_exceeded")
        if _database_count(
            connection,
            """
            SELECT COUNT(*) FROM manifest_entries
            WHERE language = ? AND entry_kind = 'file'
            """,
            parameters,
        ) > MAX_REGULAR_FILES_PER_ROOT:
            raise SafetyError("source_file_limit_exceeded")
        if _database_count(
            connection,
            """
            SELECT COALESCE(SUM(byte_count), 0) FROM manifest_entries
            WHERE language = ? AND entry_kind = 'file'
            """,
            parameters,
        ) > MAX_SOURCE_BYTES_PER_ROOT:
            raise SafetyError("source_bytes_limit_exceeded")
        if _database_count(
            connection,
            "SELECT COUNT(*) FROM source_files WHERE language = ?",
            parameters,
        ) > MAX_YML_SOURCE_FILES_PER_ROOT:
            raise SafetyError("source_yml_file_limit_exceeded")
        if _database_count(
            connection,
            "SELECT COUNT(*) FROM occurrences WHERE language = ?",
            parameters,
        ) > MAX_OCCURRENCES_PER_LANGUAGE:
            raise SafetyError("source_occurrence_language_limit_exceeded")

    if _database_count(
        connection, "SELECT COUNT(*) FROM source_files"
    ) > MAX_YML_SOURCE_FILES_TOTAL:
        raise SafetyError("source_yml_file_total_limit_exceeded")
    if _database_count(
        connection, "SELECT COUNT(*) FROM occurrences"
    ) > MAX_OCCURRENCES_TOTAL:
        raise SafetyError("source_occurrence_total_limit_exceeded")
    if _database_count(
        connection, "SELECT COUNT(*) FROM protected_tokens"
    ) > MAX_PROTECTED_TOKENS_TOTAL:
        raise SafetyError("protected_token_limit_exceeded")
    if _database_count(
        connection,
        """
        SELECT COUNT(*) FROM quarantine_records
        WHERE quarantine_scope = 'record'
        """,
    ) > MAX_RECORD_QUARANTINES_TOTAL:
        raise SafetyError("record_quarantine_limit_exceeded")
    if _database_count(
        connection,
        """
        SELECT COUNT(*) FROM quarantine_records
        WHERE quarantine_scope = 'file'
        """,
    ) > MAX_FILE_QUARANTINES_TOTAL:
        raise SafetyError("file_quarantine_limit_exceeded")
    if _database_count(
        connection,
        """
        SELECT COALESCE(SUM(candidate_count), 0)
        FROM quarantined_key_occupancy
        """,
    ) > MAX_QUARANTINED_KEY_CANDIDATES:
        raise SafetyError("quarantined_key_candidate_limit_exceeded")


def _database_count(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple[object, ...] = (),
) -> int:
    row = connection.execute(sql, parameters).fetchone()
    if row is None or len(row) != 1 or type(row[0]) is not int or row[0] < 0:
        raise SafetyError("database_resource_count_invalid")
    return row[0]


def _schema_signature(
    connection: sqlite3.Connection,
) -> tuple[object, ...]:
    master = tuple(
        tuple(row)
        for row in connection.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_master
            WHERE type IN ('table', 'index', 'view', 'trigger')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        )
    )
    details: list[tuple[object, ...]] = []
    for table in sorted(_schema_table_names()):
        columns = tuple(
            tuple(row)
            for row in connection.execute(
                f"PRAGMA table_xinfo({table})"
            )
        )
        indexes = tuple(
            tuple(row)
            for row in connection.execute(
                f"PRAGMA index_list({table})"
            )
        )
        index_details = tuple(
            (
                row[1],
                tuple(
                    tuple(detail)
                    for detail in connection.execute(
                        f"PRAGMA index_xinfo({row[1]})"
                    )
                ),
            )
            for row in indexes
        )
        foreign_keys = tuple(
            tuple(row)
            for row in connection.execute(
                f"PRAGMA foreign_key_list({table})"
            )
        )
        details.append(
            (
                table,
                columns,
                indexes,
                index_details,
                foreign_keys,
            )
        )
    return master, tuple(details)


@lru_cache(maxsize=1)
def _expected_schema_signature() -> tuple[object, ...]:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(_SCHEMA)
        return _schema_signature(connection)
    finally:
        connection.close()


_COUNT_FIELDS = (
    "english_files",
    "russian_files",
    "english_occurrences",
    "russian_occurrences",
    "strict_eligible_pairs",
    "duplicate_key_occurrences",
    "missing_counterparts",
    "version_mismatches",
    "protected_atom_mismatches",
    "malformed_record_units",
    "malformed_file_units",
    "quarantined_total",
    "context_path_mismatches",
    "ambiguous_english_groups",
    "key_alias_groups",
    "source_mutations",
    "ollama_calls",
)


def _validate_database_rows(
    connection: sqlite3.Connection,
) -> dict[str, object]:
    metadata_rows = connection.execute(
        "SELECT * FROM metadata ORDER BY singleton"
    ).fetchall()
    if len(metadata_rows) != 1:
        raise SafetyError("metadata_row_count_invalid")
    metadata = _validated_metadata(metadata_rows[0])

    manifest_rows = tuple(
        _validated_manifest_row(row)
        for row in connection.execute(
            """
            SELECT language, entry_kind, relative_path, byte_count,
                   content_sha256
            FROM manifest_entries
            ORDER BY language, relative_path
            """
        )
    )
    source_rows = tuple(
        _validated_source_file_row(row)
        for row in connection.execute(
            """
            SELECT language, relative_path, file_sha256, byte_count,
                   parse_state, parse_reason, bom, newline_style,
                   key_occupancy_scan_contract,
                   key_occupancy_candidate_count,
                   occurrence_count, quarantine_count
            FROM source_files
            ORDER BY language, relative_path
            """
        )
    )
    key_occupancy_rows = tuple(
        _validated_quarantined_key_occupancy_row(row)
        for row in connection.execute(
            """
            SELECT language, relative_path, key_hint, candidate_count
            FROM quarantined_key_occupancy
            ORDER BY language, relative_path, key_hint
            """
        )
    )
    occurrence_rows = tuple(
        _validated_occurrence_database_row(row)
        for row in connection.execute(
            "SELECT * FROM occurrences ORDER BY sequence"
        )
    )
    token_rows = tuple(
        _validated_token_row(row)
        for row in connection.execute(
            """
            SELECT occurrence_id, token_ordinal, token_kind, exact_token
            FROM protected_tokens
            ORDER BY occurrence_id, token_ordinal
            """
        )
    )
    alignment_rows = tuple(
        _validated_alignment_row(row)
        for row in connection.execute(
            """
            SELECT alignment_id, english_occurrence_id,
                   russian_occurrence_id, alignment_state,
                   path_family_match, global_text_ambiguous
            FROM unique_alignments
            ORDER BY english_occurrence_id, russian_occurrence_id
            """
        )
    )
    reference_rows = tuple(
        _validated_reference_row(row)
        for row in connection.execute(
            """
            SELECT pair_id, alignment_id, english_occurrence_id,
                   russian_occurrence_id, context_path_match,
                   global_text_ambiguous, reference_status,
                   editorially_approved
            FROM reference_pairs
            ORDER BY english_occurrence_id, russian_occurrence_id
            """
        )
    )
    quarantine_rows = tuple(
        _validated_quarantine_row(row)
        for row in connection.execute(
            "SELECT * FROM quarantine_records ORDER BY sequence"
        )
    )
    _validate_contiguous_sequences(occurrence_rows, "occurrence")
    _validate_contiguous_sequences(quarantine_rows, "quarantine")
    _validate_manifest_semantics(
        metadata,
        manifest_rows,
        source_rows,
    )
    _validate_quarantined_key_occupancy_semantics(
        source_rows,
        key_occupancy_rows,
    )
    semantic_counts, quarantine_by_reason = _validate_alignment_semantics(
        source_rows,
        key_occupancy_rows,
        occurrence_rows,
        token_rows,
        alignment_rows,
        reference_rows,
        quarantine_rows,
    )
    stored_counts = metadata["counts"]
    assert isinstance(stored_counts, dict)
    if semantic_counts != stored_counts:
        raise SafetyError("stored_count_mismatch")
    _validate_count_algebra(semantic_counts)
    logical_digest = _logical_digest(connection)
    if logical_digest != metadata["logical_digest"]:
        raise SafetyError("logical_digest_mismatch")
    hashes = {
        "english_manifest_sha256": metadata[
            "english_manifest_sha256"
        ],
        "russian_manifest_sha256": metadata[
            "russian_manifest_sha256"
        ],
        "english_dataset_sha256": metadata[
            "english_dataset_sha256"
        ],
        "russian_dataset_sha256": metadata[
            "russian_dataset_sha256"
        ],
        "logical_digest": logical_digest,
    }
    return {
        "schema_version": metadata["schema_version"],
        "game_version": metadata["game_version"],
        "build_status": metadata["build_status"],
        "hashes": hashes,
        "counts": {
            **semantic_counts,
            "quarantine_by_reason": quarantine_by_reason,
        },
    }


def _validated_metadata(row: sqlite3.Row) -> dict[str, object]:
    if _require_int_value("metadata_singleton", row["singleton"], 1) != 1:
        raise SafetyError("metadata_singleton_invalid")
    schema_version = _require_int_value(
        "metadata_schema_version", row["schema_version"], 1
    )
    application_id = _require_int_value(
        "metadata_application_id", row["application_id"], 1
    )
    if schema_version != SCHEMA_VERSION or application_id != APPLICATION_ID:
        raise SafetyError("metadata_identity_invalid")
    game_version = _validated_game_version(
        _require_text_value("metadata_game_version", row["game_version"])
    )
    build_status = _require_choice_value(
        "metadata_build_status",
        row["build_status"],
        {"COMPLETE", "COMPLETE_WITH_QUARANTINED_RECORDS"},
    )
    result: dict[str, object] = {
        "schema_version": schema_version,
        "game_version": game_version,
        "build_status": build_status,
        "english_manifest_sha256": _require_sha256_value(
            "english_manifest_sha256",
            row["english_manifest_sha256"],
        ),
        "russian_manifest_sha256": _require_sha256_value(
            "russian_manifest_sha256",
            row["russian_manifest_sha256"],
        ),
        "english_dataset_sha256": _require_sha256_value(
            "english_dataset_sha256",
            row["english_dataset_sha256"],
        ),
        "russian_dataset_sha256": _require_sha256_value(
            "russian_dataset_sha256",
            row["russian_dataset_sha256"],
        ),
        "logical_digest": _require_sha256_value(
            "logical_digest", row["logical_digest"]
        ),
    }
    counts = {
        name: _require_int_value(name, row[name], 0)
        for name in _COUNT_FIELDS
    }
    if (
        counts["source_mutations"] != 0
        or counts["ollama_calls"] != 0
    ):
        raise SafetyError("metadata_zero_counter_invalid")
    expected_status = (
        "COMPLETE"
        if counts["quarantined_total"] == 0
        else "COMPLETE_WITH_QUARANTINED_RECORDS"
    )
    if build_status != expected_status:
        raise SafetyError("metadata_status_invalid")
    result["counts"] = counts
    return result


def _validated_manifest_row(row: sqlite3.Row) -> dict[str, object]:
    language = _require_choice_value(
        "manifest_language", row["language"], set(_LANGUAGES)
    )
    kind = _require_choice_value(
        "manifest_kind",
        row["entry_kind"],
        {"directory", "file"},
    )
    relative_path = _require_relative_path_value(
        row["relative_path"]
    )
    byte_count = row["byte_count"]
    content_sha256 = row["content_sha256"]
    if kind == "directory":
        if byte_count is not None or content_sha256 is not None:
            raise SafetyError("manifest_directory_payload_invalid")
    else:
        byte_count = _require_int_value(
            "manifest_byte_count", byte_count, 0
        )
        content_sha256 = _require_sha256_value(
            "manifest_content_sha256", content_sha256
        )
    return {
        "language": language,
        "kind": kind,
        "relative_path": relative_path,
        "byte_count": byte_count,
        "content_sha256": content_sha256,
    }


def _validated_source_file_row(row: sqlite3.Row) -> dict[str, object]:
    language = _require_choice_value(
        "source_file_language", row["language"], set(_LANGUAGES)
    )
    relative_path = _require_relative_path_value(
        row["relative_path"]
    )
    if PurePosixPath(relative_path).suffix.lower() != ".yml":
        raise SafetyError("source_file_extension_invalid")
    parse_state = _require_choice_value(
        "source_file_parse_state",
        row["parse_state"],
        {"parsed", "quarantined"},
    )
    parse_reason = row["parse_reason"]
    bom = row["bom"]
    newline_style = row["newline_style"]
    key_occupancy_scan_contract = row[
        "key_occupancy_scan_contract"
    ]
    key_occupancy_candidate_count = _require_int_value(
        "source_file_key_occupancy_candidate_count",
        row["key_occupancy_candidate_count"],
        0,
    )
    occurrence_count = _require_int_value(
        "source_file_occurrence_count",
        row["occurrence_count"],
        0,
    )
    quarantine_count = _require_int_value(
        "source_file_quarantine_count",
        row["quarantine_count"],
        0,
    )
    if parse_state == "parsed":
        if (
            parse_reason is not None
            or key_occupancy_scan_contract is not None
            or key_occupancy_candidate_count != 0
        ):
            raise SafetyError("source_file_parse_payload_invalid")
        bom = _require_bool_int("source_file_bom", bom)
        newline_style = _require_choice_value(
            "source_file_newline",
            newline_style,
            {"LF", "CRLF"},
        )
    else:
        parse_reason = _require_text_value(
            "source_file_parse_reason", parse_reason
        )
        if parse_reason not in _PARSE_QUARANTINE_REASONS:
            raise SafetyError("source_file_parse_reason_unknown")
        if (
            bom is not None
            or newline_style is not None
            or occurrence_count != 0
            or quarantine_count != 1
        ):
            raise SafetyError("source_file_quarantine_payload_invalid")
        if (
            key_occupancy_scan_contract
            != _KEY_OCCUPANCY_SCAN_CONTRACT
        ):
            raise SafetyError(
                "source_file_key_occupancy_contract_invalid"
            )
    return {
        "language": language,
        "relative_path": relative_path,
        "file_sha256": _require_sha256_value(
            "source_file_sha256", row["file_sha256"]
        ),
        "byte_count": _require_int_value(
            "source_file_byte_count", row["byte_count"], 0
        ),
        "parse_state": parse_state,
        "parse_reason": parse_reason,
        "bom": bom,
        "newline_style": newline_style,
        "key_occupancy_scan_contract": key_occupancy_scan_contract,
        "key_occupancy_candidate_count": (
            key_occupancy_candidate_count
        ),
        "occurrence_count": occurrence_count,
        "quarantine_count": quarantine_count,
    }


def _validated_quarantined_key_occupancy_row(
    row: sqlite3.Row,
) -> dict[str, object]:
    language = _require_choice_value(
        "key_occupancy_language",
        row["language"],
        set(_LANGUAGES),
    )
    relative_path = _require_relative_path_value(
        row["relative_path"]
    )
    key_hint = _require_text_value(
        "key_occupancy_key_hint", row["key_hint"]
    )
    if not all(
        char.isascii()
        and (char.isalnum() or char in "_.-")
        for char in key_hint
    ):
        raise SafetyError("key_occupancy_key_hint_invalid")
    return {
        "language": language,
        "relative_path": relative_path,
        "key_hint": key_hint,
        "candidate_count": _require_int_value(
            "key_occupancy_candidate_count",
            row["candidate_count"],
            1,
        ),
    }


def _validated_occurrence_database_row(
    row: sqlite3.Row,
) -> dict[str, object]:
    sequence = _require_int_value(
        "occurrence_sequence", row["sequence"], 0
    )
    occurrence_id = _require_sha256_value(
        "occurrence_id", row["occurrence_id"]
    )
    language = _require_choice_value(
        "occurrence_language", row["language"], set(_LANGUAGES)
    )
    relative_path = _require_relative_path_value(
        row["relative_path"]
    )
    ordinal = _require_int_value(
        "occurrence_ordinal", row["occurrence_ordinal"], 0
    )
    line_number = _require_int_value(
        "occurrence_line_number", row["line_number"], 1
    )
    key = _require_text_value("occurrence_key", row["localisation_key"])
    if not all(
        char.isascii()
        and (char.isalnum() or char in "_.-")
        for char in key
    ):
        raise SafetyError("occurrence_key_invalid")
    suffix = row["version_suffix"]
    if suffix is not None:
        suffix = _require_text_value(
            "occurrence_version_suffix", suffix
        )
        if not suffix.isascii() or not suffix.isdigit():
            raise SafetyError("occurrence_version_suffix_invalid")
    value = _require_text_value(
        "occurrence_human_value",
        row["human_value"],
        allow_empty=True,
    )
    state = _require_choice_value(
        "occurrence_alignment_state",
        row["alignment_state"],
        set(_ALIGNMENT_STATES),
    )
    reason = row["diagnostic_reason"]
    if reason is not None:
        reason = _require_text_value(
            "occurrence_diagnostic_reason", reason
        )
    counterpart = row["counterpart_occurrence_id"]
    if counterpart is not None:
        counterpart = _require_sha256_value(
            "counterpart_occurrence_id", counterpart
        )
    path_match = row["context_path_match"]
    if path_match is not None:
        path_match = _require_bool_int(
            "occurrence_context_path_match", path_match
        )
    ambiguous = _require_bool_int(
        "occurrence_global_text_ambiguous",
        row["global_text_ambiguous"],
    )
    key_alias = _require_bool_int(
        "occurrence_key_alias_risk", row["key_alias_risk"]
    )
    if (
        row["reference_status"] != "REFERENCE_ONLY"
        or _require_bool_int(
            "occurrence_editorially_approved",
            row["editorially_approved"],
        )
        != 0
    ):
        raise SafetyError("occurrence_reference_status_invalid")
    expected_id = _stable_hash(
        _OCCURRENCE_ID_DOMAIN,
        (language, relative_path, ordinal, key, suffix),
    )
    if occurrence_id != expected_id:
        raise SafetyError("occurrence_id_mismatch")
    value_sha256 = _require_sha256_value(
        "occurrence_value_sha256", row["value_sha256"]
    )
    if value_sha256 != _sha256(value.encode("utf-8")):
        raise SafetyError("occurrence_value_hash_mismatch")
    return {
        "sequence": sequence,
        "occurrence_id": occurrence_id,
        "language": language,
        "relative_path": relative_path,
        "ordinal": ordinal,
        "line_number": line_number,
        "key": key,
        "suffix": suffix,
        "value": value,
        "protected_signature_sha256": _require_sha256_value(
            "protected_signature_sha256",
            row["protected_signature_sha256"],
        ),
        "source_sha256": _require_sha256_value(
            "occurrence_source_sha256", row["source_sha256"]
        ),
        "value_sha256": value_sha256,
        "state": state,
        "reason": reason,
        "counterpart": counterpart,
        "path_match": path_match,
        "ambiguous": ambiguous,
        "key_alias": key_alias,
    }


def _validated_token_row(row: sqlite3.Row) -> dict[str, object]:
    occurrence_id = _require_sha256_value(
        "token_occurrence_id", row["occurrence_id"]
    )
    ordinal = _require_int_value(
        "token_ordinal", row["token_ordinal"], 0
    )
    kind = _require_choice_value(
        "token_kind",
        row["token_kind"],
        {
            "escaped_quote",
            "escaped_backslash",
            "escaped_newline",
            "dollar_reference",
            "bracket_expression",
            "icon",
            "format_control",
        },
    )
    exact = _require_text_value("token_exact", row["exact_token"])
    if _token_kind(exact) != kind:
        raise SafetyError("token_kind_mismatch")
    return {
        "occurrence_id": occurrence_id,
        "ordinal": ordinal,
        "kind": kind,
        "exact": exact,
    }


def _validated_alignment_row(row: sqlite3.Row) -> dict[str, object]:
    english_id = _require_sha256_value(
        "alignment_english_id", row["english_occurrence_id"]
    )
    russian_id = _require_sha256_value(
        "alignment_russian_id", row["russian_occurrence_id"]
    )
    alignment_id = _require_sha256_value(
        "alignment_id", row["alignment_id"]
    )
    expected_id = _stable_hash(
        _ALIGNMENT_ID_DOMAIN, (english_id, russian_id)
    )
    if alignment_id != expected_id:
        raise SafetyError("alignment_id_mismatch")
    return {
        "alignment_id": alignment_id,
        "english_id": english_id,
        "russian_id": russian_id,
        "state": _require_choice_value(
            "alignment_state",
            row["alignment_state"],
            set(_PAIR_STATES),
        ),
        "path_match": _require_bool_int(
            "alignment_path_family_match",
            row["path_family_match"],
        ),
        "ambiguous": _require_bool_int(
            "alignment_global_text_ambiguous",
            row["global_text_ambiguous"],
        ),
    }


def _validated_reference_row(row: sqlite3.Row) -> dict[str, object]:
    alignment_id = _require_sha256_value(
        "reference_alignment_id", row["alignment_id"]
    )
    english_id = _require_sha256_value(
        "reference_english_id", row["english_occurrence_id"]
    )
    russian_id = _require_sha256_value(
        "reference_russian_id", row["russian_occurrence_id"]
    )
    pair_id = _require_sha256_value("reference_pair_id", row["pair_id"])
    if pair_id != _stable_hash(
        _PAIR_ID_DOMAIN,
        (alignment_id, english_id, russian_id),
    ):
        raise SafetyError("reference_pair_id_mismatch")
    if (
        row["reference_status"] != "REFERENCE_ONLY"
        or _require_bool_int(
            "reference_editorially_approved",
            row["editorially_approved"],
        )
        != 0
    ):
        raise SafetyError("reference_status_invalid")
    return {
        "pair_id": pair_id,
        "alignment_id": alignment_id,
        "english_id": english_id,
        "russian_id": russian_id,
        "path_match": _require_bool_int(
            "reference_context_path_match",
            row["context_path_match"],
        ),
        "ambiguous": _require_bool_int(
            "reference_global_text_ambiguous",
            row["global_text_ambiguous"],
        ),
    }


def _validated_quarantine_row(row: sqlite3.Row) -> dict[str, object]:
    sequence = _require_int_value(
        "quarantine_sequence", row["sequence"], 0
    )
    language = _require_choice_value(
        "quarantine_language", row["language"], set(_LANGUAGES)
    )
    relative_path = _require_relative_path_value(
        row["relative_path"]
    )
    scope = _require_choice_value(
        "quarantine_scope",
        row["quarantine_scope"],
        {"file", "record"},
    )
    ordinal = row["occurrence_ordinal"]
    line_number = row["line_number"]
    key_hint = row["key_hint"]
    if scope == "file":
        if (
            ordinal is not None
            or line_number is not None
            or key_hint is not None
        ):
            raise SafetyError("quarantine_file_payload_invalid")
    else:
        ordinal = _require_int_value(
            "quarantine_ordinal", ordinal, 0
        )
        line_number = _require_int_value(
            "quarantine_line_number", line_number, 1
        )
        key_hint = _require_text_value(
            "quarantine_key_hint", key_hint
        )
        if not all(
            char.isascii()
            and (char.isalnum() or char in "_.-")
            for char in key_hint
        ):
            raise SafetyError("quarantine_key_hint_invalid")
    source_sha256 = _require_sha256_value(
        "quarantine_source_sha256", row["source_sha256"]
    )
    reason = _require_text_value(
        "quarantine_reason", row["diagnostic_reason"]
    )
    allowed_reasons = (
        _PARSE_QUARANTINE_REASONS
        if scope == "file"
        else _RECORD_QUARANTINE_REASONS
    )
    if reason not in allowed_reasons:
        raise SafetyError("quarantine_reason_unknown")
    quarantine_id = _require_sha256_value(
        "quarantine_id", row["quarantine_id"]
    )
    if quarantine_id != _stable_hash(
        _QUARANTINE_ID_DOMAIN,
        (
            language,
            relative_path,
            scope,
            ordinal,
            line_number,
            key_hint,
            source_sha256,
            reason,
        ),
    ):
        raise SafetyError("quarantine_id_mismatch")
    return {
        "sequence": sequence,
        "quarantine_id": quarantine_id,
        "language": language,
        "relative_path": relative_path,
        "scope": scope,
        "ordinal": ordinal,
        "line_number": line_number,
        "key_hint": key_hint,
        "source_sha256": source_sha256,
        "reason": reason,
    }


def _validate_contiguous_sequences(
    rows: tuple[dict[str, object], ...],
    label: str,
) -> None:
    if tuple(row["sequence"] for row in rows) != tuple(
        range(len(rows))
    ):
        raise SafetyError(f"{label}_sequence_invalid")


def _validate_manifest_semantics(
    metadata: dict[str, object],
    manifest_rows: tuple[dict[str, object], ...],
    source_rows: tuple[dict[str, object], ...],
) -> None:
    manifest_lookup = {
        (row["language"], row["relative_path"]): row
        for row in manifest_rows
    }
    source_lookup = {
        (row["language"], row["relative_path"]): row
        for row in source_rows
    }
    if len(manifest_lookup) != len(manifest_rows):
        raise SafetyError("manifest_duplicate_row")
    if len(source_lookup) != len(source_rows):
        raise SafetyError("source_file_duplicate_row")
    for language in _LANGUAGES:
        language_manifest = tuple(
            row
            for row in manifest_rows
            if row["language"] == language
        )
        _validate_manifest_portable_paths(language_manifest)
        digest = _manifest_digest_from_database_rows(
            language, language_manifest
        )
        if digest != metadata[f"{language}_manifest_sha256"]:
            raise SafetyError("manifest_digest_mismatch")
        language_sources = tuple(
            row
            for row in source_rows
            if row["language"] == language
        )
        dataset_digest = _dataset_digest_from_database_rows(
            language, language_sources
        )
        if dataset_digest != metadata[f"{language}_dataset_sha256"]:
            raise SafetyError("dataset_digest_mismatch")

        yml_manifest_paths = {
            row["relative_path"]
            for row in language_manifest
            if row["kind"] == "file"
            and PurePosixPath(
                str(row["relative_path"])
            ).suffix.lower()
            == ".yml"
        }
        source_paths = {
            row["relative_path"] for row in language_sources
        }
        if yml_manifest_paths != source_paths:
            raise SafetyError("source_file_manifest_set_mismatch")
        for source in language_sources:
            manifest = manifest_lookup[
                (language, source["relative_path"])
            ]
            if (
                manifest["kind"] != "file"
                or manifest["byte_count"] != source["byte_count"]
                or manifest["content_sha256"]
                != source["file_sha256"]
            ):
                raise SafetyError("source_file_manifest_mismatch")


def _validate_manifest_portable_paths(
    rows: tuple[dict[str, object], ...],
) -> None:
    known: dict[
        tuple[str, ...], tuple[tuple[str, ...], str]
    ] = {}
    for row in rows:
        path = Path(str(row["relative_path"]))
        _admit_portable_path(known, path, str(row["kind"]))


def _validate_quarantined_key_occupancy_semantics(
    source_rows: tuple[dict[str, object], ...],
    key_occupancy_rows: tuple[dict[str, object], ...],
) -> None:
    source_lookup = {
        (row["language"], row["relative_path"]): row
        for row in source_rows
    }
    occupancy_lookup = {
        (
            row["language"],
            row["relative_path"],
            row["key_hint"],
        ): row
        for row in key_occupancy_rows
    }
    if len(occupancy_lookup) != len(key_occupancy_rows):
        raise SafetyError("key_occupancy_duplicate_row")
    totals: Counter[tuple[object, object]] = Counter()
    for row in key_occupancy_rows:
        source_key = (row["language"], row["relative_path"])
        source = source_lookup.get(source_key)
        if (
            source is None
            or source["parse_state"] != "quarantined"
            or source["key_occupancy_scan_contract"]
            != _KEY_OCCUPANCY_SCAN_CONTRACT
        ):
            raise SafetyError("key_occupancy_source_invalid")
        totals[source_key] += int(row["candidate_count"])
        if totals[source_key] > MAX_QUARANTINED_KEY_CANDIDATES:
            raise SafetyError("key_occupancy_candidate_limit_invalid")
    for source_key, source in source_lookup.items():
        if (
            totals[source_key]
            != source["key_occupancy_candidate_count"]
        ):
            raise SafetyError("key_occupancy_candidate_count_mismatch")


def _manifest_digest_from_database_rows(
    language: str,
    rows: tuple[dict[str, object], ...],
) -> str:
    semantic_rows = [
        (
            row["kind"],
            row["relative_path"],
            row["byte_count"],
            row["content_sha256"],
        )
        for row in rows
    ]
    return _semantic_digest(
        _MANIFEST_DIGEST_DOMAIN,
        [
            ("language", language),
            *[("entry", item) for item in semantic_rows],
        ],
    )


def _dataset_digest_from_database_rows(
    language: str,
    rows: tuple[dict[str, object], ...],
) -> str:
    semantic_rows = [
        (
            row["relative_path"],
            row["byte_count"],
            row["file_sha256"],
        )
        for row in rows
    ]
    return _semantic_digest(
        _DATASET_DIGEST_DOMAIN,
        [
            ("language", language),
            *[("file", item) for item in semantic_rows],
        ],
    )


def _validate_alignment_semantics(
    source_rows: tuple[dict[str, object], ...],
    key_occupancy_rows: tuple[dict[str, object], ...],
    occurrence_rows: tuple[dict[str, object], ...],
    token_rows: tuple[dict[str, object], ...],
    alignment_rows: tuple[dict[str, object], ...],
    reference_rows: tuple[dict[str, object], ...],
    quarantine_rows: tuple[dict[str, object], ...],
) -> tuple[dict[str, int], dict[str, int]]:
    source_lookup = {
        (row["language"], row["relative_path"]): row
        for row in source_rows
    }
    occurrence_lookup = {
        row["occurrence_id"]: row for row in occurrence_rows
    }
    if len(occurrence_lookup) != len(occurrence_rows):
        raise SafetyError("occurrence_id_duplicate")
    tokens_by_occurrence: dict[str, list[dict[str, object]]] = defaultdict(list)
    for token in token_rows:
        occurrence_id = str(token["occurrence_id"])
        if occurrence_id not in occurrence_lookup:
            raise SafetyError("protected_token_orphan")
        tokens_by_occurrence[occurrence_id].append(token)

    occurrences_by_file: dict[
        tuple[object, object], list[dict[str, object]]
    ] = defaultdict(list)
    for occurrence in occurrence_rows:
        source_key = (
            occurrence["language"],
            occurrence["relative_path"],
        )
        source = source_lookup.get(source_key)
        if source is None or source["parse_state"] != "parsed":
            raise SafetyError("occurrence_source_file_invalid")
        occurrences_by_file[source_key].append(occurrence)
        tokens = tokens_by_occurrence.get(
            str(occurrence["occurrence_id"]), []
        )
        if tuple(item["ordinal"] for item in tokens) != tuple(
            range(len(tokens))
        ):
            raise SafetyError("protected_token_order_invalid")
        token_objects = tuple(
            _Token(
                ordinal=int(item["ordinal"]),
                kind=str(item["kind"]),
                exact=str(item["exact"]),
            )
            for item in tokens
        )
        try:
            parsed_tokens = _protected_tokens(str(occurrence["value"]))
        except ParseError as exc:
            raise SafetyError(
                "occurrence_protected_syntax_invalid"
            ) from exc
        expected_tokens = tuple(
            _Token(
                ordinal=index,
                kind=_token_kind(token.original),
                exact=token.original,
            )
            for index, token in enumerate(parsed_tokens)
        )
        if token_objects != expected_tokens:
            raise SafetyError("occurrence_protected_tokens_mismatch")
        if (
            _token_signature(token_objects)
            != occurrence["protected_signature_sha256"]
        ):
            raise SafetyError("protected_signature_mismatch")
        occurrence["_tokens"] = token_objects

    quarantines_by_file: dict[
        tuple[object, object], list[dict[str, object]]
    ] = defaultdict(list)
    for quarantine in quarantine_rows:
        source_key = (
            quarantine["language"],
            quarantine["relative_path"],
        )
        source = source_lookup.get(source_key)
        if source is None:
            raise SafetyError("quarantine_source_file_invalid")
        quarantines_by_file[source_key].append(quarantine)

    for source_key, source in source_lookup.items():
        occurrences = sorted(
            occurrences_by_file.get(source_key, []),
            key=lambda item: int(item["ordinal"]),
        )
        quarantines = sorted(
            quarantines_by_file.get(source_key, []),
            key=lambda item: int(item["sequence"]),
        )
        if len(occurrences) != source["occurrence_count"]:
            raise SafetyError("source_file_occurrence_count_mismatch")
        if len(quarantines) != source["quarantine_count"]:
            raise SafetyError("source_file_quarantine_count_mismatch")
        if tuple(item["ordinal"] for item in occurrences) != tuple(
            range(len(occurrences))
        ):
            raise SafetyError("occurrence_file_order_invalid")
        line_numbers = tuple(
            int(item["line_number"]) for item in occurrences
        )
        if line_numbers != tuple(sorted(line_numbers)):
            raise SafetyError("occurrence_line_order_invalid")
        if source["parse_state"] == "quarantined":
            if (
                len(quarantines) != 1
                or quarantines[0]["scope"] != "file"
                or quarantines[0]["reason"] != source["parse_reason"]
                or quarantines[0]["source_sha256"]
                != source["file_sha256"]
            ):
                raise SafetyError("file_quarantine_mismatch")
        else:
            if any(item["scope"] != "record" for item in quarantines):
                raise SafetyError("record_quarantine_scope_invalid")
            expected_ordinals = tuple(
                range(
                    len(occurrences),
                    len(occurrences) + len(quarantines),
                )
            )
            actual_ordinals = tuple(
                sorted(int(item["ordinal"]) for item in quarantines)
            )
            if actual_ordinals != expected_ordinals:
                raise SafetyError("record_quarantine_order_invalid")

    english_by_key: dict[str, list[dict[str, object]]] = defaultdict(list)
    russian_by_key: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in occurrence_rows:
        target = (
            english_by_key
            if item["language"] == "english"
            else russian_by_key
        )
        target[str(item["key"])].append(item)
    english_quarantine_by_key: Counter[str] = Counter(
        str(item["key_hint"])
        for item in quarantine_rows
        if item["language"] == "english"
        and item["key_hint"] is not None
    )
    russian_quarantine_by_key: Counter[str] = Counter(
        str(item["key_hint"])
        for item in quarantine_rows
        if item["language"] == "russian"
        and item["key_hint"] is not None
    )
    for item in key_occupancy_rows:
        target = (
            english_quarantine_by_key
            if item["language"] == "english"
            else russian_quarantine_by_key
        )
        target[str(item["key_hint"])] += int(
            item["candidate_count"]
        )

    expected_occurrence: dict[
        str, tuple[str, str | None, str | None, int | None]
    ] = {}
    expected_alignments: dict[str, dict[str, object]] = {}
    for key in sorted(
        set(english_by_key)
        | set(russian_by_key)
        | set(english_quarantine_by_key)
        | set(russian_quarantine_by_key)
    ):
        english_group = english_by_key.get(key, [])
        russian_group = russian_by_key.get(key, [])
        english_occupancy = (
            len(english_group) + english_quarantine_by_key[key]
        )
        russian_occupancy = (
            len(russian_group) + russian_quarantine_by_key[key]
        )
        if english_occupancy > 1 or russian_occupancy > 1:
            reason = _duplicate_reason(
                english_occupancy, russian_occupancy
            )
            for item in (*english_group, *russian_group):
                expected_occurrence[str(item["occurrence_id"])] = (
                    "duplicate_key",
                    reason,
                    None,
                    None,
                )
            continue
        if (
            not english_group
            or not russian_group
            or english_quarantine_by_key[key]
            or russian_quarantine_by_key[key]
        ):
            reason = (
                "counterpart_quarantined"
                if english_quarantine_by_key[key]
                or russian_quarantine_by_key[key]
                else "missing_counterpart"
            )
            for item in (*english_group, *russian_group):
                expected_occurrence[str(item["occurrence_id"])] = (
                    "missing_counterpart",
                    reason,
                    None,
                    None,
                )
            continue
        english_item = english_group[0]
        russian_item = russian_group[0]
        path_match = int(
            _path_family(
                str(english_item["relative_path"]), "english"
            )
            == _path_family(
                str(russian_item["relative_path"]), "russian"
            )
        )
        if english_item["suffix"] != russian_item["suffix"]:
            state = "version_mismatch"
            reason = "version_mismatch"
        elif english_item["_tokens"] != russian_item["_tokens"]:
            state = "protected_atom_mismatch"
            reason = "protected_atom_mismatch"
        else:
            state = "strict_reference"
            reason = None
        english_id = str(english_item["occurrence_id"])
        russian_id = str(russian_item["occurrence_id"])
        expected_occurrence[english_id] = (
            state,
            reason,
            russian_id,
            path_match,
        )
        expected_occurrence[russian_id] = (
            state,
            reason,
            english_id,
            path_match,
        )
        alignment_id = _stable_hash(
            _ALIGNMENT_ID_DOMAIN, (english_id, russian_id)
        )
        expected_alignments[alignment_id] = {
            "alignment_id": alignment_id,
            "english_id": english_id,
            "russian_id": russian_id,
            "state": state,
            "path_match": path_match,
            "ambiguous": 0,
        }

    strict_by_value: dict[str, list[dict[str, object]]] = defaultdict(list)
    for alignment in expected_alignments.values():
        if alignment["state"] != "strict_reference":
            continue
        english_item = occurrence_lookup[str(alignment["english_id"])]
        strict_by_value[str(english_item["value"])].append(alignment)
    ambiguous_alignment_ids: set[str] = set()
    ambiguous_groups = 0
    for group in strict_by_value.values():
        russian_values = {
            str(
                occurrence_lookup[str(item["russian_id"])]["value"]
            )
            for item in group
        }
        if len(russian_values) > 1:
            ambiguous_groups += 1
            ambiguous_alignment_ids.update(
                str(item["alignment_id"]) for item in group
            )
    for alignment_id in ambiguous_alignment_ids:
        expected_alignments[alignment_id]["ambiguous"] = 1

    alias_groups = _key_alias_groups_from_database(occurrence_rows)
    alias_keys = {key for group in alias_groups for key in group}
    for item in occurrence_rows:
        occurrence_id = str(item["occurrence_id"])
        expected = expected_occurrence.get(occurrence_id)
        if expected is None:
            raise SafetyError("occurrence_alignment_unclassified")
        state, reason, counterpart, path_match = expected
        alignment_id = None
        if counterpart is not None:
            if item["language"] == "english":
                alignment_id = _stable_hash(
                    _ALIGNMENT_ID_DOMAIN,
                    (occurrence_id, counterpart),
                )
            else:
                alignment_id = _stable_hash(
                    _ALIGNMENT_ID_DOMAIN,
                    (counterpart, occurrence_id),
                )
        expected_ambiguous = int(
            alignment_id in ambiguous_alignment_ids
            if alignment_id is not None
            else False
        )
        if (
            item["state"] != state
            or item["reason"] != reason
            or item["counterpart"] != counterpart
            or item["path_match"] != path_match
            or item["ambiguous"] != expected_ambiguous
            or item["key_alias"] != int(item["key"] in alias_keys)
        ):
            raise SafetyError("occurrence_alignment_semantics_invalid")

    actual_alignments = {
        str(item["alignment_id"]): item for item in alignment_rows
    }
    if len(actual_alignments) != len(alignment_rows):
        raise SafetyError("alignment_duplicate")
    if set(actual_alignments) != set(expected_alignments):
        raise SafetyError("alignment_set_mismatch")
    for alignment_id, expected in expected_alignments.items():
        if actual_alignments[alignment_id] != expected:
            raise SafetyError("alignment_semantics_invalid")

    expected_references: dict[str, dict[str, object]] = {}
    for alignment in expected_alignments.values():
        if alignment["state"] != "strict_reference":
            continue
        pair_id = _stable_hash(
            _PAIR_ID_DOMAIN,
            (
                alignment["alignment_id"],
                alignment["english_id"],
                alignment["russian_id"],
            ),
        )
        expected_references[pair_id] = {
            "pair_id": pair_id,
            "alignment_id": alignment["alignment_id"],
            "english_id": alignment["english_id"],
            "russian_id": alignment["russian_id"],
            "path_match": alignment["path_match"],
            "ambiguous": alignment["ambiguous"],
        }
    actual_references = {
        str(item["pair_id"]): item for item in reference_rows
    }
    if actual_references != expected_references:
        raise SafetyError("reference_pair_semantics_invalid")

    state_counts = Counter(
        str(item["state"]) for item in occurrence_rows
    )
    pair_counts = Counter(
        str(item["state"]) for item in alignment_rows
    )
    malformed_records = sum(
        item["scope"] == "record" for item in quarantine_rows
    )
    malformed_files = sum(
        item["scope"] == "file" for item in quarantine_rows
    )
    counts = {
        "english_files": sum(
            item["language"] == "english" for item in source_rows
        ),
        "russian_files": sum(
            item["language"] == "russian" for item in source_rows
        ),
        "english_occurrences": sum(
            item["language"] == "english" for item in occurrence_rows
        ),
        "russian_occurrences": sum(
            item["language"] == "russian" for item in occurrence_rows
        ),
        "strict_eligible_pairs": pair_counts["strict_reference"],
        "duplicate_key_occurrences": state_counts["duplicate_key"],
        "missing_counterparts": state_counts["missing_counterpart"],
        "version_mismatches": pair_counts["version_mismatch"],
        "protected_atom_mismatches": pair_counts[
            "protected_atom_mismatch"
        ],
        "malformed_record_units": malformed_records,
        "malformed_file_units": malformed_files,
        "quarantined_total": (
            state_counts["duplicate_key"]
            + state_counts["missing_counterpart"]
            + 2 * pair_counts["version_mismatch"]
            + 2 * pair_counts["protected_atom_mismatch"]
            + malformed_records
            + malformed_files
        ),
        "context_path_mismatches": sum(
            item["path_match"] == 0 for item in alignment_rows
        ),
        "ambiguous_english_groups": ambiguous_groups,
        "key_alias_groups": len(alias_groups),
        "source_mutations": 0,
        "ollama_calls": 0,
    }
    quarantine_counts: Counter[str] = Counter()
    quarantine_counts["duplicate_key"] = state_counts["duplicate_key"]
    quarantine_counts["missing_counterpart"] = state_counts[
        "missing_counterpart"
    ]
    quarantine_counts["version_mismatch"] = (
        2 * pair_counts["version_mismatch"]
    )
    quarantine_counts["protected_atom_mismatch"] = (
        2 * pair_counts["protected_atom_mismatch"]
    )
    for item in quarantine_rows:
        quarantine_counts[str(item["reason"])] += 1
    quarantine_by_reason = {
        key: value
        for key, value in sorted(quarantine_counts.items())
        if value
    }
    if sum(quarantine_by_reason.values()) != counts["quarantined_total"]:
        raise SafetyError("quarantine_reason_count_mismatch")
    return counts, quarantine_by_reason


def _key_alias_groups_from_database(
    occurrences: tuple[dict[str, object], ...],
) -> tuple[tuple[str, ...], ...]:
    groups: dict[str, set[str]] = defaultdict(set)
    for item in occurrences:
        key = str(item["key"])
        groups[unicodedata.normalize("NFD", key).casefold()].add(key)
    return tuple(
        tuple(sorted(values))
        for _, values in sorted(groups.items())
        if len(values) > 1
    )


def _logical_digest(connection: sqlite3.Connection) -> str:
    metadata_columns = (
        "schema_version",
        "application_id",
        "game_version",
        "build_status",
        "english_manifest_sha256",
        "russian_manifest_sha256",
        "english_dataset_sha256",
        "russian_dataset_sha256",
        *_COUNT_FIELDS,
    )
    logical_tables = (
        (
            "metadata",
            metadata_columns,
            "SELECT " + ", ".join(metadata_columns) + " FROM metadata",
        ),
        (
            "manifest_entries",
            (
                "language",
                "entry_kind",
                "relative_path",
                "byte_count",
                "content_sha256",
            ),
            """
            SELECT language, entry_kind, relative_path, byte_count,
                   content_sha256
            FROM manifest_entries
            """,
        ),
        (
            "source_files",
            (
                "language",
                "relative_path",
                "file_sha256",
                "byte_count",
                "parse_state",
                "parse_reason",
                "bom",
                "newline_style",
                "key_occupancy_scan_contract",
                "key_occupancy_candidate_count",
                "occurrence_count",
                "quarantine_count",
            ),
            """
            SELECT language, relative_path, file_sha256, byte_count,
                   parse_state, parse_reason, bom, newline_style,
                   key_occupancy_scan_contract,
                   key_occupancy_candidate_count,
                   occurrence_count, quarantine_count
            FROM source_files
            """,
        ),
        (
            "quarantined_key_occupancy",
            (
                "language",
                "relative_path",
                "key_hint",
                "candidate_count",
            ),
            """
            SELECT language, relative_path, key_hint, candidate_count
            FROM quarantined_key_occupancy
            """,
        ),
        (
            "occurrences",
            (
                "occurrence_id",
                "language",
                "relative_path",
                "occurrence_ordinal",
                "line_number",
                "localisation_key",
                "version_suffix",
                "human_value",
                "protected_signature_sha256",
                "source_sha256",
                "value_sha256",
                "alignment_state",
                "diagnostic_reason",
                "counterpart_occurrence_id",
                "context_path_match",
                "global_text_ambiguous",
                "key_alias_risk",
                "reference_status",
                "editorially_approved",
            ),
            """
            SELECT occurrence_id, language, relative_path,
                   occurrence_ordinal, line_number, localisation_key,
                   version_suffix, human_value,
                   protected_signature_sha256, source_sha256,
                   value_sha256, alignment_state, diagnostic_reason,
                   counterpart_occurrence_id, context_path_match,
                   global_text_ambiguous, key_alias_risk,
                   reference_status, editorially_approved
            FROM occurrences
            """,
        ),
        (
            "protected_tokens",
            (
                "occurrence_id",
                "token_ordinal",
                "token_kind",
                "exact_token",
            ),
            """
            SELECT occurrence_id, token_ordinal, token_kind, exact_token
            FROM protected_tokens
            """,
        ),
        (
            "unique_alignments",
            (
                "alignment_id",
                "english_occurrence_id",
                "russian_occurrence_id",
                "alignment_state",
                "path_family_match",
                "global_text_ambiguous",
            ),
            """
            SELECT alignment_id, english_occurrence_id,
                   russian_occurrence_id, alignment_state,
                   path_family_match, global_text_ambiguous
            FROM unique_alignments
            """,
        ),
        (
            "reference_pairs",
            (
                "pair_id",
                "alignment_id",
                "english_occurrence_id",
                "russian_occurrence_id",
                "context_path_match",
                "global_text_ambiguous",
                "reference_status",
                "editorially_approved",
            ),
            """
            SELECT pair_id, alignment_id, english_occurrence_id,
                   russian_occurrence_id, context_path_match,
                   global_text_ambiguous, reference_status,
                   editorially_approved
            FROM reference_pairs
            """,
        ),
        (
            "quarantine_records",
            (
                "quarantine_id",
                "language",
                "relative_path",
                "quarantine_scope",
                "occurrence_ordinal",
                "line_number",
                "key_hint",
                "source_sha256",
                "diagnostic_reason",
            ),
            """
            SELECT quarantine_id, language, relative_path,
                   quarantine_scope, occurrence_ordinal, line_number,
                   key_hint, source_sha256, diagnostic_reason
            FROM quarantine_records
            """,
        ),
    )
    rows: list[tuple[str, object]] = []
    for table, columns, sql in logical_tables:
        for row in connection.execute(sql):
            rows.append(
                (
                    table,
                    tuple(
                        (column, row[index])
                        for index, column in enumerate(columns)
                    ),
                )
            )
    return _semantic_digest(_LOGICAL_DIGEST_DOMAIN, rows)


def _semantic_digest(
    domain: bytes,
    rows: list[tuple[str, object]],
) -> str:
    encoded_rows = sorted(_encode_value(row) for row in rows)
    digest = hashlib.sha256()
    digest.update(len(domain).to_bytes(8, "big"))
    digest.update(domain)
    digest.update(len(encoded_rows).to_bytes(8, "big"))
    for encoded in encoded_rows:
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _stable_hash(domain: bytes, value: object) -> str:
    encoded = _encode_value(value)
    digest = hashlib.sha256()
    digest.update(len(domain).to_bytes(8, "big"))
    digest.update(domain)
    digest.update(len(encoded).to_bytes(8, "big"))
    digest.update(encoded)
    return digest.hexdigest()


def _encode_value(value: object) -> bytes:
    if value is None:
        return b"N" + (0).to_bytes(8, "big")
    if type(value) is bool:
        payload = b"1" if value else b"0"
        return b"B" + len(payload).to_bytes(8, "big") + payload
    if type(value) is int:
        payload = str(value).encode("ascii")
        return b"I" + len(payload).to_bytes(8, "big") + payload
    if isinstance(value, str):
        payload = value.encode("utf-8")
        return b"S" + len(payload).to_bytes(8, "big") + payload
    if isinstance(value, bytes):
        return b"Y" + len(value).to_bytes(8, "big") + value
    if isinstance(value, (tuple, list)):
        pieces = [_encode_value(item) for item in value]
        payload = b"".join(
            (
                len(pieces).to_bytes(8, "big"),
                *(
                    len(piece).to_bytes(8, "big") + piece
                    for piece in pieces
                ),
            )
        )
        return b"T" + len(payload).to_bytes(8, "big") + payload
    raise TypeError("unsupported logical digest value type")


def _require_int_value(
    name: str,
    value: object,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if type(value) is not int or value < minimum:
        raise SafetyError(f"{name}_type_or_range_invalid")
    if maximum is not None and value > maximum:
        raise SafetyError(f"{name}_type_or_range_invalid")
    return value


def _require_bool_int(name: str, value: object) -> int:
    parsed = _require_int_value(name, value, 0, 1)
    return parsed


def _require_text_value(
    name: str,
    value: object,
    *,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise SafetyError(f"{name}_type_invalid")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SafetyError(f"{name}_encoding_invalid") from exc
    return value


def _require_choice_value(
    name: str,
    value: object,
    choices: set[str],
) -> str:
    text = _require_text_value(name, value)
    if text not in choices:
        raise SafetyError(f"{name}_unknown")
    return text


def _require_sha256_value(name: str, value: object) -> str:
    text = _require_text_value(name, value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise SafetyError(f"{name}_invalid")
    return text


def _require_relative_path_value(value: object) -> str:
    text = _require_text_value("relative_path", value)
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or not path.parts
        or text == "."
        or ".." in path.parts
        or path.as_posix() != text
        or any(
            ord(char) < 0x20
            or ord(char) == 0x7F
            or 0x80 <= ord(char) <= 0x9F
            or char in "\u2028\u2029"
            or unicodedata.category(char) in {"Zl", "Zp"}
            or unicodedata.category(char) == "Cf"
            for char in text
        )
    ):
        raise SafetyError("relative_path_invalid")
    return text


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
