from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
import time

import pytest

from stellaris_mod_translator import engine
from stellaris_mod_translator.engine import SafetyError, translate_mod
from stellaris_mod_translator.ollama import OllamaError
from stellaris_mod_translator import workspace as workspace_module
from stellaris_mod_translator.workspace import (
    InventoryRow,
    OccurrenceRow,
    WorkspaceError,
    WorkspaceRunLock,
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


def make_empty_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "empty.smt-workspace.sqlite3"
    digest = "0" * 64
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
        inventory=(),
        occurrences=(),
    )
    return workspace


def parallel_resume_worker(
    source: str,
    output: str,
    workspace: str,
    calls: object,
    inventory_calls: object,
    entered: object,
    release: object,
    results: object,
) -> None:
    class BarrierClient:
        def exact_model(self, tag: str) -> dict[str, str]:
            with inventory_calls.get_lock():
                inventory_calls.value += 1
            return {"tag": tag, "digest": "sha256:synthetic"}

        def translate(self, *, tag: str, text: str) -> str:
            with calls.get_lock():
                calls.value += 1
            entered.set()
            if not release.wait(10):
                raise RuntimeError("parallel_test_barrier_timeout")
            return "RU " + text

    try:
        report = translate_mod(
            Path(source),
            Path(output),
            "synthetic:1",
            workspace=Path(workspace),
            resume=True,
            client_factory=BarrierClient,
        )
    except BaseException as exc:
        results.put(("error", type(exc).__name__, str(exc)))
    else:
        results.put(("success", report["status"], ""))


def lock_holder(workspace: str, acquired: object) -> None:
    with WorkspaceRunLock(Path(workspace)):
        acquired.set()
        while True:
            time.sleep(60)


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
    client_constructions = 0

    def forbidden_client_factory() -> SyntheticClient:
        nonlocal client_constructions
        client_constructions += 1
        raise AssertionError("post_intent_recovery_created_model_client")

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        resume=True,
        client_factory=forbidden_client_factory,
    )

    assert client_constructions == 0
    assert report["counts"]["calls_in_final_run"] == 2
    assert engine._output_tree_identity(output).sha256 == expected_hash
    assert load_workspace(workspace).job.state == "completed"
    assert list(tmp_path.glob(".candidate.tmp-*")) == []


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


@pytest.mark.parametrize(
    "payload",
    [b"", b"\0" * 4096, b"not-a-sqlite-journal" * 256],
    ids=["empty", "zero-filled", "arbitrary-nonzero"],
)
def test_malformed_journal_is_rejected_before_sqlite_open_without_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    workspace = make_empty_workspace(tmp_path)
    source = make_source(tmp_path)
    output = tmp_path / "candidate"
    journal = Path(os.fspath(workspace) + "-journal")
    journal.write_bytes(payload)
    journal.chmod(0o600)
    database_before = hashlib.sha256(workspace.read_bytes()).hexdigest()

    def forbidden_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError("sqlite_opened_before_sidecar_preflight")

    monkeypatch.setattr(workspace_module.sqlite3, "connect", forbidden_connect)
    with pytest.raises(SafetyError, match="hot_journal_(empty|malformed)"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=SyntheticClient,
        )

    assert journal.read_bytes() == payload
    assert hashlib.sha256(workspace.read_bytes()).hexdigest() == database_before


@pytest.mark.parametrize("suffix", ["-wal", "-shm"])
def test_wal_and_shm_are_rejected_before_sqlite_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
) -> None:
    workspace = make_empty_workspace(tmp_path)
    source = make_source(tmp_path)
    output = tmp_path / "candidate"
    sidecar = Path(os.fspath(workspace) + suffix)
    sidecar.write_bytes(b"synthetic-sidecar")
    sidecar.chmod(0o600)
    database_before = hashlib.sha256(workspace.read_bytes()).hexdigest()

    def forbidden_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError("sqlite_opened_before_sidecar_preflight")

    monkeypatch.setattr(workspace_module.sqlite3, "connect", forbidden_connect)
    with pytest.raises(SafetyError, match=f"{suffix[1:]}_not_permitted"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=SyntheticClient,
        )

    assert sidecar.read_bytes() == b"synthetic-sidecar"
    assert hashlib.sha256(workspace.read_bytes()).hexdigest() == database_before


