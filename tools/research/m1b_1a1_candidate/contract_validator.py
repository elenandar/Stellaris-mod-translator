"""Bounded contract and provider boundary for the inert M1B-1A1 candidate."""

import http.client
import json
import re
import socket
import sys
import types


PROTOCOL_VERSION = "m1b-benchmark-contract-v7"
PROTOCOL_GENERATION = 108
ANALYSIS_POLICY_VERSION = "m1b-analysis-policy-v6"
REQUEST_SCHEMA = "m1b-1a1-validation-request-v1"
ENTRYPOINT_SCHEMA = "m1b-1a1-provider-entrypoint-v1"
PROVIDER_RESULT_SCHEMA = "m1b-1a1-provider-result-v1"
PROFILE_VERSION = "m1b-primary-common-profile-v1"
PROFILE_GENERATION = 202

MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_PROVIDER_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 65536
MAX_STRING_BYTES = 1024 * 1024
MAX_SEQUENCE_ENTRIES = 4096
MAX_UNITS = 4096
MAX_AGREEMENT_SOURCES = 4096
MAX_RATINGS_PER_SOURCE = 1024
MAX_TOTAL_RATING_PAIRS = 65536
MAX_GATE_STATUSES = 4096
MAX_RESULT_INTEGER_BITS = 4096
MAX_FINDINGS = 1024
MAX_GATES = 32
MIN_JSON_INTEGER = -(1 << 63)
MAX_JSON_INTEGER = (1 << 63) - 1

ANALYSIS_ACTIONS = (
    "agreement",
    "aggregate",
    "cfa_gate",
    "dimension_gates",
)
REQUEST_ACTIONS = ANALYSIS_ACTIONS + ("provider_request",)
REQUEST_FIELDS = (
    "action",
    "payload",
    "protocol_generation",
    "protocol_version",
    "request_schema",
)
ENTRYPOINT_FIELDS = ("entrypoint_schema", "mode", "value")

QUALITY_DIMENSIONS = (
    "context_voice_style",
    "literary_russian",
    "meaning_accuracy",
    "schema_atom_stability",
    "terminology_lore",
)
HUMAN_QUALITY_DIMENSIONS = (
    "context_voice_style",
    "literary_russian",
    "meaning_accuracy",
    "terminology_lore",
)
STRATA = (
    "dialogue",
    "gender_case",
    "humor_wordplay",
    "lore",
    "mechanics",
    "narrative",
    "typed_atoms",
    "ui",
)
RISK_CLASSES = (
    "auto_eligible_candidate",
    "critical_risk",
    "mandatory_human",
)

AGREEMENT_STATUSES = (
    "AGREEMENT_APPLICABILITY_DISAGREEMENT",
    "AGREEMENT_INSUFFICIENT_UNITS",
    "AGREEMENT_PASS",
    "AGREEMENT_POINT_BELOW_FLOOR",
    "AGREEMENT_ROBUSTNESS_BELOW_FLOOR",
    "AGREEMENT_UNCERTAINTY_UNDEFINED",
    "AGREEMENT_UNDEFINED_ZERO_EXPECTED_DISAGREEMENT",
)
CFA_STATUSES = (
    "CFA_CONFIDENCE_ABOVE_CEILING",
    "CFA_EVENT_OBSERVED",
    "CFA_INSUFFICIENT_UNITS",
    "CFA_PASS",
)
DIMENSION_GATE_STATUSES = ("DIMENSION_FAIL", "DIMENSION_PASS")
DIMENSION_STRATUM_STATUSES = (
    "DIMENSION_CONFIDENCE_BELOW_FLOOR",
    "DIMENSION_INSUFFICIENT_UNITS",
    "DIMENSION_OBSERVED_BELOW_FLOOR",
    "DIMENSION_STRATUM_PASS",
)

ACCOUNTING_FIELDS = (
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
REQUEST_FIELD_ALLOWLIST = (
    "format",
    "keep_alive",
    "model",
    "options",
    "prompt",
    "stream",
    "think",
)
PROFILE_FIELDS = (
    "allowed_request_fields",
    "auto_pull",
    "candidate",
    "candidate_id",
    "context_reuse",
    "continuation_reuse",
    "conversation_reuse",
    "endpoint",
    "fallback",
    "independent_request_per_sample",
    "model_digest",
    "model_ref",
    "numeric_loopback_only",
    "output_schema",
    "profile_generation",
    "profile_version",
    "proxy_routing",
    "redirects",
    "retry_limit",
    "thinking_trace_reuse",
    "timeout_ms",
)
PROVIDER_REQUEST_FIELDS = REQUEST_FIELD_ALLOWLIST
PROVIDER_OPTIONS_FIELDS = (
    "num_ctx",
    "num_predict",
    "seed",
    "temperature",
)

PROVIDER_RESULT_ROOT_FIELDS = (
    "accounting",
    "findings",
    "gates",
    "result",
    "result_schema",
)
RESULT_FIELDS = (
    "candidate_id",
    "dimension_records",
    "editorial_status",
    "failure_code",
    "profile_generation",
    "profile_version",
    "protocol_generation",
    "technical_conformance",
    "terminal_status",
)
FINDING_FIELDS = (
    "category",
    "dimension",
    "hard_fail",
    "mandatory_review",
    "severity",
)
GATE_FIELDS = ("gate", "status")
DIMENSION_RECORD_FIELDS = ("dimension", "status")

FINDING_CATEGORIES = (
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
)
CRITICAL_CATEGORIES = (
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
)
FINDING_DIMENSIONS = {
    "atom_duplicate": ("schema_atom_stability",),
    "atom_extra": ("schema_atom_stability",),
    "atom_kind_mutation": ("schema_atom_stability",),
    "atom_missing": ("schema_atom_stability",),
    "atom_multiplicity_mutation": ("schema_atom_stability",),
    "atom_position_mutation": ("schema_atom_stability",),
    "atom_value_mutation": ("schema_atom_stability",),
    "context_voice_style_error": ("context_voice_style",),
    "critical_false_accept": QUALITY_DIMENSIONS,
    "literary_error": ("literary_russian",),
    "lore_error": ("terminology_lore",),
    "meaning_inversion": ("meaning_accuracy",),
    "negation_error": ("meaning_accuracy",),
    "number_error": ("meaning_accuracy",),
    "schema_violation": ("schema_atom_stability",),
    "terminology_error": ("terminology_lore",),
}
SEVERITIES = ("none", "low", "medium", "high", "critical")
TECHNICAL_STATUSES = (
    "not_observed",
    "synthetic_conformant",
    "synthetic_nonconformant",
)
EDITORIAL_STATUSES = ("editorially_rejected", "not_evaluated")
TERMINAL_STATUSES = ("controlled_failure", "success")
DIMENSION_STATUSES = (
    "human_fail",
    "human_pass",
    "not_applicable",
    "not_evaluated",
    "synthetic_conformant",
    "synthetic_nonconformant",
)
GATE_NAMES = QUALITY_DIMENSIONS + (
    "agreement",
    "critical_false_accept",
    "editorial_approval",
)
GATE_STATUSES = ("blocked", "fail", "not_evaluated", "pass")

PUBLIC_COUNT_FIELDS = (
    "accounting_rows",
    "finding_rows",
    "gate_rows",
    "profile_rows",
    "request_rows",
    "result_rows",
)

CONTROLLED_CODES = frozenset(
    {
        "ACCOUNTING_INVALID",
        "AGGREGATE_INPUT_INVALID",
        "AGREEMENT_INPUT_INVALID",
        "ANALYSIS_LIMIT_EXCEEDED",
        "ANALYSIS_MODULE_INVALID",
        "ANALYSIS_OUTPUT_INVALID",
        "CFA_INPUT_INVALID",
        "D1_APPLICABILITY_INVALID",
        "DIMENSION_INPUT_INVALID",
        "ENDPOINT_NOT_NUMERIC_LOOPBACK",
        "ENTRYPOINT_INPUT_INVALID",
        "FINDING_INVALID",
        "FIXTURE_INVALID",
        "GATE_INVALID",
        "INPUT_SIZE_LIMIT",
        "JSON_DUPLICATE_KEY",
        "JSON_FLOAT_FORBIDDEN",
        "JSON_INTEGER_OUT_OF_RANGE",
        "JSON_MALFORMED",
        "JSON_NESTING_LIMIT",
        "JSON_STRUCTURE_LIMIT",
        "JSON_UNICODE_INVALID",
        "MATERIALIZATION_FAILURE",
        "MATERIALIZATION_WORK_LIMIT",
        "MODULE_BINDING_INVALID",
        "PROFILE_INVALID",
        "PAYLOAD_INVALID",
        "PROVIDER_DNS_FORBIDDEN",
        "PROVIDER_HTTP_FAILURE",
        "PROVIDER_NETWORK_FAILURE",
        "PROVIDER_PEER_INVALID",
        "PROVIDER_REDIRECT_FORBIDDEN",
        "PROVIDER_REQUEST_INVALID",
        "PROVIDER_RESPONSE_INVALID",
        "PROVIDER_RESPONSE_SIZE_LIMIT",
        "PROVIDER_RESULT_INVALID",
        "PROVIDER_TRUNCATION_CONTROLLED",
        "REQUEST_IDENTITY_MISMATCH",
        "REQUEST_INVALID",
        "RESULT_INVALID",
        "UNEXPECTED_FAILURE",
        "UTF8_BOM_FORBIDDEN",
        "UTF8_INVALID",
    }
)
ANALYSIS_ERROR_CODES = frozenset(
    {
        "AGGREGATE_INPUT_INVALID",
        "AGREEMENT_INPUT_INVALID",
        "ANALYSIS_LIMIT_EXCEEDED",
        "CFA_INPUT_INVALID",
        "D1_APPLICABILITY_INVALID",
        "DIMENSION_INPUT_INVALID",
        "PAYLOAD_INVALID",
        "REQUEST_IDENTITY_MISMATCH",
        "REQUEST_INVALID",
        "UNEXPECTED_FAILURE",
    }
)
MATERIALIZATION_ERROR_CODES = frozenset(
    {
        "FIXTURE_INVALID",
        "INPUT_SIZE_LIMIT",
        "MATERIALIZATION_WORK_LIMIT",
    }
)

_CODE = re.compile(r"^[A-Z][A-Z0-9_]*$", re.ASCII)
_ENDPOINT = re.compile(
    r"^http://(127[.]0[.]0[.]1|\[::1\]):([1-9][0-9]{0,4})/api$",
    re.ASCII,
)
_DIGEST = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_MODEL_REF = re.compile(
    r"^[a-z0-9][a-z0-9._/-]{0,127}:[a-z0-9][a-z0-9._-]{0,63}$",
    re.ASCII,
)
_UUID_V4 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.ASCII,
)
_SAFE_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$", re.ASCII)
_RAW_OR_PATH_KEYS = frozenset(
    {
        "annotation",
        "content",
        "excerpt",
        "file",
        "file_name",
        "file_path",
        "filename",
        "input",
        "model_output",
        "output",
        "path",
        "prompt",
        "raw",
        "raw_input",
        "raw_output",
        "raw_text",
        "source_text",
        "text",
        "traceback",
        "translation",
    }
)

