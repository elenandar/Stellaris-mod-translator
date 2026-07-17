from __future__ import annotations

from dataclasses import replace
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.research import m1a_harness as harness


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPOSITORY_ROOT / "fixtures" / "m1a"


def _fixture_bytes(case: dict) -> bytes:
    if "utf8" in case:
        return case["utf8"].encode("utf-8")
    return bytes.fromhex(case["hex"])


def _assert_expected(test: unittest.TestCase, actual: dict, expected: dict) -> None:
    for key, value in expected.items():
        test.assertIn(key, actual)
        if isinstance(value, dict):
            test.assertIsInstance(actual[key], dict)
            _assert_expected(test, actual[key], value)
        else:
            test.assertEqual(actual[key], value, key)


class FormatInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        manifest = json.loads((FIXTURE_ROOT / "format-cases.json").read_text("utf-8"))
        cls.cases = manifest["cases"]

    def test_fixture_classifications_and_identity_round_trip(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["id"]):
                source = _fixture_bytes(case)
                document = harness.inspect_bytes(source)
                self.assertEqual(document.render_identity(), source)
                _assert_expected(
                    self,
                    document.inventory.public_dict(),
                    case["expected"],
                )

    def test_unknown_and_malformed_bytes_remain_opaque_and_unchanged(self) -> None:
        selected = {
            case["id"]: case
            for case in self.cases
            if case["id"]
            in ("unknown-markup-is-opaque", "malformed-entry-is-opaque", "invalid-utf8")
        }
        self.assertEqual(len(selected), 3)
        for case in selected.values():
            source = _fixture_bytes(case)
            document = harness.inspect_bytes(source)
            self.assertGreater(document.inventory.opaque_constructs, 0)
            self.assertEqual(document.render_identity(), source)

    def test_inventory_never_returns_keys_or_text_spans(self) -> None:
        source = b'l_synthetic:\n private_marker_key:0 "PRIVATE_MARKER_VALUE"\n'
        public = json.dumps(
            harness.inspect_bytes(source).inventory.public_dict(),
            sort_keys=True,
        ).encode("ascii")
        self.assertNotIn(b"private_marker_key", public)
        self.assertNotIn(b"PRIVATE_MARKER_VALUE", public)

    def test_ambiguous_markup_cases_are_isolated_and_fail_closed(self) -> None:
        cases = (
            ("$$", 1),
            ("[syn.scope", 1),
            ("syn.scope]", 1),
            ("££", 1),
            ("£syn_icon", 1),
            ("§!Synthetic", 1),
            ("§YSynthetic", 1),
            ("Synthetic§", 1),
            ("[syn[inner]]", 2),
            ("$SYN[scope$]", 2),
            ("£syn[scope£]", 2),
            ("§Y$SYN§!_TOKEN$", 2),
        )
        for value, expected_unknown in cases:
            with self.subTest(case_index=cases.index((value, expected_unknown))):
                source = (
                    'l_synthetic:\n synthetic_case:0 "' + value + '"\n'
                ).encode("utf-8")
                document = harness.inspect_bytes(source)
                inventory = document.inventory
                self.assertEqual(document.render_identity(), source)
                self.assertEqual(inventory.entry_lines, 1)
                self.assertEqual(inventory.malformed_lines, 0)
                self.assertEqual(inventory.unknown_lines, 0)
                self.assertEqual(
                    inventory.markup.unknown_or_ambiguous,
                    expected_unknown,
                )
                self.assertEqual(inventory.opaque_constructs, expected_unknown)
                self.assertEqual(inventory.markup.placeholders, 0)
                self.assertEqual(inventory.markup.icons, 0)
                self.assertEqual(inventory.markup.scripted_localisation, 0)
                self.assertEqual(inventory.markup.formatting_spans, 0)


