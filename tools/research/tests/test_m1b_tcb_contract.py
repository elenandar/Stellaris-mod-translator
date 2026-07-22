"""Public synthetic tests for the M1B executable/TCB admission contract.

The five explicit records and four role payloads in this module are
materialized only below a temporary repository root.  Source-role surfaces
are minimal inert synthetic Python text; opaque interpreter/extension bytes
remain non-executable.  No materialized surface is imported or executed.
"""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import ast
import builtins
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools.research import m1b_tcb_contract as tcb


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CONTRACT = (
    REPOSITORY_ROOT
    / "registry"
    / "m1b"
    / "offline-executable-tcb-contract-v3.json"
)
CASES = REPOSITORY_ROOT / "fixtures" / "m1b" / "tcb-admission" / "cases.json"
VERIFIER = REPOSITORY_ROOT / "tools" / "research" / "m1b_tcb_contract.py"

IMPLEMENTATION_GENERATION = 2
PROTOCOL_GENERATION = 108
MANIFEST_SCHEMA = "m1b-executable-implementation-manifest-v1"
MANIFEST_DOMAIN = b"stellaris-m1b-executable-manifest-v1"
CONTRACT_SCHEMA = "m1b-offline-executable-tcb-contract-v3"
CONTRACT_VERSION = "m1b-offline-executable-tcb-admission-v3"
CONTRACT_GENERATION = 3
CONTRACT_DOMAIN = b"stellaris-m1b-offline-executable-tcb-contract-v3"
EXECUTION_ENVELOPE_SCHEMA = "m1b-execution-envelope-v3"
EXECUTION_ENVELOPE_GENERATION = 3
EXECUTION_ENVELOPE_DOMAIN = b"stellaris-m1b-execution-envelope-v3"
EXECUTION_ENVELOPE_DIGEST_FRAMING = (
    "sha256_domain_nul_u64be_length_canonical_envelope"
)
RUNTIME_ACCEPTANCE_SCHEMA = "m1b-runtime-execution-envelope-acceptance-v1"
RUNTIME_ACCEPTANCE_GENERATION = 1
RUNTIME_ACCEPTANCE_DOMAIN = (
    b"stellaris-m1b-runtime-execution-envelope-acceptance-v1"
)
EXECUTION_PLAN_SCHEMA = "m1b-execution-plan-v2"
EXECUTION_PLAN_GENERATION = 2

# Independently recomputed from canonical registry v3 bytes.
EXPECTED_CONTRACT_BYTES = 8438
EXPECTED_CONTRACT_FILE_SHA256 = (
    "cf91f64e8fa85dde15e85702199860f62974d86e54163b080a95fe2ac9c7a75d"
)
EXPECTED_CONTRACT_DIGEST = (
    "c346fdd761ea477a85930c041858e7444a576263f3fb5ca568cc1ab005ef9744"
)
EXPECTED_CASE_COUNT = 218
EXPECTED_CASE_BYTES = 61682
EXPECTED_CASES_SHA256 = (
    "0f14d9b28ee41095a2373b02409b288c30959013840d7d1c891538266a84eeaa"
)
EXPECTED_VERIFIER_SHA256 = (
    "0df39292b306afdfd2187ffb554b5ad2714bbe0353ca176f6fe49cf7eb162c10"
)
REQUIRED_MATRIX_IDS = frozenset(
    """
    positive-synthetic-conformance
    contract-schema-drift contract-version-drift contract-generation-drift
    contract-self-digest-field
    contract-semantic-json-noncanonical
    manifest-missing-role manifest-extra-role manifest-duplicate-role
    manifest-unknown-role manifest-one-path-multiple-roles manifest-role-swap
    manifest-path-swap manifest-digest-swap
    manifest-raw-ascii-order-wrong manifest-absolute-path manifest-empty-path
    manifest-empty-final-component manifest-dot-component
    manifest-dotdot-component manifest-repeated-separator
    manifest-backslash-path manifest-nul-path manifest-control-path
    manifest-nonascii-path manifest-self-entry
    manifest-contract-record-as-role manifest-acceptance-record-as-role
    manifest-envelope-record-as-role manifest-self-digest-field
    manifest-file-row-extra-field manifest-file-row-missing-field
    manifest-semantic-json-noncanonical manifest-wrong-file-hash
    manifest-executable-byte-change
    acceptance-proposed-state acceptance-retired-state
    acceptance-self-asserted-proven-state
    acceptance-implementation-generation-drift
    acceptance-protocol-generation-drift acceptance-wrong-manifest-digest
    acceptance-wrong-domain-digest acceptance-wrong-length-framing-digest
    acceptance-report-proven-field acceptance-fixture-expected-field
    acceptance-git-sha-as-identity
    envelope-missing-root-field envelope-extra-root-field
    envelope-semantic-json-noncanonical
    envelope-contract-version-drift envelope-contract-digest-drift
    envelope-manifest-digest-drift
    envelope-admitted-observed-drift runtime-implementation-drift
    runtime-version-drift runtime-cache-tag-drift
    runtime-byteorder-drift runtime-extension-suffix-drift
    runtime-machine-drift runtime-max-unicode-drift runtime-platform-drift
    runtime-pointer-bits-drift runtime-soabi-drift
    runtime-interpreter-digest-drift invocation-flags-drift
    invocation-argv-drift invocation-cwd-drift invocation-mode-reopen
    invocation-cwd-missing-directory invocation-cwd-regular-file
    invocation-cwd-symlink-directory
    invocation-stdio-drift invocation-inherited-fd-extra
    invocation-warnoptions-drift invocation-xoptions-drift
    python-flags-bool-as-integer python-flags-missing-field
    python-flags-extra-field
    environment-ambient-inheritance environment-variable-drift
    sys-path-ambient-user-site sys-path-unknown-entry hooks-startup-hook
    hooks-meta-path-extra hooks-path-hook-extra hooks-debugger-attached
    hooks-profile-hook hooks-trace-hook imports-missing-entry
    imports-extra-entry imports-reordered imports-source-hash-drift
    imports-extension-hash-drift imports-builtin-path-present
    imports-builtin-interpreter-digest-drift
    imports-frozen-interpreter-digest-drift bytecode-cache-not-sealed
    bytecode-write-enabled bytecode-stale-pyc-executed
    bytecode-pycache-prefix-present native-dependency-silent-bound-empty
    native-dependency-unproven-with-row native-dependency-blocker-removed
    reopened-path-instead-of-admitted-bytes
    runtime-acceptance-malformed runtime-acceptance-duplicate-key
    runtime-acceptance-noncanonical runtime-acceptance-missing-field
    runtime-acceptance-extra-field runtime-acceptance-schema-drift
    runtime-acceptance-generation-drift runtime-acceptance-proposed-state
    runtime-acceptance-retired-state runtime-acceptance-self-proven-state
    runtime-acceptance-contract-schema-drift
    runtime-acceptance-contract-version-drift
    runtime-acceptance-contract-generation-drift
    runtime-acceptance-contract-digest-drift
    runtime-acceptance-manifest-schema-drift
    runtime-acceptance-implementation-generation-drift
    runtime-acceptance-manifest-digest-drift
    runtime-acceptance-envelope-schema-drift
    runtime-acceptance-envelope-generation-drift
    runtime-acceptance-envelope-domain-drift
    runtime-acceptance-envelope-framing-drift
    runtime-acceptance-envelope-raw-sha
    runtime-acceptance-envelope-digest-drift
    runtime-acceptance-envelope-wrong-domain-digest
    runtime-acceptance-envelope-wrong-length-digest
    runtime-acceptance-protocol-generation-drift
    runtime-acceptance-stale-after-coherent-state-change
    runtime-acceptance-record-alias runtime-acceptance-cli-missing
    runtime-acceptance-cli-extra
    execution-plan-missing execution-plan-extra-field
    execution-plan-schema-drift execution-plan-generation-drift
    execution-plan-interpreter-path-drift
    execution-plan-interpreter-digest-drift
    execution-plan-entrypoint-missing execution-plan-entrypoint-wrong-role
    execution-plan-entrypoint-unlisted
    execution-plan-role-import-missing execution-plan-role-import-extra
    execution-plan-role-import-path-drift
    execution-plan-role-import-digest-drift
    execution-plan-role-import-order-swap
    execution-plan-import-binding-missing
    invocation-wrong-argv0 invocation-other-interpreter-same-bytes
    invocation-entrypoint-missing invocation-entrypoint-wrong
    invocation-inline-code invocation-module-mode invocation-stdin-mode
    invocation-double-dash-bypass invocation-unknown-flag
    invocation-reordered-flags invocation-extra-positional
    invocation-absolute-entrypoint invocation-case-alias-entrypoint
    invocation-flags-bytecode-contradiction
    invocation-xoptions-contradiction
    invocation-coherent-unsafe-inline-code
    invocation-empty-imports invocation-empty-sys-path
    coherent-harness-inline-option coherent-harness-module-option
    coherent-harness-stdin-marker coherent-harness-double-dash
    coherent-harness-unknown-option
    execution-plan-launcher-missing execution-plan-launcher-proven
    invocation-os-exec-target-wrong-base invocation-argv0-wrong-base
    invocation-cwd-wrong-base invocation-sys-path-wrong-base
    invocation-path-only-script
    entrypoint-transport-missing entrypoint-transport-extra
    entrypoint-transport-wrong-fd entrypoint-transport-stdio-collision
    entrypoint-transport-noncanonical-process-path
    entrypoint-transport-wrong-mode entrypoint-transport-wrong-kind
    entrypoint-transport-wrong-role entrypoint-transport-wrong-path
    entrypoint-transport-wrong-digest
    entrypoint-transport-wrong-byte-count
    entrypoint-transport-zero-byte-count
    entrypoint-transport-extra-field
    runtime-acceptance-stale-after-coherent-transport-change
    """.split()
)

ROLE_PAYLOADS = {
    "synthetic/analysis-engine.opaque": (
        "analysis_engine",
        b'SYNTHETIC_ROLE = "analysis_engine"\n',
    ),
    "synthetic/contract-validator.opaque": (
        "contract_validator",
        b'SYNTHETIC_ROLE = "contract_validator"\n',
    ),
    "synthetic/provider-request-harness.opaque": (
        "provider_request_harness",
        b'SYNTHETIC_ROLE = "provider_request_harness"\n',
    ),
    "synthetic/synthetic-fixture-materializer.opaque": (
        "synthetic_fixture_materializer",
        b'SYNTHETIC_ROLE = "synthetic_fixture_materializer"\n',
    ),
}

INTERPRETER_PATH = "synthetic/runtime/cpython.opaque"
SOURCE_IMPORT_PATH = "synthetic/imports/source-module.opaque"
EXTENSION_IMPORT_PATH = "synthetic/imports/extension-module.opaque"
AUXILIARY_PAYLOADS = {
    INTERPRETER_PATH: b"SYNTHETIC-OPAQUE-CPYTHON-INTERPRETER\x00NOT-EXECUTABLE\n",
    SOURCE_IMPORT_PATH: b'SYNTHETIC_ROLE = "source_import"\n',
    EXTENSION_IMPORT_PATH: b"SYNTHETIC-OPAQUE-EXTENSION-MODULE\x00NOT-A-BINARY\n",
}


def _encode(value):
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _independent_manifest_bytes(manifest):
    """Canonicalize without calling production code."""

    return _encode(manifest)


def _independent_manifest_digest(manifest_bytes):
    """Recompute the normative domain/NUL/u64be framing independently."""

    return hashlib.sha256(
        MANIFEST_DOMAIN
        + b"\x00"
        + len(manifest_bytes).to_bytes(8, "big")
        + manifest_bytes
    ).hexdigest()


def _independent_contract_digest(contract_bytes):
    return hashlib.sha256(
        CONTRACT_DOMAIN
        + b"\x00"
        + len(contract_bytes).to_bytes(8, "big")
        + contract_bytes
    ).hexdigest()


def _independent_execution_envelope_digest(envelope_bytes):
    """Recompute canonical envelope framing without production code."""

    return hashlib.sha256(
        EXECUTION_ENVELOPE_DOMAIN
        + b"\x00"
        + len(envelope_bytes).to_bytes(8, "big")
        + envelope_bytes
    ).hexdigest()


def _independent_runtime_acceptance_digest(runtime_acceptance_bytes):
    """Recompute the diagnostic external runtime-record identity."""

    return hashlib.sha256(
        RUNTIME_ACCEPTANCE_DOMAIN
        + b"\x00"
        + len(runtime_acceptance_bytes).to_bytes(8, "big")
        + runtime_acceptance_bytes
    ).hexdigest()


