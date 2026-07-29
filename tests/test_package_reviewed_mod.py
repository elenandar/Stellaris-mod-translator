from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import socket
import unicodedata

import pytest

from stellaris_mod_translator.engine import SafetyError, _tree_hash
import stellaris_mod_translator.package_reviewed_mod as packaging
from stellaris_mod_translator.package_reviewed_mod import (
    DescriptorSpec,
    package_reviewed_mod,
    parse_strict_descriptor,
    render_descriptor,
)
from stellaris_mod_translator.publication import DestinationExistsError


PRODUCTION_ATOMIC_PUBLISH = (
    packaging.atomic_publish_directory_no_replace
)


@dataclass
class SyntheticInputs:
    source: Path
    base_candidate: Path
    candidate: Path
    planned_install_root: Path
    output_parent: Path
    report: dict[str, object]
    report_pin: str


@pytest.fixture(autouse=True)
def portable_atomic_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def publish(source: Path, destination: Path) -> None:
        if destination.exists() or destination.is_symlink():
            raise DestinationExistsError("destination already exists")
        source.rename(destination)

    monkeypatch.setattr(
        packaging, "atomic_publish_directory_no_replace", publish
    )


def _write_report(candidate: Path, report: dict[str, object]) -> str:
    data = (
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")
    (candidate / "review-application-report.json").write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _localisation_files(candidate: Path) -> list[tuple[Path, bytes]]:
    return [
        (
            path.relative_to(candidate),
            path.read_bytes(),
        )
        for path in sorted((candidate / "localisation/russian").rglob("*.yml"))
    ]


def _refresh_localisation_pin(inputs: SyntheticInputs) -> None:
    hashes = inputs.report["hashes"]
    assert isinstance(hashes, dict)
    hashes["final_output_localisation_sha256"] = _tree_hash(
        _localisation_files(inputs.candidate)
    )
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)


def _synthetic_inputs(
    tmp_path: Path,
    *,
    unsupported: int = 0,
    skipped_files: int = 0,
) -> SyntheticInputs:
    source = tmp_path / "source"
    base_candidate = tmp_path / "base-candidate"
    candidate = tmp_path / "reviewed"
    planned_install_root = tmp_path / "active-mods"
    output_parent = tmp_path / "packages"
    for path in (
        source,
        base_candidate,
        candidate / "localisation/russian/nested",
        planned_install_root,
        output_parent,
    ):
        path.mkdir(parents=True)
    first = b'\xef\xbb\xbfl_russian:\n key_one:0 "Privet"\n'
    second = 'l_russian:\n key_two:0 "Корабль"\n'.encode("utf-8")
    (candidate / "localisation/russian/one_l_russian.yml").write_bytes(
        first
    )
    (
        candidate
        / "localisation/russian/nested/two_l_russian.yml"
    ).write_bytes(second)
    review_entries = 2
    total = review_entries + unsupported
    report: dict[str, object] = {
        "schema_version": 2,
        "status": "full_candidate_review_applied",
        "review_scope": "full_candidate",
        "review_pack_schema_version": 2,
        "candidate_report_schema_version": 3,
        "editorial_status": (
            "human_review_complete_for_reviewable_occurrences"
        ),
        "editorially_approved": (
            unsupported == 0 and skipped_files == 0
        ),
        "source_mod": str(source),
        "base_candidate": str(base_candidate),
        "base_candidate_status": (
            "technical_safe_partial"
            if unsupported or skipped_files
            else "technical_safe"
        ),
        "output": str(candidate),
        "decisions": str(tmp_path / "private-decisions.json"),
        "pack_fingerprint": "a" * 64,
        "model": {"tag": "synthetic:1", "digest": "b" * 64},
        "source_mutations": 0,
        "candidate_mutations": 0,
        "protected_atom_mismatches": 0,
        "ollama_calls": 0,
        "network_calls": 0,
        "counts": {
            "total_decisions": review_entries,
            "accept": 1,
            "edit": 1,
            "reject": 0,
            "actually_changed_spans": 1,
            "restored_english_spans": 0,
        },
        "review_summary": {
            "review_entries": review_entries,
            "accepted_changed": 1,
            "accepted_unchanged": 0,
            "model_fallback": 1,
            "unsupported": unsupported,
            "skipped_files": skipped_files,
            "deferred": 0,
            "pending": 0,
            "total": total,
            "whitespace_warning_entries": 0,
        },
        "technical_residue": {
            "unsupported_occurrences": unsupported,
            "skipped_files": skipped_files,
        },
        "base_candidate_counts": {
            "accepted_unchanged": 0,
            "calls_in_final_run": review_entries,
            "completed": total,
            "completed_occurrences": total,
            "discovered_yml_files": 2 + skipped_files,
            "english_files": 2,
            "fallback": 1 + unsupported,
            "fallback_occurrences": 1 + unsupported,
            "occurrences": total,
            "pending": 0,
            "unsupported_occurrences": unsupported,
            "unsupported": unsupported,
            "skipped_files": skipped_files,
            "pending_occurrences": 0,
            "deferred_occurrences": 0,
            "planned_translation_occurrences": review_entries,
            "reused_from_workspace": 0,
            "reused_from_workspace_occurrences": 0,
            "total": total,
            "total_occurrences": total,
            "translated": 1,
            "translated_occurrences": 1,
            "unchanged_accepted_occurrences": 0,
        },
        "hashes": {
            "source_localisation_sha256": "c" * 64,
            "base_candidate_localisation_sha256": "d" * 64,
            "pinned_translation_report_sha256": "e" * 64,
            "decisions_file_sha256": "f" * 64,
            "final_output_localisation_sha256": _tree_hash(
                _localisation_files(candidate)
            )
        },
    }
    report_pin = _write_report(candidate, report)
    return SyntheticInputs(
        source=source,
        base_candidate=base_candidate,
        candidate=candidate,
        planned_install_root=planned_install_root,
        output_parent=output_parent,
        report=report,
        report_pin=report_pin,
    )


