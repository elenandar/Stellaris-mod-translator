from __future__ import annotations

import hashlib
import json
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


def make_source(tmp_path: Path, data: bytes = SOURCE_BYTES) -> Path:
    source = tmp_path / "source"
    path = source / "localisation" / "english" / "demo_l_english.yml"
    path.parent.mkdir(parents=True)
    path.write_bytes(data)
    return source


def test_inspect_reports_invalid_file_without_text(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    bad = source / "localisation" / "english" / "bad_l_english.yml"
    bad.write_bytes(b"\xff")
    report = inspect_mod(source)
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
    assert (
        hashlib.sha256(
            (source / "localisation/english/demo_l_english.yml").read_bytes()
        ).hexdigest()
        == original_hash
    )
    persisted = json.loads((output / "translation-report.json").read_text())
    assert persisted["model"]["digest"] == "sha256:synthetic"


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
        client_factory=forbidden,
    )
    assert report["dry_run"] is True
    assert not output.exists()
    assert list(tmp_path.glob(".candidate.tmp-*")) == []


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


@pytest.mark.parametrize(
    "unsafe_source",
    [
        b'# comment\nl_english:\n key:0 "text"\n',
        b'l_english:\n key:0 "text"\nl_french:\n other:0 "texte"\n',
        'l_english:\n key:0 "x\ufeffy"\n'.encode(),
        b'l_english:\n key:0 "x\x00y"\n',
        'l_english:\n key:0 "x\u0085y"\n'.encode(),
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
    assert FakeClient.calls == 0
    assert not (output / "localisation").exists()
    assert source_file.read_bytes() == unsafe_source


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
