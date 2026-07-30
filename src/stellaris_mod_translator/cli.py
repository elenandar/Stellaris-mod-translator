from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from .consolidate_reviewed_mod import consolidate_reviewed_mod
from .engine import SafetyError, inspect_mod, translate_mod
from .ollama import OllamaError
from .package_reviewed_mod import package_reviewed_mod
from .review import build_review_pack
from .review_application import apply_review_decisions


def _occurrence_limit(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "must be an integer from 1 to 100"
        ) from exc
    if parsed < 1 or parsed > 100:
        raise argparse.ArgumentTypeError("must be an integer from 1 to 100")
    return parsed


def _sha256_pin(value: str) -> str:
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise argparse.ArgumentTypeError(
            "must be exactly 64 lowercase hexadecimal characters"
        )
    return value


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="stellaris_mod_translator",
        description="Build a separate, local-only Russian localisation candidate.",
    )
    commands = root.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="inspect supported localisation")
    inspect.add_argument("--source-mod", required=True, type=Path)

    translate = commands.add_parser(
        "translate-mod", help="translate supported localisation through local Ollama"
    )
    translate.add_argument("--source-mod", required=True, type=Path)
    translate.add_argument("--output", required=True, type=Path)
    translate.add_argument("--model", required=True)
    translate.add_argument(
        "--max-occurrences-per-file",
        type=_occurrence_limit,
        metavar="N",
        help=(
            "translate only the first N supported occurrences in each "
            "English file (1-100)"
        ),
    )
    translate.add_argument("--dry-run", action="store_true")
    translate.add_argument(
        "--workspace",
        type=Path,
        help="checkpoint a full translation job in a private local SQLite file",
    )
    translate.add_argument(
        "--resume",
        action="store_true",
        help="continue an existing --workspace job",
    )

    review = commands.add_parser(
        "build-review-pack",
        help="build an offline editorial review pack from an exact candidate",
    )
    review.add_argument("--source-mod", required=True, type=Path)
    review.add_argument("--candidate", required=True, type=Path)
    review.add_argument("--output", required=True, type=Path)
    review.add_argument(
        "--candidate-report-sha256",
        type=_sha256_pin,
        metavar="SHA256",
        help=(
            "required exact translation-report.json pin for schema-v3 "
            "full candidates; omit for the legacy exact pilot"
        ),
    )

    apply_review = commands.add_parser(
        "apply-review-decisions",
        help="apply a complete decision set to a new reviewed candidate",
    )
    apply_review.add_argument("--source-mod", required=True, type=Path)
    apply_review.add_argument("--candidate", required=True, type=Path)
    apply_review.add_argument(
        "--candidate-report-sha256",
        type=_sha256_pin,
        metavar="SHA256",
        help=(
            "required exact translation-report.json pin for schema-v3 "
            "full candidates; omit for the legacy exact pilot"
        ),
    )
    apply_review.add_argument("--decisions", required=True, type=Path)
    apply_review.add_argument("--output", required=True, type=Path)

    package = commands.add_parser(
        "package-reviewed-mod",
        help="build a private install package from a reviewed candidate",
    )
    package.add_argument("--reviewed-candidate", required=True, type=Path)
    package.add_argument(
        "--application-report-sha256",
        required=True,
        type=_sha256_pin,
        metavar="SHA256",
    )
    package.add_argument("--output", required=True, type=Path)
    package.add_argument("--mod-slug", required=True)
    package.add_argument("--display-name", required=True)
    package.add_argument("--dependency-name", required=True)
    package.add_argument("--supported-version", required=True)
    package.add_argument("--planned-install-root", required=True, type=Path)
    package.add_argument(
        "--allow-technical-residue",
        action="store_true",
        help=(
            "preserve explicitly acknowledged unsupported/skipped residue "
            "without claiming full editorial approval"
        ),
    )
    consolidate = commands.add_parser(
        "consolidate-reviewed-mod",
        help=(
            "build a fresh package from a reviewed candidate and a "
            "pinned owner-reviewed replace supplement"
        ),
    )
    consolidate.add_argument(
        "--reviewed-candidate", required=True, type=Path
    )
    consolidate.add_argument(
        "--application-report-sha256",
        required=True,
        type=_sha256_pin,
        metavar="SHA256",
    )
    consolidate.add_argument("--main-package", required=True, type=Path)
    consolidate.add_argument(
        "--main-package-sha256",
        required=True,
        type=_sha256_pin,
        metavar="SHA256",
    )
    consolidate.add_argument(
        "--supplement-package", required=True, type=Path
    )
    consolidate.add_argument(
        "--supplement-package-sha256",
        required=True,
        type=_sha256_pin,
        metavar="SHA256",
    )
    consolidate.add_argument(
        "--supplement-report-sha256",
        required=True,
        type=_sha256_pin,
        metavar="SHA256",
    )
    consolidate.add_argument(
        "--supplement-payload-sha256",
        required=True,
        type=_sha256_pin,
        metavar="SHA256",
    )
    consolidate.add_argument(
        "--supplement-localisation-sha256",
        required=True,
        type=_sha256_pin,
        metavar="SHA256",
    )
    consolidate.add_argument(
        "--supplement-source-mod", required=True, type=Path
    )
    consolidate.add_argument(
        "--supplement-source-sha256",
        required=True,
        type=_sha256_pin,
        metavar="SHA256",
    )
    consolidate.add_argument(
        "--supplement-mapping-sha256",
        required=True,
        type=_sha256_pin,
        metavar="SHA256",
    )
    consolidate.add_argument(
        "--supplement-content-mapping-sha256",
        required=True,
        type=_sha256_pin,
        metavar="SHA256",
    )
    consolidate.add_argument(
        "--owner-smoke-evidence", required=True, type=Path
    )
    consolidate.add_argument(
        "--owner-smoke-evidence-sha256",
        required=True,
        type=_sha256_pin,
        metavar="SHA256",
    )
    consolidate.add_argument("--output", required=True, type=Path)
    consolidate.add_argument("--mod-slug", required=True)
    consolidate.add_argument("--display-name", required=True)
    consolidate.add_argument("--dependency-name", required=True)
    consolidate.add_argument("--supported-version", required=True)
    consolidate.add_argument(
        "--planned-install-root", required=True, type=Path
    )
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "inspect":
            report = inspect_mod(args.source_mod)
        elif args.command == "translate-mod":
            report = translate_mod(
                args.source_mod,
                args.output,
                args.model,
                dry_run=args.dry_run,
                max_occurrences_per_file=args.max_occurrences_per_file,
                workspace=args.workspace,
                resume=args.resume,
            )
        elif args.command == "build-review-pack":
            report = build_review_pack(
                args.source_mod,
                args.candidate,
                args.output,
                candidate_report_sha256=args.candidate_report_sha256,
            )
        elif args.command == "apply-review-decisions":
            report = apply_review_decisions(
                args.source_mod,
                args.candidate,
                args.decisions,
                args.output,
                candidate_report_sha256=args.candidate_report_sha256,
            )
        elif args.command == "package-reviewed-mod":
            report = package_reviewed_mod(
                args.reviewed_candidate,
                args.application_report_sha256,
                args.output,
                args.mod_slug,
                args.display_name,
                args.dependency_name,
                args.supported_version,
                args.planned_install_root,
                allow_technical_residue=args.allow_technical_residue,
            )
        else:
            report = consolidate_reviewed_mod(
                args.reviewed_candidate,
                args.application_report_sha256,
                args.main_package,
                args.main_package_sha256,
                args.supplement_package,
                args.supplement_package_sha256,
                args.supplement_report_sha256,
                args.supplement_payload_sha256,
                args.supplement_localisation_sha256,
                args.supplement_source_mod,
                args.supplement_source_sha256,
                args.supplement_mapping_sha256,
                args.supplement_content_mapping_sha256,
                args.owner_smoke_evidence,
                args.owner_smoke_evidence_sha256,
                args.output,
                args.mod_slug,
                args.display_name,
                args.dependency_name,
                args.supported_version,
                args.planned_install_root,
            )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (SafetyError, OllamaError, OSError) as exc:
        print(
            json.dumps(
                {"status": "error", "code": type(exc).__name__, "message": str(exc)}
            ),
            file=sys.stderr,
        )
        return 2
