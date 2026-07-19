# M1B synthetic contract fixtures

Everything in this directory is public, minimal, and explicitly synthetic. No
official or private corpus bytes, localisation keys or excerpts, prompts,
translations, annotations, model outputs, filenames, local paths,
content-derived corpus hashes, or real model digests were used. Repeated
single-character 64-hex digests are unmistakable placeholders. Fixed
UUIDv4-shaped values are deterministic fixture identifiers, not content-derived
IDs and not examples of the random IDs required for a live run.

`contract-cases.json` contains one `base_document` plus 140 table-driven cases:
one positive case and 139 adversarial failures with exact controlled codes. The
positive document is only `partial_synthetic_conformance`; it is not a complete
benchmark report. It declares three primary assignments (one tuning sample for
each candidate) out of six required by the future candidate/sample cross
product.

Without running a model, the positive case proves:

- 15 byte-exact proposed definitions are checked against the validator's
  separately compiled trusted registry, using canonical component and bundle
  hash framing; the public synthetic corpus expectation is additionally bound
  to its domain-separated canonical digest in that registry;
- exactly three equal, unranked candidates use one profile version/generation,
  the exact common runtime proposal, synthetic model references/digests, and
  `not_probed` thinking state;
- provider residency and persistence remain `not_probed`, fallback/redirects/
  proxy/auto-pull are disabled, and live/model-call/accounting counts are zero;
- each sample has an independent request boundary, a closed request-field
  allowlist, and controlled truncation/context-overflow disposition;
- tuning and holdout sample IDs and source-unit clusters are disjoint;
- expected and observed invented atoms match on logical atom ID, occurrence ID,
  occurrence index/cardinality, kind, exact synthetic value, provenance, and
  exact UTF-8 byte span;
- D1 technical conformance is separate from D2-D5 human ground truth and from
  editorial status; all three results remain `not_evaluated`, with no findings,
  reviews, human ground truth, winner, baseline, or M1B verdict;
- every D2-D5 `human_pass`, `human_fail`, or `not_applicable` status requires a
  matching human-ground-truth record; absent evidence requires `not_evaluated`;
- coverage, per-candidate/per-stratum totals, execution lane/stage semantics,
  and aggregate accounting are derived from the synthetic rows; a repair,
  fallback, success, or terminal row cannot exist with phantom zero counters.

Exact synthetic literals and positions exist only in this public invented
fixture. A future official/private report must verify private atom bytes and
positions locally, then export only controlled codes and aggregate counts. It
must not publish private values, positions, row-level IDs, or content-derived
hashes.

The 139 negative cases cover strict JSON, canonical loopback endpoints,
stateless requests, trusted definition freeze integrity, coherent profile
drift, exact atoms, human/editorial gates, reviewer identity and role,
assignment uniqueness, partial/complete coverage, accounting, premature gate
claims, and raw/private field rejection. Raw-field cases add only a prohibited
key with a null value; the private-hash case likewise contains no hash.

The validator uses only the Python 3.9 standard library and performs no
discovery or I/O beyond the explicitly supplied JSON file. It does not call
Ollama, make a network request, inspect environment variables or a home
directory, read a model store, or inspect game/corpus locations.

Validate the positive fixture from the repository root:

```sh
python3 tools/research/m1b_contract.py validate-case fixtures/m1b/contract-cases.json positive
```

Validate a standalone synthetic contract document:

```sh
python3 tools/research/m1b_contract.py validate EXPLICIT_SYNTHETIC_JSON
```

Success exits `0`; every controlled failure exits `2`. Standard error remains
empty. Standard output is exactly one compact JSON object with only `status`,
`counts`, and `codes`. Failure counts are zero and the output never echoes an
input value, case ID, filename, path, numeric token, or exception.

Synthetic conformance success is not provider residency/persistence evidence,
model quality, human or editorial approval, an M1B verdict, or permission to
enter M2. Current gates remain `M1B: NOT_EVALUATED`, `M1A: BLOCKED`, and
`M2: FORBIDDEN`.
