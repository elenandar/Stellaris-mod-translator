"""Read-only exact contextual retrieval from a pinned vanilla memory."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
from typing import Literal

from .engine import SafetyError, _unsupported_replace_layer
from .parser import (
    Entry,
    ParseError,
    ParseResourceLimit,
    ParsedFile,
    ProtectedToken,
    parse_localisation,
)
from .vanilla_memory import (
    DATABASE_NAME,
    REPORT_NAME,
    SCHEMA_VERSION as MEMORY_SCHEMA_VERSION,
    _DatabaseIdentity,
    _build_report,
    _entry_version_suffix,
    _hash_stable_private_file,
    _path_family,
    _protected_tokens,
    _read_validated_database_session,
    _require_database_envelope,
    _require_sidecars_absent,
    _token_kind,
    _validate_private_output_directory,
    _validated_game_version,
)


RETRIEVAL_SCHEMA_VERSION = 1
POLICY = "exact_context_v1"
REFERENCE_STATUS = "REFERENCE_ONLY"
MAX_BATCH_QUERIES = 100_000
MAX_EXAMINED_REFERENCES_PER_QUERY = 256
MAX_RETURNED_CANDIDATES = 3
MAX_MATERIALIZED_INDEX_UNITS = 100_000
MAX_AGGREGATE_STDOUT_BYTES = 8 * 1024
MAX_SOURCE_MANIFEST_ENTRIES = 8_192
MAX_SOURCE_DIRECTORIES = 4_096
MAX_SOURCE_FILES = 4_096
MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_SOURCE_FILE_BYTES = 128 * 1024 * 1024
MAX_SOURCE_YML_FILES = 2_048
MAX_SOURCE_LINES = 1_500_000
MAX_SOURCE_OCCURRENCES = 250_000
MAX_SOURCE_PROTECTED_TOKENS = 500_000
_HEX = frozenset("0123456789abcdef")
_TOKEN_KINDS = frozenset(
    {
        "escaped_quote",
        "escaped_backslash",
        "escaped_newline",
        "dollar_reference",
        "bracket_expression",
        "icon",
        "format_control",
    }
)
TERMINAL_STATUSES = (
    "exact_key_context",
    "exact_text_consensus",
    "excluded_key_conflict",
    "excluded_quarantined_key",
    "excluded_key_alias",
    "excluded_ambiguous_text",
    "excluded_candidate_overflow",
    "no_match",
)
TerminalStatus = Literal[
    "exact_key_context",
    "exact_text_consensus",
    "excluded_key_conflict",
    "excluded_quarantined_key",
    "excluded_key_alias",
    "excluded_ambiguous_text",
    "excluded_candidate_overflow",
    "no_match",
]


@dataclass(frozen=True)
class RetrievalLimits:
    """Closed, scalar-only resource ceilings for one retrieval batch."""

    batch_queries: int = MAX_BATCH_QUERIES
    examined_references_per_query: int = (
        MAX_EXAMINED_REFERENCES_PER_QUERY
    )
    returned_candidates: int = MAX_RETURNED_CANDIDATES
    materialized_index_units: int = MAX_MATERIALIZED_INDEX_UNITS
    aggregate_stdout_bytes: int = MAX_AGGREGATE_STDOUT_BYTES


@dataclass(frozen=True, order=True)
class QueryToken:
    kind: str
    exact: str


@dataclass(frozen=True)
class RetrievalQuery:
    relative_path: str
    localisation_key: str
    version_suffix: str | None
    english_human_value: str
    protected_tokens: tuple[QueryToken, ...]


@dataclass(frozen=True)
class RetrievalCandidate:
    """A process-local reference; its model text must never be serialized."""

    pair_id: str
    match_kind: Literal["exact_key", "exact_text"]
    path_family_match: bool
    global_text_ambiguous: bool
    reference_status: Literal["REFERENCE_ONLY"]
    editorially_approved: Literal[False]
    auto_applied: Literal[False]
    russian_model_text: str


@dataclass(frozen=True)
class RetrievalResult:
    status: TerminalStatus
    candidates: tuple[RetrievalCandidate, ...]
    examined_references: int


@dataclass(frozen=True)
class RetrievalBatch:
    results: tuple[RetrievalResult, ...]
    memory_schema: int
    memory_game_version: str
    database_sha256: str
    logical_digest: str
    database_identity: _DatabaseIdentity
    memory_identity: _MemoryTreeIdentity


@dataclass(frozen=True)
class _StatIdentity:
    device: int
    inode: int
    mode: int
    size: int
    modified_ns: int
    changed_ns: int
    link_count: int


@dataclass(frozen=True)
class _ManifestItem:
    relative_path: str
    kind: Literal["directory", "file"]
    byte_count: int | None
    content_sha256: str | None
    identity: _StatIdentity


@dataclass(frozen=True)
class _SourceSnapshot:
    source_root: Path
    source_root_identity: _StatIdentity
    localisation_root_identity: _StatIdentity | None
    manifest: tuple[_ManifestItem, ...]
    localisation_sha256: str
    queries: tuple[RetrievalQuery, ...]


@dataclass(frozen=True)
class _MemoryTreeIdentity:
    parent: _StatIdentity
    files: tuple[tuple[str, str, object], ...]


@dataclass(frozen=True)
class _KeyFact:
    quarantined: bool
    alias_risk: bool


@dataclass(frozen=True)
class _Reference:
    pair_id: str
    english_occurrence_id: str
    russian_occurrence_id: str
    key: str
    english_path: str
    suffix: str | None
    english_value: str
    russian_value: str
    english_tokens: tuple[QueryToken, ...]
    russian_tokens: tuple[QueryToken, ...]
    alias_risk: bool
    global_text_ambiguous: bool


@dataclass(frozen=True)
class _ReferenceSeed:
    pair_id: str
    english_occurrence_id: str
    russian_occurrence_id: str
    key: str
    english_path: str
    suffix: str | None
    english_value: str
    russian_value: str
    alias_risk: bool
    global_text_ambiguous: bool


@dataclass(frozen=True)
class _RetrievalIndex:
    key_facts: dict[str, _KeyFact]
    references_by_key: dict[str, tuple[_Reference, ...]]
    references_by_signature: dict[
        tuple[str, str | None, tuple[QueryToken, ...]],
        tuple[_Reference, ...],
    ]
    overflow_queries: frozenset[int]


class _SourceGenerationChanged(RuntimeError):
    pass


def retrieval_query_for_entry(
    relative_path: str, parsed: ParsedFile, entry: Entry
) -> RetrievalQuery:
    """Build the exact typed query used by the translation plan."""
    return RetrievalQuery(
        relative_path=_validated_relative_path(relative_path),
        localisation_key=entry.key,
        version_suffix=_entry_version_suffix(parsed, entry),
        english_human_value=entry.value,
        protected_tokens=tuple(
            QueryToken(
                kind=_token_kind(token.original),
                exact=token.original,
            )
            for token in entry.protected
        ),
    )


def retrieve_exact_context_v1(
    database: Path,
    queries: tuple[RetrievalQuery, ...],
    *,
    database_sha256: str,
    logical_digest: str,
    game_version: str,
    limits: RetrievalLimits = RetrievalLimits(),
) -> RetrievalBatch:
    """Validate, index, and retrieve a batch in one SQLite lifecycle."""
    validated_limits = _validated_limits(limits)
    validated_queries = tuple(_validated_query(item) for item in queries)
    database_pin = _validated_sha256_pin(
        database_sha256, "database_sha256_pin_invalid"
    )
    logical_pin = _validated_sha256_pin(
        logical_digest, "logical_digest_pin_invalid"
    )
    version_pin = _validated_game_version(game_version)
    database_path = database.absolute()
    memory_before = _memory_tree_identity(database_path)

    def reader(
        connection: sqlite3.Connection,
        validated: dict[str, object],
    ) -> _RetrievalIndex:
        _validate_memory_pins(
            validated,
            database_sha256=database_pin,
            logical_digest=logical_pin,
            game_version=version_pin,
        )
        _validate_private_output_directory(
            database_path.parent,
            _build_report(validated),
        )
        return _extract_batch_index(
            connection,
            validated_queries,
            validated_limits,
        )

    validated, index, database_identity = (
        _read_validated_database_session(database_path, reader)
    )
    memory_after = _memory_tree_identity(database_path)
    if memory_after != memory_before:
        raise SafetyError("memory_changed_during_retrieval")
    _verify_database_identity(database_path, database_identity)
    results = tuple(
        _retrieve_one(index, query, ordinal, validated_limits)
        for ordinal, query in enumerate(validated_queries)
    )
    hashes = validated["hashes"]
    assert isinstance(hashes, dict)
    return RetrievalBatch(
        results=results,
        memory_schema=int(validated["schema_version"]),
        memory_game_version=str(validated["game_version"]),
        database_sha256=str(hashes["database_sha256"]),
        logical_digest=str(hashes["logical_digest"]),
        database_identity=database_identity,
        memory_identity=memory_after,
    )


def verify_retrieval_batch_identity(
    database: Path, batch: RetrievalBatch
) -> None:
    """Recheck the exact private memory generation without exposing content."""
    if not isinstance(batch, RetrievalBatch):
        raise SafetyError("retrieval_batch_type_invalid")
    database_path = database.absolute()
    if _memory_tree_identity(database_path) != batch.memory_identity:
        raise SafetyError("memory_changed_after_retrieval")
    _verify_database_identity(database_path, batch.database_identity)


def inspect_vanilla_context_coverage(
    source_mod: Path,
    database: Path,
    database_sha256: str,
    logical_digest: str,
    game_version: str,
    *,
    limits: RetrievalLimits = RetrievalLimits(),
) -> dict[str, object]:
    """Return aggregate-only coverage for a read-only source and memory."""
    validated_limits = _validated_limits(limits)
    database_pin = _validated_sha256_pin(
        database_sha256, "database_sha256_pin_invalid"
    )
    logical_pin = _validated_sha256_pin(
        logical_digest, "logical_digest_pin_invalid"
    )
    version_pin = _validated_game_version(game_version)
    source = _validated_source_root(source_mod)
    database_path = database.absolute()

    for attempt in range(2):
        try:
            snapshot = _snapshot_source(source, materialize_queries=True)
            batch = retrieve_exact_context_v1(
                database_path,
                snapshot.queries,
                database_sha256=database_pin,
                logical_digest=logical_pin,
                game_version=version_pin,
                limits=validated_limits,
            )
            _verify_source_snapshot(snapshot)
            memory_after = _memory_tree_identity(database_path)
            if memory_after != batch.memory_identity:
                raise SafetyError("memory_changed_during_retrieval")
            _verify_database_identity(
                database_path, batch.database_identity
            )
            _verify_source_snapshot(snapshot)
            report = _aggregate_report(snapshot, batch)
            _validate_aggregate_stdout(report, validated_limits)
            return report
        except _SourceGenerationChanged:
            if attempt == 0:
                continue
            raise SafetyError(
                "source_generation_changed_after_retry"
            ) from None
    raise AssertionError("unreachable source generation state")


def _validate_memory_pins(
    validated: dict[str, object],
    *,
    database_sha256: str,
    logical_digest: str,
    game_version: str,
) -> None:
    if validated.get("schema_version") != MEMORY_SCHEMA_VERSION:
        raise SafetyError("memory_schema_pin_mismatch")
    if validated.get("game_version") != game_version:
        raise SafetyError("memory_game_version_pin_mismatch")
    hashes = validated.get("hashes")
    if not isinstance(hashes, dict):
        raise SafetyError("memory_hashes_invalid")
    if hashes.get("database_sha256") != database_sha256:
        raise SafetyError("memory_database_sha256_pin_mismatch")
    if hashes.get("logical_digest") != logical_digest:
        raise SafetyError("memory_logical_digest_pin_mismatch")


def _extract_batch_index(
    connection: sqlite3.Connection,
    queries: tuple[RetrievalQuery, ...],
    limits: RetrievalLimits,
) -> _RetrievalIndex:
    overflow_queries = set(range(limits.batch_queries, len(queries)))
    active = tuple(enumerate(queries[: limits.batch_queries]))
    key_queries: dict[str, set[int]] = defaultdict(set)
    coarse_queries: dict[tuple[str, str | None], set[int]] = defaultdict(set)
    for ordinal, query in active:
        key_queries[query.localisation_key].add(ordinal)
        coarse_queries[
            (query.english_human_value, query.version_suffix)
        ].add(ordinal)

    units = 0
    key_facts: dict[str, _KeyFact] = {}

    def reserve(indices: set[int]) -> bool:
        nonlocal units
        if units >= limits.materialized_index_units:
            overflow_queries.update(indices)
            return False
        units += 1
        return True

    for row in connection.execute(
        """
        SELECT localisation_key, alignment_state, key_alias_risk
        FROM occurrences
        WHERE language IN (?, ?)
        ORDER BY language, sequence
        """,
        ("english", "russian"),
    ):
        key = str(row[0])
        indices = key_queries.get(key)
        if not indices:
            continue
        previous = key_facts.get(key)
        if previous is None and not reserve(indices):
            continue
        key_facts[key] = _KeyFact(
            quarantined=(
                (previous.quarantined if previous else False)
                or row[1] != "strict_reference"
            ),
            alias_risk=(
                (previous.alias_risk if previous else False)
                or row[2] == 1
            ),
        )

    for sql in (
        (
            """
            SELECT key_hint FROM quarantine_records
            WHERE language IN (?, ?) AND key_hint IS NOT NULL
            ORDER BY language, sequence
            """
        ),
        (
            """
            SELECT key_hint FROM quarantined_key_occupancy
            WHERE language IN (?, ?)
            ORDER BY language, relative_path, key_hint
            """
        ),
    ):
        for row in connection.execute(sql, ("english", "russian")):
            key = str(row[0])
            indices = key_queries.get(key)
            if not indices:
                continue
            previous = key_facts.get(key)
            if previous is None and not reserve(indices):
                continue
            key_facts[key] = _KeyFact(
                quarantined=True,
                alias_risk=previous.alias_risk if previous else False,
            )

    seeds: dict[str, _ReferenceSeed] = {}
    seed_query_indices: dict[str, set[int]] = {}
    for row in connection.execute(
        """
        SELECT rp.pair_id, rp.english_occurrence_id,
               rp.russian_occurrence_id, eo.localisation_key,
               eo.relative_path, eo.version_suffix, eo.human_value,
               ro.human_value, eo.key_alias_risk,
               rp.global_text_ambiguous
        FROM reference_pairs AS rp
        JOIN occurrences AS eo
          ON eo.occurrence_id = rp.english_occurrence_id
        JOIN occurrences AS ro
          ON ro.occurrence_id = rp.russian_occurrence_id
        WHERE rp.reference_status = ?
          AND rp.editorially_approved = ?
          AND eo.reference_status = ?
          AND eo.editorially_approved = ?
          AND ro.reference_status = ?
          AND ro.editorially_approved = ?
          AND eo.alignment_state = ?
          AND ro.alignment_state = ?
        ORDER BY rp.pair_id
        """,
        (
            REFERENCE_STATUS,
            0,
            REFERENCE_STATUS,
            0,
            REFERENCE_STATUS,
            0,
            "strict_reference",
            "strict_reference",
        ),
    ):
        key = str(row[3])
        coarse = (str(row[6]), row[5])
        indices = set(key_queries.get(key, ()))
        indices.update(coarse_queries.get(coarse, ()))
        if not indices:
            continue
        if not reserve(indices):
            continue
        seed = _ReferenceSeed(
            pair_id=str(row[0]),
            english_occurrence_id=str(row[1]),
            russian_occurrence_id=str(row[2]),
            key=key,
            english_path=str(row[4]),
            suffix=row[5],
            english_value=str(row[6]),
            russian_value=str(row[7]),
            alias_risk=row[8] == 1,
            global_text_ambiguous=row[9] == 1,
        )
        seeds[seed.pair_id] = seed
        seed_query_indices[seed.pair_id] = indices

    tokens: dict[tuple[str, int], list[QueryToken]] = defaultdict(list)
    overflow_pairs: set[str] = set()
    for row in connection.execute(
        """
        SELECT pair_id, side, token_ordinal, token_kind, exact_token
        FROM (
            SELECT rp.pair_id AS pair_id, 0 AS side,
                   pt.token_ordinal AS token_ordinal,
                   pt.token_kind AS token_kind,
                   pt.exact_token AS exact_token
            FROM reference_pairs AS rp
            JOIN protected_tokens AS pt
              ON pt.occurrence_id = rp.english_occurrence_id
            UNION ALL
            SELECT rp.pair_id AS pair_id, 1 AS side,
                   pt.token_ordinal AS token_ordinal,
                   pt.token_kind AS token_kind,
                   pt.exact_token AS exact_token
            FROM reference_pairs AS rp
            JOIN protected_tokens AS pt
              ON pt.occurrence_id = rp.russian_occurrence_id
        )
        ORDER BY pair_id, side, token_ordinal
        """
    ):
        pair_id = str(row[0])
        if pair_id not in seeds or pair_id in overflow_pairs:
            continue
        if not reserve(seed_query_indices[pair_id]):
            overflow_pairs.add(pair_id)
            continue
        tokens[(pair_id, int(row[1]))].append(
            QueryToken(kind=str(row[3]), exact=str(row[4]))
        )

    references: list[_Reference] = []
    for pair_id in sorted(seeds):
        if pair_id in overflow_pairs:
            continue
        seed = seeds[pair_id]
        english_tokens = tuple(tokens.get((pair_id, 0), ()))
        russian_tokens = tuple(tokens.get((pair_id, 1), ()))
        if english_tokens != russian_tokens:
            raise SafetyError("strict_reference_token_mismatch")
        references.append(
            _Reference(
                pair_id=seed.pair_id,
                english_occurrence_id=seed.english_occurrence_id,
                russian_occurrence_id=seed.russian_occurrence_id,
                key=seed.key,
                english_path=seed.english_path,
                suffix=seed.suffix,
                english_value=seed.english_value,
                russian_value=seed.russian_value,
                english_tokens=english_tokens,
                russian_tokens=russian_tokens,
                alias_risk=seed.alias_risk,
                global_text_ambiguous=seed.global_text_ambiguous,
            )
        )

    by_key: dict[str, list[_Reference]] = defaultdict(list)
    by_signature: dict[
        tuple[str, str | None, tuple[QueryToken, ...]],
        list[_Reference],
    ] = defaultdict(list)
    for reference in references:
        by_key[reference.key].append(reference)
        by_signature[
            (
                reference.english_value,
                reference.suffix,
                reference.english_tokens,
            )
        ].append(reference)
    return _RetrievalIndex(
        key_facts=key_facts,
        references_by_key={
            key: tuple(sorted(value, key=lambda item: item.pair_id))
            for key, value in by_key.items()
        },
        references_by_signature={
            key: tuple(sorted(value, key=lambda item: item.pair_id))
            for key, value in by_signature.items()
        },
        overflow_queries=frozenset(overflow_queries),
    )


def _retrieve_one(
    index: _RetrievalIndex,
    query: RetrievalQuery,
    ordinal: int,
    limits: RetrievalLimits,
) -> RetrievalResult:
    if ordinal in index.overflow_queries:
        return _terminal("excluded_candidate_overflow")
    key_fact = index.key_facts.get(query.localisation_key)
    if key_fact is not None:
        if key_fact.quarantined:
            return _terminal("excluded_quarantined_key")
        if key_fact.alias_risk:
            return _terminal("excluded_key_alias")
        references = index.references_by_key.get(
            query.localisation_key, ()
        )
        if len(references) > limits.examined_references_per_query:
            return _terminal(
                "excluded_candidate_overflow",
                examined=limits.examined_references_per_query,
            )
        exact = tuple(
            item
            for item in references
            if item.english_value == query.english_human_value
            and item.suffix == query.version_suffix
            and item.english_tokens == query.protected_tokens
        )
        if not exact:
            return _terminal(
                "excluded_key_conflict", examined=len(references)
            )
        compatible = tuple(
            candidate
            for item in _ranked_references(
                query, exact, exact_key=True
            )
            if (
                candidate := _compatible_candidate(
                    query, item, match_kind="exact_key"
                )
            )
        )
        if not compatible:
            return _terminal(
                "excluded_key_conflict", examined=len(references)
            )
        candidates = (compatible[0],)
        if len(candidates) > limits.returned_candidates:
            return _terminal(
                "excluded_candidate_overflow", examined=len(references)
            )
        return RetrievalResult(
            status="exact_key_context",
            candidates=candidates,
            examined_references=len(references),
        )

    signature = (
        query.english_human_value,
        query.version_suffix,
        query.protected_tokens,
    )
    references = index.references_by_signature.get(signature, ())
    if not references:
        return _terminal("no_match")
    if len(references) > limits.examined_references_per_query:
        return _terminal(
            "excluded_candidate_overflow",
            examined=limits.examined_references_per_query,
        )
    if any(item.alias_risk for item in references):
        return _terminal(
            "excluded_key_alias", examined=len(references)
        )
    if any(item.global_text_ambiguous for item in references):
        return _terminal(
            "excluded_ambiguous_text", examined=len(references)
        )
    russian_values = {
        item.russian_value.encode("utf-8") for item in references
    }
    if len(russian_values) != 1:
        return _terminal(
            "excluded_ambiguous_text", examined=len(references)
        )
    ranked = _ranked_references(query, references, exact_key=False)
    candidate = _compatible_candidate(
        query, ranked[0], match_kind="exact_text"
    )
    if candidate is None:
        return _terminal("no_match", examined=len(references))
    candidates = (candidate,)
    if len(candidates) > limits.returned_candidates:
        return _terminal(
            "excluded_candidate_overflow", examined=len(references)
        )
    return RetrievalResult(
        status="exact_text_consensus",
        candidates=candidates,
        examined_references=len(references),
    )


def _terminal(
    status: TerminalStatus, *, examined: int = 0
) -> RetrievalResult:
    return RetrievalResult(
        status=status,
        candidates=(),
        examined_references=examined,
    )


def _ranked_references(
    query: RetrievalQuery,
    references: tuple[_Reference, ...],
    *,
    exact_key: bool,
) -> tuple[_Reference, ...]:
    return tuple(
        sorted(
            references,
            key=lambda item: (
                0 if exact_key else 2,
                0 if _path_family_matches(query.relative_path, item) else 1,
                item.pair_id,
            ),
        )
    )


def _compatible_candidate(
    query: RetrievalQuery,
    reference: _Reference,
    *,
    match_kind: Literal["exact_key", "exact_text"],
) -> RetrievalCandidate | None:
    model_text = _model_safe_russian_text(
        reference.russian_value,
        reference.russian_tokens,
    )
    try:
        _query_entry(query).restore_translation(model_text)
    except ValueError:
        return None
    return RetrievalCandidate(
        pair_id=reference.pair_id,
        match_kind=match_kind,
        path_family_match=_path_family_matches(
            query.relative_path, reference
        ),
        global_text_ambiguous=reference.global_text_ambiguous,
        reference_status=REFERENCE_STATUS,
        editorially_approved=False,
        auto_applied=False,
        russian_model_text=model_text,
    )


def _query_entry(query: RetrievalQuery) -> Entry:
    whitespace = re.fullmatch(
        r"([ \t]*)(.*?)([ \t]*)", query.english_human_value
    )
    if whitespace is None:
        raise SafetyError("retrieval_query_whitespace_invalid")
    return Entry(
        line_index=0,
        key=query.localisation_key,
        value_start=0,
        value_end=0,
        value=query.english_human_value,
        leading_whitespace=whitespace.group(1),
        trailing_whitespace=whitespace.group(3),
        protected=tuple(
            ProtectedToken(
                placeholder=f"__SMT_TOKEN_{ordinal:04d}__",
                original=token.exact,
                is_atom=token.kind
                not in {
                    "escaped_quote",
                    "escaped_backslash",
                    "escaped_newline",
                },
            )
            for ordinal, token in enumerate(query.protected_tokens)
        ),
    )


def _path_family_matches(
    query_path: str, reference: _Reference
) -> bool:
    path = PurePosixPath(query_path)
    parts = list(path.parts)
    if parts and parts[0] == "localisation":
        parts = parts[1:]
        if parts and parts[0] == "english":
            parts = parts[1:]
    query_relative = PurePosixPath(*parts).as_posix()
    return _path_family(query_relative, "english") == _path_family(
        reference.english_path, "english"
    )


def _model_safe_russian_text(
    value: str, tokens: tuple[QueryToken, ...]
) -> str:
    pieces: list[str] = []
    cursor = 0
    for ordinal, token in enumerate(tokens):
        position = value.find(token.exact, cursor)
        if position < 0:
            raise SafetyError("reference_token_position_invalid")
        pieces.append(value[cursor:position])
        pieces.append(f"__SMT_TOKEN_{ordinal:04d}__")
        cursor = position + len(token.exact)
    pieces.append(value[cursor:])
    rendered = "".join(pieces)
    for token in tokens:
        if token.exact in rendered:
            raise SafetyError("reference_token_redaction_incomplete")
    whitespace = re.fullmatch(r"([ \t]*)(.*?)([ \t]*)", rendered)
    if whitespace is None:
        raise SafetyError("reference_model_text_invalid")
    return whitespace.group(2)


def _validated_limits(value: RetrievalLimits) -> RetrievalLimits:
    if not isinstance(value, RetrievalLimits):
        raise SafetyError("retrieval_limits_type_invalid")
    ceilings = (
        ("batch_queries", value.batch_queries, MAX_BATCH_QUERIES),
        (
            "examined_references_per_query",
            value.examined_references_per_query,
            MAX_EXAMINED_REFERENCES_PER_QUERY,
        ),
        (
            "returned_candidates",
            value.returned_candidates,
            MAX_RETURNED_CANDIDATES,
        ),
        (
            "materialized_index_units",
            value.materialized_index_units,
            MAX_MATERIALIZED_INDEX_UNITS,
        ),
        (
            "aggregate_stdout_bytes",
            value.aggregate_stdout_bytes,
            MAX_AGGREGATE_STDOUT_BYTES,
        ),
    )
    for name, actual, maximum in ceilings:
        if type(actual) is not int or actual < 1 or actual > maximum:
            raise SafetyError(f"retrieval_{name}_invalid")
    return value


def _validated_query(query: RetrievalQuery) -> RetrievalQuery:
    if not isinstance(query, RetrievalQuery):
        raise SafetyError("retrieval_query_type_invalid")
    relative_path = _validated_relative_path(query.relative_path)
    key = _validated_text(query.localisation_key, "retrieval_key_invalid")
    suffix = query.version_suffix
    if suffix is not None and (
        not isinstance(suffix, str)
        or not suffix
        or not suffix.isascii()
        or not suffix.isdigit()
    ):
        raise SafetyError("retrieval_version_suffix_invalid")
    value = _validated_text(
        query.english_human_value,
        "retrieval_english_value_invalid",
        allow_empty=True,
    )
    if not isinstance(query.protected_tokens, tuple):
        raise SafetyError("retrieval_tokens_type_invalid")
    tokens: list[QueryToken] = []
    for token in query.protected_tokens:
        if (
            not isinstance(token, QueryToken)
            or token.kind not in _TOKEN_KINDS
        ):
            raise SafetyError("retrieval_token_invalid")
        exact = _validated_text(
            token.exact, "retrieval_token_invalid"
        )
        if _token_kind(exact) != token.kind:
            raise SafetyError("retrieval_token_invalid")
        tokens.append(QueryToken(kind=token.kind, exact=exact))
    try:
        parsed = _protected_tokens(value)
    except (ParseError, ParseResourceLimit) as exc:
        raise SafetyError("retrieval_query_tokens_invalid") from exc
    derived = tuple(
        QueryToken(kind=_token_kind(token.original), exact=token.original)
        for token in parsed
    )
    if tuple(tokens) != derived:
        raise SafetyError("retrieval_query_tokens_invalid")
    return RetrievalQuery(
        relative_path=relative_path,
        localisation_key=key,
        version_suffix=suffix,
        english_human_value=value,
        protected_tokens=tuple(tokens),
    )


def _validated_sha256_pin(value: object, error: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in _HEX for char in value)
    ):
        raise SafetyError(error)
    return value


def _validated_text(
    value: object, error: str, *, allow_empty: bool = False
) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise SafetyError(error)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SafetyError(error) from exc
    if any(
        ord(char) < 0x20
        or ord(char) == 0x7F
        or 0x80 <= ord(char) <= 0x9F
        or char in "\u2028\u2029\ufeff"
        for char in value
    ):
        raise SafetyError(error)
    return value


def _validated_relative_path(value: object) -> str:
    text = _validated_text(value, "retrieval_relative_path_invalid")
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or not path.parts
        or text == "."
        or ".." in path.parts
        or path.as_posix() != text
    ):
        raise SafetyError("retrieval_relative_path_invalid")
    return text


def _validated_source_root(path: Path) -> Path:
    lexical = path.absolute()
    try:
        value = lexical.lstat()
    except OSError as exc:
        raise SafetyError("source_mod_unavailable") from exc
    if stat.S_ISLNK(value.st_mode):
        raise SafetyError("source_mod_symlink")
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise SafetyError("source_mod_unavailable") from exc
    if not stat.S_ISDIR(value.st_mode) or not resolved.is_dir():
        raise SafetyError("source_mod_not_directory")
    return resolved


def _snapshot_source(
    source: Path, *, materialize_queries: bool
) -> _SourceSnapshot:
    source_identity = _stable_directory(source, "source_mod_unsafe")
    localisation = source / "localisation"
    try:
        localisation_value = localisation.lstat()
    except FileNotFoundError:
        return _SourceSnapshot(
            source_root=source,
            source_root_identity=source_identity,
            localisation_root_identity=None,
            manifest=(),
            localisation_sha256=_manifest_digest(()),
            queries=(),
        )
    except OSError as exc:
        raise SafetyError("localisation_inventory_failed") from exc
    if (
        stat.S_ISLNK(localisation_value.st_mode)
        or not stat.S_ISDIR(localisation_value.st_mode)
    ):
        raise SafetyError("unsafe_localisation_root")
    localisation_identity = _stable_directory(
        localisation, "unsafe_localisation_root"
    )

    manifest: list[_ManifestItem] = []
    queries: list[RetrievalQuery] = []
    pending = [localisation]
    seen_directories = {
        (localisation_identity.device, localisation_identity.inode)
    }
    directory_count = 0
    file_count = 0
    source_bytes = 0
    yml_count = 0
    line_count = 0
    occurrence_count = 0
    protected_count = 0

    while pending:
        current = pending.pop()
        _stable_directory(current, "localisation_directory_unsafe")
        try:
            with os.scandir(current) as scan:
                entries = sorted(tuple(scan), key=lambda item: item.name)
        except OSError as exc:
            raise SafetyError("localisation_inventory_failed") from exc
        for entry in entries:
            path = current / entry.name
            relative = path.relative_to(localisation)
            relative_text = _filesystem_relative_path(relative)
            try:
                value = path.lstat()
            except FileNotFoundError as exc:
                raise _SourceGenerationChanged() from exc
            except OSError as exc:
                raise SafetyError("localisation_inventory_failed") from exc
            if stat.S_ISLNK(value.st_mode):
                raise SafetyError("symlink_in_localisation")
            if len(manifest) >= MAX_SOURCE_MANIFEST_ENTRIES:
                raise SafetyError("source_manifest_limit_exceeded")
            if stat.S_ISDIR(value.st_mode):
                if directory_count >= MAX_SOURCE_DIRECTORIES:
                    raise SafetyError("source_directory_limit_exceeded")
                identity = _stable_directory(
                    path, "localisation_directory_unsafe"
                )
                physical = (identity.device, identity.inode)
                if physical in seen_directories:
                    raise SafetyError("source_directory_alias")
                seen_directories.add(physical)
                directory_count += 1
                manifest.append(
                    _ManifestItem(
                        relative_path=relative_text,
                        kind="directory",
                        byte_count=None,
                        content_sha256=None,
                        identity=identity,
                    )
                )
                pending.append(path)
                continue
            if not stat.S_ISREG(value.st_mode):
                raise SafetyError("unsafe_localisation_file")
            if file_count >= MAX_SOURCE_FILES:
                raise SafetyError("source_file_limit_exceeded")
            data, identity = _read_stable_source_file(
                path,
                aggregate_remaining=MAX_SOURCE_BYTES - source_bytes,
            )
            file_count += 1
            source_bytes += len(data)
            digest = hashlib.sha256(data).hexdigest()
            manifest.append(
                _ManifestItem(
                    relative_path=relative_text,
                    kind="file",
                    byte_count=len(data),
                    content_sha256=digest,
                    identity=identity,
                )
            )
            if not materialize_queries or path.suffix.lower() != ".yml":
                continue
            if yml_count >= MAX_SOURCE_YML_FILES:
                raise SafetyError("source_yml_file_limit_exceeded")
            yml_count += 1
            remaining_lines = MAX_SOURCE_LINES - line_count
            remaining_occurrences = (
                MAX_SOURCE_OCCURRENCES - occurrence_count
            )
            remaining_tokens = (
                MAX_SOURCE_PROTECTED_TOKENS - protected_count
            )
            try:
                parsed = parse_localisation(
                    data,
                    max_lines=remaining_lines,
                    max_entries=remaining_occurrences,
                    max_diagnostics=remaining_occurrences,
                    max_protected_tokens=remaining_tokens,
                )
            except ParseResourceLimit as exc:
                raise SafetyError(
                    "source_parser_resource_limit_exceeded"
                ) from exc
            except ParseError:
                continue
            line_count += len(parsed.lines)
            if not parsed.is_english:
                continue
            source_relative = Path("localisation") / relative
            if _unsupported_replace_layer(source_relative):
                continue
            for entry in parsed.entries:
                tokens = tuple(
                    QueryToken(
                        kind=_token_kind(token.original),
                        exact=token.original,
                    )
                    for token in entry.protected
                )
                occurrence_count += 1
                protected_count += len(tokens)
                queries.append(
                    RetrievalQuery(
                        relative_path=(
                            PurePosixPath("localisation") / relative_text
                        ).as_posix(),
                        localisation_key=entry.key,
                        version_suffix=_entry_version_suffix(parsed, entry),
                        english_human_value=entry.value,
                        protected_tokens=tokens,
                    )
                )

    manifest.sort(key=lambda item: (item.relative_path, item.kind))
    _stable_directory(localisation, "unsafe_localisation_root")
    _stable_directory(source, "source_mod_unsafe")
    return _SourceSnapshot(
        source_root=source,
        source_root_identity=source_identity,
        localisation_root_identity=localisation_identity,
        manifest=tuple(manifest),
        localisation_sha256=_manifest_digest(tuple(manifest)),
        queries=tuple(queries),
    )


def _verify_source_snapshot(expected: _SourceSnapshot) -> None:
    try:
        actual = _snapshot_source(
            expected.source_root, materialize_queries=False
        )
    except _SourceGenerationChanged:
        raise
    except SafetyError as exc:
        raise _SourceGenerationChanged() from exc
    expected_identity = (
        expected.source_root_identity,
        expected.localisation_root_identity,
        expected.manifest,
        expected.localisation_sha256,
    )
    actual_identity = (
        actual.source_root_identity,
        actual.localisation_root_identity,
        actual.manifest,
        actual.localisation_sha256,
    )
    if actual_identity != expected_identity:
        raise _SourceGenerationChanged()


def _stable_directory(path: Path, error: str) -> _StatIdentity:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        before = path.lstat()
        descriptor = os.open(path, flags)
    except FileNotFoundError as exc:
        raise _SourceGenerationChanged() from exc
    except OSError as exc:
        raise SafetyError(error) from exc
    try:
        opened = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after = path.lstat()
    except FileNotFoundError as exc:
        raise _SourceGenerationChanged() from exc
    except OSError as exc:
        raise SafetyError(error) from exc
    identities = tuple(_stat_identity(item) for item in (before, opened, after))
    if any(not stat.S_ISDIR(item.st_mode) for item in (before, opened, after)):
        raise SafetyError(error)
    if identities[0] != identities[1] or identities[1] != identities[2]:
        raise _SourceGenerationChanged()
    return identities[0]


def _read_stable_source_file(
    path: Path, *, aggregate_remaining: int
) -> tuple[bytes, _StatIdentity]:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        before_path = path.lstat()
        descriptor = os.open(path, flags)
    except FileNotFoundError as exc:
        raise _SourceGenerationChanged() from exc
    except OSError as exc:
        raise SafetyError("source_file_open_failed") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size < 0
            or before.st_size > MAX_SOURCE_FILE_BYTES
        ):
            raise SafetyError("unsafe_localisation_file")
        if before.st_size > aggregate_remaining:
            raise SafetyError("source_bytes_limit_exceeded")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise _SourceGenerationChanged()
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise _SourceGenerationChanged()
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after_path = path.lstat()
    except FileNotFoundError as exc:
        raise _SourceGenerationChanged() from exc
    except OSError as exc:
        raise SafetyError("source_file_state_unavailable") from exc
    identities = tuple(
        _stat_identity(item)
        for item in (before_path, before, after, after_path)
    )
    if any(item != identities[0] for item in identities[1:]):
        raise _SourceGenerationChanged()
    return b"".join(chunks), identities[0]


def _stat_identity(value: os.stat_result) -> _StatIdentity:
    return _StatIdentity(
        device=value.st_dev,
        inode=value.st_ino,
        mode=value.st_mode,
        size=value.st_size,
        modified_ns=value.st_mtime_ns,
        changed_ns=value.st_ctime_ns,
        link_count=value.st_nlink,
    )


def _filesystem_relative_path(path: Path) -> str:
    try:
        value = path.as_posix()
        value.encode("utf-8")
    except UnicodeError as exc:
        raise SafetyError("source_relative_path_invalid") from exc
    candidate = PurePosixPath(value)
    if (
        candidate.is_absolute()
        or not candidate.parts
        or ".." in candidate.parts
        or candidate.as_posix() != value
    ):
        raise SafetyError("source_relative_path_invalid")
    return value


def _manifest_digest(entries: tuple[_ManifestItem, ...]) -> str:
    digest = hashlib.sha256()
    domain = b"SMT_MOD_LOCALISATION_MANIFEST_V1"
    digest.update(len(domain).to_bytes(8, "big"))
    digest.update(domain)
    for item in entries:
        fields = (
            item.kind,
            item.relative_path,
            item.byte_count,
            item.content_sha256,
        )
        payload = json.dumps(
            fields,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _verify_database_identity(
    database: Path, expected: _DatabaseIdentity
) -> None:
    _require_database_envelope(database, require_complete_output=True)
    _require_sidecars_absent(database)
    sha256, _, identity = _hash_stable_private_file(
        database,
        max_bytes=2 * 1024 * 1024 * 1024,
        prefix_bytes=0,
    )
    actual = _DatabaseIdentity(stat=identity, sha256=sha256)
    if actual != expected:
        raise SafetyError("memory_changed_during_retrieval")


def _memory_tree_identity(database: Path) -> _MemoryTreeIdentity:
    _require_database_envelope(database, require_complete_output=True)
    parent_before = _stable_directory(
        database.parent, "memory_parent_unsafe"
    )
    files: list[tuple[str, str, object]] = []
    for name, maximum in (
        (REPORT_NAME, 4 * 1024 * 1024),
        (DATABASE_NAME, 2 * 1024 * 1024 * 1024),
    ):
        digest, _, identity = _hash_stable_private_file(
            database.parent / name,
            max_bytes=maximum,
            prefix_bytes=0,
        )
        files.append((name, digest, identity))
    parent_after = _stable_directory(
        database.parent, "memory_parent_unsafe"
    )
    if parent_after != parent_before:
        raise SafetyError("memory_changed_during_retrieval")
    return _MemoryTreeIdentity(
        parent=parent_after,
        files=tuple(files),
    )


def _aggregate_report(
    snapshot: _SourceSnapshot, batch: RetrievalBatch
) -> dict[str, object]:
    counts: Counter[str] = Counter(item.status for item in batch.results)
    if set(counts) - set(TERMINAL_STATUSES):
        raise AssertionError("unknown terminal retrieval status")
    queries_total = len(batch.results)
    if sum(counts.values()) != queries_total:
        raise SafetyError("retrieval_count_algebra_invalid")
    queries_with_reference = sum(
        bool(item.candidates) for item in batch.results
    )
    reference_candidates = sum(
        len(item.candidates) for item in batch.results
    )
    if queries_with_reference > queries_total:
        raise SafetyError("retrieval_count_algebra_invalid")
    return {
        "retrieval_schema": RETRIEVAL_SCHEMA_VERSION,
        "policy": POLICY,
        "memory_schema": batch.memory_schema,
        "memory_game_version": batch.memory_game_version,
        "database_sha256": batch.database_sha256,
        "logical_digest": batch.logical_digest,
        "source_localisation_sha256": snapshot.localisation_sha256,
        "queries_total": queries_total,
        **{status: counts[status] for status in TERMINAL_STATUSES},
        "queries_with_reference": queries_with_reference,
        "reference_candidates": reference_candidates,
        "count_algebra": "PASS",
        "source_mutations": 0,
        "memory_mutations": 0,
        "ollama_calls": 0,
        "private_inputs_read": "BOUNDED_EXACT_MEMORY_AND_SOURCE_MOD",
        "private_text_output": 0,
    }


def _validate_aggregate_stdout(
    report: dict[str, object], limits: RetrievalLimits
) -> None:
    rendered = (
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    if len(rendered) > limits.aggregate_stdout_bytes:
        raise SafetyError("aggregate_stdout_limit_exceeded")
