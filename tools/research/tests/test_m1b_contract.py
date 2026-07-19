from __future__ import annotations

import ast
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools.research import m1b_contract as contract


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = REPOSITORY_ROOT / "fixtures" / "m1b" / "contract-cases.json"
README = REPOSITORY_ROOT / "fixtures" / "m1b" / "README.md"


class SyntheticContractCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_bytes = FIXTURE.read_bytes()
        cls.manifest = contract.parse_json_bytes(cls.fixture_bytes)
        cls.cases = cls.manifest["cases"]

    def test_all_table_cases_return_exact_controlled_code(self) -> None:
        self.assertEqual(len(self.cases), 59)
        self.assertEqual(
            sum(case["expected"]["status"] == "error" for case in self.cases),
            58,
        )
        for case in self.cases:
            with self.subTest(case=case["id"]):
                actual = contract.validate_fixture_case(self.manifest, case["id"])
                self.assertEqual(actual["status"], case["expected"]["status"])
                self.assertEqual(actual["codes"], case["expected"]["codes"])
                self.assertEqual(set(actual), {"codes", "counts", "status"})
                self.assertEqual(set(actual["counts"]), set(contract._COUNT_KEYS))
                if actual["status"] == "error":
                    self.assertTrue(all(value == 0 for value in actual["counts"].values()))

    def test_required_adversarial_families_are_fixture_backed(self) -> None:
        case_ids = {case["id"] for case in self.cases}
        required = {
            "accepted-critical-human-finding",
            "api-base-path-trailing-slash",
            "atom-extra",
            "atom-missing",
            "atom-mutation",
            "auto-pull-enabled",
            "boolean-integer",
            "candidate-profile-version-mismatch",
            "candidate-runtime-mismatch",
            "cloud-model-ref",
            "cloud-tag",
            "content-derived-private-corpus-hash",
            "corpus-generation-mismatch",
            "critical-review-count-insufficient",
            "duplicate-json-key",
            "duplicate-opaque-id",
            "fallback-enabled",
            "loopback-hostname-endpoint",
            "malformed-full-digest",
            "malformed-uuid",
            "missing-api-base-path",
            "missing-document-schema-version",
            "missing-output-schema-version",
            "missing-profile-version",
            "missing-prompt-version",
            "model-review-counted-as-human",
            "non-loopback-endpoint",
            "non-synthetic-atom",
            "prefixed-full-digest",
            "premature-baseline",
            "premature-m1b-verdict",
            "premature-winner",
            "profile-generation-mismatch",
            "protocol-generation-mismatch",
            "proxy-routing-enabled",
            "raw-annotation-field",
            "raw-filename-field",
            "raw-input-field",
            "raw-output-field",
            "raw-path-field",
            "raw-prompt-field",
            "raw-text-field",
            "raw-translation-field",
            "redirects-enabled",
            "result-dimension-duplicate",
            "result-dimension-missing",
            "result-dimension-unknown",
            "same-critical-reviewer-twice",
            "tuning-holdout-overlap",
            "unknown-category",
            "unknown-dimension",
            "unknown-reviewer-role",
            "unknown-severity",
            "unknown-split",
        }
        self.assertTrue(required <= case_ids, sorted(required - case_ids))

    def test_positive_contract_proves_equal_unranked_candidate_profiles(self) -> None:
        base = self.manifest["base_document"]
        candidates = base["candidate_profiles"]
        self.assertEqual(
            {candidate["candidate"] for candidate in candidates},
            contract.EXPECTED_CANDIDATES,
        )
        self.assertEqual(len(candidates), 3)
        self.assertEqual(
            {candidate["profile_version"] for candidate in candidates},
            {"m1b-primary-common-profile-v1"},
        )
        self.assertEqual(
            {candidate["selection_status"] for candidate in candidates},
            {"unranked_candidate"},
        )
        self.assertTrue(
            all(candidate["runtime"] == candidates[0]["runtime"] for candidate in candidates)
        )
        self.assertEqual(
            {candidate["thinking_profile"]["mode"] for candidate in candidates},
            {"not_probed"},
        )
        self.assertEqual(
            {candidate["thinking_profile"]["exception_status"] for candidate in candidates},
            {"none"},
        )

    def test_positive_contract_uses_placeholder_full_digest_shape_only(self) -> None:
        digests = [
            candidate["model_digest"]
            for candidate in self.manifest["base_document"]["candidate_profiles"]
        ]
        self.assertEqual(len(set(digests)), 3)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", value) for value in digests))
        self.assertTrue(all(value == value[0] * 64 for value in digests))
        self.assertNotIn("sha256:", "".join(digests))

    def test_positive_contract_proves_split_and_atom_invariants(self) -> None:
        base = self.manifest["base_document"]
        tuning = set(base["corpus"]["splits"]["tuning"])
        holdout = set(base["corpus"]["splits"]["holdout"])
        self.assertTrue(tuning)
        self.assertTrue(holdout)
        self.assertFalse(tuning & holdout)
        atoms = [
            atom
            for sample in base["corpus"]["samples"]
            for atom in sample["expected_atoms"]
        ]
        self.assertTrue(atoms)
        self.assertEqual({atom["provenance"] for atom in atoms}, {"synthetic"})
        dimension_records = base["conformance_results"][0]["dimension_records"]
        self.assertEqual(
            {record["dimension"] for record in dimension_records},
            contract.QUALITY_DIMENSIONS,
        )
        self.assertEqual(len(dimension_records), len(contract.QUALITY_DIMENSIONS))
        self.assertEqual(
            {
                record["dimension"]: record["status"]
                for record in dimension_records
            },
            {
                "context_voice_style": "not_evaluated",
                "literary_russian": "not_evaluated",
                "meaning_accuracy": "not_evaluated",
                "schema_atom_stability": "synthetic_conformant",
                "terminology_lore": "not_evaluated",
            },
        )
        result = contract.validate_fixture_case(self.manifest, "positive")
        self.assertEqual(
            result,
            {
                "codes": [],
                "counts": {
                    "candidates": 3,
                    "findings": 1,
                    "holdout_samples": 1,
                    "results": 1,
                    "reviews": 2,
                    "samples": 2,
                    "tuning_samples": 1,
                },
                "status": "ok",
            },
        )

    def test_positive_report_is_redacted_independent_and_fully_accounted(self) -> None:
        base = self.manifest["base_document"]
        report = base["aggregate_report"]
        self.assertEqual(report["redaction"], "controlled_aggregates_only")
        self.assertEqual(set(report["quality_dimensions"]), contract.QUALITY_DIMENSIONS)
        for field in (
            "cold_latency_observation_count",
            "warm_latency_observation_count",
            "memory_observation_count",
            "repair_attempt_count",
            "repair_success_count",
            "repair_failure_count",
            "fallback_attempt_count",
            "human_fallback_count",
            "model_fallback_count",
            "terminal_rejection_count",
        ):
            self.assertIn(field, report)
            self.assertIs(type(report[field]), int)
        self.assertEqual(base["benchmark_state"], {"complete": False})

    def test_positive_critical_finding_has_two_distinct_human_reviewers(self) -> None:
        finding = self.manifest["base_document"]["findings"][0]
        reviews = finding["reviews"]
        self.assertEqual(finding["severity"], "critical")
        self.assertEqual({review["reviewer_role"] for review in reviews}, {"human_reviewer"})
        self.assertEqual({review["review_credit"] for review in reviews}, {"human"})
        self.assertEqual(len({review["reviewer_id"] for review in reviews}), 2)

    def test_fixture_contains_no_private_or_raw_payload_values(self) -> None:
        serialized = self.fixture_bytes.decode("utf-8")
        for forbidden in (
            "/Users/",
            "/home/",
            "file://",
            "PRIVATE_SYNTHETIC_CONTENT",
            "copyrighted excerpt",
        ):
            self.assertNotIn(forbidden, serialized)
        for case in self.cases:
            if not case["id"].startswith("raw-") and case["id"] != "content-derived-private-corpus-hash":
                continue
            self.assertEqual(len(case["patches"]), 1)
            self.assertIsNone(case["patches"][0]["value"])

    def test_ipv4_and_ipv6_exact_api_endpoints_are_accepted(self) -> None:
        for endpoint in (
            "http://127.0.0.1:11434/api",
            "http://[::1]:11434/api",
        ):
            with self.subTest(endpoint=endpoint):
                document = copy.deepcopy(self.manifest["base_document"])
                document["provider_policy"]["endpoint"] = endpoint
                counts = contract.validate_document(document)
                self.assertEqual(counts["candidates"], 3)

    def test_thinking_difference_requires_explicit_preregistration(self) -> None:
        document = copy.deepcopy(self.manifest["base_document"])
        for index, mode in enumerate(("enabled", "low", "high")):
            thinking = document["candidate_profiles"][index]["thinking_profile"]
            thinking["mode"] = mode
            thinking["exception_status"] = "preregistered"
            thinking["exception_version"] = "m1b-thinking-exception-v1"
        counts = contract.validate_document(document)
        self.assertEqual(counts["candidates"], 3)