_PROVIDER_FORMAT = {
    "additionalProperties": False,
    "properties": {
        "accounting": {"type": "object"},
        "findings": {"type": "array"},
        "gates": {"type": "array"},
        "result": {"type": "object"},
        "result_schema": {"const": PROVIDER_RESULT_SCHEMA},
    },
    "required": [
        "accounting",
        "findings",
        "gates",
        "result",
        "result_schema",
    ],
    "type": "object",
}


class ContractError(Exception):
    """Controlled boundary failure carrying one allowlisted public code."""

    def __init__(self, code):
        if type(code) is not str or code not in CONTROLLED_CODES:
            code = "UNEXPECTED_FAILURE"
        self.code = code
        Exception.__init__(self, code)


def _empty_counts():
    return {field: 0 for field in PUBLIC_COUNT_FIELDS}


def _canonical_json(value):
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise ContractError("UNEXPECTED_FAILURE")


def _duplicate_safe_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def _reject_json_constant(_token):
    raise ContractError("JSON_MALFORMED")


def _reject_json_float(_token):
    raise ContractError("JSON_FLOAT_FORBIDDEN")


def _parse_bounded_int(token):
    if type(token) is not str or not token:
        raise ContractError("JSON_INTEGER_OUT_OF_RANGE")
    negative = token.startswith("-")
    digits = token[1:] if negative else token
    if not digits or not digits.isascii() or not digits.isdigit():
        raise ContractError("JSON_INTEGER_OUT_OF_RANGE")
    limit = "9223372036854775808" if negative else "9223372036854775807"
    if len(digits) > len(limit):
        raise ContractError("JSON_INTEGER_OUT_OF_RANGE")
    if len(digits) == len(limit) and digits > limit:
        raise ContractError("JSON_INTEGER_OUT_OF_RANGE")
    value = int(token, 10)
    if value < MIN_JSON_INTEGER or value > MAX_JSON_INTEGER:
        raise ContractError("JSON_INTEGER_OUT_OF_RANGE")
    return value


def _validate_json_tree(value):
    pending = [(value, 0)]
    nodes = 0
    while pending:
        current, depth = pending.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise ContractError("JSON_STRUCTURE_LIMIT")
        if depth > MAX_JSON_DEPTH:
            raise ContractError("JSON_NESTING_LIMIT")
        if type(current) is str:
            try:
                encoded = current.encode("utf-8", errors="strict")
            except UnicodeEncodeError:
                raise ContractError("JSON_UNICODE_INVALID")
            if len(encoded) > MAX_STRING_BYTES:
                raise ContractError("JSON_STRUCTURE_LIMIT")
        elif type(current) is list:
            if len(current) > MAX_SEQUENCE_ENTRIES:
                raise ContractError("JSON_STRUCTURE_LIMIT")
            pending.extend((item, depth + 1) for item in current)
        elif type(current) is dict:
            if len(current) > MAX_SEQUENCE_ENTRIES:
                raise ContractError("JSON_STRUCTURE_LIMIT")
            for key, item in current.items():
                if type(key) is not str:
                    raise ContractError("JSON_MALFORMED")
                pending.append((key, depth + 1))
                pending.append((item, depth + 1))
        elif current is None or type(current) in (bool, int):
            continue
        else:
            raise ContractError("JSON_MALFORMED")


def parse_json_bytes(data):
    """Decode one bounded strict UTF-8 JSON value."""

    if type(data) is not bytes:
        raise ContractError("JSON_MALFORMED")
    if len(data) > MAX_INPUT_BYTES:
        raise ContractError("INPUT_SIZE_LIMIT")
    if data.startswith(b"\xef\xbb\xbf"):
        raise ContractError("UTF8_BOM_FORBIDDEN")
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
    _validate_json_tree(value)
    return value


def _closed_object(value, fields, code):
    if type(value) is not dict or set(value) != set(fields):
        raise ContractError(code)
    return value


def _bounded_list(value, minimum, maximum, code):
    if type(value) is not list or len(value) < minimum or len(value) > maximum:
        raise ContractError(code)
    return value


def _bounded_int(value, minimum, maximum, code):
    if type(value) is not int or value < minimum or value > maximum:
        raise ContractError(code)
    return value


def _exact_bool(value, expected, code):
    if type(value) is not bool or value is not expected:
        raise ContractError(code)
    return value


def _bounded_string(value, minimum, maximum, code, ascii_only=False):
    if type(value) is not str:
        raise ContractError(code)
    try:
        encoded = value.encode(
            "ascii" if ascii_only else "utf-8",
            errors="strict",
        )
    except UnicodeEncodeError:
        raise ContractError(code)
    if len(encoded) < minimum or len(encoded) > maximum:
        raise ContractError(code)
    return value