def _run(
    inputs: SyntheticInputs,
    *,
    output: Path | None = None,
    slug: str = "example_ru_local",
    display_name: str = "Example — Русская локализация",
    dependency_name: str = "Example",
    supported_version: str = "4.4.*",
    planned_install_root: Path | None = None,
    allow_technical_residue: bool = False,
) -> dict[str, object]:
    return package_reviewed_mod(
        inputs.candidate,
        inputs.report_pin,
        output or inputs.output_parent / "package",
        slug,
        display_name,
        dependency_name,
        supported_version,
        planned_install_root or inputs.planned_install_root,
        allow_technical_residue=allow_technical_residue,
    )


def test_package_reviewed_mod_builds_exact_private_package(
    tmp_path: Path,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    output = inputs.output_parent / "package"
    report = _run(inputs, output=output)

    expected_files = {
        "install/example_ru_local.mod",
        "install/example_ru_local/descriptor.mod",
        (
            "install/example_ru_local/localisation/russian/"
            "one_l_russian.yml"
        ),
        (
            "install/example_ru_local/localisation/russian/nested/"
            "two_l_russian.yml"
        ),
        "package-report.json",
    }
    actual_files = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    assert actual_files == expected_files
    assert report["status"] == "reviewed_mod_package_created"
    inventory = report["inventory"]
    assert isinstance(inventory, dict)
    assert inventory["package_file_count"] == 5
    assert inventory["game_content_file_count"] == 4
    assert inventory["localisation_file_count"] == 2
    assert report["reviewed_localisation_sha256"] == report[
        "package_localisation_sha256"
    ]
    for relative, data in _localisation_files(inputs.candidate):
        assert (
            output / "install/example_ru_local" / relative
        ).read_bytes() == data
    assert oct(output.stat().st_mode & 0o777) == "0o700"
    assert all(
        oct(path.stat().st_mode & 0o777) == "0o600"
        for path in output.rglob("*")
        if path.is_file()
    )


def test_descriptors_have_exact_required_semantics(tmp_path: Path) -> None:
    inputs = _synthetic_inputs(tmp_path)
    output = inputs.output_parent / "package"
    _run(inputs, output=output)
    internal_data = (
        output / "install/example_ru_local/descriptor.mod"
    ).read_bytes()
    external_data = (
        output / "install/example_ru_local.mod"
    ).read_bytes()
    internal = parse_strict_descriptor(internal_data)
    external = parse_strict_descriptor(external_data)
    expected = {
        "name": "Example — Русская локализация",
        "supported_version": "4.4.*",
        "dependencies": ("Example",),
    }
    assert internal == expected
    assert external == {
        **expected,
        "path": (
            f"{inputs.planned_install_root.as_posix()}/example_ru_local"
        ),
    }
    for data in (internal_data, external_data):
        assert b"remote_file_id" not in data
        assert b"replace_path" not in data
    assert "path" not in internal


def test_package_report_contains_metadata_not_private_artifacts(
    tmp_path: Path,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    output = inputs.output_parent / "package"
    _run(inputs, output=output)
    report_bytes = (output / "package-report.json").read_bytes()
    assert str(inputs.candidate).encode() not in report_bytes
    assert str(inputs.base_candidate).encode() not in report_bytes
    assert b"private-decisions.json" not in report_bytes
    game_files = [
        path
        for path in (output / "install").rglob("*")
        if path.is_file()
    ]
    assert all(
        b"review-application-report.json" not in path.read_bytes()
        for path in game_files
    )
    assert not any(
        path.name == "review-application-report.json" for path in game_files
    )


def test_technical_residue_requires_explicit_allow_and_is_preserved(
    tmp_path: Path,
) -> None:
    inputs = _synthetic_inputs(
        tmp_path, unsupported=11, skipped_files=1
    )
    with pytest.raises(
        SafetyError, match="technical_residue_requires_explicit_allow"
    ):
        _run(inputs)
    report = _run(inputs, allow_technical_residue=True)
    assert report["technical_residue"] == {
        "unsupported_occurrences": 11,
        "skipped_files": 1,
    }
    assert report["editorially_approved"] is False


def test_wrong_application_report_pin_is_rejected(tmp_path: Path) -> None:
    inputs = _synthetic_inputs(tmp_path)
    inputs.report_pin = "0" * 64
    with pytest.raises(SafetyError, match="application_report_pin_mismatch"):
        _run(inputs)


def test_reviewed_localisation_drift_is_rejected(tmp_path: Path) -> None:
    inputs = _synthetic_inputs(tmp_path)
    (
        inputs.candidate
        / "localisation/russian/one_l_russian.yml"
    ).write_bytes(b'l_russian:\n key_one:0 "changed"\n')
    with pytest.raises(SafetyError, match="reviewed_localisation_pin_mismatch"):
        _run(inputs)


def test_candidate_generation_change_before_publication_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    original = packaging._validate_materialized_package

    def validate_and_mutate(*args: object, **kwargs: object) -> None:
        original(*args, **kwargs)
        (
            inputs.candidate
            / "localisation/russian/one_l_russian.yml"
        ).write_bytes(b'l_russian:\n key_one:0 "drift"\n')

    monkeypatch.setattr(
        packaging, "_validate_materialized_package", validate_and_mutate
    )
    with pytest.raises(
        SafetyError, match="reviewed_candidate_generation_changed"
    ):
        _run(inputs)
    assert not (inputs.output_parent / "package").exists()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("schema_version", 1),
        ("status", "bounded_pilot_review_applied"),
        ("review_scope", "partial_candidate"),
        ("review_pack_schema_version", 1),
        ("candidate_report_schema_version", 2),
    ],
)
def test_application_report_identity_is_strict(
    tmp_path: Path, key: str, value: object
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    inputs.report[key] = value
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)
    with pytest.raises(SafetyError, match="application_report_"):
        _run(inputs)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("schema_version", 2.0),
        ("schema_version", True),
        ("schema_version", "2"),
        ("review_pack_schema_version", 2.0),
        ("review_pack_schema_version", True),
        ("review_pack_schema_version", "2"),
        ("candidate_report_schema_version", 3.0),
        ("candidate_report_schema_version", True),
        ("candidate_report_schema_version", "3"),
    ],
)
def test_application_report_version_fields_require_exact_int(
    tmp_path: Path, key: str, value: object
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    inputs.report[key] = value
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)
    with pytest.raises(SafetyError, match="application_report|JSON"):
        _run(inputs)


