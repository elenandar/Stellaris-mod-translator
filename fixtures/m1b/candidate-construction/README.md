# M1B-1A1 inert candidate-construction cases

This directory contains only synthetic, inert data for static owner review.
Nothing here authorizes or performs parsing, compilation, import, execution,
provider access, model access, corpus access, benchmark work, admission, or
runtime-envelope construction.

## Closed fixture schema

`cases.json` uses schema
`m1b-1a1-candidate-construction-cases-v1`. The root has exactly:

- `cases`: the case array;
- `fixture_schema`: the exact schema identifier;
- `limits`: an object with exactly
  `cumulative_materialization_bytes`, `input_bytes`, and `max_patches`.

Every case has exactly `base`, `expected`, `id`, and `patches`.

- `base` is the explicit synthetic JSON object to copy before patching.
- `expected` has exactly `codes` and `status`. It is declarative review
  metadata only; the materializer does not evaluate it.
- `id` matches `[a-z0-9][a-z0-9-]{0,79}`. IDs are unique and sorted by raw
  ASCII bytes.
- `patches` is an ordered array of closed patch objects.

`status` is exactly `ok` or `error`. An `ok` row has no codes; an `error` row
has one controlled uppercase code. This convention records intended static
disposition only. It does not report candidate execution or a passed test.

## Materialization contract

`materialize_case(case)` accepts one explicit case object. It performs no
fixture discovery and reads no path, environment, provider, model, corpus, or
persistent state. Success returns compact sorted-key ASCII JSON bytes for the
patched `base`, without a trailing LF, and retains the result only in memory.
The caller-owned input is unchanged: the base and every accepted patch state
are handled through defensive copy-on-write materialization.

Supported operations and their exact fields are:

- `set`: `operation`, `target`, `value`;
- `append`: `operation`, `target`, `value`;
- `copy_append`: `operation`, `source`, `target`;
- `delete`: `operation`, `target`.

Each path is a nonempty array of at most 64 nonempty string keys or
nonnegative integer indices. Boolean indices are invalid. Input is an acyclic
JSON tree of objects, arrays, strings, signed 64-bit integers, booleans, and
null, with container depth at most 64. Repeated mutable-container identity is
rejected rather than treated as JSON aliasing.

The closed limits are:

- explicit canonical case input: at most `4194304` bytes (4 MiB);
- patches per case: at most `256`;
- each materialized document: at most `4194304` bytes (4 MiB);
- cumulative compact bytes for the base and every post-patch state: at most
  `16777216` bytes (16 MiB), with a full 4 MiB reserve required before another
  encoding.

Failures expose only `FIXTURE_INVALID`, `INPUT_SIZE_LIMIT`, or
`MATERIALIZATION_WORK_LIMIT` through `MaterializationError.code`; no path,
content, exception text, or traceback is included in that controlled code.

## Adversarial matrix

The 42 cases cover:

- positive manifest shape, missing/extra/duplicate/swapped roles, path/order/
  hash drift, and manifest self-entry;
- non-regular source, symlink, hardlink, execute bit, and provider harness
  sizes of zero and greater than 512 bytes;
- stale source and manifest identities;
- forbidden parse, import, compile, and execute actions;
- unexpected path and directory entries, `__init__.py`, `.pyc`, and
  `__pycache__`;
- false owner acceptance, executable admission, and envelope construction;
- non-loopback and DNS endpoints, proxy, redirect, fallback, retry, and
  request-field drift;
- controlled context overflow, truncation, malformed response, path/content
  leakage, and uncontrolled failure.

All hashes, paths, endpoint literals, states, and payloads in the fixture are
synthetic review data. The fixture contains no real prompt, template,
translation, model-store data, official corpus, private corpus, mod content, or
game content.

## Non-authority statement

This fixture is not a test, trust root, acceptance record, runtime envelope,
invocation plan, source-eligibility proof, executable-TCB admission, provider
evidence, model evidence, benchmark result, or editorial approval. The
candidate source has not been parsed, compiled, imported, or executed.
