from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3

import pytest

from stellaris_mod_translator import engine, ollama
from stellaris_mod_translator.engine import SafetyError, translate_mod
from stellaris_mod_translator.ollama import (
    OllamaResultError,
    OllamaSystemError,
)
from stellaris_mod_translator.workspace import load_workspace


SOURCE_BYTES = (
    b'l_english:\n'
    b' one:0 "One $NAME$"\n'
    b' unsupported:0 not-quoted\n'
    b' two:0 "Two"\n'
    b' three:0 "Three"\n'
)


class SyntheticClient:
    def __init__(
        self,
        *,
        digest: str = "sha256:synthetic",
        interrupt_on: int | None = None,
        system_error_on: int | None = None,
        result_error_on: int | None = None,
    ) -> None:
        self.digest = digest
        self.interrupt_on = interrupt_on
        self.system_error_on = system_error_on
        self.result_error_on = result_error_on
        self.calls: list[str] = []
        self.inventory_calls = 0

    def exact_model(self, tag: str) -> dict[str, str]:
        self.inventory_calls += 1
        return {"tag": tag, "digest": self.digest}

    def translate(self, *, tag: str, text: str) -> str:
        self.calls.append(text)
        call_number = len(self.calls)
        if call_number == self.interrupt_on:
            raise KeyboardInterrupt()
        if call_number == self.system_error_on:
            raise OllamaSystemError("synthetic transport failure")
        if call_number == self.result_error_on:
            raise OllamaResultError("synthetic malformed result")
        return "RU " + text


def make_source(
    root: Path,
    data: bytes = SOURCE_BYTES,
    *,
    name: str = "source",
) -> Path:
    source = root / name
    source_file = source / "localisation/english/demo_l_english.yml"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(data)
    return source


def workspace_paths(tmp_path: Path) -> tuple[Path, Path]:
    return (
        tmp_path / "candidate",
        tmp_path / "job.smt-workspace.sqlite3",
    )


def start_interrupted_workspace(
    tmp_path: Path,
    *,
    interrupt_on: int = 2,
) -> tuple[Path, Path, Path, SyntheticClient]:
    source = make_source(tmp_path)
    output, workspace = workspace_paths(tmp_path)
    client = SyntheticClient(interrupt_on=interrupt_on)
    with pytest.raises(KeyboardInterrupt):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: client,
        )
    return source, output, workspace, client


def read_states(workspace: Path) -> list[str]:
    with sqlite3.connect(workspace) as connection:
        return [
            row[0]
            for row in connection.execute(
                "SELECT state FROM occurrences ORDER BY sequence"
            )
        ]


def candidate_yml(candidate: Path) -> dict[str, bytes]:
    return {
        path.relative_to(candidate).as_posix(): path.read_bytes()
        for path in sorted(candidate.rglob("*.yml"))
    }


def test_uninterrupted_workspace_run_completes_and_publishes_once(
    tmp_path: Path,
) -> None:
    source = make_source(tmp_path)
    output, workspace = workspace_paths(tmp_path)
    client = SyntheticClient()

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        client_factory=lambda: client,
    )

    assert report["schema_version"] == 3
    assert report["counts"]["total_occurrences"] == 4
    assert report["counts"]["completed_occurrences"] == 4
    assert report["counts"]["translated_occurrences"] == 3
    assert report["counts"]["unchanged_accepted_occurrences"] == 0
    assert report["counts"]["fallback_occurrences"] == 1
    assert report["counts"]["unsupported_occurrences"] == 1
    assert report["counts"]["pending_occurrences"] == 0
    assert report["counts"]["reused_from_workspace_occurrences"] == 0
    assert report["counts"]["calls_in_final_run"] == 3
    assert report["counts"]["deferred_occurrences"] == 0
    assert (
        report["resumability"]["workspace_state_at_report_creation"]
        == "in_progress"
    )
    assert report["resumability"]["completion_attested_by_report"] is False
    assert report["resumability"]["run_count"] == 1
    assert client.inventory_calls == 2
    assert len(client.calls) == 3
    assert output.is_dir()
    assert workspace.stat().st_mode & 0o777 == 0o600
    assert load_workspace(workspace).job.state == "completed"
    assert not Path(str(workspace) + "-wal").exists()
    assert not Path(str(workspace) + "-shm").exists()
    assert not Path(str(workspace) + "-journal").exists()


