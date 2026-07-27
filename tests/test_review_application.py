from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket

import pytest

from stellaris_mod_translator import review_application
from stellaris_mod_translator.engine import (
    SafetyError,
    _snapshot,
    _tree_hash,
    translate_mod,
)
from stellaris_mod_translator.ollama import OllamaError
from stellaris_mod_translator.parser import parse_localisation
from stellaris_mod_translator.review import (
    ReviewIdentity,
    _validated_review_inputs,
)
from stellaris_mod_translator.review_application import apply_review_decisions


class SyntheticReviewClient:
    def exact_model(self, tag: str) -> dict[str, str]:
        assert tag == "synthetic-apply:1"
        return {"tag": tag, "digest": "sha256:synthetic-apply"}

    def translate(self, *, tag: str, text: str) -> str:
        if "FALLBACK_SENTINEL" in text:
            raise OllamaError("synthetic fallback")
        if "UNCHANGED_SENTINEL" in text:
            return text
        return "RU " + text


def _source_lines(start: int, *, first: bool) -> list[str]:
    lines = ["l_english: # synthetic header"]
    for index in range(24):
        absolute = start + index
        key = "duplicate.key" if first and index < 2 else f"synthetic.{absolute}"
        if first and index == 0:
            value = "English zero $NAME$"
        elif first and index == 1:
            value = "English one [Root.GetName]"
        elif first and index == 2:
            value = "English two £energy£"
        elif index == 3:
            value = "FALLBACK_SENTINEL English §Yhighlight§!"
        elif first and index == 4:
            value = "UNCHANGED_SENTINEL English"
        elif first and index == 5:
            value = r'English \"quoted\" and \\ path \n marker'
        else:
            value = f"English synthetic {absolute}"
        lines.append(f'  {key}:{index % 3} "{value}" # keep-{absolute}')
    if first:
        lines.append("  unsupported.synthetic:0 UNSUPPORTED_RAW")
    lines.append("# trailing comment")
    return lines


def make_apply_inputs(
    tmp_path: Path,
) -> tuple[Path, Path, ReviewIdentity]:
    source = tmp_path / "source"
    first = source / "localisation/english/first_l_english.yml"
    second = source / "localisation/english/second_l_english.yml"
    first.parent.mkdir(parents=True)
    first.write_bytes(
        b"\xef\xbb\xbf"
        + ("\r\n".join(_source_lines(0, first=True)) + "\r\n").encode()
    )
    second.write_bytes(
        ("\n".join(_source_lines(24, first=False)) + "\n").encode()
    )
    candidate = tmp_path / "candidate"
    translate_mod(
        source,
        candidate,
        "synthetic-apply:1",
        max_occurrences_per_file=23,
        client_factory=SyntheticReviewClient,
    )
    report_bytes = (candidate / "translation-report.json").read_bytes()
    identity = ReviewIdentity(
        source_localisation_sha256=_tree_hash(
            [(item.relative, item.data) for item in _snapshot(source)]
        ),
        candidate_localisation_sha256=_tree_hash(
            [(item.relative, item.data) for item in _snapshot(candidate)]
        ),
        candidate_report_sha256=hashlib.sha256(report_bytes).hexdigest(),
        model_tag="synthetic-apply:1",
        model_digest="sha256:synthetic-apply",
        review_entries=46,
        accepted_changed=43,
        accepted_unchanged=1,
        model_fallback=2,
        parser_unsupported=1,
        deferred=2,
        skipped_files=0,
    )
    return source, candidate, identity


def make_decisions_payload(
    source: Path,
    candidate: Path,
    identity: ReviewIdentity,
    *,
    decisions: dict[int, str] | None = None,
) -> dict[str, object]:
    inputs = _validated_review_inputs(
        source.resolve(),
        candidate.resolve(),
        identity,
    )
    entries = inputs.pack_data["entries"]
    assert isinstance(entries, list)
    requested = decisions or {}
    records: list[dict[str, object]] = []
    for index, entry in enumerate(entries):
        assert isinstance(entry, dict)
        decision = requested.get(index, "accept")
        item: dict[str, object] = {
            "occurrence_id": entry["id"],
            "decision": decision,
            "note": "synthetic",
            "tags": [],
            "glossary_candidate": False,
            "source_span_sha256": entry["source_span_sha256"],
            "candidate_span_sha256": entry["candidate_span_sha256"],
        }
        if decision == "edit":
            atoms = entry["protected_atoms"]
            assert isinstance(atoms, list)
            item["edited_translation"] = (
                "Редактура 😀 "
                + " безопасный текст ".join(atoms)
                + " завершена"
            )
        records.append(item)
    return {
        "schema_version": 1,
        "pack_fingerprint": inputs.pack_data["pack_fingerprint"],
        "decisions": records,
    }


