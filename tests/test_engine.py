from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from stellaris_mod_translator import engine
from stellaris_mod_translator.engine import SafetyError, inspect_mod, translate_mod
from stellaris_mod_translator.ollama import OllamaError


SOURCE_BYTES = (
    b'\xef\xbb\xbfl_english:\n'
    b' first:0 "Hello $NAME$"\n'
    b' broken:0 not-quoted\n'
    b' second:1 "Goodbye"\n'
)


class FakeClient:
    calls = 0

    def exact_model(self, tag: str) -> dict[str, str]:
        assert tag == "synthetic:1"
        return {"tag": tag, "digest": "sha256:synthetic"}

    def translate(self, *, tag: str, text: str) -> str:
        type(self).calls += 1
        if "Goodbye" in text:
            raise OllamaError("synthetic failure")
        return text.replace("Hello", "Привет")


class FixedResponseClient(FakeClient):
    response = ""

    def translate(self, *, tag: str, text: str) -> str:
        type(self).calls += 1
        return type(self).response


class RecordingClient(FakeClient):
    texts: list[str] = []

    def translate(self, *, tag: str, text: str) -> str:
        type(self).calls += 1
        type(self).texts.append(text)
        return "RU " + text


class EchoClient(FakeClient):
    def translate(self, *, tag: str, text: str) -> str:
        type(self).calls += 1
        return text


def make_source(tmp_path: Path, data: bytes = SOURCE_BYTES) -> Path:
    source = tmp_path / "source"
    path = source / "localisation" / "english" / "demo_l_english.yml"
    path.parent.mkdir(parents=True)
    path.write_bytes(data)
    return source


def synthetic_source_file(
    relative: str,
    *,
    inode: int,
) -> engine.SourceFile:
    data = b'l_english:\n key:0 "Synthetic"\n'
    return engine.SourceFile(
        relative=Path(relative),
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        stat_identity=(1, inode, len(data), 1),
        parsed=engine.parse_localisation(data),
        error=None,
    )


def assert_inspect_schema_v1(report: dict[str, object]) -> None:
    assert report["schema_version"] == 1
    assert set(report) == {
        "schema_version",
        "source",
        "counts",
        "hashes",
        "diagnostics",
    }
    assert set(report["counts"]) == {
        "discovered_yml_files",
        "english_files",
        "occurrences",
        "translated_occurrences",
        "fallback_occurrences",
        "blocked_occurrences",
        "skipped_files",
    }


def assert_translation_schema_v2(
    report: dict[str, object], *, dry_run: bool
) -> None:
    assert report["schema_version"] == 2
    counts = report["counts"]
    assert set(counts) == {
        "discovered_yml_files",
        "english_files",
        "occurrences",
        "planned_translation_occurrences",
        "translated_occurrences",
        "unchanged_accepted_occurrences",
        "fallback_occurrences",
        "deferred_occurrences",
        "skipped_files",
    }
    assert 0 <= counts["unchanged_accepted_occurrences"] <= counts[
        "translated_occurrences"
    ]
    translated_or_planned = (
        counts["planned_translation_occurrences"]
        if dry_run
        else counts["translated_occurrences"]
    )
    assert counts["occurrences"] == (
        translated_or_planned
        + counts["fallback_occurrences"]
        + counts["deferred_occurrences"]
    )


def test_inspect_supported_occurrences_keep_schema_v1(tmp_path: Path) -> None:
    source = make_source(
        tmp_path,
        b'l_english:\n first:0 "One"\n second:0 "Two"\n',
    )

    report = inspect_mod(source)

    assert_inspect_schema_v1(report)
    assert report["counts"]["occurrences"] == 2
    assert report["counts"]["blocked_occurrences"] == 0


def test_inspect_parser_diagnostics_keep_schema_v1(tmp_path: Path) -> None:
    source = make_source(tmp_path)

    report = inspect_mod(source)

    assert_inspect_schema_v1(report)
    assert report["counts"]["occurrences"] == 3
    assert report["counts"]["fallback_occurrences"] == 1
    assert report["diagnostics"][0]["code"] == "unsupported_entry"