@pytest.mark.parametrize(
    "key",
    [
        "source_mutations",
        "candidate_mutations",
        "protected_atom_mismatches",
        "ollama_calls",
        "network_calls",
    ],
)
def test_application_report_zero_boundaries_are_strict(
    tmp_path: Path, key: str
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    inputs.report[key] = 1
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)
    with pytest.raises(SafetyError, match=f"{key}_nonzero"):
        _run(inputs)


def test_application_report_requires_complete_decision_algebra(
    tmp_path: Path,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    counts = inputs.report["counts"]
    assert isinstance(counts, dict)
    counts["accept"] = 0
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)
    with pytest.raises(
        SafetyError, match="application_report_decision_counts_invalid"
    ):
        _run(inputs)


def test_decision_algebra_rejects_restored_span_not_changed(
    tmp_path: Path,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    counts = inputs.report["counts"]
    assert isinstance(counts, dict)
    counts.update(
        {
            "accept": 0,
            "edit": 1,
            "reject": 1,
            "actually_changed_spans": 0,
            "restored_english_spans": 1,
        }
    )
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)
    with pytest.raises(
        SafetyError, match="application_report_decision_counts_invalid"
    ):
        _run(inputs)


def test_decision_algebra_rejects_changes_beyond_edits_and_restores(
    tmp_path: Path,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    counts = inputs.report["counts"]
    assert isinstance(counts, dict)
    counts.update(
        {
            "accept": 0,
            "edit": 1,
            "reject": 1,
            "actually_changed_spans": 2,
            "restored_english_spans": 0,
        }
    )
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)
    with pytest.raises(
        SafetyError, match="application_report_decision_counts_invalid"
    ):
        _run(inputs)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("accept", 1.0),
        ("edit", True),
        ("reject", -1),
        ("actually_changed_spans", 1.0),
        ("restored_english_spans", True),
    ],
)
def test_decision_counters_reject_float_bool_and_negative(
    tmp_path: Path, key: str, value: object
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    counts = inputs.report["counts"]
    assert isinstance(counts, dict)
    counts[key] = value
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)
    with pytest.raises(SafetyError, match="application_report|JSON"):
        _run(inputs)


