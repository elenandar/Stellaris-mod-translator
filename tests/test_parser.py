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


def test_versionless_l_prefixed_keys_are_entries_not_language_headers() -> None:
    data = (
        b'l_english:\n'
        b' l_cluster: "Cluster text"\n'
        b' l_english_name: "English name"\n'
    )
    parsed = parse_localisation(data)

    assert [entry.key for entry in parsed.entries] == [
        "l_cluster",
        "l_english_name",
    ]
    assert parsed.render() == data


def test_russian_candidate_is_losslessly_parsed_for_review_alignment() -> None:
    data = (
        'l_russian:\n'
        ' duplicate.key:0 "Первый $NAME$"\n'
        ' duplicate.key:0 "Второй \\"текст\\""\n'
    ).encode()
    parsed = parse_localisation(data)

    assert parsed.language == "russian"
    assert parsed.is_english is False
    assert len(parsed.entries) == 2
    assert parsed.entries[0].key == parsed.entries[1].key
    assert parsed.render() == data


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


@pytest.mark.parametrize(
    "translation",
    [
        "Текст __SMT_TOKEN_0000__ __SMT_TOKEN_1__",
        "Текст __SMT_TOKEN_0000__ __SMT_OTHER__",
        "Текст __SMT_TOKEN_0000__ __SMT_TOKEN_999999_extra",
    ],
)
def test_any_unexpected_reserved_namespace_is_rejected(
    translation: str,
) -> None:
    entry = parse_localisation(
        b'l_english:\n k:0 "Human $A$"\n'
    ).entries[0]
    with pytest.raises(ValueError, match="foreign protected token"):
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


def test_late_english_header_rejects_the_whole_file() -> None:
    data = b'# leading comment\nl_english:\n key:0 "text"\n'
    with pytest.raises(ParseError, match="english_header_not_first_line"):
        parse_localisation(data)


@pytest.mark.parametrize(
    "data",
    [
        b' l_english:\n key:0 "text"\n',
        b'l_english:\n key:0 "text"\n l_french:\n',
        b'l_english:\n key:0 "text"\nl_french: trailing text\n',
        b'l_english:\n key:0 "text"\nl_french:trailing text\n',
    ],
)
def test_malformed_language_header_rejects_the_whole_file(data: bytes) -> None:
    with pytest.raises(ParseError, match="malformed_language_header"):
        parse_localisation(data)


@pytest.mark.parametrize(
    "data",
    [
        b'l_english:\n key:0 "text"\nl_french:\n other:0 "texte"\n',
        b'l_french:\n key:0 "texte"\nl_english:\n other:0 "text"\n',
        b'l_english:\n key:0 "text"\nl_english:\n other:0 "more"\n',
    ],
)
def test_multiple_or_mixed_language_sections_reject_the_whole_file(
    data: bytes,
) -> None:
    with pytest.raises(ParseError, match="multiple_language_headers"):
        parse_localisation(data)


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"l_english:\n k:0 \"\xff\"\n", "invalid_utf8"),
        (b'l_english:\r\n k:0 "x"\n', "mixed_newlines"),
        (b'l_english:\r k:0 "x"\r', "bare_cr"),
        ('l_english:\n k:0 "x\ufeffy"\n'.encode(), "hidden_bom"),
        (b'l_english:\n k:0 "x\x00y"\n', "nul_control"),
        (b'l_english:\n k:0 "x\x01y"\n', "c0_control"),
        (b'l_english:\n k:0 "x\x7fy"\n', "c0_control"),
        ('l_english:\n k:0 "x\u0085y"\n'.encode(), "c1_control"),
        ('l_english:\n k:0 "x\u200by"\n'.encode(), "unicode_format_control"),
        ('l_english:\n k:0 "x\u202ey"\n'.encode(), "unicode_format_control"),
        ('l_english:\n k:0 "x\u2066y"\n'.encode(), "unicode_format_control"),
        ('l_english:\n k:0 "x\u2028y"\n'.encode(), "unicode_line_separator"),
        ('l_english:\n k:0 "x\u2029y"\n'.encode(), "unicode_line_separator"),
    ],
)
def test_invalid_file_is_rejected(data: bytes, reason: str) -> None:
    with pytest.raises(ParseError, match=reason):
        parse_localisation(data)


def test_atom_only_result_cannot_delete_nonempty_human_text() -> None:
    entry = parse_localisation(
        b'l_english:\n key:0 "Human $NAME$"\n'
    ).entries[0]
    with pytest.raises(ValueError, match="human text is empty"):
        entry.restore_translation("__SMT_TOKEN_0000__")