def _manifest_for_payloads(payloads):
    files = []
    for path in sorted(payloads, key=lambda item: item.encode("ascii")):
        role, data = payloads[path]
        files.append(
            {
                "path": path,
                "role": role,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return {
        "files": files,
        "implementation_generation": IMPLEMENTATION_GENERATION,
        "manifest_schema": MANIFEST_SCHEMA,
    }


def _execution_state(manifest, auxiliary_payloads, role_payloads=ROLE_PAYLOADS):
    interpreter_sha256 = hashlib.sha256(
        auxiliary_payloads[INTERPRETER_PATH]
    ).hexdigest()
    source_sha256 = hashlib.sha256(
        auxiliary_payloads[SOURCE_IMPORT_PATH]
    ).hexdigest()
    extension_sha256 = hashlib.sha256(
        auxiliary_payloads[EXTENSION_IMPORT_PATH]
    ).hexdigest()
    roles = {row["role"]: row for row in manifest["files"]}
    role_imports = []
    for role, module in (
        ("analysis_engine", "synthetic_analysis_engine"),
        ("contract_validator", "synthetic_contract_validator"),
        (
            "synthetic_fixture_materializer",
            "synthetic_fixture_materializer",
        ),
    ):
        row = roles[role]
        role_imports.append(
            {
                "kind": "source",
                "module": module,
                "path": row["path"],
                "role": role,
                "sha256": row["sha256"],
            }
        )
    harness = roles["provider_request_harness"]
    execution_plan = {
        "entrypoint": {
            "mode": "descriptor_script_file",
            "repository_locator": harness["path"],
            "role": "provider_request_harness",
            "sha256": harness["sha256"],
        },
        "interpreter": {
            "repository_locator": INTERPRETER_PATH,
            "sha256": interpreter_sha256,
        },
        "launcher": {
            "blockers": [
                "INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN",
                "LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN",
                "ROLE_IMPORT_TRANSPORT_UNPROVEN",
            ],
            "status": "unproven",
        },
        "plan_generation": EXECUTION_PLAN_GENERATION,
        "plan_schema": EXECUTION_PLAN_SCHEMA,
        "role_imports": role_imports,
    }
    imports = [
        {
            "kind": "frozen",
            "module": "importlib._bootstrap",
            "path": None,
            "sha256": interpreter_sha256,
        },
        {
            "kind": "extension",
            "module": "synthetic_extension",
            "path": EXTENSION_IMPORT_PATH,
            "sha256": extension_sha256,
        },
        {
            "kind": "source",
            "module": "synthetic_source",
            "path": SOURCE_IMPORT_PATH,
            "sha256": source_sha256,
        },
    ]
    imports.extend(
        {
            "kind": row["kind"],
            "module": row["module"],
            "path": row["path"],
            "sha256": row["sha256"],
        }
        for row in role_imports
    )
    imports.append(
        {
            "kind": "builtin",
            "module": "sys",
            "path": None,
            "sha256": interpreter_sha256,
        }
    )
    return {
        "bytecode": {
            "cache_mode": "sealed_empty",
            "dont_write_bytecode": True,
            "executed_bytecode": [],
            "pycache_prefix": None,
        },
        "environment": {
            "ambient_inheritance": False,
            "policy": "empty",
            "variables": [],
        },
        "execution_plan": execution_plan,
        "imports": imports,
        "interpreter": {
            "abi_flags": "",
            "byteorder": "little",
            "cache_tag": "cpython-39",
            "executable_sha256": interpreter_sha256,
            "extension_suffix": ".cpython-39-darwin.so",
            "implementation": "cpython",
            "machine": "arm64",
            "max_unicode": 1114111,
            "platform": "darwin",
            "pointer_bits": 64,
            "repository_locator": INTERPRETER_PATH,
            "soabi": "cpython-39-darwin",
            "version_tuple": [3, 9, 6, "final", 0],
        },
        "invocation": {
            "argv0": {
                "base": "repository_root",
                "path": INTERPRETER_PATH,
            },
            "argv_tail": [
                "-I",
                "-S",
                "-B",
                "-X",
                "utf8",
                "/dev/fd/3",
            ],
            "cwd": {
                "base": "repository_root",
                "path": "synthetic/work",
            },
            "inherited_fds": [
                {
                    "byte_count": len(role_payloads[harness["path"]][1]),
                    "child_fd": 3,
                    "mode": "read",
                    "process_path": "/dev/fd/3",
                    "purpose": "provider_request_harness",
                    "repository_locator": harness["path"],
                    "role": "provider_request_harness",
                    "sha256": harness["sha256"],
                    "transport": "darwin_pipe_atomic_preload_v1",
                }
            ],
            "mode": "typed_entrypoint_fd_no_repository_reopen",
            "os_exec_target": {
                "base": "repository_root",
                "path": INTERPRETER_PATH,
            },
            "python_flags": {
                "bytes_warning": 0,
                "debug": 0,
                "dev_mode": False,
                "dont_write_bytecode": 1,
                "hash_randomization": 1,
                "ignore_environment": 1,
                "inspect": 0,
                "interactive": 0,
                "isolated": 1,
                "no_site": 1,
                "no_user_site": 1,
                "optimize": 0,
                "quiet": 0,
                "utf8_mode": 1,
                "verbose": 0,
            },
            "stdio": {
                "stderr": {
                    "fd": 2,
                    "mode": "write",
                    "target": "captured_pipe",
                },
                "stdin": {"fd": 0, "mode": "read", "target": "devnull"},
                "stdout": {
                    "fd": 1,
                    "mode": "write",
                    "target": "captured_pipe",
                },
            },
            "sys_path": [
                {"base": "repository_root", "path": "synthetic"}
            ],
            "warnoptions": [],
            "xoptions": ["utf8"],
        },
        "native_dependencies": {
            "blocker": "NATIVE_DEPENDENCY_CLOSURE_UNPROVEN",
            "dependencies": [],
            "status": "unproven",
        },
        "runtime_hooks": {
            "debugger_attached": False,
            "meta_path": ["BuiltinImporter", "FrozenImporter", "PathFinder"],
            "path_hooks": ["FileFinder"],
            "profile_hook": False,
            "startup_hooks": [],
            "trace_hook": False,
        },
    }


def _acceptance_for_manifest(manifest_sha256):
    return {
        "acceptance_state": "owner_accepted",
        "implementation_generation": IMPLEMENTATION_GENERATION,
        "manifest_schema": MANIFEST_SCHEMA,
        "manifest_sha256": manifest_sha256,
        "protocol_generation": PROTOCOL_GENERATION,
    }


def _coherently_bind_harness_path(documents, harness_path):
    """Rebind every authority/linkage surface to one harness lexical path."""

    provider_rows = [
        row
        for row in documents["manifest"]["files"]
        if row["role"] == "provider_request_harness"
    ]
    if len(provider_rows) != 1:
        raise AssertionError("positive manifest must contain one provider harness")
    provider = provider_rows[0]
    provider["path"] = harness_path
    documents["manifest"]["files"].sort(
        key=lambda row: row["path"].encode("ascii")
    )
    manifest_sha256 = _independent_manifest_digest(
        _independent_manifest_bytes(documents["manifest"])
    )
    documents["acceptance"]["manifest_sha256"] = manifest_sha256
    documents["envelope"]["manifest_sha256"] = manifest_sha256
    for state_name in ("admitted_state", "observed_state"):
        state = documents["envelope"][state_name]
        entrypoint = state["execution_plan"]["entrypoint"]
        if (
            entrypoint["role"] != "provider_request_harness"
            or entrypoint["sha256"] != provider["sha256"]
        ):
            raise AssertionError("positive plan must bind the provider harness")
        entrypoint["repository_locator"] = harness_path
        fd_row = state["invocation"]["inherited_fds"][0]
        fd_row["repository_locator"] = harness_path
    documents["runtime_acceptance"]["manifest_sha256"] = manifest_sha256


def _envelope_for_manifest(
    manifest, manifest_sha256, auxiliary_payloads, role_payloads=ROLE_PAYLOADS
):
    state = _execution_state(manifest, auxiliary_payloads, role_payloads)
    return {
        "admitted_state": copy.deepcopy(state),
        "contract_generation": CONTRACT_GENERATION,
        "contract_schema": CONTRACT_SCHEMA,
        "contract_sha256": EXPECTED_CONTRACT_DIGEST,
        "contract_version": CONTRACT_VERSION,
        "envelope_generation": EXECUTION_ENVELOPE_GENERATION,
        "envelope_schema": EXECUTION_ENVELOPE_SCHEMA,
        "implementation_generation": IMPLEMENTATION_GENERATION,
        "manifest_schema": MANIFEST_SCHEMA,
        "manifest_sha256": manifest_sha256,
        "observed_state": copy.deepcopy(state),
        "protocol_generation": PROTOCOL_GENERATION,
    }


def _runtime_acceptance_for_envelope(envelope, manifest_sha256):
    envelope_bytes = _encode(envelope)
    return {
        "contract_generation": CONTRACT_GENERATION,
        "contract_schema": CONTRACT_SCHEMA,
        "contract_sha256": EXPECTED_CONTRACT_DIGEST,
        "contract_version": CONTRACT_VERSION,
        "envelope_digest_domain": EXECUTION_ENVELOPE_DOMAIN.decode("ascii"),
        "envelope_digest_framing": EXECUTION_ENVELOPE_DIGEST_FRAMING,
        "envelope_generation": EXECUTION_ENVELOPE_GENERATION,
        "envelope_schema": EXECUTION_ENVELOPE_SCHEMA,
        "envelope_sha256": _independent_execution_envelope_digest(
            envelope_bytes
        ),
        "implementation_generation": IMPLEMENTATION_GENERATION,
        "manifest_schema": MANIFEST_SCHEMA,
        "manifest_sha256": manifest_sha256,
        "protocol_generation": PROTOCOL_GENERATION,
        "runtime_acceptance_generation": RUNTIME_ACCEPTANCE_GENERATION,
        "runtime_acceptance_schema": RUNTIME_ACCEPTANCE_SCHEMA,
        "runtime_acceptance_state": "owner_accepted",
    }


def _positive_documents():
    manifest = _manifest_for_payloads(ROLE_PAYLOADS)
    manifest_bytes = _independent_manifest_bytes(manifest)
    manifest_sha256 = _independent_manifest_digest(manifest_bytes)
    envelope = _envelope_for_manifest(
        manifest, manifest_sha256, AUXILIARY_PAYLOADS
    )
    return {
        "acceptance": _acceptance_for_manifest(manifest_sha256),
        "contract": json.loads(CONTRACT.read_text("ascii")),
        "envelope": envelope,
        "manifest": manifest,
        "runtime_acceptance": _runtime_acceptance_for_envelope(
            envelope, manifest_sha256
        ),
    }


def _materialize_documents(
    root,
    documents,
    *,
    encodings=None,
    payloads=None,
    path_overrides=None,
    refresh_runtime_acceptance=True,
    coherent_harness_path=None,
):
    encodings = {} if encodings is None else encodings
    path_overrides = {} if path_overrides is None else path_overrides
    if refresh_runtime_acceptance and "runtime_acceptance" in documents:
        documents["runtime_acceptance"]["envelope_sha256"] = (
            _independent_execution_envelope_digest(
                _encode(documents["envelope"])
            )
        )
    all_payloads = dict(ROLE_PAYLOADS)
    auxiliary_payloads = dict(AUXILIARY_PAYLOADS)
    if payloads:
        all_payloads.update(payloads.get("roles", {}))
        auxiliary_payloads.update(payloads.get("auxiliary", {}))
    if coherent_harness_path is not None:
        old_harness_path = next(
            path
            for path, (role, _data) in ROLE_PAYLOADS.items()
            if role == "provider_request_harness"
        )
        if coherent_harness_path in all_payloads:
            raise AssertionError("coherent harness path collides with payload")
        all_payloads[coherent_harness_path] = all_payloads.pop(
            old_harness_path
        )
    for path, (_role, data) in all_payloads.items():
        _write_relative(root, path, data)
    for path, data in auxiliary_payloads.items():
        _write_relative(root, path, data)
    (root / "synthetic" / "work").mkdir(parents=True, exist_ok=True)

    paths = {
        "contract": "records/contract.json",
        "manifest": "records/manifest.json",
        "acceptance": "records/acceptance.json",
        "envelope": "records/envelope.json",
        "runtime_acceptance": "records/runtime-acceptance.json",
    }
    paths.update(path_overrides)
    written_paths = set()
    for target, relative in paths.items():
        # Exact record aliases deliberately reuse the first admitted bytes.
        # This lets production admission reject the second purpose before it
        # attempts to parse or reopen that path.
        if relative in written_paths:
            continue
        if target == "contract" and documents[target] == json.loads(
            CONTRACT.read_text("ascii")
        ):
            encoded = CONTRACT.read_bytes()
        else:
            encoded = _encode(documents[target])
        if encodings.get(target) == "pretty":
            encoded = (
                json.dumps(documents[target], ensure_ascii=True, sort_keys=True, indent=2)
                + "\n"
            ).encode("ascii")
        elif encodings.get(target) == "duplicate-key":
            if target != "runtime_acceptance":
                raise AssertionError("duplicate-key encoding is record-specific")
            encoded = (
                b'{"contract_generation":2,'
                + encoded[1:]
            )
        elif encodings.get(target) == "malformed":
            encoded = b'{"runtime_acceptance_schema":'
        _write_relative(root, relative, encoded)
        written_paths.add(relative)
    return paths


def _resolve(value, path):
    current = value
    for component in path:
        current = current[component]
    return current


def _parent(value, path):
    if not path:
        return None, None
    return _resolve(value, path[:-1]), path[-1]


def _fixture_value(value, documents):
    if value == "@wrong-manifest-domain":
        manifest_bytes = _independent_manifest_bytes(documents["manifest"])
        return hashlib.sha256(
            b"stellaris-m1b-executable-manifest-v0"
            + b"\x00"
            + len(manifest_bytes).to_bytes(8, "big")
            + manifest_bytes
        ).hexdigest()
    if value == "@wrong-manifest-length":
        manifest_bytes = _independent_manifest_bytes(documents["manifest"])
        return hashlib.sha256(
            MANIFEST_DOMAIN
            + b"\x00"
            + (len(manifest_bytes) + 1).to_bytes(8, "big")
            + manifest_bytes
        ).hexdigest()
    if value in (
        "@raw-envelope-sha",
        "@wrong-envelope-domain",
        "@wrong-envelope-length",
    ):
        envelope_bytes = _encode(documents["envelope"])
        if value == "@raw-envelope-sha":
            return hashlib.sha256(envelope_bytes).hexdigest()
        domain = EXECUTION_ENVELOPE_DOMAIN
        length = len(envelope_bytes)
        if value == "@wrong-envelope-domain":
            domain = b"stellaris-m1b-execution-envelope-v1"
        else:
            length += 1
        return hashlib.sha256(
            domain
            + b"\x00"
            + length.to_bytes(8, "big")
            + envelope_bytes
        ).hexdigest()
    return copy.deepcopy(value)


def _apply_case(base_documents, case):
    documents = copy.deepcopy(base_documents)
    envelope_changed = False
    for patch in case["patches"]:
        target = documents[patch["target"]]
        if patch["target"] == "envelope":
            envelope_changed = True
        operation = patch["operation"]
        path = patch["path"]
        if operation == "reverse":
            _resolve(target, path).reverse()
            continue
        if operation == "append":
            _resolve(target, path).append(
                _fixture_value(patch["value"], documents)
            )
            continue
        if operation == "swap":
            first_parent, first_leaf = _parent(target, path)
            second_parent, second_leaf = _parent(target, patch["second_path"])
            first_parent[first_leaf], second_parent[second_leaf] = (
                second_parent[second_leaf],
                first_parent[first_leaf],
            )
            continue
        parent, leaf = _parent(target, path)
        if operation == "set":
            parent[leaf] = _fixture_value(patch["value"], documents)
        elif operation == "delete":
            del parent[leaf]
        elif operation == "copy":
            parent[leaf] = copy.deepcopy(
                _resolve(target, patch["source_path"])
            )
        else:
            raise AssertionError("unknown fixture operation")
    coherent_harness_path = case.get("coherent_harness_path")
    if coherent_harness_path is not None:
        _coherently_bind_harness_path(documents, coherent_harness_path)
        envelope_changed = True
    if envelope_changed and not case.get(
        "preserve_runtime_envelope_digest", False
    ):
        documents["runtime_acceptance"]["envelope_sha256"] = (
            _independent_execution_envelope_digest(
                _encode(documents["envelope"])
            )
        )
    return documents


def _apply_filesystem_mutations(root, case):
    for mutation in case.get("filesystem", ()):
        path = root / mutation["path"]
        if mutation["operation"] == "flip-byte":
            payload = path.read_bytes()
            if not payload:
                raise AssertionError("cannot flip empty payload")
            path.write_bytes(payload[:-1] + bytes((payload[-1] ^ 1,)))
        elif mutation["operation"] == "cwd-missing":
            path.rmdir()
        elif mutation["operation"] == "cwd-regular-file":
            path.rmdir()
            path.write_bytes(mutation["marker"].encode("ascii"))
        elif mutation["operation"] == "cwd-symlink":
            path.rmdir()
            path.symlink_to(root / mutation["target"], target_is_directory=True)
        elif mutation["operation"] == "copy-file":
            source = root / mutation["source"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source.read_bytes())
        else:
            raise AssertionError("unknown filesystem mutation")


def _case_cli_arguments(paths, root, case, *, include_command):
    arguments = [
        paths["contract"],
        paths["manifest"],
        paths["acceptance"],
        paths["envelope"],
        paths["runtime_acceptance"],
        str(root),
    ]
    variant = case.get("cli_variant")
    if variant == "missing-runtime-acceptance":
        del arguments[4]
    elif variant == "extra-argument":
        arguments.append("SYNTHETIC_EXTRA_CLI_ARGUMENT_MUST_NOT_ESCAPE")
    elif variant is not None:
        raise AssertionError("unknown CLI fixture variant")
    if include_command:
        arguments.insert(0, "verify")
    return arguments


def _write_relative(root, relative_path, data):
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _open_directory(path):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    return os.open(str(path), flags)


@contextmanager
def _root_descriptor(path):
    native_close = os.close
    descriptor = _open_directory(path)
    try:
        yield descriptor
    finally:
        native_close(descriptor)


@contextmanager
def _injected_close_failure(marker):
    """Leave injected descriptors recoverable by a saved native close."""

    native_open = os.open
    native_close = os.close
    opened = []

    def tracked_open(*args, **kwargs):
        descriptor = native_open(*args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def fail_close(_descriptor):
        raise OSError(marker)

    try:
        with mock.patch.object(
            tcb.os, "open", side_effect=tracked_open
        ) as injected_open, mock.patch.object(
            tcb.os, "close", side_effect=fail_close
        ) as injected_close:
            yield injected_open, injected_close, opened
    finally:
        for descriptor in dict.fromkeys(opened):
            try:
                native_close(descriptor)
            except OSError:
                pass


def _assert_controlled_error(testcase, context, expected):
    testcase.assertIsInstance(context.exception, tcb.TCBContractError)
    testcase.assertEqual(context.exception.code, expected)
    testcase.assertEqual(str(context.exception), expected)


class IndependentManifestIdentityTests(unittest.TestCase):
    def setUp(self):
        self.manifest = _manifest_for_payloads(ROLE_PAYLOADS)
        self.manifest_bytes = _independent_manifest_bytes(self.manifest)

    def test_independent_canonical_manifest_and_digest_match_production(self):
        self.assertEqual(
            tcb.canonical_manifest_bytes(self.manifest), self.manifest_bytes
        )
        self.assertEqual(
            tcb.manifest_digest(self.manifest_bytes),
            _independent_manifest_digest(self.manifest_bytes),
        )
        self.assertTrue(self.manifest_bytes.endswith(b"\n"))
        self.assertFalse(self.manifest_bytes.endswith(b"\n\n"))
        self.assertEqual(self.manifest_bytes, self.manifest_bytes.decode("ascii").encode("ascii"))

    def test_digest_binds_domain_nul_length_and_every_executable_byte(self):
        expected = _independent_manifest_digest(self.manifest_bytes)
        wrong_domain = hashlib.sha256(
            b"stellaris-m1b-executable-manifest-v0"
            + b"\x00"
            + len(self.manifest_bytes).to_bytes(8, "big")
            + self.manifest_bytes
        ).hexdigest()
        wrong_length = hashlib.sha256(
            MANIFEST_DOMAIN
            + b"\x00"
            + (len(self.manifest_bytes) + 1).to_bytes(8, "big")
            + self.manifest_bytes
        ).hexdigest()
        no_nul = hashlib.sha256(
            MANIFEST_DOMAIN
            + len(self.manifest_bytes).to_bytes(8, "big")
            + self.manifest_bytes
        ).hexdigest()

        changed_payloads = copy.deepcopy(ROLE_PAYLOADS)
        role, payload = changed_payloads["synthetic/analysis-engine.opaque"]
        changed_payloads["synthetic/analysis-engine.opaque"] = (
            role,
            payload[:-1] + bytes((payload[-1] ^ 1,)),
        )
        changed_manifest = _manifest_for_payloads(changed_payloads)
        changed_bytes = _independent_manifest_bytes(changed_manifest)

        self.assertEqual(len(changed_payloads), 4)
        self.assertNotEqual(expected, wrong_domain)
        self.assertNotEqual(expected, wrong_length)
        self.assertNotEqual(expected, no_nul)
        self.assertNotEqual(
            expected, _independent_manifest_digest(changed_bytes)
        )

    def test_manifest_has_four_unique_paths_and_roles_in_raw_ascii_order(self):
        rows = self.manifest["files"]
        paths = [row["path"] for row in rows]
        roles = [row["role"] for row in rows]
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(len(roles), len(set(roles)))
        self.assertEqual(
            set(roles),
            {
                "analysis_engine",
                "contract_validator",
                "provider_request_harness",
                "synthetic_fixture_materializer",
            },
        )
        self.assertEqual(paths, sorted(paths, key=lambda item: item.encode("ascii")))
        for path in paths:
            self.assertEqual(path, path.encode("ascii").decode("ascii"))

    def test_manifest_has_no_self_digest_or_self_entry(self):
        self.assertTrue(
            {"manifest_sha256", "sha256", "self_hash"}.isdisjoint(self.manifest)
        )
        self.assertNotIn(
            "registry/m1b/offline-executable-tcb-contract-v3.json",
            {row["path"] for row in self.manifest["files"]},
        )


class PhysicalIdentityAliasTests(unittest.TestCase):
    @staticmethod
    def _forced_identity_patch(*paths):
        native_identities = {
            (path.stat().st_dev, path.stat().st_ino) for path in paths
        }
        native_physical_identity = tcb._physical_identity

        def injected_identity(stat_result):
            native = (stat_result.st_dev, stat_result.st_ino)
            if native in native_identities:
                return (101, 201)
            return native_physical_identity(stat_result)

        return mock.patch.object(
            tcb, "_physical_identity", side_effect=injected_identity
        )

    @staticmethod
    def _admit_executable(index, path, payload, purpose):
        return index.admit_executable(
            path,
            hashlib.sha256(payload).hexdigest(),
            len(payload),
            purpose=purpose,
            size_code="EXECUTABLE_FILE_SIZE_LIMIT",
        )

    def test_exact_path_same_digest_reuses_bytes_and_mismatch_never_reopens(self):
        payload = b"synthetic-exact-cache-entry"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write_relative(root, "cache/value.opaque", payload)
            with _root_descriptor(root) as root_fd:
                index = tcb.AdmittedFileIndex(root_fd)
                first, added = self._admit_executable(
                    index, "cache/value.opaque", payload, "manifest_role"
                )
                self.assertTrue(added)
                with mock.patch.object(tcb.os, "open") as injected_open, mock.patch.object(
                    tcb.os, "read"
                ) as injected_read:
                    second, added = self._admit_executable(
                        index, "cache/value.opaque", payload, "source_import"
                    )
                    self.assertIs(second, first)
                    self.assertFalse(added)
                    with self.assertRaises(tcb.TCBContractError) as raised:
                        index.admit_executable(
                            "cache/value.opaque",
                            "f" * 64,
                            len(payload),
                            purpose="native_dependency",
                            size_code="EXECUTABLE_FILE_SIZE_LIMIT",
                        )
                _assert_controlled_error(
                    self, raised, "EXECUTION_FILE_HASH_MISMATCH"
                )
                injected_open.assert_not_called()
                injected_read.assert_not_called()
                self.assertEqual(len(index.by_path), 1)
                self.assertEqual(len(index.by_identity), 1)

    def test_case_alias_same_and_different_digest_fail_before_content_read(self):
        scenarios = (
            (b"same-bytes", b"same-bytes"),
            (b"first-bytes", b"different-second-bytes"),
        )
        for first_payload, second_payload in scenarios:
            with self.subTest(same=first_payload == second_payload), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root)
                first_path = _write_relative(
                    root, "left/CaseAlias", first_payload
                )
                second_path = _write_relative(
                    root, "right/casealias", second_payload
                )
                with self._forced_identity_patch(
                    first_path, second_path
                ), _root_descriptor(root) as root_fd:
                    index = tcb.AdmittedFileIndex(root_fd)
                    self._admit_executable(
                        index,
                        "left/CaseAlias",
                        first_payload,
                        "manifest_role:analysis_engine",
                    )
                    with mock.patch.object(tcb.os, "read") as injected_read:
                        with self.assertRaises(tcb.TCBContractError) as raised:
                            self._admit_executable(
                                index,
                                "right/casealias",
                                second_payload,
                                "source_import:synthetic_alias",
                            )
                    _assert_controlled_error(
                        self, raised, "PHYSICAL_IDENTITY_ALIAS"
                    )
                    injected_read.assert_not_called()
                    self.assertNotIn("right/casealias", index.by_path)

    def test_all_required_cross_surface_aliases_fail_before_second_read(self):
        native_path = "synthetic/native/libsynthetic.dylib"
        native_payload = b"SYNTHETIC-OPAQUE-NATIVE-DEPENDENCY\x00"
        pairs = (
            (
                "input-record-input-record",
                "contract",
                "manifest",
                "INPUT_RECORD_ALIAS_FORBIDDEN",
            ),
            (
                "input-record-runtime-acceptance",
                "envelope",
                "runtime_acceptance",
                "RUNTIME_ACCEPTANCE_ALIAS_FORBIDDEN",
            ),
            (
                "input-record-manifest-role",
                "contract",
                "analysis_engine",
                "PHYSICAL_IDENTITY_ALIAS",
            ),
            (
                "runtime-acceptance-manifest-role",
                "runtime_acceptance",
                "analysis_engine",
                "PHYSICAL_IDENTITY_ALIAS",
            ),
            (
                "two-manifest-roles",
                "analysis_engine",
                "contract_validator",
                "PHYSICAL_IDENTITY_ALIAS",
            ),
            (
                "role-interpreter",
                "analysis_engine",
                "interpreter",
                "PHYSICAL_IDENTITY_ALIAS",
            ),
            (
                "role-source-import",
                "analysis_engine",
                "source_import",
                "PHYSICAL_IDENTITY_ALIAS",
            ),
            (
                "role-extension-import",
                "analysis_engine",
                "extension_import",
                "PHYSICAL_IDENTITY_ALIAS",
            ),
            (
                "interpreter-import",
                "interpreter",
                "source_import",
                "PHYSICAL_IDENTITY_ALIAS",
            ),
            (
                "import-native-dependency",
                "source_import",
                "native_dependency",
                "PHYSICAL_IDENTITY_ALIAS",
            ),
        )
        for label, first_key, second_key, expected in pairs:
            with self.subTest(pair=label), tempfile.TemporaryDirectory() as raw_root:
                documents = _positive_documents()
                for state_name in ("admitted_state", "observed_state"):
                    documents["envelope"][state_name]["native_dependencies"] = {
                        "blocker": None,
                        "dependencies": [
                            {
                                "install_name": "libsynthetic.dylib",
                                "path": native_path,
                                "sha256": hashlib.sha256(
                                    native_payload
                                ).hexdigest(),
                            }
                        ],
                        "status": "bound",
                    }
                root = Path(raw_root).resolve()
                paths = _materialize_documents(
                    root,
                    documents,
                    payloads={
                        "auxiliary": {native_path: native_payload}
                    },
                )
                role_paths = {
                    row["role"]: row["path"]
                    for row in documents["manifest"]["files"]
                }
                surfaces = {
                    "contract": paths["contract"],
                    "manifest": paths["manifest"],
                    "envelope": paths["envelope"],
                    "runtime_acceptance": paths["runtime_acceptance"],
                    "analysis_engine": role_paths["analysis_engine"],
                    "contract_validator": role_paths["contract_validator"],
                    "interpreter": INTERPRETER_PATH,
                    "source_import": SOURCE_IMPORT_PATH,
                    "extension_import": EXTENSION_IMPORT_PATH,
                    "native_dependency": native_path,
                }
                first_path = root / surfaces[first_key]
                second_path = root / surfaces[second_key]
                second_native = (
                    second_path.stat().st_dev,
                    second_path.stat().st_ino,
                )
                native_read = os.read
                second_reads = []

                def tracked_read(descriptor, count):
                    observed = os.fstat(descriptor)
                    if (observed.st_dev, observed.st_ino) == second_native:
                        second_reads.append(count)
                    return native_read(descriptor, count)

                with self._forced_identity_patch(
                    first_path, second_path
                ), mock.patch.object(
                    tcb.os, "read", side_effect=tracked_read
                ):
                    result = tcb.verify_paths(
                        paths["contract"],
                        paths["manifest"],
                        paths["acceptance"],
                        paths["envelope"],
                        paths["runtime_acceptance"],
                        str(root),
                    )
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["codes"], [expected])
                self.assertEqual(second_reads, [])

    def test_changed_inode_bytes_are_not_read_and_alias_cannot_succeed(self):
        first_payload = b"synthetic-admitted-before-mutation"
        second_payload = b"synthetic-alias-never-read"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            first_path = _write_relative(
                root, "left/CaseAlias", first_payload
            )
            second_path = _write_relative(
                root, "right/casealias", second_payload
            )
            with self._forced_identity_patch(
                first_path, second_path
            ), _root_descriptor(root) as root_fd:
                index = tcb.AdmittedFileIndex(root_fd)
                first, _ = self._admit_executable(
                    index, "left/CaseAlias", first_payload, "interpreter"
                )
                first_path.write_bytes(b"changed-after-admission-same-inode")
                with mock.patch.object(tcb.os, "read") as injected_read:
                    with self.assertRaises(tcb.TCBContractError) as raised:
                        self._admit_executable(
                            index,
                            "right/casealias",
                            second_payload,
                            "source_import",
                        )
                _assert_controlled_error(
                    self, raised, "PHYSICAL_IDENTITY_ALIAS"
                )
                injected_read.assert_not_called()
                self.assertEqual(first.data, first_payload)
                self.assertNotIn("right/casealias", index.by_path)

    def test_alias_primary_survives_close_failure_and_each_fd_is_attempted_once(self):
        first_payload = b"synthetic-first-close-precedence"
        second_payload = b"synthetic-alias-close-precedence"
        marker = "SYNTHETIC_ALIAS_CLOSE_FAILURE_MUST_NOT_ESCAPE"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            first_path = _write_relative(
                root, "left/CaseAlias", first_payload
            )
            second_path = _write_relative(
                root, "right/casealias", second_payload
            )
            with self._forced_identity_patch(
                first_path, second_path
            ), _root_descriptor(root) as root_fd:
                index = tcb.AdmittedFileIndex(root_fd)
                self._admit_executable(
                    index, "left/CaseAlias", first_payload, "manifest_role"
                )
                with _injected_close_failure(marker) as (
                    _injected_open,
                    injected_close,
                    opened,
                ), mock.patch.object(tcb.os, "read") as injected_read:
                    with self.assertRaises(tcb.TCBContractError) as raised:
                        self._admit_executable(
                            index,
                            "right/casealias",
                            second_payload,
                            "extension_import",
                        )
                _assert_controlled_error(
                    self, raised, "PHYSICAL_IDENTITY_ALIAS"
                )
                injected_read.assert_not_called()
                self.assertEqual(injected_close.call_count, len(opened))
                self.assertEqual(
                    Counter(
                        call.args[0]
                        for call in injected_close.call_args_list
                    ),
                    Counter(opened),
                )
                self.assertNotIn(marker, str(raised.exception))
                self.assertNotIn("right/casealias", index.by_path)

    def test_reader_publishes_identity_only_after_successful_close(self):
        payload = b"synthetic-identity-after-close"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            path = _write_relative(root, "records/value.bin", payload)
            expected_identity = (path.stat().st_dev, path.stat().st_ino)
            identities = []
            with _root_descriptor(root) as root_fd:
                self.assertEqual(
                    tcb._read_rooted_regular_file(
                        root_fd,
                        "records/value.bin",
                        len(payload),
                        identity_out=identities,
                    ),
                    payload,
                )
            self.assertEqual(identities, [expected_identity])

            identities = []
            with _root_descriptor(root) as root_fd, _injected_close_failure(
                "SYNTHETIC_IDENTITY_CLOSE_FAILURE_MUST_NOT_ESCAPE"
            ):
                with self.assertRaises(tcb.TCBContractError) as raised:
                    tcb._read_rooted_regular_file(
                        root_fd,
                        "records/value.bin",
                        len(payload),
                        identity_out=identities,
                    )
            _assert_controlled_error(self, raised, "INPUT_READ_FAILED")
            self.assertEqual(identities, [])


class IndependentContractIdentityTests(unittest.TestCase):
    def test_contract_exact_bytes_and_external_digest_are_independently_recomputed(self):
        contract_bytes = CONTRACT.read_bytes()
        contract = json.loads(contract_bytes.decode("ascii"))
        self.assertEqual(len(contract_bytes), EXPECTED_CONTRACT_BYTES)
        self.assertEqual(
            hashlib.sha256(contract_bytes).hexdigest(),
            EXPECTED_CONTRACT_FILE_SHA256,
        )
        self.assertEqual(
            _independent_contract_digest(contract_bytes),
            EXPECTED_CONTRACT_DIGEST,
        )
        self.assertEqual(contract_bytes, _encode(contract))
        self.assertEqual(contract["contract_schema"], CONTRACT_SCHEMA)
        self.assertEqual(contract["contract_version"], CONTRACT_VERSION)
        self.assertEqual(contract["contract_generation"], CONTRACT_GENERATION)
        self.assertEqual(contract["protocol_generation"], PROTOCOL_GENERATION)
        self.assertTrue(
            {"contract_sha256", "sha256", "self_hash"}.isdisjoint(contract)
        )

    def test_contract_digest_rejects_wrong_domain_length_and_semantic_byte(self):
        contract_bytes = CONTRACT.read_bytes()
        expected = _independent_contract_digest(contract_bytes)
        wrong_domain = hashlib.sha256(
            b"stellaris-m1b-offline-executable-tcb-contract-v0"
            + b"\x00"
            + len(contract_bytes).to_bytes(8, "big")
            + contract_bytes
        ).hexdigest()
        wrong_length = hashlib.sha256(
            CONTRACT_DOMAIN
            + b"\x00"
            + (len(contract_bytes) - 1).to_bytes(8, "big")
            + contract_bytes
        ).hexdigest()
        changed = bytearray(contract_bytes)
        changed[-2] ^= 1
        self.assertNotEqual(expected, wrong_domain)
        self.assertNotEqual(expected, wrong_length)
        self.assertNotEqual(expected, _independent_contract_digest(bytes(changed)))


class IndependentEnvelopeAndRuntimeAcceptanceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.documents = _positive_documents()
        self.envelope_bytes = _encode(self.documents["envelope"])
        self.runtime_bytes = _encode(self.documents["runtime_acceptance"])

    def test_envelope_digest_binds_domain_nul_length_and_canonical_lf(self):
        expected = _independent_execution_envelope_digest(
            self.envelope_bytes
        )
        self.assertEqual(
            self.documents["runtime_acceptance"]["envelope_sha256"],
            expected,
        )
        if hasattr(tcb, "execution_envelope_digest"):
            self.assertEqual(
                tcb.execution_envelope_digest(self.envelope_bytes), expected
            )
        raw = hashlib.sha256(self.envelope_bytes).hexdigest()
        wrong_domain = hashlib.sha256(
            b"stellaris-m1b-execution-envelope-v1"
            + b"\x00"
            + len(self.envelope_bytes).to_bytes(8, "big")
            + self.envelope_bytes
        ).hexdigest()
        wrong_length = hashlib.sha256(
            EXECUTION_ENVELOPE_DOMAIN
            + b"\x00"
            + (len(self.envelope_bytes) + 1).to_bytes(8, "big")
            + self.envelope_bytes
        ).hexdigest()
        self.assertNotEqual(expected, raw)
        self.assertNotEqual(expected, wrong_domain)
        self.assertNotEqual(expected, wrong_length)
        self.assertEqual(self.envelope_bytes, _encode(self.documents["envelope"]))

    def test_runtime_acceptance_has_exact_sixteen_fields_and_external_identity(self):
        record = self.documents["runtime_acceptance"]
        self.assertEqual(
            tuple(sorted(record)),
            (
                "contract_generation",
                "contract_schema",
                "contract_sha256",
                "contract_version",
                "envelope_digest_domain",
                "envelope_digest_framing",
                "envelope_generation",
                "envelope_schema",
                "envelope_sha256",
                "implementation_generation",
                "manifest_schema",
                "manifest_sha256",
                "protocol_generation",
                "runtime_acceptance_generation",
                "runtime_acceptance_schema",
                "runtime_acceptance_state",
            ),
        )
        self.assertEqual(record["runtime_acceptance_schema"], RUNTIME_ACCEPTANCE_SCHEMA)
        self.assertEqual(record["runtime_acceptance_generation"], 1)
        self.assertEqual(record["runtime_acceptance_state"], "owner_accepted")
        expected = _independent_runtime_acceptance_digest(self.runtime_bytes)
        if hasattr(tcb, "runtime_acceptance_digest"):
            self.assertEqual(tcb.runtime_acceptance_digest(self.runtime_bytes), expected)
        self.assertNotEqual(
            expected, hashlib.sha256(self.runtime_bytes).hexdigest()
        )


class TCBAdmissionFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases_bytes = CASES.read_bytes()
        cls.fixture = json.loads(cls.cases_bytes.decode("utf-8"))
        cls.base_documents = _positive_documents()

    def test_fixture_identity_count_and_required_adversarial_matrix(self):
        self.assertEqual(len(self.cases_bytes), EXPECTED_CASE_BYTES)
        self.assertEqual(
            hashlib.sha256(self.cases_bytes).hexdigest(),
            EXPECTED_CASES_SHA256,
        )
        self.assertEqual(
            self.fixture["fixture_schema"], "m1b-tcb-admission-cases-v4"
        )
        self.assertEqual(len(self.fixture["cases"]), EXPECTED_CASE_COUNT)
        ids = [case["id"] for case in self.fixture["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(REQUIRED_MATRIX_IDS.issubset(ids))
        self.assertEqual(
            {case["expected"]["status"] for case in self.fixture["cases"]},
            {"error", "ok"},
        )
        self.assertEqual(
            sum(case["expected"]["status"] == "ok" for case in self.fixture["cases"]),
            1,
        )
        self.assertEqual(
            hashlib.sha256(VERIFIER.read_bytes()).hexdigest(),
            EXPECTED_VERIFIER_SHA256,
        )

    def test_coherent_harness_cases_rebind_every_authority_surface_and_payload(self):
        coherent_cases = [
            case
            for case in self.fixture["cases"]
            if "coherent_harness_path" in case
        ]
        self.assertEqual(len(coherent_cases), 5)
        old_harness_path, (_role, harness_payload) = next(
            (path, row)
            for path, row in ROLE_PAYLOADS.items()
            if row[0] == "provider_request_harness"
        )
        for case in coherent_cases:
            with self.subTest(case=case["id"]), tempfile.TemporaryDirectory() as raw_root:
                harness_path = case["coherent_harness_path"]
                documents = _apply_case(self.base_documents, case)
                provider = next(
                    row
                    for row in documents["manifest"]["files"]
                    if row["role"] == "provider_request_harness"
                )
                manifest_sha256 = _independent_manifest_digest(
                    _independent_manifest_bytes(documents["manifest"])
                )
                self.assertEqual(provider["path"], harness_path)
                self.assertEqual(
                    provider["sha256"],
                    hashlib.sha256(harness_payload).hexdigest(),
                )
                self.assertEqual(
                    [row["path"] for row in documents["manifest"]["files"]],
                    sorted(
                        (row["path"] for row in documents["manifest"]["files"]),
                        key=lambda value: value.encode("ascii"),
                    ),
                )
                self.assertEqual(
                    set(documents["acceptance"]),
                    {
                        "acceptance_state",
                        "implementation_generation",
                        "manifest_schema",
                        "manifest_sha256",
                        "protocol_generation",
                    },
                )
                self.assertEqual(
                    documents["acceptance"]["manifest_sha256"],
                    manifest_sha256,
                )
                self.assertEqual(
                    documents["envelope"]["manifest_sha256"],
                    manifest_sha256,
                )
                self.assertEqual(
                    documents["runtime_acceptance"]["manifest_sha256"],
                    manifest_sha256,
                )
                self.assertEqual(
                    documents["runtime_acceptance"]["envelope_sha256"],
                    _independent_execution_envelope_digest(
                        _encode(documents["envelope"])
                    ),
                )
                self.assertEqual(
                    documents["envelope"]["admitted_state"],
                    documents["envelope"]["observed_state"],
                )
                for state_name in ("admitted_state", "observed_state"):
                    state = documents["envelope"][state_name]
                    self.assertEqual(
                        state["execution_plan"]["entrypoint"],
                        {
                            "mode": "descriptor_script_file",
                            "repository_locator": harness_path,
                            "role": "provider_request_harness",
                            "sha256": provider["sha256"],
                        },
                    )
                    self.assertEqual(
                        state["invocation"]["argv_tail"][-1], "/dev/fd/3"
                    )
                    self.assertEqual(
                        state["invocation"]["inherited_fds"][0][
                            "repository_locator"
                        ],
                        harness_path,
                    )
                root = Path(raw_root).resolve()
                _materialize_documents(
                    root,
                    documents,
                    refresh_runtime_acceptance=False,
                    coherent_harness_path=harness_path,
                )
                self.assertEqual((root / harness_path).read_bytes(), harness_payload)
                self.assertFalse((root / old_harness_path).exists())

    def test_all_table_cases_return_exact_controlled_result(self):
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root).resolve()
                documents = _apply_case(self.base_documents, case)
                paths = _materialize_documents(
                    root,
                    documents,
                    encodings=case.get("encoding"),
                    path_overrides=case.get("paths"),
                    refresh_runtime_acceptance=False,
                    coherent_harness_path=case.get(
                        "coherent_harness_path"
                    ),
                )
                _apply_filesystem_mutations(root, case)
                result = tcb._execute(
                    tuple(
                        _case_cli_arguments(
                            paths, root, case, include_command=True
                        )
                    )
                )

                self.assertEqual(result["status"], case["expected"]["status"])
                self.assertEqual(result["codes"], case["expected"]["codes"])
                self.assertEqual(set(result), {"codes", "counts", "status"})
                self.assertEqual(
                    set(result["counts"]),
                    {
                        "contract_records",
                        "executable_files",
                        "import_entries",
                        "linkage_records",
                    },
                )
                if result["status"] == "ok":
                    self.assertEqual(
                        result["counts"],
                        {
                            "contract_records": 1,
                            "executable_files": 7,
                            "import_entries": 7,
                            "linkage_records": 3,
                        },
                    )
                else:
                    self.assertEqual(set(result["counts"].values()), {0})

    def test_every_table_case_has_real_cli_exit_stderr_and_leakage_evidence(self):
        base_manifest_bytes = _independent_manifest_bytes(
            self.base_documents["manifest"]
        )
        base_manifest_sha256 = _independent_manifest_digest(base_manifest_bytes)
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root).resolve()
                documents = _apply_case(self.base_documents, case)
                paths = _materialize_documents(
                    root,
                    documents,
                    encodings=case.get("encoding"),
                    path_overrides=case.get("paths"),
                    refresh_runtime_acceptance=False,
                    coherent_harness_path=case.get(
                        "coherent_harness_path"
                    ),
                )
                _apply_filesystem_mutations(root, case)
                completed = subprocess.run(
                    [sys.executable, str(VERIFIER)]
                    + _case_cli_arguments(
                        paths, root, case, include_command=True
                    ),
                    cwd=REPOSITORY_ROOT,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5,
                )

                expected_ok = case["expected"]["status"] == "ok"
                self.assertEqual(completed.returncode, 0 if expected_ok else 2)
                self.assertEqual(completed.stderr, b"")
                result = json.loads(completed.stdout)
                self.assertEqual(result["status"], case["expected"]["status"])
                self.assertEqual(result["codes"], case["expected"]["codes"])
                self.assertEqual(
                    completed.stdout,
                    tcb._encode_result(result),
                )
                combined = completed.stdout + completed.stderr
                for forbidden in (
                    case["id"].encode("ascii"),
                    str(root).encode("utf-8"),
                    EXPECTED_CONTRACT_DIGEST.encode("ascii"),
                    base_manifest_sha256.encode("ascii"),
                    b"Traceback",
                    b"Exception",
                    b"owner_accepted",
                ) + tuple(
                    payload for _role, payload in ROLE_PAYLOADS.values()
                ) + tuple(AUXILIARY_PAYLOADS.values()) + tuple(
                    mutation["marker"].encode("ascii")
                    for mutation in case.get("filesystem", ())
                    if "marker" in mutation
                ) + tuple(
                    [case["coherent_harness_path"].encode("ascii")]
                    if "coherent_harness_path" in case
                    else []
                ):
                    self.assertNotIn(forbidden, combined)

    def test_positive_role_and_import_payloads_are_never_imported_or_executed(self):
        documents = copy.deepcopy(self.base_documents)
        marker = "SYNTHETIC_ROLE_IMPORT_OR_EXECUTION_MUST_NOT_HAPPEN"
        original_import = builtins.__import__
        imported_names = []

        def guarded_import(name, *args, **kwargs):
            imported_names.append(name)
            if name.startswith("synthetic") or name in {
                "importlib._bootstrap",
                "sys",
            }:
                raise AssertionError(marker)
            return original_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root).resolve()
            paths = _materialize_documents(root, documents)
            before_modules = set(sys.modules)
            with mock.patch.object(
                builtins, "__import__", side_effect=guarded_import
            ), mock.patch.object(
                builtins, "exec", side_effect=AssertionError(marker)
            ) as injected_exec:
                result = tcb.verify_paths(
                    paths["contract"],
                    paths["manifest"],
                    paths["acceptance"],
                    paths["envelope"],
                    paths["runtime_acceptance"],
                    str(root),
                )
            after_modules = set(sys.modules)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["codes"], ["SYNTHETIC_CONFORMANCE_ONLY"])
        injected_exec.assert_not_called()
        self.assertTrue(
            set(imported_names).isdisjoint(
                {"synthetic_extension", "synthetic_source"}
            )
        )
        self.assertTrue(
            {"synthetic_extension", "synthetic_source"}.isdisjoint(
                after_modules - before_modules
            )
        )

    def test_fixture_and_success_result_cannot_create_authority(self):
        forbidden_attributes = {
            "FullDecisionAdmission",
            "_FullDecisionAdmission",
            "admit_provider_execution",
            "create_live_capability",
            "proven_implementation_identity",
        }
        self.assertTrue(
            all(not hasattr(tcb, name) for name in forbidden_attributes)
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root).resolve()
            paths = _materialize_documents(root, self.base_documents)
            result = tcb.verify_paths(
                paths["contract"],
                paths["manifest"],
                paths["acceptance"],
                paths["envelope"],
                paths["runtime_acceptance"],
                str(root),
            )
        serialized = json.dumps(result, sort_keys=True)
        self.assertEqual(result["codes"], ["SYNTHETIC_CONFORMANCE_ONLY"])
        for forbidden in (
            "owner_accepted",
            "admission",
            "provider",
            "proven",
            "capability",
            EXPECTED_CONTRACT_DIGEST,
        ):
            self.assertNotIn(forbidden, serialized.lower())

    def test_fixture_contains_no_raw_private_or_executable_payload_fields(self):
        forbidden_fields = {
            "content",
            "corpus",
            "executable_bytes",
            "model_output",
            "prompt",
            "raw_text",
            "translation",
        }

        def visit(value):
            if type(value) is dict:
                self.assertTrue(forbidden_fields.isdisjoint(value))
                for item in value.values():
                    visit(item)
            elif type(value) is list:
                for item in value:
                    visit(item)

        visit(self.fixture)
        for marker in (
            b"/Users/",
            b"l_russian:",
            b"localisation/",
            b"file://",
            b"Ollama",
        ):
            self.assertNotIn(marker, self.cases_bytes)


