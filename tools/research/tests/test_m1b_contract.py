from __future__ import annotations

import ast
import copy
from fractions import Fraction
import hashlib
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
EXPECTED_FIXTURE_CASES = 173
EXPECTED_POSITIVE_CASES = 3
EXPECTED_FIXTURE_SHA256 = (
    "fca4fabea3781f53d1759475b0a1d3a8c97c3b03cb785e04051961fb2422fba4"
)
EXPECTED_BUNDLE_HASH = (
    "18940d254087317b46bd8c78a00a1526b741907dc3dc0c1eb28b9a9f8bc22cd4"
)


class SyntheticContractCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_bytes = FIXTURE.read_bytes()
        cls.manifest = contract.parse_json_bytes(cls.fixture_bytes)
        cls.cases = cls.manifest["cases"]
        cls.base = cls.manifest["base_document"]

    def test_all_table_cases_return_exact_controlled_code(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.fixture_bytes).hexdigest(),
            EXPECTED_FIXTURE_SHA256,
        )
        self.assertEqual(len(self.cases), EXPECTED_FIXTURE_CASES)
        self.assertEqual(
            sum(case["expected"]["status"] == "error" for case in self.cases),
            EXPECTED_FIXTURE_CASES - EXPECTED_POSITIVE_CASES,
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
            "not-applicable-cannot-claim-output",
            "terminal-failure-with-observed-atoms",
            "terminal-failure-accounting-mismatch",
            "success-without-model-call",
            "human-quality-without-output",
            "human-status-without-ground-truth",
            "human-ground-truth-without-output",
            "context-overflow-ground-truth-without-output",
            "no-output-cannot-pass-blinding",
            "no-output-literary-finding-empty-reviews",
            "no-output-model-review-finding",
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
            "model-success-with-unobserved-blinding",
            "materialized-input-size-limit",
            "materialization-work-limit",
            "accounting-count-exceeds-results",
            "retry-zero-hidden-attempt",
            "multiple-model-calls-without-retry",
            "repair-attempt-index-nonzero",
            "fallback-attempt-index-nonzero",
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
            # Final methodology and state remediation.
            "self-identification-denominator-failure",
            "self-identification-without-model-call",
            "self-identification-primary-ground-truth",
            "self-identification-editorial-approval",
            "self-identification-secondary-evidence",
            "blinding-aggregate-mismatch",
            "context-binding-self-asserted",
            "implementation-identity-self-asserted",
            "human-fallback-success-zero-model-calls",
            "human-fallback-model-call-invalid",
            "model-fallback-model-call-required",
            "human-fallback-self-identification",
            "finding-adjudication-missing",
            "finding-adjudicator-not-distinct",
            "critical-false-accept-without-approval",
            "external-mapping-aggregate-mismatch",
            "critical-three-initial-reviewers",
            "external-mapping-regeneration",
            "context-overflow-controlled-failure",
            "unknown-controlled-failure-code",
            "repair-self-identification-denominator-failure",
            "repair-self-identification-sibling-regeneration",
            "partial-secondary-evidence-non-self-identifying",
        }
        self.assertTrue(required <= case_ids, sorted(required - case_ids))

    def test_retry_zero_closes_non_primary_indexes_and_sibling_rows(self) -> None:
        for case_id in (
            "repair-attempt-index-nonzero",
            "fallback-attempt-index-nonzero",
        ):
            with self.subTest(case=case_id):
                self.assertEqual(
                    contract.validate_fixture_case(self.manifest, case_id)["codes"],
                    ["ASSIGNMENT_EXTRA"],
                )

        document = contract.parse_json_bytes(
            contract.materialize_fixture_case(
                self.manifest, "human-fallback-success-zero-model-calls"
            )
        )
        fallback = next(
            result
            for result in document["conformance_results"]
            if result["experiment_lane"] == "fallback"
        )
        sibling = copy.deepcopy(fallback)
        sibling["result_id"] = "00000000-0000-4000-8000-000000009999"
        document["conformance_results"].append(sibling)
        with self.assertRaises(contract.ContractError) as raised:
            contract.validate_document(document)
        self.assertEqual(raised.exception.code, "ASSIGNMENT_DUPLICATE")

    def test_positive_contract_uses_trusted_definition_registry(self) -> None:
        bundle = self.base["definition_bundle"]
        self.assertEqual(bundle["framing"], contract.COMPONENT_FRAMING)
        self.assertEqual(bundle["sha256"], EXPECTED_BUNDLE_HASH)
        self.assertEqual(bundle["sha256"], contract.TRUSTED_BUNDLE_HASH)
        self.assertEqual(len(bundle["components"]), 17)
        self.assertEqual(
            bundle["components"],
            [dict(component) for component in contract.TRUSTED_COMPONENTS],
        )
        self.assertEqual(
            {component["acceptance_state"] for component in bundle["components"]},
            {"proposed"},
        )
        analysis_component = next(
            component
            for component in bundle["components"]
            if component["kind"] == "analysis_policy"
        )
        self.assertEqual(analysis_component["version"], "m1b-analysis-policy-v4")
        self.assertEqual(
            analysis_component["generation"], contract.PROTOCOL_GENERATION
        )
        self.assertEqual(self.base["protocol"]["generation"], 104)

    def test_component_hash_has_a_fixed_public_vector(self) -> None:
        component = self.base["definition_bundle"]["components"][0]
        actual = contract.component_hash(
            component["kind"],
            component["version"],
            component["definition"].encode("ascii"),
        )
        self.assertEqual(
            actual,
            "6e3b9bfbaaef3793dd1a84ed5a6c37b8a249be4de5e2b889c13e84b83a15a9e1",
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
            benchmark["m1b0_complete_state"],
            "always_rejected_PARTIAL_REPORT_CANNOT_BE_COMPLETE",
        )
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
        self.assertEqual(
            output["controlled_failure_codes"],
            sorted(contract.CONTROLLED_FAILURE_CODES),
        )
        self.assertEqual(output["atom_fields"], list(contract._ATOM_FIELDS))
        self.assertEqual(output["sample_fields"], list(contract._SAMPLE_FIELDS))
        self.assertEqual(
            output["adjudication_fields"], list(contract._ADJUDICATION_FIELDS)
        )
        self.assertEqual(
            output["accounting_fields"], list(contract._ACCOUNTING_FIELDS)
        )
        self.assertEqual(output["count_keys"], list(contract._COUNT_KEYS))
        generation = definitions["generation_policy"]
        self.assertEqual(generation["retry_limit"], 0)
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
        self.assertEqual(corpus["decision_grade_split"], "holdout")
        split = definitions["split_policy"]
        self.assertEqual(
            split["source_cluster_generation_binding"],
            "immutable_one_generation",
        )
        self.assertEqual(split["decision_grade_split"], "holdout")
        self.assertEqual(split["splits"], sorted(contract.SPLITS))
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
        self.assertEqual(
            validator["max_input_bytes_boundaries"],
            [
                "fixture_manifest_file",
                "materialized_fixture_document",
                "standalone_document",
            ],
        )
        self.assertEqual(
            validator["max_fixture_patch_count"],
            contract.MAX_FIXTURE_PATCH_COUNT,
        )
        self.assertEqual(
            validator["max_materialization_work_bytes"],
            contract.MAX_MATERIALIZATION_WORK_BYTES,
        )
        self.assertEqual(
            validator["materialization_preencode_reserve_bytes"],
            contract.MATERIALIZATION_PREENCODE_RESERVE_BYTES,
        )
        self.assertEqual(
            validator["materialized_final_encoding"],
            "reuse_last_budgeted_encoding",
        )
        self.assertEqual(validator["json_integer_min"], contract.MIN_JSON_INTEGER)
        self.assertEqual(validator["json_integer_max"], contract.MAX_JSON_INTEGER)
        analysis = definitions["analysis_policy"]
        self.assertEqual(
            analysis["minimum_n_per_dimension_floor"],
            {
                "context_voice_style": 22,
                "literary_russian": 22,
                "meaning_accuracy": 46,
                "terminology_lore": 30,
            },
        )
        self.assertNotIn("minimum_overall_n", analysis)
        self.assertEqual(analysis["naive_pooled_overall_interval"], "forbidden")
        self.assertEqual(analysis["candidate_family_alpha"], [1, 60])
        self.assertEqual(analysis["family_wise_alpha"], [1, 20])
        self.assertEqual(analysis["candidate_family_count"], 3)
        self.assertEqual(analysis["two_sided_candidate_tail_alpha"], [1, 120])
        self.assertEqual(
            analysis["decision_method"],
            "bonferroni_candidates_conjunctive_strata",
        )
        self.assertEqual(
            analysis["marginal_95_interval"],
            "descriptive_only_not_selection_evidence",
        )
        self.assertEqual(
            analysis["dimension_confidence_floors"],
            {
                "context_voice_style": [4, 5],
                "literary_russian": [4, 5],
                "meaning_accuracy": [9, 10],
                "terminology_lore": [17, 20],
            },
        )
        self.assertEqual(analysis["critical_false_accept_ceiling"], [1, 50])
        self.assertEqual(analysis["critical_false_accept_minimum_n"], 203)
        self.assertEqual(
            analysis["critical_false_accept_decision_grade_split"], "holdout"
        )
        self.assertIn(
            "split", analysis["critical_false_accept_input_fields"]
        )
        self.assertIn(
            "split", analysis["statistical_outcome"]["input_fields"]
        )
        self.assertEqual(
            analysis["per_stratum_boundary_vectors"],
            {"lower_successes_0": [0, 1], "upper_successes_n": [1, 1]},
        )
        self.assertEqual(
            analysis["agreement"]["stable_pair_key"], ["stratum", "dimension"]
        )
        self.assertEqual(
            analysis["agreement"]["candidate_kappa_pooling"], "forbidden"
        )
        self.assertIn("split", analysis["agreement"]["input_fields"])
        self.assertEqual(
            analysis["agreement"]["decision_grade_helper"],
            "agreement_gate_holdout_only",
        )
        self.assertEqual(
            analysis["agreement"]["ratings_materializer"],
            "inside_human_ground_truth_validator_no_report_supplied_scores",
        )
        self.assertEqual(
            analysis["agreement"]["contingency_estimator"],
            "uniform_source_then_uniform_applicable_paired_row",
        )
        self.assertEqual(
            analysis["agreement"]["source_generation_pair_mass"],
            "each_actual_pair_contributes_1/applicable_pair_count_for_source",
        )
        self.assertEqual(
            analysis["agreement"]["logical_row_key"],
            ["result_id", "dimension"],
        )
        self.assertEqual(
            analysis["agreement"]["source_matrix"],
            "D_sij=count_sij/applicable_pair_count_for_source",
        )
        self.assertEqual(
            analysis["agreement"]["robustness_interpretation"],
            "influence_check_not_sampling_confidence_interval",
        )
        self.assertEqual(
            analysis["statistical_dimension_or_gate_values"],
            sorted(contract.STATISTICAL_DIMENSIONS_OR_GATES),
        )
        self.assertEqual(
            analysis["agreement"]["statuses"],
            [
                "AGREEMENT_APPLICABILITY_DISAGREEMENT",
                "AGREEMENT_INSUFFICIENT_UNITS",
                "AGREEMENT_UNDEFINED_ZERO_EXPECTED_DISAGREEMENT",
                "AGREEMENT_POINT_BELOW_FLOOR",
                "AGREEMENT_UNCERTAINTY_UNDEFINED",
                "AGREEMENT_ROBUSTNESS_BELOW_FLOOR",
                "AGREEMENT_PASS",
            ],
        )
        self.assertTrue(analysis["owner_decision_required"])
        context = definitions["context_limit_policy"]
        self.assertEqual(context["binding"], contract._EXPECTED_CONTEXT_LIMIT_BINDING)
        implementation = definitions["implementation_identity_policy"]
        self.assertEqual(
            implementation["admission"], contract._EXPECTED_IMPLEMENTATION_IDENTITY
        )
        self.assertEqual(
            implementation["report_self_assertion"], "forbidden"
        )
        self.assertEqual(
            implementation["manifest_root_fields"],
            ["files", "implementation_generation", "manifest_schema"],
        )
        self.assertEqual(
            implementation["file_fields"], ["path", "role", "sha256"]
        )
        self.assertEqual(implementation["self_digest_field"], "forbidden")
        retention = definitions["retention_leakage_policy"]
        self.assertEqual(
            retention["persistence_blocker"], "PROVIDER_PERSISTENCE_UNPROVEN"
        )
        self.assertEqual(retention["persistence_status"], "not_probed")
        blinding = definitions["randomization_blinding_policy"]
        self.assertEqual(blinding["unblinded_review"], "secondary_only")
        self.assertEqual(blinding["self_identification_model_call_count"], 1)
        self.assertEqual(
            blinding["replacement_reviewers"], "never_unblinded_humans"
        )
        measurement = definitions["measurement_policy"]
        self.assertEqual(measurement["human_fallback_model_call_count"], 0)
        self.assertEqual(measurement["model_output_success_model_call_count"], 1)
        self.assertEqual(
            measurement["not_applicable_state"],
            "not_observed_mapping0_zero_accounting_no_human",
        )
        self.assertEqual(
            measurement["no_output_content_evidence"],
            "findings_reviews_and_ground_truth_forbidden",
        )
        self.assertTrue(
            measurement["provider_fallback_false_allows_declared_human_lane"]
        )
        quality = definitions["quality_rubric"]
        self.assertTrue(quality["human_status_requires_ground_truth"])
        self.assertEqual(quality["initial_hgt_reviewers_per_dimension"], 2)
        self.assertEqual(
            quality["critical_false_accept_definition"],
            "editorially_approved_and_confirmed_underlying_critical_same_result_dimension",
        )
        self.assertFalse(quality["safely_caught_critical_defect_is_false_accept"])
        self.assertEqual(
            quality["missing_ground_truth_status"], "not_evaluated"
        )
        self.assertEqual(
            quality["finding_outcome_fields"],
            ["decision", "severity", "hard_fail", "mandatory_review"],
        )
        self.assertEqual(quality["missing_reviewer_outcome"], "reject")

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


class MethodologyAndStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = contract.parse_json_bytes(FIXTURE.read_bytes())
        cls.base = cls.manifest["base_document"]

    def _validated_state(self, document):
        registry = contract._IdentityRegistry()
        candidates = contract._validate_candidates(
            document["candidate_profiles"], registry
        )
        samples, _, _ = contract._validate_corpus(document["corpus"], registry)
        results = contract._validate_results(
            document["conformance_results"], registry, samples, candidates
        )
        return registry, samples, results

    @staticmethod
    def _ground_truth(
        identifier,
        reviewer,
        result,
        *,
        score=4,
        status="human_pass",
        tier="primary_blinded",
        mapping=1,
        stage="initial",
        blinding="never_unblinded",
        adjudicates=None,
    ):
        return {
            "adjudicates": [] if adjudicates is None else list(adjudicates),
            "applicability_reason": (
                "frozen_not_applicable" if status == "not_applicable" else None
            ),
            "dimension": "meaning_accuracy",
            "evidence_tier": tier,
            "ground_truth_id": identifier,
            "mapping_generation": mapping,
            "ordinal_score": None if status == "not_applicable" else score,
            "result_id": result,
            "review_stage": stage,
            "reviewer_blinding": blinding,
            "reviewer_id": reviewer,
            "reviewer_role": "human_reviewer",
            "status": status,
        }

    @staticmethod
    def _mark_primary_output(result, *, blinding="passed", mapping=1):
        result["blinding_status"] = blinding
        result["mapping_generation"] = mapping
        result["terminal_status"] = "success"
        result["accounting"]["initial_attempt_count"] = 1
        result["accounting"]["model_call_count"] = 1

    @staticmethod
    def _finding_review(
        review_id,
        reviewer_id,
        finding_id,
        *,
        category="literary_error",
        dimension="literary_russian",
        decision="confirmed",
        severity="low",
        hard_fail=False,
        mandatory_review=None,
        tier="primary_blinded",
        mapping=1,
        stage="initial",
        blinding="never_unblinded",
        role="human_reviewer",
        credit="human",
    ):
        if mandatory_review is None:
            mandatory_review = severity in ("high", "critical") or hard_fail
        return {
            "category": category,
            "decision": decision,
            "dimension": dimension,
            "evidence_tier": tier,
            "finding_id": finding_id,
            "hard_fail": hard_fail,
            "mandatory_review": mandatory_review,
            "mapping_generation": mapping,
            "review_credit": credit,
            "review_id": review_id,
            "review_stage": stage,
            "reviewer_blinding": blinding,
            "reviewer_id": reviewer_id,
            "reviewer_role": role,
            "severity": severity,
        }

    @staticmethod
    def _finding(
        finding_id,
        result_id,
        reviews,
        *,
        category="literary_error",
        dimension="literary_russian",
        severity="low",
        hard_fail=False,
        mandatory_review=None,
    ):
        if mandatory_review is None:
            mandatory_review = severity in ("high", "critical") or hard_fail
        return {
            "category": category,
            "dimension": dimension,
            "finding_id": finding_id,
            "hard_fail": hard_fail,
            "mandatory_review": mandatory_review,
            "result_id": result_id,
            "reviews": list(reviews),
            "severity": severity,
        }

    @staticmethod
    def _finding_adjudication(
        adjudication_id,
        reviewer_id,
        finding_id,
        initial_review_ids,
        *,
        category="literary_error",
        dimension="literary_russian",
        decision="confirmed",
        severity="low",
        hard_fail=False,
        mandatory_review=None,
        mapping=1,
    ):
        if mandatory_review is None:
            mandatory_review = severity in ("high", "critical") or hard_fail
        return {
            "adjudication_id": adjudication_id,
            "category": category,
            "decision": decision,
            "dimension": dimension,
            "evidence_tier": "primary_blinded",
            "finding_id": finding_id,
            "hard_fail": hard_fail,
            "initial_review_ids": list(initial_review_ids),
            "mandatory_review": mandatory_review,
            "mapping_generation": mapping,
            "reviewer_blinding": "never_unblinded",
            "reviewer_id": reviewer_id,
            "reviewer_role": "human_reviewer",
            "severity": severity,
        }

    @staticmethod
    def _agreement_rows(first, second, *, candidate="candidate_a", split="holdout"):
        return [
            {
                "applicability_adjudication": None,
                "candidate": candidate,
                "dimension": "meaning_accuracy",
                "first": left,
                "initial_record_ids": [
                    f"00000000-0000-4000-8000-{index + 1000:012x}",
                    f"00000000-0000-4000-8000-{index + 2000:012x}",
                ],
                "profile": "profile_a",
                "result_id": f"00000000-0000-4000-8000-{index + 5000:012x}",
                "reviewer_pair": [
                    "00000000-0000-4000-8000-000000000901",
                    "00000000-0000-4000-8000-000000000902",
                ],
                "second": right,
                "source_generation_id": f"00000000-0000-4000-8000-{index:012x}",
                "split": split,
                "stratum": "ui",
            }
            for index, (left, right) in enumerate(zip(first, second), start=1)
        ]

    def test_exact_family_wise_minima_replace_marginal_numbers(self) -> None:
        self.assertEqual(
            contract.minimum_power_bound_n(
                Fraction(9, 10), contract.TWO_SIDED_CANDIDATE_TAIL_ALPHA
            ),
            46,
        )
        self.assertEqual(
            contract.minimum_power_bound_n(
                Fraction(17, 20), contract.TWO_SIDED_CANDIDATE_TAIL_ALPHA
            ),
            30,
        )
        self.assertEqual(
            contract.minimum_power_bound_n(
                Fraction(4, 5), contract.TWO_SIDED_CANDIDATE_TAIL_ALPHA
            ),
            22,
        )
        self.assertEqual(
            contract.minimum_power_bound_n(
                Fraction(98, 100), contract.CANDIDATE_FAMILY_ALPHA
            ),
            203,
        )
        self.assertGreater(Fraction(9, 10) ** 45, Fraction(1, 120))
        self.assertLessEqual(Fraction(9, 10) ** 46, Fraction(1, 120))
        self.assertGreater(Fraction(98, 100) ** 202, Fraction(1, 60))
        self.assertLessEqual(Fraction(98, 100) ** 203, Fraction(1, 60))

    def test_repeated_source_across_strata_is_not_pooled_independent_n(self) -> None:
        source = "00000000-0000-4000-8000-000000000091"
        summary = contract.statistical_unit_summary(
            [
                {"applicable": True, "candidate": "candidate_a", "profile": "profile_a", "dimension_or_gate": "meaning_accuracy", "source_generation_id": source, "split": "holdout", "stratum": "ui", "success": True},
                {"applicable": True, "candidate": "candidate_a", "profile": "profile_a", "dimension_or_gate": "meaning_accuracy", "source_generation_id": source, "split": "holdout", "stratum": "ui", "success": False},
                {"applicable": True, "candidate": "candidate_a", "profile": "profile_a", "dimension_or_gate": "meaning_accuracy", "source_generation_id": source, "split": "holdout", "stratum": "narrative", "success": True},
                {"applicable": False, "candidate": "candidate_a", "profile": "profile_a", "dimension_or_gate": "meaning_accuracy", "source_generation_id": "00000000-0000-4000-8000-000000000092", "split": "holdout", "stratum": "narrative", "success": None},
            ]
        )
        self.assertEqual(summary["per_stratum_counts"]["ui"], 1)
        self.assertEqual(summary["per_stratum_counts"]["narrative"], 2)
        self.assertEqual(summary["per_stratum_denominators"]["ui"], 1)
        self.assertEqual(summary["per_stratum_successes"]["ui"], 0)
        self.assertEqual(summary["per_stratum_denominators"]["narrative"], 1)
        self.assertEqual(summary["per_stratum_successes"]["narrative"], 1)
        self.assertEqual(summary["per_stratum_not_applicable"]["narrative"], 1)
        self.assertEqual(summary["stratum_contribution_count"], 3)
        self.assertEqual(summary["overall_distinct_source_count"], 2)
        self.assertEqual(summary["overall_applicable_source_count"], 1)
        self.assertEqual(summary["overall_conservative_success_count"], 0)
        self.assertEqual(summary["overall_confidence_gate"], "forbidden")
        mixed_scope = [
            {"applicable": True, "candidate": "candidate_a", "profile": "profile_a", "dimension_or_gate": "meaning_accuracy", "source_generation_id": source, "split": "holdout", "stratum": "ui", "success": True},
            {"applicable": True, "candidate": "candidate_b", "profile": "profile_a", "dimension_or_gate": "meaning_accuracy", "source_generation_id": source, "split": "holdout", "stratum": "ui", "success": True},
        ]
        with self.assertRaises(contract.ContractError) as raised:
            contract.statistical_unit_summary(mixed_scope)
        self.assertEqual(raised.exception.code, "STATISTICAL_UNIT_SCOPE_MIXED")
        unknown_gate = copy.deepcopy(mixed_scope[:1])
        unknown_gate[0]["dimension_or_gate"] = "synthetic_unknown_gate"
        with self.assertRaises(contract.ContractError) as raised:
            contract.statistical_unit_summary(unknown_gate)
        self.assertEqual(raised.exception.code, "UNKNOWN_DIMENSION_OR_GATE")
        with self.assertRaises(contract.ContractError) as raised:
            contract.statistical_unit_summary(
                [
                    {"applicable": False, "candidate": "candidate_a", "profile": "profile_a", "dimension_or_gate": "meaning_accuracy", "source_generation_id": source, "split": "holdout", "stratum": "ui", "success": None}
                ]
            )
        self.assertEqual(
            raised.exception.code, "STATISTICAL_UNIT_NO_APPLICABLE_OUTCOME"
        )

    def test_split_provenance_prevents_tuning_holdout_pooling(self) -> None:
        scores = [0, 1, 2, 3, 4] * 4 + [0, 1, 2]
        tuning = self._agreement_rows(scores, scores, split="tuning")
        holdout = self._agreement_rows(scores, scores, split="holdout")
        self.assertEqual(
            contract.agreement_diagnostic(tuning),
            {"split": "tuning", "status": "AGREEMENT_INSUFFICIENT_UNITS"},
        )
        self.assertEqual(
            contract.agreement_gate(holdout), "AGREEMENT_INSUFFICIENT_UNITS"
        )
        with self.assertRaises(contract.ContractError) as raised:
            contract.agreement_gate(tuning)
        self.assertEqual(raised.exception.code, "DECISION_GRADE_SPLIT_INVALID")
        with self.assertRaises(contract.ContractError) as raised:
            contract.agreement_unit_vectors(tuning + holdout)
        self.assertEqual(raised.exception.code, "STATISTICAL_SPLIT_MIXED")

        missing = copy.deepcopy(holdout[:1])
        missing[0].pop("split")
        with self.assertRaises(contract.ContractError) as raised:
            contract.agreement_unit_vectors(missing)
        self.assertEqual(raised.exception.code, "UNKNOWN_FIELD")
        unknown = copy.deepcopy(holdout[:1])
        unknown[0]["split"] = "synthetic_unknown"
        with self.assertRaises(contract.ContractError) as raised:
            contract.agreement_unit_vectors(unknown)
        self.assertEqual(raised.exception.code, "UNKNOWN_SPLIT")

        passing_holdout = self._agreement_rows(
            [0, 1, 2, 3, 4] * 9 + [0],
            [0, 1, 3, 2, 4] * 9 + [0],
            split="holdout",
        )
        tuning_failure = self._agreement_rows([0], [4], split="tuning")
        self.assertEqual(contract.agreement_gate(passing_holdout), "AGREEMENT_PASS")
        with self.assertRaises(contract.ContractError) as raised:
            contract.agreement_gate(passing_holdout + tuning_failure)
        self.assertEqual(raised.exception.code, "STATISTICAL_SPLIT_MIXED")

    def test_tuning_cannot_increase_holdout_statistical_or_cfa_denominators(self) -> None:
        def statistical_row(identifier, split):
            return {
                "applicable": True,
                "candidate": "candidate_a",
                "dimension_or_gate": "meaning_accuracy",
                "profile": "profile_a",
                "source_generation_id": identifier,
                "split": split,
                "stratum": "ui",
                "success": True,
            }

        tuning_stat = statistical_row(
            "00000000-0000-4000-8000-000000000091", "tuning"
        )
        holdout_stat = statistical_row(
            "00000000-0000-4000-8000-000000000092", "holdout"
        )
        self.assertFalse(
            contract.statistical_unit_summary([tuning_stat])[
                "decision_grade_eligible"
            ]
        )
        self.assertEqual(
            contract.decision_grade_statistical_unit_summary([holdout_stat])[
                "per_stratum_denominators"
            ]["ui"],
            1,
        )
        with self.assertRaises(contract.ContractError) as raised:
            contract.statistical_unit_summary([tuning_stat, holdout_stat])
        self.assertEqual(raised.exception.code, "STATISTICAL_SPLIT_MIXED")
        missing_stat = copy.deepcopy(holdout_stat)
        missing_stat.pop("split")
        with self.assertRaises(contract.ContractError) as raised:
            contract.statistical_unit_summary([missing_stat])
        self.assertEqual(raised.exception.code, "UNKNOWN_FIELD")
        unknown_stat = copy.deepcopy(holdout_stat)
        unknown_stat["split"] = "synthetic_unknown"
        with self.assertRaises(contract.ContractError) as raised:
            contract.statistical_unit_summary([unknown_stat])
        self.assertEqual(raised.exception.code, "UNKNOWN_SPLIT")

        def cfa_rows(count, split, offset):
            return [
                {
                    "candidate": "candidate_a",
                    "event": False,
                    "profile": "profile_a",
                    "risk_class": "auto_eligible_candidate",
                    "source_generation_id": (
                        f"00000000-0000-4000-8000-{offset + index:012x}"
                    ),
                    "split": split,
                }
                for index in range(count)
            ]

        tuning_cfa = cfa_rows(100, "tuning", 1000)
        holdout_cfa = cfa_rows(103, "holdout", 2000)
        self.assertEqual(
            contract.critical_false_accept_summary(tuning_cfa)[
                "source_generation_count"
            ],
            100,
        )
        holdout_summary = contract.decision_grade_critical_false_accept_summary(
            holdout_cfa
        )
        self.assertEqual(holdout_summary["source_generation_count"], 103)
        self.assertFalse(holdout_summary["meets_decision_minimum"])
        with self.assertRaises(contract.ContractError) as raised:
            contract.critical_false_accept_summary(tuning_cfa + holdout_cfa)
        self.assertEqual(raised.exception.code, "STATISTICAL_SPLIT_MIXED")
        missing_cfa = copy.deepcopy(holdout_cfa[:1])
        missing_cfa[0].pop("split")
        with self.assertRaises(contract.ContractError) as raised:
            contract.critical_false_accept_summary(missing_cfa)
        self.assertEqual(raised.exception.code, "UNKNOWN_FIELD")
        unknown_cfa = copy.deepcopy(holdout_cfa[:1])
        unknown_cfa[0]["split"] = "synthetic_unknown"
        with self.assertRaises(contract.ContractError) as raised:
            contract.critical_false_accept_summary(unknown_cfa)
        self.assertEqual(raised.exception.code, "UNKNOWN_SPLIT")
        tuning_203 = contract.critical_false_accept_summary(
            cfa_rows(203, "tuning", 3000)
        )
        self.assertFalse(tuning_203["decision_grade_eligible"])
        self.assertFalse(tuning_203["meets_decision_minimum"])

    def test_exact_quadratic_kappa_and_robustness_vectors(self) -> None:
        first = [0, 1, 2, 3, 4]
        self.assertEqual(contract.quadratic_weighted_kappa(first, first), 1)
        self.assertEqual(
            contract.quadratic_weighted_kappa(first, [0, 1, 3, 2, 4]),
            Fraction(9, 10),
        )
        self.assertEqual(
            contract.quadratic_weighted_kappa(first, [4, 3, 2, 1, 0]), -1
        )
        robust_first = first * 9 + [0]
        robust_second = [0, 1, 3, 2, 4] * 9 + [0]
        rows = self._agreement_rows(robust_first, robust_second)
        self.assertEqual(
            contract.quadratic_weighted_kappa(robust_first, robust_second),
            Fraction(217, 240),
        )
        self.assertEqual(
            contract.agreement_gate(rows),
            "AGREEMENT_PASS",
        )
        replayed_rows = copy.deepcopy(rows)
        replayed_rows.append(copy.deepcopy(replayed_rows[4]))
        with self.assertRaises(contract.ContractError) as raised:
            contract.agreement_unit_vectors(replayed_rows)
        self.assertEqual(raised.exception.code, "AGREEMENT_LOGICAL_ROW_DUPLICATE")

        duplicate_rows = copy.deepcopy(rows)
        repeated = copy.deepcopy(duplicate_rows[4])
        repeated["first"] = 1
        repeated["second"] = 2
        repeated["initial_record_ids"] = [
            "00000000-0000-4000-8000-000000003001",
            "00000000-0000-4000-8000-000000003002",
        ]
        repeated["result_id"] = "00000000-0000-4000-8000-000000003003"
        duplicate_rows.append(repeated)
        vectors = contract.agreement_unit_vectors(duplicate_rows)
        self.assertEqual(
            len(vectors["source_generation_ids"]), len(rows)
        )
        self.assertEqual(
            vectors["paired_ratings_by_source"][4], ((4, 4), (1, 2))
        )
        mixed_rows = copy.deepcopy(rows)
        mixed_rows[-1]["candidate"] = "candidate_b"
        with self.assertRaises(contract.ContractError) as raised:
            contract.agreement_gate(mixed_rows)
        self.assertEqual(raised.exception.code, "AGREEMENT_SCOPE_MIXED")
        noncanonical_pair = copy.deepcopy(rows)
        noncanonical_pair[0]["reviewer_pair"].reverse()
        with self.assertRaises(contract.ContractError) as raised:
            contract.agreement_gate(noncanonical_pair)
        self.assertEqual(raised.exception.code, "STABLE_REVIEWER_PAIR_INVALID")
        unilateral = copy.deepcopy(rows)
        unilateral[0]["first"] = None
        with self.assertRaises(contract.ContractError) as raised:
            contract.agreement_gate(unilateral)
        self.assertEqual(
            raised.exception.code,
            "AGREEMENT_APPLICABILITY_ADJUDICATION_REQUIRED",
        )
        unilateral[0]["applicability_adjudication"] = {
            "adjudication_id": "00000000-0000-4000-8000-000000000903",
            "adjudicator_reviewer_id": "00000000-0000-4000-8000-000000000904",
            "initial_record_ids": unilateral[0]["initial_record_ids"],
        }
        self.assertEqual(
            contract.agreement_gate(unilateral),
            "AGREEMENT_APPLICABILITY_DISAGREEMENT",
        )

    def test_equal_source_weighting_preserves_actual_rating_pairs(self) -> None:
        first = [index % 4 for index in range(46)]
        rows = self._agreement_rows(first, [4] * 46)
        crossed_rows = []
        for index, row in enumerate(rows, start=1):
            crossed_rows.append(row)
            crossed = copy.deepcopy(row)
            crossed["first"] = 4
            crossed["second"] = row["first"]
            crossed["initial_record_ids"] = [
                f"00000000-0000-4000-8000-{index + 3000:012x}",
                f"00000000-0000-4000-8000-{index + 4000:012x}",
            ]
            crossed["result_id"] = (
                f"00000000-0000-4000-8000-{index + 6000:012x}"
            )
            crossed_rows.append(crossed)

        self.assertTrue(
            all(row["first"] != row["second"] for row in crossed_rows)
        )
        vectors = contract.agreement_unit_vectors(crossed_rows)
        paired = vectors["paired_ratings_by_source"]
        self.assertEqual(len(paired), 46)
        self.assertTrue(all(len(source_pairs) == 2 for source_pairs in paired))
        self.assertEqual(paired[0], ((0, 4), (4, 0)))
        observed = contract.source_weighted_quadratic_kappa(paired)
        self.assertIs(type(observed), Fraction)
        self.assertEqual(observed, Fraction(-13689, 18971))
        self.assertEqual(
            contract.source_weighted_quadratic_kappa(list(reversed(paired))),
            observed,
        )
        self.assertEqual(
            contract.source_weighted_quadratic_kappa(
                [tuple(reversed(source_pairs)) for source_pairs in paired]
            ),
            observed,
        )
        transposed = [
            tuple((right, left) for left, right in source_pairs)
            for source_pairs in paired
        ]
        self.assertEqual(
            contract.source_weighted_quadratic_kappa(transposed), observed
        )
        single_pair_sources = [
            ((left, right),) for left, right in zip(first, [4] * 46)
        ]
        self.assertEqual(
            contract.source_weighted_quadratic_kappa(single_pair_sources),
            contract.quadratic_weighted_kappa(first, [4] * 46),
        )
        sparse = [((0, 0),), ((4, 0),)]
        repeated_within_source = [tuple([(0, 0)] * 100), ((4, 0),)]
        self.assertEqual(
            contract.source_weighted_quadratic_kappa(sparse),
            contract.source_weighted_quadratic_kappa(repeated_within_source),
        )
        self.assertEqual(
            contract.agreement_gate(crossed_rows),
            "AGREEMENT_POINT_BELOW_FLOOR",
        )

        passing_rows = self._agreement_rows(
            [0, 1, 2, 3, 4] * 9 + [0],
            [0, 1, 3, 2, 4] * 9 + [0],
        )
        repeated_same_pair = copy.deepcopy(passing_rows[0])
        repeated_same_pair["initial_record_ids"] = [
            "00000000-0000-4000-8000-000000007001",
            "00000000-0000-4000-8000-000000007002",
        ]
        repeated_same_pair["result_id"] = (
            "00000000-0000-4000-8000-000000007003"
        )
        whole_source_rows = passing_rows + [repeated_same_pair]
        with mock.patch.object(
            contract,
            "source_weighted_quadratic_kappa",
            wraps=contract.source_weighted_quadratic_kappa,
        ) as estimator:
            self.assertEqual(
                contract.agreement_gate(whole_source_rows), "AGREEMENT_PASS"
            )
        calls = [call.args[0] for call in estimator.call_args_list]
        self.assertEqual(len(calls[0]), 46)
        self.assertTrue(all(len(source_rows) == 45 for source_rows in calls[1:]))
        self.assertEqual(
            sum(
                any(len(source_pairs) == 2 for source_pairs in source_rows)
                for source_rows in calls
            ),
            46,
        )

    def test_critical_false_accepts_collapse_by_source_generation_and_class(self) -> None:
        source = "00000000-0000-4000-8000-000000000091"
        base = {
            "candidate": "candidate_a",
            "profile": "profile_a",
            "risk_class": "auto_eligible_candidate",
            "source_generation_id": source,
            "split": "holdout",
        }
        summary = contract.critical_false_accept_summary(
            [
                dict(base, event=False),
                dict(base, event=True),
                dict(
                    base,
                    event=False,
                    source_generation_id="00000000-0000-4000-8000-000000000092",
                ),
            ]
        )
        self.assertEqual(
            summary,
            {
                "decision_grade_eligible": True,
                "event_count": 1,
                "meets_decision_minimum": False,
                "source_generation_count": 2,
                "split": "holdout",
            },
        )
        mixed = [dict(base, event=False), dict(base, event=False, candidate="candidate_b")]
        with self.assertRaises(contract.ContractError) as raised:
            contract.critical_false_accept_summary(mixed)
        self.assertEqual(raised.exception.code, "CFA_SCOPE_MIXED")
        unknown_risk = [dict(base, event=False, risk_class="synthetic_unknown")]
        with self.assertRaises(contract.ContractError) as raised:
            contract.critical_false_accept_summary(unknown_risk)
        self.assertEqual(raised.exception.code, "UNKNOWN_RISK_CLASS")

    def test_zero_variance_and_insufficient_agreement_fail_closed(self) -> None:
        self.assertEqual(
            contract.agreement_gate(self._agreement_rows([4] * 46, [4] * 46)),
            "AGREEMENT_UNDEFINED_ZERO_EXPECTED_DISAGREEMENT",
        )
        self.assertEqual(
            contract.agreement_gate(
                self._agreement_rows(
                    [0, 1, 2, 3, 4] * 9,
                    [0, 1, 2, 3, 4] * 9,
                )
            ),
            "AGREEMENT_INSUFFICIENT_UNITS",
        )

    def test_agreement_delete_one_uncertainty_branches_fail_closed(self) -> None:
        robustness_matrix = [
            [6, 0, 0, 0, 1],
            [1, 12, 0, 2, 1],
            [1, 1, 9, 0, 0],
            [0, 0, 1, 5, 1],
            [1, 0, 0, 0, 4],
        ]
        first = []
        second = []
        for left, row in enumerate(robustness_matrix):
            for right, count in enumerate(row):
                first.extend([left] * count)
                second.extend([right] * count)
        self.assertEqual(len(first), 46)
        self.assertEqual(
            contract.quadratic_weighted_kappa(first, second), Fraction(708, 1145)
        )
        self.assertEqual(
            contract.agreement_gate(self._agreement_rows(first, second)),
            "AGREEMENT_ROBUSTNESS_BELOW_FLOOR",
        )

        mostly_constant_first = [4] * 45 + [0]
        mostly_constant_second = [4] * 45 + [0]
        self.assertEqual(
            contract.quadratic_weighted_kappa(
                mostly_constant_first, mostly_constant_second
            ),
            1,
        )
        self.assertEqual(
            contract.agreement_gate(
                self._agreement_rows(mostly_constant_first, mostly_constant_second)
            ),
            "AGREEMENT_UNCERTAINTY_UNDEFINED",
        )

    def test_stable_pair_drift_across_candidates_is_rejected(self) -> None:
        document = copy.deepcopy(self.base)
        result_ids = (
            "00000000-0000-4000-8000-000000000031",
            "00000000-0000-4000-8000-000000000032",
        )
        for result in document["conformance_results"][:2]:
            self._mark_primary_output(result)
            result["dimension_records"][1]["status"] = "human_pass"
        document["human_ground_truth"] = [
            self._ground_truth("00000000-0000-4000-8000-000000000081", "00000000-0000-4000-8000-000000000061", result_ids[0]),
            self._ground_truth("00000000-0000-4000-8000-000000000082", "00000000-0000-4000-8000-000000000062", result_ids[0]),
            self._ground_truth("00000000-0000-4000-8000-000000000083", "00000000-0000-4000-8000-000000000061", result_ids[1]),
            self._ground_truth("00000000-0000-4000-8000-000000000084", "00000000-0000-4000-8000-000000000063", result_ids[1]),
        ]
        registry, samples, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_human_ground_truth(
                document["human_ground_truth"], registry, results, samples
            )
        self.assertEqual(raised.exception.code, "STABLE_REVIEWER_PAIR_DRIFT")

    def test_external_mapping_leak_requires_fresh_mapping_and_reviewers(self) -> None:
        document = copy.deepcopy(self.base)
        result = document["conformance_results"][0]
        self._mark_primary_output(
            result, blinding="external_mapping_leak", mapping=2
        )
        result["dimension_records"][1]["status"] = "human_pass"
        result_id = result["result_id"]
        records = [
            self._ground_truth(
                "00000000-0000-4000-8000-000000000081",
                "00000000-0000-4000-8000-000000000061",
                result_id,
                tier="compromised_primary",
                mapping=1,
                blinding="unblinded",
            ),
            self._ground_truth("00000000-0000-4000-8000-000000000082", "00000000-0000-4000-8000-000000000062", result_id, mapping=2),
            self._ground_truth("00000000-0000-4000-8000-000000000083", "00000000-0000-4000-8000-000000000063", result_id, mapping=2),
        ]
        document["human_ground_truth"] = records
        registry, samples, results = self._validated_state(document)
        validated = contract._validate_human_ground_truth(
            records, registry, results, samples
        )
        self.assertEqual(
            validated[(result_id, "meaning_accuracy")],
            {
                "00000000-0000-4000-8000-000000000062",
                "00000000-0000-4000-8000-000000000063",
            },
        )

        reused = copy.deepcopy(document)
        reused["human_ground_truth"][1]["reviewer_id"] = (
            "00000000-0000-4000-8000-000000000061"
        )
        registry, samples, results = self._validated_state(reused)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_human_ground_truth(
                reused["human_ground_truth"], registry, results, samples
            )
        self.assertEqual(raised.exception.code, "BLINDING_REVIEWER_REUSE")

    def test_unblinded_reviewer_cannot_receive_primary_credit_elsewhere(self) -> None:
        document = copy.deepcopy(self.base)
        self_identifying = document["conformance_results"][0]
        self._mark_primary_output(
            self_identifying, blinding="self_identifying_output"
        )
        self_identifying["failure_code"] = "BLINDING_FAILED"
        self_identifying["terminal_status"] = "blinding_failed"
        self_identifying["accounting"]["terminal_failure_count"] = 1
        for dimension in self_identifying["dimension_records"][1:]:
            dimension["status"] = "blinding_failed"

        blinded = document["conformance_results"][1]
        self._mark_primary_output(blinded, mapping=2)
        blinded["dimension_records"][1]["status"] = "human_pass"
        records = [
            self._ground_truth(
                "00000000-0000-4000-8000-000000000081",
                "00000000-0000-4000-8000-000000000061",
                self_identifying["result_id"],
                tier="secondary_unblinded",
                mapping=1,
                stage="secondary",
                blinding="unblinded",
            ),
            self._ground_truth(
                "00000000-0000-4000-8000-000000000082",
                "00000000-0000-4000-8000-000000000061",
                blinded["result_id"],
                mapping=2,
            ),
            self._ground_truth(
                "00000000-0000-4000-8000-000000000083",
                "00000000-0000-4000-8000-000000000062",
                blinded["result_id"],
                mapping=2,
            ),
        ]
        registry, samples, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_human_ground_truth(records, registry, results, samples)
        self.assertEqual(raised.exception.code, "BLINDING_REVIEWER_REUSE")

    def test_self_identifying_state_is_truthfully_accounted_before_live_admission(self) -> None:
        cases = (
            ("self-identification-denominator-failure", 0),
            ("self-identification-secondary-evidence", 1),
            ("repair-self-identification-denominator-failure", 0),
        )
        for case_id, ground_truth_count in cases:
            with self.subTest(case=case_id):
                document = contract.parse_json_bytes(
                    contract.materialize_fixture_case(self.manifest, case_id)
                )
                registry = contract._IdentityRegistry()
                candidates = contract._validate_candidates(
                    document["candidate_profiles"], registry
                )
                samples, tuning_count, holdout_count = contract._validate_corpus(
                    document["corpus"], registry
                )
                results = contract._validate_results(
                    document["conformance_results"], registry, samples, candidates
                )
                incidents = [
                    result
                    for result in results.values()
                    if result["blinding_status"] == "self_identifying_output"
                ]
                self.assertEqual(len(incidents), 1)
                incident = incidents[0]
                self.assertEqual(incident["accounting"]["model_call_count"], 1)
                self.assertEqual(incident["terminal_status"], "blinding_failed")
                self.assertEqual(
                    {
                        incident["dimensions"][dimension]
                        for dimension in contract.QUALITY_DIMENSIONS
                        - {"schema_atom_stability"}
                    },
                    {"blinding_failed"},
                )
                ground_truth = contract._validate_human_ground_truth(
                    document["human_ground_truth"], registry, results, samples
                )
                self.assertEqual(len(document["human_ground_truth"]), ground_truth_count)
                self.assertEqual(ground_truth, {})
                provider_policy = copy.deepcopy(document["provider_policy"])
                provider_policy["residency_status"] = "proven"
                contract._validate_aggregate_report(
                    document["aggregate_report"],
                    candidates=candidates,
                    samples=samples,
                    tuning_count=tuning_count,
                    holdout_count=holdout_count,
                    results=results,
                    finding_count=0,
                    critical_count=0,
                    critical_false_accept_count=0,
                    review_count=0,
                    ground_truth_count=ground_truth_count,
                    provider_policy=provider_policy,
                )
                self.assertEqual(
                    contract.validate_fixture_case(self.manifest, case_id)["codes"],
                    ["CONTEXT_LIMIT_BINDING_UNPROVEN"],
                )

    def test_mapping_generation_zero_is_never_human_evidence(self) -> None:
        document = copy.deepcopy(self.base)
        result = document["conformance_results"][0]
        self._mark_primary_output(result)
        result["dimension_records"][1]["status"] = "human_pass"
        result_id = result["result_id"]
        records = [
            self._ground_truth(
                "00000000-0000-4000-8000-000000000081",
                "00000000-0000-4000-8000-000000000061",
                result_id,
                mapping=0,
            )
        ]
        registry, samples, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_human_ground_truth(records, registry, results, samples)
        self.assertEqual(
            raised.exception.code, "BLINDING_REPLACEMENT_MAPPING_INVALID"
        )

    def test_finding_review_provenance_obeys_blinding_and_global_identity(self) -> None:
        document = copy.deepcopy(self.base)
        self_identifying = document["conformance_results"][0]
        self._mark_primary_output(
            self_identifying, blinding="self_identifying_output"
        )
        self_identifying["failure_code"] = "BLINDING_FAILED"
        self_identifying["terminal_status"] = "blinding_failed"
        self_identifying["accounting"]["terminal_failure_count"] = 1
        for dimension in self_identifying["dimension_records"][1:]:
            dimension["status"] = "blinding_failed"

        blinded = document["conformance_results"][1]
        self._mark_primary_output(blinded, mapping=2)
        blinded["dimension_records"][1]["status"] = "human_pass"
        reviewer = "00000000-0000-4000-8000-000000000061"
        finding_id = "00000000-0000-4000-8000-000000000041"
        secondary_review = self._finding_review(
            "00000000-0000-4000-8000-000000000051",
            reviewer,
            finding_id,
            tier="secondary_unblinded",
            stage="secondary",
            blinding="unblinded",
        )
        finding = self._finding(
            finding_id,
            self_identifying["result_id"],
            [secondary_review],
        )
        registry, samples, results = self._validated_state(document)
        contract._validate_findings([finding], [], registry, results)
        ground_truth = [
            self._ground_truth(
                "00000000-0000-4000-8000-000000000081",
                reviewer,
                blinded["result_id"],
                mapping=2,
            ),
            self._ground_truth(
                "00000000-0000-4000-8000-000000000082",
                "00000000-0000-4000-8000-000000000062",
                blinded["result_id"],
                mapping=2,
            ),
        ]
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_human_ground_truth(
                ground_truth, registry, results, samples
            )
        self.assertEqual(raised.exception.code, "BLINDING_REVIEWER_REUSE")

        primary_on_self_identifying = copy.deepcopy(finding)
        primary_on_self_identifying["reviews"][0].update(
            {
                "evidence_tier": "primary_blinded",
                "review_stage": "initial",
                "reviewer_blinding": "never_unblinded",
            }
        )
        registry, _, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings(
                [primary_on_self_identifying], [], registry, results
            )
        self.assertEqual(raised.exception.code, "BLINDING_FINDING_REVIEW_INVALID")

        zero_mapping = copy.deepcopy(primary_on_self_identifying)
        zero_mapping["result_id"] = blinded["result_id"]
        zero_mapping["reviews"][0]["mapping_generation"] = 0
        registry, _, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings([zero_mapping], [], registry, results)
        self.assertEqual(raised.exception.code, "BLINDING_FINDING_REVIEW_INVALID")

    def test_external_mapping_finding_reviews_require_compromised_and_fresh_sets(self) -> None:
        document = copy.deepcopy(self.base)
        result = document["conformance_results"][0]
        self._mark_primary_output(
            result, blinding="external_mapping_leak", mapping=2
        )
        result_id = result["result_id"]
        finding_id = "00000000-0000-4000-8000-000000000041"
        finding = self._finding(
            finding_id,
            result_id,
            [
                self._finding_review(
                    "00000000-0000-4000-8000-000000000051",
                    "00000000-0000-4000-8000-000000000061",
                    finding_id,
                    tier="compromised_primary",
                    mapping=1,
                    blinding="unblinded",
                ),
                self._finding_review(
                    "00000000-0000-4000-8000-000000000052",
                    "00000000-0000-4000-8000-000000000062",
                    finding_id,
                    mapping=2,
                ),
            ],
        )
        registry, _, results = self._validated_state(document)
        contract._validate_findings([finding], [], registry, results)

        missing_fresh = copy.deepcopy(finding)
        missing_fresh["reviews"] = missing_fresh["reviews"][:1]
        registry, _, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings([missing_fresh], [], registry, results)
        self.assertEqual(raised.exception.code, "BLINDING_FINDING_REVIEW_INVALID")

    def test_reviewer_specific_severity_disagreement_requires_adjudication(self) -> None:
        document = copy.deepcopy(self.base)
        result = document["conformance_results"][0]
        self._mark_primary_output(result)
        finding_id = "00000000-0000-4000-8000-000000000041"
        review_ids = [
            "00000000-0000-4000-8000-000000000051",
            "00000000-0000-4000-8000-000000000052",
        ]
        finding = self._finding(
            finding_id,
            result["result_id"],
            [
                self._finding_review(
                    review_ids[0],
                    "00000000-0000-4000-8000-000000000061",
                    finding_id,
                    severity="medium",
                ),
                self._finding_review(
                    review_ids[1],
                    "00000000-0000-4000-8000-000000000062",
                    finding_id,
                    severity="high",
                ),
            ],
            severity="high",
        )
        registry, _, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings([finding], [], registry, results)
        self.assertEqual(raised.exception.code, "ADJUDICATION_REQUIRED")

        for changed_fields in (
            {"hard_fail": True, "mandatory_review": True},
            {"mandatory_review": True},
        ):
            disposition_disagreement = copy.deepcopy(finding)
            disposition_disagreement["severity"] = "medium"
            disposition_disagreement["hard_fail"] = changed_fields.get(
                "hard_fail", False
            )
            disposition_disagreement["mandatory_review"] = True
            for review in disposition_disagreement["reviews"]:
                review["severity"] = "medium"
                review["hard_fail"] = False
                review["mandatory_review"] = False
            disposition_disagreement["reviews"][1].update(changed_fields)
            registry, _, results = self._validated_state(document)
            with self.assertRaises(contract.ContractError) as raised:
                contract._validate_findings(
                    [disposition_disagreement], [], registry, results
                )
            self.assertEqual(raised.exception.code, "ADJUDICATION_REQUIRED")

        adjudication = self._finding_adjudication(
            "00000000-0000-4000-8000-000000000091",
            "00000000-0000-4000-8000-000000000063",
            finding_id,
            review_ids,
            severity="high",
        )
        registry, _, results = self._validated_state(document)
        findings, _, review_count = contract._validate_findings(
            [finding], [adjudication], registry, results
        )
        self.assertEqual(review_count, 3)
        self.assertTrue(findings[0]["confirmed"])
        self.assertEqual(findings[0]["severity"], "high")
        self.assertTrue(findings[0]["mandatory_review"])

        not_distinct = copy.deepcopy(adjudication)
        not_distinct["reviewer_id"] = finding["reviews"][0]["reviewer_id"]
        registry, _, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings([finding], [not_distinct], registry, results)
        self.assertEqual(raised.exception.code, "ADJUDICATOR_NOT_DISTINCT")

        wrong_links = copy.deepcopy(adjudication)
        wrong_links["initial_review_ids"] = [review_ids[0]]
        registry, _, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings([finding], [wrong_links], registry, results)
        self.assertEqual(raised.exception.code, "ADJUDICATION_LINK_INVALID")

        duplicate_initial = copy.deepcopy(finding)
        duplicate_initial["reviews"][1]["reviewer_id"] = duplicate_initial[
            "reviews"
        ][0]["reviewer_id"]
        registry, _, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings(
                [duplicate_initial], [copy.deepcopy(adjudication)], registry, results
            )
        self.assertEqual(raised.exception.code, "DUPLICATE_FINDING_REVIEWER")

        matching = copy.deepcopy(finding)
        matching["severity"] = "medium"
        matching["mandatory_review"] = False
        matching["reviews"][1]["severity"] = "medium"
        matching["reviews"][1]["mandatory_review"] = False
        registry, _, results = self._validated_state(document)
        matched, _, matched_count = contract._validate_findings(
            [matching], [], registry, results
        )
        self.assertTrue(matched[0]["confirmed"])
        self.assertEqual(matched_count, 2)

        duplicate_matching = copy.deepcopy(matching)
        duplicate_matching["reviews"][1]["reviewer_id"] = duplicate_matching[
            "reviews"
        ][0]["reviewer_id"]
        registry, _, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings(
                [duplicate_matching], [], registry, results
            )
        self.assertEqual(raised.exception.code, "DUPLICATE_FINDING_REVIEWER")

        registry, _, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings(
                [matching], [copy.deepcopy(adjudication)], registry, results
            )
        self.assertEqual(raised.exception.code, "ADJUDICATION_LINK_INVALID")

    def test_finding_outcome_is_required_and_top_level_downgrade_is_rejected(self) -> None:
        document = copy.deepcopy(self.base)
        result = document["conformance_results"][0]
        self._mark_primary_output(result)
        finding_id = "00000000-0000-4000-8000-000000000041"
        high_review = self._finding_review(
            "00000000-0000-4000-8000-000000000051",
            "00000000-0000-4000-8000-000000000061",
            finding_id,
            severity="high",
        )
        downgrade = self._finding(
            finding_id,
            result["result_id"],
            [high_review],
            severity="medium",
        )
        registry, _, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings([downgrade], [], registry, results)
        self.assertEqual(raised.exception.code, "FINDING_FINAL_OUTCOME_MISMATCH")

        missing_outcome = copy.deepcopy(downgrade)
        missing_outcome["reviews"][0].pop("severity")
        registry, _, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings([missing_outcome], [], registry, results)
        self.assertEqual(raised.exception.code, "MISSING_FIELD")

        no_review = self._finding(finding_id, result["result_id"], [])
        registry, _, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings([no_review], [], registry, results)
        self.assertEqual(raised.exception.code, "FINDING_REVIEW_OUTCOME_MISSING")

        model_only = self._finding(
            finding_id,
            result["result_id"],
            [
                self._finding_review(
                    "00000000-0000-4000-8000-000000000051",
                    "00000000-0000-4000-8000-000000000061",
                    finding_id,
                    severity="high",
                    tier="non_human",
                    mapping=0,
                    blinding="not_applicable",
                    role="model_reviewer",
                    credit="non_human",
                )
            ],
            severity="high",
        )
        registry, _, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings([model_only], [], registry, results)
        self.assertEqual(raised.exception.code, "MODEL_REVIEW_NOT_HUMAN")

        approved_document = copy.deepcopy(document)
        approved_document["conformance_results"][0]["editorial_status"] = (
            "editorially_approved"
        )
        registry, samples, results = self._validated_state(approved_document)
        high_finding = self._finding(
            finding_id,
            result["result_id"],
            [high_review],
            severity="high",
        )
        findings, _, _ = contract._validate_findings(
            [high_finding], [], registry, results
        )
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_acceptance(
                results, findings, {}, samples, {"complete": False}
            )
        self.assertEqual(raised.exception.code, "HIGH_RISK_EDITORIAL_APPROVAL")

    def test_no_output_rejects_findings_and_human_or_model_reviews(self) -> None:
        document = copy.deepcopy(self.base)
        result = document["conformance_results"][0]
        result["technical_conformance"] = "not_observed"
        result["terminal_status"] = "controlled_failure"
        result["failure_code"] = "CONTEXT_OVERFLOW_CONTROLLED"
        result["observed_atoms"] = []
        result["dimension_records"][0]["status"] = "not_evaluated"
        result["accounting"]["initial_attempt_count"] = 1
        result["accounting"]["terminal_failure_count"] = 1
        finding_id = "00000000-0000-4000-8000-000000000041"

        registry, _, results = self._validated_state(document)
        empty_review_finding = self._finding(
            finding_id, result["result_id"], [], severity="low"
        )
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings(
                [empty_review_finding], [], registry, results
            )
        self.assertEqual(raised.exception.code, "CONTENT_EVIDENCE_WITHOUT_OUTPUT")

        not_attempted_document = copy.deepcopy(self.base)
        registry, _, results = self._validated_state(not_attempted_document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings(
                [
                    self._finding(
                        finding_id,
                        not_attempted_document["conformance_results"][0][
                            "result_id"
                        ],
                        [],
                    )
                ],
                [],
                registry,
                results,
            )
        self.assertEqual(raised.exception.code, "CONTENT_EVIDENCE_WITHOUT_OUTPUT")

        model_review = self._finding_review(
            "00000000-0000-4000-8000-000000000051",
            "00000000-0000-4000-8000-000000000061",
            finding_id,
            tier="non_human",
            mapping=0,
            blinding="not_applicable",
            role="model_reviewer",
            credit="non_human",
        )
        registry, _, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_findings(
                [
                    self._finding(
                        finding_id,
                        result["result_id"],
                        [model_review],
                        severity="low",
                    )
                ],
                [],
                registry,
                results,
            )
        self.assertEqual(raised.exception.code, "CONTENT_EVIDENCE_WITHOUT_OUTPUT")

    def test_adjudicator_is_linked_distinct_and_drives_final_status(self) -> None:
        document = copy.deepcopy(self.base)
        result = document["conformance_results"][0]
        self._mark_primary_output(result)
        result["dimension_records"][1]["status"] = "human_pass"
        result_id = result["result_id"]
        first_id = "00000000-0000-4000-8000-000000000081"
        second_id = "00000000-0000-4000-8000-000000000082"
        records = [
            self._ground_truth(first_id, "00000000-0000-4000-8000-000000000061", result_id),
            self._ground_truth(second_id, "00000000-0000-4000-8000-000000000062", result_id, score=2, status="human_fail"),
            self._ground_truth(
                "00000000-0000-4000-8000-000000000083",
                "00000000-0000-4000-8000-000000000063",
                result_id,
                stage="adjudication",
                adjudicates=[first_id, second_id],
            ),
        ]
        registry, samples, results = self._validated_state(document)
        materialized = []
        contract._validate_human_ground_truth(
            records, registry, results, samples, materialized
        )
        self.assertEqual(len(materialized), 1)
        self.assertEqual(
            materialized[0]["reviewer_pair"],
            [
                "00000000-0000-4000-8000-000000000061",
                "00000000-0000-4000-8000-000000000062",
            ],
        )
        self.assertEqual(materialized[0]["first"], 4)
        self.assertEqual(materialized[0]["second"], 2)
        self.assertEqual(materialized[0]["split"], "tuning")
        self.assertEqual(
            materialized[0]["initial_record_ids"], [first_id, second_id]
        )
        self.assertIsNone(materialized[0]["applicability_adjudication"])
        self.assertEqual(
            contract.agreement_unit_vectors(materialized)[
                "paired_ratings_by_source"
            ],
            [((4, 2),)],
        )
        self.assertEqual(
            contract.agreement_diagnostic(materialized),
            {"split": "tuning", "status": "AGREEMENT_INSUFFICIENT_UNITS"},
        )
        with self.assertRaises(contract.ContractError) as raised:
            contract.agreement_gate(materialized)
        self.assertEqual(raised.exception.code, "DECISION_GRADE_SPLIT_INVALID")

        same_reviewer = copy.deepcopy(records)
        same_reviewer[2]["reviewer_id"] = same_reviewer[0]["reviewer_id"]
        registry, samples, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_human_ground_truth(
                same_reviewer, registry, results, samples
            )
        self.assertEqual(raised.exception.code, "ADJUDICATOR_NOT_DISTINCT")

    def test_not_applicable_pair_is_separate_and_one_sided_na_needs_adjudication(self) -> None:
        document = copy.deepcopy(self.base)
        result = document["conformance_results"][0]
        self._mark_primary_output(result)
        result["dimension_records"][1]["status"] = "not_applicable"
        result_id = result["result_id"]
        records = [
            self._ground_truth(
                "00000000-0000-4000-8000-000000000081",
                "00000000-0000-4000-8000-000000000061",
                result_id,
                status="not_applicable",
            ),
            self._ground_truth(
                "00000000-0000-4000-8000-000000000082",
                "00000000-0000-4000-8000-000000000062",
                result_id,
                status="not_applicable",
            ),
        ]
        registry, samples, results = self._validated_state(document)
        bilateral_materialized = []
        contract._validate_human_ground_truth(
            records, registry, results, samples, bilateral_materialized
        )
        bilateral_vectors = contract.agreement_unit_vectors(
            bilateral_materialized
        )
        self.assertEqual(
            bilateral_vectors["bilateral_not_applicable_source_count"], 1
        )
        self.assertEqual(bilateral_vectors["source_generation_ids"], [])

        mixed = self._agreement_rows([None], [None])
        numeric = copy.deepcopy(mixed[0])
        numeric["first"] = 2
        numeric["second"] = 3
        numeric["initial_record_ids"] = [
            "00000000-0000-4000-8000-000000008001",
            "00000000-0000-4000-8000-000000008002",
        ]
        numeric["result_id"] = "00000000-0000-4000-8000-000000008003"
        mixed.append(numeric)
        mixed_vectors = contract.agreement_unit_vectors(mixed)
        self.assertEqual(
            mixed_vectors["paired_ratings_by_source"], [((2, 3),)]
        )
        self.assertEqual(
            mixed_vectors["bilateral_not_applicable_source_count"], 0
        )

        unilateral = copy.deepcopy(records)
        unilateral[1]["status"] = "human_pass"
        unilateral[1]["applicability_reason"] = None
        unilateral[1]["ordinal_score"] = 4
        registry, samples, results = self._validated_state(document)
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_human_ground_truth(
                unilateral, registry, results, samples
            )
        self.assertEqual(raised.exception.code, "ADJUDICATION_REQUIRED")

        initial_ids = [row["ground_truth_id"] for row in unilateral]
        unilateral.append(
            self._ground_truth(
                "00000000-0000-4000-8000-000000000083",
                "00000000-0000-4000-8000-000000000063",
                result_id,
                stage="adjudication",
                adjudicates=initial_ids,
            )
        )
        document["conformance_results"][0]["dimension_records"][1]["status"] = (
            "human_pass"
        )
        registry, samples, results = self._validated_state(document)
        materialized = []
        contract._validate_human_ground_truth(
            unilateral, registry, results, samples, materialized
        )
        self.assertEqual(len(materialized), 1)
        self.assertIsNone(materialized[0]["first"])
        self.assertEqual(materialized[0]["second"], 4)
        self.assertEqual(
            materialized[0]["applicability_adjudication"],
            {
                "adjudication_id": "00000000-0000-4000-8000-000000000083",
                "adjudicator_reviewer_id": (
                    "00000000-0000-4000-8000-000000000063"
                ),
                "initial_record_ids": initial_ids,
            },
        )
        self.assertEqual(
            contract.agreement_diagnostic(materialized),
            {
                "split": "tuning",
                "status": "AGREEMENT_APPLICABILITY_DISAGREEMENT",
            },
        )

    def test_critical_false_accept_is_derived_only_after_actual_approval(self) -> None:
        document = copy.deepcopy(self.base)
        document["conformance_results"][0]["editorial_status"] = (
            "editorially_approved"
        )
        self._mark_primary_output(document["conformance_results"][0])
        registry, samples, results = self._validated_state(document)
        reviewers = (
            "00000000-0000-4000-8000-000000000061",
            "00000000-0000-4000-8000-000000000062",
        )

        def reviews(offset, finding_id, category):
            return [
                self._finding_review(
                    "00000000-0000-4000-8000-{0:012d}".format(
                        offset + index
                    ),
                    reviewer,
                    finding_id,
                    category=category,
                    dimension="meaning_accuracy",
                    severity="critical",
                    hard_fail=True,
                )
                for index, reviewer in enumerate(reviewers)
            ]

        result_id = document["conformance_results"][0]["result_id"]
        findings, _, _ = contract._validate_findings(
            [
                self._finding(
                    "00000000-0000-4000-8000-000000000041",
                    result_id,
                    reviews(
                        51,
                        "00000000-0000-4000-8000-000000000041",
                        "meaning_inversion",
                    ),
                    category="meaning_inversion",
                    dimension="meaning_accuracy",
                    severity="critical",
                    hard_fail=True,
                ),
                self._finding(
                    "00000000-0000-4000-8000-000000000042",
                    result_id,
                    reviews(
                        53,
                        "00000000-0000-4000-8000-000000000042",
                        "critical_false_accept",
                    ),
                    category="critical_false_accept",
                    dimension="meaning_accuracy",
                    severity="critical",
                    hard_fail=True,
                ),
            ],
            [],
            registry,
            results,
        )
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_acceptance(
                results, findings, {}, samples, {"complete": False}
            )
        self.assertEqual(raised.exception.code, "CRITICAL_FALSE_ACCEPT_DETECTED")

        safe_document = copy.deepcopy(self.base)
        self._mark_primary_output(safe_document["conformance_results"][0])
        registry, _, safe_results = self._validated_state(safe_document)
        safe_findings, _, _ = contract._validate_findings(
            [
                self._finding(
                    "00000000-0000-4000-8000-000000000041",
                    result_id,
                    reviews(
                        51,
                        "00000000-0000-4000-8000-000000000041",
                        "meaning_inversion",
                    ),
                    category="meaning_inversion",
                    dimension="meaning_accuracy",
                    severity="critical",
                    hard_fail=True,
                )
            ],
            [],
            registry,
            safe_results,
        )
        self.assertFalse(
            any(row["category"] == "critical_false_accept" for row in safe_findings)
        )

    def test_initial_finding_does_not_blanket_reject_separately_reviewed_repair(self) -> None:
        dimensions = {
            dimension: "human_pass"
            for dimension in contract.QUALITY_DIMENSIONS - {"schema_atom_stability"}
        }
        dimensions["schema_atom_stability"] = "synthetic_conformant"
        results = {
            "initial": {
                "editorial_status": "not_evaluated",
                "technical_conformance": "synthetic_conformant",
                "dimensions": dimensions,
                "sample_id": "sample",
                "terminal_status": "controlled_failure",
            },
            "repair": {
                "editorial_status": "editorially_approved",
                "technical_conformance": "synthetic_conformant",
                "dimensions": dimensions,
                "sample_id": "sample",
                "terminal_status": "success",
            },
        }
        findings = [
            {
                "category": "literary_error",
                "confirmed": True,
                "dimension": "literary_russian",
                "hard_fail": False,
                "mandatory_review": True,
                "result_id": "initial",
                "severity": "high",
            }
        ]
        ground_truth = {
            ("repair", dimension): {"reviewer"}
            for dimension in contract.QUALITY_DIMENSIONS - {"schema_atom_stability"}
        }
        contract._validate_acceptance(
            results,
            findings,
            ground_truth,
            {"sample": {"risk_class": "mandatory_human"}},
            {"complete": True},
        )

    def test_source_cluster_cannot_drift_across_primary_strata(self) -> None:
        corpus = copy.deepcopy(contract._EXPECTED_SYNTHETIC_CORPUS)
        corpus["samples"].append(
            {
                "expected_atoms": [
                    {
                        "atom_id": "00000000-0000-4000-8000-000000000095",
                        "kind": "placeholder",
                        "occurrence_id": "00000000-0000-4000-8000-000000000096",
                        "occurrence_index": 0,
                        "position_end": 17,
                        "position_policy": "exact_utf8_byte_span",
                        "position_start": 0,
                        "provenance": "synthetic",
                        "synthetic_value": "SYNTHETIC_CLUSTER",
                    }
                ],
                "risk_class": "mandatory_human",
                "sample_id": "00000000-0000-4000-8000-000000000099",
                "source_generation_id": "00000000-0000-4000-8000-000000000015",
                "source_unit_cluster_id": "00000000-0000-4000-8000-000000000013",
                "stratum": "ui",
            }
        )
        corpus["splits"]["tuning"].append(
            "00000000-0000-4000-8000-000000000099"
        )
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_corpus(corpus, contract._IdentityRegistry())
        self.assertEqual(raised.exception.code, "SOURCE_CLUSTER_STRATUM_MISMATCH")

    def test_source_cluster_cannot_change_source_generation(self) -> None:
        corpus = copy.deepcopy(contract._EXPECTED_SYNTHETIC_CORPUS)
        sample = copy.deepcopy(corpus["samples"][0])
        sample["sample_id"] = "00000000-0000-4000-8000-000000000099"
        sample["source_generation_id"] = (
            "00000000-0000-4000-8000-000000000098"
        )
        sample["expected_atoms"] = [
            {
                "atom_id": "00000000-0000-4000-8000-000000000095",
                "kind": "placeholder",
                "occurrence_id": "00000000-0000-4000-8000-000000000096",
                "occurrence_index": 0,
                "position_end": 20,
                "position_policy": "exact_utf8_byte_span",
                "position_start": 0,
                "provenance": "synthetic",
                "synthetic_value": "SYNTHETIC_GENERATION",
            }
        ]
        corpus["samples"].append(sample)
        corpus["splits"]["tuning"].append(sample["sample_id"])
        with self.assertRaises(contract.ContractError) as raised:
            contract._validate_corpus(corpus, contract._IdentityRegistry())
        self.assertEqual(
            raised.exception.code, "SOURCE_CLUSTER_GENERATION_MISMATCH"
        )

    def test_partial_report_cannot_carry_primary_human_evidence(self) -> None:
        document = copy.deepcopy(self.base)
        result = document["conformance_results"][0]
        self._mark_primary_output(result)
        result["dimension_records"][1]["status"] = "human_pass"
        result_id = result["result_id"]
        document["human_ground_truth"] = [
            self._ground_truth("00000000-0000-4000-8000-000000000081", "00000000-0000-4000-8000-000000000061", result_id),
            self._ground_truth("00000000-0000-4000-8000-000000000082", "00000000-0000-4000-8000-000000000062", result_id),
        ]
        with self.assertRaises(contract.ContractError) as raised:
            contract.validate_document(document)
        self.assertEqual(raised.exception.code, "PARTIAL_REPORT_EVIDENCE_FORBIDDEN")

    def test_live_observation_requires_context_then_external_implementation_identity(self) -> None:
        results = {
            "synthetic": {
                "accounting": {
                    field: (1 if field == "model_call_count" else 0)
                    for field in contract._ACCOUNTING_FIELDS
                }
            }
        }
        with self.assertRaises(contract.ContractError) as context_error:
            contract._validate_execution_policy(
                results,
                contract._EXPECTED_PROVIDER_CONTROLS,
                contract._EXPECTED_CONTEXT_LIMIT_BINDING,
                contract._EXPECTED_IMPLEMENTATION_IDENTITY,
            )
        self.assertEqual(context_error.exception.code, "CONTEXT_LIMIT_BINDING_UNPROVEN")
        with self.assertRaises(contract.ContractError) as implementation_error:
            contract._validate_execution_policy(
                results,
                contract._EXPECTED_PROVIDER_CONTROLS,
                {"status": "proven"},
                contract._EXPECTED_IMPLEMENTATION_IDENTITY,
            )
        self.assertEqual(
            implementation_error.exception.code,
            "EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN",
        )


class StrictJsonAndSchemaTests(unittest.TestCase):
    def test_validate_json_bytes_rejects_oversize_direct_input(self) -> None:
        payload = b"0" * (contract.MAX_INPUT_BYTES + 1)
        self.assertEqual(
            contract.validate_json_bytes(payload)["codes"],
            ["INPUT_SIZE_LIMIT"],
        )

    def test_fixture_materialization_cannot_amplify_past_input_limit(self) -> None:
        patch = {
            "operation": "copy_append",
            "source": ["items"],
            "target": ["items"],
        }
        manifest = {
            "schema": contract.FIXTURE_SCHEMA,
            "base_document": {"items": ["SYNTHETIC"]},
            "cases": [
                {
                    "id": "positive",
                    "expected": {
                        "status": "error",
                        "codes": ["INPUT_SIZE_LIMIT"],
                    },
                    "patches": [copy.deepcopy(patch) for _ in range(21)],
                }
            ],
        }
        manifest_bytes = json.dumps(
            manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode("ascii")
        self.assertLess(len(manifest_bytes), contract.MAX_INPUT_BYTES)
        self.assertEqual(
            contract.validate_fixture_case(manifest, "positive")["codes"],
            ["INPUT_SIZE_LIMIT"],
        )
        with self.assertRaises(contract.ContractError) as raised:
            contract.materialize_fixture_case(manifest, "positive")
        self.assertEqual(raised.exception.code, "INPUT_SIZE_LIMIT")

    def test_fixture_materialization_work_budget_is_cumulative(self) -> None:
        manifest = contract.parse_json_bytes(FIXTURE.read_bytes())
        self.assertEqual(
            contract.validate_fixture_case(
                manifest, "materialization-work-limit"
            )["codes"],
            ["MATERIALIZATION_WORK_LIMIT"],
        )
        with self.assertRaises(contract.ContractError) as raised:
            contract.materialize_fixture_case(
                manifest, "materialization-work-limit"
            )
        self.assertEqual(raised.exception.code, "MATERIALIZATION_WORK_LIMIT")

    def test_fixture_patch_count_is_closed_before_materialization(self) -> None:
        patch = {
            "operation": "set",
            "target": ["value"],
            "value": 0,
        }
        manifest = {
            "schema": contract.FIXTURE_SCHEMA,
            "base_document": {"value": 0},
            "cases": [
                {
                    "id": "positive",
                    "expected": {
                        "status": "error",
                        "codes": ["MATERIALIZATION_WORK_LIMIT"],
                    },
                    "patches": [
                        copy.deepcopy(patch)
                        for _ in range(contract.MAX_FIXTURE_PATCH_COUNT + 1)
                    ],
                }
            ],
        }
        self.assertEqual(
            contract.validate_fixture_case(manifest, "positive")["codes"],
            ["MATERIALIZATION_WORK_LIMIT"],
        )

    def test_materialization_budget_fails_before_unreserved_encoding(self) -> None:
        consumed = (
            contract.MAX_MATERIALIZATION_WORK_BYTES
            - contract.MATERIALIZATION_PREENCODE_RESERVE_BYTES
            + 1
        )
        with mock.patch.object(
            contract, "_encode_materialized_document"
        ) as encoder:
            with self.assertRaises(contract.ContractError) as raised:
                contract._consume_materialization_work(
                    {"synthetic": True}, consumed
                )
        self.assertEqual(raised.exception.code, "MATERIALIZATION_WORK_LIMIT")
        encoder.assert_not_called()

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
