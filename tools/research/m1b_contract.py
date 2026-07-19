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
import ipaddress
import json
import re
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple
from urllib.parse import urlsplit


DOCUMENT_SCHEMA = "m1b-synthetic-contract-v1"
FIXTURE_SCHEMA = "m1b-synthetic-contract-cases-v1"
MAX_INPUT_BYTES = 4 * 1024 * 1024

EXPECTED_CANDIDATES = frozenset(
    {
        "deepseek_r1_32b",
        "glm_4_7_flash",
        "gpt_oss_20b",
    }
)
SAMPLE_CATEGORIES = frozenset(
    {
        "synthetic_event",
        "synthetic_interface",
        "synthetic_narrative",
    }
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
        "atom_extra",
        "atom_missing",
        "atom_mutation",
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
        "atom_extra",
        "atom_missing",
        "atom_mutation",
        "critical_false_accept",
        "meaning_inversion",
        "negation_error",
        "number_error",
        "schema_violation",
    }
)
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
    "results",
    "reviews",
    "samples",
    "tuning_samples",
)


class ContractError(RuntimeError):
    """A controlled failure that never carries input content."""

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or _CODE.fullmatch(code) is None:
            code = "UNEXPECTED_FAILURE"
        self.code = code
        super().__init__(code)


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


def _define_uuid(value: Any, definitions: Set[str]) -> str:
    identifier = _require_uuid(value)
    if identifier in definitions:
        raise ContractError("DUPLICATE_OPAQUE_ID")
    definitions.add(identifier)
    return identifier


def _require_numeric_loopback_endpoint(value: Any) -> None:
    endpoint = _require_string(value)
    try:
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme != "http"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path != "/api"
            or parsed.query
            or parsed.fragment
            or parsed.hostname is None
            or parsed.port is None
        ):
            raise ValueError
        address = ipaddress.ip_address(parsed.hostname)
        if str(address) not in ("127.0.0.1", "::1"):
            raise ValueError
        canonical_netloc = (
            "[::1]:{0}".format(parsed.port)
            if str(address) == "::1"
            else "127.0.0.1:{0}".format(parsed.port)
        )
        if parsed.netloc != canonical_netloc:
            raise ValueError
    except (ValueError, TypeError):
        raise ContractError("ENDPOINT_NOT_NUMERIC_LOOPBACK")


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
    _require_int(protocol["generation"], minimum=1)
    _require_version(protocol["output_schema_version"])
    _require_version(protocol["prompt_version"])
    _require_version(protocol["protocol_version"])
    return protocol


