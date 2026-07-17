# M1A research harness

`m1a_harness.py` is a Python 3.9 standard-library spike for M1A evidence.  It is
not the M2 parser, renderer, product CLI, or publisher.  It never translates or
normalizes input and its only render operation is an identity return of the
original immutable bytes.

## Safety properties exercised

- a file is read twice through one descriptor and accepted only when descriptor
  metadata, path metadata, byte count, and both byte passes agree;
- source symlinks, source replacement, partial reads, and observed generation
  changes abort with path-free error codes;
- inventory output contains only aggregate counts, booleans, controlled class
  labels, sizes, and hashes; source keys, values, filenames, and paths are not
  serialized;
- unknown or malformed input remains opaque and byte-identical;
- candidate assembly requires a sealed existing disposable root disjoint from
  every caller-supplied protected root;
- equality, ancestor/descendant overlap, traversal, duplicate/colliding relative
  paths, root replacement, and symlink substitution fail closed;
- candidate physical layout is flat, with generated payload names written
  directly through the sealed root descriptor; logical paths exist only in the
  manifest and nested-output rename races are outside this M1A protocol;
- every payload is reread from disk, hardlinks/extra entries are rejected, an
  observed payload-tree hash is computed independently of the manifest hash,
  and `manifest.json` is committed last;
- candidate `generation` is a content-addressed identity of accepted bytes;
  its source ID is domain-separated from the normalized synthetic logical path;
  absolute-path/device/inode/time observations remain in a separate observer
  digest so metadata-only churn or checkout relocation invalidates a live read
  without making logical output nondeterministic;
- a pre-commit crash/write failure cannot produce a complete candidate; a
  post-commit retry validates and reuses exact bytes without rebuilding.

The low-level aggregate inventory command accepts explicit absolute regular
file paths and writes JSON to stdout. Its error output is controlled JSON;
tracebacks, argument values, and exception strings are suppressed because they
may contain source paths. Codex/cloud agents must never invoke this explicit-
path mode on game, Workshop, launcher, mod, or private-translation files. It is
available only for an owner-controlled local process with an already-reviewed
privacy boundary.

```sh
python3 tools/research/m1a_harness.py inspect /absolute/path/to/input.yml
```

Do not attach raw command input or redirect unreviewed private output into Git.
Run the leakage check before retaining aggregate evidence.  Candidate-building
APIs are library-only so a caller must first provide all protected roots and
obtain a `DisposableRootSeal`; there is intentionally no convenient active-path
publishing command.

For Codex-visible local evidence, use the path-free auto-discovery collector:

```sh
python3 tools/research/m1a_local_probe.py collect
```

It accepts no game, Workshop, mod, descriptor, launcher, or corpus path. It
discovers only standard macOS/Steam locations inside the process, rejects
relative library paths and source symlinks, performs two full stable-read
content/topology manifests, runs a corpus-aware no-excerpt leakage check, and
emits fixed-schema aggregate JSON. A discovered launcher database is read only
as bytes for the generation manifest and is never opened through SQLite;
schema/order semantics remain unproven. Real local-mod `path` values are not
followed by this M1A helper. The scan reports exact-line, long structured-token,
descriptor/value, and private-path match counts only; it never returns a match.

Run the synthetic-only suite with:

```sh
python3 -m unittest discover -s tools/research/tests -v
```