def test_inspect_reports_invalid_file_without_text(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    bad = source / "localisation" / "english" / "bad_l_english.yml"
    bad.write_bytes(b"\xff")
    report = inspect_mod(source)
    assert_inspect_schema_v1(report)
    assert report["counts"]["skipped_files"] == 1
    assert report["counts"]["english_files"] == 1
    assert "Hello" not in json.dumps(report)


def test_translation_changes_only_allowed_spans_and_keeps_source(
    tmp_path: Path,
) -> None:
    FakeClient.calls = 0
    source = make_source(tmp_path)
    original_hash = hashlib.sha256(
        (source / "localisation/english/demo_l_english.yml").read_bytes()
    ).hexdigest()
    output = tmp_path / "candidate"
    report = translate_mod(
        source, output, "synthetic:1", client_factory=FakeClient
    )
    candidate = output / "localisation/russian/demo_l_russian.yml"
    rendered = candidate.read_bytes()
    assert rendered.startswith(b"\xef\xbb\xbfl_russian:\n")
    assert b' first:0 "\xd0\x9f\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82 $NAME$"\n' in rendered
    assert b" broken:0 not-quoted\n" in rendered
    assert b' second:1 "Goodbye"\n' in rendered
    assert report["counts"]["translated_occurrences"] == 1
    assert report["counts"]["fallback_occurrences"] == 2
    assert report["counts"]["planned_translation_occurrences"] == 2
    assert report["counts"]["unchanged_accepted_occurrences"] == 0
    assert report["counts"]["deferred_occurrences"] == 0
    assert_translation_schema_v2(report, dry_run=False)
    assert FakeClient.calls == 2
    assert (
        hashlib.sha256(
            (source / "localisation/english/demo_l_english.yml").read_bytes()
        ).hexdigest()
        == original_hash
    )
    persisted = json.loads((output / "translation-report.json").read_text())
    assert persisted["model"]["digest"] == "sha256:synthetic"


def test_versionless_l_prefixed_entries_are_translated(
    tmp_path: Path,
) -> None:
    source_bytes = (
        b'l_english:\n'
        b' l_cluster: "Hello"\n'
        b' l_english_name: "Hello name"\n'
    )
    source = make_source(tmp_path, source_bytes)
    source_file = source / "localisation/english/demo_l_english.yml"
    output = tmp_path / "candidate"
    FakeClient.calls = 0

    report = translate_mod(
        source, output, "synthetic:1", client_factory=FakeClient
    )

    assert (
        output / "localisation/russian/demo_l_russian.yml"
    ).read_bytes() == (
        'l_russian:\n'
        ' l_cluster: "Привет"\n'
        ' l_english_name: "Привет name"\n'
    ).encode()
    assert report["counts"]["translated_occurrences"] == 2
    assert report["counts"]["unchanged_accepted_occurrences"] == 0
    assert report["counts"]["planned_translation_occurrences"] == 2
    assert report["max_occurrences_per_file"] is None
    assert report["status"] == "technical_safe"
    assert_translation_schema_v2(report, dry_run=False)
    assert FakeClient.calls == 2
    assert source_file.read_bytes() == source_bytes


def test_dry_run_never_calls_provider_or_writes(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    output = tmp_path / "candidate"

    def forbidden():
        raise AssertionError("provider must not be constructed")

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        dry_run=True,
        max_occurrences_per_file=1,
        client_factory=forbidden,
    )
    assert report["dry_run"] is True
    assert report["counts"]["planned_translation_occurrences"] == 1
    assert report["counts"]["fallback_occurrences"] == 1
    assert report["counts"]["deferred_occurrences"] == 1
    assert report["status"] == "dry_run_partial"
    assert_translation_schema_v2(report, dry_run=True)
    assert not output.exists()
    assert list(tmp_path.glob(".candidate.tmp-*")) == []


@pytest.mark.parametrize("limit", [0, -1, 1.5, "1", 101, True])
def test_library_rejects_invalid_occurrence_limit(
    tmp_path: Path, limit: object
) -> None:
    source = make_source(tmp_path)
    with pytest.raises(
        SafetyError,
        match="max_occurrences_per_file_must_be_integer_from_1_to_100",
    ):
        translate_mod(
            source,
            tmp_path / "candidate",
            "synthetic:1",
            dry_run=True,
            max_occurrences_per_file=limit,  # type: ignore[arg-type]
        )


def test_bounded_selection_is_deterministic_across_creation_order(
    tmp_path: Path,
) -> None:
    def build_source(root: Path, order: list[str]) -> Path:
        source = root / "source"
        english = source / "localisation/english"
        english.mkdir(parents=True)
        payloads = {
            "a": b'l_english:\n a1:0 "A first"\n a2:0 "A second"\n',
            "b": b'l_english:\n b1:0 "B first"\n b2:0 "B second"\n',
        }
        for name in order:
            (english / f"{name}_l_english.yml").write_bytes(payloads[name])
        return source

    source_one = build_source(tmp_path / "one", ["b", "a"])
    source_two = build_source(tmp_path / "two", ["a", "b"])
    observed: list[list[str]] = []
    rendered: list[list[tuple[str, bytes]]] = []
    for index, source in enumerate((source_one, source_two), start=1):
        RecordingClient.calls = 0
        RecordingClient.texts = []
        output = tmp_path / f"candidate-{index}"
        translate_mod(
            source,
            output,
            "synthetic:1",
            max_occurrences_per_file=1,
            client_factory=RecordingClient,
        )
        observed.append(list(RecordingClient.texts))
        rendered.append(
            [
                (path.relative_to(output).as_posix(), path.read_bytes())
                for path in sorted(output.rglob("*.yml"))
            ]
        )

    assert observed == [["A first", "B first"], ["A first", "B first"]]
    assert rendered[0] == rendered[1]


def test_limit_is_per_file_and_deferred_is_not_fallback(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    english = source / "localisation/english"
    english.mkdir(parents=True)
    for name in ("a", "b"):
        (english / f"{name}_l_english.yml").write_bytes(
            (
                "l_english:\n"
                f" {name}1:0 \"{name} first\"\n"
                f" {name}2:0 \"{name} second\"\n"
                f" {name}3:0 \"{name} third\"\n"
            ).encode()
        )
    RecordingClient.calls = 0
    RecordingClient.texts = []

    report = translate_mod(
        source,
        tmp_path / "candidate",
        "synthetic:1",
        max_occurrences_per_file=2,
        client_factory=RecordingClient,
    )

    assert RecordingClient.calls == 4
    assert report["counts"]["occurrences"] == 6
    assert report["counts"]["planned_translation_occurrences"] == 4
    assert report["counts"]["translated_occurrences"] == 4
    assert report["counts"]["fallback_occurrences"] == 0
    assert report["counts"]["deferred_occurrences"] == 2
    assert_translation_schema_v2(report, dry_run=False)


def test_unsupported_entry_does_not_consume_quota_and_deferred_is_identical(
    tmp_path: Path,
) -> None:
    source_bytes = (
        b'l_english:\n'
        b' unsupported:0 not-quoted\n'
        b' selected:0 "First supported"\n'
        b' deferred:0 "Keep exact \\"English\\"\\\\path\\ntext $NAME$"\n'
    )
    source = make_source(tmp_path, source_bytes)
    output = tmp_path / "candidate"
    RecordingClient.calls = 0
    RecordingClient.texts = []

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        max_occurrences_per_file=1,
        client_factory=RecordingClient,
    )

    assert RecordingClient.texts == ["First supported"]
    assert (
        output / "localisation/russian/demo_l_russian.yml"
    ).read_bytes() == (
        b'l_russian:\n'
        b' unsupported:0 not-quoted\n'
        b' selected:0 "RU First supported"\n'
        b' deferred:0 "Keep exact \\"English\\"\\\\path\\ntext $NAME$"\n'
    )
    assert report["counts"]["occurrences"] == 3
    assert report["counts"]["planned_translation_occurrences"] == 1
    assert report["counts"]["translated_occurrences"] == 1
    assert report["counts"]["fallback_occurrences"] == 1
    assert report["counts"]["deferred_occurrences"] == 1
    assert report["status"] == "technical_safe_partial"


def test_selected_model_failure_is_fallback_while_later_entry_is_deferred(
    tmp_path: Path,
) -> None:
    source_bytes = (
        b'l_english:\n'
        b' selected:0 "Selected"\n'
        b' deferred:0 "Deferred $NAME$"\n'
    )
    source = make_source(tmp_path, source_bytes)
    output = tmp_path / "candidate"

    class FailingClient(FakeClient):
        def translate(self, *, tag: str, text: str) -> str:
            type(self).calls += 1
            raise OllamaError("selected failure")

    FailingClient.calls = 0
    report = translate_mod(
        source,
        output,
        "synthetic:1",
        max_occurrences_per_file=1,
        client_factory=FailingClient,
    )

    assert FailingClient.calls == 1
    assert (
        output / "localisation/russian/demo_l_russian.yml"
    ).read_bytes() == source_bytes.replace(b"l_english:", b"l_russian:", 1)
    assert report["counts"]["planned_translation_occurrences"] == 1
    assert report["counts"]["translated_occurrences"] == 0
    assert report["counts"]["fallback_occurrences"] == 1
    assert report["counts"]["deferred_occurrences"] == 1


def test_bounded_report_schema_identity_and_placeholder_cleanup(
    tmp_path: Path,
) -> None:
    source_bytes = (
        b'l_english:\n'
        b' selected:0 "Hello \\"quoted\\"\\\\path\\nnext $NAME$"\n'
        b' deferred:0 "Deferred [Root.GetName]"\n'
    )
    source = make_source(tmp_path, source_bytes)
    output = tmp_path / "candidate"

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        max_occurrences_per_file=1,
        client_factory=FakeClient,
    )
    candidate = output / "localisation/russian/demo_l_russian.yml"
    persisted = json.loads((output / "translation-report.json").read_text())

    assert report["schema_version"] == 2
    assert report["max_occurrences_per_file"] == 1
    assert report["model"] == {
        "tag": "synthetic:1",
        "digest": "sha256:synthetic",
    }
    assert report["status"] == "technical_safe_partial"
    assert report["editorial_status"] == "human_review_required"
    assert report["editorially_approved"] is False
    assert persisted == report
    assert b"__SMT_" not in candidate.read_bytes()
    assert b'\\"quoted\\"\\\\path\\nnext $NAME$' in candidate.read_bytes()


