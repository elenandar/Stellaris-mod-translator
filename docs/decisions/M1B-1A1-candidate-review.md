# M1B-1A1 inert candidate review

- Milestone: `M1B-1A1 — exact inert four-role candidate construction`
- Recommended Codex model: `GPT-5.6 Sol`
- Reasoning level: `Ultra`
- Construction date: `2026-07-23`
- Review state: `M1B-1A1 CANDIDATE: READY_FOR_OWNER_REVIEW`
- Authorization state: `M1B-1A1-AUTH: ACCEPTED/MERGED`
- Construction state: `CANDIDATE CONSTRUCTION: COMPLETE_WITHIN_EXACT_INERT_SCOPE`
- Source state: `CANDIDATE SOURCE: NOT_PARSED_NOT_COMPILED_NOT_IMPORTED_NOT_EXECUTED`
- Manifest state: `PROPOSED EXECUTABLE MANIFEST: REVIEWABLE_PROPOSAL_ONLY_NOT_ADMISSION`
- Executable admission: `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`
- Runtime envelope: `RUNTIME_ENVELOPE_CONSTRUCTION: NOT_AUTHORIZED`
- Provider execution: `M1B-1A PROVIDER EXECUTION: NOT_STARTED`
- Dependent gates: `M1B: NOT_EVALUATED`; `M1A: BLOCKED`; `M2: FORBIDDEN`

This record reviews proposed inert source bytes and synthetic data only. It is
not an implementation acceptance record, runtime acceptance record, execution
envelope, invocation plan, executable admission, provider result, benchmark
result, quality verdict, source-eligibility proof, or editorial approval.

## Merge and authorization provenance

Construction started from exact merged PR #9 provenance:

- repository: `elenandar/Stellaris-mod-translator`;
- PR #9 state: `MERGED`;
- merge commit: `1f10c151c5adac5fbf765af8093c7eddf8cf0429`;
- ordered parents:
  `bfe3faaaf1c13021f4ecc62b7c584bc28ba964bc`,
  `da3d44e4123c1ea41233ab2c7995d17394deadfd`;
- construction branch:
  `agent/m1b-1a1-inert-candidate-construction`;
- base inputs: `18/18` raw SHA-256 matches;
- post-merge AUTH inputs: `4/4` exact byte identities.

The authorization scope identity is:

| Field | Exact value |
|---|---|
| Schema | `m1b-1a1-candidate-construction-scope-v2` |
| Generation | `2` |
| Canonical bytes | `11157` |
| Raw SHA-256 | `c757c7c7c6bd6f35c4c068fa45fc2543ef0f9aaa37f3fe18bb7d7926c1cc6294` |
| Framed SHA-256 | `0c0a277598e1466dc764692dc4fe81abbb264e175a7cdc9205c2fe8e4cc8c9d1` |

Post-merge AUTH inputs reproduced before construction:

| Path | Bytes | Raw SHA-256 |
|---|---:|---|
| `docs/decisions/M1B-1A1-AUTH-owner-authorization.json` | `3744` | `3dbe6b8ed6ec980ecb712aa0667ee9fd25920164eeb5b455bdae8e9a1136ab50` |
| `docs/decisions/M1B-1A1-AUTH-owner-signoff.md` | `11988` | `19bec94f5efc3dd2a217965b59ce476fb0de718479aa7ef12605eeb1eab69ba5` |
| `docs/specs/m1b-1a1-candidate-construction-authorization-contract.md` | `23822` | `6d4f69cd8a4d39e071c475cd1f0d08ed63e6f0802988b7c200e653b3f45f7bf4` |
| `registry/m1b/m1b-1a1-candidate-construction-scope-v2.json` | `11157` | `c757c7c7c6bd6f35c4c068fa45fc2543ef0f9aaa37f3fe18bb7d7926c1cc6294` |

## Architecture and role boundaries

The four roles are deliberately separate:

1. `analysis_engine` performs deterministic calculations only over already
   validated structures. It uses exact integer and `Fraction` arithmetic for
   agreement, weighted kappa, D1-D5, CFA, and aggregate gates. Technical and
   editorial outcomes remain distinct, and editorial approval remains a human
   decision.
2. `contract_validator` owns the strict UTF-8 JSON boundary, closed protocol
   v7/generation-108 schemas, controlled failures, manifest-bound role-module
   handoff, and the future numeric-loopback-only provider request boundary.
   Its network logic is inert source text in this milestone.
3. `provider_request_harness` is only the bounded descriptor-script bootstrap:
   it imports the three exact role modules and delegates to the closed
   `provider_entrypoint`.
4. `synthetic_fixture_materializer` accepts one explicit inert case, applies a
   closed copy-on-write patch language, and returns only bounded in-memory
   canonical bytes. It performs no discovery or persistent output.

