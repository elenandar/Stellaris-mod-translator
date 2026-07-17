from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.research import m1a_local_probe as probe


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


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
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["corpus"]["file_count"], 2)
            self.assertTrue(result["corpus"]["pre_post_manifest_equal"])
            self.assertEqual(result["corpus"]["roundtrip_failure_count"], 0)
            self.assertTrue(result["candidate"]["identical"])
            self.assertTrue(result["leakage"]["passed"])
            self.assertNotIn("PRIVATE" + "_SYNTHETIC_PROBE_MARKER", serialized)
            self.assertNotIn(str(home), serialized)

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
            result = probe._leakage_evidence(root, source_hashes, set(), set())
            serialized = json.dumps(result, sort_keys=True)
            self.assertFalse(result["passed"])
            self.assertEqual(result["match_count"], 1)
            self.assertNotIn("PRIVATE_SEQUENCE_FOR_BOOLEAN_ONLY", serialized)

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
                probe._line_fingerprints(source),
                probe._token_fingerprints(source),
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
                set(),
                set(),
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
        self.assertEqual(json.loads(completed.stdout)["code"], "INVALID_ARGUMENTS")

    def test_discovery_rejects_relative_library_and_workshop_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = root / "home"
            steamapps = home / "Library" / "Application Support" / "Steam" / "steamapps"
            steamapps.mkdir(parents=True)
            (steamapps / "libraryfolders.vdf").write_text(
                '"path" "relative/library"\n', encoding="utf-8"
            )
            with self.assertRaises(probe.ProbeError) as raised:
                probe.discover(home)
            self.assertEqual(raised.exception.code, "STEAM_LIBRARY_METADATA_INVALID")

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


if __name__ == "__main__":
    unittest.main()