def test_accepted_unchanged_plain_text_is_counted_and_requires_review(
    tmp_path: Path,
) -> None:
    source_bytes = b'l_english:\n key:0 "  Keep Latin Name  "\n'
    source = make_source(tmp_path, source_bytes)
    output = tmp_path / "candidate"
    EchoClient.calls = 0

    report = translate_mod(
        source, output, "synthetic:1", client_factory=EchoClient
    )

    assert EchoClient.calls == 1
    assert report["counts"]["translated_occurrences"] == 1
    assert report["counts"]["unchanged_accepted_occurrences"] == 1
    assert report["counts"]["fallback_occurrences"] == 0
    assert report["editorial_status"] == "human_review_required"
    assert report["editorially_approved"] is False
    assert (
        output / "localisation/russian/demo_l_russian.yml"
    ).read_bytes() == source_bytes.replace(b"l_english:", b"l_russian:", 1)
    assert_translation_schema_v2(report, dry_run=False)


def test_accepted_unchanged_protected_atoms_are_counted_after_restoration(
    tmp_path: Path,
) -> None:
    source_bytes = (
        b'l_english:\n'
        b' key:0 "  Keep $NAME$ [Root.GetName] \\"quoted\\"  "\n'
    )
    source = make_source(tmp_path, source_bytes)
    output = tmp_path / "candidate"
    EchoClient.calls = 0

    report = translate_mod(
        source, output, "synthetic:1", client_factory=EchoClient
    )

    assert EchoClient.calls == 1
    assert report["counts"]["translated_occurrences"] == 1
    assert report["counts"]["unchanged_accepted_occurrences"] == 1
    assert report["counts"]["fallback_occurrences"] == 0
    assert report["editorial_status"] == "human_review_required"
    assert (
        output / "localisation/russian/demo_l_russian.yml"
    ).read_bytes() == source_bytes.replace(b"l_english:", b"l_russian:", 1)
    assert_translation_schema_v2(report, dry_run=False)


