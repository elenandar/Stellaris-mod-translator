from __future__ import annotations

import pytest

from stellaris_mod_translator.parser import ParseError, parse_localisation


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_lossless_round_trip_bom_and_newlines(bom: bytes, newline: bytes) -> None:
    data = bom + newline.join(
        [
            b"l_english:",
            b" # comment",
            b' key:0 "Human $NAME$ [Root.GetName] \xc2\xa3energy\xc2\xa3 \xc2\xa7Ggreen\xc2\xa7!"',
            b"",
        ]
    )
    parsed = parse_localisation(data)
    assert parsed.render() == data
    assert parsed.newline == newline


def test_preserves_comments_whitespace_versions_duplicates_and_escapes() -> None:
    data = (
        b'\xef\xbb\xbfl_english: # h\r\n'
        b'  same.key :12 "First \\"quoted\\"\\\\path\\nnext" # one\r\n'
        b'\tsame.key: "Second"  # two\r\n'
    )
    parsed = parse_localisation(data)
    assert len(parsed.entries) == 2
    assert parsed.entries[0].key == parsed.entries[1].key
    assert parsed.render() == data

    replacement = parsed.entries[0].restore_translation(
        'Первый __SMT_TOKEN_0000__текст__SMT_TOKEN_0001__'
        'путь__SMT_TOKEN_0002__каталог__SMT_TOKEN_0003__далее'
    )
    rendered = parsed.render(
        {parsed.entries[0].line_index: replacement}, russian_header=True
    )
    assert rendered.startswith(b"\xef\xbb\xbfl_russian: # h\r\n")
    assert b"  same.key :12 " in rendered
    assert rendered.count(b'\\"') == 2
    assert b"\\\\" in rendered and b"\\n" in rendered
    assert rendered.endswith(b'\tsame.key: "Second"  # two\r\n')


def test_every_supported_atom_is_opaque_and_restored() -> None:
    data = (
        'l_english:\n k:0 "Hi $NAME$ [Root.GetName] £energy£ §Ggreen§!"\n'
    ).encode()
    entry = parse_localisation(data).entries[0]
    model_text = entry.model_text()
    assert model_text == (
        "Hi __SMT_TOKEN_0000__ __SMT_TOKEN_0001__ "
        "__SMT_TOKEN_0002__ __SMT_TOKEN_0003__green__SMT_TOKEN_0004__"
    )
    translated = (
        "Привет __SMT_TOKEN_0000__ __SMT_TOKEN_0001__ "
        "__SMT_TOKEN_0002__ __SMT_TOKEN_0003__зелёный__SMT_TOKEN_0004__"
    )
    assert entry.restore_translation(translated).endswith("§Gзелёный§!")


@pytest.mark.parametrize(
    "translation",
    [
        "x __SMT_TOKEN_0001__ __SMT_TOKEN_0000__",
        "x __SMT_TOKEN_0000__",
        "x __SMT_TOKEN_0000__ __SMT_TOKEN_0001__ __SMT_TOKEN_9999__",
    ],
)
def test_atom_reorder_deletion_or_foreign_id_is_rejected(translation: str) -> None:
    entry = parse_localisation(b'l_english:\n k:0 "x $A$ [B]"\n').entries[0]
    with pytest.raises(ValueError):
        entry.restore_translation(translation)


def test_malformed_entry_is_preserved_as_fallback() -> None:
    data = b'l_english:\n good:0 "ok"\n bad:0 unquoted\n'
    parsed = parse_localisation(data)
    assert len(parsed.entries) == 1
    assert parsed.diagnostics == (
        {"code": "unsupported_entry", "line": 3},
    )
    assert parsed.render() == data


def test_value_edge_whitespace_is_not_sent_to_model_and_is_preserved() -> None:
    parsed = parse_localisation(b'l_english:\n key:0 "  Human text \t"\n')
    entry = parsed.entries[0]
    assert entry.model_text() == "Human text"
    assert entry.restore_translation("Текст") == "  Текст \t"


def test_ambiguous_markup_is_an_entry_fallback() -> None:
    parsed = parse_localisation(b'l_english:\n key:0 "Broken $ATOM"\n')
    assert parsed.entries == ()
    assert parsed.diagnostics[0]["reason"] == "ambiguous_markup"


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"l_english:\n k:0 \"\xff\"\n", "invalid_utf8"),
        (b'l_english:\r\n k:0 "x"\n', "mixed_newlines"),
        (b'l_english:\r k:0 "x"\r', "bare_cr"),
    ],
)
def test_invalid_file_is_rejected(data: bytes, reason: str) -> None:
    with pytest.raises(ParseError, match=reason):
        parse_localisation(data)
