from __future__ import annotations

import json
from pathlib import Path

import pytest

from stellaris_mod_translator import cli
from stellaris_mod_translator.cli import main, parser


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "text", "101"])
def test_occurrence_limit_rejects_invalid_cli_values(value: str) -> None:
    with pytest.raises(SystemExit) as exc:
        parser().parse_args(
            [
                "translate-mod",
                "--source-mod",
                "/source",
                "--output",
                "/output",
                "--model",
                "synthetic:1",
                "--max-occurrences-per-file",
                value,
            ]
        )
    assert exc.value.code == 2


@pytest.mark.parametrize("value", ["1", "100"])
def test_occurrence_limit_accepts_bounds(value: str) -> None:
    args = parser().parse_args(
        [
            "translate-mod",
            "--source-mod",
            "/source",
            "--output",
            "/output",
            "--model",
            "synthetic:1",
            "--max-occurrences-per-file",
            value,
        ]
    )
    assert args.max_occurrences_per_file == int(value)


def test_occurrence_limit_is_optional() -> None:
    args = parser().parse_args(
        [
            "translate-mod",
            "--source-mod",
            "/source",
            "--output",
            "/output",
            "--model",
            "synthetic:1",
        ]
    )
    assert args.max_occurrences_per_file is None


def test_workspace_and_resume_arguments_are_exposed() -> None:
    args = parser().parse_args(
        [
            "translate-mod",
            "--source-mod",
            "/source",
            "--output",
            "/output",
            "--model",
            "synthetic:1",
            "--workspace",
            "/job.smt-workspace.sqlite3",
            "--resume",
        ]
    )
    assert args.workspace == Path("/job.smt-workspace.sqlite3")
    assert args.resume is True


def test_resume_requires_workspace_at_dispatch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(
        [
            "translate-mod",
            "--source-mod",
            "/source",
            "--output",
            "/output",
            "--model",
            "synthetic:1",
            "--resume",
        ]
    )
    assert result == 2
    assert (
        json.loads(capsys.readouterr().err)["message"]
        == "resume_requires_workspace"
    )


