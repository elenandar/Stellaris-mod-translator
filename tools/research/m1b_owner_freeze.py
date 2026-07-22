#!/usr/bin/env python3
"""Offline verifier for the external M1B owner-freeze decision.

The verifier accepts only two explicitly supplied repository records: an
immutable registry snapshot and a separate owner-controlled decision record.
It performs no provider, network, environment, home, corpus, game, Workshop,
launcher, report, or fixture discovery.  A successful result proves only that
the two public records match the exact declarative v7/generation 108 proposal.
It does not create live admission or an M1B feasibility verdict.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from typing import Any, Dict, Mapping, Optional, Sequence, Set, Tuple


MAX_INPUT_BYTES = 64 * 1024
MAX_JSON_INTEGER = (1 << 63) - 1
MIN_JSON_INTEGER = -(1 << 63)

REGISTRY_SNAPSHOT_SCHEMA = "m1b-owner-freeze-registry-snapshot-v1"
REGISTRY_SNAPSHOT_FRAMING = (
    "m1b-owner-freeze-registry-snapshot-sha256-v1"
)
OWNER_DECISION_SCHEMA = "m1b-owner-freeze-decision-v1"
PROTOCOL_VERSION = "m1b-benchmark-contract-v7"
PROTOCOL_GENERATION = 108
DEFINITION_BUNDLE_SHA256 = (
    "50f51b3cf9be042ebc310d1a6c57791dd31a43362778798455d7ea9678c31e06"
)
ACCEPTANCE_STATE = "owner_accepted"
ACCEPTANCE_SCOPE = "m1b_1a_preparation_basis_only"
OPERATIONAL_EFFECT = "after_review_and_merge_to_main"
NEXT_STAGE = "m1b_1a_local_synthetic_provider_preflight"

_SNAPSHOT_DOMAIN = b"stellaris-m1b-owner-freeze-registry-snapshot-v1\x00"
_LEGACY_BUNDLE_DOMAIN = b"stellaris-m1b-bundle-v1\x00"
_TOKEN = re.compile(r"[a-z0-9._-]+", re.ASCII)
_DIGEST = re.compile(r"[0-9a-f]{64}", re.ASCII)
_CODE = re.compile(r"[A-Z][A-Z0-9_]+", re.ASCII)

EXPECTED_COMPONENT_ROWS: Tuple[Tuple[str, str, int, str], ...] = (
    (
        "analysis_policy",
        "m1b-analysis-policy-v6",
        108,
        "53fc6ba8bebeb7a872c937b2e5096b9bbee04ff01d2a66d1815ac38365a6ac74",
    ),
    (
        "benchmark_contract",
        "m1b-benchmark-contract-v7",
        108,
        "4d5a1d1b343cbed19bac4f9d6e58101975a62c2e30d9f6eaa2730b37e8a59532",
    ),
    (
        "candidate_profile.deepseek_r1_32b",
        "m1b-primary-common-profile-v1",
        202,
        "0a9aecddf4fb4dc4a090434c1b5b7f66cfe69b64392a527bf3c5f5d95b24c3a3",
    ),
    (
        "candidate_profile.glm_4_7_flash",
        "m1b-primary-common-profile-v1",
        202,
        "1ac428581d95f9862e956da9def260ac6b0de12d960bfb80cf0c4df38d63ad8e",
    ),
    (
        "candidate_profile.gpt_oss_20b",
        "m1b-primary-common-profile-v1",
        202,
        "2651960755cd898064f48cf5f948c4b00976104b5bcfe54a62fe5bea3ac53933",
    ),
    (
        "context_limit_policy",
        "m1b-context-limit-policy-v2",
        105,
        "c5e60400a7783c0635d34019d0cb32a3506080297e6f7bae82ce21e4457cc0e5",
    ),
    (
        "corpus_policy",
        "m1b-corpus-policy-v3",
        105,
        "83943902f422a4ebc00e4e3abb150f7f27496ff71a63b76c33b96eaa84a30ee4",
    ),
    (
        "generation_policy",
        "m1b-generation-policy-v2",
        105,
        "a9fc7d94a890491945e141fb1e5eefd591d29200220d410991cc9fa4c955b7ce",
    ),
    (
        "implementation_identity_policy",
        "m1b-implementation-identity-policy-v2",
        108,
        "826d976613f44657c5a2ae9299d3cc80ad21751eb7298989a24653d0849de784",
    ),
    (
        "measurement_policy",
        "m1b-measurement-policy-v4",
        106,
        "194d87ef56600b13d7171ed8cd54f89acabdf42e1fc51eb3bdecf80b2c53b549",
    ),
    (
        "output_schema",
        "m1b-synthetic-output-v4",
        105,
        "1be06166d50a33934c40f20916e28db70ce161cb7689defba924a826cb79afd7",
    ),
    (
        "prompt_policy",
        "m1b-synthetic-prompt-policy-v1",
        101,
        "54e929fd64cab6e20683f2f18ac4408ff30909b7ecff38674fd59395c523859d",
    ),
    (
        "quality_rubric",
        "m1b-quality-rubric-v6",
        106,
        "220a56232b672ffbe215ee18d067a5a279bbacf2596d3993aac1d2a71eb6f978",
    ),
    (
        "randomization_blinding_policy",
        "m1b-randomization-blinding-policy-v3",
        105,
        "ce8ea00e77c5650d7e6dc4f105f55c084a90dda6e8f366ecfffd18a336781f34",
    ),
    (
        "retention_leakage_policy",
        "m1b-retention-leakage-policy-v1",
        101,
        "a13f2b1c342a60dff0c341715708432a77b2fc34354d630b6e50807e4aacb13b",
    ),
    (
        "split_policy",
        "m1b-split-policy-v5",
        108,
        "16fe20df047eed035507f62f2887ad39746da218babf12c23d4219b0fd8c3ef6",
    ),
    (
        "validator_policy",
        "m1b-validator-policy-v7",
        108,
        "a3f6399c76d49a31eb9cf542c2850185d23e5f4d53b48ebc010f580b38804201",
    ),
)

PRESERVED_BLOCKERS = (
    "EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN",
    "CONTEXT_LIMIT_BINDING_UNPROVEN",
    "PROVIDER_PERSISTENCE_UNPROVEN",
    "RESIDENCY_UNPROVEN",
    "OUTPUT_LIMIT_BINDING_UNPROVEN",
    "LIFECYCLE_STATE_UNPROVEN",
)

_SNAPSHOT_FIELDS = (
    "acceptance_state",
    "components",
    "definition_bundle_sha256",
    "framing",
    "protocol_generation",
    "protocol_version",
    "schema_version",
)
_COMPONENT_FIELDS = (
    "component_sha256",
    "generation",
    "kind",
    "version",
)
_DECISION_FIELDS = (
    "acceptance_scope",
    "acceptance_state",
    "blockers",
    "complete_benchmark_authorized",
    "complete_benchmark_schema_v4",
    "component_count",
    "definition_bundle_sha256",
    "effect",
    "m1a_state",
    "m1b_state",
    "m2_state",
    "missing_freeze_inputs",
    "model_calls_authorized",
    "next_stage_after_merge",
    "owner_decision_schema",
    "owner_delegation",
    "private_corpus_authorized",
    "protocol_generation",
    "protocol_version",
    "registry_snapshot_framing",
    "registry_snapshot_schema",
    "registry_snapshot_sha256",
)


class OwnerFreezeError(RuntimeError):
    """A controlled failure that never carries record content."""

    def __init__(self, code: str) -> None:
        if type(code) is not str or _CODE.fullmatch(code) is None:
            code = "UNEXPECTED_FAILURE"
        self.code = code
        super().__init__(code)


def _duplicate_safe_object(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OwnerFreezeError("JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> None:
    raise OwnerFreezeError("JSON_MALFORMED")


def _reject_json_float(_value: str) -> None:
    raise OwnerFreezeError("JSON_FLOAT_FORBIDDEN")


def _parse_bounded_int(token: str) -> int:
    if type(token) is not str or not token:
        raise OwnerFreezeError("JSON_INTEGER_OUT_OF_RANGE")
    negative = token.startswith("-")
    digits = token[1:] if negative else token
    if not digits or not digits.isascii() or not digits.isdigit():
        raise OwnerFreezeError("JSON_INTEGER_OUT_OF_RANGE")
    limit = "9223372036854775808" if negative else "9223372036854775807"
    if len(digits) > len(limit) or (
        len(digits) == len(limit) and digits > limit
    ):
        raise OwnerFreezeError("JSON_INTEGER_OUT_OF_RANGE")
    value = int(token, 10)
    if value < MIN_JSON_INTEGER or value > MAX_JSON_INTEGER:
        raise OwnerFreezeError("JSON_INTEGER_OUT_OF_RANGE")
    return value


def _assert_unicode_scalars(value: Any) -> None:
    if type(value) is str:
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            raise OwnerFreezeError("JSON_UNICODE_INVALID")
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
    """Parse one bounded strict UTF-8 JSON value."""

    if type(data) is not bytes:
        raise OwnerFreezeError("INVALID_TYPE")
    if len(data) > MAX_INPUT_BYTES:
        raise OwnerFreezeError("INPUT_SIZE_LIMIT")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise OwnerFreezeError("UTF8_INVALID")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_safe_object,
            parse_constant=_reject_json_constant,
            parse_float=_reject_json_float,
            parse_int=_parse_bounded_int,
        )
    except OwnerFreezeError:
        raise
    except RecursionError:
        raise OwnerFreezeError("JSON_NESTING_LIMIT")
    except (json.JSONDecodeError, TypeError, ValueError):
        raise OwnerFreezeError("JSON_MALFORMED")
    _assert_unicode_scalars(value)
    return value


def _read_explicit_regular_file(value: str) -> bytes:
    if type(value) is not str or not value or "\x00" in value:
        raise OwnerFreezeError("INPUT_READ_FAILED")
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    descriptor = -1
    try:
        descriptor = os.open(value, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise OwnerFreezeError("INPUT_FILE_INVALID")
        if before.st_size > MAX_INPUT_BYTES:
            raise OwnerFreezeError("INPUT_SIZE_LIMIT")
        chunks = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 8192))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if len(data) > MAX_INPUT_BYTES:
            raise OwnerFreezeError("INPUT_SIZE_LIMIT")
        after = os.fstat(descriptor)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_identity != after_identity:
            raise OwnerFreezeError("INPUT_CHANGED")
        if len(data) != before.st_size:
            raise OwnerFreezeError("INPUT_CHANGED")
        return data
    except OwnerFreezeError:
        raise
    except (OSError, OverflowError, ValueError):
        raise OwnerFreezeError("INPUT_READ_FAILED")
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _require_object(value: Any, fields: Sequence[str], code: str) -> Dict[str, Any]:
    if type(value) is not dict or set(value) != set(fields):
        raise OwnerFreezeError(code)
    return value


def _require_string(value: Any, code: str) -> str:
    if type(value) is not str:
        raise OwnerFreezeError(code)
    return value


def _require_int(value: Any, code: str) -> int:
    if type(value) is not int or value < 1 or value > MAX_JSON_INTEGER:
        raise OwnerFreezeError(code)
    return value


def _ascii_token(value: Any, code: str) -> bytes:
    text = _require_string(value, code)
    if _TOKEN.fullmatch(text) is None:
        raise OwnerFreezeError(code)
    try:
        return text.encode("ascii", errors="strict")
    except UnicodeEncodeError:
        raise OwnerFreezeError(code)


def _digest_bytes(value: Any, code: str) -> bytes:
    text = _require_string(value, code)
    if _DIGEST.fullmatch(text) is None:
        raise OwnerFreezeError(code)
    return bytes.fromhex(text)


def _framed_ascii(value: str) -> bytes:
    encoded = value.encode("ascii", errors="strict")
    return len(encoded).to_bytes(4, "big") + encoded


def legacy_bundle_digest(
    rows: Sequence[Tuple[str, str, int, str]],
) -> str:
    """Independently recompute the v7 bundle digest from component identities."""

    prepared = []
    seen: Set[Tuple[bytes, bytes]] = set()
    for row in rows:
        if type(row) not in (list, tuple) or len(row) != 4:
            raise OwnerFreezeError("COMPONENT_IDENTITY_MISMATCH")
        kind = _ascii_token(row[0], "COMPONENT_IDENTITY_MISMATCH")
        version = _ascii_token(row[1], "COMPONENT_IDENTITY_MISMATCH")
        digest = _digest_bytes(row[3], "COMPONENT_IDENTITY_MISMATCH")
        pair = (kind, version)
        if pair in seen:
            raise OwnerFreezeError("COMPONENT_DUPLICATE")
        seen.add(pair)
        prepared.append((kind, version, digest))
    framed = [_LEGACY_BUNDLE_DOMAIN, len(prepared).to_bytes(4, "big")]
    for kind, version, digest in sorted(prepared, key=lambda item: (item[0], item[1])):
        framed.extend(
            (
                len(kind).to_bytes(4, "big"),
                kind,
                len(version).to_bytes(4, "big"),
                version,
                digest,
            )
        )
    return hashlib.sha256(b"".join(framed)).hexdigest()


def registry_snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    """Return the domain-separated digest of one already validated snapshot."""

    components = snapshot["components"]
    framed = [
        _SNAPSHOT_DOMAIN,
        _framed_ascii(snapshot["schema_version"]),
        _framed_ascii(snapshot["framing"]),
        _framed_ascii(snapshot["protocol_version"]),
        snapshot["protocol_generation"].to_bytes(8, "big"),
        bytes.fromhex(snapshot["definition_bundle_sha256"]),
        _framed_ascii(snapshot["acceptance_state"]),
        len(components).to_bytes(4, "big"),
    ]
    for component in components:
        framed.extend(
            (
                _framed_ascii(component["kind"]),
                _framed_ascii(component["version"]),
                component["generation"].to_bytes(8, "big"),
                bytes.fromhex(component["component_sha256"]),
            )
        )
    return hashlib.sha256(b"".join(framed)).hexdigest()


def validate_registry_snapshot(value: Any) -> Tuple[Dict[str, Any], str]:
    if type(value) is dict and any(
        field in value
        for field in ("registry_snapshot_sha256", "sha256", "self_hash")
    ):
        raise OwnerFreezeError("REGISTRY_SNAPSHOT_SELF_HASH_FORBIDDEN")
    snapshot = _require_object(value, _SNAPSHOT_FIELDS, "REGISTRY_SNAPSHOT_INVALID")
    if snapshot["schema_version"] != REGISTRY_SNAPSHOT_SCHEMA:
        raise OwnerFreezeError("REGISTRY_SNAPSHOT_SCHEMA_UNSUPPORTED")
    if snapshot["framing"] != REGISTRY_SNAPSHOT_FRAMING:
        raise OwnerFreezeError("REGISTRY_SNAPSHOT_FRAMING_UNSUPPORTED")
    if snapshot["protocol_version"] != PROTOCOL_VERSION:
        raise OwnerFreezeError("PROTOCOL_VERSION_MISMATCH")
    if (
        _require_int(snapshot["protocol_generation"], "INVALID_INTEGER")
        != PROTOCOL_GENERATION
    ):
        raise OwnerFreezeError("PROTOCOL_GENERATION_MISMATCH")
    if snapshot["definition_bundle_sha256"] != DEFINITION_BUNDLE_SHA256:
        raise OwnerFreezeError("DEFINITION_BUNDLE_HASH_MISMATCH")
    _digest_bytes(snapshot["definition_bundle_sha256"], "DEFINITION_BUNDLE_HASH_MISMATCH")
    if snapshot["acceptance_state"] != ACCEPTANCE_STATE:
        raise OwnerFreezeError("ACCEPTANCE_STATE_MISMATCH")
    if type(snapshot["components"]) is not list:
        raise OwnerFreezeError("COMPONENT_SET_INVALID")
    if len(snapshot["components"]) != len(EXPECTED_COMPONENT_ROWS):
        raise OwnerFreezeError("COMPONENT_COUNT_MISMATCH")

    rows = []
    seen: Set[Tuple[str, str]] = set()
    for raw in snapshot["components"]:
        component = _require_object(raw, _COMPONENT_FIELDS, "COMPONENT_ROW_INVALID")
        kind = _require_string(component["kind"], "COMPONENT_ROW_INVALID")
        version = _require_string(component["version"], "COMPONENT_ROW_INVALID")
        _ascii_token(kind, "COMPONENT_ROW_INVALID")
        _ascii_token(version, "COMPONENT_ROW_INVALID")
        generation = _require_int(component["generation"], "INVALID_INTEGER")
        digest = _require_string(
            component["component_sha256"], "COMPONENT_ROW_INVALID"
        )
        _digest_bytes(digest, "COMPONENT_ROW_INVALID")
        pair = (kind, version)
        if pair in seen:
            raise OwnerFreezeError("COMPONENT_DUPLICATE")
        seen.add(pair)
        rows.append((kind, version, generation, digest))

    actual_pairs = tuple((row[0], row[1]) for row in rows)
    expected_pairs = tuple((row[0], row[1]) for row in EXPECTED_COMPONENT_ROWS)
    if set(actual_pairs) == set(expected_pairs) and actual_pairs != expected_pairs:
        raise OwnerFreezeError("COMPONENT_ORDER_NONCANONICAL")
    if tuple(rows) != EXPECTED_COMPONENT_ROWS:
        raise OwnerFreezeError("COMPONENT_IDENTITY_MISMATCH")
    if legacy_bundle_digest(rows) != DEFINITION_BUNDLE_SHA256:
        raise OwnerFreezeError("DEFINITION_BUNDLE_HASH_MISMATCH")
    return snapshot, registry_snapshot_digest(snapshot)


def validate_owner_decision(value: Any, snapshot_digest: str) -> Dict[str, Any]:
    decision = _require_object(value, _DECISION_FIELDS, "OWNER_DECISION_INVALID")
    for field in (
        "complete_benchmark_authorized",
        "model_calls_authorized",
        "private_corpus_authorized",
    ):
        if type(decision[field]) is not bool:
            raise OwnerFreezeError("OWNER_DECISION_MISMATCH")
    for field in ("component_count", "protocol_generation"):
        if type(decision[field]) is not int:
            raise OwnerFreezeError("OWNER_DECISION_MISMATCH")
    expected = {
        "acceptance_scope": ACCEPTANCE_SCOPE,
        "acceptance_state": ACCEPTANCE_STATE,
        "blockers": list(PRESERVED_BLOCKERS),
        "complete_benchmark_authorized": False,
        "complete_benchmark_schema_v4": "PARTIAL_REPORT_CANNOT_BE_COMPLETE",
        "component_count": len(EXPECTED_COMPONENT_ROWS),
        "definition_bundle_sha256": DEFINITION_BUNDLE_SHA256,
        "effect": OPERATIONAL_EFFECT,
        "m1a_state": "blocked",
        "m1b_state": "not_evaluated",
        "m2_state": "forbidden",
        "missing_freeze_inputs": [
            "frozen_prompt_bytes",
            "frozen_template_bytes",
            "real_candidate_identities",
        ],
        "model_calls_authorized": False,
        "next_stage_after_merge": NEXT_STAGE,
        "owner_decision_schema": OWNER_DECISION_SCHEMA,
        "owner_delegation": "explicit",
        "private_corpus_authorized": False,
        "protocol_generation": PROTOCOL_GENERATION,
        "protocol_version": PROTOCOL_VERSION,
        "registry_snapshot_framing": REGISTRY_SNAPSHOT_FRAMING,
        "registry_snapshot_schema": REGISTRY_SNAPSHOT_SCHEMA,
        "registry_snapshot_sha256": snapshot_digest,
    }
    if decision != expected:
        raise OwnerFreezeError("OWNER_DECISION_MISMATCH")
    return decision


def verify_bytes(snapshot_bytes: bytes, decision_bytes: bytes) -> Dict[str, Any]:
    try:
        snapshot, digest = validate_registry_snapshot(parse_json_bytes(snapshot_bytes))
        validate_owner_decision(parse_json_bytes(decision_bytes), digest)
        return _result("ok", component_identities=len(snapshot["components"]), owner_records=1)
    except OwnerFreezeError as error:
        return _result("error", code=error.code)
    except BaseException:
        return _result("error", code="UNEXPECTED_FAILURE")


def _result(
    status: str,
    *,
    code: Optional[str] = None,
    component_identities: int = 0,
    owner_records: int = 0,
) -> Dict[str, Any]:
    return {
        "codes": [] if code is None else [code],
        "counts": {
            "component_identities": component_identities,
            "owner_records": owner_records,
        },
        "status": status,
    }


def _execute(argv: Sequence[str]) -> Dict[str, Any]:
    try:
        if len(argv) != 3 or argv[0] != "verify":
            raise OwnerFreezeError("CLI_ARGUMENTS_INVALID")
        snapshot_bytes = _read_explicit_regular_file(argv[1])
        decision_bytes = _read_explicit_regular_file(argv[2])
        return verify_bytes(snapshot_bytes, decision_bytes)
    except OwnerFreezeError as error:
        return _result("error", code=error.code)
    except BaseException:
        return _result("error", code="UNEXPECTED_FAILURE")


def _encode_result(result: Mapping[str, Any]) -> bytes:
    try:
        return (
            json.dumps(result, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
            + "\n"
        ).encode("ascii")
    except BaseException:
        return b'{"codes":["UNEXPECTED_FAILURE"],"counts":{"component_identities":0,"owner_records":0},"status":"error"}\n'


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
