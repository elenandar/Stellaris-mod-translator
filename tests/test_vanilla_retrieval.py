from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3

import pytest

from stellaris_mod_translator.cli import main
from stellaris_mod_translator.engine import SafetyError
from stellaris_mod_translator import engine, ollama, vanilla_retrieval, workspace
from stellaris_mod_translator.parser import parse_localisation
from stellaris_mod_translator.vanilla_memory import (
    DATABASE_NAME,
    REPORT_NAME,
    build_vanilla_memory,
)
from stellaris_mod_translator.vanilla_retrieval import (
    QueryToken,
    RetrievalLimits,
    RetrievalQuery,
    inspect_vanilla_context_coverage,
    retrieve_exact_context_v1,
)


GAME_VERSION = "Synthetic Pegasus 4.4.6"
BOM = b"\xef\xbb\xbf"


def _localisation(
    language: str,
    entries: list[tuple[str, str | None, str]],
    *,
    extra_lines: tuple[str, ...] = (),
) -> bytes:
    lines = [f"l_{language}:", " # synthetic gold corpus"]
    for key, suffix, value in entries:
        version = "" if suffix is None else suffix
        lines.append(f' {key}:{version} "{value}"')
    lines.extend(extra_lines)
    return BOM + ("\n".join(lines) + "\n").encode("utf-8")


def _write(root: Path, relative: str, data: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _build_memory(
    tmp_path: Path,
    english_files: dict[str, bytes],
    russian_files: dict[str, bytes],
    *,
    name: str = "memory",
) -> tuple[dict[str, object], Path]:
    english = tmp_path / f"{name}-inputs" / "english"
    russian = tmp_path / f"{name}-inputs" / "russian"
    english.mkdir(parents=True)
    russian.mkdir(parents=True)
    for relative, data in english_files.items():
        _write(english, relative, data)
    for relative, data in russian_files.items():
        _write(russian, relative, data)
    output = tmp_path / name
    report = build_vanilla_memory(
        english, russian, GAME_VERSION, output
    )
    return report, output / DATABASE_NAME


def _one_pair_memory(
    tmp_path: Path,
    *,
    english_value: str = (
        "MVP6B synthetic $MVP6B_ACTOR_20260731$ "
        "[MVP6B.GetSyntheticName]"
    ),
    russian_value: str = (
        "MVP6B русский $MVP6B_ACTOR_20260731$ "
        "[MVP6B.GetSyntheticName]"
    ),
    suffix: str | None = "0",
) -> tuple[dict[str, object], Path]:
    return _build_memory(
        tmp_path,
        {
            "context/scene_l_english.yml": _localisation(
                "english", [("synthetic.entry", suffix, english_value)]
            )
        },
        {
            "context/scene_l_russian.yml": _localisation(
                "russian", [("synthetic.entry", suffix, russian_value)]
            )
        },
    )


def _pins(report: dict[str, object]) -> dict[str, str]:
    hashes = report["hashes"]
    assert isinstance(hashes, dict)
    return {
        "database_sha256": str(hashes["database_sha256"]),
        "logical_digest": str(hashes["logical_digest"]),
        "game_version": GAME_VERSION,
    }


def _tokens(value: str) -> tuple[QueryToken, ...]:
    parsed = vanilla_retrieval._protected_tokens(value)
    return tuple(
        QueryToken(
            kind=vanilla_retrieval._token_kind(token.original),
            exact=token.original,
        )
        for token in parsed
    )


def _query(
    key: str,
    value: str,
    *,
    suffix: str | None = "0",
    path: str = "localisation/english/context/scene_l_english.yml",
) -> RetrievalQuery:
    return RetrievalQuery(
        relative_path=path,
        localisation_key=key,
        version_suffix=suffix,
        english_human_value=value,
        protected_tokens=_tokens(value),
    )


def _retrieve(
    report: dict[str, object],
    database: Path,
    *queries: RetrievalQuery,
    limits: RetrievalLimits = RetrievalLimits(),
):
    return retrieve_exact_context_v1(
        database,
        tuple(queries),
        limits=limits,
        **_pins(report),
    )


def _source_mod(
    tmp_path: Path,
    files: dict[str, bytes],
    *,
    name: str = "source",
) -> Path:
    source = tmp_path / name
    source.mkdir()
    for relative, data in files.items():
        _write(source, relative, data)
    return source


def _coverage(
    report: dict[str, object], database: Path, source: Path
) -> dict[str, object]:
    pins = _pins(report)
    return inspect_vanilla_context_coverage(
        source,
        database,
        pins["database_sha256"],
        pins["logical_digest"],
        pins["game_version"],
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_exact_key_context_overrides_ambiguous_text_and_preserves_flag(
    tmp_path: Path,
) -> None:
    report, database = _build_memory(
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
                    ("context.one", "0", "Первый вариант"),
                    ("context.two", "0", "Второй вариант"),
                ],
            )
        },
    )

    batch = _retrieve(
        report,
        database,
        _query("context.one", "Shared English"),
        _query("context.absent", "Shared English"),
    )

    exact, fallback = batch.results
    assert exact.status == "exact_key_context"
    assert len(exact.candidates) == 1
    assert exact.candidates[0].global_text_ambiguous is True
    assert exact.candidates[0].russian_model_text == "Первый вариант"
    assert fallback.status == "excluded_ambiguous_text"
    assert fallback.candidates == ()


