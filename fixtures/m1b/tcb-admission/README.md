# M1B executable/TCB admission adversarial fixtures

`cases.json` is public, synthetic and explicitly untrusted test material for
the M1B-1A0 generation-3 contract-only verifier. It contains mutation
instructions and expected controlled outcomes only. It is not an executable
manifest, an implementation or runtime acceptance record, an execution
envelope, a benchmark report, an implementation identity or an authority
source.

The four synthetic role files are materialized only by the test module inside
a temporary repository root. The source-role payloads are minimal inert
synthetic Python text, while native-extension payloads remain opaque bytes;
neither the test suite nor the production verifier imports or executes them. No executable
surface, real manifest, runtime profile or operational `owner_accepted` record
is stored in this fixture directory. The temporary synthetic runtime acceptance
proves only closed shape and exact linkage; it is not an owner-controlled trust
root.

The final table has `218` unique cases: one synthetic success and `217`
controlled failures. Exact fixture identity is `61682` bytes with diagnostic
SHA-256
`0f14d9b28ee41095a2373b02409b288c30959013840d7d1c891538266a84eeaa`.
These values were independently recalculated; the superseded generation-1 and
generation-2 identities are not evidence for v3.

The table covers the closed manifest, unchanged five-field implementation
acceptance, new 16-field runtime acceptance, canonical envelope framed digest,
closed execution plan, typed repository locators, exact interpreter and
`/dev/fd/3` argv surfaces, atomic cached-provider pipe transport, explicit
launcher blockers, all-four-role linkage, non-empty imports/sys-path, stale bytecode and native blockers. Deep envelope
mutations explicitly refresh runtime acceptance linkage so they reach the deep
validator; a separate coherent-state mutation intentionally leaves the runtime
record stale and must fail on envelope binding.

The adversarial matrix must also prove that a manifest-bound entrypoint whose
raw relative path begins with ASCII `-` fails closed even when manifest, plan,
argv, both envelope states and runtime acceptance are coherently updated. This
covers `-c`, `-m`, `-`, `--`, `-E` and the general first-byte rule.

Byte-level invalid JSON, exact/over-size limits (including the `512`-byte
atomic entrypoint bound), hostile filesystem objects,
global lexical/physical aliasing, no-reopen, short/premature reads,
metadata/entry replacement and injected read/close failures are generated
directly by the test module because those states cannot be represented
faithfully as ordinary JSON mutations. Platform-independent tests cover aliases
between all input and executable surface classes and prove that an alias is
rejected before its content is read.

For every controlled CLI failure the tests require a non-zero exit, empty
stderr, an allowlisted compact result and no path, input, digest, marker,
exception or traceback leakage. Descriptor lifecycle tests account for every
opened descriptor and use a saved native close only to clean up descriptors
which an intentionally injected close failure leaves open. Transport-specific
tests additionally require one full atomic write, writer close before any
possible child, exact readback plus EOF, correct pipe access modes and
non-inheritability, rejection of reused/duplicate descriptors, and cached-byte
stability after the source pathname changes.

Run from the repository root:

```sh
python3 -m unittest tools.research.tests.test_m1b_tcb_contract -v
```

Passing this synthetic matrix means only `SYNTHETIC_CONFORMANCE_ONLY`. A
fixture hash, expected result, Git identity, verifier self-report or
caller-supplied record is not a trust root and cannot grant executable TCB,
provider, Ollama, corpus, benchmark or M2 admission.
