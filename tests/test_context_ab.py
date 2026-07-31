from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

import pytest

from stellaris_mod_translator.context_ab import (
    ABReviewEntry,
    _baseline_is_exact_compatible,
    _is_protected_atom_mismatch,
    _legacy_skipped_file_count,
    build_context_ab_review_pack,
    run_context_ab_pilot,
)
from stellaris_mod_translator import engine, ollama, review, vanilla_retrieval
from stellaris_mod_translator.engine import SafetyError
from stellaris_mod_translator.engine import translate_mod
from stellaris_mod_translator.review_application import apply_review_decisions
from stellaris_mod_translator.vanilla_retrieval import (
    REFERENCE_STATUS,
    RetrievalBatch,
    RetrievalCandidate,
    RetrievalResult,
)


def _entries(marker: str = "SYNTHETIC_AB_PRIVATE_SENTINEL"):
    return tuple(
        ABReviewEntry(
            occurrence_identity_sha256=hashlib.sha256(
                f"occurrence-{index}".encode("ascii")
            ).hexdigest(),
            source=f"Source {index} {marker}",
            baseline=f"Baseline {index} {marker}",
            contextual=f"Contextual {index} {marker}",
            reviewed_reference=f"Reviewed {index} {marker}",
        )
        for index in range(3)
    )


def _build(tmp_path: Path, entries=None):
    output = tmp_path / "ab-pack"
    result = build_context_ab_review_pack(
        _entries() if entries is None else entries,
        output,
        context_binding_sha256="a" * 64,
        source_localisation_sha256="b" * 64,
        model_digest="sha256:synthetic",
    )
    return output, result


def test_pack_is_private_content_separated_and_stably_blinded(
    tmp_path: Path,
) -> None:
    marker = "SYNTHETIC_AB_PRIVATE_SENTINEL"
    output, result = _build(tmp_path)

    assert result["ab_entries"] == 3
    assert result["status"] == "AB_QUALITY_STATUS: HUMAN_REVIEW_REQUIRED"
    assert output.stat().st_mode & 0o777 == 0o700
    assert {path.name for path in output.iterdir()} == {
        "index.html",
        "blind-mapping.json",
        "pack-summary.json",
    }
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in output.iterdir())
    html = (output / "index.html").read_text()
    mapping_text = (output / "blind-mapping.json").read_text()
    summary_text = (output / "pack-summary.json").read_text()
    assert marker in html
    assert marker not in mapping_text
    assert marker not in summary_text
    assert "http://" not in html
    assert "https://" not in html
    assert "connect-src 'none'" in html
    mapping = json.loads(mapping_text)
    assert len(mapping["entries"]) == 3
    assert all(
        {item["variant_a"], item["variant_b"]}
        == {"baseline", "contextual"}
        for item in mapping["entries"]
    )

    second_parent = tmp_path / "second"
    second_parent.mkdir()
    second = second_parent / "ab-pack"
    build_context_ab_review_pack(
        _entries(),
        second,
        context_binding_sha256="a" * 64,
        source_localisation_sha256="b" * 64,
        model_digest="sha256:synthetic",
    )
    assert (second / "blind-mapping.json").read_bytes() == (
        output / "blind-mapping.json"
    ).read_bytes()


def test_pack_escapes_script_delimiters_and_has_matching_csp_hash(
    tmp_path: Path,
) -> None:
    marker = '</script><script>globalThis.PWNED=true</script>'
    output, _ = _build(tmp_path, _entries(marker))
    html = (output / "index.html").read_text()

    assert marker not in html
    assert "\\u003c/script>" in html
    scripts = re.findall(r"<script(?: [^>]*)?>(.*?)</script>", html, re.S)
    assert len(scripts) == 2
    csp_hash = re.search(r"script-src 'sha256-([^']+)'", html)
    assert csp_hash is not None
    import base64

    actual = base64.b64encode(
        hashlib.sha256(scripts[-1].encode("utf-8")).digest()
    ).decode("ascii")
    assert actual == csp_hash.group(1)


def test_prepublication_failure_removes_temp_and_publishes_nothing(
    tmp_path: Path,
) -> None:
    output = tmp_path / "ab-pack"

    def fail() -> None:
        raise SafetyError("synthetic_input_drift")

    with pytest.raises(SafetyError, match="synthetic_input_drift"):
        build_context_ab_review_pack(
            _entries(),
            output,
            context_binding_sha256="a" * 64,
            source_localisation_sha256="b" * 64,
            model_digest="sha256:synthetic",
            pre_publish_check=fail,
        )
    assert not output.exists()
    assert list(tmp_path.glob(".ab-pack.tmp-*")) == []