def test_decision_algebra_accepts_unchanged_edit(tmp_path: Path) -> None:
    inputs = _synthetic_inputs(tmp_path)
    counts = inputs.report["counts"]
    assert isinstance(counts, dict)
    counts["actually_changed_spans"] = 0
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)
    report = _run(inputs)
    assert report["status"] == "reviewed_mod_package_created"


def test_decision_algebra_accepts_current_real_relationship() -> None:
    packaging._validate_decision_count_algebra(
        total_decisions=1678,
        accept=619,
        edit=1030,
        reject=29,
        actually_changed=1035,
        restored_english=5,
    )


def test_application_report_rejects_pending_review_entries(
    tmp_path: Path,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    summary = inputs.report["review_summary"]
    assert isinstance(summary, dict)
    summary["pending"] = 1
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)
    with pytest.raises(
        SafetyError, match="application_report_review_scope_incomplete"
    ):
        _run(inputs)


def test_application_report_rejects_duplicate_fields(tmp_path: Path) -> None:
    inputs = _synthetic_inputs(tmp_path)
    data = b'{"schema_version":2,"schema_version":2}'
    (
        inputs.candidate / "review-application-report.json"
    ).write_bytes(data)
    inputs.report_pin = hashlib.sha256(data).hexdigest()
    with pytest.raises(
        SafetyError, match="duplicate_application_report_field"
    ):
        _run(inputs)


@pytest.mark.parametrize(
    "nested",
    [False, True],
)
def test_application_report_rejects_unknown_fields(
    tmp_path: Path, nested: bool
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    target = inputs.report["counts"] if nested else inputs.report
    assert isinstance(target, dict)
    target["unexpected_field"] = 0
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)
    with pytest.raises(SafetyError, match="fields_mismatch"):
        _run(inputs)


def test_application_report_rejects_cross_object_count_contradiction(
    tmp_path: Path,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    base_counts = inputs.report["base_candidate_counts"]
    assert isinstance(base_counts, dict)
    base_counts["total"] = 999
    base_counts["total_occurrences"] = 999
    base_counts["occurrences"] = 999
    base_counts["completed"] = 999
    base_counts["completed_occurrences"] = 999
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)
    with pytest.raises(
        SafetyError, match="application_report_base_counts_mismatch"
    ):
        _run(inputs)


