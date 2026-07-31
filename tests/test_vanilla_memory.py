from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import stat
import unicodedata
from urllib.parse import quote

import pytest

from stellaris_mod_translator.engine import SafetyError
from stellaris_mod_translator.publication import DestinationExistsError
from stellaris_mod_translator import vanilla_memory
from stellaris_mod_translator.vanilla_memory import (
    DATABASE_NAME,
    REPORT_NAME,
    build_vanilla_memory,
    inspect_vanilla_memory,
)


GAME_VERSION = "Synthetic Pegasus 4.4.6"
BOM = b"\xef\xbb\xbf"


def _localisation(
    language: str,
    entries: list[tuple[str, str | None, str]],
    *,
    bom: bool = True,
    newline: str = "\n",
    extra_lines: tuple[str, ...] = (),
) -> bytes:
    lines = [f"l_{language}:", " # synthetic comment"]
    for key, suffix, value in entries:
        version = "" if suffix is None else suffix
        lines.append(f' {key}:{version} "{value}"')
    lines.extend(extra_lines)
    payload = (newline.join(lines) + newline).encode("utf-8")
    return (BOM if bom else b"") + payload


def _write(root: Path, relative: str, data: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _roots(tmp_path: Path, name: str = "inputs") -> tuple[Path, Path]:
    base = tmp_path / name
    english = base / "english"
    russian = base / "russian"
    english.mkdir(parents=True)
    russian.mkdir(parents=True)
    return english, russian


def _build(
    tmp_path: Path,
    english_files: dict[str, bytes],
    russian_files: dict[str, bytes],
    *,
    name: str = "memory",
    roots_name: str = "inputs",
) -> tuple[dict[str, object], Path, Path, Path]:
    english, russian = _roots(tmp_path, roots_name)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    output = tmp_path / name
    report = build_vanilla_memory(english, russian, GAME_VERSION, output)
    return report, output / DATABASE_NAME, english, russian


def _read_rows(
    database: Path,
    sql: str,
    parameters: tuple[object, ...] = (),
) -> list[sqlite3.Row]:
    uri = "file:" + quote(os.fspath(database), safe="/") + "?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(sql, parameters).fetchall()


def _one_pair_files(
    *,
    english_value: str = "Synthetic $ACTOR$ [Root.GetName]",
    russian_value: str = "MVP6A_SYNTHETIC_CONTEXT_VALUE_20260731 $ACTOR$ [Root.GetName]",
    english_suffix: str | None = "0",
    russian_suffix: str | None = "0",
) -> tuple[dict[str, bytes], dict[str, bytes]]:
    return (
        {
            "context/scene_l_english.yml": _localisation(
                "english",
                [("synthetic.entry", english_suffix, english_value)],
            )
        },
        {
            "context/scene_l_russian.yml": _localisation(
                "russian",
                [("synthetic.entry", russian_suffix, russian_value)],
            )
        },
    )


def _tree_bytes(root: Path) -> tuple[tuple[str, bytes], ...]:
    return tuple(
        (path.relative_to(root).as_posix(), path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


def _assert_limit_failure(
    tmp_path: Path,
    english_files: dict[str, bytes],
    russian_files: dict[str, bytes],
    error: str,
) -> None:
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    before = (_tree_bytes(english), _tree_bytes(russian))
    output = tmp_path / "memory"

    with pytest.raises(SafetyError) as raised:
        build_vanilla_memory(english, russian, GAME_VERSION, output)

    assert str(raised.value) == error
    assert "synthetic.entry" not in str(raised.value)
    assert "scene_l_english.yml" not in str(raised.value)
    assert (_tree_bytes(english), _tree_bytes(russian)) == before
    assert not output.exists()
    assert list(tmp_path.glob(".memory.tmp-*")) == []


def test_build_and_inspect_strict_reference_are_private_and_aggregate_only(
    tmp_path: Path,
) -> None:
    english_files, russian_files = _one_pair_files()
    report, database, english, russian = _build(
        tmp_path, english_files, russian_files
    )

    assert report["schema_version"] == vanilla_memory.SCHEMA_VERSION
    assert report["status"] == "COMPLETE"
    assert report["game_version"] == GAME_VERSION
    assert report["source_generations"] == "PASS"
    assert report["source_mutations"] == 0
    assert report["ollama_calls"] == 0
    assert "private_content_in_git" not in report
    assert "private_content_in_git" not in report["counts"]
    assert report["counts"]["strict_eligible_pairs"] == 1
    assert report["counts"]["quarantined_total"] == 0

    inspected = inspect_vanilla_memory(database)
    assert set(inspected) == {
        "schema_version",
        "game_version",
        "hashes",
        "counts",
    }
    assert inspected["schema_version"] == report["schema_version"]
    assert inspected["game_version"] == report["game_version"]
    assert inspected["hashes"] == report["hashes"]
    assert inspected["counts"] == report["counts"]
    metadata_columns = {
        row["name"]
        for row in _read_rows(database, "PRAGMA table_info(metadata)")
    }
    assert "private_content_in_git" not in metadata_columns

    public_bytes = json.dumps(
        {"report": report, "inspection": inspected},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    for forbidden in (
        b"synthetic.entry",
        b"Synthetic $ACTOR$",
        "MVP6A_SYNTHETIC_CONTEXT_VALUE_20260731".encode("utf-8"),
        b"scene_l_english.yml",
        os.fsencode(english),
        os.fsencode(russian),
    ):
        assert forbidden not in public_bytes

    occurrences = _read_rows(
        database,
        """
        SELECT language, alignment_state, reference_status,
               editorially_approved, counterpart_occurrence_id
        FROM occurrences ORDER BY language
        """,
    )
    assert len(occurrences) == 2
    assert {row["alignment_state"] for row in occurrences} == {
        "strict_reference"
    }
    assert {row["reference_status"] for row in occurrences} == {
        "REFERENCE_ONLY"
    }
    assert {row["editorially_approved"] for row in occurrences} == {0}
    assert all(row["counterpart_occurrence_id"] for row in occurrences)


def test_version_suffix_absent_zero_and_leading_zero_remain_exact_and_distinct(
    tmp_path: Path,
) -> None:
    occurrence_ids: set[str] = set()
    logical_digests: set[str] = set()
    for index, suffix in enumerate((None, "0", "007")):
        case = tmp_path / f"case-{index}"
        case.mkdir()
        english_files, russian_files = _one_pair_files(
            english_suffix=suffix,
            russian_suffix=suffix,
        )
        report, database, _, _ = _build(
            case,
            english_files,
            russian_files,
        )
        rows = _read_rows(
            database,
            """
            SELECT occurrence_id, language, version_suffix
            FROM occurrences ORDER BY language
            """,
        )
        assert [row["version_suffix"] for row in rows] == [suffix, suffix]
        occurrence_ids.add(
            next(
                row["occurrence_id"]
                for row in rows
                if row["language"] == "english"
            )
        )
        logical_digests.add(report["hashes"]["logical_digest"])

    assert len(occurrence_ids) == 3
    assert len(logical_digests) == 3


@pytest.mark.parametrize(
    ("english_count", "russian_count", "expected"),
    [(2, 1, 3), (1, 2, 3), (2, 2, 4)],
)
def test_duplicate_key_precedes_version_and_atom_mismatches(
    tmp_path: Path,
    english_count: int,
    russian_count: int,
    expected: int,
) -> None:
    english_entries = [
        ("duplicate.key", "0", f"English {index} $EN_{index}$")
        for index in range(english_count)
    ]
    russian_entries = [
        ("duplicate.key", "1", f"Русский {index} $RU_{index}$")
        for index in range(russian_count)
    ]
    report, database, _, _ = _build(
        tmp_path,
        {"duplicates_l_english.yml": _localisation("english", english_entries)},
        {"duplicates_l_russian.yml": _localisation("russian", russian_entries)},
    )

    counts = report["counts"]
    assert counts["duplicate_key_occurrences"] == expected
    assert counts["version_mismatches"] == 0
    assert counts["protected_atom_mismatches"] == 0
    assert counts["strict_eligible_pairs"] == 0
    assert counts["quarantined_total"] == expected
    states = _read_rows(
        database,
        "SELECT alignment_state, counterpart_occurrence_id FROM occurrences",
    )
    assert {row["alignment_state"] for row in states} == {"duplicate_key"}
    assert all(row["counterpart_occurrence_id"] is None for row in states)
    assert _read_rows(database, "SELECT * FROM unique_alignments") == []


def test_missing_counterparts_are_terminal_and_counted_per_occurrence(
    tmp_path: Path,
) -> None:
    report, database, _, _ = _build(
        tmp_path,
        {
            "missing_l_english.yml": _localisation(
                "english", [("english.only", "0", "English only")]
            )
        },
        {
            "missing_l_russian.yml": _localisation(
                "russian", [("russian.only", "0", "Только русский")]
            )
        },
    )

    assert report["counts"]["missing_counterparts"] == 2
    assert report["counts"]["quarantined_total"] == 2
    rows = _read_rows(
        database,
        """
        SELECT alignment_state, diagnostic_reason,
               counterpart_occurrence_id, context_path_match
        FROM occurrences
        """,
    )
    assert all(row["alignment_state"] == "missing_counterpart" for row in rows)
    assert all(row["diagnostic_reason"] == "missing_counterpart" for row in rows)
    assert all(row["counterpart_occurrence_id"] is None for row in rows)
    assert all(row["context_path_match"] is None for row in rows)


def test_version_mismatch_precedes_protected_atom_mismatch(tmp_path: Path) -> None:
    english_files, russian_files = _one_pair_files(
        english_value="Synthetic $ENGLISH$",
        russian_value="MVP6A_SYNTHETIC_CONTEXT_VALUE_20260731 $RUSSIAN$",
        english_suffix="0",
        russian_suffix="1",
    )
    report, database, _, _ = _build(
        tmp_path, english_files, russian_files
    )

    assert report["counts"]["version_mismatches"] == 1
    assert report["counts"]["protected_atom_mismatches"] == 0
    assert report["counts"]["quarantined_total"] == 2
    rows = _read_rows(
        database,
        "SELECT alignment_state, diagnostic_reason FROM occurrences",
    )
    assert {(row["alignment_state"], row["diagnostic_reason"]) for row in rows} == {
        ("version_mismatch", "version_mismatch")
    }


@pytest.mark.parametrize(
    ("russian_value", "expected_state"),
    [
        ("Русский $ONE$ [Root.GetName]", "strict_reference"),
        ("Русский $TWO$ [Root.GetName]", "protected_atom_mismatch"),
        ("Русский [Root.GetName] $ONE$", "protected_atom_mismatch"),
        ("Русский £ONE£ [Root.GetName]", "protected_atom_mismatch"),
    ],
)
def test_protected_compatibility_uses_exact_kind_token_and_order(
    tmp_path: Path,
    russian_value: str,
    expected_state: str,
) -> None:
    english_files, russian_files = _one_pair_files(
        english_value="English $ONE$ [Root.GetName]",
        russian_value=russian_value,
    )
    report, database, _, _ = _build(
        tmp_path, english_files, russian_files
    )

    expected_strict = int(expected_state == "strict_reference")
    assert report["counts"]["strict_eligible_pairs"] == expected_strict
    assert report["counts"]["protected_atom_mismatches"] == 1 - expected_strict
    states = _read_rows(
        database,
        "SELECT DISTINCT alignment_state FROM occurrences",
    )
    assert [row["alignment_state"] for row in states] == [expected_state]


def test_path_family_mismatch_is_diagnostic_but_remains_strict_reference(
    tmp_path: Path,
) -> None:
    report, database, _, _ = _build(
        tmp_path,
        {
            "english_context/one_l_english.yml": _localisation(
                "english", [("path.context", "0", "Context")]
            )
        },
        {
            "russian_context/two_l_russian.yml": _localisation(
                "russian", [("path.context", "0", "Контекст")]
            )
        },
    )

    assert report["counts"]["strict_eligible_pairs"] == 1
    assert report["counts"]["context_path_mismatches"] == 1
    assert report["counts"]["quarantined_total"] == 0
    pair = _read_rows(
        database,
        """
        SELECT context_path_match, global_text_ambiguous,
               reference_status, editorially_approved
        FROM reference_pairs
        """,
    )[0]
    assert pair["context_path_match"] == 0
    assert pair["global_text_ambiguous"] == 0
    assert pair["reference_status"] == "REFERENCE_ONLY"
    assert pair["editorially_approved"] == 0


def test_same_english_text_with_distinct_russian_values_is_contextual_ambiguity(
    tmp_path: Path,
) -> None:
    english_entries = [
        ("context.one", "0", "Shared English"),
        ("context.two", "0", "Shared English"),
    ]
    russian_entries = [
        ("context.one", "0", "Первый вариант"),
        ("context.two", "0", "Второй вариант"),
    ]
    report, database, _, _ = _build(
        tmp_path,
        {"contexts_l_english.yml": _localisation("english", english_entries)},
        {"contexts_l_russian.yml": _localisation("russian", russian_entries)},
    )

    assert report["counts"]["strict_eligible_pairs"] == 2
    assert report["counts"]["ambiguous_english_groups"] == 1
    assert report["counts"]["quarantined_total"] == 0
    assert {
        row["global_text_ambiguous"]
        for row in _read_rows(database, "SELECT global_text_ambiguous FROM occurrences")
    } == {1}
    assert {
        row["global_text_ambiguous"]
        for row in _read_rows(
            database, "SELECT global_text_ambiguous FROM reference_pairs"
        )
    } == {1}


def test_same_english_text_with_same_russian_value_is_not_ambiguous(
    tmp_path: Path,
) -> None:
    report, database, _, _ = _build(
        tmp_path,
        {
            "contexts_l_english.yml": _localisation(
                "english",
                [
                    ("context.one", "0", "Shared English"),
                    ("context.two", "0", "Shared English"),
                ],
            )
        },
        {
            "contexts_l_russian.yml": _localisation(
                "russian",
                [
                    ("context.one", "0", "Один вариант"),
                    ("context.two", "0", "Один вариант"),
                ],
            )
        },
    )

    assert report["counts"]["ambiguous_english_groups"] == 0
    assert {
        row["global_text_ambiguous"]
        for row in _read_rows(database, "SELECT global_text_ambiguous FROM occurrences")
    } == {0}


def test_case_similar_keys_remain_exact_joins_and_are_flagged_as_alias_risk(
    tmp_path: Path,
) -> None:
    report, database, _, _ = _build(
        tmp_path,
        {
            "aliases_l_english.yml": _localisation(
                "english",
                [
                    ("Alias.Key", "0", "Upper"),
                    ("alias.key", "0", "Lower"),
                ],
            )
        },
        {
            "aliases_l_russian.yml": _localisation(
                "russian",
                [
                    ("Alias.Key", "0", "Верхний"),
                    ("alias.key", "0", "Нижний"),
                ],
            )
        },
    )

    assert report["counts"]["strict_eligible_pairs"] == 2
    assert report["counts"]["key_alias_groups"] == 1
    assert report["counts"]["duplicate_key_occurrences"] == 0
    rows = _read_rows(
        database,
        "SELECT localisation_key, key_alias_risk FROM occurrences",
    )
    assert {row["localisation_key"] for row in rows} == {
        "Alias.Key",
        "alias.key",
    }
    assert {row["key_alias_risk"] for row in rows} == {1}


def test_malformed_file_and_record_are_quarantined_without_losing_valid_pair(
    tmp_path: Path,
) -> None:
    english_valid = _localisation(
        "english",
        [("valid.key", "0", "Valid")],
        extra_lines=(" malformed.key:0 unquoted",),
    )
    report, database, _, _ = _build(
        tmp_path,
        {
            "mixed_l_english.yml": english_valid,
            "invalid_l_english.yml": b"\xef\xbb\xbfl_english:\n invalid:0 \"\xff\"\n",
        },
        {
            "mixed_l_russian.yml": _localisation(
                "russian", [("valid.key", "0", "Корректно")]
            )
        },
    )

    counts = report["counts"]
    assert report["status"] == "COMPLETE_WITH_QUARANTINED_RECORDS"
    assert counts["strict_eligible_pairs"] == 1
    assert counts["malformed_record_units"] == 1
    assert counts["malformed_file_units"] == 1
    assert counts["quarantined_total"] == 2
    assert counts["quarantine_by_reason"] == {
        "invalid_utf8": 1,
        "malformed_syntax": 1,
    }
    rows = _read_rows(
        database,
        """
        SELECT quarantine_scope, diagnostic_reason
        FROM quarantine_records ORDER BY sequence
        """,
    )
    assert [(row["quarantine_scope"], row["diagnostic_reason"]) for row in rows] == [
        ("file", "invalid_utf8"),
        ("record", "malformed_syntax"),
    ]
    occupancy = _read_rows(
        database,
        """
        SELECT key_hint, candidate_count
        FROM quarantined_key_occupancy
        WHERE relative_path = 'invalid_l_english.yml'
        ORDER BY key_hint
        """,
    )
    assert ("invalid", 1) in [
        (row["key_hint"], row["candidate_count"])
        for row in occupancy
    ]


def test_bom_newline_comments_and_expected_headers_are_recorded(
    tmp_path: Path,
) -> None:
    report, database, _, _ = _build(
        tmp_path,
        {
            "format_l_english.yml": _localisation(
                "english",
                [("format.key", None, "English")],
                bom=True,
                newline="\r\n",
            )
        },
        {
            "format_l_russian.yml": _localisation(
                "russian",
                [("format.key", None, "Русский")],
                bom=False,
                newline="\n",
            )
        },
    )

    assert report["counts"]["strict_eligible_pairs"] == 1
    rows = _read_rows(
        database,
        "SELECT language, bom, newline_style FROM source_files ORDER BY language",
    )
    assert [(row["language"], row["bom"], row["newline_style"]) for row in rows] == [
        ("english", 1, "CRLF"),
        ("russian", 0, "LF"),
    ]


def test_wrong_language_header_is_file_quarantine_not_global_blocker(
    tmp_path: Path,
) -> None:
    report, database, _, _ = _build(
        tmp_path,
        {
            "wrong_l_english.yml": _localisation(
                "russian", [("header.key", "0", "Wrong root")]
            )
        },
        {
            "right_l_russian.yml": _localisation(
                "russian", [("header.key", "0", "Русский")]
            )
        },
    )

    assert report["status"] == "COMPLETE_WITH_QUARANTINED_RECORDS"
    assert report["counts"]["malformed_file_units"] == 1
    assert report["counts"]["missing_counterparts"] == 1
    assert report["counts"]["quarantined_total"] == 2
    reasons = _read_rows(
        database,
        "SELECT diagnostic_reason FROM quarantine_records",
    )
    assert [row["diagnostic_reason"] for row in reasons] == [
        "unexpected_language_header"
    ]


def test_private_modes_and_sidecar_absence_hold_under_permissive_umask(
    tmp_path: Path,
) -> None:
    english_files, russian_files = _one_pair_files()
    old_umask = os.umask(0)
    try:
        _, database, _, _ = _build(tmp_path, english_files, russian_files)
    finally:
        os.umask(old_umask)

    output = database.parent
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert stat.S_IMODE(database.stat().st_mode) == 0o600
    assert stat.S_IMODE((output / REPORT_NAME).stat().st_mode) == 0o600
    assert database.stat().st_nlink == 1
    assert (output / REPORT_NAME).stat().st_nlink == 1
    for suffix in ("-journal", "-wal", "-shm"):
        assert not Path(os.fspath(database) + suffix).exists()


@pytest.mark.parametrize("kind", ["file", "directory", "symlink"])
def test_existing_output_is_preserved_without_temp_residue(
    tmp_path: Path,
    kind: str,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    output = tmp_path / "memory"
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "marker"
    marker.write_bytes(b"outside")
    if kind == "file":
        output.write_bytes(b"owner")
    elif kind == "directory":
        output.mkdir()
        (output / "owner").write_bytes(b"owner")
    else:
        output.symlink_to(outside, target_is_directory=True)

    with pytest.raises(SafetyError, match="output_must_not_exist"):
        build_vanilla_memory(english, russian, GAME_VERSION, output)

    if kind == "file":
        assert output.read_bytes() == b"owner"
    elif kind == "directory":
        assert (output / "owner").read_bytes() == b"owner"
    else:
        assert output.is_symlink()
        assert output.resolve() == outside
        assert marker.read_bytes() == b"outside"
    assert list(tmp_path.glob(".memory.tmp-*")) == []


def test_publication_race_preserves_competitor_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    output = tmp_path / "memory"

    def race(_source: Path, destination: Path) -> None:
        destination.mkdir()
        (destination / "competitor").write_bytes(b"preserve")
        raise DestinationExistsError("synthetic race")

    monkeypatch.setattr(
        vanilla_memory, "atomic_publish_directory_no_replace", race
    )
    with pytest.raises(SafetyError, match="output_appeared_before_publication"):
        build_vanilla_memory(english, russian, GAME_VERSION, output)

    assert (output / "competitor").read_bytes() == b"preserve"
    assert list(tmp_path.glob(".memory.tmp-*")) == []


def test_generic_publication_failure_leaves_no_output_or_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    output = tmp_path / "memory"

    def fail(_source: Path, _destination: Path) -> None:
        raise OSError("synthetic publication failure")

    monkeypatch.setattr(
        vanilla_memory, "atomic_publish_directory_no_replace", fail
    )
    with pytest.raises(SafetyError, match="vanilla_memory_build_failed"):
        build_vanilla_memory(english, russian, GAME_VERSION, output)

    assert not output.exists()
    assert list(tmp_path.glob(".memory.tmp-*")) == []


@pytest.mark.parametrize("language", ["english", "russian"])
def test_publication_time_source_drift_rolls_back_and_retries_stably(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    language: str,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    target_root = english if language == "english" else russian
    target = next(path for path in target_root.rglob("*.yml"))
    output = tmp_path / "memory"
    actual_publish = vanilla_memory.atomic_publish_directory_no_replace
    publications = 0

    def drift_first_publication(source: Path, destination: Path) -> None:
        nonlocal publications
        actual_publish(source, destination)
        if destination != output:
            return
        publications += 1
        if publications == 1:
            current = target.read_bytes()
            if language == "english":
                changed = current.replace(
                    b"Synthetic $ACTOR$ [Root.GetName]",
                    b"Retried synthetic $ACTOR$ [Root.GetName]",
                    1,
                )
            else:
                changed = current.replace(
                    "MVP6A_SYNTHETIC_CONTEXT_VALUE_20260731".encode("utf-8"),
                    "MVP6A_RETRIED_CONTEXT_VALUE_20260731".encode("utf-8"),
                    1,
                )
            assert changed != current
            target.write_bytes(changed)

    monkeypatch.setattr(
        vanilla_memory,
        "atomic_publish_directory_no_replace",
        drift_first_publication,
    )
    report = build_vanilla_memory(english, russian, GAME_VERSION, output)

    fresh = vanilla_memory._snapshot_source_tree(target_root, language)
    assert publications == 2
    assert report["source_generations"] == "PASS"
    assert report["hashes"][f"{language}_manifest_sha256"] == (
        fresh.manifest_sha256
    )
    assert report["hashes"][f"{language}_dataset_sha256"] == (
        fresh.dataset_sha256
    )
    rows = _read_rows(
        output / DATABASE_NAME,
        """
        SELECT human_value FROM occurrences
        WHERE language = ?
        """,
        (language,),
    )
    assert len(rows) == 1
    assert "Retried" in rows[0]["human_value"] or "RETRIED" in rows[0][
        "human_value"
    ]
    assert inspect_vanilla_memory(output / DATABASE_NAME)["hashes"] == (
        report["hashes"]
    )
    assert output.is_dir()
    assert list(tmp_path.glob(".memory.tmp-*")) == []


def test_publication_time_drift_on_both_attempts_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    target = next(path for path in english.rglob("*.yml"))
    output = tmp_path / "memory"
    actual_publish = vanilla_memory.atomic_publish_directory_no_replace
    publications = 0

    def drift_every_publication(source: Path, destination: Path) -> None:
        nonlocal publications
        actual_publish(source, destination)
        if destination != output:
            return
        publications += 1
        target.write_bytes(
            target.read_bytes()
            + f" # synthetic drift {publications}\n".encode("ascii")
        )

    monkeypatch.setattr(
        vanilla_memory,
        "atomic_publish_directory_no_replace",
        drift_every_publication,
    )
    with pytest.raises(
        SafetyError, match="source_generation_changed_after_retry"
    ):
        build_vanilla_memory(english, russian, GAME_VERSION, output)

    assert publications == 2
    assert not output.exists()
    assert list(tmp_path.glob(".memory.tmp-*")) == []


@pytest.mark.parametrize("language", ["english", "russian"])
def test_terminal_drift_during_database_validation_rolls_back_and_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    language: str,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    target_root = english if language == "english" else russian
    target = next(path for path in target_root.rglob("*.yml"))
    output = tmp_path / "memory"
    actual_validate = vanilla_memory._validate_database_read_only
    validation_calls = 0

    def drift_during_first_published_validation(
        path: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        nonlocal validation_calls
        validation_calls += 1
        validated = actual_validate(path, **kwargs)
        if validation_calls == 2:
            current = target.read_bytes()
            if language == "english":
                changed = current.replace(
                    b"Synthetic $ACTOR$ [Root.GetName]",
                    b"Terminal retried $ACTOR$ [Root.GetName]",
                    1,
                )
            else:
                changed = current.replace(
                    "MVP6A_SYNTHETIC_CONTEXT_VALUE_20260731".encode("utf-8"),
                    "MVP6A_TERMINAL_RETRIED_VALUE_20260731".encode("utf-8"),
                    1,
                )
            assert changed != current
            target.write_bytes(changed)
        return validated

    monkeypatch.setattr(
        vanilla_memory,
        "_validate_database_read_only",
        drift_during_first_published_validation,
    )
    report = build_vanilla_memory(english, russian, GAME_VERSION, output)

    fresh = vanilla_memory._snapshot_source_tree(target_root, language)
    rows = _read_rows(
        output / DATABASE_NAME,
        """
        SELECT human_value FROM occurrences
        WHERE language = ?
        """,
        (language,),
    )
    assert validation_calls == 4
    assert report["source_generations"] == "PASS"
    assert report["hashes"][f"{language}_manifest_sha256"] == (
        fresh.manifest_sha256
    )
    assert report["hashes"][f"{language}_dataset_sha256"] == (
        fresh.dataset_sha256
    )
    assert len(rows) == 1
    assert "Terminal" in rows[0]["human_value"] or "TERMINAL" in rows[0][
        "human_value"
    ]
    assert inspect_vanilla_memory(output / DATABASE_NAME)["hashes"] == (
        report["hashes"]
    )
    assert list(tmp_path.glob(".memory.tmp-*")) == []
    assert list(tmp_path.glob(".memory.rollback-*")) == []


def test_terminal_drift_during_both_database_validations_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    target = next(path for path in english.rglob("*.yml"))
    output = tmp_path / "memory"
    actual_validate = vanilla_memory._validate_database_read_only
    validation_calls = 0

    def drift_during_each_published_validation(
        path: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        nonlocal validation_calls
        validation_calls += 1
        validated = actual_validate(path, **kwargs)
        if validation_calls == 2:
            current = target.read_bytes()
            changed = current.replace(
                b"Synthetic $ACTOR$ [Root.GetName]",
                b"First terminal $ACTOR$ [Root.GetName]",
                1,
            )
            assert changed != current
            target.write_bytes(changed)
        elif validation_calls == 4:
            current = target.read_bytes()
            changed = current.replace(
                b"First terminal $ACTOR$ [Root.GetName]",
                b"Second terminal $ACTOR$ [Root.GetName]",
                1,
            )
            assert changed != current
            target.write_bytes(changed)
        return validated

    monkeypatch.setattr(
        vanilla_memory,
        "_validate_database_read_only",
        drift_during_each_published_validation,
    )
    with pytest.raises(
        SafetyError, match="source_generation_changed_after_retry"
    ):
        build_vanilla_memory(english, russian, GAME_VERSION, output)

    assert validation_calls == 4
    assert not output.exists()
    assert list(tmp_path.glob(".memory.tmp-*")) == []
    assert list(tmp_path.glob(".memory.rollback-*")) == []


def test_terminal_verification_uses_independent_budgets_and_publishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    output = tmp_path / "memory"
    actual_verify = vanilla_memory._verify_source_snapshot
    calls: list[tuple[str, object]] = []

    def record_budget(
        snapshot: object,
        budget: object | None = None,
    ) -> None:
        assert budget is not None
        calls.append((snapshot.language, budget))
        actual_verify(snapshot, budget)

    monkeypatch.setattr(
        vanilla_memory, "_verify_source_snapshot", record_budget
    )
    report = build_vanilla_memory(english, russian, GAME_VERSION, output)

    assert [language for language, _ in calls] == [
        "english",
        "russian",
        "english",
        "russian",
        "english",
        "russian",
    ]
    assert calls[0][1] is calls[1][1]
    assert calls[2][1] is calls[3][1]
    assert calls[4][1] is calls[5][1]
    assert len({id(calls[index][1]) for index in (0, 2, 4)}) == 3
    assert report["source_generations"] == "PASS"
    assert output.is_dir()
    assert list(tmp_path.glob(".memory.tmp-*")) == []
    assert list(tmp_path.glob(".memory.rollback-*")) == []


def test_terminal_drift_rollback_never_deletes_replacement_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    output = tmp_path / "memory"
    displaced = tmp_path / "displaced-owned-output"
    actual_verify = vanilla_memory._verify_source_snapshot
    calls = 0

    def replace_before_rollback(
        snapshot: object,
        budget: object | None = None,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 5:
            output.rename(displaced)
            output.mkdir()
            (output / "competitor").write_bytes(b"preserve")
            raise vanilla_memory._SourceGenerationChanged()
        actual_verify(snapshot, budget)

    monkeypatch.setattr(
        vanilla_memory, "_verify_source_snapshot", replace_before_rollback
    )
    with pytest.raises(
        SafetyError, match="post_publication_rollback_unproven"
    ):
        build_vanilla_memory(english, russian, GAME_VERSION, output)

    assert (output / "competitor").read_bytes() == b"preserve"
    assert (displaced / DATABASE_NAME).is_file()


def test_rollback_isolates_owned_tree_before_replacement_can_appear(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    output = tmp_path / "memory"
    actual_validate = vanilla_memory._validate_database_read_only
    validation_calls = 0

    def fail_post_publication(
        path: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        nonlocal validation_calls
        validation_calls += 1
        if validation_calls == 2:
            raise SafetyError("synthetic_post_publication_failure")
        return actual_validate(path, **kwargs)

    actual_identity = vanilla_memory._published_tree_identity

    def replace_after_isolation(root: Path):
        identity = actual_identity(root)
        if root.name == "owned-publication":
            output.mkdir()
            (output / "competitor").write_bytes(b"preserve")
        return identity

    monkeypatch.setattr(
        vanilla_memory, "_validate_database_read_only", fail_post_publication
    )
    monkeypatch.setattr(
        vanilla_memory, "_published_tree_identity", replace_after_isolation
    )
    with pytest.raises(
        SafetyError, match="post_publication_rollback_unproven"
    ):
        build_vanilla_memory(english, russian, GAME_VERSION, output)

    assert (output / "competitor").read_bytes() == b"preserve"
    assert list(tmp_path.glob(".memory.rollback-*")) == []


def test_inspect_is_immutable_read_only_and_preserves_database_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    _, database, _, _ = _build(tmp_path, english_files, russian_files)
    before = (
        hashlib.sha256(database.read_bytes()).hexdigest(),
        database.stat().st_ino,
        database.stat().st_mtime_ns,
        database.stat().st_ctime_ns,
    )
    actual_connect = vanilla_memory.sqlite3.connect
    opened: list[object] = []

    def record_connect(database_arg: object, *args: object, **kwargs: object):
        opened.append(database_arg)
        return actual_connect(database_arg, *args, **kwargs)

    monkeypatch.setattr(vanilla_memory.sqlite3, "connect", record_connect)
    inspected = inspect_vanilla_memory(database)

    assert inspected["counts"]["strict_eligible_pairs"] == 1
    assert opened
    assert all(
        "?mode=ro&immutable=1" in os.fspath(item)
        for item in opened
        if os.fspath(item) != ":memory:"
    )
    after = (
        hashlib.sha256(database.read_bytes()).hexdigest(),
        database.stat().st_ino,
        database.stat().st_mtime_ns,
        database.stat().st_ctime_ns,
    )
    assert after == before
    for suffix in ("-journal", "-wal", "-shm"):
        assert not Path(os.fspath(database) + suffix).exists()


def test_inspect_rejects_mismatched_build_report(
    tmp_path: Path,
) -> None:
    english_files, russian_files = _one_pair_files()
    _, database, _, _ = _build(tmp_path, english_files, russian_files)
    report_path = database.parent / REPORT_NAME
    loaded = json.loads(report_path.read_text(encoding="utf-8"))
    loaded["counts"]["strict_eligible_pairs"] = 0
    report_path.write_text(
        json.dumps(loaded, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path.chmod(0o600)

    with pytest.raises(SafetyError, match="build_report_mismatch"):
        inspect_vanilla_memory(database)


@pytest.mark.parametrize(
    ("field_path", "replacement"),
    [
        (("schema_version",), float(vanilla_memory.SCHEMA_VERSION)),
        (("counts", "quarantined_total"), False),
    ],
)
def test_inspect_rejects_json_type_equivalent_build_report(
    tmp_path: Path,
    field_path: tuple[str, ...],
    replacement: object,
) -> None:
    english_files, russian_files = _one_pair_files()
    _, database, _, _ = _build(tmp_path, english_files, russian_files)
    report_path = database.parent / REPORT_NAME
    loaded = json.loads(report_path.read_text(encoding="utf-8"))
    target = loaded
    for component in field_path[:-1]:
        target = target[component]
    target[field_path[-1]] = replacement
    report_path.write_bytes(vanilla_memory._canonical_report_bytes(loaded))
    report_path.chmod(0o600)

    with pytest.raises(SafetyError, match="build_report_mismatch"):
        inspect_vanilla_memory(database)


def test_inspect_rejects_duplicate_key_hidden_build_report_value(
    tmp_path: Path,
) -> None:
    english_files, russian_files = _one_pair_files()
    _, database, _, _ = _build(tmp_path, english_files, russian_files)
    report_path = database.parent / REPORT_NAME
    canonical = report_path.read_bytes()
    tampered = canonical.replace(
        b"{\n",
        (
            b'{\n  "game_version": '
            b'"MVP6A_SYNTHETIC_HIDDEN_REPORT_VALUE_20260731",\n'
        ),
        1,
    )
    assert json.loads(tampered) == json.loads(canonical)
    report_path.write_bytes(tampered)
    report_path.chmod(0o600)

    with pytest.raises(SafetyError, match="build_report_mismatch"):
        inspect_vanilla_memory(database)


def test_inspect_rejects_unsafe_build_report_mode(
    tmp_path: Path,
) -> None:
    english_files, russian_files = _one_pair_files()
    _, database, _, _ = _build(tmp_path, english_files, russian_files)
    (database.parent / REPORT_NAME).chmod(0o644)

    with pytest.raises(
        SafetyError, match="private_output_file_mode_invalid"
    ):
        inspect_vanilla_memory(database)


def test_inspect_rejects_hardlinked_build_report(
    tmp_path: Path,
) -> None:
    english_files, russian_files = _one_pair_files()
    _, database, _, _ = _build(tmp_path, english_files, russian_files)
    report_path = database.parent / REPORT_NAME
    os.link(report_path, tmp_path / "synthetic-report-link.json")

    with pytest.raises(
        SafetyError, match="private_output_file_mode_invalid"
    ):
        inspect_vanilla_memory(database)


def test_inspect_rejects_sidecar_before_sqlite_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    _, database, _, _ = _build(tmp_path, english_files, russian_files)
    sidecar = Path(os.fspath(database) + "-wal")
    sidecar.write_bytes(b"synthetic-sidecar")
    sidecar.chmod(0o600)
    before = hashlib.sha256(database.read_bytes()).hexdigest()

    def forbidden_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("sqlite opened before sidecar preflight")

    monkeypatch.setattr(vanilla_memory.sqlite3, "connect", forbidden_connect)
    with pytest.raises(
        SafetyError,
        match="database_(parent_inventory_invalid|sidecar_present)",
    ):
        inspect_vanilla_memory(database)

    assert sidecar.read_bytes() == b"synthetic-sidecar"
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_logical_digest_is_reproducible_across_creation_and_output_order(
    tmp_path: Path,
) -> None:
    english_files = {
        "zeta_l_english.yml": _localisation(
            "english", [("zeta.key", "0", "Zeta")]
        ),
        "alpha_l_english.yml": _localisation(
            "english", [("alpha.key", "0", "Alpha")]
        ),
    }
    russian_files = {
        "zeta_l_russian.yml": _localisation(
            "russian", [("zeta.key", "0", "Зета")]
        ),
        "alpha_l_russian.yml": _localisation(
            "russian", [("alpha.key", "0", "Альфа")]
        ),
    }
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first, _, _, _ = _build(
        first_root,
        english_files,
        russian_files,
    )
    second, _, _, _ = _build(
        second_root,
        dict(reversed(list(english_files.items()))),
        dict(reversed(list(russian_files.items()))),
    )

    for name in (
        "english_manifest_sha256",
        "russian_manifest_sha256",
        "english_dataset_sha256",
        "russian_dataset_sha256",
        "logical_digest",
    ):
        assert first["hashes"][name] == second["hashes"][name]
    assert first["counts"] == second["counts"]


def test_manifest_entry_limit_fails_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vanilla_memory, "MAX_MANIFEST_ENTRIES_PER_ROOT", 1)
    _assert_limit_failure(
        tmp_path,
        *_one_pair_files(),
        "manifest_entry_limit_exceeded",
    )


def test_source_directory_limit_fails_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vanilla_memory, "MAX_SOURCE_DIRECTORIES_PER_ROOT", 0)
    _assert_limit_failure(
        tmp_path,
        *_one_pair_files(),
        "source_directory_limit_exceeded",
    )


def test_directory_discovery_stops_before_materializing_more_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english, russian = _roots(tmp_path)
    output = tmp_path / "memory"

    class SyntheticEntry:
        name = "synthetic-directory"

        @staticmethod
        def is_dir(*, follow_symlinks: bool) -> bool:
            assert follow_symlinks is False
            return True

    class BoundedIterator:
        calls = 0
        closed = False

        def __iter__(self):
            return self

        def __next__(self):
            self.calls += 1
            if self.calls == 1:
                return SyntheticEntry()
            raise AssertionError("source discovery read past the bound")

        def close(self) -> None:
            self.closed = True

    iterator = BoundedIterator()
    monkeypatch.setattr(vanilla_memory.os, "scandir", lambda _path: iterator)
    monkeypatch.setattr(vanilla_memory, "MAX_SOURCE_DIRECTORIES_PER_ROOT", 0)

    with pytest.raises(SafetyError, match="source_directory_limit_exceeded"):
        build_vanilla_memory(english, russian, GAME_VERSION, output)

    assert iterator.calls == 1
    assert iterator.closed is True
    assert not output.exists()


def test_regular_file_limit_fails_before_read_or_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vanilla_memory, "MAX_REGULAR_FILES_PER_ROOT", 0)
    _assert_limit_failure(
        tmp_path,
        *_one_pair_files(),
        "source_file_limit_exceeded",
    )


def test_source_byte_limit_fails_before_aggregate_read_or_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    monkeypatch.setattr(
        vanilla_memory,
        "MAX_SOURCE_BYTES_PER_ROOT",
        len(next(iter(english_files.values()))) - 1,
    )
    _assert_limit_failure(
        tmp_path,
        english_files,
        russian_files,
        "source_bytes_limit_exceeded",
    )


def test_yml_file_limit_per_root_fails_before_read_or_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vanilla_memory, "MAX_YML_SOURCE_FILES_PER_ROOT", 0)
    _assert_limit_failure(
        tmp_path,
        *_one_pair_files(),
        "source_yml_file_limit_exceeded",
    )


def test_yml_file_total_limit_fails_before_second_root_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vanilla_memory, "MAX_YML_SOURCE_FILES_TOTAL", 1)
    _assert_limit_failure(
        tmp_path,
        *_one_pair_files(),
        "source_yml_file_total_limit_exceeded",
    )


def test_parsed_line_limit_fails_before_parser_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vanilla_memory, "MAX_PARSED_LINES_PER_LANGUAGE", 1)
    _assert_limit_failure(
        tmp_path,
        *_one_pair_files(),
        "source_line_limit_exceeded",
    )


def test_occurrence_limit_per_language_fails_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vanilla_memory, "MAX_OCCURRENCES_PER_LANGUAGE", 0)
    _assert_limit_failure(
        tmp_path,
        *_one_pair_files(),
        "source_occurrence_language_limit_exceeded",
    )


def test_occurrence_total_limit_fails_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vanilla_memory, "MAX_OCCURRENCES_TOTAL", 1)
    _assert_limit_failure(
        tmp_path,
        *_one_pair_files(),
        "source_occurrence_total_limit_exceeded",
    )


def test_protected_token_total_limit_fails_before_row_allocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vanilla_memory, "MAX_PROTECTED_TOKENS_TOTAL", 3)
    _assert_limit_failure(
        tmp_path,
        *_one_pair_files(),
        "protected_token_limit_exceeded",
    )


def test_record_quarantine_limit_fails_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vanilla_memory, "MAX_RECORD_QUARANTINES_TOTAL", 0)
    _assert_limit_failure(
        tmp_path,
        {
            "bounded_l_english.yml": _localisation(
                "english",
                [("synthetic.entry", "0", "Supported")],
                extra_lines=(" synthetic.quarantine:0 unquoted",),
            )
        },
        {},
        "record_quarantine_limit_exceeded",
    )


def test_file_quarantine_limit_fails_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vanilla_memory, "MAX_FILE_QUARANTINES_TOTAL", 0)
    _assert_limit_failure(
        tmp_path,
        {"bounded_l_english.yml": b"\xff"},
        {},
        "file_quarantine_limit_exceeded",
    )


def test_quarantined_key_candidate_limit_is_aggregate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vanilla_memory, "MAX_QUARANTINED_KEY_CANDIDATES", 1
    )
    unsafe = BOM + b'l_english:\n synthetic.entry:0 "\xff"\n'
    _assert_limit_failure(
        tmp_path,
        {
            "first_l_english.yml": unsafe,
            "second_l_english.yml": unsafe,
        },
        {},
        "quarantined_key_candidate_limit_exceeded",
    )


def test_all_resource_classes_pass_immediately_below_their_limits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    largest_source = max(
        len(data)
        for data in (*english_files.values(), *russian_files.values())
    )
    limits = {
        "MAX_MANIFEST_ENTRIES_PER_ROOT": 3,
        "MAX_SOURCE_DIRECTORIES_PER_ROOT": 2,
        "MAX_REGULAR_FILES_PER_ROOT": 2,
        "MAX_SOURCE_BYTES_PER_ROOT": largest_source + 1,
        "MAX_YML_SOURCE_FILES_PER_ROOT": 2,
        "MAX_YML_SOURCE_FILES_TOTAL": 3,
        "MAX_PARSED_LINES_PER_LANGUAGE": 4,
        "MAX_PARSED_LINES_TOTAL": 7,
        "MAX_OCCURRENCES_PER_LANGUAGE": 2,
        "MAX_OCCURRENCES_TOTAL": 3,
        "MAX_PROTECTED_TOKENS_TOTAL": 5,
        "MAX_RECORD_QUARANTINES_TOTAL": 1,
        "MAX_FILE_QUARANTINES_TOTAL": 1,
        "MAX_QUARANTINED_KEY_CANDIDATES": 1,
    }
    for name, value in limits.items():
        monkeypatch.setattr(vanilla_memory, name, value)

    report, database, _, _ = _build(
        tmp_path, english_files, russian_files
    )

    assert report["counts"]["english_occurrences"] == 1
    assert report["counts"]["russian_occurrences"] == 1
    assert inspect_vanilla_memory(database)["counts"] == report["counts"]


def test_inspect_applies_resource_bounds_before_materializing_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report, database, _, _ = _build(tmp_path, *_one_pair_files())
    assert report["counts"]["english_occurrences"] == 1
    assert report["counts"]["russian_occurrences"] == 1
    monkeypatch.setattr(vanilla_memory, "MAX_OCCURRENCES_TOTAL", 1)

    def forbidden_rows(_connection: sqlite3.Connection) -> dict[str, object]:
        raise AssertionError("rows materialized before resource bounds")

    actual_read = vanilla_memory._read_stable_private_file

    def forbid_buffered_database_read(
        path: Path,
        *,
        max_bytes: int,
    ):
        assert path.name != DATABASE_NAME
        return actual_read(path, max_bytes=max_bytes)

    monkeypatch.setattr(
        vanilla_memory, "_validate_database_rows", forbidden_rows
    )
    monkeypatch.setattr(
        vanilla_memory,
        "_read_stable_private_file",
        forbid_buffered_database_read,
    )

    with pytest.raises(
        SafetyError, match="source_occurrence_total_limit_exceeded"
    ):
        inspect_vanilla_memory(database)


@pytest.mark.parametrize(
    ("constant", "value", "error"),
    [
        ("MAX_MANIFEST_ENTRIES_PER_ROOT", 1, "manifest_entry_limit_exceeded"),
        ("MAX_SOURCE_DIRECTORIES_PER_ROOT", 0, "source_directory_limit_exceeded"),
        ("MAX_REGULAR_FILES_PER_ROOT", 0, "source_file_limit_exceeded"),
        ("MAX_SOURCE_BYTES_PER_ROOT", 0, "source_bytes_limit_exceeded"),
        ("MAX_YML_SOURCE_FILES_PER_ROOT", 0, "source_yml_file_limit_exceeded"),
        ("MAX_YML_SOURCE_FILES_TOTAL", 1, "source_yml_file_total_limit_exceeded"),
        (
            "MAX_OCCURRENCES_PER_LANGUAGE",
            0,
            "source_occurrence_language_limit_exceeded",
        ),
        ("MAX_OCCURRENCES_TOTAL", 1, "source_occurrence_total_limit_exceeded"),
        ("MAX_PROTECTED_TOKENS_TOTAL", 3, "protected_token_limit_exceeded"),
    ],
)
def test_inspect_rejects_each_persisted_resource_class_before_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    constant: str,
    value: int,
    error: str,
) -> None:
    _, database, _, _ = _build(tmp_path, *_one_pair_files())
    monkeypatch.setattr(vanilla_memory, constant, value)
    monkeypatch.setattr(
        vanilla_memory,
        "_validate_database_rows",
        lambda _connection: (_ for _ in ()).throw(
            AssertionError("rows materialized before resource bounds")
        ),
    )

    with pytest.raises(SafetyError, match=error):
        inspect_vanilla_memory(database)


