#!/usr/bin/env python3
"""Standard-library structural checks for repository Markdown."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Dict, List, Tuple
from urllib.parse import unquote


LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
TABLE_SEPARATOR = re.compile(r"^:?-{3,}:?$")


def _target(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")]
    if " " in value:
        return value.split(" ", 1)[0]
    return value


def _cells(line: str) -> Tuple[str, ...]:
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]
    return tuple(cell.strip() for cell in value.split("|"))


def validate(root: Path) -> Dict[str, object]:
    markdown_files = sorted(root.rglob("*.md"))
    errors: List[str] = []
    relative_links = 0
    fences = 0
    tables = 0
    for path in markdown_files:
        relative_name = path.relative_to(root).as_posix()
        text = path.read_text("utf-8")
        lines = text.splitlines()

        open_fence = ""
        for number, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            marker = "```" if stripped.startswith("```") else "~~~" if stripped.startswith("~~~") else ""
            if marker:
                if not open_fence:
                    open_fence = marker
                    fences += 1
                elif open_fence == marker:
                    open_fence = ""
        if open_fence:
            errors.append(f"{relative_name}:unclosed-fence")

        for match in LINK.finditer(text):
            target = _target(match.group(1))
            lowered = target.casefold()
            if (
                not target
                or target.startswith("#")
                or lowered.startswith(("http://", "https://", "mailto:"))
            ):
                continue
            relative_links += 1
            file_part = unquote(target.split("#", 1)[0])
            if not file_part:
                continue
            resolved = (path.parent / file_part).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(f"{relative_name}:link-outside-root")
                continue
            if not resolved.exists():
                errors.append(f"{relative_name}:missing-link")

        for index in range(1, len(lines)):
            separator = _cells(lines[index]) if "|" in lines[index] else ()
            if not separator or not all(TABLE_SEPARATOR.fullmatch(cell) for cell in separator):
                continue
            header = _cells(lines[index - 1])
            tables += 1
            if len(header) != len(separator):
                errors.append(f"{relative_name}:table-column-mismatch")
                continue
            cursor = index + 1
            while cursor < len(lines) and "|" in lines[cursor] and lines[cursor].strip():
                if len(_cells(lines[cursor])) != len(separator):
                    errors.append(f"{relative_name}:table-row-mismatch")
                    break
                cursor += 1

    return {
        "schema": "m1a-markdown-validation-v1",
        "markdown_file_count": len(markdown_files),
        "relative_link_count": relative_links,
        "fenced_block_count": fences,
        "table_count": tables,
        "error_count": len(errors),
        "passed": not errors,
        "error_codes": sorted(set(error.rsplit(":", 1)[-1] for error in errors)),
    }


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    try:
        result = validate(root)
    except (OSError, UnicodeError):
        result = {
            "schema": "m1a-markdown-validation-v1",
            "error_count": 1,
            "passed": False,
            "error_codes": ["validation-io-failure"],
        }
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