def test_application_report_cannot_claim_approval_with_residue(
    tmp_path: Path,
) -> None:
    inputs = _synthetic_inputs(tmp_path, unsupported=1)
    inputs.report["editorially_approved"] = True
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)
    with pytest.raises(
        SafetyError, match="application_report_editorial_approval_mismatch"
    ):
        _run(inputs, allow_technical_residue=True)


def test_candidate_rejects_unexpected_file(tmp_path: Path) -> None:
    inputs = _synthetic_inputs(tmp_path)
    (inputs.candidate / "private.txt").write_text("not allowed")
    with pytest.raises(
        SafetyError, match="inventory_unexpected_file"
    ):
        _run(inputs)


def test_candidate_rejects_unexpected_directory(tmp_path: Path) -> None:
    inputs = _synthetic_inputs(tmp_path)
    (inputs.candidate / "decisions").mkdir()
    with pytest.raises(
        SafetyError, match="inventory_unexpected_directory"
    ):
        _run(inputs)


def test_candidate_rejects_symlink(tmp_path: Path) -> None:
    inputs = _synthetic_inputs(tmp_path)
    target = inputs.candidate / "localisation/russian/link.yml"
    target.symlink_to(
        inputs.candidate / "localisation/russian/one_l_russian.yml"
    )
    with pytest.raises(SafetyError, match="reviewed_candidate_symlink"):
        _run(inputs)


def test_candidate_rejects_hardlink(tmp_path: Path) -> None:
    inputs = _synthetic_inputs(tmp_path)
    os.link(
        inputs.candidate / "localisation/russian/one_l_russian.yml",
        inputs.candidate / "localisation/russian/hardlink.yml",
    )
    with pytest.raises(SafetyError, match="reviewed_candidate_unsafe_file"):
        _run(inputs)


def test_candidate_rejects_fifo_without_blocking(tmp_path: Path) -> None:
    inputs = _synthetic_inputs(tmp_path)
    os.mkfifo(inputs.candidate / "localisation/russian/fifo.yml")
    with pytest.raises(SafetyError, match="reviewed_candidate_unsafe_file"):
        _run(inputs)


def test_candidate_rejects_socket(tmp_path: Path) -> None:
    inputs = _synthetic_inputs(tmp_path)
    path = inputs.candidate / "localisation/russian/socket.yml"
    short_path = Path("/tmp") / f"smt-package-socket-{os.getpid()}"
    if short_path.exists():
        short_path.unlink()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as value:
        value.bind(str(short_path))
        short_path.rename(path)
        with pytest.raises(
            SafetyError, match="reviewed_candidate_unsafe_file"
        ):
            _run(inputs)


def test_candidate_requires_russian_header(tmp_path: Path) -> None:
    inputs = _synthetic_inputs(tmp_path)
    (
        inputs.candidate
        / "localisation/russian/one_l_russian.yml"
    ).write_bytes(b'l_english:\n key_one:0 "value"\n')
    _refresh_localisation_pin(inputs)
    with pytest.raises(
        SafetyError, match="reviewed_candidate_header_mismatch"
    ):
        _run(inputs)


def test_candidate_rejects_placeholder_residue(tmp_path: Path) -> None:
    inputs = _synthetic_inputs(tmp_path)
    (
        inputs.candidate
        / "localisation/russian/one_l_russian.yml"
    ).write_bytes(b'l_russian:\n key_one:0 "__SMT_ATOM_0__"\n')
    _refresh_localisation_pin(inputs)
    with pytest.raises(
        SafetyError, match="reviewed_candidate_placeholder_residue"
    ):
        _run(inputs)