def _validate_protocol_identity(request):
    if (
        request["request_schema"] != REQUEST_SCHEMA
        or request["protocol_version"] != PROTOCOL_VERSION
        or type(request["protocol_generation"]) is not int
        or request["protocol_generation"] != PROTOCOL_GENERATION
    ):
        raise ContractError("REQUEST_IDENTITY_MISMATCH")


def _validate_agreement_payload(value):
    payload = _closed_object(
        value,
        (
            "bilateral_not_applicable_source_count",
            "sources",
            "unilateral_not_applicable_source_count",
        ),
        "AGREEMENT_INPUT_INVALID",
    )
    bilateral = _bounded_int(
        payload["bilateral_not_applicable_source_count"],
        0,
        MAX_AGREEMENT_SOURCES,
        "AGREEMENT_INPUT_INVALID",
    )
    unilateral = _bounded_int(
        payload["unilateral_not_applicable_source_count"],
        0,
        MAX_AGREEMENT_SOURCES,
        "AGREEMENT_INPUT_INVALID",
    )
    sources = _bounded_list(
        payload["sources"],
        1,
        MAX_AGREEMENT_SOURCES,
        "AGREEMENT_INPUT_INVALID",
    )
    total_pairs = 0
    for raw_source in sources:
        source = _closed_object(
            raw_source,
            ("pairs",),
            "AGREEMENT_INPUT_INVALID",
        )
        pairs = _bounded_list(
            source["pairs"],
            1,
            MAX_RATINGS_PER_SOURCE,
            "AGREEMENT_INPUT_INVALID",
        )
        total_pairs += len(pairs)
        if total_pairs > MAX_TOTAL_RATING_PAIRS:
            raise ContractError("ANALYSIS_LIMIT_EXCEEDED")
        for pair in pairs:
            pair = _bounded_list(pair, 2, 2, "AGREEMENT_INPUT_INVALID")
            _bounded_int(pair[0], 0, 4, "AGREEMENT_INPUT_INVALID")
            _bounded_int(pair[1], 0, 4, "AGREEMENT_INPUT_INVALID")
    if len(sources) + bilateral + unilateral > MAX_AGREEMENT_SOURCES:
        raise ContractError("ANALYSIS_LIMIT_EXCEEDED")
    return payload


def _validate_dimension_payload(value):
    payload = _closed_object(
        value,
        ("dimensions",),
        "DIMENSION_INPUT_INVALID",
    )
    dimensions = _bounded_list(
        payload["dimensions"],
        len(QUALITY_DIMENSIONS),
        len(QUALITY_DIMENSIONS),
        "DIMENSION_INPUT_INVALID",
    )
    observed_dimensions = []
    for raw_dimension in dimensions:
        dimension = _closed_object(
            raw_dimension,
            ("dimension", "strata"),
            "DIMENSION_INPUT_INVALID",
        )
        name = dimension["dimension"]
        if type(name) is not str:
            raise ContractError("DIMENSION_INPUT_INVALID")
        observed_dimensions.append(name)
        strata = _bounded_list(
            dimension["strata"],
            len(STRATA),
            len(STRATA),
            "DIMENSION_INPUT_INVALID",
        )
        observed_strata = []
        for raw_stratum in strata:
            stratum = _closed_object(
                raw_stratum,
                (
                    "applicable_count",
                    "assigned_count",
                    "stratum",
                    "success_count",
                ),
                "DIMENSION_INPUT_INVALID",
            )
            stratum_name = stratum["stratum"]
            if type(stratum_name) is not str:
                raise ContractError("DIMENSION_INPUT_INVALID")
            observed_strata.append(stratum_name)
            assigned = _bounded_int(
                stratum["assigned_count"],
                0,
                MAX_UNITS,
                "DIMENSION_INPUT_INVALID",
            )
            applicable = _bounded_int(
                stratum["applicable_count"],
                0,
                assigned,
                "DIMENSION_INPUT_INVALID",
            )
            _bounded_int(
                stratum["success_count"],
                0,
                applicable,
                "DIMENSION_INPUT_INVALID",
            )
            if name == "schema_atom_stability" and applicable != assigned:
                raise ContractError("D1_APPLICABILITY_INVALID")
        if tuple(observed_strata) != STRATA:
            raise ContractError("DIMENSION_INPUT_INVALID")
    if tuple(observed_dimensions) != QUALITY_DIMENSIONS:
        raise ContractError("DIMENSION_INPUT_INVALID")
    return payload


def _validate_cfa_payload(value):
    payload = _closed_object(
        value,
        ("event_count", "risk_class", "source_generation_count"),
        "CFA_INPUT_INVALID",
    )
    source_count = _bounded_int(
        payload["source_generation_count"],
        0,
        MAX_UNITS,
        "CFA_INPUT_INVALID",
    )
    _bounded_int(
        payload["event_count"],
        0,
        source_count,
        "CFA_INPUT_INVALID",
    )
    if payload["risk_class"] not in RISK_CLASSES:
        raise ContractError("CFA_INPUT_INVALID")
    return payload


def _validate_aggregate_payload(value):
    payload = _closed_object(
        value,
        (
            "agreement_statuses",
            "approved_critical_finding_count",
            "approved_d1_defect_count",
            "cfa_statuses",
            "dimension_statuses",
            "editorially_approved_count",
            "mandatory_human_evidence_missing_count",
            "result_count",
            "technical_safe_count",
        ),
        "AGGREGATE_INPUT_INVALID",
    )
    result_count = _bounded_int(
        payload["result_count"],
        1,
        MAX_UNITS,
        "AGGREGATE_INPUT_INVALID",
    )
    approved_count = _bounded_int(
        payload["editorially_approved_count"],
        0,
        result_count,
        "AGGREGATE_INPUT_INVALID",
    )
    technical_safe_count = _bounded_int(
        payload["technical_safe_count"],
        0,
        result_count,
        "AGGREGATE_INPUT_INVALID",
    )
    if approved_count > technical_safe_count:
        raise ContractError("AGGREGATE_INPUT_INVALID")
    _bounded_int(
        payload["mandatory_human_evidence_missing_count"],
        0,
        result_count,
        "AGGREGATE_INPUT_INVALID",
    )
    for field in (
        "approved_critical_finding_count",
        "approved_d1_defect_count",
    ):
        _bounded_int(
            payload[field],
            0,
            approved_count,
            "AGGREGATE_INPUT_INVALID",
        )
    agreement = _bounded_list(
        payload["agreement_statuses"],
        1,
        MAX_GATE_STATUSES,
        "AGGREGATE_INPUT_INVALID",
    )
    if any(status not in AGREEMENT_STATUSES for status in agreement):
        raise ContractError("AGGREGATE_INPUT_INVALID")
    cfa = _bounded_list(
        payload["cfa_statuses"],
        1,
        MAX_GATE_STATUSES,
        "AGGREGATE_INPUT_INVALID",
    )
    if any(status not in CFA_STATUSES for status in cfa):
        raise ContractError("AGGREGATE_INPUT_INVALID")
    dimensions = _bounded_list(
        payload["dimension_statuses"],
        len(QUALITY_DIMENSIONS),
        len(QUALITY_DIMENSIONS),
        "AGGREGATE_INPUT_INVALID",
    )
    names = []
    for raw_row in dimensions:
        row = _closed_object(
            raw_row,
            ("dimension", "status"),
            "AGGREGATE_INPUT_INVALID",
        )
        names.append(row["dimension"])
        if row["status"] not in DIMENSION_GATE_STATUSES:
            raise ContractError("AGGREGATE_INPUT_INVALID")
    if tuple(names) != QUALITY_DIMENSIONS:
        raise ContractError("AGGREGATE_INPUT_INVALID")
    return payload