class StrictJsonAndSchemaTests(unittest.TestCase):
    def test_duplicate_object_keys_are_rejected_before_schema_validation(self) -> None:
        result = contract.validate_json_bytes(b'{"a":1,"a":2}')
        self.assertEqual(result["codes"], ["JSON_DUPLICATE_KEY"])

    def test_invalid_utf8_is_controlled(self) -> None:
        result = contract.validate_json_bytes(b'{"schema_version":"\xff"}')
        self.assertEqual(result["codes"], ["UTF8_INVALID"])

    def test_malformed_and_nonfinite_json_are_controlled(self) -> None:
        cases = (
            (b"{", "JSON_MALFORMED"),
            (b'{"value":NaN}', "JSON_MALFORMED"),
            (b'{"value":Infinity}', "JSON_MALFORMED"),
            (b'{"value":-Infinity}', "JSON_MALFORMED"),
        )
        for payload, code in cases:
            with self.subTest(code=code, payload=payload):
                self.assertEqual(contract.validate_json_bytes(payload)["codes"], [code])

    def test_escaped_surrogate_is_not_a_valid_unicode_scalar(self) -> None:
        result = contract.validate_json_bytes(b'{"value":"\\ud800"}')
        self.assertEqual(result["codes"], ["JSON_UNICODE_INVALID"])

    def test_bool_is_not_accepted_as_integer(self) -> None:
        manifest = contract.parse_json_bytes(FIXTURE.read_bytes())
        result = contract.validate_fixture_case(manifest, "boolean-integer")
        self.assertEqual(result["codes"], ["INVALID_TYPE"])

    def test_manifest_and_document_objects_have_closed_field_sets(self) -> None:
        manifest = contract.parse_json_bytes(FIXTURE.read_bytes())
        self.assertEqual(
            contract.validate_fixture_case(manifest, "unknown-additional-field")["codes"],
            ["UNKNOWN_FIELD"],
        )
        malformed = copy.deepcopy(manifest)
        malformed["extra"] = None
        with self.assertRaises(contract.ContractError) as raised:
            contract.materialize_fixture_case(malformed, "positive")
        self.assertEqual(raised.exception.code, "UNKNOWN_FIELD")

    def test_all_public_failure_codes_are_controlled_identifiers(self) -> None:
        manifest = contract.parse_json_bytes(FIXTURE.read_bytes())
        for case in manifest["cases"]:
            result = contract.validate_fixture_case(manifest, case["id"])
            for code in result["codes"]:
                self.assertRegex(code, r"^[A-Z][A-Z0-9_]*$")


