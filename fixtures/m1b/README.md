# M1B synthetic contract fixtures

Everything in this directory is public, minimal, and explicitly synthetic. No
official/private corpus bytes, localisation keys or excerpts, prompts,
translations, annotations, model outputs, filenames, local paths,
content-derived private hashes, real model tags, or real model digests were
used. Repeated single-character 64-hex digests are unmistakable placeholders;
fixed UUIDv4-shaped values are deterministic fixture IDs, not live identities.

`contract-cases.json` contains one `base_document` and `173` table-driven cases:
`3` controlled successes and `170` failures with one exact controlled code each.
The successful cases are:

- `positive` — canonical partial no-attempt state: zero model calls, technical
  `not_observed`, empty atoms, D1–D5 `not_evaluated`, zero technical successes;
- `human-fallback-success-zero-model-calls` — the declared human-fallback lane
  succeeds with `human_fallback_count=1` and `model_call_count=0`;
- `context-overflow-controlled-failure` — a no-output controlled failure with no
  human-quality evidence.

None is a complete benchmark. Document schema `m1b-synthetic-contract-v4`
always rejects `complete_benchmark`; the positive document declares only three
of six future primary assignments and makes no attempt/output/D1 claim. Only the
separate human-fallback transition has output-bearing synthetic D1 conformance;
D2–D5 and editorial state remain `not_evaluated`.

## Frozen public proposal identities

The fixture uses:

- fixture schema `m1b-synthetic-contract-cases-v4`;
- protocol `m1b-benchmark-contract-v6`, generation `107`;
- output schema `m1b-synthetic-output-v4`;
- corpus `m1b-synthetic-corpus-v3`, generation `304`;
- quality rubric `m1b-quality-rubric-v6`, generation `106`;
- analysis policy `m1b-analysis-policy-v6`, generation `107`;
- `17` byte-exact public proposal components;
- bundle SHA-256
  `7f1e417a843a0f3d0658e1e2abeb794c5c21a1dcb6f6482cd5f561c986ae00a9`;
- public synthetic corpus SHA-256
  `ec5a1201f790a5c1645a29002b37848d7e98aa79988da0eb186b6cb2147bc250`;
- fixed first-component vector
  `e180ba237311a7d7de3aa4c7c97881f09507651910a8469df7bcef0cd04cd7f0`;
- fixture file SHA-256
  `22c43f48f139b906b922da5ab5ceeb6f1378cf7ad36a4f019dae61fc0c361828`.

All definitions remain `proposed`; none is `owner_accepted`. The bundle binds
declarative definitions and the public synthetic corpus, not the exact current
validator/harness/analysis/runtime TCB. Synthetic scope provenance is therefore
diagnostic-only; full decision admission remains unavailable and blocked by
`OWNER_DECISION_REQUIRED`, `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN` and
`CONTEXT_LIMIT_BINDING_UNPROVEN`.

## What the offline gate checks

Without Ollama or a live model, the table and unit tests cover:

- strict bounded UTF-8 JSON, duplicate-key, integer, endpoint, closed-schema,
  controlled-output, no-path/no-exception-echo, and materialized fixture
  expansion/patch-count/cumulative-work boundaries;
- exact component/bundle/corpus framing and coherent definition/profile drift;
- equal unranked candidates, partial coverage, unique assignments, immutable
  source cluster to split/stratum/source-generation binding, and row-derived
  accounting;
- exact typed-atom value, kind, occurrence, multiplicity, and UTF-8 byte-span
  preservation using invented literals only;
- separate technical, human, editorial, finding, review, and adjudication
  states; critical false accept only after actual approval plus a confirmed
  underlying critical defect;
- truthful primary/repair/model-fallback model calls and zero-call human
  fallback, with `attempt_index=0` in every lane when retries are disabled;
- external mapping compromise versus non-recoverable self-identification,
  positive mapping generations, global reviewer exposure, and exact blinding
  aggregate derivation;
- HGT-derived unique logical rows, exact two-existing-conflicting-initial linkage,
  same-result/dimension/current-mapping scope, one distinct third human, full HGT
  consumption, and canonical stable reviewer pairs; exact
  `0..4` source-balanced quadratic kappa, bilateral and unilateral
  `not_applicable`, equal-source weighting of actual paired rows, zero variance,
  insufficient coverage, every delete-one-whole-source robustness branch, and
  explicit split provenance with no tuning/holdout pooling;
- source-generation conservative collapse, descriptive-only overall totals,
  three-candidate family correction, and closed split-scoped CFA source/class
  aggregation; exact synthetic scopes remain diagnostic/ineligible, while all
  three production decision entrypoints reject caller rows and require a
  separate full admission unavailable in M1B-0;
- immutable reviewer-specific finding outcomes for decision/severity/hard-fail/
  mandatory-review, exact third-human adjudication, top-level downgrade
  rejection, distinct identities for two initial human reviews, and no
  model-review human credit;
- no-output and no-attempt rows reject findings and human/model content reviews;
  no-attempt rows have zero technical success, and every no-output row becomes a
  conservative failure in synthetic quality/gate scopes instead of disappearing
  from denominators;
  self-identifying output permits only descriptive secondary-unblinded evidence;
- partial-report evidence restrictions, context self-assertion rejection, and
  the external implementation-identity blocker.

Self-identifying model-output rows require exactly one model call. Their
denominator/secondary/aggregate transitions are checked by offline state
validators, but a full M1B-0 document containing such a live observation stops
at `CONTEXT_LIMIT_BINDING_UNPROVEN`; the fixture does not pretend that a model
was called. Generic agreement, statistical, and CFA rows are public synthetic
math vectors only and never expose decision eligibility or a satisfied raw CFA
minimum. The synthetic-scope issuer revalidates the exact analysis-source subset
(proposal bundle/protocol, canonical corpus, candidates, results, findings and
HGT) before materializing complete per-scope rows. Its nominal token prevents
accidental caller-row use under an unmodified same-process TCB, but is not a
security boundary against reflection/monkeypatching inside that TCB. Agreement
rows retain linked frozen initial records and the source sample split. Tuning and
holdout scope math remain explicitly marked diagnostics and cannot satisfy a
production gate without separate full admission.

For official/private data, exact values, positions, row IDs, content-derived
hashes, and reviewer/source mappings must remain local. Only controlled codes
and aggregates may leave the future private runner after a separate leakage
gate.

## Run

From the repository root:

```sh
python3 tools/research/m1b_contract.py validate-case fixtures/m1b/contract-cases.json positive
python3 -m unittest tools.research.tests.test_m1b_contract -v
```

A standalone explicitly supplied public synthetic document can be checked with:

```sh
python3 tools/research/m1b_contract.py validate EXPLICIT_SYNTHETIC_JSON
```

Success exits `0`; controlled failure exits `2`. Standard error remains empty.
Standard output is one compact JSON object containing only `status`, `counts`,
and `codes`; it never echoes input data, case ID, filename, path, numeric token,
exception, or traceback.

Synthetic conformance is not provider residency/persistence evidence, model
quality, human/editorial approval, executable identity, an M1B verdict, or
permission to enter M2. Current gates remain `M1B: NOT_EVALUATED`,
`M1A: BLOCKED`, and `M2: FORBIDDEN`.