def _require_numeric_loopback_endpoint(value):
    endpoint = _bounded_string(
        value,
        1,
        128,
        "ENDPOINT_NOT_NUMERIC_LOOPBACK",
        ascii_only=True,
    )
    if endpoint != endpoint.strip():
        raise ContractError("ENDPOINT_NOT_NUMERIC_LOOPBACK")
    if any(ord(character) <= 31 or ord(character) == 127 for character in endpoint):
        raise ContractError("ENDPOINT_NOT_NUMERIC_LOOPBACK")
    match = _ENDPOINT.fullmatch(endpoint)
    if match is None:
        raise ContractError("ENDPOINT_NOT_NUMERIC_LOOPBACK")
    port = int(match.group(2), 10)
    if port < 1 or port > 65535:
        raise ContractError("ENDPOINT_NOT_NUMERIC_LOOPBACK")
    host = match.group(1)
    if host == "[::1]":
        return socket.AF_INET6, "::1", port, "[::1]"
    return socket.AF_INET, "127.0.0.1", port, "127.0.0.1"


def _validate_profile(value):
    profile = _closed_object(value, PROFILE_FIELDS, "PROFILE_INVALID")
    if (
        profile["profile_version"] != PROFILE_VERSION
        or type(profile["profile_generation"]) is not int
        or profile["profile_generation"] != PROFILE_GENERATION
        or profile["output_schema"] != PROVIDER_RESULT_SCHEMA
    ):
        raise ContractError("PROFILE_INVALID")
    if profile["candidate"] not in (
        "deepseek_r1_32b",
        "glm_4_7_flash",
        "gpt_oss_20b",
    ):
        raise ContractError("PROFILE_INVALID")
    if (
        type(profile["candidate_id"]) is not str
        or _UUID_V4.fullmatch(profile["candidate_id"]) is None
    ):
        raise ContractError("PROFILE_INVALID")
    _require_numeric_loopback_endpoint(profile["endpoint"])
    _exact_bool(
        profile["numeric_loopback_only"],
        True,
        "ENDPOINT_NOT_NUMERIC_LOOPBACK",
    )
    for field in (
        "auto_pull",
        "context_reuse",
        "continuation_reuse",
        "conversation_reuse",
        "fallback",
        "proxy_routing",
        "redirects",
        "thinking_trace_reuse",
    ):
        _exact_bool(profile[field], False, "PROFILE_INVALID")
    _exact_bool(
        profile["independent_request_per_sample"],
        True,
        "PROFILE_INVALID",
    )
    allowed = _bounded_list(
        profile["allowed_request_fields"],
        len(REQUEST_FIELD_ALLOWLIST),
        len(REQUEST_FIELD_ALLOWLIST),
        "PROFILE_INVALID",
    )
    if tuple(allowed) != REQUEST_FIELD_ALLOWLIST:
        raise ContractError("PROFILE_INVALID")
    _bounded_int(profile["retry_limit"], 0, 0, "PROFILE_INVALID")
    _bounded_int(profile["timeout_ms"], 300000, 300000, "PROFILE_INVALID")
    model_ref = _bounded_string(
        profile["model_ref"],
        3,
        193,
        "PROFILE_INVALID",
        ascii_only=True,
    )
    if _MODEL_REF.fullmatch(model_ref) is None:
        raise ContractError("PROFILE_INVALID")
    model_name, model_tag = model_ref.split(":", 1)
    if model_name.endswith("-cloud") or model_tag.endswith("-cloud"):
        raise ContractError("PROFILE_INVALID")
    digest = _bounded_string(
        profile["model_digest"],
        64,
        64,
        "PROFILE_INVALID",
        ascii_only=True,
    )
    if _DIGEST.fullmatch(digest) is None:
        raise ContractError("PROFILE_INVALID")
    return profile


def _validate_provider_request(value, profile):
    request = _closed_object(
        value,
        PROVIDER_REQUEST_FIELDS,
        "PROVIDER_REQUEST_INVALID",
    )
    if tuple(sorted(request)) != tuple(sorted(REQUEST_FIELD_ALLOWLIST)):
        raise ContractError("PROVIDER_REQUEST_INVALID")
    if request["format"] != _PROVIDER_FORMAT:
        raise ContractError("PROVIDER_REQUEST_INVALID")
    _bounded_int(request["keep_alive"], 0, 0, "PROVIDER_REQUEST_INVALID")
    if request["model"] != profile["model_ref"]:
        raise ContractError("PROVIDER_REQUEST_INVALID")
    options = _closed_object(
        request["options"],
        PROVIDER_OPTIONS_FIELDS,
        "PROVIDER_REQUEST_INVALID",
    )
    _bounded_int(options["num_ctx"], 8192, 8192, "PROVIDER_REQUEST_INVALID")
    _bounded_int(
        options["num_predict"],
        2048,
        2048,
        "PROVIDER_REQUEST_INVALID",
    )
    _bounded_int(options["seed"], 424242, 424242, "PROVIDER_REQUEST_INVALID")
    _bounded_int(options["temperature"], 0, 0, "PROVIDER_REQUEST_INVALID")
    _bounded_string(
        request["prompt"],
        1,
        MAX_STRING_BYTES,
        "PROVIDER_REQUEST_INVALID",
    )
    _exact_bool(request["stream"], False, "PROVIDER_REQUEST_INVALID")
    _exact_bool(request["think"], False, "PROVIDER_REQUEST_INVALID")
    return request


def _validate_accounting(value):
    accounting = _closed_object(
        value,
        ACCOUNTING_FIELDS,
        "ACCOUNTING_INVALID",
    )
    for field in ACCOUNTING_FIELDS:
        _bounded_int(accounting[field], 0, 1, "ACCOUNTING_INVALID")
    if (
        accounting["repair_success_count"]
        + accounting["repair_failure_count"]
        != accounting["repair_attempt_count"]
    ):
        raise ContractError("ACCOUNTING_INVALID")
    if (
        accounting["human_fallback_count"]
        + accounting["model_fallback_count"]
        != accounting["fallback_attempt_count"]
    ):
        raise ContractError("ACCOUNTING_INVALID")
    if (
        accounting["retry_attempt_count"]
        or accounting["repair_attempt_count"]
        or accounting["fallback_attempt_count"]
    ):
        raise ContractError("ACCOUNTING_INVALID")
    if accounting["initial_attempt_count"] != 1:
        raise ContractError("ACCOUNTING_INVALID")
    if accounting["model_call_count"] != 1:
        raise ContractError("ACCOUNTING_INVALID")
    for field in (
        "cold_latency_observation_count",
        "memory_observation_count",
        "warm_latency_observation_count",
    ):
        if accounting[field] > accounting["model_call_count"]:
            raise ContractError("ACCOUNTING_INVALID")
    return accounting


def _validate_dimension_records(value):
    records = _bounded_list(
        value,
        len(QUALITY_DIMENSIONS),
        len(QUALITY_DIMENSIONS),
        "RESULT_INVALID",
    )
    names = []
    statuses = {}
    for raw_record in records:
        record = _closed_object(
            raw_record,
            DIMENSION_RECORD_FIELDS,
            "RESULT_INVALID",
        )
        dimension = record["dimension"]
        status = record["status"]
        if dimension not in QUALITY_DIMENSIONS or status not in DIMENSION_STATUSES:
            raise ContractError("RESULT_INVALID")
        if dimension in statuses:
            raise ContractError("RESULT_INVALID")
        if dimension == "schema_atom_stability":
            if status not in (
                "not_evaluated",
                "synthetic_conformant",
                "synthetic_nonconformant",
            ):
                raise ContractError("RESULT_INVALID")
        elif status.startswith("synthetic_"):
            raise ContractError("RESULT_INVALID")
        names.append(dimension)
        statuses[dimension] = status
    if tuple(names) != QUALITY_DIMENSIONS:
        raise ContractError("RESULT_INVALID")
    return statuses


