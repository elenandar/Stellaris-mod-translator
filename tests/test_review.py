from __future__ import annotations

from dataclasses import replace
import base64
import hashlib
import json
from pathlib import Path
import os
import re
import shutil
import subprocess

import pytest

from stellaris_mod_translator import review
from stellaris_mod_translator.engine import (
    SafetyError,
    _snapshot,
    _tree_hash,
    translate_mod,
)
from stellaris_mod_translator.ollama import OllamaError
from stellaris_mod_translator.review import (
    ReviewIdentity,
    build_review_pack,
    validate_decisions_payload,
)


class ReviewClient:
    def exact_model(self, tag: str) -> dict[str, str]:
        assert tag == "synthetic-review:1"
        return {"tag": tag, "digest": "sha256:synthetic-review"}

    def translate(self, *, tag: str, text: str) -> str:
        if "FALLBACK_SENTINEL" in text:
            raise OllamaError("synthetic fallback")
        if "UNCHANGED_SENTINEL" in text:
            return text
        return "RU " + text


def make_review_inputs(
    tmp_path: Path,
    *,
    old_schema: bool = False,
    hostile_text: bool = False,
    bom: bool = False,
) -> tuple[Path, Path, ReviewIdentity]:
    source = tmp_path / "source"
    first = source / "localisation/english/first_l_english.yml"
    second = source / "localisation/english/second_l_english.yml"
    first.parent.mkdir(parents=True)
    hostile = "</script><script>synthetic_unicode_Ж"
    first_payload = (
            'l_english:\n'
            f' duplicate.key:0 "CHANGE_SENTINEL {hostile if hostile_text else "alpha"} $NAME$"\n'
            ' duplicate.key:0 "UNCHANGED_SENTINEL beta [Root.GetName]"\n'
            ' unsupported.synthetic:0 DEFERRED_UNSUPPORTED_RAW\n'
            ' deferred.one:0 "DEFERRED_RAW_ONE"\n'
        ).encode()
    first.write_bytes((b"\xef\xbb\xbf" if bom else b"") + first_payload)
    second.write_bytes(
        b'l_english:\n'
        b' second.one:0 "FALLBACK_SENTINEL gamma \\"quoted\\""\n'
        b' second.two:0 "CHANGE_SENTINEL delta"\n'
        b' deferred.two:0 "DEFERRED_RAW_TWO"\n'
    )
    candidate = tmp_path / "candidate"
    translate_mod(
        source,
        candidate,
        "synthetic-review:1",
        max_occurrences_per_file=2,
        client_factory=ReviewClient,
    )
    if old_schema:
        report_path = candidate / "translation-report.json"
        report = json.loads(report_path.read_text())
        del report["counts"]["unchanged_accepted_occurrences"]
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
    return source, candidate, identity_for(source, candidate)


def identity_for(
    source: Path,
    candidate: Path,
    *,
    review_entries: int = 4,
    accepted_changed: int = 2,
    accepted_unchanged: int = 1,
    model_fallback: int = 1,
    parser_unsupported: int = 1,
    deferred: int = 2,
    skipped_files: int = 0,
) -> ReviewIdentity:
    source_files = _snapshot(source)
    candidate_files = _snapshot(candidate)
    report_bytes = (candidate / "translation-report.json").read_bytes()
    return ReviewIdentity(
        source_localisation_sha256=_tree_hash(
            [(item.relative, item.data) for item in source_files]
        ),
        candidate_localisation_sha256=_tree_hash(
            [(item.relative, item.data) for item in candidate_files]
        ),
        candidate_report_sha256=hashlib.sha256(report_bytes).hexdigest(),
        model_tag="synthetic-review:1",
        model_digest="sha256:synthetic-review",
        review_entries=review_entries,
        accepted_changed=accepted_changed,
        accepted_unchanged=accepted_unchanged,
        model_fallback=model_fallback,
        parser_unsupported=parser_unsupported,
        deferred=deferred,
        skipped_files=skipped_files,
    )