def test_inspect_rejects_quarantine_bounds_before_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, record_database, _, _ = _build(
        tmp_path,
        {
            "bounded_l_english.yml": _localisation(
                "english",
                [("synthetic.entry", "0", "Supported")],
                extra_lines=(" synthetic.quarantine:0 unquoted",),
            )
        },
        {},
        name="record-memory",
        roots_name="record-inputs",
    )
    monkeypatch.setattr(vanilla_memory, "MAX_RECORD_QUARANTINES_TOTAL", 0)
    monkeypatch.setattr(
        vanilla_memory,
        "_validate_database_rows",
        lambda _connection: (_ for _ in ()).throw(
            AssertionError("rows materialized before resource bounds")
        ),
    )
    with pytest.raises(SafetyError, match="record_quarantine_limit_exceeded"):
        inspect_vanilla_memory(record_database)

    monkeypatch.undo()
    monkeypatch.setattr(
        vanilla_memory,
        "MAX_RECORD_QUARANTINES_TOTAL",
        500_000,
    )
    unsafe = BOM + b'l_english:\n synthetic.entry:0 "\xff"\n'
    _, file_database, _, _ = _build(
        tmp_path,
        {"bounded_l_english.yml": unsafe},
        {},
        name="file-memory",
        roots_name="file-inputs",
    )
    monkeypatch.setattr(vanilla_memory, "MAX_FILE_QUARANTINES_TOTAL", 0)
    with pytest.raises(SafetyError, match="file_quarantine_limit_exceeded"):
        inspect_vanilla_memory(file_database)

    monkeypatch.setattr(vanilla_memory, "MAX_FILE_QUARANTINES_TOTAL", 16_384)
    monkeypatch.setattr(vanilla_memory, "MAX_QUARANTINED_KEY_CANDIDATES", 0)
    with pytest.raises(
        SafetyError, match="quarantined_key_candidate_limit_exceeded"
    ):
        inspect_vanilla_memory(file_database)