def _validate_provider_policy(value: Any) -> None:
    policy = _require_object(
        value,
        (
            "auto_pull",
            "endpoint",
            "fallback",
            "numeric_loopback_only",
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


def _validate_runtime(value: Any) -> None:
    runtime = _require_object(
        value,
        (
            "lifecycle",
            "num_ctx",
            "output_token_limit",
            "retry_limit",
            "seed",
            "temperature_milli",
            "timeout_ms",
        ),
    )
    _require_int(runtime["num_ctx"], minimum=1)
    _require_int(runtime["output_token_limit"], minimum=1)
    _require_int(runtime["retry_limit"], minimum=0)
    _require_int(runtime["seed"], minimum=0)
    _require_int(runtime["temperature_milli"], minimum=0)
    _require_int(runtime["timeout_ms"], minimum=1)
    if runtime["lifecycle"] != "cold_and_warm_separate":
        raise ContractError("INVALID_PROFILE_VALUE")


def _validate_thinking_profile(value: Any) -> Tuple[str, str]:
    profile = _require_object(
        value,
        ("exception_status", "exception_version", "mode"),
    )
    mode = _require_string(profile["mode"])
    if mode not in THINKING_MODES:
        raise ContractError("INVALID_PROFILE_VALUE")
    status = _require_string(profile["exception_status"])
    if status == "none":
        if profile["exception_version"] is not None:
            raise ContractError("CANDIDATE_PROFILE_MISMATCH")
    elif status == "preregistered":
        _require_version(profile["exception_version"])
    else:
        raise ContractError("CANDIDATE_PROFILE_MISMATCH")
    return mode, status


def _validate_candidates(
    value: Any,
    definitions: Set[str],
) -> Tuple[Set[str], int]:
    candidates = _require_list(value)
    if len(candidates) != 3:
        raise ContractError("CANDIDATE_SET_INVALID")
    candidate_ids: Set[str] = set()
    candidate_names: Set[str] = set()
    profile_generations: Set[int] = set()
    profile_versions: Set[str] = set()
    common_runtimes: List[Dict[str, Any]] = []
    thinking_profiles: List[Tuple[str, str]] = []
    digests: Set[str] = set()
    for raw_candidate in candidates:
        candidate = _require_object(
            raw_candidate,
            (
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
            ),
            missing_codes={"profile_version": "MISSING_PROFILE_VERSION"},
        )
        candidate_id = _define_uuid(candidate["candidate_id"], definitions)
        candidate_ids.add(candidate_id)
        candidate_name = _require_string(candidate["candidate"])
        if candidate_name not in EXPECTED_CANDIDATES:
            raise ContractError("CANDIDATE_SET_INVALID")
        if candidate_name in candidate_names:
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

        profile_versions.add(_require_version(candidate["profile_version"]))
        profile_generations.add(
            _require_int(candidate["profile_generation"], minimum=1)
        )
        if candidate["selection_status"] != "unranked_candidate":
            raise ContractError("PREMATURE_SELECTION")
        _validate_runtime(candidate["runtime"])
        common_runtimes.append(candidate["runtime"])
        thinking_profiles.append(
            _validate_thinking_profile(candidate["thinking_profile"])
        )
    if candidate_names != EXPECTED_CANDIDATES or len(profile_generations) != 1:
        raise ContractError("CANDIDATE_SET_INVALID")
    if len(profile_versions) != 1 or any(
        runtime != common_runtimes[0] for runtime in common_runtimes[1:]
    ):
        raise ContractError("CANDIDATE_PROFILE_MISMATCH")
    if len({mode for mode, _status in thinking_profiles}) > 1 and any(
        status != "preregistered" for _mode, status in thinking_profiles
    ):
        raise ContractError("CANDIDATE_PROFILE_MISMATCH")
    return candidate_ids, next(iter(profile_generations))


def _validate_atom_definition(value: Any, definitions: Set[str]) -> Tuple[str, str]:
    atom = _require_object(value, ("atom_id", "kind", "provenance"))
    atom_id = _define_uuid(atom["atom_id"], definitions)
    kind = _require_string(atom["kind"])
    if kind not in ATOM_KINDS:
        raise ContractError("UNKNOWN_ATOM_KIND")
    if atom["provenance"] != "synthetic":
        raise ContractError("NON_SYNTHETIC_ATOM_FORBIDDEN")
    return atom_id, kind


def _validate_corpus(
    value: Any,
    definitions: Set[str],
) -> Tuple[Dict[str, Dict[str, str]], int, int, int]:
    corpus = _require_object(
        value,
        (
            "corpus_class",
            "corpus_version",
            "generation",
            "samples",
            "splits",
        ),
    )
    if corpus["corpus_class"] != "synthetic":
        raise ContractError("NON_SYNTHETIC_CORPUS_FORBIDDEN")
    _require_version(corpus["corpus_version"])
    generation = _require_int(corpus["generation"], minimum=1)

    samples: Dict[str, Dict[str, str]] = {}
    for raw_sample in _require_list(corpus["samples"]):
        sample = _require_object(
            raw_sample,
            ("category", "expected_atoms", "sample_id"),
        )
        sample_id = _define_uuid(sample["sample_id"], definitions)
        category = _require_string(sample["category"])
        if category not in SAMPLE_CATEGORIES:
            raise ContractError("UNKNOWN_CATEGORY")
        atoms: Dict[str, str] = {}
        for raw_atom in _require_list(sample["expected_atoms"]):
            atom_id, kind = _validate_atom_definition(raw_atom, definitions)
            atoms[atom_id] = kind
        if not atoms:
            raise ContractError("ATOM_SET_EMPTY")
        samples[sample_id] = atoms
    if not samples:
        raise ContractError("CORPUS_EMPTY")

    splits = corpus["splits"]
    if type(splits) is not dict:
        raise ContractError("INVALID_TYPE")
    if any(key not in ("tuning", "holdout") for key in splits):
        raise ContractError("UNKNOWN_SPLIT")
    if set(splits) != {"tuning", "holdout"}:
        raise ContractError("MISSING_FIELD")
    split_ids: Dict[str, Set[str]] = {}
    for split in ("tuning", "holdout"):
        members: Set[str] = set()
        for raw_id in _require_list(splits[split]):
            member = _require_uuid(raw_id)
            if member in members:
                raise ContractError("DUPLICATE_OPAQUE_ID")
            members.add(member)
        split_ids[split] = members
    if split_ids["tuning"] & split_ids["holdout"]:
        raise ContractError("CORPUS_SPLIT_OVERLAP")
    if split_ids["tuning"] | split_ids["holdout"] != set(samples):
        raise ContractError("SPLIT_MEMBERSHIP_INVALID")
    if not split_ids["tuning"] or not split_ids["holdout"]:
        raise ContractError("SPLIT_MEMBERSHIP_INVALID")
    return (
        samples,
        generation,
        len(split_ids["tuning"]),
        len(split_ids["holdout"]),
    )


def _validate_observed_atom(value: Any) -> Tuple[str, str]:
    atom = _require_object(value, ("atom_id", "kind", "provenance"))
    atom_id = _require_uuid(atom["atom_id"])
    kind = _require_string(atom["kind"])
    if kind not in ATOM_KINDS:
        raise ContractError("UNKNOWN_ATOM_KIND")
    if atom["provenance"] != "synthetic":
        raise ContractError("NON_SYNTHETIC_ATOM_FORBIDDEN")
    return atom_id, kind


def _validate_dimension_records(value: Any) -> None:
    observed: Set[str] = set()
    for raw_record in _require_list(value):
        record = _require_object(raw_record, ("dimension", "status"))
        dimension = _require_string(record["dimension"])
        if dimension not in QUALITY_DIMENSIONS:
            raise ContractError("UNKNOWN_DIMENSION")
        if dimension in observed:
            raise ContractError("DUPLICATE_DIMENSION_RECORD")
        observed.add(dimension)
        expected_status = (
            "synthetic_conformant"
            if dimension == "schema_atom_stability"
            else "not_evaluated"
        )
        if _require_string(record["status"]) != expected_status:
            raise ContractError("DIMENSION_STATUS_INVALID")
    if observed != QUALITY_DIMENSIONS:
        raise ContractError("MISSING_DIMENSION_RECORD")


def _validate_results(
    value: Any,
    definitions: Set[str],
    samples: Mapping[str, Mapping[str, str]],
    candidate_ids: Set[str],
    *,
    protocol_generation: int,
    profile_generation: int,
    corpus_generation: int,
) -> Dict[str, str]:
    results: Dict[str, str] = {}
    for raw_result in _require_list(value):
        result = _require_object(
            raw_result,
            (
                "candidate_id",
                "corpus_generation",
                "dimension_records",
                "disposition",
                "observed_atoms",
                "profile_generation",
                "protocol_generation",
                "result_id",
                "sample_id",
            ),
        )
        result_id = _define_uuid(result["result_id"], definitions)
        sample_id = _require_uuid(result["sample_id"])
        candidate_id = _require_uuid(result["candidate_id"])
        if sample_id not in samples or candidate_id not in candidate_ids:
            raise ContractError("REFERENCE_NOT_FOUND")
        if result["disposition"] not in ("accepted", "rejected"):
            raise ContractError("UNKNOWN_DISPOSITION")
        _validate_dimension_records(result["dimension_records"])
        if _require_int(result["corpus_generation"], minimum=1) != corpus_generation:
            raise ContractError("CORPUS_GENERATION_MISMATCH")
        if _require_int(result["profile_generation"], minimum=1) != profile_generation:
            raise ContractError("PROFILE_GENERATION_MISMATCH")
        if _require_int(result["protocol_generation"], minimum=1) != protocol_generation:
            raise ContractError("PROTOCOL_GENERATION_MISMATCH")

        observed: Dict[str, str] = {}
        for raw_atom in _require_list(result["observed_atoms"]):
            atom_id, kind = _validate_observed_atom(raw_atom)
            if atom_id in observed:
                raise ContractError("DUPLICATE_OPAQUE_ID")
            observed[atom_id] = kind
        expected = samples[sample_id]
        missing = set(expected) - set(observed)
        extra = set(observed) - set(expected)
        if missing:
            raise ContractError("ATOM_MISSING")
        if extra:
            raise ContractError("ATOM_EXTRA")
        if any(observed[atom_id] != expected[atom_id] for atom_id in expected):
            raise ContractError("ATOM_MUTATION")
        results[result_id] = result["disposition"]
    if not results:
        raise ContractError("RESULT_SET_EMPTY")
    return results


def _validate_findings(
    value: Any,
    definitions: Set[str],
    results: Mapping[str, str],
) -> Tuple[int, int]:
    critical_count = 0
    review_count = 0
    for raw_finding in _require_list(value):
        finding = _require_object(
            raw_finding,
            (
                "category",
                "dimension",
                "finding_id",
                "result_id",
                "reviews",
                "severity",
            ),
        )
        _define_uuid(finding["finding_id"], definitions)
        result_id = _require_uuid(finding["result_id"])
        if result_id not in results:
            raise ContractError("REFERENCE_NOT_FOUND")
        category = _require_string(finding["category"])
        if category not in FINDING_CATEGORIES:
            raise ContractError("UNKNOWN_CATEGORY")
        dimension = _require_string(finding["dimension"])
        if dimension not in QUALITY_DIMENSIONS:
            raise ContractError("UNKNOWN_DIMENSION")
        severity = _require_string(finding["severity"])
        if severity not in SEVERITIES:
            raise ContractError("UNKNOWN_SEVERITY")
        if category in CRITICAL_CATEGORIES and severity != "critical":
            raise ContractError("CRITICAL_SEVERITY_REQUIRED")

        human_reviewers: List[str] = []
        for raw_review in _require_list(finding["reviews"]):
            review = _require_object(
                raw_review,
                (
                    "decision",
                    "review_credit",
                    "review_id",
                    "reviewer_id",
                    "reviewer_role",
                ),
            )
            _define_uuid(review["review_id"], definitions)
            reviewer_id = _require_uuid(review["reviewer_id"])
            role = _require_string(review["reviewer_role"])
            if role not in REVIEWER_ROLES:
                raise ContractError("UNKNOWN_REVIEWER_ROLE")
            credit = _require_string(review["review_credit"])
            if credit not in REVIEW_CREDITS:
                raise ContractError("UNKNOWN_REVIEW_CREDIT")
            if role == "model_reviewer" and credit == "human":
                raise ContractError("MODEL_REVIEW_NOT_HUMAN")
            if role == "human_reviewer" and credit != "human":
                raise ContractError("REVIEW_CREDIT_MISMATCH")
            if review["decision"] not in ("confirmed", "dismissed"):
                raise ContractError("UNKNOWN_REVIEW_DECISION")
            if (
                role == "human_reviewer"
                and credit == "human"
                and review["decision"] == "confirmed"
            ):
                human_reviewers.append(reviewer_id)
            review_count += 1

        if severity == "critical" or category in CRITICAL_CATEGORIES:
            critical_count += 1
            if len(human_reviewers) != len(set(human_reviewers)):
                raise ContractError("DUPLICATE_CRITICAL_REVIEWER")
            if len(set(human_reviewers)) < 2:
                raise ContractError("CRITICAL_REVIEW_COUNT_INSUFFICIENT")
            if results[result_id] == "accepted":
                raise ContractError("CRITICAL_FINDING_ACCEPTED")
    return critical_count, review_count


def _validate_benchmark_state(value: Any) -> None:
    if type(value) is not dict:
        raise ContractError("INVALID_TYPE")
    state = value
    if "complete" not in state:
        raise ContractError("MISSING_FIELD")
    if any(
        field not in ("baseline", "complete", "m1b_verdict", "winner")
        for field in state
    ):
        raise ContractError("UNKNOWN_FIELD")
    complete = _require_bool(state["complete"])
    if (
        complete
        or "winner" in state
        or "baseline" in state
        or "m1b_verdict" in state
    ):
        raise ContractError("PREMATURE_SELECTION")


def _validate_aggregate_report(
    value: Any,
    *,
    candidate_count: int,
    sample_count: int,
    tuning_count: int,
    holdout_count: int,
    result_count: int,
    finding_count: int,
    critical_count: int,
    accepted_count: int,
    rejected_count: int,
) -> None:
    report = _require_object(
        value,
        (
            "accepted_result_count",
            "candidate_count",
            "cold_latency_observation_count",
            "conformance_result_count",
            "critical_finding_count",
            "fallback_attempt_count",
            "finding_count",
            "holdout_sample_count",
            "human_fallback_count",
            "memory_observation_count",
            "model_fallback_count",
            "quality_dimensions",
            "redaction",
            "repair_attempt_count",
            "repair_failure_count",
            "repair_success_count",
            "sample_count",
            "terminal_rejection_count",
            "tuning_sample_count",
            "warm_latency_observation_count",
        ),
    )
    if report["redaction"] != "controlled_aggregates_only":
        raise ContractError("REPORT_REDACTION_INVALID")
    dimensions = _require_list(report["quality_dimensions"])
    if (
        any(type(item) is not str for item in dimensions)
        or len(dimensions) != len(set(dimensions))
        or set(dimensions) != QUALITY_DIMENSIONS
    ):
        raise ContractError("QUALITY_DIMENSIONS_INVALID")
    expected = {
        "accepted_result_count": accepted_count,
        "candidate_count": candidate_count,
        "conformance_result_count": result_count,
        "critical_finding_count": critical_count,
        "finding_count": finding_count,
        "holdout_sample_count": holdout_count,
        "sample_count": sample_count,
        "tuning_sample_count": tuning_count,
    }
    for field, expected_value in expected.items():
        if _require_int(report[field], minimum=0) != expected_value:
            raise ContractError("AGGREGATE_COUNT_MISMATCH")
    for field in (
        "cold_latency_observation_count",
        "fallback_attempt_count",
        "human_fallback_count",
        "memory_observation_count",
        "model_fallback_count",
        "repair_attempt_count",
        "repair_failure_count",
        "repair_success_count",
        "terminal_rejection_count",
        "warm_latency_observation_count",
    ):
        _require_int(report[field], minimum=0)
    if report["repair_success_count"] + report["repair_failure_count"] != report[
        "repair_attempt_count"
    ]:
        raise ContractError("AGGREGATE_COUNT_MISMATCH")
    if report["human_fallback_count"] + report["model_fallback_count"] != report[
        "fallback_attempt_count"
    ]:
        raise ContractError("AGGREGATE_COUNT_MISMATCH")
    if report["terminal_rejection_count"] != rejected_count:
        raise ContractError("AGGREGATE_COUNT_MISMATCH")


def validate_document(document: Any) -> Dict[str, int]:
    """Validate one already-parsed synthetic contract document."""

    _scan_for_forbidden_fields(document)
    root = _require_object(
        document,
        (
            "aggregate_report",
            "benchmark_state",
            "candidate_profiles",
            "conformance_results",
            "corpus",
            "findings",
            "protocol",
            "provider_policy",
            "schema_version",
        ),
        missing_codes={"schema_version": "MISSING_SCHEMA_VERSION"},
    )
    if root["schema_version"] != DOCUMENT_SCHEMA:
        raise ContractError("SCHEMA_VERSION_UNSUPPORTED")

    definitions: Set[str] = set()
    protocol = _validate_protocol(root["protocol"])
    _validate_provider_policy(root["provider_policy"])
    candidate_ids, profile_generation = _validate_candidates(
        root["candidate_profiles"], definitions
    )
    samples, corpus_generation, tuning_count, holdout_count = _validate_corpus(
        root["corpus"], definitions
    )
    results = _validate_results(
        root["conformance_results"],
        definitions,
        samples,
        candidate_ids,
        protocol_generation=protocol["generation"],
        profile_generation=profile_generation,
        corpus_generation=corpus_generation,
    )
    critical_count, review_count = _validate_findings(
        root["findings"], definitions, results
    )
    _validate_benchmark_state(root["benchmark_state"])
    accepted_count = sum(value == "accepted" for value in results.values())
    _validate_aggregate_report(
        root["aggregate_report"],
        candidate_count=len(candidate_ids),
        sample_count=len(samples),
        tuning_count=tuning_count,
        holdout_count=holdout_count,
        result_count=len(results),
        finding_count=len(root["findings"]),
        critical_count=critical_count,
        accepted_count=accepted_count,
        rejected_count=sum(value == "rejected" for value in results.values()),
    )
    return {
        "candidates": len(candidate_ids),
        "findings": len(root["findings"]),
        "holdout_samples": holdout_count,
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
        elif operation == "delete":
            patch = _require_object(raw_patch, ("operation", "target"))
        else:
            raise ContractError("FIXTURE_INVALID")
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
        return b'{"codes":["UNEXPECTED_FAILURE"],"counts":{"candidates":0,"findings":0,"holdout_samples":0,"results":0,"reviews":0,"samples":0,"tuning_samples":0},"status":"error"}\n'


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