No role imports a historical repository implementation. Runtime imports are
limited to Python standard-library names and the exact candidate roles used by
the provider bootstrap.

## Exact source identities

All four source paths are new regular files, mode `0644`, `st_nlink=1`, with no
execute bits, symlink, hardlink, shebang, BOM, CR, NUL, or non-ASCII byte.
Every file uses LF and exactly one terminal LF.

| Role | Path | Bytes | Raw SHA-256 | Mode | Type | Links |
|---|---|---:|---|---:|---|---:|
| `analysis_engine` | `tools/research/m1b_1a1_candidate/analysis_engine.py` | `22743` | `a88c80415cb481beb25c7e18881bc863bef8196c85a95926d9fc5cdf64e67f92` | `0644` | regular | `1` |
| `contract_validator` | `tools/research/m1b_1a1_candidate/contract_validator.py` | `62538` | `51f0d00b068f27687b90094123c0991d009a6afd019fcc8d856517fc882748f1` | `0644` | regular | `1` |
| `provider_request_harness` | `tools/research/m1b_1a1_candidate/provider_request_harness.py` | `187` | `b2a18e2d54fe2273981263586234fe64b57eec24ff2c6fc20b2b617c22774174` | `0644` | regular | `1` |
| `synthetic_fixture_materializer` | `tools/research/m1b_1a1_candidate/synthetic_fixture_materializer.py` | `9005` | `ffc07a0e32f120cf38d4f41c2c6550837cec3d39dd53c3037596fa32207dfbd5` | `0644` | regular | `1` |

The provider harness is `187` bytes and therefore lies inside the required
atomic descriptor transport range `1..512` bytes. This structural fact is not
source-eligibility evidence.

## Proposed manifest identity

`registry/m1b/m1b-1a1-proposed-executable-manifest-v1.json` is compact
sorted-key ASCII JSON plus one LF. It contains only the exact four sorted
role/path/hash rows.

| Field | Exact value |
|---|---|
| Schema | `m1b-executable-implementation-manifest-v1` |
| Implementation generation | `1` |
| Canonical bytes | `814` |
| Raw SHA-256 | `3d2daab0211fb7a4e3e40cdcdb0fddeb6087b1fb0e640f1e2925557ff8ec48cd` |
| Framing domain | `stellaris-m1b-executable-manifest-v1` |
| Framed SHA-256 | `38c710987da74369d26883cfa33a7587a98746f1eb7129716a5d8315a23cd391` |

The framed digest is only a proposed identity. The manifest has no self-entry,
self-hash, acceptance, envelope, or admission field.

## Inert synthetic fixture identity

| Field | Exact value |
|---|---|
| Schema | `m1b-1a1-candidate-construction-cases-v1` |
| Unique raw-ASCII-sorted cases | `42` |
| Canonical bytes | `22394` |
| Raw SHA-256 | `a7f13de146722edf6af167ce63b7c33bf650fad3ab66339e73d902b047859ec7` |

The fixture is synthetic inert data. Its declared outcomes were not produced
by candidate execution. It is not a test, trust root, admission record, prompt,
template, translation, corpus, provider result, or benchmark result.

## Exact output inventory

The tracked diff contains exactly these `11` paths:

1. `README.md`
2. `docs/decisions/M1B-1A1-candidate-review.md`
3. `docs/roadmap.md`
4. `fixtures/m1b/candidate-construction/README.md`
5. `fixtures/m1b/candidate-construction/cases.json`
6. `registry/m1b/m1b-1a1-proposed-executable-manifest-v1.json`
7. `tools/research/README.md`
8. `tools/research/m1b_1a1_candidate/analysis_engine.py`
9. `tools/research/m1b_1a1_candidate/contract_validator.py`
10. `tools/research/m1b_1a1_candidate/provider_request_harness.py`
11. `tools/research/m1b_1a1_candidate/synthetic_fixture_materializer.py`

The only ignored output is
`artifacts/m1b/m1b-1a1/candidate-construction-evidence.json`. It is a regular
mode-`0600` sanitized artifact and is not staged or force-added.

## Static validation performed

Only bounded host validation and static exact-byte review were performed:

- Python version check: `3.9.6`;
- PR #9 merge SHA, ordered parents, ancestry, exact `origin/main`, clean initial
  worktree/index, and future branch/PR/directory absence;
- two independent scope canonical/raw/framed identity reproductions;
- base hashes `18/18`, post-merge AUTH identities `4/4`, closed schemas, exact
  counts `18/4/4/4/12`, raw-ASCII order, uniqueness, path grammar, and parent
  closure;
- exact directory type/mode checks for four create-only directories;
- static source type/mode/link/size/hash and ASCII/LF/no-BOM/no-CR/no-NUL
  checks, including harness `1..512` and aggregate `32 MiB` bounds;