def test_interruption_checkpoints_only_committed_occurrences_and_no_output(
    tmp_path: Path,
) -> None:
    source, output, workspace, client = start_interrupted_workspace(
        tmp_path, interrupt_on=3
    )

    assert source.is_dir()
    assert not output.exists()
    assert client.calls == [
        "One __SMT_TOKEN_0000__",
        "Two",
        "Three",
    ]
    assert read_states(workspace) == [
        "accepted_changed",
        "accepted_changed",
        "pending",
    ]
    snapshot = load_workspace(workspace)
    assert snapshot.job.completed_count == 2
    assert snapshot.job.state == "in_progress"
    assert not Path(str(workspace) + "-journal").exists()


def test_resume_reuses_committed_results_and_retries_only_uncommitted_call(
    tmp_path: Path,
) -> None:
    source, output, workspace, initial = start_interrupted_workspace(
        tmp_path, interrupt_on=2
    )
    resume_client = SyntheticClient()

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        resume=True,
        client_factory=lambda: resume_client,
    )

    assert initial.calls == ["One __SMT_TOKEN_0000__", "Two"]
    assert resume_client.calls == ["Two", "Three"]
    assert report["counts"]["reused_from_workspace_occurrences"] == 1
    assert report["counts"]["calls_in_final_run"] == 2
    assert report["resumability"]["run_count"] == 2
    assert read_states(workspace) == [
        "accepted_changed",
        "accepted_changed",
        "accepted_changed",
    ]


def test_keyboard_interrupt_and_systemic_failure_both_preserve_progress(
    tmp_path: Path,
) -> None:
    keyboard_root = tmp_path / "keyboard"
    system_root = tmp_path / "system"
    keyboard_root.mkdir()
    system_root.mkdir()
    _, keyboard_output, keyboard_workspace, _ = start_interrupted_workspace(
        keyboard_root, interrupt_on=3
    )

    source = make_source(system_root)
    system_output, system_workspace = workspace_paths(system_root)
    system_client = SyntheticClient(system_error_on=3)
    with pytest.raises(OllamaSystemError, match="transport"):
        translate_mod(
            source,
            system_output,
            "synthetic:1",
            workspace=system_workspace,
            client_factory=lambda: system_client,
        )

    assert not keyboard_output.exists()
    assert not system_output.exists()
    assert read_states(keyboard_workspace) == [
        "accepted_changed",
        "accepted_changed",
        "pending",
    ]
    assert read_states(system_workspace) == [
        "accepted_changed",
        "accepted_changed",
        "pending",
    ]


def test_systemic_provider_failure_stops_before_all_remaining_occurrences(
    tmp_path: Path,
) -> None:
    source = make_source(
        tmp_path,
        (
            b'l_english:\n'
            b' one:0 "One"\n'
            b' two:0 "Two"\n'
            b' three:0 "Three"\n'
            b' four:0 "Four"\n'
        ),
    )
    output, workspace = workspace_paths(tmp_path)
    client = SyntheticClient(system_error_on=2)

    with pytest.raises(OllamaSystemError, match="transport"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: client,
        )

    assert client.calls == ["One", "Two"]
    assert read_states(workspace) == [
        "accepted_changed",
        "pending",
        "pending",
        "pending",
    ]
    assert not output.exists()


def test_invalid_per_entry_result_is_one_fallback_and_later_calls_continue(
    tmp_path: Path,
) -> None:
    source = make_source(tmp_path)
    output, workspace = workspace_paths(tmp_path)
    client = SyntheticClient(result_error_on=2)

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        client_factory=lambda: client,
    )

    assert client.calls == ["One __SMT_TOKEN_0000__", "Two", "Three"]
    assert read_states(workspace) == [
        "accepted_changed",
        "model_fallback",
        "accepted_changed",
    ]
    assert report["counts"]["translated_occurrences"] == 2
    assert report["counts"]["fallback_occurrences"] == 2
    rendered = (
        output / "localisation/russian/demo_l_russian.yml"
    ).read_text()
    assert ' two:0 "Two"' in rendered
    assert ' three:0 "RU Three"' in rendered


def test_unsafe_per_entry_text_is_renderer_fallback_and_does_not_stop(
    tmp_path: Path,
) -> None:
    source = make_source(tmp_path)
    output, workspace = workspace_paths(tmp_path)

    class UnsafeTextClient(SyntheticClient):
        def translate(self, *, tag: str, text: str) -> str:
            self.calls.append(text)
            if len(self.calls) == 2:
                return "Unsafe $OTHER$"
            return "RU " + text

    client = UnsafeTextClient()
    report = translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        client_factory=lambda: client,
    )

    assert client.calls == ["One __SMT_TOKEN_0000__", "Two", "Three"]
    assert read_states(workspace) == [
        "accepted_changed",
        "model_fallback",
        "accepted_changed",
    ]
    assert report["counts"]["calls_in_final_run"] == 3
    assert report["counts"]["fallback_occurrences"] == 2


