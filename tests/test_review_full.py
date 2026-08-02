from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from stellaris_mod_translator import engine, review
from stellaris_mod_translator.engine import (
    SafetyError,
    _snapshot,
    _tree_hash,
    translate_mod,
)
from stellaris_mod_translator.ollama import OllamaResultError
from stellaris_mod_translator.parser import parse_localisation
from stellaris_mod_translator.review import build_review_pack


MODEL_DIGEST = "a" * 64


class FullReviewClient:
    def exact_model(self, tag: str) -> dict[str, str]:
        assert tag == "synthetic-review:1"
        return {"tag": tag, "digest": MODEL_DIGEST}

    def translate(self, *, tag: str, text: str) -> str:
        assert tag == "synthetic-review:1"
        if "FALLBACK_SENTINEL" in text:
            raise OllamaResultError("synthetic fallback")
        if "UNCHANGED_SENTINEL" in text:
            return text
        if "LEADING_SENTINEL" in text:
            return text.replace(
                "__SMT_TOKEN_0000__ after",
                "__SMT_TOKEN_0000__after",
            )
        if "TRAILING_SENTINEL" in text:
            return text.replace(
                "before __SMT_TOKEN_0000__",
                "before__SMT_TOKEN_0000__",
            )
        if "ATOM_SENTINEL" in text:
            return text.replace(
                "ATOM_SENTINEL __SMT_TOKEN_0000__ tail",
                "ATOM_SENTINEL__SMT_TOKEN_0000__tail",
            )
        return "RU " + text


def make_full_review_inputs(
    tmp_path: Path,
    *,
    entry_count: int | None = None,
    hostile_text: bool = False,
    include_replace: bool = False,
    leading_prefix: bool = False,
) -> tuple[Path, Path, str]:
    source = tmp_path / "source"
    source_file = source / "localisation/english/full_l_english.yml"
    source_file.parent.mkdir(parents=True)
    if entry_count is None:
        lines = [
            "l_english:",
            (
                ' changed:0 "CHANGE_SENTINEL '
                '</script><script>synthetic_unicode_Ж"'
                if hostile_text
                else ' changed:0 "CHANGE_SENTINEL"'
            ),
            ' unchanged:0 "UNCHANGED_SENTINEL"',
            ' fallback:0 "FALLBACK_SENTINEL"',
            ' leading:0 "LEADING_SENTINEL$NAME$ after"',
            ' trailing:0 "TRAILING_SENTINEL before $NAME$after"',
            ' atom:0 "ATOM_SENTINEL $NAME$ tail"',
            " unsupported:0 SYNTHETIC_UNSUPPORTED",
        ]
    else:
        lines = ["l_english:"] + [
            f' scale.{index}:0 "Scale entry {index}"'
            for index in range(entry_count)
        ]
    prefix = "# leading comment\n\n" if leading_prefix else ""
    source_file.write_text(prefix + "\n".join(lines) + "\n")
    if include_replace:
        replace_file = (
            source
            / "localisation/english/replace/full_replace_l_english.yml"
        )
        replace_file.parent.mkdir(parents=True)
        replace_file.write_bytes(
            b"\xef\xbb\xbfl_english: # replace-header\r\n"
            b"# replace-comment\r\n"
            b"\r\n"
            b' replace.accept:1 "REPLACE_ACCEPT $NAME$"\r\n'
            b' replace.edit:2 "REPLACE_EDIT [Root.GetName] '
            b'\xc2\xa3energy\xc2\xa3 \xc2\xa7Ggreen\xc2\xa7!"\r\n'
        )
    candidate = tmp_path / "candidate"
    workspace = tmp_path / "translation.smt-workspace.sqlite3"
    translate_mod(
        source,
        candidate,
        "synthetic-review:1",
        workspace=workspace,
        client_factory=FullReviewClient,
    )
    report_path = candidate / "translation-report.json"
    return source, candidate, hashlib.sha256(report_path.read_bytes()).hexdigest()


def extract_pack(output: Path) -> dict[str, object]:
    html = (output / "index.html").read_text()
    encoded = re.search(
        r'<script id="review-data" type="application/octet-stream">([^<]+)</script>',
        html,
    )
    assert encoded is not None
    return json.loads(base64.b64decode(encoded.group(1)))


def colliding_review_source_files() -> list[review.SourceFile]:
    data = b'l_english:\n key:0 "Synthetic"\n'
    parsed = parse_localisation(data)
    return [
        review.SourceFile(
            relative=Path(
                "localisation/english/CaseDir/one_l_english.yml"
            ),
            data=data,
            sha256=hashlib.sha256(data).hexdigest(),
            stat_identity=(1, 1, len(data), 1),
            parsed=parsed,
            error=None,
        ),
        review.SourceFile(
            relative=Path(
                "localisation/english/casedir/two_l_english.yml"
            ),
            data=data,
            sha256=hashlib.sha256(data).hexdigest(),
            stat_identity=(1, 2, len(data), 1),
            parsed=parsed,
            error=None,
        ),
    ]


def test_review_pack_rejects_ambiguous_source_candidate_mapping_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    candidate = tmp_path / "candidate"
    source.mkdir()
    candidate.mkdir()
    source_files = colliding_review_source_files()

    def snapshot(
        path: Path, **kwargs: object
    ) -> list[review.SourceFile]:
        return source_files if path == source.resolve() else []

    monkeypatch.setattr(review, "_snapshot", snapshot)
    report_path = candidate / "translation-report.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "resumability": {
                    "parser_order_version": (
                        "mvp7a-leading-header-parser-order-v2"
                    )
                },
            }
        )
        + "\n"
    )
    pin = hashlib.sha256(report_path.read_bytes()).hexdigest()
    output = tmp_path / "review"
    with pytest.raises(SafetyError, match="candidate_path_collision"):
        build_review_pack(
            source,
            candidate,
            output,
            candidate_report_sha256=pin,
        )

    assert not output.exists()
    assert not list(tmp_path.glob(".review.tmp-*"))


def extract_runtime(output: Path) -> str:
    html = (output / "index.html").read_text()
    scripts = re.findall(r"<script(?: [^>]*)?>(.*?)</script>", html, re.S)
    assert scripts
    return scripts[-1]


def rewrite_report(candidate: Path, mutate: object) -> str:
    report_path = candidate / "translation-report.json"
    report = json.loads(report_path.read_text())
    assert callable(mutate)
    mutate(report)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    return hashlib.sha256(report_path.read_bytes()).hexdigest()


def rebind_candidate_hash(candidate: Path) -> str:
    return rewrite_report(
        candidate,
        lambda report: report["hashes"].__setitem__(
            "output_localisation_sha256",
            _tree_hash(
                [
                    (item.relative, item.data)
                    for item in _snapshot(candidate)
                ]
            ),
        ),
    )


def test_schema_v3_full_candidate_builds_pack_schema_v2_with_warnings(
    tmp_path: Path,
) -> None:
    source, candidate, pin = make_full_review_inputs(tmp_path)
    workspace = tmp_path / "translation.smt-workspace.sqlite3"
    workspace.unlink()
    output = tmp_path / "review"

    result = build_review_pack(
        source,
        candidate,
        output,
        candidate_report_sha256=pin,
    )
    pack = extract_pack(output)

    assert result["counts"] == {
        "total": 7,
        "review_entries": 6,
        "accepted_changed": 4,
        "accepted_unchanged": 1,
        "model_fallback": 1,
        "unsupported": 1,
        "deferred": 0,
        "skipped_files": 0,
        "pending": 0,
        "whitespace_warning_entries": 0,
    }
    assert pack["schema_version"] == 2
    assert pack["review_scope"] == "full_candidate"
    assert pack["candidate_report_schema_version"] == 3
    assert len(pack["entries"]) == 6
    assert [entry["key"] for entry in pack["entries"]] == [
        "changed",
        "unchanged",
        "fallback",
        "leading",
        "trailing",
        "atom",
    ]
    assert [entry["occurrence_ordinal"] for entry in pack["entries"]] == list(
        range(6)
    )
    assert pack["entries"][0]["previous_in_file_id"] is None
    assert (
        pack["entries"][0]["next_in_file_id"]
        == pack["entries"][1]["id"]
    )
    assert (
        pack["entries"][-1]["previous_in_file_id"]
        == pack["entries"][-2]["id"]
    )
    assert pack["entries"][-1]["next_in_file_id"] is None
    assert all(
        set(entry["warnings"]).issubset(review.WARNING_FLAGS)
        for entry in pack["entries"]
    )
    by_status = {entry["status"]: entry for entry in pack["entries"]}
    assert by_status["model_fallback"]["warnings"] == ["model_fallback"]
    assert by_status["accepted_unchanged"]["warnings"] == [
        "accepted_unchanged"
    ]
    by_line = {entry["line"]: entry for entry in pack["entries"]}
    assert by_line[5]["warnings"] == []
    assert by_line[6]["warnings"] == []
    assert by_line[7]["warnings"] == []
    summary = json.loads(
        (output / "review-pack-summary.json").read_text()
    )
    assert summary["schema_version"] == 2
    assert summary["review_scope"] == "full_candidate"
    assert summary["candidate_report_schema_version"] == 3
    assert pack["pack_fingerprint"] == review._sha256_json(
        {
            "schema_version": 2,
            "review_scope": "full_candidate",
            "candidate_report_schema_version": 3,
            "candidate_report_sha256": (
                summary["identities"]["candidate_report_sha256"]
            ),
            "source_localisation_sha256": (
                summary["identities"]["source_localisation_sha256"]
            ),
            "candidate_localisation_sha256": (
                summary["identities"]["candidate_localisation_sha256"]
            ),
            "model": {
                "tag": "synthetic-review:1",
                "digest": MODEL_DIGEST,
            },
            "occurrence_ids": [entry["id"] for entry in pack["entries"]],
            "warning_flags": [
                {
                    "occurrence_id": entry["id"],
                    "warnings": entry["warnings"],
                }
                for entry in pack["entries"]
            ],
            "summary": pack["summary"],
        }
    )


def test_full_review_rejects_rebound_candidate_prefix_mutation(
    tmp_path: Path,
) -> None:
    source, candidate, _ = make_full_review_inputs(
        tmp_path,
        leading_prefix=True,
    )
    candidate_file = (
        candidate / "localisation/russian/full_l_russian.yml"
    )
    candidate_file.write_bytes(
        candidate_file.read_bytes().replace(
            b"# leading comment", b"# changed comment", 1
        )
    )
    pin = rebind_candidate_hash(candidate)

    with pytest.raises(
        SafetyError, match="candidate_line_alignment_mismatch"
    ):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            candidate_report_sha256=pin,
        )


def test_full_review_pack_propagates_qualified_replace_entries(
    tmp_path: Path,
) -> None:
    source, candidate, pin = make_full_review_inputs(
        tmp_path,
        include_replace=True,
    )
    output = tmp_path / "review"

    result = build_review_pack(
        source,
        candidate,
        output,
        candidate_report_sha256=pin,
    )
    pack = extract_pack(output)
    replace_path = (
        "localisation/english/replace/full_replace_l_english.yml"
    )
    replace_entries = [
        entry for entry in pack["entries"] if entry["path"] == replace_path
    ]

    assert len(replace_entries) == 2
    assert [entry["occurrence_ordinal"] for entry in replace_entries] == [0, 1]
    assert replace_entries[0]["protected_atoms"] == ["$NAME$"]
    assert replace_entries[1]["protected_atoms"] == [
        "[Root.GetName]",
        "£energy£",
        "§G",
        "§!",
    ]
    assert result["counts"]["review_entries"] == 8
    assert result["counts"]["skipped_files"] == 0
    candidate_file = (
        candidate
        / "localisation/russian/replace/full_replace_l_russian.yml"
    )
    assert candidate_file.read_bytes().startswith(
        b"\xef\xbb\xbfl_russian: # replace-header\r\n"
    )
    assert b"# replace-comment\r\n\r\n" in candidate_file.read_bytes()


def test_boundary_whitespace_flags_only_outer_human_span_boundaries() -> None:
    assert review._warning_flags(
        "accepted_changed",
        [" source", "middle", "tail "],
        ["source", "middle", "tail"],
    ) == [
        "leading_boundary_whitespace_changed",
        "trailing_boundary_whitespace_changed",
    ]
    assert review._warning_flags(
        "accepted_changed",
        ["left ", " right"],
        ["left", "right"],
    ) == []


@pytest.mark.parametrize(
    "whitespace",
    [" ", "\t", "\u00a0", "\u2009", "\u3000"],
)
def test_boundary_whitespace_uses_fixed_unicode_allowlist(
    whitespace: str,
) -> None:
    assert review._boundary_whitespace(
        whitespace + "text",
        leading=True,
    ) == whitespace
    assert review._boundary_whitespace(
        "text" + whitespace,
        leading=False,
    ) == whitespace


