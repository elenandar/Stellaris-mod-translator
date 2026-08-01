from __future__ import annotations

import json
from pathlib import Path

import pytest

from stellaris_mod_translator import cli
from stellaris_mod_translator.cli import main, parser
from stellaris_mod_translator.engine import SafetyError


def _build_vanilla_memory_argv() -> list[str]:
    return [
        "build-vanilla-memory",
        "--english-root",
        "/private/english",
        "--russian-root",
        "/private/russian",
        "--game-version",
        "Pegasus v4.4.6 (fdde)",
        "--output",
        "/private/memory",
    ]


def test_build_vanilla_memory_exposes_closed_interface() -> None:
    args = parser().parse_args(_build_vanilla_memory_argv())

    assert args.command == "build-vanilla-memory"
    assert args.english_root == Path("/private/english")
    assert args.russian_root == Path("/private/russian")
    assert args.game_version == "Pegasus v4.4.6 (fdde)"
    assert args.output == Path("/private/memory")


def test_build_vanilla_memory_dispatches_content_free_report(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received: tuple[Path, Path, str, Path] | None = None

    def build(
        english_root: Path,
        russian_root: Path,
        game_version: str,
        output: Path,
    ) -> dict[str, object]:
        nonlocal received
        received = (english_root, russian_root, game_version, output)
        return {
            "schema_version": 1,
            "game_version": game_version,
            "logical_digest": "a" * 64,
            "counts": {"strict_eligible_pairs": 1},
        }

    monkeypatch.setattr(cli, "build_vanilla_memory", build)

    result = main(_build_vanilla_memory_argv())

    assert result == 0
    assert received == (
        Path("/private/english"),
        Path("/private/russian"),
        "Pegasus v4.4.6 (fdde)",
        Path("/private/memory"),
    )
    assert json.loads(capsys.readouterr().out) == {
        "schema_version": 1,
        "game_version": "Pegasus v4.4.6 (fdde)",
        "logical_digest": "a" * 64,
        "counts": {"strict_eligible_pairs": 1},
    }


def test_build_vanilla_memory_help_lists_required_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        parser().parse_args(["build-vanilla-memory", "--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    for option in (
        "--english-root ENGLISH_ROOT",
        "--russian-root RUSSIAN_ROOT",
        "--game-version GAME_VERSION",
        "--output OUTPUT",
    ):
        assert option in output


def test_inspect_vanilla_memory_exposes_closed_interface() -> None:
    args = parser().parse_args(
        [
            "inspect-vanilla-memory",
            "--database",
            "/private/memory/vanilla-memory.sqlite3",
        ]
    )

    assert args.command == "inspect-vanilla-memory"
    assert args.database == Path(
        "/private/memory/vanilla-memory.sqlite3"
    )


def test_inspect_vanilla_memory_dispatches_content_free_report(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received: Path | None = None

    def inspect(database: Path) -> dict[str, object]:
        nonlocal received
        received = database
        return {
            "schema_version": 1,
            "game_version": "Pegasus v4.4.6 (fdde)",
            "database_sha256": "b" * 64,
            "logical_digest": "c" * 64,
            "counts": {"strict_eligible_pairs": 1},
        }

    monkeypatch.setattr(cli, "inspect_vanilla_memory", inspect)

    result = main(
        [
            "inspect-vanilla-memory",
            "--database",
            "/private/memory/vanilla-memory.sqlite3",
        ]
    )

    assert result == 0
    assert received == Path("/private/memory/vanilla-memory.sqlite3")
    assert json.loads(capsys.readouterr().out) == {
        "schema_version": 1,
        "game_version": "Pegasus v4.4.6 (fdde)",
        "database_sha256": "b" * 64,
        "logical_digest": "c" * 64,
        "counts": {"strict_eligible_pairs": 1},
    }


def test_inspect_vanilla_memory_help_lists_database_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        parser().parse_args(["inspect-vanilla-memory", "--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "--database DATABASE" in output
    assert "--english-root" not in output
    assert "--russian-root" not in output
    assert "--output" not in output


def test_root_help_lists_vanilla_memory_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        parser().parse_args(["--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "build-vanilla-memory" in output
    assert "inspect-vanilla-memory" in output
    assert "inspect-vanilla-context-coverage" in output


@pytest.mark.parametrize(
    ("function_name", "argv"),
    [
        ("build_vanilla_memory", _build_vanilla_memory_argv()),
        (
            "inspect_vanilla_memory",
            [
                "inspect-vanilla-memory",
                "--database",
                "/private/memory/vanilla-memory.sqlite3",
            ],
        ),
        (
            "inspect_vanilla_context_coverage",
            [
                "inspect-vanilla-context-coverage",
                "--source-mod",
                "/private/source",
                "--database",
                "/private/memory/vanilla-memory.sqlite3",
                "--database-sha256",
                "a" * 64,
                "--logical-digest",
                "b" * 64,
                "--game-version",
                "Synthetic v1",
            ],
        ),
    ],
)
def test_vanilla_memory_safety_errors_remain_content_free(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    function_name: str,
    argv: list[str],
) -> None:
    def fail(*args: object) -> dict[str, object]:
        raise SafetyError("vanilla_memory_validation_failed")

    monkeypatch.setattr(cli, function_name, fail)

    result = main(argv)

    assert result == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "status": "error",
        "code": "SafetyError",
        "message": "vanilla_memory_validation_failed",
    }
    assert "/private/" not in captured.err


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


def test_context_arguments_are_exposed_and_dispatched(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received: dict[str, object] = {}

    def fake_translate(
        source_mod: Path,
        output: Path,
        model: str,
        **kwargs: object,
    ) -> dict[str, object]:
        received.update(
            {"source_mod": source_mod, "output": output, "model": model}
        )
        received.update(kwargs)
        return {"status": "synthetic"}

    monkeypatch.setattr(cli, "translate_mod", fake_translate)
    result = main(
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
            "--context-policy",
            "exact_context_v1",
            "--vanilla-memory-database",
            "/private/memory.sqlite3",
            "--vanilla-memory-database-sha256",
            "a" * 64,
            "--vanilla-memory-logical-digest",
            "b" * 64,
            "--vanilla-memory-game-version",
            "Synthetic v1",
        ]
    )

    assert result == 0
    assert json.loads(capsys.readouterr().out) == {"status": "synthetic"}
    assert received["context_policy"] == "exact_context_v1"
    assert received["vanilla_memory_database"] == Path(
        "/private/memory.sqlite3"
    )
    assert received["vanilla_memory_database_sha256"] == "a" * 64
    assert received["vanilla_memory_logical_digest"] == "b" * 64
    assert received["vanilla_memory_game_version"] == "Synthetic v1"


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
    assert "--context-policy CONTEXT_POLICY" in output
    assert "--vanilla-memory-database VANILLA_MEMORY_DATABASE" in output
    assert "--vanilla-memory-database-sha256 SHA256" in output
    assert "--vanilla-memory-logical-digest SHA256" in output
    assert "--vanilla-memory-game-version VANILLA_MEMORY_GAME_VERSION" in output


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


def _consolidation_argv() -> list[str]:
    return [
        "consolidate-reviewed-mod",
        "--reviewed-candidate",
        "/reviewed",
        "--application-report-sha256",
        "1" * 64,
        "--main-package",
        "/main-package",
        "--main-package-sha256",
        "9" * 64,
        "--supplement-package",
        "/supplement",
        "--supplement-package-sha256",
        "2" * 64,
        "--supplement-report-sha256",
        "3" * 64,
        "--supplement-payload-sha256",
        "4" * 64,
        "--supplement-localisation-sha256",
        "5" * 64,
        "--supplement-source-mod",
        "/source",
        "--supplement-source-sha256",
        "6" * 64,
        "--supplement-mapping-sha256",
        "7" * 64,
        "--supplement-content-mapping-sha256",
        "a" * 64,
        "--technical-smoke-evidence",
        "/technical-status.json",
        "--technical-smoke-evidence-sha256",
        "8" * 64,
        "--owner-visual-confirmation",
        "/owner-confirmation.json",
        "--owner-visual-confirmation-sha256",
        "b" * 64,
        "--output",
        "/package",
        "--mod-slug",
        "example_ru_native",
        "--display-name",
        "Example native translation",
        "--dependency-name",
        "Example",
        "--supported-version",
        "4.4.*",
        "--planned-install-root",
        "/active/mod",
    ]


def test_consolidate_reviewed_mod_exposes_closed_interface() -> None:
    args = parser().parse_args(_consolidation_argv())
    assert args.reviewed_candidate == Path("/reviewed")
    assert args.main_package == Path("/main-package")
    assert args.supplement_package == Path("/supplement")
    assert args.supplement_source_mod == Path("/source")
    assert args.technical_smoke_evidence == Path(
        "/technical-status.json"
    )
    assert args.owner_visual_confirmation == Path(
        "/owner-confirmation.json"
    )
    assert args.output == Path("/package")
    assert args.mod_slug == "example_ru_native"
    assert args.dependency_name == "Example"
    assert args.planned_install_root == Path("/active/mod")
    assert args.technical_smoke_evidence_sha256 == "8" * 64
    assert args.owner_visual_confirmation_sha256 == "b" * 64


def test_consolidate_reviewed_mod_dispatches_without_ollama(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received: tuple[object, ...] | None = None

    def consolidate(*args: object) -> dict[str, object]:
        nonlocal received
        received = args
        return {"status": "consolidated_reviewed_mod_package_created"}

    monkeypatch.setattr(cli, "consolidate_reviewed_mod", consolidate)
    result = main(_consolidation_argv())
    assert result == 0
    assert received == (
        Path("/reviewed"),
        "1" * 64,
        Path("/main-package"),
        "9" * 64,
        Path("/supplement"),
        "2" * 64,
        "3" * 64,
        "4" * 64,
        "5" * 64,
        Path("/source"),
        "6" * 64,
        "7" * 64,
        "a" * 64,
        Path("/technical-status.json"),
        "8" * 64,
        Path("/owner-confirmation.json"),
        "b" * 64,
        Path("/package"),
        "example_ru_native",
        "Example native translation",
        "Example",
        "4.4.*",
        Path("/active/mod"),
    )
    assert json.loads(capsys.readouterr().out) == {
        "status": "consolidated_reviewed_mod_package_created"
    }


def test_consolidate_reviewed_mod_help_lists_all_authorities(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        parser().parse_args(["consolidate-reviewed-mod", "--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    for option in (
        "--reviewed-candidate REVIEWED_CANDIDATE",
        "--application-report-sha256 SHA256",
        "--main-package MAIN_PACKAGE",
        "--main-package-sha256 SHA256",
        "--supplement-package SUPPLEMENT_PACKAGE",
        "--supplement-package-sha256 SHA256",
        "--supplement-report-sha256 SHA256",
        "--supplement-payload-sha256 SHA256",
        "--supplement-localisation-sha256 SHA256",
        "--supplement-source-mod SUPPLEMENT_SOURCE_MOD",
        "--supplement-source-sha256 SHA256",
        "--supplement-mapping-sha256 SHA256",
        "--supplement-content-mapping-sha256 SHA256",
        "--technical-smoke-evidence TECHNICAL_SMOKE_EVIDENCE",
        "--technical-smoke-evidence-sha256 SHA256",
        "--owner-visual-confirmation OWNER_VISUAL_CONFIRMATION",
        "--owner-visual-confirmation-sha256 SHA256",
        "--planned-install-root PLANNED_INSTALL_ROOT",
    ):
        assert option in output


def test_consolidate_reviewed_mod_rejects_malformed_pin() -> None:
    argv = _consolidation_argv()
    index = argv.index("--supplement-package-sha256") + 1
    argv[index] = "A" * 64
    with pytest.raises(SystemExit) as exc:
        parser().parse_args(argv)
    assert exc.value.code == 2