def rebind_candidate_report(
    source: Path, candidate: Path, identity: ReviewIdentity
) -> ReviewIdentity:
    report_path = candidate / "translation-report.json"
    report = json.loads(report_path.read_text())
    report["hashes"]["source_localisation_sha256"] = _tree_hash(
        [(item.relative, item.data) for item in _snapshot(source)]
    )
    report["hashes"]["output_localisation_sha256"] = _tree_hash(
        [(item.relative, item.data) for item in _snapshot(candidate)]
    )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    rebound = identity_for(
        source,
        candidate,
        review_entries=identity.review_entries,
        accepted_changed=identity.accepted_changed,
        accepted_unchanged=identity.accepted_unchanged,
        model_fallback=identity.model_fallback,
        parser_unsupported=identity.parser_unsupported,
        deferred=identity.deferred,
        skipped_files=identity.skipped_files,
    )
    return rebound


def extract_pack(output: Path) -> dict[str, object]:
    html = (output / "index.html").read_text()
    encoded = re.search(
        r'<script id="review-data" type="application/octet-stream">([^<]+)</script>',
        html,
    )
    assert encoded is not None
    return json.loads(base64.b64decode(encoded.group(1)))


def extract_runtime(output: Path) -> str:
    html = (output / "index.html").read_text()
    scripts = re.findall(r"<script(?: [^>]*)?>(.*?)</script>", html, re.S)
    assert scripts
    return scripts[-1]


@pytest.mark.parametrize("old_schema", [False, True])
def test_builds_deterministic_review_pack_for_both_v2_count_schemas(
    tmp_path: Path, old_schema: bool
) -> None:
    source, candidate, identity = make_review_inputs(
        tmp_path, old_schema=old_schema
    )
    first_output = tmp_path / "review-one"
    second_output = tmp_path / "review-two"

    first = build_review_pack(
        source, candidate, first_output, expected_identity=identity
    )
    second = build_review_pack(
        source, candidate, second_output, expected_identity=identity
    )
    first_pack = extract_pack(first_output)
    second_pack = extract_pack(second_output)

    assert first["counts"] == {
        "review_entries": 4,
        "accepted_changed": 2,
        "accepted_unchanged": 1,
        "model_fallback": 1,
        "parser_unsupported": 1,
        "deferred": 2,
        "skipped_files": 0,
    }
    assert first["pack_fingerprint"] == second["pack_fingerprint"]
    assert set(first_pack) == {
        "schema_version",
        "pack_fingerprint",
        "summary",
        "entries",
    }
    assert first_pack["schema_version"] == 1
    assert all("warnings" not in entry for entry in first_pack["entries"])
    assert [entry["id"] for entry in first_pack["entries"]] == [
        entry["id"] for entry in second_pack["entries"]
    ]
    duplicate_entries = [
        entry
        for entry in first_pack["entries"]
        if entry["path"].endswith("first_l_english.yml")
    ]
    assert len(duplicate_entries) == 2
    assert duplicate_entries[0]["id"] != duplicate_entries[1]["id"]
    assert {entry["status"] for entry in first_pack["entries"]} == {
        "accepted_changed",
        "accepted_unchanged",
        "model_fallback",
    }


def test_bom_header_alignment_is_preserved(tmp_path: Path) -> None:
    source, candidate, identity = make_review_inputs(tmp_path, bom=True)
    result = build_review_pack(
        source,
        candidate,
        tmp_path / "review",
        expected_identity=identity,
    )
    assert result["counts"]["review_entries"] == 4


@pytest.mark.parametrize(
    ("target", "error"),
    [
        ("source", "source_localisation_identity_mismatch"),
        ("candidate", "candidate_localisation_identity_mismatch"),
        ("report", "candidate_report_identity_mismatch"),
    ],
)
def test_pinned_source_candidate_and_report_hash_mismatch_fail_closed(
    tmp_path: Path, target: str, error: str
) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    if target == "source":
        path = source / "localisation/english/first_l_english.yml"
        path.write_bytes(path.read_bytes() + b"# drift\n")
    elif target == "candidate":
        path = candidate / "localisation/russian/first_l_russian.yml"
        path.write_bytes(path.read_bytes() + b"# drift\n")
    else:
        path = candidate / "translation-report.json"
        path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(SafetyError, match=error):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            expected_identity=identity,
        )


