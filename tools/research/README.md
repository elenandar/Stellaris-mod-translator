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
- preflight identities are compared with the identities of the descriptors that
  were actually opened, and hardlink aliases observed after preflight abort;
- inventory output contains only aggregate counts, booleans, controlled class
  labels, sizes, and hashes; source keys, values, filenames, and paths are not
  serialized;
- unknown or malformed input remains opaque and byte-identical;
- candidate assembly requires a sealed existing disposable root disjoint from
  every caller-supplied protected root;
- equality, ancestor/descendant overlap, traversal, duplicate/colliding relative
  paths, root replacement, and symlink substitution fail closed;
- logical relative paths must be strictly UTF-8 encodable before source reads or
  candidate layout/write; unpaired surrogates return controlled
  `INVALID_RELATIVE_PATH`, while valid non-ASCII UTF-8 paths remain allowed;
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

A failure of the final directory `fsync` is still reported as a failed build.
The manifest may already describe a complete tree in the current filesystem
view, but M1A does not claim power-loss durability for that state.

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
emits `m1a-local-redacted-evidence-v2` aggregate JSON. `status=ok` means that
collection completed; it does not override any item in `blockers` and is not an
M1A gate verdict.

The duplicate section has three deliberately overlapping axes: intra-file
groups/occurrences stay in `inventory`, while same-source cross-file and
cross-source groups/occurrences are in `duplicates`. They must not be summed and
do not prove a collision winner. Two equal sequential manifests prove observed
pre/post equality, not an atomic cross-file snapshot; the collector therefore
always returns `CROSS_FILE_GENERATION_COHERENCE_UNPROVEN`.

A discovered launcher database is read only as bytes for the generation
manifest and is never opened through SQLite; schema/order semantics remain
unproven. Real local-mod `path` values are not followed by this M1A helper.

Before role-specific parsing, every observed private input contributes an exact
digest when nonempty plus physical-line and long structured-token fingerprints.
This includes localisation, descriptors, active-load/playset, version,
launcher-database and Steam discovery metadata. Invalid UTF-8/binary data stays
byte-level. Only the first physical localisation line receives the public-header
exception: after removing exactly its CR, LF, or CRLF terminator, an optional
BOM is accepted only at byte offset 0 and the entire remaining line must match
the strict public language-header grammar. Surrounding whitespace, control
bytes, a misplaced BOM, metadata and later header-shaped lines receive no
exception and remain fingerprinted. Parsed private values and paths remain
defense in depth. Public schema v2 returns only input/fingerprint denominators,
typed match counts and booleans; any match yields controlled
`LEAKAGE_DETECTED`, `status=blocked` and a non-zero CLI exit without returning a
fragment, digest, filename or path.

Write evidence is an exact field mapping, not five prose domains compressed
into four numbers: `containment.source_write_attempts` covers registered game
and Workshop source roots; `containment.launcher_write_attempts` covers launcher
roots; `containment.active_path_write_attempts` covers Documents/active roots;
`launcher.source_writes` states that launcher metadata/database has no write
entrypoint; and `candidate.active_path_writes` states candidate writes stayed in
disposable roots. All five are protocol-level zero counters/claims, not an
OS-wide syscall audit. Discovery and the repository leakage walk remain
path-based between operations, so protection against an arbitrary concurrent
same-UID actor is not claimed and
`CONCURRENT_SAME_UID_PATH_RACE_UNPROVEN` remains a blocker.

Run the synthetic-only suite with:

```sh
python3 -m unittest discover -s tools/research/tests -v
```

## M1B synthetic protocol gate

The M1B-0 [benchmark contract](../../docs/specs/m1b-benchmark-contract.md),
[corpus policy](../../docs/m1b-corpus-policy.md),
[quality rubric](../../docs/specs/m1b-quality-rubric.md), and
[threat model](../../docs/m1b-threat-model.md) define the protocol currently
under review. The offline [synthetic fixture contract](../../fixtures/m1b/README.md)
is checked by [`m1b_contract.py`](m1b_contract.py) without Ollama, network, corpus,
game, Workshop, launcher, or active-path access.

Passing this synthetic conformance gate does not evaluate model quality:
`M1B: NOT_EVALUATED`, `M1A: BLOCKED`, and `M2: FORBIDDEN` remain in force.