@pytest.mark.parametrize(
    ("kind", "error"),
    [
        ("symlink", "journal_not_regular"),
        ("hardlink", "journal_link_count_invalid"),
        ("wrong-mode", "journal_mode_invalid"),
    ],
)
def test_unsafe_journal_identity_is_rejected_before_sqlite_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    error: str,
) -> None:
    workspace = make_empty_workspace(tmp_path)
    journal = Path(os.fspath(workspace) + "-journal")
    target = tmp_path / "journal-target"
    target.write_bytes(b"x" * 4096)
    target.chmod(0o600)
    if kind == "symlink":
        journal.symlink_to(target)
    elif kind == "hardlink":
        os.link(target, journal)
    else:
        journal.write_bytes(b"x" * 4096)
        journal.chmod(0o644)

    def forbidden_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError("sqlite_opened_before_sidecar_preflight")

    monkeypatch.setattr(workspace_module.sqlite3, "connect", forbidden_connect)
    with pytest.raises(WorkspaceError, match=error):
        load_workspace(workspace)


def test_fifo_journal_fails_fast_without_sqlite_open_or_mutation(
    tmp_path: Path,
) -> None:
    workspace = make_empty_workspace(tmp_path)
    journal = Path(os.fspath(workspace) + "-journal")
    os.mkfifo(journal, 0o600)
    database_before = hashlib.sha256(workspace.read_bytes()).hexdigest()
    source_root = Path(__file__).resolve().parents[1] / "src"
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "from stellaris_mod_translator.workspace import "
        "WorkspaceError, load_workspace\n"
        "try:\n"
        "    load_workspace(Path(sys.argv[1]))\n"
        "except WorkspaceError as exc:\n"
        "    print(exc)\n"
        "    raise SystemExit(23)\n"
        "raise SystemExit(99)\n"
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.fspath(source_root)

    result = subprocess.run(
        [sys.executable, "-c", code, os.fspath(workspace)],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
        timeout=3,
    )

    assert result.returncode == 23
    assert result.stdout.strip() == "workspace_journal_not_regular"
    assert hashlib.sha256(workspace.read_bytes()).hexdigest() == database_before
    assert stat.S_ISFIFO(journal.lstat().st_mode)


def test_parallel_resume_has_one_model_caller_and_one_checkpoint_writer(
    tmp_path: Path,
) -> None:
    source = make_source(
        tmp_path,
        b'l_english:\n one:0 "Deterministic sentence"\n',
    )
    output, workspace = paths(tmp_path)

    class PendingClient(SyntheticClient):
        def translate(self, *, tag: str, text: str) -> str:
            raise OllamaError("synthetic transport stop")

    with pytest.raises(OllamaError, match="synthetic transport stop"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=PendingClient,
        )
    before = load_workspace(workspace)
    assert before.job.run_count == 1
    assert before.job.completed_count == 0

    context = multiprocessing.get_context("spawn")
    calls = context.Value("i", 0)
    inventory_calls = context.Value("i", 0)
    entered = context.Event()
    release = context.Event()
    results = context.Queue()
    arguments = (
        os.fspath(source),
        os.fspath(output),
        os.fspath(workspace),
        calls,
        inventory_calls,
        entered,
        release,
        results,
    )
    first = context.Process(target=parallel_resume_worker, args=arguments)
    second = context.Process(target=parallel_resume_worker, args=arguments)
    first.start()
    assert entered.wait(5)
    second.start()
    second.join(5)
    assert not second.is_alive()
    release.set()
    first.join(10)
    assert not first.is_alive()
    assert first.exitcode == 0
    assert second.exitcode == 0

    outcomes = [results.get(timeout=2), results.get(timeout=2)]
    assert sorted(item[0] for item in outcomes) == ["error", "success"]
    assert any(
        item[0] == "error" and item[2] == "workspace_already_in_use"
        for item in outcomes
    )
    assert calls.value == 1
    assert inventory_calls.value == 2
    snapshot = load_workspace(workspace)
    assert snapshot.job.run_count == 2
    assert snapshot.job.completed_count == 1
    assert snapshot.job.state == "completed"
    assert (
        output / "localisation/russian/demo_l_russian.yml"
    ).read_bytes() == (
        b'l_russian:\n one:0 "RU Deterministic sentence"\n'
    )