@pytest.mark.parametrize("hash_name", ["source", "candidate"])
def test_report_internal_hash_mismatch_is_rejected(
    tmp_path: Path, hash_name: str
) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    report_path = candidate / "translation-report.json"
    report = json.loads(report_path.read_text())
    report["hashes"][
        "source_localisation_sha256"
        if hash_name == "source"
        else "output_localisation_sha256"
    ] = "0" * 64
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    identity = replace(
        identity,
        candidate_report_sha256=hashlib.sha256(
            report_path.read_bytes()
        ).hexdigest(),
    )

    with pytest.raises(SafetyError, match=f"report_{hash_name}_hash_mismatch"):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            expected_identity=identity,
        )


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_missing_or_extra_candidate_file_is_rejected(
    tmp_path: Path, change: str
) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    if change == "missing":
        (
            candidate / "localisation/russian/second_l_russian.yml"
        ).unlink()
    else:
        (
            candidate / "localisation/russian/extra_l_russian.yml"
        ).write_bytes(b'l_russian:\n extra:0 "synthetic"\n')
    identity = rebind_candidate_report(source, candidate, identity)

    with pytest.raises(
        SafetyError,
        match=(
            "missing_candidate_file"
            if change == "missing"
            else "extra_candidate_file"
        ),
    ):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            expected_identity=identity,
        )


def test_line_alignment_mismatch_is_rejected(tmp_path: Path) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    path = candidate / "localisation/russian/first_l_russian.yml"
    path.write_bytes(path.read_bytes().replace(b" duplicate.key:0", b"  duplicate.key:0", 1))
    identity = rebind_candidate_report(source, candidate, identity)

    with pytest.raises(SafetyError, match="occurrence_alignment"):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            expected_identity=identity,
        )


def test_protected_atom_and_escape_mismatch_is_rejected(tmp_path: Path) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    path = candidate / "localisation/russian/first_l_russian.yml"
    path.write_bytes(path.read_bytes().replace(b"$NAME$", b"$OTHER$", 1))
    identity = rebind_candidate_report(source, candidate, identity)

    with pytest.raises(SafetyError, match="protected_atom_or_escape_mismatch"):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            expected_identity=identity,
        )


def test_placeholder_residue_is_rejected(tmp_path: Path) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    path = candidate / "localisation/russian/first_l_russian.yml"
    path.write_bytes(
        path.read_bytes().replace(
            b"RU CHANGE_SENTINEL", b"RU __SMT_RESIDUE__ CHANGE_SENTINEL", 1
        )
    )
    identity = rebind_candidate_report(source, candidate, identity)

    with pytest.raises(SafetyError, match="candidate_placeholder_residue"):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            expected_identity=identity,
        )


def test_output_overlap_and_no_clobber_are_rejected(tmp_path: Path) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    for output in (source / "review", candidate / "review"):
        with pytest.raises(SafetyError, match="output_overlap"):
            build_review_pack(
                source, candidate, output, expected_identity=identity
            )
    existing = tmp_path / "existing"
    existing.mkdir()
    marker = existing / "marker"
    marker.write_text("preserve")
    with pytest.raises(SafetyError, match="output_must_not_exist"):
        build_review_pack(
            source, candidate, existing, expected_identity=identity
        )
    assert marker.read_text() == "preserve"


def test_non_regular_candidate_report_fails_without_blocking(
    tmp_path: Path,
) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    report = candidate / "translation-report.json"
    report.unlink()
    os.mkfifo(report)

    with pytest.raises(SafetyError, match="not_regular_file"):
        build_review_pack(
            source,
            candidate,
            tmp_path / "review",
            expected_identity=identity,
        )


@pytest.mark.parametrize("drift_target", ["source", "candidate"])
def test_source_or_candidate_generation_drift_prevents_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift_target: str,
) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    output = tmp_path / "review"
    real_render = review._render_review_html

    def drift(pack_data: dict[str, object]) -> bytes:
        rendered = real_render(pack_data)
        if drift_target == "source":
            path = source / "localisation/english/first_l_english.yml"
        else:
            path = candidate / "localisation/russian/first_l_russian.yml"
        path.write_bytes(path.read_bytes() + b"# generation drift\n")
        return rendered

    monkeypatch.setattr(review, "_render_review_html", drift)
    with pytest.raises(SafetyError, match="generation_changed"):
        build_review_pack(
            source, candidate, output, expected_identity=identity
        )
    assert not output.exists()
    assert list(tmp_path.glob(".review.tmp-*")) == []


def test_publication_race_preserves_existing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    output = tmp_path / "review"
    real_publish = review.atomic_publish_directory_no_replace

    def race(source_path: Path, destination: Path) -> None:
        destination.mkdir()
        (destination / "marker").write_text("preserve")
        real_publish(source_path, destination)

    monkeypatch.setattr(review, "atomic_publish_directory_no_replace", race)
    with pytest.raises(SafetyError, match="output_appeared_before_publication"):
        build_review_pack(
            source, candidate, output, expected_identity=identity
        )
    assert (output / "marker").read_text() == "preserve"
    assert list(tmp_path.glob(".review.tmp-*")) == []