class StrictJsonBoundaryTests(unittest.TestCase):
    def test_malformed_trailing_duplicate_utf8_bom_and_surrogate_are_controlled(self):
        cases = (
            (b"{", "JSON_MALFORMED"),
            (b"{} trailing", "JSON_MALFORMED"),
            (b'{"x":1,"x":2}', "JSON_DUPLICATE_KEY"),
            (b"\xffSYNTHETIC_INVALID_UTF8", "UTF8_INVALID"),
            (b"\xef\xbb\xbf{}", "JSON_MALFORMED"),
            (b'{"x":"\\ud800"}', "JSON_UNICODE_INVALID"),
        )
        for payload, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaises(tcb.TCBContractError) as raised:
                    tcb.parse_json_bytes(payload)
                _assert_controlled_error(self, raised, expected)

    def test_float_nonfinite_and_oversized_integer_are_controlled(self):
        cases = (
            (b'{"x":1.0}', "JSON_FLOAT_FORBIDDEN"),
            (b'{"x":NaN}', "JSON_MALFORMED"),
            (b'{"x":Infinity}', "JSON_MALFORMED"),
            (b'{"x":-Infinity}', "JSON_MALFORMED"),
            (b'{"x":9223372036854775808}', "JSON_INTEGER_OUT_OF_RANGE"),
            (b'{"x":-9223372036854775809}', "JSON_INTEGER_OUT_OF_RANGE"),
            (b'{"x":999999999999999999999999999999999999999999}', "JSON_INTEGER_OUT_OF_RANGE"),
        )
        for payload, expected in cases:
            with self.subTest(payload=payload[:24], expected=expected):
                with self.assertRaises(tcb.TCBContractError) as raised:
                    tcb.parse_json_bytes(payload)
                _assert_controlled_error(self, raised, expected)

    def test_signed_64_bit_boundaries_are_accepted_before_schema_validation(self):
        parsed = tcb.parse_json_bytes(
            b'{"max":9223372036854775807,"min":-9223372036854775808}'
        )
        self.assertEqual(parsed["max"], (1 << 63) - 1)
        self.assertEqual(parsed["min"], -(1 << 63))
        self.assertIs(type(parsed["max"]), int)
        self.assertIs(type(parsed["min"]), int)

    def test_json_size_exact_boundary_and_oversize_before_parsing(self):
        exact = b" " * (tcb.MAX_JSON_INPUT_BYTES - 1) + b"0"
        self.assertEqual(len(exact), tcb.MAX_JSON_INPUT_BYTES)
        self.assertEqual(tcb.parse_json_bytes(exact), 0)
        with mock.patch.object(tcb.json, "loads", wraps=tcb.json.loads) as loads:
            with self.assertRaises(tcb.TCBContractError) as raised:
                tcb.parse_json_bytes(exact + b" ")
        _assert_controlled_error(self, raised, "INPUT_SIZE_LIMIT")
        loads.assert_not_called()

    def test_bool_remains_bool_for_closed_typed_schema_checks(self):
        parsed = tcb.parse_json_bytes(b'{"generation":true}')
        self.assertIs(parsed["generation"], True)
        self.assertIsNot(type(parsed["generation"]), int)

    def test_string_and_sequence_exact_boundaries_are_finite(self):
        exact_string = (b'"' + b"x" * tcb.MAX_STRING_BYTES + b'"')
        self.assertEqual(
            len(tcb.parse_json_bytes(exact_string)), tcb.MAX_STRING_BYTES
        )
        with self.assertRaises(tcb.TCBContractError) as raised:
            tcb.parse_json_bytes(exact_string[:-1] + b'x"')
        _assert_controlled_error(self, raised, "JSON_STRING_SIZE_LIMIT")

        exact_sequence = b"[" + b",".join(
            b"0" for _ in range(tcb.MAX_SEQUENCE_ENTRIES)
        ) + b"]"
        self.assertEqual(
            len(tcb.parse_json_bytes(exact_sequence)),
            tcb.MAX_SEQUENCE_ENTRIES,
        )
        oversized_sequence = exact_sequence[:-1] + b",0]"
        with self.assertRaises(tcb.TCBContractError) as raised:
            tcb.parse_json_bytes(oversized_sequence)
        _assert_controlled_error(self, raised, "JSON_SEQUENCE_SIZE_LIMIT")

    def test_non_bytes_input_is_controlled(self):
        for value in ("{}", bytearray(b"{}"), memoryview(b"{}"), None):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(tcb.TCBContractError) as raised:
                    tcb.parse_json_bytes(value)
                _assert_controlled_error(self, raised, "INVALID_TYPE")


class ExecutionPolicyBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.base_documents = _positive_documents()

    def _verify(self, documents, *, payloads=None):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root).resolve()
            paths = _materialize_documents(
                root, documents, payloads=payloads
            )
            return tcb.verify_paths(
                paths["contract"],
                paths["manifest"],
                paths["acceptance"],
                paths["envelope"],
                paths["runtime_acceptance"],
                str(root),
            )

    def test_declared_import_order_is_exact_not_silently_alphabetized(self):
        documents = copy.deepcopy(self.base_documents)
        imports = documents["envelope"]["admitted_state"]["imports"]
        reordered = [imports[index] for index in (2, 0, 1, 3, 4, 5, 6)]
        modules = [row["module"] for row in reordered]
        self.assertNotEqual(modules, sorted(modules, key=lambda value: value.encode("ascii")))
        documents["envelope"]["admitted_state"]["imports"] = copy.deepcopy(
            reordered
        )
        documents["envelope"]["observed_state"]["imports"] = copy.deepcopy(
            reordered
        )
        result = self._verify(documents)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["import_entries"], 7)

    def test_sys_path_declared_order_is_not_silently_alphabetized(self):
        invocation = copy.deepcopy(
            self.base_documents["envelope"]["admitted_state"]["invocation"]
        )
        invocation["sys_path"] = [
            {"base": "repository_root", "path": "synthetic/a"},
            {"base": "repository_root", "path": "synthetic/A"},
        ]
        state = self.base_documents["envelope"]["admitted_state"]
        harness_path, (_role, harness_bytes) = next(
            (path, row)
            for path, row in ROLE_PAYLOADS.items()
            if row[0] == "provider_request_harness"
        )
        provider_entry = tcb.AdmittedFile(
            harness_path,
            harness_bytes,
            hashlib.sha256(harness_bytes).hexdigest(),
            (1, 1),
            is_record=False,
            purpose="test_provider_harness",
        )
        manifest_bindings = {
            "provider_request_harness": provider_entry
        }
        validated, paths = tcb._validate_invocation(
            invocation,
            state["interpreter"],
            state["execution_plan"],
            manifest_bindings,
            state["bytecode"],
            state["environment"],
        )
        self.assertEqual(paths, ("synthetic/a", "synthetic/A"))
        self.assertEqual(validated["sys_path"], invocation["sys_path"])
        self.assertNotEqual(
            list(paths), sorted(paths, key=lambda value: value.encode("ascii"))
        )
        invocation["sys_path"] = [
            {"base": "repository_root", "path": "synthetic/a"},
            {"base": "repository_root", "path": "synthetic/a"},
        ]
        with self.assertRaises(tcb.TCBContractError) as raised:
            tcb._validate_invocation(
                invocation,
                state["interpreter"],
                state["execution_plan"],
                manifest_bindings,
                state["bytecode"],
                state["environment"],
            )
        _assert_controlled_error(self, raised, "INVOCATION_POLICY_INVALID")

    def test_manifest_roles_interpreter_and_imports_reuse_admitted_bytes_without_reopen(self):
        documents = copy.deepcopy(self.base_documents)
        native_open = os.open
        opened_leaf_names = []

        def tracked_open(*args, **kwargs):
            opened_leaf_names.append(args[0])
            return native_open(*args, **kwargs)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root).resolve()
            paths = _materialize_documents(root, documents)
            with mock.patch.object(tcb.os, "open", side_effect=tracked_open):
                result = tcb.verify_paths(
                    paths["contract"],
                    paths["manifest"],
                    paths["acceptance"],
                    paths["envelope"],
                    paths["runtime_acceptance"],
                    str(root),
                )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["executable_files"], 7)
        for relative_path in tuple(ROLE_PAYLOADS) + tuple(AUXILIARY_PAYLOADS):
            self.assertEqual(
                opened_leaf_names.count(relative_path.rsplit("/", 1)[-1]),
                1,
                relative_path,
            )

    def test_executable_total_exact_boundary_and_one_unique_byte_over_fail_closed(self):
        role_payloads = {}
        for index, (path, (role, _payload)) in enumerate(ROLE_PAYLOADS.items()):
            role_payloads[path] = (role, bytes((65 + index,)) * 16)
        auxiliary_payloads = {
            path: bytes((75 + index,)) * 16
            for index, path in enumerate(AUXILIARY_PAYLOADS)
        }
        manifest = _manifest_for_payloads(role_payloads)
        manifest_bytes = _independent_manifest_bytes(manifest)
        manifest_sha256 = _independent_manifest_digest(manifest_bytes)
        documents = {
            "contract": json.loads(CONTRACT.read_text("ascii")),
            "manifest": manifest,
            "acceptance": _acceptance_for_manifest(manifest_sha256),
            "envelope": _envelope_for_manifest(
                manifest,
                manifest_sha256,
                auxiliary_payloads,
                role_payloads,
            ),
        }
        documents["runtime_acceptance"] = _runtime_acceptance_for_envelope(
            documents["envelope"], manifest_sha256
        )
        with mock.patch.object(
            tcb, "MAX_EXECUTABLE_FILE_BYTES", 17
        ), mock.patch.object(tcb, "MAX_EXECUTABLE_TOTAL_BYTES", 112):
            result = self._verify(
                documents,
                payloads={
                    "roles": role_payloads,
                    "auxiliary": auxiliary_payloads,
                },
            )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["executable_files"], 7)

        over_documents = copy.deepcopy(documents)
        over_auxiliary_payloads = dict(auxiliary_payloads)
        over_auxiliary_payloads[EXTENSION_IMPORT_PATH] = b"Z" * 17
        extension_sha256 = hashlib.sha256(
            over_auxiliary_payloads[EXTENSION_IMPORT_PATH]
        ).hexdigest()
        for state_name in ("admitted_state", "observed_state"):
            over_documents["envelope"][state_name]["imports"][1][
                "sha256"
            ] = extension_sha256
        with mock.patch.object(
            tcb, "MAX_EXECUTABLE_FILE_BYTES", 17
        ), mock.patch.object(tcb, "MAX_EXECUTABLE_TOTAL_BYTES", 112):
            result = self._verify(
                over_documents,
                payloads={
                    "roles": role_payloads,
                    "auxiliary": over_auxiliary_payloads,
                },
            )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["codes"], ["EXECUTABLE_TOTAL_SIZE_LIMIT"])

    def test_import_count_exact_boundary_and_oversize_are_closed(self):
        documents = copy.deepcopy(self.base_documents)
        interpreter_sha256 = documents["envelope"]["admitted_state"][
            "interpreter"
        ]["executable_sha256"]
        additions = [
            {
                "kind": "builtin",
                "module": "synthetic_builtin_{:03d}".format(index),
                "path": None,
                "sha256": interpreter_sha256,
            }
            for index in range(tcb.MAX_IMPORT_ENTRIES - 7)
        ]
        for state_name in ("admitted_state", "observed_state"):
            documents["envelope"][state_name]["imports"].extend(
                copy.deepcopy(additions)
            )
        result = self._verify(documents)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["import_entries"], tcb.MAX_IMPORT_ENTRIES)

        oversized = copy.deepcopy(documents)
        extra = {
            "kind": "builtin",
            "module": "synthetic_builtin_oversize",
            "path": None,
            "sha256": interpreter_sha256,
        }
        for state_name in ("admitted_state", "observed_state"):
            oversized["envelope"][state_name]["imports"].append(
                copy.deepcopy(extra)
            )
        result = self._verify(oversized)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["codes"], ["IMPORT_CLOSURE_INVALID"])

    def test_native_dependency_entry_limit_is_finite_before_file_reads(self):
        rows = [
            {
                "install_name": "libsynthetic{:03d}.dylib".format(index),
                "path": "synthetic/native/lib{:03d}.dylib".format(index),
                "sha256": "e" * 64,
            }
            for index in range(tcb.MAX_NATIVE_DEPENDENCY_ENTRIES + 1)
        ]
        value = {"blocker": None, "dependencies": rows, "status": "bound"}
        with mock.patch.object(
            tcb, "_verify_executable_identity"
        ) as verify_identity:
            with self.assertRaises(tcb.TCBContractError) as raised:
                tcb._validate_native_dependencies(value, None, 0)
        _assert_controlled_error(
            self, raised, "NATIVE_DEPENDENCY_POLICY_INVALID"
        )
        verify_identity.assert_not_called()


