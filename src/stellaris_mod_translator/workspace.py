"""Narrow SQLite persistence for resumable full-mod translation jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat
from urllib.parse import quote


SCHEMA_VERSION = 2
KNOWN_ERROR_CODES = frozenset(
    {"model_result_invalid", "renderer_validation_failed"}
)
_TERMINAL_STATES = frozenset(
    {"accepted_changed", "accepted_unchanged", "model_fallback"}
)
_ALL_STATES = _TERMINAL_STATES | {"pending"}
_HEX = frozenset("0123456789abcdef")

_SCHEMA = """
CREATE TABLE job (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 2),
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
    completed_at TEXT,
    finalization_state TEXT NOT NULL
        CHECK (finalization_state IN ('none', 'intent')),
    output_tree_sha256 TEXT,
    output_file_count INTEGER CHECK (
        output_file_count IS NULL OR output_file_count >= 1
    ),
    output_directory_count INTEGER CHECK (
        output_directory_count IS NULL OR output_directory_count >= 1
    ),
    report_run_count INTEGER CHECK (
        report_run_count IS NULL OR report_run_count >= 1
    ),
    report_reused_count INTEGER CHECK (
        report_reused_count IS NULL OR report_reused_count >= 0
    ),
    report_calls_count INTEGER CHECK (
        report_calls_count IS NULL OR report_calls_count >= 0
    ),
    finalization_started_at TEXT,
    CHECK (
        (
            finalization_state = 'none'
            AND output_tree_sha256 IS NULL
            AND output_file_count IS NULL
            AND output_directory_count IS NULL
            AND report_run_count IS NULL
            AND report_reused_count IS NULL
            AND report_calls_count IS NULL
            AND finalization_started_at IS NULL
        )
        OR (
            finalization_state = 'intent'
            AND output_tree_sha256 IS NOT NULL
            AND output_file_count IS NOT NULL
            AND output_directory_count IS NOT NULL
            AND report_run_count IS NOT NULL
            AND report_reused_count IS NOT NULL
            AND report_calls_count IS NOT NULL
            AND finalization_started_at IS NOT NULL
        )
    ),
    CHECK (
        (
            state = 'in_progress'
            AND completed_at IS NULL
        )
        OR (
            state = 'completed'
            AND completed_at IS NOT NULL
            AND finalization_state = 'intent'
            AND completed_count = occurrence_count
        )
    )
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
    error_code TEXT CHECK (
        error_code IS NULL
        OR error_code IN ('model_result_invalid', 'renderer_validation_failed')
    ),
    FOREIGN KEY (relative_path) REFERENCES inventory(relative_path),
    UNIQUE (relative_path, line_number, ordinal, source_span_sha256),
    CHECK (
        (
            state = 'accepted_changed'
            AND model_result IS NOT NULL
            AND error_code IS NULL
        )
        OR (
            state = 'accepted_unchanged'
            AND model_result IS NULL
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


class WorkspaceError(RuntimeError):
    """A workspace is unsafe, inconsistent, or incompatible."""


class _HotJournalRecoveryRequired(RuntimeError):
    pass


@dataclass(frozen=True)
class _FileIdentity:
    device: int
    inode: int
    size: int
    modified_ns: int
    link_count: int


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
    finalization_state: str
    output_tree_sha256: str | None
    output_file_count: int | None
    output_directory_count: int | None
    report_run_count: int | None
    report_reused_count: int | None
    report_calls_count: int | None
    finalization_started_at: str | None


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
        if _require_workspace_file(path) != created_identity:
            raise WorkspaceError("workspace_replaced_during_creation")
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        connection.executescript(_SCHEMA)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        now = _timestamp()
        connection.execute(
            """
            INSERT INTO job (
                singleton,
                schema_version,
                state,
                source_path,
                output_path,
                source_tree_sha256,
                inventory_sha256,
                parser_order_version,
                model_tag,
                model_digest,
                prompt_profile_hash,
                occurrence_count,
                completed_count,
                run_count,
                created_at,
                updated_at,
                finalization_state
            )
            VALUES (
                1, ?, 'in_progress', ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?,
                'none'
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
    except WorkspaceError:
        if connection is not None:
            connection.close()
        _unlink_if_identity(path, created_identity)
        raise
    except sqlite3.Error as exc:
        if connection is not None:
            connection.close()
        _unlink_if_identity(path, created_identity)
        raise WorkspaceError("workspace_creation_failed") from exc
    except BaseException:
        if connection is not None:
            connection.close()
        _unlink_if_identity(path, created_identity)
        raise
    else:
        connection.close()
    final_identity = _require_workspace_file(path)
    if (final_identity.device, final_identity.inode) != (
        created_identity.device,
        created_identity.inode,
    ):
        raise WorkspaceError("workspace_replaced_during_creation")


def load_workspace(path: Path) -> WorkspaceSnapshot:
    try:
        return _load_workspace_read_only(path)
    except _HotJournalRecoveryRequired:
        _recover_hot_delete_journal(path)
        return _load_workspace_read_only(path)


def _load_workspace_read_only(path: Path) -> WorkspaceSnapshot:
    before = _require_workspace_file(path)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(_read_only_uri(path), uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        _validate_database(connection)
        raw_job_rows = connection.execute(
            "SELECT * FROM job ORDER BY singleton"
        ).fetchall()
        if len(raw_job_rows) != 1:
            raise WorkspaceError("workspace_job_row_invalid")
        job = _validated_job_row(raw_job_rows[0])
        inventory = tuple(
            _validated_inventory_row(row)
            for row in connection.execute(
                "SELECT * FROM inventory ORDER BY sequence"
            )
        )
        occurrences = tuple(
            _validated_occurrence_row(row)
            for row in connection.execute(
                "SELECT * FROM occurrences ORDER BY sequence"
            )
        )
    except WorkspaceError:
        raise
    except sqlite3.OperationalError as exc:
        if _is_readonly_recovery_error(exc) and _journal_path(path).exists():
            raise _HotJournalRecoveryRequired() from exc
        raise WorkspaceError("workspace_database_invalid") from exc
    except (sqlite3.DatabaseError, UnicodeError, TypeError, ValueError) as exc:
        raise WorkspaceError("workspace_database_invalid") from exc
    finally:
        if connection is not None:
            try:
                connection.close()
            except sqlite3.Error as exc:
                raise WorkspaceError("workspace_database_close_failed") from exc
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
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self.path)
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            journal_mode = connection.execute(
                "PRAGMA journal_mode"
            ).fetchone()[0]
            if str(journal_mode).lower() != "delete":
                raise WorkspaceError("workspace_journal_mode_invalid")
            after = _require_workspace_file(self.path)
            if (after.device, after.inode) != (before.device, before.inode):
                raise WorkspaceError("workspace_replaced_before_write")
        except WorkspaceError:
            if connection is not None:
                try:
                    connection.close()
                except sqlite3.Error:
                    pass
            raise
        except sqlite3.Error as exc:
            if connection is not None:
                try:
                    connection.close()
                except sqlite3.Error:
                    pass
            raise WorkspaceError("workspace_writer_open_failed") from exc
        assert connection is not None
        self.connection = connection
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self.connection is not None:
            try:
                self.connection.close()
            except sqlite3.Error as exc:
                raise WorkspaceError("workspace_writer_close_failed") from exc
            finally:
                self.connection = None

    def execute(
        self, sql: str, parameters: tuple[object, ...] = ()
    ) -> sqlite3.Cursor:
        return self._connection().execute(sql, parameters)

    def start_resume_run(self) -> None:
        try:
            self.execute("BEGIN IMMEDIATE")
            cursor = self.execute(
                """
                UPDATE job
                SET run_count = run_count + 1, updated_at = ?
                WHERE singleton = 1
                  AND state = 'in_progress'
                  AND finalization_state = 'none'
                """,
                (_timestamp(),),
            )
            if cursor.rowcount != 1:
                raise WorkspaceError("workspace_not_translating")
            self._connection().commit()
        except WorkspaceError:
            _rollback_safely(self._connection())
            raise
        except sqlite3.Error as exc:
            _rollback_safely(self._connection())
            raise WorkspaceError("workspace_resume_update_failed") from exc
        except BaseException:
            _rollback_safely(self._connection())
            raise

    def checkpoint(
        self,
        sequence: int,
        *,
        state: str,
        model_result: str | None,
        error_code: str | None,
    ) -> None:
        _validate_checkpoint_payload(state, model_result, error_code)
        try:
            self.execute("BEGIN IMMEDIATE")
            cursor = self.execute(
                """
                UPDATE occurrences
                SET state = ?, model_result = ?, error_code = ?
                WHERE sequence = ? AND state = 'pending'
                """,
                (state, model_result, error_code, sequence),
            )
            if cursor.rowcount != 1:
                raise WorkspaceError("workspace_checkpoint_target_invalid")
            cursor = self.execute(
                """
                UPDATE job
                SET completed_count = completed_count + 1, updated_at = ?
                WHERE singleton = 1
                  AND state = 'in_progress'
                  AND finalization_state = 'none'
                  AND completed_count < occurrence_count
                """,
                (_timestamp(),),
            )
            if cursor.rowcount != 1:
                raise WorkspaceError("workspace_counter_update_invalid")
            self._connection().commit()
        except WorkspaceError:
            _rollback_safely(self._connection())
            raise
        except sqlite3.Error as exc:
            _rollback_safely(self._connection())
            raise WorkspaceError("workspace_checkpoint_failed") from exc
        except BaseException:
            _rollback_safely(self._connection())
            raise

    def _connection(self) -> sqlite3.Connection:
        if self.connection is None:
            raise WorkspaceError("workspace_writer_not_open")
        return self.connection


def set_finalization_intent(
    path: Path,
    *,
    output_tree_sha256: str,
    output_file_count: int,
    output_directory_count: int,
    report_run_count: int,
    report_reused_count: int,
    report_calls_count: int,
) -> None:
    _require_sha256("output_tree_sha256", output_tree_sha256)
    _require_int("output_file_count", output_file_count, minimum=1)
    _require_int(
        "output_directory_count", output_directory_count, minimum=1
    )
    _require_int("report_run_count", report_run_count, minimum=1)
    _require_int("report_reused_count", report_reused_count, minimum=0)
    _require_int("report_calls_count", report_calls_count, minimum=0)
    with WorkspaceWriter(path) as writer:
        try:
            writer.execute("BEGIN IMMEDIATE")
            pending = writer.execute(
                "SELECT COUNT(*) FROM occurrences WHERE state = 'pending'"
            ).fetchone()[0]
            if pending != 0:
                raise WorkspaceError("workspace_pending_not_zero")
            now = _timestamp()
            cursor = writer.execute(
                """
                UPDATE job
                SET finalization_state = 'intent',
                    output_tree_sha256 = ?,
                    output_file_count = ?,
                    output_directory_count = ?,
                    report_run_count = ?,
                    report_reused_count = ?,
                    report_calls_count = ?,
                    finalization_started_at = ?,
                    updated_at = ?
                WHERE singleton = 1
                  AND state = 'in_progress'
                  AND finalization_state = 'none'
                  AND completed_count = occurrence_count
                """,
                (
                    output_tree_sha256,
                    output_file_count,
                    output_directory_count,
                    report_run_count,
                    report_reused_count,
                    report_calls_count,
                    now,
                    now,
                ),
            )
            if cursor.rowcount != 1:
                raise WorkspaceError("workspace_finalization_intent_invalid")
            writer._connection().commit()
        except WorkspaceError:
            _rollback_safely(writer._connection())
            raise
        except sqlite3.Error as exc:
            _rollback_safely(writer._connection())
            raise WorkspaceError(
                "workspace_finalization_intent_failed"
            ) from exc
        except BaseException:
            _rollback_safely(writer._connection())
            raise


def mark_workspace_completed(
    path: Path,
    *,
    output_tree_sha256: str,
    output_file_count: int,
    output_directory_count: int,
) -> None:
    with WorkspaceWriter(path) as writer:
        try:
            writer.execute("BEGIN IMMEDIATE")
            pending = writer.execute(
                "SELECT COUNT(*) FROM occurrences WHERE state = 'pending'"
            ).fetchone()[0]
            if pending != 0:
                raise WorkspaceError("workspace_pending_not_zero")
            now = _timestamp()
            cursor = writer.execute(
                """
                UPDATE job
                SET state = 'completed', completed_at = ?, updated_at = ?
                WHERE singleton = 1
                  AND state = 'in_progress'
                  AND finalization_state = 'intent'
                  AND completed_count = occurrence_count
                  AND output_tree_sha256 = ?
                  AND output_file_count = ?
                  AND output_directory_count = ?
                """,
                (
                    now,
                    now,
                    output_tree_sha256,
                    output_file_count,
                    output_directory_count,
                ),
            )
            if cursor.rowcount != 1:
                raise WorkspaceError("workspace_completion_state_invalid")
            writer._connection().commit()
        except WorkspaceError:
            _rollback_safely(writer._connection())
            raise
        except sqlite3.Error as exc:
            _rollback_safely(writer._connection())
            raise WorkspaceError("workspace_completion_failed") from exc
        except BaseException:
            _rollback_safely(writer._connection())
            raise


def _validate_database(connection: sqlite3.Connection) -> None:
    integrity = connection.execute("PRAGMA integrity_check").fetchall()
    if len(integrity) != 1 or integrity[0][0] != "ok":
        raise WorkspaceError("workspace_integrity_check_failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise WorkspaceError("workspace_foreign_key_check_failed")
    user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    if type(user_version) is not int or user_version != SCHEMA_VERSION:
        raise WorkspaceError("workspace_schema_version_unknown")
    journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    if str(journal_mode).lower() != "delete":
        raise WorkspaceError("workspace_journal_mode_invalid")
    if _schema_signature(connection) != _expected_schema_signature():
        raise WorkspaceError("workspace_schema_contract_invalid")


def _validated_job_row(raw: sqlite3.Row) -> JobRow:
    if set(raw.keys()) != {
        "singleton",
        "schema_version",
        "state",
        "source_path",
        "output_path",
        "source_tree_sha256",
        "inventory_sha256",
        "parser_order_version",
        "model_tag",
        "model_digest",
        "prompt_profile_hash",
        "occurrence_count",
        "completed_count",
        "run_count",
        "created_at",
        "updated_at",
        "completed_at",
        "finalization_state",
        "output_tree_sha256",
        "output_file_count",
        "output_directory_count",
        "report_run_count",
        "report_reused_count",
        "report_calls_count",
        "finalization_started_at",
    }:
        raise WorkspaceError("workspace_job_columns_invalid")
    if _require_int("singleton", raw["singleton"], minimum=1, maximum=1) != 1:
        raise WorkspaceError("workspace_job_singleton_invalid")
    if (
        _require_int(
            "schema_version", raw["schema_version"], minimum=SCHEMA_VERSION
        )
        != SCHEMA_VERSION
    ):
        raise WorkspaceError("workspace_schema_version_unknown")
    state = _require_choice(
        "state", raw["state"], {"in_progress", "completed"}
    )
    finalization_state = _require_choice(
        "finalization_state", raw["finalization_state"], {"none", "intent"}
    )
    occurrence_count = _require_int(
        "occurrence_count", raw["occurrence_count"], minimum=0
    )
    completed_count = _require_int(
        "completed_count", raw["completed_count"], minimum=0
    )
    run_count = _require_int("run_count", raw["run_count"], minimum=1)
    created_at = _require_timestamp("created_at", raw["created_at"])
    updated_at = _require_timestamp("updated_at", raw["updated_at"])
    completed_at = _optional_timestamp("completed_at", raw["completed_at"])

    if completed_count > occurrence_count:
        raise WorkspaceError("workspace_completed_count_invalid")
    if finalization_state == "none":
        for name in (
            "output_tree_sha256",
            "output_file_count",
            "output_directory_count",
            "report_run_count",
            "report_reused_count",
            "report_calls_count",
            "finalization_started_at",
        ):
            if raw[name] is not None:
                raise WorkspaceError("workspace_finalization_fields_invalid")
        output_tree_sha256 = None
        output_file_count = None
        output_directory_count = None
        report_run_count = None
        report_reused_count = None
        report_calls_count = None
        finalization_started_at = None
    else:
        output_tree_sha256 = _require_sha256(
            "output_tree_sha256", raw["output_tree_sha256"]
        )
        output_file_count = _require_int(
            "output_file_count", raw["output_file_count"], minimum=1
        )
        output_directory_count = _require_int(
            "output_directory_count",
            raw["output_directory_count"],
            minimum=1,
        )
        report_run_count = _require_int(
            "report_run_count", raw["report_run_count"], minimum=1
        )
        report_reused_count = _require_int(
            "report_reused_count", raw["report_reused_count"], minimum=0
        )
        report_calls_count = _require_int(
            "report_calls_count", raw["report_calls_count"], minimum=0
        )
        finalization_started_at = _require_timestamp(
            "finalization_started_at", raw["finalization_started_at"]
        )
    if state == "completed":
        if (
            completed_at is None
            or finalization_state != "intent"
            or completed_count != occurrence_count
        ):
            raise WorkspaceError("workspace_completed_state_invalid")
    elif completed_at is not None:
        raise WorkspaceError("workspace_in_progress_state_invalid")

    return JobRow(
        state=state,
        source_path=_require_text("source_path", raw["source_path"]),
        output_path=_require_text("output_path", raw["output_path"]),
        source_tree_sha256=_require_sha256(
            "source_tree_sha256", raw["source_tree_sha256"]
        ),
        inventory_sha256=_require_sha256(
            "inventory_sha256", raw["inventory_sha256"]
        ),
        parser_order_version=_require_text(
            "parser_order_version", raw["parser_order_version"]
        ),
        model_tag=_require_text("model_tag", raw["model_tag"]),
        model_digest=_require_text("model_digest", raw["model_digest"]),
        prompt_profile_hash=_require_sha256(
            "prompt_profile_hash", raw["prompt_profile_hash"]
        ),
        occurrence_count=occurrence_count,
        completed_count=completed_count,
        run_count=run_count,
        created_at=created_at,
        updated_at=updated_at,
        completed_at=completed_at,
        finalization_state=finalization_state,
        output_tree_sha256=output_tree_sha256,
        output_file_count=output_file_count,
        output_directory_count=output_directory_count,
        report_run_count=report_run_count,
        report_reused_count=report_reused_count,
        report_calls_count=report_calls_count,
        finalization_started_at=finalization_started_at,
    )


def _validated_inventory_row(raw: sqlite3.Row) -> InventoryRow:
    sequence = _require_int("inventory_sequence", raw["sequence"], minimum=0)
    relative_path = _require_relative_path(raw["relative_path"])
    parse_status = _require_choice(
        "parse_status",
        raw["parse_status"],
        {"english", "non_english", "skipped"},
    )
    return InventoryRow(
        sequence=sequence,
        relative_path=relative_path,
        sha256=_require_sha256("inventory_sha256", raw["sha256"]),
        byte_count=_require_int(
            "inventory_byte_count", raw["byte_count"], minimum=0
        ),
        parse_status=parse_status,
        occurrence_count=_require_int(
            "inventory_occurrence_count",
            raw["occurrence_count"],
            minimum=0,
        ),
        unsupported_count=_require_int(
            "inventory_unsupported_count",
            raw["unsupported_count"],
            minimum=0,
        ),
    )


def _validated_occurrence_row(raw: sqlite3.Row) -> OccurrenceRow:
    state = _require_choice("occurrence_state", raw["state"], _ALL_STATES)
    model_result = raw["model_result"]
    error_code = raw["error_code"]
    if state == "accepted_changed":
        model_result = _require_text("model_result", model_result, allow_empty=True)
        if error_code is not None:
            raise WorkspaceError("workspace_occurrence_payload_invalid")
    elif state == "accepted_unchanged":
        if model_result is not None or error_code is not None:
            raise WorkspaceError("workspace_occurrence_payload_invalid")
    elif state == "model_fallback":
        if model_result is not None:
            raise WorkspaceError("workspace_occurrence_payload_invalid")
        error_code = _require_choice(
            "error_code", error_code, KNOWN_ERROR_CODES
        )
    elif model_result is not None or error_code is not None:
        raise WorkspaceError("workspace_occurrence_payload_invalid")
    return OccurrenceRow(
        sequence=_require_int(
            "occurrence_sequence", raw["sequence"], minimum=0
        ),
        relative_path=_require_relative_path(raw["relative_path"]),
        line_number=_require_int(
            "occurrence_line_number", raw["line_number"], minimum=1
        ),
        ordinal=_require_int(
            "occurrence_ordinal", raw["ordinal"], minimum=0
        ),
        source_span_sha256=_require_sha256(
            "source_span_sha256", raw["source_span_sha256"]
        ),
        state=state,
        model_result=model_result,
        error_code=error_code,
    )


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
    completed = sum(row.state in _TERMINAL_STATES for row in occurrences)
    if (
        job.occurrence_count != len(occurrences)
        or job.completed_count != completed
    ):
        raise WorkspaceError("workspace_counter_mismatch")
    inventory_occurrences = sum(row.occurrence_count for row in inventory)
    if inventory_occurrences != job.occurrence_count:
        raise WorkspaceError("workspace_inventory_counter_mismatch")
    inventory_paths = {row.relative_path for row in inventory}
    if any(row.relative_path not in inventory_paths for row in occurrences):
        raise WorkspaceError("workspace_occurrence_foreign_path")
    if job.finalization_state == "intent" and completed != len(occurrences):
        raise WorkspaceError("workspace_finalization_pending_invalid")


def _validate_checkpoint_payload(
    state: str,
    model_result: str | None,
    error_code: str | None,
) -> None:
    if state == "accepted_changed":
        _require_text("model_result", model_result, allow_empty=True)
        valid = error_code is None
    elif state == "accepted_unchanged":
        valid = model_result is None and error_code is None
    elif state == "model_fallback":
        valid = (
            model_result is None
            and error_code in KNOWN_ERROR_CODES
        )
    else:
        valid = False
    if not valid:
        raise WorkspaceError("workspace_checkpoint_payload_invalid")


def _recover_hot_delete_journal(path: Path) -> None:
    database_before = _require_workspace_file(path)
    journal = _journal_path(path)
    _require_journal_file(journal)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(path)
        connection.execute(
            "SELECT name FROM sqlite_master ORDER BY name LIMIT 1"
        ).fetchone()
    except sqlite3.Error as exc:
        raise WorkspaceError("workspace_hot_journal_recovery_failed") from exc
    finally:
        if connection is not None:
            try:
                connection.close()
            except sqlite3.Error as exc:
                raise WorkspaceError(
                    "workspace_hot_journal_recovery_close_failed"
                ) from exc
    database_after = _require_workspace_file(path)
    if (
        database_after.device,
        database_after.inode,
        database_after.link_count,
    ) != (
        database_before.device,
        database_before.inode,
        database_before.link_count,
    ):
        raise WorkspaceError("workspace_replaced_during_recovery")
    if journal.exists() or journal.is_symlink():
        raise WorkspaceError("workspace_hot_journal_not_cleared")


def _require_workspace_file(path: Path) -> _FileIdentity:
    try:
        value = path.lstat()
    except FileNotFoundError as exc:
        raise WorkspaceError("workspace_does_not_exist") from exc
    if stat.S_ISLNK(value.st_mode):
        raise WorkspaceError("workspace_symlink")
    if not stat.S_ISREG(value.st_mode):
        raise WorkspaceError("workspace_not_regular_file")
    if value.st_nlink != 1:
        raise WorkspaceError("workspace_link_count_must_be_one")
    if stat.S_IMODE(value.st_mode) != 0o600:
        raise WorkspaceError("workspace_mode_must_be_0600")
    return _identity_from_stat(value)


def _require_journal_file(path: Path) -> _FileIdentity:
    try:
        value = path.lstat()
    except FileNotFoundError as exc:
        raise WorkspaceError("workspace_hot_journal_missing") from exc
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISREG(value.st_mode):
        raise WorkspaceError("workspace_hot_journal_not_regular")
    if value.st_nlink != 1:
        raise WorkspaceError("workspace_hot_journal_link_count_invalid")
    if stat.S_IMODE(value.st_mode) != 0o600:
        raise WorkspaceError("workspace_hot_journal_mode_invalid")
    if value.st_size <= 0:
        raise WorkspaceError("workspace_hot_journal_empty")
    return _identity_from_stat(value)


def _identity_from_stat(value: os.stat_result) -> _FileIdentity:
    return _FileIdentity(
        device=value.st_dev,
        inode=value.st_ino,
        size=value.st_size,
        modified_ns=value.st_mtime_ns,
        link_count=value.st_nlink,
    )


def _schema_signature(connection: sqlite3.Connection) -> tuple[object, ...]:
    master = tuple(
        tuple(row)
        for row in connection.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_master
            WHERE type IN ('table', 'index', 'view', 'trigger')
            ORDER BY type, name
            """
        )
    )
    table_details: list[tuple[object, ...]] = []
    for table in ("inventory", "job", "occurrences"):
        columns = tuple(
            tuple(row)
            for row in connection.execute(f"PRAGMA table_xinfo({table})")
        )
        indexes = tuple(
            tuple(row)
            for row in connection.execute(f"PRAGMA index_list({table})")
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
        table_details.append(
            (table, columns, indexes, index_details, foreign_keys)
        )
    return (master, tuple(table_details))


@lru_cache(maxsize=1)
def _expected_schema_signature() -> tuple[object, ...]:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(_SCHEMA)
        return _schema_signature(connection)
    finally:
        connection.close()


def _require_int(
    name: str,
    value: object,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if type(value) is not int or value < minimum:
        raise WorkspaceError(f"workspace_{name}_type_or_range_invalid")
    if maximum is not None and value > maximum:
        raise WorkspaceError(f"workspace_{name}_type_or_range_invalid")
    return value


def _require_text(
    name: str, value: object, *, allow_empty: bool = False
) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise WorkspaceError(f"workspace_{name}_type_invalid")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise WorkspaceError(f"workspace_{name}_encoding_invalid") from exc
    return value


def _require_choice(
    name: str, value: object, choices: frozenset[str] | set[str]
) -> str:
    text = _require_text(name, value)
    if text not in choices:
        raise WorkspaceError(f"workspace_{name}_unknown")
    return text


def _require_sha256(name: str, value: object) -> str:
    text = _require_text(name, value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise WorkspaceError(f"workspace_{name}_invalid")
    return text


def _require_timestamp(name: str, value: object) -> str:
    text = _require_text(name, value)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise WorkspaceError(f"workspace_{name}_invalid") from exc
    if parsed.tzinfo is None:
        raise WorkspaceError(f"workspace_{name}_invalid")
    return text


def _optional_timestamp(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _require_timestamp(name, value)


def _require_relative_path(value: object) -> str:
    text = _require_text("relative_path", value)
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != text:
        raise WorkspaceError("workspace_relative_path_invalid")
    return text


def _read_only_uri(path: Path) -> str:
    return "file:" + quote(os.fspath(path), safe="/") + "?mode=ro"


def _journal_path(path: Path) -> Path:
    return Path(os.fspath(path) + "-journal")


def _is_readonly_recovery_error(error: sqlite3.OperationalError) -> bool:
    code = getattr(error, "sqlite_errorcode", None)
    return code == getattr(sqlite3, "SQLITE_READONLY", 8) or (
        "readonly" in str(error).lower()
    )


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rollback_safely(connection: sqlite3.Connection) -> None:
    try:
        connection.rollback()
    except sqlite3.Error:
        pass


def _unlink_if_identity(path: Path, expected: _FileIdentity) -> None:
    try:
        value = path.lstat()
    except FileNotFoundError:
        return
    actual = _identity_from_stat(value)
    if (
        stat.S_ISREG(value.st_mode)
        and (actual.device, actual.inode) == (expected.device, expected.inode)
    ):
        path.unlink()
