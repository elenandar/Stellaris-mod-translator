from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from stellaris_mod_translator import engine
from stellaris_mod_translator.engine import SafetyError, translate_mod
from stellaris_mod_translator.ollama import OllamaError
from stellaris_mod_translator import workspace as workspace_module
from stellaris_mod_translator.workspace import (
    InventoryRow,
    OccurrenceRow,
    WorkspaceError,
    WorkspaceWriter,
    create_workspace,
    load_workspace,
)


SOURCE_BYTES = (
    b'l_english:\n'
    b' one:0 "Distinctive alpha sentence"\n'
    b' two:0 "Distinctive beta sentence"\n'
)


class SyntheticClient:
    def __init__(self, *, echo: bool = False) -> None:
        self.echo = echo
        self.calls: list[str] = []
        self.inventory_calls = 0

    def exact_model(self, tag: str) -> dict[str, str]:
        self.inventory_calls += 1
        return {"tag": tag, "digest": "sha256:synthetic"}

    def translate(self, *, tag: str, text: str) -> str:
        self.calls.append(text)
        return text if self.echo else "RU " + text


def make_source(tmp_path: Path, data: bytes = SOURCE_BYTES) -> Path:
    source = tmp_path / "source"
    source_file = source / "localisation/english/demo_l_english.yml"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(data)
    return source


def paths(tmp_path: Path) -> tuple[Path, Path]:
    return (
        tmp_path / "candidate",
        tmp_path / "job.smt-workspace.sqlite3",
    )


def crash_after_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    interruption: BaseException,
) -> tuple[Path, Path, Path]:
    source = make_source(tmp_path)
    output, workspace = paths(tmp_path)
    real_completion = engine.mark_workspace_completed

    def fail_completion(*args: object, **kwargs: object) -> None:
        raise interruption

    monkeypatch.setattr(engine, "mark_workspace_completed", fail_completion)
    expected = (
        KeyboardInterrupt
        if isinstance(interruption, KeyboardInterrupt)
        else SafetyError
    )
    with pytest.raises(expected):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: SyntheticClient(),
        )
    monkeypatch.setattr(engine, "mark_workspace_completed", real_completion)
    snapshot = load_workspace(workspace)
    assert snapshot.job.state == "in_progress"
    assert snapshot.job.finalization_state == "intent"
    assert snapshot.job.output_tree_sha256 is not None
    assert output.is_dir()
    return source, output, workspace


def test_exception_after_rename_recovers_without_model_or_republication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, output, workspace = crash_after_publish(
        tmp_path,
        monkeypatch,
        interruption=sqlite3.OperationalError("synthetic completion failure"),
    )
    output_inode = output.stat().st_ino
    output_hash = engine._output_tree_identity(output).sha256
    client = SyntheticClient()

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        resume=True,
        client_factory=lambda: client,
    )

    assert client.calls == []
    assert client.inventory_calls == 0
    assert output.stat().st_ino == output_inode
    assert engine._output_tree_identity(output).sha256 == output_hash
    assert load_workspace(workspace).job.state == "completed"
    assert (
        report["resumability"]["workspace_state_at_report_creation"]
        == "in_progress"
    )
    assert report["resumability"]["completion_attested_by_report"] is False


def test_keyboard_interrupt_after_rename_recovers_without_model_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, output, workspace = crash_after_publish(
        tmp_path,
        monkeypatch,
        interruption=KeyboardInterrupt(),
    )
    client = SyntheticClient()

    translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        resume=True,
        client_factory=lambda: client,
    )

    assert client.calls == []
    assert client.inventory_calls == 0
    assert output.is_dir()
    assert load_workspace(workspace).job.state == "completed"


def test_interruption_after_intent_before_publication_rebuilds_exact_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_source(tmp_path)
    output, workspace = paths(tmp_path)
    real_publish = engine.atomic_publish_directory_no_replace

    def interrupt_before_rename(
        source_path: Path, destination_path: Path
    ) -> None:
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        engine, "atomic_publish_directory_no_replace", interrupt_before_rename
    )
    with pytest.raises(KeyboardInterrupt):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: SyntheticClient(),
        )
    snapshot = load_workspace(workspace)
    expected_hash = snapshot.job.output_tree_sha256
    assert snapshot.job.finalization_state == "intent"
    assert not output.exists()
    monkeypatch.setattr(
        engine, "atomic_publish_directory_no_replace", real_publish
    )
    resume_client = SyntheticClient()

    translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        resume=True,
        client_factory=lambda: resume_client,
    )

    assert resume_client.calls == []
    assert engine._output_tree_identity(output).sha256 == expected_hash
    assert load_workspace(workspace).job.state == "completed"


