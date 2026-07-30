from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import unicodedata

import pytest

import stellaris_mod_translator.consolidate_reviewed_mod as consolidation
from stellaris_mod_translator.consolidate_reviewed_mod import (
    consolidate_reviewed_mod,
)
from stellaris_mod_translator.engine import SafetyError, _tree_hash
from stellaris_mod_translator.parser import parse_localisation
from stellaris_mod_translator.publication import DestinationExistsError


PRODUCTION_ATOMIC_PUBLISH = (
    consolidation.atomic_publish_directory_no_replace
)


@dataclass
class ConsolidationFixture:
    candidate: Path
    main_package: Path
    source: Path
    supplement: Path
    evidence: Path
    output_parent: Path
    install_root: Path
    application_report: dict[str, object]
    supplement_report: dict[str, object]
    owner_evidence: dict[str, object]
    application_report_pin: str
    main_package_pin: str
    supplement_package_pin: str
    supplement_report_pin: str
    supplement_payload_pin: str
    supplement_localisation_pin: str
    supplement_source_pin: str
    mapping_pin: str
    content_mapping_pin: str
    evidence_pin: str


@pytest.fixture(autouse=True)
def portable_atomic_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def publish(source: Path, destination: Path) -> None:
        if destination.exists() or destination.is_symlink():
            raise DestinationExistsError("destination already exists")
        source.rename(destination)

    monkeypatch.setattr(
        consolidation, "atomic_publish_directory_no_replace", publish
    )