def test_exact_key_conflict_never_falls_back_to_matching_other_key(
    tmp_path: Path,
) -> None:
    report, database = _build_memory(
        tmp_path,
        {
            "priority_l_english.yml": _localisation(
                "english",
                [
                    ("priority.key", "0", "Exact source"),
                    ("fallback.key", "0", "Fallback source"),
                ],
            )
        },
        {
            "priority_l_russian.yml": _localisation(
                "russian",
                [
                    ("priority.key", "0", "Точный контекст"),
                    ("fallback.key", "0", "Резервный контекст"),
                ],
            )
        },
    )

    result = _retrieve(
        report,
        database,
        _query("priority.key", "Fallback source"),
    ).results[0]

    assert result.status == "excluded_key_conflict"
    assert result.candidates == ()


def test_exact_text_consensus_collapses_equal_russian_and_ranks_path_family(
    tmp_path: Path,
) -> None:
    english_files = {
        "other/scene_l_english.yml": _localisation(
            "english", [("consensus.other", "0", "Consensus English")]
        ),
        "family/scene_l_english.yml": _localisation(
            "english", [("consensus.family", "0", "Consensus English")]
        ),
    }
    russian_files = {
        "other/scene_l_russian.yml": _localisation(
            "russian", [("consensus.other", "0", "Единый вариант")]
        ),
        "family/scene_l_russian.yml": _localisation(
            "russian", [("consensus.family", "0", "Единый вариант")]
        ),
    }
    report, database = _build_memory(
        tmp_path, english_files, russian_files
    )
    reordered_report, reordered_database = _build_memory(
        tmp_path,
        dict(reversed(tuple(english_files.items()))),
        dict(reversed(tuple(russian_files.items()))),
        name="memory-reordered",
    )
    query = _query(
        "consensus.absent",
        "Consensus English",
        path="localisation/english/family/scene_l_english.yml",
    )

    first = _retrieve(report, database, query).results[0]
    second = _retrieve(
        reordered_report, reordered_database, query
    ).results[0]

    assert first.status == "exact_text_consensus"
    assert first.examined_references == 2
    assert len(first.candidates) == 1
    assert first.candidates[0].path_family_match is True
    assert first.candidates[0].russian_model_text == "Единый вариант"
    assert second.candidates[0].pair_id == first.candidates[0].pair_id


def test_path_family_uses_exact_nfc_nfd_bytes_without_normalization(
) -> None:
    nfc = "caf\u00e9"
    nfd = "cafe\u0301"
    reference = vanilla_retrieval._Reference(
        pair_id="a" * 64,
        english_occurrence_id="b" * 64,
        russian_occurrence_id="c" * 64,
        key="unicode.reference",
        english_path=f"{nfc}/scene_l_english.yml",
        suffix="0",
        english_value="Unicode context",
        russian_value="Один контекст",
        english_tokens=(),
        russian_tokens=(),
        alias_risk=False,
        global_text_ambiguous=False,
    )
    exact_query = _query(
        "unicode.query",
        "Unicode context",
        path=f"localisation/english/{nfc}/scene_l_english.yml",
    )
    normalized_query = _query(
        "unicode.query",
        "Unicode context",
        path=f"localisation/english/{nfd}/scene_l_english.yml",
    )

    assert vanilla_retrieval._path_family_matches(
        exact_query.relative_path, reference
    )
    assert not vanilla_retrieval._path_family_matches(
        normalized_query.relative_path, reference
    )