def test_no_clobber_and_entry_contracts(tmp_path: Path) -> None:
    output, _ = _build(tmp_path)
    before = {
        path.name: (path.read_bytes(), os.stat(path).st_mtime_ns)
        for path in output.iterdir()
    }
    with pytest.raises(SafetyError, match="ab_output_must_not_exist"):
        build_context_ab_review_pack(
            _entries(),
            output,
            context_binding_sha256="a" * 64,
            source_localisation_sha256="b" * 64,
            model_digest="sha256:synthetic",
        )
    after = {
        path.name: (path.read_bytes(), os.stat(path).st_mtime_ns)
        for path in output.iterdir()
    }
    assert after == before

    duplicate = (_entries()[0], _entries()[0])
    with pytest.raises(SafetyError, match="ab_occurrence_identity_duplicate"):
        build_context_ab_review_pack(
            duplicate,
            tmp_path / "duplicate",
            context_binding_sha256="a" * 64,
            source_localisation_sha256="b" * 64,
            model_digest="sha256:synthetic",
        )


class PilotClient:
    def __init__(self, digest: str = "d" * 64) -> None:
        self.digest = digest
        self.calls: list[tuple[str, str]] = []

    def exact_model(self, tag: str) -> dict[str, str]:
        return {"tag": tag, "digest": self.digest}

    def translate(self, *, tag: str, text: str) -> str:
        self.calls.append(("legacy", text))
        return "RU " + text

    def translate_with_context(
        self, *, tag: str, text: str, reference_text: str
    ) -> str:
        self.calls.append(("context", text))
        return "CTX " + text


def _pilot_inputs(tmp_path: Path, *, include_skipped: bool = False):
    source = tmp_path / "source"
    source_file = source / "localisation/english/demo_l_english.yml"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(
        b'l_english:\n first:0 "First"\n second:0 "Second"\n'
    )
    if include_skipped:
        (source_file.parent / "skipped_l_english.yml").write_bytes(
            b'l_english:\n malformed:0 "unterminated\n'
        )
    baseline = tmp_path / "baseline"
    translate_mod(
        source,
        baseline,
        "synthetic:1",
        workspace=tmp_path / "baseline.smt-workspace.sqlite3",
        client_factory=PilotClient,
    )
    report_path = baseline / "translation-report.json"
    report_pin = hashlib.sha256(report_path.read_bytes()).hexdigest()
    inputs = review._validated_review_inputs(
        source.resolve(), baseline.resolve(), None, report_pin
    )
    records = []
    entries = inputs.pack_data["entries"]
    assert isinstance(entries, list)
    for entry in entries:
        assert isinstance(entry, dict)
        records.append(
            {
                "occurrence_id": entry["id"],
                "decision": "accept",
                "note": "synthetic",
                "tags": [],
                "glossary_candidate": False,
                "source_span_sha256": entry["source_span_sha256"],
                "candidate_span_sha256": entry["candidate_span_sha256"],
            }
        )
    decisions = tmp_path / "decisions.json"
    decisions.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pack_fingerprint": inputs.pack_data["pack_fingerprint"],
                "decisions": records,
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n"
    )
    reviewed = tmp_path / "reviewed"
    apply_review_decisions(
        source,
        baseline,
        decisions,
        reviewed,
        candidate_report_sha256=report_pin,
    )
    application = reviewed / "review-application-report.json"
    application_pin = hashlib.sha256(application.read_bytes()).hexdigest()
    return source, baseline, report_pin, reviewed, application_pin


def _install_pilot_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    def retrieve(
        database: Path, queries: tuple[object, ...], **kwargs: object
    ) -> RetrievalBatch:
        return RetrievalBatch(
            results=(
                RetrievalResult(
                    status="exact_key_context",
                    candidates=(
                        RetrievalCandidate(
                            pair_id="private-process-local",
                            match_kind="exact_key",
                            path_family_match=True,
                            global_text_ambiguous=False,
                            reference_status=REFERENCE_STATUS,
                            editorially_approved=False,
                            auto_applied=False,
                            russian_model_text="Reference",
                        ),
                    ),
                    examined_references=1,
                ),
                RetrievalResult(
                    status="no_match", candidates=(), examined_references=0
                ),
            ),
            memory_schema=3,
            memory_game_version=str(kwargs["game_version"]),
            database_sha256=str(kwargs["database_sha256"]),
            logical_digest=str(kwargs["logical_digest"]),
            database_identity=None,  # type: ignore[arg-type]
            memory_identity=None,  # type: ignore[arg-type]
        )

    monkeypatch.setattr(
        vanilla_retrieval, "retrieve_exact_context_v1", retrieve
    )
    monkeypatch.setattr(
        vanilla_retrieval,
        "verify_retrieval_batch_identity",
        lambda database, batch: None,
    )


