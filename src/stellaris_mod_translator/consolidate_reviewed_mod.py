"""Consolidate a reviewed candidate and a qualified replace supplement."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import unicodedata

from .engine import SafetyError, _tree_hash, _write_new
from .package_reviewed_mod import (
    APPLICATION_REPORT_NAME,
    MAX_APPLICATION_REPORT_BYTES,
    MAX_LOCALISATION_FILE_BYTES,
    PRIVATE_PATH_RE,
    DescriptorSpec,
    ReviewedCandidateSnapshot,
    StableFile,
    _load_application_report,
    _mkdir_private,
    _mkdir_private_parents,
    _paths_overlap,
    _physical_path_identity,
    _physical_paths_overlap,
    _read_stable_regular_file,
    _sha256,
    _snapshot_file,
    _snapshot_reviewed_candidate,
    _stable_directory_identity,
    _validate_application_report,
    _validate_path_relationships,
    _validate_private_content_absent,
    _validated_absolute_path_text,
    _validated_candidate_root,
    _validated_descriptor_text,
    _validated_mod_slug,
    _validated_package_output,
    _validated_planned_install_root,
    _validated_report_authority_path,
    _validated_supported_version,
    _verify_reviewed_candidate_snapshot,
    parse_strict_descriptor,
    render_descriptor,
)
from .parser import ParseError, ParsedFile, parse_localisation
from .publication import (
    AtomicPublicationUnavailable,
    DestinationExistsError,
    atomic_publish_directory_no_replace,
)


CONSOLIDATED_PACKAGE_REPORT_SCHEMA_VERSION = 2
CONSOLIDATION_MODE = "reviewed_plus_owner_replace_supplement_v1"
PACKAGE_REPORT_NAME = "package-report.json"
MAX_SUPPLEMENT_REPORT_BYTES = 1024 * 1024
MAX_OWNER_EVIDENCE_BYTES = 1024 * 1024
SHA256_RE = re.compile(r"[0-9a-f]{64}")
UTC_TIMESTAMP_RE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
)
ENTRY_ID_RE = re.compile(
    rb'^[ \t]*(?P<key>[A-Za-z0-9_.-]+)[ \t]*:'
    rb'(?P<version>[0-9]*)[ \t]+"'
)
DESCRIPTOR_FIELD_RE = re.compile(r'([a-z_]+)="([^"\\\r\n]*)"')
DESCRIPTOR_DEPENDENCY_RE = re.compile(r'\t"([^"\\\r\n]*)"')
SUPPLEMENT_REPORT_FIELDS = frozenset(
    {
        "captured_at_utc",
        "descriptors",
        "localisation",
        "main_translation",
        "milestone",
        "payload",
        "privacy",
        "schema_version",
        "source",
        "status",
    }
)
SUPPLEMENT_PAYLOAD_FIELDS = frozenset(
    {"file_count", "multi_link_count", "nonregular_count", "tree_sha256"}
)
SUPPLEMENT_SOURCE_FIELDS = frozenset(
    {"mutations", "path", "sha256_before_after", "size"}
)
SUPPLEMENT_LOCALISATION_FIELDS = frozenset(
    {
        "bare_lf_count",
        "bom",
        "bytes",
        "crlf_count",
        "entry_count",
        "file",
        "header",
        "key_set_and_order_exact",
        "lossless_structure",
        "mapping_fingerprint_sha256",
        "owner_mapping_exact",
        "protected_atoms_and_escapes_exact",
        "sha256",
        "version_suffixes_exact",
    }
)
SUPPLEMENT_MAIN_FIELDS = frozenset(
    {"file_count", "stability_snapshots", "tree_sha256", "unchanged"}
)
SUPPLEMENT_DESCRIPTOR_FIELDS = frozenset(
    {"external", "external_sha256", "internal", "internal_sha256"}
)
SUPPLEMENT_DESCRIPTOR_DETAIL_FIELDS = frozenset(
    {
        "dependencies",
        "display_name",
        "forbidden_fields_absent",
        "path",
        "supported_version",
    }
)
SUPPLEMENT_PRIVACY_FIELDS = frozenset(
    {"private_text_output", "raw_source_or_localisation_duplicated_in_report"}
)
OWNER_EVIDENCE_FIELDS = frozenset(
    {
        "schema_version",
        "captured_at_utc",
        "authoritative",
        "terminal_status",
        "mvp5k_replace_patch_smoke",
        "patch_package_pin",
        "patch_keys",
        "patch_install_payload",
        "launcher_patch",
        "playset",
        "playset_active",
        "playset_membership",
        "load_order",
        "main_menu",
        "new_relevant_log_errors",
        "known_upstream_nsc3_warning",
        "crash",
        "source_mutations",
        "workshop_mutations",
        "main_translation_mutations",
        "patch_mutations_after_preflight",
        "direct_launcher_db_writes",
        "saves_created",
        "ollama_calls",
        "git_changes",
        "private_text_output",
        "evidence",
        "next",
    }
)
BASE_TRANSLATION_REPORT_FIELDS = frozenset(
    {
        "schema_version",
        "source",
        "counts",
        "hashes",
        "diagnostics",
        "output",
        "dry_run",
        "max_occurrences_per_file",
        "model",
        "resumability",
        "status",
        "editorial_status",
        "editorially_approved",
    }
)


@dataclass(frozen=True)
class StableTreeSnapshot:
    root: Path
    directories: tuple[
        tuple[str, tuple[int, int, int, int, int, int, int]], ...
    ]
    files: tuple[StableFile, ...]
    tree_sha256: str


@dataclass(frozen=True)
class ConsolidationInputs:
    main: ReviewedCandidateSnapshot
    main_package: StableTreeSnapshot
    supplement: StableTreeSnapshot
    source_root: Path
    source_replace: StableTreeSnapshot
    base_report: StableFile
    owner_evidence: StableFile
    supplement_report: dict[str, object]
    application_report: dict[str, object]
    supplement_localisation: StableFile
    source_localisation: StableFile
    supplement_entries: int
    supplement_payload_sha256: str
    content_mapping_sha256: str


def consolidate_reviewed_mod(
    reviewed_candidate: Path,
    application_report_sha256: str,
    main_package: Path,
    main_package_sha256: str,
    supplement_package: Path,
    supplement_package_sha256: str,
    supplement_report_sha256: str,
    supplement_payload_sha256: str,
    supplement_localisation_sha256: str,
    supplement_source_mod: Path,
    supplement_source_sha256: str,
    supplement_mapping_sha256: str,
    supplement_content_mapping_sha256: str,
    owner_smoke_evidence: Path,
    owner_smoke_evidence_sha256: str,
    output: Path,
    mod_slug: str,
    display_name: str,
    dependency_name: str,
    supported_version: str,
    planned_install_root: Path,
) -> dict[str, object]:
    """Atomically create a fresh consolidated package without active writes."""
    pins = {
        "application_report_sha256": application_report_sha256,
        "main_package_sha256": main_package_sha256,
        "supplement_package_sha256": supplement_package_sha256,
        "supplement_report_sha256": supplement_report_sha256,
        "supplement_payload_sha256": supplement_payload_sha256,
        "supplement_localisation_sha256": supplement_localisation_sha256,
        "supplement_source_sha256": supplement_source_sha256,
        "supplement_mapping_sha256": supplement_mapping_sha256,
        "supplement_content_mapping_sha256": (
            supplement_content_mapping_sha256
        ),
        "owner_smoke_evidence_sha256": owner_smoke_evidence_sha256,
    }
    for label, value in pins.items():
        _validated_sha256_pin(value, label)

    candidate_root = _validated_candidate_root(reviewed_candidate)
    output_abs = _validated_package_output(candidate_root, output)
    main_package_root = _validated_existing_directory(
        main_package, "main_package"
    )
    supplement_root = _validated_existing_directory(
        supplement_package, "supplement_package"
    )
    source_root = _validated_existing_directory(
        supplement_source_mod, "supplement_source"
    )
    evidence_path = _validated_existing_file(
        owner_smoke_evidence, "owner_smoke_evidence"
    )
    slug = _validated_mod_slug(mod_slug)
    name = _validated_descriptor_text(display_name, "display_name")
    dependency = _validated_descriptor_text(
        dependency_name, "dependency_name"
    )
    version = _validated_supported_version(supported_version)
    install_root_text, install_root = _validated_planned_install_root(
        planned_install_root
    )

    inputs = _snapshot_and_validate_inputs(
        candidate_root=candidate_root,
        application_report_sha256=application_report_sha256,
        main_package_root=main_package_root,
        main_package_sha256=main_package_sha256,
        supplement_root=supplement_root,
        supplement_package_sha256=supplement_package_sha256,
        supplement_report_sha256=supplement_report_sha256,
        supplement_payload_sha256=supplement_payload_sha256,
        supplement_localisation_sha256=supplement_localisation_sha256,
        source_root=source_root,
        supplement_source_sha256=supplement_source_sha256,
        supplement_mapping_sha256=supplement_mapping_sha256,
        supplement_content_mapping_sha256=(
            supplement_content_mapping_sha256
        ),
        evidence_path=evidence_path,
        owner_smoke_evidence_sha256=owner_smoke_evidence_sha256,
        dependency_name=dependency,
    )
    _validate_path_relationships(
        output_abs,
        candidate_root,
        install_root,
        inputs.application_report,
    )
    _validate_consolidation_path_relationships(
        output=output_abs,
        candidate=candidate_root,
        source=source_root,
        main_package=main_package_root,
        supplement=supplement_root,
        install_root=install_root,
        evidence=evidence_path,
    )
    report_source = _validated_report_authority_path(
        inputs.application_report, "source_mod"
    )
    if report_source != source_root:
        raise SafetyError("main_and_supplement_source_mismatch")

    combined_localisation = (
        *inputs.main.localisation_files,
        inputs.supplement_localisation,
    )
    main_replace_files = [
        item
        for item in inputs.main.localisation_files
        if item.relative.parts[:3]
        == ("localisation", "russian", "replace")
    ]
    native_replace_files = [
        item
        for item in combined_localisation
        if item.relative.parts[:3]
        == ("localisation", "russian", "replace")
    ]
    if main_replace_files or native_replace_files != [
        inputs.supplement_localisation
    ]:
        raise SafetyError("consolidated_replace_inventory_invalid")
    _validate_portable_paths(
        [(item.relative, "file") for item in combined_localisation],
        "consolidated_localisation",
    )
    if len({item.relative for item in combined_localisation}) != len(
        combined_localisation
    ):
        raise SafetyError("consolidated_localisation_path_collision")

    internal_spec = DescriptorSpec(
        name=name,
        supported_version=version,
        dependency=dependency,
    )
    planned_mod_path = f"{install_root_text}/{slug}"
    external_spec = DescriptorSpec(
        name=name,
        supported_version=version,
        dependency=dependency,
        path=planned_mod_path,
    )
    internal_descriptor = render_descriptor(internal_spec)
    external_descriptor = render_descriptor(external_spec)
    report_payload = _consolidated_report(
        inputs=inputs,
        pins=pins,
        localisation_files=combined_localisation,
        mod_slug=slug,
        display_name=name,
        dependency_name=dependency,
        supported_version=version,
        internal_descriptor=internal_descriptor,
        external_descriptor=external_descriptor,
        native_replace_file_count=len(native_replace_files),
    )
    report_bytes = _render_report(report_payload)
    _validate_report_privacy(report_bytes)

    temp = Path(
        tempfile.mkdtemp(
            prefix=f".{output_abs.name}.tmp-",
            dir=output_abs.parent,
        )
    )
    try:
        install = _mkdir_private(temp / "install")
        mod_root = _mkdir_private(install / slug)
        _write_new(install / f"{slug}.mod", external_descriptor)
        _write_new(mod_root / "descriptor.mod", internal_descriptor)
        for item in combined_localisation:
            target = mod_root / item.relative
            _mkdir_private_parents(target.parent, mod_root)
            _write_new(target, item.data)
        _write_new(temp / PACKAGE_REPORT_NAME, report_bytes)

        _validate_materialized_consolidated_package(
            temp,
            report_payload=report_payload,
            report_bytes=report_bytes,
            internal_spec=internal_spec,
            external_spec=external_spec,
            internal_descriptor=internal_descriptor,
            external_descriptor=external_descriptor,
            localisation_files=combined_localisation,
        )
        _verify_consolidation_inputs(inputs)
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

    _validate_materialized_consolidated_package(
        output_abs,
        report_payload=report_payload,
        report_bytes=report_bytes,
        internal_spec=internal_spec,
        external_spec=external_spec,
        internal_descriptor=internal_descriptor,
        external_descriptor=external_descriptor,
        localisation_files=combined_localisation,
    )
    _verify_consolidation_inputs(inputs)
    return report_payload


def _snapshot_and_validate_inputs(
    *,
    candidate_root: Path,
    application_report_sha256: str,
    main_package_root: Path,
    main_package_sha256: str,
    supplement_root: Path,
    supplement_package_sha256: str,
    supplement_report_sha256: str,
    supplement_payload_sha256: str,
    supplement_localisation_sha256: str,
    source_root: Path,
    supplement_source_sha256: str,
    supplement_mapping_sha256: str,
    supplement_content_mapping_sha256: str,
    evidence_path: Path,
    owner_smoke_evidence_sha256: str,
    dependency_name: str,
) -> ConsolidationInputs:
    main = _snapshot_reviewed_candidate(candidate_root)
    _validate_portable_paths(
        [
            *[
                (Path(relative), "directory")
                for relative, _ in main.directories
            ],
            *[(item.relative, "file") for item in main.files],
        ],
        "main_reviewed_candidate",
    )
    application_report_file = _snapshot_file(
        main, Path(APPLICATION_REPORT_NAME)
    )
    if application_report_file.sha256 != application_report_sha256:
        raise SafetyError("application_report_pin_mismatch")
    application_report = _load_application_report(
        application_report_file.data
    )
    residue = _validate_application_report(
        application_report,
        candidate_root=candidate_root,
        localisation_sha256=main.localisation_sha256,
        allow_technical_residue=True,
    )
    if residue != {"unsupported_occurrences": 11, "skipped_files": 1}:
        raise SafetyError("main_candidate_residue_not_consolidatable")
    _validate_private_content_absent(
        main.localisation_files, application_report
    )

    main_package = _snapshot_tree(
        main_package_root,
        label="main_package",
        max_file_bytes=MAX_LOCALISATION_FILE_BYTES,
    )
    if main_package.tree_sha256 != main_package_sha256:
        raise SafetyError("main_package_pin_mismatch")

    base_candidate = _validated_report_authority_path(
        application_report, "base_candidate"
    )
    base_report_path = _validated_existing_file(
        base_candidate / "translation-report.json",
        "base_translation_report",
    )
    base_report = _read_stable_regular_file(
        base_report_path,
        base_report_path,
        max_bytes=MAX_APPLICATION_REPORT_BYTES,
    )
    application_hashes = application_report.get("hashes")
    if not isinstance(application_hashes, dict):
        raise SafetyError("main_application_hashes_invalid")
    pinned_base_report = application_hashes.get(
        "pinned_translation_report_sha256"
    )
    if base_report.sha256 != pinned_base_report:
        raise SafetyError("base_translation_report_pin_mismatch")

    supplement = _snapshot_tree(
        supplement_root,
        label="supplement_package",
        max_file_bytes=MAX_LOCALISATION_FILE_BYTES,
    )
    if supplement.tree_sha256 != supplement_package_sha256:
        raise SafetyError("supplement_package_pin_mismatch")
    report_file = _tree_file(supplement, Path(PACKAGE_REPORT_NAME))
    if report_file.sha256 != supplement_report_sha256:
        raise SafetyError("supplement_report_pin_mismatch")
    supplement_report = _load_strict_json(
        report_file.data, "supplement_report"
    )
    _validate_main_package_binding(
        main_package,
        main,
        supplement_report,
    )

    source_replace_root = _validated_descendant_directory(
        source_root,
        Path("localisation/english/replace"),
        "supplement_source_replace",
    )
    source_replace = _snapshot_tree(
        source_replace_root,
        label="supplement_source_replace",
        max_file_bytes=MAX_LOCALISATION_FILE_BYTES,
    )
    owner_evidence = _read_stable_regular_file(
        evidence_path,
        evidence_path,
        max_bytes=MAX_OWNER_EVIDENCE_BYTES,
    )
    if owner_evidence.sha256 != owner_smoke_evidence_sha256:
        raise SafetyError("owner_smoke_evidence_pin_mismatch")

    (
        supplement_localisation,
        source_localisation,
        supplement_entries,
        actual_payload_sha256,
        content_mapping_sha256,
    ) = _validate_supplement_report(
        supplement_report,
        supplement=supplement,
        source_root=source_root,
        source_replace=source_replace,
        main=main,
        supplement_payload_sha256=supplement_payload_sha256,
        supplement_localisation_sha256=supplement_localisation_sha256,
        supplement_source_sha256=supplement_source_sha256,
        supplement_mapping_sha256=supplement_mapping_sha256,
        supplement_content_mapping_sha256=(
            supplement_content_mapping_sha256
        ),
        dependency_name=dependency_name,
    )
    _validate_base_skip_authority(
        base_report,
        application_report=application_report,
        source_relative=(
            Path("localisation/english/replace")
            / source_localisation.relative
        ),
    )
    evidence = _load_strict_json(
        owner_evidence.data, "owner_smoke_evidence"
    )
    _validate_owner_evidence(evidence, supplement_entries)
    return ConsolidationInputs(
        main=main,
        main_package=main_package,
        supplement=supplement,
        source_root=source_root,
        source_replace=source_replace,
        base_report=base_report,
        owner_evidence=owner_evidence,
        supplement_report=supplement_report,
        application_report=application_report,
        supplement_localisation=supplement_localisation,
        source_localisation=source_localisation,
        supplement_entries=supplement_entries,
        supplement_payload_sha256=actual_payload_sha256,
        content_mapping_sha256=content_mapping_sha256,
    )


def _validate_supplement_report(
    report: dict[str, object],
    *,
    supplement: StableTreeSnapshot,
    source_root: Path,
    source_replace: StableTreeSnapshot,
    main: ReviewedCandidateSnapshot,
    supplement_payload_sha256: str,
    supplement_localisation_sha256: str,
    supplement_source_sha256: str,
    supplement_mapping_sha256: str,
    supplement_content_mapping_sha256: str,
    dependency_name: str,
) -> tuple[StableFile, StableFile, int, str, str]:
    _require_exact_fields(
        report, SUPPLEMENT_REPORT_FIELDS, "supplement_report"
    )
    _require_exact_value(report, "schema_version", 1, "supplement_report")
    _require_exact_value(report, "status", "PASS", "supplement_report")
    _require_exact_value(
        report, "milestone", "MVP-5K", "supplement_report"
    )
    captured = report.get("captured_at_utc")
    if not isinstance(captured, str) or UTC_TIMESTAMP_RE.fullmatch(
        captured
    ) is None:
        raise SafetyError("supplement_report_captured_at_utc_invalid")

    payload = _require_object(report, "payload", "supplement_report")
    _require_exact_fields(
        payload, SUPPLEMENT_PAYLOAD_FIELDS, "supplement_payload"
    )
    payload_file_count = _require_nonnegative_int(
        payload, "file_count", "supplement_payload"
    )
    if (
        payload_file_count != 3
        or _require_nonnegative_int(
            payload, "multi_link_count", "supplement_payload"
        )
        != 0
        or _require_nonnegative_int(
            payload, "nonregular_count", "supplement_payload"
        )
        != 0
    ):
        raise SafetyError("supplement_payload_inventory_invalid")
    payload_pin = _require_sha256(
        payload, "tree_sha256", "supplement_payload"
    )
    install_files = [
        (
            item.relative.relative_to("install"),
            item.data,
        )
        for item in supplement.files
        if item.relative.parts and item.relative.parts[0] == "install"
    ]
    actual_payload_sha256 = _tree_hash(install_files)
    if (
        len(install_files) != payload_file_count
        or payload_pin != supplement_payload_sha256
        or actual_payload_sha256 != supplement_payload_sha256
    ):
        raise SafetyError("supplement_payload_pin_mismatch")

    localisation = _require_object(
        report, "localisation", "supplement_report"
    )
    _require_exact_fields(
        localisation,
        SUPPLEMENT_LOCALISATION_FIELDS,
        "supplement_localisation",
    )
    target_text = localisation.get("file")
    if not isinstance(target_text, str):
        raise SafetyError("supplement_localisation_file_invalid")
    target_relative = Path(target_text)
    _validate_relative_path(target_relative, "supplement_localisation")
    parts = target_relative.parts
    if (
        len(parts) < 6
        or parts[0] != "install"
        or parts[2:5] != ("localisation", "russian", "replace")
        or not parts[-1].endswith("_l_russian.yml")
    ):
        raise SafetyError("supplement_localisation_path_noncanonical")
    slug = parts[1]
    if _validated_mod_slug(slug) != slug:
        raise SafetyError("supplement_localisation_path_noncanonical")
    target = _tree_file(supplement, target_relative)
    if target.sha256 != supplement_localisation_sha256:
        raise SafetyError("supplement_localisation_pin_mismatch")

    source_name = (
        parts[-1][: -len("_l_russian.yml")] + "_l_english.yml"
    )
    source_relative = Path(*parts[5:-1], source_name)
    source = _tree_file(source_replace, source_relative)
    if source.sha256 != supplement_source_sha256:
        raise SafetyError("supplement_source_pin_mismatch")
    expected_source_path = (
        source_root
        / "localisation/english/replace"
        / source_relative
    )

    source_meta = _require_object(
        report, "source", "supplement_report"
    )
    _require_exact_fields(
        source_meta, SUPPLEMENT_SOURCE_FIELDS, "supplement_source"
    )
    if (
        source_meta.get("path") != str(expected_source_path)
        or _require_nonnegative_int(
            source_meta, "mutations", "supplement_source"
        )
        != 0
        or _require_nonnegative_int(
            source_meta, "size", "supplement_source"
        )
        != len(source.data)
        or _require_sha256(
            source_meta, "sha256_before_after", "supplement_source"
        )
        != source.sha256
    ):
        raise SafetyError("supplement_source_metadata_mismatch")

    (
        parsed_source,
        parsed_target,
        content_mapping_sha256,
    ) = _validate_source_target_mapping(source, target)
    _validate_private_content_absent((target,), report)
    entry_count = len(parsed_target.entries)
    boolean_fields = (
        "key_set_and_order_exact",
        "lossless_structure",
        "owner_mapping_exact",
        "protected_atoms_and_escapes_exact",
        "version_suffixes_exact",
    )
    if any(localisation.get(key) is not True for key in boolean_fields):
        raise SafetyError("supplement_localisation_authority_invalid")
    if (
        localisation.get("bom") is not parsed_target.bom
        or localisation.get("header") != "l_russian"
        or _require_nonnegative_int(
            localisation, "bytes", "supplement_localisation"
        )
        != len(target.data)
        or _require_nonnegative_int(
            localisation, "entry_count", "supplement_localisation"
        )
        != entry_count
        or _require_nonnegative_int(
            localisation, "crlf_count", "supplement_localisation"
        )
        != target.data.count(b"\r\n")
        or _require_nonnegative_int(
            localisation, "bare_lf_count", "supplement_localisation"
        )
        != target.data.count(b"\n") - target.data.count(b"\r\n")
        or _require_sha256(
            localisation, "sha256", "supplement_localisation"
        )
        != target.sha256
    ):
        raise SafetyError("supplement_localisation_metadata_mismatch")
    if (
        _require_sha256(
            localisation,
            "mapping_fingerprint_sha256",
            "supplement_localisation",
        )
        != supplement_mapping_sha256
    ):
        raise SafetyError("supplement_mapping_pin_mismatch")
    if content_mapping_sha256 != supplement_content_mapping_sha256:
        raise SafetyError("supplement_content_mapping_pin_mismatch")
    if len(parsed_source.entries) != entry_count or entry_count <= 0:
        raise SafetyError("supplement_entry_count_invalid")

    expected_files = {
        Path(PACKAGE_REPORT_NAME),
        Path("install") / f"{slug}.mod",
        Path("install") / slug / "descriptor.mod",
        target_relative,
    }
    expected_directories = _parent_directories(expected_files)
    if (
        {item.relative for item in supplement.files} != expected_files
        or {Path(item[0]) for item in supplement.directories}
        != expected_directories
    ):
        raise SafetyError("supplement_inventory_mismatch")
    if (
        len(source_replace.files) != 1
        or source_replace.files[0].relative != source_relative
        or {Path(item[0]) for item in source_replace.directories}
        != _parent_directories({source_relative})
    ):
        raise SafetyError("supplement_source_inventory_mismatch")

    main_meta = _require_object(
        report, "main_translation", "supplement_report"
    )
    _require_exact_fields(
        main_meta, SUPPLEMENT_MAIN_FIELDS, "supplement_main_translation"
    )
    if (
        _require_nonnegative_int(
            main_meta, "file_count", "supplement_main_translation"
        )
        != len(main.files)
        or main_meta.get("stability_snapshots") != "3/3"
        or main_meta.get("unchanged") is not True
    ):
        raise SafetyError("supplement_main_translation_invalid")
    _require_sha256(
        main_meta, "tree_sha256", "supplement_main_translation"
    )

    descriptors = _require_object(
        report, "descriptors", "supplement_report"
    )
    _require_exact_fields(
        descriptors,
        SUPPLEMENT_DESCRIPTOR_FIELDS,
        "supplement_descriptors",
    )
    internal_path = Path("install") / slug / "descriptor.mod"
    external_path = Path("install") / f"{slug}.mod"
    internal_file = _tree_file(supplement, internal_path)
    external_file = _tree_file(supplement, external_path)
    if (
        _require_sha256(
            descriptors, "internal_sha256", "supplement_descriptors"
        )
        != internal_file.sha256
        or _require_sha256(
            descriptors, "external_sha256", "supplement_descriptors"
        )
        != external_file.sha256
    ):
        raise SafetyError("supplement_descriptor_pin_mismatch")
    internal = _parse_supplement_descriptor(internal_file.data)
    external = _parse_supplement_descriptor(external_file.data)
    _validate_supplement_descriptor_metadata(
        descriptors,
        "internal",
        internal,
        dependency_name=dependency_name,
        path_required=False,
    )
    _validate_supplement_descriptor_metadata(
        descriptors,
        "external",
        external,
        dependency_name=dependency_name,
        path_required=True,
    )

    privacy = _require_object(report, "privacy", "supplement_report")
    _require_exact_fields(
        privacy, SUPPLEMENT_PRIVACY_FIELDS, "supplement_privacy"
    )
    if (
        _require_nonnegative_int(
            privacy, "private_text_output", "supplement_privacy"
        )
        != 0
        or privacy.get("raw_source_or_localisation_duplicated_in_report")
        is not False
    ):
        raise SafetyError("supplement_privacy_invalid")
    consolidated_target = StableFile(
        relative=Path(*parts[2:]),
        data=target.data,
        sha256=target.sha256,
        stat_identity=target.stat_identity,
    )
    return (
        consolidated_target,
        source,
        entry_count,
        actual_payload_sha256,
        content_mapping_sha256,
    )


def _validate_main_package_binding(
    package: StableTreeSnapshot,
    main: ReviewedCandidateSnapshot,
    supplement_report: dict[str, object],
) -> None:
    internal_descriptors = [
        item
        for item in package.files
        if len(item.relative.parts) == 3
        and item.relative.parts[0] == "install"
        and item.relative.parts[2] == "descriptor.mod"
    ]
    if len(internal_descriptors) != 1:
        raise SafetyError("main_package_inventory_invalid")
    slug = internal_descriptors[0].relative.parts[1]
    if _validated_mod_slug(slug) != slug:
        raise SafetyError("main_package_inventory_invalid")
    mod_root = Path("install") / slug
    packaged_localisation = [
        item
        for item in package.files
        if item.relative.parts[:4]
        == ("install", slug, "localisation", "russian")
        and item.relative.suffix == ".yml"
    ]
    packaged_by_relative = {
        item.relative.relative_to(mod_root): item
        for item in packaged_localisation
    }
    main_by_relative = {
        item.relative: item for item in main.localisation_files
    }
    if (
        len(packaged_by_relative) != len(packaged_localisation)
        or set(packaged_by_relative) != set(main_by_relative)
        or any(
            packaged_by_relative[relative].data != item.data
            for relative, item in main_by_relative.items()
        )
    ):
        raise SafetyError("main_package_candidate_binding_mismatch")
    expected_files = {
        Path(PACKAGE_REPORT_NAME),
        Path("install") / f"{slug}.mod",
        mod_root / "descriptor.mod",
        *[item.relative for item in packaged_localisation],
    }
    if (
        {item.relative for item in package.files} != expected_files
        or {Path(item[0]) for item in package.directories}
        != _parent_directories(expected_files)
    ):
        raise SafetyError("main_package_inventory_invalid")
    content_files = [
        (item.relative.relative_to(mod_root), item.data)
        for item in package.files
        if mod_root in item.relative.parents
    ]
    main_meta = _require_object(
        supplement_report, "main_translation", "supplement_report"
    )
    _require_exact_fields(
        main_meta,
        SUPPLEMENT_MAIN_FIELDS,
        "supplement_main_translation",
    )
    if (
        _require_nonnegative_int(
            main_meta, "file_count", "supplement_main_translation"
        )
        != len(content_files)
        or _require_sha256(
            main_meta, "tree_sha256", "supplement_main_translation"
        )
        != _tree_hash(content_files)
    ):
        raise SafetyError("supplement_main_translation_pin_mismatch")


def _validate_base_skip_authority(
    base_report: StableFile,
    *,
    application_report: dict[str, object],
    source_relative: Path,
) -> None:
    report = _load_strict_json(
        base_report.data, "base_translation_report"
    )
    _require_exact_fields(
        report,
        BASE_TRANSLATION_REPORT_FIELDS,
        "base_translation_report",
    )
    expected_scalars: dict[str, object] = {
        "schema_version": 3,
        "source": application_report.get("source_mod"),
        "output": application_report.get("base_candidate"),
        "dry_run": False,
        "max_occurrences_per_file": None,
        "status": "technical_safe_partial",
        "editorial_status": "human_review_required",
        "editorially_approved": False,
    }
    for key, value in expected_scalars.items():
        _require_exact_value(
            report, key, value, "base_translation_report"
        )
    counts = report.get("counts")
    expected_counts = application_report.get("base_candidate_counts")
    if (
        not isinstance(counts, dict)
        or not isinstance(expected_counts, dict)
        or set(counts) != set(expected_counts)
    ):
        raise SafetyError("base_translation_report_counts_mismatch")
    for key, expected in expected_counts.items():
        if (
            type(expected) is not int
            or type(counts.get(key)) is not int
            or counts.get(key) != expected
        ):
            raise SafetyError(
                "base_translation_report_counts_mismatch"
            )
    hashes = report.get("hashes")
    application_hashes = application_report.get("hashes")
    if (
        not isinstance(hashes, dict)
        or set(hashes)
        != {
            "output_localisation_sha256",
            "source_localisation_sha256",
        }
        or not isinstance(application_hashes, dict)
        or hashes.get("output_localisation_sha256")
        != application_hashes.get(
            "base_candidate_localisation_sha256"
        )
        or hashes.get("source_localisation_sha256")
        != application_hashes.get("source_localisation_sha256")
    ):
        raise SafetyError("base_translation_report_hashes_mismatch")
    diagnostics = report.get("diagnostics")
    if not isinstance(diagnostics, list):
        raise SafetyError("base_translation_report_diagnostics_invalid")
    skip_diagnostics = [
        item
        for item in diagnostics
        if isinstance(item, dict)
        and item.get("code")
        in {"replace_layer_unsupported", "file_skipped"}
    ]
    if (
        len(skip_diagnostics)
        != expected_counts.get("skipped_files")
        or len(skip_diagnostics) != 1
        or set(skip_diagnostics[0]) != {"code", "path"}
        or skip_diagnostics[0].get("code")
        != "replace_layer_unsupported"
        or skip_diagnostics[0].get("path")
        != source_relative.as_posix()
    ):
        raise SafetyError("supplement_skipped_source_authority_mismatch")


def _validate_source_target_mapping(
    source: StableFile, target: StableFile
) -> tuple[ParsedFile, ParsedFile, str]:
    if b"__SMT_" in source.data or b"__SMT_" in target.data:
        raise SafetyError("supplement_placeholder_residue")
    try:
        parsed_source = parse_localisation(source.data)
        parsed_target = parse_localisation(target.data)
    except ParseError as exc:
        raise SafetyError("supplement_localisation_invalid") from exc
    if (
        parsed_source.language != "english"
        or parsed_target.language != "russian"
        or parsed_source.header_line != 0
        or parsed_target.header_line != 0
        or parsed_source.bom != parsed_target.bom
        or parsed_source.newline != parsed_target.newline
        or parsed_source.diagnostics
        or parsed_target.diagnostics
    ):
        raise SafetyError("supplement_source_target_structure_mismatch")
    source_ids = _entry_identities(parsed_source)
    target_ids = _entry_identities(parsed_target)
    if source_ids != target_ids:
        raise SafetyError("supplement_key_order_or_version_mismatch")
    if len(set(source_ids)) != len(source_ids):
        raise SafetyError("supplement_duplicate_entry_identity")
    source_protected = [
        tuple(token.original for token in entry.protected)
        for entry in parsed_source.entries
    ]
    target_protected = [
        tuple(token.original for token in entry.protected)
        for entry in parsed_target.entries
    ]
    if source_protected != target_protected:
        raise SafetyError("supplement_protected_atom_or_escape_mismatch")
    replacements = {
        source_entry.line_index: target_entry.value
        for source_entry, target_entry in zip(
            parsed_source.entries, parsed_target.entries
        )
    }
    try:
        rendered = parsed_source.render(
            replacements, russian_header=True
        )
    except (UnicodeError, ValueError) as exc:
        raise SafetyError("supplement_lossless_structure_mismatch") from exc
    if rendered != target.data:
        raise SafetyError("supplement_lossless_structure_mismatch")
    return (
        parsed_source,
        parsed_target,
        _content_mapping_sha256(
            source_ids,
            parsed_source,
            parsed_target,
        ),
    )


def _content_mapping_sha256(
    identities: list[tuple[str, str]],
    source: ParsedFile,
    target: ParsedFile,
) -> str:
    digest = hashlib.sha256()
    digest.update(b"SMT_CONSOLIDATED_MAPPING_V1\0")
    for identity, source_entry, target_entry in zip(
        identities, source.entries, target.entries
    ):
        fields = (
            identity[0],
            identity[1],
            source_entry.value,
            target_entry.value,
        )
        for field in fields:
            encoded = field.encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
    return digest.hexdigest()


def _entry_identities(parsed: ParsedFile) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for entry in parsed.entries:
        line = parsed.lines[entry.line_index]
        body = line.removesuffix(parsed.newline)
        match = ENTRY_ID_RE.match(body)
        if match is None:
            raise SafetyError("supplement_entry_identity_invalid")
        result.append(
            (
                match.group("key").decode("ascii"),
                match.group("version").decode("ascii"),
            )
        )
    return result


def _validate_owner_evidence(
    evidence: dict[str, object], entry_count: int
) -> None:
    _require_exact_fields(
        evidence, OWNER_EVIDENCE_FIELDS, "owner_smoke_evidence"
    )
    expected: dict[str, object] = {
        "schema_version": 1,
        "authoritative": True,
        "terminal_status": "COMPLETE",
        "patch_package_pin": "PASS",
        "patch_keys": f"{entry_count}/{entry_count}",
        "patch_install_payload": "PASS",
        "mvp5k_replace_patch_smoke": (
            "PASS_WITH_UPSTREAM_NSC3_WARNING"
        ),
        "launcher_patch": "READY_TO_PLAY",
        "playset": "SMT NSC3 RU",
        "playset_active": True,
        "playset_membership": "PASS",
        "load_order": "NSC3 -> LOCALISATION -> REPLACE_PATCH",
        "main_menu": "PASS",
        "known_upstream_nsc3_warning": (
            "PRESENT_MATCHING_FINGERPRINT"
        ),
    }
    for key, value in expected.items():
        _require_exact_value(
            evidence, key, value, "owner_smoke_evidence"
        )
    captured = evidence.get("captured_at_utc")
    if not isinstance(captured, str) or UTC_TIMESTAMP_RE.fullmatch(
        captured
    ) is None:
        raise SafetyError("owner_smoke_evidence_timestamp_invalid")
    for key in (
        "next",
    ):
        value = evidence.get(key)
        if not isinstance(value, str) or not value:
            raise SafetyError(f"owner_smoke_evidence_{key}_invalid")
    evidence_path = evidence.get("evidence")
    if (
        not isinstance(evidence_path, str)
        or not Path(evidence_path).is_absolute()
        or _validated_absolute_path_text(
            evidence_path, "owner_evidence_path"
        )
        != evidence_path
    ):
        raise SafetyError("owner_smoke_evidence_path_invalid")
    for key in (
        "new_relevant_log_errors",
        "crash",
        "source_mutations",
        "workshop_mutations",
        "main_translation_mutations",
        "patch_mutations_after_preflight",
        "direct_launcher_db_writes",
        "saves_created",
        "ollama_calls",
        "git_changes",
        "private_text_output",
    ):
        if _require_nonnegative_int(
            evidence, key, "owner_smoke_evidence"
        ) != 0:
            raise SafetyError(f"owner_smoke_evidence_{key}_nonzero")


def _consolidated_report(
    *,
    inputs: ConsolidationInputs,
    pins: dict[str, str],
    localisation_files: tuple[StableFile, ...],
    mod_slug: str,
    display_name: str,
    dependency_name: str,
    supported_version: str,
    internal_descriptor: bytes,
    external_descriptor: bytes,
    native_replace_file_count: int,
) -> dict[str, object]:
    counts = inputs.application_report["counts"]
    summary = inputs.application_report["review_summary"]
    if not isinstance(counts, dict) or not isinstance(summary, dict):
        raise SafetyError("consolidated_main_report_invalid")
    main_reviewed = _strict_count(counts, "total_decisions")
    unsupported = _strict_count(summary, "unsupported")
    supplement_reviewed = inputs.supplement_entries
    reviewed = main_reviewed + supplement_reviewed
    source_occurrences = reviewed + unsupported
    if (
        main_reviewed != 1678
        or supplement_reviewed != 9
        or reviewed != 1687
        or unsupported != 11
        or source_occurrences != 1698
    ):
        raise SafetyError("consolidated_provenance_algebra_mismatch")

    game_files = [
        f"{mod_slug}.mod",
        f"{mod_slug}/descriptor.mod",
        *[
            f"{mod_slug}/{item.relative.as_posix()}"
            for item in localisation_files
        ],
    ]
    package_files = [
        *[f"install/{path}" for path in game_files],
        PACKAGE_REPORT_NAME,
    ]
    if (
        len(localisation_files) != 17
        or len(game_files) != 19
        or len(package_files) != 20
    ):
        raise SafetyError("consolidated_inventory_count_mismatch")
    game_content = [
        (Path(game_files[0]), external_descriptor),
        (Path(game_files[1]), internal_descriptor),
        *[
            (Path(f"{mod_slug}/{item.relative.as_posix()}"), item.data)
            for item in localisation_files
        ],
    ]
    return {
        "schema_version": CONSOLIDATED_PACKAGE_REPORT_SCHEMA_VERSION,
        "construction_mode": CONSOLIDATION_MODE,
        "status": "consolidated_reviewed_mod_package_created",
        "review_scope": "main_reviewed_plus_owner_replace_supplement",
        "editorial_status": (
            "human_review_complete_for_reviewable_occurrences"
        ),
        "editorially_approved": False,
        "authorities": {
            "main_reviewed_candidate": "application_report_v2",
            "replace_supplement": "owner_reviewed_mvp5k_package",
            "owner_visual_smoke": "authoritative_terminal_evidence_v1",
        },
        "provenance": {
            "main_reviewed_candidate": {
                "application_report_sha256": pins[
                    "application_report_sha256"
                ],
                "base_translation_report_sha256": (
                    inputs.base_report.sha256
                ),
                "reviewed_package_tree_sha256": pins[
                    "main_package_sha256"
                ],
                "reviewed_localisation_sha256": (
                    inputs.main.localisation_sha256
                ),
                "reviewed_occurrences": main_reviewed,
                "decisions": {
                    "accept": _strict_count(counts, "accept"),
                    "edit": _strict_count(counts, "edit"),
                    "reject": _strict_count(counts, "reject"),
                },
                "unsupported_occurrences": unsupported,
                "skipped_files_before_consolidation": 1,
            },
            "owner_reviewed_replace_supplement": {
                "package_tree_sha256": pins[
                    "supplement_package_sha256"
                ],
                "package_report_sha256": pins[
                    "supplement_report_sha256"
                ],
                "payload_tree_sha256": pins[
                    "supplement_payload_sha256"
                ],
                "reviewed_localisation_sha256": pins[
                    "supplement_localisation_sha256"
                ],
                "source_replace_sha256": pins[
                    "supplement_source_sha256"
                ],
                "owner_mapping_fingerprint_sha256": pins[
                    "supplement_mapping_sha256"
                ],
                "content_mapping_sha256": inputs.content_mapping_sha256,
                "owner_smoke_evidence_sha256": pins[
                    "owner_smoke_evidence_sha256"
                ],
                "reviewed_occurrences": supplement_reviewed,
            },
        },
        "counts": {
            "source_occurrences": source_occurrences,
            "reviewed_occurrences": reviewed,
            "unsupported_occurrences": unsupported,
            "skipped_files": 0,
        },
        "hashes": {
            "package_localisation_sha256": _tree_hash(
                [(item.relative, item.data) for item in localisation_files]
            ),
            "game_content_tree_sha256": _tree_hash(game_content),
            "internal_descriptor_sha256": _sha256(
                internal_descriptor
            ),
            "external_descriptor_sha256": _sha256(
                external_descriptor
            ),
        },
        "inventory": {
            "localisation_file_count": len(localisation_files),
            "game_content_file_count": len(game_files),
            "package_file_count": len(package_files),
            "localisation_files": [
                {
                    "path": item.relative.as_posix(),
                    "bytes": len(item.data),
                    "sha256": item.sha256,
                }
                for item in localisation_files
            ],
            "game_content_files": game_files,
            "package_files": package_files,
            "native_replace_file_count": native_replace_file_count,
        },
        "mod": {
            "slug": mod_slug,
            "display_name": display_name,
            "dependency_name": dependency_name,
            "supported_version": supported_version,
            "dependency_count": 1,
            "replace_path_present": False,
        },
        "permissions": {"directories": "0700", "files": "0600"},
        "mutation_counters": {
            "source_mod": 0,
            "reviewed_candidate": 0,
            "supplement_package": 0,
            "existing_packages": 0,
            "active_mod": 0,
            "launcher": 0,
            "ollama": 0,
            "network": 0,
        },
        "installation_state": "not_installed",
        "in_game_smoke_required_after_installation": True,
    }


def _validate_materialized_consolidated_package(
    root: Path,
    *,
    report_payload: dict[str, object],
    report_bytes: bytes,
    internal_spec: DescriptorSpec,
    external_spec: DescriptorSpec,
    internal_descriptor: bytes,
    external_descriptor: bytes,
    localisation_files: tuple[StableFile, ...],
) -> None:
    snapshot = _snapshot_tree(
        root,
        label="materialized_package",
        max_file_bytes=MAX_LOCALISATION_FILE_BYTES,
    )
    inventory = report_payload.get("inventory")
    if not isinstance(inventory, dict):
        raise SafetyError("consolidated_package_inventory_invalid")
    package_files = inventory.get("package_files")
    if not isinstance(package_files, list) or any(
        not isinstance(item, str) for item in package_files
    ):
        raise SafetyError("consolidated_package_inventory_invalid")
    if {item.relative.as_posix() for item in snapshot.files} != set(
        package_files
    ):
        raise SafetyError("consolidated_package_inventory_mismatch")
    mod = report_payload.get("mod")
    if not isinstance(mod, dict) or not isinstance(mod.get("slug"), str):
        raise SafetyError("consolidated_package_inventory_invalid")
    slug = mod["slug"]
    internal_path = Path("install") / str(slug) / "descriptor.mod"
    external_path = Path("install") / f"{slug}.mod"
    if (
        _tree_file(snapshot, internal_path).data != internal_descriptor
        or _tree_file(snapshot, external_path).data != external_descriptor
        or parse_strict_descriptor(internal_descriptor)
        != parse_strict_descriptor(render_descriptor(internal_spec))
        or parse_strict_descriptor(external_descriptor)
        != parse_strict_descriptor(render_descriptor(external_spec))
    ):
        raise SafetyError("consolidated_package_descriptor_mismatch")
    if _tree_file(snapshot, Path(PACKAGE_REPORT_NAME)).data != report_bytes:
        raise SafetyError("consolidated_package_report_mismatch")
    loaded = _load_strict_json(report_bytes, "consolidated_package_report")
    if loaded != report_payload:
        raise SafetyError("consolidated_package_report_mismatch")
    for item in localisation_files:
        target = Path("install") / str(slug) / item.relative
        if _tree_file(snapshot, target).data != item.data:
            raise SafetyError("consolidated_package_localisation_mismatch")
    root_mode = root.stat().st_mode & 0o777
    if root_mode != 0o700:
        raise SafetyError("consolidated_package_root_mode_invalid")
    for _, identity in snapshot.directories:
        if identity[2] & 0o777 != 0o700:
            raise SafetyError("consolidated_package_directory_mode_invalid")
    for item in snapshot.files:
        if item.stat_identity[2] & 0o777 != 0o600:
            raise SafetyError("consolidated_package_file_mode_invalid")
    _validate_report_privacy(report_bytes)


def _snapshot_tree(
    root: Path,
    *,
    label: str,
    max_file_bytes: int,
) -> StableTreeSnapshot:
    directories: list[
        tuple[str, tuple[int, int, int, int, int, int, int]]
    ] = []
    files: list[StableFile] = []
    root_identity = _stable_directory_identity(root)
    if root_identity[3] < 1:
        raise SafetyError(f"{label}_root_identity_invalid")

    def fail_walk(error: OSError) -> None:
        raise SafetyError(f"{label}_inventory_failed") from error

    try:
        for current, names, filenames in os.walk(
            root, followlinks=False, onerror=fail_walk
        ):
            names.sort()
            filenames.sort()
            current_path = Path(current)
            for name in names:
                path = current_path / name
                relative = path.relative_to(root)
                _validate_relative_path(relative, label)
                directories.append(
                    (
                        relative.as_posix(),
                        _stable_directory_identity(path),
                    )
                )
            for name in filenames:
                path = current_path / name
                relative = path.relative_to(root)
                _validate_relative_path(relative, label)
                maximum = (
                    MAX_SUPPLEMENT_REPORT_BYTES
                    if relative == Path(PACKAGE_REPORT_NAME)
                    else max_file_bytes
                )
                files.append(
                    _read_stable_regular_file(
                        path, relative, max_bytes=maximum
                    )
                )
    except SafetyError:
        raise
    except OSError as exc:
        raise SafetyError(f"{label}_inventory_failed") from exc
    files.sort(key=lambda item: item.relative.as_posix())
    directories.sort()
    _validate_portable_paths(
        [
            *[(Path(relative), "directory") for relative, _ in directories],
            *[(item.relative, "file") for item in files],
        ],
        label,
    )
    return StableTreeSnapshot(
        root=root,
        directories=tuple(directories),
        files=tuple(files),
        tree_sha256=_tree_hash(
            [(item.relative, item.data) for item in files]
        ),
    )


def _verify_tree_snapshot(expected: StableTreeSnapshot) -> None:
    current = _snapshot_tree(
        expected.root,
        label="input_recheck",
        max_file_bytes=MAX_LOCALISATION_FILE_BYTES,
    )
    if current != expected:
        raise SafetyError("consolidation_input_generation_changed")


def _verify_consolidation_inputs(inputs: ConsolidationInputs) -> None:
    _verify_reviewed_candidate_snapshot(inputs.main)
    _verify_tree_snapshot(inputs.main_package)
    _verify_tree_snapshot(inputs.supplement)
    current_source_replace = _validated_descendant_directory(
        inputs.source_root,
        Path("localisation/english/replace"),
        "supplement_source_replace",
    )
    if current_source_replace != inputs.source_replace.root:
        raise SafetyError("consolidation_input_generation_changed")
    _verify_tree_snapshot(inputs.source_replace)
    current_base_report = _read_stable_regular_file(
        inputs.base_report.relative,
        inputs.base_report.relative,
        max_bytes=MAX_APPLICATION_REPORT_BYTES,
    )
    if current_base_report != inputs.base_report:
        raise SafetyError("consolidation_input_generation_changed")
    current_evidence = _read_stable_regular_file(
        inputs.owner_evidence.relative,
        inputs.owner_evidence.relative,
        max_bytes=MAX_OWNER_EVIDENCE_BYTES,
    )
    if current_evidence != inputs.owner_evidence:
        raise SafetyError("consolidation_input_generation_changed")


def _validated_existing_directory(path: Path, label: str) -> Path:
    lexical = path.absolute()
    if path.is_symlink():
        raise SafetyError(f"{label}_root_symlink")
    try:
        resolved = lexical.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SafetyError(f"{label}_missing") from exc
    if not resolved.is_dir():
        raise SafetyError(f"{label}_not_directory")
    return resolved


def _validated_descendant_directory(
    root: Path,
    relative: Path,
    label: str,
) -> Path:
    _validate_relative_path(relative, label)
    current = root
    for part in relative.parts:
        current = current / part
        try:
            value = current.lstat()
        except OSError as exc:
            raise SafetyError(f"{label}_missing") from exc
        if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
            raise SafetyError(f"{label}_unsafe_ancestor")
        _stable_directory_identity(current)
    root_identity = _physical_path_identity(
        root, label=f"{label}_root", must_exist=True
    )
    child_identity = _physical_path_identity(
        current, label=label, must_exist=True
    )
    if not _physical_paths_overlap(root_identity, child_identity):
        raise SafetyError(f"{label}_physical_containment_unproven")
    return current


def _validated_existing_file(path: Path, label: str) -> Path:
    lexical = path.absolute()
    if path.is_symlink():
        raise SafetyError(f"{label}_symlink")
    try:
        resolved = lexical.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SafetyError(f"{label}_missing") from exc
    if not resolved.is_file():
        raise SafetyError(f"{label}_not_regular")
    return resolved


def _validate_consolidation_path_relationships(
    *,
    output: Path,
    candidate: Path,
    source: Path,
    main_package: Path,
    supplement: Path,
    install_root: Path,
    evidence: Path,
) -> None:
    evidence_parent = evidence.parent
    named = (
        ("output", output, False),
        ("main_candidate", candidate, True),
        ("source", source, True),
        ("main_package", main_package, True),
        ("supplement", supplement, True),
        ("install_root", install_root, False),
        ("owner_evidence_parent", evidence_parent, True),
    )
    physical = {
        label: _physical_path_identity(
            path, label=label, must_exist=must_exist
        )
        for label, path, must_exist in named
    }
    for index, (left_label, left, _) in enumerate(named):
        for right_label, right, _ in named[index + 1 :]:
            if _paths_overlap(left, right) or _physical_paths_overlap(
                physical[left_label], physical[right_label]
            ):
                raise SafetyError(f"{left_label}_{right_label}_overlap")


def _validate_portable_paths(
    entries: list[tuple[Path, str]], label: str
) -> None:
    exact: dict[tuple[str, ...], tuple[tuple[str, ...], str]] = {}
    prefixes: dict[tuple[str, ...], tuple[tuple[str, ...], str]] = {}
    for path, kind in entries:
        _validate_relative_path(path, label)
        raw = path.parts
        folded = tuple(
            unicodedata.normalize("NFC", part).casefold()
            for part in raw
        )
        prior = exact.get(folded)
        if prior is not None and (prior[0] != raw or prior[1] != kind):
            raise SafetyError(f"{label}_portable_path_collision")
        exact[folded] = (raw, kind)
        for length in range(1, len(folded)):
            prefix = folded[:length]
            raw_prefix = raw[:length]
            file_entry = exact.get(prefix)
            if file_entry is not None and file_entry[1] == "file":
                raise SafetyError(f"{label}_file_directory_collision")
            prior_prefix = prefixes.get(prefix)
            if prior_prefix is not None and prior_prefix[0] != raw_prefix:
                raise SafetyError(f"{label}_portable_path_collision")
            prefixes[prefix] = (raw_prefix, "directory")
        if kind == "file" and folded in prefixes:
            raise SafetyError(f"{label}_file_directory_collision")


def _validate_relative_path(path: Path, label: str) -> None:
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise SafetyError(f"{label}_unsafe_path")
    for part in path.parts:
        if (
            part in {"", ".", ".."}
            or unicodedata.normalize("NFC", part) != part
            or any(
                ord(char) < 0x20
                or ord(char) == 0x7F
                or unicodedata.category(char) == "Cf"
                for char in part
            )
        ):
            raise SafetyError(f"{label}_unsafe_path")


def _tree_file(
    snapshot: StableTreeSnapshot, relative: Path
) -> StableFile:
    matches = [item for item in snapshot.files if item.relative == relative]
    if len(matches) != 1:
        raise SafetyError("supplement_required_file_missing")
    return matches[0]


def _parent_directories(files: set[Path]) -> set[Path]:
    result: set[Path] = set()
    for path in files:
        parent = path.parent
        while parent != Path("."):
            result.add(parent)
            parent = parent.parent
    return result


def _load_strict_json(data: bytes, label: str) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise SafetyError(f"{label}_duplicate_field")
            result[key] = value
        return result

    def reject_float(value: str) -> object:
        raise ValueError(f"JSON float is forbidden: {value}")

    def reject_constant(value: str) -> object:
        raise ValueError(f"JSON constant is forbidden: {value}")

    try:
        payload = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=unique,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise SafetyError(f"{label}_invalid_json") from exc
    if not isinstance(payload, dict):
        raise SafetyError(f"{label}_invalid_json")
    return payload


def _require_object(
    value: dict[str, object], key: str, label: str
) -> dict[str, object]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise SafetyError(f"{label}_{key}_invalid")
    return item


def _require_exact_fields(
    value: dict[str, object],
    expected: frozenset[str],
    label: str,
) -> None:
    if set(value) != expected:
        raise SafetyError(f"{label}_fields_mismatch")


def _require_exact_value(
    value: dict[str, object],
    key: str,
    expected: object,
    label: str,
) -> None:
    actual = value.get(key)
    if (
        type(expected) is int
        and (type(actual) is not int or actual != expected)
    ) or (
        type(expected) is bool
        and (type(actual) is not bool or actual is not expected)
    ) or (
        type(expected) not in {int, bool}
        and (type(actual) is not type(expected) or actual != expected)
    ):
        raise SafetyError(f"{label}_{key}_mismatch")


def _require_nonnegative_int(
    value: dict[str, object], key: str, label: str
) -> int:
    item = value.get(key)
    if type(item) is not int or item < 0:
        raise SafetyError(f"{label}_{key}_invalid")
    return item


def _strict_count(value: dict[str, object], key: str) -> int:
    item = value.get(key)
    if type(item) is not int or item < 0:
        raise SafetyError(f"consolidated_{key}_invalid")
    return item


def _require_sha256(
    value: dict[str, object], key: str, label: str
) -> str:
    item = value.get(key)
    if not isinstance(item, str) or SHA256_RE.fullmatch(item) is None:
        raise SafetyError(f"{label}_{key}_invalid")
    return item


def _validated_sha256_pin(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise SafetyError(f"invalid_{label}")
    return value


def _parse_supplement_descriptor(data: bytes) -> dict[str, object]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SafetyError("supplement_descriptor_invalid_utf8") from exc
    if not text.endswith("\n") or "\r" in text or "\ufeff" in text:
        raise SafetyError("supplement_descriptor_malformed")
    lines = text[:-1].split("\n")
    fields: dict[str, object] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if line == "dependencies={":
            if "dependencies" in fields:
                raise SafetyError("supplement_descriptor_duplicate_field")
            dependencies: list[str] = []
            index += 1
            while index < len(lines) and lines[index] != "}":
                match = DESCRIPTOR_DEPENDENCY_RE.fullmatch(lines[index])
                if match is None:
                    raise SafetyError("supplement_descriptor_malformed")
                dependencies.append(
                    _validated_descriptor_text(
                        match.group(1), "supplement_dependency"
                    )
                )
                index += 1
            if index >= len(lines) or lines[index] != "}":
                raise SafetyError("supplement_descriptor_malformed")
            if len(dependencies) != 2:
                raise SafetyError(
                    "supplement_descriptor_dependency_count_invalid"
                )
            fields["dependencies"] = dependencies
            index += 1
            continue
        match = DESCRIPTOR_FIELD_RE.fullmatch(line)
        if match is None:
            raise SafetyError("supplement_descriptor_malformed")
        key, raw = match.groups()
        if key in fields:
            raise SafetyError("supplement_descriptor_duplicate_field")
        if key in {"replace_path", "remote_file_id"}:
            raise SafetyError("supplement_descriptor_forbidden_field")
        if key not in {"name", "supported_version", "path"}:
            raise SafetyError("supplement_descriptor_unknown_field")
        if key == "supported_version":
            fields[key] = _validated_supported_version(raw)
        elif key == "path":
            fields[key] = _validated_absolute_path_text(
                raw, "supplement_descriptor_path"
            )
        else:
            fields[key] = _validated_descriptor_text(
                raw, "supplement_descriptor_name"
            )
        index += 1
    if set(fields) not in (
        {"name", "supported_version", "dependencies"},
        {"name", "supported_version", "dependencies", "path"},
    ):
        raise SafetyError("supplement_descriptor_required_field_missing")
    return fields


def _validate_supplement_descriptor_metadata(
    descriptors: dict[str, object],
    key: str,
    parsed: dict[str, object],
    *,
    dependency_name: str,
    path_required: bool,
) -> None:
    metadata = descriptors.get(key)
    if not isinstance(metadata, dict):
        raise SafetyError("supplement_descriptor_metadata_invalid")
    _require_exact_fields(
        metadata,
        SUPPLEMENT_DESCRIPTOR_DETAIL_FIELDS,
        f"supplement_descriptor_{key}",
    )
    expected_path = parsed.get("path")
    if (
        metadata.get("display_name") != parsed.get("name")
        or metadata.get("supported_version")
        != parsed.get("supported_version")
        or metadata.get("dependencies") != parsed.get("dependencies")
        or metadata.get("forbidden_fields_absent") is not True
        or metadata.get("path") != expected_path
        or (path_required and not isinstance(expected_path, str))
        or (not path_required and expected_path is not None)
    ):
        raise SafetyError("supplement_descriptor_metadata_mismatch")
    dependencies = parsed.get("dependencies")
    if (
        not isinstance(dependencies, list)
        or len(dependencies) != 2
        or dependencies[0] != dependency_name
    ):
        raise SafetyError("supplement_descriptor_dependency_mismatch")


def _render_report(report: dict[str, object]) -> bytes:
    return (
        json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _validate_report_privacy(report_bytes: bytes) -> None:
    lowered = report_bytes.lower()
    if (
        PRIVATE_PATH_RE.search(report_bytes)
        or b"review-decisions" in lowered
        or b"decisions.json" in lowered
        or b"translation-report.json" in lowered
        or b"prompt" in lowered
        or b".smt-workspace" in lowered
    ):
        raise SafetyError("private_content_in_consolidated_report")