def _validate_result(value, profile, accounting):
    result = _closed_object(value, RESULT_FIELDS, "RESULT_INVALID")
    candidate_id = _bounded_string(
        result["candidate_id"],
        1,
        128,
        "RESULT_INVALID",
        ascii_only=True,
    )
    if (
        _UUID_V4.fullmatch(candidate_id) is None
        or candidate_id != profile["candidate_id"]
    ):
        raise ContractError("RESULT_INVALID")
    if (
        result["profile_version"] != profile["profile_version"]
        or type(result["profile_generation"]) is not int
        or result["profile_generation"] != profile["profile_generation"]
        or type(result["protocol_generation"]) is not int
        or result["protocol_generation"] != PROTOCOL_GENERATION
    ):
        raise ContractError("RESULT_INVALID")
    technical = result["technical_conformance"]
    editorial = result["editorial_status"]
    terminal = result["terminal_status"]
    if (
        technical not in TECHNICAL_STATUSES
        or editorial not in EDITORIAL_STATUSES
        or terminal not in TERMINAL_STATUSES
    ):
        raise ContractError("RESULT_INVALID")
    statuses = _validate_dimension_records(result["dimension_records"])
    failure_code = result["failure_code"]
    if terminal == "success":
        if failure_code is not None or accounting["terminal_failure_count"]:
            raise ContractError("RESULT_INVALID")
        if technical == "not_observed":
            raise ContractError("RESULT_INVALID")
    else:
        if (
            type(failure_code) is not str
            or _CODE.fullmatch(failure_code) is None
            or accounting["terminal_failure_count"] != 1
            or technical != "not_observed"
        ):
            raise ContractError("RESULT_INVALID")
    if technical == "not_observed":
        if any(status != "not_evaluated" for status in statuses.values()):
            raise ContractError("RESULT_INVALID")
    else:
        expected_d1 = technical
        if statuses["schema_atom_stability"] != expected_d1:
            raise ContractError("RESULT_INVALID")
    return result


def _validate_findings(value):
    findings = _bounded_list(value, 0, MAX_FINDINGS, "FINDING_INVALID")
    for raw_finding in findings:
        finding = _closed_object(
            raw_finding,
            FINDING_FIELDS,
            "FINDING_INVALID",
        )
        category = finding["category"]
        dimension = finding["dimension"]
        severity = finding["severity"]
        if (
            category not in FINDING_CATEGORIES
            or dimension not in FINDING_DIMENSIONS[category]
            or severity not in SEVERITIES
            or type(finding["hard_fail"]) is not bool
            or type(finding["mandatory_review"]) is not bool
        ):
            raise ContractError("FINDING_INVALID")
        if category in CRITICAL_CATEGORIES:
            if (
                severity != "critical"
                or not finding["hard_fail"]
                or not finding["mandatory_review"]
            ):
                raise ContractError("FINDING_INVALID")
        if severity == "none" and (
            finding["hard_fail"] or finding["mandatory_review"]
        ):
            raise ContractError("FINDING_INVALID")
        if severity == "critical" and not finding["hard_fail"]:
            raise ContractError("FINDING_INVALID")
        if (
            severity in ("high", "critical") or finding["hard_fail"]
        ) and not finding["mandatory_review"]:
            raise ContractError("FINDING_INVALID")
    return findings


def _validate_gates(value, result):
    gates = _bounded_list(
        value,
        len(GATE_NAMES),
        len(GATE_NAMES),
        "GATE_INVALID",
    )
    observed = []
    statuses = {}
    for raw_gate in gates:
        gate = _closed_object(raw_gate, GATE_FIELDS, "GATE_INVALID")
        if gate["gate"] not in GATE_NAMES or gate["status"] not in GATE_STATUSES:
            raise ContractError("GATE_INVALID")
        if gate["gate"] in observed:
            raise ContractError("GATE_INVALID")
        observed.append(gate["gate"])
        statuses[gate["gate"]] = gate["status"]
        if gate["status"] == "pass":
            if gate["gate"] != "schema_atom_stability":
                raise ContractError("GATE_INVALID")
            if result["technical_conformance"] != "synthetic_conformant":
                raise ContractError("GATE_INVALID")
    if tuple(observed) != tuple(sorted(GATE_NAMES)):
        raise ContractError("GATE_INVALID")
    expected_d1_status = {
        "not_observed": "not_evaluated",
        "synthetic_conformant": "pass",
        "synthetic_nonconformant": "fail",
    }[result["technical_conformance"]]
    if statuses["schema_atom_stability"] != expected_d1_status:
        raise ContractError("GATE_INVALID")
    return gates


def _validate_provider_result(value, profile):
    root = _closed_object(
        value,
        PROVIDER_RESULT_ROOT_FIELDS,
        "PROVIDER_RESULT_INVALID",
    )
    if root["result_schema"] != PROVIDER_RESULT_SCHEMA:
        raise ContractError("PROVIDER_RESULT_INVALID")
    accounting = _validate_accounting(root["accounting"])
    result = _validate_result(root["result"], profile, accounting)
    findings = _validate_findings(root["findings"])
    gates = _validate_gates(root["gates"], result)
    if result["terminal_status"] == "controlled_failure" and (
        findings or any(gate["status"] == "pass" for gate in gates)
    ):
        raise ContractError("PROVIDER_RESULT_INVALID")
    return root


def _validate_provider_payload(value):
    payload = _closed_object(
        value,
        ("profile", "provider_request"),
        "PROVIDER_REQUEST_INVALID",
    )
    profile = _validate_profile(payload["profile"])
    request = _validate_provider_request(payload["provider_request"], profile)
    return profile, request


def validate_request(value):
    """Validate and return one detached, closed request object."""

    request = _closed_object(value, REQUEST_FIELDS, "REQUEST_INVALID")
    _validate_protocol_identity(request)
    action = request["action"]
    if action not in REQUEST_ACTIONS:
        raise ContractError("REQUEST_INVALID")
    if action == "agreement":
        _validate_agreement_payload(request["payload"])
    elif action == "dimension_gates":
        _validate_dimension_payload(request["payload"])
    elif action == "cfa_gate":
        _validate_cfa_payload(request["payload"])
    elif action == "aggregate":
        _validate_aggregate_payload(request["payload"])
    else:
        _validate_provider_payload(request["payload"])
    return request


def validate_request_bytes(data):
    """Strictly decode and validate one bounded request."""

    return validate_request(parse_json_bytes(data))


def _validate_provider_api_response(value, expected_model):
    fields = (
        "context",
        "created_at",
        "done",
        "done_reason",
        "eval_count",
        "eval_duration",
        "load_duration",
        "model",
        "prompt_eval_count",
        "prompt_eval_duration",
        "response",
        "total_duration",
    )
    response = _closed_object(value, fields, "PROVIDER_RESPONSE_INVALID")
    if response["model"] != expected_model:
        raise ContractError("PROVIDER_RESPONSE_INVALID")
    _bounded_string(
        response["created_at"],
        1,
        128,
        "PROVIDER_RESPONSE_INVALID",
        ascii_only=True,
    )
    _exact_bool(response["done"], True, "PROVIDER_RESPONSE_INVALID")
    if response["done_reason"] not in ("length", "stop"):
        raise ContractError("PROVIDER_RESPONSE_INVALID")
    for field in (
        "eval_count",
        "eval_duration",
        "load_duration",
        "prompt_eval_count",
        "prompt_eval_duration",
        "total_duration",
    ):
        _bounded_int(
            response[field],
            0,
            MAX_JSON_INTEGER,
            "PROVIDER_RESPONSE_INVALID",
        )
    context = _bounded_list(
        response["context"],
        0,
        MAX_SEQUENCE_ENTRIES,
        "PROVIDER_RESPONSE_INVALID",
    )
    for token in context:
        _bounded_int(token, 0, MAX_JSON_INTEGER, "PROVIDER_RESPONSE_INVALID")
    text = _bounded_string(
        response["response"],
        1,
        MAX_PROVIDER_RESPONSE_BYTES,
        "PROVIDER_RESPONSE_INVALID",
    )
    if response["done_reason"] == "length":
        raise ContractError("PROVIDER_TRUNCATION_CONTROLLED")
    return text