@pytest.mark.parametrize(
    "tamper",
    ["changed", "incomplete", "extra", "symlink", "fifo"],
)
def test_mismatched_published_output_is_rejected_without_mutations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    source, output, workspace = crash_after_publish(
        tmp_path,
        monkeypatch,
        interruption=sqlite3.OperationalError("synthetic completion failure"),
    )
    report = output / "translation-report.json"
    candidate = output / "localisation/russian/demo_l_russian.yml"
    if tamper == "changed":
        report.write_bytes(report.read_bytes() + b" ")
    elif tamper == "incomplete":
        candidate.unlink()
    elif tamper == "extra":
        (output / "foreign.txt").write_bytes(b"foreign")
    elif tamper == "symlink":
        report.unlink()
        report.symlink_to(candidate)
    else:
        report.unlink()
        os.mkfifo(report, 0o600)
    workspace_before = hashlib.sha256(workspace.read_bytes()).hexdigest()
    client = SyntheticClient()

    with pytest.raises(SafetyError, match="finalization_output"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: client,
        )

    assert client.calls == []
    assert client.inventory_calls == 0
    assert hashlib.sha256(workspace.read_bytes()).hexdigest() == workspace_before
    assert load_workspace(workspace).job.state == "in_progress"


def test_checkpoint_operational_error_is_controlled_and_keeps_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_source(tmp_path)
    output, workspace = paths(tmp_path)
    original_execute = WorkspaceWriter.execute

    def fail_checkpoint(
        self: WorkspaceWriter,
        sql: str,
        parameters: tuple[object, ...] = (),
    ) -> sqlite3.Cursor:
        if "UPDATE occurrences" in sql:
            raise sqlite3.OperationalError("synthetic checkpoint failure")
        return original_execute(self, sql, parameters)

    monkeypatch.setattr(WorkspaceWriter, "execute", fail_checkpoint)
    with pytest.raises(SafetyError, match="workspace_checkpoint_failed"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: SyntheticClient(),
        )

    assert not output.exists()
    snapshot = load_workspace(workspace)
    assert snapshot.job.completed_count == 0
    assert all(row.state == "pending" for row in snapshot.occurrences)


def test_completion_operational_error_is_controlled_after_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_source(tmp_path)
    output, workspace = paths(tmp_path)
    original_execute = WorkspaceWriter.execute

    def fail_completion(
        self: WorkspaceWriter,
        sql: str,
        parameters: tuple[object, ...] = (),
    ) -> sqlite3.Cursor:
        if "SET state = 'completed'" in sql:
            raise sqlite3.OperationalError("synthetic completion failure")
        return original_execute(self, sql, parameters)

    monkeypatch.setattr(WorkspaceWriter, "execute", fail_completion)
    with pytest.raises(SafetyError, match="workspace_completion_failed"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: SyntheticClient(),
        )

    assert output.is_dir()
    snapshot = load_workspace(workspace)
    assert snapshot.job.state == "in_progress"
    assert snapshot.job.finalization_state == "intent"


