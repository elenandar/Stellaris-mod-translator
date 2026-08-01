"""Private offline blind A/B review pack for bounded contextual pilots."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Callable, Iterable

from . import engine, ollama, package_reviewed_mod, review
from .engine import SafetyError, SourceFile, _write_new
from .ollama import OllamaClient, OllamaResultError
from .parser import ParseError, parse_localisation
from .publication import (
    AtomicPublicationUnavailable,
    DestinationExistsError,
    atomic_publish_directory_no_replace,
)


AB_PACK_SCHEMA_VERSION = 2
AB_MAPPING_SCHEMA_VERSION = 2
AB_STORAGE_SCHEMA_VERSION = 2
AB_DECISIONS_SCHEMA_VERSION = 2
AB_QUALITY_STATUS = "HUMAN_REVIEW_REQUIRED"
AB_CHOICES = ("A better", "B better", "tie", "both bad")
MAX_AB_ENTRIES = 100
MAX_AB_PILOT_ENTRIES = 23
MAX_AB_TEXT_BYTES = 1024 * 1024


@dataclass(frozen=True, repr=False)
class ABReviewEntry:
    occurrence_identity_sha256: str
    source: str
    baseline: str
    contextual: str
    reviewed_reference: str | None = None


@dataclass(frozen=True, repr=False)
class _BaselinePilotInputs:
    source: Path
    candidate: Path
    source_files: list[SourceFile]
    candidate_files: list[SourceFile]
    candidate_inventory: tuple[tuple[str, ...], tuple[str, ...]]
    report_file: review.StableFile
    report: dict[str, object]
    source_localisation_sha256: str
    candidate_localisation_sha256: str


def run_context_ab_pilot(
    source_mod: Path,
    vanilla_memory_database: Path,
    baseline_candidate: Path,
    baseline_candidate_report_sha256: str,
    reviewed_candidate: Path,
    reviewed_application_report_sha256: str,
    output: Path,
    model: str,
    *,
    evaluation_root: Path,
    vanilla_memory_database_sha256: str,
    vanilla_memory_logical_digest: str,
    vanilla_memory_game_version: str,
    expected_entries: int = 23,
    client_factory: Callable[[], OllamaClient] = OllamaClient,
) -> dict[str, object]:
    """Run only eligible A/B calls and publish an aggregate-described pack."""
    if (
        isinstance(expected_entries, bool)
        or not isinstance(expected_entries, int)
        or expected_entries < 1
        or expected_entries > MAX_AB_PILOT_ENTRIES
    ):
        raise SafetyError("ab_expected_entry_count_invalid")
    report_pin = _sha256(
        baseline_candidate_report_sha256,
        "ab_baseline_report_pin_invalid",
    )
    application_pin = _sha256(
        reviewed_application_report_sha256,
        "ab_reviewed_application_pin_invalid",
    )
    source = review._validated_input_root(source_mod, "source")
    baseline = review._validated_input_root(
        baseline_candidate, "candidate"
    )
    if review._paths_overlap(source, baseline):
        raise SafetyError("ab_source_candidate_overlap")
    reviewed_root = package_reviewed_mod._validated_candidate_root(
        reviewed_candidate
    )
    configuration = engine._validated_translation_context_configuration(
        context_policy="exact_context_v1",
        database=vanilla_memory_database,
        database_sha256=vanilla_memory_database_sha256,
        logical_digest=vanilla_memory_logical_digest,
        game_version=vanilla_memory_game_version,
    )
    assert configuration is not None
    memory_root = review._validated_input_root(
        configuration.database.parent, "memory"
    )
    output_abs = _validated_pilot_output(
        output,
        evaluation_root=evaluation_root,
        protected_roots=(
            ("source", source),
            ("baseline", baseline),
            ("reviewed", reviewed_root),
            ("memory", memory_root),
        ),
    )
    baseline_inputs = _validated_baseline_pilot_inputs(
        source, baseline, report_pin
    )
    _, reviewed_snapshot, reviewed_values = (
        _validated_reviewed_values(
            source,
            baseline,
            baseline_inputs,
            reviewed_root,
            application_pin,
        )
    )
    inventory, plan, source_tree_hash, inventory_hash = (
        engine._workspace_inputs(baseline_inputs.source_files)
    )
    del inventory
    context_runtime = engine._prepare_translation_context(
        configuration,
        files=baseline_inputs.source_files,
        plan=plan,
        source_tree_hash=source_tree_hash,
        inventory_hash=inventory_hash,
    )
    assert context_runtime is not None
    eligible_sequences = tuple(
        item.sequence
        for item, result in zip(plan, context_runtime.batch.results)
        if result.status in {"exact_key_context", "exact_text_consensus"}
    )
    if len(eligible_sequences) != expected_entries:
        raise SafetyError("ab_eligible_entry_count_mismatch")
    baseline_values = _available_candidate_values(
        baseline_inputs.source_files,
        baseline_inputs.candidate_files,
    )
    if len(baseline_values) != len(plan) or len(reviewed_values) != len(plan):
        raise SafetyError("ab_candidate_alignment_mismatch")
    if any(
        baseline_values[sequence] is None
        or reviewed_values[sequence] is None
        for sequence in eligible_sequences
    ):
        raise SafetyError("ab_eligible_candidate_value_missing")

    engine._verify_snapshot(source, baseline_inputs.source_files)
    _verify_baseline_pilot_inputs(baseline_inputs)
    package_reviewed_mod._verify_reviewed_candidate_snapshot(
        reviewed_snapshot
    )
    engine._verify_translation_context_identity(context_runtime)
    client = client_factory()
    identity = engine._validated_model_identity(
        client.exact_model(model), model
    )
    historical_model = baseline_inputs.report.get("model")
    if (
        not isinstance(historical_model, dict)
        or set(historical_model) != {"tag", "digest"}
        or historical_model.get("tag") != model
        or not isinstance(historical_model.get("digest"), str)
    ):
        raise SafetyError("ab_baseline_model_identity_invalid")
    reuse_baseline = _baseline_is_exact_compatible(
        baseline_inputs.report,
        historical_model=historical_model,
        current_identity=identity,
        requested_model=model,
    )

    pack_entries: list[ABReviewEntry] = []
    baseline_calls = 0
    contextual_calls = 0
    invalid_baseline_outputs = 0
    invalid_context_outputs = 0
    protected_atom_mismatches = 0
    for sequence in eligible_sequences:
        item = plan[sequence]
        source_text = item.entry.model_text()
        if reuse_baseline:
            baseline_value = baseline_values[sequence]
            assert baseline_value is not None
        else:
            baseline_calls += 1
            try:
                baseline_result = client.translate(
                    tag=model, text=source_text
                )
                baseline_value = item.entry.restore_translation(
                    baseline_result
                )
            except OllamaResultError:
                invalid_baseline_outputs += 1
                baseline_value = item.entry.value
            except ValueError as exc:
                invalid_baseline_outputs += 1
                if _is_protected_atom_mismatch(exc):
                    protected_atom_mismatches += 1
                baseline_value = item.entry.value

        reference_text = engine._context_reference_text(
            context_runtime, sequence
        )
        if reference_text is None:
            raise SafetyError("ab_eligible_reference_missing")
        contextual_calls += 1
        try:
            contextual_result = client.translate_with_context(
                tag=model,
                text=source_text,
                reference_text=reference_text,
            )
            contextual_value = item.entry.restore_translation(
                contextual_result
            )
        except OllamaResultError:
            invalid_context_outputs += 1
            contextual_value = item.entry.value
        except ValueError as exc:
            invalid_context_outputs += 1
            if _is_protected_atom_mismatch(exc):
                protected_atom_mismatches += 1
            contextual_value = item.entry.value

        occurrence_identity = hashlib.sha256(
            _canonical_json(
                {
                    "context_binding_sha256": (
                        context_runtime.binding_sha256
                    ),
                    "sequence": item.sequence,
                    "source_span_sha256": item.source_span_sha256,
                }
            )
        ).hexdigest()
        pack_entries.append(
            ABReviewEntry(
                occurrence_identity_sha256=occurrence_identity,
                source=item.entry.value,
                baseline=baseline_value,
                contextual=contextual_value,
                reviewed_reference=reviewed_values[sequence],
            )
        )

    final_identity = engine._validated_model_identity(
        client.exact_model(model), model
    )
    if final_identity != identity:
        raise SafetyError("ab_model_identity_changed")

    def pre_publish_check() -> None:
        engine._verify_snapshot(source, baseline_inputs.source_files)
        _verify_baseline_pilot_inputs(baseline_inputs)
        package_reviewed_mod._verify_reviewed_candidate_snapshot(
            reviewed_snapshot
        )
        engine._verify_translation_context_identity(context_runtime)
        current = engine._validated_model_identity(
            client.exact_model(model), model
        )
        if current != identity:
            raise SafetyError("ab_model_identity_changed")

    pack_report = build_context_ab_review_pack(
        pack_entries,
        output_abs,
        context_binding_sha256=context_runtime.binding_sha256,
        source_localisation_sha256=source_tree_hash,
        model_digest=identity["digest"],
        pre_publish_check=pre_publish_check,
    )
    return {
        **pack_report,
        "queries_total": len(plan),
        "eligible_context": len(eligible_sequences),
        "context_prompts": contextual_calls,
        "legacy_prompts_changed_outside_eligible": 0,
        "baseline_calls": baseline_calls,
        "ollama_calls": baseline_calls + contextual_calls,
        "invalid_baseline_outputs": invalid_baseline_outputs,
        "invalid_context_outputs": invalid_context_outputs,
        "protected_atom_mismatches": protected_atom_mismatches,
        "baseline_reused": reuse_baseline,
        "source_mutations": 0,
        "memory_mutations": 0,
        "candidate_mutations": 0,
        "writes_confined_to_authorized_evaluation_root": True,
        "external_network_requests": 0,
    }


def _baseline_is_exact_compatible(
    report: dict[str, object],
    *,
    historical_model: dict[str, object],
    current_identity: dict[str, str],
    requested_model: str,
) -> bool:
    resumability = report.get("resumability")
    if not isinstance(resumability, dict):
        raise SafetyError("ab_baseline_resumability_invalid")
    prompt_profile_hash = resumability.get("prompt_profile_hash")
    if not isinstance(prompt_profile_hash, str):
        raise SafetyError("ab_baseline_prompt_profile_hash_invalid")
    return (
        historical_model == current_identity
        and historical_model.get("tag") == requested_model
        and prompt_profile_hash == ollama.translation_prompt_profile_hash()
    )


def _is_protected_atom_mismatch(error: ValueError) -> bool:
    return str(error) in {
        "foreign protected token",
        "protected token missing or duplicated",
        "protected token order changed",
    }


def _validated_baseline_pilot_inputs(
    source: Path, candidate: Path, report_pin: str
) -> _BaselinePilotInputs:
    source_files = engine._snapshot(source)
    engine._validate_candidate_path_mappings(source_files)
    candidate_files = engine._snapshot(candidate)
    report_file = review._read_stable_file(
        candidate / "translation-report.json", "candidate_report"
    )
    if report_file.sha256 != report_pin:
        raise SafetyError("ab_baseline_report_identity_mismatch")
    report = review._load_report(report_file.data)
    source_hash = engine._tree_hash(
        [(item.relative, item.data) for item in source_files]
    )
    candidate_hash = engine._tree_hash(
        [(item.relative, item.data) for item in candidate_files]
    )
    review._validate_full_report_header(
        report, source, candidate, source_hash, candidate_hash
    )
    counts = report.get("counts")
    if not isinstance(counts, dict):
        raise SafetyError("ab_baseline_report_counts_invalid")
    required_counts = (
        "accepted_unchanged",
        "deferred_occurrences",
        "discovered_yml_files",
        "english_files",
        "fallback_occurrences",
        "planned_translation_occurrences",
        "skipped_files",
        "translated_occurrences",
        "unsupported",
    )
    if any(
        isinstance(counts.get(name), bool)
        or not isinstance(counts.get(name), int)
        or counts[name] < 0
        for name in required_counts
    ):
        raise SafetyError("ab_baseline_report_counts_invalid")
    model_fallback = counts["fallback_occurrences"] - counts["unsupported"]
    if model_fallback < 0:
        raise SafetyError("ab_baseline_report_counts_invalid")
    review._validate_full_report_counts(
        counts,
        selected_count=counts["planned_translation_occurrences"],
        accepted_count=counts["translated_occurrences"],
        accepted_unchanged=counts["accepted_unchanged"],
        model_fallback=model_fallback,
        parser_unsupported=counts["unsupported"],
        discovered=counts["discovered_yml_files"],
        english_files=counts["english_files"],
        skipped_files=counts["skipped_files"],
        resumability=report["resumability"],
        report_status=report["status"],
    )
    inventory = review._candidate_inventory(candidate)
    actual_files, actual_directories = inventory
    expected_files = {
        item.relative.as_posix() for item in candidate_files
    } | {"translation-report.json"}
    expected_directories = {"localisation", "localisation/russian"}
    for item in candidate_files:
        parent = item.relative.parent
        while parent != Path("."):
            expected_directories.add(parent.as_posix())
            parent = parent.parent
    if (
        set(actual_files) != expected_files
        or set(actual_directories) != expected_directories
    ):
        raise SafetyError("ab_baseline_candidate_inventory_invalid")
    values = _available_candidate_values(source_files, candidate_files)
    legacy_skipped_files = _legacy_skipped_file_count(
        source_files, candidate_files
    )
    if (
        legacy_skipped_files != counts["skipped_files"]
        or sum(item is not None for item in values)
        != counts["planned_translation_occurrences"]
    ):
        raise SafetyError("ab_baseline_legacy_skip_mismatch")
    return _BaselinePilotInputs(
        source=source,
        candidate=candidate,
        source_files=source_files,
        candidate_files=candidate_files,
        candidate_inventory=inventory,
        report_file=report_file,
        report=report,
        source_localisation_sha256=source_hash,
        candidate_localisation_sha256=candidate_hash,
    )


def _legacy_skipped_file_count(
    source_files: list[SourceFile], candidate_files: list[SourceFile]
) -> int:
    candidate_paths = {
        item.relative.as_posix() for item in candidate_files
    }
    skipped = 0
    for item in source_files:
        if item.error is not None:
            skipped += 1
        elif item.parsed is not None and item.parsed.is_english:
            candidate_path = engine._candidate_relative(
                item.relative
            ).as_posix()
            if candidate_path not in candidate_paths:
                skipped += 1
    return skipped


def _verify_baseline_pilot_inputs(inputs: _BaselinePilotInputs) -> None:
    engine._verify_snapshot(inputs.source, inputs.source_files)
    engine._verify_snapshot(inputs.candidate, inputs.candidate_files)
    review._verify_stable_file(
        inputs.report_file,
        "candidate_report_generation_changed",
        label="candidate_report",
    )
    if review._candidate_inventory(inputs.candidate) != inputs.candidate_inventory:
        raise SafetyError("candidate_generation_changed")


def _validated_reviewed_values(
    source: Path,
    baseline: Path,
    baseline_inputs: _BaselinePilotInputs,
    reviewed_candidate: Path,
    application_pin: str,
) -> tuple[
    Path,
    package_reviewed_mod.ReviewedCandidateSnapshot,
    tuple[str | None, ...],
]:
    root = package_reviewed_mod._validated_candidate_root(
        reviewed_candidate
    )
    if review._paths_overlap(source, root) or review._paths_overlap(
        baseline, root
    ):
        raise SafetyError("ab_reviewed_candidate_overlap")
    snapshot = package_reviewed_mod._snapshot_reviewed_candidate(root)
    report_file = package_reviewed_mod._snapshot_file(
        snapshot, Path(package_reviewed_mod.APPLICATION_REPORT_NAME)
    )
    if report_file.sha256 != application_pin:
        raise SafetyError("ab_reviewed_application_pin_mismatch")
    report = package_reviewed_mod._load_application_report(report_file.data)
    package_reviewed_mod._validate_application_report(
        report,
        candidate_root=root,
        localisation_sha256=snapshot.localisation_sha256,
        allow_technical_residue=True,
    )
    hashes = report.get("hashes")
    if (
        report.get("source_mod") != str(source)
        or report.get("base_candidate") != str(baseline)
        or not isinstance(hashes, dict)
        or hashes.get("source_localisation_sha256")
        != baseline_inputs.source_localisation_sha256
        or hashes.get("base_candidate_localisation_sha256")
        != baseline_inputs.candidate_localisation_sha256
        or hashes.get("pinned_translation_report_sha256")
        != baseline_inputs.report_file.sha256
    ):
        raise SafetyError("ab_reviewed_candidate_identity_mismatch")
    parsed_files: list[SourceFile] = []
    for item in snapshot.localisation_files:
        try:
            parsed = parse_localisation(item.data)
        except ParseError as exc:
            raise SafetyError("ab_reviewed_candidate_parse_invalid") from exc
        parsed_files.append(
            SourceFile(
                relative=item.relative,
                data=item.data,
                sha256=item.sha256,
                stat_identity=(0, 0, len(item.data), 0),
                parsed=parsed,
                error=None,
            )
        )
    values = _available_candidate_values(
        baseline_inputs.source_files, parsed_files
    )
    return root, snapshot, values


def _available_candidate_values(
    source_files: list[SourceFile], candidate_files: Iterable[SourceFile]
) -> tuple[str | None, ...]:
    candidates = {item.relative: item for item in candidate_files}
    expected = {
        engine._candidate_relative(item.relative)
        for item in source_files
        if item.parsed is not None and item.parsed.is_english
    }
    if not set(candidates).issubset(expected):
        raise SafetyError("ab_candidate_inventory_mismatch")
    values: list[str | None] = []
    for source_file in source_files:
        parsed = source_file.parsed
        if parsed is None or not parsed.is_english:
            continue
        candidate = candidates.get(
            engine._candidate_relative(source_file.relative)
        )
        if candidate is None:
            values.extend(None for _ in parsed.entries)
            continue
        review._validate_file_alignment(source_file, candidate, None)
        if candidate.parsed is None:
            raise SafetyError("ab_candidate_parse_invalid")
        by_line = {
            item.line_index: item for item in candidate.parsed.entries
        }
        for entry in parsed.entries:
            values.append(by_line[entry.line_index].value)
    return tuple(values)


_STYLE = """
:root{color-scheme:light dark;font-family:system-ui,sans-serif}body{margin:0 auto;max-width:1100px;padding:24px}header{position:sticky;top:0;background:Canvas;padding:12px 0;border-bottom:1px solid GrayText;z-index:2}.entry{border:1px solid GrayText;border-radius:10px;padding:16px;margin:18px 0}.variants{display:grid;grid-template-columns:1fr 1fr;gap:14px}.text{white-space:pre-wrap;overflow-wrap:anywhere;padding:12px;background:color-mix(in srgb,CanvasText 7%,Canvas);border-radius:8px}.choices{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.choices label{border:1px solid GrayText;border-radius:8px;padding:8px}.note{width:100%;min-height:4em}button{padding:8px 12px;margin-right:8px}.status{font-variant-numeric:tabular-nums}@media(max-width:720px){.variants{grid-template-columns:1fr}}
""".strip()


_SCRIPT = r"""
(()=>{"use strict";
const pack=JSON.parse(document.getElementById("pack-data").textContent);
const choices=new Set(["A better","B better","tie","both bad"]);
const storageKey="smt-mvp6c-ab-v2:"+pack.pack_fingerprint;
let state={};
const exact=(value,fields)=>value&&typeof value==="object"&&!Array.isArray(value)&&Object.keys(value).sort().join("\0")===fields.slice().sort().join("\0");
function cleanDecisions(value){
  if(!exact(value,["schema_version","pack_fingerprint","decisions"])||value.schema_version!==2||value.pack_fingerprint!==pack.pack_fingerprint||!Array.isArray(value.decisions))throw new Error("invalid decisions document");
  const known=new Set(pack.entries.map(entry=>entry.id));const next={};
  for(const item of value.decisions){if(!exact(item,["occurrence_id","choice","note"])||!known.has(item.occurrence_id)||Object.hasOwn(next,item.occurrence_id)||!choices.has(item.choice)||typeof item.note!=="string")throw new Error("invalid decision record");next[item.occurrence_id]={choice:item.choice,note:item.note,locked:true};}
  return next;
}
function cleanStorage(value){
  if(!exact(value,["schema_version","pack_fingerprint","decisions"])||value.schema_version!==2||value.pack_fingerprint!==pack.pack_fingerprint||!Array.isArray(value.decisions))throw new Error("invalid storage document");
  const known=new Set(pack.entries.map(entry=>entry.id));const next={};
  for(const item of value.decisions){if(!exact(item,["occurrence_id","choice","note","locked"])||!known.has(item.occurrence_id)||Object.hasOwn(next,item.occurrence_id)||!choices.has(item.choice)||typeof item.note!=="string"||typeof item.locked!=="boolean")throw new Error("invalid storage record");next[item.occurrence_id]={choice:item.choice,note:item.note,locked:item.locked};}
  return next;
}
function documentValue(value=state){return {schema_version:2,pack_fingerprint:pack.pack_fingerprint,decisions:pack.entries.filter(entry=>value[entry.id]?.locked===true).map(entry=>({occurrence_id:entry.id,choice:value[entry.id].choice,note:value[entry.id].note}))};}
function storageValue(value=state){return {schema_version:2,pack_fingerprint:pack.pack_fingerprint,decisions:pack.entries.filter(entry=>value[entry.id]).map(entry=>({occurrence_id:entry.id,choice:value[entry.id].choice,note:value[entry.id].note,locked:value[entry.id].locked}))};}
function commit(next){localStorage.setItem(storageKey,JSON.stringify(storageValue(next)));state=next;updateStatus();}
function changed(next,renderAfter=true){try{commit(next);if(renderAfter)render();return true;}catch(error){alert(error.message);if(renderAfter)render();return false;}}
function nextState(){const next={};for(const entry of pack.entries){const item=state[entry.id];if(item)next[entry.id]={choice:item.choice,note:item.note,locked:item.locked};}return next;}
function setTentativeChoice(id,choice){const current=state[id];if(current?.locked===true){render();return false;}const next=nextState();next[id]={choice,note:current?.note||"",locked:false};return changed(next);}
function lockChoice(id){const current=state[id];if(!current||current.locked===true)return false;const next=nextState();next[id]={choice:current.choice,note:current.note,locked:true};return changed(next);}
function updateNote(id,note){const current=state[id];if(!current)return false;const next=nextState();next[id]={choice:current.choice,note,locked:current.locked};return changed(next,false);}
function importedState(value){const imported=cleanDecisions(value);const next=nextState();for(const entry of pack.entries){const item=imported[entry.id];if(!item)continue;const current=next[entry.id];if(current?.locked===true&&current.choice!==item.choice)throw new Error("locked choice conflict");next[entry.id]=item;}return next;}
function updateStatus(){const locked=Object.values(state).filter(item=>item.locked===true).length;const tentative=Object.values(state).length-locked;document.getElementById("status").textContent=locked+" / "+pack.entries.length+" locked; "+tentative+" tentative";}
function node(tag,text,className){const value=document.createElement(tag);if(text!==undefined)value.textContent=text;if(className)value.className=className;return value;}
function render(){const root=document.getElementById("entries");root.replaceChildren();for(const [index,entry] of pack.entries.entries()){
  const current=state[entry.id];const locked=current?.locked===true;
  const card=node("section",undefined,"entry");card.append(node("h2","Entry "+(index+1)));
  card.append(node("h3","Source"),node("div",entry.source,"text"));
  const variants=node("div",undefined,"variants");for(const label of ["A","B"]){const box=node("div");box.append(node("h3","Variant "+label),node("div",entry[label.toLowerCase()],"text"));variants.append(box);}card.append(variants);
  const controls=node("div",undefined,"choices");for(const choice of choices){const label=node("label");const radio=document.createElement("input");radio.type="radio";radio.name="choice-"+entry.id;radio.value=choice;radio.checked=current?.choice===choice;radio.disabled=locked;radio.addEventListener("change",()=>setTentativeChoice(entry.id,choice));label.append(radio,document.createTextNode(" "+choice));controls.append(label);}card.append(controls);
  const confirm=document.createElement("button");confirm.type="button";confirm.className="lock-choice";confirm.textContent=locked?"Выбор зафиксирован":"Зафиксировать выбор и показать эталон";confirm.disabled=locked||!current;confirm.addEventListener("click",()=>lockChoice(entry.id));card.append(confirm);
  const note=document.createElement("textarea");note.className="note";note.placeholder="Optional note";note.value=current?.note||"";note.disabled=!current;note.addEventListener("input",()=>updateNote(entry.id,note.value));card.append(note);
  if(locked&&entry.reviewed_reference!==null){card.append(node("h3","Reviewed-candidate reference"),node("div",entry.reviewed_reference,"text reviewed-reference"));}root.append(card);}updateStatus();}
function download(){const blob=new Blob([JSON.stringify(documentValue(),null,2)+"\n"],{type:"application/json"});const link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="mvp6c-ab-decisions.json";link.click();setTimeout(()=>URL.revokeObjectURL(link.href),0);}
document.getElementById("export").addEventListener("click",download);
document.getElementById("import").addEventListener("change",event=>{const file=event.target.files[0];if(!file)return;const reader=new FileReader();reader.onload=()=>{try{changed(importedState(JSON.parse(reader.result)));}catch(error){alert(error.message);}};reader.readAsText(file);});
try{const saved=localStorage.getItem(storageKey);if(saved)state=cleanStorage(JSON.parse(saved));}catch(error){localStorage.removeItem(storageKey);state={};}
render();
})();
""".strip()


def build_context_ab_review_pack(
    entries: Iterable[ABReviewEntry],
    output: Path,
    *,
    context_binding_sha256: str,
    source_localisation_sha256: str,
    model_digest: str,
    pre_publish_check: Callable[[], None] | None = None,
) -> dict[str, object]:
    """Publish one autonomous no-clobber pack without logging its text."""
    normalized = tuple(_validated_entry(item) for item in entries)
    if not normalized or len(normalized) > MAX_AB_ENTRIES:
        raise SafetyError("ab_entry_count_invalid")
    if len({item.occurrence_identity_sha256 for item in normalized}) != len(
        normalized
    ):
        raise SafetyError("ab_occurrence_identity_duplicate")
    binding = _sha256(context_binding_sha256, "ab_context_binding_invalid")
    source_hash = _sha256(
        source_localisation_sha256, "ab_source_identity_invalid"
    )
    digest = _validated_model_digest(model_digest)
    output_abs = _validated_output(output)

    displayed: list[dict[str, object]] = []
    mapping: list[dict[str, str]] = []
    for item in normalized:
        swap_digest = hashlib.sha256(
            (
                "mvp6c-ab-map-v1\0"
                + binding
                + "\0"
                + item.occurrence_identity_sha256
            ).encode("ascii")
        ).digest()
        swapped = bool(swap_digest[0] & 1)
        first = item.contextual if swapped else item.baseline
        second = item.baseline if swapped else item.contextual
        displayed.append(
            {
                "a": first,
                "b": second,
                "id": item.occurrence_identity_sha256,
                "reviewed_reference": item.reviewed_reference,
                "source": item.source,
            }
        )
        mapping.append(
            {
                "id": item.occurrence_identity_sha256,
                "variant_a": "contextual" if swapped else "baseline",
                "variant_b": "baseline" if swapped else "contextual",
            }
        )

    fingerprint = hashlib.sha256(
        _canonical_json(
            {
                "context_binding_sha256": binding,
                "entries": displayed,
                "model_digest": digest,
                "schema_version": AB_PACK_SCHEMA_VERSION,
                "source_localisation_sha256": source_hash,
            }
        )
    ).hexdigest()
    pack = {
        "decisions_schema_version": AB_DECISIONS_SCHEMA_VERSION,
        "entries": displayed,
        "pack_fingerprint": fingerprint,
        "quality_status": AB_QUALITY_STATUS,
        "schema_version": AB_PACK_SCHEMA_VERSION,
        "storage_schema_version": AB_STORAGE_SCHEMA_VERSION,
    }
    mapping_document = {
        "entries": mapping,
        "pack_fingerprint": fingerprint,
        "schema_version": AB_MAPPING_SCHEMA_VERSION,
    }
    summary = {
        "ab_entries": len(normalized),
        "ab_quality_status": AB_QUALITY_STATUS,
        "context_binding_sha256": binding,
        "decisions_schema_version": AB_DECISIONS_SCHEMA_VERSION,
        "mapping_schema_version": AB_MAPPING_SCHEMA_VERSION,
        "model_digest": digest,
        "network_dependencies": 0,
        "pack_fingerprint": fingerprint,
        "schema_version": AB_PACK_SCHEMA_VERSION,
        "source_localisation_sha256": source_hash,
        "storage_schema_version": AB_STORAGE_SCHEMA_VERSION,
    }
    html = _render_html(pack)

    temp = Path(
        tempfile.mkdtemp(
            prefix=f".{output_abs.name}.tmp-", dir=output_abs.parent
        )
    )
    os.chmod(temp, 0o700)
    try:
        _write_new(temp / "index.html", html)
        _write_new(
            temp / "blind-mapping.json",
            _canonical_json(mapping_document) + b"\n",
        )
        _write_new(
            temp / "pack-summary.json",
            json.dumps(
                summary,
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            ).encode("ascii")
            + b"\n",
        )
        if pre_publish_check is not None:
            pre_publish_check()
        try:
            atomic_publish_directory_no_replace(temp, output_abs)
        except DestinationExistsError as exc:
            raise SafetyError("ab_output_appeared_before_publication") from exc
        except AtomicPublicationUnavailable as exc:
            raise SafetyError("atomic_no_replace_unavailable") from exc
    except BaseException:
        if temp.exists():
            shutil.rmtree(temp)
        raise
    return {
        "status": "AB_QUALITY_STATUS: HUMAN_REVIEW_REQUIRED",
        "output": str(output_abs),
        "ab_entries": len(normalized),
        "pack_fingerprint": fingerprint,
        "context_binding_sha256": binding,
        "source_localisation_sha256": source_hash,
        "model_digest": digest,
        "network_dependencies": 0,
    }


def _validated_entry(value: ABReviewEntry) -> ABReviewEntry:
    if not isinstance(value, ABReviewEntry):
        raise SafetyError("ab_entry_type_invalid")
    identity = _sha256(
        value.occurrence_identity_sha256, "ab_occurrence_identity_invalid"
    )
    return ABReviewEntry(
        occurrence_identity_sha256=identity,
        source=_text(value.source, "ab_source_text_invalid"),
        baseline=_text(value.baseline, "ab_baseline_text_invalid"),
        contextual=_text(value.contextual, "ab_contextual_text_invalid"),
        reviewed_reference=(
            None
            if value.reviewed_reference is None
            else _text(
                value.reviewed_reference,
                "ab_reviewed_reference_invalid",
            )
        ),
    )


def _text(value: object, error: str) -> str:
    if not isinstance(value, str):
        raise SafetyError(error)
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SafetyError(error) from exc
    if len(encoded) > MAX_AB_TEXT_BYTES:
        raise SafetyError(error)
    return value


def _sha256(value: object, error: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(item not in "0123456789abcdef" for item in value)
    ):
        raise SafetyError(error)
    return value


def _validated_model_digest(value: object) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 256:
        raise SafetyError("ab_model_digest_invalid")
    return value


def _validated_pilot_output(
    output: Path,
    *,
    evaluation_root: Path,
    protected_roots: tuple[tuple[str, Path], ...],
) -> Path:
    authorized_root = review._validated_input_root(
        evaluation_root, "evaluation"
    )
    output_abs = _validated_output(output)
    if output_abs.parent != authorized_root:
        raise SafetyError("ab_output_outside_authorized_evaluation_root")
    output_identity = package_reviewed_mod._physical_path_identity(
        output_abs,
        label="ab_output",
        must_exist=False,
    )
    for label, root in protected_roots:
        root_identity = package_reviewed_mod._physical_path_identity(
            root,
            label=f"ab_{label}",
            must_exist=True,
        )
        if review._paths_overlap(output_abs, root) or (
            package_reviewed_mod._physical_paths_overlap(
                output_identity, root_identity
            )
        ):
            raise SafetyError(f"ab_output_{label}_overlap")
    return output_abs


def _validated_output(output: Path) -> Path:
    if not isinstance(output, Path):
        raise SafetyError("ab_output_path_invalid")
    lexical = output.absolute()
    if lexical.exists() or lexical.is_symlink():
        raise SafetyError("ab_output_must_not_exist")
    try:
        parent = lexical.parent.resolve(strict=True)
    except OSError as exc:
        raise SafetyError("ab_output_parent_invalid") from exc
    if not parent.is_dir():
        raise SafetyError("ab_output_parent_invalid")
    return parent / lexical.name


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _render_html(pack: dict[str, object]) -> bytes:
    encoded_pack = _canonical_json(pack).decode("utf-8")
    encoded_pack = encoded_pack.replace("&", "\\u0026").replace(
        "<", "\\u003c"
    )
    script_hash = base64.b64encode(
        hashlib.sha256(_SCRIPT.encode("utf-8")).digest()
    ).decode("ascii")
    html = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'\">"
        "<title>MVP-6C blind A/B review</title>"
        f"<style>{_STYLE}</style></head><body>"
        "<header><h1>MVP-6C blind A/B review</h1>"
        "<p>Choose without treating either variant as editorially approved.</p>"
        "<p id=\"status\" class=\"status\"></p>"
        "<button id=\"export\" type=\"button\">Export JSON</button>"
        "<label>Import JSON <input id=\"import\" type=\"file\" accept=\"application/json\"></label>"
        "</header><main id=\"entries\"></main>"
        f"<script id=\"pack-data\" type=\"application/json\">{encoded_pack}</script>"
        f"<script>{_SCRIPT}</script></body></html>"
    )
    return html.encode("utf-8")
