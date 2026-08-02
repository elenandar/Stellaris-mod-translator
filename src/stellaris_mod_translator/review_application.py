"""Apply a complete MVP-2 editorial decision set to a new candidate."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile

from .engine import (
    SafetyError,
    SourceFile,
    _candidate_relative,
    _tree_hash,
    _write_new,
)
from .parser import parse_localisation
from .publication import (
    AtomicPublicationUnavailable,
    DestinationExistsError,
    atomic_publish_directory_no_replace,
)
from .review import (
    FULL_REVIEW_PACK_SCHEMA_VERSION,
    MAX_DECISIONS_BYTES,
    MVP2_PILOT_IDENTITY,
    ReviewIdentity,
    SHA256_RE,
    _paths_overlap,
    _read_stable_file,
    _segments_and_atoms,
    _split_edited_translation,
    _validated_input_root,
    _validated_review_inputs,
    _validated_review_output,
    _validate_file_alignment,
    _verify_review_inputs,
    _verify_stable_file,
    validate_decisions_payload,
)


REVIEW_APPLICATION_SCHEMA_VERSION = 1
FULL_REVIEW_APPLICATION_SCHEMA_VERSION = 2


def apply_review_decisions(
    source_mod: Path,
    candidate: Path,
    decisions: Path,
    output: Path,
    *,
    expected_identity: ReviewIdentity | None = None,
    candidate_report_sha256: str | None = None,
) -> dict[str, object]:
    """Apply one complete decision per exact reviewable occurrence."""
    if (
        candidate_report_sha256 is not None
        and (
            not isinstance(candidate_report_sha256, str)
            or SHA256_RE.fullmatch(candidate_report_sha256) is None
        )
    ):
        raise SafetyError("invalid_candidate_report_sha256")
    if candidate_report_sha256 is not None and expected_identity is not None:
        raise SafetyError("candidate_report_pin_incompatible_with_legacy_identity")
    source = _validated_input_root(source_mod, "source")
    candidate_root = _validated_input_root(candidate, "candidate")
    if _paths_overlap(source, candidate_root):
        raise SafetyError("source_candidate_overlap")
    output_abs = _validated_review_output(source, candidate_root, output)
    decisions_path = _validated_decisions_path(decisions)
    if _paths_overlap(output_abs, decisions_path):
        raise SafetyError("decisions_output_overlap")

    inputs = _validated_review_inputs(
        source,
        candidate_root,
        (
            None
            if candidate_report_sha256 is not None
            else expected_identity or MVP2_PILOT_IDENTITY
        ),
        candidate_report_sha256,
    )
    full_candidate = (
        inputs.pack_schema_version == FULL_REVIEW_PACK_SCHEMA_VERSION
    )
    decisions_file = _read_stable_file(
        decisions_path,
        "decisions",
        max_bytes=MAX_DECISIONS_BYTES,
    )
    payload = _load_decisions(decisions_file.data)
    normalized = validate_decisions_payload(payload, inputs.pack_data)
    entries = inputs.pack_data.get("entries")
    if not isinstance(entries, list):
        raise SafetyError("invalid_pack_entries")
    occurrence_ids = {
        entry.get("id")
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    if (
        (
            not full_candidate
            and len(entries)
            != (expected_identity or MVP2_PILOT_IDENTITY).review_entries
        )
        or len(occurrence_ids) != len(entries)
        or set(normalized) != occurrence_ids
    ):
        raise SafetyError("incomplete_decisions")
    if any(item.get("decision") == "unreviewed" for item in normalized.values()):
        raise SafetyError("unreviewed_decision")

    _verify_review_inputs(inputs)
    _verify_stable_file(
        decisions_file,
        "decisions_generation_changed",
        label="decisions",
        max_bytes=MAX_DECISIONS_BYTES,
    )
    (
        replacements,
        decision_counts,
        changed_spans,
        restored_english_spans,
    ) = _planned_replacements(
        inputs.source_files,
        inputs.candidate_files,
        inputs.report,
        entries,
        normalized,
    )
    _verify_review_inputs(inputs)
    _verify_stable_file(
        decisions_file,
        "decisions_generation_changed",
        label="decisions",
        max_bytes=MAX_DECISIONS_BYTES,
    )

    temp = Path(
        tempfile.mkdtemp(
            prefix=f".{output_abs.name}.tmp-",
            dir=output_abs.parent,
        )
    )
    try:
        rendered_files = _render_output_files(
            temp,
            inputs.source_files,
            inputs.candidate_files,
            inputs.report,
            replacements,
        )
        final_hash = _tree_hash(rendered_files)
        fingerprint = inputs.pack_data.get("pack_fingerprint")
        if not isinstance(fingerprint, str):
            raise SafetyError("invalid_pack_fingerprint")
        model = inputs.report.get("model")
        if (
            not isinstance(model, dict)
            or not isinstance(model.get("tag"), str)
            or not isinstance(model.get("digest"), str)
        ):
            raise SafetyError("invalid_candidate_model_identity")
        common_report: dict[str, object] = {
            "source_mod": str(source),
            "base_candidate": str(candidate_root),
            "decisions": str(decisions_file.path),
            "output": str(output_abs),
            "pack_fingerprint": fingerprint,
            "model": {"tag": model["tag"], "digest": model["digest"]},
            "source_mutations": 0,
            "candidate_mutations": 0,
            "protected_atom_mismatches": 0,
            "ollama_calls": 0,
            "network_calls": 0,
        }
        if full_candidate:
            summary = inputs.summary
            unsupported = summary.get("unsupported")
            skipped_files = summary.get("skipped_files")
            if (
                isinstance(unsupported, bool)
                or not isinstance(unsupported, int)
                or isinstance(skipped_files, bool)
                or not isinstance(skipped_files, int)
            ):
                raise SafetyError("invalid_full_review_summary")
            base_counts = inputs.report.get("counts")
            base_status = inputs.report.get("status")
            if not isinstance(base_counts, dict) or not isinstance(
                base_status, str
            ):
                raise SafetyError("invalid_candidate_report_summary")
            report = {
                "schema_version": FULL_REVIEW_APPLICATION_SCHEMA_VERSION,
                "status": "full_candidate_review_applied",
                "review_scope": "full_candidate",
                "review_pack_schema_version": (
                    FULL_REVIEW_PACK_SCHEMA_VERSION
                ),
                "candidate_report_schema_version": 3,
                "editorial_status": (
                    "human_review_complete_for_reviewable_occurrences"
                ),
                "editorially_approved": (
                    unsupported == 0 and skipped_files == 0
                ),
                "base_candidate_status": base_status,
                "base_candidate_counts": dict(base_counts),
                "review_summary": dict(summary),
                "technical_residue": {
                    "unsupported_occurrences": unsupported,
                    "skipped_files": skipped_files,
                },
                "counts": {
                    "total_decisions": len(normalized),
                    "accept": decision_counts["accept"],
                    "edit": decision_counts["edit"],
                    "reject": decision_counts["reject"],
                    "actually_changed_spans": changed_spans,
                    "restored_english_spans": restored_english_spans,
                },
                "hashes": {
                    "source_localisation_sha256": (
                        inputs.source_localisation_sha256
                    ),
                    "base_candidate_localisation_sha256": (
                        inputs.candidate_localisation_sha256
                    ),
                    "pinned_translation_report_sha256": (
                        inputs.report_file.sha256
                    ),
                    "decisions_file_sha256": decisions_file.sha256,
                    "final_output_localisation_sha256": final_hash,
                },
                **common_report,
            }
        else:
            report = {
                "schema_version": REVIEW_APPLICATION_SCHEMA_VERSION,
                "status": "bounded_pilot_review_applied",
                "editorial_status": (
                    "human_review_complete_for_bounded_pilot"
                ),
                "editorially_approved": False,
                "counts": {
                    "total_decisions": len(normalized),
                    "accept": decision_counts["accept"],
                    "edit": decision_counts["edit"],
                    "reject": decision_counts["reject"],
                    "actually_changed_spans": changed_spans,
                    "restored_english_spans": decision_counts["reject"],
                },
                "hashes": {
                    "source_localisation_sha256": (
                        inputs.source_localisation_sha256
                    ),
                    "base_candidate_localisation_sha256": (
                        inputs.candidate_localisation_sha256
                    ),
                    "base_translation_report_sha256": (
                        inputs.report_file.sha256
                    ),
                    "decisions_file_sha256": decisions_file.sha256,
                    "final_output_localisation_sha256": final_hash,
                },
                **common_report,
            }
        _write_new(
            temp / "review-application-report.json",
            (
                json.dumps(
                    report,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8"),
        )
        _validate_output_inventory(temp, inputs.candidate_files)
        _verify_review_inputs(inputs)
        _verify_stable_file(
            decisions_file,
            "decisions_generation_changed",
            label="decisions",
            max_bytes=MAX_DECISIONS_BYTES,
        )
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
    return report


def _validated_decisions_path(path: Path) -> Path:
    lexical = path.absolute()
    if path.is_symlink():
        raise SafetyError("decisions_symlink")
    try:
        parent = lexical.parent.resolve(strict=True)
    except OSError as exc:
        raise SafetyError("decisions_parent_missing") from exc
    if not parent.is_dir():
        raise SafetyError("decisions_parent_not_directory")
    return parent / lexical.name


def _load_decisions(data: bytes) -> dict[str, object]:
    try:
        text = data.decode("utf-8")
        payload = json.loads(
            text,
            object_pairs_hook=_unique_decisions_object,
            parse_float=_finite_json_float,
            parse_constant=_reject_json_constant,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        RecursionError,
    ) as exc:
        raise SafetyError("invalid_decisions_json") from exc
    if not isinstance(payload, dict):
        raise SafetyError("invalid_decisions_json")
    return payload


def _unique_decisions_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise SafetyError("duplicate_decisions_field")
        value[key] = item
    return value


def _finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number")
    return parsed


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"invalid JSON constant: {value}")


def _planned_replacements(
    source_files: list[SourceFile],
    candidate_files: list[SourceFile],
    report: dict[str, object],
    entries: list[object],
    decisions: dict[str, dict[str, object]],
) -> tuple[dict[Path, dict[int, str]], Counter[str], int, int]:
    limit = report.get("max_occurrences_per_file")
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int)
    ):
        raise SafetyError("invalid_report_occurrence_limit")
    source_by_path = {item.relative.as_posix(): item for item in source_files}
    candidate_by_path = {item.relative: item for item in candidate_files}
    replacements: dict[Path, dict[int, str]] = {}
    decision_counts: Counter[str] = Counter()
    changed_spans = 0
    restored_english_spans = 0
    for raw_record in entries:
        if not isinstance(raw_record, dict):
            raise SafetyError("invalid_pack_entry")
        occurrence_id = raw_record.get("id")
        path = raw_record.get("path")
        line = raw_record.get("line")
        ordinal = raw_record.get("occurrence_ordinal")
        if (
            not isinstance(occurrence_id, str)
            or not isinstance(path, str)
            or isinstance(line, bool)
            or not isinstance(line, int)
            or isinstance(ordinal, bool)
            or not isinstance(ordinal, int)
        ):
            raise SafetyError("invalid_pack_occurrence_identity")
        source_file = source_by_path.get(path)
        if source_file is None or source_file.parsed is None:
            raise SafetyError("invalid_pack_source_path")
        selected = (
            source_file.parsed.entries
            if limit is None
            else source_file.parsed.entries[:limit]
        )
        if (
            ordinal < 0
            or ordinal >= len(selected)
            or selected[ordinal].line_index + 1 != line
        ):
            raise SafetyError("pack_occurrence_identity_mismatch")
        source_entry = selected[ordinal]
        candidate_relative = _candidate_relative(source_file.relative)
        candidate_file = candidate_by_path.get(candidate_relative)
        if candidate_file is None or candidate_file.parsed is None:
            raise SafetyError("invalid_pack_candidate_path")
        candidate_by_line = {
            item.line_index: item for item in candidate_file.parsed.entries
        }
        candidate_entry = candidate_by_line.get(source_entry.line_index)
        if candidate_entry is None:
            raise SafetyError("candidate_occurrence_alignment_mismatch")
        source_segments, source_atoms = _segments_and_atoms(source_entry)
        _, candidate_atoms = _segments_and_atoms(candidate_entry)
        if source_atoms != candidate_atoms:
            raise SafetyError("protected_atom_or_escape_mismatch")

        decision_record = decisions[occurrence_id]
        decision = decision_record.get("decision")
        if decision not in {"accept", "edit", "reject"}:
            raise SafetyError("unreviewed_decision")
        decision_counts[decision] += 1
        if decision == "accept":
            final_value = candidate_entry.value
        elif decision == "edit":
            edited = decision_record.get("edited_translation")
            if not isinstance(edited, str):
                raise SafetyError("invalid_edited_translation")
            edited_segments = _split_edited_translation(raw_record, edited)
            final_value = _join_segments_atoms(
                edited_segments,
                candidate_atoms,
            )
        else:
            final_value = _join_segments_atoms(
                source_segments,
                candidate_atoms,
            )
        if final_value != candidate_entry.value:
            replacements.setdefault(candidate_relative, {})[
                candidate_entry.line_index
            ] = final_value
            changed_spans += 1
            if decision == "reject":
                restored_english_spans += 1
    return (
        replacements,
        decision_counts,
        changed_spans,
        restored_english_spans,
    )


def _join_segments_atoms(segments: list[str], atoms: list[str]) -> str:
    if len(segments) != len(atoms) + 1:
        raise SafetyError("human_segment_atom_count_mismatch")
    pieces: list[str] = []
    for index, segment in enumerate(segments):
        pieces.append(segment)
        if index < len(atoms):
            pieces.append(atoms[index])
    return "".join(pieces)


def _render_output_files(
    temp: Path,
    source_files: list[SourceFile],
    candidate_files: list[SourceFile],
    report: dict[str, object],
    replacements: dict[Path, dict[int, str]],
) -> list[tuple[Path, bytes]]:
    limit = report.get("max_occurrences_per_file")
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int)
    ):
        raise SafetyError("invalid_report_occurrence_limit")
    source_by_candidate = {
        _candidate_relative(item.relative): item
        for item in source_files
        if item.parsed is not None and item.parsed.is_english
    }
    rendered_files: list[tuple[Path, bytes]] = []
    for candidate_file in candidate_files:
        parsed = candidate_file.parsed
        source_file = source_by_candidate.get(candidate_file.relative)
        if parsed is None or source_file is None:
            raise SafetyError("candidate_parse_failure")
        file_replacements = replacements.get(candidate_file.relative, {})
        rendered = (
            parsed.render(file_replacements)
            if file_replacements
            else candidate_file.data
        )
        final_parsed = parse_localisation(rendered)
        final_file = SourceFile(
            relative=candidate_file.relative,
            data=rendered,
            sha256=hashlib.sha256(rendered).hexdigest(),
            stat_identity=(0, 0, len(rendered), 0),
            parsed=final_parsed,
            error=None,
        )
        _validate_file_alignment(source_file, final_file, limit)
        target = temp / candidate_file.relative
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_new(target, rendered)
        rendered_files.append((candidate_file.relative, rendered))
    return rendered_files


def _validate_output_inventory(
    temp: Path,
    candidate_files: list[SourceFile],
) -> None:
    expected = {
        item.relative.as_posix() for item in candidate_files
    } | {"review-application-report.json"}
    actual: set[str] = set()
    for root, directories, names in os.walk(temp, followlinks=False):
        root_path = Path(root)
        for directory in directories:
            if (root_path / directory).is_symlink():
                raise SafetyError("symlink_in_reviewed_candidate")
        for name in names:
            path = root_path / name
            if path.is_symlink() or not path.is_file():
                raise SafetyError("unsafe_reviewed_candidate_file")
            actual.add(path.relative_to(temp).as_posix())
    if actual != expected:
        raise SafetyError("reviewed_candidate_inventory_mismatch")