class StableReadTests(unittest.TestCase):
    def _source(self, root: Path, data: bytes = b"synthetic-stable-bytes") -> Path:
        path = root / "opaque-source.bin"
        path.write_bytes(data)
        return path.resolve()

    def test_short_os_reads_are_accumulated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = self._source(Path(temporary).resolve(), b"0123456789")

            def short_reader(fd: int, requested: int, _pass: int, _chunk: int) -> bytes:
                return os.read(fd, min(requested, 2))

            result = harness.read_stable_file(source, reader=short_reader)
            self.assertEqual(result.data, b"0123456789")

    def test_premature_eof_is_a_clean_partial_read_abort(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = self._source(Path(temporary).resolve(), b"0123456789")

            def premature_reader(fd: int, _requested: int, pass_index: int, chunk: int) -> bytes:
                if pass_index == 1 and chunk > 0:
                    return b""
                return os.read(fd, 1)

            with self.assertRaises(harness.HarnessError) as raised:
                harness.read_stable_file(source, reader=premature_reader)
            self.assertEqual(raised.exception.code, "PARTIAL_READ")

    def test_in_place_generation_change_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = self._source(Path(temporary).resolve(), b"A" * 32)
            changed = False

            def mutate(event: str, pass_index: int, chunk: int) -> None:
                nonlocal changed
                if event == "after_chunk" and pass_index == 1 and chunk == 0 and not changed:
                    source.write_bytes(b"B" * 32)
                    changed = True

            with self.assertRaises(harness.HarnessError) as raised:
                harness.read_stable_file(source, chunk_size=8, hook=mutate)
            self.assertEqual(raised.exception.code, "GENERATION_MISMATCH")

    def test_replacement_between_metadata_and_open_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = self._source(root, b"same-size-original")
            replacement = root / "replacement.bin"
            replacement.write_bytes(b"same-size-replace!")
            replaced = False

            def replace_source(event: str, _pass: int, _chunk: int) -> None:
                nonlocal replaced
                if event == "after_metadata" and not replaced:
                    os.replace(str(replacement), str(source))
                    replaced = True

            with self.assertRaises(harness.HarnessError) as raised:
                harness.read_stable_file(source, hook=replace_source)
            self.assertEqual(raised.exception.code, "GENERATION_MISMATCH")

    def test_symlink_substitution_before_final_recheck_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = self._source(root)
            other = root / "other.bin"
            other.write_bytes(b"synthetic-other-bytes")
            substituted = False

            def substitute(event: str, _pass: int, _chunk: int) -> None:
                nonlocal substituted
                if event == "before_path_recheck" and not substituted:
                    source.unlink()
                    source.symlink_to(other)
                    substituted = True

            with self.assertRaises(harness.HarnessError) as raised:
                harness.read_stable_file(source, hook=substitute)
            self.assertEqual(raised.exception.code, "GENERATION_MISMATCH")

    def test_source_symlink_is_rejected_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = self._source(root)
            alias = root / "source-alias.bin"
            alias.symlink_to(source)
            with self.assertRaises(harness.HarnessError) as raised:
                harness.read_stable_file(alias)
            self.assertEqual(raised.exception.code, "SOURCE_SYMLINK_REJECTED")

    def test_duplicate_relative_paths_abort_before_any_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            first = self._source(root)
            second = root / "second.bin"
            second.write_bytes(b"synthetic-second")
            requests = [
                harness.SourceRequest(first, "opaque/same.yml"),
                harness.SourceRequest(second.resolve(), "opaque/same.yml"),
            ]
            with self.assertRaises(harness.HarnessError) as raised:
                harness.snapshot_sources(requests)
            self.assertEqual(raised.exception.code, "DUPLICATE_RELATIVE_PATH")

    def test_observed_hardlink_source_identity_alias_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            first = self._source(root)
            alias = root / "hardlink-alias.bin"
            os.link(str(first), str(alias))
            requests = [
                harness.SourceRequest(first, "opaque/first.yml"),
                harness.SourceRequest(alias.resolve(), "opaque/second.yml"),
            ]
            with self.assertRaises(harness.HarnessError) as raised:
                harness.snapshot_sources(requests)
            self.assertEqual(raised.exception.code, "SOURCE_IDENTITY_ALIAS")


class RootContainmentTests(unittest.TestCase):
    def test_disjoint_existing_roots_are_sealed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            protected = base / "protected"
            output = base / "output"
            protected.mkdir()
            output.mkdir()
            seal = harness.seal_disposable_root(output, [protected])
            seal.verify()
            self.assertTrue(seal.opaque_root_id.startswith("root-"))
            self.assertNotIn(str(output), repr(seal))

    def test_equality_and_ancestor_descendant_overlap_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            protected = base / "protected"
            protected.mkdir()
            child = protected / "child"
            child.mkdir()
            for output, source in (
                (protected, protected),
                (child, protected),
                (protected, child),
            ):
                with self.subTest(output=output.name, source=source.name):
                    with self.assertRaises(harness.HarnessError) as raised:
                        harness.seal_disposable_root(output, [source])
                    self.assertEqual(raised.exception.code, "PROTECTED_ROOT_OVERLAP")

    def test_casefolded_ancestor_alias_is_detected(self) -> None:
        left = Path("/synthetic/Protected/child")
        right = Path("/synthetic/protected")
        self.assertTrue(harness._roots_alias(left, right))

    def test_traversal_and_relative_roots_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            protected = base / "protected"
            output = base / "output"
            filler = base / "filler"
            protected.mkdir()
            output.mkdir()
            filler.mkdir()
            traversal = Path(str(filler / ".." / "output"))
            with self.assertRaises(harness.HarnessError) as raised:
                harness.seal_disposable_root(traversal, [protected])
            self.assertEqual(raised.exception.code, "AMBIGUOUS_ROOT_PATH")
            with self.assertRaises(harness.HarnessError) as raised:
                harness.seal_disposable_root(Path("relative-output"), [protected])
            self.assertEqual(raised.exception.code, "AMBIGUOUS_ROOT_PATH")

    def test_symlink_root_alias_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            protected = base / "protected"
            output = base / "output"
            alias = base / "output-alias"
            protected.mkdir()
            output.mkdir()
            alias.symlink_to(output, target_is_directory=True)
            with self.assertRaises(harness.HarnessError) as raised:
                harness.seal_disposable_root(alias, [protected])
            self.assertEqual(raised.exception.code, "ROOT_SYMLINK_REJECTED")

    def test_output_root_generation_substitution_invalidates_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            protected = base / "protected"
            output = base / "output"
            moved = base / "moved"
            protected.mkdir()
            output.mkdir()
            seal = harness.seal_disposable_root(output, [protected])
            output.rename(moved)
            output.symlink_to(moved, target_is_directory=True)
            with self.assertRaises(harness.HarnessError) as raised:
                seal.verify()
            self.assertEqual(raised.exception.code, "OUTPUT_ROOT_GENERATION_MISMATCH")

    def test_protected_root_generation_substitution_invalidates_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            protected = base / "protected"
            output = base / "output"
            moved = base / "moved-protected"
            protected.mkdir()
            output.mkdir()
            seal = harness.seal_disposable_root(output, [protected])
            protected.rename(moved)
            protected.mkdir()
            with self.assertRaises(harness.HarnessError) as raised:
                seal.verify()
            self.assertEqual(raised.exception.code, "PROTECTED_ROOT_GENERATION_MISMATCH")


class CandidateProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source_root = (FIXTURE_ROOT / "candidate").resolve()
        cls.requests = (
            harness.SourceRequest(source_root / "source-a.yml", "localisation/opaque-a.yml"),
            harness.SourceRequest(source_root / "source-b.yml", "localisation/opaque-b.yml"),
        )
        cls.source_root = source_root

    def _blobs(self) -> tuple:
        return harness.snapshot_sources(self.requests)

    def _sealed_output(self, base: Path, name: str) -> harness.DisposableRootSeal:
        output = base / name
        output.mkdir()
        return harness.seal_disposable_root(output, [self.source_root])

    def test_deterministic_build_rebuild_and_source_immutability(self) -> None:
        before_blobs = self._blobs()
        source_manifest_before = harness.snapshot_manifest(before_blobs)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            first = harness.build_candidate(
                self._sealed_output(base, "candidate-one"),
                before_blobs,
            )
            second_seal = self._sealed_output(base, "candidate-two")
            second = harness.build_candidate(second_seal, before_blobs)
            self.assertEqual(first.manifest_sha256, second.manifest_sha256)
            self.assertEqual(first.tree_sha256, second.tree_sha256)
            manifest = json.loads(
                (second_seal.canonical / harness.MANIFEST_NAME).read_text("ascii")
            )
            self.assertEqual(manifest["policy_id"], "synthetic-only")
            self.assertEqual(manifest["profile_id"], "stellaris-4.4.6-research")
            self.assertEqual(
                [record["position"] for record in manifest["source_order"]],
                [0, 1],
            )
            self.assertEqual(len(manifest["source_order_digest"]), 64)
            self.assertEqual(
                [record["storage"] for record in manifest["files"]],
                ["payload-000000.bin", "payload-000001.bin"],
            )
            self.assertEqual(
                sorted(path.name for path in second_seal.canonical.iterdir()),
                ["manifest.json", "payload-000000.bin", "payload-000001.bin"],
            )
            self.assertNotEqual(second.manifest_sha256, second.tree_sha256)
            rerun = harness.build_candidate(second_seal, before_blobs)
            self.assertTrue(rerun.reused)
            self.assertEqual(second.manifest_sha256, rerun.manifest_sha256)

        after_blobs = self._blobs()
        self.assertEqual(source_manifest_before, harness.snapshot_manifest(after_blobs))

    def test_candidate_manifest_is_content_deterministic_across_metadata_churn(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            source_root = base / "source"
            source_root.mkdir()
            source = source_root / "synthetic.yml"
            raw = b"\xef\xbb\xbfl_synthetic:\n synthetic_key:0 \"value\"\n"
            source.write_bytes(raw)
            requests = (
                harness.SourceRequest(source, "localisation/synthetic.yml"),
            )
            before = harness.snapshot_sources(requests)
            metadata = source.stat()
            os.utime(
                source,
                ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 1_000_000),
            )
            after = harness.snapshot_sources(requests)
            relocated_root = base / "source-relocated"
            relocated_root.mkdir()
            relocated_source = relocated_root / "synthetic.yml"
            relocated_source.write_bytes(raw)
            relocated = harness.snapshot_sources(
                (
                    harness.SourceRequest(
                        relocated_source,
                        "localisation/synthetic.yml",
                    ),
                )
            )

            self.assertEqual(before[0].sha256, after[0].sha256)
            self.assertNotEqual(before[0].generation_sha256, after[0].generation_sha256)
            self.assertEqual(
                before[0].content_generation_sha256,
                after[0].content_generation_sha256,
            )
            self.assertNotEqual(
                harness.snapshot_manifest(before),
                harness.snapshot_manifest(after),
            )
            self.assertNotEqual(
                before[0].opaque_source_id,
                relocated[0].opaque_source_id,
            )
            self.assertEqual(
                before[0].content_generation_sha256,
                relocated[0].content_generation_sha256,
            )

            first_root = base / "candidate-before"
            second_root = base / "candidate-after"
            relocated_candidate_root = base / "candidate-relocated"
            first_root.mkdir()
            second_root.mkdir()
            relocated_candidate_root.mkdir()
            first = harness.build_candidate(
                harness.seal_disposable_root(first_root, [source_root]),
                before,
            )
            second = harness.build_candidate(
                harness.seal_disposable_root(second_root, [source_root]),
                after,
            )
            relocated_candidate = harness.build_candidate(
                harness.seal_disposable_root(
                    relocated_candidate_root,
                    [relocated_root],
                ),
                relocated,
            )
            self.assertEqual(first.manifest_sha256, second.manifest_sha256)
            self.assertEqual(first.tree_sha256, second.tree_sha256)
            self.assertEqual(
                first.manifest_sha256,
                relocated_candidate.manifest_sha256,
            )
            self.assertEqual(first.tree_sha256, relocated_candidate.tree_sha256)

    def test_candidate_duplicate_traversal_and_type_conflicts_abort(self) -> None:
        blobs = self._blobs()
        cases = (
            (
                (blobs[0], replace(blobs[1], relative_path=blobs[0].relative_path)),
                "DUPLICATE_RELATIVE_PATH",
            ),
            (
                (blobs[0], replace(blobs[1], relative_path="LOCALISATION/OPAQUE-A.YML")),
                "DUPLICATE_RELATIVE_PATH",
            ),
            (
                (
                    replace(blobs[0], relative_path="localisation/synthétique.yml"),
                    replace(blobs[1], relative_path="localisation/synthe\u0301tique.yml"),
                ),
                "DUPLICATE_RELATIVE_PATH",
            ),
            (
                (blobs[0], replace(blobs[1], relative_path="../escape.yml")),
                "INVALID_RELATIVE_PATH",
            ),
            (
                (blobs[0], replace(blobs[1], relative_path="localisation")),
                "RELATIVE_PATH_TYPE_CONFLICT",
            ),
            (
                (blobs[0], replace(blobs[1], relative_path="MANIFEST.JSON")),
                "RESERVED_RELATIVE_PATH",
            ),
            (
                (
                    replace(blobs[0], relative_path="Localisation/opaque-a.yml"),
                    replace(blobs[1], relative_path="localisation/opaque-b.yml"),
                ),
                "AMBIGUOUS_RELATIVE_PATH",
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            for index, (candidate_blobs, expected) in enumerate(cases):
                seal = self._sealed_output(base, f"invalid-{index}")
                with self.assertRaises(harness.HarnessError) as raised:
                    harness.build_candidate(seal, candidate_blobs)
                self.assertEqual(raised.exception.code, expected)
                self.assertEqual(harness.candidate_state(seal), "empty")

    def test_precommit_crash_points_never_create_completion_manifest(self) -> None:
        blobs = self._blobs()
        checkpoints = (
            "after_preflight",
            "before_payload_write",
            "after_payload_write",
            "after_payload_validation",
            "after_manifest_stage",
        )
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            for index, checkpoint in enumerate(checkpoints):
                with self.subTest(checkpoint=checkpoint):
                    seal = self._sealed_output(base, f"crash-{index}")

                    def crash(event: str, _item: int, target: str = checkpoint) -> None:
                        if event == target:
                            raise harness.SimulatedCrash(event)

                    with self.assertRaises(harness.SimulatedCrash):
                        harness.build_candidate(seal, blobs, hook=crash)
                    self.assertNotEqual(harness.candidate_state(seal), "complete")
                    if checkpoint in ("after_preflight", "before_payload_write"):
                        self.assertEqual(harness.candidate_state(seal), "empty")
                    else:
                        self.assertEqual(harness.candidate_state(seal), "incomplete")
                        with self.assertRaises(harness.HarnessError) as raised:
                            harness.build_candidate(seal, blobs)
                        self.assertEqual(raised.exception.code, "INCOMPLETE_BUILD_PRESENT")

    def test_postcommit_crash_recovers_as_complete_without_rewrite(self) -> None:
        blobs = self._blobs()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            seal = self._sealed_output(base, "postcommit")

            def crash(event: str, _item: int) -> None:
                if event == "after_manifest_commit":
                    raise harness.SimulatedCrash(event)

            with self.assertRaises(harness.SimulatedCrash):
                harness.build_candidate(seal, blobs, hook=crash)
            self.assertEqual(harness.candidate_state(seal), "complete")
            recovered = harness.build_candidate(seal, blobs)
            self.assertTrue(recovered.reused)

    def test_disk_full_protocol_abort_leaves_no_complete_candidate(self) -> None:
        blobs = self._blobs()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            seal = self._sealed_output(base, "disk-full")

            def disk_full(event: str, item: int) -> None:
                if event == "after_payload_write" and item == 0:
                    raise OSError(errno.ENOSPC, "synthetic disk full")

            with self.assertRaises(harness.HarnessError) as raised:
                harness.build_candidate(seal, blobs, hook=disk_full)
            self.assertEqual(raised.exception.code, "DISK_FULL")
            self.assertEqual(harness.candidate_state(seal), "incomplete")

    def test_flat_payload_symlink_substitution_aborts_before_external_write(self) -> None:
        blobs = self._blobs()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            protected = base / "protected-target"
            protected.mkdir()
            output = base / "output"
            output.mkdir()
            seal = harness.seal_disposable_root(output, [protected, self.source_root])
            substituted = False

            def substitute(event: str, item: int) -> None:
                nonlocal substituted
                if event == "before_payload_write" and item == 0 and not substituted:
                    (output / "payload-000000.bin").symlink_to(
                        protected / "outside.bin"
                    )
                    substituted = True

            with self.assertRaises(harness.HarnessError) as raised:
                harness.build_candidate(seal, blobs, hook=substitute)
            self.assertEqual(raised.exception.code, "CANDIDATE_TARGET_EXISTS")
            self.assertEqual(list(protected.iterdir()), [])

    def test_hardlink_target_substitution_aborts_without_source_mutation(self) -> None:
        blobs = self._blobs()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            protected = base / "protected-target"
            protected.mkdir()
            protected_file = protected / "protected.bin"
            protected_bytes = b"synthetic-protected-hardlink-target"
            protected_file.write_bytes(protected_bytes)
            output = base / "output"
            output.mkdir()
            seal = harness.seal_disposable_root(output, [protected, self.source_root])
            substituted = False

            def substitute(event: str, item: int) -> None:
                nonlocal substituted
                if event == "before_payload_write" and item == 0 and not substituted:
                    os.link(
                        str(protected_file),
                        str(output / "payload-000000.bin"),
                    )
                    substituted = True

            with self.assertRaises(harness.HarnessError) as raised:
                harness.build_candidate(seal, blobs, hook=substitute)
            self.assertEqual(raised.exception.code, "CANDIDATE_TARGET_EXISTS")
            self.assertEqual(protected_file.read_bytes(), protected_bytes)

    def test_payload_tamper_before_manifest_commit_is_detected(self) -> None:
        blobs = self._blobs()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            seal = self._sealed_output(base, "tampered")

            def tamper(event: str, item: int) -> None:
                if event == "after_payload_write" and item == 0:
                    (seal.canonical / "payload-000000.bin").write_bytes(b"tampered")

            with self.assertRaises(harness.HarnessError) as raised:
                harness.build_candidate(seal, blobs, hook=tamper)
            self.assertEqual(raised.exception.code, "CANDIDATE_MISMATCH")
            self.assertEqual(harness.candidate_state(seal), "incomplete")

    def test_complete_candidate_hardlink_substitution_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            source_root = base / "source"
            source_root.mkdir()
            source = source_root / "synthetic.yml"
            source.write_bytes(b"synthetic-hardlink-source")
            blobs = harness.snapshot_sources(
                (harness.SourceRequest(source, "localisation/synthetic.yml"),)
            )
            output = base / "complete-hardlink"
            output.mkdir()
            seal = harness.seal_disposable_root(output, [source_root])
            harness.build_candidate(seal, blobs)
            payload = seal.canonical / "payload-000000.bin"
            payload.unlink()
            os.link(str(source), str(payload))
            with self.assertRaises(harness.HarnessError) as raised:
                harness.build_candidate(seal, blobs)
            self.assertEqual(raised.exception.code, "CANDIDATE_HARDLINK_REJECTED")


class PrivacyEvidenceTests(unittest.TestCase):
    def test_redacted_report_and_leakage_check_do_not_expose_source_or_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="private-path-marker-") as temporary:
            root = Path(temporary).resolve()
            source = root / "private-file-marker.yml"
            raw = b'l_synthetic:\n private_key_marker:0 "PRIVATE_TEXT_MARKER"\n'
            source.write_bytes(raw)
            blobs = harness.snapshot_sources(
                [harness.SourceRequest(source, "opaque/000001.yml")]
            )
            payload, leakage = harness.render_redacted_evidence(
                blobs,
                additional_forbidden=(
                    os.fsencode(str(source)),
                    os.fsencode(source.name),
                    b' private_key_marker:0 "PRIVATE_TEXT_MARKER"',
                    b"private_key_marker",
                    b"PRIVATE_TEXT_MARKER",
                ),
            )
            self.assertFalse(leakage.leak_detected)
            self.assertGreaterEqual(leakage.checked_sequence_count, 5)
            self.assertNotIn(raw, payload)
            self.assertNotIn(os.fsencode(str(source)), payload)
            self.assertNotIn(b"private_key_marker", payload)
            self.assertNotIn(b"PRIVATE_TEXT_MARKER", payload)
            decoded = json.loads(payload)
            self.assertEqual(decoded["status"], "ok")
            self.assertEqual(decoded["file_count"], 1)

    def test_leakage_detection_returns_only_boolean_and_count(self) -> None:
        secret = b"PRIVATE_FORBIDDEN_SEQUENCE"
        result = harness.leakage_check(b'{"bad":"PRIVATE_FORBIDDEN_SEQUENCE"}', [secret])
        public = json.dumps(result.public_dict(), sort_keys=True)
        self.assertTrue(result.leak_detected)
        self.assertNotIn(secret.decode("ascii"), public)

    def test_cli_success_and_failure_are_path_and_content_free(self) -> None:
        script = REPOSITORY_ROOT / "tools" / "research" / "m1a_harness.py"
        with tempfile.TemporaryDirectory(prefix="private-cli-path-") as temporary:
            root = Path(temporary).resolve()
            source = root / "private-cli-file.yml"
            content = b'l_synthetic:\n private_cli_key:0 "PRIVATE_CLI_TEXT"\n'
            source.write_bytes(content)
            completed = subprocess.run(
                [sys.executable, str(script), "inspect", str(source)],
                cwd=str(REPOSITORY_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 0)
            combined = completed.stdout + completed.stderr
            self.assertNotIn(os.fsencode(str(source)), combined)
            self.assertNotIn(os.fsencode(source.name), combined)
            self.assertNotIn(b"private_cli_key", combined)
            self.assertNotIn(b"PRIVATE_CLI_TEXT", combined)

            missing = root / "private-missing-file.yml"
            failed = subprocess.run(
                [sys.executable, str(script), "inspect", str(missing)],
                cwd=str(REPOSITORY_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(failed.returncode, 2)
            failure_output = failed.stdout + failed.stderr
            self.assertNotIn(os.fsencode(str(missing)), failure_output)
            self.assertNotIn(os.fsencode(missing.name), failure_output)
            self.assertEqual(json.loads(failed.stdout)["status"], "blocked")

            invalid_value = "PRIVATE_ARGUMENT_MARKER"
            invalid = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "inspect",
                    "--max-bytes",
                    invalid_value,
                    str(source),
                ],
                cwd=str(REPOSITORY_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(invalid.returncode, 2)
            self.assertNotIn(invalid_value.encode("ascii"), invalid.stdout + invalid.stderr)


if __name__ == "__main__":
    unittest.main()