def write_decisions(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _entry_by_line(data: bytes, line: int) -> str:
    parsed = parse_localisation(data)
    return next(
        entry.value for entry in parsed.entries if entry.line_index + 1 == line
    )


def test_mixed_decisions_are_lossless_and_report_exact_identities(
    tmp_path: Path,
) -> None:
    source, candidate, identity = make_apply_inputs(tmp_path)
    payload = make_decisions_payload(
        source,
        candidate,
        identity,
        decisions={0: "accept", 1: "edit", 2: "reject"},
    )
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)
    (tmp_path / "index.html").write_text(
        '{"pack_fingerprint":"not-authority"}',
        encoding="utf-8",
    )
    output = tmp_path / "reviewed"
    source_before = _tree_hash(
        [(item.relative, item.data) for item in _snapshot(source)]
    )
    candidate_before = _tree_hash(
        [(item.relative, item.data) for item in _snapshot(candidate)]
    )
    decisions_before = decisions.read_bytes()

    report = apply_review_decisions(
        source,
        candidate,
        decisions,
        output,
        expected_identity=identity,
    )

    assert _tree_hash(
        [(item.relative, item.data) for item in _snapshot(source)]
    ) == source_before
    assert _tree_hash(
        [(item.relative, item.data) for item in _snapshot(candidate)]
    ) == candidate_before
    assert decisions.read_bytes() == decisions_before
    assert not (output / "translation-report.json").exists()
    assert set(path.name for path in output.iterdir()) == {
        "localisation",
        "review-application-report.json",
    }
    persisted = json.loads(
        (output / "review-application-report.json").read_text()
    )
    assert persisted == report
    assert report["status"] == "bounded_pilot_review_applied"
    assert report["editorial_status"] == (
        "human_review_complete_for_bounded_pilot"
    )
    assert report["editorially_approved"] is False
    assert report["counts"] == {
        "total_decisions": 46,
        "accept": 44,
        "edit": 1,
        "reject": 1,
        "actually_changed_spans": 2,
        "restored_english_spans": 1,
    }
    assert report["source_mutations"] == 0
    assert report["candidate_mutations"] == 0
    assert report["protected_atom_mismatches"] == 0
    assert report["model"] == {
        "tag": identity.model_tag,
        "digest": identity.model_digest,
    }
    assert report["hashes"]["source_localisation_sha256"] == source_before
    assert (
        report["hashes"]["base_candidate_localisation_sha256"]
        == candidate_before
    )
    assert report["hashes"]["decisions_file_sha256"] == hashlib.sha256(
        decisions_before
    ).hexdigest()
    assert report["hashes"]["final_output_localisation_sha256"] == _tree_hash(
        [(item.relative, item.data) for item in _snapshot(output)]
    )

    source_first = (
        source / "localisation/english/first_l_english.yml"
    ).read_bytes()
    candidate_first = (
        candidate / "localisation/russian/first_l_russian.yml"
    ).read_bytes()
    output_first = (
        output / "localisation/russian/first_l_russian.yml"
    ).read_bytes()
    assert output_first.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in output_first
    assert output_first.replace(b"\r\n", b"").find(b"\n") == -1
    assert _entry_by_line(output_first, 2) == _entry_by_line(candidate_first, 2)
    assert _entry_by_line(output_first, 3).startswith("Редактура 😀")
    assert "[Root.GetName]" in _entry_by_line(output_first, 3)
    assert _entry_by_line(output_first, 4) == _entry_by_line(source_first, 4)
    assert "£energy£" in _entry_by_line(output_first, 4)
    candidate_parsed = parse_localisation(candidate_first)
    output_parsed = parse_localisation(output_first)
    candidate_lines = candidate_first[3:].splitlines(keepends=True)
    output_lines = output_first[3:].splitlines(keepends=True)
    for line_index in (2, 3):
        candidate_entry = next(
            item
            for item in candidate_parsed.entries
            if item.line_index == line_index
        )
        output_entry = next(
            item
            for item in output_parsed.entries
            if item.line_index == line_index
        )
        assert (
            candidate_lines[line_index][: candidate_entry.value_start]
            == output_lines[line_index][: output_entry.value_start]
        )
        assert (
            candidate_lines[line_index][candidate_entry.value_end :]
            == output_lines[line_index][output_entry.value_end :]
        )
    assert output_first.splitlines(keepends=True)[24:] == (
        candidate_first.splitlines(keepends=True)[24:]
    )
    output_second = (
        output / "localisation/russian/second_l_russian.yml"
    ).read_bytes()
    assert not output_second.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in output_second


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("empty", "incomplete_decisions"),
        ("missing", "incomplete_decisions"),
        ("unreviewed", "unreviewed_decision"),
        ("duplicate", "duplicate_decision_occurrence_id"),
        ("unknown", "unknown_decision_occurrence_id"),
        ("fingerprint", "decisions_fingerprint_mismatch"),
        ("source_hash", "decision_span_identity_mismatch"),
        ("candidate_hash", "decision_span_identity_mismatch"),
    ],
)
def test_incomplete_or_identity_mismatched_decisions_fail_closed(
    tmp_path: Path,
    mutation: str,
    error: str,
) -> None:
    source, candidate, identity = make_apply_inputs(tmp_path)
    payload = make_decisions_payload(source, candidate, identity)
    records = payload["decisions"]
    assert isinstance(records, list)
    if mutation == "empty":
        records.clear()
    elif mutation == "missing":
        records.pop()
    elif mutation == "unreviewed":
        records[0]["decision"] = "unreviewed"
    elif mutation == "duplicate":
        records.append(dict(records[0]))
    elif mutation == "unknown":
        records[0]["occurrence_id"] = "0" * 64
    elif mutation == "fingerprint":
        payload["pack_fingerprint"] = "0" * 64
    elif mutation == "source_hash":
        records[0]["source_span_sha256"] = "0" * 64
    else:
        records[0]["candidate_span_sha256"] = "0" * 64
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)
    output = tmp_path / "reviewed"

    with pytest.raises(SafetyError, match=error):
        apply_review_decisions(
            source,
            candidate,
            decisions,
            output,
            expected_identity=identity,
        )
    assert not output.exists()