class OfflineCliBoundaryTests(unittest.TestCase):
    def _run(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(REPOSITORY_ROOT / "tools" / "research" / "m1b_contract.py"), *arguments],
            cwd=str(REPOSITORY_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_positive_fixture_cli_is_compact_and_stderr_free(self) -> None:
        completed = self._run("validate-case", str(FIXTURE), "positive")
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, b"")
        self.assertEqual(completed.stdout.count(b"\n"), 1)
        payload = json.loads(completed.stdout.decode("ascii"))
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["codes"], [])
        self.assertNotIn(b"positive", completed.stdout)
        self.assertNotIn(os.fsencode(str(FIXTURE)), completed.stdout)

    def test_explicit_standalone_document_cli_is_supported(self) -> None:
        manifest = contract.parse_json_bytes(FIXTURE.read_bytes())
        document_bytes = contract.materialize_fixture_case(manifest, "positive")
        with tempfile.TemporaryDirectory() as temporary:
            input_file = Path(temporary) / "synthetic-contract.json"
            input_file.write_bytes(document_bytes)
            completed = self._run("validate", str(input_file))
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, b"")
        self.assertEqual(json.loads(completed.stdout)["status"], "ok")

    def test_missing_input_never_echoes_filename_path_or_exception(self) -> None:
        marker = "SENSITIVE_SYNTHETIC_FILENAME_MARKER"
        completed = self._run("validate", marker)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stderr, b"")
        self.assertNotIn(marker.encode("ascii"), completed.stdout)
        self.assertEqual(
            json.loads(completed.stdout)["codes"],
            ["INPUT_READ_FAILED"],
        )

    def test_invalid_utf8_cli_never_echoes_input_path_or_bytes(self) -> None:
        marker = "SENSITIVE_SYNTHETIC_UTF8_MARKER"
        with tempfile.TemporaryDirectory() as temporary:
            input_file = Path(temporary) / marker
            input_file.write_bytes(b"\xffPRIVATE_SYNTHETIC_BYTE_MARKER")
            completed = self._run("validate", str(input_file))
            encoded_path = os.fsencode(str(input_file))
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stderr, b"")
        self.assertNotIn(encoded_path, completed.stdout)
        self.assertNotIn(marker.encode("ascii"), completed.stdout)
        self.assertNotIn(b"PRIVATE_SYNTHETIC_BYTE_MARKER", completed.stdout)
        self.assertEqual(json.loads(completed.stdout)["codes"], ["UTF8_INVALID"])

    def test_bad_arguments_are_controlled_and_not_echoed(self) -> None:
        marker = "SENSITIVE_SYNTHETIC_ARGUMENT_MARKER"
        completed = self._run("unsupported", marker)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stderr, b"")
        self.assertNotIn(marker.encode("ascii"), completed.stdout)
        self.assertEqual(json.loads(completed.stdout)["codes"], ["CLI_ARGUMENTS_INVALID"])

    def test_unexpected_exception_text_is_discarded(self) -> None:
        marker = "PRIVATE_SYNTHETIC_EXCEPTION_MARKER"
        with mock.patch.object(contract, "_read_explicit_file", side_effect=RuntimeError(marker)):
            result = contract._execute(("validate", "synthetic"))
        encoded = contract._encode_result(result)
        self.assertNotIn(marker.encode("ascii"), encoded)
        self.assertEqual(json.loads(encoded)["codes"], ["UNEXPECTED_FAILURE"])

    def test_input_size_limit_is_controlled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            input_file = Path(temporary) / "synthetic-oversize.json"
            input_file.write_bytes(b"0" * (contract.MAX_INPUT_BYTES + 1))
            completed = self._run("validate", str(input_file))
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stderr, b"")
        self.assertEqual(json.loads(completed.stdout)["codes"], ["INPUT_SIZE_LIMIT"])

    def test_validator_imports_no_network_process_or_discovery_modules(self) -> None:
        source_path = REPOSITORY_ROOT / "tools" / "research" / "m1b_contract.py"
        tree = ast.parse(source_path.read_text("utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertFalse(
            imported
            & {
                "http.client",
                "os",
                "pathlib",
                "requests",
                "socket",
                "subprocess",
                "urllib.request",
            }
        )
        source = source_path.read_text("utf-8")
        for forbidden_call in ("Path.home(", "expanduser(", "getenv(", "environ["):
            self.assertNotIn(forbidden_call, source)

    def test_validation_makes_no_network_call(self) -> None:
        manifest = contract.parse_json_bytes(FIXTURE.read_bytes())
        with mock.patch("socket.create_connection", side_effect=AssertionError), mock.patch(
            "urllib.request.urlopen", side_effect=AssertionError
        ):
            result = contract.validate_fixture_case(manifest, "positive")
        self.assertEqual(result["status"], "ok")


if __name__ == "__main__":
    unittest.main()
