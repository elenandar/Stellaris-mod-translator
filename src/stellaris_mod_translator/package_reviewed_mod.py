"""Build a private, installable local mod package from a reviewed candidate."""

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
from .parser import ParseError, parse_localisation
from .publication import (
    AtomicPublicationUnavailable,
    DestinationExistsError,
    atomic_publish_directory_no_replace,
)


APPLICATION_REPORT_NAME = "review-application-report.json"
PACKAGE_REPORT_NAME = "package-report.json"
PACKAGE_REPORT_SCHEMA_VERSION = 1
MAX_APPLICATION_REPORT_BYTES = 1024 * 1024
MAX_LOCALISATION_FILE_BYTES = 32 * 1024 * 1024
SHA256_RE = re.compile(r"[0-9a-f]{64}")
MOD_SLUG_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")
SUPPORTED_VERSION_RE = re.compile(r"[0-9]+(?:\.[0-9]+)*(?:\.\*)?")
DESCRIPTOR_FIELD_RE = re.compile(r'([a-z_]+)="([^"\\\r\n]*)"')
DESCRIPTOR_DEPENDENCY_RE = re.compile(r'\t"([^"\\\r\n]*)"')
PRIVATE_PATH_RE = re.compile(
    rb"(?<![A-Za-z0-9_])/(?:Users|home|private|Volumes|tmp)/"
)
PRIVATE_ARTIFACT_MARKERS = (
    b"review-application-report.json",
    b"review-decisions",
    b"decisions.json",
    b"review-pack-summary.json",
    b"translation-report.json",
    b"prompt_profile_hash",
    b"checkpoint_boundary",
    b".smt-workspace",
)
APPLICATION_REPORT_FIELDS = frozenset(
    {
        "base_candidate",
        "base_candidate_counts",
        "base_candidate_status",
        "candidate_mutations",
        "candidate_report_schema_version",
        "counts",
        "decisions",
        "editorial_status",
        "editorially_approved",
        "hashes",
        "model",
        "network_calls",
        "ollama_calls",
        "output",
        "pack_fingerprint",
        "protected_atom_mismatches",
        "review_pack_schema_version",
        "review_scope",
        "review_summary",
        "schema_version",
        "source_mod",
        "source_mutations",
        "status",
        "technical_residue",
    }
)
APPLICATION_COUNTS_FIELDS = frozenset(
    {
        "total_decisions",
        "accept",
        "edit",
        "reject",
        "actually_changed_spans",
        "restored_english_spans",
    }
)
APPLICATION_REVIEW_SUMMARY_FIELDS = frozenset(
    {
        "accepted_changed",
        "accepted_unchanged",
        "deferred",
        "model_fallback",
        "pending",
        "review_entries",
        "skipped_files",
        "total",
        "unsupported",
        "whitespace_warning_entries",
    }
)
APPLICATION_TECHNICAL_RESIDUE_FIELDS = frozenset(
    {"unsupported_occurrences", "skipped_files"}
)
APPLICATION_BASE_COUNT_FIELDS = frozenset(
    {
        "accepted_unchanged",
        "calls_in_final_run",
        "completed",
        "completed_occurrences",
        "deferred_occurrences",
        "discovered_yml_files",
        "english_files",
        "fallback",
        "fallback_occurrences",
        "occurrences",
        "pending",
        "pending_occurrences",
        "planned_translation_occurrences",
        "reused_from_workspace",
        "reused_from_workspace_occurrences",
        "skipped_files",
        "total",
        "total_occurrences",
        "translated",
        "translated_occurrences",
        "unchanged_accepted_occurrences",
        "unsupported",
        "unsupported_occurrences",
    }
)
APPLICATION_HASH_FIELDS = frozenset(
    {
        "source_localisation_sha256",
        "base_candidate_localisation_sha256",
        "pinned_translation_report_sha256",
        "decisions_file_sha256",
        "final_output_localisation_sha256",
    }
)
APPLICATION_MODEL_FIELDS = frozenset({"tag", "digest"})


@dataclass(frozen=True)
class StableFile:
    relative: Path
    data: bytes
    sha256: str
    stat_identity: tuple[int, int, int, int, int, int, int]


@dataclass(frozen=True)
class ReviewedCandidateSnapshot:
    root: Path
    directories: tuple[
        tuple[str, tuple[int, int, int, int, int, int, int]], ...
    ]
    files: tuple[StableFile, ...]
    localisation_files: tuple[StableFile, ...]
    localisation_sha256: str


@dataclass(frozen=True)
class DescriptorSpec:
    name: str
    supported_version: str
    dependency: str
    path: str | None = None


DirectoryIdentity = tuple[int, int]


@dataclass(frozen=True)
class PhysicalPathIdentity:
    path: Path
    anchor_identity: DirectoryIdentity
    ancestor_identities: tuple[DirectoryIdentity, ...]
    missing_parts: tuple[str, ...]
    exact_exists: bool