@pytest.mark.parametrize(
    "pin",
    [
        "",
        "A" * 64,
        "0" * 63,
        "g" * 64,
        "0" * 65,
    ],
)
def test_full_report_pin_shape_is_strict(
    tmp_path: Path,
    pin: str,
) -> None:
    source, candidate, _ = make_full_review_inputs(tmp_path)
    with pytest.raises(SafetyError, match="invalid_candidate_report_sha256"):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            candidate_report_sha256=pin,
        )


def test_schema_v3_requires_pin_and_mismatched_pin_is_rejected(
    tmp_path: Path,
) -> None:
    source, candidate, _ = make_full_review_inputs(tmp_path)
    with pytest.raises(SafetyError, match="candidate_report_sha256_required"):
        build_review_pack(source, candidate, tmp_path / "without-pin")
    with pytest.raises(SafetyError, match="candidate_report_identity_mismatch"):
        build_review_pack(
            source,
            candidate,
            tmp_path / "wrong-pin",
            candidate_report_sha256="0" * 64,
        )


@pytest.mark.parametrize(
    ("parser_order_version", "expected_entries"),
    [
        ("mvp4-lossless-parser-order-v1", 1),
        ("mvp7a-leading-header-parser-order-v2", 2),
    ],
)
def test_full_review_replays_known_parser_order_generations(
    tmp_path: Path,
    parser_order_version: str,
    expected_entries: int,
) -> None:
    source = tmp_path / "source"
    english = source / "localisation/english"
    english.mkdir(parents=True)
    (english / "header_first_l_english.yml").write_bytes(
        b'l_english:\n first:0 "Header first"\n'
    )
    (english / "leading_prefix_l_english.yml").write_bytes(
        b'# leading comment\n\nl_english:\n second:0 "Prefixed"\n'
    )
    (english / "unsafe_prefix_l_english.yml").write_bytes(
        b' visible content\nl_english:\n third:0 "Unsafe prefix"\n'
    )
    candidate = tmp_path / "candidate"
    with pytest.MonkeyPatch.context() as generation:
        generation.setattr(
            engine, "PARSER_ORDER_VERSION", parser_order_version
        )
        translate_mod(
            source,
            candidate,
            "synthetic-review:1",
            workspace=tmp_path / "translation.smt-workspace.sqlite3",
            client_factory=FullReviewClient,
        )
    report_path = candidate / "translation-report.json"
    pin = hashlib.sha256(report_path.read_bytes()).hexdigest()

    result = build_review_pack(
        source,
        candidate,
        tmp_path / "review",
        candidate_report_sha256=pin,
    )

    assert result["status"] == "review_pack_created"
    assert result["counts"]["total"] == expected_entries
    assert len(list(candidate.rglob("*.yml"))) == expected_entries


def test_schema_v2_rejects_full_candidate_pin(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source_file = source / "localisation/english/pilot_l_english.yml"
    source_file.parent.mkdir(parents=True)
    source_file.write_text('l_english:\n pilot:0 "Pilot"\n')
    candidate = tmp_path / "candidate"
    translate_mod(
        source,
        candidate,
        "synthetic-review:1",
        max_occurrences_per_file=1,
        client_factory=FullReviewClient,
    )
    pin = hashlib.sha256(
        (candidate / "translation-report.json").read_bytes()
    ).hexdigest()
    with pytest.raises(
        SafetyError,
        match="candidate_report_pin_requires_schema_v3",
    ):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            candidate_report_sha256=pin,
        )


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        (lambda report: report.__setitem__("extra", True), "schema"),
        (lambda report: report.pop("resumability"), "resumability"),
        (
            lambda report: report["counts"].__setitem__(
                "accepted_unchanged",
                report["counts"]["accepted_unchanged"] + 1,
            ),
            "alias",
        ),
        (
            lambda report: report["counts"].__setitem__(
                "deferred_occurrences",
                1,
            ),
            "deferred",
        ),
        (
            lambda report: report["counts"].update(
                {
                    "pending_occurrences": 1,
                    "pending": 1,
                    "completed_occurrences": (
                        report["counts"]["completed_occurrences"] - 1
                    ),
                    "completed": report["counts"]["completed"] - 1,
                }
            ),
            "pending",
        ),
        (
            lambda report: report["resumability"].__setitem__(
                "mode",
                "unknown",
            ),
            "resumability",
        ),
        (
            lambda report: report["resumability"].__setitem__(
                "prompt_profile_hash",
                "not-a-hash",
            ),
            "resumability",
        ),
        (
            lambda report: report["resumability"].__setitem__(
                "parser_order_version",
                "unknown-parser-order-v999",
            ),
            "resumability",
        ),
        (
            lambda report: report["resumability"].__setitem__(
                "parser_order_version",
                ["mvp7a-leading-header-parser-order-v2"],
            ),
            "resumability",
        ),
        (
            lambda report: report["resumability"].__setitem__(
                "run_count",
                True,
            ),
            "resumability",
        ),
        (
            lambda report: report["model"].__setitem__(
                "digest",
                "sha256:synthetic",
            ),
            "model",
        ),
        (
            lambda report: report["model"].__setitem__(
                "digest",
                "A" * 64,
            ),
            "model",
        ),
        (
            lambda report: report["model"].__setitem__(
                "tag",
                "synthetic-review",
            ),
            "model",
        ),
        (
            lambda report: report["model"].__setitem__(
                "tag",
                "synthetic-review:latest-cloud",
            ),
            "model",
        ),
        (
            lambda report: report["model"].__setitem__(
                "extra",
                "not allowed",
            ),
            "model",
        ),
        (
            lambda report: report["counts"].__setitem__(
                "extra",
                0,
            ),
            "count_schema",
        ),
        (
            lambda report: report["resumability"].__setitem__(
                "extra",
                0,
            ),
            "resumability",
        ),
    ],
)
def test_schema_v3_rejects_fields_alias_pending_deferred_and_resumability_drift(
    tmp_path: Path,
    mutation: object,
    error: str,
) -> None:
    source, candidate, _ = make_full_review_inputs(tmp_path)
    pin = rewrite_report(candidate, mutation)
    with pytest.raises(SafetyError, match=error):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            candidate_report_sha256=pin,
        )


@pytest.mark.parametrize("schema_version", [3.0, True, "3"])
def test_schema_v3_requires_exact_integer_schema_version(
    tmp_path: Path,
    schema_version: object,
) -> None:
    source, candidate, _ = make_full_review_inputs(tmp_path)
    pin = rewrite_report(
        candidate,
        lambda report: report.__setitem__("schema_version", schema_version),
    )
    with pytest.raises(
        SafetyError,
        match="candidate_report_pin_requires_schema_v3",
    ):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            candidate_report_sha256=pin,
        )


@pytest.mark.parametrize("workspace_schema_version", [2.0, True, "2"])
def test_schema_v3_requires_exact_integer_workspace_schema_version(
    tmp_path: Path,
    workspace_schema_version: object,
) -> None:
    source, candidate, _ = make_full_review_inputs(tmp_path)
    pin = rewrite_report(
        candidate,
        lambda report: report["resumability"].__setitem__(
            "workspace_schema_version",
            workspace_schema_version,
        ),
    )
    with pytest.raises(SafetyError, match="resumability"):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            candidate_report_sha256=pin,
        )


def test_schema_v3_rejects_rehashed_untrusted_total_count(
    tmp_path: Path,
) -> None:
    source, candidate, _ = make_full_review_inputs(tmp_path)
    pin = rewrite_report(
        candidate,
        lambda report: report["counts"].__setitem__(
            "total",
            report["counts"]["total"] + 1,
        ),
    )
    with pytest.raises(
        SafetyError,
        match="candidate_report_count_alias_mismatch_total",
    ):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            candidate_report_sha256=pin,
        )


@pytest.mark.parametrize(
    "tag",
    [
        "synthetic-review:1",
        "registry.example/team/model:latest",
        "synthetic-review-cloud:latest",
    ],
)
def test_schema_v3_accepts_runtime_compatible_model_tag_forms(
    tmp_path: Path,
    tag: str,
) -> None:
    source, candidate, _ = make_full_review_inputs(tmp_path)
    pin = rewrite_report(
        candidate,
        lambda report: report["model"].__setitem__("tag", tag),
    )
    result = build_review_pack(
        source,
        candidate,
        tmp_path / "review",
        candidate_report_sha256=pin,
    )
    assert result["counts"]["review_entries"] == 6


@pytest.mark.parametrize(
    "tag",
    [
        "synthetic-review:latest-cloud",
        "synthetic-review",
        "synthetic-review:",
        ":latest",
    ],
)
def test_schema_v3_rejects_cloud_suffix_and_malformed_model_tag_forms(
    tmp_path: Path,
    tag: str,
) -> None:
    source, candidate, _ = make_full_review_inputs(tmp_path)
    pin = rewrite_report(
        candidate,
        lambda report: report["model"].__setitem__("tag", tag),
    )
    with pytest.raises(SafetyError, match="model"):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            candidate_report_sha256=pin,
        )


def test_schema_v3_rechecks_protected_atoms_and_candidate_hash(
    tmp_path: Path,
) -> None:
    source, candidate, _ = make_full_review_inputs(tmp_path)
    candidate_file = (
        candidate / "localisation/russian/full_l_russian.yml"
    )
    candidate_file.write_bytes(
        candidate_file.read_bytes().replace(b"$NAME$", b"$OTHER$", 1)
    )
    pin = rebind_candidate_hash(candidate)
    with pytest.raises(
        SafetyError,
        match="protected_atom_or_escape_mismatch",
    ):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            candidate_report_sha256=pin,
        )


@pytest.mark.parametrize("drift_target", ["source", "candidate", "report"])
def test_schema_v3_generation_drift_prevents_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift_target: str,
) -> None:
    source, candidate, pin = make_full_review_inputs(tmp_path)
    output = tmp_path / "review"
    real_render = review._render_review_html

    def drift(pack_data: dict[str, object]) -> bytes:
        rendered = real_render(pack_data)
        if drift_target == "source":
            path = source / "localisation/english/full_l_english.yml"
        elif drift_target == "candidate":
            path = (
                candidate / "localisation/russian/full_l_russian.yml"
            )
        else:
            path = candidate / "translation-report.json"
        path.write_bytes(path.read_bytes() + b" ")
        return rendered

    monkeypatch.setattr(review, "_render_review_html", drift)
    with pytest.raises(SafetyError, match="generation_changed"):
        build_review_pack(
            source,
            candidate,
            output,
            candidate_report_sha256=pin,
        )
    assert not output.exists()
    assert list(tmp_path.glob(".review.tmp-*")) == []


def test_schema_v3_html_is_csp_safe_base64_and_offline(
    tmp_path: Path,
) -> None:
    source, candidate, pin = make_full_review_inputs(
        tmp_path,
        hostile_text=True,
    )
    output = tmp_path / "review"
    build_review_pack(
        source,
        candidate,
        output,
        candidate_report_sha256=pin,
    )
    html = (output / "index.html").read_text()
    decoded = json.dumps(extract_pack(output), ensure_ascii=False)
    hostile = "</script><script>synthetic_unicode_Ж"
    assert hostile not in html
    assert hostile in decoded
    assert "connect-src 'none'" in html
    assert "frame-src 'none'" in html
    assert "form-action 'none'" in html
    assert "innerHTML" not in html
    assert "https://" not in html
    assert "http://" not in html
    for network_api in (
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "EventSource",
        "sendBeacon",
    ):
        assert network_api not in html


def test_schema_v3_full_pack_scales_to_12871_entries(
    tmp_path: Path,
) -> None:
    source, candidate, pin = make_full_review_inputs(
        tmp_path,
        entry_count=12871,
    )
    output = tmp_path / "review"
    result = build_review_pack(
        source,
        candidate,
        output,
        candidate_report_sha256=pin,
    )
    pack = extract_pack(output)
    assert result["counts"]["review_entries"] == 12871
    assert result["counts"]["accepted_changed"] == 12871
    assert len(pack["entries"]) == 12871
    assert len(review._canonical_json(pack).encode()) <= (
        review.MAX_REVIEW_PACK_JSON_BYTES
    )


