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


def test_apply_review_decisions_dispatches_without_ollama(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received: tuple[Path, Path, Path, Path] | None = None

    def apply(
        source: Path,
        candidate: Path,
        decisions: Path,
        output: Path,
    ) -> dict[str, object]:
        nonlocal received
        received = (source, candidate, decisions, output)
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
    )
    assert json.loads(capsys.readouterr().out) == {
        "status": "bounded_pilot_review_applied"
    }