def test_workspace_and_single_pass_localisation_are_deterministically_equal(
    tmp_path: Path,
) -> None:
    source = make_source(
        tmp_path,
        b'l_english:\n one:0 "One $NAME$"\n two:0 "Two"\n',
    )
    single_output = tmp_path / "single"
    workspace_output = tmp_path / "workspace-candidate"
    workspace = tmp_path / "job.smt-workspace.sqlite3"

    single_report = translate_mod(
        source,
        single_output,
        "synthetic:1",
        client_factory=lambda: SyntheticClient(),
    )
    workspace_report = translate_mod(
        source,
        workspace_output,
        "synthetic:1",
        workspace=workspace,
        client_factory=lambda: SyntheticClient(),
    )

    assert candidate_yml(single_output) == candidate_yml(workspace_output)
    assert (
        single_report["hashes"]["output_localisation_sha256"]
        == workspace_report["hashes"]["output_localisation_sha256"]
    )


@pytest.mark.parametrize("drift", ["bytes", "inventory", "order"])
def test_source_bytes_inventory_and_order_drift_are_rejected_before_model_calls(
    tmp_path: Path,
    drift: str,
) -> None:
    source, output, workspace, _ = start_interrupted_workspace(tmp_path)
    source_file = source / "localisation/english/demo_l_english.yml"
    if drift == "bytes":
        source_file.write_bytes(SOURCE_BYTES.replace(b"Three", b"Changed"))
    elif drift == "inventory":
        (source_file.parent / "added_l_english.yml").write_bytes(
            b'l_english:\n added:0 "Added"\n'
        )
    else:
        source_file.write_bytes(
            SOURCE_BYTES.replace(
                b' two:0 "Two"\n three:0 "Three"\n',
                b' three:0 "Three"\n two:0 "Two"\n',
            )
        )
    constructed = False

    def forbidden_factory() -> SyntheticClient:
        nonlocal constructed
        constructed = True
        return SyntheticClient()

    with pytest.raises(SafetyError, match="workspace_.*drift"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=forbidden_factory,
        )

    assert constructed is False
    assert not output.exists()


def test_model_tag_and_digest_drift_are_rejected_before_translation(
    tmp_path: Path,
) -> None:
    source, output, workspace, _ = start_interrupted_workspace(tmp_path)
    tag_client = SyntheticClient()
    with pytest.raises(SafetyError, match="workspace_model_tag_drift"):
        translate_mod(
            source,
            output,
            "other:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: tag_client,
        )
    assert tag_client.inventory_calls == 0
    assert tag_client.calls == []

    digest_client = SyntheticClient(digest="sha256:drift")
    with pytest.raises(SafetyError, match="workspace_model_digest_drift"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: digest_client,
        )
    assert digest_client.inventory_calls == 1
    assert digest_client.calls == []


def test_output_path_and_saved_counter_drift_are_rejected(
    tmp_path: Path,
) -> None:
    source, output, workspace, _ = start_interrupted_workspace(tmp_path)
    alternate_output = tmp_path / "alternate-candidate"
    with pytest.raises(SafetyError, match="workspace_output_path_drift"):
        translate_mod(
            source,
            alternate_output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: SyntheticClient(),
        )

    with sqlite3.connect(workspace) as connection:
        connection.execute("UPDATE job SET completed_count = 0")
        connection.commit()
    with pytest.raises(SafetyError, match="workspace_counter_mismatch"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: SyntheticClient(),
        )


def test_parser_and_prompt_profile_drift_are_rejected_before_model_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, output, workspace, _ = start_interrupted_workspace(tmp_path)
    parser_client = SyntheticClient()
    monkeypatch.setattr(engine, "PARSER_ORDER_VERSION", "synthetic-drift")
    with pytest.raises(SafetyError, match="parser_order_version_drift"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: parser_client,
        )
    assert parser_client.inventory_calls == 0
    monkeypatch.setattr(
        engine, "PARSER_ORDER_VERSION", "mvp4-lossless-parser-order-v1"
    )

    prompt_client = SyntheticClient()
    monkeypatch.setattr(
        ollama, "TRANSLATION_PROMPT_PROFILE_VERSION", "synthetic-drift"
    )
    with pytest.raises(SafetyError, match="prompt_profile_hash_drift"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: prompt_client,
        )
    assert prompt_client.inventory_calls == 0