def test_same_columns_without_constraints_are_rejected(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    output, workspace = paths(tmp_path)
    minimal_schema = """
    CREATE TABLE job (
        singleton INTEGER PRIMARY KEY, schema_version INTEGER, state TEXT,
        source_path TEXT, output_path TEXT, source_tree_sha256 TEXT,
        inventory_sha256 TEXT, parser_order_version TEXT, model_tag TEXT,
        model_digest TEXT, prompt_profile_hash TEXT, occurrence_count INTEGER,
        completed_count INTEGER, run_count INTEGER, created_at TEXT,
        updated_at TEXT, completed_at TEXT, finalization_state TEXT,
        output_tree_sha256 TEXT, output_file_count INTEGER,
        output_directory_count INTEGER, report_run_count INTEGER,
        report_reused_count INTEGER, report_calls_count INTEGER,
        finalization_started_at TEXT
    );
    CREATE TABLE inventory (
        sequence INTEGER PRIMARY KEY, relative_path TEXT, sha256 TEXT,
        byte_count INTEGER, parse_status TEXT, occurrence_count INTEGER,
        unsupported_count INTEGER
    );
    CREATE TABLE occurrences (
        sequence INTEGER PRIMARY KEY, relative_path TEXT, line_number INTEGER,
        ordinal INTEGER, source_span_sha256 TEXT, state TEXT,
        model_result TEXT, error_code TEXT
    );
    """
    with sqlite3.connect(workspace) as connection:
        connection.executescript(minimal_schema)
        connection.execute("PRAGMA user_version = 2")
    workspace.chmod(0o600)

    with pytest.raises(SafetyError, match="schema_contract_invalid"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: SyntheticClient(),
        )


def test_missing_fk_and_unique_index_are_rejected(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    output, workspace = paths(tmp_path)
    altered = workspace_module._SCHEMA.replace(
        """
    FOREIGN KEY (relative_path) REFERENCES inventory(relative_path),
    UNIQUE (relative_path, line_number, ordinal, source_span_sha256),
""",
        "",
    )
    with sqlite3.connect(workspace) as connection:
        connection.executescript(altered)
        connection.execute("PRAGMA user_version = 2")
    workspace.chmod(0o600)

    with pytest.raises(SafetyError, match="schema_contract_invalid"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: SyntheticClient(),
        )


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("job", "run_count"),
        ("job", "occurrence_count"),
        ("inventory", "byte_count"),
        ("occurrences", "line_number"),
    ],
)
def test_text_in_numeric_fields_is_controlled_tamper_rejection(
    tmp_path: Path,
    table: str,
    column: str,
) -> None:
    source = make_source(tmp_path)
    output, workspace = paths(tmp_path)
    client = SyntheticClient()

    class InterruptingClient(SyntheticClient):
        def translate(self, *, tag: str, text: str) -> str:
            raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: InterruptingClient(),
        )
    with sqlite3.connect(workspace) as connection:
        connection.execute(f"UPDATE {table} SET {column} = 'x'")
        connection.commit()

    with pytest.raises(SafetyError, match="type_or_range_invalid"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: client,
        )
    assert client.inventory_calls == 0


def test_unknown_error_code_is_controlled_tamper_rejection(
    tmp_path: Path,
) -> None:
    source = make_source(tmp_path)
    output, workspace = paths(tmp_path)

    class InterruptingClient(SyntheticClient):
        def translate(self, *, tag: str, text: str) -> str:
            raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: InterruptingClient(),
        )
    with sqlite3.connect(workspace) as connection:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute(
            """
            UPDATE occurrences
            SET state = 'model_fallback', error_code = 'future_error'
            WHERE sequence = 0
            """
        )
        connection.execute("UPDATE job SET completed_count = 1")
        connection.commit()

    with pytest.raises(SafetyError, match="error_code_unknown"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: SyntheticClient(),
        )


def test_hardlinked_workspace_is_rejected_before_sqlite_open(
    tmp_path: Path,
) -> None:
    source = make_source(tmp_path)
    output, workspace = paths(tmp_path)

    class InterruptingClient(SyntheticClient):
        def translate(self, *, tag: str, text: str) -> str:
            raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: InterruptingClient(),
        )
    os.link(workspace, tmp_path / "workspace-hardlink")

    with pytest.raises(SafetyError, match="link_count_must_be_one"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: SyntheticClient(),
        )


