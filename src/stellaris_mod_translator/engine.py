"""Discovery, immutable source snapshots, translation, and atomic output."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Callable

from .ollama import OllamaClient, OllamaError
from .parser import ParseError, ParsedFile, parse_localisation


class SafetyError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceFile:
    relative: Path
    data: bytes
    sha256: str
    stat_identity: tuple[int, int, int, int]
    parsed: ParsedFile | None
    error: str | None


def inspect_mod(source_mod: Path) -> dict[str, object]:
    source = _validated_source(source_mod)
    files = _snapshot(source)
    return _base_report(source, files)


def translate_mod(
    source_mod: Path,
    output: Path,
    model: str,
    *,
    dry_run: bool = False,
    client_factory: Callable[[], OllamaClient] = OllamaClient,
) -> dict[str, object]:
    source = _validated_source(source_mod)
    output_abs = _validated_output(source, output)
    files = _snapshot(source)
    report = _base_report(source, files)
    report["output"] = str(output_abs)
    report["dry_run"] = dry_run
    report["model"] = {"tag": model, "digest": None}
    if dry_run:
        return report

    client = client_factory()
    identity = client.exact_model(model)
    report["model"] = identity
    temp = Path(
        tempfile.mkdtemp(prefix=f".{output_abs.name}.tmp-", dir=output_abs.parent)
    )
    candidates: list[tuple[Path, bytes]] = []
    translated = fallback = 0
    try:
        for source_file in files:
            parsed = source_file.parsed
            if parsed is None or not parsed.is_english:
                continue
            replacements: dict[int, str] = {}
            for entry in parsed.entries:
                try:
                    result = client.translate(tag=model, text=entry.model_text())
                    replacements[entry.line_index] = entry.restore_translation(result)
                    translated += 1
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
        report["counts"]["fallback_occurrences"] += fallback
        report["hashes"]["output_localisation_sha256"] = candidate_hash
        report_path = temp / "translation-report.json"
        _write_new(
            report_path,
            (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
        _verify_snapshot(source, files)
        os.rename(temp, output_abs)
    except BaseException:
        if temp.exists():
            shutil.rmtree(temp)
        raise
    return report


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
    for root, dirs, names in os.walk(localisation, followlinks=False):
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
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags)
            try:
                before = os.fstat(descriptor)
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


def _base_report(source: Path, files: list[SourceFile]) -> dict[str, object]:
    diagnostics: list[dict[str, object]] = []
    english_files = occurrences = fallback = skipped = 0
    hash_inputs: list[tuple[Path, bytes]] = []
    for item in files:
        hash_inputs.append((item.relative, item.data))
        if item.error:
            skipped += 1
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


def _candidate_relative(relative: Path) -> Path:
    parts = list(relative.parts)
    if not parts or parts[0] != "localisation":
        raise SafetyError("unexpected_source_path")
    tail = parts[1:]
    if tail and tail[0].lower() == "english":
        tail = tail[1:]
    filename = tail[-1]
    if filename.endswith("_l_english.yml"):
        filename = filename[: -len("_l_english.yml")] + "_l_russian.yml"
    tail[-1] = filename
    candidate = Path("localisation", "russian", *tail)
    if ".." in candidate.parts:
        raise SafetyError("path_traversal")
    return candidate


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


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