def test_unchanged_accepted_must_be_subset_of_accepted_results(
    tmp_path: Path,
) -> None:
    report = translate_mod(
        make_source(tmp_path),
        tmp_path / "candidate",
        "synthetic:1",
        dry_run=True,
    )
    report["counts"]["unchanged_accepted_occurrences"] = 1

    with pytest.raises(
        SafetyError, match="unchanged_accepted_count_invariant_failed"
    ):
        engine._validate_count_invariant(report, dry_run=True)


def test_system_error_never_publishes_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_source(tmp_path)
    output = tmp_path / "candidate"

    def fail_publication(source_path: Path, destination_path: Path) -> None:
        raise OSError("synthetic publication failure")

    monkeypatch.setattr(
        engine, "atomic_publish_directory_no_replace", fail_publication
    )
    with pytest.raises(OSError, match="synthetic"):
        translate_mod(source, output, "synthetic:1", client_factory=FakeClient)
    assert not output.exists()
    assert list(tmp_path.glob(".candidate.tmp-*")) == []


def test_unavailable_no_replace_primitive_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_source(tmp_path)
    source_file = source / "localisation/english/demo_l_english.yml"
    original_source = source_file.read_bytes()
    output = tmp_path / "candidate"

    def unavailable(source_path: Path, destination_path: Path) -> None:
        raise engine.AtomicPublicationUnavailable("synthetic unavailable")

    monkeypatch.setattr(
        engine, "atomic_publish_directory_no_replace", unavailable
    )
    with pytest.raises(SafetyError, match="atomic_no_replace_unavailable"):
        translate_mod(source, output, "synthetic:1", client_factory=FakeClient)
    assert not output.exists()
    assert list(tmp_path.glob(".candidate.tmp-*")) == []
    assert source_file.read_bytes() == original_source