def test_failed_resume_preflight_does_not_change_source_or_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, output, workspace, _ = start_interrupted_workspace(tmp_path)
    source_file = source / "localisation/english/demo_l_english.yml"
    source_before = hashlib.sha256(source_file.read_bytes()).hexdigest()
    workspace_before = hashlib.sha256(workspace.read_bytes()).hexdigest()
    monkeypatch.setattr(
        ollama, "TRANSLATION_PROMPT_PROFILE_VERSION", "synthetic-drift"
    )

    with pytest.raises(SafetyError, match="prompt_profile_hash_drift"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: SyntheticClient(),
        )

    assert hashlib.sha256(source_file.read_bytes()).hexdigest() == source_before
    assert hashlib.sha256(workspace.read_bytes()).hexdigest() == workspace_before
    assert not output.exists()


def test_tampered_saved_translation_is_revalidated_and_rejected(
    tmp_path: Path,
) -> None:
    source, output, workspace, _ = start_interrupted_workspace(tmp_path)
    with sqlite3.connect(workspace) as connection:
        connection.execute(
            """
            UPDATE occurrences
            SET model_result = 'Broken __SMT_TOKEN_9999__'
            WHERE sequence = 0
            """
        )
        connection.commit()
    client = SyntheticClient()

    with pytest.raises(SafetyError, match="saved_translation_invalid"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: client,
        )

    assert client.inventory_calls == 0
    assert client.calls == []
    assert not output.exists()


def test_final_model_and_source_rechecks_prevent_publication(
    tmp_path: Path,
) -> None:
    model_root = tmp_path / "model"
    source_root = tmp_path / "source"
    model_root.mkdir()
    source_root.mkdir()

    model_source = make_source(model_root)
    model_output, model_workspace = workspace_paths(model_root)

    class FinalDigestDriftClient(SyntheticClient):
        def exact_model(self, tag: str) -> dict[str, str]:
            self.inventory_calls += 1
            digest = (
                "sha256:synthetic"
                if self.inventory_calls == 1
                else "sha256:drift"
            )
            return {"tag": tag, "digest": digest}

    model_client = FinalDigestDriftClient()
    with pytest.raises(SafetyError, match="model_identity_changed"):
        translate_mod(
            model_source,
            model_output,
            "synthetic:1",
            workspace=model_workspace,
            client_factory=lambda: model_client,
        )
    assert not model_output.exists()
    assert load_workspace(model_workspace).job.state == "in_progress"

    mutable_source = make_source(source_root)
    source_output, source_workspace = workspace_paths(source_root)
    mutable_file = (
        mutable_source / "localisation/english/demo_l_english.yml"
    )

    class FinalSourceDriftClient(SyntheticClient):
        def exact_model(self, tag: str) -> dict[str, str]:
            self.inventory_calls += 1
            if self.inventory_calls == 2:
                mutable_file.write_bytes(SOURCE_BYTES + b"# drift\n")
            return {"tag": tag, "digest": self.digest}

    source_client = FinalSourceDriftClient()
    with pytest.raises(SafetyError, match="source_generation_changed"):
        translate_mod(
            mutable_source,
            source_output,
            "synthetic:1",
            workspace=source_workspace,
            client_factory=lambda: source_client,
        )
    assert not source_output.exists()
    assert load_workspace(source_workspace).job.state == "in_progress"


@pytest.mark.parametrize("kind", ["corrupt", "unknown_schema", "fifo"])
def test_corrupt_unknown_schema_and_fifo_workspaces_are_rejected(
    tmp_path: Path,
    kind: str,
) -> None:
    source = make_source(tmp_path)
    output, workspace = workspace_paths(tmp_path)
    if kind == "corrupt":
        workspace.write_bytes(b"not sqlite")
        workspace.chmod(0o600)
    elif kind == "unknown_schema":
        with sqlite3.connect(workspace) as connection:
            connection.execute("CREATE TABLE foreign_data (value TEXT)")
            connection.execute("PRAGMA user_version = 999")
        workspace.chmod(0o600)
    else:
        os.mkfifo(workspace, 0o600)

    with pytest.raises(SafetyError, match="workspace"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: SyntheticClient(),
        )

    assert not output.exists()


