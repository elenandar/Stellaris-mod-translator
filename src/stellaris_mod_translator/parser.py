"""A deliberately small lossless parser for the MVP-0 supported subset."""

from __future__ import annotations

from dataclasses import dataclass
import re


class ParseError(ValueError):
    """The whole file is unsafe to process."""


_HEADER = re.compile(rb"^l_english:(?P<tail>[ \t]*(?:#.*)?)$")
_LANGUAGE_HEADER = re.compile(
    rb"^l_(?P<language>[A-Za-z][A-Za-z0-9_]*):"
    rb"(?P<tail>[ \t]*(?:#.*)?)$"
)
_LANGUAGE_HEADER_LIKE = re.compile(
    rb"^[ \t]*l_[A-Za-z][A-Za-z0-9_]*[ \t]*:(?![0-9])"
)
_ENTRY = re.compile(
    rb'^(?P<indent>[ \t]*)(?P<key>[A-Za-z0-9_.-]+)(?P<precolon>[ \t]*):'
    rb'(?P<version>[0-9]*)(?P<space>[ \t]+)"'
    rb'(?P<value>(?:\\["\\n]|[^"\\\r\n])*)"'
    rb"(?P<tail>[ \t]*(?:#.*)?)$"
)
_ENTRY_LIKE = re.compile(rb"^[ \t]*[^# \t][^:\r\n]*:")
_ATOM = re.compile(r"\$[^$\r\n]+\$|\[[^\[\]\r\n]+\]|£[^£\r\n]+£|§.")
_ESCAPE = re.compile(r'\\"|\\\\|\\n')
_PROTECTED = re.compile(
    r'\\"|\\\\|\\n|\$[^$\r\n]+\$|\[[^\[\]\r\n]+\]|£[^£\r\n]+£|§.'
)
_UNSAFE_UNPROTECTED = frozenset('$[]£§\\"')


@dataclass(frozen=True)
class ProtectedToken:
    placeholder: str
    original: str
    is_atom: bool


@dataclass(frozen=True)
class Entry:
    line_index: int
    key: str
    value_start: int
    value_end: int
    value: str
    leading_whitespace: str
    trailing_whitespace: str
    protected: tuple[ProtectedToken, ...]

    def model_text(self) -> str:
        pieces: list[str] = []
        cursor = 0
        for index, match in enumerate(_PROTECTED.finditer(self.value)):
            pieces.append(self.value[cursor : match.start()])
            pieces.append(self.protected[index].placeholder)
            cursor = match.end()
        pieces.append(self.value[cursor:])
        rendered = "".join(pieces)
        start = len(self.leading_whitespace)
        end = len(rendered) - len(self.trailing_whitespace)
        return rendered[start:end]

    def restore_translation(self, translated: str) -> str:
        if not isinstance(translated, str):
            raise ValueError("translation must be a string")
        try:
            translated.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("translation is not UTF-8 encodable") from exc
        translated_human_text = translated
        for token in self.protected:
            translated_human_text = translated_human_text.replace(
                token.placeholder, ""
            )
        if self._has_human_text() and not translated_human_text.strip():
            raise ValueError("translation human text is empty")
        if any(
            ord(char) < 0x20
            or ord(char) == 0x7F
            or 0x80 <= ord(char) <= 0x9F
            for char in translated
        ):
            raise ValueError("translation contains control characters")
        if any(char in "\u2028\u2029\ufeff" for char in translated):
            raise ValueError("translation contains unsafe Unicode separators or BOM")
        if any(char in _UNSAFE_UNPROTECTED for char in translated):
            reduced = translated
            for token in self.protected:
                reduced = reduced.replace(token.placeholder, "")
            if any(char in _UNSAFE_UNPROTECTED for char in reduced):
                raise ValueError("translation introduces protected syntax")

        positions: list[int] = []
        restored = translated
        for token in self.protected:
            if restored.count(token.placeholder) != 1:
                raise ValueError("protected token missing or duplicated")
            positions.append(restored.index(token.placeholder))
        if positions != sorted(positions):
            raise ValueError("protected token order changed")

        expected = {token.placeholder for token in self.protected}
        foreign = set(re.findall(r"__SMT_[A-Z]+_[0-9]{4}__", restored)) - expected
        if foreign:
            raise ValueError("foreign protected token")
        for token in self.protected:
            restored = restored.replace(token.placeholder, token.original)
        return self.leading_whitespace + restored + self.trailing_whitespace

    def _has_human_text(self) -> bool:
        human_text = self.model_text()
        for token in self.protected:
            human_text = human_text.replace(token.placeholder, "")
        return bool(human_text.strip())


@dataclass(frozen=True)
class ParsedFile:
    original: bytes
    bom: bool
    newline: bytes
    lines: tuple[bytes, ...]
    header_line: int | None
    entries: tuple[Entry, ...]
    diagnostics: tuple[dict[str, object], ...]

    @property
    def is_english(self) -> bool:
        return self.header_line is not None

    def render(
        self, replacements: dict[int, str] | None = None, *, russian_header: bool = False
    ) -> bytes:
        replacements = replacements or {}
        lines = list(self.lines)
        if russian_header and self.header_line is not None:
            raw = lines[self.header_line]
            body, ending = _split_ending(raw)
            match = _HEADER.fullmatch(body)
            assert match is not None
            lines[self.header_line] = (
                b"l_russian:" + match.group("tail") + ending
            )
        for entry in self.entries:
            if entry.line_index not in replacements:
                continue
            raw = lines[entry.line_index]
            body, ending = _split_ending(raw)
            value = replacements[entry.line_index].encode("utf-8")
            lines[entry.line_index] = (
                body[: entry.value_start] + value + body[entry.value_end :] + ending
            )
        prefix = b"\xef\xbb\xbf" if self.bom else b""
        return prefix + b"".join(lines)


