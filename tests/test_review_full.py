from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
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
from stellaris_mod_translator.ollama import OllamaResultError
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
    source_file.write_text("\n".join(lines) + "\n")
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
        (lambda report: report.pop("resumability"), "schema"),
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
                "synthetic-review-cloud:latest",
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


def test_schema_v3_full_pack_scales_to_about_1700_entries(
    tmp_path: Path,
) -> None:
    source, candidate, pin = make_full_review_inputs(
        tmp_path,
        entry_count=1700,
    )
    output = tmp_path / "review"
    result = build_review_pack(
        source,
        candidate,
        output,
        candidate_report_sha256=pin,
    )
    pack = extract_pack(output)
    assert result["counts"]["review_entries"] == 1700
    assert result["counts"]["accepted_changed"] == 1700
    assert len(pack["entries"]) == 1700
    assert (output / "index.html").stat().st_size < 4 * 1024 * 1024


def test_full_ui_sparse_storage_exports_imports_keyboard_and_dom_window(
    tmp_path: Path,
) -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for JavaScript regression"
    source, candidate, pin = make_full_review_inputs(
        tmp_path,
        entry_count=1700,
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
    encoded_pack = base64.b64encode(
        json.dumps(
            extract_pack(output),
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
  "progressBar", "storageWarning", "helpPanel", "closeHelp", "search",
  "attentionFilter", "fileFilter", "statusFilter", "decisionFilter",
  "warningFilter", "resultCount", "pagePrevious", "pageInfo", "pageNext",
  "entryList", "empty", "review", "path", "line", "status", "warnings",
  "acceptWarning", "sourceText", "candidateText", "atoms", "decision",
  "editorField", "editor", "note", "tags", "glossary", "previous", "next",
  "draftExport", "finalExport", "importButton", "helpButton", "clear",
  "importFile", "error"
];
const elements = new Map(ids.map(id => [id, new StubElement("div", id)]));
for (const id of [
  "search", "attentionFilter", "fileFilter", "statusFilter",
  "decisionFilter", "warningFilter", "decision", "note", "glossary",
  "importFile"
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
  fail: false,
  getItem(key) {
    if (this.fail) throw new Error("synthetic quota");
    return this.values.has(key) ? this.values.get(key) : null;
  },
  setItem(key, value) {
    if (this.fail) throw new Error("synthetic quota");
    this.values.set(key, value);
  },
  removeItem(key) {
    if (this.fail) throw new Error("synthetic quota");
    this.values.delete(key);
  }
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
async function fireDocument(type, event) {
  for (const listener of documentListeners.get(type) || []) {
    await listener(event);
  }
}
(async () => {
  const initialRows = elements.get("entryList").children.length;
  await elements.get("pageNext").fire("click");
  const secondPageRows = elements.get("entryList").children.length;
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
  elements.get("importFile").files = [{
    size: finalBytes.length,
    text: async () => finalBytes.toString("utf8")
  }];
  await elements.get("importFile").fire(
    "change", {target: elements.get("importFile")}
  );
  const importedCount = vm.runInThisContext("state.size");
  const beforeInvalidImport = vm.runInThisContext(
    "JSON.stringify(sparseDocument())"
  );
  const invalidDocument = JSON.parse(finalBytes.toString("utf8"));
  invalidDocument.pack_fingerprint = "0".repeat(64);
  const invalidText = JSON.stringify(invalidDocument);
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
  let oversizedRead = false;
  elements.get("importFile").files = [{
    size: 4 * 1024 * 1024 + 1,
    text: async () => { oversizedRead = true; return "{}"; }
  }];
  await elements.get("importFile").fire(
    "change", {target: elements.get("importFile")}
  );
  vm.runInThisContext("state=new Map();drafts.clear();currentId=pack.entries[0].id;pageIndex=0;render()");
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
    textWasDebounced,
    sparseAfterBlurChanges: sparseAfterBlur.changes.length,
    sparseAfterDecisionChanges: sparseAfterDecision.changes.length,
    reloadDecision,
    memorySurvivedStorageFailure,
    storageWarningVisible,
    draftDecisionCount: draftDocument.decisions.length,
    draftExactlyOneLf,
    incompleteFinalDisabled,
    finalEnabled,
    finalDecisionCount: finalDocument.decisions.length,
    finalExactlyOneLf: finalBytes.at(-1) === 10 && finalBytes.at(-2) !== 10,
    importedCount,
    atomicInvalidImport,
    oversizedRead,
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
        "textWasDebounced": True,
        "sparseAfterBlurChanges": 1,
        "sparseAfterDecisionChanges": 1,
        "reloadDecision": "accept",
        "memorySurvivedStorageFailure": True,
        "storageWarningVisible": True,
        "draftDecisionCount": 1700,
        "draftExactlyOneLf": True,
        "incompleteFinalDisabled": True,
        "finalEnabled": True,
        "finalDecisionCount": 1700,
        "finalExactlyOneLf": True,
        "importedCount": 1700,
        "atomicInvalidImport": True,
        "oversizedRead": False,
        "keyboardAcceptedAndAdvanced": True,
        "focusedKeyExcluded": True,
        "noEndWrap": True,
        "noStartWrap": True,
        "searchFocused": True,
    }