@pytest.mark.parametrize(
    "unsafe_edit",
    [
        "Новый $OTHER$",
        "Новый [Other.Scope]",
        "Новый £minerals£",
        "Новый §Rцвет§!",
        r"Новый \n escape",
    ],
)
def test_edit_cannot_introduce_new_atoms_or_escapes(
    tmp_path: Path,
    unsafe_edit: str,
) -> None:
    source, candidate, identity = make_apply_inputs(tmp_path)
    payload = make_decisions_payload(
        source,
        candidate,
        identity,
        decisions={6: "edit"},
    )
    payload["decisions"][6]["edited_translation"] = unsafe_edit
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)

    with pytest.raises(SafetyError, match="protected_syntax"):
        apply_review_decisions(
            source,
            candidate,
            decisions,
            tmp_path / "reviewed",
            expected_identity=identity,
        )


@pytest.mark.parametrize("unsafe_edit", ["line\nbreak", "\u0001control", "\ud800"])
def test_edit_rejects_controls_and_non_scalar_text(
    tmp_path: Path,
    unsafe_edit: str,
) -> None:
    source, candidate, identity = make_apply_inputs(tmp_path)
    payload = make_decisions_payload(
        source,
        candidate,
        identity,
        decisions={6: "edit"},
    )
    payload["decisions"][6]["edited_translation"] = unsafe_edit
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)

    with pytest.raises(SafetyError, match="edited_translation"):
        apply_review_decisions(
            source,
            candidate,
            decisions,
            tmp_path / "reviewed",
            expected_identity=identity,
        )


@pytest.mark.parametrize(
    "target",
    ["source", "candidate", "candidate_report", "decisions"],
)
def test_input_generation_drift_prevents_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    source, candidate, identity = make_apply_inputs(tmp_path)
    payload = make_decisions_payload(source, candidate, identity)
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)
    output = tmp_path / "reviewed"
    real_render = review_application._render_output_files

    def drift(*args: object, **kwargs: object) -> list[tuple[Path, bytes]]:
        rendered = real_render(*args, **kwargs)
        if target == "source":
            path = source / "localisation/english/first_l_english.yml"
        elif target == "candidate":
            path = candidate / "localisation/russian/first_l_russian.yml"
        elif target == "candidate_report":
            path = candidate / "translation-report.json"
        else:
            path = decisions
        path.write_bytes(path.read_bytes() + b" ")
        return rendered

    monkeypatch.setattr(review_application, "_render_output_files", drift)
    with pytest.raises(SafetyError, match="generation_changed"):
        apply_review_decisions(
            source,
            candidate,
            decisions,
            output,
            expected_identity=identity,
        )
    assert not output.exists()
    assert list(tmp_path.glob(".reviewed.tmp-*")) == []