@pytest.mark.parametrize(
    "marker",
    [
        "/Users/private/review.json",
        "review-decisions-final.json",
        "prompt_profile_hash",
        ".smt-workspace.sqlite3",
    ],
)
def test_candidate_rejects_private_artifact_residue(
    tmp_path: Path, marker: str
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    (
        inputs.candidate
        / "localisation/russian/one_l_russian.yml"
    ).write_text(f'l_russian:\n key_one:0 "{marker}"\n')
    _refresh_localisation_pin(inputs)
    with pytest.raises(
        SafetyError, match="private_artifact_in_localisation"
    ):
        _run(inputs)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "Uppercase",
        "two-hyphens",
        "../escape",
        "with/slash",
        "кириллица",
        "has.dot",
        "a" * 65,
    ],
)
def test_unsafe_slug_is_rejected(tmp_path: Path, value: str) -> None:
    inputs = _synthetic_inputs(tmp_path)
    with pytest.raises(SafetyError, match="unsafe_mod_slug"):
        _run(inputs, slug=value)


@pytest.mark.parametrize(
    "value",
    [
        'quote"',
        "back\\slash",
        "line\nbreak",
        "control\x01",
        "format\u202econtrol",
        "separator\u2028",
    ],
)
def test_descriptor_text_injection_is_rejected(value: str) -> None:
    with pytest.raises(SafetyError, match="unsafe_descriptor_name"):
        render_descriptor(
            DescriptorSpec(
                name=value,
                supported_version="4.4.*",
                dependency="NSC3",
            )
        )


@pytest.mark.parametrize(
    "value",
    ["", "4.*.4", "4.4.x", "v4.4", "4.4.*\npath=", "4\\4"],
)
def test_malformed_supported_version_is_rejected(value: str) -> None:
    with pytest.raises(SafetyError, match="unsafe_supported_version"):
        render_descriptor(
            DescriptorSpec(
                name="Name",
                supported_version=value,
                dependency="NSC3",
            )
        )


@pytest.mark.parametrize(
    "value",
    [
        "relative/path",
        "/tmp/../escape",
        "/tmp//double",
        '/tmp/quote"',
        "/tmp/back\\slash",
        "/tmp/new\nline",
    ],
)
def test_descriptor_path_injection_is_rejected(value: str) -> None:
    with pytest.raises(SafetyError, match="unsafe_descriptor_path"):
        render_descriptor(
            DescriptorSpec(
                name="Name",
                supported_version="4.4.*",
                dependency="NSC3",
                path=value,
            )
        )


@pytest.mark.parametrize(
    "data",
    [
        (
            b'name="A"\nname="B"\nsupported_version="4.4.*"\n'
            b'dependencies={\n\t"NSC3"\n}\n'
        ),
        (
            b'name="A"\nsupported_version="4.4.*"\n'
            b'dependencies={\n\t"NSC3"\n'
        ),
        (
            b'name="A"\nsupported_version="4.4.*"\n'
            b'dependencies={\n\t"NSC3"\n}\nunknown="x"\n'
        ),
        (
            b'name="A"\nsupported_version="4.4.*"\n'
            b'dependencies={\n\t"NSC3"\n}\nremote_file_id="1"\n'
        ),
        (
            b'name="A"\nsupported_version="4.4.*"\n'
            b'dependencies={\n\t"NSC3"\n}\nreplace_path="localisation"\n'
        ),
    ],
)
def test_strict_descriptor_parser_rejects_ambiguous_or_forbidden_data(
    data: bytes,
) -> None:
    with pytest.raises(SafetyError, match="descriptor_"):
        parse_strict_descriptor(data)


@pytest.mark.parametrize(
    "target",
    ["candidate", "source", "base_candidate", "install_root"],
)
def test_output_overlap_is_rejected(tmp_path: Path, target: str) -> None:
    inputs = _synthetic_inputs(tmp_path)
    roots = {
        "candidate": inputs.candidate,
        "source": inputs.source,
        "base_candidate": inputs.base_candidate,
        "install_root": inputs.planned_install_root,
    }
    output = roots[target] / "new-package"
    with pytest.raises(SafetyError, match="overlap"):
        _run(inputs, output=output)
    assert not output.exists()