def test_case_and_unicode_similar_query_keys_remain_exact_bytes() -> None:
    upper = vanilla_retrieval._validated_query(
        _query("Alias.Key", "Value")
    )
    lower = vanilla_retrieval._validated_query(
        _query("alias.key", "Value")
    )
    nfc = vanilla_retrieval._validated_query(
        _query("A\u00c5", "Value")
    )
    nfd = vanilla_retrieval._validated_query(
        _query("AA\u030a", "Value")
    )

    assert upper.localisation_key != lower.localisation_key
    assert nfc.localisation_key != nfd.localisation_key
    assert nfc.localisation_key.encode() != nfd.localisation_key.encode()


def test_key_alias_risk_is_terminal_for_exact_key_and_text_fallback(
    tmp_path: Path,
) -> None:
    report, database = _build_memory(
        tmp_path,
        {
            "alias_l_english.yml": _localisation(
                "english",
                [
                    ("Alias.Key", "0", "Aliased English"),
                    ("alias.key", "0", "Aliased English"),
                ],
            )
        },
        {
            "alias_l_russian.yml": _localisation(
                "russian",
                [
                    ("Alias.Key", "0", "Одинаково"),
                    ("alias.key", "0", "Одинаково"),
                ],
            )
        },
    )

    batch = _retrieve(
        report,
        database,
        _query("Alias.Key", "Aliased English"),
        _query("absent.key", "Aliased English"),
    )

    assert [item.status for item in batch.results] == [
        "excluded_key_alias",
        "excluded_key_alias",
    ]
    assert all(item.candidates == () for item in batch.results)


def test_suffix_none_zero_and_leading_zero_are_distinct_in_retrieval(
    tmp_path: Path,
) -> None:
    entries = [
        ("suffix.none", None, "Same suffix text"),
        ("suffix.zero", "0", "Same suffix text"),
        ("suffix.leading", "007", "Same suffix text"),
    ]
    report, database = _build_memory(
        tmp_path,
        {"suffix_l_english.yml": _localisation("english", entries)},
        {
            "suffix_l_russian.yml": _localisation(
                "russian",
                    [
                        ("suffix.none", None, "Единый вариант"),
                        ("suffix.zero", "0", "Единый вариант"),
                        ("suffix.leading", "007", "Единый вариант"),
                ],
            )
        },
    )

    batch = _retrieve(
        report,
        database,
        _query("missing.none", "Same suffix text", suffix=None),
        _query("missing.zero", "Same suffix text", suffix="0"),
        _query("missing.leading", "Same suffix text", suffix="007"),
        _query("missing.other", "Same suffix text", suffix="1"),
    )

    assert [item.status for item in batch.results] == [
        "exact_text_consensus",
        "exact_text_consensus",
        "exact_text_consensus",
        "no_match",
    ]
    assert [item.examined_references for item in batch.results] == [1, 1, 1, 0]


def test_exact_key_changed_suffix_and_token_kind_order_are_conflicts(
    tmp_path: Path,
) -> None:
    value = "Value $MVP6B_ACTOR_20260731$ [MVP6B.GetSyntheticName]"
    report, database = _one_pair_memory(
        tmp_path,
        english_value=value,
        russian_value=(
            "Текст $MVP6B_ACTOR_20260731$ [MVP6B.GetSyntheticName]"
        ),
    )

    batch = _retrieve(
        report,
        database,
        _query("synthetic.entry", value, suffix="007"),
        _query(
            "synthetic.entry",
            "Value [Root.GetName] $ACTOR$",
        ),
        _query(
            "synthetic.entry",
            "Value £ACTOR£ [Root.GetName]",
        ),
    )

    assert all(
        item.status == "excluded_key_conflict" for item in batch.results
    )


def test_non_strict_and_quarantined_keys_never_fall_back(
    tmp_path: Path,
) -> None:
    report, database = _build_memory(
        tmp_path,
        {
            "unsafe_l_english.yml": _localisation(
                "english",
                [
                    ("duplicate.key", "0", "Unsafe shared"),
                    ("duplicate.key", "0", "Unsafe shared"),
                    ("missing.key", "0", "Unsafe shared"),
                    ("version.key", "0", "Unsafe shared"),
                    ("atom.key", "0", "Unsafe $ONE$"),
                    ("fallback.key", "0", "Unsafe shared"),
                ],
                extra_lines=(' malformed.key:0 unquoted',),
            )
        },
        {
            "unsafe_l_russian.yml": _localisation(
                "russian",
                [
                    ("duplicate.key", "0", "Небезопасно"),
                    ("version.key", "1", "Небезопасно"),
                    ("atom.key", "0", "Небезопасно $TWO$"),
                    ("fallback.key", "0", "Допустимый fallback"),
                    ("malformed.key", "0", "Карантин"),
                    ("russian.only", "0", "Только русский"),
                ],
            )
        },
    )
    queries = (
        _query("duplicate.key", "Unsafe shared"),
        _query("missing.key", "Unsafe shared"),
        _query("version.key", "Unsafe shared"),
        _query("atom.key", "Unsafe $ONE$"),
        _query("malformed.key", "Unsafe shared"),
        _query("russian.only", "Unsafe shared"),
    )

    batch = _retrieve(report, database, *queries)

    assert all(
        item.status == "excluded_quarantined_key"
        for item in batch.results
    )
    assert all(item.candidates == () for item in batch.results)


