from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import pytest

from stellaris_mod_translator import engine, review, review_application
from stellaris_mod_translator.engine import (
    SafetyError,
    _snapshot,
    _tree_hash,
    translate_mod,
)
from stellaris_mod_translator.ollama import OllamaResultError
from stellaris_mod_translator.parser import parse_localisation
from stellaris_mod_translator.review import _validated_review_inputs
from stellaris_mod_translator.review_application import apply_review_decisions


MODEL_TAG = "synthetic-full-apply:1"
MODEL_DIGEST = "b" * 64


class FullApplicationClient:
    def exact_model(self, tag: str) -> dict[str, str]:
        assert tag == MODEL_TAG
        return {"tag": tag, "digest": MODEL_DIGEST}

    def translate(self, *, tag: str, text: str) -> str:
        assert tag == MODEL_TAG
        if "FALLBACK_SENTINEL" in text:
            raise OllamaResultError("synthetic fallback")
        if "UNCHANGED_SENTINEL" in text:
            return text
        return "RU " + text


def make_full_application_inputs(
    tmp_path: Path,
    *,
    entry_count: int | None = None,
    include_replace: bool = False,
    leading_prefix_first: bool = False,
    generation_parser_order_version: str | None = None,
) -> tuple[Path, Path, str]:
    source = tmp_path / "source"
    first = source / "localisation/english/first_l_english.yml"
    first.parent.mkdir(parents=True)
    if entry_count is None:
        first_payload = (
            "\r\n".join(
                [
                    "l_english: # synthetic header",
                    ' changed:0 "CHANGE_SENTINEL $NAME$" # keep-changed',
                    ' unchanged:0 "UNCHANGED_SENTINEL" # keep-unchanged',
                    (
                        ' fallback:0 "FALLBACK_SENTINEL '
                        '§Yhighlight§!" # keep-fallback'
                    ),
                    (
                        ' leading:0 " LEADING_SENTINEL '
                        '$NAME$ tail" # keep-leading'
                    ),
                    (
                        ' trailing:0 "TRAILING_SENTINEL '
                        '$NAME$ tail " # keep-trailing'
                    ),
                    (
                        r' escape:7 "ESCAPE_SENTINEL \"quote\" and '
                        r'\\ path \n marker" # keep-escape'
                    ),
                    (
                        " unsupported:0 SYNTHETIC_UNSUPPORTED "
                        "# keep-unsupported"
                    ),
                    "# keep-final-comment",
                ]
            )
            + "\r\n"
        )
        prefix = (
            b"# leading comment\r\n\r\n" if leading_prefix_first else b""
        )
        first.write_bytes(
            b"\xef\xbb\xbf" + prefix + first_payload.encode("utf-8")
        )
        second = source / "localisation/english/second_l_english.yml"
        second.write_text(
            "\n".join(
                [
                    "l_english:",
                    ' second.edit:2 "SECOND_EDIT [Root.GetName]" # keep-edit',
                    ' second.reject:0 "SECOND_REJECT £energy£" # keep-reject',
                    "# keep-second-comment",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        skipped = source / "localisation/replace/skipped_l_english.yml"
        skipped.parent.mkdir(parents=True)
        skipped.write_text(
            'l_english:\n skipped:0 "SKIPPED_SOURCE_RESIDUE"\n',
            encoding="utf-8",
        )
    else:
        first.write_text(
            "\n".join(
                ["l_english:"]
                + [
                    f' scale.{index}:0 "Scale entry {index}"'
                    for index in range(entry_count)
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    if include_replace:
        replace_file = (
            source
            / "localisation/english/replace/decisions_l_english.yml"
        )
        replace_file.parent.mkdir(parents=True, exist_ok=True)
        replace_file.write_bytes(
            b"\xef\xbb\xbfl_english: # replace-header\r\n"
            b"# replace-comment\r\n"
            b"\r\n"
            b' replace.accept:1 "REPLACE_ACCEPT $NAME$"\r\n'
            b' replace.edit:2 "REPLACE_EDIT [Root.GetName] '
            b'\xc2\xa7Ggreen\xc2\xa7!"\r\n'
            b' replace.reject:0 "REPLACE_REJECT \xc2\xa3energy\xc2\xa3"\r\n'
        )
    candidate = tmp_path / "candidate"
    with pytest.MonkeyPatch.context() as generation:
        if generation_parser_order_version is not None:
            generation.setattr(
                engine,
                "PARSER_ORDER_VERSION",
                generation_parser_order_version,
            )
        translate_mod(
            source,
            candidate,
            MODEL_TAG,
            workspace=tmp_path / "translation.smt-workspace.sqlite3",
            client_factory=FullApplicationClient,
        )
    if entry_count is None:
        first_candidate = (
            candidate / "localisation/russian/first_l_russian.yml"
        )
        if first_candidate.exists():
            parsed = parse_localisation(first_candidate.read_bytes())
            by_line = {
                item.line_index + 1: item for item in parsed.entries
            }
            leading_line = 7 if leading_prefix_first else 5
            trailing_line = 8 if leading_prefix_first else 6
            leading = by_line[leading_line].value
            trailing = by_line[trailing_line].value
            assert leading.startswith(" ")
            assert trailing.endswith(" ")
            first_candidate.write_bytes(
                parsed.render(
                    {
                        by_line[leading_line].line_index: leading[1:],
                        by_line[trailing_line].line_index: trailing[:-1],
                    }
                )
            )
        report_path = candidate / "translation-report.json"
        report = json.loads(report_path.read_text())
        report["hashes"]["output_localisation_sha256"] = localisation_hash(
            candidate
        )
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    report = candidate / "translation-report.json"
    return source, candidate, hashlib.sha256(report.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("parser_order_version", "expected_candidate_files"),
    [
        ("mvp4-lossless-parser-order-v1", 1),
        ("mvp7a-leading-header-parser-order-v2", 2),
    ],
)
def test_full_application_replays_known_parser_order_generations(
    tmp_path: Path,
    parser_order_version: str,
    expected_candidate_files: int,
) -> None:
    source, candidate, pin = make_full_application_inputs(
        tmp_path,
        leading_prefix_first=True,
        generation_parser_order_version=parser_order_version,
    )
    payload = make_full_decisions(source, candidate, pin)
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)

    report = apply_review_decisions(
        source,
        candidate,
        decisions,
        tmp_path / "reviewed",
        candidate_report_sha256=pin,
    )

    assert report["status"] == "full_candidate_review_applied"
    assert len(list(candidate.rglob("*.yml"))) == expected_candidate_files


def make_full_decisions(
    source: Path,
    candidate: Path,
    pin: str,
    *,
    decisions: dict[tuple[str, int], str] | None = None,
    reverse: bool = False,
) -> dict[str, object]:
    inputs = _validated_review_inputs(
        source.resolve(),
        candidate.resolve(),
        None,
        pin,
    )
    entries = inputs.pack_data["entries"]
    assert isinstance(entries, list)
    requested = decisions or {}
    records: list[dict[str, object]] = []
    for entry in entries:
        assert isinstance(entry, dict)
        identity = (str(entry["path"]), int(entry["line"]))
        decision = requested.get(identity, "accept")
        record: dict[str, object] = {
            "occurrence_id": entry["id"],
            "decision": decision,
            "note": "synthetic full decision",
            "tags": [],
            "glossary_candidate": False,
            "source_span_sha256": entry["source_span_sha256"],
            "candidate_span_sha256": entry["candidate_span_sha256"],
        }
        if decision == "edit":
            atoms = entry["protected_atoms"]
            assert isinstance(atoms, list)
            record["edited_translation"] = (
                "Русская редактура "
                + " безопасный текст ".join(str(atom) for atom in atoms)
                + " завершена"
            )
        records.append(record)
    if reverse:
        records.reverse()
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


def test_application_rejects_ambiguous_mapping_before_decision_or_output_spans(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    candidate = tmp_path / "candidate"
    source.mkdir()
    candidate.mkdir()
    data = b'l_english:\n key:0 "Synthetic"\n'
    parsed = parse_localisation(data)
    source_files = [
        review.SourceFile(
            relative=Path(
                "localisation/english/CaseDir/one_l_english.yml"
            ),
            data=data,
            sha256=hashlib.sha256(data).hexdigest(),
            stat_identity=(1, 1, len(data), 1),
            parsed=parsed,
            error=None,
        ),
        review.SourceFile(
            relative=Path(
                "localisation/english/casedir/two_l_english.yml"
            ),
            data=data,
            sha256=hashlib.sha256(data).hexdigest(),
            stat_identity=(1, 2, len(data), 1),
            parsed=parsed,
            error=None,
        ),
    ]

    def snapshot(
        path: Path, **kwargs: object
    ) -> list[review.SourceFile]:
        return source_files if path == source.resolve() else []

    monkeypatch.setattr(review, "_snapshot", snapshot)
    report_path = candidate / "translation-report.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "resumability": {
                    "parser_order_version": (
                        "mvp7a-leading-header-parser-order-v2"
                    )
                },
            }
        )
        + "\n"
    )
    pin = hashlib.sha256(report_path.read_bytes()).hexdigest()
    decisions = tmp_path / "decisions.json"
    write_decisions(
        decisions,
        {
            "schema_version": 1,
            "pack_fingerprint": "0" * 64,
            "decisions": [
                {"decision": "accept"},
                {"decision": "reject"},
            ],
        },
    )
    output = tmp_path / "reviewed"
    with pytest.raises(SafetyError, match="candidate_path_collision"):
        apply_review_decisions(
            source,
            candidate,
            decisions,
            output,
            candidate_report_sha256=pin,
        )

    assert not output.exists()
    assert not list(tmp_path.glob(".reviewed.tmp-*"))


def entry_value(path: Path, line: int) -> str:
    parsed = parse_localisation(path.read_bytes())
    return next(
        item.value for item in parsed.entries if item.line_index + 1 == line
    )


def localisation_hash(root: Path) -> str:
    return _tree_hash(
        [(item.relative, item.data) for item in _snapshot(root)]
    )


def test_full_application_is_lossless_complete_and_order_independent(
    tmp_path: Path,
) -> None:
    source, candidate, pin = make_full_application_inputs(tmp_path)
    first_path = "localisation/english/first_l_english.yml"
    second_path = "localisation/english/second_l_english.yml"
    payload = make_full_decisions(
        source,
        candidate,
        pin,
        decisions={
            (first_path, 4): "edit",
            (first_path, 7): "edit",
            (second_path, 2): "edit",
            (second_path, 3): "reject",
        },
        reverse=True,
    )
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)
    output = tmp_path / "reviewed"
    source_before = localisation_hash(source)
    candidate_before = localisation_hash(candidate)
    decisions_before = decisions.read_bytes()
    first_candidate = (
        candidate / "localisation/russian/first_l_russian.yml"
    )
    second_candidate = (
        candidate / "localisation/russian/second_l_russian.yml"
    )

    report = apply_review_decisions(
        source,
        candidate,
        decisions,
        output,
        candidate_report_sha256=pin,
    )

    assert localisation_hash(source) == source_before
    assert localisation_hash(candidate) == candidate_before
    assert decisions.read_bytes() == decisions_before
    assert report["schema_version"] == 2
    assert report["status"] == "full_candidate_review_applied"
    assert report["review_scope"] == "full_candidate"
    assert report["review_pack_schema_version"] == 2
    assert report["candidate_report_schema_version"] == 3
    assert report["editorial_status"] == (
        "human_review_complete_for_reviewable_occurrences"
    )
    assert report["editorially_approved"] is False
    assert report["counts"] == {
        "total_decisions": 8,
        "accept": 4,
        "edit": 3,
        "reject": 1,
        "actually_changed_spans": 4,
        "restored_english_spans": 1,
    }
    assert report["technical_residue"] == {
        "unsupported_occurrences": 1,
        "skipped_files": 1,
    }
    assert report["base_candidate_status"] == "technical_safe_partial"
    assert report["base_candidate_counts"]["unsupported_occurrences"] == 1
    assert report["base_candidate_counts"]["skipped_files"] == 1
    assert report["review_summary"] == {
        "total": 9,
        "review_entries": 8,
        "accepted_changed": 6,
        "accepted_unchanged": 1,
        "model_fallback": 1,
        "unsupported": 1,
        "deferred": 0,
        "skipped_files": 1,
        "pending": 0,
        "whitespace_warning_entries": 2,
    }
    assert report["hashes"] == {
        "source_localisation_sha256": source_before,
        "base_candidate_localisation_sha256": candidate_before,
        "pinned_translation_report_sha256": pin,
        "decisions_file_sha256": hashlib.sha256(decisions_before).hexdigest(),
        "final_output_localisation_sha256": localisation_hash(output),
    }
    assert report["model"] == {"tag": MODEL_TAG, "digest": MODEL_DIGEST}
    assert report["source_mutations"] == 0
    assert report["candidate_mutations"] == 0
    assert report["ollama_calls"] == 0
    assert report["network_calls"] == 0
    assert json.loads(
        (output / "review-application-report.json").read_text()
    ) == report
    assert not (output / "translation-report.json").exists()

    first_output = output / "localisation/russian/first_l_russian.yml"
    second_output = output / "localisation/russian/second_l_russian.yml"
    first_source = source / first_path
    second_source = source / second_path
    assert first_output.read_bytes().startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in first_output.read_bytes()
    assert first_output.read_bytes().replace(b"\r\n", b"").find(b"\n") == -1
    assert not second_output.read_bytes().startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in second_output.read_bytes()
    assert entry_value(first_output, 2) == entry_value(first_candidate, 2)
    assert entry_value(first_output, 3) == entry_value(first_candidate, 3)
    assert entry_value(first_output, 4).startswith("Русская редактура")
    assert "§Y" in entry_value(first_output, 4)
    assert "§!" in entry_value(first_output, 4)
    assert entry_value(first_output, 7).startswith("Русская редактура")
    assert r"\"" in entry_value(first_output, 7)
    assert r"\\" in entry_value(first_output, 7)
    assert r"\n" in entry_value(first_output, 7)
    assert entry_value(second_output, 2).startswith("Русская редактура")
    assert "[Root.GetName]" in entry_value(second_output, 2)
    assert entry_value(second_output, 3) == entry_value(second_source, 3)
    assert entry_value(second_output, 3) != entry_value(second_candidate, 3)
    candidate_lines = first_candidate.read_bytes().splitlines(keepends=True)
    output_lines = first_output.read_bytes().splitlines(keepends=True)
    assert output_lines[7:] == candidate_lines[7:]
    assert b"# keep-final-comment" in first_output.read_bytes()
    assert b"# keep-second-comment" in second_output.read_bytes()
    assert b"# keep-reject" in second_output.read_bytes()
    assert first_source.read_bytes().startswith(b"\xef\xbb\xbf")
    assert not (
        output / "localisation/replace/skipped_l_english.yml"
    ).exists()


def test_full_application_preserves_qualified_replace_path_and_lossless_bytes(
    tmp_path: Path,
) -> None:
    source, candidate, pin = make_full_application_inputs(
        tmp_path,
        include_replace=True,
    )
    source_path = (
        "localisation/english/replace/decisions_l_english.yml"
    )
    candidate_path = (
        candidate
        / "localisation/russian/replace/decisions_l_russian.yml"
    )
    payload = make_full_decisions(
        source,
        candidate,
        pin,
        decisions={
            (source_path, 5): "edit",
            (source_path, 6): "reject",
        },
    )
    decisions = tmp_path / "replace-decisions.json"
    write_decisions(decisions, payload)
    output = tmp_path / "reviewed"
    source_before = localisation_hash(source)
    candidate_before = localisation_hash(candidate)

    report = apply_review_decisions(
        source,
        candidate,
        decisions,
        output,
        candidate_report_sha256=pin,
    )

    reviewed_path = (
        output
        / "localisation/russian/replace/decisions_l_russian.yml"
    )
    reviewed = reviewed_path.read_bytes()
    assert reviewed.startswith(
        b"\xef\xbb\xbfl_russian: # replace-header\r\n"
    )
    assert b"# replace-comment\r\n\r\n" in reviewed
    assert reviewed.replace(b"\r\n", b"").find(b"\n") == -1
    assert entry_value(reviewed_path, 4) == entry_value(candidate_path, 4)
    assert entry_value(reviewed_path, 5).startswith("Русская редактура")
    assert "[Root.GetName]" in entry_value(reviewed_path, 5)
    assert "§G" in entry_value(reviewed_path, 5)
    assert "§!" in entry_value(reviewed_path, 5)
    assert entry_value(reviewed_path, 6) == entry_value(
        source / source_path,
        6,
    )
    assert entry_value(reviewed_path, 6) != entry_value(candidate_path, 6)
    assert report["counts"]["accept"] >= 1
    assert report["counts"]["edit"] >= 1
    assert report["counts"]["reject"] >= 1
    assert report["technical_residue"]["skipped_files"] == 1
    assert localisation_hash(source) == source_before
    assert localisation_hash(candidate) == candidate_before


def test_full_reject_of_existing_english_is_not_reported_as_restored(
    tmp_path: Path,
) -> None:
    source, candidate, pin = make_full_application_inputs(tmp_path)
    payload = make_full_decisions(
        source,
        candidate,
        pin,
        decisions={
            (
                "localisation/english/first_l_english.yml",
                3,
            ): "reject",
        },
    )
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)

    report = apply_review_decisions(
        source,
        candidate,
        decisions,
        tmp_path / "reviewed",
        candidate_report_sha256=pin,
    )

    assert report["counts"]["reject"] == 1
    assert report["counts"]["restored_english_spans"] == 0


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("missing", "incomplete_decisions"),
        ("partial", "incomplete_decisions"),
        ("duplicate", "duplicate_decision_occurrence_id"),
        ("unknown", "unknown_decision_occurrence_id"),
        ("extra", "unknown_decision_occurrence_id"),
        ("unreviewed", "unreviewed_decision"),
        ("fingerprint", "decisions_fingerprint_mismatch"),
        ("source_span", "decision_span_identity_mismatch"),
        ("candidate_span", "decision_span_identity_mismatch"),
        ("unsafe_edit", "protected_syntax"),
    ],
)
def test_full_application_rejects_incomplete_or_unsafe_decisions_atomically(
    tmp_path: Path,
    mutation: str,
    error: str,
) -> None:
    source, candidate, pin = make_full_application_inputs(tmp_path)
    payload = make_full_decisions(source, candidate, pin)
    records = payload["decisions"]
    assert isinstance(records, list)
    if mutation == "missing":
        records.pop()
    elif mutation == "partial":
        del records[len(records) // 2 :]
    elif mutation == "duplicate":
        records.append(dict(records[0]))
    elif mutation in {"unknown", "extra"}:
        unknown = dict(records[0])
        unknown["occurrence_id"] = "f" * 64
        if mutation == "unknown":
            records[0] = unknown
        else:
            records.append(unknown)
    elif mutation == "unreviewed":
        records[0]["decision"] = "unreviewed"
    elif mutation == "fingerprint":
        payload["pack_fingerprint"] = "0" * 64
    elif mutation == "source_span":
        records[0]["source_span_sha256"] = "0" * 64
    elif mutation == "candidate_span":
        records[0]["candidate_span_sha256"] = "0" * 64
    else:
        records[1]["decision"] = "edit"
        records[1]["edited_translation"] = "Небезопасный $OTHER$"
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)
    output = tmp_path / "reviewed"

    with pytest.raises(SafetyError, match=error):
        apply_review_decisions(
            source,
            candidate,
            decisions,
            output,
            candidate_report_sha256=pin,
        )
    assert not output.exists()
    assert list(tmp_path.glob(".reviewed.tmp-*")) == []