def test_real_hot_delete_journal_is_recovered_before_readonly_validation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "hot.smt-workspace.sqlite3"
    digest = "0" * 64
    occurrences = tuple(
        OccurrenceRow(
            sequence=index,
            relative_path="localisation/english/demo_l_english.yml",
            line_number=index + 2,
            ordinal=index,
            source_span_sha256=digest,
        )
        for index in range(3000)
    )
    create_workspace(
        workspace,
        source_path="/synthetic/source",
        output_path="/synthetic/output",
        source_tree_sha256=digest,
        inventory_sha256=digest,
        parser_order_version="synthetic-parser",
        model_tag="synthetic:1",
        model_digest="sha256:synthetic",
        prompt_profile_hash=digest,
        inventory=(
            InventoryRow(
                sequence=0,
                relative_path="localisation/english/demo_l_english.yml",
                sha256=digest,
                byte_count=1,
                parse_status="english",
                occurrence_count=len(occurrences),
                unsupported_count=0,
            ),
        ),
        occurrences=occurrences,
    )
    child = (
        "import os, sqlite3, sys\n"
        "connection = sqlite3.connect(sys.argv[1])\n"
        "connection.execute('PRAGMA journal_mode = DELETE')\n"
        "connection.execute('PRAGMA synchronous = FULL')\n"
        "connection.execute('PRAGMA cache_size = 1')\n"
        "connection.execute('PRAGMA cache_spill = ON')\n"
        "connection.execute('BEGIN IMMEDIATE')\n"
        "connection.execute(\"UPDATE occurrences SET "
        "state='model_fallback', error_code='model_result_invalid'\")\n"
        "os._exit(91)\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", child, os.fspath(workspace)],
        check=False,
    )

    assert result.returncode == 91
    journal = Path(os.fspath(workspace) + "-journal")
    assert journal.is_file()
    assert journal.stat().st_size > 0
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        with sqlite3.connect(
            f"file:{workspace}?mode=ro", uri=True
        ) as connection:
            connection.execute("SELECT COUNT(*) FROM occurrences").fetchone()

    snapshot = load_workspace(workspace)

    assert snapshot.job.completed_count == 0
    assert all(row.state == "pending" for row in snapshot.occurrences)
    assert not journal.exists()


def test_echo_results_are_not_stored_and_resume_never_recalls_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_source(tmp_path)
    output, workspace = paths(tmp_path)
    real_publish = engine.atomic_publish_directory_no_replace

    def interrupt_before_publish(
        source_path: Path, destination_path: Path
    ) -> None:
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        engine, "atomic_publish_directory_no_replace", interrupt_before_publish
    )
    first_client = SyntheticClient(echo=True)
    with pytest.raises(KeyboardInterrupt):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: first_client,
        )
    snapshot = load_workspace(workspace)
    assert all(
        row.state == "accepted_unchanged" for row in snapshot.occurrences
    )
    assert all(row.model_result is None for row in snapshot.occurrences)
    database_bytes = workspace.read_bytes()
    assert b"Distinctive alpha sentence" not in database_bytes
    assert b"Distinctive beta sentence" not in database_bytes
    monkeypatch.setattr(
        engine, "atomic_publish_directory_no_replace", real_publish
    )
    resume_client = SyntheticClient(echo=True)

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        resume=True,
        client_factory=lambda: resume_client,
    )

    assert resume_client.calls == []
    assert report["counts"]["unchanged_accepted_occurrences"] == 2
    assert (
        output / "localisation/russian/demo_l_russian.yml"
    ).read_bytes() == SOURCE_BYTES.replace(b"l_english:", b"l_russian:")
    assert load_workspace(workspace).job.state == "completed"


def test_legacy_single_pass_generic_ollama_error_is_per_entry_fallback(
    tmp_path: Path,
) -> None:
    source = make_source(tmp_path)
    output = tmp_path / "legacy-candidate"

    class LegacyClient(SyntheticClient):
        def translate(self, *, tag: str, text: str) -> str:
            self.calls.append(text)
            if len(self.calls) == 1:
                raise OllamaError("legacy per-entry failure")
            return "RU " + text

    client = LegacyClient()
    report = translate_mod(
        source,
        output,
        "synthetic:1",
        client_factory=lambda: client,
    )

    assert len(client.calls) == 2
    assert report["counts"]["fallback_occurrences"] == 1
    assert report["counts"]["translated_occurrences"] == 1
    rendered = (
        output / "localisation/russian/demo_l_russian.yml"
    ).read_text()
    assert ' one:0 "Distinctive alpha sentence"' in rendered
    assert ' two:0 "RU Distinctive beta sentence"' in rendered