def test_model_safe_candidate_round_trips_current_entry_renderer(
    tmp_path: Path,
) -> None:
    english_value = (
        "  Lead $MVP6B_ACTOR_20260731$ "
        "[MVP6B.GetSyntheticName] §Hbold§!  "
    )
    russian_value = (
        "\tТекст $MVP6B_ACTOR_20260731$ "
        "[MVP6B.GetSyntheticName] §Hжирный§!\t"
    )
    report, database = _one_pair_memory(
        tmp_path,
        english_value=english_value,
        russian_value=russian_value,
    )
    source_bytes = _localisation(
        "english", [("synthetic.entry", "0", english_value)]
    )
    parsed = parse_localisation(source_bytes)
    entry = parsed.entries[0]

    candidate = _retrieve(
        report,
        database,
        _query("synthetic.entry", english_value),
    ).results[0].candidates[0]
    restored = entry.restore_translation(candidate.russian_model_text)
    rendered = parsed.render(
        {entry.line_index: restored}, russian_header=True
    )
    reparsed = parse_localisation(rendered)

    assert "__SMT_TOKEN_0000__" in candidate.russian_model_text
    assert not candidate.russian_model_text.startswith((" ", "\t"))
    assert not candidate.russian_model_text.endswith((" ", "\t"))
    assert all(
        token.original not in candidate.russian_model_text
        for token in entry.protected
    )
    assert tuple(
        token.original for token in reparsed.entries[0].protected
    ) == tuple(token.original for token in entry.protected)
    assert reparsed.entries[0].value.startswith("  Текст")
    assert reparsed.entries[0].value.endswith("§!  ")


def test_literal_reserved_renderer_placeholder_is_never_returned(
    tmp_path: Path,
) -> None:
    english_value = "Synthetic renderer-safe source"
    report, database = _one_pair_memory(
        tmp_path,
        english_value=english_value,
        russian_value="Literal __SMT_TOKEN_0000__ must stay unavailable",
    )

    exact, fallback = _retrieve(
        report,
        database,
        _query("synthetic.entry", english_value),
        _query("synthetic.absent", english_value),
    ).results

    assert exact.status == "excluded_key_conflict"
    assert fallback.status == "no_match"
    assert exact.candidates == ()
    assert fallback.candidates == ()


@pytest.mark.parametrize(
    "field",
    [
        "batch_queries",
        "examined_references_per_query",
        "returned_candidates",
        "materialized_index_units",
        "aggregate_stdout_bytes",
    ],
)
def test_bool_and_invalid_scalar_limits_are_rejected(
    tmp_path: Path, field: str
) -> None:
    report, database = _one_pair_memory(tmp_path)
    limits = replace(RetrievalLimits(), **{field: True})

    with pytest.raises(SafetyError, match=f"retrieval_{field}_invalid"):
        _retrieve(
            report,
            database,
            _query(
                "synthetic.entry",
                "MVP6B synthetic $MVP6B_ACTOR_20260731$ "
                "[MVP6B.GetSyntheticName]",
            ),
            limits=limits,
        )