def test_html_is_base64_embedded_csp_offline_and_contains_review_only_data(
    tmp_path: Path,
) -> None:
    source, candidate, identity = make_review_inputs(
        tmp_path, hostile_text=True
    )
    output = tmp_path / "review"
    build_review_pack(
        source, candidate, output, expected_identity=identity
    )
    html = (output / "index.html").read_text()
    pack = extract_pack(output)
    decoded_pack = json.dumps(pack, ensure_ascii=False)

    assert "</script><script>synthetic_unicode_Ж" not in html
    assert "</script><script>synthetic_unicode_Ж" in decoded_pack
    assert "DEFERRED_RAW_ONE" not in decoded_pack
    assert "DEFERRED_RAW_TWO" not in decoded_pack
    assert "DEFERRED_UNSUPPORTED_RAW" not in decoded_pack
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
    assert json.loads(
        (output / "review-pack-summary.json").read_text()
    )["network_dependencies"] == 0


def test_javascript_export_uses_real_lf_and_round_trips_through_import(
    tmp_path: Path,
) -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for the JavaScript regression"
    source, candidate, identity = make_review_inputs(tmp_path)
    output = tmp_path / "review"
    build_review_pack(
        source, candidate, output, expected_identity=identity
    )
    runtime = tmp_path / "review-runtime.js"
    harness = tmp_path / "review-runtime-harness.cjs"
    exported = tmp_path / "decisions.json"
    runtime.write_text(extract_runtime(output))
    harness.write_text(
        r"""
const fs = require("fs");
const vm = require("vm");
if (typeof Blob === "undefined") {
  globalThis.Blob = require("buffer").Blob;
}
if (typeof atob === "undefined") {
  globalThis.atob = value => Buffer.from(value, "base64").toString("binary");
}
if (typeof TextDecoder === "undefined") {
  globalThis.TextDecoder = require("util").TextDecoder;
}
class StubElement {
  constructor(tagName = "div", id = "") {
    this.tagName = tagName.toUpperCase();
    this.id = id;
    this.children = [];
    this.listeners = new Map();
    this.className = "";
    this.textContent = "";
    this.value = "";
    this.checked = false;
    this.files = [];
    this.style = {};
    this.classList = {toggle() {}};
  }
  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }
  append(...children) {
    this.children.push(...children);
  }
  replaceChildren(...children) {
    this.children = children;
  }
  setAttribute() {}
  querySelectorAll(selector) {
    const matches = [];
    const visit = node => {
      if (!(node instanceof StubElement)) return;
      if (selector === "input" && node.tagName === "INPUT") matches.push(node);
      if (
        selector === "input:checked"
        && node.tagName === "INPUT"
        && node.checked
      ) {
        matches.push(node);
      }
      node.children.forEach(visit);
    };
    this.children.forEach(visit);
    return matches;
  }
  async fire(type, event = {}) {
    for (const listener of this.listeners.get(type) || []) {
      await listener(event);
    }
  }
  click() {
    if (this.tagName === "A") {
      globalThis.downloadCount = (globalThis.downloadCount || 0) + 1;
    }
    return this.fire("click", {target: this});
  }
}
const ids = [
  "review-data", "fingerprint", "progressText", "progressBar", "search",
  "fileFilter", "statusFilter", "decisionFilter", "entryList", "empty",
  "review", "path", "line", "status", "sourceText", "candidateText",
  "atoms", "decision", "editorField", "editor", "note", "tags",
  "glossary", "previous", "next", "export", "importButton", "clear",
  "importFile", "error"
];
const elements = new Map(ids.map(id => [id, new StubElement("div", id)]));
elements.get("review-data").textContent = fs.readFileSync(
  process.argv[2] + ".pack-data",
  "utf8"
);
globalThis.document = {
  getElementById(id) {
    return elements.get(id);
  },
  createElement(tagName) {
    return new StubElement(tagName);
  },
  createTextNode(text) {
    return {textContent: text};
  }
};
globalThis.localStorage = {
  values: new Map(),
  getItem(key) { return this.values.has(key) ? this.values.get(key) : null; },
  setItem(key, value) { this.values.set(key, value); },
  removeItem(key) { this.values.delete(key); }
};
globalThis.confirm = () => true;
globalThis.URL = {
  createObjectURL(blob) {
    globalThis.capturedBlob = blob;
    return "blob:synthetic";
  },
  revokeObjectURL() {}
};
vm.runInThisContext(fs.readFileSync(process.argv[2], "utf8"));
vm.runInThisContext(`
  var editRecordForTest = pack.entries.find(
    record => record.protected_atoms.length > 0
  );
  var acceptRecordForTest = pack.entries.find(
    record => record.id !== editRecordForTest.id
  );
  var acceptItemForTest = defaults(acceptRecordForTest);
  acceptItemForTest.decision = "accept";
  state.set(acceptRecordForTest.id, acceptItemForTest);
  var editItemForTest = defaults(editRecordForTest);
  editItemForTest.decision = "edit";
  editItemForTest.edited_segments[0] = "Отредактировано ";
  editItemForTest.note = "Синтетический комментарий";
  editItemForTest.tags = ["style", "terminology"];
  state.set(editRecordForTest.id, editItemForTest);
  save();
  currentId = editRecordForTest.id;
  render();
`);
(async () => {
  const invalidValues = [
    'нельзя "кавычку',
    "нельзя\nстроку",
    "нельзя\\слеш",
    "нельзя $OTHER$",
    "нельзя \ud800"
  ];
  const invalidResults = [];
  const safeSegment = "Отредактировано 😀 ";
  for (let index = 0; index < invalidValues.length; index++) {
    const before = localStorage.getItem(storageKey);
    let area = elements.get("editor").children.find(
      child => child.tagName === "TEXTAREA"
    );
    area.value = invalidValues[index];
    globalThis.capturedBlob = undefined;
    globalThis.downloadCount = 0;
    await area.fire("input", {target: area});
    const inputError = elements.get("error").textContent;
    render();
    const renderError = elements.get("error").textContent;
    area = elements.get("editor").children.find(
      child => child.tagName === "TEXTAREA"
    );
    await elements.get("export").fire(
      "click",
      {target: elements.get("export")}
    );
    invalidResults.push({
      storage_unchanged: localStorage.getItem(storageKey) === before,
      draft_visible: area.value === invalidValues[index],
      render_preserved_error: inputError !== "" && renderError === inputError,
      export_blocked: globalThis.capturedBlob === undefined
        && globalThis.downloadCount === 0,
      export_error_visible: elements.get("error").textContent.startsWith(
        "Экспорт отклонён:"
      )
    });
    if (index + 1 < invalidValues.length) {
      area.value = safeSegment;
      await area.fire("input", {target: area});
      render();
    }
  }
  const persistedBeforeReload = localStorage.getItem(storageKey);
  state = validateDocument(JSON.parse(persistedBeforeReload));
  drafts.clear();
  render();
  const restoredArea = elements.get("editor").children.find(
    child => child.tagName === "TEXTAREA"
  );
  const restoredEdit = state.get(editRecordForTest.id);
  const restoredAccept = state.get(acceptRecordForTest.id);
  const restored = {
    accept: restoredAccept.decision,
    edit: restoredEdit.decision,
    edited_segment: restoredArea.value,
    note: restoredEdit.note,
    tags: restoredEdit.tags.slice().sort()
  };
  const boolDocument = exportDocument();
  boolDocument.schema_version = true;
  let booleanSchemaRejected = false;
  try {
    validateDocument(boolDocument);
  } catch (error) {
    booleanSchemaRejected = error.message === "invalid decisions schema";
  }
  globalThis.capturedBlob = undefined;
  globalThis.downloadCount = 0;
  await elements.get("export").fire("click", {target: elements.get("export")});
  const bytes = Buffer.from(await globalThis.capturedBlob.arrayBuffer());
  fs.writeFileSync(process.argv[3], bytes);
  const documentValue = JSON.parse(bytes.toString("utf8"));
  vm.runInThisContext("state = validateDocument(" + JSON.stringify(documentValue) + ")");
  const roundTrip = vm.runInThisContext(`(() => {
    const roundTripAccept = state.get(acceptRecordForTest.id);
    const roundTripEdit = state.get(editRecordForTest.id);
    const roundTrip = exportDocument();
    const editDecision = roundTrip.decisions.find(
      item => item.occurrence_id === editRecordForTest.id
    );
    return {
      accept: roundTripAccept.decision,
      edit: roundTripEdit.decision,
      edited_translation: editDecision.edited_translation,
      expected_translation: fullTranslation(editRecordForTest, roundTripEdit),
      note: roundTripEdit.note,
      tags: roundTripEdit.tags.slice().sort()
    };
  })()`);
  process.stdout.write(JSON.stringify({
    invalidResults,
    restored,
    booleanSchemaRejected,
    downloadCount: globalThis.downloadCount,
    roundTrip
  }));
})().catch(error => {
  process.stderr.write(String(error.stack || error));
  process.exitCode = 1;
});
""".strip()
        + "\n"
    )
    pack = extract_pack(output)
    encoded = base64.b64encode(
        json.dumps(
            pack,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).decode()
    (tmp_path / "review-runtime.js.pack-data").write_text(encoded)

    completed = subprocess.run(
        [node, str(harness), str(runtime), str(exported)],
        check=True,
        capture_output=True,
        text=True,
    )
    exported_bytes = exported.read_bytes()
    exported_document = json.loads(exported_bytes)
    restored = json.loads(completed.stdout)

    assert exported_bytes.endswith(b"\n")
    assert not exported_bytes.endswith(b"\\n")
    assert exported_document["schema_version"] == 1
    assert all(
        result
        == {
            "storage_unchanged": True,
            "draft_visible": True,
            "render_preserved_error": True,
            "export_blocked": True,
            "export_error_visible": True,
        }
        for result in restored["invalidResults"]
    )
    assert restored["restored"] == {
        "accept": "accept",
        "edit": "edit",
        "edited_segment": "Отредактировано 😀 ",
        "note": "Синтетический комментарий",
        "tags": ["style", "terminology"],
    }
    assert restored["booleanSchemaRejected"] is True
    assert restored["downloadCount"] == 1
    assert restored["roundTrip"] == {
        "accept": "accept",
        "edit": "edit",
        "edited_translation": restored["roundTrip"]["expected_translation"],
        "expected_translation": restored["roundTrip"]["expected_translation"],
        "note": "Синтетический комментарий",
        "tags": ["style", "terminology"],
    }


def test_review_json_limits_have_one_python_authority_and_exact_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert review.MAX_REVIEW_PACK_JSON_BYTES == 32 * 1024 * 1024
    assert review.MAX_DECISIONS_BYTES == 32 * 1024 * 1024
    pack = {
        "schema_version": review.FULL_REVIEW_PACK_SCHEMA_VERSION,
        "pack_fingerprint": "a" * 64,
        "entry_order_sha256": "b" * 64,
        "summary": {},
        "entries": [],
    }
    exact_size = len(review._canonical_json(pack).encode("utf-8"))
    monkeypatch.setattr(review, "MAX_REVIEW_PACK_JSON_BYTES", exact_size)
    html = review._render_review_html(pack).decode("utf-8")
    assert f"const MAX_REVIEW_PACK_JSON_BYTES={exact_size};" in html
    assert (
        f"const MAX_DECISIONS_BYTES={32 * 1024 * 1024};" in html
    )

    monkeypatch.setattr(
        review,
        "MAX_REVIEW_PACK_JSON_BYTES",
        exact_size - 1,
    )
    with pytest.raises(SafetyError, match="review_pack_json_too_large"):
        review._render_review_html(pack)


def valid_decisions(pack: dict[str, object]) -> dict[str, object]:
    record = pack["entries"][0]
    return {
        "schema_version": 1,
        "pack_fingerprint": pack["pack_fingerprint"],
        "decisions": [
            {
                "occurrence_id": record["id"],
                "decision": "accept",
                "note": "",
                "tags": [],
                "glossary_candidate": False,
                "source_span_sha256": record["source_span_sha256"],
                "candidate_span_sha256": record[
                    "candidate_span_sha256"
                ],
            }
        ],
    }


def valid_edit_decisions(
    pack: dict[str, object], edited_translation: str
) -> dict[str, object]:
    record = next(
        item for item in pack["entries"] if item["protected_atoms"]
    )
    return {
        "schema_version": 1,
        "pack_fingerprint": pack["pack_fingerprint"],
        "decisions": [
            {
                "occurrence_id": record["id"],
                "decision": "edit",
                "edited_translation": edited_translation,
                "note": "synthetic",
                "tags": ["style"],
                "glossary_candidate": True,
                "source_span_sha256": record["source_span_sha256"],
                "candidate_span_sha256": record[
                    "candidate_span_sha256"
                ],
            }
        ],
    }


@pytest.mark.parametrize(
    ("schema_version", "accepted"),
    [(True, False), (1.0, True)],
)
def test_python_schema_version_matches_javascript_numeric_contract(
    tmp_path: Path, schema_version: object, accepted: bool
) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    output = tmp_path / "review"
    build_review_pack(
        source, candidate, output, expected_identity=identity
    )
    pack = extract_pack(output)
    payload = valid_decisions(pack)
    payload["schema_version"] = schema_version

    if accepted:
        assert validate_decisions_payload(payload, pack)
    else:
        with pytest.raises(SafetyError, match="schema_version"):
            validate_decisions_payload(payload, pack)


@pytest.mark.parametrize(
    "unsafe_segment",
    ['нельзя "кавычку', "нельзя\nстроку", "нельзя\\слеш", "$OTHER$", "\ud800"],
)
def test_python_validator_rejects_unsafe_or_non_scalar_edited_segments(
    tmp_path: Path, unsafe_segment: str
) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    output = tmp_path / "review"
    build_review_pack(
        source, candidate, output, expected_identity=identity
    )
    pack = extract_pack(output)
    record = next(
        item for item in pack["entries"] if item["protected_atoms"]
    )
    payload = valid_edit_decisions(
        pack, unsafe_segment + record["protected_atoms"][0]
    )

    with pytest.raises(SafetyError):
        validate_decisions_payload(payload, pack)


def test_python_validator_accepts_emoji_and_rejects_non_scalar_note(
    tmp_path: Path,
) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    output = tmp_path / "review"
    build_review_pack(
        source, candidate, output, expected_identity=identity
    )
    pack = extract_pack(output)
    record = next(
        item for item in pack["entries"] if item["protected_atoms"]
    )
    payload = valid_edit_decisions(
        pack, "Корректный emoji 😀 " + record["protected_atoms"][0]
    )
    json_round_trip = json.loads(json.dumps(payload, ensure_ascii=True))

    assert validate_decisions_payload(json_round_trip, pack)
    json_round_trip["decisions"][0]["note"] = "\udfff"
    with pytest.raises(SafetyError, match="note_unicode"):
        validate_decisions_payload(json_round_trip, pack)


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("fingerprint", "fingerprint"),
        ("unknown_id", "unknown"),
        ("duplicate_id", "duplicate"),
        ("enum", "enum"),
        ("extra_field", "fields"),
    ],
)
def test_decisions_import_rejects_mismatch_unknown_duplicate_enum_and_extras(
    tmp_path: Path, mutation: str, error: str
) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    output = tmp_path / "review"
    build_review_pack(
        source, candidate, output, expected_identity=identity
    )
    pack = extract_pack(output)
    payload = valid_decisions(pack)
    if mutation == "fingerprint":
        payload["pack_fingerprint"] = "0" * 64
    elif mutation == "unknown_id":
        payload["decisions"][0]["occurrence_id"] = "0" * 64
    elif mutation == "duplicate_id":
        payload["decisions"].append(dict(payload["decisions"][0]))
    elif mutation == "enum":
        payload["decisions"][0]["decision"] = "approve"
    else:
        payload["decisions"][0]["extra"] = True

    with pytest.raises(SafetyError, match=error):
        validate_decisions_payload(payload, pack)


def test_edit_import_preserves_exact_protected_atoms(tmp_path: Path) -> None:
    source, candidate, identity = make_review_inputs(tmp_path)
    output = tmp_path / "review"
    build_review_pack(
        source, candidate, output, expected_identity=identity
    )
    pack = extract_pack(output)
    record = next(
        item for item in pack["entries"] if item["protected_atoms"]
    )
    payload = valid_decisions(pack)
    payload["decisions"][0] = {
        "occurrence_id": record["id"],
        "decision": "edit",
        "edited_translation": (
            "Синтетика "
            + record["protected_atoms"][0]
        ),
        "note": "synthetic",
        "tags": ["style"],
        "glossary_candidate": True,
        "source_span_sha256": record["source_span_sha256"],
        "candidate_span_sha256": record["candidate_span_sha256"],
    }
    assert validate_decisions_payload(payload, pack)
    payload["decisions"][0]["edited_translation"] = "Синтетика $OTHER$"
    with pytest.raises(SafetyError, match="protected"):
        validate_decisions_payload(payload, pack)