def test_workspace_lock_is_released_by_kernel_after_process_kill(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "kill-recovery.smt-workspace.sqlite3"
    context = multiprocessing.get_context("spawn")
    acquired = context.Event()
    process = context.Process(
        target=lock_holder, args=(os.fspath(workspace), acquired)
    )
    process.start()
    assert acquired.wait(5)
    process.terminate()
    process.join(5)
    assert not process.is_alive()

    with WorkspaceRunLock(workspace):
        pass

    lock_path = Path(os.fspath(workspace) + ".lock")
    assert stat.S_ISREG(lock_path.lstat().st_mode)
    assert stat.S_IMODE(lock_path.stat().st_mode) == 0o600


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


def test_commit_phase_hot_journal_with_changed_page_one_is_recovered(
    tmp_path: Path,
) -> None:
    workspace = make_empty_workspace(tmp_path)
    journal = Path(os.fspath(workspace) + "-journal")
    ready = tmp_path / "commit-ready"
    proceed = tmp_path / "commit-proceed"

    def database_page_geometry(path: Path) -> tuple[int, int]:
        with path.open("rb") as stream:
            header = stream.read(100)
        assert header[:16] == b"SQLite format 3\0"
        page_size = int.from_bytes(header[16:18], "big")
        if page_size == 1:
            page_size = 65536
        return page_size, int.from_bytes(header[28:32], "big")

    page_size, original_pages = database_page_geometry(workspace)
    original_size = workspace.stat().st_size
    assert original_size == page_size * original_pages
    child = (
        "import os, sqlite3, sys, time\n"
        "from pathlib import Path\n"
        "database, ready, proceed = map(Path, sys.argv[1:])\n"
        "connection = sqlite3.connect(database)\n"
        "connection.execute('PRAGMA journal_mode = DELETE')\n"
        "connection.execute('PRAGMA synchronous = FULL')\n"
        "connection.execute('PRAGMA cache_size = 1')\n"
        "connection.execute('PRAGMA cache_spill = ON')\n"
        "connection.execute('BEGIN IMMEDIATE')\n"
        "connection.execute("
        "'CREATE TABLE commit_phase_growth(payload BLOB NOT NULL)')\n"
        "connection.execute("
        "\"WITH RECURSIVE counter(value) AS (VALUES(1) UNION ALL "
        "SELECT value + 1 FROM counter WHERE value < 36000) "
        "INSERT INTO commit_phase_growth "
        "SELECT zeroblob(4000) FROM counter\")\n"
        "ready.write_bytes(b'ready')\n"
        "while not proceed.exists():\n"
        "    time.sleep(0.001)\n"
        "connection.commit()\n"
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            child,
            os.fspath(workspace),
            os.fspath(ready),
            os.fspath(proceed),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    killed_during_commit = False
    deadline = time.monotonic() + 45
    try:
        while not ready.exists() and time.monotonic() < deadline:
            if process.poll() is not None:
                break
            time.sleep(0.001)
        assert ready.is_file()
        assert process.poll() is None
        assert database_page_geometry(workspace)[1] == original_pages
        assert journal.is_file()
        proceed.write_bytes(b"proceed")

        while process.poll() is None and time.monotonic() < deadline:
            try:
                crash_pages = database_page_geometry(workspace)[1]
                with journal.open("rb") as stream:
                    journal_header = stream.read(28)
            except FileNotFoundError:
                continue
            if (
                crash_pages != original_pages
                and journal_header[:8]
                == bytes.fromhex("d9d505f920a163d7")
            ):
                process.kill()
                killed_during_commit = True
                break
        process.wait(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
    assert process.stdout is not None
    assert process.stderr is not None
    process.stdout.close()
    stderr = process.stderr.read().decode("utf-8", errors="replace")
    process.stderr.close()
    assert killed_during_commit, stderr
    assert process.returncode == -9

    crash_page_size, crash_pages = database_page_geometry(workspace)
    with journal.open("rb") as stream:
        journal_header = stream.read(28)
    journal_original_pages = int.from_bytes(journal_header[16:20], "big")
    assert crash_page_size == page_size
    assert crash_pages > original_pages
    assert journal_original_pages == original_pages
    assert journal.is_file()

    sqlite_control = tmp_path / "sqlite-control.sqlite3"
    sqlite_control_journal = Path(
        os.fspath(sqlite_control) + "-journal"
    )
    shutil.copyfile(workspace, sqlite_control)
    shutil.copyfile(journal, sqlite_control_journal)
    sqlite_control.chmod(0o600)
    sqlite_control_journal.chmod(0o600)
    with sqlite3.connect(sqlite_control) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == (
            "ok",
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE name = 'commit_phase_growth'"
        ).fetchone() == (0,)
    assert database_page_geometry(sqlite_control)[1] == original_pages
    assert not sqlite_control_journal.exists()

    snapshot = load_workspace(workspace)

    assert snapshot.job.state == "in_progress"
    assert snapshot.job.completed_count == 0
    assert snapshot.job.occurrence_count == 0
    assert snapshot.inventory == ()
    assert snapshot.occurrences == ()
    assert database_page_geometry(workspace)[1] == original_pages
    assert workspace.stat().st_size == original_size
    assert not journal.exists()
    with sqlite3.connect(workspace) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == (
            "ok",
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE name = 'commit_phase_growth'"
        ).fetchone() == (0,)


def test_published_tree_change_between_manifest_passes_blocks_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_source(tmp_path)
    output, workspace = paths(tmp_path)
    real_hash_output_file = engine._hash_output_file
    changed = False

    def change_report_while_next_yml_is_read(
        digest: object, relative: Path, path: Path
    ) -> object:
        nonlocal changed
        if (
            not changed
            and path.suffix == ".yml"
            and output in path.parents
        ):
            report = output / "translation-report.json"
            report.write_bytes(report.read_bytes() + b" ")
            changed = True
        return real_hash_output_file(digest, relative, path)

    monkeypatch.setattr(
        engine, "_hash_output_file", change_report_while_next_yml_is_read
    )
    with pytest.raises(
        SafetyError, match="finalization_output_tree_unstable"
    ):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=SyntheticClient,
        )

    assert changed is True
    snapshot = load_workspace(workspace)
    assert snapshot.job.state == "in_progress"
    assert snapshot.job.finalization_state == "intent"
    assert output.is_dir()


@pytest.mark.parametrize("parent_mode", [0o500, 0o555])
def test_lost_success_after_completion_commit_resumes_idempotently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    parent_mode: int,
) -> None:
    source = make_source(tmp_path)
    output, workspace = paths(tmp_path)
    real_complete = engine._complete_workspace

    def complete_then_lose_success(
        workspace_path: Path, *, output_identity: object
    ) -> None:
        real_complete(
            workspace_path,
            output_identity=output_identity,
        )
        raise SafetyError("synthetic_success_response_lost")

    monkeypatch.setattr(
        engine, "_complete_workspace", complete_then_lose_success
    )
    with pytest.raises(
        SafetyError, match="synthetic_success_response_lost"
    ):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=SyntheticClient,
        )
    monkeypatch.setattr(engine, "_complete_workspace", real_complete)

    committed = load_workspace(workspace)
    assert committed.job.state == "completed"
    run_count = committed.job.run_count
    workspace_hash = hashlib.sha256(workspace.read_bytes()).hexdigest()
    output_inode = output.stat().st_ino
    output_identity = engine._output_tree_identity(output)
    published_report = json.loads(
        (output / "translation-report.json").read_text()
    )
    sibling_inventory = tuple(
        sorted(
            (
                path.name,
                stat.S_IFMT(path.lstat().st_mode),
                path.lstat().st_ino,
            )
            for path in tmp_path.iterdir()
        )
    )
    factory_calls = 0

    def forbidden_client_factory() -> SyntheticClient:
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("completed_resume_created_model_client")

    tmp_path.chmod(parent_mode)
    try:
        report = translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=forbidden_client_factory,
        )
        sibling_inventory_after = tuple(
            sorted(
                (
                    path.name,
                    stat.S_IFMT(path.lstat().st_mode),
                    path.lstat().st_ino,
                )
                for path in tmp_path.iterdir()
            )
        )
        workspace_hash_after = hashlib.sha256(
            workspace.read_bytes()
        ).hexdigest()
        output_identity_after = engine._output_tree_identity(output)
    finally:
        tmp_path.chmod(0o700)

    assert report == published_report
    assert factory_calls == 0
    assert sibling_inventory_after == sibling_inventory
    assert not any(
        name.startswith(".candidate.recover-")
        for name, _, _ in sibling_inventory_after
    )
    assert output.stat().st_ino == output_inode
    assert output_identity_after == output_identity
    assert workspace_hash_after == workspace_hash
    assert hashlib.sha256(workspace.read_bytes()).hexdigest() == workspace_hash
    resumed = load_workspace(workspace)
    assert resumed.job.state == "completed"
    assert resumed.job.run_count == run_count


@pytest.mark.parametrize("tamper", ["missing", "changed"])
def test_completed_resume_rejects_missing_or_changed_output_read_only(
    tmp_path: Path,
    tamper: str,
) -> None:
    source = make_source(tmp_path)
    output, workspace = paths(tmp_path)
    translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        client_factory=SyntheticClient,
    )
    if tamper == "missing":
        shutil.rmtree(output)
        expected_error = "completed_workspace_output_missing"
    else:
        report = output / "translation-report.json"
        report.write_bytes(report.read_bytes() + b" ")
        expected_error = "finalization_output_identity_mismatch"
    workspace_hash = hashlib.sha256(workspace.read_bytes()).hexdigest()
    factory_calls = 0

    def forbidden_client_factory() -> SyntheticClient:
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("completed_resume_created_model_client")

    with pytest.raises(SafetyError, match=expected_error):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=forbidden_client_factory,
        )

    assert factory_calls == 0
    assert hashlib.sha256(workspace.read_bytes()).hexdigest() == workspace_hash
    assert load_workspace(workspace).job.state == "completed"


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