- line-oriented manual review of role boundaries, closed schemas, bounded
  sequences, controlled public results, prohibited dynamic-code/process
  surfaces, and numeric-loopback provider policy;
- independent raw-text-only source review, bounded remediation of four
  producer/consumer and result/gate consistency findings, and repeat raw-text
  review without parsing, compiling, importing, or executing candidate source;
- two independent manifest canonical/raw/framed reproductions and exact linkage
  to source hashes;
- system JSON validation of fixture closed schemas, canonical bytes,
  unique/sorted case IDs, limits, and required adversarial matrix coverage;
- Markdown links in the five changed future documents checked using Git tree
  metadata without reading arbitrary link targets;
- exact future-directory inventories, no execute bits, no symlink/hardlink,
  and absence of `__init__.py`, `.pyc`, and `__pycache__`;
- leakage/sentinel scan limited to the exact `12` future outputs;
- status-only diff review for `README.md`, `docs/roadmap.md`, and
  `tools/research/README.md`;
- `git diff --check`, exact `11`-path tracked inventory, ignored-evidence
  exclusion, unchanged `origin/main`, and final local/upstream/remote/PR-head
  parity.

These checks are not runtime, source-eligibility, provider, benchmark, product,
canonical full-suite, or private-corpus validation.

## Zero action counters and caveat

| Action | Count |
|---|---:|
| Candidate source parse / AST / tokenizer / language parser | `0` |
| Candidate source compile / `py_compile` / `compileall` | `0` |
| Candidate source import | `0` |
| Candidate source execution / `eval` / `exec` / `runpy` / subprocess | `0` |
| Provider / Ollama / model calls or metadata probes | `0` |
| Official/private corpus reads | `0` |
| Mod / Workshop / Stellaris / launcher / active-playset reads | `0` |
| Benchmark / tuning / holdout / human scoring | `0` |
| Runtime or execution envelope construction | `0` |
| Invocation plan construction | `0` |
| Implementation or runtime acceptance-record construction | `0` |

These are protocol-level counters for the bounded construction workflow, not
an OS-wide syscall audit.

## Preserved blockers

All `16` authorization blockers remain preserved:

1. `CONTEXT_LIMIT_BINDING_UNPROVEN`
2. `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN`
3. `EXECUTABLE_TCB_OWNER_DECISION_REQUIRED`
4. `INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN`
5. `LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN`
6. `LIFECYCLE_STATE_UNPROVEN`
7. `MISSING_PROMPT_BYTES`
8. `MISSING_REAL_CANDIDATE_IDENTITIES`
9. `MISSING_TEMPLATE_BYTES`
10. `NATIVE_DEPENDENCY_CLOSURE_UNPROVEN`
11. `OUTPUT_LIMIT_BINDING_UNPROVEN`
12. `PARTIAL_REPORT_CANNOT_BE_COMPLETE`
13. `PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN`
14. `PROVIDER_PERSISTENCE_UNPROVEN`
15. `RESIDENCY_UNPROVEN`
16. `ROLE_IMPORT_TRANSPORT_UNPROVEN`

The proposed identities are reviewable but not owner-accepted executable
identities. No admitted interpreter selected these bytes, no launcher
opened-byte chain or role-import transport was proved, no context/output or
native-dependency binding was proved, and no provider persistence/residency or
lifecycle evidence was collected.

## Gate

```text
VERDICT: READY_FOR_OWNER_REVIEW
M1B-1A1-AUTH: ACCEPTED/MERGED
M1B-1A1: READY_FOR_OWNER_REVIEW
CANDIDATE CONSTRUCTION: COMPLETE_WITHIN_EXACT_INERT_SCOPE
CANDIDATE SOURCE: NOT_PARSED_NOT_COMPILED_NOT_IMPORTED_NOT_EXECUTED
PROPOSED EXECUTABLE MANIFEST: REVIEWABLE_PROPOSAL_ONLY_NOT_ADMISSION
NEW REPOSITORY CODE EXECUTION: NOT_AUTHORIZED
RUNTIME_ENVELOPE_CONSTRUCTION: NOT_AUTHORIZED
EXECUTABLE_TCB_ADMISSION: NOT_GRANTED
EXECUTABLE_TCB_OWNER_DECISION_REQUIRED: PRESERVED
PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN: PRESERVED
EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN: PRESERVED
MISSING_REAL_CANDIDATE_IDENTITIES: PRESERVED
INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN: PRESERVED
LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN: PRESERVED
ROLE_IMPORT_TRANSPORT_UNPROVEN: PRESERVED
M1B-1A PROVIDER EXECUTION: NOT_STARTED
M1B: NOT_EVALUATED
M1A: BLOCKED
M2: FORBIDDEN
```

The only next action is owner review of the draft PR. No Ready-for-review
transition, merge, auto-merge, runtime construction, admission, provider/model
action, corpus work, benchmark, activation, or publishing is authorized.