def test_foreign_symlink_and_wrong_mode_workspaces_are_rejected(
    tmp_path: Path,
) -> None:
    original_root = tmp_path / "original"
    foreign_root = tmp_path / "foreign"
    original_root.mkdir()
    foreign_root.mkdir()
    _, _, workspace, _ = start_interrupted_workspace(original_root)
    foreign_source = make_source(foreign_root)
    foreign_output = foreign_root / "candidate"

    with pytest.raises(SafetyError, match="workspace_source_path_drift"):
        translate_mod(
            foreign_source,
            foreign_output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: SyntheticClient(),
        )

    symlink = tmp_path / "linked.smt-workspace.sqlite3"
    symlink.symlink_to(workspace)
    with pytest.raises(SafetyError, match="workspace_symlink"):
        translate_mod(
            original_root / "source",
            original_root / "candidate",
            "synthetic:1",
            workspace=symlink,
            resume=True,
            client_factory=lambda: SyntheticClient(),
        )

    workspace.chmod(0o644)
    with pytest.raises(SafetyError, match="0600"):
        translate_mod(
            original_root / "source",
            original_root / "candidate",
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: SyntheticClient(),
        )


def test_resume_and_first_run_workspace_existence_contracts(
    tmp_path: Path,
) -> None:
    source = make_source(tmp_path)
    output, workspace = workspace_paths(tmp_path)

    with pytest.raises(SafetyError, match="existing_workspace"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
        )

    workspace.write_bytes(b"already here")
    workspace.chmod(0o600)
    with pytest.raises(SafetyError, match="absent_workspace"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"dry_run": True}, "incompatible_with_dry_run"),
        (
            {"max_occurrences_per_file": 1},
            "incompatible_with_max_occurrences_per_file",
        ),
    ],
)
def test_workspace_mode_rejects_bounded_and_dry_run_options(
    tmp_path: Path,
    kwargs: dict[str, object],
    message: str,
) -> None:
    source = make_source(tmp_path)
    output, workspace = workspace_paths(tmp_path)

    with pytest.raises(SafetyError, match=message):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: SyntheticClient(),
            **kwargs,
        )

    assert not workspace.exists()
    assert not output.exists()


@pytest.mark.parametrize("relationship", ["source", "output"])
def test_workspace_source_and_output_overlap_are_rejected(
    tmp_path: Path,
    relationship: str,
) -> None:
    source = make_source(tmp_path)
    output = tmp_path / "candidate"
    workspace = (
        source / "job.smt-workspace.sqlite3"
        if relationship == "source"
        else output
    )

    with pytest.raises(SafetyError, match="overlap"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: SyntheticClient(),
        )


def test_existing_output_blocks_incomplete_resume_without_workspace_mutation(
    tmp_path: Path,
) -> None:
    source, output, workspace, _ = start_interrupted_workspace(tmp_path)
    output.mkdir()
    (output / "marker").write_bytes(b"existing")
    workspace_before = hashlib.sha256(workspace.read_bytes()).hexdigest()
    client = SyntheticClient()

    with pytest.raises(
        SafetyError, match="output_exists_without_finalization_intent"
    ):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=lambda: client,
        )

    assert (output / "marker").read_bytes() == b"existing"
    assert hashlib.sha256(workspace.read_bytes()).hexdigest() == workspace_before
    assert client.inventory_calls == 0


def test_publication_race_preserves_destination_and_keeps_workspace_in_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_source(tmp_path)
    output, workspace = workspace_paths(tmp_path)
    real_publish = engine.atomic_publish_directory_no_replace

    def race(source_path: Path, destination_path: Path) -> None:
        destination_path.mkdir()
        (destination_path / "marker").write_bytes(b"existing")
        real_publish(source_path, destination_path)

    monkeypatch.setattr(engine, "atomic_publish_directory_no_replace", race)
    with pytest.raises(SafetyError, match="output_appeared_before_publication"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: SyntheticClient(),
        )

    assert (output / "marker").read_bytes() == b"existing"
    snapshot = load_workspace(workspace)
    assert snapshot.job.state == "in_progress"
    assert snapshot.job.completed_count == snapshot.job.occurrence_count
    assert list(tmp_path.glob(".candidate.tmp-*")) == []


def test_completed_workspace_resume_is_idempotent_and_not_republished(
    tmp_path: Path,
) -> None:
    source = make_source(tmp_path)
    output, workspace = workspace_paths(tmp_path)
    translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        client_factory=lambda: SyntheticClient(),
    )
    client = SyntheticClient()
    output_inode = output.stat().st_ino
    workspace_before = hashlib.sha256(workspace.read_bytes()).hexdigest()
    run_count = load_workspace(workspace).job.run_count

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        resume=True,
        client_factory=lambda: client,
    )

    assert client.inventory_calls == 0
    assert client.calls == []
    assert output.stat().st_ino == output_inode
    assert hashlib.sha256(workspace.read_bytes()).hexdigest() == workspace_before
    assert load_workspace(workspace).job.run_count == run_count
    assert report == json.loads(
        (output / "translation-report.json").read_text()
    )