def test_inspect_hashes_database_without_buffering_entire_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report, database, _, _ = _build(tmp_path, *_one_pair_files())
    actual_read = vanilla_memory._read_stable_private_file

    def guard(path: Path, *, max_bytes: int):
        assert path.name != DATABASE_NAME
        return actual_read(path, max_bytes=max_bytes)

    monkeypatch.setattr(vanilla_memory, "_read_stable_private_file", guard)

    assert inspect_vanilla_memory(database)["hashes"] == report["hashes"]


def test_build_hashes_publication_identity_without_buffering_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual_read = vanilla_memory._read_stable_private_file

    def guard(path: Path, *, max_bytes: int):
        assert path.name != DATABASE_NAME
        return actual_read(path, max_bytes=max_bytes)

    monkeypatch.setattr(vanilla_memory, "_read_stable_private_file", guard)

    report, database, _, _ = _build(tmp_path, *_one_pair_files())

    assert database.is_file()
    assert inspect_vanilla_memory(database)["hashes"] == report["hashes"]


def test_resource_limit_defaults_are_exactly_documented() -> None:
    assert vanilla_memory.MAX_MANIFEST_ENTRIES_PER_ROOT == 4_096
    assert vanilla_memory.MAX_SOURCE_DIRECTORIES_PER_ROOT == 2_048
    assert vanilla_memory.MAX_REGULAR_FILES_PER_ROOT == 2_048
    assert vanilla_memory.MAX_SOURCE_BYTES_PER_ROOT == 128 * 1024 * 1024
    assert vanilla_memory.MAX_YML_SOURCE_FILES_PER_ROOT == 1_024
    assert vanilla_memory.MAX_YML_SOURCE_FILES_TOTAL == 2_048
    assert vanilla_memory.MAX_PARSED_LINES_PER_LANGUAGE == 1_500_000
    assert vanilla_memory.MAX_PARSED_LINES_TOTAL == 3_000_000
    assert vanilla_memory.MAX_OCCURRENCES_PER_LANGUAGE == 1_000_000
    assert vanilla_memory.MAX_OCCURRENCES_TOTAL == 2_000_000
    assert vanilla_memory.MAX_PROTECTED_TOKENS_TOTAL == 1_500_000
    assert vanilla_memory.MAX_RECORD_QUARANTINES_TOTAL == 500_000
    assert vanilla_memory.MAX_FILE_QUARANTINES_TOTAL == 16_384
    assert vanilla_memory.MAX_QUARANTINED_KEY_CANDIDATES == 2_000_000


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_source_links_and_special_files_fail_before_publication(
    tmp_path: Path,
    kind: str,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    unsafe = english / "unsafe_l_english.yml"
    target = tmp_path / "outside.yml"
    target.write_bytes(_localisation("english", [("outside", "0", "Outside")]))
    if kind == "symlink":
        unsafe.symlink_to(target)
    elif kind == "hardlink":
        os.link(target, unsafe)
    else:
        os.mkfifo(unsafe)
    output = tmp_path / "memory"

    with pytest.raises(SafetyError):
        build_vanilla_memory(english, russian, GAME_VERSION, output)

    assert not output.exists()
    assert list(tmp_path.glob(".memory.tmp-*")) == []


@pytest.mark.parametrize("alias_kind", ["case", "unicode"])
def test_distinct_portable_path_aliases_fail_closed_when_filesystem_allows_them(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    if alias_kind == "case":
        first_name = "Alias_l_english.yml"
        second_name = "alias_l_english.yml"
    else:
        first_name = "caf\u00e9_l_english.yml"
        second_name = unicodedata.normalize("NFD", first_name)
    first = english / first_name
    second = english / second_name
    first.write_bytes(_localisation("english", [("first", "0", "First")]))
    second.write_bytes(_localisation("english", [("second", "0", "Second")]))
    if os.path.samefile(first, second):
        pytest.skip("filesystem collapses this portable alias")

    with pytest.raises(SafetyError, match="source_portable_path_collision"):
        build_vanilla_memory(
            english,
            russian,
            GAME_VERSION,
            tmp_path / "memory",
        )


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("Alias_l_english.yml", "alias_l_english.yml"),
        (
            "caf\u00e9_l_english.yml",
            "cafe\u0301_l_english.yml",
        ),
    ],
)
def test_portable_path_collision_gate_is_filesystem_independent(
    first: str,
    second: str,
) -> None:
    known: dict[
        tuple[str, ...], tuple[tuple[str, ...], str]
    ] = {}
    vanilla_memory._admit_portable_path(
        known, Path(first), "file"
    )

    with pytest.raises(SafetyError, match="source_portable_path_collision"):
        vanilla_memory._admit_portable_path(
            known, Path(second), "file"
        )