def test_full_ui_sparse_storage_exports_imports_keyboard_and_dom_window(
    tmp_path: Path,
) -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for JavaScript regression"
    source, candidate, pin = make_full_review_inputs(
        tmp_path,
        entry_count=12871,
    )
    output = tmp_path / "review"
    build_review_pack(
        source,
        candidate,
        output,
        candidate_report_sha256=pin,
    )
    runtime = tmp_path / "full-review-runtime.js"
    runtime.write_text(extract_runtime(output))
    runtime_pack = extract_pack(output)
    repeat_indexes = [1000, 1001, 1002]
    for index in repeat_indexes:
        runtime_pack["entries"][index]["source_segments"] = [
            "Exact repeat ",
            " tail",
        ]
        runtime_pack["entries"][index]["protected_atoms"] = ["$NAME$"]
    runtime_pack["entries"][1000]["candidate_segments"] = [
        "Точный повтор ",
        " хвост",
    ]
    runtime_pack["entries"][1001]["candidate_segments"] = [
        "Точный повтор ",
        " хвост",
    ]
    runtime_pack["entries"][1002]["candidate_segments"] = [
        "Другой вариант ",
        " хвост",
    ]
    runtime_pack["entries"][1003]["source_segments"] = [
        "Exact repeat  ",
        " tail",
    ]
    runtime_pack["entries"][1003]["candidate_segments"] = [
        "Почти повтор ",
        " хвост",
    ]
    runtime_pack["entries"][1003]["protected_atoms"] = ["$NAME$"]
    runtime_pack["entries"][4]["status"] = "model_fallback"
    runtime_pack["entries"][4]["warnings"] = ["model_fallback"]
    runtime_pack["entries"][5]["status"] = "accepted_unchanged"
    runtime_pack["entries"][5]["warnings"] = ["accepted_unchanged"]
    runtime_pack["entries"][6]["warnings"] = [
        "leading_boundary_whitespace_changed"
    ]
    runtime_pack["entries"][1200]["key"] = "unique_search_key_sentinel"
    encoded_pack = base64.b64encode(
        json.dumps(
            runtime_pack,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).decode()
    (tmp_path / "full-review-runtime.js.pack-data").write_text(encoded_pack)
    harness = tmp_path / "full-review-harness.cjs"
    harness.write_text(
        r"""
const fs = require("fs");
const vm = require("vm");
if (typeof Blob === "undefined") globalThis.Blob = require("buffer").Blob;
if (typeof atob === "undefined") {
  globalThis.atob = value => Buffer.from(value, "base64").toString("binary");
}
if (typeof TextDecoder === "undefined") {
  globalThis.TextDecoder = require("util").TextDecoder;
}
if (typeof TextEncoder === "undefined") {
  globalThis.TextEncoder = require("util").TextEncoder;
}
class StubClassList {
  constructor() { this.values = new Set(); }
  toggle(name, force) {
    const enabled = force === undefined ? !this.values.has(name) : force;
    if (enabled) this.values.add(name); else this.values.delete(name);
    return enabled;
  }
  contains(name) { return this.values.has(name); }
}
class StubElement {
  constructor(tagName = "div", id = "") {
    this.tagName = tagName.toUpperCase();
    this.id = id;
    this.children = [];
    this.listeners = new Map();
    this.className = "";
    this.classList = new StubClassList();
    this.textContent = "";
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.files = [];
    this.style = {};
    this.isContentEditable = false;
  }
  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute() {}
  focus() { globalThis.focusedElement = this; }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
  querySelectorAll(selector) {
    const matches = [];
    const visit = node => {
      if (!(node instanceof StubElement)) return;
      if (selector === "input" && node.tagName === "INPUT") matches.push(node);
      if (selector === "textarea" && node.tagName === "TEXTAREA") {
        matches.push(node);
      }
      if (
        selector === "input:checked"
        && node.tagName === "INPUT"
        && node.checked
      ) matches.push(node);
      node.children.forEach(visit);
    };
    this.children.forEach(visit);
    return matches;
  }
  async fire(type, event = {}) {
    if (!event.target) event.target = this;
    if (!event.preventDefault) event.preventDefault = () => {};
    for (const listener of this.listeners.get(type) || []) {
      await listener(event);
    }
  }
  click() {
    if (this.tagName === "A") {
      globalThis.downloadCount = (globalThis.downloadCount || 0) + 1;
      return;
    }
    return this.fire("click", {target: this, preventDefault() {}});
  }
}
const ids = [
  "review-data", "fingerprint", "scopeSummary", "progressText",
  "progressBar", "progressDetails", "storageWarning", "helpPanel", "closeHelp",
  "search",
  "attentionFilter", "fileFilter", "statusFilter", "decisionFilter",
  "warningFilter", "repeatFilter", "resultCount", "pagePrevious", "pageInfo",
  "pageNext", "selectedCount", "selectUnreviewedPage", "clearSelection",
  "batchAccept", "batchReject", "undoBatch",
  "entryList", "empty", "review", "path", "line", "status", "warnings",
  "key", "ordinal", "previousContext", "nextContext", "repeatInfo",
  "repeatPrevious", "repeatNext", "repeatWarning", "acceptWarning",
  "sourceText", "candidateText", "atoms", "decision",
  "editorField", "editor", "note", "tags", "glossary", "previous", "next",
  "draftExport", "finalExport", "importButton", "helpButton", "clear",
  "importFile", "error"
];
const elements = new Map(ids.map(id => [id, new StubElement("div", id)]));
for (const id of [
  "search", "attentionFilter", "fileFilter", "statusFilter",
  "decisionFilter", "warningFilter", "repeatFilter", "decision", "note",
  "glossary", "importFile"
]) {
  elements.get(id).tagName = id === "note" ? "TEXTAREA" : "INPUT";
}
elements.get("review-data").textContent = fs.readFileSync(
  process.argv[2] + ".pack-data", "utf8"
);
const documentListeners = new Map();
globalThis.document = {
  getElementById(id) { return elements.get(id); },
  createElement(tagName) { return new StubElement(tagName); },
  createTextNode(text) { return {textContent: text}; },
  addEventListener(type, listener) {
    const listeners = documentListeners.get(type) || [];
    listeners.push(listener);
    documentListeners.set(type, listeners);
  }
};
globalThis.window = {addEventListener() {}};
globalThis.localStorage = {
  values: new Map(),
  setCounts: new Map(),
  fail: false,
  getItem(key) {
    if (this.fail) throw new Error("synthetic quota");
    return this.values.has(key) ? this.values.get(key) : null;
  },
  setItem(key, value) {
    if (this.fail) throw new Error("synthetic quota");
    this.setCounts.set(key, (this.setCounts.get(key) || 0) + 1);
    this.values.set(key, value);
  },
  removeItem(key) {
    if (this.fail) throw new Error("synthetic quota");
    this.values.delete(key);
  }
};
globalThis.confirmResult = true;
globalThis.lastConfirmMessage = "";
globalThis.confirm = message => {
  globalThis.lastConfirmMessage = String(message);
  return globalThis.confirmResult;
};
globalThis.URL = {
  createObjectURL(blob) {
    globalThis.capturedBlob = blob;
    return "blob:synthetic";
  },
  revokeObjectURL() {}
};
vm.runInThisContext(fs.readFileSync(process.argv[2], "utf8"));
async function fireDocument(type, event) {
  for (const listener of documentListeners.get(type) || []) {
    await listener(event);
  }
}
(async () => {
  const initialRows = elements.get("entryList").children.length;
  await elements.get("pageNext").fire("click");
  const secondPageRows = elements.get("entryList").children.length;
  vm.runInThisContext(`
    state=new Map();drafts.clear();selected.clear();undoState=null;
    resetFilters();currentId=pack.entries[0].id;pageIndex=0;applyFilters()
  `);
  const keyAndOrdinalRendered = vm.runInThisContext(
    `el("key").textContent==="key: "+pack.entries[0].key`
    + `&&el("ordinal").textContent==="occurrence ordinal: "+pack.entries[0].occurrence_ordinal`
    + `&&searchable(pack.entries[0]).includes(pack.entries[0].key)`
  );
  await elements.get("nextContext").fire("click");
  const nextContextNavigated = vm.runInThisContext(
    "currentId===pack.entries[1].id"
  );
  await elements.get("previousContext").fire("click");
  const previousContextNavigated = vm.runInThisContext(
    "currentId===pack.entries[0].id"
  );
  elements.get("search").value = vm.runInThisContext("pack.entries[1200].key");
  await elements.get("search").fire("input");
  const keySearchExact = vm.runInThisContext(
    "visible.length===1&&visible[0].id===pack.entries[1200].id"
    + "&&currentId===pack.entries[1200].id"
    + '&&el("key").textContent==="key: "+pack.entries[1200].key'
  );
  vm.runInThisContext(
    "resetFilters();currentId=pack.entries[1000].id;pageIndex=0;applyFilters()"
  );
  const exactRepeatGrouping = vm.runInThisContext(
    "repeatGroupById.get(currentId).records.length===3"
    + "&&repeatGroupById.get(currentId).inconsistent===true"
    + '&&el("repeatInfo").textContent.includes("Точных повторов: 3")'
    + '&&!el("repeatWarning").classList.contains("hidden")'
  );
  await elements.get("repeatNext").fire("click");
  const repeatNextNavigated = vm.runInThisContext(
    "currentId===pack.entries[1001].id"
  );
  await elements.get("repeatPrevious").fire("click");
  const repeatPreviousNavigated = vm.runInThisContext(
    "currentId===pack.entries[1000].id"
  );
  elements.get("repeatFilter").value = "inconsistent";
  await elements.get("repeatFilter").fire("change");
  const inconsistentRepeatFilterExact = vm.runInThisContext(
    "visible.length===3"
    + "&&visible.every(record=>[1000,1001,1002]"
    + ".map(index=>pack.entries[index].id).includes(record.id))"
    + "&&!visible.some(record=>record.id===pack.entries[1003].id)"
  );
  elements.get("repeatFilter").value = "exact_repeat";
  await elements.get("repeatFilter").fire("change");
  const noFuzzyGrouping = vm.runInThisContext(
    "visible.length===3"
    + "&&!visible.some(record=>record.id===pack.entries[1003].id)"
  );
  vm.runInThisContext(
    "resetFilters();currentId=pack.entries[0].id;pageIndex=0;applyFilters()"
  );
  await elements.get("selectUnreviewedPage").fire("click");
  const pageLocalSelectionCount = vm.runInThisContext(
    "selected.size===100"
    + '&&el("selectedCount").textContent==="Выбрано на странице: 100"'
  );
  await elements.get("pageNext").fire("click");
  const pageChangeClearsSelection = vm.runInThisContext("selected.size===0");
  await elements.get("pagePrevious").fire("click");
  await elements.get("selectUnreviewedPage").fire("click");
  elements.get("search").value = "scale.5";
  await elements.get("search").fire("input");
  const searchChangeClearsSelection = vm.runInThisContext("selected.size===0");
  vm.runInThisContext(
    "resetFilters();currentId=pack.entries[0].id;pageIndex=0;applyFilters()"
  );
  await elements.get("selectUnreviewedPage").fire("click");
  elements.get("statusFilter").value = "accepted_changed";
  await elements.get("statusFilter").fire("change");
  const filterChangeClearsSelection = vm.runInThisContext("selected.size===0");
  vm.runInThisContext(`
    state=new Map();drafts.clear();selected.clear();undoState=null;
    resetFilters();currentId=pack.entries[0].id;pageIndex=0;
    {
      const record=pack.entries[0];
      const item=defaults(record);
      item.note="batch metadata";
      item.tags=["terminology"];
      item.glossary_candidate=true;
      state.set(record.id,item)
    }
    applyFilters()
  `);
  await elements.get("selectUnreviewedPage").fire("click");
  const beforeCancelledBatch = vm.runInThisContext(
    "JSON.stringify(sparseDocument())"
  );
  globalThis.confirmResult = false;
  await elements.get("batchAccept").fire("click");
  const confirmationCancelAtomic = vm.runInThisContext(
    "JSON.stringify(sparseDocument())"
    + "===" + JSON.stringify(beforeCancelledBatch)
    + "&&selected.size===100&&undoState===null"
  );
  globalThis.confirmResult = true;
  vm.runInThisContext("selected.clear();render()");
  const beforeZeroBatch = vm.runInThisContext(
    "JSON.stringify(sparseDocument())"
  );
  await elements.get("batchReject").fire("click");
  const zeroSelectionRejected = vm.runInThisContext(
    "JSON.stringify(sparseDocument())"
    + "===" + JSON.stringify(beforeZeroBatch)
    + '&&el("error").textContent.includes("не выбрано")'
  );
  vm.runInThisContext(
    "selected=new Set([pack.entries[0].id,pack.entries[100].id]);updateProgress()"
  );
  const beforeHiddenBatch = vm.runInThisContext(
    "JSON.stringify(sparseDocument())"
  );
  await elements.get("batchAccept").fire("click");
  const hiddenSelectionRejectedAtomically = vm.runInThisContext(
    "JSON.stringify(sparseDocument())"
    + "===" + JSON.stringify(beforeHiddenBatch)
    + "&&undoState===null"
  );
  vm.runInThisContext(`
    {
      const record=pack.entries[1];
      const item=defaults(record);item.decision="accept";
      state.set(record.id,item);selected=new Set([record.id])
    }
  `);
  const beforeReviewedBatch = vm.runInThisContext(
    "JSON.stringify(sparseDocument())"
  );
  await elements.get("batchReject").fire("click");
  const reviewedNotOverwritten = vm.runInThisContext(
    "JSON.stringify(sparseDocument())"
    + "===" + JSON.stringify(beforeReviewedBatch)
    + "&&currentState(pack.entries[1]).decision==='accept'"
  );
  vm.runInThisContext(`
    state=new Map();drafts.clear();selected.clear();undoState=null;
    resetFilters();currentId=pack.entries[0].id;pageIndex=0;
    {
      const record=pack.entries[0];
      const item=defaults(record);
      item.note="batch metadata";
      item.tags=["terminology"];
      item.glossary_candidate=true;
      state.set(record.id,item)
    }
    applyFilters();
    localStorage.setCounts.set(storageKey,0)
  `);
  await elements.get("selectUnreviewedPage").fire("click");
  await elements.get("batchAccept").fire("click");
  const batchAcceptAtomic = vm.runInThisContext(
    "pack.entries.slice(0,100).every("
    + "record=>currentState(record).decision==='accept')"
    + "&&pack.entries.slice(100).every("
    + "record=>currentState(record).decision==='unreviewed')"
  );
  const batchPreservesMetadata = vm.runInThisContext(
    "currentState(pack.entries[0]).note==='batch metadata'"
    + "&&currentState(pack.entries[0]).tags.length===1"
    + "&&currentState(pack.entries[0]).tags[0]==='terminology'"
    + "&&currentState(pack.entries[0]).glossary_candidate===true"
  );
  const batchSingleSparseSave = vm.runInThisContext(
    "localStorage.setCounts.get(storageKey)===1"
  );
  const confirmationIsExplicit = (
    globalThis.lastConfirmMessage.includes("100")
    && globalThis.lastConfirmMessage.includes("Status:")
    && globalThis.lastConfirmMessage.includes("Требуют внимания: 3")
    && globalThis.lastConfirmMessage.includes(
      "отдельное редакторское решение для каждой выбранной строки"
    )
  );
  const progressCountersImmediate = vm.runInThisContext(
    'el("progressText").textContent==="100 / 12871 проверено"'
    + '&&el("progressDetails").textContent.includes('
    + '"Непроверенные: 12771")'
    + '&&el("progressDetails").textContent.includes('
    + '"невалидные edits: 0")'
    + '&&el("progressDetails").textContent.includes('
    + '"несогласованных групп повторов: 1")'
    + '&&el("selectedCount").textContent==="Выбрано на странице: 0"'
  );
  const undoStoredForExactPack = vm.runInThisContext(
    "(()=>{const saved=JSON.parse(localStorage.getItem(storageKey));"
    + "return saved.storage_schema_version===3"
    + "&&saved.pack_fingerprint===pack.pack_fingerprint"
    + "&&saved.entry_order_sha256===pack.entry_order_sha256"
    + "&&saved.last_batch_undo.records.length===100})()"
  );
  const validUndoDocument = vm.runInThisContext(
    "JSON.stringify(undoDocument())"
  );
  const beforeInvalidUndo = vm.runInThisContext(
    "JSON.stringify(sparseDocument())"
  );
  vm.runInThisContext(`
    undoState={
      decision:"accept",
      entries:[{
        occurrence_id:"0".repeat(64),
        before:defaults(pack.entries[0]),
        after:defaults(pack.entries[0])
      }]
    };
    undoLastBatch()
  `);
  const undoValidationFailureAtomic = vm.runInThisContext(
    "JSON.stringify(sparseDocument())"
    + "===" + JSON.stringify(beforeInvalidUndo)
    + '&&el("error").textContent.startsWith("Отмена отклонена:")'
  );
  vm.runInThisContext(
    "undoState=validateUndoDocument(JSON.parse("
    + JSON.stringify(validUndoDocument)
    + "))"
  );
  vm.runInThisContext(
    "navigateToRecord(pack.entries[1500].id);setDecision('accept',false)"
  );
  vm.runInThisContext("undoLastBatch()");
  const undoRestoresExactPriorState = vm.runInThisContext(
    "pack.entries.slice(0,100).every("
    + "record=>currentState(record).decision==='unreviewed')"
    + "&&currentState(pack.entries[0]).note==='batch metadata'"
    + "&&currentState(pack.entries[0]).tags[0]==='terminology'"
    + "&&currentState(pack.entries[0]).glossary_candidate===true"
  );
  const undoPreservesUnrelatedIndividualChange = vm.runInThisContext(
    "currentState(pack.entries[1500]).decision==='accept'"
  );
  const undoConsumed = vm.runInThisContext(
    "undoState===null"
    + "&&JSON.parse(localStorage.getItem(storageKey)).last_batch_undo===null"
  );
  vm.runInThisContext(`
    state=new Map();drafts.clear();selected.clear();undoState=null;
    resetFilters();currentId=pack.entries[0].id;pageIndex=0;applyFilters()
  `);
  let firstCheckbox = elements.get("entryList").children[0].children[0];
  firstCheckbox.checked = true;
  await firstCheckbox.fire("change");
  await elements.get("batchReject").fire("click");
  const batchRejectExact = vm.runInThisContext(
    "currentState(pack.entries[0]).decision==='reject'"
    + "&&pack.entries.slice(1).every("
    + "record=>currentState(record).decision==='unreviewed')"
  );
  const reviewedCheckboxDisabled = (
    elements.get("entryList").children[0].children[0].disabled === true
  );
  await elements.get("clear").fire("click");
  const clearResetsUndo = vm.runInThisContext(
    "state.size===0&&undoState===null&&selected.size===0"
    + "&&localStorage.getItem(storageKey)===null"
  );
  vm.runInThisContext(`
    state=new Map();drafts.clear();selected.clear();undoState=null;
    resetFilters();currentId=pack.entries[0].id;pageIndex=0;
    {
      const record=pack.entries[0];
      const item=defaults(record);
      item.note="multi-tag metadata";
      item.tags=["terminology","lore"];
      item.glossary_candidate=true;
      setStateMemory(record,item)
    }
    applyFilters()
  `);
  firstCheckbox = elements.get("entryList").children[0].children[0];
  firstCheckbox.checked = true;
  await firstCheckbox.fire("change");
  await elements.get("batchAccept").fire("click");
  const multiTagCanonicalization = vm.runInThisContext(
    "JSON.stringify(currentState(pack.entries[0]).tags)"
    + '===JSON.stringify(["lore","terminology"])'
  );
  const batchReloadUndo = vm.runInThisContext(
    "(()=>{const restored=validateStorageDocument(JSON.parse("
    + "localStorage.getItem(storageKey)));"
    + "return restored.state.get(pack.entries[0].id).decision==='accept'"
    + "&&restored.undo!==null&&restored.undoDiscarded===false"
    + "&&JSON.stringify(restored.state.get(pack.entries[0].id).tags)"
    + '===JSON.stringify(["lore","terminology"])})()'
  );
  const legacyV2UnsortedUndoCompatible = vm.runInThisContext(`
    (()=>{
      const legacy={
        storage_schema_version:2,
        pack_fingerprint:pack.pack_fingerprint,
        changes:sparseDocument().changes,
        last_batch_undo:undoDocument()
      };
      const entry=legacy.last_batch_undo.entries.find(
        item=>item.occurrence_id===pack.entries[0].id
      );
      entry.before.tags=["terminology","lore"];
      entry.after.tags=["terminology","lore"];
      const restored=validateStorageDocument(
        JSON.parse(JSON.stringify(legacy))
      );
      return restored.undo!==null&&restored.undoDiscarded===false
        &&restored.migrated===true
        &&JSON.stringify(restored.state.get(pack.entries[0].id).tags)
          ===JSON.stringify(["lore","terminology"])
    })()
  `);
  const legacyV2ReverseUndoMigratesCanonically = vm.runInThisContext(`
    (()=>{
      const records=pack.entries.slice(0,2);
      const before=records.map(record=>defaults(record));
      const after=before.map((item,index)=>{
        const result=cloneItem(item);result.decision="accept";
        result.edited_segments=records[index].candidate_segments.slice();
        return result
      });
      const legacy={
        storage_schema_version:2,
        pack_fingerprint:pack.pack_fingerprint,
        changes:records.map((record,index)=>decisionRecord(record,after[index])),
        last_batch_undo:{
          undo_schema_version:1,
          pack_fingerprint:pack.pack_fingerprint,
          decision:"accept",
          entries:[1,0].map(index=>({
            occurrence_id:records[index].id,
            before:cloneItem(before[index]),
            after:cloneItem(after[index])
          }))
        }
      };
      const restored=validateStorageDocument(legacy);
      const compact=storageDocument(restored.state,restored.undo);
      const reloaded=validateStorageDocument(
        JSON.parse(JSON.stringify(compact))
      );
      return restored.migrated===true&&restored.undoDiscarded===false
        &&compact.last_batch_undo.records[0][0]===0
        &&compact.last_batch_undo.records[1][0]===1
        &&reloaded.undo!==null&&reloaded.undo.entries.length===2
    })()
  `);
  const corruptLegacyUndoSalvagesDecisions = vm.runInThisContext(`
    (()=>{
      const records=pack.entries.slice(0,2);
      const after=records.map(record=>{
        const item=defaults(record);item.decision="accept";return item
      });
      const legacy={
        storage_schema_version:2,
        pack_fingerprint:pack.pack_fingerprint,
        changes:records.map((record,index)=>decisionRecord(record,after[index])),
        last_batch_undo:{
          undo_schema_version:1,
          pack_fingerprint:pack.pack_fingerprint,
          decision:"accept",
          entries:[{
            occurrence_id:"0".repeat(64),
            before:cloneItem(defaults(records[0])),
            after:cloneItem(after[0])
          }]
        }
      };
      const restored=validateStorageDocument(legacy);
      const migrated=storageDocument(restored.state,restored.undo);
      const reloaded=validateStorageDocument(
        JSON.parse(JSON.stringify(migrated))
      );
      return restored.migrated===true&&restored.undo===null
        &&restored.undoDiscarded===true&&restored.state.size===2
        &&migrated.storage_schema_version===3
        &&migrated.last_batch_undo===null
        &&reloaded.state.size===2&&reloaded.undo===null
        &&records.every(record=>reloaded.state.get(record.id).decision==="accept")
    })()
  `);
  const repeatedSaveReloadUndo = vm.runInThisContext(`
    (()=>{
      for(let index=0;index<2;index++){
        const restored=validateStorageDocument(JSON.parse(
          localStorage.getItem(storageKey)
        ));
        if(restored.undo===null||restored.undoDiscarded)return false;
        state=restored.state;undoState=restored.undo;persistSparse()
      }
      const restored=validateStorageDocument(JSON.parse(
        localStorage.getItem(storageKey)
      ));
      state=restored.state;undoState=restored.undo;
      return restored.undo!==null&&restored.undoDiscarded===false
    })()
  `);
  vm.runInThisContext("undoLastBatch()");
  const exactMultiTagMetadataRestoration = vm.runInThisContext(
    "currentState(pack.entries[0]).decision==='unreviewed'"
    + "&&currentState(pack.entries[0]).note==='multi-tag metadata'"
    + "&&JSON.stringify(currentState(pack.entries[0]).tags)"
    + '===JSON.stringify(["lore","terminology"])'
    + "&&currentState(pack.entries[0]).glossary_candidate===true"
    + "&&undoState===null"
  );
  vm.runInThisContext(`
    state=new Map();drafts.clear();selected.clear();undoState=null;
    resetFilters();currentId=pack.entries[0].id;pageIndex=0;
    {
      const record=pack.entries[0];
      const item=defaults(record);
      item.tags=["terminology","lore"];
      setStateMemory(record,item)
    }
    applyFilters()
  `);
  firstCheckbox = elements.get("entryList").children[0].children[0];
  firstCheckbox.checked = true;
  await firstCheckbox.fire("change");
  await elements.get("batchAccept").fire("click");
  vm.runInThisContext(
    "updateDraftAwareField(pack.entries[0],'tags',['lore'],true)"
  );
  const affectedTagMutationClearsUndo = vm.runInThisContext(
    "currentState(pack.entries[0]).decision==='accept'"
    + "&&JSON.stringify(currentState(pack.entries[0]).tags)"
    + '===JSON.stringify(["lore"])&&undoState===null'
    + "&&validateStorageDocument(JSON.parse(localStorage.getItem(storageKey)))"
    + ".undo===null"
  );
  vm.runInThisContext(`
    state=new Map();drafts.clear();selected.clear();undoState=null;
    resetFilters();currentId=pack.entries[0].id;pageIndex=0;
    applyFilters();persistSparse()
  `);
  const legacySparseV1Compatible = vm.runInThisContext(
    "validateStorageDocument(sparseDocument()).state.size===0"
    + "&&validateStorageDocument(sparseDocument()).undo===null"
  );
  const legacyStorageV1UnsortedTags = vm.runInThisContext(`
    (()=>{
      const record=pack.entries[0];
      const item=decisionRecord(record,defaults(record));
      item.note="legacy storage metadata";
      item.tags=["terminology","lore"];
      const restored=validateStorageDocument({
        storage_schema_version:1,
        pack_fingerprint:pack.pack_fingerprint,
        changes:[item]
      });
      const migrated=storageDocument(restored.state,restored.undo);
      return restored.undo===null&&restored.undoDiscarded===false
        &&restored.migrated===true
        &&validateStorageDocument(migrated).migrated===false
        &&JSON.stringify(restored.state.get(record.id).tags)
          ===JSON.stringify(["lore","terminology"])
    })()
  `);
  const legacyDraftV1UnsortedTags = vm.runInThisContext(`
    (()=>{
      const draft=exportDocument(new Map(),false,false);
      draft.decisions[0].note="legacy draft metadata";
      draft.decisions[0].tags=["terminology","lore"];
      const restored=validateDocument(draft);
      return JSON.stringify(restored.get(pack.entries[0].id).tags)
        ===JSON.stringify(["lore","terminology"])
    })()
  `);
  const duplicateTagRejected = vm.runInThisContext(`
    (()=>{
      const draft=exportDocument(new Map(),false,false);
      draft.decisions[0].tags=["lore","lore"];
      try{validateDocument(draft);return false}catch(error){return true}
    })()
  `);
  const unknownTagRejected = vm.runInThisContext(`
    (()=>{
      const draft=exportDocument(new Map(),false,false);
      draft.decisions[0].tags=["unknown"];
      try{validateDocument(draft);return false}catch(error){return true}
    })()
  `);
  const storageV3Validation = vm.runInThisContext(`
    (()=>{
      const value=new Map();
      const edit=defaults(pack.entries[0]);
      edit.decision="edit";edit.edited_segments=["Юникод 😀"];
      value.set(pack.entries[0].id,edit);
      const noted=defaults(pack.entries[1]);
      noted.decision="accept";noted.note="compact note";
      value.set(pack.entries[1].id,noted);
      const tagged=defaults(pack.entries[2]);
      tagged.decision="reject";tagged.tags=["lore","terminology"];
      tagged.glossary_candidate=true;
      value.set(pack.entries[2].id,tagged);
      const envelope=storageDocument(value,null);
      const restored=validateStorageDocument(envelope);
      const beforeState=JSON.stringify(sparseDocument());
      const beforeStorage=localStorage.getItem(storageKey);
      const beforeUndo=JSON.stringify(undoDocument());
      const rejects=documentValue=>{
        try{validateStorageDocument(documentValue);return false}
        catch(error){return JSON.stringify(sparseDocument())===beforeState
          &&localStorage.getItem(storageKey)===beforeStorage
          &&JSON.stringify(undoDocument())===beforeUndo}
      };
      const mutate=callback=>{const clone=JSON.parse(JSON.stringify(envelope));callback(clone);return clone};
      const cases=[
        mutate(clone=>{clone.records.at(-1)[2].unknown=true}),
        mutate(clone=>{clone.records.splice(1,0,JSON.parse(JSON.stringify(clone.records[0])))}),
        mutate(clone=>{clone.records.at(-1)[1]="0".repeat(64)}),
        mutate(clone=>{clone.records=clone.records.filter(record=>record[0]!==0)}),
        mutate(clone=>{clone.records.reverse()}),
        mutate(clone=>{clone.pack_fingerprint="0".repeat(64)}),
        mutate(clone=>{clone.entry_order_sha256="0".repeat(64)}),
        mutate(clone=>{clone.decision_states=clone.decision_states.slice(1)}),
        mutate(clone=>{const left=clone.records[0][1];clone.records[0][1]=clone.records[1][1];clone.records[1][1]=left})
      ];
      return {
        roundTrip:restored.state.size===3
          &&restored.state.get(pack.entries[0].id).edited_segments[0]==="Юникод 😀"
          &&restored.state.get(pack.entries[1].id).note==="compact note"
          &&JSON.stringify(storageDocument(restored.state,restored.undo))===JSON.stringify(envelope),
        compact:envelope.decision_states.length===pack.entries.length
          &&envelope.records.length===3
          &&envelope.records[0][2].edited_translation==="Юникод 😀"
          &&!Object.hasOwn(envelope.records[1][2],"edited_translation")
          &&envelope.records[1][2].note==="compact note",
        invalidAtomic:cases.every(rejects)
      }
    })()
  `);
  const persistedBeforeStorageFailure = localStorage.getItem(
    vm.runInThisContext("storageKey")
  );
  firstCheckbox = elements.get("entryList").children[0].children[0];
  firstCheckbox.checked = true;
  await firstCheckbox.fire("change");
  localStorage.fail = true;
  await elements.get("batchAccept").fire("click");
  globalThis.capturedBlob = undefined;
  vm.runInThisContext("downloadDocument(false)");
  const failedStorageDraftBytes = Buffer.from(
    await globalThis.capturedBlob.arrayBuffer()
  );
  const failedStorageDraft = JSON.parse(
    failedStorageDraftBytes.toString("utf8")
  );
  const storageFailureKeepsMemoryExport = (
    vm.runInThisContext(
      "currentState(pack.entries[0]).decision==='accept'&&undoState!==null"
    )
    && failedStorageDraft.decisions[0].decision === "accept"
  );
  localStorage.fail = false;
  const storageEnvelopeFailureCoherent = vm.runInThisContext(
    "(()=>{const restored=validateStorageDocument(JSON.parse("
    + JSON.stringify(persistedBeforeStorageFailure)
    + "));return restored.state.size===0&&restored.undo===null})()"
  );
  vm.runInThisContext(`
    {
      const restored=validateStorageDocument(JSON.parse(
        ${JSON.stringify(persistedBeforeStorageFailure)}
      ));
      state=restored.state;undoState=restored.undo;
    }
    drafts.clear();selected.clear();currentId=pack.entries[0].id;
    pageIndex=0;applyFilters()
  `);
  firstCheckbox = elements.get("entryList").children[0].children[0];
  firstCheckbox.checked = true;
  await firstCheckbox.fire("change");
  await elements.get("batchAccept").fire("click");
  let secondCheckbox = elements.get("entryList").children[1].children[0];
  secondCheckbox.checked = true;
  await secondCheckbox.fire("change");
  await elements.get("batchReject").fire("click");
  const newBatchReplacesUndo = vm.runInThisContext(
    "undoState.decision==='reject'&&undoState.entries.length===1"
    + "&&undoState.entries[0].occurrence_id===pack.entries[1].id"
  );
  vm.runInThisContext("undoLastBatch()");
  const latestBatchOnlyUndo = vm.runInThisContext(
    "currentState(pack.entries[0]).decision==='accept'"
    + "&&currentState(pack.entries[1]).decision==='unreviewed'"
    + "&&undoState===null"
  );
  vm.runInThisContext(`
    state=new Map();drafts.clear();selected.clear();undoState=null;
    resetFilters();currentId=pack.entries[0].id;pageIndex=0;applyFilters()
  `);
  firstCheckbox = elements.get("entryList").children[0].children[0];
  firstCheckbox.checked = true;
  await firstCheckbox.fire("change");
  await elements.get("batchAccept").fire("click");
  const coherentBatchEnvelope = JSON.parse(
    localStorage.getItem(vm.runInThisContext("storageKey"))
  );
  const corruptedUndoEnvelope = JSON.parse(
    JSON.stringify(coherentBatchEnvelope)
  );
  corruptedUndoEnvelope.last_batch_undo.records[0][1] = "0".repeat(64);
  const malformedUndoRejectedAtomically = vm.runInThisContext(
    "(()=>{const before=JSON.stringify(storageDocument());try{"
    + "validateStorageDocument(" + JSON.stringify(corruptedUndoEnvelope)
    + ");return false}catch(error){return JSON.stringify(storageDocument())"
    + "===before}})()"
  );
  vm.runInThisContext("setDecision('reject',false)");
  const sameBatchDecisionMutationReloads = vm.runInThisContext(
    "(()=>{const restored=validateStorageDocument(JSON.parse("
    + "localStorage.getItem(storageKey)));"
    + "return restored.state.get(pack.entries[0].id).decision==='reject'"
    + "&&restored.undo===null&&restored.undoDiscarded===false})()"
  );
  vm.runInThisContext(`
    state=new Map();drafts.clear();selected.clear();undoState=null;
    resetFilters();currentId=pack.entries[0].id;pageIndex=0;applyFilters()
  `);
  firstCheckbox = elements.get("entryList").children[0].children[0];
  firstCheckbox.checked = true;
  await firstCheckbox.fire("change");
  await elements.get("batchAccept").fire("click");
  vm.runInThisContext(
    "updateDraftAwareField(pack.entries[0],'note','post batch note',true)"
  );
  const sameBatchMetadataMutationReloads = vm.runInThisContext(
    "(()=>{const restored=validateStorageDocument(JSON.parse("
    + "localStorage.getItem(storageKey)));const item=restored.state.get("
    + "pack.entries[0].id);return item.decision==='accept'"
    + "&&item.note==='post batch note'&&restored.undo===null"
    + "&&restored.undoDiscarded===false})()"
  );
  vm.runInThisContext(`
    state=new Map();drafts.clear();selected.clear();undoState=null;
    {
      const record=pack.entries[0];
      drafts.set(record.id,{
        item:defaults(record),valid:false,error:"invalid selection sentinel"
      })
    }
    resetFilters();currentId=pack.entries[0].id;pageIndex=0;applyFilters()
  `);
  const invalidDraftCheckboxDisabled = (
    elements.get("entryList").children[0].children[0].disabled === true
  );
  await elements.get("selectUnreviewedPage").fire("click");
  const invalidDraftNotSelected = vm.runInThisContext(
    "selected.size===99&&!selected.has(pack.entries[0].id)"
  );
  vm.runInThisContext(`
    state=new Map();drafts.clear();selected.clear();undoState=null;
    resetFilters();localStorage.values.clear();localStorage.setCounts.clear();
    currentId=pack.entries[0].id;pageIndex=0;applyFilters()
  `);
  vm.runInThisContext("currentId=pack.entries[0].id;pageIndex=0;render()");
  const beforeTextStorage = localStorage.getItem(
    vm.runInThisContext("storageKey")
  );
  elements.get("note").value = "debounced note";
  await elements.get("note").fire("input");
  const textWasDebounced = localStorage.getItem(
    vm.runInThisContext("storageKey")
  ) === beforeTextStorage;
  await elements.get("note").fire("blur");
  const sparseAfterBlur = JSON.parse(localStorage.getItem(
    vm.runInThisContext("storageKey")
  ));
  vm.runInThisContext('setDecision("accept",false)');
  const sparseAfterDecision = JSON.parse(localStorage.getItem(
    vm.runInThisContext("storageKey")
  ));
  const firstId = vm.runInThisContext("pack.entries[0].id");
  const reloadDecision = vm.runInThisContext(
    "state=validateSparseDocument(JSON.parse(localStorage.getItem(storageKey)));"
    + "currentState(byId.get(" + JSON.stringify(firstId) + ")).decision"
  );
  localStorage.fail = true;
  vm.runInThisContext("currentId=pack.entries[1].id;render();setDecision('reject',false)");
  const memorySurvivedStorageFailure = vm.runInThisContext(
    "currentState(pack.entries[1]).decision==='reject'"
  );
  const storageWarningVisible = (
    elements.get("storageWarning").textContent.includes("памяти")
    && !elements.get("storageWarning").classList.contains("hidden")
  );
  localStorage.fail = false;
  globalThis.capturedBlob = undefined;
  vm.runInThisContext("downloadDocument(false)");
  const draftBytes = Buffer.from(await globalThis.capturedBlob.arrayBuffer());
  const draftDocument = JSON.parse(draftBytes.toString("utf8"));
  const draftExactlyOneLf = (
    draftBytes.at(-1) === 10 && draftBytes.at(-2) !== 10
  );
  const incompleteFinalDisabled = elements.get("finalExport").disabled;
  vm.runInThisContext(`
    state=new Map(pack.entries.map(record=>{
      const item=defaults(record);item.decision="accept";return [record.id,item]
    }));
    drafts.clear();updateProgress()
  `);
  const finalEnabled = !elements.get("finalExport").disabled;
  globalThis.capturedBlob = undefined;
  vm.runInThisContext("downloadDocument(true)");
  const finalBytes = Buffer.from(await globalThis.capturedBlob.arrayBuffer());
  const finalDocument = JSON.parse(finalBytes.toString("utf8"));
  const mixedFinalExportExact = vm.runInThisContext(`
    (()=>{
      const mixed=new Map(pack.entries.map(record=>{
        const item=defaults(record);item.decision="accept";
        return [record.id,item]
      }));
      mixed.get(pack.entries[1].id).decision="reject";
      const edited=mixed.get(pack.entries[1000].id);
      edited.decision="edit";
      edited.edited_segments=["Юникод 😀 "," хвост"];
      const documentValue=exportDocument(mixed,true,true);
      const editRecord=documentValue.decisions[1000];
      const encoded=documentBytes(documentValue);
      return documentValue.decisions[0].decision==="accept"
        &&documentValue.decisions[1].decision==="reject"
        &&editRecord.decision==="edit"
        &&editRecord.edited_translation==="Юникод 😀 $NAME$ хвост"
        &&encoded.at(-1)===10&&encoded.at(-2)!==10
    })()
  `);
  const reorderedDocument = {
    ...finalDocument,
    decisions: finalDocument.decisions.slice().reverse()
  };
  const reorderedText = JSON.stringify(reorderedDocument);
  vm.runInThisContext(`
    {
      const record=pack.entries[0];
      const before=defaults(record);
      const after=defaults(record);after.decision="accept";
      undoState={
        decision:"accept",
        entries:[{occurrence_id:record.id,before,after}]
      }
    }
    selected=new Set([pack.entries[0].id]);
    persistSparse();updateProgress()
  `);
  elements.get("importFile").files = [{
    size: Buffer.byteLength(reorderedText),
    text: async () => reorderedText
  }];
  await elements.get("importFile").fire(
    "change", {target: elements.get("importFile")}
  );
  const importedCount = vm.runInThisContext("state.size");
  const reorderedFullImportAccepted = vm.runInThisContext(
    "state.size===pack.entries.length"
    + "&&pack.entries.every(record=>currentState(record).decision==='accept')"
  );
  const legacyImportResetsBatchState = vm.runInThisContext(
    "undoState===null&&selected.size===0"
    + "&&JSON.parse(localStorage.getItem(storageKey)).last_batch_undo===null"
  );
  const reloadedFinalBytes = vm.runInThisContext(`
    (()=>{
      const restored=validateStorageDocument(JSON.parse(
        localStorage.getItem(storageKey)
      ));
      return documentBytes(exportDocument(restored.state,true,true))
    })()
  `);
  const finalExportStableAfterStorageV3Reload = Buffer.from(
    reloadedFinalBytes
  ).equals(finalBytes);
  const maxDecisionBytes = vm.runInThisContext("MAX_DECISIONS_BYTES");
  const finalTextAtLimitBase = finalBytes.toString("utf8");
  const finalTextAtLimit = finalTextAtLimitBase + " ".repeat(
    maxDecisionBytes - Buffer.byteLength(finalTextAtLimitBase)
  );
  let exactLimitRead = false;
  elements.get("importFile").files = [{
    size: maxDecisionBytes,
    text: async () => { exactLimitRead = true; return finalTextAtLimit; }
  }];
  await elements.get("importFile").fire(
    "change", {target: elements.get("importFile")}
  );
  const exactDecisionLimitAccepted = exactLimitRead && vm.runInThisContext(
    "state.size===pack.entries.length"
  );
  const beforeInvalidImport = vm.runInThisContext(
    "JSON.stringify(sparseDocument())"
  );
  const invalidDocument = JSON.parse(finalBytes.toString("utf8"));
  invalidDocument.pack_fingerprint = "0".repeat(64);
  const invalidText = JSON.stringify(invalidDocument);
  vm.runInThisContext("selected=new Set([pack.entries[0].id]);updateProgress()");
  elements.get("importFile").files = [{
    size: Buffer.byteLength(invalidText),
    text: async () => invalidText
  }];
  await elements.get("importFile").fire(
    "change", {target: elements.get("importFile")}
  );
  const atomicInvalidImport = beforeInvalidImport === vm.runInThisContext(
    "JSON.stringify(sparseDocument())"
  );
  const invalidImportPreservesSelection = vm.runInThisContext(
    "selected.size===1&&selected.has(pack.entries[0].id)"
  );
  vm.runInThisContext(`
    el("search").value="";
    el("attentionFilter").checked=false;
    el("fileFilter").value="";
    el("statusFilter").value="";
    el("decisionFilter").value="accept";
    el("warningFilter").value="";
    currentId=pack.entries[Math.floor(pack.entries.length/2)].id;
    pageIndex=0;
    applyFilters();
    {
      const record=byId.get(currentId);
      drafts.set(record.id,{
        item:cloneItem(currentState(record)),
        valid:false,
        error:"atomic import sentinel"
      });
      render()
    }
  `);
  function captureImportParts() {
    return vm.runInThisContext(`({
      decisionBytes:JSON.stringify(exportDocument(state,false,false)),
      sparseBytes:JSON.stringify(sparseDocument()),
      storageBytes:localStorage.getItem(storageKey),
      draftsBytes:JSON.stringify([...drafts.entries()].map(
        ([id,draft])=>[id,{
          item:draft.item,valid:draft.valid,error:draft.error
        }]
      )),
      uiBytes:JSON.stringify({
        currentId,
        visible:visible.map(record=>record.id),
        search:el("search").value,
        attention:el("attentionFilter").checked,
        file:el("fileFilter").value,
        status:el("statusFilter").value,
        decisionFilter:el("decisionFilter").value,
        warning:el("warningFilter").value,
        resultCount:el("resultCount").textContent,
        path:el("path").textContent,
        decision:el("decision").value,
        emptyHidden:el("empty").classList.contains("hidden"),
        reviewHidden:el("review").classList.contains("hidden"),
        selected:[...selected]
      })
    })`);
  }
  function cloneFinalDocument() {
    return JSON.parse(JSON.stringify(finalDocument));
  }
  const partialOneDocument = cloneFinalDocument();
  partialOneDocument.decisions.pop();
  const partialManyDocument = cloneFinalDocument();
  partialManyDocument.decisions = partialManyDocument.decisions.slice(
    0, Math.floor(partialManyDocument.decisions.length / 2)
  );
  const duplicateDocument = cloneFinalDocument();
  duplicateDocument.decisions[duplicateDocument.decisions.length - 1] = {
    ...duplicateDocument.decisions[0]
  };
  const unknownDocument = cloneFinalDocument();
  unknownDocument.decisions[unknownDocument.decisions.length - 1] = {
    ...unknownDocument.decisions[unknownDocument.decisions.length - 1],
    occurrence_id: "0".repeat(64)
  };
  const extraDocument = cloneFinalDocument();
  extraDocument.decisions.push({...extraDocument.decisions[0]});
  const malformedLastDocument = cloneFinalDocument();
  malformedLastDocument.decisions.at(-1).unknown_field = true;
  const invalidImportDocuments = [
    ["missing_occurrence", partialOneDocument],
    ["partial_document", partialManyDocument],
    ["duplicate_occurrence", duplicateDocument],
    ["unknown_occurrence", unknownDocument],
    ["extra_entry", extraDocument],
    ["malformed_last_record", malformedLastDocument]
  ];
  const completeImportSnapshot = captureImportParts();
  const invalidImportResults = [];
  for (const [name, documentValue] of invalidImportDocuments) {
    const text = JSON.stringify(documentValue);
    elements.get("importFile").files = [{
      size: Buffer.byteLength(text),
      text: async () => text
    }];
    await elements.get("importFile").fire(
      "change", {target: elements.get("importFile")}
    );
    const after = captureImportParts();
    invalidImportResults.push({
      name,
      rejected: elements.get("error").textContent.startsWith(
        "Импорт отклонён:"
      ),
      stateUnchanged:
        after.decisionBytes === completeImportSnapshot.decisionBytes,
      sparseUnchanged:
        after.sparseBytes === completeImportSnapshot.sparseBytes,
      storageUnchanged:
        after.storageBytes === completeImportSnapshot.storageBytes,
      draftsUnchanged:
        after.draftsBytes === completeImportSnapshot.draftsBytes,
      uiUnchanged: after.uiBytes === completeImportSnapshot.uiBytes
    });
  }
  const completeImportFailuresAtomic = invalidImportResults.every(
    result => Object.entries(result).every(
      ([key, value]) => key === "name" || value === true
    )
  );
  const beforeQuotaImport = captureImportParts();
  localStorage.fail = true;
  elements.get("importFile").files = [{
    size: finalBytes.length,
    text: async () => finalBytes.toString("utf8")
  }];
  await elements.get("importFile").fire(
    "change", {target: elements.get("importFile")}
  );
  localStorage.fail = false;
  const afterQuotaImport = captureImportParts();
  const quotaImportFailureAtomic = (
    beforeQuotaImport.decisionBytes === afterQuotaImport.decisionBytes
    && beforeQuotaImport.sparseBytes === afterQuotaImport.sparseBytes
    && beforeQuotaImport.storageBytes === afterQuotaImport.storageBytes
    && beforeQuotaImport.draftsBytes === afterQuotaImport.draftsBytes
    && beforeQuotaImport.uiBytes === afterQuotaImport.uiBytes
    && elements.get("storageWarning").textContent.includes("checkpoint")
  );
  const partialImportResult = invalidImportResults.find(
    result => result.name === "missing_occurrence"
  );
  const partialImportState12871Preserved = (
    finalDocument.decisions.length === 12871
    && partialImportResult.stateUnchanged
    && partialImportResult.sparseUnchanged
  );
  const partialImportDraftsPreserved = partialImportResult.draftsUnchanged;
  const partialImportStoragePreserved = partialImportResult.storageUnchanged;
  const partialImportCardFiltersPreserved = partialImportResult.uiUnchanged;
  let oversizedRead = false;
  elements.get("importFile").files = [{
    size: vm.runInThisContext("MAX_DECISIONS_BYTES") + 1,
    text: async () => { oversizedRead = true; return "{}"; }
  }];
  await elements.get("importFile").fire(
    "change", {target: elements.get("importFile")}
  );
  vm.runInThisContext(`
    state=new Map();drafts.clear();
    el("decisionFilter").value="unreviewed";
    currentId=pack.entries[0].id;pageIndex=0;applyFilters()
  `);
  globalThis.focusedElement = undefined;
  const keyboardEditId = vm.runInThisContext("currentId");
  await fireDocument("keydown", {
    key: "E", target: elements.get("review"), preventDefault() {}
  });
  const filteredKeyboardEditStayed = vm.runInThisContext(
    "currentId===" + JSON.stringify(keyboardEditId)
    + "&&currentState(byId.get(currentId)).decision==='edit'"
  );
  const filteredKeyboardEditorFocused = (
    globalThis.focusedElement === elements.get("editor").querySelector("textarea")
  );
  const filteredKeyboardCountIsStrict = vm.runInThisContext(
    "visible.length===pack.entries.length-1"
    + "&&!visible.some(record=>record.id===currentId)"
  );
  vm.runInThisContext(`
    state=new Map();drafts.clear();
    el("decisionFilter").value="unreviewed";
    currentId=pack.entries[1].id;pageIndex=0;applyFilters()
  `);
  globalThis.focusedElement = undefined;
  const selectEditId = vm.runInThisContext("currentId");
  elements.get("decision").value = "edit";
  await elements.get("decision").fire("change");
  const filteredSelectEditStayed = vm.runInThisContext(
    "currentId===" + JSON.stringify(selectEditId)
    + "&&currentState(byId.get(currentId)).decision==='edit'"
  );
  const filteredSelectEditorFocused = (
    globalThis.focusedElement === elements.get("editor").querySelector("textarea")
  );
  const filteredSelectCountIsStrict = vm.runInThisContext(
    "visible.length===pack.entries.length-1"
    + "&&!visible.some(record=>record.id===currentId)"
  );
  vm.runInThisContext(`
    el("decisionFilter").value="";
    state=new Map(pack.entries.map(record=>{
      const item=defaults(record);item.decision="accept";return [record.id,item]
    }));
    drafts.clear();currentId=pack.entries[0].id;pageIndex=0;applyFilters();
    setDecision("edit",false)
  `);
  let editArea = elements.get("editor").querySelector("textarea");
  editArea.value = "VALID LAST STATE";
  await editArea.fire("input");
  await editArea.fire("blur");
  const lastValidTranslation = vm.runInThisContext(
    "fullTranslation(byId.get(currentId),currentState(byId.get(currentId)))"
  );
  const validEditCounters = vm.runInThisContext(
    'el("progressText").textContent==="12871 / 12871 проверено"'
    + '&&el("progressDetails").textContent.includes("Непроверенные: 0")'
    + '&&el("progressDetails").textContent.includes("невалидные edits: 0")'
  );
  editArea = elements.get("editor").querySelector("textarea");
  editArea.value = "$INVALID_BYTES";
  await editArea.fire("input");
  const invalidDraftPresent = vm.runInThisContext(
    "drafts.has(currentId)&&drafts.get(currentId).valid===false"
  );
  const invalidEditCounters = vm.runInThisContext(
    'el("progressText").textContent==="12870 / 12871 проверено"'
    + '&&el("progressDetails").textContent.includes("Непроверенные: 0")'
    + '&&el("progressDetails").textContent.includes("невалидные edits: 1")'
    + '&&el("progressDetails").textContent.includes("без валидного решения: 1")'
  );
  globalThis.capturedBlob = undefined;
  vm.runInThisContext("downloadDocument(false)");
  const invalidEditDraftBytes = Buffer.from(
    await globalThis.capturedBlob.arrayBuffer()
  );
  const invalidEditDraftDocument = JSON.parse(
    invalidEditDraftBytes.toString("utf8")
  );
  const invalidEditDraftRecord = invalidEditDraftDocument.decisions.find(
    item => item.occurrence_id === keyboardEditId
  );
  const invalidEditDraftUsesLastValid = (
    invalidEditDraftRecord.edited_translation === lastValidTranslation
  );
  const invalidEditDraftExcludesInvalidBytes = (
    !invalidEditDraftBytes.includes(Buffer.from("$INVALID_BYTES"))
  );
  const invalidEditDraftExactlyOneLf = (
    invalidEditDraftBytes.at(-1) === 10
    && invalidEditDraftBytes.at(-2) !== 10
  );
  const invalidEditFinalDisabled = elements.get("finalExport").disabled;
  globalThis.capturedBlob = undefined;
  let invalidEditFinalRejected = false;
  try {
    vm.runInThisContext("downloadDocument(true)");
  } catch (error) {
    invalidEditFinalRejected = error.message.includes("невалидную редакцию");
  }
  const invalidEditFinalNoBlob = globalThis.capturedBlob === undefined;
  const tagInput = elements.get("tags").querySelectorAll("input").find(
    input => input.value === "terminology"
  );
  tagInput.checked = true;
  await tagInput.fire("change");
  const tagSavedDuringInvalidDraft = vm.runInThisContext(
    "currentState(byId.get(currentId)).tags.includes('terminology')"
    + "&&drafts.get(currentId).item.tags.includes('terminology')"
    + "&&drafts.get(currentId).valid===false"
  );
  const tagPersistedDuringInvalidDraft = vm.runInThisContext(
    "validateSparseDocument(JSON.parse(localStorage.getItem(storageKey)))"
    + ".get(currentId).tags.includes('terminology')"
  );
  editArea.value = "VALID TAG REPAIR";
  await editArea.fire("input");
  await editArea.fire("blur");
  const tagDraftAfterRepair = vm.runInThisContext(
    "exportDocument(state,false,false).decisions.find("
    + "item=>item.occurrence_id===currentId)"
  );
  const tagFinalAfterRepair = vm.runInThisContext(
    "exportDocument(state,true,true).decisions.find("
    + "item=>item.occurrence_id===currentId)"
  );
  const tagSurvivesInvalidRepair = (
    tagDraftAfterRepair.tags.includes("terminology")
    && tagFinalAfterRepair.tags.includes("terminology")
    && tagDraftAfterRepair.edited_translation === "VALID TAG REPAIR"
    && !JSON.stringify(tagDraftAfterRepair).includes("$INVALID_BYTES")
  );
  const repairedEditCounters = vm.runInThisContext(
    'el("progressText").textContent==="12871 / 12871 проверено"'
    + '&&el("progressDetails").textContent.includes("Непроверенные: 0")'
    + '&&el("progressDetails").textContent.includes("невалидные edits: 0")'
  );
  vm.runInThisContext(`
    state=new Map(pack.entries.map(record=>{
      const item=defaults(record);item.decision="accept";return [record.id,item]
    }));
    drafts.clear();currentId=pack.entries[0].id;pageIndex=0;applyFilters();
    setDecision("edit",false)
  `);
  editArea = elements.get("editor").querySelector("textarea");
  editArea.value = "VALID GLOSSARY STATE";
  await editArea.fire("input");
  await editArea.fire("blur");
  editArea = elements.get("editor").querySelector("textarea");
  editArea.value = "$INVALID_GLOSSARY_BYTES";
  await editArea.fire("input");
  elements.get("glossary").checked = true;
  await elements.get("glossary").fire("change");
  const glossarySavedDuringInvalidDraft = vm.runInThisContext(
    "currentState(byId.get(currentId)).glossary_candidate===true"
    + "&&drafts.get(currentId).item.glossary_candidate===true"
    + "&&drafts.get(currentId).valid===false"
  );
  const glossaryPersistedDuringInvalidDraft = vm.runInThisContext(
    "validateSparseDocument(JSON.parse(localStorage.getItem(storageKey)))"
    + ".get(currentId).glossary_candidate===true"
  );
  editArea.value = "VALID GLOSSARY REPAIR";
  await editArea.fire("input");
  await editArea.fire("blur");
  const glossaryDraftAfterRepair = vm.runInThisContext(
    "exportDocument(state,false,false).decisions.find("
    + "item=>item.occurrence_id===currentId)"
  );
  const glossaryFinalAfterRepair = vm.runInThisContext(
    "exportDocument(state,true,true).decisions.find("
    + "item=>item.occurrence_id===currentId)"
  );
  const glossarySurvivesInvalidRepair = (
    glossaryDraftAfterRepair.glossary_candidate === true
    && glossaryFinalAfterRepair.glossary_candidate === true
    && glossaryDraftAfterRepair.edited_translation === "VALID GLOSSARY REPAIR"
    && !JSON.stringify(glossaryDraftAfterRepair).includes(
      "$INVALID_GLOSSARY_BYTES"
    )
  );
  vm.runInThisContext(`
    state=new Map();drafts.clear();
    el("decisionFilter").value="unreviewed";
    currentId=pack.entries[0].id;pageIndex=0;applyFilters()
  `);
  await fireDocument("keydown", {
    key: "E", target: elements.get("review"), preventDefault() {}
  });
  editArea = elements.get("editor").querySelector("textarea");
  editArea.value = "VALID FILTERED ACCEPT EDIT";
  await editArea.fire("input");
  await editArea.fire("blur");
  const filteredAcceptRemainingBefore = vm.runInThisContext("visible.length");
  await fireDocument("keydown", {
    key: "A", target: elements.get("review"), preventDefault() {}
  });
  const filteredEditAcceptAdvance = vm.runInThisContext(
    "visible.length===pack.entries.length-1"
    + "&&currentId===pack.entries[1].id"
    + "&&currentId!==null"
    + "&&!el('review').classList.contains('hidden')"
    + "&&el('empty').classList.contains('hidden')"
  );
  vm.runInThisContext(`
    state=new Map();drafts.clear();
    el("decisionFilter").value="unreviewed";
    currentId=pack.entries[1].id;pageIndex=0;applyFilters()
  `);
  await fireDocument("keydown", {
    key: "E", target: elements.get("review"), preventDefault() {}
  });
  editArea = elements.get("editor").querySelector("textarea");
  editArea.value = "VALID FILTERED REJECT EDIT";
  await editArea.fire("input");
  await editArea.fire("blur");
  const filteredRejectRemainingBefore = vm.runInThisContext("visible.length");
  await fireDocument("keydown", {
    key: "R", target: elements.get("review"), preventDefault() {}
  });
  const filteredEditRejectAdvance = vm.runInThisContext(
    "visible.length===pack.entries.length-1"
    + "&&currentId===pack.entries[2].id"
    + "&&currentId!==null"
    + "&&!el('review').classList.contains('hidden')"
    + "&&el('empty').classList.contains('hidden')"
  );
  vm.runInThisContext(`
    state=new Map();drafts.clear();
    el("decisionFilter").value="unreviewed";
    currentId=pack.entries[pack.entries.length-1].id;pageIndex=0;applyFilters()
  `);
  await fireDocument("keydown", {
    key: "E", target: elements.get("review"), preventDefault() {}
  });
  editArea = elements.get("editor").querySelector("textarea");
  editArea.value = "VALID FILTERED END EDIT";
  await editArea.fire("input");
  await editArea.fire("blur");
  await fireDocument("keydown", {
    key: "A", target: elements.get("review"), preventDefault() {}
  });
  const filteredEditNoEndWrap = vm.runInThisContext(
    "currentId===pack.entries[pack.entries.length-1].id"
    + "&&currentId!==pack.entries[0].id"
    + "&&!visible.some(record=>record.id===currentId)"
    + "&&!el('review').classList.contains('hidden')"
  );
  const decisionFilterCases = [];
  for (const filter of ["unreviewed", "accept", "edit", "reject"]) {
    for (const position of ["first", "middle", "last"]) {
      const terminalDecision = (
        filter === "unreviewed"
          ? (position === "middle" ? "reject" : "accept")
          : filter
      );
      decisionFilterCases.push({
        filter,
        position,
        awayDecision: filter === "edit" ? "accept" : "edit",
        terminalDecision
      });
    }
  }
  function filterStateSnapshot(filter, targetId) {
    return vm.runInThisContext(`(()=>{
      const expected=pack.entries.filter(
        record=>currentState(record).decision===${JSON.stringify(filter)}
      );
      const target=byId.get(${JSON.stringify(targetId)});
      return {
        predicateExact:
          visible.length===expected.length
          &&visible.every((record,index)=>record.id===expected[index].id),
        resultCountExact:
          el("resultCount").textContent==="Найдено: "+visible.length,
        targetDecision:currentState(target).decision,
        currentId,
        dropdownDecision:el("decision").value,
        cardVisible:!el("review").classList.contains("hidden")
      }
    })()`);
  }
  const decisionFilterMatrix = [];
  for (const testCase of decisionFilterCases) {
    const targetIndex = (
      testCase.position === "first"
        ? 0
        : testCase.position === "last"
          ? vm.runInThisContext("pack.entries.length-1")
          : vm.runInThisContext("Math.floor(pack.entries.length/2)")
    );
    const targetId = vm.runInThisContext(
      `pack.entries[${targetIndex}].id`
    );
    vm.runInThisContext(`
      state=new Map();
      drafts.clear();
      for(const record of pack.entries){
        const item=defaults(record);
        item.decision=${JSON.stringify(testCase.filter)};
        if(!isDefaultItem(record,item))state.set(record.id,item)
      }
      el("search").value="";
      el("attentionFilter").checked=false;
      el("fileFilter").value="";
      el("statusFilter").value="";
      el("decisionFilter").value=${JSON.stringify(testCase.filter)};
      el("warningFilter").value="";
      currentId=${JSON.stringify(targetId)};
      pageIndex=0;
      applyFilters()
    `);
    vm.runInThisContext(
      `setDecision(${JSON.stringify(testCase.awayDecision)},false)`
    );
    const afterAway = filterStateSnapshot(testCase.filter, targetId);
    vm.runInThisContext(
      `setDecision(${JSON.stringify(testCase.terminalDecision)},true)`
    );
    const afterTerminal = filterStateSnapshot(testCase.filter, targetId);
    const expectedAdvanceId = vm.runInThisContext(
      targetIndex + 1 < vm.runInThisContext("pack.entries.length")
        ? `pack.entries[${targetIndex + 1}].id`
        : `pack.entries[${targetIndex}].id`
    );
    const expectedCardDecision = (
      targetIndex + 1 < vm.runInThisContext("pack.entries.length")
        ? testCase.filter
        : testCase.terminalDecision
    );
    vm.runInThisContext(`
      currentId=${JSON.stringify(targetId)};
      render();
      setDecision(${JSON.stringify(testCase.filter)},false)
    `);
    const afterRestore = filterStateSnapshot(testCase.filter, targetId);
    decisionFilterMatrix.push({
      ...testCase,
      predicateExact:
        afterAway.predicateExact
        && afterTerminal.predicateExact
        && afterRestore.predicateExact,
      resultCountExact:
        afterAway.resultCountExact
        && afterTerminal.resultCountExact
        && afterRestore.resultCountExact,
      awayCardActual:
        afterAway.currentId === targetId
        && afterAway.targetDecision === testCase.awayDecision
        && afterAway.dropdownDecision === testCase.awayDecision
        && afterAway.cardVisible,
      terminalStateActual:
        afterTerminal.targetDecision === testCase.terminalDecision
        && afterTerminal.dropdownDecision === expectedCardDecision
        && afterTerminal.cardVisible,
      advanceOriginalOrder: afterTerminal.currentId === expectedAdvanceId,
      restoredReentry:
        afterRestore.targetDecision === testCase.filter
        && afterRestore.currentId === targetId
        && afterRestore.dropdownDecision === testCase.filter
        && vm.runInThisContext(
          `visible.some(record=>record.id===${JSON.stringify(targetId)})`
        ),
      endNoWrap:
        testCase.position !== "last"
        || afterTerminal.currentId === targetId
    });
  }
  const decisionFilterStateMatrix = decisionFilterMatrix.every(
    result => (
      result.predicateExact
      && result.awayCardActual
      && result.terminalStateActual
      && result.advanceOriginalOrder
    )
  );
  const matchingFilterReentry = decisionFilterMatrix.every(
    result => result.restoredReentry
  );
  const filterResultCount = decisionFilterMatrix.every(
    result => result.resultCountExact
  );
  const filterEndNoWrap = decisionFilterMatrix.every(
    result => result.endNoWrap
  );
  vm.runInThisContext('el("decisionFilter").value="";state=new Map();drafts.clear();currentId=pack.entries[0].id;pageIndex=0;applyFilters()');
  await fireDocument("keydown", {
    key: "a", target: elements.get("review"), preventDefault() {}
  });
  const keyboardAcceptedAndAdvanced = vm.runInThisContext(
    "currentState(pack.entries[0]).decision==='accept'&&currentId===pack.entries[1].id"
  );
  const beforeFocusedKey = vm.runInThisContext("currentId");
  await fireDocument("keydown", {
    key: "r", target: elements.get("search"), preventDefault() {}
  });
  const focusedKeyExcluded = beforeFocusedKey === vm.runInThisContext(
    "currentId"
  );
  vm.runInThisContext("currentId=pack.entries[pack.entries.length-1].id;render();move(1)");
  const noEndWrap = vm.runInThisContext(
    "currentId===pack.entries[pack.entries.length-1].id"
  );
  vm.runInThisContext("currentId=pack.entries[0].id;pageIndex=0;render();move(-1)");
  const noStartWrap = vm.runInThisContext(
    "currentId===pack.entries[0].id"
  );
  await fireDocument("keydown", {
    key: "/", target: elements.get("review"), preventDefault() {}
  });
  const searchFocused = globalThis.focusedElement === elements.get("search");
  process.stdout.write(JSON.stringify({
    initialRows,
    secondPageRows,
    keyAndOrdinalRendered,
    nextContextNavigated,
    previousContextNavigated,
    keySearchExact,
    exactRepeatGrouping,
    repeatNextNavigated,
    repeatPreviousNavigated,
    inconsistentRepeatFilterExact,
    noFuzzyGrouping,
    pageLocalSelectionCount,
    pageChangeClearsSelection,
    searchChangeClearsSelection,
    filterChangeClearsSelection,
    confirmationCancelAtomic,
    zeroSelectionRejected,
    hiddenSelectionRejectedAtomically,
    reviewedNotOverwritten,
    batchAcceptAtomic,
    batchPreservesMetadata,
    batchSingleSparseSave,
    confirmationIsExplicit,
    progressCountersImmediate,
    undoStoredForExactPack,
    undoValidationFailureAtomic,
    undoRestoresExactPriorState,
    undoPreservesUnrelatedIndividualChange,
    undoConsumed,
    batchRejectExact,
    reviewedCheckboxDisabled,
    clearResetsUndo,
    multiTagCanonicalization,
    batchReloadUndo,
    legacyV2UnsortedUndoCompatible,
    legacyV2ReverseUndoMigratesCanonically,
    corruptLegacyUndoSalvagesDecisions,
    repeatedSaveReloadUndo,
    exactMultiTagMetadataRestoration,
    affectedTagMutationClearsUndo,
    legacySparseV1Compatible,
    legacyStorageV1UnsortedTags,
    legacyDraftV1UnsortedTags,
    duplicateTagRejected,
    unknownTagRejected,
    storageV3RoundTrip:storageV3Validation.roundTrip,
    storageV3Compact:storageV3Validation.compact,
    storageV3InvalidAtomic:storageV3Validation.invalidAtomic,
    storageFailureKeepsMemoryExport,
    storageEnvelopeFailureCoherent,
    newBatchReplacesUndo,
    latestBatchOnlyUndo,
    malformedUndoRejectedAtomically,
    sameBatchDecisionMutationReloads,
    sameBatchMetadataMutationReloads,
    invalidDraftCheckboxDisabled,
    invalidDraftNotSelected,
    textWasDebounced,
    storageSchemaAfterBlur: sparseAfterBlur.storage_schema_version,
    storageAfterBlurRecords: sparseAfterBlur.records.length,
    storageAfterDecisionRecords: sparseAfterDecision.records.length,
    reloadDecision,
    memorySurvivedStorageFailure,
    storageWarningVisible,
    draftDecisionCount: draftDocument.decisions.length,
    draftExactlyOneLf,
    incompleteFinalDisabled,
    finalEnabled,
    finalDecisionCount: finalDocument.decisions.length,
    finalExactlyOneLf: finalBytes.at(-1) === 10 && finalBytes.at(-2) !== 10,
    mixedFinalExportExact,
    importedCount,
    reorderedFullImportAccepted,
    legacyImportResetsBatchState,
    finalExportStableAfterStorageV3Reload,
    exactDecisionLimitAccepted,
    atomicInvalidImport,
    invalidImportPreservesSelection,
    invalidImportCaseCount: invalidImportResults.length,
    completeImportFailuresAtomic,
    quotaImportFailureAtomic,
    partialImportState12871Preserved,
    partialImportDraftsPreserved,
    partialImportStoragePreserved,
    partialImportCardFiltersPreserved,
    oversizedRead,
    filteredKeyboardEditStayed,
    filteredKeyboardEditorFocused,
    filteredKeyboardCountIsStrict,
    filteredSelectEditStayed,
    filteredSelectEditorFocused,
    filteredSelectCountIsStrict,
    validEditCounters,
    invalidDraftPresent,
    invalidEditCounters,
    invalidEditDraftDecisionCount: invalidEditDraftDocument.decisions.length,
    invalidEditDraftUsesLastValid,
    invalidEditDraftExcludesInvalidBytes,
    invalidEditDraftExactlyOneLf,
    invalidEditFinalDisabled,
    invalidEditFinalRejected,
    invalidEditFinalNoBlob,
    tagSavedDuringInvalidDraft,
    tagPersistedDuringInvalidDraft,
    tagSurvivesInvalidRepair,
    repairedEditCounters,
    glossarySavedDuringInvalidDraft,
    glossaryPersistedDuringInvalidDraft,
    glossarySurvivesInvalidRepair,
    filteredAcceptRemainingBefore,
    filteredEditAcceptAdvance,
    filteredRejectRemainingBefore,
    filteredEditRejectAdvance,
    filteredEditNoEndWrap,
    decisionFilterCaseCount: decisionFilterMatrix.length,
    decisionFilterStateMatrix,
    matchingFilterReentry,
    filterResultCount,
    filterEndNoWrap,
    keyboardAcceptedAndAdvanced,
    focusedKeyExcluded,
    noEndWrap,
    noStartWrap,
    searchFocused
  }));
})().catch(error => {
  process.stderr.write(String(error.stack || error));
  process.exitCode = 1;
});
""".strip()
        + "\n"
    )
    completed = subprocess.run(
        [node, str(harness), str(runtime)],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result == {
        "initialRows": 100,
        "secondPageRows": 100,
        "keyAndOrdinalRendered": True,
        "nextContextNavigated": True,
        "previousContextNavigated": True,
        "keySearchExact": True,
        "exactRepeatGrouping": True,
        "repeatNextNavigated": True,
        "repeatPreviousNavigated": True,
        "inconsistentRepeatFilterExact": True,
        "noFuzzyGrouping": True,
        "pageLocalSelectionCount": True,
        "pageChangeClearsSelection": True,
        "searchChangeClearsSelection": True,
        "filterChangeClearsSelection": True,
        "confirmationCancelAtomic": True,
        "zeroSelectionRejected": True,
        "hiddenSelectionRejectedAtomically": True,
        "reviewedNotOverwritten": True,
        "batchAcceptAtomic": True,
        "batchPreservesMetadata": True,
        "batchSingleSparseSave": True,
        "confirmationIsExplicit": True,
        "progressCountersImmediate": True,
        "undoStoredForExactPack": True,
        "undoValidationFailureAtomic": True,
        "undoRestoresExactPriorState": True,
        "undoPreservesUnrelatedIndividualChange": True,
        "undoConsumed": True,
        "batchRejectExact": True,
        "reviewedCheckboxDisabled": True,
        "clearResetsUndo": True,
        "multiTagCanonicalization": True,
        "batchReloadUndo": True,
        "legacyV2UnsortedUndoCompatible": True,
        "legacyV2ReverseUndoMigratesCanonically": True,
        "corruptLegacyUndoSalvagesDecisions": True,
        "repeatedSaveReloadUndo": True,
        "exactMultiTagMetadataRestoration": True,
        "affectedTagMutationClearsUndo": True,
        "legacySparseV1Compatible": True,
        "legacyStorageV1UnsortedTags": True,
        "legacyDraftV1UnsortedTags": True,
        "duplicateTagRejected": True,
        "unknownTagRejected": True,
        "storageV3RoundTrip": True,
        "storageV3Compact": True,
        "storageV3InvalidAtomic": True,
        "storageFailureKeepsMemoryExport": True,
        "storageEnvelopeFailureCoherent": True,
        "newBatchReplacesUndo": True,
        "latestBatchOnlyUndo": True,
        "malformedUndoRejectedAtomically": True,
        "sameBatchDecisionMutationReloads": True,
        "sameBatchMetadataMutationReloads": True,
        "invalidDraftCheckboxDisabled": True,
        "invalidDraftNotSelected": True,
        "textWasDebounced": True,
        "storageSchemaAfterBlur": 3,
        "storageAfterBlurRecords": 1,
        "storageAfterDecisionRecords": 1,
        "reloadDecision": "accept",
        "memorySurvivedStorageFailure": True,
        "storageWarningVisible": True,
        "draftDecisionCount": 12871,
        "draftExactlyOneLf": True,
        "incompleteFinalDisabled": True,
        "finalEnabled": True,
        "finalDecisionCount": 12871,
        "finalExactlyOneLf": True,
        "mixedFinalExportExact": True,
        "importedCount": 12871,
        "reorderedFullImportAccepted": True,
        "legacyImportResetsBatchState": True,
        "finalExportStableAfterStorageV3Reload": True,
        "exactDecisionLimitAccepted": True,
        "atomicInvalidImport": True,
        "invalidImportPreservesSelection": True,
        "invalidImportCaseCount": 6,
        "completeImportFailuresAtomic": True,
        "quotaImportFailureAtomic": True,
        "partialImportState12871Preserved": True,
        "partialImportDraftsPreserved": True,
        "partialImportStoragePreserved": True,
        "partialImportCardFiltersPreserved": True,
        "oversizedRead": False,
        "filteredKeyboardEditStayed": True,
        "filteredKeyboardEditorFocused": True,
        "filteredKeyboardCountIsStrict": True,
        "filteredSelectEditStayed": True,
        "filteredSelectEditorFocused": True,
        "filteredSelectCountIsStrict": True,
        "validEditCounters": True,
        "invalidDraftPresent": True,
        "invalidEditCounters": True,
        "invalidEditDraftDecisionCount": 12871,
        "invalidEditDraftUsesLastValid": True,
        "invalidEditDraftExcludesInvalidBytes": True,
        "invalidEditDraftExactlyOneLf": True,
        "invalidEditFinalDisabled": True,
        "invalidEditFinalRejected": True,
        "invalidEditFinalNoBlob": True,
        "tagSavedDuringInvalidDraft": True,
        "tagPersistedDuringInvalidDraft": True,
        "tagSurvivesInvalidRepair": True,
        "repairedEditCounters": True,
        "glossarySavedDuringInvalidDraft": True,
        "glossaryPersistedDuringInvalidDraft": True,
        "glossarySurvivesInvalidRepair": True,
        "filteredAcceptRemainingBefore": 12870,
        "filteredEditAcceptAdvance": True,
        "filteredRejectRemainingBefore": 12870,
        "filteredEditRejectAdvance": True,
        "filteredEditNoEndWrap": True,
        "decisionFilterCaseCount": 12,
        "decisionFilterStateMatrix": True,
        "matchingFilterReentry": True,
        "filterResultCount": True,
        "filterEndNoWrap": True,
        "keyboardAcceptedAndAdvanced": True,
        "focusedKeyExcluded": True,
        "noEndWrap": True,
        "noStartWrap": True,
        "searchFocused": True,
    }
