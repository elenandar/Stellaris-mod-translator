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
EXPECTED_FIXTURE_CASES = 140
EXPECTED_BUNDLE_HASH = (
    "4bc9475737ab6fbc364b9c16b604ca9ea649bfc36077eadb01edfdbb0d4e0e40"
)


class SyntheticContractCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_bytes = FIXTURE.read_bytes()
        cls.manifest = contract.parse_json_bytes(cls.fixture_bytes)
        cls.cases = cls.manifest["cases"]
        cls.base = cls.manifest["base_document"]

    def test_all_table_cases_return_exact_controlled_code(self) -> None:
        self.assertEqual(len(self.cases), EXPECTED_FIXTURE_CASES)
        self.assertEqual(
            sum(case["expected"]["status"] == "error" for case in self.cases),
            EXPECTED_FIXTURE_CASES - 1,
        )
        for case in self.cases:
            with self.subTest(case=case["id"]):
                actual = contract.validate_fixture_case(self.manifest, case["id"])
                self.assertEqual(actual["status"], case["expected"]["status"])
                self.assertEqual(actual["codes"], case["expected"]["codes"])
                self.assertEqual(set(actual), {"codes", "counts", "status"})
                self.assertEqual(set(actual["counts"]), set(contract._COUNT_KEYS))
                if actual["status"] == "error":
                    self.assertTrue(
                        all(value == 0 for value in actual["counts"].values())
                    )

    def test_required_remediation_regressions_are_fixture_backed(self) -> None:
        case_ids = {case["id"] for case in self.cases}
        required = {
            # Human/editorial separation and identity.
            "editorial-approved-unevaluated",
            "editorial-approved-without-technical",
            "approved-high-no-reviews",
            "approved-mandatory-human-without-gate",
            "model-review-instead-of-human",
            "critical-review-count-insufficient",
            "same-critical-reviewer-twice",
            "reviewer-role-inconsistent",
            "reviewer-id-role-collision",
            "finding-dimension-mismatch",
            "holdout-ground-truth-missing",
            "model-ground-truth-not-human",
            "high-approved-after-repair",
            "critical-approved-after-fallback",
            "not-observed-without-terminal-failure",
            "terminal-failure-with-observed-atoms",
            "terminal-failure-accounting-mismatch",
            "success-without-model-call",
            "human-quality-without-output",
            "human-status-without-ground-truth",
            "human-ground-truth-without-output",
            # Exact typed atoms.
            "atom-value-mutation",
            "atom-position-reordered",
            "atom-multiplicity-mutation",
            "expected-atom-occurrence-index-duplicate",
            "coherent-expected-observed-atom-kind-drift",
            "coherent-expected-observed-atom-value-drift",
            "coherent-expected-observed-atom-position-drift",
            "atom-occurrence-duplicate",
            "atom-missing",
            "atom-extra",
            "atom-kind-mutation",
            # Trusted freeze registry and coherent drift.
            "definition-component-missing",
            "definition-component-duplicate",
            "definition-component-extra",
            "definition-kind-unknown",
            "definition-hash-malformed",
            "bundle-hash-malformed",
            "bundle-hash-mismatch",
            "definition-payload-drift",
            "definition-self-rehash-drift",
            "definition-generation-drift",
            "definition-state-self-accepted",
            "definition-version-drift",
            "protocol-version-drift",
            "prompt-version-drift",
            "output-schema-version-drift",
            "document-schema-version-drift",
            "all-candidate-runtime-drift",
            # Assignment, coverage, and accounting.
            "duplicate-assignment-new-result-id",
            "complete-missing-assignment",
            "extra-primary-assignment",
            "candidate-without-results",
            "phantom-repair-row",
            "phantom-fallback-row",
            "fallback-row-while-disabled",
            "model-fallback-while-disabled",
            "live-observation-not-probed",
            "accounting-count-exceeds-results",
            "retry-zero-hidden-attempt",
            "multiple-model-calls-without-retry",
            "repair-accounting-mismatch",
            "aggregate-count-mismatch",
            "aggregate-accounting-mismatch",
            "mixed-result-generation",
            "partial-report-claimed-complete",
            "narrative-auto-eligible-risk",
            # Endpoint and bounded parsing.
            "leading-lf-endpoint",
            "trailing-lf-endpoint",
            "inside-lf-endpoint",
            "inside-tab-endpoint",
            "crlf-endpoint",
            "unicode-whitespace-endpoint",
            "ascii-whitespace-endpoint",
            "port-zero-endpoint",
            "missing-port-endpoint",
            "out-of-range-port-endpoint",
            "oversize-json-integer",
            "json-float",
            # Privacy and premature gate claims.
            "raw-annotation-field",
            "raw-filename-field",
            "raw-input-field",
            "raw-output-field",
            "raw-path-field",
            "raw-prompt-field",
            "raw-text-field",
            "raw-translation-field",
            "content-derived-private-corpus-hash",
            "premature-winner",
            "premature-baseline",
            "premature-m1b-verdict",
        }
        self.assertTrue(required <= case_ids, sorted(required - case_ids))

    def test_positive_contract_uses_external_trusted_definition_registry(self) -> None:
        bundle = self.base["definition_bundle"]
        self.assertEqual(bundle["framing"], contract.COMPONENT_FRAMING)
        self.assertEqual(bundle["sha256"], EXPECTED_BUNDLE_HASH)
        self.assertEqual(bundle["sha256"], contract.TRUSTED_BUNDLE_HASH)
        self.assertEqual(len(bundle["components"]), 15)
        self.assertEqual(
            bundle["components"],
            [dict(component) for component in contract.TRUSTED_COMPONENTS],
        )
        self.assertEqual(
            {component["acceptance_state"] for component in bundle["components"]},
            {"proposed"},
        )

    def test_component_hash_has_a_fixed_public_vector(self) -> None:
        component = self.base["definition_bundle"]["components"][0]
        actual = contract.component_hash(
            component["kind"],
            component["version"],
            component["definition"].encode("ascii"),
        )
        self.assertEqual(
            actual,
            "6b55a57f4905db55972ae301daa080c5cc8b7c42e66e75c7249a6b8abf9147dc",
        )
        self.assertEqual(actual, component["sha256"])

    def test_trusted_definitions_cover_executable_semantics(self) -> None:
        definitions = {
            component["kind"]: json.loads(component["definition"])
            for component in self.base["definition_bundle"]["components"]
        }
        benchmark = definitions["benchmark_contract"]
        self.assertEqual(benchmark["root_fields"], list(contract._ROOT_FIELDS))
        self.assertEqual(
            benchmark["assignment_tuple"],
            [
                "candidate_id",
                "sample_id",
                "profile_version",
                "profile_generation",
                "experiment_lane",
                "attempt_stage",
                "attempt_index",
            ],
        )
        output = definitions["output_schema"]
        self.assertEqual(output["result_fields"], list(contract._RESULT_FIELDS))
        self.assertEqual(output["atom_fields"], list(contract._ATOM_FIELDS))
        self.assertEqual(
            output["accounting_fields"], list(contract._ACCOUNTING_FIELDS)
        )
        self.assertEqual(output["count_keys"], list(contract._COUNT_KEYS))
        generation = definitions["generation_policy"]
        self.assertEqual(
            generation["request_boundary"],
            contract._EXPECTED_REQUEST_BOUNDARY,
        )
        self.assertEqual(
            generation["provider_controls"],
            contract._EXPECTED_PROVIDER_CONTROLS,
        )
        corpus = definitions["corpus_policy"]
        self.assertEqual(
            corpus["synthetic_corpus_sha256"],
            contract.SYNTHETIC_CORPUS_SHA256,
        )
        for candidate in self.base["candidate_profiles"]:
            definition = definitions["candidate_profile." + candidate["candidate"]]
            self.assertEqual(
                definition["candidate_profile_fields"],
                list(contract._CANDIDATE_FIELDS),
            )
            self.assertEqual(definition["model_ref"], candidate["model_ref"])
            self.assertEqual(definition["model_digest"], candidate["model_digest"])
            self.assertEqual(definition["runtime"], candidate["runtime"])
            self.assertEqual(
                definition["thinking_profile"], candidate["thinking_profile"]
            )
        validator = definitions["validator_policy"]
        self.assertEqual(validator["max_input_bytes"], contract.MAX_INPUT_BYTES)
        self.assertEqual(validator["json_integer_min"], contract.MIN_JSON_INTEGER)
        self.assertEqual(validator["json_integer_max"], contract.MAX_JSON_INTEGER)
        analysis = definitions["analysis_policy"]
        self.assertEqual(analysis["minimum_n_per_required_stratum"], 36)
        self.assertEqual(analysis["minimum_overall_n"], 288)
        self.assertEqual(analysis["critical_false_accept_minimum_n"], 149)
        self.assertTrue(analysis["owner_decision_required"])
        retention = definitions["retention_leakage_policy"]
        self.assertEqual(
            retention["persistence_blocker"], "PROVIDER_PERSISTENCE_UNPROVEN"
        )
        self.assertEqual(retention["persistence_status"], "not_probed")
        blinding = definitions["randomization_blinding_policy"]
        self.assertEqual(blinding["unblinded_review"], "secondary_only")
        self.assertEqual(
            blinding["replacement_reviewers"], "never_unblinded_humans"
        )
        quality = definitions["quality_rubric"]
        self.assertTrue(quality["human_status_requires_ground_truth"])
        self.assertEqual(
            quality["missing_ground_truth_status"], "not_evaluated"
        )

    def test_bundle_hash_has_fixed_vector_and_deterministic_order(self) -> None:
        rows = [
            (component["kind"], component["version"], component["sha256"])
            for component in self.base["definition_bundle"]["components"]
        ]
        self.assertEqual(contract.bundle_hash(rows), EXPECTED_BUNDLE_HASH)
        self.assertEqual(contract.bundle_hash(list(reversed(rows))), EXPECTED_BUNDLE_HASH)

    def test_hash_helpers_reject_duplicate_and_malformed_records(self) -> None:
        row = ("benchmark_contract", "m1b-benchmark-contract-v1", "0" * 64)
        with self.assertRaises(contract.ContractError) as duplicate:
            contract.bundle_hash([row, row])
        self.assertEqual(duplicate.exception.code, "DEFINITION_COMPONENT_DUPLICATE")
        with self.assertRaises(contract.ContractError) as malformed:
            contract.bundle_hash([(row[0], row[1], "sha256:bad")])
        self.assertEqual(malformed.exception.code, "DEFINITION_HASH_INVALID")
        with self.assertRaises(contract.ContractError) as invalid_payload:
            contract.component_hash(row[0], row[1], "not-bytes")
        self.assertEqual(invalid_payload.exception.code, "INVALID_TYPE")

    def test_positive_contract_proves_equal_unranked_candidate_profiles(self) -> None:
        candidates = self.base["candidate_profiles"]
        self.assertEqual(
            {candidate["candidate"] for candidate in candidates},
            contract.EXPECTED_CANDIDATES,
        )
        self.assertEqual(len(candidates), 3)
        self.assertEqual(
            {candidate["profile_version"] for candidate in candidates},
            {contract.PROFILE_VERSION},
        )
        self.assertEqual(
            {candidate["profile_generation"] for candidate in candidates},
            {contract.PROFILE_GENERATION},
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

    def test_positive_contract_uses_placeholder_full_digest_shape_only(self) -> None:
        digests = [
            candidate["model_digest"] for candidate in self.base["candidate_profiles"]
        ]
        self.assertEqual(len(set(digests)), 3)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", value) for value in digests))
        self.assertTrue(all(value == value[0] * 64 for value in digests))
        self.assertNotIn("sha256:", "".join(digests))

    def test_positive_is_declared_partial_not_complete_benchmark(self) -> None:
        self.assertEqual(
            self.base["benchmark_state"],
            {"complete": False, "report_kind": "partial_synthetic_conformance"},
        )
        coverage = self.base["coverage"]
        self.assertEqual(coverage["declared_primary_assignment_count"], 3)
        self.assertEqual(coverage["required_primary_assignment_count"], 6)
        self.assertEqual(
            {row["primary_result_count"] for row in coverage["per_candidate"]},
            {1},
        )
        self.assertEqual(
            sum(row["primary_result_count"] for row in coverage["per_stratum"]),
            3,
        )

    def test_positive_exact_atoms_cover_value_position_and_multiplicity(self) -> None:
        sample = self.base["corpus"]["samples"][0]
        expected = sample["expected_atoms"]
        self.assertEqual(len(expected), 3)
        logical = [
            atom
            for atom in expected
            if atom["atom_id"] == "00000000-0000-4000-8000-000000000021"
        ]
        self.assertEqual(len(logical), 2)
        self.assertEqual({atom["occurrence_index"] for atom in logical}, {0, 1})
        self.assertEqual(len({atom["occurrence_id"] for atom in expected}), 3)
        self.assertEqual(
            {atom["position_policy"] for atom in expected},
            {"exact_utf8_byte_span"},
        )
        self.assertTrue(
            all(
                atom["position_end"] - atom["position_start"]
                == len(atom["synthetic_value"].encode("utf-8"))
                for atom in expected
            )
        )
        for result in self.base["conformance_results"]:
            self.assertEqual(result["observed_atoms"], expected)

    def test_positive_separates_technical_human_and_editorial_state(self) -> None:
        self.assertEqual(self.base["findings"], [])
        self.assertEqual(self.base["human_ground_truth"], [])
        for result in self.base["conformance_results"]:
            self.assertEqual(result["technical_conformance"], "synthetic_conformant")
            self.assertEqual(result["editorial_status"], "not_evaluated")
            dimensions = {
                row["dimension"]: row["status"]
                for row in result["dimension_records"]
            }
            self.assertEqual(
                dimensions,
                {
                    "schema_atom_stability": "synthetic_conformant",
                    "meaning_accuracy": "not_evaluated",
                    "terminology_lore": "not_evaluated",
                    "literary_russian": "not_evaluated",
                    "context_voice_style": "not_evaluated",
                },
            )

    def test_positive_report_is_redacted_zero_live_accounting(self) -> None:
        report = self.base["aggregate_report"]
        self.assertEqual(report["redaction"], "controlled_aggregates_only")
        self.assertEqual(set(report["quality_dimensions"]), contract.QUALITY_DIMENSIONS)
        for field in contract._ACCOUNTING_FIELDS:
            self.assertEqual(report[field], 0)
            self.assertTrue(
                all(result["accounting"][field] == 0 for result in self.base["conformance_results"])
            )
        self.assertEqual(self.base["provider_policy"]["residency_status"], "not_probed")
        self.assertEqual(self.base["provider_policy"]["persistence_status"], "not_probed")
        self.assertFalse(self.base["provider_policy"]["fallback"])
        self.assertEqual(report["human_ground_truth_count"], 0)

    def test_positive_result_has_exact_aggregate_counts(self) -> None:
        self.assertEqual(
            contract.validate_fixture_case(self.manifest, "positive"),
            {
                "codes": [],
                "counts": {
                    "candidates": 3,
                    "findings": 0,
                    "holdout_samples": 1,
                    "human_ground_truth": 0,
                    "results": 3,
                    "reviews": 0,
                    "samples": 2,
                    "tuning_samples": 1,
                },
                "status": "ok",
            },
        )

    def test_fixture_contains_no_private_or_raw_payload_values(self) -> None:
        serialized = self.fixture_bytes.decode("utf-8")
        for forbidden in (
            "/Users/",
            "/home/",
            "file://",
            "PRIVATE_SYNTHETIC_CONTENT",
            "copyrighted excerpt",
            "l_russian:",
        ):
            self.assertNotIn(forbidden, serialized)
        for case in self.cases:
            if not case["id"].startswith("raw-") and case["id"] != "content-derived-private-corpus-hash":
                continue
            self.assertEqual(len(case["patches"]), 1)
            self.assertIsNone(case["patches"][0]["value"])

    def test_ipv4_and_ipv6_exact_api_endpoints_are_accepted(self) -> None:
        for endpoint in (
            "http://127.0.0.1:1/api",
            "http://127.0.0.1:65535/api",
            "http://[::1]:11434/api",
        ):
            with self.subTest(endpoint=endpoint):
                document = copy.deepcopy(self.base)
                document["provider_policy"]["endpoint"] = endpoint
                counts = contract.validate_document(document)
                self.assertEqual(counts["candidates"], 3)


class StrictJsonAndSchemaTests(unittest.TestCase):
    def test_bounded_json_integer_accepts_signed_64_bit_boundaries(self) -> None:
        self.assertEqual(
            contract.parse_json_bytes(str(contract.MAX_JSON_INTEGER).encode("ascii")),
            contract.MAX_JSON_INTEGER,
        )
        self.assertEqual(
            contract.parse_json_bytes(str(contract.MIN_JSON_INTEGER).encode("ascii")),
            contract.MIN_JSON_INTEGER,
        )

    def test_bounded_json_integer_rejects_before_integer_conversion(self) -> None:
        tokens = (
            str(contract.MAX_JSON_INTEGER + 1),
            str(contract.MIN_JSON_INTEGER - 1),
            "9" * 80,
        )
        for token in tokens:
            with self.subTest(length=len(token), negative=token.startswith("-")):
                result = contract.validate_json_bytes(token.encode("ascii"))
                self.assertEqual(result["codes"], ["JSON_INTEGER_OUT_OF_RANGE"])
                self.assertNotIn(token, json.dumps(result, sort_keys=True))

    def test_floats_and_nonfinite_numbers_are_controlled(self) -> None:
        cases = (
            (b"1.0", "JSON_FLOAT_FORBIDDEN"),
            (b"1e3", "JSON_FLOAT_FORBIDDEN"),
            (b"NaN", "JSON_MALFORMED"),
            (b"Infinity", "JSON_MALFORMED"),
            (b"-Infinity", "JSON_MALFORMED"),
        )
        for payload, code in cases:
            with self.subTest(code=code, payload=payload):
                self.assertEqual(contract.validate_json_bytes(payload)["codes"], [code])

    def test_duplicate_object_keys_are_rejected_before_schema_validation(self) -> None:
        self.assertEqual(
            contract.validate_json_bytes(b'{"a":1,"a":2}')["codes"],
            ["JSON_DUPLICATE_KEY"],
        )

    def test_invalid_utf8_malformed_json_and_surrogate_are_controlled(self) -> None:
        cases = (
            (b'{"schema_version":"\xff"}', "UTF8_INVALID"),
            (b"{", "JSON_MALFORMED"),
            (b'{"value":"\\ud800"}', "JSON_UNICODE_INVALID"),
        )
        for payload, code in cases:
            with self.subTest(code=code):
                self.assertEqual(contract.validate_json_bytes(payload)["codes"], [code])

    def test_bool_is_not_accepted_as_integer(self) -> None:
        result = contract.validate_fixture_case(
            contract.parse_json_bytes(FIXTURE.read_bytes()), "boolean-integer"
        )
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
            [
                sys.executable,
                str(REPOSITORY_ROOT / "tools" / "research" / "m1b_contract.py"),
                *arguments,
            ],
            cwd=str(REPOSITORY_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_positive_fixture_cli_is_compact_stderr_free_and_path_free(self) -> None:
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

    def test_oversize_integer_cli_never_echoes_token_or_path(self) -> None:
        marker = "9" * 80
        with tempfile.TemporaryDirectory() as temporary:
            input_file = Path(temporary) / "synthetic-number.json"
            input_file.write_text(marker, encoding="ascii")
            completed = self._run("validate", str(input_file))
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stderr, b"")
        self.assertNotIn(marker.encode("ascii"), completed.stdout)
        self.assertNotIn(os.fsencode(str(input_file)), completed.stdout)
        self.assertEqual(
            json.loads(completed.stdout)["codes"],
            ["JSON_INTEGER_OUT_OF_RANGE"],
        )

    def test_missing_input_never_echoes_filename_path_or_exception(self) -> None:
        marker = "SENSITIVE_SYNTHETIC_FILENAME_MARKER"
        completed = self._run("validate", marker)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stderr, b"")
        self.assertNotIn(marker.encode("ascii"), completed.stdout)
        self.assertEqual(json.loads(completed.stdout)["codes"], ["INPUT_READ_FAILED"])

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
        with mock.patch.object(
            contract, "_read_explicit_file", side_effect=RuntimeError(marker)
        ):
            result = contract._execute(("validate", "synthetic"))
        encoded = contract._encode_result(result)
        self.assertNotIn(marker.encode("ascii"), encoded)
        self.assertEqual(json.loads(encoded)["codes"], ["UNEXPECTED_FAILURE"])

    def test_encode_fallback_preserves_closed_count_schema(self) -> None:
        encoded = contract._encode_result(
            {"status": object(), "codes": [], "counts": contract._empty_counts()}
        )
        result = json.loads(encoded)
        self.assertEqual(result["codes"], ["UNEXPECTED_FAILURE"])
        self.assertEqual(set(result["counts"]), set(contract._COUNT_KEYS))

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