def package_reviewed_mod(
    reviewed_candidate: Path,
    application_report_sha256: str,
    output: Path,
    mod_slug: str,
    display_name: str,
    dependency_name: str,
    supported_version: str,
    planned_install_root: Path,
    *,
    allow_technical_residue: bool = False,
) -> dict[str, object]:
    """Create an atomic no-clobber install package without touching active paths."""
    if (
        not isinstance(application_report_sha256, str)
        or SHA256_RE.fullmatch(application_report_sha256) is None
    ):
        raise SafetyError("invalid_application_report_sha256")
    candidate_root = _validated_candidate_root(reviewed_candidate)
    output_abs = _validated_package_output(candidate_root, output)
    slug = _validated_mod_slug(mod_slug)
    root_text, install_root = _validated_planned_install_root(
        planned_install_root
    )
    name = _validated_descriptor_text(display_name, "display_name")
    dependency = _validated_descriptor_text(
        dependency_name, "dependency_name"
    )
    version = _validated_supported_version(supported_version)
    planned_mod_path = f"{root_text}/{slug}"
    planned_descriptor_path = f"{root_text}/{slug}.mod"

    snapshot = _snapshot_reviewed_candidate(candidate_root)
    report_file = _snapshot_file(
        snapshot, Path(APPLICATION_REPORT_NAME)
    )
    if report_file.sha256 != application_report_sha256:
        raise SafetyError("application_report_pin_mismatch")
    report = _load_application_report(report_file.data)
    residue = _validate_application_report(
        report,
        candidate_root=candidate_root,
        localisation_sha256=snapshot.localisation_sha256,
        allow_technical_residue=allow_technical_residue,
    )
    _validate_path_relationships(
        output_abs,
        candidate_root,
        install_root,
        report,
    )
    _validate_private_content_absent(snapshot.localisation_files, report)

    internal_spec = DescriptorSpec(
        name=name,
        supported_version=version,
        dependency=dependency,
    )
    external_spec = DescriptorSpec(
        name=name,
        supported_version=version,
        dependency=dependency,
        path=planned_mod_path,
    )
    internal_descriptor = render_descriptor(internal_spec)
    external_descriptor = render_descriptor(external_spec)
    internal_descriptor_sha256 = _sha256(internal_descriptor)
    external_descriptor_sha256 = _sha256(external_descriptor)

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
        for item in snapshot.localisation_files:
            target = mod_root / item.relative
            _mkdir_private_parents(target.parent, mod_root)
            _write_new(target, item.data)

        report_payload = _package_report(
            application_report_sha256=application_report_sha256,
            reviewed_localisation_sha256=snapshot.localisation_sha256,
            package_localisation_sha256=_tree_hash(
                [
                    (item.relative, item.data)
                    for item in snapshot.localisation_files
                ]
            ),
            internal_descriptor_sha256=internal_descriptor_sha256,
            external_descriptor_sha256=external_descriptor_sha256,
            localisation_files=snapshot.localisation_files,
            mod_slug=slug,
            display_name=name,
            dependency_name=dependency,
            supported_version=version,
            planned_install_root=root_text,
            planned_mod_path=planned_mod_path,
            planned_descriptor_path=planned_descriptor_path,
            technical_residue=residue,
            editorial_status=report["editorial_status"],
            editorially_approved=report["editorially_approved"],
        )
        report_bytes = (
            json.dumps(
                report_payload,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        _write_new(temp / PACKAGE_REPORT_NAME, report_bytes)
        _validate_materialized_package(
            temp,
            report_payload=report_payload,
            report_bytes=report_bytes,
            internal_spec=internal_spec,
            external_spec=external_spec,
            internal_descriptor=internal_descriptor,
            external_descriptor=external_descriptor,
            localisation_files=snapshot.localisation_files,
        )
        _verify_reviewed_candidate_snapshot(snapshot)
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
    return report_payload


def render_descriptor(spec: DescriptorSpec) -> bytes:
    """Render and re-parse the supported descriptor subset."""
    name = _validated_descriptor_text(spec.name, "descriptor_name")
    version = _validated_supported_version(spec.supported_version)
    dependency = _validated_descriptor_text(
        spec.dependency, "descriptor_dependency"
    )
    path = (
        None
        if spec.path is None
        else _validated_descriptor_path(spec.path)
    )
    fields = [
        f'name="{name}"',
        f'supported_version="{version}"',
        "dependencies={",
        f'\t"{dependency}"',
        "}",
    ]
    if path is not None:
        fields.append(f'path="{path}"')
    data = ("\n".join(fields) + "\n").encode("utf-8")
    parsed = parse_strict_descriptor(data)
    expected = {
        "name": name,
        "supported_version": version,
        "dependencies": (dependency,),
    }
    if path is not None:
        expected["path"] = path
    if parsed != expected:
        raise SafetyError("descriptor_roundtrip_mismatch")
    return data


def parse_strict_descriptor(data: bytes) -> dict[str, object]:
    """Parse only the canonical local descriptor subset and reject ambiguity."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SafetyError("descriptor_invalid_utf8") from exc
    if not text.endswith("\n") or "\r" in text or "\ufeff" in text:
        raise SafetyError("descriptor_malformed")
    lines = text[:-1].split("\n")
    fields: dict[str, object] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if line == "dependencies={":
            if "dependencies" in fields:
                raise SafetyError("descriptor_duplicate_field")
            dependencies: list[str] = []
            index += 1
            while index < len(lines) and lines[index] != "}":
                match = DESCRIPTOR_DEPENDENCY_RE.fullmatch(lines[index])
                if match is None:
                    raise SafetyError("descriptor_malformed")
                dependencies.append(
                    _validated_descriptor_text(
                        match.group(1), "descriptor_dependency"
                    )
                )
                index += 1
            if index >= len(lines) or lines[index] != "}":
                raise SafetyError("descriptor_malformed")
            if len(dependencies) != 1:
                raise SafetyError("descriptor_dependency_count_invalid")
            fields["dependencies"] = tuple(dependencies)
            index += 1
            continue
        match = DESCRIPTOR_FIELD_RE.fullmatch(line)
        if match is None:
            raise SafetyError("descriptor_malformed")
        key, value = match.groups()
        if key in fields:
            raise SafetyError("descriptor_duplicate_field")
        if key in {"remote_file_id", "replace_path"}:
            raise SafetyError("descriptor_forbidden_field")
        if key not in {"name", "supported_version", "path"}:
            raise SafetyError("descriptor_unknown_field")
        if key == "supported_version":
            fields[key] = _validated_supported_version(value)
        elif key == "path":
            fields[key] = _validated_descriptor_path(value)
        else:
            fields[key] = _validated_descriptor_text(
                value, "descriptor_name"
            )
        index += 1
    if set(fields) not in (
        {"name", "supported_version", "dependencies"},
        {"name", "supported_version", "dependencies", "path"},
    ):
        raise SafetyError("descriptor_required_field_missing")
    return fields


def _validated_candidate_root(path: Path) -> Path:
    lexical = path.absolute()
    if path.is_symlink():
        raise SafetyError("reviewed_candidate_root_symlink")
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise SafetyError("reviewed_candidate_root_missing") from exc
    if not resolved.is_dir():
        raise SafetyError("reviewed_candidate_root_not_directory")
    return resolved


def _validated_package_output(candidate: Path, output: Path) -> Path:
    lexical = output.absolute()
    if output.exists() or output.is_symlink():
        raise SafetyError("output_must_not_exist")
    _validated_absolute_path_text(lexical.as_posix(), "output")
    parent = lexical.parent
    if parent.is_symlink() and not parent.exists():
        raise SafetyError("output_parent_missing")
    try:
        parent_is_directory = parent.is_dir()
    except OSError as exc:
        raise SafetyError("output_parent_missing") from exc
    if not parent_is_directory:
        raise SafetyError("output_parent_not_directory")
    if _paths_overlap(candidate, lexical):
        raise SafetyError("reviewed_candidate_output_overlap")
    return lexical


def _validated_mod_slug(value: str) -> str:
    if not isinstance(value, str) or MOD_SLUG_RE.fullmatch(value) is None:
        raise SafetyError("unsafe_mod_slug")
    return value


def _validated_descriptor_text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 255:
        raise SafetyError(f"invalid_{label}")
    _validate_safe_unicode(value, f"unsafe_{label}")
    if '"' in value or "\\" in value or "\n" in value or "\r" in value:
        raise SafetyError(f"unsafe_{label}")
    return value


def _validated_supported_version(value: str) -> str:
    if (
        not isinstance(value, str)
        or SUPPORTED_VERSION_RE.fullmatch(value) is None
    ):
        raise SafetyError("unsafe_supported_version")
    return value


def _validated_planned_install_root(path: Path) -> tuple[str, Path]:
    text = os.fspath(path)
    if not isinstance(text, str):
        raise SafetyError("unsafe_planned_install_root")
    canonical_text = _validated_absolute_path_text(
        text, "planned_install_root"
    )
    if canonical_text == "/":
        raise SafetyError("unsafe_planned_install_root")
    return canonical_text, Path(canonical_text)


def _validated_descriptor_path(value: str) -> str:
    return _validated_absolute_path_text(value, "descriptor_path")


def _validated_absolute_path_text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise SafetyError(f"unsafe_{label}")
    _validate_safe_unicode(value, f"unsafe_{label}")
    if '"' in value or "\\" in value or "\n" in value or "\r" in value:
        raise SafetyError(f"unsafe_{label}")
    path = Path(value)
    if (
        not path.is_absolute()
        or value != path.as_posix()
        or any(part in {".", ".."} for part in path.parts)
    ):
        raise SafetyError(f"unsafe_{label}")
    return value


def _validate_safe_unicode(value: str, error: str) -> None:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SafetyError(error) from exc
    if any(
        ord(char) < 0x20
        or ord(char) == 0x7F
        or 0x80 <= ord(char) <= 0x9F
        or char in "\u2028\u2029\ufeff"
        or unicodedata.category(char) == "Cf"
        for char in value
    ):
        raise SafetyError(error)


def _snapshot_reviewed_candidate(root: Path) -> ReviewedCandidateSnapshot:
    directories: list[
        tuple[str, tuple[int, int, int, int, int, int, int]]
    ] = []
    files: list[StableFile] = []

    def fail_walk(error: OSError) -> None:
        raise SafetyError("reviewed_candidate_inventory_failed") from error

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
                _validate_candidate_relative_path(relative)
                if not _allowed_candidate_directory(relative):
                    raise SafetyError(
                        "reviewed_candidate_inventory_unexpected_directory"
                    )
                directories.append(
                    (relative.as_posix(), _stable_directory_identity(path))
                )
            for name in filenames:
                path = current_path / name
                relative = path.relative_to(root)
                _validate_candidate_relative_path(relative)
                if not _allowed_candidate_file(relative):
                    raise SafetyError(
                        "reviewed_candidate_inventory_unexpected_file"
                    )
                maximum = (
                    MAX_APPLICATION_REPORT_BYTES
                    if relative == Path(APPLICATION_REPORT_NAME)
                    else MAX_LOCALISATION_FILE_BYTES
                )
                files.append(
                    _read_stable_regular_file(
                        path,
                        relative,
                        max_bytes=maximum,
                    )
                )
    except SafetyError:
        raise
    except OSError as exc:
        raise SafetyError("reviewed_candidate_inventory_failed") from exc

    files.sort(key=lambda item: item.relative.as_posix())
    directories.sort()
    report_files = [
        item
        for item in files
        if item.relative == Path(APPLICATION_REPORT_NAME)
    ]
    localisation_files = [
        item
        for item in files
        if item.relative != Path(APPLICATION_REPORT_NAME)
    ]
    if len(report_files) != 1:
        raise SafetyError("application_report_missing")
    if not localisation_files:
        raise SafetyError("reviewed_candidate_localisation_missing")
    for item in localisation_files:
        _validate_localisation_file(item)
    return ReviewedCandidateSnapshot(
        root=root,
        directories=tuple(directories),
        files=tuple(files),
        localisation_files=tuple(localisation_files),
        localisation_sha256=_tree_hash(
            [(item.relative, item.data) for item in localisation_files]
        ),
    )


def _validate_candidate_relative_path(relative: Path) -> None:
    if relative.is_absolute() or ".." in relative.parts:
        raise SafetyError("reviewed_candidate_unsafe_path")
    for part in relative.parts:
        _validate_safe_unicode(part, "reviewed_candidate_unsafe_path")


def _allowed_candidate_directory(relative: Path) -> bool:
    return relative == Path("localisation") or relative == Path(
        "localisation/russian"
    ) or (
        len(relative.parts) > 2
        and relative.parts[:2] == ("localisation", "russian")
    )


def _allowed_candidate_file(relative: Path) -> bool:
    if relative == Path(APPLICATION_REPORT_NAME):
        return True
    return (
        len(relative.parts) >= 3
        and relative.parts[:2] == ("localisation", "russian")
        and relative.suffix == ".yml"
    )


def _stable_directory_identity(
    path: Path,
) -> tuple[int, int, int, int, int, int, int]:
    before = path.lstat()
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
        raise SafetyError("reviewed_candidate_unsafe_directory")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    after = path.lstat()
    identities = tuple(
        _full_stat_identity(value) for value in (before, opened, after)
    )
    if (
        not stat.S_ISDIR(opened.st_mode)
        or identities[0] != identities[1]
        or identities[1] != identities[2]
    ):
        raise SafetyError("reviewed_candidate_directory_changed_during_read")
    return identities[1]


def _read_stable_regular_file(
    path: Path,
    relative: Path,
    *,
    max_bytes: int,
) -> StableFile:
    if path.is_symlink():
        raise SafetyError("reviewed_candidate_symlink")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise SafetyError("reviewed_candidate_unsafe_file") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > max_bytes
        ):
            raise SafetyError("reviewed_candidate_unsafe_file")
        chunks: list[bytes] = []
        byte_count = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            byte_count += len(chunk)
            if byte_count > max_bytes:
                raise SafetyError("reviewed_candidate_file_too_large")
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    before_identity = _full_stat_identity(before)
    after_identity = _full_stat_identity(after)
    if before_identity != after_identity or byte_count != before.st_size:
        raise SafetyError("reviewed_candidate_file_changed_during_read")
    path_after = path.lstat()
    if _full_stat_identity(path_after) != after_identity:
        raise SafetyError("reviewed_candidate_file_replaced_during_read")
    data = b"".join(chunks)
    return StableFile(
        relative=relative,
        data=data,
        sha256=_sha256(data),
        stat_identity=after_identity,
    )


def _full_stat_identity(
    value: os.stat_result,
) -> tuple[int, int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _validate_localisation_file(item: StableFile) -> None:
    if b"__SMT_" in item.data:
        raise SafetyError("reviewed_candidate_placeholder_residue")
    try:
        parsed = parse_localisation(item.data)
    except ParseError as exc:
        raise SafetyError("reviewed_candidate_localisation_invalid") from exc
    if parsed.language != "russian" or parsed.header_line != 0:
        raise SafetyError("reviewed_candidate_header_mismatch")


def _snapshot_file(
    snapshot: ReviewedCandidateSnapshot, relative: Path
) -> StableFile:
    matches = [item for item in snapshot.files if item.relative == relative]
    if len(matches) != 1:
        raise SafetyError("application_report_missing")
    return matches[0]


def _load_application_report(data: bytes) -> dict[str, object]:
    try:
        payload = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_unique_application_report_object,
            parse_float=_reject_json_float,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise SafetyError("invalid_application_report_json") from exc
    if not isinstance(payload, dict):
        raise SafetyError("invalid_application_report_json")
    return payload


def _unique_application_report_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise SafetyError("duplicate_application_report_field")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"invalid JSON constant: {value}")


def _reject_json_float(value: str) -> object:
    raise ValueError(f"JSON float is forbidden: {value}")


def _validate_application_report(
    report: dict[str, object],
    *,
    candidate_root: Path,
    localisation_sha256: str,
    allow_technical_residue: bool,
) -> dict[str, int]:
    _require_exact_fields(
        report,
        APPLICATION_REPORT_FIELDS,
        "application_report",
    )
    expected_scalars: dict[str, object] = {
        "schema_version": 2,
        "status": "full_candidate_review_applied",
        "review_scope": "full_candidate",
        "review_pack_schema_version": 2,
        "candidate_report_schema_version": 3,
        "editorial_status": (
            "human_review_complete_for_reviewable_occurrences"
        ),
    }
    for key, expected in expected_scalars.items():
        actual = report.get(key)
        if (
            type(expected) is int
            and (type(actual) is not int or actual != expected)
        ) or (type(expected) is not int and actual != expected):
            raise SafetyError(f"application_report_{key}_mismatch")
    if report.get("output") != str(candidate_root):
        raise SafetyError("application_report_output_mismatch")
    for key in (
        "source_mutations",
        "candidate_mutations",
        "protected_atom_mismatches",
        "ollama_calls",
        "network_calls",
    ):
        if report.get(key) != 0 or isinstance(report.get(key), bool):
            raise SafetyError(f"application_report_{key}_nonzero")

    counts = _require_object(report, "counts")
    _require_exact_fields(
        counts,
        APPLICATION_COUNTS_FIELDS,
        "application_report_counts",
    )
    total_decisions = _report_count(counts, "total_decisions")
    accept = _report_count(counts, "accept")
    edit = _report_count(counts, "edit")
    reject = _report_count(counts, "reject")
    actually_changed = _report_count(counts, "actually_changed_spans")
    restored_english = _report_count(counts, "restored_english_spans")
    _validate_decision_count_algebra(
        total_decisions=total_decisions,
        accept=accept,
        edit=edit,
        reject=reject,
        actually_changed=actually_changed,
        restored_english=restored_english,
    )

    summary = _require_object(report, "review_summary")
    _require_exact_fields(
        summary,
        APPLICATION_REVIEW_SUMMARY_FIELDS,
        "application_report_review_summary",
    )
    review_entries = _report_count(summary, "review_entries")
    pending = _report_count(summary, "pending")
    deferred = _report_count(summary, "deferred")
    accepted_changed = _report_count(summary, "accepted_changed")
    accepted_unchanged = _report_count(summary, "accepted_unchanged")
    model_fallback = _report_count(summary, "model_fallback")
    unsupported = _report_count(summary, "unsupported")
    skipped_files = _report_count(summary, "skipped_files")
    total = _report_count(summary, "total")
    whitespace_warnings = _report_count(
        summary, "whitespace_warning_entries"
    )
    if (
        pending != 0
        or deferred != 0
        or review_entries != total_decisions
        or accepted_changed + accepted_unchanged + model_fallback
        != review_entries
        or review_entries + unsupported != total
        or whitespace_warnings > review_entries
    ):
        raise SafetyError("application_report_review_scope_incomplete")

    technical = _require_object(report, "technical_residue")
    _require_exact_fields(
        technical,
        APPLICATION_TECHNICAL_RESIDUE_FIELDS,
        "application_report_technical_residue",
    )
    technical_unsupported = _report_count(
        technical, "unsupported_occurrences"
    )
    technical_skipped = _report_count(technical, "skipped_files")
    if (
        technical_unsupported != unsupported
        or technical_skipped != skipped_files
    ):
        raise SafetyError("application_report_technical_residue_mismatch")

    base_counts = _require_object(report, "base_candidate_counts")
    _require_exact_fields(
        base_counts,
        APPLICATION_BASE_COUNT_FIELDS,
        "application_report_base_candidate_counts",
    )
    base = {
        key: _report_count(base_counts, key)
        for key in APPLICATION_BASE_COUNT_FIELDS
    }
    if (
        base["total"] != total
        or base["total_occurrences"] != total
        or base["occurrences"] != total
        or base["completed"] != total
        or base["completed_occurrences"] != total
        or base["planned_translation_occurrences"] != review_entries
        or base["unsupported"] != unsupported
        or base["unsupported_occurrences"] != unsupported
        or base["skipped_files"] != skipped_files
        or base["pending"] != 0
        or base["pending_occurrences"] != 0
        or base["deferred_occurrences"] != 0
        or base["translated"] != base["translated_occurrences"]
        or base["accepted_unchanged"]
        != base["unchanged_accepted_occurrences"]
        or base["accepted_unchanged"] != accepted_unchanged
        or base["fallback"] != base["fallback_occurrences"]
        or base["reused_from_workspace"]
        != base["reused_from_workspace_occurrences"]
        or base["translated"]
        != accepted_changed + accepted_unchanged
        or base["fallback"] != model_fallback + unsupported
        or base["translated"] + base["fallback"] != total
        or base["reused_from_workspace"] + base["calls_in_final_run"]
        != review_entries
        or base["english_files"] > base["discovered_yml_files"]
        or base["skipped_files"] > base["discovered_yml_files"]
    ):
        raise SafetyError("application_report_base_counts_mismatch")
    base_status = report.get("base_candidate_status")
    expected_base_status = (
        "technical_safe_partial"
        if unsupported or skipped_files
        else "technical_safe"
    )
    if base_status != expected_base_status:
        raise SafetyError("application_report_base_status_mismatch")

    editorially_approved = report.get("editorially_approved")
    expected_approval = unsupported == 0 and skipped_files == 0
    if (
        not isinstance(editorially_approved, bool)
        or editorially_approved is not expected_approval
    ):
        raise SafetyError("application_report_editorial_approval_mismatch")
    if (unsupported or skipped_files) and not allow_technical_residue:
        raise SafetyError("technical_residue_requires_explicit_allow")

    pack_fingerprint = report.get("pack_fingerprint")
    if (
        not isinstance(pack_fingerprint, str)
        or SHA256_RE.fullmatch(pack_fingerprint) is None
    ):
        raise SafetyError("application_report_pack_fingerprint_invalid")
    _validated_report_authority_path(report, "decisions")
    hashes = _require_object(report, "hashes")
    _require_exact_fields(
        hashes,
        APPLICATION_HASH_FIELDS,
        "application_report_hashes",
    )
    for key in APPLICATION_HASH_FIELDS:
        value = hashes.get(key)
        if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
            raise SafetyError(f"application_report_{key}_invalid")
    pinned_localisation = hashes.get("final_output_localisation_sha256")
    if (
        not isinstance(pinned_localisation, str)
        or SHA256_RE.fullmatch(pinned_localisation) is None
        or pinned_localisation != localisation_sha256
    ):
        raise SafetyError("reviewed_localisation_pin_mismatch")
    model = _require_object(report, "model")
    _require_exact_fields(
        model,
        APPLICATION_MODEL_FIELDS,
        "application_report_model",
    )
    model_tag = model.get("tag")
    model_digest = model.get("digest")
    if (
        not isinstance(model_tag, str)
        or not model_tag
        or len(model_tag) > 255
        or not isinstance(model_digest, str)
        or SHA256_RE.fullmatch(model_digest) is None
    ):
        raise SafetyError("application_report_model_invalid")
    _validate_safe_unicode(model_tag, "application_report_model_invalid")
    return {
        "unsupported_occurrences": unsupported,
        "skipped_files": skipped_files,
    }


def _require_object(
    value: dict[str, object], key: str
) -> dict[str, object]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise SafetyError(f"application_report_{key}_invalid")
    return item


def _require_exact_fields(
    value: dict[str, object],
    expected: frozenset[str],
    label: str,
) -> None:
    if set(value) != expected:
        raise SafetyError(f"{label}_fields_mismatch")


def _report_count(value: dict[str, object], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int) or item < 0:
        raise SafetyError(f"application_report_{key}_invalid")
    return item


def _validate_decision_count_algebra(
    *,
    total_decisions: int,
    accept: int,
    edit: int,
    reject: int,
    actually_changed: int,
    restored_english: int,
) -> None:
    if (
        total_decisions <= 0
        or accept + edit + reject != total_decisions
        or restored_english > actually_changed
        or actually_changed > edit + restored_english
        or restored_english > reject
    ):
        raise SafetyError("application_report_decision_counts_invalid")


def _validate_path_relationships(
    output: Path,
    candidate: Path,
    install_root: Path,
    report: dict[str, object],
) -> None:
    source = _validated_report_authority_path(report, "source_mod")
    base_candidate = _validated_report_authority_path(
        report, "base_candidate"
    )
    named_paths = (
        ("output", output, False),
        ("source", source, True),
        ("base_candidate", base_candidate, True),
        ("reviewed_candidate", candidate, True),
        ("install_root", install_root, False),
    )
    physical_paths = {
        label: _physical_path_identity(
            path,
            label=label,
            must_exist=must_exist,
        )
        for label, path, must_exist in named_paths
    }
    for first_index, (first_label, first, _) in enumerate(named_paths):
        for second_label, second, _ in named_paths[first_index + 1 :]:
            if _paths_overlap(first, second) or _physical_paths_overlap(
                physical_paths[first_label],
                physical_paths[second_label],
            ):
                raise SafetyError(
                    f"{first_label}_{second_label}_overlap"
                )


def _validated_report_authority_path(
    report: dict[str, object], key: str
) -> Path:
    value = report.get(key)
    if not isinstance(value, str):
        raise SafetyError(f"application_report_{key}_invalid")
    text = _validated_absolute_path_text(value, f"report_{key}")
    return Path(text)


def _paths_overlap(left: Path, right: Path) -> bool:
    return (
        left == right
        or left in right.parents
        or right in left.parents
    )


def _physical_path_identity(
    path: Path,
    *,
    label: str,
    must_exist: bool,
) -> PhysicalPathIdentity:
    if not path.is_absolute():
        raise SafetyError(f"{label}_physical_identity_unavailable")
    cursor = path
    missing_reversed: list[str] = []
    while True:
        try:
            value = os.stat(cursor, follow_symlinks=True)
        except FileNotFoundError as exc:
            if cursor.is_symlink() or cursor.parent == cursor:
                raise SafetyError(
                    f"{label}_physical_identity_unavailable"
                ) from exc
            missing_reversed.append(cursor.name)
            cursor = cursor.parent
            continue
        except OSError as exc:
            raise SafetyError(
                f"{label}_physical_identity_unavailable"
            ) from exc
        if not stat.S_ISDIR(value.st_mode):
            raise SafetyError(f"{label}_physical_identity_not_directory")
        break

    missing_parts = tuple(reversed(missing_reversed))
    if must_exist and missing_parts:
        raise SafetyError(f"{label}_physical_identity_unavailable")
    anchor_identity = _stable_physical_directory_identity(
        cursor, label=label
    )
    try:
        physical_anchor = cursor.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SafetyError(
            f"{label}_physical_identity_unavailable"
        ) from exc
    physical_anchor_identity = _stable_physical_directory_identity(
        physical_anchor, label=label
    )
    if physical_anchor_identity != anchor_identity:
        raise SafetyError(f"{label}_physical_identity_changed")

    ancestor_identities = [anchor_identity]
    ancestor = physical_anchor
    while True:
        parent = ancestor.parent
        if parent == ancestor:
            break
        ancestor = parent
        ancestor_identities.append(
            _stable_physical_directory_identity(ancestor, label=label)
        )
    return PhysicalPathIdentity(
        path=path,
        anchor_identity=anchor_identity,
        ancestor_identities=tuple(ancestor_identities),
        missing_parts=missing_parts,
        exact_exists=not missing_parts,
    )


def _stable_physical_directory_identity(
    path: Path,
    *,
    label: str,
) -> DirectoryIdentity:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
    )
    try:
        before = os.stat(path, follow_symlinks=True)
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise SafetyError(
            f"{label}_physical_identity_unavailable"
        ) from exc
    try:
        opened = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after = os.stat(path, follow_symlinks=True)
    except OSError as exc:
        raise SafetyError(
            f"{label}_physical_identity_unavailable"
        ) from exc
    identities = tuple(
        (value.st_dev, value.st_ino)
        for value in (before, opened, after)
    )
    if (
        any(not stat.S_ISDIR(value.st_mode) for value in (before, opened, after))
        or identities[0] != identities[1]
        or identities[1] != identities[2]
    ):
        raise SafetyError(f"{label}_physical_identity_changed")
    return identities[1]


def _physical_paths_overlap(
    left: PhysicalPathIdentity,
    right: PhysicalPathIdentity,
) -> bool:
    if (
        left.exact_exists
        and left.anchor_identity in right.ancestor_identities
    ):
        return True
    if (
        right.exact_exists
        and right.anchor_identity in left.ancestor_identities
    ):
        return True
    if (
        not left.exact_exists
        and not right.exact_exists
        and left.anchor_identity == right.anchor_identity
    ):
        raise SafetyError("physical_path_separation_unproven")
    return False


def _validate_private_content_absent(
    localisation_files: tuple[StableFile, ...],
    report: dict[str, object],
) -> None:
    absolute_report_paths = tuple(
        value.encode("utf-8")
        for value in _nested_strings(report)
        if value.startswith("/")
    )
    for item in localisation_files:
        lowered = item.data.lower()
        if (
            PRIVATE_PATH_RE.search(item.data)
            or any(marker in lowered for marker in PRIVATE_ARTIFACT_MARKERS)
            or any(path in item.data for path in absolute_report_paths)
        ):
            raise SafetyError("private_artifact_in_localisation")


def _nested_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_nested_strings(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(_nested_strings(item))
        return result
    return []


def _package_report(
    *,
    application_report_sha256: str,
    reviewed_localisation_sha256: str,
    package_localisation_sha256: str,
    internal_descriptor_sha256: str,
    external_descriptor_sha256: str,
    localisation_files: tuple[StableFile, ...],
    mod_slug: str,
    display_name: str,
    dependency_name: str,
    supported_version: str,
    planned_install_root: str,
    planned_mod_path: str,
    planned_descriptor_path: str,
    technical_residue: dict[str, int],
    editorial_status: object,
    editorially_approved: object,
) -> dict[str, object]:
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
    return {
        "schema_version": PACKAGE_REPORT_SCHEMA_VERSION,
        "status": "reviewed_mod_package_created",
        "review_scope": "full_candidate",
        "editorial_status": editorial_status,
        "editorially_approved": editorially_approved,
        "application_report_sha256": application_report_sha256,
        "reviewed_localisation_sha256": reviewed_localisation_sha256,
        "package_localisation_sha256": package_localisation_sha256,
        "descriptor_hashes": {
            "internal_descriptor_sha256": internal_descriptor_sha256,
            "external_descriptor_sha256": external_descriptor_sha256,
        },
        "inventory": {
            "package_file_count": len(package_files),
            "game_content_file_count": len(game_files),
            "localisation_file_count": len(localisation_files),
            "package_files": package_files,
            "game_content_files": game_files,
            "localisation_files": [
                {
                    "path": item.relative.as_posix(),
                    "bytes": len(item.data),
                    "sha256": item.sha256,
                }
                for item in localisation_files
            ],
        },
        "mod": {
            "slug": mod_slug,
            "display_name": display_name,
            "dependency_name": dependency_name,
            "supported_version": supported_version,
        },
        "planned_install": {
            "root": planned_install_root,
            "mod_path": planned_mod_path,
            "descriptor_path": planned_descriptor_path,
        },
        "technical_residue": dict(technical_residue),
        "source_mutations": 0,
        "reviewed_candidate_mutations": 0,
        "active_mod_mutations": 0,
        "launcher_mutations": 0,
        "ollama_calls": 0,
        "network_calls": 0,
        "in_game_smoke_required": True,
    }


def _mkdir_private(path: Path) -> Path:
    try:
        path.mkdir(mode=0o700)
    except OSError as exc:
        raise SafetyError("package_directory_creation_failed") from exc
    return path


def _mkdir_private_parents(path: Path, boundary: Path) -> None:
    missing: list[Path] = []
    current = path
    while current != boundary and not current.exists():
        missing.append(current)
        current = current.parent
    if current != boundary and not _paths_overlap(boundary, current):
        raise SafetyError("package_path_escape")
    for directory in reversed(missing):
        _mkdir_private(directory)


def _validate_materialized_package(
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
    inventory = _require_object(report_payload, "inventory")
    expected_paths_value = inventory.get("package_files")
    if not isinstance(expected_paths_value, list) or any(
        not isinstance(item, str) for item in expected_paths_value
    ):
        raise SafetyError("package_inventory_invalid")
    expected_paths = set(expected_paths_value)
    actual: dict[str, StableFile] = {}
    for current, directories, filenames in os.walk(
        root, followlinks=False
    ):
        directories.sort()
        filenames.sort()
        current_path = Path(current)
        for directory in directories:
            _stable_directory_identity(current_path / directory)
        for filename in filenames:
            path = current_path / filename
            relative = path.relative_to(root)
            actual[relative.as_posix()] = _read_stable_regular_file(
                path,
                relative,
                max_bytes=max(
                    MAX_LOCALISATION_FILE_BYTES,
                    MAX_APPLICATION_REPORT_BYTES,
                ),
            )
    if set(actual) != expected_paths:
        raise SafetyError("package_inventory_mismatch")

    mod = _require_object(report_payload, "mod")
    slug = mod.get("slug")
    if not isinstance(slug, str):
        raise SafetyError("package_inventory_invalid")
    internal_path = f"install/{slug}/descriptor.mod"
    external_path = f"install/{slug}.mod"
    if (
        actual[internal_path].data != internal_descriptor
        or actual[external_path].data != external_descriptor
        or parse_strict_descriptor(actual[internal_path].data)
        != parse_strict_descriptor(render_descriptor(internal_spec))
        or parse_strict_descriptor(actual[external_path].data)
        != parse_strict_descriptor(render_descriptor(external_spec))
    ):
        raise SafetyError("package_descriptor_mismatch")
    if actual[PACKAGE_REPORT_NAME].data != report_bytes:
        raise SafetyError("package_report_mismatch")
    try:
        loaded_report = json.loads(report_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SafetyError("package_report_invalid") from exc
    if loaded_report != report_payload:
        raise SafetyError("package_report_mismatch")
    for item in localisation_files:
        target = f"install/{slug}/{item.relative.as_posix()}"
        if actual[target].data != item.data:
            raise SafetyError("package_localisation_mismatch")
    if any(
        path.endswith(APPLICATION_REPORT_NAME)
        for path in actual
        if path.startswith("install/")
    ):
        raise SafetyError("application_report_in_game_content")


def _verify_reviewed_candidate_snapshot(
    expected: ReviewedCandidateSnapshot,
) -> None:
    current = _snapshot_reviewed_candidate(expected.root)
    if current != expected:
        raise SafetyError("reviewed_candidate_generation_changed")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
