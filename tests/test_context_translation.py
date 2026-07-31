from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

import pytest

from stellaris_mod_translator import engine, ollama, vanilla_retrieval
from stellaris_mod_translator.engine import SafetyError, translate_mod
from stellaris_mod_translator.ollama import OllamaResultError
from stellaris_mod_translator.vanilla_retrieval import (
    REFERENCE_STATUS,
    TERMINAL_STATUSES,
    RetrievalBatch,
    RetrievalCandidate,
    RetrievalResult,
)
from stellaris_mod_translator.workspace import load_workspace


PINS = {
    "context_policy": "exact_context_v1",
    "vanilla_memory_database_sha256": "a" * 64,
    "vanilla_memory_logical_digest": "b" * 64,
    "vanilla_memory_game_version": "Synthetic v1",
}


class ContextClient:
    def __init__(
        self,
        *,
        interrupt_on: int | None = None,
        result_error: bool = False,
    ) -> None:
        self.interrupt_on = interrupt_on
        self.result_error = result_error
        self.calls: list[tuple[str, str, str | None]] = []
        self.inventory_calls = 0

    def exact_model(self, tag: str) -> dict[str, str]:
        self.inventory_calls += 1
        return {"tag": tag, "digest": "sha256:synthetic"}

    def translate(self, *, tag: str, text: str) -> str:
        return self._finish("legacy", text, None)

    def translate_with_context(
        self, *, tag: str, text: str, reference_text: str
    ) -> str:
        if self.result_error:
            self.calls.append(("context", text, reference_text))
            raise OllamaResultError("synthetic contextual result failure")
        return self._finish("context", text, reference_text)

    def _finish(
        self, mode: str, text: str, reference: str | None
    ) -> str:
        self.calls.append((mode, text, reference))
        if len(self.calls) == self.interrupt_on:
            raise KeyboardInterrupt()
        return "RU " + text


def _source(tmp_path: Path, count: int, *, token: bool = False) -> Path:
    root = tmp_path / "source"
    target = root / "localisation/english/demo_l_english.yml"
    target.parent.mkdir(parents=True)
    values = [f"Value {index}" for index in range(count)]
    if token and values:
        values[0] = "Value $NAME$"
    lines = ["l_english:"] + [
        f' key_{index}:0 "{value}"' for index, value in enumerate(values)
    ]
    target.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return root


def _context_kwargs(tmp_path: Path, **changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        **PINS,
        "vanilla_memory_database": tmp_path / "memory.sqlite3",
    }
    values.update(changes)
    return values


def _candidate(reference: str, *, match_kind: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        pair_id="process-local-pair",
        match_kind=match_kind,  # type: ignore[arg-type]
        path_family_match=True,
        global_text_ambiguous=False,
        reference_status=REFERENCE_STATUS,
        editorially_approved=False,
        auto_applied=False,
        russian_model_text=reference,
    )


def _install_retrieval(
    monkeypatch: pytest.MonkeyPatch,
    statuses: tuple[str, ...],
    *,
    references: dict[int, str] | None = None,
    before_return: object | None = None,
) -> tuple[list[object], list[object]]:
    references = references or {}
    retrieval_calls: list[object] = []
    verification_calls: list[object] = []

    def retrieve(
        database: Path,
        queries: tuple[object, ...],
        **kwargs: object,
    ) -> RetrievalBatch:
        retrieval_calls.append((database, queries, kwargs))
        if callable(before_return):
            before_return()
        results = []
        for sequence, status in enumerate(statuses):
            candidates = ()
            if status in {"exact_key_context", "exact_text_consensus"}:
                candidates = (
                    _candidate(
                        references.get(sequence, f"Reference {sequence}"),
                        match_kind=(
                            "exact_key"
                            if status == "exact_key_context"
                            else "exact_text"
                        ),
                    ),
                )
            results.append(
                RetrievalResult(
                    status=status,  # type: ignore[arg-type]
                    candidates=candidates,
                    examined_references=len(candidates),
                )
            )
        return RetrievalBatch(
            results=tuple(results),
            memory_schema=3,
            memory_game_version=str(kwargs["game_version"]),
            database_sha256=str(kwargs["database_sha256"]),
            logical_digest=str(kwargs["logical_digest"]),
            database_identity=None,  # type: ignore[arg-type]
            memory_identity=None,  # type: ignore[arg-type]
        )

    def verify(database: Path, batch: RetrievalBatch) -> None:
        verification_calls.append((database, batch))

    monkeypatch.setattr(
        vanilla_retrieval, "retrieve_exact_context_v1", retrieve
    )
    monkeypatch.setattr(
        vanilla_retrieval, "verify_retrieval_batch_identity", verify
    )
    return retrieval_calls, verification_calls


