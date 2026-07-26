from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .engine import SafetyError, inspect_mod, translate_mod
from .ollama import OllamaError


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
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "inspect":
            report = inspect_mod(args.source_mod)
        else:
            report = translate_mod(
                args.source_mod,
                args.output,
                args.model,
                dry_run=args.dry_run,
                max_occurrences_per_file=args.max_occurrences_per_file,
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