def _json_bytes(value: dict[str, object]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tree_files(root: Path) -> list[tuple[Path, bytes]]:
    return [
        (path.relative_to(root), path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def _descriptor(
    *,
    path: str | None,
) -> bytes:
    lines = [
        'name="Synthetic replace supplement"',
        'supported_version="4.4.*"',
        "dependencies={",
        '\t"NSC3"',
        '\t"Synthetic main translation"',
        "}",
    ]
    if path is not None:
        lines.append(f'path="{path}"')
    return ("\n".join(lines) + "\n").encode()


def _source_and_target() -> tuple[bytes, bytes]:
    lines = ["l_english:"]
    for index in range(9):
        lines.append(
            f' key_{index}:{index % 3} "Source {index} '
            '$TOKEN$ [Root.GetName] \\"quoted\\""'
        )
    source = b"\xef\xbb\xbf" + ("\r\n".join(lines) + "\r\n").encode()
    parsed = parse_localisation(source)
    replacements = {
        entry.line_index: (
            f"Цель {index} $TOKEN$ [Root.GetName] "
            '\\"quoted\\"'
        )
        for index, entry in enumerate(parsed.entries)
    }
    target = parsed.render(replacements, russian_header=True)
    return source, target


def _application_report(
    *,
    source: Path,
    base_candidate: Path,
    candidate: Path,
    localisation_sha256: str,
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "status": "full_candidate_review_applied",
        "review_scope": "full_candidate",
        "review_pack_schema_version": 2,
        "candidate_report_schema_version": 3,
        "editorial_status": (
            "human_review_complete_for_reviewable_occurrences"
        ),
        "editorially_approved": False,
        "source_mod": str(source),
        "base_candidate": str(base_candidate),
        "base_candidate_status": "technical_safe_partial",
        "output": str(candidate),
        "decisions": str(candidate.parent / "private-decisions.json"),
        "pack_fingerprint": "1" * 64,
        "model": {"tag": "synthetic:1", "digest": "2" * 64},
        "source_mutations": 0,
        "candidate_mutations": 0,
        "protected_atom_mismatches": 0,
        "ollama_calls": 0,
        "network_calls": 0,
        "counts": {
            "total_decisions": 1678,
            "accept": 619,
            "edit": 1030,
            "reject": 29,
            "actually_changed_spans": 1035,
            "restored_english_spans": 5,
        },
        "review_summary": {
            "review_entries": 1678,
            "accepted_changed": 1417,
            "accepted_unchanged": 59,
            "model_fallback": 202,
            "unsupported": 11,
            "skipped_files": 1,
            "deferred": 0,
            "pending": 0,
            "total": 1689,
            "whitespace_warning_entries": 13,
        },
        "technical_residue": {
            "unsupported_occurrences": 11,
            "skipped_files": 1,
        },
        "base_candidate_counts": {
            "accepted_unchanged": 59,
            "calls_in_final_run": 113,
            "completed": 1689,
            "completed_occurrences": 1689,
            "discovered_yml_files": 170,
            "english_files": 16,
            "fallback": 213,
            "fallback_occurrences": 213,
            "occurrences": 1689,
            "pending": 0,
            "unsupported_occurrences": 11,
            "unsupported": 11,
            "skipped_files": 1,
            "pending_occurrences": 0,
            "deferred_occurrences": 0,
            "planned_translation_occurrences": 1678,
            "reused_from_workspace": 1565,
            "reused_from_workspace_occurrences": 1565,
            "total": 1689,
            "total_occurrences": 1689,
            "translated": 1476,
            "translated_occurrences": 1476,
            "unchanged_accepted_occurrences": 59,
        },
        "hashes": {
            "source_localisation_sha256": "3" * 64,
            "base_candidate_localisation_sha256": "4" * 64,
            "pinned_translation_report_sha256": "5" * 64,
            "decisions_file_sha256": "6" * 64,
            "final_output_localisation_sha256": localisation_sha256,
        },
    }


def _synthetic_fixture(tmp_path: Path) -> ConsolidationFixture:
    candidate = tmp_path / "reviewed"
    source = tmp_path / "source"
    base_candidate = tmp_path / "base-candidate"
    main_package = tmp_path / "main-package"
    supplement = tmp_path / "supplement"
    evidence_dir = tmp_path / "evidence"
    output_parent = tmp_path / "packages"
    install_root = tmp_path / "active-mods"
    for path in (
        candidate / "localisation/russian",
        source / "localisation/english/replace",
        base_candidate,
        main_package,
        supplement,
        evidence_dir,
        output_parent,
        install_root,
    ):
        path.mkdir(parents=True, exist_ok=True)

    for index in range(16):
        data = (
            f'l_russian:\n main_{index}:0 "Synthetic {index}"\n'
        ).encode()
        (
            candidate
            / "localisation/russian"
            / f"main_{index}_l_russian.yml"
        ).write_bytes(data)
    localisation_files = [
        (path.relative_to(candidate), path.read_bytes())
        for path in sorted(
            (candidate / "localisation/russian").rglob("*.yml")
        )
    ]
    application_report = _application_report(
        source=source,
        base_candidate=base_candidate,
        candidate=candidate,
        localisation_sha256=_tree_hash(localisation_files),
    )
    base_report = {
        "schema_version": 3,
        "source": str(source),
        "counts": dict(application_report["base_candidate_counts"]),
        "hashes": {
            "output_localisation_sha256": application_report["hashes"][
                "base_candidate_localisation_sha256"
            ],
            "source_localisation_sha256": application_report["hashes"][
                "source_localisation_sha256"
            ],
        },
        "diagnostics": [
            {
                "code": "replace_layer_unsupported",
                "path": (
                    "localisation/english/replace/"
                    "synthetic_l_english.yml"
                ),
            }
        ],
        "output": str(base_candidate),
        "dry_run": False,
        "max_occurrences_per_file": None,
        "model": {"tag": "synthetic:1", "digest": "2" * 64},
        "resumability": {},
        "status": "technical_safe_partial",
        "editorial_status": "human_review_required",
        "editorially_approved": False,
    }
    base_report_bytes = _json_bytes(base_report)
    (base_candidate / "translation-report.json").write_bytes(
        base_report_bytes
    )
    application_hashes = application_report["hashes"]
    assert isinstance(application_hashes, dict)
    application_hashes["pinned_translation_report_sha256"] = _sha256(
        base_report_bytes
    )
    application_report_bytes = _json_bytes(application_report)
    (candidate / "review-application-report.json").write_bytes(
        application_report_bytes
    )

    source_bytes, target_bytes = _source_and_target()
    parsed_source = parse_localisation(source_bytes)
    parsed_target = parse_localisation(target_bytes)
    content_mapping_pin = consolidation._content_mapping_sha256(
        consolidation._entry_identities(parsed_source),
        parsed_source,
        parsed_target,
    )
    source_file = (
        source
        / "localisation/english/replace/synthetic_l_english.yml"
    )
    source_file.write_bytes(source_bytes)
    slug = "synthetic_replace_patch"
    mod_root = supplement / "install" / slug
    target_file = (
        mod_root
        / "localisation/russian/replace/synthetic_l_russian.yml"
    )
    target_file.parent.mkdir(parents=True)
    target_file.write_bytes(target_bytes)
    external_path = str(tmp_path / "old-active" / slug)
    external_descriptor = _descriptor(path=external_path)
    internal_descriptor = _descriptor(path=None)
    (supplement / "install" / f"{slug}.mod").write_bytes(
        external_descriptor
    )
    (mod_root / "descriptor.mod").write_bytes(internal_descriptor)

    main_slug = "synthetic_main"
    main_mod_root = main_package / "install" / main_slug
    main_mod_root.mkdir(parents=True)
    (main_package / "install" / f"{main_slug}.mod").write_bytes(
        b'name="Synthetic main"\n'
    )
    (main_mod_root / "descriptor.mod").write_bytes(
        b'name="Synthetic main"\n'
    )
    for relative, data in localisation_files:
        path = main_mod_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (main_package / "package-report.json").write_bytes(b"{}\n")
    main_content_pin = _tree_hash(_tree_files(main_mod_root))

    install = supplement / "install"
    payload_pin = _tree_hash(_tree_files(install))
    mapping_pin = "7" * 64
    supplement_report: dict[str, object] = {
        "schema_version": 1,
        "captured_at_utc": "2026-07-30T10:32:46Z",
        "status": "PASS",
        "milestone": "MVP-5K",
        "payload": {
            "file_count": 3,
            "multi_link_count": 0,
            "nonregular_count": 0,
            "tree_sha256": payload_pin,
        },
        "source": {
            "mutations": 0,
            "path": str(source_file),
            "sha256_before_after": _sha256(source_bytes),
            "size": len(source_bytes),
        },
        "localisation": {
            "bare_lf_count": (
                target_bytes.count(b"\n")
                - target_bytes.count(b"\r\n")
            ),
            "bom": True,
            "bytes": len(target_bytes),
            "crlf_count": target_bytes.count(b"\r\n"),
            "entry_count": 9,
            "file": (
                "install/synthetic_replace_patch/localisation/"
                "russian/replace/synthetic_l_russian.yml"
            ),
            "header": "l_russian",
            "key_set_and_order_exact": True,
            "lossless_structure": True,
            "mapping_fingerprint_sha256": mapping_pin,
            "owner_mapping_exact": True,
            "protected_atoms_and_escapes_exact": True,
            "sha256": _sha256(target_bytes),
            "version_suffixes_exact": True,
        },
        "main_translation": {
            "file_count": 17,
            "stability_snapshots": "3/3",
            "tree_sha256": main_content_pin,
            "unchanged": True,
        },
        "descriptors": {
            "external": {
                "dependencies": [
                    "NSC3",
                    "Synthetic main translation",
                ],
                "display_name": "Synthetic replace supplement",
                "forbidden_fields_absent": True,
                "path": external_path,
                "supported_version": "4.4.*",
            },
            "external_sha256": _sha256(external_descriptor),
            "internal": {
                "dependencies": [
                    "NSC3",
                    "Synthetic main translation",
                ],
                "display_name": "Synthetic replace supplement",
                "forbidden_fields_absent": True,
                "path": None,
                "supported_version": "4.4.*",
            },
            "internal_sha256": _sha256(internal_descriptor),
        },
        "privacy": {
            "private_text_output": 0,
            "raw_source_or_localisation_duplicated_in_report": False,
        },
    }
    supplement_report_bytes = _json_bytes(supplement_report)
    (supplement / "package-report.json").write_bytes(
        supplement_report_bytes
    )
    owner_evidence: dict[str, object] = {
        "schema_version": 1,
        "captured_at_utc": "2026-07-30T10:40:00Z",
        "authoritative": True,
        "terminal_status": "COMPLETE",
        "mvp5k_replace_patch_smoke": (
            "PASS_WITH_UPSTREAM_NSC3_WARNING"
        ),
        "patch_package_pin": "PASS",
        "patch_keys": "9/9",
        "patch_install_payload": "PASS",
        "launcher_patch": "READY_TO_PLAY",
        "playset": "SMT NSC3 RU",
        "playset_active": True,
        "playset_membership": "PASS",
        "load_order": "NSC3 -> LOCALISATION -> REPLACE_PATCH",
        "main_menu": "PASS",
        "new_relevant_log_errors": 0,
        "known_upstream_nsc3_warning": (
            "PRESENT_MATCHING_FINGERPRINT"
        ),
        "crash": 0,
        "source_mutations": 0,
        "workshop_mutations": 0,
        "main_translation_mutations": 0,
        "patch_mutations_after_preflight": 0,
        "direct_launcher_db_writes": 0,
        "saves_created": 0,
        "ollama_calls": 0,
        "git_changes": 0,
        "private_text_output": 0,
        "evidence": str(evidence_dir),
        "next": "owner migration review",
    }
    evidence = evidence_dir / "final-status.json"
    evidence_bytes = _json_bytes(owner_evidence)
    evidence.write_bytes(evidence_bytes)
    return ConsolidationFixture(
        candidate=candidate,
        main_package=main_package,
        source=source,
        supplement=supplement,
        evidence=evidence,
        output_parent=output_parent,
        install_root=install_root,
        application_report=application_report,
        supplement_report=supplement_report,
        owner_evidence=owner_evidence,
        application_report_pin=_sha256(application_report_bytes),
        main_package_pin=_tree_hash(_tree_files(main_package)),
        supplement_package_pin=_tree_hash(_tree_files(supplement)),
        supplement_report_pin=_sha256(supplement_report_bytes),
        supplement_payload_pin=payload_pin,
        supplement_localisation_pin=_sha256(target_bytes),
        supplement_source_pin=_sha256(source_bytes),
        mapping_pin=mapping_pin,
        content_mapping_pin=content_mapping_pin,
        evidence_pin=_sha256(evidence_bytes),
    )


def _run(
    fixture: ConsolidationFixture,
    *,
    output: Path | None = None,
    supplement_package: Path | None = None,
    source: Path | None = None,
    install_root: Path | None = None,
    pins: dict[str, str] | None = None,
) -> dict[str, object]:
    values = {
        "application": fixture.application_report_pin,
        "main": fixture.main_package_pin,
        "package": fixture.supplement_package_pin,
        "report": fixture.supplement_report_pin,
        "payload": fixture.supplement_payload_pin,
        "localisation": fixture.supplement_localisation_pin,
        "source": fixture.supplement_source_pin,
        "mapping": fixture.mapping_pin,
        "content_mapping": fixture.content_mapping_pin,
        "evidence": fixture.evidence_pin,
    }
    if pins:
        values.update(pins)
    return consolidate_reviewed_mod(
        fixture.candidate,
        values["application"],
        fixture.main_package,
        values["main"],
        supplement_package or fixture.supplement,
        values["package"],
        values["report"],
        values["payload"],
        values["localisation"],
        source or fixture.source,
        values["source"],
        values["mapping"],
        values["content_mapping"],
        fixture.evidence,
        values["evidence"],
        output or fixture.output_parent / "consolidated",
        "synthetic_native",
        "Synthetic native translation",
        "NSC3",
        "4.4.*",
        install_root or fixture.install_root,
    )


def _refresh_supplement_report(
    fixture: ConsolidationFixture,
    *,
    raw: bytes | None = None,
) -> None:
    report_bytes = (
        raw if raw is not None else _json_bytes(fixture.supplement_report)
    )
    (fixture.supplement / "package-report.json").write_bytes(report_bytes)
    fixture.supplement_report_pin = _sha256(report_bytes)
    fixture.supplement_package_pin = _tree_hash(
        _tree_files(fixture.supplement)
    )


def _refresh_application_report(
    fixture: ConsolidationFixture,
) -> None:
    localisation_files = [
        (path.relative_to(fixture.candidate), path.read_bytes())
        for path in sorted(
            (fixture.candidate / "localisation/russian").rglob("*.yml")
        )
    ]
    hashes = fixture.application_report["hashes"]
    assert isinstance(hashes, dict)
    hashes["final_output_localisation_sha256"] = _tree_hash(
        localisation_files
    )
    report_bytes = _json_bytes(fixture.application_report)
    (
        fixture.candidate / "review-application-report.json"
    ).write_bytes(report_bytes)
    fixture.application_report_pin = _sha256(report_bytes)


def _refresh_source(
    fixture: ConsolidationFixture, data: bytes
) -> None:
    source_file = (
        fixture.source
        / "localisation/english/replace/synthetic_l_english.yml"
    )
    source_file.write_bytes(data)
    fixture.supplement_source_pin = _sha256(data)
    source_meta = fixture.supplement_report["source"]
    assert isinstance(source_meta, dict)
    source_meta["sha256_before_after"] = fixture.supplement_source_pin
    source_meta["size"] = len(data)
    _refresh_supplement_report(fixture)


def _refresh_evidence(
    fixture: ConsolidationFixture,
    *,
    raw: bytes | None = None,
) -> None:
    evidence_bytes = (
        raw if raw is not None else _json_bytes(fixture.owner_evidence)
    )
    fixture.evidence.write_bytes(evidence_bytes)
    fixture.evidence_pin = _sha256(evidence_bytes)


def _refresh_target(
    fixture: ConsolidationFixture, data: bytes
) -> None:
    target = (
        fixture.supplement
        / "install/synthetic_replace_patch/localisation/"
        "russian/replace/synthetic_l_russian.yml"
    )
    target.write_bytes(data)
    fixture.supplement_localisation_pin = _sha256(data)
    localisation = fixture.supplement_report["localisation"]
    assert isinstance(localisation, dict)
    localisation["sha256"] = fixture.supplement_localisation_pin
    localisation["bytes"] = len(data)
    localisation["crlf_count"] = data.count(b"\r\n")
    localisation["bare_lf_count"] = (
        data.count(b"\n") - data.count(b"\r\n")
    )
    install = fixture.supplement / "install"
    fixture.supplement_payload_pin = _tree_hash(_tree_files(install))
    payload = fixture.supplement_report["payload"]
    assert isinstance(payload, dict)
    payload["tree_sha256"] = fixture.supplement_payload_pin
    _refresh_supplement_report(fixture)


def test_consolidation_builds_exact_package_with_two_provenance_branches(
    tmp_path: Path,
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    output = fixture.output_parent / "consolidated"
    report = _run(fixture, output=output)

    assert report["status"] == (
        "consolidated_reviewed_mod_package_created"
    )
    assert report["schema_version"] == 2
    assert report["construction_mode"] == (
        "reviewed_plus_owner_replace_supplement_v1"
    )
    assert report["counts"] == {
        "source_occurrences": 1698,
        "reviewed_occurrences": 1687,
        "unsupported_occurrences": 11,
        "skipped_files": 0,
    }
    assert report["editorially_approved"] is False
    provenance = report["provenance"]
    assert isinstance(provenance, dict)
    assert set(provenance) == {
        "main_reviewed_candidate",
        "owner_reviewed_replace_supplement",
    }
    main_provenance = provenance["main_reviewed_candidate"]
    supplement_provenance = provenance[
        "owner_reviewed_replace_supplement"
    ]
    assert isinstance(main_provenance, dict)
    assert isinstance(supplement_provenance, dict)
    assert (
        main_provenance["reviewed_package_tree_sha256"]
        == fixture.main_package_pin
    )
    assert (
        supplement_provenance["content_mapping_sha256"]
        == fixture.content_mapping_pin
    )
    inventory = report["inventory"]
    assert isinstance(inventory, dict)
    assert inventory["localisation_file_count"] == 17
    assert inventory["game_content_file_count"] == 19
    assert inventory["package_file_count"] == 20
    assert inventory["native_replace_file_count"] == 1

    files = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    assert len(files) == 20
    assert (
        "install/synthetic_native/localisation/russian/replace/"
        "synthetic_l_russian.yml"
    ) in files
    internal = (
        output / "install/synthetic_native/descriptor.mod"
    ).read_bytes()
    external = (
        output / "install/synthetic_native.mod"
    ).read_bytes()
    for descriptor in (internal, external):
        assert descriptor.count(b'"NSC3"') == 1
        assert b"Synthetic main translation" not in descriptor
        assert b"replace_path" not in descriptor
    report_bytes = (output / "package-report.json").read_bytes()
    assert consolidation.PRIVATE_PATH_RE.search(report_bytes) is None
    assert oct(output.stat().st_mode & 0o777) == "0o700"
    assert all(
        oct(path.stat().st_mode & 0o777) == "0o700"
        for path in output.rglob("*")
        if path.is_dir()
    )
    assert all(
        oct(path.stat().st_mode & 0o777) == "0o600"
        for path in output.rglob("*")
        if path.is_file()
    )


@pytest.mark.parametrize(
    "pin_name",
    [
        "application",
        "main",
        "package",
        "report",
        "payload",
        "localisation",
        "source",
        "mapping",
        "content_mapping",
        "evidence",
    ],
)
def test_every_wrong_pin_is_rejected_before_output(
    tmp_path: Path, pin_name: str
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    output = fixture.output_parent / "consolidated"
    with pytest.raises(SafetyError, match="pin_mismatch"):
        _run(fixture, output=output, pins={pin_name: "f" * 64})
    assert not output.exists()
    assert not any(
        path.name.startswith(".consolidated.tmp-")
        for path in fixture.output_parent.iterdir()
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", True),
        ("schema_version", 1.0),
        ("status", 1),
    ],
)
def test_supplement_report_rejects_bool_float_and_wrong_types(
    tmp_path: Path, field: str, value: object
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    fixture.supplement_report[field] = value
    _refresh_supplement_report(fixture)
    with pytest.raises(SafetyError):
        _run(fixture)
    assert not (fixture.output_parent / "consolidated").exists()


def test_supplement_report_rejects_duplicate_fields(
    tmp_path: Path,
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    original = _json_bytes(fixture.supplement_report)
    raw = original.replace(
        b'{\n  "captured_at_utc"',
        b'{\n  "schema_version": 1,\n  "captured_at_utc"',
        1,
    )
    _refresh_supplement_report(fixture, raw=raw)
    with pytest.raises(SafetyError, match="duplicate_field"):
        _run(fixture)


@pytest.mark.parametrize("change", ["malformed", "missing", "unknown"])
def test_supplement_report_requires_valid_json_and_exact_fields(
    tmp_path: Path, change: str
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    if change == "malformed":
        _refresh_supplement_report(fixture, raw=b"{")
    else:
        if change == "missing":
            del fixture.supplement_report["privacy"]
        else:
            fixture.supplement_report["extra"] = 0
        _refresh_supplement_report(fixture)
    with pytest.raises(SafetyError):
        _run(fixture)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", True),
        ("schema_version", 1.0),
        ("authoritative", 1),
        ("new_relevant_log_errors", False),
    ],
)
def test_owner_evidence_rejects_bool_float_and_wrong_types(
    tmp_path: Path, field: str, value: object
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    fixture.owner_evidence[field] = value
    _refresh_evidence(fixture)
    with pytest.raises(SafetyError):
        _run(fixture)


@pytest.mark.parametrize("change", ["duplicate", "missing", "unknown"])
def test_owner_evidence_rejects_duplicate_or_inexact_fields(
    tmp_path: Path, change: str
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    if change == "duplicate":
        raw = _json_bytes(fixture.owner_evidence).replace(
            b'{\n  "authoritative"',
            b'{\n  "schema_version": 1,\n  "authoritative"',
            1,
        )
        _refresh_evidence(fixture, raw=raw)
    else:
        if change == "missing":
            del fixture.owner_evidence["main_menu"]
        else:
            fixture.owner_evidence["extra"] = 0
        _refresh_evidence(fixture)
    with pytest.raises(SafetyError):
        _run(fixture)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mvp5k_replace_patch_smoke", "PASSPORT"),
        ("load_order", "WRONG"),
        ("known_upstream_nsc3_warning", "NO"),
    ],
)
def test_owner_evidence_requires_closed_smoke_semantics(
    tmp_path: Path, field: str, value: str
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    fixture.owner_evidence[field] = value
    _refresh_evidence(fixture)
    with pytest.raises(SafetyError, match="mismatch"):
        _run(fixture)


@pytest.mark.parametrize("change", ["extra", "missing"])
def test_closed_supplement_inventory_rejects_extra_or_missing_file(
    tmp_path: Path, change: str
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    descriptor = (
        fixture.supplement
        / "install/synthetic_replace_patch/descriptor.mod"
    )
    if change == "extra":
        (fixture.supplement / "extra").write_bytes(b"extra")
    else:
        descriptor.unlink()
    fixture.supplement_package_pin = _tree_hash(
        _tree_files(fixture.supplement)
    )
    with pytest.raises(SafetyError):
        _run(fixture)


@pytest.mark.parametrize("change", ["extra", "missing"])
def test_closed_source_replace_inventory_rejects_extra_or_missing_file(
    tmp_path: Path, change: str
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    source_file = (
        fixture.source
        / "localisation/english/replace/synthetic_l_english.yml"
    )
    if change == "extra":
        (
            fixture.source
            / "localisation/english/replace/extra_l_english.yml"
        ).write_bytes(b'l_english:\n extra:0 "Extra"\n')
    else:
        source_file.unlink()
    with pytest.raises(SafetyError):
        _run(fixture)


@pytest.mark.parametrize(
    "mutation",
    ["key", "order", "version", "protected", "newline", "bom", "header"],
)
def test_source_target_mapping_rejects_semantic_and_structure_drift(
    tmp_path: Path, mutation: str
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    source_file = (
        fixture.source
        / "localisation/english/replace/synthetic_l_english.yml"
    )
    data = source_file.read_bytes()
    if mutation == "key":
        data = data.replace(b"key_0:", b"other_0:", 1)
    elif mutation == "order":
        lines = data.splitlines(keepends=True)
        lines[1], lines[2] = lines[2], lines[1]
        data = b"".join(lines)
    elif mutation == "version":
        data = data.replace(b"key_0:0", b"key_0:9", 1)
    elif mutation == "protected":
        data = data.replace(b"$TOKEN$", b"$OTHER$", 1)
    elif mutation == "newline":
        data = data.replace(b"\r\n", b"\n")
    elif mutation == "bom":
        data = data.removeprefix(b"\xef\xbb\xbf")
    else:
        data = data.replace(b"l_english:", b"l_german:", 1)
    _refresh_source(fixture, data)
    with pytest.raises(SafetyError):
        _run(fixture)


def test_duplicate_source_target_identity_is_rejected(
    tmp_path: Path,
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    source_file = (
        fixture.source
        / "localisation/english/replace/synthetic_l_english.yml"
    )
    target_file = (
        fixture.supplement
        / "install/synthetic_replace_patch/localisation/"
        "russian/replace/synthetic_l_russian.yml"
    )
    _refresh_source(
        fixture,
        source_file.read_bytes().replace(b"key_3:0", b"key_0:0", 1),
    )
    _refresh_target(
        fixture,
        target_file.read_bytes().replace(b"key_3:0", b"key_0:0", 1),
    )
    with pytest.raises(
        SafetyError, match="supplement_duplicate_entry_identity"
    ):
        _run(fixture)


def test_intermediate_source_symlink_is_rejected(
    tmp_path: Path,
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    english = fixture.source / "localisation/english"
    outside = tmp_path / "outside"
    outside.mkdir()
    moved = outside / "english"
    shutil.move(str(english), moved)
    english.symlink_to(moved, target_is_directory=True)
    with pytest.raises(
        SafetyError, match="supplement_source_replace_unsafe_ancestor"
    ):
        _run(fixture)


def test_supplement_main_tree_must_match_exact_main_package(
    tmp_path: Path,
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    main_meta = fixture.supplement_report["main_translation"]
    assert isinstance(main_meta, dict)
    main_meta["tree_sha256"] = "f" * 64
    _refresh_supplement_report(fixture)
    with pytest.raises(
        SafetyError, match="supplement_main_translation_pin_mismatch"
    ):
        _run(fixture)


def test_supplement_must_cover_exact_base_skipped_source(
    tmp_path: Path,
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    base_report_path = (
        fixture.application_report["base_candidate"]
    )
    assert isinstance(base_report_path, str)
    report_path = Path(base_report_path) / "translation-report.json"
    report = json.loads(report_path.read_text())
    report["diagnostics"][0]["path"] = (
        "localisation/english/replace/other_l_english.yml"
    )
    report_bytes = _json_bytes(report)
    report_path.write_bytes(report_bytes)
    hashes = fixture.application_report["hashes"]
    assert isinstance(hashes, dict)
    hashes["pinned_translation_report_sha256"] = _sha256(report_bytes)
    _refresh_application_report(fixture)
    with pytest.raises(
        SafetyError, match="supplement_skipped_source_authority_mismatch"
    ):
        _run(fixture)


def test_additional_file_skipped_diagnostic_is_rejected(
    tmp_path: Path,
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    base_candidate = fixture.application_report["base_candidate"]
    assert isinstance(base_candidate, str)
    report_path = Path(base_candidate) / "translation-report.json"
    report = json.loads(report_path.read_text())
    report["diagnostics"].append(
        {
            "code": "file_skipped",
            "path": "localisation/english/other_l_english.yml",
            "reason": "invalid_utf8",
        }
    )
    report_bytes = _json_bytes(report)
    report_path.write_bytes(report_bytes)
    hashes = fixture.application_report["hashes"]
    assert isinstance(hashes, dict)
    hashes["pinned_translation_report_sha256"] = _sha256(report_bytes)
    _refresh_application_report(fixture)
    with pytest.raises(
        SafetyError, match="supplement_skipped_source_authority_mismatch"
    ):
        _run(fixture)


def test_main_candidate_cannot_already_contain_replace_file(
    tmp_path: Path,
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    relative = Path(
        "localisation/russian/replace/main_l_russian.yml"
    )
    data = b'l_russian:\n main_replace:0 "Synthetic"\n'
    candidate_file = fixture.candidate / relative
    candidate_file.parent.mkdir()
    candidate_file.write_bytes(data)
    main_mod_root = (
        fixture.main_package / "install/synthetic_main"
    )
    packaged_file = main_mod_root / relative
    packaged_file.parent.mkdir()
    packaged_file.write_bytes(data)
    fixture.main_package_pin = _tree_hash(
        _tree_files(fixture.main_package)
    )
    main_meta = fixture.supplement_report["main_translation"]
    assert isinstance(main_meta, dict)
    main_meta["file_count"] = len(_tree_files(main_mod_root))
    main_meta["tree_sha256"] = _tree_hash(
        _tree_files(main_mod_root)
    )
    _refresh_supplement_report(fixture)
    _refresh_application_report(fixture)
    with pytest.raises(
        SafetyError, match="consolidated_replace_inventory_invalid"
    ):
        _run(fixture)


def test_placeholder_residue_is_rejected(
    tmp_path: Path,
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    target = (
        fixture.supplement
        / "install/synthetic_replace_patch/localisation/"
        "russian/replace/synthetic_l_russian.yml"
    )
    _refresh_target(
        fixture,
        target.read_bytes().replace(b"\xd0\xa6\xd0\xb5\xd0\xbb\xd1\x8c", b"__SMT_BAD__", 1),
    )
    with pytest.raises(SafetyError, match="placeholder_residue"):
        _run(fixture)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "socket"])
def test_supplement_rejects_links_and_special_files(
    tmp_path: Path, kind: str
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    path = fixture.supplement / "unsafe"
    if kind == "symlink":
        path.symlink_to(fixture.evidence)
    elif kind == "hardlink":
        os.link(fixture.evidence, path)
    elif kind == "fifo":
        os.mkfifo(path)
    else:
        short_path = Path("/tmp") / f"smt-consolidation-socket-{os.getpid()}"
        if short_path.exists():
            short_path.unlink()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(short_path))
        short_path.rename(path)
    fixture.supplement_package_pin = "f" * 64
    try:
        with pytest.raises(SafetyError):
            _run(fixture)
    finally:
        if kind == "socket":
            server.close()


@pytest.mark.parametrize(
    "entries",
    [
        [(Path("Alpha"), "file"), (Path("alpha"), "file")],
        [
            (Path(unicodedata.normalize("NFC", "café")), "file"),
            (Path(unicodedata.normalize("NFD", "café")), "file"),
        ],
        [(Path("node"), "file"), (Path("node/child"), "file")],
    ],
)
def test_portable_path_collision_classes_fail_closed(
    entries: list[tuple[Path, str]],
) -> None:
    with pytest.raises(SafetyError):
        consolidation._validate_portable_paths(entries, "synthetic")


@pytest.mark.parametrize(
    ("source_role", "supplement_role"),
    [
        ("source", "source"),
        ("candidate", "candidate"),
        ("install", "install"),
    ],
)
def test_source_supplement_and_main_overlap_classes_fail_closed(
    tmp_path: Path,
    source_role: str,
    supplement_role: str,
) -> None:
    roots = {
        "output": tmp_path / "output",
        "candidate": tmp_path / "candidate",
        "source": tmp_path / "source",
        "supplement": tmp_path / "supplement",
        "install": tmp_path / "install",
        "evidence": tmp_path / "evidence",
    }
    for role, path in roots.items():
        if role != "output":
            path.mkdir()
    source = roots[source_role]
    supplement = roots[supplement_role]
    with pytest.raises(SafetyError, match="overlap"):
        consolidation._validate_consolidation_path_relationships(
            output=roots["output"],
            candidate=roots["candidate"],
            source=source,
            main_package=roots["supplement"],
            supplement=supplement,
            install_root=roots["install"],
            evidence=roots["evidence"] / "status.json",
        )


@pytest.mark.parametrize("overlap", ["output", "install"])
def test_authority_overlap_is_rejected(
    tmp_path: Path, overlap: str
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    if overlap == "output":
        output = fixture.source / "new-package"
        install = fixture.install_root
    else:
        output = fixture.output_parent / "consolidated"
        install = fixture.supplement
    with pytest.raises(SafetyError, match="overlap"):
        _run(fixture, output=output, install_root=install)


def test_input_drift_after_materialization_prevents_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    output = fixture.output_parent / "consolidated"
    real_verify = consolidation._verify_consolidation_inputs
    changed = False

    def drift(inputs: consolidation.ConsolidationInputs) -> None:
        nonlocal changed
        if not changed:
            changed = True
            os.utime(fixture.evidence, None)
        real_verify(inputs)

    monkeypatch.setattr(
        consolidation, "_verify_consolidation_inputs", drift
    )
    with pytest.raises(
        SafetyError, match="consolidation_input_generation_changed"
    ):
        _run(fixture, output=output)
    assert not output.exists()


def test_occupied_output_is_preserved(
    tmp_path: Path,
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    output = fixture.output_parent / "consolidated"
    output.mkdir()
    marker = output / "owner-data"
    marker.write_bytes(b"preserve")
    before = marker.stat()
    with pytest.raises(SafetyError, match="output_must_not_exist"):
        _run(fixture, output=output)
    assert marker.read_bytes() == b"preserve"
    assert marker.stat().st_ino == before.st_ino
    assert marker.stat().st_mtime_ns == before.st_mtime_ns


def test_invalid_input_is_rejected_before_temp_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    output = fixture.output_parent / "consolidated"
    payload = fixture.supplement_report["payload"]
    assert isinstance(payload, dict)
    payload["file_count"] = False
    _refresh_supplement_report(fixture)

    def forbidden(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("temp creation must not be reached")

    monkeypatch.setattr(consolidation.tempfile, "mkdtemp", forbidden)
    with pytest.raises(SafetyError):
        _run(fixture, output=output)
    assert not output.exists()


def test_publication_race_preserves_competing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _synthetic_fixture(tmp_path)
    output = fixture.output_parent / "consolidated"

    def race(_source: Path, destination: Path) -> None:
        destination.mkdir()
        (destination / "competitor").write_bytes(b"preserve")
        raise DestinationExistsError("destination appeared")

    monkeypatch.setattr(
        consolidation, "atomic_publish_directory_no_replace", race
    )
    with pytest.raises(
        SafetyError, match="output_appeared_before_publication"
    ):
        _run(fixture, output=output)
    assert (output / "competitor").read_bytes() == b"preserve"


def test_production_atomic_primitive_never_replaces_destination(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    (source / "payload").write_bytes(b"first")
    PRODUCTION_ATOMIC_PUBLISH(source, destination)
    assert (destination / "payload").read_bytes() == b"first"

    collision = tmp_path / "collision"
    collision.mkdir()
    (collision / "payload").write_bytes(b"second")
    with pytest.raises(DestinationExistsError):
        PRODUCTION_ATOMIC_PUBLISH(collision, destination)
    assert (destination / "payload").read_bytes() == b"first"