def test_source_change_during_final_inventory_prevents_publication(
    tmp_path: Path,
) -> None:
    source = make_source(tmp_path)
    source_file = source / "localisation/english/demo_l_english.yml"
    output = tmp_path / "candidate"

    class SourceDriftClient(FakeClient):
        inventory_calls = 0

        def exact_model(self, tag: str) -> dict[str, str]:
            type(self).inventory_calls += 1
            if type(self).inventory_calls == 2:
                source_file.write_bytes(SOURCE_BYTES + b"# external drift\n")
            return super().exact_model(tag)

    with pytest.raises(SafetyError, match="source_generation_changed"):
        translate_mod(
            source, output, "synthetic:1", client_factory=SourceDriftClient
        )
    assert not output.exists()
    assert list(tmp_path.glob(".candidate.tmp-*")) == []


def test_source_output_overlap_is_rejected(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    with pytest.raises(SafetyError, match="overlap"):
        translate_mod(
            source,
            source / "candidate",
            "synthetic:1",
            dry_run=True,
        )
    with pytest.raises(SafetyError, match="overlap"):
        translate_mod(
            source,
            tmp_path,
            "synthetic:1",
            dry_run=True,
        )


def test_symlink_in_localisation_is_rejected(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    outside = tmp_path / "outside.yml"
    outside.write_bytes(b'l_english:\n k:0 "x"\n')
    (source / "localisation" / "linked.yml").symlink_to(outside)
    with pytest.raises(SafetyError, match="symlink"):
        inspect_mod(source)


def test_non_regular_localisation_file_fails_without_blocking(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    localisation = source / "localisation/english"
    localisation.mkdir(parents=True)
    os.mkfifo(localisation / "fifo.yml")

    with pytest.raises(SafetyError, match="unsafe_localisation_file"):
        inspect_mod(source)


def test_existing_output_is_rejected(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    output = tmp_path / "candidate"
    output.mkdir()
    with pytest.raises(SafetyError, match="must_not_exist"):
        translate_mod(source, output, "synthetic:1", dry_run=True)


@pytest.mark.parametrize("destination_kind", ["file", "directory", "symlink"])
def test_destination_appearing_at_publication_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    destination_kind: str,
) -> None:
    source = make_source(tmp_path)
    source_file = source / "localisation/english/demo_l_english.yml"
    original_source = source_file.read_bytes()
    output = tmp_path / "candidate"
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "marker"
    marker.write_bytes(b"outside")
    real_publish = engine.atomic_publish_directory_no_replace

    def race(source_path: Path, destination_path: Path) -> None:
        if destination_kind == "file":
            destination_path.write_bytes(b"existing")
        elif destination_kind == "directory":
            destination_path.mkdir()
            (destination_path / "marker").write_bytes(b"existing")
        else:
            destination_path.symlink_to(outside, target_is_directory=True)
        real_publish(source_path, destination_path)

    monkeypatch.setattr(engine, "atomic_publish_directory_no_replace", race)
    with pytest.raises(SafetyError, match="output_appeared_before_publication"):
        translate_mod(source, output, "synthetic:1", client_factory=FakeClient)

    if destination_kind == "file":
        assert output.read_bytes() == b"existing"
    elif destination_kind == "directory":
        assert (output / "marker").read_bytes() == b"existing"
    else:
        assert output.is_symlink()
        assert output.resolve() == outside
        assert marker.read_bytes() == b"outside"
    assert source_file.read_bytes() == original_source
    assert list(tmp_path.glob(".candidate.tmp-*")) == []


@pytest.mark.parametrize(
    "response",
    [
        "",
        " \t ",
        "__SMT_TOKEN_0000__",
        "\ud800",
        "text\u0085",
        "text\u2028",
        "text\u2029",
        "text\ufeff",
        "text\u200b",
        "text\u202e",
        "text\u2066",
        "\u0301",
        " \t\u0301\u034f ",
        "Text __SMT_TOKEN_0000__ __SMT_OTHER__",
        "Text __SMT_TOKEN_0000__ __SMT_TOKEN_123456__",
    ],
)
def test_invalid_translation_falls_back_to_exact_english_and_keeps_source(
    tmp_path: Path, response: str
) -> None:
    source_bytes = b'l_english:\n key:0 "Original English $NAME$"\n'
    source = make_source(tmp_path, source_bytes)
    source_file = source / "localisation/english/demo_l_english.yml"
    FixedResponseClient.calls = 0
    FixedResponseClient.response = response
    output = tmp_path / "candidate"

    report = translate_mod(
        source, output, "synthetic:1", client_factory=FixedResponseClient
    )

    candidate = output / "localisation/russian/demo_l_russian.yml"
    assert candidate.read_bytes() == (
        b'l_russian:\n key:0 "Original English $NAME$"\n'
    )
    assert report["counts"]["translated_occurrences"] == 0
    assert report["counts"]["fallback_occurrences"] == 1
    assert source_file.read_bytes() == source_bytes


def test_bounded_dry_run_with_skipped_file_is_partial(tmp_path: Path) -> None:
    source = make_source(
        tmp_path,
        b'l_english:\n key:0 "Hello"\n',
    )
    skipped = source / "localisation/english/skipped_l_english.yml"
    skipped.write_bytes(b"\xff")
    output = tmp_path / "candidate"

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        dry_run=True,
        max_occurrences_per_file=1,
    )

    assert report["counts"]["skipped_files"] == 1
    assert report["counts"]["fallback_occurrences"] == 0
    assert report["counts"]["deferred_occurrences"] == 0
    assert report["status"] == "dry_run_partial"
    assert_translation_schema_v2(report, dry_run=True)
    assert not output.exists()


@pytest.mark.parametrize(
    "unsafe_source",
    [
        b'# comment\nl_english:\n key:0 "text"\n',
        b'l_english:\n key:0 "text"\nl_french:\n other:0 "texte"\n',
        'l_english:\n key:0 "x\ufeffy"\n'.encode(),
        b'l_english:\n key:0 "x\x00y"\n',
        'l_english:\n key:0 "x\u0085y"\n'.encode(),
        'l_english:\n key:0 "x\u200by"\n'.encode(),
        'l_english:\n key:0 "x\u202ey"\n'.encode(),
        'l_english:\n key:0 "x\u2028y"\n'.encode(),
        'l_english:\n key:0 "x\u2029y"\n'.encode(),
    ],
)
def test_unsafe_file_is_skipped_without_translation_or_candidate_bytes(
    tmp_path: Path, unsafe_source: bytes
) -> None:
    source = make_source(tmp_path, unsafe_source)
    source_file = source / "localisation/english/demo_l_english.yml"
    FakeClient.calls = 0
    output = tmp_path / "candidate"

    report = translate_mod(
        source, output, "synthetic:1", client_factory=FakeClient
    )

    assert report["counts"]["skipped_files"] == 1
    assert report["status"] == "technical_safe_partial"
    assert FakeClient.calls == 0
    assert not (output / "localisation").exists()
    assert source_file.read_bytes() == unsafe_source


def test_qualified_replace_layer_is_discovered_rendered_and_lossless(
    tmp_path: Path,
) -> None:
    source = make_source(
        tmp_path,
        b'l_english:\n normal:0 "Normal"\n',
    )
    replace_file = (
        source / "localisation/english/replace/demo_l_english.yml"
    )
    replace_file.parent.mkdir(parents=True)
    replace_bytes = (
        b"\xef\xbb\xbfl_english: # keep-header\r\n"
        b"# keep-comment\r\n"
        b"\r\n"
        b' first:1 "Hello $NAME$ [Root.GetName] '
        b'\xc2\xa3energy\xc2\xa3 \xc2\xa7Ggreen\xc2\xa7! \\\\n"\r\n'
        b' second:2 "Goodbye"\r\n'
        b" unsupported:3 SYNTHETIC_UNSUPPORTED\r\n"
    )
    replace_file.write_bytes(replace_bytes)
    source_before = {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*.yml")
    }

    inspect = inspect_mod(source)
    assert inspect["counts"] == {
        "discovered_yml_files": 2,
        "english_files": 2,
        "occurrences": 4,
        "translated_occurrences": 0,
        "fallback_occurrences": 1,
        "blocked_occurrences": 0,
        "skipped_files": 0,
    }
    assert all(
        item["code"] != "replace_layer_unsupported"
        for item in inspect["diagnostics"]
    )

    dry_output = tmp_path / "dry-candidate"

    def forbidden():
        raise AssertionError("provider must not be constructed")

    dry_report = translate_mod(
        source,
        dry_output,
        "synthetic:1",
        dry_run=True,
        client_factory=forbidden,
    )
    assert dry_report["counts"]["planned_translation_occurrences"] == 3
    assert not dry_output.exists()

    output = tmp_path / "candidate"
    EchoClient.calls = 0
    report = translate_mod(
        source,
        output,
        "synthetic:1",
        client_factory=EchoClient,
    )

    normal_candidate = (
        output / "localisation/russian/demo_l_russian.yml"
    )
    replace_candidate = (
        output
        / "localisation/russian/replace/demo_l_russian.yml"
    )
    assert normal_candidate.read_bytes() == (
        b'l_russian:\n normal:0 "Normal"\n'
    )
    assert replace_candidate.read_bytes() == replace_bytes.replace(
        b"l_english:", b"l_russian:", 1
    )
    assert EchoClient.calls == 3
    assert report["counts"]["english_files"] == 2
    assert report["counts"]["translated_occurrences"] == 3
    assert report["counts"]["unchanged_accepted_occurrences"] == 3
    assert report["counts"]["fallback_occurrences"] == 1
    assert report["counts"]["skipped_files"] == 0
    assert report["status"] == "technical_safe_partial"
    assert {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*.yml")
    } == source_before


@pytest.mark.parametrize(
    "relative",
    [
        "localisation/replace/demo_l_english.yml",
        "localisation/other/replace/demo_l_english.yml",
        "localisation/English/replace/demo_l_english.yml",
        "localisation/english/Replace/demo_l_english.yml",
        "localisation/ｅｎｇｌｉｓｈ/ｒｅｐｌａｃｅ/demo_l_english.yml",
        "localisation/еnglish/replace/demo_l_english.yml",
        "localisation/english/replаce/demo_l_english.yml",
        "localisation/engl\u0131sh/replace/demo_l_english.yml",
        "localisation/english/repl\u0251ce/demo_l_english.yml",
        "localisation/engl\u0131sh/repl\u0251ce/demo_l_english.yml",
        "localisation/english/repla\u034fce/demo_l_english.yml",
        "localisation/english/repla\ufe0fce/demo_l_english.yml",
        "localisation/english/repla\u200dce/demo_l_english.yml",
        "localisation/eng\u034flish/replace/demo_l_english.yml",
        "localisation/english/repl\u3164ace/demo_l_english.yml",
        "localisation/english/nested/replace/demo_l_english.yml",
    ],
)
def test_unqualified_or_noncanonical_replace_layer_is_skipped_fail_closed(
    tmp_path: Path,
    relative: str,
) -> None:
    source = tmp_path / "source"
    source_file = source / relative
    source_file.parent.mkdir(parents=True)
    source_bytes = b'l_english:\n key:0 "Hello"\n'
    source_file.write_bytes(source_bytes)
    output = tmp_path / "candidate"
    constructed = False

    def forbidden():
        nonlocal constructed
        constructed = True
        raise AssertionError("provider must not be constructed")

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        client_factory=forbidden,
    )

    assert constructed is False
    assert report["counts"]["skipped_files"] == 1
    assert report["counts"]["english_files"] == 0
    assert report["counts"]["planned_translation_occurrences"] == 0
    assert report["status"] == "technical_safe_partial"
    assert report["diagnostics"] == [
        {
            "path": relative,
            "code": "replace_layer_unsupported",
        }
    ]
    assert not (output / "localisation").exists()
    assert not list(tmp_path.glob(".candidate.tmp-*"))
    assert source_file.read_bytes() == source_bytes


def test_canonical_nested_localisation_without_replace_is_translated(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source_file = (
        source
        / "localisation/english/nested/demo_l_english.yml"
    )
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b'l_english:\n key:0 "Nested"\n')
    output = tmp_path / "candidate"
    EchoClient.calls = 0

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        client_factory=EchoClient,
    )

    assert EchoClient.calls == 1
    assert report["counts"]["skipped_files"] == 0
    assert (
        output / "localisation/russian/nested/demo_l_russian.yml"
    ).is_file()