def _run(
    tmp_path: Path,
    source: Path,
    client: ContextClient,
    **changes: object,
) -> tuple[dict[str, object], Path, Path]:
    output = tmp_path / "candidate"
    workspace = tmp_path / "job.smt-workspace.sqlite3"
    report = translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        client_factory=lambda: client,
        **_context_kwargs(tmp_path, **changes),
    )
    return report, output, workspace


def test_contextual_run_uses_only_two_eligible_statuses_and_schema_v4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path, len(TERMINAL_STATUSES))
    retrieval_calls, verification_calls = _install_retrieval(
        monkeypatch, TERMINAL_STATUSES
    )
    client = ContextClient()

    report, output, workspace = _run(tmp_path, source, client)

    assert len(retrieval_calls) == 1
    assert verification_calls
    assert [item[0] for item in client.calls] == [
        "context",
        "context",
        "legacy",
        "legacy",
        "legacy",
        "legacy",
        "legacy",
        "legacy",
    ]
    assert report["schema_version"] == 4
    context = report["translation_context"]
    assert isinstance(context, dict)
    assert set(context) == {
        "enabled",
        "policy",
        "prompt_framing_version",
        "memory_schema",
        "game_version",
        "database_sha256",
        "logical_digest",
        "source_localisation_sha256",
        "context_binding_sha256",
        *TERMINAL_STATUSES,
        "context_prompt_count",
        "legacy_prompt_count",
        "reference_status",
        "editorially_approved",
        "auto_applied",
    }
    assert context["context_prompt_count"] == 2
    assert context["legacy_prompt_count"] == 6
    assert all(context[status] == 1 for status in TERMINAL_STATUSES)
    assert context["reference_status"] == REFERENCE_STATUS
    assert context["editorially_approved"] is False
    assert context["auto_applied"] is False
    assert load_workspace(workspace).job.prompt_profile_hash == report[
        "resumability"
    ]["prompt_profile_hash"]
    assert output.exists()


def test_context_reference_is_process_local_and_protected_tokens_survive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = "PRIVATE_REFERENCE_SENTINEL_20260731"
    source = _source(tmp_path, 1, token=True)
    _install_retrieval(
        monkeypatch,
        ("exact_key_context",),
        references={0: f"{marker} __SMT_TOKEN_0000__"},
    )
    client = ContextClient()

    report, output, workspace = _run(tmp_path, source, client)

    candidate = output / "localisation/russian/demo_l_russian.yml"
    assert b"$NAME$" in candidate.read_bytes()
    assert marker.encode("utf-8") not in workspace.read_bytes()
    assert marker not in json.dumps(report, ensure_ascii=False)
    assert marker.encode("utf-8") not in (
        output / "translation-report.json"
    ).read_bytes()


@pytest.mark.parametrize(
    "mask",
    [
        mask
        for mask in itertools.product((False, True), repeat=5)
        if any(mask) and not all(mask)
    ],
)
def test_context_arguments_are_all_or_none_before_reads(
    tmp_path: Path, mask: tuple[bool, ...]
) -> None:
    names = (
        "context_policy",
        "vanilla_memory_database",
        "vanilla_memory_database_sha256",
        "vanilla_memory_logical_digest",
        "vanilla_memory_game_version",
    )
    complete = _context_kwargs(tmp_path)
    partial = {
        name: complete[name] for name, included in zip(names, mask) if included
    }
    with pytest.raises(SafetyError, match="context_arguments_must_be_complete"):
        translate_mod(
            tmp_path / "source-does-not-exist",
            tmp_path / "output",
            "synthetic:1",
            **partial,
        )


