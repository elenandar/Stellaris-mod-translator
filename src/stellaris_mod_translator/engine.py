"""Discovery, immutable source snapshots, translation, and atomic output."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
from typing import Callable

from . import ollama
from .ollama import (
    OllamaClient,
    OllamaError,
    OllamaResultError,
    OllamaSystemError,
)
from .parser import Entry, ParseError, ParsedFile, parse_localisation
from .publication import (
    AtomicPublicationUnavailable,
    DestinationExistsError,
    atomic_publish_directory_no_replace,
)
from .workspace import (
    InventoryRow,
    OccurrenceRow,
    WorkspaceError,
    WorkspaceSnapshot,
    WorkspaceWriter,
    create_workspace,
    load_workspace,
    mark_workspace_completed,
    set_finalization_intent,
)


class SafetyError(RuntimeError):
    pass


PARSER_ORDER_VERSION = "mvp4-lossless-parser-order-v1"


@dataclass(frozen=True)
class SourceFile:
    relative: Path
    data: bytes
    sha256: str
    stat_identity: tuple[int, int, int, int]
    parsed: ParsedFile | None
    error: str | None


@dataclass(frozen=True)
class PlannedOccurrence:
    sequence: int
    relative_path: str
    line_number: int
    ordinal: int
    source_span_sha256: str
    entry: Entry


@dataclass(frozen=True)
class OutputTreeIdentity:
    sha256: str
    file_count: int
    directory_count: int


def inspect_mod(source_mod: Path) -> dict[str, object]:
    source = _validated_source(source_mod)
    files = _snapshot(source)
    return _inspect_report(source, files)


def translate_mod(
    source_mod: Path,
    output: Path,
    model: str,
    *,
    dry_run: bool = False,
    max_occurrences_per_file: int | None = None,
    workspace: Path | None = None,
    resume: bool = False,
    client_factory: Callable[[], OllamaClient] = OllamaClient,
) -> dict[str, object]:
    if resume and workspace is None:
        raise SafetyError("resume_requires_workspace")
    if workspace is not None:
        if dry_run:
            raise SafetyError("workspace_mode_incompatible_with_dry_run")
        if max_occurrences_per_file is not None:
            raise SafetyError(
                "workspace_mode_incompatible_with_max_occurrences_per_file"
            )
        return _translate_mod_resumable(
            source_mod,
            output,
            model,
            workspace=workspace,
            resume=resume,
            client_factory=client_factory,
        )
    return _translate_mod_single_pass(
        source_mod,
        output,
        model,
        dry_run=dry_run,
        max_occurrences_per_file=max_occurrences_per_file,
        client_factory=client_factory,
    )


def _translate_mod_single_pass(
    source_mod: Path,
    output: Path,
    model: str,
    *,
    dry_run: bool,
    max_occurrences_per_file: int | None,
    client_factory: Callable[[], OllamaClient],
) -> dict[str, object]:
    _validate_occurrence_limit(max_occurrences_per_file)
    source = _validated_source(source_mod)
    output_abs = _validated_output(source, output)
    files = _snapshot(source)
    report = _translation_report(source, files)
    report["output"] = str(output_abs)
    report["dry_run"] = dry_run
    report["max_occurrences_per_file"] = max_occurrences_per_file
    report["model"] = {"tag": model, "digest": None}
    planned, deferred = _translation_plan_counts(
        files, max_occurrences_per_file
    )
    report["counts"]["planned_translation_occurrences"] = planned
    report["counts"]["deferred_occurrences"] = deferred
    if dry_run:
        _validate_count_invariant(report, dry_run=True)
        report["status"] = _translation_status(report, dry_run=True)
        report["editorial_status"] = "not_evaluated"
        report["editorially_approved"] = False
        return report

    needs_model = planned > 0
    client: OllamaClient | None = None
    identity: dict[str, str] | None = None
    if needs_model:
        client = client_factory()
        identity = _validated_model_identity(client.exact_model(model), model)
        report["model"] = identity
    temp = Path(
        tempfile.mkdtemp(prefix=f".{output_abs.name}.tmp-", dir=output_abs.parent)
    )
    candidates: list[tuple[Path, bytes]] = []
    translated = unchanged = fallback = 0
    try:
        for source_file in files:
            parsed = source_file.parsed
            if parsed is None or not parsed.is_english:
                continue
            replacements: dict[int, str] = {}
            for entry in _selected_entries(
                parsed, max_occurrences_per_file
            ):
                try:
                    if client is None:
                        raise SafetyError("model_client_unavailable")
                    result = client.translate(tag=model, text=entry.model_text())
                    restored = entry.restore_translation(result)
                    replacements[entry.line_index] = restored
                    translated += 1
                    if restored.encode("utf-8") == entry.value.encode("utf-8"):
                        unchanged += 1
                except (OllamaError, ValueError) as exc:
                    fallback += 1
                    report["diagnostics"].append(
                        {
                            "path": source_file.relative.as_posix(),
                            "line": entry.line_index + 1,
                            "code": "translation_fallback",
                            "reason": type(exc).__name__,
                        }
                    )
            relative = _candidate_relative(source_file.relative)
            rendered = parsed.render(replacements, russian_header=True)
            target = temp / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_new(target, rendered)
            candidates.append((relative, rendered))

        _verify_snapshot(source, files)
        candidate_hash = _tree_hash(candidates)
        report["counts"]["translated_occurrences"] = translated
        report["counts"]["unchanged_accepted_occurrences"] = unchanged
        report["counts"]["fallback_occurrences"] += fallback
        report["hashes"]["output_localisation_sha256"] = candidate_hash
        _validate_count_invariant(report, dry_run=False)
        report["status"] = _translation_status(report, dry_run=False)
        report["editorial_status"] = "human_review_required"
        report["editorially_approved"] = False
        report_path = temp / "translation-report.json"
        _write_new(
            report_path,
            (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
        _verify_snapshot(source, files)
        if client is not None:
            final_identity = _validated_model_identity(
                client.exact_model(model), model
            )
            if final_identity != identity:
                raise SafetyError("model_identity_changed")
        _verify_snapshot(source, files)
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


def _translate_mod_resumable(
    source_mod: Path,
    output: Path,
    model: str,
    *,
    workspace: Path,
    resume: bool,
    client_factory: Callable[[], OllamaClient],
) -> dict[str, object]:
    source = _validated_source(source_mod)
    output_abs = _normalized_output(source, output)
    workspace_abs = _normalized_workspace(workspace, resume=resume)
    _validate_workspace_path_relationships(source, output_abs, workspace_abs)

    if resume:
        initial_workspace = _load_workspace(workspace_abs)
        if initial_workspace.job.state == "completed":
            raise SafetyError("workspace_already_completed")
    else:
        if workspace_abs.exists() or workspace_abs.is_symlink():
            raise SafetyError("first_run_requires_absent_workspace")
        initial_workspace = None
    output_exists = output_abs.exists() or output_abs.is_symlink()
    if not resume and output_exists:
        raise SafetyError("output_must_not_exist")
    if (
        resume
        and output_exists
        and initial_workspace is not None
        and initial_workspace.job.finalization_state != "intent"
    ):
        raise SafetyError("output_exists_without_finalization_intent")

    files = _snapshot(source)
    inventory, plan, source_tree_hash, inventory_hash = _workspace_inputs(files)
    prompt_profile_hash = ollama.translation_prompt_profile_hash()

    if initial_workspace is not None:
        _validate_workspace_semantics(
            initial_workspace,
            source=source,
            output=output_abs,
            model=model,
            files=files,
            inventory=inventory,
            plan=plan,
            source_tree_hash=source_tree_hash,
            inventory_hash=inventory_hash,
            prompt_profile_hash=prompt_profile_hash,
        )
        reused = initial_workspace.job.completed_count

    if output_exists:
        assert initial_workspace is not None
        identity = _validated_model_identity(
            {
                "tag": initial_workspace.job.model_tag,
                "digest": initial_workspace.job.model_digest,
            },
            model,
        )
        _verify_snapshot(source, files)
        report_run_count = initial_workspace.job.report_run_count
        report_reused = initial_workspace.job.report_reused_count
        report_calls = initial_workspace.job.report_calls_count
        if (
            report_run_count is None
            or report_reused is None
            or report_calls is None
        ):
            raise SafetyError("workspace_finalization_report_counters_missing")
        recovery_temp = Path(
            tempfile.mkdtemp(
                prefix=f".{output_abs.name}.recover-",
                dir=output_abs.parent,
            )
        )
        try:
            expected_report, expected_output = _build_workspace_candidate_tree(
                temp=recovery_temp,
                source=source,
                output=output_abs,
                workspace=workspace_abs,
                model_identity=identity,
                files=files,
                plan=plan,
                workspace_snapshot=initial_workspace,
                report_run_count=report_run_count,
                reused=report_reused,
                calls_in_final_run=report_calls,
                prompt_profile_hash=prompt_profile_hash,
            )
            _validate_intended_output_identity(
                initial_workspace, expected_output
            )
            actual_output = _output_tree_identity(output_abs)
            if actual_output != expected_output:
                raise SafetyError("finalization_output_identity_mismatch")
            _verify_snapshot(source, files)
            _complete_workspace(
                workspace_abs,
                output_identity=actual_output,
            )
            completed = _load_workspace(workspace_abs)
            if completed.job.state != "completed":
                raise SafetyError("workspace_completion_not_persisted")
            return expected_report
        finally:
            if recovery_temp.exists():
                shutil.rmtree(recovery_temp)

    client = client_factory()
    identity = _validated_model_identity(client.exact_model(model), model)
    _verify_snapshot(source, files)

    if initial_workspace is None:
        try:
            create_workspace(
                workspace_abs,
                source_path=str(source),
                output_path=str(output_abs),
                source_tree_sha256=source_tree_hash,
                inventory_sha256=inventory_hash,
                parser_order_version=PARSER_ORDER_VERSION,
                model_tag=model,
                model_digest=identity["digest"],
                prompt_profile_hash=prompt_profile_hash,
                inventory=inventory,
                occurrences=tuple(
                    OccurrenceRow(
                        sequence=item.sequence,
                        relative_path=item.relative_path,
                        line_number=item.line_number,
                        ordinal=item.ordinal,
                        source_span_sha256=item.source_span_sha256,
                    )
                    for item in plan
                ),
            )
        except FileExistsError as exc:
            raise SafetyError("workspace_appeared_before_creation") from exc
        except (WorkspaceError, sqlite3.Error) as exc:
            raise SafetyError(str(exc)) from exc
        initial_workspace = _load_workspace(workspace_abs)
        _validate_workspace_semantics(
            initial_workspace,
            source=source,
            output=output_abs,
            model=model,
            files=files,
            inventory=inventory,
            plan=plan,
            source_tree_hash=source_tree_hash,
            inventory_hash=inventory_hash,
            prompt_profile_hash=prompt_profile_hash,
        )
        reused = 0
    elif identity["digest"] != initial_workspace.job.model_digest:
        raise SafetyError("workspace_model_digest_drift")
    _verify_snapshot(source, files)

    calls_in_final_run = 0
    plan_by_sequence = {item.sequence: item for item in plan}
    translating = initial_workspace.job.finalization_state == "none"
    if translating:
        try:
            with WorkspaceWriter(workspace_abs) as writer:
                if resume:
                    writer.start_resume_run()
                for row in initial_workspace.occurrences:
                    if row.state != "pending":
                        continue
                    item = plan_by_sequence[row.sequence]
                    calls_in_final_run += 1
                    try:
                        result = client.translate(
                            tag=model, text=item.entry.model_text()
                        )
                        restored = item.entry.restore_translation(result)
                        if (
                            restored.encode("utf-8")
                            == item.entry.value.encode("utf-8")
                        ):
                            state = "accepted_unchanged"
                            saved_result = None
                        else:
                            state = "accepted_changed"
                            saved_result = result
                        writer.checkpoint(
                            item.sequence,
                            state=state,
                            model_result=saved_result,
                            error_code=None,
                        )
                    except OllamaResultError:
                        writer.checkpoint(
                            item.sequence,
                            state="model_fallback",
                            model_result=None,
                            error_code="model_result_invalid",
                        )
                    except ValueError:
                        writer.checkpoint(
                            item.sequence,
                            state="model_fallback",
                            model_result=None,
                            error_code="renderer_validation_failed",
                        )
        except (WorkspaceError, sqlite3.Error) as exc:
            raise SafetyError(str(exc)) from exc

    completed_workspace = _load_workspace(workspace_abs)
    _validate_workspace_semantics(
        completed_workspace,
        source=source,
        output=output_abs,
        model=model,
        files=files,
        inventory=inventory,
        plan=plan,
        source_tree_hash=source_tree_hash,
        inventory_hash=inventory_hash,
        prompt_profile_hash=prompt_profile_hash,
    )
    if any(row.state == "pending" for row in completed_workspace.occurrences):
        raise SafetyError("workspace_pending_occurrences_remain")

    final_files = _snapshot(source)
    if _snapshot_identity(final_files) != _snapshot_identity(files):
        raise SafetyError("source_generation_changed")
    (
        final_inventory,
        final_plan,
        final_source_tree_hash,
        final_inventory_hash,
    ) = _workspace_inputs(final_files)
    _validate_workspace_semantics(
        completed_workspace,
        source=source,
        output=output_abs,
        model=model,
        files=final_files,
        inventory=final_inventory,
        plan=final_plan,
        source_tree_hash=final_source_tree_hash,
        inventory_hash=final_inventory_hash,
        prompt_profile_hash=prompt_profile_hash,
    )

    if completed_workspace.job.finalization_state == "intent":
        report_run_count = completed_workspace.job.report_run_count
        report_reused = completed_workspace.job.report_reused_count
        report_calls = completed_workspace.job.report_calls_count
        if (
            report_run_count is None
            or report_reused is None
            or report_calls is None
        ):
            raise SafetyError("workspace_finalization_report_counters_missing")
    else:
        report_run_count = completed_workspace.job.run_count
        report_reused = reused
        report_calls = calls_in_final_run

    temp = Path(
        tempfile.mkdtemp(prefix=f".{output_abs.name}.tmp-", dir=output_abs.parent)
    )
    try:
        report, output_identity = _build_workspace_candidate_tree(
            temp=temp,
            source=source,
            output=output_abs,
            workspace=workspace_abs,
            model_identity=identity,
            files=final_files,
            plan=final_plan,
            workspace_snapshot=completed_workspace,
            report_run_count=report_run_count,
            reused=report_reused,
            calls_in_final_run=report_calls,
            prompt_profile_hash=prompt_profile_hash,
        )
        _verify_snapshot(source, final_files)
        final_identity = _validated_model_identity(
            client.exact_model(model), model
        )
        if final_identity != identity:
            raise SafetyError("model_identity_changed")
        _verify_snapshot(source, final_files)

        if completed_workspace.job.finalization_state == "none":
            try:
                set_finalization_intent(
                    workspace_abs,
                    output_tree_sha256=output_identity.sha256,
                    output_file_count=output_identity.file_count,
                    output_directory_count=output_identity.directory_count,
                    report_run_count=report_run_count,
                    report_reused_count=report_reused,
                    report_calls_count=report_calls,
                )
            except (WorkspaceError, sqlite3.Error) as exc:
                raise SafetyError(str(exc)) from exc
            intent_workspace = _load_workspace(workspace_abs)
            _validate_intended_output_identity(
                intent_workspace, output_identity
            )
        else:
            _validate_intended_output_identity(
                completed_workspace, output_identity
            )

        _verify_snapshot(source, final_files)
        _require_output_absent(output_abs)
        try:
            atomic_publish_directory_no_replace(temp, output_abs)
        except DestinationExistsError as exc:
            raise SafetyError("output_appeared_before_publication") from exc
        except AtomicPublicationUnavailable as exc:
            raise SafetyError("atomic_no_replace_unavailable") from exc
        _complete_workspace(
            workspace_abs,
            output_identity=output_identity,
        )
    except BaseException:
        if temp.exists():
            shutil.rmtree(temp)
        raise
    return report


def _workspace_inputs(
    files: list[SourceFile],
) -> tuple[
    tuple[InventoryRow, ...],
    tuple[PlannedOccurrence, ...],
    str,
    str,
]:
    inventory: list[InventoryRow] = []
    plan: list[PlannedOccurrence] = []
    for file_sequence, source_file in enumerate(files):
        parsed = source_file.parsed
        if source_file.error is not None:
            parse_status = "skipped"
            occurrence_count = unsupported_count = 0
        elif parsed is not None and parsed.is_english:
            parse_status = "english"
            occurrence_count = len(parsed.entries)
            unsupported_count = len(parsed.diagnostics)
            relative_path = source_file.relative.as_posix()
            for ordinal, entry in enumerate(parsed.entries):
                plan.append(
                    PlannedOccurrence(
                        sequence=len(plan),
                        relative_path=relative_path,
                        line_number=entry.line_index + 1,
                        ordinal=ordinal,
                        source_span_sha256=hashlib.sha256(
                            entry.value.encode("utf-8")
                        ).hexdigest(),
                        entry=entry,
                    )
                )
        else:
            parse_status = "non_english"
            occurrence_count = unsupported_count = 0
        inventory.append(
            InventoryRow(
                sequence=file_sequence,
                relative_path=source_file.relative.as_posix(),
                sha256=source_file.sha256,
                byte_count=len(source_file.data),
                parse_status=parse_status,
                occurrence_count=occurrence_count,
                unsupported_count=unsupported_count,
            )
        )
    source_tree_hash = _tree_hash(
        [(item.relative, item.data) for item in files]
    )
    inventory_payload = [
        {
            "sequence": row.sequence,
            "relative_path": row.relative_path,
            "sha256": row.sha256,
            "byte_count": row.byte_count,
            "parse_status": row.parse_status,
            "occurrence_count": row.occurrence_count,
            "unsupported_count": row.unsupported_count,
        }
        for row in inventory
    ]
    inventory_hash = hashlib.sha256(
        json.dumps(
            inventory_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return tuple(inventory), tuple(plan), source_tree_hash, inventory_hash


def _validate_workspace_semantics(
    snapshot: WorkspaceSnapshot,
    *,
    source: Path,
    output: Path,
    model: str,
    files: list[SourceFile],
    inventory: tuple[InventoryRow, ...],
    plan: tuple[PlannedOccurrence, ...],
    source_tree_hash: str,
    inventory_hash: str,
    prompt_profile_hash: str,
) -> None:
    job = snapshot.job
    expected_job = {
        "source_path": str(source),
        "output_path": str(output),
        "source_tree_sha256": source_tree_hash,
        "inventory_sha256": inventory_hash,
        "parser_order_version": PARSER_ORDER_VERSION,
        "model_tag": model,
        "prompt_profile_hash": prompt_profile_hash,
        "occurrence_count": len(plan),
    }
    for field, expected in expected_job.items():
        if getattr(job, field) != expected:
            raise SafetyError(f"workspace_{field}_drift")
    if snapshot.inventory != inventory:
        raise SafetyError("workspace_source_inventory_drift")
    if len(snapshot.occurrences) != len(plan):
        raise SafetyError("workspace_occurrence_count_drift")

    for row, item in zip(snapshot.occurrences, plan):
        expected_identity = (
            item.sequence,
            item.relative_path,
            item.line_number,
            item.ordinal,
            item.source_span_sha256,
        )
        actual_identity = (
            row.sequence,
            row.relative_path,
            row.line_number,
            row.ordinal,
            row.source_span_sha256,
        )
        if actual_identity != expected_identity:
            raise SafetyError("workspace_occurrence_identity_drift")
        if row.state == "accepted_changed":
            if row.model_result is None:
                raise SafetyError("workspace_saved_result_missing")
            try:
                restored = item.entry.restore_translation(row.model_result)
            except ValueError as exc:
                raise SafetyError(
                    "workspace_saved_translation_invalid"
                ) from exc
            unchanged = (
                restored.encode("utf-8") == item.entry.value.encode("utf-8")
            )
            expected_state = (
                "accepted_unchanged" if unchanged else "accepted_changed"
            )
            if row.state != expected_state:
                raise SafetyError("workspace_saved_result_state_mismatch")
        elif row.state == "accepted_unchanged":
            if row.model_result is not None:
                raise SafetyError("workspace_unchanged_result_must_be_absent")
        elif row.state == "model_fallback":
            if not row.error_code:
                raise SafetyError("workspace_fallback_reason_missing")
        elif row.state != "pending":
            raise SafetyError("workspace_occurrence_state_invalid")

    expected_tree_hash = _tree_hash(
        [(item.relative, item.data) for item in files]
    )
    if expected_tree_hash != source_tree_hash:
        raise SafetyError("workspace_source_tree_hash_internal_mismatch")


def _workspace_translation_report(
    *,
    source: Path,
    output: Path,
    workspace: Path,
    model_identity: dict[str, str],
    files: list[SourceFile],
    workspace_snapshot: WorkspaceSnapshot,
    report_run_count: int,
    reused: int,
    calls_in_final_run: int,
    prompt_profile_hash: str,
) -> dict[str, object]:
    report = _translation_report(source, files)
    report["schema_version"] = 3
    report["output"] = str(output)
    report["dry_run"] = False
    report["max_occurrences_per_file"] = None
    report["model"] = model_identity
    counts = report["counts"]
    assert isinstance(counts, dict)
    accepted = sum(
        row.state in {"accepted_changed", "accepted_unchanged"}
        for row in workspace_snapshot.occurrences
    )
    unchanged = sum(
        row.state == "accepted_unchanged"
        for row in workspace_snapshot.occurrences
    )
    model_fallback = sum(
        row.state == "model_fallback"
        for row in workspace_snapshot.occurrences
    )
    pending = sum(
        row.state == "pending" for row in workspace_snapshot.occurrences
    )
    unsupported = sum(
        len(item.parsed.diagnostics)
        for item in files
        if item.parsed is not None and item.parsed.is_english
    )
    counts["planned_translation_occurrences"] = len(
        workspace_snapshot.occurrences
    )
    counts["translated_occurrences"] = accepted
    counts["unchanged_accepted_occurrences"] = unchanged
    counts["fallback_occurrences"] = unsupported + model_fallback
    counts["deferred_occurrences"] = 0
    counts["total_occurrences"] = counts["occurrences"]
    counts["completed_occurrences"] = counts["occurrences"] - pending
    counts["unsupported_occurrences"] = unsupported
    counts["pending_occurrences"] = pending
    counts["reused_from_workspace_occurrences"] = reused
    counts["calls_in_final_run"] = calls_in_final_run
    counts["total"] = counts["occurrences"]
    counts["completed"] = counts["occurrences"] - pending
    counts["translated"] = accepted
    counts["accepted_unchanged"] = unchanged
    counts["fallback"] = unsupported + model_fallback
    counts["unsupported"] = unsupported
    counts["pending"] = pending
    counts["reused_from_workspace"] = reused
    for row in workspace_snapshot.occurrences:
        if row.state == "model_fallback":
            report["diagnostics"].append(
                {
                    "path": row.relative_path,
                    "line": row.line_number,
                    "code": "translation_fallback",
                    "reason": row.error_code,
                }
            )
    report["resumability"] = {
        "mode": "sqlite_workspace",
        "workspace": str(workspace),
        "workspace_schema_version": 2,
        "parser_order_version": PARSER_ORDER_VERSION,
        "prompt_profile_hash": prompt_profile_hash,
        "finalization_protocol": "intent_then_no_clobber_publish_then_complete_v1",
        "workspace_state_at_report_creation": "in_progress",
        "completion_attested_by_report": False,
        "output_identity_scope": "all_paths_types_and_bytes_including_report",
        "run_count": report_run_count,
        "reused_from_workspace": reused,
        "calls_in_final_run": calls_in_final_run,
        "checkpoint_boundary": "committed_after_each_finished_occurrence",
    }
    return report


def _build_workspace_candidate_tree(
    *,
    temp: Path,
    source: Path,
    output: Path,
    workspace: Path,
    model_identity: dict[str, str],
    files: list[SourceFile],
    plan: tuple[PlannedOccurrence, ...],
    workspace_snapshot: WorkspaceSnapshot,
    report_run_count: int,
    reused: int,
    calls_in_final_run: int,
    prompt_profile_hash: str,
) -> tuple[dict[str, object], OutputTreeIdentity]:
    report = _workspace_translation_report(
        source=source,
        output=output,
        workspace=workspace,
        model_identity=model_identity,
        files=files,
        workspace_snapshot=workspace_snapshot,
        report_run_count=report_run_count,
        reused=reused,
        calls_in_final_run=calls_in_final_run,
        prompt_profile_hash=prompt_profile_hash,
    )
    candidates = _render_workspace_candidates(
        temp,
        files,
        plan,
        workspace_snapshot,
    )
    report["hashes"]["output_localisation_sha256"] = _tree_hash(candidates)
    _validate_count_invariant(report, dry_run=False)
    report["status"] = _translation_status(report, dry_run=False)
    report["editorial_status"] = "human_review_required"
    report["editorially_approved"] = False
    _write_new(
        temp / "translation-report.json",
        (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        ),
    )
    return report, _output_tree_identity(temp)


def _render_workspace_candidates(
    temp: Path,
    files: list[SourceFile],
    plan: tuple[PlannedOccurrence, ...],
    workspace_snapshot: WorkspaceSnapshot,
) -> list[tuple[Path, bytes]]:
    rows = {row.sequence: row for row in workspace_snapshot.occurrences}
    plan_by_path: dict[str, list[PlannedOccurrence]] = {}
    for item in plan:
        plan_by_path.setdefault(item.relative_path, []).append(item)

    candidates: list[tuple[Path, bytes]] = []
    for source_file in files:
        parsed = source_file.parsed
        if parsed is None or not parsed.is_english:
            continue
        replacements: dict[int, str] = {}
        for item in plan_by_path.get(source_file.relative.as_posix(), []):
            row = rows[item.sequence]
            if row.state == "accepted_changed":
                assert row.model_result is not None
                try:
                    replacements[item.entry.line_index] = (
                        item.entry.restore_translation(row.model_result)
                    )
                except ValueError as exc:
                    raise SafetyError(
                        "workspace_saved_translation_invalid"
                    ) from exc
        relative = _candidate_relative(source_file.relative)
        rendered = parsed.render(replacements, russian_header=True)
        target = temp / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_new(target, rendered)
        candidates.append((relative, rendered))
    return candidates


def _output_tree_identity(root: Path) -> OutputTreeIdentity:
    try:
        root_before = root.lstat()
    except FileNotFoundError as exc:
        raise SafetyError("finalization_output_missing") from exc
    if stat.S_ISLNK(root_before.st_mode) or not stat.S_ISDIR(
        root_before.st_mode
    ):
        raise SafetyError("finalization_output_root_not_directory")

    digest = hashlib.sha256()
    digest.update(b"stellaris-mod-translator-output-tree-v1\0")
    _update_output_identity_entry(digest, Path("."), b"D", None)
    directory_count = 1
    file_count = 0

    def fail_walk(error: OSError) -> None:
        raise SafetyError("finalization_output_inventory_failed") from error

    try:
        for current, directories, names in os.walk(
            root, followlinks=False, onerror=fail_walk
        ):
            current_path = Path(current)
            directories.sort()
            names.sort()
            for name in directories:
                path = current_path / name
                value = path.lstat()
                if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(
                    value.st_mode
                ):
                    raise SafetyError(
                        "finalization_output_directory_type_invalid"
                    )
                relative = path.relative_to(root)
                _update_output_identity_entry(
                    digest, relative, b"D", None
                )
                directory_count += 1
            for name in names:
                path = current_path / name
                value = path.lstat()
                if stat.S_ISLNK(value.st_mode):
                    raise SafetyError("finalization_output_symlink")
                if not stat.S_ISREG(value.st_mode):
                    raise SafetyError("finalization_output_special_file")
                if value.st_nlink != 1:
                    raise SafetyError("finalization_output_hardlink")
                relative = path.relative_to(root)
                _hash_output_file(digest, relative, path)
                file_count += 1
    except SafetyError:
        raise
    except OSError as exc:
        raise SafetyError("finalization_output_inventory_failed") from exc

    root_after = root.lstat()
    if (
        root_after.st_dev,
        root_after.st_ino,
        root_after.st_mtime_ns,
    ) != (
        root_before.st_dev,
        root_before.st_ino,
        root_before.st_mtime_ns,
    ):
        raise SafetyError("finalization_output_changed_during_read")
    if file_count < 1:
        raise SafetyError("finalization_output_has_no_files")
    return OutputTreeIdentity(
        sha256=digest.hexdigest(),
        file_count=file_count,
        directory_count=directory_count,
    )


def _update_output_identity_entry(
    digest: object,
    relative: Path,
    kind: bytes,
    byte_count: int | None,
) -> None:
    encoded = os.fsencode(relative.as_posix())
    digest.update(len(encoded).to_bytes(8, "big"))
    digest.update(encoded)
    digest.update(kind)
    if byte_count is not None:
        digest.update(byte_count.to_bytes(8, "big"))


def _hash_output_file(
    digest: object, relative: Path, path: Path
) -> None:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise SafetyError("finalization_output_file_type_invalid")
        _update_output_identity_entry(
            digest, relative, b"F", before.st_size
        )
        bytes_read = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            bytes_read += len(chunk)
            digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if bytes_read != before.st_size or _stat_identity(before) != _stat_identity(
        after
    ):
        raise SafetyError("finalization_output_file_changed_during_read")
    path_after = path.lstat()
    if (
        path_after.st_dev,
        path_after.st_ino,
        path_after.st_size,
        path_after.st_mtime_ns,
        path_after.st_nlink,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_nlink,
    ):
        raise SafetyError("finalization_output_file_replaced_during_read")


def _validate_intended_output_identity(
    snapshot: WorkspaceSnapshot, actual: OutputTreeIdentity
) -> None:
    job = snapshot.job
    if job.finalization_state != "intent":
        raise SafetyError("workspace_finalization_intent_missing")
    if (
        job.output_tree_sha256,
        job.output_file_count,
        job.output_directory_count,
    ) != (
        actual.sha256,
        actual.file_count,
        actual.directory_count,
    ):
        raise SafetyError("finalization_output_identity_mismatch")


def _complete_workspace(
    workspace: Path, *, output_identity: OutputTreeIdentity
) -> None:
    try:
        mark_workspace_completed(
            workspace,
            output_tree_sha256=output_identity.sha256,
            output_file_count=output_identity.file_count,
            output_directory_count=output_identity.directory_count,
        )
    except (WorkspaceError, sqlite3.Error) as exc:
        raise SafetyError(str(exc)) from exc


def _normalized_workspace(path: Path, *, resume: bool) -> Path:
    lexical = path.absolute()
    if path.is_symlink():
        raise SafetyError("workspace_symlink")
    if resume:
        try:
            return lexical.resolve(strict=True)
        except FileNotFoundError as exc:
            raise SafetyError("resume_requires_existing_workspace") from exc
    if lexical.exists() or lexical.is_symlink():
        raise SafetyError("first_run_requires_absent_workspace")
    parent = lexical.parent.resolve(strict=True)
    if not parent.is_dir():
        raise SafetyError("workspace_parent_not_directory")
    return parent / lexical.name


def _normalized_output(source: Path, output: Path) -> Path:
    lexical = output.absolute()
    resolved = lexical.resolve(strict=False)
    if resolved == source or source in resolved.parents or resolved in source.parents:
        raise SafetyError("source_output_overlap")
    parent = lexical.parent.resolve(strict=True)
    if not parent.is_dir():
        raise SafetyError("output_parent_not_directory")
    return parent / lexical.name


def _require_output_absent(output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise SafetyError("output_must_not_exist")


def _validate_workspace_path_relationships(
    source: Path, output: Path, workspace: Path
) -> None:
    if _paths_overlap(source, workspace):
        raise SafetyError("source_workspace_overlap")
    if _paths_overlap(output, workspace):
        raise SafetyError("workspace_output_overlap")


def _paths_overlap(first: Path, second: Path) -> bool:
    return (
        first == second
        or first in second.parents
        or second in first.parents
    )


def _load_workspace(path: Path) -> WorkspaceSnapshot:
    try:
        return load_workspace(path)
    except WorkspaceError as exc:
        raise SafetyError(str(exc)) from exc


def _snapshot_identity(
    files: list[SourceFile],
) -> list[tuple[Path, str, tuple[int, int, int, int]]]:
    return [
        (item.relative, item.sha256, item.stat_identity) for item in files
    ]


def _validate_occurrence_limit(value: int | None) -> None:
    if value is None:
        return
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
        or value > 100
    ):
        raise SafetyError(
            "max_occurrences_per_file_must_be_integer_from_1_to_100"
        )


def _selected_entries(
    parsed: ParsedFile, max_occurrences_per_file: int | None
) -> tuple[Entry, ...]:
    if max_occurrences_per_file is None:
        return parsed.entries
    return parsed.entries[:max_occurrences_per_file]


def _translation_plan_counts(
    files: list[SourceFile], max_occurrences_per_file: int | None
) -> tuple[int, int]:
    planned = deferred = 0
    for source_file in files:
        parsed = source_file.parsed
        if parsed is None or not parsed.is_english:
            continue
        selected = len(_selected_entries(parsed, max_occurrences_per_file))
        planned += selected
        deferred += len(parsed.entries) - selected
    return planned, deferred


def _validate_count_invariant(
    report: dict[str, object], *, dry_run: bool
) -> None:
    counts = report["counts"]
    assert isinstance(counts, dict)
    unchanged = counts["unchanged_accepted_occurrences"]
    translated = counts["translated_occurrences"]
    if (
        not isinstance(unchanged, int)
        or isinstance(unchanged, bool)
        or not isinstance(translated, int)
        or isinstance(translated, bool)
        or unchanged < 0
        or unchanged > translated
        or (dry_run and (translated != 0 or unchanged != 0))
    ):
        raise SafetyError("unchanged_accepted_count_invariant_failed")
    if dry_run:
        accounted = (
            counts["planned_translation_occurrences"]
            + counts["fallback_occurrences"]
            + counts["deferred_occurrences"]
        )
    else:
        accounted = (
            counts["translated_occurrences"]
            + counts["fallback_occurrences"]
            + counts["deferred_occurrences"]
        )
    if counts["occurrences"] != accounted:
        raise SafetyError("occurrence_count_invariant_failed")


def _translation_status(
    report: dict[str, object], *, dry_run: bool
) -> str:
    counts = report["counts"]
    assert isinstance(counts, dict)
    is_partial = any(
        counts[name]
        for name in (
            "fallback_occurrences",
            "deferred_occurrences",
            "skipped_files",
        )
    )
    if is_partial:
        return "dry_run_partial" if dry_run else "technical_safe_partial"
    if counts["occurrences"] == 0:
        return (
            "dry_run_no_translatable_content"
            if dry_run
            else "no_translatable_content"
        )
    return "dry_run_plan" if dry_run else "technical_safe"


def _validated_source(path: Path) -> Path:
    lexical = path.absolute()
    if path.is_symlink():
        raise SafetyError("source_mod_symlink")
    resolved = lexical.resolve(strict=True)
    if not resolved.is_dir():
        raise SafetyError("source_mod_not_directory")
    return resolved


def _validated_output(source: Path, output: Path) -> Path:
    lexical = output.absolute()
    resolved = lexical.resolve(strict=False)
    if resolved == source or source in resolved.parents or resolved in source.parents:
        raise SafetyError("source_output_overlap")
    if output.exists() or output.is_symlink():
        raise SafetyError("output_must_not_exist")
    parent = lexical.parent.resolve(strict=True)
    resolved = parent / lexical.name
    return resolved


def _snapshot(source: Path) -> list[SourceFile]:
    localisation = source / "localisation"
    if not localisation.exists():
        return []
    if localisation.is_symlink() or not localisation.is_dir():
        raise SafetyError("unsafe_localisation_root")
    results: list[SourceFile] = []
    def fail_walk(error: OSError) -> None:
        raise SafetyError("localisation_inventory_failed") from error

    for root, dirs, names in os.walk(
        localisation, followlinks=False, onerror=fail_walk
    ):
        root_path = Path(root)
        for dirname in dirs:
            if (root_path / dirname).is_symlink():
                raise SafetyError("symlink_in_localisation")
        for name in sorted(names):
            path = root_path / name
            if path.is_symlink():
                raise SafetyError("symlink_in_localisation")
            if path.suffix.lower() != ".yml":
                continue
            relative = path.relative_to(source)
            flags = (
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0)
            )
            descriptor = os.open(path, flags)
            try:
                before = os.fstat(descriptor)
                if not stat.S_ISREG(before.st_mode):
                    raise SafetyError("unsafe_localisation_file")
                chunks: list[bytes] = []
                while chunk := os.read(descriptor, 1024 * 1024):
                    chunks.append(chunk)
                after = os.fstat(descriptor)
            finally:
                os.close(descriptor)
            data = b"".join(chunks)
            identity_before = _stat_identity(before)
            identity_after = _stat_identity(after)
            if identity_before != identity_after:
                raise SafetyError("source_changed_during_read")
            digest = hashlib.sha256(data).hexdigest()
            if _is_replace_layer(relative):
                parsed = None
                error = "replace_layer_unsupported"
            else:
                try:
                    parsed = parse_localisation(data)
                    error = None
                except ParseError as exc:
                    parsed = None
                    error = str(exc)
            results.append(
                SourceFile(
                    relative=relative,
                    data=data,
                    sha256=digest,
                    stat_identity=identity_after,
                    parsed=parsed,
                    error=error,
                )
            )
    return sorted(results, key=lambda item: item.relative.as_posix())


def _verify_snapshot(source: Path, files: list[SourceFile]) -> None:
    current = _snapshot(source)
    expected = [
        (item.relative, item.sha256, item.stat_identity) for item in files
    ]
    actual = [
        (item.relative, item.sha256, item.stat_identity) for item in current
    ]
    if actual != expected:
        raise SafetyError("source_generation_changed")


def _inspect_report(source: Path, files: list[SourceFile]) -> dict[str, object]:
    diagnostics: list[dict[str, object]] = []
    english_files = occurrences = fallback = skipped = 0
    hash_inputs: list[tuple[Path, bytes]] = []
    for item in files:
        hash_inputs.append((item.relative, item.data))
        if item.error:
            skipped += 1
            if item.error == "replace_layer_unsupported":
                diagnostics.append(
                    {
                        "path": item.relative.as_posix(),
                        "code": "replace_layer_unsupported",
                    }
                )
            else:
                diagnostics.append(
                    {
                        "path": item.relative.as_posix(),
                        "code": "file_skipped",
                        "reason": item.error,
                    }
                )
        elif item.parsed and item.parsed.is_english:
            english_files += 1
            occurrences += len(item.parsed.entries) + len(item.parsed.diagnostics)
            fallback += len(item.parsed.diagnostics)
            for diagnostic in item.parsed.diagnostics:
                diagnostics.append(
                    {"path": item.relative.as_posix(), **diagnostic}
                )
    return {
        "schema_version": 1,
        "source": str(source),
        "counts": {
            "discovered_yml_files": len(files),
            "english_files": english_files,
            "occurrences": occurrences,
            "translated_occurrences": 0,
            "fallback_occurrences": fallback,
            "blocked_occurrences": 0,
            "skipped_files": skipped,
        },
        "hashes": {
            "source_localisation_sha256": _tree_hash(hash_inputs),
            "output_localisation_sha256": None,
        },
        "diagnostics": diagnostics,
    }


def _translation_report(
    source: Path, files: list[SourceFile]
) -> dict[str, object]:
    inspect_report = _inspect_report(source, files)
    inspect_counts = inspect_report["counts"]
    assert isinstance(inspect_counts, dict)
    return {
        **inspect_report,
        "schema_version": 2,
        "counts": {
            "discovered_yml_files": inspect_counts["discovered_yml_files"],
            "english_files": inspect_counts["english_files"],
            "occurrences": inspect_counts["occurrences"],
            "planned_translation_occurrences": 0,
            "translated_occurrences": 0,
            "unchanged_accepted_occurrences": 0,
            "fallback_occurrences": inspect_counts["fallback_occurrences"],
            "deferred_occurrences": 0,
            "skipped_files": inspect_counts["skipped_files"],
        },
    }


def _candidate_relative(relative: Path) -> Path:
    parts = list(relative.parts)
    if not parts or parts[0] != "localisation":
        raise SafetyError("unexpected_source_path")
    tail = parts[1:]
    if tail and tail[0].lower() == "english":
        tail = tail[1:]
    if tail and tail[0].lower() == "replace":
        raise SafetyError("replace_layer_unsupported")
    filename = tail[-1]
    if filename.endswith("_l_english.yml"):
        filename = filename[: -len("_l_english.yml")] + "_l_russian.yml"
    tail[-1] = filename
    candidate = Path("localisation", "russian", *tail)
    if ".." in candidate.parts:
        raise SafetyError("path_traversal")
    return candidate


def _is_replace_layer(relative: Path) -> bool:
    parts = relative.parts
    return (
        len(parts) >= 3
        and parts[0] == "localisation"
        and parts[1].lower() == "replace"
    ) or (
        len(parts) >= 4
        and parts[0] == "localisation"
        and parts[1].lower() == "english"
        and parts[2].lower() == "replace"
    )


def _tree_hash(items: list[tuple[Path, bytes]]) -> str:
    digest = hashlib.sha256()
    for relative, data in sorted(items, key=lambda item: item[0].as_posix()):
        encoded = relative.as_posix().encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _write_new(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def _validated_model_identity(
    identity: object, requested_tag: str
) -> dict[str, str]:
    if (
        not isinstance(identity, dict)
        or identity.get("tag") != requested_tag
        or not isinstance(identity.get("digest"), str)
        or not identity["digest"]
    ):
        raise OllamaSystemError("invalid exact model identity")
    return {"tag": requested_tag, "digest": identity["digest"]}


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