class AtomicEntrypointTransportBoundaryTests(unittest.TestCase):
    def test_snapshot_is_one_atomic_write_and_writer_closes_before_read(self):
        payload = b'SYNTHETIC_ROLE = "provider_request_harness"\n'
        native_pipe = os.pipe
        native_write = os.write
        native_read = os.read
        native_close = os.close
        pair = []
        events = []

        def tracked_pipe():
            descriptors = native_pipe()
            pair.extend(descriptors)
            events.append(("pipe", descriptors))
            return descriptors

        def tracked_write(descriptor, data):
            events.append(("write", descriptor, bytes(data)))
            return native_write(descriptor, data)

        def tracked_read(descriptor, size):
            events.append(("read", descriptor, size))
            return native_read(descriptor, size)

        def tracked_close(descriptor):
            events.append(("close", descriptor))
            native_close(descriptor)

        with mock.patch.object(
            tcb.os, "pipe", side_effect=tracked_pipe
        ), mock.patch.object(
            tcb.os, "write", side_effect=tracked_write
        ), mock.patch.object(
            tcb.os, "read", side_effect=tracked_read
        ), mock.patch.object(
            tcb.os, "close", side_effect=tracked_close
        ):
            tcb._verify_atomic_entrypoint_snapshot(payload)

        self.assertEqual(len(pair), 2)
        read_descriptor, write_descriptor = pair
        writes = [event for event in events if event[0] == "write"]
        self.assertEqual(writes, [("write", write_descriptor, payload)])
        writer_close = events.index(("close", write_descriptor))
        first_read = next(
            index for index, event in enumerate(events) if event[0] == "read"
        )
        self.assertLess(writer_close, first_read)
        self.assertEqual(
            Counter(
                event[1] for event in events if event[0] == "close"
            ),
            Counter((read_descriptor, write_descriptor)),
        )

    def test_empty_and_over_atomic_bound_fail_before_pipe_creation(self):
        for payload in (b"", b"x" * (tcb.MAX_ATOMIC_ENTRYPOINT_BYTES + 1)):
            with self.subTest(size=len(payload)), mock.patch.object(
                tcb.os, "pipe"
            ) as injected_pipe:
                with self.assertRaises(tcb.TCBContractError) as raised:
                    tcb._verify_atomic_entrypoint_snapshot(payload)
                _assert_controlled_error(
                    self, raised, "ENTRYPOINT_TRANSPORT_SIZE_LIMIT"
                )
                injected_pipe.assert_not_called()

    def test_short_and_zero_atomic_write_fail_and_close_each_end_once(self):
        for returned in (0, 1):
            native_pipe = os.pipe
            native_close = os.close
            pair = []
            close_attempts = []

            def tracked_pipe():
                descriptors = native_pipe()
                pair.extend(descriptors)
                return descriptors

            def tracked_close(descriptor):
                close_attempts.append(descriptor)
                native_close(descriptor)

            with self.subTest(returned=returned), mock.patch.object(
                tcb.os, "pipe", side_effect=tracked_pipe
            ), mock.patch.object(
                tcb.os, "write", return_value=returned
            ), mock.patch.object(
                tcb.os, "close", side_effect=tracked_close
            ):
                with self.assertRaises(tcb.TCBContractError) as raised:
                    tcb._verify_atomic_entrypoint_snapshot(b"synthetic")
            _assert_controlled_error(
                self, raised, "ENTRYPOINT_TRANSPORT_IO_FAILED"
            )
            self.assertEqual(Counter(close_attempts), Counter(pair))

    def test_early_eof_extra_and_wrong_transport_bytes_fail_closed(self):
        payload = b"synthetic"
        scenarios = (
            ("early_eof", [b""], "ENTRYPOINT_TRANSPORT_IO_FAILED"),
            (
                "extra",
                [payload, b"x"],
                "ENTRYPOINT_TRANSPORT_IO_FAILED",
            ),
            (
                "wrong",
                [b"synthetiX", b""],
                "ENTRYPOINT_TRANSPORT_BINDING_MISMATCH",
            ),
        )
        for scenario, reads, code in scenarios:
            with self.subTest(scenario=scenario), mock.patch.object(
                tcb.os, "read", side_effect=reads
            ):
                with self.assertRaises(tcb.TCBContractError) as raised:
                    tcb._verify_atomic_entrypoint_snapshot(payload)
            _assert_controlled_error(self, raised, code)

    def test_write_exception_primary_survives_reader_close_failure(self):
        marker = "SYNTHETIC_TRANSPORT_FAILURE_MUST_NOT_ESCAPE"
        native_pipe = os.pipe
        native_close = os.close
        pair = []
        close_attempts = []

        def tracked_pipe():
            descriptors = native_pipe()
            pair.extend(descriptors)
            return descriptors

        def fail_close(descriptor):
            close_attempts.append(descriptor)
            raise OSError(marker)

        try:
            with mock.patch.object(
                tcb.os, "pipe", side_effect=tracked_pipe
            ), mock.patch.object(
                tcb.os, "write", side_effect=OSError(marker)
            ), mock.patch.object(
                tcb.os, "close", side_effect=fail_close
            ):
                with self.assertRaises(tcb.TCBContractError) as raised:
                    tcb._verify_atomic_entrypoint_snapshot(b"synthetic")
        finally:
            for descriptor in pair:
                try:
                    native_close(descriptor)
                except OSError:
                    pass

        _assert_controlled_error(
            self, raised, "ENTRYPOINT_TRANSPORT_IO_FAILED"
        )
        self.assertNotIn(marker, str(raised.exception))
        self.assertEqual(Counter(close_attempts), Counter(pair))

    def test_writer_close_failure_is_not_retried_and_blocks_success(self):
        marker = "SYNTHETIC_TRANSPORT_CLOSE_FAILURE_MUST_NOT_ESCAPE"
        native_pipe = os.pipe
        native_close = os.close
        pair = []
        close_attempts = []

        def tracked_pipe():
            descriptors = native_pipe()
            pair.extend(descriptors)
            return descriptors

        def fail_writer_close(descriptor):
            close_attempts.append(descriptor)
            if pair and descriptor == pair[1]:
                raise OSError(marker)
            native_close(descriptor)

        try:
            with mock.patch.object(
                tcb.os, "pipe", side_effect=tracked_pipe
            ), mock.patch.object(
                tcb.os, "close", side_effect=fail_writer_close
            ):
                with self.assertRaises(tcb.TCBContractError) as raised:
                    tcb._verify_atomic_entrypoint_snapshot(b"synthetic")
        finally:
            if pair:
                try:
                    native_close(pair[1])
                except OSError:
                    pass

        _assert_controlled_error(
            self, raised, "ENTRYPOINT_TRANSPORT_CLOSE_FAILED"
        )
        self.assertNotIn(marker, str(raised.exception))
        self.assertEqual(Counter(close_attempts), Counter(pair))

    def test_pipe_buf_below_pinned_bound_fails_without_write(self):
        with mock.patch.object(
            tcb.os, "fpathconf", return_value=tcb.MAX_ATOMIC_ENTRYPOINT_BYTES - 1
        ), mock.patch.object(tcb.os, "write") as injected_write:
            with self.assertRaises(tcb.TCBContractError) as raised:
                tcb._verify_atomic_entrypoint_snapshot(b"synthetic")
        _assert_controlled_error(
            self, raised, "ENTRYPOINT_TRANSPORT_SIZE_LIMIT"
        )
        injected_write.assert_not_called()

    def test_wrong_pipe_end_type_access_and_inheritability_fail_closed(self):
        native_pipe = os.pipe
        scenarios = ("regular", "swapped", "inheritable")
        for scenario in scenarios:
            descriptors = []
            if scenario == "regular":
                first_raw = tempfile.TemporaryFile()
                second_raw = tempfile.TemporaryFile()
                first = os.dup(first_raw.fileno())
                second = os.dup(second_raw.fileno())
                first_raw.close()
                second_raw.close()
                supplied = (first, second)
            else:
                read_descriptor, write_descriptor = native_pipe()
                if scenario == "inheritable":
                    os.set_inheritable(read_descriptor, True)
                    supplied = (read_descriptor, write_descriptor)
                else:
                    supplied = (write_descriptor, read_descriptor)
            descriptors.extend(supplied)
            with self.subTest(scenario=scenario), mock.patch.object(
                tcb.os, "pipe", return_value=supplied
            ):
                with self.assertRaises(tcb.TCBContractError) as raised:
                    tcb._verify_atomic_entrypoint_snapshot(b"synthetic")
            _assert_controlled_error(
                self, raised, "ENTRYPOINT_TRANSPORT_IO_FAILED"
            )
            for descriptor in set(descriptors):
                with self.assertRaises(OSError):
                    os.fstat(descriptor)

    def test_duplicate_or_closed_reused_pipe_fd_never_succeeds(self):
        native_pipe = os.pipe
        read_descriptor, write_descriptor = native_pipe()
        try:
            with mock.patch.object(
                tcb.os,
                "pipe",
                return_value=(read_descriptor, read_descriptor),
            ):
                with self.assertRaises(tcb.TCBContractError) as duplicate:
                    tcb._verify_atomic_entrypoint_snapshot(b"synthetic")
            _assert_controlled_error(
                self, duplicate, "ENTRYPOINT_TRANSPORT_IO_FAILED"
            )
        finally:
            try:
                os.close(write_descriptor)
            except OSError:
                pass

        closed_descriptor, live_descriptor = native_pipe()
        os.close(closed_descriptor)
        try:
            with mock.patch.object(
                tcb.os,
                "pipe",
                return_value=(closed_descriptor, live_descriptor),
            ):
                with self.assertRaises(tcb.TCBContractError) as reused:
                    tcb._verify_atomic_entrypoint_snapshot(b"synthetic")
            _assert_controlled_error(
                self, reused, "ENTRYPOINT_TRANSPORT_IO_FAILED"
            )
        finally:
            try:
                os.close(live_descriptor)
            except OSError:
                pass

    def test_snapshot_uses_cached_bytes_after_source_path_mutation(self):
        admitted = b'SYNTHETIC_ROLE = "provider_request_harness"\n'
        mutated = b'SYNTHETIC_ROLE = "mutated_path"\n'
        native_write = os.write
        observed_writes = []
        with tempfile.TemporaryDirectory() as raw_root:
            source = Path(raw_root) / "provider.py"
            source.write_bytes(admitted)
            cached = source.read_bytes()
            source.write_bytes(mutated)

            def capture_write(descriptor, data):
                observed_writes.append(bytes(data))
                return native_write(descriptor, data)

            with mock.patch.object(
                tcb.os, "write", side_effect=capture_write
            ):
                tcb._verify_atomic_entrypoint_snapshot(cached)

            self.assertEqual(observed_writes, [admitted])
            self.assertEqual(source.read_bytes(), mutated)

    def test_transport_failure_cli_output_is_controlled_and_stderr_free(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root).resolve()
            paths = _materialize_documents(root, _positive_documents())
            arguments = (
                "verify",
                paths["contract"],
                paths["manifest"],
                paths["acceptance"],
                paths["envelope"],
                paths["runtime_acceptance"],
                str(root),
            )
            stdout_bytes = io.BytesIO()
            stderr_bytes = io.BytesIO()
            stdout = io.TextIOWrapper(stdout_bytes, encoding="utf-8")
            stderr = io.TextIOWrapper(stderr_bytes, encoding="utf-8")
            with mock.patch.object(
                tcb.os, "write", return_value=0
            ), mock.patch.object(sys, "stdout", stdout), mock.patch.object(
                sys, "stderr", stderr
            ):
                exit_code = tcb.main(arguments)
                stdout.flush()
                stderr.flush()
            result = json.loads(stdout_bytes.getvalue())

        self.assertEqual(exit_code, 2)
        self.assertEqual(stderr_bytes.getvalue(), b"")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["codes"], ["ENTRYPOINT_TRANSPORT_IO_FAILED"])
        self.assertEqual(result["counts"], tcb._empty_counts())