def test_candidate_and_install_root_overlap_is_rejected(
    tmp_path: Path,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    with pytest.raises(SafetyError, match="overlap"):
        _run(
            inputs,
            planned_install_root=inputs.candidate
            / "localisation/russian",
        )


def _case_alias(path: Path) -> Path:
    alias = path.with_name(path.name.swapcase())
    if (
        alias == path
        or not alias.exists()
        or not os.path.samefile(path, alias)
    ):
        pytest.skip("filesystem does not expose case-insensitive aliases")
    return alias


def _forbid_temp_tree(
    *_args: object, **_kwargs: object
) -> str:
    raise AssertionError("temporary package tree must not be created")


@pytest.mark.parametrize(
    ("authority", "expected_error"),
    [
        ("source", "output_source_overlap"),
        ("base_candidate", "output_base_candidate_overlap"),
        ("reviewed_candidate", "output_reviewed_candidate_overlap"),
        ("install_root", "output_install_root_overlap"),
    ],
)
def test_output_inside_nested_authority_via_symlink_is_rejected_before_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority: str,
    expected_error: str,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    roots = {
        "source": inputs.source,
        "base_candidate": inputs.base_candidate,
        "reviewed_candidate": inputs.candidate,
        "install_root": inputs.planned_install_root,
    }
    nested = roots[authority] / "localisation/russian/nested"
    nested.mkdir(parents=True, exist_ok=True)
    alias = tmp_path / f"{authority}-nested-alias"
    alias.symlink_to(nested, target_is_directory=True)
    output = alias / "new-package"

    monkeypatch.setattr(
        packaging.tempfile, "mkdtemp", _forbid_temp_tree
    )
    with pytest.raises(SafetyError, match=expected_error):
        _run(inputs, output=output)
    assert not output.exists()


def test_nested_authority_symlink_overlap_is_rejected_before_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    nested = inputs.source / "nested"
    nested.mkdir()
    alias = tmp_path / "base-candidate-nested-alias"
    alias.symlink_to(nested, target_is_directory=True)
    inputs.report["base_candidate"] = alias.as_posix()
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)

    monkeypatch.setattr(
        packaging.tempfile, "mkdtemp", _forbid_temp_tree
    )
    with pytest.raises(
        SafetyError, match="source_base_candidate_overlap"
    ):
        _run(inputs)
    assert not (inputs.output_parent / "package").exists()


def test_output_inside_source_via_case_alias_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    output = _case_alias(inputs.source) / "new-package"

    monkeypatch.setattr(
        packaging.tempfile, "mkdtemp", _forbid_temp_tree
    )
    with pytest.raises(SafetyError, match="output_source_overlap"):
        _run(inputs, output=output)
    assert not output.exists()


def test_output_inside_install_root_via_case_alias_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    output = _case_alias(inputs.planned_install_root) / "new-package"
    monkeypatch.setattr(
        packaging.tempfile, "mkdtemp", _forbid_temp_tree
    )
    with pytest.raises(
        SafetyError, match="output_install_root_overlap"
    ):
        _run(inputs, output=output)
    assert not output.exists()


def test_authority_roots_via_portable_physical_alias_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    alias = tmp_path / "source-alias"
    alias.symlink_to(inputs.source, target_is_directory=True)
    inputs.report["base_candidate"] = alias.as_posix()
    inputs.report_pin = _write_report(inputs.candidate, inputs.report)
    monkeypatch.setattr(
        packaging.tempfile, "mkdtemp", _forbid_temp_tree
    )
    with pytest.raises(
        SafetyError, match="source_base_candidate_overlap"
    ):
        _run(inputs)


def test_unicode_normalization_alias_overlap_is_rejected_when_supported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    composed = tmp_path / "caf\u00e9"
    composed.mkdir()
    decomposed = tmp_path / unicodedata.normalize("NFD", "caf\u00e9")
    if (
        composed == decomposed
        or not decomposed.exists()
        or not os.path.samefile(composed, decomposed)
    ):
        pytest.skip(
            "filesystem does not expose Unicode normalization aliases"
        )
    output = decomposed / "new-package"
    monkeypatch.setattr(
        packaging.tempfile, "mkdtemp", _forbid_temp_tree
    )
    with pytest.raises(
        SafetyError, match="output_install_root_overlap"
    ):
        _run(
            inputs,
            output=output,
            planned_install_root=composed,
        )
    assert not output.exists()