def _read_http_response(response):
    if 300 <= response.status <= 399:
        raise ContractError("PROVIDER_REDIRECT_FORBIDDEN")
    if response.status != 200:
        response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
        raise ContractError("PROVIDER_HTTP_FAILURE")
    critical_headers = (
        "content-encoding",
        "content-length",
        "content-type",
        "location",
        "transfer-encoding",
    )
    for name in critical_headers:
        values = response.headers.get_all(name, [])
        if len(values) > 1:
            raise ContractError("PROVIDER_RESPONSE_INVALID")
    if response.headers.get("Content-Encoding") not in (None, "identity"):
        raise ContractError("PROVIDER_RESPONSE_INVALID")
    content_type = response.headers.get("Content-Type")
    if (
        type(content_type) is not str
        or content_type.split(";", 1)[0].strip().lower() != "application/json"
    ):
        raise ContractError("PROVIDER_RESPONSE_INVALID")
    data = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
    if len(data) > MAX_PROVIDER_RESPONSE_BYTES:
        raise ContractError("PROVIDER_RESPONSE_SIZE_LIMIT")
    return data


def _perform_provider_request(profile, provider_request):
    family, host, port, host_header = _require_numeric_loopback_endpoint(
        profile["endpoint"]
    )
    body = _canonical_json(provider_request)
    if len(body) > MAX_INPUT_BYTES:
        raise ContractError("INPUT_SIZE_LIMIT")
    request_head = (
        "POST /api/generate HTTP/1.1\r\n"
        "Host: {0}:{1}\r\n"
        "Content-Type: application/json\r\n"
        "Accept: application/json\r\n"
        "Connection: close\r\n"
        "Content-Length: {2}\r\n"
        "\r\n"
    ).format(host_header, port, len(body)).encode("ascii")
    sock = None
    response = None
    try:
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(profile["timeout_ms"] / 1000)
        if family == socket.AF_INET6:
            sock.connect((host, port, 0, 0))
        else:
            sock.connect((host, port))
        peer = sock.getpeername()
        if not peer or peer[0] != host:
            raise ContractError("PROVIDER_PEER_INVALID")
        sock.sendall(request_head + body)
        response = http.client.HTTPResponse(sock)
        response.begin()
        response_bytes = _read_http_response(response)
    except ContractError:
        raise
    except (OSError, ValueError, http.client.HTTPException):
        raise ContractError("PROVIDER_NETWORK_FAILURE")
    finally:
        if response is not None:
            try:
                response.close()
            except (OSError, ValueError):
                pass
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
    outer = parse_json_bytes(response_bytes)
    inner_text = _validate_provider_api_response(
        outer,
        profile["model_ref"],
    )
    try:
        inner_bytes = inner_text.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        raise ContractError("JSON_UNICODE_INVALID")
    inner = parse_json_bytes(inner_bytes)
    validated = _validate_provider_result(inner, profile)
    return {
        "accounting": dict(validated["accounting"]),
        "editorial_status": validated["result"]["editorial_status"],
        "finding_count": len(validated["findings"]),
        "gate_count": len(validated["gates"]),
        "result_schema": PROVIDER_RESULT_SCHEMA,
        "technical_conformance": validated["result"]["technical_conformance"],
        "terminal_status": validated["result"]["terminal_status"],
    }


def _safe_action(value):
    if type(value) is dict and value.get("action") in REQUEST_ACTIONS:
        return value["action"]
    return "unrecognized"


def _validate_fraction(value, code, nullable=False):
    if nullable and value is None:
        return None
    fraction = _closed_object(
        value,
        ("denominator", "numerator"),
        code,
    )
    denominator = fraction["denominator"]
    numerator = fraction["numerator"]
    if (
        type(denominator) is not int
        or denominator <= 0
        or denominator.bit_length() > MAX_RESULT_INTEGER_BITS
        or type(numerator) is not int
        or abs(numerator).bit_length() > MAX_RESULT_INTEGER_BITS
    ):
        raise ContractError(code)
    return fraction


def _validate_agreement_output(value):
    result = _closed_object(
        value,
        (
            "applicable_source_count",
            "bilateral_not_applicable_source_count",
            "gate_status",
            "minimum_delete_one_kappa",
            "point_kappa",
            "rating_pair_count",
            "threshold",
            "unilateral_not_applicable_source_count",
        ),
        "ANALYSIS_OUTPUT_INVALID",
    )
    applicable = _bounded_int(
        result["applicable_source_count"],
        0,
        MAX_AGREEMENT_SOURCES,
        "ANALYSIS_OUTPUT_INVALID",
    )
    bilateral = _bounded_int(
        result["bilateral_not_applicable_source_count"],
        0,
        MAX_AGREEMENT_SOURCES,
        "ANALYSIS_OUTPUT_INVALID",
    )
    unilateral = _bounded_int(
        result["unilateral_not_applicable_source_count"],
        0,
        MAX_AGREEMENT_SOURCES,
        "ANALYSIS_OUTPUT_INVALID",
    )
    if applicable + bilateral + unilateral > MAX_AGREEMENT_SOURCES:
        raise ContractError("ANALYSIS_OUTPUT_INVALID")
    _bounded_int(
        result["rating_pair_count"],
        0,
        MAX_TOTAL_RATING_PAIRS,
        "ANALYSIS_OUTPUT_INVALID",
    )
    if result["gate_status"] not in AGREEMENT_STATUSES:
        raise ContractError("ANALYSIS_OUTPUT_INVALID")
    threshold = _validate_fraction(
        result["threshold"],
        "ANALYSIS_OUTPUT_INVALID",
    )
    if threshold != {"denominator": 5, "numerator": 3}:
        raise ContractError("ANALYSIS_OUTPUT_INVALID")
    _validate_fraction(
        result["point_kappa"],
        "ANALYSIS_OUTPUT_INVALID",
        nullable=True,
    )
    _validate_fraction(
        result["minimum_delete_one_kappa"],
        "ANALYSIS_OUTPUT_INVALID",
        nullable=True,
    )
    return result


