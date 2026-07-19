#!/usr/bin/env python3
"""Offline synthetic conformance gate for the M1B benchmark contract.

The validator consumes only an explicitly supplied JSON file.  It performs no
provider, network, environment, home-directory, model-store, corpus, game, or
launcher discovery.  Its public result is deliberately limited to controlled
codes and aggregate counts.

This is Python 3.9 standard-library research tooling.  It is not an Ollama
client, a benchmark runner, a translator, or an M1B feasibility verdict.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple


DOCUMENT_SCHEMA = "m1b-synthetic-contract-v2"
FIXTURE_SCHEMA = "m1b-synthetic-contract-cases-v2"
MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_JSON_INTEGER = (1 << 63) - 1
MIN_JSON_INTEGER = -(1 << 63)

PROTOCOL_VERSION = "m1b-benchmark-contract-v1"
OUTPUT_SCHEMA_VERSION = "m1b-synthetic-output-v2"
PROMPT_VERSION = "m1b-synthetic-prompt-policy-v1"
PROFILE_VERSION = "m1b-primary-common-profile-v1"
CORPUS_VERSION = "m1b-synthetic-corpus-v2"
PROTOCOL_GENERATION = 101
PROFILE_GENERATION = 202
CORPUS_GENERATION = 303

COMPONENT_FRAMING = "m1b-length-framed-sha256-v1"
_COMPONENT_DOMAIN = b"stellaris-m1b-component-v1\x00"
_BUNDLE_DOMAIN = b"stellaris-m1b-bundle-v1\x00"

EXPECTED_CANDIDATES = frozenset(
    {
        "deepseek_r1_32b",
        "glm_4_7_flash",
        "gpt_oss_20b",
    }
)
STRATA = frozenset(
    {
        "dialogue",
        "gender_case",
        "humor_wordplay",
        "lore",
        "mechanics",
        "narrative",
        "typed_atoms",
        "ui",
    }
)
RISK_CLASSES = frozenset(
    {"auto_eligible_candidate", "critical_risk", "mandatory_human"}
)
QUALITY_DIMENSIONS = frozenset(
    {
        "context_voice_style",
        "literary_russian",
        "meaning_accuracy",
        "schema_atom_stability",
        "terminology_lore",
    }
)
FINDING_CATEGORIES = frozenset(
    {
        "atom_duplicate",
        "atom_extra",
        "atom_kind_mutation",
        "atom_missing",
        "atom_multiplicity_mutation",
        "atom_position_mutation",
        "atom_value_mutation",
        "context_voice_style_error",
        "critical_false_accept",
        "literary_error",
        "lore_error",
        "meaning_inversion",
        "negation_error",
        "number_error",
        "schema_violation",
        "terminology_error",
    }
)
CRITICAL_CATEGORIES = frozenset(
    {
        "atom_duplicate",
        "atom_extra",
        "atom_kind_mutation",
        "atom_missing",
        "atom_multiplicity_mutation",
        "atom_position_mutation",
        "atom_value_mutation",
        "critical_false_accept",
        "meaning_inversion",
        "negation_error",
        "number_error",
        "schema_violation",
    }
)
FINDING_DIMENSIONS = {
    "atom_duplicate": frozenset({"schema_atom_stability"}),
    "atom_extra": frozenset({"schema_atom_stability"}),
    "atom_kind_mutation": frozenset({"schema_atom_stability"}),
    "atom_missing": frozenset({"schema_atom_stability"}),
    "atom_multiplicity_mutation": frozenset({"schema_atom_stability"}),
    "atom_position_mutation": frozenset({"schema_atom_stability"}),
    "atom_value_mutation": frozenset({"schema_atom_stability"}),
    "context_voice_style_error": frozenset({"context_voice_style"}),
    "critical_false_accept": QUALITY_DIMENSIONS,
    "literary_error": frozenset({"literary_russian"}),
    "lore_error": frozenset({"terminology_lore"}),
    "meaning_inversion": frozenset({"meaning_accuracy"}),
    "negation_error": frozenset({"meaning_accuracy"}),
    "number_error": frozenset({"meaning_accuracy"}),
    "schema_violation": frozenset({"schema_atom_stability"}),
    "terminology_error": frozenset({"terminology_lore"}),
}
SEVERITIES = frozenset({"none", "low", "medium", "high", "critical"})
REVIEWER_ROLES = frozenset({"human_reviewer", "model_reviewer"})
REVIEW_CREDITS = frozenset({"human", "non_human"})
ATOM_KINDS = frozenset({"formatting", "icon", "placeholder", "scripted"})
THINKING_MODES = frozenset(
    {"not_probed", "disabled", "enabled", "low", "medium", "high", "max"}
)

_CODE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_UUID_V4 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_FULL_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_MODEL_REF = re.compile(r"^[a-z0-9][a-z0-9._/-]*:[a-z0-9][a-z0-9._-]*$")
_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
_ENDPOINT = re.compile(
    r"^http://(?:127[.]0[.]0[.]1|\[::1\]):([1-9][0-9]{0,4})/api$",
    re.ASCII,
)
_COMPONENT_NAME = re.compile(r"^[a-z0-9._-]+$", re.ASCII)

_PRIVATE_HASH_FIELDS = frozenset(
    {
        "content_derived_hash",
        "private_content_hash",
        "private_corpus_hash",
        "private_hash",
    }
)
_RAW_FIELDS = frozenset(
    {
        "annotation",
        "annotations",
        "file_name",
        "file_path",
        "filename",
        "input",
        "inputs",
        "model_output",
        "output",
        "outputs",
        "path",
        "prompt",
        "prompts",
        "raw_input",
        "raw_output",
        "raw_text",
        "raw_value",
        "raw_values",
        "source_text",
        "text",
        "translation",
        "translations",
    }
)

_COUNT_KEYS = (
    "candidates",
    "findings",
    "holdout_samples",
    "human_ground_truth",
    "results",
    "reviews",
    "samples",
    "tuning_samples",
)

_EXPECTED_RUNTIME = {
    "lifecycle": "cold_and_warm_separate",
    "num_ctx": 8192,
    "output_token_limit": 2048,
    "retry_limit": 0,
    "seed": 424242,
    "temperature_milli": 0,
    "timeout_ms": 300000,
}
_EXPECTED_THINKING = {
    "exception_status": "none",
    "exception_version": None,
    "mode": "not_probed",
}
_EXPECTED_MODEL_REFS = {
    "glm_4_7_flash": "glm-4.7-flash:synthetic-placeholder",
    "deepseek_r1_32b": "deepseek-r1-32b:synthetic-placeholder",
    "gpt_oss_20b": "gpt-oss-20b:synthetic-placeholder",
}
_EXPECTED_MODEL_DIGESTS = {
    "glm_4_7_flash": "1" * 64,
    "deepseek_r1_32b": "2" * 64,
    "gpt_oss_20b": "3" * 64,
}

_REQUEST_FIELD_ALLOWLIST = (
    "format",
    "keep_alive",
    "model",
    "options",
    "prompt",
    "stream",
    "think",
)
_EXPECTED_PROVIDER_CONTROLS = {
    "auto_pull": False,
    "fallback": False,
    "numeric_loopback_only": True,
    "persistence_status": "not_probed",
    "proxy_routing": False,
    "redirects": False,
    "residency_status": "not_probed",
}
_EXPECTED_REQUEST_BOUNDARY = {
    "allowed_request_fields": list(_REQUEST_FIELD_ALLOWLIST),
    "context_overflow_policy": "controlled_failure",
    "context_reuse": False,
    "continuation_reuse": False,
    "conversation_reuse": False,
    "independent_request_per_sample": True,
    "thinking_trace_reuse": False,
    "truncation_policy": "controlled_failure",
}

_ROOT_FIELDS = (
    "aggregate_report",
    "benchmark_state",
    "candidate_profiles",
    "conformance_results",
    "corpus",
    "coverage",
    "definition_bundle",
    "findings",
    "human_ground_truth",
    "protocol",
    "provider_policy",
    "request_boundary",
    "schema_version",
)
_CANDIDATE_FIELDS = (
    "candidate",
    "candidate_id",
    "digest_kind",
    "model_digest",
    "model_ref",
    "profile_generation",
    "profile_version",
    "runtime",
    "selection_status",
    "thinking_profile",
)
_ATOM_FIELDS = (
    "atom_id",
    "kind",
    "occurrence_id",
    "occurrence_index",
    "position_end",
    "position_policy",
    "position_start",
    "provenance",
    "synthetic_value",
)
_RESULT_FIELDS = (
    "accounting",
    "attempt_index",
    "attempt_stage",
    "candidate_id",
    "corpus_generation",
    "dimension_records",
    "editorial_status",
    "experiment_lane",
    "initial_result_id",
    "observed_atoms",
    "profile_generation",
    "profile_version",
    "protocol_generation",
    "result_id",
    "sample_id",
    "technical_conformance",
    "terminal_status",
)
_FINDING_FIELDS = (
    "category",
    "dimension",
    "finding_id",
    "result_id",
    "reviews",
    "severity",
)
_REVIEW_FIELDS = (
    "decision",
    "review_credit",
    "review_id",
    "review_stage",
    "reviewer_id",
    "reviewer_role",
)
_HUMAN_GROUND_TRUTH_FIELDS = (
    "applicability_reason",
    "dimension",
    "ground_truth_id",
    "result_id",
    "review_stage",
    "reviewer_id",
    "reviewer_role",
    "status",
)
_COVERAGE_FIELDS = (
    "declared_primary_assignment_count",
    "per_candidate",
    "per_stratum",
    "required_primary_assignment_count",
)
_ACCOUNTING_FIELDS = (
    "cold_latency_observation_count",
    "fallback_attempt_count",
    "human_fallback_count",
    "initial_attempt_count",
    "memory_observation_count",
    "model_call_count",
    "model_fallback_count",
    "repair_attempt_count",
    "repair_failure_count",
    "repair_success_count",
    "retry_attempt_count",
    "terminal_failure_count",
    "warm_latency_observation_count",
)
_QUALITY_DIMENSION_ORDER = (
    "schema_atom_stability",
    "meaning_accuracy",
    "terminology_lore",
    "literary_russian",
    "context_voice_style",
)
_TECHNICAL_CONFORMANCE_STATUSES = (
    "not_observed",
    "synthetic_conformant",
    "synthetic_nonconformant",
)
_EDITORIAL_STATUSES = (
    "editorially_approved",
    "editorially_rejected",
    "not_evaluated",
)
_TERMINAL_STATUSES = ("controlled_failure", "not_applicable", "success")
_LANE_STAGE_PAIRS = frozenset(
    {("fallback", "fallback"), ("primary", "initial"), ("repair", "repair")}
)
_BENCHMARK_STATES = frozenset(
    {
        (False, "partial_synthetic_conformance"),
        (True, "complete_benchmark"),
    }
)
_AUTO_ELIGIBLE_STRATA = frozenset({"mechanics", "ui"})
_DIMENSION_STATUSES = frozenset(
    {
        "human_fail",
        "human_pass",
        "not_applicable",
        "not_evaluated",
        "synthetic_conformant",
        "synthetic_nonconformant",
    }
)


def _canonical_public_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


_EXPECTED_SYNTHETIC_CORPUS = {
    "corpus_class": "synthetic",
    "corpus_version": CORPUS_VERSION,
    "generation": CORPUS_GENERATION,
    "samples": [
        {
            "expected_atoms": [
                {
                    "atom_id": "00000000-0000-4000-8000-000000000021",
                    "kind": "placeholder",
                    "occurrence_id": "00000000-0000-4000-8000-000000000071",
                    "occurrence_index": 0,
                    "position_end": 21,
                    "position_policy": "exact_utf8_byte_span",
                    "position_start": 0,
                    "provenance": "synthetic",
                    "synthetic_value": "SYNTHETIC_PLACEHOLDER",
                },
                {
                    "atom_id": "00000000-0000-4000-8000-000000000021",
                    "kind": "placeholder",
                    "occurrence_id": "00000000-0000-4000-8000-000000000072",
                    "occurrence_index": 1,
                    "position_end": 43,
                    "position_policy": "exact_utf8_byte_span",
                    "position_start": 22,
                    "provenance": "synthetic",
                    "synthetic_value": "SYNTHETIC_PLACEHOLDER",
                },
                {
                    "atom_id": "00000000-0000-4000-8000-000000000022",
                    "kind": "icon",
                    "occurrence_id": "00000000-0000-4000-8000-000000000073",
                    "occurrence_index": 0,
                    "position_end": 58,
                    "position_policy": "exact_utf8_byte_span",
                    "position_start": 44,
                    "provenance": "synthetic",
                    "synthetic_value": "SYNTHETIC_ICON",
                },
            ],
            "risk_class": "mandatory_human",
            "sample_id": "00000000-0000-4000-8000-000000000011",
            "source_unit_cluster_id": "00000000-0000-4000-8000-000000000013",
            "stratum": "narrative",
        },
        {
            "expected_atoms": [
                {
                    "atom_id": "00000000-0000-4000-8000-000000000023",
                    "kind": "scripted",
                    "occurrence_id": "00000000-0000-4000-8000-000000000074",
                    "occurrence_index": 0,
                    "position_end": 18,
                    "position_policy": "exact_utf8_byte_span",
                    "position_start": 0,
                    "provenance": "synthetic",
                    "synthetic_value": "SYNTHETIC_SCRIPTED",
                }
            ],
            "risk_class": "auto_eligible_candidate",
            "sample_id": "00000000-0000-4000-8000-000000000012",
            "source_unit_cluster_id": "00000000-0000-4000-8000-000000000014",
            "stratum": "ui",
        },
    ],
    "splits": {
        "holdout": ["00000000-0000-4000-8000-000000000012"],
        "tuning": ["00000000-0000-4000-8000-000000000011"],
    },
}
_SYNTHETIC_CORPUS_DOMAIN = b"stellaris-m1b-synthetic-corpus-v1\x00"
_EXPECTED_SYNTHETIC_CORPUS_BYTES = _canonical_public_json(
    _EXPECTED_SYNTHETIC_CORPUS
)
SYNTHETIC_CORPUS_SHA256 = hashlib.sha256(
    _SYNTHETIC_CORPUS_DOMAIN
    + len(_EXPECTED_SYNTHETIC_CORPUS_BYTES).to_bytes(8, "big")
    + _EXPECTED_SYNTHETIC_CORPUS_BYTES
).hexdigest()


def _candidate_definition(candidate: str) -> bytes:
    return _canonical_public_json(
        {
            "candidate": candidate,
            "candidate_profile_fields": list(_CANDIDATE_FIELDS),
            "digest_kind": "synthetic_placeholder",
            "model_digest": _EXPECTED_MODEL_DIGESTS[candidate],
            "model_ref": _EXPECTED_MODEL_REFS[candidate],
            "profile_generation": PROFILE_GENERATION,
            "runtime": _EXPECTED_RUNTIME,
            "selection_status": "unranked_candidate",
            "thinking_profile": _EXPECTED_THINKING,
        }
    )

_TRUSTED_COMPONENT_ROWS = (
    (
        "benchmark_contract",
        PROTOCOL_VERSION,
        PROTOCOL_GENERATION,
        _canonical_public_json(
            {
                "assignment_tuple": [
                    "candidate_id",
                    "sample_id",
                    "profile_version",
                    "profile_generation",
                    "experiment_lane",
                    "attempt_stage",
                    "attempt_index",
                ],
                "benchmark_states": [list(state) for state in sorted(_BENCHMARK_STATES)],
                "document_schema": DOCUMENT_SCHEMA,
                "protocol_generation": PROTOCOL_GENERATION,
                "root_fields": list(_ROOT_FIELDS),
            }
        ),
    ),
    (
        "output_schema",
        OUTPUT_SCHEMA_VERSION,
        PROTOCOL_GENERATION,
        _canonical_public_json(
            {
                "accounting_fields": list(_ACCOUNTING_FIELDS),
                "atom_fields": list(_ATOM_FIELDS),
                "count_keys": list(_COUNT_KEYS),
                "dimension_statuses": sorted(_DIMENSION_STATUSES),
                "dimensions": list(_QUALITY_DIMENSION_ORDER),
                "editorial_statuses": list(_EDITORIAL_STATUSES),
                "finding_fields": list(_FINDING_FIELDS),
                "human_ground_truth_fields": list(_HUMAN_GROUND_TRUTH_FIELDS),
                "review_fields": list(_REVIEW_FIELDS),
                "result_fields": list(_RESULT_FIELDS),
                "coverage_fields": list(_COVERAGE_FIELDS),
                "schema_version": OUTPUT_SCHEMA_VERSION,
                "technical_conformance": list(_TECHNICAL_CONFORMANCE_STATUSES),
                "terminal_statuses": list(_TERMINAL_STATUSES),
            }
        ),
    ),
    (
        "prompt_policy",
        PROMPT_VERSION,
        PROTOCOL_GENERATION,
        _canonical_public_json(
            {
                "prompt_state": "not_created",
                "prompt_version": PROMPT_VERSION,
            }
        ),
    ),
    (
        "candidate_profile.glm_4_7_flash",
        PROFILE_VERSION,
        PROFILE_GENERATION,
        _candidate_definition("glm_4_7_flash"),
    ),
    (
        "candidate_profile.deepseek_r1_32b",
        PROFILE_VERSION,
        PROFILE_GENERATION,
        _candidate_definition("deepseek_r1_32b"),
    ),
    (
        "candidate_profile.gpt_oss_20b",
        PROFILE_VERSION,
        PROFILE_GENERATION,
        _candidate_definition("gpt_oss_20b"),
    ),
    (
        "corpus_policy",
        "m1b-corpus-policy-v1",
        PROTOCOL_GENERATION,
        _canonical_public_json(
            {
                "corpus_class": "synthetic",
                "corpus_generation": CORPUS_GENERATION,
                "corpus_version": CORPUS_VERSION,
                "publication": "synthetic_only",
                "raw_private_publication": False,
                "synthetic_corpus_framing": "m1b-synthetic-corpus-sha256-v1",
                "synthetic_corpus_sha256": SYNTHETIC_CORPUS_SHA256,
            }
        ),
    ),
    (
        "split_policy",
        "m1b-split-policy-v1",
        PROTOCOL_GENERATION,
        _canonical_public_json(
            {
                "auto_eligible_strata": sorted(_AUTO_ELIGIBLE_STRATA),
                "related_variants_same_split": True,
                "risk_classes": sorted(RISK_CLASSES),
                "splits": ["tuning", "holdout"],
                "strata": sorted(STRATA),
            }
        ),
    ),
    (
        "generation_policy",
        "m1b-generation-policy-v1",
        PROTOCOL_GENERATION,
        _canonical_public_json(
            {
                "endpoint_policy": {
                    "forms": [
                        "http://127.0.0.1:<1..65535>/api",
                        "http://[::1]:<1..65535>/api",
                    ],
                    "normalization": False,
                },
                "provider_controls": _EXPECTED_PROVIDER_CONTROLS,
                "request_boundary": _EXPECTED_REQUEST_BOUNDARY,
                "retry_limit": 0,
            }
        ),
    ),
    (
        "randomization_blinding_policy",
        "m1b-randomization-blinding-policy-v1",
        PROTOCOL_GENERATION,
        _canonical_public_json(
            {
                "blinding_failure": "denominator_failure",
                "mapping": "private",
                "replacement_reviewers": "never_unblinded_humans",
                "self_identification": "primary_failure",
                "unblinded_review": "secondary_only",
            }
        ),
    ),
    (
        "quality_rubric",
        "m1b-quality-rubric-v1",
        PROTOCOL_GENERATION,
        _canonical_public_json(
            {
                "dimensions": list(_QUALITY_DIMENSION_ORDER),
                "finding_dimension_mapping": {
                    category: sorted(dimensions)
                    for category, dimensions in FINDING_DIMENSIONS.items()
                },
                "human_status_requires_ground_truth": True,
                "missing_ground_truth_status": "not_evaluated",
                "reviewer_roles": sorted(REVIEWER_ROLES),
                "severities": ["none", "low", "medium", "high", "critical"],
            }
        ),
    ),
    (
        "measurement_policy",
        "m1b-measurement-policy-v1",
        PROTOCOL_GENERATION,
        _canonical_public_json(
            {
                "accounting_fields": list(_ACCOUNTING_FIELDS),
                "cold_warm_separate": True,
                "row_derived_accounting": True,
                "terminal_failure_in_denominator": True,
            }
        ),
    ),
    (
        "retention_leakage_policy",
        "m1b-retention-leakage-policy-v1",
        PROTOCOL_GENERATION,
        _canonical_public_json(
            {
                "cleanup_required": True,
                "persistence_blocker": "PROVIDER_PERSISTENCE_UNPROVEN",
                "persistence_status": "not_probed",
                "public_raw_fields": False,
                "retention_state": "proposal",
            }
        ),
    ),
    (
        "validator_policy",
        "m1b-validator-policy-v2",
        PROTOCOL_GENERATION,
        _canonical_public_json(
            {
                "closed_schema": True,
                "component_framing": COMPONENT_FRAMING,
                "fixture_schema": FIXTURE_SCHEMA,
                "json_integer_max": MAX_JSON_INTEGER,
                "json_integer_min": MIN_JSON_INTEGER,
                "max_input_bytes": MAX_INPUT_BYTES,
                "offline": True,
                "output_fields": ["codes", "counts", "status"],
                "strict_json": {
                    "duplicate_keys": "reject",
                    "floats": "reject",
                    "nonfinite": "reject",
                    "unicode": "strict_utf8_scalars",
                },
            }
        ),
    ),
    (
        "analysis_policy",
        "m1b-analysis-policy-v1",
        PROTOCOL_GENERATION,
        _canonical_public_json(
            {
                "cluster_aware": True,
                "critical_false_accept_minimum_n": 149,
                "minimum_n_per_required_stratum": 36,
                "minimum_overall_n": 288,
                "owner_decision_required": True,
                "stable_reviewer_pairs": True,
                "strata": sorted(STRATA),
            }
        ),
    ),
)

REQUIRED_COMPONENT_KINDS = tuple(row[0] for row in _TRUSTED_COMPONENT_ROWS)


class ContractError(RuntimeError):
    """A controlled failure that never carries input content."""

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or _CODE.fullmatch(code) is None:
            code = "UNEXPECTED_FAILURE"
        self.code = code
        super().__init__(code)


def _ascii_contract_token(value: Any, code: str) -> bytes:
    if type(value) is not str:
        raise ContractError("INVALID_TYPE")
    if _COMPONENT_NAME.fullmatch(value) is None:
        raise ContractError(code)
    try:
        return value.encode("ascii", errors="strict")
    except UnicodeEncodeError:
        raise ContractError(code)


def component_hash(kind: str, version: str, payload: bytes) -> str:
    """Return the canonical public component digest defined by the M1B contract."""

    kind_bytes = _ascii_contract_token(kind, "DEFINITION_KIND_INVALID")
    version_bytes = _ascii_contract_token(version, "DEFINITION_VERSION_INVALID")
    if type(payload) is not bytes:
        raise ContractError("INVALID_TYPE")
    framed = b"".join(
        (
            _COMPONENT_DOMAIN,
            len(kind_bytes).to_bytes(4, "big"),
            kind_bytes,
            len(version_bytes).to_bytes(4, "big"),
            version_bytes,
            len(payload).to_bytes(8, "big"),
            payload,
        )
    )
    return hashlib.sha256(framed).hexdigest()


def bundle_hash(components: Sequence[Tuple[str, str, str]]) -> str:
    """Return the deterministic digest of unique component hash records."""

    if type(components) not in (list, tuple):
        raise ContractError("INVALID_TYPE")
    prepared: List[Tuple[bytes, bytes, bytes]] = []
    seen: Set[Tuple[bytes, bytes]] = set()
    for raw in components:
        if type(raw) not in (list, tuple) or len(raw) != 3:
            raise ContractError("INVALID_TYPE")
        kind_bytes = _ascii_contract_token(raw[0], "DEFINITION_KIND_INVALID")
        version_bytes = _ascii_contract_token(
            raw[1], "DEFINITION_VERSION_INVALID"
        )
        if type(raw[2]) is not str:
            raise ContractError("INVALID_TYPE")
        stored_hash = raw[2]
        if _FULL_DIGEST.fullmatch(stored_hash) is None:
            raise ContractError("DEFINITION_HASH_INVALID")
        key = (kind_bytes, version_bytes)
        if key in seen:
            raise ContractError("DEFINITION_COMPONENT_DUPLICATE")
        seen.add(key)
        prepared.append((kind_bytes, version_bytes, bytes.fromhex(stored_hash)))
    framed: List[bytes] = [
        _BUNDLE_DOMAIN,
        len(prepared).to_bytes(4, "big"),
    ]
    for kind_bytes, version_bytes, digest_bytes in sorted(
        prepared, key=lambda row: (row[0], row[1])
    ):
        framed.extend(
            (
                len(kind_bytes).to_bytes(4, "big"),
                kind_bytes,
                len(version_bytes).to_bytes(4, "big"),
                version_bytes,
                digest_bytes,
            )
        )
    return hashlib.sha256(b"".join(framed)).hexdigest()


def _trusted_components() -> Tuple[Dict[str, Any], ...]:
    rows: List[Dict[str, Any]] = []
    for kind, version, generation, payload in _TRUSTED_COMPONENT_ROWS:
        rows.append(
            {
                "acceptance_state": "proposed",
                "definition": payload.decode("ascii"),
                "generation": generation,
                "kind": kind,
                "sha256": component_hash(kind, version, payload),
                "version": version,
            }
        )
    return tuple(rows)


TRUSTED_COMPONENTS = _trusted_components()
TRUSTED_COMPONENTS_BY_KIND = {
    component["kind"]: component for component in TRUSTED_COMPONENTS
}
TRUSTED_BUNDLE_HASH = bundle_hash(
    [
        (component["kind"], component["version"], component["sha256"])
        for component in TRUSTED_COMPONENTS
    ]
)


def _empty_counts() -> Dict[str, int]:
    return {key: 0 for key in _COUNT_KEYS}


def _result(
    status: str,
    *,
    code: Optional[str] = None,
    counts: Optional[Mapping[str, int]] = None,
) -> Dict[str, Any]:
    return {
        "codes": [] if code is None else [code],
        "counts": dict(_empty_counts() if counts is None else counts),
        "status": status,
    }


def _duplicate_safe_object(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> None:
    raise ContractError("JSON_MALFORMED")


def _reject_json_float(_value: str) -> None:
    raise ContractError("JSON_FLOAT_FORBIDDEN")


def _parse_bounded_int(token: str) -> int:
    if type(token) is not str or not token:
        raise ContractError("JSON_INTEGER_OUT_OF_RANGE")
    negative = token.startswith("-")
    digits = token[1:] if negative else token
    if not digits or not digits.isascii() or not digits.isdigit():
        raise ContractError("JSON_INTEGER_OUT_OF_RANGE")
    limit = "9223372036854775808" if negative else "9223372036854775807"
    if len(digits) > len(limit) or (len(digits) == len(limit) and digits > limit):
        raise ContractError("JSON_INTEGER_OUT_OF_RANGE")
    value = int(token, 10)
    if value < MIN_JSON_INTEGER or value > MAX_JSON_INTEGER:
        raise ContractError("JSON_INTEGER_OUT_OF_RANGE")
    return value


def _assert_unicode_scalars(value: Any) -> None:
    if isinstance(value, str):
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            raise ContractError("JSON_UNICODE_INVALID")
        return
    if type(value) is list:
        for item in value:
            _assert_unicode_scalars(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            _assert_unicode_scalars(key)
            _assert_unicode_scalars(item)


def parse_json_bytes(data: bytes) -> Any:
    """Parse strict UTF-8 JSON with duplicate-key and constant rejection."""

    if type(data) is not bytes:
        raise ContractError("INVALID_TYPE")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ContractError("UTF8_INVALID")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_safe_object,
            parse_constant=_reject_json_constant,
            parse_float=_reject_json_float,
            parse_int=_parse_bounded_int,
        )
    except ContractError:
        raise
    except RecursionError:
        raise ContractError("JSON_NESTING_LIMIT")
    except (json.JSONDecodeError, TypeError, ValueError):
        raise ContractError("JSON_MALFORMED")
    _assert_unicode_scalars(value)
    return value


def _read_explicit_file(value: str) -> bytes:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ContractError("INPUT_READ_FAILED")
    try:
        with open(value, "rb") as stream:
            data = stream.read(MAX_INPUT_BYTES + 1)
    except (OSError, ValueError):
        raise ContractError("INPUT_READ_FAILED")
    if len(data) > MAX_INPUT_BYTES:
        raise ContractError("INPUT_SIZE_LIMIT")
    return data


def _scan_for_forbidden_fields(value: Any) -> None:
    if type(value) is list:
        for item in value:
            _scan_for_forbidden_fields(item)
        return
    if type(value) is not dict:
        return
    for key, item in value.items():
        normalized = key.casefold() if isinstance(key, str) else ""
        if normalized in _PRIVATE_HASH_FIELDS:
            raise ContractError("PRIVATE_CORPUS_HASH_FORBIDDEN")
        if normalized in _RAW_FIELDS:
            raise ContractError("RAW_FIELD_FORBIDDEN")
        _scan_for_forbidden_fields(item)


def _require_object(
    value: Any,
    fields: Sequence[str],
    *,
    missing_codes: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    if type(value) is not dict:
        raise ContractError("INVALID_TYPE")
    expected = set(fields)
    missing_codes = {} if missing_codes is None else missing_codes
    for field in fields:
        if field not in value:
            raise ContractError(missing_codes.get(field, "MISSING_FIELD"))
    if set(value) != expected:
        raise ContractError("UNKNOWN_FIELD")
    return value


def _require_list(value: Any) -> List[Any]:
    if type(value) is not list:
        raise ContractError("INVALID_TYPE")
    return value


def _require_string(value: Any) -> str:
    if type(value) is not str:
        raise ContractError("INVALID_TYPE")
    return value


def _require_bool(value: Any) -> bool:
    if type(value) is not bool:
        raise ContractError("INVALID_TYPE")
    return value


def _require_int(value: Any, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ContractError("INVALID_TYPE")
    return value


def _require_version(value: Any) -> str:
    value = _require_string(value)
    if _VERSION.fullmatch(value) is None:
        raise ContractError("INVALID_VERSION")
    return value


def _require_uuid(value: Any) -> str:
    value = _require_string(value)
    if _UUID_V4.fullmatch(value) is None:
        raise ContractError("INVALID_OPAQUE_ID")
    return value


class _IdentityRegistry:
    def __init__(self) -> None:
        self.roles: Dict[str, str] = {}

    def define(
        self,
        value: Any,
        role: str,
        *,
        allow_same_role_repeat: bool = False,
    ) -> str:
        identifier = _require_uuid(value)
        previous = self.roles.get(identifier)
        if previous is None:
            self.roles[identifier] = role
            return identifier
        if role.startswith("reviewer:") and previous.startswith("reviewer:"):
            if role != previous:
                raise ContractError("REVIEWER_ROLE_INCONSISTENT")
            return identifier
        if role.startswith("reviewer:") or previous.startswith("reviewer:"):
            raise ContractError("OPAQUE_ID_ROLE_COLLISION")
        if previous != role:
            raise ContractError("OPAQUE_ID_ROLE_COLLISION")
        if allow_same_role_repeat:
            return identifier
        raise ContractError("DUPLICATE_OPAQUE_ID")

    def reference(self, value: Any, role: str) -> str:
        identifier = _require_uuid(value)
        if self.roles.get(identifier) != role:
            raise ContractError("REFERENCE_NOT_FOUND")
        return identifier

    def reviewer(self, value: Any, reviewer_role: str) -> str:
        if reviewer_role not in REVIEWER_ROLES:
            raise ContractError("UNKNOWN_REVIEWER_ROLE")
        return self.define(
            value,
            "reviewer:{0}".format(reviewer_role),
            allow_same_role_repeat=True,
        )


def _require_numeric_loopback_endpoint(value: Any) -> None:
    endpoint = _require_string(value)
    if (
        not endpoint.isascii()
        or endpoint != endpoint.strip()
        or any(ord(character) <= 0x1F or 0x7F <= ord(character) <= 0x9F for character in endpoint)
    ):
        raise ContractError("ENDPOINT_NOT_NUMERIC_LOOPBACK")
    match = _ENDPOINT.fullmatch(endpoint)
    if match is None:
        raise ContractError("ENDPOINT_NOT_NUMERIC_LOOPBACK")
    port = int(match.group(1), 10)
    if port < 1 or port > 65535:
        raise ContractError("ENDPOINT_NOT_NUMERIC_LOOPBACK")


def _validate_definition_bundle(value: Any) -> Tuple[str, ...]:
    definition_bundle = _require_object(
        value, ("components", "framing", "sha256")
    )
    if definition_bundle["framing"] != COMPONENT_FRAMING:
        raise ContractError("DEFINITION_FRAMING_UNSUPPORTED")
    stored_bundle_hash = _require_string(definition_bundle["sha256"])
    if _FULL_DIGEST.fullmatch(stored_bundle_hash) is None:
        raise ContractError("BUNDLE_HASH_INVALID")

    parsed: List[Dict[str, Any]] = []
    seen_pairs: Set[Tuple[str, str]] = set()
    seen_kinds: Set[str] = set()
    for raw_component in _require_list(definition_bundle["components"]):
        component = _require_object(
            raw_component,
            (
                "acceptance_state",
                "definition",
                "generation",
                "kind",
                "sha256",
                "version",
            ),
        )
        kind = _require_string(component["kind"])
        if _COMPONENT_NAME.fullmatch(kind) is None:
            raise ContractError("DEFINITION_KIND_INVALID")
        if kind not in TRUSTED_COMPONENTS_BY_KIND:
            raise ContractError("DEFINITION_KIND_UNKNOWN")
        version = _require_version(component["version"])
        pair = (kind, version)
        if pair in seen_pairs:
            raise ContractError("DEFINITION_COMPONENT_DUPLICATE")
        seen_pairs.add(pair)
        if kind in seen_kinds:
            raise ContractError("DEFINITION_COMPONENT_EXTRA")
        seen_kinds.add(kind)
        stored_hash = _require_string(component["sha256"])
        if _FULL_DIGEST.fullmatch(stored_hash) is None:
            raise ContractError("DEFINITION_HASH_INVALID")
        _require_int(component["generation"], minimum=1)
        if component["acceptance_state"] not in (
            "owner_accepted",
            "proposed",
            "retired",
        ):
            raise ContractError("DEFINITION_ACCEPTANCE_STATE_INVALID")
        _require_string(component["definition"])
        parsed.append(component)

    missing = set(REQUIRED_COMPONENT_KINDS) - seen_kinds
    if missing:
        raise ContractError("DEFINITION_COMPONENT_MISSING")
    if len(parsed) != len(REQUIRED_COMPONENT_KINDS):
        raise ContractError("DEFINITION_COMPONENT_EXTRA")

    digest_rows: List[Tuple[str, str, str]] = []
    states: List[str] = []
    for component in parsed:
        trusted = TRUSTED_COMPONENTS_BY_KIND[component["kind"]]
        if component["version"] != trusted["version"]:
            raise ContractError("DEFINITION_VERSION_UNSUPPORTED")
        if component["generation"] != trusted["generation"]:
            raise ContractError("DEFINITION_GENERATION_MISMATCH")
        if component["acceptance_state"] != trusted["acceptance_state"]:
            raise ContractError("DEFINITION_ACCEPTANCE_STATE_MISMATCH")
        payload = component["definition"].encode("utf-8", errors="strict")
        if payload != trusted["definition"].encode("ascii"):
            raise ContractError("DEFINITION_PAYLOAD_MISMATCH")
        calculated = component_hash(
            component["kind"], component["version"], payload
        )
        if component["sha256"] != calculated or calculated != trusted["sha256"]:
            raise ContractError("DEFINITION_HASH_MISMATCH")
        digest_rows.append(
            (component["kind"], component["version"], component["sha256"])
        )
        states.append(component["acceptance_state"])
    calculated_bundle_hash = bundle_hash(digest_rows)
    if (
        stored_bundle_hash != calculated_bundle_hash
        or calculated_bundle_hash != TRUSTED_BUNDLE_HASH
    ):
        raise ContractError("BUNDLE_HASH_MISMATCH")
    return tuple(states)


def _validate_protocol(value: Any) -> Dict[str, Any]:
    protocol = _require_object(
        value,
        (
            "generation",
            "output_schema_version",
            "prompt_version",
            "protocol_version",
        ),
        missing_codes={
            "output_schema_version": "MISSING_SCHEMA_VERSION",
            "prompt_version": "MISSING_PROMPT_VERSION",
        },
    )
    if _require_int(protocol["generation"], minimum=1) != PROTOCOL_GENERATION:
        raise ContractError("PROTOCOL_GENERATION_MISMATCH")
    if _require_version(protocol["output_schema_version"]) != OUTPUT_SCHEMA_VERSION:
        raise ContractError("OUTPUT_SCHEMA_VERSION_UNSUPPORTED")
    if _require_version(protocol["prompt_version"]) != PROMPT_VERSION:
        raise ContractError("PROMPT_VERSION_UNSUPPORTED")
    if _require_version(protocol["protocol_version"]) != PROTOCOL_VERSION:
        raise ContractError("PROTOCOL_VERSION_UNSUPPORTED")
    return protocol


def _validate_provider_policy(value: Any) -> Dict[str, Any]:
    policy = _require_object(
        value,
        (
            "auto_pull",
            "endpoint",
            "fallback",
            "numeric_loopback_only",
            "persistence_status",
            "proxy_routing",
            "redirects",
            "residency_status",
        ),
    )
    if not _require_bool(policy["numeric_loopback_only"]):
        raise ContractError("ENDPOINT_NOT_NUMERIC_LOOPBACK")
    _require_numeric_loopback_endpoint(policy["endpoint"])
    for field, code in (
        ("redirects", "REDIRECTS_ENABLED"),
        ("proxy_routing", "PROXY_ROUTING_ENABLED"),
        ("auto_pull", "AUTO_PULL_ENABLED"),
        ("fallback", "FALLBACK_ENABLED"),
    ):
        if _require_bool(policy[field]):
            raise ContractError(code)
    if policy["residency_status"] != "not_probed":
        raise ContractError("RESIDENCY_STATE_INVALID")
    if policy["persistence_status"] != "not_probed":
        raise ContractError("PERSISTENCE_STATE_INVALID")
    return policy


def _validate_request_boundary(value: Any) -> None:
    boundary = _require_object(
        value,
        (
            "allowed_request_fields",
            "context_overflow_policy",
            "context_reuse",
            "continuation_reuse",
            "conversation_reuse",
            "independent_request_per_sample",
            "thinking_trace_reuse",
            "truncation_policy",
        ),
    )
    if not _require_bool(boundary["independent_request_per_sample"]):
        raise ContractError("STATELESS_REQUEST_POLICY_INVALID")
    for field in (
        "context_reuse",
        "continuation_reuse",
        "conversation_reuse",
        "thinking_trace_reuse",
    ):
        if _require_bool(boundary[field]):
            raise ContractError("STATELESS_REQUEST_POLICY_INVALID")
    allowed = _require_list(boundary["allowed_request_fields"])
    if tuple(allowed) != _REQUEST_FIELD_ALLOWLIST or any(
        type(item) is not str for item in allowed
    ):
        raise ContractError("REQUEST_FIELD_ALLOWLIST_INVALID")
    if (
        boundary["truncation_policy"] != "controlled_failure"
        or boundary["context_overflow_policy"] != "controlled_failure"
    ):
        raise ContractError("REQUEST_FAILURE_POLICY_INVALID")


def _validate_runtime(value: Any) -> Dict[str, Any]:
    runtime = _require_object(value, tuple(_EXPECTED_RUNTIME))
    _require_string(runtime["lifecycle"])
    for field in (
        "num_ctx",
        "output_token_limit",
        "retry_limit",
        "seed",
        "temperature_milli",
        "timeout_ms",
    ):
        _require_int(runtime[field], minimum=0 if field in ("retry_limit", "seed", "temperature_milli") else 1)
    if runtime != _EXPECTED_RUNTIME:
        raise ContractError("PROFILE_DEFINITION_MISMATCH")
    return runtime


def _validate_thinking_profile(value: Any) -> Dict[str, Any]:
    profile = _require_object(
        value, ("exception_status", "exception_version", "mode")
    )
    mode = _require_string(profile["mode"])
    if mode not in THINKING_MODES:
        raise ContractError("INVALID_PROFILE_VALUE")
    if profile != _EXPECTED_THINKING:
        raise ContractError("PROFILE_DEFINITION_MISMATCH")
    return profile


def _validate_candidates(
    value: Any, registry: _IdentityRegistry
) -> Dict[str, Dict[str, Any]]:
    candidates = _require_list(value)
    if len(candidates) != 3:
        raise ContractError("CANDIDATE_SET_INVALID")
    result: Dict[str, Dict[str, Any]] = {}
    candidate_names: Set[str] = set()
    digests: Set[str] = set()
    for raw_candidate in candidates:
        candidate = _require_object(
            raw_candidate,
            _CANDIDATE_FIELDS,
            missing_codes={"profile_version": "MISSING_PROFILE_VERSION"},
        )
        candidate_id = registry.define(candidate["candidate_id"], "candidate")
        candidate_name = _require_string(candidate["candidate"])
        if candidate_name not in EXPECTED_CANDIDATES or candidate_name in candidate_names:
            raise ContractError("CANDIDATE_SET_INVALID")
        candidate_names.add(candidate_name)
        model_ref = _require_string(candidate["model_ref"])
        lowered_ref = model_ref.casefold()
        if "-cloud" in lowered_ref or ":cloud" in lowered_ref:
            raise ContractError("CLOUD_MODEL_FORBIDDEN")
        if _MODEL_REF.fullmatch(model_ref) is None:
            raise ContractError("INVALID_MODEL_REF")
        digest = _require_string(candidate["model_digest"])
        if _FULL_DIGEST.fullmatch(digest) is None:
            raise ContractError("INVALID_MODEL_DIGEST")
        if digest in digests:
            raise ContractError("DUPLICATE_MODEL_DIGEST")
        digests.add(digest)
        if candidate["digest_kind"] != "synthetic_placeholder":
            raise ContractError("NON_SYNTHETIC_DIGEST_FORBIDDEN")
        if _require_version(candidate["profile_version"]) != PROFILE_VERSION:
            raise ContractError("PROFILE_VERSION_UNSUPPORTED")
        if _require_int(candidate["profile_generation"], minimum=1) != PROFILE_GENERATION:
            raise ContractError("PROFILE_GENERATION_MISMATCH")
        if candidate["selection_status"] != "unranked_candidate":
            raise ContractError("PREMATURE_SELECTION")
        _validate_runtime(candidate["runtime"])
        _validate_thinking_profile(candidate["thinking_profile"])
        if (
            model_ref != _EXPECTED_MODEL_REFS[candidate_name]
            or digest != _EXPECTED_MODEL_DIGESTS[candidate_name]
        ):
            raise ContractError("PROFILE_DEFINITION_MISMATCH")
        result[candidate_id] = candidate
    if candidate_names != EXPECTED_CANDIDATES:
        raise ContractError("CANDIDATE_SET_INVALID")
    return result


_SYNTHETIC_VALUE = re.compile(r"^SYNTHETIC_[A-Z0-9_]+$", re.ASCII)


def _validate_atom_shape(value: Any) -> Dict[str, Any]:
    atom = _require_object(value, _ATOM_FIELDS)
    atom_id = _require_uuid(atom["atom_id"])
    occurrence_id = _require_uuid(atom["occurrence_id"])
    kind = _require_string(atom["kind"])
    if kind not in ATOM_KINDS:
        raise ContractError("UNKNOWN_ATOM_KIND")
    if atom["provenance"] != "synthetic":
        raise ContractError("NON_SYNTHETIC_ATOM_FORBIDDEN")
    synthetic_value = _require_string(atom["synthetic_value"])
    if _SYNTHETIC_VALUE.fullmatch(synthetic_value) is None:
        raise ContractError("NON_SYNTHETIC_ATOM_FORBIDDEN")
    occurrence_index = _require_int(atom["occurrence_index"], minimum=0)
    if atom["position_policy"] != "exact_utf8_byte_span":
        raise ContractError("ATOM_POSITION_POLICY_INVALID")
    start = _require_int(atom["position_start"], minimum=0)
    end = _require_int(atom["position_end"], minimum=1)
    if end <= start or end - start != len(synthetic_value.encode("utf-8")):
        raise ContractError("ATOM_POSITION_INVALID")
    return {
        "atom_id": atom_id,
        "kind": kind,
        "occurrence_id": occurrence_id,
        "occurrence_index": occurrence_index,
        "position_end": end,
        "position_policy": atom["position_policy"],
        "position_start": start,
        "provenance": atom["provenance"],
        "synthetic_value": synthetic_value,
    }


def _validate_expected_atoms(
    value: Any,
    registry: _IdentityRegistry,
    sample_id: str,
    atom_owners: Dict[str, str],
) -> Dict[str, Dict[str, Any]]:
    atoms: Dict[str, Dict[str, Any]] = {}
    definitions: Dict[str, Tuple[str, str]] = {}
    indexes: Dict[str, Set[int]] = {}
    spans: List[Tuple[int, int]] = []
    for raw_atom in _require_list(value):
        atom = _validate_atom_shape(raw_atom)
        atom_id = atom["atom_id"]
        owner = atom_owners.get(atom_id)
        if owner is None:
            registry.define(atom_id, "atom")
            atom_owners[atom_id] = sample_id
        elif owner != sample_id:
            raise ContractError("DUPLICATE_OPAQUE_ID")
        definition = (atom["kind"], atom["synthetic_value"])
        previous_definition = definitions.setdefault(atom_id, definition)
        if definition[0] != previous_definition[0]:
            raise ContractError("ATOM_KIND_MUTATION")
        if definition[1] != previous_definition[1]:
            raise ContractError("ATOM_VALUE_MUTATION")
        occurrence_id = registry.define(atom["occurrence_id"], "occurrence")
        atoms[occurrence_id] = atom
        atom_indexes = indexes.setdefault(atom_id, set())
        if atom["occurrence_index"] in atom_indexes:
            raise ContractError("ATOM_MULTIPLICITY_MISMATCH")
        atom_indexes.add(atom["occurrence_index"])
        spans.append((atom["position_start"], atom["position_end"]))
    if not atoms:
        raise ContractError("ATOM_SET_EMPTY")
    for atom_id, observed_indexes in indexes.items():
        if observed_indexes != set(range(len(observed_indexes))):
            raise ContractError("ATOM_MULTIPLICITY_MISMATCH")
    ordered_spans = sorted(spans)
    if any(
        ordered_spans[index][0] < ordered_spans[index - 1][1]
        for index in range(1, len(ordered_spans))
    ):
        raise ContractError("ATOM_POSITION_INVALID")
    return atoms


def _validate_corpus(
    value: Any, registry: _IdentityRegistry
) -> Tuple[Dict[str, Dict[str, Any]], int, int]:
    corpus = _require_object(
        value,
        ("corpus_class", "corpus_version", "generation", "samples", "splits"),
    )
    if corpus["corpus_class"] != "synthetic":
        raise ContractError("NON_SYNTHETIC_CORPUS_FORBIDDEN")
    if _require_version(corpus["corpus_version"]) != CORPUS_VERSION:
        raise ContractError("CORPUS_VERSION_UNSUPPORTED")
    if _require_int(corpus["generation"], minimum=1) != CORPUS_GENERATION:
        raise ContractError("CORPUS_GENERATION_MISMATCH")
    samples: Dict[str, Dict[str, Any]] = {}
    atom_owners: Dict[str, str] = {}
    for raw_sample in _require_list(corpus["samples"]):
        sample = _require_object(
            raw_sample,
            (
                "expected_atoms",
                "risk_class",
                "sample_id",
                "source_unit_cluster_id",
                "stratum",
            ),
        )
        sample_id = registry.define(sample["sample_id"], "sample")
        cluster_id = registry.define(
            sample["source_unit_cluster_id"],
            "source_unit_cluster",
            allow_same_role_repeat=True,
        )
        stratum = _require_string(sample["stratum"])
        if stratum not in STRATA:
            raise ContractError("UNKNOWN_STRATUM")
        risk_class = _require_string(sample["risk_class"])
        if risk_class not in RISK_CLASSES:
            raise ContractError("UNKNOWN_RISK_CLASS")
        if (
            risk_class == "auto_eligible_candidate"
            and stratum not in _AUTO_ELIGIBLE_STRATA
        ):
            raise ContractError("RISK_CLASS_STRATUM_MISMATCH")
        samples[sample_id] = {
            "atoms": _validate_expected_atoms(
                sample["expected_atoms"], registry, sample_id, atom_owners
            ),
            "cluster_id": cluster_id,
            "risk_class": risk_class,
            "split": None,
            "stratum": stratum,
        }
    if not samples:
        raise ContractError("CORPUS_EMPTY")
    splits = corpus["splits"]
    if type(splits) is not dict:
        raise ContractError("INVALID_TYPE")
    if any(key not in ("tuning", "holdout") for key in splits):
        raise ContractError("UNKNOWN_SPLIT")
    if set(splits) != {"tuning", "holdout"}:
        raise ContractError("MISSING_FIELD")
    members_by_split: Dict[str, Set[str]] = {}
    for split in ("tuning", "holdout"):
        members: Set[str] = set()
        for raw_id in _require_list(splits[split]):
            member = registry.reference(raw_id, "sample")
            if member in members:
                raise ContractError("DUPLICATE_OPAQUE_ID")
            members.add(member)
        members_by_split[split] = members
    if members_by_split["tuning"] & members_by_split["holdout"]:
        raise ContractError("CORPUS_SPLIT_OVERLAP")
    if members_by_split["tuning"] | members_by_split["holdout"] != set(samples):
        raise ContractError("SPLIT_MEMBERSHIP_INVALID")
    if not members_by_split["tuning"] or not members_by_split["holdout"]:
        raise ContractError("SPLIT_MEMBERSHIP_INVALID")
    cluster_splits: Dict[str, str] = {}
    for split, members in members_by_split.items():
        for member in members:
            samples[member]["split"] = split
            cluster = samples[member]["cluster_id"]
            previous = cluster_splits.setdefault(cluster, split)
            if previous != split:
                raise ContractError("CORPUS_SPLIT_OVERLAP")
    return samples, len(members_by_split["tuning"]), len(members_by_split["holdout"])


def _validate_synthetic_corpus_freeze(value: Any) -> None:
    payload = _canonical_public_json(value)
    calculated = hashlib.sha256(
        _SYNTHETIC_CORPUS_DOMAIN
        + len(payload).to_bytes(8, "big")
        + payload
    ).hexdigest()
    if (
        payload != _EXPECTED_SYNTHETIC_CORPUS_BYTES
        or calculated != SYNTHETIC_CORPUS_SHA256
    ):
        raise ContractError("CORPUS_DEFINITION_MISMATCH")


def _validate_observed_atoms(
    value: Any, expected: Mapping[str, Mapping[str, Any]]
) -> None:
    observed: Dict[str, Dict[str, Any]] = {}
    for raw_atom in _require_list(value):
        atom = _validate_atom_shape(raw_atom)
        occurrence_id = atom["occurrence_id"]
        if occurrence_id in observed:
            raise ContractError("ATOM_OCCURRENCE_DUPLICATE")
        observed[occurrence_id] = atom
    missing = set(expected) - set(observed)
    extra = set(observed) - set(expected)
    if missing:
        raise ContractError("ATOM_MISSING")
    if extra:
        raise ContractError("ATOM_EXTRA")
    for occurrence_id, expected_atom in expected.items():
        observed_atom = observed[occurrence_id]
        if observed_atom["atom_id"] != expected_atom["atom_id"]:
            raise ContractError("ATOM_MULTIPLICITY_MISMATCH")
        if observed_atom["kind"] != expected_atom["kind"]:
            raise ContractError("ATOM_KIND_MUTATION")
        if observed_atom["synthetic_value"] != expected_atom["synthetic_value"]:
            raise ContractError("ATOM_VALUE_MUTATION")
        if observed_atom["occurrence_index"] != expected_atom["occurrence_index"]:
            raise ContractError("ATOM_MULTIPLICITY_MISMATCH")
        if any(
            observed_atom[field] != expected_atom[field]
            for field in ("position_policy", "position_start", "position_end")
        ):
            raise ContractError("ATOM_POSITION_MUTATION")
        if observed_atom["provenance"] != expected_atom["provenance"]:
            raise ContractError("ATOM_MUTATION")


def _validate_dimension_records(value: Any) -> Dict[str, str]:
    observed: Dict[str, str] = {}
    for raw_record in _require_list(value):
        record = _require_object(raw_record, ("dimension", "status"))
        dimension = _require_string(record["dimension"])
        if dimension not in QUALITY_DIMENSIONS:
            raise ContractError("UNKNOWN_DIMENSION")
        if dimension in observed:
            raise ContractError("DUPLICATE_DIMENSION_RECORD")
        status = _require_string(record["status"])
        if status not in _DIMENSION_STATUSES:
            raise ContractError("DIMENSION_STATUS_INVALID")
        if dimension == "schema_atom_stability" and status not in (
            "not_evaluated",
            "synthetic_conformant",
            "synthetic_nonconformant",
        ):
            raise ContractError("DIMENSION_STATUS_INVALID")
        if dimension != "schema_atom_stability" and status.startswith("synthetic_"):
            raise ContractError("DIMENSION_STATUS_INVALID")
        observed[dimension] = status
    if set(observed) != QUALITY_DIMENSIONS:
        raise ContractError("MISSING_DIMENSION_RECORD")
    return observed


def _validate_result_accounting(value: Any) -> Dict[str, int]:
    accounting = _require_object(value, _ACCOUNTING_FIELDS)
    for field in _ACCOUNTING_FIELDS:
        _require_int(accounting[field], minimum=0)
    if accounting["repair_success_count"] + accounting["repair_failure_count"] != accounting["repair_attempt_count"]:
        raise ContractError("REPAIR_ACCOUNTING_INVALID")
    if accounting["human_fallback_count"] + accounting["model_fallback_count"] != accounting["fallback_attempt_count"]:
        raise ContractError("FALLBACK_ACCOUNTING_INVALID")
    if accounting["initial_attempt_count"] > 1 or accounting["terminal_failure_count"] > 1:
        raise ContractError("ACCOUNTING_COUNT_EXCEEDS_COVERAGE")
    if accounting["retry_attempt_count"] or accounting["model_call_count"] > 1:
        raise ContractError("RETRY_ACCOUNTING_INVALID")
    if any(
        accounting[field] > accounting["model_call_count"]
        for field in (
            "cold_latency_observation_count",
            "memory_observation_count",
            "warm_latency_observation_count",
        )
    ):
        raise ContractError("ACCOUNTING_COUNT_EXCEEDS_COVERAGE")
    return accounting


def _validate_lane_accounting(
    lane: str, terminal_status: str, accounting: Mapping[str, int]
) -> None:
    repair_fields = (
        "repair_attempt_count",
        "repair_failure_count",
        "repair_success_count",
    )
    fallback_fields = (
        "fallback_attempt_count",
        "human_fallback_count",
        "model_fallback_count",
    )
    if lane == "primary":
        if any(accounting[field] for field in repair_fields):
            raise ContractError("REPAIR_ACCOUNTING_INVALID")
        if any(accounting[field] for field in fallback_fields):
            raise ContractError("FALLBACK_ACCOUNTING_INVALID")
        if terminal_status == "not_applicable":
            if any(accounting.values()):
                raise ContractError("INITIAL_ACCOUNTING_INVALID")
        elif accounting["initial_attempt_count"] != 1:
            raise ContractError("INITIAL_ACCOUNTING_INVALID")
        return
    if accounting["initial_attempt_count"]:
        raise ContractError("INITIAL_ACCOUNTING_INVALID")
    if lane == "repair":
        if any(accounting[field] for field in fallback_fields):
            raise ContractError("FALLBACK_ACCOUNTING_INVALID")
        if terminal_status == "not_applicable":
            raise ContractError("REPAIR_ACCOUNTING_INVALID")
        expected_success = 1 if terminal_status == "success" else 0
        expected_failure = 1 if terminal_status == "controlled_failure" else 0
        if (
            accounting["repair_attempt_count"] != 1
            or accounting["repair_success_count"] != expected_success
            or accounting["repair_failure_count"] != expected_failure
        ):
            raise ContractError("REPAIR_ACCOUNTING_INVALID")
        return
    if any(accounting[field] for field in repair_fields):
        raise ContractError("REPAIR_ACCOUNTING_INVALID")
    if terminal_status == "not_applicable":
        raise ContractError("FALLBACK_ACCOUNTING_INVALID")
    if (
        accounting["fallback_attempt_count"] != 1
        or accounting["human_fallback_count"]
        + accounting["model_fallback_count"]
        != 1
    ):
        raise ContractError("FALLBACK_ACCOUNTING_INVALID")
    if accounting["human_fallback_count"] and accounting["model_call_count"]:
        raise ContractError("FALLBACK_ACCOUNTING_INVALID")


def _validate_results(
    value: Any,
    registry: _IdentityRegistry,
    samples: Mapping[str, Mapping[str, Any]],
    candidates: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    assignments: Set[Tuple[Any, ...]] = set()
    for raw_result in _require_list(value):
        result = _require_object(
            raw_result,
            _RESULT_FIELDS,
        )
        result_id = registry.define(result["result_id"], "result")
        sample_id = registry.reference(result["sample_id"], "sample")
        candidate_id = registry.reference(result["candidate_id"], "candidate")
        if sample_id not in samples or candidate_id not in candidates:
            raise ContractError("REFERENCE_NOT_FOUND")
        if _require_version(result["profile_version"]) != PROFILE_VERSION:
            raise ContractError("PROFILE_VERSION_UNSUPPORTED")
        if _require_int(result["profile_generation"], minimum=1) != PROFILE_GENERATION:
            raise ContractError("PROFILE_GENERATION_MISMATCH")
        if _require_int(result["corpus_generation"], minimum=1) != CORPUS_GENERATION:
            raise ContractError("CORPUS_GENERATION_MISMATCH")
        if _require_int(result["protocol_generation"], minimum=1) != PROTOCOL_GENERATION:
            raise ContractError("PROTOCOL_GENERATION_MISMATCH")
        lane = _require_string(result["experiment_lane"])
        stage = _require_string(result["attempt_stage"])
        if (lane, stage) not in _LANE_STAGE_PAIRS:
            raise ContractError("ASSIGNMENT_STAGE_INVALID")
        attempt_index = _require_int(result["attempt_index"], minimum=0)
        assignment = (
            candidate_id,
            sample_id,
            result["profile_version"],
            result["profile_generation"],
            lane,
            stage,
            attempt_index,
        )
        if assignment in assignments:
            raise ContractError("ASSIGNMENT_DUPLICATE")
        assignments.add(assignment)
        if lane == "primary" and attempt_index != 0:
            raise ContractError("ASSIGNMENT_EXTRA")
        if lane == "primary":
            if result["initial_result_id"] is not None:
                raise ContractError("ASSIGNMENT_STAGE_INVALID")
        else:
            _require_uuid(result["initial_result_id"])
        technical = _require_string(result["technical_conformance"])
        if technical not in _TECHNICAL_CONFORMANCE_STATUSES:
            raise ContractError("TECHNICAL_CONFORMANCE_INVALID")
        editorial = _require_string(result["editorial_status"])
        if editorial not in _EDITORIAL_STATUSES:
            raise ContractError("EDITORIAL_STATUS_INVALID")
        terminal_status = _require_string(result["terminal_status"])
        if terminal_status not in _TERMINAL_STATUSES:
            raise ContractError("TERMINAL_STATUS_INVALID")
        dimensions = _validate_dimension_records(result["dimension_records"])
        accounting = _validate_result_accounting(result["accounting"])
        if technical == "not_observed":
            if _require_list(result["observed_atoms"]):
                raise ContractError("TECHNICAL_CONFORMANCE_MISMATCH")
            if dimensions["schema_atom_stability"] != "not_evaluated":
                raise ContractError("DIMENSION_STATUS_INVALID")
            if terminal_status != "controlled_failure":
                raise ContractError("TERMINAL_STATUS_MISMATCH")
            if any(
                dimensions[dimension] != "not_evaluated"
                for dimension in QUALITY_DIMENSIONS - {"schema_atom_stability"}
            ):
                raise ContractError("HUMAN_QUALITY_WITHOUT_OUTPUT")
        else:
            _validate_observed_atoms(
                result["observed_atoms"], samples[sample_id]["atoms"]
            )
            expected_d1 = (
                "synthetic_conformant"
                if technical == "synthetic_conformant"
                else "synthetic_nonconformant"
            )
            if dimensions["schema_atom_stability"] != expected_d1:
                raise ContractError("DIMENSION_STATUS_INVALID")
            if technical == "synthetic_nonconformant":
                raise ContractError("TECHNICAL_CONFORMANCE_MISMATCH")
            if terminal_status == "controlled_failure":
                raise ContractError("TERMINAL_STATUS_MISMATCH")
        expected_terminal_failures = 1 if terminal_status == "controlled_failure" else 0
        if accounting["terminal_failure_count"] != expected_terminal_failures:
            raise ContractError("TERMINAL_ACCOUNTING_INVALID")
        if terminal_status == "success" and accounting["model_call_count"] != 1:
            raise ContractError("TERMINAL_ACCOUNTING_INVALID")
        _validate_lane_accounting(lane, terminal_status, accounting)
        results[result_id] = {
            "accounting": accounting,
            "assignment": assignment,
            "candidate_id": candidate_id,
            "dimensions": dimensions,
            "editorial_status": editorial,
            "initial_result_id": result["initial_result_id"],
            "lane": lane,
            "sample_id": sample_id,
            "stage": stage,
            "technical_conformance": technical,
            "terminal_status": terminal_status,
        }
    if not results:
        raise ContractError("RESULT_SET_EMPTY")
    for result_id, result in results.items():
        if result["lane"] == "primary":
            continue
        initial_id = result["initial_result_id"]
        initial = results.get(initial_id)
        if initial is None or initial["lane"] != "primary":
            raise ContractError("ASSIGNMENT_INITIAL_REFERENCE_INVALID")
        if (
            initial["candidate_id"] != result["candidate_id"]
            or initial["sample_id"] != result["sample_id"]
        ):
            raise ContractError("ASSIGNMENT_INITIAL_REFERENCE_INVALID")
    return results


def _validate_findings(
    value: Any,
    registry: _IdentityRegistry,
    results: Mapping[str, Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, int]:
    findings: List[Dict[str, Any]] = []
    critical_count = 0
    review_count = 0
    for raw_finding in _require_list(value):
        finding = _require_object(
            raw_finding,
            _FINDING_FIELDS,
        )
        registry.define(finding["finding_id"], "finding")
        result_id = registry.reference(finding["result_id"], "result")
        category = _require_string(finding["category"])
        if category not in FINDING_CATEGORIES:
            raise ContractError("UNKNOWN_CATEGORY")
        dimension = _require_string(finding["dimension"])
        if dimension not in QUALITY_DIMENSIONS:
            raise ContractError("UNKNOWN_DIMENSION")
        if dimension not in FINDING_DIMENSIONS[category]:
            raise ContractError("FINDING_DIMENSION_MISMATCH")
        severity = _require_string(finding["severity"])
        if severity not in SEVERITIES:
            raise ContractError("UNKNOWN_SEVERITY")
        if category in CRITICAL_CATEGORIES and severity != "critical":
            raise ContractError("CRITICAL_SEVERITY_REQUIRED")
        human_reviewers: List[str] = []
        model_review_count = 0
        for raw_review in _require_list(finding["reviews"]):
            review = _require_object(
                raw_review,
                _REVIEW_FIELDS,
            )
            registry.define(review["review_id"], "review")
            role = _require_string(review["reviewer_role"])
            reviewer_id = registry.reviewer(review["reviewer_id"], role)
            credit = _require_string(review["review_credit"])
            if credit not in REVIEW_CREDITS:
                raise ContractError("UNKNOWN_REVIEW_CREDIT")
            if role == "model_reviewer":
                model_review_count += 1
                if credit == "human":
                    raise ContractError("MODEL_REVIEW_NOT_HUMAN")
            elif credit != "human":
                raise ContractError("REVIEW_CREDIT_MISMATCH")
            stage = _require_string(review["review_stage"])
            if stage not in ("adjudication", "initial"):
                raise ContractError("UNKNOWN_REVIEW_STAGE")
            decision = _require_string(review["decision"])
            if decision not in ("confirmed", "dismissed"):
                raise ContractError("UNKNOWN_REVIEW_DECISION")
            if role == "human_reviewer" and stage == "initial" and decision == "confirmed":
                human_reviewers.append(reviewer_id)
            review_count += 1
        mandatory = severity in ("high", "critical") or category in CRITICAL_CATEGORIES
        if mandatory and not human_reviewers:
            if model_review_count:
                raise ContractError("MODEL_REVIEW_NOT_HUMAN")
            raise ContractError("MANDATORY_HUMAN_EVIDENCE_MISSING")
        if severity == "critical" or category in CRITICAL_CATEGORIES:
            critical_count += 1
            if len(human_reviewers) != len(set(human_reviewers)):
                raise ContractError("DUPLICATE_CRITICAL_REVIEWER")
            if len(set(human_reviewers)) < 2:
                raise ContractError("CRITICAL_REVIEW_COUNT_INSUFFICIENT")
        findings.append(
            {
                "category": category,
                "dimension": dimension,
                "result_id": result_id,
                "severity": severity,
            }
        )
    return findings, critical_count, review_count


def _validate_human_ground_truth(
    value: Any,
    registry: _IdentityRegistry,
    results: Mapping[str, Mapping[str, Any]],
    samples: Mapping[str, Mapping[str, Any]],
) -> Dict[Tuple[str, str], Set[str]]:
    records: Dict[Tuple[str, str], Set[str]] = {}
    statuses: Dict[Tuple[str, str], Set[str]] = {}
    for raw_record in _require_list(value):
        record = _require_object(
            raw_record,
            _HUMAN_GROUND_TRUTH_FIELDS,
        )
        registry.define(record["ground_truth_id"], "human_ground_truth")
        result_id = registry.reference(record["result_id"], "result")
        dimension = _require_string(record["dimension"])
        if dimension not in QUALITY_DIMENSIONS - {"schema_atom_stability"}:
            raise ContractError("HUMAN_GROUND_TRUTH_DIMENSION_INVALID")
        role = _require_string(record["reviewer_role"])
        reviewer_id = registry.reviewer(record["reviewer_id"], role)
        if role != "human_reviewer":
            raise ContractError("MODEL_REVIEW_NOT_HUMAN")
        if record["review_stage"] != "initial":
            raise ContractError("HUMAN_GROUND_TRUTH_STAGE_INVALID")
        status = _require_string(record["status"])
        if status not in ("human_fail", "human_pass", "not_applicable"):
            raise ContractError("HUMAN_GROUND_TRUTH_STATUS_INVALID")
        if status == "not_applicable":
            if record["applicability_reason"] != "frozen_not_applicable":
                raise ContractError("HUMAN_GROUND_TRUTH_STATUS_INVALID")
        elif record["applicability_reason"] is not None:
            raise ContractError("HUMAN_GROUND_TRUTH_STATUS_INVALID")
        key = (result_id, dimension)
        reviewers = records.setdefault(key, set())
        if reviewer_id in reviewers:
            raise ContractError("DUPLICATE_HUMAN_GROUND_TRUTH")
        reviewers.add(reviewer_id)
        statuses.setdefault(key, set()).add(status)
    for result_id, result in results.items():
        sample = samples[result["sample_id"]]
        has_output = result["terminal_status"] != "controlled_failure"
        if not has_output and any(key[0] == result_id for key in records):
            raise ContractError("HUMAN_GROUND_TRUTH_WITHOUT_OUTPUT")
        if sample["split"] == "holdout" and has_output:
            for dimension in QUALITY_DIMENSIONS - {"schema_atom_stability"}:
                if not records.get((result_id, dimension)):
                    raise ContractError("HOLDOUT_GROUND_TRUTH_MISSING")
        if has_output and sample["risk_class"] == "critical_risk":
            for dimension in QUALITY_DIMENSIONS - {"schema_atom_stability"}:
                if len(records.get((result_id, dimension), set())) < 2:
                    raise ContractError("CRITICAL_REVIEW_COUNT_INSUFFICIENT")
        for dimension in QUALITY_DIMENSIONS - {"schema_atom_stability"}:
            key = (result_id, dimension)
            if key not in statuses:
                if result["dimensions"][dimension] != "not_evaluated":
                    raise ContractError("MANDATORY_HUMAN_EVIDENCE_MISSING")
                continue
            dimension_status = result["dimensions"][dimension]
            observed = statuses[key]
            expected_status = (
                "human_fail"
                if "human_fail" in observed or len(observed) > 1
                else next(iter(observed))
            )
            if dimension_status != expected_status:
                raise ContractError("HUMAN_GROUND_TRUTH_STATUS_MISMATCH")
    return records


def _validate_benchmark_state(value: Any) -> Dict[str, Any]:
    if type(value) is not dict:
        raise ContractError("INVALID_TYPE")
    if any(field in value for field in ("baseline", "m1b_verdict", "winner")):
        raise ContractError("PREMATURE_SELECTION")
    state = _require_object(value, ("complete", "report_kind"))
    complete = _require_bool(state["complete"])
    report_kind = _require_string(state["report_kind"])
    if (complete, report_kind) not in _BENCHMARK_STATES:
        raise ContractError("BENCHMARK_STATE_INVALID")
    return state


def _validate_acceptance(
    results: Mapping[str, Mapping[str, Any]],
    findings: Sequence[Mapping[str, Any]],
    ground_truth: Mapping[Tuple[str, str], Set[str]],
    samples: Mapping[str, Mapping[str, Any]],
    benchmark_state: Mapping[str, Any],
) -> None:
    risky_results = {
        finding["result_id"]
        for finding in findings
        if finding["severity"] in ("high", "critical")
    }
    human_dimensions = QUALITY_DIMENSIONS - {"schema_atom_stability"}
    for result_id, result in results.items():
        if result["editorial_status"] != "editorially_approved":
            continue
        if result["technical_conformance"] != "synthetic_conformant":
            raise ContractError("TECHNICAL_CONFORMANCE_REQUIRED_FOR_APPROVAL")
        if result_id in risky_results:
            raise ContractError("HIGH_RISK_EDITORIAL_APPROVAL")
        if any(
            result["dimensions"][dimension] == "not_evaluated"
            for dimension in human_dimensions
        ):
            raise ContractError("EDITORIAL_APPROVAL_WITH_UNEVALUATED_DIMENSION")
        if any(
            result["dimensions"][dimension]
            not in ("human_pass", "not_applicable")
            for dimension in human_dimensions
        ):
            raise ContractError("EDITORIAL_APPROVAL_WITH_FAILED_DIMENSION")
        if any(not ground_truth.get((result_id, dimension)) for dimension in human_dimensions):
            raise ContractError("MANDATORY_HUMAN_EVIDENCE_MISSING")
        sample = samples[result["sample_id"]]
        if sample["risk_class"] == "critical_risk" and any(
            len(ground_truth.get((result_id, dimension), set())) < 2
            for dimension in human_dimensions
        ):
            raise ContractError("CRITICAL_REVIEW_COUNT_INSUFFICIENT")
        if not benchmark_state["complete"]:
            raise ContractError("EDITORIAL_APPROVAL_INCOMPLETE_BENCHMARK")
    if benchmark_state["complete"]:
        for result_id, result in results.items():
            sample = samples[result["sample_id"]]
            if (
                result["terminal_status"] != "controlled_failure"
                and sample["risk_class"] in ("critical_risk", "mandatory_human")
                and any(
                    not ground_truth.get((result_id, dimension))
                    for dimension in human_dimensions
                )
            ):
                raise ContractError("MANDATORY_HUMAN_EVIDENCE_MISSING")


def _validate_execution_policy(
    results: Mapping[str, Mapping[str, Any]],
    provider_policy: Mapping[str, Any],
) -> None:
    if not provider_policy["fallback"] and any(
        result["lane"] == "fallback" for result in results.values()
    ):
        raise ContractError("FALLBACK_ACCOUNTING_INVALID")


def _validate_coverage(
    value: Any,
    results: Mapping[str, Mapping[str, Any]],
    candidates: Mapping[str, Mapping[str, Any]],
    samples: Mapping[str, Mapping[str, Any]],
    benchmark_state: Mapping[str, Any],
) -> None:
    coverage = _require_object(
        value,
        _COVERAGE_FIELDS,
    )
    primary = [
        result
        for result in results.values()
        if result["lane"] == "primary" and result["stage"] == "initial"
    ]
    per_candidate = {candidate_id: 0 for candidate_id in candidates}
    per_stratum = {stratum: 0 for stratum in STRATA}
    pairs: Set[Tuple[str, str]] = set()
    for result in primary:
        per_candidate[result["candidate_id"]] += 1
        per_stratum[samples[result["sample_id"]]["stratum"]] += 1
        pairs.add((result["candidate_id"], result["sample_id"]))
    if any(count == 0 for count in per_candidate.values()):
        raise ContractError("CANDIDATE_COVERAGE_MISSING")
    required_count = len(candidates) * len(samples)
    if _require_int(coverage["required_primary_assignment_count"], minimum=0) != required_count:
        raise ContractError("COVERAGE_COUNT_MISMATCH")
    if _require_int(coverage["declared_primary_assignment_count"], minimum=0) != len(primary):
        raise ContractError("COVERAGE_COUNT_MISMATCH")

    candidate_rows: Dict[str, int] = {}
    for raw_row in _require_list(coverage["per_candidate"]):
        row = _require_object(raw_row, ("candidate_id", "primary_result_count"))
        candidate_id = _require_uuid(row["candidate_id"])
        if candidate_id not in candidates or candidate_id in candidate_rows:
            raise ContractError("COVERAGE_COUNT_MISMATCH")
        candidate_rows[candidate_id] = _require_int(row["primary_result_count"], minimum=0)
    if candidate_rows != per_candidate:
        raise ContractError("COVERAGE_COUNT_MISMATCH")
    stratum_rows: Dict[str, int] = {}
    for raw_row in _require_list(coverage["per_stratum"]):
        row = _require_object(raw_row, ("primary_result_count", "stratum"))
        stratum = _require_string(row["stratum"])
        if stratum not in STRATA or stratum in stratum_rows:
            raise ContractError("COVERAGE_COUNT_MISMATCH")
        stratum_rows[stratum] = _require_int(row["primary_result_count"], minimum=0)
    if stratum_rows != per_stratum:
        raise ContractError("COVERAGE_COUNT_MISMATCH")
    if benchmark_state["complete"]:
        expected_pairs = {
            (candidate_id, sample_id)
            for candidate_id in candidates
            for sample_id in samples
        }
        if pairs != expected_pairs or len(primary) != required_count:
            raise ContractError("COVERAGE_INCOMPLETE")


def _validate_aggregate_report(
    value: Any,
    *,
    candidates: Mapping[str, Mapping[str, Any]],
    samples: Mapping[str, Mapping[str, Any]],
    tuning_count: int,
    holdout_count: int,
    results: Mapping[str, Mapping[str, Any]],
    finding_count: int,
    critical_count: int,
    review_count: int,
    ground_truth_count: int,
    provider_policy: Mapping[str, Any],
) -> None:
    fixed_fields = (
        "candidate_count",
        "conformance_result_count",
        "critical_finding_count",
        "editorially_approved_count",
        "editorially_rejected_count",
        "finding_count",
        "holdout_sample_count",
        "human_ground_truth_count",
        "quality_dimensions",
        "redaction",
        "review_count",
        "sample_count",
        "technical_conformant_count",
        "tuning_sample_count",
    )
    report = _require_object(value, fixed_fields + _ACCOUNTING_FIELDS)
    if report["redaction"] != "controlled_aggregates_only":
        raise ContractError("REPORT_REDACTION_INVALID")
    dimensions = _require_list(report["quality_dimensions"])
    if (
        any(type(item) is not str for item in dimensions)
        or len(dimensions) != len(set(dimensions))
        or set(dimensions) != QUALITY_DIMENSIONS
    ):
        raise ContractError("QUALITY_DIMENSIONS_INVALID")
    sums = {field: sum(result["accounting"][field] for result in results.values()) for field in _ACCOUNTING_FIELDS}
    if sums["repair_success_count"] + sums["repair_failure_count"] != sums["repair_attempt_count"]:
        raise ContractError("REPAIR_ACCOUNTING_INVALID")
    if sums["human_fallback_count"] + sums["model_fallback_count"] != sums["fallback_attempt_count"]:
        raise ContractError("FALLBACK_ACCOUNTING_INVALID")
    if sums["retry_attempt_count"]:
        raise ContractError("RETRY_ACCOUNTING_INVALID")
    if not provider_policy["fallback"] and any(
        sums[field]
        for field in ("fallback_attempt_count", "human_fallback_count", "model_fallback_count")
    ):
        raise ContractError("FALLBACK_ACCOUNTING_INVALID")
    if provider_policy["residency_status"] == "not_probed" and any(
        sums[field]
        for field in (
            "cold_latency_observation_count",
            "initial_attempt_count",
            "memory_observation_count",
            "model_call_count",
            "repair_attempt_count",
            "retry_attempt_count",
            "warm_latency_observation_count",
        )
    ):
        raise ContractError("LIVE_OBSERVATION_WITHOUT_RESIDENCY")
    if any(sums[field] > len(results) for field in _ACCOUNTING_FIELDS):
        raise ContractError("ACCOUNTING_COUNT_EXCEEDS_COVERAGE")
    expected: Dict[str, int] = {
        "candidate_count": len(candidates),
        "conformance_result_count": len(results),
        "critical_finding_count": critical_count,
        "editorially_approved_count": sum(
            result["editorial_status"] == "editorially_approved" for result in results.values()
        ),
        "editorially_rejected_count": sum(
            result["editorial_status"] == "editorially_rejected" for result in results.values()
        ),
        "finding_count": finding_count,
        "holdout_sample_count": holdout_count,
        "human_ground_truth_count": ground_truth_count,
        "review_count": review_count,
        "sample_count": len(samples),
        "technical_conformant_count": sum(
            result["technical_conformance"] == "synthetic_conformant" for result in results.values()
        ),
        "tuning_sample_count": tuning_count,
    }
    expected.update(sums)
    for field, expected_value in expected.items():
        if _require_int(report[field], minimum=0) != expected_value:
            if field in _ACCOUNTING_FIELDS:
                raise ContractError("AGGREGATE_ACCOUNTING_MISMATCH")
            raise ContractError("AGGREGATE_COUNT_MISMATCH")


def validate_document(document: Any) -> Dict[str, int]:
    """Validate one already-parsed synthetic contract document."""

    _scan_for_forbidden_fields(document)
    root = _require_object(
        document,
        _ROOT_FIELDS,
        missing_codes={"schema_version": "MISSING_SCHEMA_VERSION"},
    )
    if root["schema_version"] != DOCUMENT_SCHEMA:
        raise ContractError("SCHEMA_VERSION_UNSUPPORTED")
    definition_states = _validate_definition_bundle(root["definition_bundle"])
    _validate_protocol(root["protocol"])
    provider_policy = _validate_provider_policy(root["provider_policy"])
    _validate_request_boundary(root["request_boundary"])
    registry = _IdentityRegistry()
    candidates = _validate_candidates(root["candidate_profiles"], registry)
    samples, tuning_count, holdout_count = _validate_corpus(root["corpus"], registry)
    results = _validate_results(
        root["conformance_results"], registry, samples, candidates
    )
    _validate_synthetic_corpus_freeze(root["corpus"])
    findings, critical_count, review_count = _validate_findings(
        root["findings"], registry, results
    )
    ground_truth = _validate_human_ground_truth(
        root["human_ground_truth"], registry, results, samples
    )
    benchmark_state = _validate_benchmark_state(root["benchmark_state"])
    _validate_coverage(
        root["coverage"], results, candidates, samples, benchmark_state
    )
    _validate_acceptance(
        results, findings, ground_truth, samples, benchmark_state
    )
    _validate_execution_policy(results, provider_policy)
    _validate_aggregate_report(
        root["aggregate_report"],
        candidates=candidates,
        samples=samples,
        tuning_count=tuning_count,
        holdout_count=holdout_count,
        results=results,
        finding_count=len(findings),
        critical_count=critical_count,
        review_count=review_count,
        ground_truth_count=len(root["human_ground_truth"]),
        provider_policy=provider_policy,
    )
    if benchmark_state["complete"] and any(
        state != "owner_accepted" for state in definition_states
    ):
        raise ContractError("OWNER_DECISION_REQUIRED")
    return {
        "candidates": len(candidates),
        "findings": len(findings),
        "holdout_samples": holdout_count,
        "human_ground_truth": len(root["human_ground_truth"]),
        "results": len(results),
        "reviews": review_count,
        "samples": len(samples),
        "tuning_samples": tuning_count,
    }


def validate_json_bytes(data: bytes) -> Dict[str, Any]:
    try:
        document = parse_json_bytes(data)
        return _result("ok", counts=validate_document(document))
    except ContractError as error:
        return _result("error", code=error.code)
    except BaseException:
        return _result("error", code="UNEXPECTED_FAILURE")


def _validate_expected(value: Any) -> None:
    expected = _require_object(value, ("codes", "status"))
    if expected["status"] not in ("ok", "error"):
        raise ContractError("FIXTURE_INVALID")
    codes = _require_list(expected["codes"])
    if any(type(code) is not str or _CODE.fullmatch(code) is None for code in codes):
        raise ContractError("FIXTURE_INVALID")
    if (expected["status"] == "ok" and codes) or (
        expected["status"] == "error" and len(codes) != 1
    ):
        raise ContractError("FIXTURE_INVALID")


def _patch_target(root: Any, target: Sequence[Any]) -> Tuple[Any, Any]:
    if type(target) is not list or not target:
        raise ContractError("FIXTURE_INVALID")
    current = root
    for component in target[:-1]:
        if type(component) not in (str, int) or type(component) is bool:
            raise ContractError("FIXTURE_INVALID")
        try:
            if type(current) is dict and type(component) is str:
                current = current[component]
            elif type(current) is list and type(component) is int:
                current = current[component]
            else:
                raise ContractError("FIXTURE_INVALID")
        except (KeyError, IndexError):
            raise ContractError("FIXTURE_INVALID")
    leaf = target[-1]
    if type(leaf) not in (str, int) or type(leaf) is bool:
        raise ContractError("FIXTURE_INVALID")
    return current, leaf


def _apply_patches(base: Any, patches: Any) -> Any:
    document = copy.deepcopy(base)
    for raw_patch in _require_list(patches):
        if type(raw_patch) is not dict:
            raise ContractError("FIXTURE_INVALID")
        operation = raw_patch.get("operation")
        if operation in ("set", "append"):
            patch = _require_object(raw_patch, ("operation", "target", "value"))
        elif operation == "copy_append":
            patch = _require_object(raw_patch, ("operation", "source", "target"))
        elif operation == "delete":
            patch = _require_object(raw_patch, ("operation", "target"))
        else:
            raise ContractError("FIXTURE_INVALID")
        if operation == "copy_append":
            source = document
            for component in patch["source"]:
                if type(component) not in (str, int) or type(component) is bool:
                    raise ContractError("FIXTURE_INVALID")
                try:
                    source = source[component]
                except (KeyError, IndexError, TypeError):
                    raise ContractError("FIXTURE_INVALID")
            target = document
            for component in patch["target"]:
                if type(component) not in (str, int) or type(component) is bool:
                    raise ContractError("FIXTURE_INVALID")
                try:
                    target = target[component]
                except (KeyError, IndexError, TypeError):
                    raise ContractError("FIXTURE_INVALID")
            if type(target) is not list:
                raise ContractError("FIXTURE_INVALID")
            target.append(copy.deepcopy(source))
            continue
        if operation == "append":
            current = document
            for component in patch["target"]:
                if type(component) not in (str, int) or type(component) is bool:
                    raise ContractError("FIXTURE_INVALID")
                try:
                    current = current[component]
                except (KeyError, IndexError, TypeError):
                    raise ContractError("FIXTURE_INVALID")
            if type(current) is not list:
                raise ContractError("FIXTURE_INVALID")
            current.append(copy.deepcopy(patch["value"]))
            continue
        parent, leaf = _patch_target(document, patch["target"])
        try:
            if operation == "set":
                if type(parent) is dict and type(leaf) is str:
                    parent[leaf] = copy.deepcopy(patch["value"])
                elif type(parent) is list and type(leaf) is int:
                    parent[leaf] = copy.deepcopy(patch["value"])
                else:
                    raise ContractError("FIXTURE_INVALID")
            elif type(parent) is dict and type(leaf) is str:
                del parent[leaf]
            elif type(parent) is list and type(leaf) is int:
                del parent[leaf]
            else:
                raise ContractError("FIXTURE_INVALID")
        except (KeyError, IndexError):
            raise ContractError("FIXTURE_INVALID")
    return document


def _validate_fixture_manifest(value: Any) -> Dict[str, Any]:
    manifest = _require_object(value, ("base_document", "cases", "schema"))
    if manifest["schema"] != FIXTURE_SCHEMA:
        raise ContractError("FIXTURE_INVALID")
    if type(manifest["base_document"]) is not dict:
        raise ContractError("FIXTURE_INVALID")
    seen: Set[str] = set()
    for raw_case in _require_list(manifest["cases"]):
        if type(raw_case) is not dict:
            raise ContractError("FIXTURE_INVALID")
        if set(raw_case) == {"expected", "id", "patches"}:
            _require_list(raw_case["patches"])
        elif set(raw_case) == {"document_utf8", "expected", "id"}:
            _require_string(raw_case["document_utf8"])
        else:
            raise ContractError("FIXTURE_INVALID")
        case_id = _require_string(raw_case["id"])
        if _CASE_ID.fullmatch(case_id) is None or case_id in seen:
            raise ContractError("FIXTURE_INVALID")
        seen.add(case_id)
        _validate_expected(raw_case["expected"])
    if "positive" not in seen:
        raise ContractError("FIXTURE_INVALID")
    return manifest


def materialize_fixture_case(manifest: Any, case_id: str) -> bytes:
    manifest = _validate_fixture_manifest(manifest)
    if type(case_id) is not str or _CASE_ID.fullmatch(case_id) is None:
        raise ContractError("FIXTURE_CASE_NOT_FOUND")
    for case in manifest["cases"]:
        if case["id"] != case_id:
            continue
        if "document_utf8" in case:
            try:
                return case["document_utf8"].encode("utf-8", errors="strict")
            except UnicodeEncodeError:
                raise ContractError("FIXTURE_INVALID")
        document = _apply_patches(manifest["base_document"], case["patches"])
        return json.dumps(
            document,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    raise ContractError("FIXTURE_CASE_NOT_FOUND")


def validate_fixture_case(manifest: Any, case_id: str) -> Dict[str, Any]:
    try:
        return validate_json_bytes(materialize_fixture_case(manifest, case_id))
    except ContractError as error:
        return _result("error", code=error.code)
    except BaseException:
        return _result("error", code="UNEXPECTED_FAILURE")


def _execute(argv: Sequence[str]) -> Dict[str, Any]:
    try:
        if len(argv) == 2 and argv[0] == "validate":
            return validate_json_bytes(_read_explicit_file(argv[1]))
        if len(argv) == 3 and argv[0] == "validate-case":
            manifest = parse_json_bytes(_read_explicit_file(argv[1]))
            return validate_fixture_case(manifest, argv[2])
        raise ContractError("CLI_ARGUMENTS_INVALID")
    except ContractError as error:
        return _result("error", code=error.code)
    except BaseException:
        return _result("error", code="UNEXPECTED_FAILURE")


def _encode_result(result: Mapping[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                result,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
    except BaseException:
        return b'{"codes":["UNEXPECTED_FAILURE"],"counts":{"candidates":0,"findings":0,"holdout_samples":0,"human_ground_truth":0,"results":0,"reviews":0,"samples":0,"tuning_samples":0},"status":"error"}\n'


def main(argv: Optional[Sequence[str]] = None) -> int:
    result = _execute(tuple(sys.argv[1:] if argv is None else argv))
    try:
        sys.stdout.buffer.write(_encode_result(result))
        sys.stdout.buffer.flush()
    except BaseException:
        return 2
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
