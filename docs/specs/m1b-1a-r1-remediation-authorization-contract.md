# M1B-1A-R1-AUTH v3 — post-merge transport and evidence-provenance remediation authorization

```text
Milestone: M1B-1A-R1-AUTH v3 — authorization only
Разрешённый слой: one bounded future post-merge remediation branch and draft PR after effect
Рекомендуемая модель Codex: GPT-5.6 Sol
Уровень рассуждения: Ultra
Входные evidence: exact PR #10 merged provenance/tree, PR #11 recovery refs, accepted M1B-1A0 v4 and M1B-1A1-AUTH bytes
Результаты: closed scope, owner authorization, owner signoff, minimal status links, sanitized ignored evidence
Обязательные проверки: canonical/hash/path/order/link/diff/parity validation without candidate execution
Условия остановки: any PR #10 provenance, PR #11, main, worktree, identity, path, schema, or effect mismatch
Вне scope: remediation implementation, candidate execution, provider/model/corpus access, envelope instances, acceptance, admission, benchmark, M2
```

- Scope schema: `m1b-1a-r1-remediation-scope-v3`
- Scope generation: `3`
- Owner record: `m1b-1a-r1-remediation-owner-authorization-v3`
- Operational review state: `M1B-1A-R1-AUTH-V3: READY_FOR_OWNER_REVIEW`
- Effect: `after_review_and_merge_to_main`
- Historical PR #10 state: `MERGED_OWNER_CONTROLLED_SCOPE_DEVIATION`
- Scope v1 state: `NEVER_EFFECTIVE`
- Scope v2 state: `SUPERSEDED_BEFORE_EFFECT`
- Remediation state: `NOT_AUTHORIZED_UNTIL_V3_MERGE`
- New repository code execution: `NOT_AUTHORIZED`
- Executable TCB admission: `NOT_GRANTED`

## 1. Decision boundary