def test_non_english_replace_tree_remains_ignored_without_new_residue(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source_file = (
        source
        / "localisation/german/replace/demo_l_german.yml"
    )
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b'l_german:\n key:0 "Synthetic"\n')
    output = tmp_path / "candidate"

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        client_factory=lambda: pytest.fail(
            "provider must not be constructed"
        ),
    )

    assert report["counts"]["english_files"] == 0
    assert report["counts"]["skipped_files"] == 0
    assert report["status"] == "no_translatable_content"
    assert report["diagnostics"] == []
    assert not (output / "localisation").exists()


def test_malformed_qualified_replace_never_constructs_provider(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source_file = (
        source / "localisation/english/replace/bad_l_english.yml"
    )
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"\xff")
    output = tmp_path / "candidate"

    def forbidden():
        raise AssertionError("provider must not be constructed")

    report = translate_mod(
        source,
        output,
        "synthetic:1",
        client_factory=forbidden,
    )

    assert report["counts"]["skipped_files"] == 1
    assert report["counts"]["english_files"] == 0
    assert report["diagnostics"][0]["code"] == "file_skipped"
    assert not (output / "localisation").exists()


def test_empty_source_has_explicit_no_translatable_content_status(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    dry_output = tmp_path / "dry-candidate"
    full_output = tmp_path / "full-candidate"

    dry_report = translate_mod(
        source, dry_output, "synthetic:1", dry_run=True
    )
    full_report = translate_mod(source, full_output, "synthetic:1")

    assert dry_report["status"] == "dry_run_no_translatable_content"
    assert full_report["status"] == "no_translatable_content"
    assert dry_report["counts"]["occurrences"] == 0
    assert full_report["counts"]["occurrences"] == 0
    assert_translation_schema_v2(dry_report, dry_run=True)
    assert_translation_schema_v2(full_report, dry_run=False)
    assert not dry_output.exists()
    assert (full_output / "translation-report.json").is_file()


def test_candidate_mapping_collision_is_rejected_before_provider_or_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    english = source / "localisation/english"
    english.mkdir(parents=True)
    first = english / "same_l_english.yml"
    second = english / "same_l_russian.yml"
    first.write_bytes(b'l_english:\n first:0 "First"\n')
    second.write_bytes(b'l_english:\n second:0 "Second"\n')
    output = tmp_path / "candidate"

    def forbidden_factory():
        raise AssertionError("provider must not be constructed")

    def forbidden_temp(*args: object, **kwargs: object):
        raise AssertionError("temporary output must not be created")

    monkeypatch.setattr(engine.tempfile, "mkdtemp", forbidden_temp)
    with pytest.raises(SafetyError, match="candidate_path_collision"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            client_factory=forbidden_factory,
        )

    assert not output.exists()
    assert first.read_bytes() == b'l_english:\n first:0 "First"\n'
    assert second.read_bytes() == b'l_english:\n second:0 "Second"\n'


def test_candidate_file_directory_collision_remains_rejected() -> None:
    files = [
        synthetic_source_file(
            "localisation/english/node.yml",
            inode=1,
        ),
        synthetic_source_file(
            "localisation/english/node.yml/child_l_english.yml",
            inode=2,
        ),
    ]

    with pytest.raises(SafetyError, match="candidate_path_collision"):
        engine._validate_candidate_path_mappings(files)


@pytest.mark.parametrize(
    ("first_directory", "second_directory"),
    [
        ("CaseDir", "casedir"),
        ("Caf\u00e9", "Cafe\u0301"),
    ],
)
def test_candidate_directory_prefix_alias_is_rejected_before_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    first_directory: str,
    second_directory: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "candidate"
    workspace = tmp_path / "job.smt-workspace.sqlite3"
    files = [
        synthetic_source_file(
            (
                f"localisation/english/{first_directory}/"
                "one_l_english.yml"
            ),
            inode=1,
        ),
        synthetic_source_file(
            (
                f"localisation/english/{second_directory}/"
                "two_l_english.yml"
            ),
            inode=2,
        ),
    ]
    monkeypatch.setattr(engine, "_snapshot", lambda path: files)

    def forbidden_factory():
        raise AssertionError("provider must not be constructed")

    def forbidden_temp(*args: object, **kwargs: object):
        raise AssertionError("temporary output must not be created")

    monkeypatch.setattr(engine.tempfile, "mkdtemp", forbidden_temp)
    with pytest.raises(SafetyError, match="candidate_path_collision"):
        translate_mod(
            source,
            output,
            "synthetic:1",
            workspace=workspace,
            client_factory=forbidden_factory,
        )

    assert not output.exists()
    assert not workspace.exists()
    assert not Path(str(workspace) + ".lock").exists()


def test_filename_without_language_suffix_is_not_reconstructed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source_file = source / "localisation/english/plain.yml"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b'l_english:\n key:0 "Hello"\n')
    output = tmp_path / "candidate"
    translate_mod(source, output, "synthetic:1", client_factory=FakeClient)
    assert (output / "localisation/russian/plain.yml").is_file()
