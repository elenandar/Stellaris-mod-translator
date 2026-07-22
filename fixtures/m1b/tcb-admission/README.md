# M1B executable/TCB admission adversarial fixtures

`cases.json` is public, synthetic and explicitly untrusted test material for
the M1B-1A0 generation-4 contract-only verifier. It contains mutation
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

The final v5 table has `241` unique cases: one synthetic success and `240`
controlled failures. Exact fixture identity is `73746` compact sorted-key
UTF-8 JSON bytes plus one LF, with
diagnostic SHA-256
`b729305612bdf5f3e88d42a90603cf6a10b2100bd31b144c28399a155984d862`.
These values were independently recalculated; identities from superseded
contract generations 1, 2, and 3 are not evidence for contract v4. The
superseded public fixture schema v4 and its identity are not evidence for the
current fixture schema v5.

The table covers the closed manifest, unchanged five-field implementation
acceptance, new 16-field runtime acceptance, canonical envelope framed digest,
closed execution plan, typed repository locators, exact interpreter and
`/dev/fd/3` argv surfaces, atomic cached-provider pipe transport, explicit
launcher blockers, all-four-role linkage, non-empty imports/sys-path, stale bytecode and native blockers. Deep envelope
mutations explicitly refresh runtime acceptance linkage so they reach the deep
validator; a separate coherent-state mutation intentionally leaves the runtime
record stale and must fail on envelope binding.

The v5 additions preserve the external owner-decision and provider-source
eligibility blockers against deletion, rename and ordering drift. They also
exercise coherent cwd/`sys_path` reuse, unique path-bearing imports and every
representable source/extension/interpreter/manifest/provider-to-native purpose
collision. The single positive case exercises all three intentional cached
reuse profiles; generated tests separately count opens and reads to prove that
allowed cached binding does not reopen a pathname.

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

Injected directory physical aliases, case-insensitive APFS aliases, directory
replacement/metadata/stat/close faults, mid-protocol FD substitution and
provider payloads containing invalid UTF-8, NUL or invalid Python syntax also
remain generated tests. Those provider payloads may satisfy only synthetic
shape/linkage; the exact launcher and global
`PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN` blocker remains mandatory.

For every controlled CLI failure the tests require a non-zero exit, empty
stderr, an allowlisted compact result and no path, input, digest, marker,
exception or traceback leakage. Descriptor lifecycle tests account for every
opened descriptor and use a saved native close only to clean up descriptors
which an intentionally injected close failure leaves open. Transport-specific
tests additionally require one full atomic write, writer close before any
possible child, exact readback plus EOF, correct pipe access modes and
non-inheritability, pre/post FIFO/access/physical-identity checks, rejection of
reused/substituted descriptors, and cached-byte stability after the source
pathname changes. This does not claim protection from hostile same-process
monkeypatching and does not prove a future launcher.

Run from the repository root:

```sh
python3 -m unittest tools.research.tests.test_m1b_tcb_contract -v
```

Passing this synthetic matrix means only `SYNTHETIC_CONFORMANCE_ONLY`. A
fixture hash, expected result, Git identity, verifier self-report or
caller-supplied record is not a trust root and cannot grant executable TCB,
`M1B-1A1-AUTH`, candidate construction, provider, Ollama, corpus, benchmark or
M2 admission.