def parse_localisation(data: bytes) -> ParsedFile:
    bom = data.startswith(b"\xef\xbb\xbf")
    payload = data[3:] if bom else data
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError("invalid_utf8") from exc
    if "\ufeff" in decoded:
        raise ParseError("hidden_bom")
    if "\x00" in decoded:
        raise ParseError("nul_control")
    if any(
        (ord(char) < 0x20 and char not in "\t\r\n") or ord(char) == 0x7F
        for char in decoded
    ):
        raise ParseError("c0_control")
    if any(0x80 <= ord(char) <= 0x9F for char in decoded):
        raise ParseError("c1_control")
    if any(char in "\u2028\u2029" for char in decoded):
        raise ParseError("unicode_line_separator")
    if b"\r" in payload.replace(b"\r\n", b""):
        raise ParseError("bare_cr")
    has_crlf = b"\r\n" in payload
    without_crlf = payload.replace(b"\r\n", b"")
    has_lf = b"\n" in without_crlf
    if has_crlf and has_lf:
        raise ParseError("mixed_newlines")
    newline = b"\r\n" if has_crlf else b"\n"
    lines = tuple(payload.splitlines(keepends=True))
    if not lines and payload == b"":
        lines = ()
    elif payload and not lines:
        lines = (payload,)

    language_headers: list[tuple[int, re.Match[bytes]]] = []
    for index, raw in enumerate(lines):
        body, _ = _split_ending(raw)
        header = _LANGUAGE_HEADER.fullmatch(body)
        if header is not None:
            language_headers.append((index, header))
        elif _LANGUAGE_HEADER_LIKE.match(body):
            raise ParseError("malformed_language_header")
    if not language_headers:
        raise ParseError("missing_language_header")
    if len(language_headers) != 1:
        raise ParseError("multiple_language_headers")

    language_line, language_header = language_headers[0]
    is_english = language_header.group("language") == b"english"
    if is_english and language_line != 0:
        raise ParseError("english_header_not_first_line")

    header_line: int | None = language_line if is_english else None
    entries: list[Entry] = []
    diagnostics: list[dict[str, object]] = []
    if not is_english:
        parsed = ParsedFile(
            original=data,
            bom=bom,
            newline=newline,
            lines=lines,
            header_line=None,
            entries=(),
            diagnostics=(),
        )
        if parsed.render() != data:
            raise AssertionError("lossless render invariant failed")
        return parsed

    for index, raw in enumerate(lines):
        body, _ = _split_ending(raw)
        if index == header_line:
            continue
        match = _ENTRY.fullmatch(body)
        if match:
            value_bytes = match.group("value")
            value = value_bytes.decode("utf-8")
            try:
                protected = _protected_tokens(value)
            except ParseError as exc:
                diagnostics.append(
                    {
                        "code": "unsupported_entry",
                        "line": index + 1,
                        "reason": str(exc),
                    }
                )
                continue
            whitespace = re.fullmatch(r"([ \t]*)(.*?)([ \t]*)", value)
            assert whitespace is not None
            entries.append(
                Entry(
                    line_index=index,
                    key=match.group("key").decode("ascii"),
                    value_start=match.start("value"),
                    value_end=match.end("value"),
                    value=value,
                    leading_whitespace=whitespace.group(1),
                    trailing_whitespace=whitespace.group(3),
                    protected=protected,
                )
            )
        elif _ENTRY_LIKE.match(body):
            diagnostics.append(
                {"code": "unsupported_entry", "line": index + 1}
            )

    parsed = ParsedFile(
        original=data,
        bom=bom,
        newline=newline,
        lines=lines,
        header_line=header_line,
        entries=tuple(entries),
        diagnostics=tuple(diagnostics),
    )
    if parsed.render() != data:
        raise AssertionError("lossless render invariant failed")
    return parsed


def _protected_tokens(value: str) -> tuple[ProtectedToken, ...]:
    tokens: list[ProtectedToken] = []
    for index, match in enumerate(_PROTECTED.finditer(value)):
        original = match.group(0)
        tokens.append(
            ProtectedToken(
                placeholder=f"__SMT_TOKEN_{index:04d}__",
                original=original,
                is_atom=bool(_ATOM.fullmatch(original)),
            )
        )
    # Every backslash and every markup delimiter must belong to a supported token.
    residue = value
    for token in tokens:
        residue = residue.replace(token.original, "", 1)
    if "\\" in residue:
        raise ParseError("unsupported_escape")
    if any(delimiter in residue for delimiter in "$[]£§"):
        raise ParseError("ambiguous_markup")
    return tuple(tokens)


def _split_ending(line: bytes) -> tuple[bytes, bytes]:
    if line.endswith(b"\r\n"):
        return line[:-2], b"\r\n"
    if line.endswith(b"\n"):
        return line[:-1], b"\n"
    return line, b""