@pytest.mark.parametrize(
    "target",
    ["source", "candidate", "report", "decisions", "wrong_pin"],
)
def test_tampered_full_inputs_and_wrong_pin_never_create_output(
    tmp_path: Path,
    target: str,
) -> None:
    source, candidate, pin = make_full_application_inputs(tmp_path)
    payload = make_full_decisions(source, candidate, pin)
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)
    if target == "source":
        path = source / "localisation/english/first_l_english.yml"
        path.write_bytes(path.read_bytes() + b"# tampered\r\n")
    elif target == "candidate":
        path = candidate / "localisation/russian/first_l_russian.yml"
        path.write_bytes(path.read_bytes() + b"# tampered\r\n")
    elif target == "report":
        path = candidate / "translation-report.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif target == "decisions":
        payload["pack_fingerprint"] = "0" * 64
        write_decisions(decisions, payload)
    else:
        pin = "0" * 64
    output = tmp_path / "reviewed"

    with pytest.raises(SafetyError):
        apply_review_decisions(
            source,
            candidate,
            decisions,
            output,
            candidate_report_sha256=pin,
        )
    assert not output.exists()


@pytest.mark.parametrize(
    "target",
    ["source", "candidate", "candidate_report", "decisions"],
)
def test_full_application_detects_input_drift_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    source, candidate, pin = make_full_application_inputs(tmp_path)
    payload = make_full_decisions(source, candidate, pin)
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)
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
    output = tmp_path / "reviewed"
    with pytest.raises(SafetyError, match="generation_changed"):
        apply_review_decisions(
            source,
            candidate,
            decisions,
            output,
            candidate_report_sha256=pin,
        )
    assert not output.exists()
    assert list(tmp_path.glob(".reviewed.tmp-*")) == []