@pytest.mark.parametrize(
    ("query", "error"),
    [
        (None, "retrieval_query_type_invalid"),
        (
            RetrievalQuery(
                relative_path=1,  # type: ignore[arg-type]
                localisation_key="synthetic.entry",
                version_suffix="0",
                english_human_value="Value",
                protected_tokens=(),
            ),
            "retrieval_relative_path_invalid",
        ),
        (
            RetrievalQuery(
                relative_path="localisation/value.yml",
                localisation_key=1,  # type: ignore[arg-type]
                version_suffix="0",
                english_human_value="Value",
                protected_tokens=(),
            ),
            "retrieval_key_invalid",
        ),
        (
            RetrievalQuery(
                relative_path="localisation/value.yml",
                localisation_key="synthetic.entry",
                version_suffix=0,  # type: ignore[arg-type]
                english_human_value="Value",
                protected_tokens=(),
            ),
            "retrieval_version_suffix_invalid",
        ),
        (
            RetrievalQuery(
                relative_path="localisation/value.yml",
                localisation_key="synthetic.entry",
                version_suffix="0",
                english_human_value=1,  # type: ignore[arg-type]
                protected_tokens=(),
            ),
            "retrieval_english_value_invalid",
        ),
        (
            RetrievalQuery(
                relative_path="localisation/value.yml",
                localisation_key="synthetic.entry",
                version_suffix="0",
                english_human_value="Value",
                protected_tokens=[],  # type: ignore[arg-type]
            ),
            "retrieval_tokens_type_invalid",
        ),
    ],
)
def test_invalid_typed_query_scalars_fail_closed(
    tmp_path: Path,
    query: RetrievalQuery | None,
    error: str,
) -> None:
    report, database = _one_pair_memory(tmp_path)

    with pytest.raises(SafetyError, match=error):
        retrieve_exact_context_v1(
            database,
            (query,),  # type: ignore[arg-type]
            **_pins(report),
        )


def test_returned_candidate_limit_one_is_enforced(
    tmp_path: Path,
) -> None:
    report, database = _one_pair_memory(tmp_path)
    query = _query(
        "synthetic.entry",
        "MVP6B synthetic $MVP6B_ACTOR_20260731$ "
        "[MVP6B.GetSyntheticName]",
    )

    result = _retrieve(
        report,
        database,
        query,
        limits=replace(RetrievalLimits(), returned_candidates=1),
    ).results[0]

    assert result.status == "exact_key_context"
    assert len(result.candidates) == 1


@pytest.mark.parametrize("value", [0, 4, -1, 1.0, "1"])
def test_returned_candidate_ceiling_rejects_invalid_scalars(
    tmp_path: Path, value: object
) -> None:
    report, database = _one_pair_memory(tmp_path)
    limits = replace(
        RetrievalLimits(),
        returned_candidates=value,  # type: ignore[arg-type]
    )

    with pytest.raises(
        SafetyError, match="retrieval_returned_candidates_invalid"
    ):
        _retrieve(report, database, limits=limits)


def test_batch_examined_and_index_overflow_are_per_occurrence_statuses(
    tmp_path: Path,
) -> None:
    report, database = _build_memory(
        tmp_path,
        {
            "limits_l_english.yml": _localisation(
                "english",
                [
                    ("limit.one", "0", "Repeated English"),
                    ("limit.two", "0", "Repeated English"),
                ],
            )
        },
        {
            "limits_l_russian.yml": _localisation(
                "russian",
                [
                    ("limit.one", "0", "Одинаково"),
                    ("limit.two", "0", "Одинаково"),
                ],
            )
        },
    )
    exact = _query("limit.one", "Repeated English")
    fallback = _query("limit.absent", "Repeated English")

    batch_limited = _retrieve(
        report,
        database,
        exact,
        fallback,
        limits=replace(RetrievalLimits(), batch_queries=1),
    )
    examined_limited = _retrieve(
        report,
        database,
        fallback,
        limits=replace(
            RetrievalLimits(), examined_references_per_query=1
        ),
    )
    index_limited = _retrieve(
        report,
        database,
        exact,
        limits=replace(RetrievalLimits(), materialized_index_units=1),
    )

    assert [item.status for item in batch_limited.results] == [
        "exact_key_context",
        "excluded_candidate_overflow",
    ]
    assert examined_limited.results[0].status == (
        "excluded_candidate_overflow"
    )
    assert index_limited.results[0].status == "excluded_candidate_overflow"


@pytest.mark.parametrize(
    ("pin", "error"),
    [
        ("database_sha256", "memory_database_sha256_pin_mismatch"),
        ("logical_digest", "memory_logical_digest_pin_mismatch"),
        ("game_version", "memory_game_version_pin_mismatch"),
    ],
)
def test_exact_memory_pins_are_mandatory(
    tmp_path: Path, pin: str, error: str
) -> None:
    report, database = _one_pair_memory(tmp_path)
    pins = _pins(report)
    pins[pin] = (
        "f" * 64 if pin != "game_version" else "Synthetic other version"
    )

    with pytest.raises(SafetyError, match=error):
        retrieve_exact_context_v1(
            database,
            (
                _query(
                    "synthetic.entry",
                    "MVP6B synthetic $MVP6B_ACTOR_20260731$ "
                    "[MVP6B.GetSyntheticName]",
                ),
            ),
            **pins,
        )


