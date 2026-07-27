"""Narrow SQLite persistence for resumable full-mod translation jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import stat
from urllib.parse import quote


SCHEMA_VERSION = 1
_TERMINAL_STATES = frozenset(
    {"accepted_changed", "accepted_unchanged", "model_fallback"}
)
_ALL_STATES = _TERMINAL_STATES | {"pending"}

_SCHEMA = """
CREATE TABLE job (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('in_progress', 'completed')),
    source_path TEXT NOT NULL,
    output_path TEXT NOT NULL,
    source_tree_sha256 TEXT NOT NULL,
    inventory_sha256 TEXT NOT NULL,
    parser_order_version TEXT NOT NULL,
    model_tag TEXT NOT NULL,
    model_digest TEXT NOT NULL,
    prompt_profile_hash TEXT NOT NULL,
    occurrence_count INTEGER NOT NULL CHECK (occurrence_count >= 0),
    completed_count INTEGER NOT NULL
        CHECK (completed_count >= 0 AND completed_count <= occurrence_count),
    run_count INTEGER NOT NULL CHECK (run_count >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE inventory (
    sequence INTEGER PRIMARY KEY CHECK (sequence >= 0),
    relative_path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    byte_count INTEGER NOT NULL CHECK (byte_count >= 0),
    parse_status TEXT NOT NULL
        CHECK (parse_status IN ('english', 'non_english', 'skipped')),
    occurrence_count INTEGER NOT NULL CHECK (occurrence_count >= 0),
    unsupported_count INTEGER NOT NULL CHECK (unsupported_count >= 0)
);

CREATE TABLE occurrences (
    sequence INTEGER PRIMARY KEY CHECK (sequence >= 0),
    relative_path TEXT NOT NULL,
    line_number INTEGER NOT NULL CHECK (line_number >= 1),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    source_span_sha256 TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN (
            'pending',
            'accepted_changed',
            'accepted_unchanged',
            'model_fallback'
        )
    ),
    model_result TEXT,
    error_code TEXT,
    FOREIGN KEY (relative_path) REFERENCES inventory(relative_path),
    UNIQUE (relative_path, line_number, ordinal, source_span_sha256),
    CHECK (
        (
            state IN ('accepted_changed', 'accepted_unchanged')
            AND model_result IS NOT NULL
            AND error_code IS NULL
        )
        OR (
            state = 'model_fallback'
            AND model_result IS NULL
            AND error_code IS NOT NULL
        )
        OR (
            state = 'pending'
            AND model_result IS NULL
            AND error_code IS NULL
        )
    )
);
"""

_EXPECTED_COLUMNS = {
    "job": (
        ("singleton", "INTEGER", 0, 1),
        ("schema_version", "INTEGER", 1, 0),
        ("state", "TEXT", 1, 0),
        ("source_path", "TEXT", 1, 0),
        ("output_path", "TEXT", 1, 0),
        ("source_tree_sha256", "TEXT", 1, 0),
        ("inventory_sha256", "TEXT", 1, 0),
        ("parser_order_version", "TEXT", 1, 0),
        ("model_tag", "TEXT", 1, 0),
        ("model_digest", "TEXT", 1, 0),
        ("prompt_profile_hash", "TEXT", 1, 0),
        ("occurrence_count", "INTEGER", 1, 0),
        ("completed_count", "INTEGER", 1, 0),
        ("run_count", "INTEGER", 1, 0),
        ("created_at", "TEXT", 1, 0),
        ("updated_at", "TEXT", 1, 0),
        ("completed_at", "TEXT", 0, 0),
    ),
    "inventory": (
        ("sequence", "INTEGER", 0, 1),
        ("relative_path", "TEXT", 1, 0),
        ("sha256", "TEXT", 1, 0),
        ("byte_count", "INTEGER", 1, 0),
        ("parse_status", "TEXT", 1, 0),
        ("occurrence_count", "INTEGER", 1, 0),
        ("unsupported_count", "INTEGER", 1, 0),
    ),
    "occurrences": (
        ("sequence", "INTEGER", 0, 1),
        ("relative_path", "TEXT", 1, 0),
        ("line_number", "INTEGER", 1, 0),
        ("ordinal", "INTEGER", 1, 0),
        ("source_span_sha256", "TEXT", 1, 0),
        ("state", "TEXT", 1, 0),
        ("model_result", "TEXT", 0, 0),
        ("error_code", "TEXT", 0, 0),
    ),
}


class WorkspaceError(RuntimeError):
    """A workspace is unsafe, inconsistent, or incompatible."""


@dataclass(frozen=True)
class InventoryRow:
    sequence: int
    relative_path: str
    sha256: str
    byte_count: int
    parse_status: str
    occurrence_count: int
    unsupported_count: int


@dataclass(frozen=True)
class OccurrenceRow:
    sequence: int
    relative_path: str
    line_number: int
    ordinal: int
    source_span_sha256: str
    state: str = "pending"
    model_result: str | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class JobRow:
    state: str
    source_path: str
    output_path: str
    source_tree_sha256: str
    inventory_sha256: str
    parser_order_version: str
    model_tag: str
    model_digest: str
    prompt_profile_hash: str
    occurrence_count: int
    completed_count: int
    run_count: int
    created_at: str
    updated_at: str
    completed_at: str | None


@dataclass(frozen=True)
class WorkspaceSnapshot:
    job: JobRow
    inventory: tuple[InventoryRow, ...]
    occurrences: tuple[OccurrenceRow, ...]


def create_workspace(
    path: Path,
    *,
    source_path: str,
    output_path: str,
    source_tree_sha256: str,
    inventory_sha256: str,
    parser_order_version: str,
    model_tag: str,
    model_digest: str,
    prompt_profile_hash: str,
    inventory: tuple[InventoryRow, ...],
    occurrences: tuple[OccurrenceRow, ...],
) -> None:
    descriptor = os.open(
        path,
        os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(descriptor, 0o600)
        created_identity = _identity_from_stat(os.fstat(descriptor))
    finally:
        os.close(descriptor)

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        connection.executescript(_SCHEMA)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        now = _timestamp()
        connection.execute(
            """
            INSERT INTO job VALUES (
                1, ?, 'in_progress', ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?, NULL
            )
            """,
            (
                SCHEMA_VERSION,
                source_path,
                output_path,
                source_tree_sha256,
                inventory_sha256,
                parser_order_version,
                model_tag,
                model_digest,
                prompt_profile_hash,
                len(occurrences),
                now,
                now,
            ),
        )
        connection.executemany(
            """
            INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.sequence,
                    row.relative_path,
                    row.sha256,
                    row.byte_count,
                    row.parse_status,
                    row.occurrence_count,
                    row.unsupported_count,
                )
                for row in inventory
            ],
        )
        connection.executemany(
            """
            INSERT INTO occurrences VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.sequence,
                    row.relative_path,
                    row.line_number,
                    row.ordinal,
                    row.source_span_sha256,
                    row.state,
                    row.model_result,
                    row.error_code,
                )
                for row in occurrences
            ],
        )
        connection.commit()
    except BaseException:
        if connection is not None:
            connection.close()
        _unlink_if_identity(path, created_identity)
        raise
    else:
        connection.close()
    _require_workspace_file(path)


def load_workspace(path: Path) -> WorkspaceSnapshot:
    before = _require_workspace_file(path)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(_read_only_uri(path), uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        _validate_database(connection)
        job_rows = connection.execute(
            "SELECT * FROM job ORDER BY singleton"
        ).fetchall()
        if len(job_rows) != 1:
            raise WorkspaceError("workspace_job_row_invalid")
        raw_job = job_rows[0]
        if raw_job["singleton"] != 1 or raw_job["schema_version"] != SCHEMA_VERSION:
            raise WorkspaceError("workspace_schema_version_unknown")
        job = JobRow(
            **{
                name: raw_job[name]
                for name in JobRow.__dataclass_fields__
            }
        )
        inventory = tuple(
            InventoryRow(**dict(row))
            for row in connection.execute(
                "SELECT * FROM inventory ORDER BY sequence"
            )
        )
        occurrences = tuple(
            OccurrenceRow(**dict(row))
            for row in connection.execute(
                "SELECT * FROM occurrences ORDER BY sequence"
            )
        )
    except (sqlite3.DatabaseError, UnicodeError) as exc:
        raise WorkspaceError("workspace_database_invalid") from exc
    finally:
        if connection is not None:
            connection.close()
    after = _require_workspace_file(path)
    if after != before:
        raise WorkspaceError("workspace_changed_during_validation")
    _validate_snapshot_counters(job, inventory, occurrences)
    return WorkspaceSnapshot(
        job=job,
        inventory=inventory,
        occurrences=occurrences,
    )


class WorkspaceWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection: sqlite3.Connection | None = None

    def __enter__(self) -> "WorkspaceWriter":
        before = _require_workspace_file(self.path)
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            journal_mode = connection.execute(
                "PRAGMA journal_mode"
            ).fetchone()[0]
            if str(journal_mode).lower() != "delete":
                raise WorkspaceError("workspace_journal_mode_invalid")
            after = _require_workspace_file(self.path)
            if after[:2] != before[:2]:
                raise WorkspaceError("workspace_replaced_before_write")
        except BaseException:
            connection.close()
            raise
        self.connection = connection
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def start_resume_run(self) -> None:
        connection = self._connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE job
                SET run_count = run_count + 1, updated_at = ?
                WHERE singleton = 1 AND state = 'in_progress'
                """,
                (_timestamp(),),
            )
            if cursor.rowcount != 1:
                raise WorkspaceError("workspace_not_in_progress")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    def checkpoint(
        self,
        sequence: int,
        *,
        state: str,
        model_result: str | None,
        error_code: str | None,
    ) -> None:
        if state not in _TERMINAL_STATES:
            raise WorkspaceError("workspace_checkpoint_state_invalid")
        if state.startswith("accepted_"):
            valid_values = model_result is not None and error_code is None
        else:
            valid_values = model_result is None and error_code is not None
        if not valid_values:
            raise WorkspaceError("workspace_checkpoint_payload_invalid")

        connection = self._connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE occurrences
                SET state = ?, model_result = ?, error_code = ?
                WHERE sequence = ? AND state = 'pending'
                """,
                (state, model_result, error_code, sequence),
            )
            if cursor.rowcount != 1:
                raise WorkspaceError("workspace_checkpoint_target_invalid")
            cursor = connection.execute(
                """
                UPDATE job
                SET completed_count = completed_count + 1, updated_at = ?
                WHERE singleton = 1
                  AND state = 'in_progress'
                  AND completed_count < occurrence_count
                """,
                (_timestamp(),),
            )
            if cursor.rowcount != 1:
                raise WorkspaceError("workspace_counter_update_invalid")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    def _connection(self) -> sqlite3.Connection:
        if self.connection is None:
            raise WorkspaceError("workspace_writer_not_open")
        return self.connection


def mark_workspace_completed(path: Path) -> None:
    with WorkspaceWriter(path) as writer:
        connection = writer._connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            pending = connection.execute(
                "SELECT COUNT(*) FROM occurrences WHERE state = 'pending'"
            ).fetchone()[0]
            if pending != 0:
                raise WorkspaceError("workspace_pending_not_zero")
            now = _timestamp()
            cursor = connection.execute(
                """
                UPDATE job
                SET state = 'completed', completed_at = ?, updated_at = ?
                WHERE singleton = 1
                  AND state = 'in_progress'
                  AND completed_count = occurrence_count
                """,
                (now, now),
            )
            if cursor.rowcount != 1:
                raise WorkspaceError("workspace_completion_state_invalid")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


def _validate_database(connection: sqlite3.Connection) -> None:
    integrity = connection.execute("PRAGMA integrity_check").fetchall()
    if len(integrity) != 1 or integrity[0][0] != "ok":
        raise WorkspaceError("workspace_integrity_check_failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise WorkspaceError("workspace_foreign_key_check_failed")
    user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    if user_version != SCHEMA_VERSION:
        raise WorkspaceError("workspace_schema_version_unknown")
    journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    if str(journal_mode).lower() != "delete":
        raise WorkspaceError("workspace_journal_mode_invalid")
    objects = {
        (row[0], row[1])
        for row in connection.execute(
            """
            SELECT type, name
            FROM sqlite_master
            WHERE type IN ('table', 'view', 'trigger')
            """
        )
    }
    expected_objects = {("table", name) for name in _EXPECTED_COLUMNS}
    if objects != expected_objects:
        raise WorkspaceError("workspace_schema_objects_invalid")
    for table, expected in _EXPECTED_COLUMNS.items():
        actual = tuple(
            (row[1], row[2].upper(), row[3], row[5])
            for row in connection.execute(f"PRAGMA table_info({table})")
        )
        if actual != expected:
            raise WorkspaceError("workspace_schema_columns_invalid")


def _validate_snapshot_counters(
    job: JobRow,
    inventory: tuple[InventoryRow, ...],
    occurrences: tuple[OccurrenceRow, ...],
) -> None:
    if tuple(row.sequence for row in inventory) != tuple(range(len(inventory))):
        raise WorkspaceError("workspace_inventory_order_invalid")
    if tuple(row.sequence for row in occurrences) != tuple(
        range(len(occurrences))
    ):
        raise WorkspaceError("workspace_occurrence_order_invalid")
    if any(row.state not in _ALL_STATES for row in occurrences):
        raise WorkspaceError("workspace_occurrence_state_invalid")
    completed = sum(row.state in _TERMINAL_STATES for row in occurrences)
    if (
        job.occurrence_count != len(occurrences)
        or job.completed_count != completed
        or job.run_count < 1
    ):
        raise WorkspaceError("workspace_counter_mismatch")
    if job.state == "completed":
        if completed != len(occurrences) or job.completed_at is None:
            raise WorkspaceError("workspace_completed_state_invalid")
    elif job.state == "in_progress":
        if job.completed_at is not None:
            raise WorkspaceError("workspace_in_progress_state_invalid")
    else:
        raise WorkspaceError("workspace_job_state_invalid")


def _require_workspace_file(path: Path) -> tuple[int, int, int, int]:
    try:
        value = path.lstat()
    except FileNotFoundError as exc:
        raise WorkspaceError("workspace_does_not_exist") from exc
    if stat.S_ISLNK(value.st_mode):
        raise WorkspaceError("workspace_symlink")
    if not stat.S_ISREG(value.st_mode):
        raise WorkspaceError("workspace_not_regular_file")
    if stat.S_IMODE(value.st_mode) != 0o600:
        raise WorkspaceError("workspace_mode_must_be_0600")
    return _identity_from_stat(value)


def _identity_from_stat(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def _read_only_uri(path: Path) -> str:
    return "file:" + quote(os.fspath(path), safe="/") + "?mode=ro"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _unlink_if_identity(
    path: Path, expected: tuple[int, int, int, int]
) -> None:
    try:
        actual = _identity_from_stat(path.lstat())
    except FileNotFoundError:
        return
    if actual[:2] == expected[:2] and stat.S_ISREG(path.lstat().st_mode):
        path.unlink()