def test_source_and_output_physical_overlap_is_rejected(tmp_path: Path) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)

    with pytest.raises(SafetyError, match="vanilla_memory_path_overlap"):
        build_vanilla_memory(
            english,
            russian,
            GAME_VERSION,
            english / "memory",
        )


def test_english_and_russian_roots_cannot_be_the_same_physical_tree(
    tmp_path: Path,
) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    _write(
        shared,
        "one_l_english.yml",
        _localisation("english", [("one", "0", "One")]),
    )

    with pytest.raises(SafetyError, match="vanilla_memory_path_overlap"):
        build_vanilla_memory(
            shared,
            shared,
            GAME_VERSION,
            tmp_path / "memory",
        )


def test_symlinked_output_parent_is_rejected(tmp_path: Path) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    real_parent = tmp_path / "real-output-parent"
    real_parent.mkdir()
    alias_parent = tmp_path / "output-parent-alias"
    alias_parent.symlink_to(real_parent, target_is_directory=True)

    with pytest.raises(SafetyError, match="output_parent_unsafe"):
        build_vanilla_memory(
            english,
            russian,
            GAME_VERSION,
            alias_parent / "memory",
        )


def test_one_full_source_generation_retry_can_succeed_without_residue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    output = tmp_path / "memory"
    actual_verify = vanilla_memory._verify_source_snapshot
    calls = 0

    def drift_once(
        snapshot: object,
        budget: object | None = None,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise vanilla_memory._SourceGenerationChanged()
        actual_verify(snapshot, budget)

    monkeypatch.setattr(vanilla_memory, "_verify_source_snapshot", drift_once)
    report = build_vanilla_memory(english, russian, GAME_VERSION, output)

    assert report["source_generations"] == "PASS"
    assert calls == 7
    assert output.is_dir()
    assert list(tmp_path.glob(".memory.tmp-*")) == []


def test_repeated_source_generation_drift_blocks_after_one_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    output = tmp_path / "memory"

    def always_drift(
        _snapshot: object,
        _budget: object | None = None,
    ) -> None:
        raise vanilla_memory._SourceGenerationChanged()

    monkeypatch.setattr(
        vanilla_memory, "_verify_source_snapshot", always_drift
    )
    with pytest.raises(
        SafetyError, match="source_generation_changed_after_retry"
    ):
        build_vanilla_memory(english, russian, GAME_VERSION, output)

    assert not output.exists()
    assert list(tmp_path.glob(".memory.tmp-*")) == []


def test_inspect_rejects_semantically_tampered_count_algebra(
    tmp_path: Path,
) -> None:
    english_files, russian_files = _one_pair_files()
    _, database, _, _ = _build(tmp_path, english_files, russian_files)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE metadata
            SET strict_eligible_pairs = 0,
                missing_counterparts = 2,
                quarantined_total = 2,
                build_status = 'COMPLETE_WITH_QUARANTINED_RECORDS'
            WHERE singleton = 1
            """
        )

    with pytest.raises(SafetyError, match="stored_count_mismatch"):
        inspect_vanilla_memory(database)


def test_inspect_rejects_schema_extension(tmp_path: Path) -> None:
    english_files, russian_files = _one_pair_files()
    _, database, _, _ = _build(tmp_path, english_files, russian_files)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE synthetic_extra(value TEXT) STRICT")

    with pytest.raises(SafetyError, match="database_schema_signature_invalid"):
        inspect_vanilla_memory(database)


@pytest.mark.parametrize(
    ("pragma", "error"),
    [
        ("PRAGMA user_version = 2", "database_schema_version_unknown"),
        ("PRAGMA application_id = 1397576758", "database_application_id_unknown"),
    ],
)
def test_inspect_rejects_previous_schema_and_application_domains(
    tmp_path: Path,
    pragma: str,
    error: str,
) -> None:
    _, database, _, _ = _build(tmp_path, *_one_pair_files())
    with sqlite3.connect(database) as connection:
        connection.execute(pragma)

    with pytest.raises(SafetyError, match=error):
        inspect_vanilla_memory(database)


def test_schema_and_logical_digest_domains_are_v3() -> None:
    assert vanilla_memory.SCHEMA_VERSION == 3
    assert vanilla_memory.APPLICATION_ID == 0x534D5437
    assert vanilla_memory._LOGICAL_DIGEST_DOMAIN == (
        b"SMT_CONTEXTUAL_VANILLA_MEMORY_LOGICAL_V3"
    )


def test_build_never_constructs_ollama_or_network_clients(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network or Ollama client constructed")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(
        "stellaris_mod_translator.engine.OllamaClient",
        forbidden,
    )
    report, _, _, _ = _build(tmp_path, english_files, russian_files)

    assert report["ollama_calls"] == 0
    assert report["counts"]["ollama_calls"] == 0


def test_quarantined_key_hint_prevents_hidden_duplicate_strict_pair(
    tmp_path: Path,
) -> None:
    report, database, _, _ = _build(
        tmp_path,
        {
            "duplicate_l_english.yml": _localisation(
                "english",
                [("hidden.duplicate", "0", "Supported")],
                extra_lines=(" hidden.duplicate:0 unquoted",),
            )
        },
        {
            "duplicate_l_russian.yml": _localisation(
                "russian",
                [("hidden.duplicate", "0", "Поддержано")],
            )
        },
    )

    assert report["counts"]["strict_eligible_pairs"] == 0
    assert report["counts"]["duplicate_key_occurrences"] == 2
    assert report["counts"]["malformed_record_units"] == 1
    assert report["counts"]["quarantined_total"] == 3
    assert {
        row["alignment_state"]
        for row in _read_rows(
            database, "SELECT alignment_state FROM occurrences"
        )
    } == {"duplicate_key"}
    quarantine = _read_rows(
        database,
        "SELECT key_hint FROM quarantine_records",
    )
    assert [row["key_hint"] for row in quarantine] == [
        "hidden.duplicate"
    ]


@pytest.mark.parametrize(
    "unsafe_line",
    [
        b' mvp6a.hidden.file.duplicate:0 "\xff"\n',
        (
            ' mvp6a.hidden.file.duplicate:0 "MVP6A '
            'synthetic\u200bvalue"\n'
        ).encode("utf-8"),
    ],
)
def test_whole_file_key_inventory_prevents_hidden_duplicate_strict_pair(
    tmp_path: Path,
    unsafe_line: bytes,
) -> None:
    key = "mvp6a.hidden.file.duplicate"
    report, database, _, _ = _build(
        tmp_path,
        {
            "parsed_l_english.yml": _localisation(
                "english",
                [(key, "0", "MVP6A synthetic supported value")],
            ),
            "quarantined_l_english.yml": (
                BOM + b"l_english:\n" + unsafe_line
            ),
        },
        {
            "parsed_l_russian.yml": _localisation(
                "russian",
                [(key, "0", "MVP6A synthetic Russian value")],
            )
        },
    )

    assert report["counts"]["strict_eligible_pairs"] == 0
    assert report["counts"]["duplicate_key_occurrences"] == 2
    assert report["counts"]["malformed_file_units"] == 1
    assert report["counts"]["quarantined_total"] == 3
    assert _read_rows(database, "SELECT * FROM reference_pairs") == []
    assert {
        row["alignment_state"]
        for row in _read_rows(
            database, "SELECT alignment_state FROM occurrences"
        )
    } == {"duplicate_key"}
    inventory = _read_rows(
        database,
        """
        SELECT candidate_count
        FROM quarantined_key_occupancy
        WHERE key_hint = ?
        """,
        (key,),
    )
    assert [row["candidate_count"] for row in inventory] == [1]


def test_whole_file_key_inventory_preserves_hidden_multiplicity(
    tmp_path: Path,
) -> None:
    key = "mvp6a.repeated.quarantined.key"
    report, database, _, _ = _build(
        tmp_path,
        {
            "parsed_l_english.yml": _localisation(
                "english",
                [(key, "0", "MVP6A synthetic English")],
            ),
            "quarantined_l_english.yml": (
                BOM
                + b"l_english:\n"
                + b' mvp6a.repeated.quarantined.key:0 "\xff"\n'
                + b' mvp6a.repeated.quarantined.key:0 "\xfe"\n'
            ),
        },
        {
            "parsed_l_russian.yml": _localisation(
                "russian",
                [(key, "0", "MVP6A synthetic Russian")],
            )
        },
    )

    assert report["counts"]["duplicate_key_occurrences"] == 2
    inventory = _read_rows(
        database,
        """
        SELECT candidate_count
        FROM quarantined_key_occupancy
        WHERE key_hint = ?
        """,
        (key,),
    )
    assert [row["candidate_count"] for row in inventory] == [2]


def test_unattributed_malformed_record_quarantines_its_file(
    tmp_path: Path,
) -> None:
    report, database, _, _ = _build(
        tmp_path,
        {
            "unsafe_l_english.yml": _localisation(
                "english",
                [("otherwise.valid", "0", "Supported")],
                extra_lines=(" malformed$key:0 unquoted",),
            )
        },
        {
            "safe_l_russian.yml": _localisation(
                "russian",
                [("otherwise.valid", "0", "Поддержано")],
            )
        },
    )

    assert report["counts"]["strict_eligible_pairs"] == 0
    assert report["counts"]["malformed_file_units"] == 1
    assert report["counts"]["missing_counterparts"] == 1
    reasons = _read_rows(
        database,
        "SELECT diagnostic_reason FROM quarantine_records",
    )
    assert [row["diagnostic_reason"] for row in reasons] == [
        "unattributed_malformed_record"
    ]


def test_context_path_mismatch_counts_every_unique_alignment_state(
    tmp_path: Path,
) -> None:
    report, _, _, _ = _build(
        tmp_path,
        {
            "one/version_l_english.yml": _localisation(
                "english",
                [("path.and.version", "0", "English")],
            )
        },
        {
            "two/version_l_russian.yml": _localisation(
                "russian",
                [("path.and.version", "1", "Русский")],
            )
        },
    )

    assert report["counts"]["strict_eligible_pairs"] == 0
    assert report["counts"]["version_mismatches"] == 1
    assert report["counts"]["context_path_mismatches"] == 1


def test_post_publication_validation_failure_rolls_back_owned_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    output = tmp_path / "memory"
    actual_validate = vanilla_memory._validate_database_read_only
    calls = 0

    def fail_second(path: Path, **kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise SafetyError("synthetic_post_publication_failure")
        return actual_validate(path, **kwargs)

    monkeypatch.setattr(
        vanilla_memory, "_validate_database_read_only", fail_second
    )
    with pytest.raises(
        SafetyError, match="synthetic_post_publication_failure"
    ):
        build_vanilla_memory(english, russian, GAME_VERSION, output)

    assert not output.exists()
    assert list(tmp_path.glob(".memory.tmp-*")) == []


def test_initial_snapshot_drift_gets_one_full_generation_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    actual_snapshot = vanilla_memory._snapshot_source_tree
    calls = 0

    def drift_once(
        root: Path,
        language: str,
        budget: object | None = None,
    ):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise vanilla_memory._SourceGenerationChanged()
        return actual_snapshot(root, language, budget)

    monkeypatch.setattr(
        vanilla_memory, "_snapshot_source_tree", drift_once
    )
    report = build_vanilla_memory(
        english,
        russian,
        GAME_VERSION,
        tmp_path / "memory",
    )

    assert report["source_generations"] == "PASS"
    assert calls >= 5


def test_inspect_rejects_persistent_wal_header_without_sidecars(
    tmp_path: Path,
) -> None:
    english_files, russian_files = _one_pair_files()
    _, database, _, _ = _build(tmp_path, english_files, russian_files)
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "PRAGMA journal_mode = WAL"
        ).fetchone()[0] == "wal"
    for suffix in ("-journal", "-wal", "-shm"):
        sidecar = Path(os.fspath(database) + suffix)
        if sidecar.exists():
            sidecar.unlink()

    with pytest.raises(SafetyError, match="database_header_mode_invalid"):
        inspect_vanilla_memory(database)


def test_inspect_rejects_tokens_not_derived_from_exact_human_value(
    tmp_path: Path,
) -> None:
    english_files, russian_files = _one_pair_files()
    _, database, _, _ = _build(tmp_path, english_files, russian_files)
    empty_signature = vanilla_memory._token_signature(())
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM protected_tokens")
        connection.execute(
            "UPDATE occurrences SET protected_signature_sha256 = ?",
            (empty_signature,),
        )
        digest = vanilla_memory._logical_digest(connection)
        connection.execute(
            "UPDATE metadata SET logical_digest = ?",
            (digest,),
        )

    with pytest.raises(
        SafetyError, match="occurrence_protected_tokens_mismatch"
    ):
        inspect_vanilla_memory(database)


def test_inspect_rejects_unknown_quarantine_reason_before_output(
    tmp_path: Path,
) -> None:
    report, database, _, _ = _build(
        tmp_path,
        {"invalid_l_english.yml": b"\xff"},
        {},
    )
    assert report["counts"]["malformed_file_units"] == 1
    source = _read_rows(
        database,
        """
        SELECT key_occupancy_scan_contract,
               key_occupancy_candidate_count
        FROM source_files
        WHERE parse_state = 'quarantined'
        """,
    )[0]
    assert source["key_occupancy_scan_contract"] == (
        vanilla_memory._KEY_OCCUPANCY_SCAN_CONTRACT
    )
    assert source["key_occupancy_candidate_count"] == 0
    assert _read_rows(
        database,
        "SELECT * FROM quarantined_key_occupancy",
    ) == []
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE quarantine_records
            SET diagnostic_reason = 'SYNTHETIC_PRIVATE_SENTINEL'
            """
        )

    with pytest.raises(SafetyError, match="quarantine_reason_unknown"):
        inspect_vanilla_memory(database)