def test_translate_help_lists_workspace_and_resume(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        parser().parse_args(["translate-mod", "--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "--workspace WORKSPACE" in output
    assert "--resume" in output


def test_build_review_pack_requires_all_three_paths() -> None:
    args = parser().parse_args(
        [
            "build-review-pack",
            "--source-mod",
            "/source",
            "--candidate",
            "/candidate",
            "--output",
            "/review",
        ]
    )
    assert str(args.source_mod) == "/source"
    assert str(args.candidate) == "/candidate"
    assert str(args.output) == "/review"
    assert args.candidate_report_sha256 is None


def test_build_review_pack_accepts_and_dispatches_full_report_pin(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pin = "a" * 64
    received: tuple[Path, Path, Path, str | None] | None = None

    def build(
        source: Path,
        candidate: Path,
        output: Path,
        *,
        candidate_report_sha256: str | None,
    ) -> dict[str, object]:
        nonlocal received
        received = (source, candidate, output, candidate_report_sha256)
        return {"status": "review_pack_created"}

    monkeypatch.setattr(cli, "build_review_pack", build)
    result = main(
        [
            "build-review-pack",
            "--source-mod",
            "/source",
            "--candidate",
            "/candidate",
            "--output",
            "/review",
            "--candidate-report-sha256",
            pin,
        ]
    )
    assert result == 0
    assert received == (
        Path("/source"),
        Path("/candidate"),
        Path("/review"),
        pin,
    )
    assert json.loads(capsys.readouterr().out) == {
        "status": "review_pack_created"
    }


@pytest.mark.parametrize(
    "pin",
    ["A" * 64, "a" * 63, "g" * 64, "a" * 65],
)
def test_build_review_pack_rejects_malformed_report_pin(pin: str) -> None:
    with pytest.raises(SystemExit) as exc:
        parser().parse_args(
            [
                "build-review-pack",
                "--source-mod",
                "/source",
                "--candidate",
                "/candidate",
                "--output",
                "/review",
                "--candidate-report-sha256",
                pin,
            ]
        )
    assert exc.value.code == 2


def test_build_review_help_lists_full_report_pin(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        parser().parse_args(["build-review-pack", "--help"])
    assert exc.value.code == 0
    assert "--candidate-report-sha256 SHA256" in capsys.readouterr().out


def test_apply_review_decisions_requires_all_four_paths() -> None:
    args = parser().parse_args(
        [
            "apply-review-decisions",
            "--source-mod",
            "/source",
            "--candidate",
            "/candidate",
            "--decisions",
            "/decisions.json",
            "--output",
            "/reviewed",
        ]
    )
    assert str(args.source_mod) == "/source"
    assert str(args.candidate) == "/candidate"
    assert str(args.decisions) == "/decisions.json"
    assert str(args.output) == "/reviewed"
    assert args.candidate_report_sha256 is None


def test_apply_review_decisions_dispatches_without_ollama(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received: tuple[Path, Path, Path, Path, str | None] | None = None

    def apply(
        source: Path,
        candidate: Path,
        decisions: Path,
        output: Path,
        *,
        candidate_report_sha256: str | None,
    ) -> dict[str, object]:
        nonlocal received
        received = (
            source,
            candidate,
            decisions,
            output,
            candidate_report_sha256,
        )
        return {"status": "bounded_pilot_review_applied"}

    monkeypatch.setattr(cli, "apply_review_decisions", apply)
    result = main(
        [
            "apply-review-decisions",
            "--source-mod",
            "/source",
            "--candidate",
            "/candidate",
            "--decisions",
            "/decisions.json",
            "--output",
            "/reviewed",
        ]
    )

    assert result == 0
    assert received == (
        Path("/source"),
        Path("/candidate"),
        Path("/decisions.json"),
        Path("/reviewed"),
        None,
    )
    assert json.loads(capsys.readouterr().out) == {
        "status": "bounded_pilot_review_applied"
    }


def test_apply_review_decisions_accepts_and_dispatches_full_report_pin(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pin = "c" * 64
    received: tuple[Path, Path, Path, Path, str | None] | None = None

    def apply(
        source: Path,
        candidate: Path,
        decisions: Path,
        output: Path,
        *,
        candidate_report_sha256: str | None,
    ) -> dict[str, object]:
        nonlocal received
        received = (
            source,
            candidate,
            decisions,
            output,
            candidate_report_sha256,
        )
        return {"status": "full_candidate_review_applied"}

    monkeypatch.setattr(cli, "apply_review_decisions", apply)
    result = main(
        [
            "apply-review-decisions",
            "--source-mod",
            "/source",
            "--candidate",
            "/candidate",
            "--candidate-report-sha256",
            pin,
            "--decisions",
            "/decisions.json",
            "--output",
            "/reviewed",
        ]
    )

    assert result == 0
    assert received == (
        Path("/source"),
        Path("/candidate"),
        Path("/decisions.json"),
        Path("/reviewed"),
        pin,
    )
    assert json.loads(capsys.readouterr().out) == {
        "status": "full_candidate_review_applied"
    }


@pytest.mark.parametrize(
    "pin",
    ["A" * 64, "a" * 63, "g" * 64, "a" * 65],
)
def test_apply_review_decisions_rejects_malformed_report_pin(pin: str) -> None:
    with pytest.raises(SystemExit) as exc:
        parser().parse_args(
            [
                "apply-review-decisions",
                "--source-mod",
                "/source",
                "--candidate",
                "/candidate",
                "--candidate-report-sha256",
                pin,
                "--decisions",
                "/decisions.json",
                "--output",
                "/reviewed",
            ]
        )
    assert exc.value.code == 2


def test_apply_review_help_lists_full_report_pin(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        parser().parse_args(["apply-review-decisions", "--help"])
    assert exc.value.code == 0
    assert "--candidate-report-sha256 SHA256" in capsys.readouterr().out


def test_package_reviewed_mod_exposes_exact_interface() -> None:
    args = parser().parse_args(
        [
            "package-reviewed-mod",
            "--reviewed-candidate",
            "/reviewed",
            "--application-report-sha256",
            "d" * 64,
            "--output",
            "/package",
            "--mod-slug",
            "example_ru_local",
            "--display-name",
            "Example — Русская локализация",
            "--dependency-name",
            "Example",
            "--supported-version",
            "4.4.*",
            "--planned-install-root",
            "/active/mod",
            "--allow-technical-residue",
        ]
    )
    assert args.reviewed_candidate == Path("/reviewed")
    assert args.application_report_sha256 == "d" * 64
    assert args.output == Path("/package")
    assert args.mod_slug == "example_ru_local"
    assert args.display_name == "Example — Русская локализация"
    assert args.dependency_name == "Example"
    assert args.supported_version == "4.4.*"
    assert args.planned_install_root == Path("/active/mod")
    assert args.allow_technical_residue is True


def test_package_reviewed_mod_dispatches_without_ollama(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received: tuple[object, ...] | None = None

    def package(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal received
        received = (*args, kwargs)
        return {"status": "reviewed_mod_package_created"}

    monkeypatch.setattr(cli, "package_reviewed_mod", package)
    result = main(
        [
            "package-reviewed-mod",
            "--reviewed-candidate",
            "/reviewed",
            "--application-report-sha256",
            "e" * 64,
            "--output",
            "/package",
            "--mod-slug",
            "example_ru_local",
            "--display-name",
            "Example — Русская локализация",
            "--dependency-name",
            "Example",
            "--supported-version",
            "4.4.*",
            "--planned-install-root",
            "/active/mod",
            "--allow-technical-residue",
        ]
    )
    assert result == 0
    assert received == (
        Path("/reviewed"),
        "e" * 64,
        Path("/package"),
        "example_ru_local",
        "Example — Русская локализация",
        "Example",
        "4.4.*",
        Path("/active/mod"),
        {"allow_technical_residue": True},
    )
    assert json.loads(capsys.readouterr().out) == {
        "status": "reviewed_mod_package_created"
    }


def test_package_reviewed_mod_help_lists_safety_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        parser().parse_args(["package-reviewed-mod", "--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    for option in (
        "--reviewed-candidate REVIEWED_CANDIDATE",
        "--application-report-sha256 SHA256",
        "--planned-install-root PLANNED_INSTALL_ROOT",
        "--allow-technical-residue",
    ):
        assert option in output