def test_context_requires_workspace_before_source_read(tmp_path: Path) -> None:
    with pytest.raises(SafetyError, match="context_requires_workspace"):
        translate_mod(
            tmp_path / "source-does-not-exist",
            tmp_path / "output",
            "synthetic:1",
            **_context_kwargs(tmp_path),
        )


def test_retrieval_and_source_recheck_precede_client_and_workspace_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path, 1)
    output = tmp_path / "candidate"
    workspace = tmp_path / "job.smt-workspace.sqlite3"
    source_file = source / "localisation/english/demo_l_english.yml"

    def drift() -> None:
        assert not output.exists()
        assert not workspace.exists()
        source_file.write_bytes(
            source_file.read_bytes().replace(b"Value 0", b"Drifted")
        )

    _install_retrieval(
        monkeypatch, ("no_match",), before_return=drift
    )
    factory_calls = 0

    def factory() -> ContextClient:
        nonlocal factory_calls
        factory_calls += 1
        return ContextClient()

    with pytest.raises(SafetyError, match="source_generation_changed"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=factory,
            **_context_kwargs(tmp_path),
        )
    assert factory_calls == 0
    assert not output.exists()
    assert not workspace.exists()


def test_memory_pin_failure_precedes_client_workspace_and_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path, 1)
    output = tmp_path / "candidate"
    workspace = tmp_path / "job.smt-workspace.sqlite3"

    def reject(*args: object, **kwargs: object) -> object:
        raise SafetyError("memory_database_sha256_pin_mismatch")

    monkeypatch.setattr(
        vanilla_retrieval, "retrieve_exact_context_v1", reject
    )

    def forbidden_factory() -> ContextClient:
        raise AssertionError("memory pin failure must precede client")

    with pytest.raises(
        SafetyError, match="memory_database_sha256_pin_mismatch"
    ):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=forbidden_factory,
            **_context_kwargs(tmp_path),
        )
    assert not output.exists()
    assert not workspace.exists()
    assert not Path(str(workspace) + ".lock").exists()


def test_interruption_resume_reuses_binding_and_completed_resume_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path, 3)
    retrieval_calls, _ = _install_retrieval(
        monkeypatch,
        ("exact_key_context", "no_match", "exact_text_consensus"),
    )
    output = tmp_path / "candidate"
    workspace = tmp_path / "job.smt-workspace.sqlite3"
    interrupted = ContextClient(interrupt_on=2)
    with pytest.raises(KeyboardInterrupt):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: interrupted,
            **_context_kwargs(tmp_path),
        )
    first_binding = load_workspace(workspace).job.prompt_profile_hash

    resumed = ContextClient()
    report = translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        resume=True,
        client_factory=lambda: resumed,
        **_context_kwargs(tmp_path),
    )
    assert len(retrieval_calls) == 2
    assert report["resumability"]["prompt_profile_hash"] == first_binding
    assert len(resumed.calls) == 2
    before = {
        path.relative_to(output): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in output.rglob("*")
        if path.is_file()
    }

    def forbidden_factory() -> ContextClient:
        raise AssertionError("completed resume must not create a client")

    repeated = translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        resume=True,
        client_factory=forbidden_factory,
        **_context_kwargs(tmp_path),
    )
    after = {
        path.relative_to(output): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in output.rglob("*")
        if path.is_file()
    }
    assert repeated == report
    assert before == after


def test_context_configuration_change_on_resume_precedes_provider_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path, 2)
    _install_retrieval(monkeypatch, ("exact_key_context", "no_match"))
    output = tmp_path / "candidate"
    workspace = tmp_path / "job.smt-workspace.sqlite3"
    with pytest.raises(KeyboardInterrupt):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=lambda: ContextClient(interrupt_on=1),
            **_context_kwargs(tmp_path),
        )

    def forbidden_factory() -> ContextClient:
        raise AssertionError("drifted resume must not create a client")

    with pytest.raises(SafetyError, match="workspace_prompt_profile_hash_drift"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            resume=True,
            client_factory=forbidden_factory,
            **_context_kwargs(
                tmp_path, vanilla_memory_logical_digest="c" * 64
            ),
        )


