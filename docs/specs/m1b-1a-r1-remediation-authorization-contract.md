# M1B-1A-R1-AUTH — transport and evidence-provenance remediation authorization

```text
Milestone: M1B-1A-R1-AUTH — authorization only
Разрешённый слой: bounded future remediation of the existing draft PR #10
Рекомендуемая модель Codex: GPT-5.6 Sol
Уровень рассуждения: Ultra
Входные evidence: exact origin/main, PR #10 metadata/tree, accepted M1B-1A0 v4 and M1B-1A1-AUTH bytes
Результаты: closed scope, owner authorization, owner signoff, minimal status links, sanitized ignored evidence
Обязательные проверки: canonical/hash/path/order/link/diff/parity validation without candidate execution
Условия остановки: any PR #10, base, worktree, identity, path, schema, or effect mismatch
Вне scope: remediation implementation, candidate execution, provider/model/corpus access, envelope instances, acceptance, admission, benchmark, M2
```

- Scope schema: `m1b-1a-r1-remediation-scope-v1`
- Scope generation: `1`
- Owner record: `m1b-1a-r1-remediation-owner-authorization-v1`
- Operational review state: `M1B-1A-R1-AUTH: READY_FOR_OWNER_REVIEW`
- Effect: `after_review_and_merge_to_main`
- Pre-effect PR #10 state: `CHANGES_REQUIRED_UNCHANGED`
- New repository code execution: `NOT_AUTHORIZED`
- Executable TCB admission: `NOT_GRANTED`

## 1. Decision boundary

