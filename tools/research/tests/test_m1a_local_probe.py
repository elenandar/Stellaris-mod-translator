from __future__ import annotations

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

from tools.research import m1a_local_probe as probe


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPOSITORY_ROOT / "fixtures" / "m1a"
LEAKAGE_KEYS = {
    "checked_repository_files",
    "private_input_file_count",
    "nonempty_private_input_file_count",
    "source_file_fingerprint_count",
    "source_line_fingerprint_count",
    "source_token_fingerprint_count",
    "private_identifier_count",
    "match_count",
    "exact_file_match_count",
    "exact_line_match_count",
    "token_match_count",
    "private_value_match_count",
    "passed",
    "minimum_line_bytes",
    "minimum_token_bytes",
}


def _fixture_bytes(case: dict) -> bytes:
    if "utf8" in case:
        return case["utf8"].encode("utf-8")
    return bytes.fromhex(case["hex"])


class LocalProbeTests(unittest.TestCase):
    def _synthetic_repository(self, root: Path) -> Path:
        repository = root / "repository"
        candidate = repository / "fixtures" / "m1a" / "candidate"
        candidate.mkdir(parents=True)
        (candidate / "source-a.yml").write_bytes(
            b'l_synthetic:\n synthetic_a:0 "Synthetic A"\n'
        )
        (candidate / "source-b.yml").write_bytes(
            b'l_synthetic:\n synthetic_b:0 "Synthetic B"\n'
        )
        (repository / "README.md").write_text(
            "# Synthetic hermetic repository\n", encoding="utf-8"
        )
        return repository

    def _synthetic_home(self, root: Path) -> Path:
        home = root / "home"
        steamapps = home / "Library" / "Application Support" / "Steam" / "steamapps"
        game = steamapps / "common" / "Stellaris"
        official = game / "localisation" / "english"
        workshop_source = steamapps / "workshop" / "content" / "281990" / "opaque-source"
        workshop_loc = workshop_source / "localisation" / "english"
        documents = home / "Documents" / "Paradox Interactive" / "Stellaris"
        launcher = (
            home
            / "Library"
            / "Application Support"
            / "Paradox Interactive"
            / "launcher-v2"
        )
        for directory in (official, workshop_loc, documents, launcher):
            directory.mkdir(parents=True, exist_ok=True)
        private_marker = "PRIVATE" + "_SYNTHETIC_PROBE_MARKER"
        (official / "official.yml").write_bytes(
            ("\ufeffl_english:\n probe_official:0 \"Synthetic official\"\n").encode(
                "utf-8"
            )
        )
        (workshop_loc / "workshop.yml").write_bytes(
            ("\ufeffl_english:\n probe_workshop:0 \"" + private_marker + "\"\n").encode(
                "utf-8"
            )
        )
        (workshop_source / "descriptor.mod").write_text(
            'name="' + private_marker + '"\nsupported_version="4.4.*"\n',
            encoding="utf-8",
        )
        (documents / "dlc_load.json").write_text(
            json.dumps(
                {
                    "enabled_mods": ["mod/" + "opaque" + ".mod"],
                    "disabled_dlcs": [],
                }
            ),
            encoding="utf-8",
        )
        (game / "launcher-settings.json").write_text(
            json.dumps({"rawVersion": "v4.4.6", "checksum": "fdde"}),
            encoding="utf-8",
        )
        (launcher / "launcher-v2.sqlite").write_bytes(b"synthetic-not-opened-as-sqlite")
        return home

    def _fingerprints_for(
        self,
        data: bytes,
        *,
        role: str = "official",
    ) -> probe._PrivateInputFingerprints:
        path_id = "synthetic-path-id"
        located = probe.LocatedFile(
            role=role,
            source_id="synthetic-source-id",
            path=Path("/synthetic/private-input"),
            path_id=path_id,
        )
        return probe._private_input_fingerprints((located,), {path_id: data})

    def test_full_synthetic_collection_is_redacted_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = self._synthetic_home(root)
            repository = self._synthetic_repository(root)
            candidate_parent = root / "candidate-parent"
            candidate_parent.mkdir()
            result = probe.collect_evidence(
                home=home,
                repository_root=repository,
                candidate_temporary_parent=candidate_parent,
            )
            serialized = json.dumps(result, sort_keys=True)
            self.assertEqual(result["schema"], "m1a-local-redacted-evidence-v2")
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["corpus"]["file_count"], 2)
            self.assertTrue(result["corpus"]["pre_post_manifest_equal"])
            self.assertEqual(result["corpus"]["roundtrip_failure_count"], 0)
            self.assertTrue(result["candidate"]["identical"])
            self.assertTrue(result["leakage"]["passed"])
            self.assertEqual(set(result["leakage"]), LEAKAGE_KEYS)
            self.assertEqual(
                result["leakage"]["private_input_file_count"],
                result["corpus"]["observed_file_count_including_metadata"],
            )
            self.assertEqual(
                result["leakage"]["nonempty_private_input_file_count"],
                result["corpus"]["observed_file_count_including_metadata"],
            )
            self.assertIn(
                "CROSS_FILE_GENERATION_COHERENCE_UNPROVEN",
                result["blockers"],
            )
            self.assertIn(
                "CONCURRENT_SAME_UID_PATH_RACE_UNPROVEN",
                result["blockers"],
            )
            self.assertNotIn("PRIVATE" + "_SYNTHETIC_PROBE_MARKER", serialized)
            self.assertNotIn(str(home), serialized)

    def test_same_source_and_cross_source_duplicates_are_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = self._synthetic_home(root)
            repository = self._synthetic_repository(root)
            candidate_parent = root / "candidate-parent"
            candidate_parent.mkdir()
            steamapps = (
                home
                / "Library"
                / "Application Support"
                / "Steam"
                / "steamapps"
            )
            official = steamapps / "common" / "Stellaris" / "localisation" / "english"
            workshop = (
                steamapps
                / "workshop"
                / "content"
                / "281990"
                / "opaque-source"
                / "localisation"
                / "english"
            )
            (official / "official.yml").write_bytes(
                b'\xef\xbb\xbfl_english:\n shared_key:0 "Synthetic one"\n'
                b' shared_key:0 "Synthetic two"\n'
            )
            (official / "official-two.yml").write_bytes(
                b'\xef\xbb\xbfl_english:\n shared_key:0 "Synthetic three"\n'
            )
            (workshop / "workshop.yml").write_bytes(
                b'\xef\xbb\xbfl_english:\n shared_key:0 "Synthetic four"\n'
            )

            result = probe.collect_evidence(
                home=home,
                repository_root=repository,
                candidate_temporary_parent=candidate_parent,
            )
            duplicates = result["duplicates"]
            self.assertEqual(result["inventory"]["duplicate_key_groups"], 1)
            self.assertEqual(result["inventory"]["duplicate_key_occurrences"], 2)
            self.assertEqual(
                duplicates["same_source_cross_file_key_groups"],
                1,
            )
            self.assertEqual(
                duplicates["same_source_cross_file_occurrences"],
                3,
            )
            self.assertEqual(duplicates["cross_source_key_groups"], 1)
            self.assertEqual(duplicates["cross_source_occurrences"], 4)

    def test_format_inventory_and_key_extraction_share_fail_closed_boundary(self) -> None:
        manifest = json.loads((FIXTURE_ROOT / "format-cases.json").read_text("utf-8"))
        for case in manifest["cases"]:
            with self.subTest(case=case["id"]):
                payload = _fixture_bytes(case)
                inventory = probe.harness.inspect_bytes(payload).inventory
                self.assertEqual(
                    len(probe._entry_key_hashes(payload)),
                    inventory.entry_lines,
                )

    def test_invalid_entry_lines_never_affect_duplicate_metrics(self) -> None:
        invalid_values = (
            ("nul", "before\x00after"),
            ("c0_soh", "before\x01after"),
            ("c0_backspace", "before\x08after"),
            ("c0_escape", "before\x1bafter"),
            ("delete", "before\x7fafter"),
            ("c1_80", "before\x80after"),
            ("c1_9f", "before\x9fafter"),
            ("vertical_tab", "before\x0bafter"),
            ("form_feed", "before\x0cafter"),
            ("file_separator", "before\x1cafter"),
            ("group_separator", "before\x1dafter"),
            ("record_separator", "before\x1eafter"),
            ("next_line", "before\x85after"),
            ("line_separator", "before\u2028after"),
            ("paragraph_separator", "before\u2029after"),
        )
        for case_name, value in invalid_values:
            with self.subTest(case=case_name):
                payload = (
                    'l_synthetic:\n shared_key:0 "valid"\n shared_key:0 "'
                    + value
                    + '"\n'
                ).encode("utf-8")
                inventory = probe.harness.inspect_bytes(payload).inventory
                self.assertEqual(inventory.entry_lines, 1)
                self.assertEqual(inventory.duplicate_key_groups, 0)
                self.assertEqual(inventory.duplicate_key_occurrences, 0)
                self.assertEqual(len(probe._entry_key_hashes(payload)), 1)

        for malformed in (' shared_key:0"invalid"\n', ' shared_key:"invalid"\n'):
            with self.subTest(case="missing_value_separator"):
                payload = (
                    'l_synthetic:\n shared_key:0 "valid"\n' + malformed
                ).encode("utf-8")
                inventory = probe.harness.inspect_bytes(payload).inventory
                self.assertEqual(inventory.entry_lines, 1)
                self.assertEqual(inventory.duplicate_key_groups, 0)
                self.assertEqual(len(probe._entry_key_hashes(payload)), 1)

    def test_key_extraction_uses_only_cr_lf_and_crlf_physical_boundaries(self) -> None:
        for terminator in (b"\n", b"\r", b"\r\n"):
            with self.subTest(terminator=terminator):
                payload = terminator.join(
                    (
                        b"l_synthetic:",
                        b' first_key:0 "Synthetic"',
                        b' second_key:0 "Synthetic"',
                        b"",
                    )
                )
                inventory = probe.harness.inspect_bytes(payload).inventory
                self.assertEqual(inventory.entry_lines, 2)
                self.assertEqual(len(probe._entry_key_hashes(payload)), 2)

    def test_bare_cr_is_byte_preserved_and_blocks_transform_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = self._synthetic_home(root)
            repository = self._synthetic_repository(root)
            candidate_parent = root / "candidate-parent"
            candidate_parent.mkdir()
            official = (
                home
                / "Library"
                / "Application Support"
                / "Steam"
                / "steamapps"
                / "common"
                / "Stellaris"
                / "localisation"
                / "english"
                / "official.yml"
            )
            payload = (
                probe.harness.UTF8_BOM
                + b'l_english:\r synthetic_cr:0 "Synthetic CR"\r'
            )
            official.write_bytes(payload)
            self.assertEqual(
                probe.harness.inspect_bytes(payload).render_identity(),
                payload,
            )
            result = probe.collect_evidence(
                home=home,
                repository_root=repository,
                candidate_temporary_parent=candidate_parent,
            )
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["inventory"]["newline_styles"]["CR"], 1)
            self.assertGreaterEqual(result["format_blocker_count"], 1)
            self.assertIn("FORMAT_PROFILE_HAS_BLOCKERS", result["blockers"])

    def test_schema_v2_covers_leakage_and_controlled_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = self._synthetic_home(root)
            repository = self._synthetic_repository(root)
            candidate_parent = root / "candidate-parent"
            candidate_parent.mkdir()
            (repository / "synthetic-leak.txt").write_bytes(
                b'probe_workshop:0 "PRIVATE_SYNTHETIC_PROBE_MARKER"\n'
            )
            result = probe.collect_evidence(
                home=home,
                repository_root=repository,
                candidate_temporary_parent=candidate_parent,
            )
            self.assertEqual(result["schema"], "m1a-local-redacted-evidence-v2")
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["code"], "LEAKAGE_DETECTED")
            self.assertEqual(set(result["leakage"]), LEAKAGE_KEYS)
        self.assertEqual(
            probe._controlled_failure("SYNTHETIC_FAILURE")["schema"],
            "m1a-local-redacted-evidence-v2",
        )

    def test_all_observed_private_roles_are_fingerprinted_before_parsing(self) -> None:
        cases = (
            (
                "invalid_utf8_descriptor",
                "workshop_descriptor",
                b"\xff\xfePRIVATE_SYNTHETIC_DESCRIPTOR_BINARY",
            ),
            (
                "malformed_unquoted_descriptor",
                "workshop_descriptor",
                b"name=PRIVATE_SYNTHETIC_UNQUOTED_DESCRIPTOR\n",
            ),
            (
                "invalid_active_load_json",
                "active_load",
                b'{"enabled_mods":[PRIVATE_SYNTHETIC_ACTIVE_LOAD',
            ),
            (
                "exact_version_metadata",
                "version_metadata",
                b'{"rawVersion":"v4.4.6","checksum":"fdde"}',
            ),
            (
                "launcher_database_binary",
                "launcher_database",
                b"\x00\xffPRIVATE_SYNTHETIC_LAUNCHER_DATABASE_BINARY\x00",
            ),
            (
                "steam_discovery_metadata",
                "steam_library_metadata",
                b"\xffPRIVATE_SYNTHETIC_DISCOVERY_METADATA",
            ),
        )
        for case_name, role, payload in cases:
            with self.subTest(case=case_name):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary).resolve()
                    home = self._synthetic_home(root)
                    repository = self._synthetic_repository(root)
                    candidate_parent = root / "candidate-parent"
                    candidate_parent.mkdir()
                    steamapps = (
                        home
                        / "Library"
                        / "Application Support"
                        / "Steam"
                        / "steamapps"
                    )
                    paths = {
                        "workshop_descriptor": (
                            steamapps
                            / "workshop"
                            / "content"
                            / "281990"
                            / "opaque-source"
                            / "descriptor.mod"
                        ),
                        "active_load": (
                            home
                            / "Documents"
                            / "Paradox Interactive"
                            / "Stellaris"
                            / "dlc_load.json"
                        ),
                        "version_metadata": (
                            steamapps
                            / "common"
                            / "Stellaris"
                            / "launcher-settings.json"
                        ),
                        "launcher_database": (
                            home
                            / "Library"
                            / "Application Support"
                            / "Paradox Interactive"
                            / "launcher-v2"
                            / "launcher-v2.sqlite"
                        ),
                        "steam_library_metadata": steamapps / "libraryfolders.vdf",
                    }
                    private_input = paths[role]
                    private_input.write_bytes(payload)
                    (repository / (case_name + ".bin")).write_bytes(payload)
                    result = probe.collect_evidence(
                        home=home,
                        repository_root=repository,
                        candidate_temporary_parent=candidate_parent,
                    )
                    serialized = json.dumps(result, sort_keys=True)
                    self.assertEqual(result["status"], "blocked")
                    self.assertEqual(result["code"], "LEAKAGE_DETECTED")
                    self.assertEqual(set(result["leakage"]), LEAKAGE_KEYS)
                    self.assertGreaterEqual(
                        result["leakage"]["exact_file_match_count"],
                        1,
                    )
                    self.assertNotIn("PRIVATE_SYNTHETIC", serialized)
                    self.assertNotIn(payload.hex(), serialized)
                    self.assertNotIn(str(home), serialized)
                    self.assertNotIn(str(repository), serialized)

    def test_language_header_line_exception_is_localisation_only(self) -> None:
        header_body = b"l_synthetic:"
        digest = hashlib.sha256(header_body).digest()
        for terminator in (b"", b"\r", b"\n", b"\r\n"):
            with self.subTest(terminator=terminator):
                localisation = self._fingerprints_for(
                    header_body + terminator,
                    role="official",
                )
                bom_localisation = self._fingerprints_for(
                    probe.harness.UTF8_BOM + header_body + terminator,
                    role="official",
                )
                self.assertNotIn(digest, localisation.line_hashes)
                self.assertFalse(localisation.line_hashes)
                self.assertFalse(bom_localisation.line_hashes)

        header = header_body + b"\n"
        bom_header = probe.harness.UTF8_BOM + header
        metadata = self._fingerprints_for(header, role="version_metadata")
        bom_metadata = self._fingerprints_for(
            bom_header,
            role="version_metadata",
        )
        later_header = self._fingerprints_for(
            b"l_synthetic:\nl_private_later:\n",
            role="official",
        )
        later_digest = hashlib.sha256(b"l_private_later:").digest()
        self.assertIn(later_digest, later_header.line_hashes)
        self.assertIn(digest, metadata.line_hashes)
        self.assertTrue(bom_metadata.line_hashes)
        self.assertEqual(
            self._fingerprints_for(header, role="official").file_hashes,
            metadata.file_hashes,
        )

    def test_language_header_line_exception_rejects_malformed_bytes(self) -> None:
        malformed = {
            "leading_space": b" l_synthetic:\n",
            "trailing_space": b"l_synthetic: \n",
            "trailing_tab": b"l_synthetic:\t\n",
            "leading_vertical_tab": b"\x0bl_synthetic:\n",
            "trailing_form_feed": b"l_synthetic:\x0c\n",
            "embedded_control": b"l_synthetic:\x00\n",
            "bom_after_space": b" " + probe.harness.UTF8_BOM + b"l_synthetic:\n",
            "bom_after_byte": b"x" + probe.harness.UTF8_BOM + b"l_synthetic:\n",
        }
        for case_name, payload in malformed.items():
            with self.subTest(case=case_name):
                fingerprints = self._fingerprints_for(payload, role="official")
                self.assertTrue(fingerprints.line_hashes)

    def test_malformed_header_partial_leak_blocks_with_redacted_cli(self) -> None:
        marker = "l_PRIVATE_SYNTHETIC_HEADER_BYPASS:"
        marker_bytes = marker.encode("ascii")
        source = b" " + marker_bytes + b"\t\n key:0 \"Synthetic\"\n"
        leaked_line = b" " + marker_bytes + b"\t\n"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = self._synthetic_home(root)
            repository = self._synthetic_repository(root)
            candidate_parent = root / "candidate-parent"
            candidate_parent.mkdir()
            official = (
                home
                / "Library"
                / "Application Support"
                / "Steam"
                / "steamapps"
                / "common"
                / "Stellaris"
                / "localisation"
                / "english"
                / "official.yml"
            )
            leaked_file = repository / "malformed-header-partial.bin"
            official.write_bytes(source)
            leaked_file.write_bytes(leaked_line)

            result = probe.collect_evidence(
                home=home,
                repository_root=repository,
                candidate_temporary_parent=candidate_parent,
            )
            leakage = result["leakage"]
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["code"], "LEAKAGE_DETECTED")
            self.assertFalse(leakage["passed"])
            self.assertEqual(leakage["exact_file_match_count"], 0)
            self.assertGreaterEqual(leakage["exact_line_match_count"], 1)
            self.assertGreaterEqual(leakage["match_count"], 1)

            output = io.StringIO()
            with mock.patch.object(probe, "collect_evidence", return_value=result):
                with mock.patch.object(sys, "stdout", output):
                    exit_code = probe.main(["collect"])
            serialized = output.getvalue()
            self.assertEqual(exit_code, 2)
            self.assertEqual(json.loads(serialized), result)
            for private_value in (
                marker,
                "PRIVATE_SYNTHETIC_HEADER_BYPASS",
                hashlib.sha256(source).hexdigest(),
                hashlib.sha256(marker_bytes).hexdigest(),
                official.name,
                leaked_file.name,
                str(home),
                str(repository),
                str(official),
            ):
                self.assertNotIn(private_value, serialized)

    def test_invalid_utf8_long_token_leak_is_detected_without_replacement(self) -> None:
        token = (
            b"PRIVATE_SYNTHETIC_BINARY_TOKEN_"
            b"0123456789_ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"
        )
        private_data = b"\xffbinary-prefix " + token + b" binary-suffix\x00"
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary).resolve()
            (repository / "partial.bin").write_bytes(b"repository " + token + b" tail")
            result = probe._leakage_evidence(
                repository,
                self._fingerprints_for(private_data, role="launcher_database"),
                set(),
            )
        serialized = json.dumps(result, sort_keys=True)
        self.assertFalse(result["passed"])
        self.assertEqual(result["exact_file_match_count"], 0)
        self.assertGreaterEqual(result["token_match_count"], 1)
        self.assertNotIn(token.decode("ascii"), serialized)

    def test_leakage_cli_exit_is_nonzero_and_serialized_output_is_redacted(self) -> None:
        marker = "PRIVATE_SYNTHETIC_LEAKAGE_OUTPUT_MARKER"
        leakage = {
            "checked_repository_files": 1,
            "private_input_file_count": 1,
            "nonempty_private_input_file_count": 1,
            "source_file_fingerprint_count": 1,
            "source_line_fingerprint_count": 1,
            "source_token_fingerprint_count": 0,
            "private_identifier_count": 0,
            "match_count": 1,
            "exact_file_match_count": 1,
            "exact_line_match_count": 0,
            "token_match_count": 0,
            "private_value_match_count": 0,
            "passed": False,
            "minimum_line_bytes": probe.MIN_PRIVATE_LINE_BYTES,
            "minimum_token_bytes": probe.MIN_PRIVATE_TOKEN_BYTES,
        }
        evidence = {
            "schema": probe.SCHEMA,
            "status": "blocked",
            "code": "LEAKAGE_DETECTED",
            "leakage": leakage,
        }
        output = io.StringIO()
        with mock.patch.object(probe, "collect_evidence", return_value=evidence):
            with mock.patch.object(sys, "stdout", output):
                exit_code = probe.main(["collect"])
        serialized = output.getvalue()
        self.assertEqual(exit_code, 2)
        self.assertEqual(json.loads(serialized), evidence)
        self.assertNotIn(marker, serialized)

    def test_leakage_result_contains_only_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            candidate = root / "candidate.md"
            candidate.write_bytes(b"PRIVATE_SEQUENCE_FOR_BOOLEAN_ONLY\n")
            source_hashes = {
                __import__("hashlib")
                .sha256(b"PRIVATE_SEQUENCE_FOR_BOOLEAN_ONLY")
                .digest()
            }
            fingerprints = probe._PrivateInputFingerprints(
                observed_file_count=1,
                nonempty_file_count=1,
                file_hashes=frozenset(),
                line_hashes=frozenset(source_hashes),
                token_hashes=frozenset(),
            )
            result = probe._leakage_evidence(root, fingerprints, set())
            serialized = json.dumps(result, sort_keys=True)
            self.assertFalse(result["passed"])
            self.assertEqual(result["match_count"], 1)
            self.assertNotIn("PRIVATE_SEQUENCE_FOR_BOOLEAN_ONLY", serialized)

    def test_repository_scan_rejects_symlinked_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            target = root / "target"
            target.mkdir()
            repository = root / "repository"
            repository.mkdir()
            (repository / "README.md").write_text(
                "# Synthetic\n",
                encoding="utf-8",
            )
            (repository / "alias").symlink_to(target, target_is_directory=True)
            with self.assertRaises(probe.ProbeError) as raised:
                probe._repository_files(repository)
            self.assertEqual(raised.exception.code, "REPOSITORY_SCAN_FAILED")

    def test_short_exact_and_partial_token_leaks_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "short.bin").write_bytes(b"SHORT_LEAK\n")
            (root / "partial.bin").write_bytes(
                b"prefix PRIVATE_TOKEN_FRAGMENT_WITH_LONG_SUFFIX_0123456789_ABCDEFGHIJKLMNOPQRSTUVWXYZ suffix\n"
            )
            source = b"SHORT_LEAK\nsource PRIVATE_TOKEN_FRAGMENT_WITH_LONG_SUFFIX_0123456789_ABCDEFGHIJKLMNOPQRSTUVWXYZ tail\n"
            result = probe._leakage_evidence(
                root,
                self._fingerprints_for(source),
                set(),
            )
            self.assertFalse(result["passed"])
            self.assertGreaterEqual(result["match_count"], 2)

    def test_version_and_active_metadata_require_exact_schema(self) -> None:
        self.assertTrue(
            probe._version_matches(b'{"rawVersion":"v4.4.6","checksum":"fdde"}')
        )
        self.assertFalse(
            probe._version_matches(b'{"note":"v4.4.6 fdde"}')
        )
        self.assertFalse(
            probe._version_matches(
                b'{"rawVersion":"v4.4.60","checksum":"xfddey"}'
            )
        )
        self.assertFalse(
            probe._version_matches(
                b'{"rawVersion":"v4.4.6","checksum":"fdde","extra":true}'
            )
        )
        self.assertFalse(
            probe._version_matches(
                b'{"rawVersion":"v0.0.0","rawVersion":"v4.4.6",'
                b'"checksum":"fdde"}'
            )
        )
        self.assertFalse(
            probe._version_matches(
                b'{"rawVersion":"v4.4.6","gameVersion":"v0.0.0",'
                b'"checksum":"fdde"}'
            )
        )
        for payload in (b"[]", b"{}", b'{"disabled_dlcs":[]}'):
            self.assertFalse(probe._active_load_evidence(payload, set())["valid_json"])
        self.assertTrue(
            probe._active_load_evidence(
                b'{"enabled_mods":[],"disabled_dlcs":[]}', set()
            )["valid_json"]
        )
        private_values = set()
        evidence = probe._active_load_evidence(
            b'{"enabled_mods":[],"disabled_dlcs":["PRIVATE_DISABLED_VALUE"],'
            b'"unknown_field":"PRIVATE_UNKNOWN_VALUE"}',
            private_values,
        )
        self.assertFalse(evidence["valid_json"])
        self.assertEqual(evidence["disabled_dlc_count"], 1)
        self.assertIn(b"PRIVATE_DISABLED_VALUE", private_values)
        self.assertIn(b"PRIVATE_UNKNOWN_VALUE", private_values)

        duplicate_values = set()
        duplicate = probe._active_load_evidence(
            b'{"enabled_mods":["PRIVATE_OVERWRITTEN_VALUE"],'
            b'"enabled_mods":[],"disabled_dlcs":[]}',
            duplicate_values,
        )
        self.assertFalse(duplicate["valid_json"])
        self.assertEqual(duplicate["enabled_count"], 0)
        self.assertIn(b"PRIVATE_OVERWRITTEN_VALUE", duplicate_values)

    def test_header_profile_requires_one_nonempty_first_header(self) -> None:
        cases = (
            (b"l_synthetic:\n synthetic:0 \"v\"\n", "other"),
            (b"l_:\n synthetic:0 \"v\"\n", "missing_or_multiple"),
            (b"# comment\nl_synthetic:\n synthetic:0 \"v\"\n", "misplaced"),
            (
                b"l_synthetic:\nl_second:\n synthetic:0 \"v\"\n",
                "missing_or_multiple",
            ),
            (b" l_synthetic:\n synthetic:0 \"v\"\n", "missing_or_multiple"),
            (b"synthetic:0 \"v\"\n", "missing_or_multiple"),
        )
        for payload, expected in cases:
            with self.subTest(expected=expected, size=len(payload)):
                inventory = probe.harness.inspect_bytes(payload).inventory
                self.assertEqual(
                    probe._header_class(payload, inventory.language_header_lines),
                    expected,
                )

    def test_descriptor_unknown_or_malformed_syntax_is_counted(self) -> None:
        private_values = set()
        valid = probe._descriptor_evidence(
            b'name="Synthetic"\ndependencies={\n"Synthetic dependency"\n}\n',
            private_values,
        )
        self.assertEqual(valid["unsupported_syntax_occurrences"], 0)
        self.assertEqual(valid["unterminated_block_count"], 0)
        self.assertEqual(valid["dependency_value_count"], 1)

        malformed = probe._descriptor_evidence(
            b'name=unquoted\nbroken line\nbad-field?="Synthetic"\ndependencies={\n"Open"\n',
            set(),
        )
        self.assertGreaterEqual(malformed["unsupported_syntax_occurrences"], 4)
        self.assertEqual(malformed["unterminated_block_count"], 1)

    def test_discovery_seeds_full_private_home_path_for_leakage_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = self._synthetic_home(root)
            discovery = probe.discover(home)
            repository = root / "leak-repository"
            repository.mkdir()
            (repository / "path.bin").write_bytes(str(home).encode("utf-8"))
            result = probe._leakage_evidence(
                repository,
                probe._private_input_fingerprints((), {}),
                set(discovery.private_path_values),
            )
            self.assertFalse(result["passed"])
            self.assertGreaterEqual(result["private_value_match_count"], 1)

    def test_invalid_cli_argument_is_not_echoed(self) -> None:
        marker = "PRIVATE_ARGUMENT_MARKER"
        script = REPOSITORY_ROOT / "tools" / "research" / "m1a_local_probe.py"
        completed = subprocess.run(
            [sys.executable, str(script), "collect", marker],
            cwd=str(REPOSITORY_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertNotIn(marker.encode("ascii"), completed.stdout + completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["code"], "INVALID_ARGUMENTS")
        self.assertEqual(output["schema"], "m1a-local-redacted-evidence-v2")

    def test_discovery_blocks_relative_library_and_rejects_workshop_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = root / "home"
            steamapps = home / "Library" / "Application Support" / "Steam" / "steamapps"
            steamapps.mkdir(parents=True)
            (steamapps / "libraryfolders.vdf").write_text(
                '"path" "relative/library"\n', encoding="utf-8"
            )
            discovery = probe.discover(home)
            self.assertFalse(discovery.steam_library_metadata_valid)
            self.assertEqual(len(discovery.discovery_metadata_files), 1)
            self.assertEqual(
                discovery.discovery_metadata_fingerprints.observed_file_count,
                1,
            )

            (steamapps / "libraryfolders.vdf").unlink()
            workshop = steamapps / "workshop" / "content" / "281990"
            target = root / "target"
            workshop.mkdir(parents=True)
            target.mkdir()
            (workshop / "alias").symlink_to(target, target_is_directory=True)
            with self.assertRaises(probe.ProbeError) as raised:
                probe.discover(home)
            self.assertEqual(raised.exception.code, "SOURCE_SYMLINK_REJECTED")

    def test_between_discovery_mutation_aborts_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = self._synthetic_home(root)
            repository = self._synthetic_repository(root)
            candidate_parent = root / "candidate-parent"
            candidate_parent.mkdir()
            official = (
                home
                / "Library"
                / "Application Support"
                / "Steam"
                / "steamapps"
                / "common"
                / "Stellaris"
                / "localisation"
                / "english"
                / "official.yml"
            )

            def mutate() -> None:
                official.write_bytes(
                    b'\xef\xbb\xbfl_english:\n changed_key:0 "Synthetic changed"\n'
                )

            with self.assertRaises(probe.ProbeError) as raised:
                probe.collect_evidence(
                    home=home,
                    repository_root=repository,
                    candidate_temporary_parent=candidate_parent,
                    between_discovery_hook=mutate,
                )
            self.assertEqual(raised.exception.code, "GENERATION_MISMATCH")

    def test_hardlink_alias_inserted_after_preflight_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = self._synthetic_home(root)
            repository = self._synthetic_repository(root)
            candidate_parent = root / "candidate-parent"
            candidate_parent.mkdir()
            real_read = probe.harness.read_stable_file
            first_path = None
            call_count = 0

            def insert_alias(file_path: Path, **kwargs: object):
                nonlocal first_path, call_count
                current = Path(file_path)
                if first_path is None:
                    first_path = current
                elif call_count == 1:
                    current.unlink()
                    os.link(first_path, current)
                call_count += 1
                return real_read(current, **kwargs)

            with mock.patch.object(
                probe.harness,
                "read_stable_file",
                side_effect=insert_alias,
            ):
                with self.assertRaises(probe.ProbeError) as raised:
                    probe.collect_evidence(
                        home=home,
                        repository_root=repository,
                        candidate_temporary_parent=candidate_parent,
                    )
            self.assertEqual(raised.exception.code, "SOURCE_IDENTITY_ALIAS")


if __name__ == "__main__":
    unittest.main()