def test_malformed_reference_is_rejected_before_provider_and_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path, 1, token=True)
    _install_retrieval(
        monkeypatch,
        ("exact_key_context",),
        references={0: "Reference missing protected placeholder"},
    )

    def forbidden_factory() -> ContextClient:
        raise AssertionError("malformed reference must precede client")

    with pytest.raises(SafetyError, match="context_reference_invalid"):
        translate_mod(
            source,
            tmp_path / "candidate",
            "synthetic:1",
            workspace=tmp_path / "job.smt-workspace.sqlite3",
            client_factory=forbidden_factory,
            **_context_kwargs(tmp_path),
        )
    assert not (tmp_path / "candidate").exists()
    assert not (tmp_path / "job.smt-workspace.sqlite3").exists()


def test_context_result_failure_is_one_call_with_legacy_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path, 1)
    _install_retrieval(monkeypatch, ("exact_key_context",))
    client = ContextClient(result_error=True)

    report, output, _ = _run(tmp_path, source, client)

    assert len(client.calls) == 1
    assert client.calls[0][0] == "context"
    assert report["counts"]["translated_occurrences"] == 0
    assert report["counts"]["fallback_occurrences"] == 1
    assert b"Value 0" in (
        output / "localisation/russian/demo_l_russian.yml"
    ).read_bytes()


def test_terminal_memory_drift_blocks_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path, 1)
    _install_retrieval(monkeypatch, ("exact_key_context",))
    verification_count = 0

    def drift_on_publication(
        database: Path, batch: RetrievalBatch
    ) -> None:
        nonlocal verification_count
        verification_count += 1
        if verification_count == 4:
            raise SafetyError("memory_changed_after_retrieval")

    monkeypatch.setattr(
        vanilla_retrieval,
        "verify_retrieval_batch_identity",
        drift_on_publication,
    )
    with pytest.raises(SafetyError, match="memory_changed_after_retrieval"):
        _run(tmp_path, source, ContextClient())
    assert verification_count == 4
    assert not (tmp_path / "candidate").exists()
    assert list(tmp_path.glob(".candidate.tmp-*")) == []


def test_context_binding_is_canonical_and_contains_no_reference_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = "CONTEXT_BINDING_PRIVATE_SENTINEL"
    source = _source(tmp_path, 1)
    _install_retrieval(
        monkeypatch,
        ("exact_text_consensus",),
        references={0: marker},
    )
    report, _, workspace = _run(tmp_path, source, ContextClient())
    context = report["translation_context"]
    assert isinstance(context, dict)
    assert len(context["context_binding_sha256"]) == 64
    assert marker.encode("utf-8") not in workspace.read_bytes()
    assert hashlib.sha256(marker.encode("utf-8")).hexdigest() != context[
        "context_binding_sha256"
    ]


def test_context_disabled_keeps_legacy_prompt_hash_report_and_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path, 1)

    def forbidden_retrieval(*args: object, **kwargs: object) -> object:
        raise AssertionError("default-off run must not retrieve memory")

    monkeypatch.setattr(
        vanilla_retrieval, "retrieve_exact_context_v1", forbidden_retrieval
    )
    output = tmp_path / "candidate"
    workspace = tmp_path / "job.smt-workspace.sqlite3"
    client = ContextClient()
    report = translate_mod(
        source,
        output,
        "synthetic:1",
        workspace=workspace,
        client_factory=lambda: client,
    )

    assert report["schema_version"] == 3
    assert "translation_context" not in report
    assert [item[0] for item in client.calls] == ["legacy"]
    assert report["resumability"]["prompt_profile_hash"] == (
        "3e991aa062c660ad2286befc47fb80d571ec6de9bde0ef52512ff9cadc3ee6da"
    )
    assert ollama.translation_prompt_profile_hash() == report[
        "resumability"
    ]["prompt_profile_hash"]