class RootedStableReadBoundaryTests(unittest.TestCase):
    def _read(self, root_fd, relative_path, limit=None):
        if limit is None:
            limit = tcb.MAX_JSON_INPUT_BYTES
        return tcb._read_rooted_regular_file(root_fd, relative_path, limit)

    def test_exact_complete_and_short_positive_reads_return_all_bytes(self):
        payload = b"synthetic-short-positive-read-payload"
        native_read = os.read
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write_relative(root, "records/value.json", payload)
            with _root_descriptor(root) as root_fd:
                self.assertEqual(self._read(root_fd, "records/value.json"), payload)

                def short_read(descriptor, count):
                    return native_read(descriptor, min(count, 3))

                with mock.patch.object(
                    tcb.os, "read", side_effect=short_read
                ) as injected_read:
                    self.assertEqual(
                        self._read(root_fd, "records/value.json"), payload
                    )
                self.assertGreater(injected_read.call_count, 1)

    def test_physical_exact_size_and_oversize_are_checked_before_read(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            exact = _write_relative(
                root,
                "records/exact.bin",
                b"x" * tcb.MAX_EXECUTABLE_FILE_BYTES,
            )
            oversize = _write_relative(
                root,
                "records/oversize.bin",
                b"x" * (tcb.MAX_EXECUTABLE_FILE_BYTES + 1),
            )
            self.assertEqual(exact.stat().st_size, tcb.MAX_EXECUTABLE_FILE_BYTES)
            self.assertEqual(
                oversize.stat().st_size, tcb.MAX_EXECUTABLE_FILE_BYTES + 1
            )
            with _root_descriptor(root) as root_fd:
                self.assertEqual(
                    len(
                        self._read(
                            root_fd,
                            "records/exact.bin",
                            tcb.MAX_EXECUTABLE_FILE_BYTES,
                        )
                    ),
                    tcb.MAX_EXECUTABLE_FILE_BYTES,
                )
                with mock.patch.object(tcb.os, "read") as injected_read:
                    with self.assertRaises(tcb.TCBContractError) as raised:
                        self._read(
                            root_fd,
                            "records/oversize.bin",
                            tcb.MAX_EXECUTABLE_FILE_BYTES,
                        )
                _assert_controlled_error(self, raised, "INPUT_SIZE_LIMIT")
                injected_read.assert_not_called()

    def test_premature_eof_is_rejected_and_closed(self):
        payload = b"synthetic-premature-eof"
        native_close = os.close
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write_relative(root, "records/value.json", payload)
            with _root_descriptor(root) as root_fd, mock.patch.object(
                tcb.os, "read", side_effect=(payload[:-1], b"")
            ) as injected_read, mock.patch.object(
                tcb.os, "close", side_effect=native_close
            ) as injected_close:
                with self.assertRaises(tcb.TCBContractError) as raised:
                    self._read(root_fd, "records/value.json")
        _assert_controlled_error(self, raised, "INPUT_CHANGED")
        self.assertEqual(injected_read.call_count, 2)
        self.assertGreaterEqual(injected_close.call_count, 1)
        for call in injected_close.call_args_list:
            descriptor = call.args[0]
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_growth_shrink_and_metadata_drift_are_rejected(self):
        scenarios = ("growth", "shrink", "metadata")
        for scenario in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root)
                path = _write_relative(
                    root, "records/value.json", b"synthetic-stable-read"
                )
                native_read = os.read
                changed = False

                def mutate_then_read(descriptor, count):
                    nonlocal changed
                    chunk = native_read(descriptor, min(count, 4))
                    if not changed:
                        changed = True
                        if scenario == "growth":
                            with path.open("ab") as stream:
                                stream.write(b"+")
                        elif scenario == "shrink":
                            os.truncate(path, 1)
                        else:
                            current = path.stat()
                            os.utime(
                                path,
                                ns=(current.st_atime_ns, current.st_mtime_ns + 1_000_000),
                            )
                    return chunk

                with _root_descriptor(root) as root_fd, mock.patch.object(
                    tcb.os, "read", side_effect=mutate_then_read
                ):
                    with self.assertRaises(tcb.TCBContractError) as raised:
                        self._read(root_fd, "records/value.json")
                _assert_controlled_error(self, raised, "INPUT_CHANGED")

    def test_entry_replacement_after_open_is_rejected(self):
        original = b"synthetic-original-opened-bytes"
        replacement = b"synthetic-replacement-path-bytes"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            path = _write_relative(root, "records/value.json", original)
            moved = root / "records" / "opened-original.json"
            native_read = os.read
            replaced = False

            def replace_then_read(descriptor, count):
                nonlocal replaced
                chunk = native_read(descriptor, count)
                if not replaced:
                    replaced = True
                    path.rename(moved)
                    path.write_bytes(replacement)
                return chunk

            with _root_descriptor(root) as root_fd, mock.patch.object(
                tcb.os, "read", side_effect=replace_then_read
            ):
                with self.assertRaises(tcb.TCBContractError) as raised:
                    self._read(root_fd, "records/value.json")
        _assert_controlled_error(self, raised, "INPUT_CHANGED")

    def test_read_failure_and_close_failure_are_controlled_without_marker(self):
        read_marker = "SYNTHETIC_READ_EXCEPTION_MUST_NOT_ESCAPE"
        close_marker = "SYNTHETIC_CLOSE_EXCEPTION_MUST_NOT_ESCAPE"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write_relative(root, "records/value.json", b"synthetic")
            with _root_descriptor(root) as root_fd, mock.patch.object(
                tcb.os, "read", side_effect=OSError(read_marker)
            ):
                with self.assertRaises(tcb.TCBContractError) as raised:
                    self._read(root_fd, "records/value.json")
            _assert_controlled_error(self, raised, "INPUT_READ_FAILED")
            self.assertNotIn(read_marker, str(raised.exception))

            with _root_descriptor(root) as root_fd, _injected_close_failure(
                close_marker
            ) as (injected_open, injected_close, opened):
                with self.assertRaises(tcb.TCBContractError) as raised:
                    self._read(root_fd, "records/value.json")
            _assert_controlled_error(self, raised, "INPUT_READ_FAILED")
            self.assertNotIn(close_marker, str(raised.exception))
            self.assertGreaterEqual(injected_open.call_count, 1)
            self.assertEqual(injected_close.call_count, len(opened))
            self.assertEqual(
                [call.args[0] for call in injected_close.call_args_list], opened
            )

    def test_primary_input_changed_error_survives_close_failure(self):
        marker = "SYNTHETIC_EOF_CLOSE_EXCEPTION_MUST_NOT_ESCAPE"
        payload = b"synthetic-eof-primary"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write_relative(root, "records/value.json", payload)
            with _root_descriptor(root) as root_fd, _injected_close_failure(
                marker
            ) as (_, injected_close, opened), mock.patch.object(
                tcb.os, "read", side_effect=(payload[:-1], b"")
            ):
                with self.assertRaises(tcb.TCBContractError) as raised:
                    self._read(root_fd, "records/value.json")
        _assert_controlled_error(self, raised, "INPUT_CHANGED")
        self.assertEqual(injected_close.call_count, len(opened))

    def test_symlink_parent_leaf_directory_fifo_and_hardlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            real_directory = root / "real"
            real_directory.mkdir()
            regular = _write_relative(root, "real/value.json", b"synthetic")
            (root / "parent-link").symlink_to(real_directory, target_is_directory=True)
            (root / "leaf-link.json").symlink_to(regular)
            (root / "directory-leaf").mkdir()
            os.mkfifo(root / "fifo-leaf")
            os.link(regular, root / "hardlink-leaf.json")

            with _root_descriptor(root) as root_fd:
                for relative in (
                    "parent-link/value.json",
                    "leaf-link.json",
                    "directory-leaf",
                    "fifo-leaf",
                    "real/value.json",
                    "hardlink-leaf.json",
                ):
                    with self.subTest(relative=relative):
                        with self.assertRaises(tcb.TCBContractError) as raised:
                            self._read(root_fd, relative)
                        _assert_controlled_error(self, raised, "INPUT_FILE_INVALID")

    def test_character_device_leaf_fails_closed_without_reading(self):
        with _root_descriptor(Path("/")) as root_fd, mock.patch.object(
            tcb.os, "read"
        ) as injected_read:
            with self.assertRaises(tcb.TCBContractError) as raised:
                self._read(root_fd, "dev/null")
        _assert_controlled_error(self, raised, "INPUT_FILE_INVALID")
        injected_read.assert_not_called()

    def test_component_path_parser_rejects_ambiguous_or_non_ascii_paths(self):
        invalid = (
            "",
            "/absolute",
            "a/",
            "/a",
            "a//b",
            "a/./b",
            "a/../b",
            ".",
            "..",
            "a\\b",
            "a\x00b",
            "a\nb",
            "synthetic/é.json",
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            with _root_descriptor(root) as root_fd:
                for value in invalid:
                    with self.subTest(value=ascii(value)):
                        with self.assertRaises(tcb.TCBContractError) as raised:
                            self._read(root_fd, value)
                        _assert_controlled_error(self, raised, "INPUT_FILE_INVALID")

    def test_every_successfully_opened_descriptor_gets_exactly_one_close_attempt(self):
        native_open = os.open
        native_close = os.close
        opened = []
        closed = []

        def tracked_open(*args, **kwargs):
            descriptor = native_open(*args, **kwargs)
            opened.append(descriptor)
            return descriptor

        def tracked_close(descriptor):
            closed.append(descriptor)
            native_close(descriptor)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write_relative(root, "one/two/value.json", b"synthetic")
            root_fd = native_open(
                str(root),
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_CLOEXEC", 0),
            )
            try:
                with mock.patch.object(
                    tcb.os, "open", side_effect=tracked_open
                ), mock.patch.object(tcb.os, "close", side_effect=tracked_close):
                    self.assertEqual(
                        self._read(root_fd, "one/two/value.json"), b"synthetic"
                    )
            finally:
                native_close(root_fd)

        self.assertEqual(len(opened), 3)
        self.assertEqual(Counter(closed), Counter(opened))
        self.assertTrue(all(count == 1 for count in Counter(closed).values()))

    def test_verify_paths_closes_root_chain_once_on_early_failure(self):
        native_open = os.open
        native_close = os.close
        opened = []
        closed = []

        def tracked_open(*args, **kwargs):
            descriptor = native_open(*args, **kwargs)
            opened.append(descriptor)
            return descriptor

        def tracked_close(descriptor):
            closed.append(descriptor)
            native_close(descriptor)

        with tempfile.TemporaryDirectory() as raw_parent:
            root = Path(raw_parent).resolve() / "nested" / "repository"
            root.mkdir(parents=True)
            with mock.patch.object(
                tcb.os, "open", side_effect=tracked_open
            ), mock.patch.object(tcb.os, "close", side_effect=tracked_close):
                result = tcb.verify_paths(
                    "missing-contract.json",
                    "manifest.json",
                    "acceptance.json",
                    "envelope.json",
                    "runtime-acceptance.json",
                    str(root),
                )

        self.assertEqual(result["status"], "error")
        self.assertIn(
            result["codes"][0], {"INPUT_FILE_INVALID", "INPUT_READ_FAILED"}
        )
        self.assertGreaterEqual(len(opened), 2)
        self.assertEqual(Counter(closed), Counter(opened))
        self.assertTrue(all(count == 1 for count in Counter(closed).values()))

    def test_close_failure_attempts_every_descriptor_once_and_never_succeeds(self):
        marker = "SYNTHETIC_ROOT_CLOSE_FAILURE_MUST_NOT_ESCAPE"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root).resolve()
            _write_relative(root, "contract.json", b"{}")
            for name in (
                "manifest.json",
                "acceptance.json",
                "envelope.json",
                "runtime-acceptance.json",
            ):
                _write_relative(root, name, b"{}")
            with _injected_close_failure(marker) as (
                injected_open,
                injected_close,
                opened,
            ):
                result = tcb.verify_paths(
                    "contract.json",
                    "manifest.json",
                    "acceptance.json",
                    "envelope.json",
                    "runtime-acceptance.json",
                    str(root),
                )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["codes"], ["INPUT_READ_FAILED"])
        self.assertGreaterEqual(injected_open.call_count, 2)
        self.assertEqual(injected_close.call_count, len(opened))
        self.assertEqual(
            Counter(call.args[0] for call in injected_close.call_args_list),
            Counter(opened),
        )
        self.assertNotIn(marker, json.dumps(result))

    def test_semantic_primary_survives_root_chain_close_failures(self):
        marker = "SYNTHETIC_ROOT_CLOSE_AFTER_SEMANTIC_ERROR_MUST_NOT_ESCAPE"
        documents = _positive_documents()
        documents["manifest"]["synthetic_unknown"] = False
        native_close = os.close
        real_open_root = tcb._open_repository_root
        root_descriptors = []
        close_attempts = []

        def capture_root(repository_root):
            result = real_open_root(repository_root)
            root_descriptors.extend(result[1])
            return result

        def fail_root_close(descriptor):
            close_attempts.append(descriptor)
            if descriptor in root_descriptors:
                raise OSError(marker)
            native_close(descriptor)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root).resolve()
            paths = _materialize_documents(root, documents)
            try:
                with mock.patch.object(
                    tcb, "_open_repository_root", side_effect=capture_root
                ), mock.patch.object(
                    tcb.os, "close", side_effect=fail_root_close
                ):
                    result = tcb.verify_paths(
                        paths["contract"],
                        paths["manifest"],
                        paths["acceptance"],
                        paths["envelope"],
                        paths["runtime_acceptance"],
                        str(root),
                    )
            finally:
                for descriptor in dict.fromkeys(root_descriptors):
                    try:
                        native_close(descriptor)
                    except OSError:
                        pass

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["codes"], ["MANIFEST_INVALID"])
        self.assertNotIn(marker, json.dumps(result))
        self.assertEqual(
            Counter(
                descriptor
                for descriptor in close_attempts
                if descriptor in root_descriptors
            ),
            Counter(root_descriptors),
        )