def test_physical_overlap_algorithm_detects_portable_alias(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    real_identity = packaging._physical_path_identity(
        real,
        label="real",
        must_exist=True,
    )
    alias_identity = packaging._physical_path_identity(
        alias,
        label="alias",
        must_exist=True,
    )
    assert packaging._physical_paths_overlap(
        real_identity, alias_identity
    )


def test_safe_independent_physical_roots_package_successfully(
    tmp_path: Path,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    output = inputs.output_parent / "independent-package"
    _run(inputs, output=output)
    assert output.is_dir()


def test_no_clobber_collision_preserves_existing_package(
    tmp_path: Path,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    output = inputs.output_parent / "package"
    output.mkdir()
    marker = output / "owner-data"
    marker.write_bytes(b"preserve")
    before = marker.stat()
    with pytest.raises(SafetyError, match="output_must_not_exist"):
        _run(inputs, output=output)
    assert marker.read_bytes() == b"preserve"
    assert marker.stat().st_ino == before.st_ino
    assert marker.stat().st_mtime_ns == before.st_mtime_ns


def test_publication_race_preserves_competing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    output = inputs.output_parent / "package"

    def race(_source: Path, destination: Path) -> None:
        destination.mkdir()
        (destination / "competitor").write_bytes(b"preserve")
        raise DestinationExistsError("destination appeared")

    monkeypatch.setattr(
        packaging, "atomic_publish_directory_no_replace", race
    )
    with pytest.raises(
        SafetyError, match="output_appeared_before_publication"
    ):
        _run(inputs, output=output)
    assert (output / "competitor").read_bytes() == b"preserve"
    assert not any(
        item.name.startswith(".package.tmp-")
        for item in inputs.output_parent.iterdir()
    )


def test_production_atomic_primitive_never_replaces_destination(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    (source / "payload").write_bytes(b"first")
    PRODUCTION_ATOMIC_PUBLISH(source, destination)
    assert not source.exists()
    assert (destination / "payload").read_bytes() == b"first"

    collision_source = tmp_path / "collision-source"
    collision_source.mkdir()
    (collision_source / "payload").write_bytes(b"second")
    destination_before = (
        (destination / "payload").read_bytes(),
        (destination / "payload").stat().st_ino,
        (destination / "payload").stat().st_mtime_ns,
    )
    with pytest.raises(DestinationExistsError):
        PRODUCTION_ATOMIC_PUBLISH(collision_source, destination)
    assert collision_source.exists()
    assert (
        (destination / "payload").read_bytes(),
        (destination / "payload").stat().st_ino,
        (destination / "payload").stat().st_mtime_ns,
    ) == destination_before


def test_source_candidates_install_root_and_launcher_stay_unchanged(
    tmp_path: Path,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    source_marker = inputs.source / "descriptor.mod"
    base_marker = inputs.base_candidate / "translation-report.json"
    active_marker = inputs.planned_install_root / "existing.mod"
    launcher_marker = tmp_path / "launcher-v2.sqlite"
    markers = {
        source_marker: b"source",
        base_marker: b"base",
        active_marker: b"active",
        launcher_marker: b"launcher",
    }
    for path, data in markers.items():
        path.write_bytes(data)
    before = {
        path: (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
        for path in markers
    }
    candidate_before = {
        path.relative_to(inputs.candidate).as_posix(): (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_mtime_ns,
        )
        for path in inputs.candidate.rglob("*")
        if path.is_file()
    }
    _run(inputs)
    assert {
        path: (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
        for path in markers
    } == before
    assert {
        path.relative_to(inputs.candidate).as_posix(): (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_mtime_ns,
        )
        for path in inputs.candidate.rglob("*")
        if path.is_file()
    } == candidate_before


def test_package_report_and_descriptor_hashes_are_exact(
    tmp_path: Path,
) -> None:
    inputs = _synthetic_inputs(tmp_path)
    output = inputs.output_parent / "package"
    report = _run(inputs, output=output)
    hashes = report["descriptor_hashes"]
    assert isinstance(hashes, dict)
    assert hashes["internal_descriptor_sha256"] == hashlib.sha256(
        (output / "install/example_ru_local/descriptor.mod").read_bytes()
    ).hexdigest()
    assert hashes["external_descriptor_sha256"] == hashlib.sha256(
        (output / "install/example_ru_local.mod").read_bytes()
    ).hexdigest()
    assert report == json.loads(
        (output / "package-report.json").read_text()
    )
