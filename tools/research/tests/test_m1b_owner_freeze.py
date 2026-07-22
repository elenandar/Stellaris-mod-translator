"""Synthetic-only tests for the external M1B owner-freeze verifier."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools.research import m1b_contract
from tools.research import m1b_owner_freeze as freeze


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = REPOSITORY_ROOT / "registry" / "m1b" / "owner-freeze-v7-g108.json"
DECISION = REPOSITORY_ROOT / "docs" / "decisions" / "M1B-0F-owner-freeze.json"
CASES = REPOSITORY_ROOT / "fixtures" / "m1b" / "owner-freeze" / "cases.json"
LEGACY_FIXTURE = REPOSITORY_ROOT / "fixtures" / "m1b" / "contract-cases.json"
VERIFIER = REPOSITORY_ROOT / "tools" / "research" / "m1b_owner_freeze.py"

EXPECTED_CASE_COUNT = 25
EXPECTED_CASES_SHA256 = (
    "ff1e153b87a49cabb6871b9db835b07c829465857c5e5b9ed8a892394eeea96c"
)
EXPECTED_REGISTRY_SNAPSHOT_SHA256 = (
    "df84871be332ee52c315d0c0cc1a7a0046251352a2a0131382b5cb994cffcb58"
)
EXPECTED_LEGACY_BUNDLE_SHA256 = (
    "50f51b3cf9be042ebc310d1a6c57791dd31a43362778798455d7ea9678c31e06"
)
EXPECTED_LEGACY_FIXTURE_SHA256 = (
    "ec2f958ce90fd5e97036b3658ae0a5a3f946aebe75c83b02b6998c3639133cb2"
)


def _encode(value):
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _resolve(value, path):
    current = value
    for component in path:
        current = current[component]
    return current


def _parent(value, path):
    if not path:
        return None, None
    return _resolve(value, path[:-1]), path[-1]


def _apply_case(snapshot, decision, case):
    roots = {
        "registry_snapshot": copy.deepcopy(snapshot),
        "owner_decision": copy.deepcopy(decision),
    }
    for patch in case["patches"]:
        target_name = patch["target"]
        operation = patch["operation"]
        path = patch["path"]
        if operation == "replace":
            if path:
                raise AssertionError("replace is root-only")
            roots[target_name] = copy.deepcopy(patch["value"])
            continue
        target = roots[target_name]
        if operation == "reverse":
            selected = _resolve(target, path)
            selected.reverse()
            continue
        if operation == "append":
            _resolve(target, path).append(copy.deepcopy(patch["value"]))
            continue
        parent, leaf = _parent(target, path)
        if operation == "set":
            parent[leaf] = copy.deepcopy(patch["value"])
        elif operation == "delete":
            del parent[leaf]
        elif operation == "copy":
            parent[leaf] = copy.deepcopy(_resolve(target, patch["source_path"]))
        else:
            raise AssertionError("unknown fixture operation")
    return roots["registry_snapshot"], roots["owner_decision"]


def _independent_ascii_frame(value):
    encoded = value.encode("ascii", errors="strict")
    return len(encoded).to_bytes(4, "big") + encoded


def _independent_registry_digest(snapshot):
    framed = [
        b"stellaris-m1b-owner-freeze-registry-snapshot-v1\x00",
        _independent_ascii_frame(snapshot["schema_version"]),
        _independent_ascii_frame(snapshot["framing"]),
        _independent_ascii_frame(snapshot["protocol_version"]),
        snapshot["protocol_generation"].to_bytes(8, "big"),
        bytes.fromhex(snapshot["definition_bundle_sha256"]),
        _independent_ascii_frame(snapshot["acceptance_state"]),
        len(snapshot["components"]).to_bytes(4, "big"),
    ]
    for row in snapshot["components"]:
        framed.extend(
            (
                _independent_ascii_frame(row["kind"]),
                _independent_ascii_frame(row["version"]),
                row["generation"].to_bytes(8, "big"),
                bytes.fromhex(row["component_sha256"]),
            )
        )
    return hashlib.sha256(b"".join(framed)).hexdigest()


def _independent_legacy_bundle_digest(rows):
    prepared = []
    for row in rows:
        kind = row["kind"].encode("ascii")
        version = row["version"].encode("ascii")
        prepared.append((kind, version, bytes.fromhex(row["component_sha256"])))
    framed = [
        b"stellaris-m1b-bundle-v1\x00",
        len(prepared).to_bytes(4, "big"),
    ]
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


class OwnerFreezeFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot_bytes = SNAPSHOT.read_bytes()
        cls.decision_bytes = DECISION.read_bytes()
        cls.cases_bytes = CASES.read_bytes()
        cls.snapshot = freeze.parse_json_bytes(cls.snapshot_bytes)
        cls.decision = freeze.parse_json_bytes(cls.decision_bytes)
        cls.manifest = freeze.parse_json_bytes(cls.cases_bytes)

    def test_fixture_identity_and_required_matrix(self):
        self.assertEqual(
            hashlib.sha256(self.cases_bytes).hexdigest(), EXPECTED_CASES_SHA256
        )
        self.assertEqual(self.manifest["fixture_schema"], "m1b-owner-freeze-cases-v1")
        self.assertEqual(len(self.manifest["cases"]), EXPECTED_CASE_COUNT)
        ids = [case["id"] for case in self.manifest["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(
            set(ids),
            {
                "acceptance-state-drift-old-bundle-unchanged",
                "bool-instead-of-generation",
                "component-addition",
                "component-duplication",
                "component-generation-drift-old-bundle-unchanged",
                "component-hash-mutation",
                "component-missing-field",
                "component-removal",
                "component-unknown-field",
                "fake-acceptance-inside-benchmark-report",
                "fake-acceptance-inside-fixture",
                "integer-instead-of-authorization-boolean",
                "owner-record-blocker-removal",
                "owner-record-gate-drift",
                "owner-record-missing-field",
                "owner-record-snapshot-digest-mismatch",
                "owner-record-unknown-field",
                "positive-exact",
                "reordered-components",
                "snapshot-missing-field",
                "snapshot-self-hash-circular-trust-attempt",
                "snapshot-unknown-field",
                "stale-protocol-generation",
                "stale-protocol-version",
                "wrong-definition-bundle-hash",
            },
        )

    def test_all_table_cases_return_exact_controlled_result(self):
        for case in self.manifest["cases"]:
            with self.subTest(case=case["id"]):
                snapshot, decision = _apply_case(self.snapshot, self.decision, case)
                result = freeze.verify_bytes(_encode(snapshot), _encode(decision))
                self.assertEqual(result["status"], case["expected"]["status"])
                self.assertEqual(result["codes"], case["expected"]["codes"])
                self.assertEqual(set(result), {"codes", "counts", "status"})
                self.assertEqual(
                    set(result["counts"]),
                    {"component_identities", "owner_records"},
                )

    def test_independent_new_and_legacy_digest_vectors(self):
        self.assertEqual(
            _independent_registry_digest(self.snapshot),
            EXPECTED_REGISTRY_SNAPSHOT_SHA256,
        )
        self.assertEqual(
            _independent_legacy_bundle_digest(self.snapshot["components"]),
            EXPECTED_LEGACY_BUNDLE_SHA256,
        )
        self.assertEqual(
            self.decision["registry_snapshot_sha256"],
            EXPECTED_REGISTRY_SNAPSHOT_SHA256,
        )

    def test_acceptance_generation_and_order_change_the_new_digest(self):
        state_drift = copy.deepcopy(self.snapshot)
        state_drift["acceptance_state"] = "proposed"
        self.assertEqual(
            _independent_registry_digest(state_drift),
            "6ed10eec8df8a0601f2f0db7e4cbeae2451a1e2700da25b01da46d79fdbc1d3c",
        )
        generation_drift = copy.deepcopy(self.snapshot)
        generation_drift["components"][1]["generation"] = 107
        self.assertEqual(
            _independent_registry_digest(generation_drift),
            "c01fe1089834734f2f6103890aa1bbbfc86e809412988a8abe9d186595cc7cc2",
        )
        reordered = copy.deepcopy(self.snapshot)
        reordered["components"].reverse()
        self.assertEqual(
            _independent_registry_digest(reordered),
            "6b7d6b90cb16f482354dbbced154ac0a694cd932ac24955765edb37944bf6583",
        )

    def test_historical_registry_and_fixture_remain_proposed_evidence_only(self):
        legacy_bytes = LEGACY_FIXTURE.read_bytes()
        legacy = m1b_contract.parse_json_bytes(legacy_bytes)
        self.assertEqual(
            hashlib.sha256(legacy_bytes).hexdigest(),
            EXPECTED_LEGACY_FIXTURE_SHA256,
        )
        self.assertEqual(len(legacy["cases"]), 173)
        presented = legacy["base_document"]["definition_bundle"]["components"]
        self.assertEqual({row["acceptance_state"] for row in presented}, {"proposed"})
        trusted = tuple(
            sorted(
                (
                    row["kind"],
                    row["version"],
                    row["generation"],
                    row["sha256"],
                )
                for row in m1b_contract.TRUSTED_COMPONENTS
            )
        )
        owner_rows = tuple(
            (
                row["kind"],
                row["version"],
                row["generation"],
                row["component_sha256"],
            )
            for row in self.snapshot["components"]
        )
        self.assertEqual(trusted, owner_rows)
        self.assertEqual(
            {row["acceptance_state"] for row in m1b_contract.TRUSTED_COMPONENTS},
            {"proposed"},
        )

    def test_records_and_fixture_contain_no_raw_or_path_payload_fields(self):
        forbidden_fields = {
            "annotation",
            "content",
            "corpus_hash",
            "filename",
            "input",
            "model_output",
            "output",
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

        for value in (self.snapshot, self.decision, self.manifest):
            visit(value)
        for case in self.manifest["cases"]:
            for patch in case["patches"]:
                for component in patch["path"]:
                    if type(component) is str:
                        self.assertNotIn("/", component)
                        self.assertNotIn("\\", component)
        serialized = self.snapshot_bytes + self.decision_bytes + self.cases_bytes
        for marker in (b"/Users/", b"l_russian:", b"localisation/", b"file://"):
            self.assertNotIn(marker, serialized)


class StrictJsonAndBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = SNAPSHOT.read_bytes()
        cls.decision = DECISION.read_bytes()

    def test_duplicate_keys_malformed_utf8_and_oversize_are_controlled(self):
        cases = (
            (
                b'{"schema_version":"first","schema_version":"second"}',
                self.decision,
                "JSON_DUPLICATE_KEY",
            ),
            (b"\xffSYNTHETIC_INVALID_UTF8", self.decision, "UTF8_INVALID"),
            (b" " * (freeze.MAX_INPUT_BYTES + 1), self.decision, "INPUT_SIZE_LIMIT"),
            (
                self.snapshot,
                b'{"owner_decision_schema":"first","owner_decision_schema":"second"}',
                "JSON_DUPLICATE_KEY",
            ),
            (self.snapshot, b"\xffSYNTHETIC_INVALID_UTF8", "UTF8_INVALID"),
            (self.snapshot, b" " * (freeze.MAX_INPUT_BYTES + 1), "INPUT_SIZE_LIMIT"),
        )
        for snapshot, decision, code in cases:
            with self.subTest(code=code, decision_invalid=decision is not self.decision):
                result = freeze.verify_bytes(snapshot, decision)
                self.assertEqual(result["codes"], [code])
                self.assertEqual(result["counts"], {"component_identities": 0, "owner_records": 0})

    def test_float_nonfinite_surrogate_and_huge_integer_are_controlled(self):
        cases = (
            (b'{"protocol_generation":1.0}', "JSON_FLOAT_FORBIDDEN"),
            (b'{"protocol_generation":NaN}', "JSON_MALFORMED"),
            (b'{"schema_version":"\\ud800"}', "JSON_UNICODE_INVALID"),
            (b'{"protocol_generation":9223372036854775808}', "JSON_INTEGER_OUT_OF_RANGE"),
        )
        for snapshot, code in cases:
            with self.subTest(code=code):
                self.assertEqual(
                    freeze.verify_bytes(snapshot, self.decision)["codes"], [code]
                )

    def test_unexpected_exception_text_is_discarded(self):
        marker = "SYNTHETIC_EXCEPTION_CONTENT_MUST_NOT_ESCAPE"
        with mock.patch.object(
            freeze,
            "validate_registry_snapshot",
            side_effect=RuntimeError(marker),
        ):
            result = freeze.verify_bytes(self.snapshot, self.decision)
        self.assertEqual(result["codes"], ["UNEXPECTED_FAILURE"])
        self.assertNotIn(marker, json.dumps(result))

    def test_authorization_fields_require_exact_json_booleans(self):
        snapshot = json.loads(SNAPSHOT.read_text("utf-8"))
        decision = json.loads(DECISION.read_text("utf-8"))
        for field in (
            "complete_benchmark_authorized",
            "model_calls_authorized",
            "private_corpus_authorized",
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(decision)
                changed[field] = 0
                result = freeze.verify_bytes(_encode(snapshot), _encode(changed))
                self.assertEqual(result["codes"], ["OWNER_DECISION_MISMATCH"])

    def test_verifier_imports_no_network_process_or_discovery_clients(self):
        tree = ast.parse(VERIFIER.read_text("utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            imported.isdisjoint(
                {
                    "http",
                    "pathlib",
                    "requests",
                    "socket",
                    "subprocess",
                    "urllib",
                }
            )
        )
        source = VERIFIER.read_text("utf-8")
        for forbidden in (
            "expanduser(",
            "getenv(",
            "glob(",
            "listdir(",
            "os.environ",
            "scandir(",
            "walk(",
        ):
            self.assertNotIn(forbidden, source)

    def test_fail_closed_validation_precedence_is_stable(self):
        snapshot = json.loads(SNAPSHOT.read_text("utf-8"))
        snapshot["registry_snapshot_sha256"] = "b" * 64
        snapshot["protocol_version"] = "m1b-benchmark-contract-v6"
        result = freeze.verify_bytes(_encode(snapshot), DECISION.read_bytes())
        self.assertEqual(result["codes"], ["REGISTRY_SNAPSHOT_SELF_HASH_FORBIDDEN"])

        snapshot = json.loads(SNAPSHOT.read_text("utf-8"))
        snapshot["protocol_version"] = "m1b-benchmark-contract-v6"
        snapshot["definition_bundle_sha256"] = "f" * 64
        result = freeze.verify_bytes(_encode(snapshot), DECISION.read_bytes())
        self.assertEqual(result["codes"], ["PROTOCOL_VERSION_MISMATCH"])


class OfflineCliBoundaryTests(unittest.TestCase):
    def _run(self, *arguments):
        return subprocess.run(
            [sys.executable, str(VERIFIER), *arguments],
            cwd=REPOSITORY_ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )

    def test_positive_cli_is_compact_stderr_free_and_explicit(self):
        completed = self._run("verify", str(SNAPSHOT), str(DECISION))
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, b"")
        self.assertEqual(
            completed.stdout,
            b'{"codes":[],"counts":{"component_identities":17,"owner_records":1},"status":"ok"}\n',
        )

    def test_bad_arguments_and_missing_paths_are_not_echoed(self):
        marker = "SYNTHETIC_MISSING_RECORD_PATH_MARKER"
        cases = (
            ((), "CLI_ARGUMENTS_INVALID"),
            (("verify", marker, marker + "-decision"), "INPUT_READ_FAILED"),
        )
        for arguments, expected_code in cases:
            with self.subTest(arguments=len(arguments), code=expected_code):
                completed = self._run(*arguments)
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stderr, b"")
                combined = completed.stdout + completed.stderr
                self.assertNotIn(marker.encode("ascii"), combined)
                result = json.loads(completed.stdout)
                self.assertEqual(set(result), {"codes", "counts", "status"})
                self.assertEqual(result["codes"], [expected_code])

    def test_invalid_file_bytes_and_symlink_target_are_not_echoed(self):
        marker = "SYNTHETIC_PRIVATE_RECORD_MARKER"
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            invalid = directory / (marker + ".json")
            invalid.write_bytes(b"\xff" + marker.encode("ascii"))
            symlink = directory / (marker + "-link.json")
            symlink.symlink_to(SNAPSHOT)
            fifo = directory / (marker + "-fifo.json")
            os.mkfifo(fifo)
            for snapshot_path in (invalid, symlink, fifo):
                with self.subTest(kind=snapshot_path.name.rsplit("-", 1)[-1]):
                    completed = self._run("verify", str(snapshot_path), str(DECISION))
                    self.assertEqual(completed.returncode, 2)
                    self.assertEqual(completed.stderr, b"")
                    self.assertNotIn(
                        marker.encode("ascii"), completed.stdout + completed.stderr
                    )
                    self.assertEqual(json.loads(completed.stdout)["status"], "error")

    def test_invalid_or_missing_decision_is_not_echoed_after_valid_snapshot(self):
        marker = "SYNTHETIC_OWNER_DECISION_MARKER"
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            invalid = directory / (marker + ".json")
            invalid.write_bytes(b"\xff" + marker.encode("ascii"))
            missing = directory / (marker + "-missing.json")
            cases = ((invalid, "UTF8_INVALID"), (missing, "INPUT_READ_FAILED"))
            for decision_path, expected_code in cases:
                with self.subTest(code=expected_code):
                    completed = self._run("verify", str(SNAPSHOT), str(decision_path))
                    self.assertEqual(completed.returncode, 2)
                    self.assertEqual(completed.stderr, b"")
                    self.assertNotIn(
                        marker.encode("ascii"), completed.stdout + completed.stderr
                    )
                    self.assertEqual(
                        json.loads(completed.stdout)["codes"], [expected_code]
                    )


if __name__ == "__main__":
    unittest.main()