def test_symlink_and_fifo_decisions_fail_quickly(
    tmp_path: Path,
) -> None:
    source, candidate, identity = make_apply_inputs(tmp_path)
    payload = make_decisions_payload(source, candidate, identity)
    real_decisions = tmp_path / "real-decisions.json"
    write_decisions(real_decisions, payload)
    symlink = tmp_path / "symlink-decisions.json"
    symlink.symlink_to(real_decisions)
    fifo = tmp_path / "decisions.fifo"
    os.mkfifo(fifo)

    with pytest.raises(SafetyError, match="decisions_symlink"):
        apply_review_decisions(
            source,
            candidate,
            symlink,
            tmp_path / "symlink-output",
            expected_identity=identity,
        )
    with pytest.raises(SafetyError, match="decisions_not_regular_file"):
        apply_review_decisions(
            source,
            candidate,
            fifo,
            tmp_path / "fifo-output",
            expected_identity=identity,
        )


@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema_version":1,"schema_version":1}',
        b'{"schema_version":NaN}',
        b'{"schema_version":1e999}',
        b'{"schema_version":1} trailing',
        b"\xff",
    ],
)
def test_decisions_json_is_strict(
    tmp_path: Path,
    raw: bytes,
) -> None:
    source, candidate, identity = make_apply_inputs(tmp_path)
    decisions = tmp_path / "decisions.json"
    decisions.write_bytes(raw)
    error = "duplicate_decisions_field" if raw.count(b"schema_version") == 2 else (
        "invalid_decisions_json"
    )
    with pytest.raises(SafetyError, match=error):
        apply_review_decisions(
            source,
            candidate,
            decisions,
            tmp_path / "reviewed",
            expected_identity=identity,
        )


def test_decisions_size_is_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, candidate, identity = make_apply_inputs(tmp_path)
    payload = make_decisions_payload(source, candidate, identity)
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)
    monkeypatch.setattr(review_application, "MAX_DECISIONS_BYTES", 8)

    with pytest.raises(SafetyError, match="decisions_too_large"):
        apply_review_decisions(
            source,
            candidate,
            decisions,
            tmp_path / "reviewed",
            expected_identity=identity,
        )


def test_existing_output_and_publication_race_do_not_clobber(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, candidate, identity = make_apply_inputs(tmp_path)
    payload = make_decisions_payload(source, candidate, identity)
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)
    existing = tmp_path / "existing"
    existing.mkdir()
    marker = existing / "marker"
    marker.write_text("preserve")
    with pytest.raises(SafetyError, match="output_must_not_exist"):
        apply_review_decisions(
            source,
            candidate,
            decisions,
            existing,
            expected_identity=identity,
        )
    assert marker.read_text() == "preserve"

    output = tmp_path / "raced"
    real_publish = review_application.atomic_publish_directory_no_replace

    def race(source_path: Path, destination: Path) -> None:
        destination.mkdir()
        (destination / "marker").write_text("preserve")
        real_publish(source_path, destination)

    monkeypatch.setattr(
        review_application,
        "atomic_publish_directory_no_replace",
        race,
    )
    with pytest.raises(SafetyError, match="output_appeared_before_publication"):
        apply_review_decisions(
            source,
            candidate,
            decisions,
            output,
            expected_identity=identity,
        )
    assert (output / "marker").read_text() == "preserve"
    assert list(tmp_path.glob(".raced.tmp-*")) == []


def test_write_failure_cleans_temporary_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, candidate, identity = make_apply_inputs(tmp_path)
    payload = make_decisions_payload(source, candidate, identity)
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)
    output = tmp_path / "reviewed"
    real_write = review_application._write_new

    def fail_report(path: Path, data: bytes) -> None:
        if path.name == "review-application-report.json":
            raise OSError("synthetic write failure")
        real_write(path, data)

    monkeypatch.setattr(review_application, "_write_new", fail_report)
    with pytest.raises(OSError, match="synthetic write failure"):
        apply_review_decisions(
            source,
            candidate,
            decisions,
            output,
            expected_identity=identity,
        )
    assert not output.exists()
    assert list(tmp_path.glob(".reviewed.tmp-*")) == []


def test_application_never_constructs_ollama_or_opens_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, candidate, identity = make_apply_inputs(tmp_path)
    payload = make_decisions_payload(source, candidate, identity)
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("network or Ollama access is forbidden")

    monkeypatch.setattr(
        "stellaris_mod_translator.ollama.OllamaClient.__init__",
        forbidden,
    )
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    report = apply_review_decisions(
        source,
        candidate,
        decisions,
        tmp_path / "reviewed",
        expected_identity=identity,
    )
    assert report["ollama_calls"] == 0
    assert report["network_calls"] == 0