This contract authorizes no remediation in its own PR. It records only an
owner-controlled, default-deny scope for one later post-merge remediation branch
and one new draft PR. Historical
[PR #10](https://github.com/elenandar/Stellaris-mod-translator/pull/10) is
already merged and is only an immutable baseline. The authorization PR creates
four normative authorization artifacts, two minimal status/link updates, and
one sanitized ignored evidence file. It does not remediate or execute any
candidate, modify M1B-1A0 verifier/test/fixture/v4 bytes, revert PR #10, or
create the future remediation branch/PR.

The machine owner record uses `acceptance_state=owner_accepted` only for this
exact delegated remediation scope. That value does not activate the scope.
Operational authority remains absent until the owner has reviewed and merged
the exact authorization bytes into `main`. Commit, push, draft-PR creation, or
merge without owner review cannot independently activate the effect.

Repository bytes cannot self-assert PR #11 final head or owner review. Therefore
a separate pre-effect, read-only activation-verification plane binds exact PR
#11, the fixed authorization branch and base branch, then requires the external
owner-controlled merge event and exact two-parent merge provenance. This
external witness is not a future implementation identity and cannot be
constructed by the scope or owner-record bytes.

PR #10 was merged by an external owner-controlled action contrary to its own
stop rule. The classification is `OWNER_CONTROLLED_SCOPE_DEVIATION`. Scope v1
never had effect and does not authorize that action retroactively. Scope v2 was
superseded before effect and grants no authority. The merged candidate bytes
remain inert and reviewable, not admitted executable bytes.

After effect, scope v3 permits only one new branch
`agent/m1b-1a-r1-postmerge-remediation`, one ordinary remediation commit, one
non-force push and one new draft remediation PR to `main`. It does not authorize
candidate execution, functional tests, provider execution, executable
acceptance, admission, or any mutation of PR #10.

## 2. Normative scope identity

The authoritative machine scope is
[`registry/m1b/m1b-1a-r1-remediation-scope-v3.json`](../../registry/m1b/m1b-1a-r1-remediation-scope-v3.json).
It is compact sorted-key ASCII JSON plus one LF and contains no self-hash.

| Field | Exact value |
|---|---|
| Schema / generation | `m1b-1a-r1-remediation-scope-v3` / `3` |
| Canonical bytes | `44423` |
| Raw SHA-256 | `1b860ee3ce42ba76ee457d9ceca0a2391e0d6a3216892ca77bf235219a9f4944` |
| Framing domain | `stellaris-m1b-1a-r1-remediation-scope-v3` |
| Framed SHA-256 | `fb3f439cfc67707922ddbae2e94a9deec4544336abf8bdace1d56191bad2b6e1` |

The framed digest is:

```text
SHA-256(
  ASCII("stellaris-m1b-1a-r1-remediation-scope-v3") ||
  NUL ||
  u64be(canonical_scope_length) ||
  canonical_scope_bytes
)
```

The separate owner record binds both digests and length. The scope binds the
four post-merge authorization paths by exact reviewed merge provenance. This
avoids circular self-hash and prevents an unreviewed replacement artifact from
activating the effect.

The authorization PR provenance is closed without a circular final-head field:
PR #11 has head branch
`agent/m1b-1a-r1-transport-provenance-auth`, base branch `main`, and an external
final head. That final head must descend from recovery integration merge
`3a57701275914d905f76606cf6db3072c40a17ac`, whose ordered parents are
`b2db2e612aac29f88f2762cb8bc1d3efbcdb6da6` and
`3c6ca3146d838b977f24bbc6b8c79dfb271e142b`.

Effect requires one ordinary two-parent merge reachable from `origin/main`.
Its first parent must equal exact
`3c6ca3146d838b977f24bbc6b8c79dfb271e142b`; its second parent must equal the
external final PR #11 head. Both the PR final-head diff against that exact base
and the base-to-merge delta must contain exactly six authorization-stage
tracked outputs. The final PR head and merge tree must contain byte-identical
copies of the four normative authorization artifacts. If `main` changes first,
effect does not activate. Squash, rebase, repository self-attestation,
branch-name-only provenance, or a merely descendant first parent cannot
activate effect.

The separate owner record is canonical
`m1b-1a-r1-remediation-owner-authorization-v3`, `8146` bytes, raw SHA-256
`06307a2351a75d19b231a4715f51c0de0f4704d4ca7a523005e221d5194c6fc7`.

## 3. Exact v3 correction preflight and historical merged baseline

The v3 correction preflight stopped before writes unless all of the following
matched after the bounded fetch:

- repository `elenandar/Stellaris-mod-translator`;
- clean branch `agent/m1b-1a-r1-transport-provenance-auth` at local/upstream,
  remote branch and PR #11 head
  `b247a20500b28227e826b9f3c14da8b8d77d48a3`;
- `origin/main` and PR #11 base at
  `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- PR #11 `OPEN / DRAFT / MERGEABLE`, auto-merge absent;
- clean tracked worktree and index;
- exact six-path base-to-head diff ending in R1 scope v2;
- future branch absent from local, remote-tracking, advertised-remote and live
  GitHub-PR namespaces;
- unresolved review thread `PRRT_kwDOTbY5J86TVPjf`;
- PR #10 `MERGED` with head
  `66f905cf266b9d1c1f56d0d706184387ffedb36e`, merge commit
  `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`, ordered parents
  `1f10c151c5adac5fbf765af8093c7eddf8cf0429` then
  `66f905cf266b9d1c1f56d0d706184387ffedb36e`, and merge/head tree
  `289e2396975c5ef6fe1001a7c5990523edaa06c5`.

The `b247a205…` value is only the exact initial head for this v3 correction.
It is neither the externally bound final v3 head nor the future remediation
branch base. Historical recovery integration merge
`3a57701275914d905f76606cf6db3072c40a17ac` and its ordered parents remain
unchanged. The future branch base is only the exact external two-parent PR #11
merge commit after effect.

The exact historical PR #10 merged tree contains these `11` paths:

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
are repeated in the machine scope. Recovery verification compared Git
mode/size/hash identities and byte parity only. Candidate source was not parsed,
tokenized, linted, compiled, imported, executed, or re-accepted as executable.

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
These are immutable historical merged-baseline identities, not accepted
executable identities.

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

After effect, a future remediation must fail closed unless exact PR #11 merge,
ancestry, exact repository identity and clean tracked worktree/index are proven.
The current checkout may remain at the external final PR #11 head or be another
clean non-target branch/detached state of this exact repository. Current `HEAD`
does not have to equal the merge commit, and no preliminary checkout or switch
is required or authorized.

After the bounded fetch and before branch creation, the exact future branch name
must be absent simultaneously from:

1. `refs/heads/agent/m1b-1a-r1-postmerge-remediation`;
2. `refs/remotes/origin/agent/m1b-1a-r1-postmerge-remediation`;
3. advertised remote
   `refs/heads/agent/m1b-1a-r1-postmerge-remediation`;
4. every live GitHub PR (`OPEN`, draft or non-draft, any base) with exact head
   branch `agent/m1b-1a-r1-postmerge-remediation`.

Any existing ref or live PR fails closed. It is not reused, deleted or reset.
The future remediation may then:

1. perform bounded fetches of exact repository refs needed for effect and
   ancestry verification;
2. perform the sole authorized branch transition:
   `git switch -c agent/m1b-1a-r1-postmerge-remediation
   <exact-pr11-merge-commit>`;
3. write only the exact future-output allowlist and create only the four exact
   create-only directories;
4. create one ordinary remediation commit;
5. perform one non-force push of that branch;
6. create exactly one new draft remediation PR with base `main`;
7. update only the title/body of that new draft PR.

The future PR number is unknown before creation and is bound through external
GitHub metadata. The four normative AUTH artifacts already exist in the PR #11
merge and become immutable base inputs; they are neither integration
consequences nor remediation outputs.

The scope forbids stash, reset, clean, amend, rebase, force-push, main mutation,
PR #10 mutation, merge/auto-merge/ready/close of the future remediation PR,
other branch or PR mutations, tags, releases, Actions changes, and network
outside exact Git/GitHub repository operations. A partial push cannot be
republished without a new owner decision.

After an ambiguous push result, only read-only reconciliation of the exact
advertised remote ref and intended SHA is authorized. After ambiguous PR
creation, only a read-only check for exactly one live PR with the exact head and
base `main` is authorized. No second push or PR creation may occur while the
first result is unknown. A missing or mismatched remote SHA, zero or multiple
matching PRs, a wrong base, or continuing uncertainty yields
`NEW_OWNER_DECISION_REQUIRED`.

No future remediation branch or PR is created in this authorization task:
`R1_REMEDIATION: NOT_AUTHORIZED_UNTIL_V3_MERGE`.

## 6. Closed repository content plane

Exact closed counts are:

| Surface | Count |
|---|---:|
| SHA-bound base inputs | `23` |
| Authorization-stage outputs | `6` |
| Immutable AUTH inputs | `4` |
| Candidate roles | `4` |
| Historical PR #10 paths | `11` |
| Future outputs | `19` (`18` tracked + `1` ignored) |
| Future directories | `4` |
| Preserved blockers | `16` |

The repository content plane is default-deny. After effect, semantic reads are
limited to:

- `23` exact SHA-bound historical/read-only inputs in the scope;
- the exact `11` historical PR #10 merged bytes above;
- the four exact reviewed post-merge authorization artifacts;
- static readback of exact future outputs.

Candidate source reads remain raw-byte SHA and line-oriented static-text only.
Metadata reads are limited to exact scope paths and lexical parent closure.
Unlisted reads and writes are denied.

The 23rd input is root [`.gitignore`](../../.gitignore): exact `733` bytes,
full file/Git mode `100644`, raw SHA-256
`0f36fee465d056ae9373a2aa702e58740f82c99c0fb25e0f24a326318087a82d`.
Its bytes may be read only to verify the `artifacts/` rule, support
`git status` and `git check-ignore`, and prove ignored evidence will not enter
the index. `.gitignore` is read-only and may not be changed.

The only future directories that may be created if absent are these exact real
directories:

| Path | Mode | Parent | Relationship |
|---|---:|---|---|
| `artifacts` | `0755` | repository root / `.` | repository root |
| `artifacts/m1b` | `0700` | `artifacts` | authorized predecessor or pre-existing real directory |
| `artifacts/m1b/m1b-1a-r1` | `0700` | `artifacts/m1b` | authorized predecessor or pre-existing real directory |
| `fixtures/m1b/tcb-admission-v5` | `0755` | `fixtures/m1b` | pre-existing real directory |

The closed creation order is `artifacts`, `artifacts/m1b`,
`artifacts/m1b/m1b-1a-r1`, then independently
`fixtures/m1b/tcb-admission-v5`. Every row is create-only-if-absent, requires a
real directory with its exact permission mode and forbids symlink, replacement
and deletion. An existing wrong type, symlink or wrong mode fails closed; no
`chmod`, replacement or deletion is authorized. Recursive ambient parent
creation and any other directory creation are forbidden.

The future file allowlist contains exactly `19` paths: `18` tracked and one
ignored sanitized evidence file.

| Path | Tracked | Lifecycle | Write kind |
|---|---:|---|---|
| `README.md` | `true` | existing tracked | status/link only |
| `artifacts/m1b/m1b-1a-r1/remediation-evidence.json` | `false` | new ignored evidence | sanitized ignored evidence |
| `docs/decisions/M1B-1A-R1-remediation-review.md` | `true` | new tracked | remediation review |
| `docs/decisions/M1B-1A0-contract-v5-review.md` | `true` | new tracked | contract-v5 review |
| `docs/decisions/M1B-1A1-candidate-review.md` | `true` | existing tracked | candidate review remediation |
| `docs/roadmap.md` | `true` | existing tracked | status/link only |
| `docs/specs/m1b-offline-executable-tcb-admission-contract-v5.md` | `true` | new tracked | versioned v5 specification |
| `fixtures/m1b/candidate-construction/README.md` | `true` | existing tracked | candidate fixture documentation remediation |
| `fixtures/m1b/candidate-construction/cases.json` | `true` | existing tracked | inert candidate fixture remediation |
| `fixtures/m1b/tcb-admission-v5/cases.json` | `true` | new tracked | versioned contract-v5 inert TCB fixture |
| `registry/m1b/m1b-1a1-proposed-executable-manifest-v1.json` | `true` | existing tracked | proposed manifest generation 2 |
| `registry/m1b/offline-executable-tcb-contract-v5.json` | `true` | new tracked | versioned machine contract v5 |
| `tools/research/README.md` | `true` | existing tracked | status/link only |
| `tools/research/m1b_1a1_candidate/analysis_engine.py` | `true` | existing tracked | candidate source remediation |
| `tools/research/m1b_1a1_candidate/contract_validator.py` | `true` | existing tracked | candidate source remediation |
| `tools/research/m1b_1a1_candidate/provider_request_harness.py` | `true` | existing tracked | candidate source remediation |
| `tools/research/m1b_1a1_candidate/synthetic_fixture_materializer.py` | `true` | existing tracked | candidate source remediation |
| `tools/research/m1b_tcb_contract_v5.py` | `true` | new tracked | versioned verifier-v5 inert source |
| `tools/research/tests/test_m1b_tcb_contract_v5.py` | `true` | new tracked | versioned verifier-v5 test inert source |

All pre-write existence, type, mode, link, identity and applicable
parent-containment checks for all `19` rows must complete successfully before
the first repository-content write. Post-write checks occur only after the
corresponding writer has completed.

For the `11` existing tracked rows, pre-write state is the exact regular tracked
file from the tree of the exact PR #11 authorization merge commit (not a
`git merge-base` result), full file/Git mode `100644`, `st_nlink == 1`, no
symlink, hardlink or physical alias, and bytes identical to that bound tree
blob. Deletion and path replacement are forbidden. Writing is descriptor-bound,
no-follow and in place; post-write verification repeats type, mode, link count
and containment.

For the `7` new tracked rows, the path must be absent in both the exact base tree
and worktree before any write. Creation is exclusive and no-follow. Final state
is a regular file with full mode `100644`, `st_nlink == 1`, no symlink,
hardlink or physical alias, and verified containment. Any collision fails
closed; deletion, replacement of an existing object and overwriting are
forbidden.

The ignored `remediation-evidence.json` path must likewise be absent before any
write and be created exclusive/no-follow. Its final state is a regular file
with permission mode `0600`, `st_nlink == 1`; writer close and post-write
type/mode/link/containment verification are mandatory. Existing file, symlink,
hardlink, alias or any other object fails closed without overwrite. It is never
staged or force-added.

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

After PR #11 effect, these four M1B-1A-R1-AUTH v3 artifacts are immutable base
inputs: owner record, owner signoff, this contract and scope v3. Their exact
bytes must match between the external final PR #11 head and its two-parent
merge tree. They may not be edited, deleted, replaced or staged as future
remediation outputs.

## 12. Host validation boundary

Only these validation purposes are authorized:

- canonical JSON reproduction;
- duplicate-key, type, float, path, order, and closed-schema checks;
- raw and framed SHA-256;
- exact file type/mode/link/path and parent closure;
- all-19-row pre-write lifecycle gate and declarative collision/link cases;
- four-directory fresh-tree closure;
- four-namespace branch/live-PR absence;
- SHA-bound `.gitignore`, `git status`, `git check-ignore` and index exclusion;
- read-only reconciliation of ambiguous push/PR-creation results;
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
- M1B-1A2, product CLI, M2, translation activation or product publishing;
- merge, auto-merge, ready-for-review or close of the future remediation PR.

All `16` existing executable/runtime blockers remain preserved.

## 14. Authorization-stage validation and gate

The authorization PR may validate only its six tracked outputs and one ignored
evidence file. It must show exact PR #10 merged provenance/tree parity, exact
recovery integration provenance, two independent scope
canonical/raw/framed reproductions, `23/23` immutable input hashes, lifecycle
rows `19/19`, directories `4/4`, candidate roles `4/4`, blockers `16/16`,
immutable AUTH inputs `4/4`, exact parent closure, status-only diffs, Markdown
links, `git diff --check`, no `.pyc` or `__pycache__`, exact six-path final PR
diff, and R1 scope-v1/v2 absence from both final tree and PR file list.

Static adversarial review must prove: a fresh tree without `artifacts/` has a
closed authorized chain; existing symlink/hardlink evidence paths, any new
tracked collision, and an existing tracked output with `st_nlink > 1` fail
closed before the first write. It must also prove that an initial `HEAD` at the
PR #11 final head can directly create-and-switch the future branch from the
exact merge commit, that absence covers all four namespaces, and that network
ambiguity never authorizes a repeated mutation.

At least two independent read-only semantic reviews must examine the same final
machine scope. Any P0–P2 finding blocks publication until corrected and both
reviews are rerun. Final validation also requires clean
local/upstream/remote/PR-head parity, PR #11 `OPEN / DRAFT / MERGEABLE`, and
auto-merge absent. Repository tests are intentionally not run and must not be
claimed as passed.

No candidate source was executed or passed to Python language tooling. No
provider, model, corpus, mod, game, launcher, playset, or translation data was
accessed.

```text
REMEDIATION: READY_FOR_OWNER_REVIEW
PR10: MERGED_OWNER_CONTROLLED_SCOPE_DEVIATION
PR10_CANDIDATE: INERT_NOT_ADMITTED
SCOPE_V1: NEVER_EFFECTIVE
SCOPE_V2: SUPERSEDED_BEFORE_EFFECT
M1B-1A-R1-AUTH-V3: READY_FOR_OWNER_REVIEW
R1_REMEDIATION: NOT_AUTHORIZED_UNTIL_V3_MERGE
NEW_REPOSITORY_CODE_EXECUTION: NOT_AUTHORIZED
PROVIDER_EXECUTION: NOT_STARTED
EXECUTABLE_TCB_ADMISSION: NOT_GRANTED
M1B: NOT_EVALUATED
M1A: BLOCKED
M2: FORBIDDEN
PR11: DRAFT
```

The only next step is owner review of this authorization draft PR. Remediation
branch/PR creation remains forbidden until the exact reviewed authorization
bytes are merged into `main` by the required owner-controlled two-parent merge.