def test_full_application_output_race_is_no_clobber_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, candidate, pin = make_full_application_inputs(tmp_path)
    payload = make_full_decisions(source, candidate, pin)
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)
    output = tmp_path / "reviewed"
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
            candidate_report_sha256=pin,
        )
    assert (output / "marker").read_text() == "preserve"
    assert list(tmp_path.glob(".reviewed.tmp-*")) == []


def test_full_application_scales_to_12871_entries_without_legacy_limit(
    tmp_path: Path,
) -> None:
    source, candidate, pin = make_full_application_inputs(
        tmp_path,
        entry_count=12871,
    )
    payload = make_full_decisions(
        source,
        candidate,
        pin,
        reverse=True,
    )
    decisions = tmp_path / "decisions.json"
    write_decisions(decisions, payload)

    report = apply_review_decisions(
        source,
        candidate,
        decisions,
        tmp_path / "reviewed",
        candidate_report_sha256=pin,
    )

    assert report["counts"]["total_decisions"] == 12871
    assert report["counts"]["accept"] == 12871
    assert report["status"] == "full_candidate_review_applied"


def test_full_application_never_constructs_ollama_or_opens_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, candidate, pin = make_full_application_inputs(tmp_path)
    payload = make_full_decisions(source, candidate, pin)
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
        candidate_report_sha256=pin,
    )
    assert report["ollama_calls"] == 0
    assert report["network_calls"] == 0