@pytest.mark.parametrize(
    ("pragma", "error"),
    [
        ("PRAGMA user_version = 2", "database_schema_version_unknown"),
        (
            "PRAGMA application_id = 1397576758",
            "database_application_id_unknown",
        ),
    ],
)
def test_previous_schema_and_application_id_are_rejected(
    tmp_path: Path, pragma: str, error: str
) -> None:
    report, database = _one_pair_memory(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(pragma)
    pins = _pins(report)
    pins["database_sha256"] = _sha256(database)

    with pytest.raises(SafetyError, match=error):
        retrieve_exact_context_v1(database, (), **pins)


def test_semantic_database_tampering_is_rejected(tmp_path: Path) -> None:
    report, database = _one_pair_memory(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE occurrences SET key_alias_risk = 1"
        )
    pins = _pins(report)
    pins["database_sha256"] = _sha256(database)

    with pytest.raises(
        SafetyError, match="occurrence_alignment_semantics_invalid"
    ):
        retrieve_exact_context_v1(database, (), **pins)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_database_symlink_hardlink_and_fifo_are_rejected(
    tmp_path: Path, kind: str
) -> None:
    report, database = _one_pair_memory(tmp_path)
    unsafe = tmp_path / f"unsafe-{kind}"
    unsafe.mkdir(mode=0o700)
    copied_report = unsafe / REPORT_NAME
    copied_report.write_bytes((database.parent / REPORT_NAME).read_bytes())
    copied_report.chmod(0o600)
    target = unsafe / DATABASE_NAME
    if kind == "symlink":
        target.symlink_to(database)
    elif kind == "hardlink":
        os.link(database, target)
    else:
        os.mkfifo(target, 0o600)

    with pytest.raises(SafetyError):
        retrieve_exact_context_v1(target, (), **_pins(report))


def test_sidecar_and_in_session_database_replacement_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report, database = _one_pair_memory(tmp_path)
    sidecar = Path(os.fspath(database) + "-wal")
    sidecar.write_bytes(b"synthetic")
    with pytest.raises(
        SafetyError,
        match="database_(parent_inventory_invalid|sidecar_present)",
    ):
        retrieve_exact_context_v1(database, (), **_pins(report))
    sidecar.unlink()

    actual_extract = vanilla_retrieval._extract_batch_index

    def replace_database(
        connection: sqlite3.Connection,
        queries: tuple[RetrievalQuery, ...],
        limits: RetrievalLimits,
    ):
        result = actual_extract(connection, queries, limits)
        replacement = database.parent / "replacement.sqlite3"
        replacement.write_bytes(database.read_bytes())
        replacement.chmod(0o600)
        os.replace(replacement, database)
        return result

    monkeypatch.setattr(
        vanilla_retrieval, "_extract_batch_index", replace_database
    )
    with pytest.raises(
        SafetyError, match="database_changed_during_inspection"
    ):
        retrieve_exact_context_v1(database, (), **_pins(report))


def test_in_session_report_replacement_is_rejected_by_typed_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report, database = _one_pair_memory(tmp_path)
    report_path = database.parent / REPORT_NAME
    actual_extract = vanilla_retrieval._extract_batch_index

    def replace_report(
        connection: sqlite3.Connection,
        queries: tuple[RetrievalQuery, ...],
        limits: RetrievalLimits,
    ):
        result = actual_extract(connection, queries, limits)
        replacement = database.parent / "replacement-report.json"
        replacement.write_bytes(report_path.read_bytes())
        replacement.chmod(0o600)
        os.replace(replacement, report_path)
        return result

    monkeypatch.setattr(
        vanilla_retrieval, "_extract_batch_index", replace_report
    )

    with pytest.raises(
        SafetyError, match="memory_changed_during_retrieval"
    ):
        retrieve_exact_context_v1(database, (), **_pins(report))


def test_validation_and_index_extraction_share_one_sqlite_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report, database = _one_pair_memory(tmp_path)
    actual_connect = sqlite3.connect
    database_opens = 0

    def counted_connect(*args: object, **kwargs: object):
        nonlocal database_opens
        if args and str(database) in str(args[0]):
            database_opens += 1
        return actual_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", counted_connect)
    batch = _retrieve(
        report,
        database,
        _query(
            "synthetic.entry",
            "MVP6B synthetic $MVP6B_ACTOR_20260731$ "
            "[MVP6B.GetSyntheticName]",
        ),
    )

    assert batch.results[0].status == "exact_key_context"
    assert database_opens == 1


def test_source_generation_gets_one_full_retry_then_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report, database = _one_pair_memory(tmp_path)
    source = _source_mod(
        tmp_path,
        {
            "localisation/english/context/scene_l_english.yml": (
                _localisation(
                    "english",
                    [
                        (
                            "synthetic.entry",
                            "0",
                            "MVP6B synthetic $MVP6B_ACTOR_20260731$ "
                            "[MVP6B.GetSyntheticName]",
                        )
                    ],
                )
            )
        },
    )
    actual_verify = vanilla_retrieval._verify_source_snapshot
    calls = 0

    def drift_once(snapshot: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise vanilla_retrieval._SourceGenerationChanged()
        actual_verify(snapshot)  # type: ignore[arg-type]

    monkeypatch.setattr(
        vanilla_retrieval, "_verify_source_snapshot", drift_once
    )
    coverage = _coverage(report, database, source)

    assert coverage["count_algebra"] == "PASS"
    assert coverage["exact_key_context"] == 1
    assert calls == 3


def test_coverage_excludes_unsupported_replace_layout_like_legacy_engine(
    tmp_path: Path,
) -> None:
    report, database = _one_pair_memory(
        tmp_path,
        english_value="Unsupported replace source",
        russian_value="Unsupported replace reference",
    )
    source = _source_mod(
        tmp_path,
        {
            "localisation/replace/context/scene_l_english.yml": (
                _localisation(
                    "english",
                    [
                        (
                            "synthetic.entry",
                            "0",
                            "Unsupported replace source",
                        )
                    ],
                )
            )
        },
    )

    legacy = engine.inspect_mod(source)
    coverage = _coverage(report, database, source)

    assert legacy["counts"]["occurrences"] == 0
    assert coverage["queries_total"] == 0
    assert coverage["queries_with_reference"] == 0
    assert coverage["count_algebra"] == "PASS"


def test_legacy_localisation_path_matches_memory_path_family() -> None:
    reference = vanilla_retrieval._Reference(
        pair_id="synthetic-pair",
        english_occurrence_id="synthetic-english",
        russian_occurrence_id="synthetic-russian",
        key="synthetic.entry",
        english_path="context/scene_l_english.yml",
        suffix="0",
        english_value="Synthetic path family",
        russian_value="Synthetic reference",
        english_tokens=(),
        russian_tokens=(),
        alias_risk=False,
        global_text_ambiguous=False,
    )

    assert vanilla_retrieval._path_family_matches(
        "localisation/context/scene_l_english.yml", reference
    )


def test_repeated_source_generation_drift_fails_content_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report, database = _one_pair_memory(tmp_path)
    source = _source_mod(
        tmp_path,
        {
            "localisation/english/context/scene_l_english.yml": (
                _localisation(
                    "english",
                    [
                        (
                            "synthetic.entry",
                            "0",
                            "MVP6B synthetic $MVP6B_ACTOR_20260731$ "
                            "[MVP6B.GetSyntheticName]",
                        )
                    ],
                )
            )
        },
    )

    def always_drift(_snapshot: object) -> None:
        raise vanilla_retrieval._SourceGenerationChanged()

    monkeypatch.setattr(
        vanilla_retrieval, "_verify_source_snapshot", always_drift
    )
    with pytest.raises(
        SafetyError, match="source_generation_changed_after_retry"
    ) as raised:
        _coverage(report, database, source)

    assert "synthetic.entry" not in str(raised.value)
    assert "scene_l_english.yml" not in str(raised.value)


def test_aggregate_coverage_is_content_free_and_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    markers = (
        "SQL_SELECT_PRIVATE_SENTINEL_20260731",
        "JSON_PRIVATE_SENTINEL_20260731",
        "MARKDOWN_PRIVATE_SENTINEL_20260731",
        "HTML_PRIVATE_SENTINEL_20260731",
        "PROMPT_INJECTION_PRIVATE_SENTINEL_20260731",
    )
    marker = " ".join(markers)
    report, database = _one_pair_memory(
        tmp_path,
        english_value=f"{marker} $ACTOR$",
        russian_value=f"РУССКИЙ_{marker} $ACTOR$",
    )
    source = _source_mod(
        tmp_path,
        {
            "localisation/english/context/scene_l_english.yml": (
                _localisation(
                    "english",
                    [("synthetic.entry", "0", f"{marker} $ACTOR$")],
                )
            )
        },
    )
    source_before = tuple(
        (path.relative_to(source).as_posix(), _sha256(path))
        for path in sorted(source.rglob("*"))
        if path.is_file()
    )
    memory_before = tuple(
        (path.name, _sha256(path), path.stat().st_mode)
        for path in sorted(database.parent.iterdir())
    )

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network or Ollama client constructed")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(engine, "OllamaClient", forbidden)
    coverage = _coverage(report, database, source)
    rendered = json.dumps(coverage, ensure_ascii=False, sort_keys=True)
    source_after = tuple(
        (path.relative_to(source).as_posix(), _sha256(path))
        for path in sorted(source.rglob("*"))
        if path.is_file()
    )
    memory_after = tuple(
        (path.name, _sha256(path), path.stat().st_mode)
        for path in sorted(database.parent.iterdir())
    )

    assert coverage["retrieval_schema"] == 1
    assert coverage["policy"] == "exact_context_v1"
    assert coverage["queries_total"] == 1
    assert coverage["exact_key_context"] == 1
    assert sum(coverage[name] for name in vanilla_retrieval.TERMINAL_STATUSES) == 1
    assert coverage["queries_with_reference"] == 1
    assert coverage["reference_candidates"] == 1
    assert coverage["source_mutations"] == 0
    assert coverage["memory_mutations"] == 0
    assert coverage["ollama_calls"] == 0
    assert coverage["private_text_output"] == 0
    assert all(item not in rendered for item in markers)
    assert "synthetic.entry" not in rendered
    assert "scene_l_english.yml" not in rendered
    assert str(source) not in rendered
    assert str(database) not in rendered
    assert source_after == source_before
    assert memory_after == memory_before
    for suffix in ("-journal", "-wal", "-shm"):
        assert not Path(os.fspath(database) + suffix).exists()
    assert set(path.name for path in database.parent.iterdir()) == {
        DATABASE_NAME,
        REPORT_NAME,
    }


def test_cli_emits_only_aggregate_allowed_fields(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    marker = "PROMPT_HTML_SQL_PRIVATE_SENTINEL_20260731"
    report, database = _one_pair_memory(
        tmp_path,
        english_value=marker,
        russian_value=f"REFERENCE_{marker}",
    )
    source = _source_mod(
        tmp_path,
        {
            "localisation/english/context/scene_l_english.yml": (
                _localisation(
                    "english",
                    [
                        (
                            "synthetic.entry",
                            "0",
                            marker,
                        )
                    ],
                )
            )
        },
    )
    pins = _pins(report)

    status = main(
        [
            "inspect-vanilla-context-coverage",
            "--source-mod",
            str(source),
            "--database",
            str(database),
            "--database-sha256",
            pins["database_sha256"],
            "--logical-digest",
            pins["logical_digest"],
            "--game-version",
            pins["game_version"],
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert status == 0
    assert captured.err == ""
    assert set(payload) == {
        "retrieval_schema",
        "policy",
        "memory_schema",
        "memory_game_version",
        "database_sha256",
        "logical_digest",
        "source_localisation_sha256",
        "queries_total",
        *vanilla_retrieval.TERMINAL_STATUSES,
        "queries_with_reference",
        "reference_candidates",
        "count_algebra",
        "source_mutations",
        "memory_mutations",
        "ollama_calls",
        "private_inputs_read",
        "private_text_output",
    }
    assert str(source) not in captured.out
    assert str(database) not in captured.out
    assert "synthetic.entry" not in captured.out
    assert marker not in captured.out
    assert marker not in captured.err


def test_noncontext_prompt_workspace_and_report_contracts_remain_stable(
    tmp_path: Path,
) -> None:
    source = _source_mod(
        tmp_path,
        {
            "localisation/english/demo_l_english.yml": _localisation(
                "english", [("legacy.entry", "0", "Legacy")]
            )
        },
    )

    inspected = engine.inspect_mod(source)
    dry_run = engine.translate_mod(
        source, tmp_path / "unused", "synthetic:1", dry_run=True
    )

    assert (
        engine.PARSER_ORDER_VERSION
        == "mvp7a-leading-header-parser-order-v2"
    )
    assert workspace.SCHEMA_VERSION == 2
    assert ollama.translation_prompt_profile_hash() == (
        "3e991aa062c660ad2286befc47fb80d571ec6de9bde0ef52512ff9cadc3ee6da"
    )
    assert inspected["schema_version"] == 1
    assert dry_run["schema_version"] == 2
    assert "memory" not in inspected
    assert "memory" not in dry_run
