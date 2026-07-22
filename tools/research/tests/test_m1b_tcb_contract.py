"""Public synthetic tests for the M1B executable/TCB admission contract.

The four role payloads in this module are materialized only below a temporary
repository root.  They are opaque bytes and are never imported or executed.
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
    / "offline-executable-tcb-contract-v1.json"
)
CASES = REPOSITORY_ROOT / "fixtures" / "m1b" / "tcb-admission" / "cases.json"
VERIFIER = REPOSITORY_ROOT / "tools" / "research" / "m1b_tcb_contract.py"

IMPLEMENTATION_GENERATION = 1
PROTOCOL_GENERATION = 108
MANIFEST_SCHEMA = "m1b-executable-implementation-manifest-v1"
MANIFEST_DOMAIN = b"stellaris-m1b-executable-manifest-v1"
CONTRACT_SCHEMA = "m1b-offline-executable-tcb-contract-v1"
CONTRACT_VERSION = "m1b-offline-executable-tcb-admission-v1"
CONTRACT_DOMAIN = b"stellaris-m1b-offline-executable-tcb-contract-v1"
EXECUTION_ENVELOPE_SCHEMA = "m1b-execution-envelope-v1"
EXPECTED_CONTRACT_BYTES = 4848
EXPECTED_CONTRACT_FILE_SHA256 = (
    "7af6471986e194fd11a9e8cf003e92a8f534c1328b3b15ab00a043067e82a3dc"
)
EXPECTED_CONTRACT_DIGEST = (
    "589cf895c659b57c2f44268acfa0bf33b3c98d6cd5e6b4fea1f2f9b2500d1a5f"
)
EXPECTED_CASE_COUNT = 127
EXPECTED_CASES_SHA256 = (
    "99f8c109f5967b1b1f7bb11e12617788b001b63c805626def0642200a901a082"
)
REQUIRED_MATRIX_IDS = frozenset(
    """
    positive-synthetic-conformance
    contract-schema-drift contract-version-drift contract-generation-drift
    contract-self-digest-field
    contract-semantic-json-noncanonical
    manifest-missing-role manifest-extra-role manifest-duplicate-role
    manifest-unknown-role manifest-one-path-multiple-roles manifest-role-swap
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
    """.split()
)

ROLE_PAYLOADS = {
    "synthetic/analysis-engine.opaque": (
        "analysis_engine",
        b"SYNTHETIC-OPAQUE-ANALYSIS-ENGINE\x00NOT-PYTHON\n",
    ),
    "synthetic/contract-validator.opaque": (
        "contract_validator",
        b"SYNTHETIC-OPAQUE-CONTRACT-VALIDATOR\x00NOT-PYTHON\n",
    ),
    "synthetic/provider-request-harness.opaque": (
        "provider_request_harness",
        b"SYNTHETIC-OPAQUE-PROVIDER-HARNESS\x00NOT-PYTHON\n",
    ),
    "synthetic/synthetic-fixture-materializer.opaque": (
        "synthetic_fixture_materializer",
        b"SYNTHETIC-OPAQUE-FIXTURE-MATERIALIZER\x00NOT-PYTHON\n",
    ),
}

INTERPRETER_PATH = "synthetic/runtime/cpython.opaque"
SOURCE_IMPORT_PATH = "synthetic/imports/source-module.opaque"
EXTENSION_IMPORT_PATH = "synthetic/imports/extension-module.opaque"
AUXILIARY_PAYLOADS = {
    INTERPRETER_PATH: b"SYNTHETIC-OPAQUE-CPYTHON-INTERPRETER\x00NOT-EXECUTABLE\n",
    SOURCE_IMPORT_PATH: b"SYNTHETIC-OPAQUE-SOURCE-MODULE\x00NOT-PYTHON\n",
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


def _execution_state(auxiliary_payloads):
    interpreter_sha256 = hashlib.sha256(
        auxiliary_payloads[INTERPRETER_PATH]
    ).hexdigest()
    source_sha256 = hashlib.sha256(
        auxiliary_payloads[SOURCE_IMPORT_PATH]
    ).hexdigest()
    extension_sha256 = hashlib.sha256(
        auxiliary_payloads[EXTENSION_IMPORT_PATH]
    ).hexdigest()
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
        "imports": [
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
            {
                "kind": "builtin",
                "module": "sys",
                "path": None,
                "sha256": interpreter_sha256,
            },
        ],
        "interpreter": {
            "abi_flags": "",
            "byteorder": "little",
            "cache_tag": "cpython-39",
            "executable_path": INTERPRETER_PATH,
            "executable_sha256": interpreter_sha256,
            "extension_suffix": ".cpython-39-darwin.so",
            "implementation": "cpython",
            "machine": "arm64",
            "max_unicode": 1114111,
            "platform": "darwin",
            "pointer_bits": 64,
            "soabi": "cpython-39-darwin",
            "version_tuple": [3, 9, 6, "final", 0],
        },
        "invocation": {
            "argv": [
                INTERPRETER_PATH,
                "-I",
                "-S",
                "-B",
                "synthetic/contract-validator.opaque",
            ],
            "cwd": "synthetic/work",
            "inherited_fds": [],
            "mode": "verified_open_descriptors_no_reopen",
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
            "sys_path": ["synthetic/imports"],
            "warnoptions": [],
            "xoptions": [],
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


def _envelope_for_manifest(manifest_sha256, auxiliary_payloads):
    state = _execution_state(auxiliary_payloads)
    return {
        "admitted_state": copy.deepcopy(state),
        "contract_generation": 1,
        "contract_schema": CONTRACT_SCHEMA,
        "contract_sha256": EXPECTED_CONTRACT_DIGEST,
        "contract_version": CONTRACT_VERSION,
        "envelope_generation": 1,
        "envelope_schema": EXECUTION_ENVELOPE_SCHEMA,
        "implementation_generation": IMPLEMENTATION_GENERATION,
        "manifest_schema": MANIFEST_SCHEMA,
        "manifest_sha256": manifest_sha256,
        "observed_state": copy.deepcopy(state),
        "protocol_generation": PROTOCOL_GENERATION,
    }


def _positive_documents():
    manifest = _manifest_for_payloads(ROLE_PAYLOADS)
    manifest_bytes = _independent_manifest_bytes(manifest)
    manifest_sha256 = _independent_manifest_digest(manifest_bytes)
    return {
        "acceptance": _acceptance_for_manifest(manifest_sha256),
        "contract": json.loads(CONTRACT.read_text("ascii")),
        "envelope": _envelope_for_manifest(manifest_sha256, AUXILIARY_PAYLOADS),
        "manifest": manifest,
    }


def _materialize_documents(root, documents, *, encodings=None, payloads=None):
    encodings = {} if encodings is None else encodings
    all_payloads = dict(ROLE_PAYLOADS)
    auxiliary_payloads = dict(AUXILIARY_PAYLOADS)
    if payloads:
        all_payloads.update(payloads.get("roles", {}))
        auxiliary_payloads.update(payloads.get("auxiliary", {}))
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
    }
    for target, relative in paths.items():
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
        _write_relative(root, relative, encoded)
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
    return copy.deepcopy(value)


def _apply_case(base_documents, case):
    documents = copy.deepcopy(base_documents)
    for patch in case["patches"]:
        target = documents[patch["target"]]
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
        else:
            raise AssertionError("unknown filesystem mutation")


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
            "registry/m1b/offline-executable-tcb-contract-v1.json",
            {row["path"] for row in self.manifest["files"]},
        )


class PhysicalIdentityAliasTests(unittest.TestCase):
    RECORD_PATHS = (
        "records/contract.json",
        "records/manifest.json",
        "records/acceptance.json",
        "records/envelope.json",
    )

    def _case_variant_manifest(self):
        manifest = _manifest_for_payloads(ROLE_PAYLOADS)
        manifest["files"][0]["path"] = "synthetic/CaseAlias.opaque"
        manifest["files"][1]["path"] = "synthetic/casealias.opaque"
        manifest["files"].sort(key=lambda row: row["path"].encode("ascii"))
        return manifest

    def test_lexically_distinct_case_variant_roles_cannot_share_physical_identity(self):
        manifest = self._case_variant_manifest()
        aliases = {
            "synthetic/CaseAlias.opaque": (101, 201),
            "synthetic/casealias.opaque": (101, 201),
        }
        next_inode = 300

        def injected_identity(
            _root_descriptor,
            relative_path,
            _expected_sha256,
            _verified,
            total_bytes,
        ):
            nonlocal next_inode
            identity = aliases.get(relative_path)
            if identity is None:
                identity = (101, next_inode)
                next_inode += 1
            return total_bytes + 1, True, identity

        with mock.patch.object(
            tcb,
            "_verify_executable_identity",
            side_effect=injected_identity,
        ):
            with self.assertRaises(tcb.TCBContractError) as raised:
                tcb._validate_manifest_bytes(
                    _independent_manifest_bytes(manifest),
                    -1,
                    self.RECORD_PATHS,
                    set(),
                    {},
                    0,
                )
        _assert_controlled_error(self, raised, "MANIFEST_PATH_INVALID")

    def test_role_identity_aliasing_each_input_record_is_forbidden(self):
        manifest = _manifest_for_payloads(ROLE_PAYLOADS)
        manifest_bytes = _independent_manifest_bytes(manifest)
        first_path = manifest["files"][0]["path"]
        for record_index, record_path in enumerate(self.RECORD_PATHS):
            with self.subTest(record=record_path):
                record_identity = (401, 500 + record_index)
                next_inode = 600

                def injected_identity(
                    _root_descriptor,
                    relative_path,
                    _expected_sha256,
                    _verified,
                    total_bytes,
                ):
                    nonlocal next_inode
                    if relative_path == first_path:
                        identity = record_identity
                    else:
                        identity = (401, next_inode)
                        next_inode += 1
                    return total_bytes + 1, True, identity

                with mock.patch.object(
                    tcb,
                    "_verify_executable_identity",
                    side_effect=injected_identity,
                ):
                    with self.assertRaises(tcb.TCBContractError) as raised:
                        tcb._validate_manifest_bytes(
                            manifest_bytes,
                            -1,
                            self.RECORD_PATHS,
                            {record_identity},
                            {},
                            0,
                        )
                _assert_controlled_error(
                    self, raised, "MANIFEST_SELF_ENTRY_FORBIDDEN"
                )

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
        self.assertEqual(contract["contract_generation"], 1)
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


class TCBAdmissionFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases_bytes = CASES.read_bytes()
        cls.fixture = json.loads(cls.cases_bytes.decode("utf-8"))
        cls.base_documents = _positive_documents()

    def test_fixture_identity_count_and_required_adversarial_matrix(self):
        self.assertEqual(
            hashlib.sha256(self.cases_bytes).hexdigest(),
            EXPECTED_CASES_SHA256,
        )
        self.assertEqual(
            self.fixture["fixture_schema"], "m1b-tcb-admission-cases-v1"
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

    def test_all_table_cases_return_exact_controlled_result(self):
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root).resolve()
                documents = _apply_case(self.base_documents, case)
                paths = _materialize_documents(
                    root,
                    documents,
                    encodings=case.get("encoding"),
                )
                _apply_filesystem_mutations(root, case)
                result = tcb.verify_paths(
                    paths["contract"],
                    paths["manifest"],
                    paths["acceptance"],
                    paths["envelope"],
                    str(root),
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
                            "import_entries": 4,
                            "linkage_records": 2,
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
                )
                _apply_filesystem_mutations(root, case)
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(VERIFIER),
                        "verify",
                        paths["contract"],
                        paths["manifest"],
                        paths["acceptance"],
                        paths["envelope"],
                        str(root),
                    ],
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
                str(root),
            )

    def test_declared_import_order_is_exact_not_silently_alphabetized(self):
        documents = copy.deepcopy(self.base_documents)
        imports = documents["envelope"]["admitted_state"]["imports"]
        reordered = [imports[index] for index in (3, 0, 2, 1)]
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
        self.assertEqual(result["counts"]["import_entries"], 4)

    def test_sys_path_declared_order_is_not_silently_alphabetized(self):
        invocation = copy.deepcopy(
            self.base_documents["envelope"]["admitted_state"]["invocation"]
        )
        invocation["sys_path"] = ["synthetic/a", "synthetic/A"]
        validated, paths = tcb._validate_invocation(invocation)
        self.assertEqual(paths, ("synthetic/a", "synthetic/A"))
        self.assertEqual(validated["sys_path"], ["synthetic/a", "synthetic/A"])
        self.assertNotEqual(
            list(paths), sorted(paths, key=lambda value: value.encode("ascii"))
        )
        invocation["sys_path"] = ["synthetic/a", "synthetic/a"]
        with self.assertRaises(tcb.TCBContractError) as raised:
            tcb._validate_invocation(invocation)
        _assert_controlled_error(self, raised, "INVOCATION_POLICY_INVALID")

    def test_repeated_manifest_import_path_reuses_admitted_bytes_without_reopen(self):
        documents = copy.deepcopy(self.base_documents)
        manifest_row = documents["manifest"]["files"][1]
        for state_name in ("admitted_state", "observed_state"):
            state = documents["envelope"][state_name]
            state["imports"][2]["path"] = manifest_row["path"]
            state["imports"][2]["sha256"] = manifest_row["sha256"]
            state["invocation"]["sys_path"] = ["synthetic"]

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
                    str(root),
                )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["executable_files"], 6)
        self.assertEqual(
            opened_leaf_names.count("contract-validator.opaque"), 1
        )

    def test_executable_total_exact_boundary_and_one_unique_byte_over_fail_closed(self):
        role_payloads = {}
        for index, (path, (role, _payload)) in enumerate(ROLE_PAYLOADS.items()):
            role_payloads[path] = (role, bytes((65 + index,)) * 16)

        manifest = _manifest_for_payloads(role_payloads)
        manifest_bytes = _independent_manifest_bytes(manifest)
        manifest_sha256 = _independent_manifest_digest(manifest_bytes)
        documents = {
            "contract": json.loads(CONTRACT.read_text("ascii")),
            "manifest": manifest,
            "acceptance": _acceptance_for_manifest(manifest_sha256),
            "envelope": _envelope_for_manifest(
                manifest_sha256, AUXILIARY_PAYLOADS
            ),
        }
        manifest_rows = documents["manifest"]["files"]
        for state_name in ("admitted_state", "observed_state"):
            state = documents["envelope"][state_name]
            state["interpreter"]["executable_path"] = manifest_rows[0]["path"]
            state["interpreter"]["executable_sha256"] = manifest_rows[0]["sha256"]
            for import_index, manifest_index in ((1, 2), (2, 1)):
                state["imports"][import_index]["path"] = manifest_rows[manifest_index]["path"]
                state["imports"][import_index]["sha256"] = manifest_rows[manifest_index]["sha256"]
            for import_index in (0, 3):
                state["imports"][import_index]["sha256"] = manifest_rows[0]["sha256"]
            state["invocation"]["sys_path"] = ["synthetic"]

        with mock.patch.object(
            tcb, "MAX_EXECUTABLE_FILE_BYTES", 16
        ), mock.patch.object(tcb, "MAX_EXECUTABLE_TOTAL_BYTES", 64):
            result = self._verify(
                documents, payloads={"roles": role_payloads}
            )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["executable_files"], 4)

        over_documents = copy.deepcopy(documents)
        interpreter_sha256 = hashlib.sha256(
            AUXILIARY_PAYLOADS[INTERPRETER_PATH]
        ).hexdigest()
        for state_name in ("admitted_state", "observed_state"):
            interpreter = over_documents["envelope"][state_name]["interpreter"]
            interpreter["executable_path"] = INTERPRETER_PATH
            interpreter["executable_sha256"] = interpreter_sha256
            for import_index in (0, 3):
                over_documents["envelope"][state_name]["imports"][import_index][
                    "sha256"
                ] = interpreter_sha256
        with mock.patch.object(
            tcb, "MAX_EXECUTABLE_FILE_BYTES", 16
        ), mock.patch.object(tcb, "MAX_EXECUTABLE_TOTAL_BYTES", 64):
            result = self._verify(
                over_documents, payloads={"roles": role_payloads}
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
            for index in range(tcb.MAX_IMPORT_ENTRIES - 4)
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
                tcb._validate_native_dependencies(value, -1, {}, 0)
        _assert_controlled_error(
            self, raised, "NATIVE_DEPENDENCY_POLICY_INVALID"
        )
        verify_identity.assert_not_called()


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
            for name in ("manifest.json", "acceptance.json", "envelope.json"):
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
        signature_names = tuple(tcb.verify_paths.__code__.co_varnames[:5])
        self.assertEqual(
            signature_names,
            (
                "contract_path",
                "manifest_path",
                "acceptance_path",
                "envelope_path",
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
            (),
            ("fixture",),
            ("materialize",),
            ("report",),
            ("verify",),
            ("verify", marker, marker, marker, marker),
            ("verify", marker, marker, marker, marker, marker, marker),
        )
        for arguments in argument_sets:
            with self.subTest(arguments=arguments[:1], count=len(arguments)):
                result = self._assert_closed_failure(
                    self._run(*arguments), marker
                )
                self.assertEqual(result["codes"], ["CLI_ARGUMENTS_INVALID"])

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
                for name in ("manifest.json", "acceptance.json", "envelope.json"):
                    _write_relative(root, name, b"{}")
                completed = self._run(
                    "verify",
                    "contract.json",
                    "manifest.json",
                    "acceptance.json",
                    "envelope.json",
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