@pytest.mark.parametrize(
    "pin",
    ["", "A" * 64, "a" * 63, "g" * 64, "a" * 65],
)
def test_full_application_report_pin_shape_is_strict(
    tmp_path: Path,
    pin: str,
) -> None:
    with pytest.raises(SafetyError, match="invalid_candidate_report_sha256"):
        apply_review_decisions(
            tmp_path / "source",
            tmp_path / "candidate",
            tmp_path / "decisions.json",
            tmp_path / "reviewed",
            candidate_report_sha256=pin,
        )


def test_full_schema_requires_pin_and_legacy_schema_rejects_pin(
    tmp_path: Path,
) -> None:
    source, candidate, pin = make_full_application_inputs(tmp_path)
    decisions = tmp_path / "decisions.json"
    decisions.write_text("{}")
    with pytest.raises(SafetyError, match="candidate_report_sha256_required"):
        apply_review_decisions(source, candidate, decisions, tmp_path / "no-pin")

    legacy_source = tmp_path / "legacy-source"
    legacy_file = (
        legacy_source / "localisation/english/legacy_l_english.yml"
    )
    legacy_file.parent.mkdir(parents=True)
    legacy_file.write_text('l_english:\n legacy:0 "Legacy"\n')
    legacy_candidate = tmp_path / "legacy-candidate"
    translate_mod(
        legacy_source,
        legacy_candidate,
        MODEL_TAG,
        max_occurrences_per_file=1,
        client_factory=FullApplicationClient,
    )
    legacy_pin = hashlib.sha256(
        (legacy_candidate / "translation-report.json").read_bytes()
    ).hexdigest()
    with pytest.raises(
        SafetyError,
        match="candidate_report_pin_requires_schema_v3",
    ):
        apply_review_decisions(
            legacy_source,
            legacy_candidate,
            decisions,
            tmp_path / "legacy-output",
            candidate_report_sha256=legacy_pin,
        )
    assert pin != legacy_pin