def _validate_dimension_output(value):
    result = _closed_object(
        value,
        (
            "dimensions",
            "editorial_approval",
            "editorial_quality_outcome",
            "technical_outcome",
        ),
        "ANALYSIS_OUTPUT_INVALID",
    )
    if result["editorial_approval"] != "HUMAN_DECISION_REQUIRED":
        raise ContractError("ANALYSIS_OUTPUT_INVALID")
    if result["editorial_quality_outcome"] not in (
        "EDITORIAL_QUALITY_GATES_FAIL",
        "EDITORIAL_QUALITY_GATES_PASS",
    ):
        raise ContractError("ANALYSIS_OUTPUT_INVALID")
    if result["technical_outcome"] not in (
        "TECHNICAL_GATE_FAIL",
        "TECHNICAL_GATE_PASS",
    ):
        raise ContractError("ANALYSIS_OUTPUT_INVALID")
    dimensions = _bounded_list(
        result["dimensions"],
        len(QUALITY_DIMENSIONS),
        len(QUALITY_DIMENSIONS),
        "ANALYSIS_OUTPUT_INVALID",
    )
    observed_dimensions = []
    for raw_dimension in dimensions:
        dimension = _closed_object(
            raw_dimension,
            ("dimension", "floor", "gate_status", "minimum_n", "strata"),
            "ANALYSIS_OUTPUT_INVALID",
        )
        name = dimension["dimension"]
        if name not in QUALITY_DIMENSIONS:
            raise ContractError("ANALYSIS_OUTPUT_INVALID")
        observed_dimensions.append(name)
        _validate_fraction(
            dimension["floor"],
            "ANALYSIS_OUTPUT_INVALID",
        )
        if dimension["gate_status"] not in DIMENSION_GATE_STATUSES:
            raise ContractError("ANALYSIS_OUTPUT_INVALID")
        _bounded_int(
            dimension["minimum_n"],
            0,
            MAX_UNITS,
            "ANALYSIS_OUTPUT_INVALID",
        )
        strata = _bounded_list(
            dimension["strata"],
            len(STRATA),
            len(STRATA),
            "ANALYSIS_OUTPUT_INVALID",
        )
        observed_strata = []
        for raw_stratum in strata:
            stratum = _closed_object(
                raw_stratum,
                (
                    "applicable_count",
                    "assigned_count",
                    "confidence_floor_met",
                    "gate_status",
                    "not_applicable_count",
                    "observed_rate",
                    "stratum",
                    "success_count",
                ),
                "ANALYSIS_OUTPUT_INVALID",
            )
            stratum_name = stratum["stratum"]
            if stratum_name not in STRATA:
                raise ContractError("ANALYSIS_OUTPUT_INVALID")
            observed_strata.append(stratum_name)
            assigned = _bounded_int(
                stratum["assigned_count"],
                0,
                MAX_UNITS,
                "ANALYSIS_OUTPUT_INVALID",
            )
            applicable = _bounded_int(
                stratum["applicable_count"],
                0,
                assigned,
                "ANALYSIS_OUTPUT_INVALID",
            )
            success = _bounded_int(
                stratum["success_count"],
                0,
                applicable,
                "ANALYSIS_OUTPUT_INVALID",
            )
            not_applicable = _bounded_int(
                stratum["not_applicable_count"],
                0,
                assigned,
                "ANALYSIS_OUTPUT_INVALID",
            )
            if applicable + not_applicable != assigned:
                raise ContractError("ANALYSIS_OUTPUT_INVALID")
            if stratum["gate_status"] not in DIMENSION_STRATUM_STATUSES:
                raise ContractError("ANALYSIS_OUTPUT_INVALID")
            rate = _validate_fraction(
                stratum["observed_rate"],
                "ANALYSIS_OUTPUT_INVALID",
                nullable=True,
            )
            if applicable == 0:
                if rate is not None:
                    raise ContractError("ANALYSIS_OUTPUT_INVALID")
            elif (
                rate["numerator"] < 0
                or rate["numerator"] > rate["denominator"]
                or rate["numerator"] * applicable
                != success * rate["denominator"]
            ):
                raise ContractError("ANALYSIS_OUTPUT_INVALID")
            confidence = stratum["confidence_floor_met"]
            if name == "schema_atom_stability":
                if confidence is not None or applicable != assigned:
                    raise ContractError("ANALYSIS_OUTPUT_INVALID")
            elif type(confidence) is not bool:
                raise ContractError("ANALYSIS_OUTPUT_INVALID")
        if tuple(observed_strata) != STRATA:
            raise ContractError("ANALYSIS_OUTPUT_INVALID")
    if tuple(observed_dimensions) != QUALITY_DIMENSIONS:
        raise ContractError("ANALYSIS_OUTPUT_INVALID")
    return result


def _validate_cfa_output(value):
    result = _closed_object(
        value,
        (
            "confidence_ceiling_met",
            "event_count",
            "gate_status",
            "minimum_n",
            "risk_class",
            "source_generation_count",
            "upper_bound_ceiling",
        ),
        "ANALYSIS_OUTPUT_INVALID",
    )
    source_count = _bounded_int(
        result["source_generation_count"],
        0,
        MAX_UNITS,
        "ANALYSIS_OUTPUT_INVALID",
    )
    _bounded_int(
        result["event_count"],
        0,
        source_count,
        "ANALYSIS_OUTPUT_INVALID",
    )
    if (
        type(result["confidence_ceiling_met"]) is not bool
        or result["gate_status"] not in CFA_STATUSES
        or result["risk_class"] not in RISK_CLASSES
    ):
        raise ContractError("ANALYSIS_OUTPUT_INVALID")
    _bounded_int(
        result["minimum_n"],
        203,
        203,
        "ANALYSIS_OUTPUT_INVALID",
    )
    ceiling = _validate_fraction(
        result["upper_bound_ceiling"],
        "ANALYSIS_OUTPUT_INVALID",
    )
    if ceiling != {"denominator": 50, "numerator": 1}:
        raise ContractError("ANALYSIS_OUTPUT_INVALID")
    return result


def _validate_aggregate_output(value):
    result = _closed_object(
        value,
        (
            "aggregate_status",
            "editorial_approval",
            "editorial_gate_status",
            "gate_counts",
            "result_counts",
            "technical_gate_status",
        ),
        "ANALYSIS_OUTPUT_INVALID",
    )
    if (
        result["aggregate_status"]
        not in ("AGGREGATE_GATES_FAIL", "AGGREGATE_GATES_PASS")
        or result["editorial_approval"] != "HUMAN_DECISION_REQUIRED"
        or result["editorial_gate_status"]
        not in ("EDITORIAL_GATES_FAIL", "EDITORIAL_GATES_PASS")
        or result["technical_gate_status"]
        not in ("TECHNICAL_GATES_FAIL", "TECHNICAL_GATES_PASS")
    ):
        raise ContractError("ANALYSIS_OUTPUT_INVALID")
    gate_counts = _closed_object(
        result["gate_counts"],
        (
            "agreement_failed_count",
            "agreement_scope_count",
            "cfa_failed_count",
            "cfa_scope_count",
            "dimension_failed_count",
            "dimension_scope_count",
        ),
        "ANALYSIS_OUTPUT_INVALID",
    )
    agreement_scopes = _bounded_int(
        gate_counts["agreement_scope_count"],
        1,
        MAX_GATE_STATUSES,
        "ANALYSIS_OUTPUT_INVALID",
    )
    _bounded_int(
        gate_counts["agreement_failed_count"],
        0,
        agreement_scopes,
        "ANALYSIS_OUTPUT_INVALID",
    )
    cfa_scopes = _bounded_int(
        gate_counts["cfa_scope_count"],
        1,
        MAX_GATE_STATUSES,
        "ANALYSIS_OUTPUT_INVALID",
    )
    _bounded_int(
        gate_counts["cfa_failed_count"],
        0,
        cfa_scopes,
        "ANALYSIS_OUTPUT_INVALID",
    )
    dimension_scopes = _bounded_int(
        gate_counts["dimension_scope_count"],
        len(QUALITY_DIMENSIONS),
        len(QUALITY_DIMENSIONS),
        "ANALYSIS_OUTPUT_INVALID",
    )
    _bounded_int(
        gate_counts["dimension_failed_count"],
        0,
        dimension_scopes,
        "ANALYSIS_OUTPUT_INVALID",
    )
    result_counts = _closed_object(
        result["result_counts"],
        (
            "approved_critical_finding_count",
            "approved_d1_defect_count",
            "editorially_approved_count",
            "mandatory_human_evidence_missing_count",
            "result_count",
            "technical_safe_count",
        ),
        "ANALYSIS_OUTPUT_INVALID",
    )
    result_count = _bounded_int(
        result_counts["result_count"],
        1,
        MAX_UNITS,
        "ANALYSIS_OUTPUT_INVALID",
    )
    approved_count = _bounded_int(
        result_counts["editorially_approved_count"],
        0,
        result_count,
        "ANALYSIS_OUTPUT_INVALID",
    )
    technical_safe_count = _bounded_int(
        result_counts["technical_safe_count"],
        0,
        result_count,
        "ANALYSIS_OUTPUT_INVALID",
    )
    if approved_count > technical_safe_count:
        raise ContractError("ANALYSIS_OUTPUT_INVALID")
    _bounded_int(
        result_counts["mandatory_human_evidence_missing_count"],
        0,
        result_count,
        "ANALYSIS_OUTPUT_INVALID",
    )
    for field in (
        "approved_critical_finding_count",
        "approved_d1_defect_count",
    ):
        _bounded_int(
            result_counts[field],
            0,
            approved_count,
            "ANALYSIS_OUTPUT_INVALID",
        )
    if result["aggregate_status"] == "AGGREGATE_GATES_PASS":
        if (
            result["editorial_gate_status"] != "EDITORIAL_GATES_PASS"
            or result["technical_gate_status"] != "TECHNICAL_GATES_PASS"
        ):
            raise ContractError("ANALYSIS_OUTPUT_INVALID")
    return result


