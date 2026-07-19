# M1B synthetic contract fixtures

Everything in this directory is public, minimal, and explicitly synthetic. No
official or private corpus bytes, localisation excerpts, prompts, translations,
annotations, model responses, filenames, local paths, content-derived corpus
hashes, or real model digests were used. The repeated hexadecimal digest values
are unmistakable test placeholders with the required bare lowercase 64-hex
shape. The zero-based UUIDv4-shaped values are deterministic fixture identifiers,
not content-derived IDs and not examples of the random IDs required for a live
run.

`contract-cases.json` contains one `base_document` and table-driven patches. The
base is the positive synthetic conformance document. It proves, without running
a model:

- exactly the three unranked candidates, with one common profile version and
  identical common runtime fields;
- provider and thinking residency states remain `not_probed`;
- an exact numeric-loopback `/api` endpoint policy with redirects, proxy routing,
  automatic pull, and fallback disabled;
- disjoint tuning and holdout UUID sets;
- synthetic-only typed atoms and exact observed atom equality;
- the five independent quality dimensions and two distinct human reviewers for
  a synthetic critical finding whose result is rejected; every result has one
  closed record per dimension, with only technical atom/schema conformance
  marked `synthetic_conformant` and all human-quality dimensions explicitly
  `not_evaluated`;
- explicit separate accounting for cold latency, warm latency, memory, repair,
  fallback, and terminal rejection;
- no completed benchmark, winner, baseline, or M1B verdict.

The remaining cases mutate exactly one boundary (except where a pair is needed
to express overlap) and name the expected controlled code. Raw-field cases add
only a prohibited key with a null value; they contain no raw payload. The private
corpus hash case likewise tests field presence with null and contains no hash.

The validator is Python 3.9 standard-library only and performs no discovery or
I/O beyond the explicitly supplied JSON file. It does not call Ollama, make a
network request, inspect environment variables or a home directory, read a model
store, or inspect any game/corpus location.

Validate the positive fixture from the repository root:

```sh
python3 tools/research/m1b_contract.py validate-case fixtures/m1b/contract-cases.json positive
```

Validate a standalone synthetic contract document:

```sh
python3 tools/research/m1b_contract.py validate EXPLICIT_SYNTHETIC_JSON
```

Success exits `0`; every controlled failure exits `2`. Standard error remains
empty. Standard output is exactly one compact JSON object with the allowlisted
keys `status`, `counts`, and `codes`. Counts are aggregate integers only. A
failure returns zero counts and one controlled code; it never echoes an input
value, case ID, filename, path, or exception.

The publishable document schema is closed at every object. It rejects unknown
fields, duplicate JSON keys, invalid UTF-8, non-finite JSON numbers, wrong exact
types (`bool` is not an integer), raw/free-text sinks, private content hashes,
profile or generation drift, and all adversarial states recorded in the case
table. Synthetic conformance success is not provider residency evidence, a model
quality result, an M1B verdict, or permission to enter M2.