@pytest.mark.parametrize(
    "label",
    [
        "/private/version",
        "Pegasus\\private",
        "Pegasus\nprivate",
        "Пегас 4.4.6",
    ],
)
def test_game_version_is_a_closed_content_free_label(
    tmp_path: Path,
    label: str,
) -> None:
    english_files, russian_files = _one_pair_files()
    english, russian = _roots(tmp_path)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)

    with pytest.raises(SafetyError, match="game_version_invalid"):
        build_vanilla_memory(
            english,
            russian,
            label,
            tmp_path / "memory",
        )


@pytest.mark.parametrize(
    "relative",
    [".", "unsafe\u0085name.yml", "unsafe\u2028name.yml"],
)
def test_relative_path_validator_rejects_ambiguous_components(
    relative: str,
) -> None:
    with pytest.raises(SafetyError, match="relative_path_invalid"):
        vanilla_memory._require_relative_path_value(relative)


@pytest.mark.parametrize(
    "filename",
    ["unsafe\u0085_l_english.yml", "unsafe\u2029_l_english.yml"],
)
def test_builder_rejects_ambiguous_source_path_before_publication(
    tmp_path: Path,
    filename: str,
) -> None:
    english_files, russian_files = _one_pair_files()
    english_files[filename] = _localisation(
        "english", [("unsafe.path", "0", "Unsafe")]
    )

    with pytest.raises(SafetyError, match="relative_path_invalid"):
        _build(tmp_path, english_files, russian_files)
    assert not (tmp_path / "memory").exists()


def test_inspect_rejects_root_equivalent_manifest_path(
    tmp_path: Path,
) -> None:
    english_files, russian_files = _one_pair_files()
    _, database, _, _ = _build(tmp_path, english_files, russian_files)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE manifest_entries
            SET relative_path = '.'
            WHERE language = 'english'
              AND entry_kind = 'directory'
              AND relative_path = 'context'
            """
        )

    with pytest.raises(SafetyError, match="relative_path_invalid"):
        inspect_vanilla_memory(database)
