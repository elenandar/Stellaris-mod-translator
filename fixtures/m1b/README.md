# M1B synthetic contract fixtures

Everything in this directory is public, minimal, and explicitly synthetic. No
official/private corpus bytes, localisation keys or excerpts, prompts,
translations, annotations, model outputs, filenames, local paths,
content-derived private hashes, real model tags, or real model digests were
used. Repeated single-character 64-hex digests are unmistakable placeholders;
fixed UUIDv4-shaped values are deterministic fixture IDs, not live identities.

`contract-cases.json` contains one `base_document` and `169` table-driven cases:
`3` controlled successes and `166` failures with one exact controlled code each.
The successful cases are:

- `positive` — partial public synthetic D1 conformance with zero model calls;
- `human-fallback-success-zero-model-calls` — the declared human-fallback lane
  succeeds with `human_fallback_count=1` and `model_call_count=0`;
- `context-overflow-controlled-failure` — a no-output controlled failure with no
  human-quality evidence.

None is a complete benchmark. Document schema `m1b-synthetic-contract-v3`
always rejects `complete_benchmark`; the positive document declares only three
of six future primary assignments. D1 is `synthetic_conformant`, while D2-D5 and
editorial state remain `not_evaluated`.

## Frozen public proposal identities

The fixture uses:

- fixture schema `m1b-synthetic-contract-cases-v3`;
- protocol `m1b-benchmark-contract-v2`, generation `102`;
- output schema `m1b-synthetic-output-v3`;
- corpus `m1b-synthetic-corpus-v3`, generation `304`;
- quality rubric `m1b-quality-rubric-v2`;
- `17` byte-exact public proposal components;
- bundle SHA-256
  `8992351db59d99deec8809a7228458577cca09c11f0d3c2fe15567315c4108d9`;
- public synthetic corpus SHA-256
  `ec5a1201f790a5c1645a29002b37848d7e98aa79988da0eb186b6cb2147bc250`;
- fixed first-component vector
  `00a5ff494e7bc07e7e4eb7ef18ee0b8dad7ef0b7f0a3d8c08b39e6a91e83bf34`.

All definitions remain `proposed`; none is `owner_accepted`. The bundle binds
declarative definitions and the public synthetic corpus, not the exact current
validator/harness/analysis implementation. Live admission therefore remains
blocked by `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN`. Context/tokenizer
admission independently remains `CONTEXT_LIMIT_BINDING_UNPROVEN`.

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
  fallback;
- external mapping compromise versus non-recoverable self-identification,
  positive mapping generations, global reviewer exposure, and exact blinding
  aggregate derivation;
- HGT-derived stable reviewer pairs, exact `0..4` quadratic kappa, bilateral and
  unilateral `not_applicable`, zero variance, insufficient coverage, and every
  delete-one-source robustness branch;
- source-generation conservative collapse, descriptive-only overall totals,
  three-candidate family correction, and closed CFA source/class aggregation;
- partial-report evidence restrictions, context self-assertion rejection, and
  the external implementation-identity blocker.

Self-identifying model-output rows require exactly one model call. Their
denominator/secondary/aggregate transitions are checked by offline state
validators, but a full M1B-0 document containing such a live observation stops
at `CONTEXT_LIMIT_BINDING_UNPROVEN`; the fixture does not pretend that a model
was called. Generic agreement rows are public synthetic math vectors only.
Decision-grade agreement rows are materialized inside the HGT validator from
linked frozen initial records.

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