def _scan_public_result(value):
    pending = [value]
    nodes = 0
    while pending:
        current = pending.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise ContractError("ANALYSIS_OUTPUT_INVALID")
        if type(current) is dict:
            for key, item in current.items():
                if type(key) is not str:
                    raise ContractError("ANALYSIS_OUTPUT_INVALID")
                if key.casefold() in _RAW_OR_PATH_KEYS:
                    raise ContractError("ANALYSIS_OUTPUT_INVALID")
                pending.append(item)
        elif type(current) is list:
            if len(current) > MAX_SEQUENCE_ENTRIES:
                raise ContractError("ANALYSIS_OUTPUT_INVALID")
            pending.extend(current)
        elif type(current) is str:
            _bounded_string(
                current,
                0,
                4096,
                "ANALYSIS_OUTPUT_INVALID",
                ascii_only=True,
            )
        elif current is None or type(current) in (bool, int):
            continue
        else:
            raise ContractError("ANALYSIS_OUTPUT_INVALID")


def _validate_analysis_output(value, action):
    if type(value) is not dict or value.get("status") not in ("error", "ok"):
        raise ContractError("ANALYSIS_OUTPUT_INVALID")
    if value["status"] == "ok":
        fields = (
            "action",
            "analysis_policy_version",
            "protocol_generation",
            "result",
            "status",
        )
    else:
        fields = (
            "action",
            "analysis_policy_version",
            "code",
            "protocol_generation",
            "status",
        )
    _closed_object(value, fields, "ANALYSIS_OUTPUT_INVALID")
    if (
        value["action"] != action
        or value["analysis_policy_version"] != ANALYSIS_POLICY_VERSION
        or type(value["protocol_generation"]) is not int
        or value["protocol_generation"] != PROTOCOL_GENERATION
    ):
        raise ContractError("ANALYSIS_OUTPUT_INVALID")
    if value["status"] == "error":
        if value["code"] not in ANALYSIS_ERROR_CODES:
            raise ContractError("ANALYSIS_OUTPUT_INVALID")
    else:
        if action == "agreement":
            _validate_agreement_output(value["result"])
        elif action == "dimension_gates":
            _validate_dimension_output(value["result"])
        elif action == "cfa_gate":
            _validate_cfa_output(value["result"])
        elif action == "aggregate":
            _validate_aggregate_output(value["result"])
        else:
            raise ContractError("ANALYSIS_OUTPUT_INVALID")
        _scan_public_result(value["result"])
    return value


def _bind_module(module, module_name, function_name, error_name, code):
    if type(module) is not types.ModuleType or module.__name__ != module_name:
        raise ContractError(code)
    function = module.__dict__.get(function_name)
    error_type = module.__dict__.get(error_name)
    if (
        type(function) is not types.FunctionType
        or function.__name__ != function_name
        or function.__module__ != module_name
        or type(error_type) is not type
        or error_type.__name__ != error_name
        or error_type.__module__ != module_name
        or not issubclass(error_type, Exception)
    ):
        raise ContractError(code)
    return function, error_type


def _bind_roles(analysis_engine_module, materializer_module):
    analysis = _bind_module(
        analysis_engine_module,
        "analysis_engine",
        "analyze_validated_request",
        "AnalysisError",
        "ANALYSIS_MODULE_INVALID",
    )
    materializer = _bind_module(
        materializer_module,
        "synthetic_fixture_materializer",
        "materialize_case",
        "MaterializationError",
        "MODULE_BINDING_INVALID",
    )
    return analysis, materializer


def _materialize_request(case, function, error_type):
    try:
        data = function(case)
    except Exception as error:
        if type(error) is error_type:
            code = getattr(error, "code", None)
            if code in MATERIALIZATION_ERROR_CODES:
                raise ContractError(code)
        raise ContractError("MATERIALIZATION_FAILURE")
    if type(data) is not bytes:
        raise ContractError("MATERIALIZATION_FAILURE")
    return validate_request_bytes(data)


def _call_analysis(request, function, error_type):
    try:
        output = function(request)
    except Exception as error:
        if type(error) is error_type:
            code = getattr(error, "code", None)
            if code in ANALYSIS_ERROR_CODES:
                raise ContractError(code)
        raise ContractError("UNEXPECTED_FAILURE")
    output = _validate_analysis_output(output, request["action"])
    if output["status"] == "error":
        raise ContractError(output["code"])
    return output


def _request_counts(request, result):
    counts = _empty_counts()
    counts["request_rows"] = 1
    counts["result_rows"] = 1
    if request["action"] == "provider_request":
        counts["profile_rows"] = 1
        counts["accounting_rows"] = 1
        counts["finding_rows"] = result["finding_count"]
        counts["gate_rows"] = result["gate_count"]
    return counts


def process_entrypoint_bytes(
    data,
    analysis_engine_module,
    synthetic_fixture_materializer_module,
):
    """Process one bounded direct or synthetic request under explicit roles."""

    analysis_binding, materializer_binding = _bind_roles(
        analysis_engine_module,
        synthetic_fixture_materializer_module,
    )
    envelope = _closed_object(
        parse_json_bytes(data),
        ENTRYPOINT_FIELDS,
        "ENTRYPOINT_INPUT_INVALID",
    )
    if envelope["entrypoint_schema"] != ENTRYPOINT_SCHEMA:
        raise ContractError("ENTRYPOINT_INPUT_INVALID")
    if envelope["mode"] == "direct":
        request = validate_request(envelope["value"])
    elif envelope["mode"] == "synthetic_case":
        request = _materialize_request(
            envelope["value"],
            materializer_binding[0],
            materializer_binding[1],
        )
    else:
        raise ContractError("ENTRYPOINT_INPUT_INVALID")
    if request["action"] == "provider_request":
        profile, provider_request = _validate_provider_payload(request["payload"])
        result = _perform_provider_request(profile, provider_request)
    else:
        result = _call_analysis(
            request,
            analysis_binding[0],
            analysis_binding[1],
        )
    return {
        "codes": [],
        "counts": _request_counts(request, result),
        "result": result,
        "status": "ok",
    }


def _read_bounded_stdin():
    try:
        data = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    except (OSError, ValueError):
        raise ContractError("ENTRYPOINT_INPUT_INVALID")
    if type(data) is not bytes:
        raise ContractError("ENTRYPOINT_INPUT_INVALID")
    if len(data) > MAX_INPUT_BYTES:
        raise ContractError("INPUT_SIZE_LIMIT")
    return data


def _write_public_outcome(value):
    data = _canonical_json(value) + b"\n"
    try:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    except (OSError, ValueError):
        raise SystemExit(2)


def provider_entrypoint(
    analysis_engine_module,
    synthetic_fixture_materializer_module,
):
    """Closed future bootstrap for exact externally manifest-bound roles."""

    exit_code = 0
    try:
        outcome = process_entrypoint_bytes(
            _read_bounded_stdin(),
            analysis_engine_module,
            synthetic_fixture_materializer_module,
        )
    except ContractError as error:
        exit_code = 2
        outcome = {
            "codes": [error.code],
            "counts": _empty_counts(),
            "status": "error",
        }
    except Exception:
        exit_code = 2
        outcome = {
            "codes": ["UNEXPECTED_FAILURE"],
            "counts": _empty_counts(),
            "status": "error",
        }
    _write_public_outcome(outcome)
    raise SystemExit(exit_code)