class CwdAdmissionBoundaryTests(unittest.TestCase):
    def _main_arguments(self, paths, root):
        return (
            "verify",
            paths["contract"],
            paths["manifest"],
            paths["acceptance"],
            paths["envelope"],
            paths["runtime_acceptance"],
            str(root),
        )

    def _captured_main(self, arguments):
        stdout_bytes = io.BytesIO()
        stderr_bytes = io.BytesIO()
        stdout = io.TextIOWrapper(stdout_bytes, encoding="utf-8")
        stderr = io.TextIOWrapper(stderr_bytes, encoding="utf-8")
        with mock.patch.object(sys, "stdout", stdout), mock.patch.object(
            sys, "stderr", stderr
        ):
            exit_code = tcb.main(arguments)
            stdout.flush()
            stderr.flush()
        return exit_code, stdout_bytes.getvalue(), stderr_bytes.getvalue()

    def _assert_cwd_cli_failure(self, exit_code, output, errors, *forbidden):
        self.assertEqual(exit_code, 2)
        self.assertEqual(errors, b"")
        self.assertEqual(
            json.loads(output),
            {
                "codes": ["INVOCATION_CWD_INVALID"],
                "counts": {
                    "contract_records": 0,
                    "executable_files": 0,
                    "import_entries": 0,
                    "linkage_records": 0,
                },
                "status": "error",
            },
        )
        for marker in forbidden:
            if type(marker) is str:
                marker = marker.encode("utf-8")
            self.assertNotIn(marker, output + errors)
        self.assertNotIn(b"Traceback", output + errors)

    def test_cwd_replacement_and_metadata_drift_are_cli_failures_with_one_close_each(self):
        for scenario in ("replacement", "metadata"):
            marker = "SYNTHETIC_CWD_{}_MUST_NOT_ESCAPE".format(
                scenario.upper()
            )
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root).resolve()
                paths = _materialize_documents(root, _positive_documents())
                cwd_path = root / "synthetic" / "work"
                moved_path = root / "synthetic" / "opened-work"
                native_open = os.open
                native_close = os.close
                native_fstat = os.fstat
                opened = []
                close_attempts = []
                cwd_descriptor = []
                mutated = False

                def tracked_open(*args, **kwargs):
                    descriptor = native_open(*args, **kwargs)
                    opened.append(descriptor)
                    if args[0] == "work":
                        cwd_descriptor.append(descriptor)
                    return descriptor

                def mutate_after_first_cwd_fstat(descriptor):
                    nonlocal mutated
                    result = native_fstat(descriptor)
                    if (
                        cwd_descriptor
                        and descriptor == cwd_descriptor[0]
                        and not mutated
                    ):
                        mutated = True
                        if scenario == "replacement":
                            cwd_path.rename(moved_path)
                            cwd_path.mkdir()
                        else:
                            current = cwd_path.stat()
                            os.utime(
                                cwd_path,
                                ns=(
                                    current.st_atime_ns,
                                    current.st_mtime_ns + 1_000_000,
                                ),
                            )
                    return result

                def tracked_close(descriptor):
                    close_attempts.append(descriptor)
                    native_close(descriptor)

                with mock.patch.object(
                    tcb.os, "open", side_effect=tracked_open
                ), mock.patch.object(
                    tcb.os, "fstat", side_effect=mutate_after_first_cwd_fstat
                ), mock.patch.object(
                    tcb.os, "close", side_effect=tracked_close
                ), mock.patch.object(
                    tcb,
                    "_verify_atomic_entrypoint_snapshot",
                    return_value=None,
                ):
                    exit_code, output, errors = self._captured_main(
                        self._main_arguments(paths, root)
                    )

                self.assertTrue(mutated)
                self.assertEqual(Counter(opened), Counter(close_attempts))
                self._assert_cwd_cli_failure(
                    exit_code,
                    output,
                    errors,
                    marker,
                    str(root),
                    str(cwd_path),
                )

    def test_cwd_close_failure_blocks_success_and_is_attempted_once(self):
        marker = "SYNTHETIC_CWD_CLOSE_FAILURE_MUST_NOT_ESCAPE"
        native_open = os.open
        native_close = os.close
        opened = []
        close_attempts = []
        cwd_descriptor = []
        injected_failure = False
        cwd_close_failures = 0

        def tracked_open(*args, **kwargs):
            descriptor = native_open(*args, **kwargs)
            opened.append(descriptor)
            if args[0] == "work":
                cwd_descriptor.append(descriptor)
            return descriptor

        def fail_cwd_close(descriptor):
            nonlocal injected_failure, cwd_close_failures
            close_attempts.append(descriptor)
            if (
                cwd_descriptor
                and descriptor == cwd_descriptor[0]
                and not injected_failure
            ):
                injected_failure = True
                cwd_close_failures += 1
                raise OSError(marker)
            native_close(descriptor)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root).resolve()
            paths = _materialize_documents(root, _positive_documents())
            try:
                with mock.patch.object(
                    tcb.os, "open", side_effect=tracked_open
                ), mock.patch.object(
                    tcb.os, "close", side_effect=fail_cwd_close
                ), mock.patch.object(
                    tcb,
                    "_verify_atomic_entrypoint_snapshot",
                    return_value=None,
                ):
                    exit_code, output, errors = self._captured_main(
                        self._main_arguments(paths, root)
                    )
            finally:
                for descriptor in cwd_descriptor:
                    try:
                        native_close(descriptor)
                    except OSError:
                        pass

        self.assertEqual(Counter(opened), Counter(close_attempts))
        self.assertEqual(cwd_close_failures, 1)
        self._assert_cwd_cli_failure(
            exit_code, output, errors, marker, str(root)
        )

    def test_primary_invalid_cwd_survives_close_failure_and_cleanup_is_external(self):
        marker = "SYNTHETIC_CWD_PRIMARY_CLOSE_FAILURE_MUST_NOT_ESCAPE"
        native_open = os.open
        native_close = os.close
        opened = []
        close_attempts = []

        def tracked_open(*args, **kwargs):
            descriptor = native_open(*args, **kwargs)
            opened.append(descriptor)
            return descriptor

        def fail_close(descriptor):
            close_attempts.append(descriptor)
            raise OSError(marker)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write_relative(root, "synthetic/work", b"not-a-directory")
            with _root_descriptor(root) as root_fd:
                try:
                    with mock.patch.object(
                        tcb.os, "open", side_effect=tracked_open
                    ), mock.patch.object(
                        tcb.os, "close", side_effect=fail_close
                    ):
                        with self.assertRaises(tcb.TCBContractError) as raised:
                            tcb._verify_rooted_directory(
                                root_fd, "synthetic/work"
                            )
                finally:
                    for descriptor in dict.fromkeys(opened):
                        try:
                            native_close(descriptor)
                        except OSError:
                            pass

        _assert_controlled_error(self, raised, "INVOCATION_CWD_INVALID")
        self.assertEqual(Counter(opened), Counter(close_attempts))
        self.assertNotIn(marker, str(raised.exception))