@pytest.mark.parametrize(
    ("digest", "baseline_reused", "expected_calls"),
    [
        ("d" * 64, True, ["context"]),
        ("e" * 64, False, ["legacy", "context"]),
    ],
)
def test_bounded_pilot_calls_only_eligible_and_reuses_or_rebuilds_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    digest: str,
    baseline_reused: bool,
    expected_calls: list[str],
) -> None:
    source, baseline, report_pin, reviewed, application_pin = _pilot_inputs(
        tmp_path
    )
    _install_pilot_retrieval(monkeypatch)
    client = PilotClient(digest)
    evaluation_root = tmp_path / "evaluations"
    evaluation_root.mkdir(mode=0o700)
    output = evaluation_root / "ab-pilot"
    memory_root = tmp_path / "memory"
    memory_root.mkdir(mode=0o700)
    database = memory_root / "memory.sqlite3"
    database.touch(mode=0o600)

    report = run_context_ab_pilot(
        source,
        database,
        baseline,
        report_pin,
        reviewed,
        application_pin,
        output,
        "synthetic:1",
        evaluation_root=evaluation_root,
        vanilla_memory_database_sha256="a" * 64,
        vanilla_memory_logical_digest="b" * 64,
        vanilla_memory_game_version="Synthetic v1",
        expected_entries=1,
        client_factory=lambda: client,
    )

    assert [item[0] for item in client.calls] == expected_calls
    assert report["queries_total"] == 2
    assert report["eligible_context"] == 1
    assert report["context_prompts"] == 1
    assert report["baseline_reused"] is baseline_reused
    assert report["ollama_calls"] == len(expected_calls)
    assert report["ab_entries"] == 1
    assert report["legacy_prompts_changed_outside_eligible"] == 0
    assert output.exists()


def test_pilot_output_is_contained_before_retrieval_or_model_calls(
    tmp_path: Path,
) -> None:
    source, baseline, report_pin, reviewed, application_pin = _pilot_inputs(
        tmp_path
    )
    memory_root = tmp_path / "memory"
    memory_root.mkdir(mode=0o700)
    database = memory_root / "memory.sqlite3"
    database.touch(mode=0o600)
    factory_calls = 0

    def forbidden_factory() -> PilotClient:
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("containment must precede model creation")

    with pytest.raises(SafetyError, match="ab_output_source_overlap"):
        run_context_ab_pilot(
            source,
            database,
            baseline,
            report_pin,
            reviewed,
            application_pin,
            source / "ab-pilot",
            "synthetic:1",
            evaluation_root=source,
            vanilla_memory_database_sha256="a" * 64,
            vanilla_memory_logical_digest="b" * 64,
            vanilla_memory_game_version="Synthetic v1",
            expected_entries=1,
            client_factory=forbidden_factory,
        )
    assert factory_calls == 0
    assert not (source / "ab-pilot").exists()


def test_legacy_skipped_source_file_is_valid_for_bounded_pilot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, baseline, report_pin, reviewed, application_pin = _pilot_inputs(
        tmp_path, include_skipped=True
    )
    _install_pilot_retrieval(monkeypatch)
    evaluation_root = tmp_path / "evaluations"
    evaluation_root.mkdir(mode=0o700)
    memory_root = tmp_path / "memory"
    memory_root.mkdir(mode=0o700)
    database = memory_root / "memory.sqlite3"
    database.touch(mode=0o600)

    report = run_context_ab_pilot(
        source,
        database,
        baseline,
        report_pin,
        reviewed,
        application_pin,
        evaluation_root / "ab-pilot",
        "synthetic:1",
        evaluation_root=evaluation_root,
        vanilla_memory_database_sha256="a" * 64,
        vanilla_memory_logical_digest="b" * 64,
        vanilla_memory_game_version="Synthetic v1",
        expected_entries=1,
        client_factory=PilotClient,
    )

    assert report["queries_total"] == 2
    assert report["ab_entries"] == 1


def test_legacy_skip_can_be_a_now_supported_file_absent_from_candidate(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    english = source / "localisation/english"
    english.mkdir(parents=True)
    (english / "first_l_english.yml").write_bytes(
        b'l_english:\n first:0 "First"\n'
    )
    (english / "second_l_english.yml").write_bytes(
        b'l_english:\n second:0 "Second"\n'
    )
    candidate = tmp_path / "candidate"
    russian = candidate / "localisation/russian"
    russian.mkdir(parents=True)
    (russian / "first_l_russian.yml").write_bytes(
        b'l_russian:\n first:0 "RU First"\n'
    )

    assert _legacy_skipped_file_count(
        engine._snapshot(source), engine._snapshot(candidate)
    ) == 1


def test_baseline_reuse_binds_exact_legacy_prompt_profile() -> None:
    identity = {"tag": "synthetic:1", "digest": "d" * 64}
    report = {
        "resumability": {
            "prompt_profile_hash": ollama.translation_prompt_profile_hash()
        }
    }
    assert _baseline_is_exact_compatible(
        report,
        historical_model=identity,
        current_identity=identity,
        requested_model="synthetic:1",
    )
    report["resumability"]["prompt_profile_hash"] = "f" * 64
    assert not _baseline_is_exact_compatible(
        report,
        historical_model=identity,
        current_identity=identity,
        requested_model="synthetic:1",
    )


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("protected token missing or duplicated", True),
        ("protected token order changed", True),
        ("foreign protected token", True),
        ("translation human text is empty", False),
        ("translation contains control characters", False),
        ("translation introduces protected syntax", False),
    ],
)
def test_protected_atom_mismatch_counter_is_narrow(
    message: str, expected: bool
) -> None:
    assert _is_protected_atom_mismatch(ValueError(message)) is expected
