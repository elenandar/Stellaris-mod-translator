"""Build a local, immutable editorial review pack from a translation candidate."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unicodedata
from typing import Iterable

from .engine import (
    SafetyError,
    SourceFile,
    _candidate_relative,
    _snapshot,
    _tree_hash,
    _verify_snapshot,
    _write_new,
)
from .parser import Entry
from .publication import (
    AtomicPublicationUnavailable,
    DestinationExistsError,
    atomic_publish_directory_no_replace,
)


REVIEW_PACK_SCHEMA_VERSION = 1
DECISIONS_SCHEMA_VERSION = 1
DECISIONS = frozenset({"unreviewed", "accept", "edit", "reject"})
TAGS = frozenset(
    {
        "terminology",
        "lore",
        "meaning",
        "style",
        "grammar",
        "leftover_english",
    }
)
STATUSES = frozenset(
    {"accepted_changed", "accepted_unchanged", "model_fallback"}
)


@dataclass(frozen=True)
class ReviewIdentity:
    source_localisation_sha256: str
    candidate_localisation_sha256: str
    candidate_report_sha256: str
    model_tag: str
    model_digest: str
    review_entries: int
    accepted_changed: int
    accepted_unchanged: int
    model_fallback: int
    parser_unsupported: int
    deferred: int
    skipped_files: int


MVP2_PILOT_IDENTITY = ReviewIdentity(
    source_localisation_sha256=(
        "4f7da212e280f7f28c218614ceb29a3ec9c385430c41675f28ba86124999693b"
    ),
    candidate_localisation_sha256=(
        "92eff41846107a2ed28df6085976847aacc0708f5c92980c370056b4d575d642"
    ),
    candidate_report_sha256=(
        "e86fadbb81f7899d033f92c05680f84641a50ba131137cbc1ff744ac1084a293"
    ),
    model_tag="glm-4.7-flash:latest",
    model_digest=(
        "4475827791a269b02c8ec49b1c3bc1abb5846bacf3fae015b75d33986322d8f6"
    ),
    review_entries=46,
    accepted_changed=41,
    accepted_unchanged=1,
    model_fallback=4,
    parser_unsupported=11,
    deferred=1632,
    skipped_files=1,
)


@dataclass(frozen=True)
class StableFile:
    path: Path
    data: bytes
    sha256: str
    stat_identity: tuple[int, int, int, int]


def build_review_pack(
    source_mod: Path,
    candidate: Path,
    output: Path,
    *,
    expected_identity: ReviewIdentity = MVP2_PILOT_IDENTITY,
) -> dict[str, object]:
    """Validate exact immutable inputs and publish a new autonomous review pack."""
    source = _validated_input_root(source_mod, "source")
    candidate_root = _validated_input_root(candidate, "candidate")
    if _paths_overlap(source, candidate_root):
        raise SafetyError("source_candidate_overlap")
    output_abs = _validated_review_output(source, candidate_root, output)

    source_files = _snapshot(source)
    candidate_files = _snapshot(candidate_root)
    report_file = _read_stable_file(
        candidate_root / "translation-report.json", "candidate_report"
    )
    inventory = _candidate_inventory(candidate_root)
    report = _load_report(report_file.data)

    source_hash = _tree_hash(
        [(item.relative, item.data) for item in source_files]
    )
    candidate_hash = _tree_hash(
        [(item.relative, item.data) for item in candidate_files]
    )
    _require_identity(
        source_hash,
        expected_identity.source_localisation_sha256,
        "source_localisation_identity_mismatch",
    )
    _require_identity(
        candidate_hash,
        expected_identity.candidate_localisation_sha256,
        "candidate_localisation_identity_mismatch",
    )
    _require_identity(
        report_file.sha256,
        expected_identity.candidate_report_sha256,
        "candidate_report_identity_mismatch",
    )

    entries, summary = _validated_review_entries(
        source,
        candidate_root,
        source_files,
        candidate_files,
        inventory,
        report,
        source_hash,
        candidate_hash,
        report_file.sha256,
        expected_identity,
    )
    pack_fingerprint = _sha256_json(
        {
            "schema_version": REVIEW_PACK_SCHEMA_VERSION,
            "source_localisation_sha256": source_hash,
            "candidate_localisation_sha256": candidate_hash,
            "candidate_report_sha256": report_file.sha256,
            "model": {
                "tag": expected_identity.model_tag,
                "digest": expected_identity.model_digest,
            },
            "occurrence_ids": [entry["id"] for entry in entries],
        }
    )
    pack_data = {
        "schema_version": REVIEW_PACK_SCHEMA_VERSION,
        "pack_fingerprint": pack_fingerprint,
        "summary": summary,
        "entries": entries,
    }
    html = _render_review_html(pack_data)
    pack_summary = {
        "schema_version": REVIEW_PACK_SCHEMA_VERSION,
        "pack_fingerprint": pack_fingerprint,
        "counts": summary,
        "identities": {
            "source_localisation_sha256": source_hash,
            "candidate_localisation_sha256": candidate_hash,
            "candidate_report_sha256": report_file.sha256,
        },
        "network_dependencies": 0,
    }

    temp = Path(
        tempfile.mkdtemp(
            prefix=f".{output_abs.name}.tmp-", dir=output_abs.parent
        )
    )
    try:
        _write_new(temp / "index.html", html)
        _write_new(
            temp / "review-pack-summary.json",
            (
                json.dumps(
                    pack_summary,
                    ensure_ascii=True,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            ).encode("ascii"),
        )
        _verify_snapshot(source, source_files)
        _verify_snapshot(candidate_root, candidate_files)
        _verify_stable_file(report_file, "candidate_report_generation_changed")
        if _candidate_inventory(candidate_root) != inventory:
            raise SafetyError("candidate_generation_changed")
        try:
            atomic_publish_directory_no_replace(temp, output_abs)
        except DestinationExistsError as exc:
            raise SafetyError("output_appeared_before_publication") from exc
        except AtomicPublicationUnavailable as exc:
            raise SafetyError("atomic_no_replace_unavailable") from exc
    except BaseException:
        if temp.exists():
            shutil.rmtree(temp)
        raise

    return {
        "status": "review_pack_created",
        "output": str(output_abs),
        "pack_fingerprint": pack_fingerprint,
        "counts": summary,
        "identities": pack_summary["identities"],
        "network_dependencies": 0,
    }


def validate_decisions_payload(
    payload: object, pack_data: dict[str, object]
) -> dict[str, dict[str, object]]:
    """Validate the strict decisions contract also enforced by the local UI."""
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "pack_fingerprint",
        "decisions",
    }:
        raise SafetyError("invalid_decisions_document_fields")
    if payload["schema_version"] != DECISIONS_SCHEMA_VERSION:
        raise SafetyError("invalid_decisions_schema_version")
    if payload["pack_fingerprint"] != pack_data.get("pack_fingerprint"):
        raise SafetyError("decisions_fingerprint_mismatch")
    raw_entries = pack_data.get("entries")
    if not isinstance(raw_entries, list):
        raise SafetyError("invalid_pack_entries")
    known = {
        entry["id"]: entry
        for entry in raw_entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    decisions = payload["decisions"]
    if not isinstance(decisions, list):
        raise SafetyError("invalid_decisions_array")
    normalized: dict[str, dict[str, object]] = {}
    base_fields = {
        "occurrence_id",
        "decision",
        "note",
        "tags",
        "glossary_candidate",
        "source_span_sha256",
        "candidate_span_sha256",
    }
    for item in decisions:
        if not isinstance(item, dict):
            raise SafetyError("invalid_decision_record")
        occurrence_id = item.get("occurrence_id")
        if not isinstance(occurrence_id, str):
            raise SafetyError("invalid_decision_occurrence_id")
        if occurrence_id in normalized:
            raise SafetyError("duplicate_decision_occurrence_id")
        if occurrence_id not in known:
            raise SafetyError("unknown_decision_occurrence_id")
        record = known[occurrence_id]
        decision = item.get("decision")
        expected_fields = (
            base_fields | {"edited_translation"}
            if decision == "edit"
            else base_fields
        )
        if set(item) != expected_fields:
            raise SafetyError("invalid_decision_record_fields")
        if not isinstance(decision, str) or decision not in DECISIONS:
            raise SafetyError("invalid_decision_enum")
        if not isinstance(item["note"], str):
            raise SafetyError("invalid_decision_note")
        tags = item["tags"]
        if (
            not isinstance(tags, list)
            or any(not isinstance(tag, str) for tag in tags)
            or len(tags) != len(set(tags))
            or any(tag not in TAGS for tag in tags)
        ):
            raise SafetyError("invalid_decision_tags")
        if not isinstance(item["glossary_candidate"], bool):
            raise SafetyError("invalid_glossary_candidate")
        if (
            item["source_span_sha256"] != record["source_span_sha256"]
            or item["candidate_span_sha256"]
            != record["candidate_span_sha256"]
        ):
            raise SafetyError("decision_span_identity_mismatch")
        if decision == "edit":
            edited = item["edited_translation"]
            if not isinstance(edited, str):
                raise SafetyError("invalid_edited_translation")
            _split_edited_translation(record, edited)
        normalized[occurrence_id] = dict(item)
    return normalized


def _validated_review_entries(
    source: Path,
    candidate_root: Path,
    source_files: list[SourceFile],
    candidate_files: list[SourceFile],
    inventory: tuple[tuple[str, ...], tuple[str, ...]],
    report: dict[str, object],
    source_hash: str,
    candidate_hash: str,
    report_hash: str,
    expected_identity: ReviewIdentity,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    _validate_report_header(
        report,
        source,
        candidate_root,
        source_hash,
        candidate_hash,
        expected_identity,
    )
    source_english = [
        item for item in source_files if item.parsed and item.parsed.is_english
    ]
    expected_candidates = {
        _candidate_relative(item.relative): item for item in source_english
    }
    candidate_by_path = {item.relative: item for item in candidate_files}
    if set(candidate_by_path) != set(expected_candidates):
        missing = set(expected_candidates) - set(candidate_by_path)
        raise SafetyError(
            "missing_candidate_file" if missing else "extra_candidate_file"
        )
    expected_file_inventory = {
        path.as_posix() for path in expected_candidates
    } | {"translation-report.json"}
    actual_files, actual_dirs = inventory
    if set(actual_files) != expected_file_inventory:
        missing = expected_file_inventory - set(actual_files)
        raise SafetyError(
            "missing_candidate_file" if missing else "extra_candidate_file"
        )
    expected_dirs = {"localisation", "localisation/russian"}
    for relative in expected_candidates:
        parent = relative.parent
        while parent != Path("."):
            expected_dirs.add(parent.as_posix())
            parent = parent.parent
    if set(actual_dirs) != expected_dirs:
        raise SafetyError("candidate_directory_inventory_mismatch")

    counts = report["counts"]
    assert isinstance(counts, dict)
    limit = report["max_occurrences_per_file"]
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 100
    ):
        raise SafetyError("invalid_report_occurrence_limit")
    selected: list[tuple[SourceFile, SourceFile, Entry, Entry, int]] = []
    parser_diagnostics: list[dict[str, object]] = []
    skipped_files = 0
    for item in source_files:
        if item.error:
            skipped_files += 1
            diagnostic: dict[str, object]
            if item.error == "replace_layer_unsupported":
                diagnostic = {
                    "path": item.relative.as_posix(),
                    "code": "replace_layer_unsupported",
                }
            else:
                diagnostic = {
                    "path": item.relative.as_posix(),
                    "code": "file_skipped",
                    "reason": item.error,
                }
            parser_diagnostics.append(diagnostic)
            continue
        if not item.parsed or not item.parsed.is_english:
            continue
        for diagnostic in item.parsed.diagnostics:
            parser_diagnostics.append(
                {"path": item.relative.as_posix(), **diagnostic}
            )
        candidate_file = candidate_by_path[_candidate_relative(item.relative)]
        _validate_file_alignment(item, candidate_file, limit)
        assert candidate_file.parsed is not None
        candidate_entries = {
            entry.line_index: entry for entry in candidate_file.parsed.entries
        }
        for ordinal, source_entry in enumerate(item.parsed.entries[:limit]):
            selected.append(
                (
                    item,
                    candidate_file,
                    source_entry,
                    candidate_entries[source_entry.line_index],
                    ordinal,
                )
            )

    diagnostics = report["diagnostics"]
    if not isinstance(diagnostics, list):
        raise SafetyError("invalid_report_diagnostics")
    model_fallbacks: list[dict[str, object]] = []
    report_parser_diagnostics: list[dict[str, object]] = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict) or not isinstance(
            diagnostic.get("code"), str
        ):
            raise SafetyError("invalid_report_diagnostic")
        if diagnostic["code"] == "translation_fallback":
            if set(diagnostic) != {"path", "line", "code", "reason"}:
                raise SafetyError("invalid_translation_fallback_diagnostic")
            if (
                not isinstance(diagnostic["path"], str)
                or isinstance(diagnostic["line"], bool)
                or not isinstance(diagnostic["line"], int)
                or not isinstance(diagnostic["reason"], str)
            ):
                raise SafetyError("invalid_translation_fallback_diagnostic")
            model_fallbacks.append(diagnostic)
        else:
            report_parser_diagnostics.append(diagnostic)
    if Counter(_canonical_json(item) for item in report_parser_diagnostics) != Counter(
        _canonical_json(item) for item in parser_diagnostics
    ):
        raise SafetyError("report_parser_diagnostics_mismatch")

    selected_lines = {
        (source_file.relative.as_posix(), source_entry.line_index + 1)
        for source_file, _, source_entry, _, _ in selected
    }
    fallback_lines = [
        (item["path"], item["line"]) for item in model_fallbacks
    ]
    if (
        len(fallback_lines) != len(set(fallback_lines))
        or any(line not in selected_lines for line in fallback_lines)
    ):
        raise SafetyError("report_fallback_alignment_mismatch")
    fallback_set = set(fallback_lines)

    entries: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    for source_file, _, source_entry, candidate_entry, ordinal in selected:
        source_segments, source_atoms = _segments_and_atoms(source_entry)
        candidate_segments, candidate_atoms = _segments_and_atoms(candidate_entry)
        if source_atoms != candidate_atoms:
            raise SafetyError("protected_atom_or_escape_mismatch")
        source_span_hash = _human_span_hash(source_segments)
        candidate_span_hash = _human_span_hash(candidate_segments)
        line_identity = (
            source_file.relative.as_posix(),
            source_entry.line_index + 1,
        )
        if line_identity in fallback_set:
            if source_entry.value != candidate_entry.value:
                raise SafetyError("fallback_candidate_changed")
            status = "model_fallback"
        elif source_entry.value == candidate_entry.value:
            status = "accepted_unchanged"
        else:
            status = "accepted_changed"
        status_counts[status] += 1
        occurrence_id = _sha256_json(
            {
                "source_path": source_file.relative.as_posix(),
                "line": source_entry.line_index + 1,
                "occurrence_ordinal": ordinal,
                "source_human_span_sha256": source_span_hash,
                "candidate_human_span_sha256": candidate_span_hash,
                "source_tree_sha256": source_hash,
                "candidate_tree_sha256": candidate_hash,
            }
        )
        entries.append(
            {
                "id": occurrence_id,
                "path": source_file.relative.as_posix(),
                "line": source_entry.line_index + 1,
                "occurrence_ordinal": ordinal,
                "status": status,
                "source_span_sha256": source_span_hash,
                "candidate_span_sha256": candidate_span_hash,
                "source_segments": source_segments,
                "candidate_segments": candidate_segments,
                "protected_atoms": source_atoms,
            }
        )
    if len({entry["id"] for entry in entries}) != len(entries):
        raise SafetyError("duplicate_occurrence_id")

    parser_unsupported = sum(
        1
        for item in parser_diagnostics
        if item.get("code") == "unsupported_entry"
    )
    _validate_report_counts(
        counts,
        selected_count=len(selected),
        accepted_count=(
            status_counts["accepted_changed"]
            + status_counts["accepted_unchanged"]
        ),
        accepted_unchanged=status_counts["accepted_unchanged"],
        model_fallback=status_counts["model_fallback"],
        parser_unsupported=parser_unsupported,
        deferred=expected_identity.deferred,
        discovered=len(source_files),
        english_files=len(source_english),
        skipped_files=skipped_files,
    )
    actual_summary = {
        "review_entries": len(entries),
        "accepted_changed": status_counts["accepted_changed"],
        "accepted_unchanged": status_counts["accepted_unchanged"],
        "model_fallback": status_counts["model_fallback"],
        "parser_unsupported": parser_unsupported,
        "deferred": counts["deferred_occurrences"],
        "skipped_files": skipped_files,
    }
    expected_summary = {
        "review_entries": expected_identity.review_entries,
        "accepted_changed": expected_identity.accepted_changed,
        "accepted_unchanged": expected_identity.accepted_unchanged,
        "model_fallback": expected_identity.model_fallback,
        "parser_unsupported": expected_identity.parser_unsupported,
        "deferred": expected_identity.deferred,
        "skipped_files": expected_identity.skipped_files,
    }
    if actual_summary != expected_summary:
        raise SafetyError("review_summary_identity_mismatch")
    if report_hash != expected_identity.candidate_report_sha256:
        raise SafetyError("candidate_report_identity_mismatch")
    return entries, actual_summary


def _validate_report_header(
    report: dict[str, object],
    source: Path,
    candidate: Path,
    source_hash: str,
    candidate_hash: str,
    expected_identity: ReviewIdentity,
) -> None:
    common_fields = {
        "schema_version",
        "source",
        "output",
        "counts",
        "hashes",
        "diagnostics",
        "dry_run",
        "max_occurrences_per_file",
        "model",
        "status",
        "editorial_status",
        "editorially_approved",
    }
    if set(report) != common_fields or report.get("schema_version") != 2:
        raise SafetyError("unsupported_candidate_report_schema")
    if report["source"] != str(source) or report["output"] != str(candidate):
        raise SafetyError("candidate_report_path_identity_mismatch")
    if report["dry_run"] is not False:
        raise SafetyError("candidate_report_must_not_be_dry_run")
    if (
        report["editorial_status"] != "human_review_required"
        or report["editorially_approved"] is not False
    ):
        raise SafetyError("candidate_report_editorial_state_mismatch")
    if report["status"] not in {
        "technical_safe",
        "technical_safe_partial",
        "technical_safe_with_fallbacks",
    }:
        raise SafetyError("candidate_report_status_mismatch")
    model = report["model"]
    if not isinstance(model, dict) or set(model) != {"tag", "digest"}:
        raise SafetyError("invalid_candidate_model_identity")
    if model != {
        "tag": expected_identity.model_tag,
        "digest": expected_identity.model_digest,
    }:
        raise SafetyError("candidate_model_identity_mismatch")
    hashes = report["hashes"]
    if not isinstance(hashes, dict) or set(hashes) != {
        "source_localisation_sha256",
        "output_localisation_sha256",
    }:
        raise SafetyError("invalid_candidate_report_hashes")
    if hashes["source_localisation_sha256"] != source_hash:
        raise SafetyError("report_source_hash_mismatch")
    if hashes["output_localisation_sha256"] != candidate_hash:
        raise SafetyError("report_candidate_hash_mismatch")


def _validate_report_counts(
    counts: object,
    *,
    selected_count: int,
    accepted_count: int,
    accepted_unchanged: int,
    model_fallback: int,
    parser_unsupported: int,
    deferred: int,
    discovered: int,
    english_files: int,
    skipped_files: int,
) -> None:
    old_fields = {
        "discovered_yml_files",
        "english_files",
        "occurrences",
        "planned_translation_occurrences",
        "translated_occurrences",
        "fallback_occurrences",
        "deferred_occurrences",
        "skipped_files",
    }
    current_fields = old_fields | {"unchanged_accepted_occurrences"}
    if not isinstance(counts, dict) or frozenset(counts) not in {
        frozenset(old_fields),
        frozenset(current_fields),
    }:
        raise SafetyError("unsupported_candidate_count_schema")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in counts.values()
    ):
        raise SafetyError("invalid_candidate_report_count")
    expected = {
        "discovered_yml_files": discovered,
        "english_files": english_files,
        "planned_translation_occurrences": selected_count,
        "translated_occurrences": accepted_count,
        "fallback_occurrences": parser_unsupported + model_fallback,
        "deferred_occurrences": deferred,
        "skipped_files": skipped_files,
        "occurrences": selected_count + parser_unsupported + deferred,
    }
    for name, value in expected.items():
        if counts[name] != value:
            raise SafetyError(f"candidate_report_count_mismatch_{name}")
    if (
        "unchanged_accepted_occurrences" in counts
        and counts["unchanged_accepted_occurrences"] != accepted_unchanged
    ):
        raise SafetyError("candidate_report_unchanged_count_mismatch")


def _validate_file_alignment(
    source_file: SourceFile, candidate_file: SourceFile, limit: int
) -> None:
    source = source_file.parsed
    candidate = candidate_file.parsed
    if source is None or candidate is None:
        raise SafetyError("candidate_parse_failure")
    if not source.is_english or candidate.language != "russian":
        raise SafetyError("candidate_header_mismatch")
    if source.header_line != 0 or candidate.header_line != 0:
        raise SafetyError("candidate_header_mismatch")
    if (
        source.bom != candidate.bom
        or source.newline != candidate.newline
        or len(source.lines) != len(candidate.lines)
    ):
        raise SafetyError("candidate_line_alignment_mismatch")
    expected_header = source.lines[0].replace(
        b"l_english:", b"l_russian:", 1
    )
    if candidate.lines[0] != expected_header:
        raise SafetyError("candidate_header_mismatch")
    if candidate.diagnostics != source.diagnostics:
        raise SafetyError("candidate_diagnostic_alignment_mismatch")
    source_by_line = {entry.line_index: entry for entry in source.entries}
    candidate_by_line = {entry.line_index: entry for entry in candidate.entries}
    if set(source_by_line) != set(candidate_by_line):
        raise SafetyError("candidate_occurrence_alignment_mismatch")
    selected_lines = {
        entry.line_index for entry in source.entries[:limit]
    }
    for index, (source_line, candidate_line) in enumerate(
        zip(source.lines, candidate.lines)
    ):
        if index == 0:
            continue
        source_entry = source_by_line.get(index)
        candidate_entry = candidate_by_line.get(index)
        if source_entry is None:
            if candidate_line != source_line:
                raise SafetyError("candidate_line_alignment_mismatch")
            continue
        assert candidate_entry is not None
        if (
            source_line[: source_entry.value_start]
            != candidate_line[: candidate_entry.value_start]
            or source_line[source_entry.value_end :]
            != candidate_line[candidate_entry.value_end :]
        ):
            raise SafetyError("candidate_occurrence_alignment_mismatch")
        if index not in selected_lines and candidate_entry.value != source_entry.value:
            raise SafetyError("deferred_candidate_changed")
        if "__SMT_" in candidate_entry.value:
            raise SafetyError("candidate_placeholder_residue")
        _, source_atoms = _segments_and_atoms(source_entry)
        _, candidate_atoms = _segments_and_atoms(candidate_entry)
        if source_atoms != candidate_atoms:
            raise SafetyError("protected_atom_or_escape_mismatch")
    if b"__SMT_" in candidate_file.data:
        raise SafetyError("candidate_placeholder_residue")


def _segments_and_atoms(entry: Entry) -> tuple[list[str], list[str]]:
    segments: list[str] = []
    atoms: list[str] = []
    cursor = 0
    for token in entry.protected:
        position = entry.value.find(token.original, cursor)
        if position < 0:
            raise SafetyError("protected_atom_alignment_failure")
        segments.append(entry.value[cursor:position])
        atoms.append(token.original)
        cursor = position + len(token.original)
    segments.append(entry.value[cursor:])
    return segments, atoms


def _human_span_hash(segments: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for segment in segments:
        encoded = segment.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _split_edited_translation(
    record: dict[str, object], edited: str
) -> list[str]:
    _validate_editorial_text(edited)
    atoms = record.get("protected_atoms")
    if not isinstance(atoms, list) or any(
        not isinstance(atom, str) for atom in atoms
    ):
        raise SafetyError("invalid_pack_protected_atoms")
    segments: list[str] = []
    cursor = 0
    for atom in atoms:
        position = edited.find(atom, cursor)
        if position < 0:
            raise SafetyError("edited_translation_protected_atom_mismatch")
        segment = edited[cursor:position]
        _validate_unprotected_segment(segment)
        segments.append(segment)
        cursor = position + len(atom)
    final_segment = edited[cursor:]
    _validate_unprotected_segment(final_segment)
    segments.append(final_segment)
    reconstructed = "".join(
        segment + (atoms[index] if index < len(atoms) else "")
        for index, segment in enumerate(segments)
    )
    if reconstructed != edited:
        raise SafetyError("edited_translation_protected_atom_mismatch")
    return segments


def _validate_editorial_text(value: str) -> None:
    if any(
        ord(char) < 0x20
        or ord(char) == 0x7F
        or 0x80 <= ord(char) <= 0x9F
        or char in "\u2028\u2029\ufeff"
        or unicodedata.category(char) == "Cf"
        for char in value
    ):
        raise SafetyError("edited_translation_contains_unsafe_control")


def _validate_unprotected_segment(value: str) -> None:
    if any(char in '$[]£§\\"' for char in value):
        raise SafetyError("edited_translation_introduces_protected_syntax")


def _validated_input_root(path: Path, label: str) -> Path:
    lexical = path.absolute()
    if path.is_symlink():
        raise SafetyError(f"{label}_root_symlink")
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise SafetyError(f"{label}_root_missing") from exc
    if not resolved.is_dir():
        raise SafetyError(f"{label}_root_not_directory")
    return resolved


def _validated_review_output(
    source: Path, candidate: Path, output: Path
) -> Path:
    lexical = output.absolute()
    if output.exists() or output.is_symlink():
        raise SafetyError("output_must_not_exist")
    try:
        parent = lexical.parent.resolve(strict=True)
    except OSError as exc:
        raise SafetyError("output_parent_missing") from exc
    if not parent.is_dir():
        raise SafetyError("output_parent_not_directory")
    resolved = parent / lexical.name
    if _paths_overlap(source, resolved):
        raise SafetyError("source_output_overlap")
    if _paths_overlap(candidate, resolved):
        raise SafetyError("candidate_output_overlap")
    return resolved


def _paths_overlap(left: Path, right: Path) -> bool:
    return (
        left == right
        or left in right.parents
        or right in left.parents
    )


def _candidate_inventory(
    candidate: Path,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    files: list[str] = []
    directories: list[str] = []
    def fail_walk(error: OSError) -> None:
        raise SafetyError("candidate_inventory_failed") from error

    for root, dirs, names in os.walk(
        candidate, followlinks=False, onerror=fail_walk
    ):
        root_path = Path(root)
        for dirname in sorted(dirs):
            path = root_path / dirname
            if path.is_symlink():
                raise SafetyError("symlink_in_candidate")
            directories.append(path.relative_to(candidate).as_posix())
        for name in sorted(names):
            path = root_path / name
            if path.is_symlink() or not path.is_file():
                raise SafetyError("unsafe_candidate_file")
            files.append(path.relative_to(candidate).as_posix())
    return tuple(sorted(files)), tuple(sorted(directories))


def _read_stable_file(path: Path, label: str) -> StableFile:
    if path.is_symlink():
        raise SafetyError(f"{label}_symlink")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise SafetyError(f"{label}_missing") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise SafetyError(f"{label}_not_regular_file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    before_identity = _stat_identity(before)
    after_identity = _stat_identity(after)
    if before_identity != after_identity:
        raise SafetyError(f"{label}_changed_during_read")
    data = b"".join(chunks)
    return StableFile(
        path=path,
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        stat_identity=after_identity,
    )


def _verify_stable_file(expected: StableFile, error: str) -> None:
    current = _read_stable_file(expected.path, "candidate_report")
    if (
        current.sha256 != expected.sha256
        or current.stat_identity != expected.stat_identity
    ):
        raise SafetyError(error)


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def _load_report(data: bytes) -> dict[str, object]:
    try:
        text = data.decode("utf-8")
        report = json.loads(text, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SafetyError("invalid_candidate_report_json") from exc
    if not isinstance(report, dict):
        raise SafetyError("invalid_candidate_report_json")
    return report


def _unique_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise SafetyError("duplicate_candidate_report_field")
        value[key] = item
    return value


def _require_identity(actual: str, expected: str, error: str) -> None:
    if actual != expected:
        raise SafetyError(error)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _render_review_html(pack_data: dict[str, object]) -> bytes:
    encoded = base64.b64encode(
        _canonical_json(pack_data).encode("utf-8")
    ).decode("ascii")
    fingerprint = pack_data["pack_fingerprint"]
    assert isinstance(fingerprint, str)
    html = (
        _HTML_SHELL.replace("__PACK_DATA_BASE64__", encoded)
        .replace("__PACK_FINGERPRINT__", fingerprint)
    )
    return html.encode("utf-8")


_HTML_SHELL = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; font-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; child-src 'none'; worker-src 'none'; form-action 'none'; base-uri 'none'; manifest-src 'none'">
<title>Stellaris Editorial Review</title>
<style>
:root{color-scheme:dark;--bg:#10141d;--panel:#171d29;--line:#2b3445;--text:#edf1f7;--muted:#98a4b8;--accent:#7bd7c4;--warn:#f4c56b;--bad:#ff8d91}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 system-ui,sans-serif}
button,input,select,textarea{font:inherit}button,select,input,textarea{color:var(--text);background:#111722;border:1px solid var(--line);border-radius:8px}
button{padding:.55rem .8rem;cursor:pointer}button:hover{border-color:var(--accent)}main{max-width:1500px;margin:auto;padding:18px}
.top{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}.title{font-size:1.35rem;font-weight:700}.muted{color:var(--muted)}
.progress{height:10px;background:#242c3a;border-radius:8px;overflow:hidden;min-width:220px}.progress>span{display:block;height:100%;background:var(--accent)}
.filters{display:grid;grid-template-columns:minmax(220px,2fr) repeat(3,minmax(140px,1fr));gap:10px;margin:16px 0}.filters input,.filters select{padding:.6rem}
.layout{display:grid;grid-template-columns:minmax(240px,310px) 1fr;gap:14px}.list{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:8px;max-height:76vh;overflow:auto}
.list button{width:100%;text-align:left;margin-bottom:6px}.list button.active{border-color:var(--accent);background:#1b2b30}.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.metadata{display:flex;gap:12px;flex-wrap:wrap;color:var(--muted);margin-bottom:12px}.status{color:var(--warn)}
.columns{display:grid;grid-template-columns:1fr 1fr;gap:12px}.spanbox{min-height:130px;padding:12px;white-space:pre-wrap;overflow-wrap:anywhere;background:#111722;border:1px solid var(--line);border-radius:9px}
.atom{display:inline-block;padding:1px 6px;margin:1px 2px;border:1px solid #52706d;border-radius:5px;color:var(--accent);background:#172725;font-family:ui-monospace,monospace}
.field{margin-top:14px}.field>label{display:block;font-weight:650;margin-bottom:6px}.editor{display:flex;flex-wrap:wrap;align-items:stretch;gap:6px}.editor textarea{min-height:84px;min-width:170px;flex:1;padding:9px;resize:vertical}
.decision-row,.tag-row,.actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.decision-row select,.field textarea{padding:9px;width:100%}.tag-row label{font-weight:400}
.actions{justify-content:space-between;margin-top:16px}.error{color:var(--bad);min-height:1.4em}.hidden{display:none}
@media(max-width:850px){.filters,.layout,.columns{grid-template-columns:1fr}.list{max-height:240px}}
</style>
</head>
<body>
<main>
  <div class="top">
    <div><div class="title">Local editorial review pack</div><div class="muted" id="fingerprint">Pack __PACK_FINGERPRINT__</div></div>
    <div><div id="progressText"></div><div class="progress"><span id="progressBar"></span></div></div>
  </div>
  <div class="filters">
    <input id="search" type="search" placeholder="Поиск по оригиналу или candidate">
    <select id="fileFilter"><option value="">Все файлы</option></select>
    <select id="statusFilter"><option value="">Все статусы</option><option>accepted_changed</option><option>accepted_unchanged</option><option>model_fallback</option></select>
    <select id="decisionFilter"><option value="">Все решения</option><option>unreviewed</option><option>accept</option><option>edit</option><option>reject</option></select>
  </div>
  <div class="layout">
    <nav class="list" id="entryList" aria-label="Occurrences"></nav>
    <section class="card">
      <div id="empty">Нет записей для выбранного фильтра.</div>
      <div id="review" class="hidden">
        <div class="metadata"><span id="path"></span><span id="line"></span><span class="status" id="status"></span></div>
        <div class="columns">
          <div><strong>Оригинал</strong><div class="spanbox" id="sourceText"></div></div>
          <div><strong>Candidate</strong><div class="spanbox" id="candidateText"></div></div>
        </div>
        <div class="field"><label>Protected atoms / escapes</label><div id="atoms"></div></div>
        <div class="field decision-row"><label for="decision">Решение</label><select id="decision"><option>unreviewed</option><option>accept</option><option>edit</option><option>reject</option></select></div>
        <div class="field" id="editorField"><label>Итоговый русский вариант</label><div class="editor" id="editor"></div></div>
        <div class="field"><label for="note">Комментарий</label><textarea id="note" rows="3"></textarea></div>
        <div class="field"><label>Теги</label><div class="tag-row" id="tags"></div></div>
        <div class="field"><label><input type="checkbox" id="glossary"> glossary_candidate</label></div>
        <div class="actions"><div><button id="previous">← Предыдущая</button> <button id="next">Следующая →</button></div><div><button id="export">Экспорт JSON</button> <button id="importButton">Импорт JSON</button> <button id="clear">Очистить решения</button><input class="hidden" id="importFile" type="file" accept="application/json"></div></div>
        <div class="error" id="error" role="alert"></div>
      </div>
    </section>
  </div>
</main>
<script id="review-data" type="application/octet-stream">__PACK_DATA_BASE64__</script>
<script>
"use strict";
const raw=document.getElementById("review-data").textContent.trim();
const bytes=Uint8Array.from(atob(raw),c=>c.charCodeAt(0));
const pack=JSON.parse(new TextDecoder().decode(bytes));
const allowedDecisions=new Set(["unreviewed","accept","edit","reject"]);
const allowedTags=new Set(["terminology","lore","meaning","style","grammar","leftover_english"]);
const storageKey="stellaris-review-pack:"+pack.pack_fingerprint;
const byId=new Map(pack.entries.map(entry=>[entry.id,entry]));
let state=new Map();
let visible=[];
let currentId=pack.entries.length?pack.entries[0].id:null;
const el=id=>document.getElementById(id);
const defaults=record=>({decision:"unreviewed",edited_segments:record.candidate_segments.slice(),note:"",tags:[],glossary_candidate:false});
const currentState=record=>state.get(record.id)||defaults(record);
function appendSpan(container,segments,atoms){
  container.replaceChildren();
  segments.forEach((segment,index)=>{
    container.append(document.createTextNode(segment));
    if(index<atoms.length){const chip=document.createElement("span");chip.className="atom";chip.textContent=atoms[index];container.append(chip)}
  });
}
function fullTranslation(record,item){let result="";item.edited_segments.forEach((segment,index)=>{result+=segment;if(index<record.protected_atoms.length)result+=record.protected_atoms[index]});return result}
function validateText(value){if(typeof value!=="string"||/[\u0000-\u001f\u007f-\u009f\u2028\u2029\ufeff]/u.test(value)||/\p{Cf}/u.test(value))throw new Error("edited_translation contains unsafe control")}
function validateSegment(value){validateText(value);if(/[$\[\]£§\\\\"]/u.test(value))throw new Error("edited_translation introduces protected syntax")}
function splitEdited(record,value){
  validateText(value);const segments=[];let cursor=0;
  for(const atom of record.protected_atoms){const position=value.indexOf(atom,cursor);if(position<0)throw new Error("protected atom mismatch");const segment=value.slice(cursor,position);validateSegment(segment);segments.push(segment);cursor=position+atom.length}
  const finalSegment=value.slice(cursor);validateSegment(finalSegment);segments.push(finalSegment);
  let rebuilt="";segments.forEach((segment,index)=>{rebuilt+=segment;if(index<record.protected_atoms.length)rebuilt+=record.protected_atoms[index]});
  if(rebuilt!==value)throw new Error("protected atom mismatch");return segments
}
function exportDocument(){
  return {schema_version:1,pack_fingerprint:pack.pack_fingerprint,decisions:pack.entries.map(record=>{
    const item=currentState(record);const result={occurrence_id:record.id,decision:item.decision,note:item.note,tags:item.tags.slice().sort(),glossary_candidate:item.glossary_candidate,source_span_sha256:record.source_span_sha256,candidate_span_sha256:record.candidate_span_sha256};
    if(item.decision==="edit")result.edited_translation=fullTranslation(record,item);return result
  })}
}
function exactFields(object,fields){const actual=Object.keys(object).sort().join("\\n");const expected=fields.slice().sort().join("\\n");return actual===expected}
function validateDocument(documentValue){
  if(!documentValue||typeof documentValue!=="object"||Array.isArray(documentValue)||!exactFields(documentValue,["schema_version","pack_fingerprint","decisions"]))throw new Error("invalid decisions document fields");
  if(documentValue.schema_version!==1)throw new Error("invalid decisions schema");
  if(documentValue.pack_fingerprint!==pack.pack_fingerprint)throw new Error("fingerprint mismatch");
  if(!Array.isArray(documentValue.decisions))throw new Error("invalid decisions array");
  const next=new Map();
  for(const item of documentValue.decisions){
    if(!item||typeof item!=="object"||Array.isArray(item))throw new Error("invalid decision record");
    const record=byId.get(item.occurrence_id);if(!record)throw new Error("unknown occurrence ID");if(next.has(item.occurrence_id))throw new Error("duplicate occurrence ID");
    if(!allowedDecisions.has(item.decision))throw new Error("invalid decision enum");
    const fields=["occurrence_id","decision","note","tags","glossary_candidate","source_span_sha256","candidate_span_sha256"];if(item.decision==="edit")fields.push("edited_translation");
    if(!exactFields(item,fields))throw new Error("invalid decision fields");
    if(typeof item.note!=="string"||typeof item.glossary_candidate!=="boolean"||!Array.isArray(item.tags)||new Set(item.tags).size!==item.tags.length||item.tags.some(tag=>!allowedTags.has(tag)))throw new Error("invalid decision values");
    if(item.source_span_sha256!==record.source_span_sha256||item.candidate_span_sha256!==record.candidate_span_sha256)throw new Error("span identity mismatch");
    const editedSegments=item.decision==="edit"?splitEdited(record,item.edited_translation):record.candidate_segments.slice();
    next.set(record.id,{decision:item.decision,edited_segments:editedSegments,note:item.note,tags:item.tags.slice(),glossary_candidate:item.glossary_candidate});
  }
  return next
}
function save(){localStorage.setItem(storageKey,JSON.stringify(exportDocument()))}
function showError(message){el("error").textContent=message}
function updateProgress(){const reviewed=pack.entries.filter(record=>currentState(record).decision!=="unreviewed").length;el("progressText").textContent=reviewed+" / "+pack.entries.length+" reviewed";el("progressBar").style.width=(pack.entries.length?reviewed/pack.entries.length*100:0)+"%"}
function searchable(record){return [record.path,record.status,...record.source_segments,...record.candidate_segments].join("\\n").toLocaleLowerCase()}
function applyFilters(){
  const query=el("search").value.toLocaleLowerCase();const file=el("fileFilter").value;const status=el("statusFilter").value;const decision=el("decisionFilter").value;
  visible=pack.entries.filter(record=>(!file||record.path===file)&&(!status||record.status===status)&&(!decision||currentState(record).decision===decision)&&(!query||searchable(record).includes(query)));
  if(!visible.some(record=>record.id===currentId))currentId=visible.length?visible[0].id:null;render()
}
function renderList(){
  const list=el("entryList");list.replaceChildren();
  visible.forEach(record=>{const button=document.createElement("button");button.type="button";button.className=record.id===currentId?"active":"";const item=currentState(record);button.textContent=record.path+" · "+record.line+"\\n"+record.status+" · "+item.decision;button.addEventListener("click",()=>{currentId=record.id;render()});list.append(button)})
}
function renderEditor(record,item){
  const editor=el("editor");editor.replaceChildren();
  item.edited_segments.forEach((segment,index)=>{const area=document.createElement("textarea");area.value=segment;area.setAttribute("aria-label","Editable human segment "+(index+1));area.addEventListener("input",()=>{item.edited_segments[index]=area.value;state.set(record.id,item);save()});editor.append(area);if(index<record.protected_atoms.length){const atom=document.createElement("span");atom.className="atom";atom.textContent=record.protected_atoms[index];editor.append(atom)}})
}
function render(){
  renderList();updateProgress();const record=byId.get(currentId);el("empty").classList.toggle("hidden",Boolean(record));el("review").classList.toggle("hidden",!record);if(!record)return;
  const item=currentState(record);el("path").textContent=record.path;el("line").textContent="line "+record.line;el("status").textContent=record.status;
  appendSpan(el("sourceText"),record.source_segments,record.protected_atoms);appendSpan(el("candidateText"),record.candidate_segments,record.protected_atoms);
  const atoms=el("atoms");atoms.replaceChildren();if(!record.protected_atoms.length)atoms.textContent="Нет";record.protected_atoms.forEach(value=>{const chip=document.createElement("span");chip.className="atom";chip.textContent=value;atoms.append(chip)});
  el("decision").value=item.decision;el("note").value=item.note;el("glossary").checked=item.glossary_candidate;el("editorField").classList.toggle("hidden",item.decision!=="edit");renderEditor(record,item);
  for(const input of el("tags").querySelectorAll("input"))input.checked=item.tags.includes(input.value);showError("")
}
function move(delta){const index=visible.findIndex(record=>record.id===currentId);if(index>=0&&visible.length){currentId=visible[(index+delta+visible.length)%visible.length].id;render()}}
for(const file of [...new Set(pack.entries.map(record=>record.path))].sort()){const option=document.createElement("option");option.value=file;option.textContent=file;el("fileFilter").append(option)}
for(const tag of allowedTags){const label=document.createElement("label");const input=document.createElement("input");input.type="checkbox";input.value=tag;input.addEventListener("change",()=>{const record=byId.get(currentId);if(!record)return;const item=currentState(record);item.tags=[...el("tags").querySelectorAll("input:checked")].map(node=>node.value);state.set(record.id,item);save()});label.append(input,document.createTextNode(" "+tag));el("tags").append(label)}
for(const id of ["search","fileFilter","statusFilter","decisionFilter"])el(id).addEventListener(id==="search"?"input":"change",applyFilters);
el("decision").addEventListener("change",()=>{const record=byId.get(currentId);if(!record)return;const item=currentState(record);item.decision=el("decision").value;state.set(record.id,item);save();applyFilters()});
el("note").addEventListener("input",()=>{const record=byId.get(currentId);if(!record)return;const item=currentState(record);item.note=el("note").value;state.set(record.id,item);save()});
el("glossary").addEventListener("change",()=>{const record=byId.get(currentId);if(!record)return;const item=currentState(record);item.glossary_candidate=el("glossary").checked;state.set(record.id,item);save()});
el("previous").addEventListener("click",()=>move(-1));el("next").addEventListener("click",()=>move(1));
el("export").addEventListener("click",()=>{try{const blob=new Blob([JSON.stringify(exportDocument(),null,2)+"\n"],{type:"application/json"});const link=document.createElement("a");link.download="review-decisions-"+pack.pack_fingerprint.slice(0,12)+".json";link.href=URL.createObjectURL(blob);link.click();setTimeout(()=>URL.revokeObjectURL(link.href),0);showError("")}catch(error){showError(error.message)}});
el("importButton").addEventListener("click",()=>el("importFile").click());
el("importFile").addEventListener("change",async event=>{try{const file=event.target.files[0];if(!file)return;const documentValue=JSON.parse(await file.text());state=validateDocument(documentValue);save();applyFilters();showError("")}catch(error){showError("Импорт отклонён: "+error.message)}finally{event.target.value=""}});
el("clear").addEventListener("click",()=>{if(confirm("Удалить все локальные решения для этого pack?")){state=new Map();localStorage.removeItem(storageKey);applyFilters()}});
try{const saved=localStorage.getItem(storageKey);if(saved)state=validateDocument(JSON.parse(saved))}catch(error){state=new Map();showError("Локальное сохранение отклонено: "+error.message)}
applyFilters();
</script>
</body>
</html>
"""