class StaticOfflineSurfaceTests(unittest.TestCase):
    def test_raw_reader_is_reachable_only_through_global_admission_index(self):
        tree = ast.parse(VERIFIER.read_text("utf-8"))
        callers = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "_read_rooted_regular_file"
                for call in ast.walk(node)
            ):
                callers.add(node.name)
        self.assertEqual(callers, {"admit_record", "admit_executable"})

        source = VERIFIER.read_text("utf-8")
        for forbidden in (".casefold(", ".lower(", "realpath("):
            self.assertNotIn(forbidden, source)

    def test_verifier_imports_no_existing_m1b_validator_network_or_process_client(self):
        tree = ast.parse(VERIFIER.read_text("utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        forbidden = {
            "http",
            "http.client",
            "importlib",
            "requests",
            "runpy",
            "socket",
            "subprocess",
            "urllib",
            "urllib.request",
            "tools.research.m1b_contract",
            "tools.research.m1b_owner_freeze",
        }
        self.assertTrue(imported.isdisjoint(forbidden), imported & forbidden)

    def test_verifier_has_no_dynamic_execution_or_ambient_discovery_calls(self):
        tree = ast.parse(VERIFIER.read_text("utf-8"))
        called_names = set()
        called_attributes = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_attributes.add(node.func.attr)
        self.assertTrue(
            called_names.isdisjoint(
                {"__import__", "compile", "eval", "exec", "input", "open"}
            )
        )
        self.assertTrue(
            called_attributes.isdisjoint(
                {
                    "chdir",
                    "expanduser",
                    "getcwd",
                    "getenv",
                    "glob",
                    "listdir",
                    "popen",
                    "scandir",
                    "system",
                    "walk",
                }
            )
        )
        source = VERIFIER.read_text("utf-8")
        self.assertNotIn("os.environ", source)
        self.assertNotIn("Path.home", source)

    def test_public_api_has_no_fixture_report_or_default_path_mode(self):
        self.assertFalse(hasattr(tcb, "verify_bytes"))
        signature_names = tuple(tcb.verify_paths.__code__.co_varnames[:6])
        self.assertEqual(
            signature_names,
            (
                "contract_path",
                "manifest_path",
                "acceptance_path",
                "envelope_path",
                "runtime_acceptance_path",
                "repository_root",
            ),
        )
        source = VERIFIER.read_text("utf-8")
        for forbidden in (
            'argv[0] == "fixture"',
            'argv[0] == "materialize"',
            'argv[0] == "report"',
            "stdin.read",
            "sys.stdin",
        ):
            self.assertNotIn(forbidden, source)


class OfflineCliFailureBoundaryTests(unittest.TestCase):
    def _run(self, *arguments):
        return subprocess.run(
            [sys.executable, str(VERIFIER), *arguments],
            cwd=REPOSITORY_ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )

    def _assert_closed_failure(self, completed, *forbidden):
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stderr, b"")
        result = json.loads(completed.stdout)
        self.assertEqual(set(result), {"codes", "counts", "status"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(
            set(result["counts"]),
            {
                "contract_records",
                "executable_files",
                "import_entries",
                "linkage_records",
            },
        )
        self.assertEqual(set(result["counts"].values()), {0})
        self.assertEqual(len(result["codes"]), 1)
        self.assertRegex(result["codes"][0], r"\A[A-Z][A-Z0-9_]+\Z")
        combined = completed.stdout + completed.stderr
        for value in forbidden:
            if type(value) is str:
                value = value.encode("utf-8")
            self.assertNotIn(value, combined)
        self.assertNotIn(b"Traceback", combined)
        self.assertNotIn(b"Exception", combined)
        return result

    def test_bad_arguments_and_forbidden_modes_are_compact_and_stderr_free(self):
        marker = "SYNTHETIC_BAD_ARGUMENT_PATH_MUST_NOT_ESCAPE"
        argument_sets = (
            ((), "CLI_ARGUMENT_MISSING"),
            (("verify",), "CLI_ARGUMENT_MISSING"),
            (
                ("verify", marker, marker, marker, marker, marker),
                "CLI_ARGUMENT_MISSING",
            ),
            (
                ("verify", marker, marker, marker, marker, marker, marker, marker),
                "CLI_ARGUMENT_EXTRA",
            ),
            (
                ("fixture", marker, marker, marker, marker, marker, marker),
                "CLI_ARGUMENTS_INVALID",
            ),
            (
                ("materialize", marker, marker, marker, marker, marker, marker),
                "CLI_ARGUMENTS_INVALID",
            ),
            (
                ("report", marker, marker, marker, marker, marker, marker),
                "CLI_ARGUMENTS_INVALID",
            ),
        )
        for arguments, expected in argument_sets:
            with self.subTest(arguments=arguments[:1], count=len(arguments)):
                result = self._assert_closed_failure(
                    self._run(*arguments), marker
                )
                self.assertEqual(result["codes"], [expected])

    def test_missing_explicit_record_never_echoes_path_or_exception(self):
        marker = "SYNTHETIC_MISSING_CONTRACT_PATH_MUST_NOT_ESCAPE"
        with tempfile.TemporaryDirectory() as raw_root:
            repository_root = str(Path(raw_root).resolve())
            completed = self._run(
                "verify",
                marker,
                "manifest.json",
                "acceptance.json",
                "envelope.json",
                "runtime-acceptance.json",
                repository_root,
            )
        result = self._assert_closed_failure(completed, marker, repository_root)
        self.assertIn(
            result["codes"][0],
            {"INPUT_FILE_INVALID", "INPUT_READ_FAILED"},
        )

    def test_invalid_utf8_bom_duplicate_and_oversize_contract_do_not_leak(self):
        marker = b"SYNTHETIC_CONTRACT_CONTENT_MUST_NOT_ESCAPE"
        cases = (
            (b"\xff" + marker, "UTF8_INVALID"),
            (b"\xef\xbb\xbf{}" + marker, "JSON_MALFORMED"),
            (b'{"x":1,"x":2}', "JSON_DUPLICATE_KEY"),
            (b" " * (tcb.MAX_JSON_INPUT_BYTES + 1), "INPUT_SIZE_LIMIT"),
        )
        for payload, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root).resolve()
                _write_relative(root, "contract.json", payload)
                for name in (
                    "manifest.json",
                    "acceptance.json",
                    "envelope.json",
                    "runtime-acceptance.json",
                ):
                    _write_relative(root, name, b"{}")
                completed = self._run(
                    "verify",
                    "contract.json",
                    "manifest.json",
                    "acceptance.json",
                    "envelope.json",
                    "runtime-acceptance.json",
                    str(root),
                )
                result = self._assert_closed_failure(
                    completed,
                    marker,
                    str(root),
                    str(root / "contract.json"),
                    payload if len(payload) < 4096 else marker,
                )
                self.assertEqual(result["codes"], [expected])

    def test_symlink_and_relative_repository_root_fail_closed_without_leakage(self):
        marker = "SYNTHETIC_ROOT_PATH_MUST_NOT_ESCAPE"
        with tempfile.TemporaryDirectory() as raw_parent:
            parent = Path(raw_parent).resolve()
            real_root = parent / "real-root"
            real_root.mkdir()
            link_root = parent / marker
            link_root.symlink_to(real_root, target_is_directory=True)
            for root_value in (str(link_root), marker):
                with self.subTest(absolute=os.path.isabs(root_value)):
                    completed = self._run(
                        "verify",
                        "contract.json",
                        "manifest.json",
                        "acceptance.json",
                        "envelope.json",
                        "runtime-acceptance.json",
                        root_value,
                    )
                    self._assert_closed_failure(completed, marker, str(real_root))

    def test_unexpected_exception_text_is_discarded_by_execute(self):
        marker = "SYNTHETIC_UNEXPECTED_EXCEPTION_MUST_NOT_ESCAPE"
        with mock.patch.object(
            tcb,
            "verify_paths",
            side_effect=RuntimeError(marker),
        ):
            result = tcb._execute(
                (
                    "verify",
                    "contract.json",
                    "manifest.json",
                    "acceptance.json",
                    "envelope.json",
                    "runtime-acceptance.json",
                    "/synthetic/root",
                )
            )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["codes"], ["UNEXPECTED_FAILURE"])
        self.assertNotIn(marker, json.dumps(result))

    def test_result_encoder_fallback_remains_closed_and_allowlisted(self):
        marker = "SYNTHETIC_ENCODER_EXCEPTION_MUST_NOT_ESCAPE"
        with mock.patch.object(tcb.json, "dumps", side_effect=RuntimeError(marker)):
            encoded = tcb._encode_result({"synthetic": object()})
        self.assertEqual(
            encoded,
            b'{"codes":["UNEXPECTED_FAILURE"],"counts":{"contract_records":0,"executable_files":0,"import_entries":0,"linkage_records":0},"status":"error"}\n',
        )
        self.assertNotIn(marker.encode("ascii"), encoded)


if __name__ == "__main__":
    unittest.main()