This contract authorizes no remediation in its own PR. It records only an
owner-controlled, default-deny scope for a later update of the already existing
draft [PR #10](https://github.com/elenandar/Stellaris-mod-translator/pull/10).
The authorization PR creates four normative authorization artifacts, two
minimal status/link updates, and one sanitized ignored evidence file. It does
not modify any candidate, M1B-1A0 verifier, test, fixture, v4 contract, or
accepted historical artifact.

The machine owner record uses `acceptance_state=owner_accepted` only for this
exact delegated remediation scope. That value does not activate the scope.
Operational authority remains absent until the owner has reviewed and merged
the exact authorization bytes into `main`. Commit, push, draft-PR creation, or
merge without owner review cannot independently activate the effect.

Repository bytes cannot self-assert their own future PR number, final head, or
owner review. Therefore a separate pre-effect, read-only activation-verification
plane binds the fixed authorization branch and base to exactly one GitHub PR,
then requires the external owner-controlled merge event and the exact
two-parent merge provenance. This external witness is not a future
implementation identity and cannot be constructed by the scope or owner-record
bytes.

After effect, the scope allows one bounded remediation of the same draft PR
#10. It does not authorize a new remediation branch or PR, candidate execution,
functional testing, provider execution, executable acceptance, or admission.

## 2. Normative scope identity

The authoritative machine scope is
[`registry/m1b/m1b-1a-r1-remediation-scope-v1.json`](../../registry/m1b/m1b-1a-r1-remediation-scope-v1.json).
It is compact sorted-key ASCII JSON plus one LF and contains no self-hash.

| Field | Exact value |
|---|---|
| Schema / generation | `m1b-1a-r1-remediation-scope-v1` / `1` |
| Canonical bytes | `27399` |
| Raw SHA-256 | `86741260ac3b6338d4d8df5855a9d34e6ae4007d8d0aaa671b22b2e5a481742b` |
| Framing domain | `stellaris-m1b-1a-r1-remediation-scope-v1` |
| Framed SHA-256 | `26121585897212dd54732a29245858cc856a334d6b421a946273f0f2708bb74b` |

The framed digest is:

```text
SHA-256(
  ASCII("stellaris-m1b-1a-r1-remediation-scope-v1") ||
  NUL ||
  u64be(canonical_scope_length) ||
  canonical_scope_bytes
)
```

The separate owner record binds both digests and length. The scope binds the
four post-merge authorization paths by exact reviewed merge provenance. This
avoids circular self-hash and prevents an unreviewed replacement artifact from
activating the effect.

The authorization PR provenance is closed without a post-publication
self-update: its head branch is
`agent/m1b-1a-r1-transport-provenance-auth`, its creation base is exact
`1f10c151c5adac5fbf765af8093c7eddf8cf0429`, and external merged-PR metadata
supplies its number and final head. Effect requires one ordinary two-parent
merge reachable from `origin/main`; its second parent must equal that final
head. Both the PR final-head delta and the base-to-main-merge delta must contain
exactly the six authorization-stage tracked outputs, and the merge tree must
contain the exact four authorization artifacts. This prevents unrelated
`main` content from being imported into PR #10. Its first parent must equal
exact `1f10c151c5adac5fbf765af8093c7eddf8cf0429`; a merely descendant
first parent cannot activate the effect. Squash, rebase, repository
self-attestation, or branch-name-only provenance cannot activate the effect.

## 3. Exact preflight and immutable remediation target

Authorization preflight was required to stop before writes unless all of the
following matched after one `fetch`:

- `origin/main=1f10c151c5adac5fbf765af8093c7eddf8cf0429`;
- PR #10 is `OPEN / DRAFT`, auto-merge absent;
- head branch
  `agent/m1b-1a1-inert-candidate-construction`;
- head commit
  `66f905cf266b9d1c1f56d0d706184387ffedb36e`;
- base commit
  `1f10c151c5adac5fbf765af8093c7eddf8cf0429`;
- tracked worktree and index are clean.

The exact PR #10 tree contains these `11` paths:

| Path | Bytes | Mode | Raw SHA-256 |
|---|---:|---:|---|
| `README.md` | `17498` | `100644` | `ed84521741e2e8f15f2cece9b086086aed88343601f9a3d16ccc37439f6d9369` |
| `docs/decisions/M1B-1A1-candidate-review.md` | `12304` | `100644` | `36fcabf9888f9516618661654061a691daafa533d307ef4b9c2aedfd1b1a7323` |
| `docs/roadmap.md` | `18504` | `100644` | `974b927cc5dbcc9626a57670c8471462286b315f6bc81311c0424643b6c17b90` |
| `fixtures/m1b/candidate-construction/README.md` | `4180` | `100644` | `6ef0beed6c4d7c8fe4a7b445fbadc2050bd6e0115c111edb789330de6a5f1c63` |
| `fixtures/m1b/candidate-construction/cases.json` | `22394` | `100644` | `a7f13de146722edf6af167ce63b7c33bf650fad3ab66339e73d902b047859ec7` |
| `registry/m1b/m1b-1a1-proposed-executable-manifest-v1.json` | `814` | `100644` | `3d2daab0211fb7a4e3e40cdcdb0fddeb6087b1fb0e640f1e2925557ff8ec48cd` |
| `tools/research/README.md` | `10155` | `100644` | `e62d2c16ec1f85b61526551ae6f57bdc44021c8cd03d75a1776edc21386ca2e0` |
| `tools/research/m1b_1a1_candidate/analysis_engine.py` | `22743` | `100644` | `a88c80415cb481beb25c7e18881bc863bef8196c85a95926d9fc5cdf64e67f92` |
| `tools/research/m1b_1a1_candidate/contract_validator.py` | `62538` | `100644` | `51f0d00b068f27687b90094123c0991d009a6afd019fcc8d856517fc882748f1` |
| `tools/research/m1b_1a1_candidate/provider_request_harness.py` | `187` | `100644` | `b2a18e2d54fe2273981263586234fe64b57eec24ff2c6fc20b2b617c22774174` |
| `tools/research/m1b_1a1_candidate/synthetic_fixture_materializer.py` | `9005` | `100644` | `ffc07a0e32f120cf38d4f41c2c6550837cec3d39dd53c3037596fa32207dfbd5` |

The four candidate sources total `94473` bytes. Their exact role/path/hash rows
are repeated in the machine scope. Candidate source was read only as raw bytes
for SHA/size and line-oriented static review. It was not parsed, tokenized,
linted, compiled, imported, or executed.

The proposed manifest identity bound to that tree is:

| Field | Exact value |
|---|---|
| Schema / implementation generation | `m1b-executable-implementation-manifest-v1` / `1` |
| Canonical bytes | `814` |
| Raw SHA-256 | `3d2daab0211fb7a4e3e40cdcdb0fddeb6087b1fb0e640f1e2925557ff8ec48cd` |
| Framing domain | `stellaris-m1b-executable-manifest-v1` |
| Framed SHA-256 | `38c710987da74369d26883cfa33a7587a98746f1eb7129716a5d8315a23cd391` |
| Source linkage | `4/4` |

The inert candidate fixture is canonical
`m1b-1a1-candidate-construction-cases-v1`, `22394` bytes, `42` cases, raw
SHA-256
`a7f13de146722edf6af167ce63b7c33bf650fad3ab66339e73d902b047859ec7`.
These are read-only pre-remediation identities, not accepted executable
identities.

## 4. Why bounded remediation is required

Independent raw-text review of the exact PR #10 bytes found four gate-critical
classes that justify remediation authority:

1. The entrypoint consumes ambient `sys.stdin` and writes ambient
   `sys.stdout`; it does not bind one authorized request pipe or a separate
   private result-retention channel. A nominal provider result discards the
   private translated text while exposing only public-looking metadata.
2. Raw/direct/synthetic diagnostic vectors share analysis paths that can emit
   decision-looking PASS labels without explicit scope, split, eligibility, or
   non-caller-constructible full-decision admission.
3. Provider/model JSON supplies accounting, findings, gates, D1 technical
   conformance, and D2–D5 human-looking statuses. Shape agreement is not
   evidence provenance.
4. Post-dispatch failures collapse into the same zero-count top-level error as
   pre-dispatch rejection, so assigned denominators and terminal failure
   accounting are not preserved.

These findings authorize only versioned static remediation. They are not
runtime observations, provider results, private-corpus evidence, or an
acceptance decision.

## 5. Effect and bounded Git/GitHub control plane

Before effect, only the activation-verification plane may fetch exact repository
refs and read Git/GitHub metadata, ancestry, commit/tree metadata, and the four
authorization artifacts from the prospective merge tree. It permits no
GitHub or repository-worktree/content mutation. The only local mutation is the
narrow Git-internal object and remote-ref consequence of that exact `origin`
fetch. It must prove the fixed branch/base, external owner-controlled merged PR
event, final-head binding, and exact ordinary main authorization merge described
above.

After effect, a future remediation must fail closed unless PR #10 is still
exactly `OPEN / DRAFT` on the bound branch and exact pre-remediation head
`66f905cf…`, with clean index and tracked worktree already checked out at that
exact branch/head. No switch, checkout, tracking setup, or worktree
materialization is authorized by this scope. It must then:

1. identify the exact reviewed **main authorization PR merge commit** proven by
   the activation-verification plane;
2. create at most one ordinary **PR #10 integration merge commit** whose first
   parent is exact `66f905cf266b9d1c1f56d0d706184387ffedb36e` and whose
   second parent is the exact main authorization PR merge commit;
3. resolve/write only the exact future-output allowlist;
4. create at most one ordinary remediation commit;
5. perform at most one non-force push of the existing PR #10 branch;
6. update only the title/body of that same draft PR #10.

The integration merge may materialize the four exact authorization artifacts
only as immutable merge consequences. They are not remediation outputs, cannot
be independently edited or staged, and must remain byte-identical to the
reviewed main authorization merge tree.

The scope permits no new remediation branch or PR. It forbids stash, clean,
reset, amend, published-branch rebase, force-push, main mutation, PR #10 merge,
auto-merge, ready-for-review, close, tag/release/Actions changes, other PR
mutation, or network outside exact Git/GitHub repository operations.

PR #10 remains unchanged in this authorization task:
`PR10: CHANGES_REQUIRED_UNCHANGED`.

## 6. Closed repository content plane

The repository content plane is default-deny. After effect, semantic reads are
limited to:

- `22` exact SHA-bound historical/read-only inputs in the scope;
- the exact `11` PR #10 target bytes above;
- the four exact reviewed post-merge authorization artifacts;
- static readback of exact future outputs.

Candidate source reads remain raw-byte SHA and line-oriented static-text only.
Metadata reads are limited to exact scope paths and lexical parent closure.
Unlisted reads and writes are denied.

The only future directories that may be created if absent are these exact real
directories:

| Path | Mode | Required parent |
|---|---:|---|
| `artifacts/m1b` | `0700` | pre-existing real `artifacts` |
| `artifacts/m1b/m1b-1a-r1` | `0700` | authorized predecessor or pre-existing real `artifacts/m1b` |
| `fixtures/m1b/tcb-admission-v5` | `0755` | pre-existing real `fixtures/m1b` |

Symlink, replacement, deletion, recursive ambient parent creation, or any other
directory creation is forbidden.

The future file allowlist contains exactly `19` paths: `18` tracked and one
ignored sanitized evidence file.

| Path | Tracked | Write kind |
|---|---:|---|
| `README.md` | `true` | status/link only |
| `artifacts/m1b/m1b-1a-r1/remediation-evidence.json` | `false` | sanitized ignored evidence |
| `docs/decisions/M1B-1A-R1-remediation-review.md` | `true` | remediation review |
| `docs/decisions/M1B-1A0-contract-v5-review.md` | `true` | contract-v5 review |
| `docs/decisions/M1B-1A1-candidate-review.md` | `true` | candidate review remediation |
| `docs/roadmap.md` | `true` | status/link only |
| `docs/specs/m1b-offline-executable-tcb-admission-contract-v5.md` | `true` | versioned v5 specification |
| `fixtures/m1b/candidate-construction/README.md` | `true` | candidate fixture documentation remediation |
| `fixtures/m1b/candidate-construction/cases.json` | `true` | inert candidate fixture remediation |
| `fixtures/m1b/tcb-admission-v5/cases.json` | `true` | versioned contract-v5 inert TCB fixture |
| `registry/m1b/m1b-1a1-proposed-executable-manifest-v1.json` | `true` | proposed manifest generation 2 |
| `registry/m1b/offline-executable-tcb-contract-v5.json` | `true` | versioned machine contract v5 |
| `tools/research/README.md` | `true` | status/link only |
| `tools/research/m1b_1a1_candidate/analysis_engine.py` | `true` | candidate source remediation |
| `tools/research/m1b_1a1_candidate/contract_validator.py` | `true` | candidate source remediation |
| `tools/research/m1b_1a1_candidate/provider_request_harness.py` | `true` | candidate source remediation |
| `tools/research/m1b_1a1_candidate/synthetic_fixture_materializer.py` | `true` | candidate source remediation |
| `tools/research/m1b_tcb_contract_v5.py` | `true` | versioned verifier-v5 inert source |
| `tools/research/tests/test_m1b_tcb_contract_v5.py` | `true` | versioned verifier-v5 test inert source |

Only `tracked=true` paths may be staged. The ignored evidence must never be
force-added. `README.md`, `docs/roadmap.md`, and
`tools/research/README.md` may change only status and links.

The historical unversioned fixture already uses
`fixture_schema=m1b-tcb-admission-cases-v5`. The new contract-v5 fixture is
therefore isolated at `fixtures/m1b/tcb-admission-v5/cases.json` and must use
the non-colliding schema
`m1b-tcb-admission-contract-v5-cases-v1`. This preserves the requested
versioned TCB fixture v5 while preventing silent reuse or mutation of the
historical fixture identity.

## 7. Required v5 request/result transport semantics

The future v5 normative generation must replace `stdin=devnull` with one
explicit bounded anonymous request pipe:

- maximum request bytes: `4194304` (`4 MiB`);
- exactly one request;
- writer closure is mandatory;
- no ambient argv input, environment input, cwd discovery, or repository input
  file;
- request validity before dispatch is distinct from failure after an accepted
  assignment.

It must define a separate bounded anonymous private-result pipe. The exact v5
bound must be explicit and no greater than `4194304` bytes. The translated
private result is non-public and may not enter Git, PR text, tracked or ignored
evidence, logs, screenshots, or public outcomes. It is retained locally for
later human review, or the assigned request ends in one controlled failure.
Discarding the translation while publishing quality or technical success is
forbidden.

Exactly one private result is permitted. The result writer must close, the
reader must read through EOF under the declared bound, and overflow,
truncation, or writer/EOF failure after assignment must produce exactly one
controlled terminal-failure row while preserving the assigned denominator.

This changes invocation semantics and therefore requires new identities:

- contract v5 / generation `5`;
- execution envelope v5 / generation `5`;
- execution plan v4 / generation `4`.

The remediation authors normative schema definitions only. It does not create
an execution-envelope instance, invocation-plan instance, implementation
acceptance, or runtime acceptance. Launcher opened-byte, interpreter, role
import, and actual runtime request/result transport remain unproven until a
separate execution gate.

## 8. Diagnostic-only analysis boundary

Raw, direct, and synthetic vectors are never decision-grade evidence. Their
closed records must state `decision_grade_eligible=false`, an explicit scope,
and an explicit split. Mixed split is rejected. Tuning never becomes holdout.

Decision-looking aggregate PASS is forbidden without a separately bound
full-decision admission that the caller cannot construct or self-assert. The
remediation does not create such an admission. Diagnostic calculations may
still expose clearly qualified intermediate observations, but must not be
projected as an owner, editorial, quality-feasibility, or benchmark verdict.

## 9. Evidence provenance

Provider/model JSON is untrusted candidate content. It cannot assign:

- `technical_conformance`;
- D2–D5 human statuses;
- authoritative findings;
- any gate pass;
- accounting counters;
- latency, memory, or other runtime measurements.

D1 pass is allowed only as a local deterministic comparison of exact expected
and observed technical atoms. If that validator is not implemented, D1 remains
`not_evaluated`. Any critical D1 finding excludes D1 pass and technical
success.

D2–D5 remain `not_evaluated` until separately bound human evidence exists.
Model-provided labels cannot simulate that evidence. Findings, gates,
accounting, and public projections are harness/validator-derived from bound
inputs and evidence, never accepted because the model emitted a matching
shape.

## 10. Failure accounting

Once an assignment is accepted, each timeout, network/HTTP failure, truncation,
malformed JSON, schema error, or provider error must create exactly one
controlled terminal-failure row and remain in the assigned denominator.
Post-assignment failure cannot become a zero-count top-level error.

Pre-dispatch invalid request is a distinct phase and does not create a model
attempt. Failure codes use a closed v5 allowlist. Retry, repair, and fallback
remain forbidden. The harness—not the model—computes
`initial_attempt_count`, `model_call_count`, retry/fallback/repair counts, and
terminal-failure count.

## 11. Identity and historical-byte preservation

If any candidate source changes, all of the following are mandatory:

- `implementation_generation=2`;
- recomputation of all four source SHA-256 values;
- a new canonical and framed proposed-manifest digest;
- final identity updates in fixture, reviews, sanitized evidence, and PR body.

This authorization accepts no unknown future source, manifest, contract,
fixture, verifier, or candidate identity. Future bytes become reviewable
proposals only after construction and static validation. They are not
executable admission.

Protocol proposal v7/generation 108 remains unchanged unless semantics require
a separate owner-freeze generation. Normative protocol semantics cannot drift
inside R1 remediation.

These historical paths must remain byte-identical:

| Path | Raw SHA-256 |
|---|---|
| `registry/m1b/offline-executable-tcb-contract-v4.json` | `fd5e54a8c4b03b6a9c0a62b715ce6d8b2eac070965467bd2de0dbe772808ce6f` |
| `docs/specs/m1b-offline-executable-tcb-admission-contract.md` | `8cfee3b0e28dac105bd9d51114288f9f70ef849ec45e8afb3ad72681f13b5d34` |
| `fixtures/m1b/tcb-admission/cases.json` | `b729305612bdf5f3e88d42a90603cf6a10b2100bd31b144c28399a155984d862` |
| `docs/decisions/M1B-1A0-contract-review.md` | `26ddc28ed1671138c1981be52b81871e4ad5e3980e58c64d8841bc204411d26a` |
| `registry/m1b/m1b-1a1-candidate-construction-scope-v2.json` | `c757c7c7c6bd6f35c4c068fa45fc2543ef0f9aaa37f3fe18bb7d7926c1cc6294` |
| `docs/specs/m1b-1a1-candidate-construction-authorization-contract.md` | `6d4f69cd8a4d39e071c475cd1f0d08ed63e6f0802988b7c200e653b3f45f7bf4` |
| `docs/decisions/M1B-1A1-AUTH-owner-authorization.json` | `3dbe6b8ed6ec980ecb712aa0667ee9fd25920164eeb5b455bdae8e9a1136ab50` |
| `docs/decisions/M1B-1A1-AUTH-owner-signoff.md` | `19bec94f5efc3dd2a217965b59ce476fb0de718479aa7ef12605eeb1eab69ba5` |

Historical v4 contract framed SHA-256 remains
`ad6bce1a5c516753d79ee0d807f5445e9b860a398e661adfb9730d9c4fee9c31`.

## 12. Host validation boundary

Only these validation purposes are authorized:

- canonical JSON reproduction;
- duplicate-key, type, float, path, order, and closed-schema checks;
- raw and framed SHA-256;
- exact file type/mode/link/path and parent closure;
- raw-byte and line-oriented static review of scoped future outputs;
- status-only diff review;
- Markdown link validation in changed future documents;
- `git diff --check`;
- exact changed-path checks;
- clean-tree and local/upstream/remote/PR parity;
- sanitized ignored evidence creation.

Candidate source must not be passed to AST, tokenizer, linter, compiler,
interpreter, import machinery, `py_compile`, `runpy`, `eval`, `exec`, or a
subprocess. Newly created repository verifier/test/source files also remain
inert and are not imported or executed in the remediation. Host Python, when
used for authorized data validation, must run with
`PYTHONDONTWRITEBYTECODE=1`; `.pyc` and `__pycache__` are forbidden.

These checks are static authorization evidence only. They are not functional,
provider, model, benchmark, runtime, source-eligibility, full-suite,
private-corpus, or executable-admission validation.

## 13. Explicitly outside scope

Neither this authorization nor the later remediation permits:

- candidate import, parse, tokenization, lint, compile, or execution;
- provider/Ollama/model call or metadata probe;
- model store, official/private corpus, prompt/template, mod, Workshop,
  Stellaris, launcher, active playset, or translation reads;
- real translation generation, human scoring, benchmark, tuning, or holdout;
- execution/runtime envelope or invocation-plan instance construction;
- implementation/runtime acceptance records or executable TCB admission;
- M1B-1A2, product CLI, M2, activation, publishing, or merge of PR #10.

All `16` existing executable/runtime blockers remain preserved.

## 14. Authorization-stage validation and gate

The authorization PR may validate only its six tracked outputs and one ignored
evidence file. It must show exact PR #10 identity, two independent scope
canonical/raw/framed reproductions, `22/22` immutable input hashes, closed
schemas/counts/order/parent closure, status-only diffs, Markdown links,
`git diff --check`, and final branch/upstream/remote/new-draft-PR parity.

No candidate source was executed or passed to Python language tooling. No
provider, model, corpus, mod, game, launcher, playset, or translation data was
accessed.

```text
AUTHORIZATION: READY_FOR_OWNER_REVIEW
M1B-1A-R1-AUTH: READY_FOR_OWNER_REVIEW
EFFECT: NOT_ACTIVE_UNTIL_OWNER_REVIEW_AND_MERGE
PR10: CHANGES_REQUIRED_UNCHANGED
M1B-1A1: BLOCKED_PENDING_R1_AUTH
M1B-1A2: FORBIDDEN
EXECUTABLE_TCB_ADMISSION: NOT_GRANTED
M1B-1A PROVIDER EXECUTION: NOT_STARTED
M1B: NOT_EVALUATED
M1A: BLOCKED
M2: FORBIDDEN
PR: DRAFT
```

The only next step is owner review of this authorization draft PR. Remediation
of PR #10 remains forbidden until the exact reviewed authorization bytes are
merged into `main`.
