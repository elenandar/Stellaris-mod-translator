# M1B executable/TCB admission adversarial fixtures

`cases.json` is public, synthetic and explicitly untrusted test material for
the M1B-1A0 contract-only verifier. It contains mutation instructions and
expected controlled outcomes only. It is not an executable manifest, an
external acceptance record, an execution envelope, a benchmark report, an
implementation identity or an authority source.

The four synthetic role files are materialized only by the test module inside
a temporary repository root. They are opaque byte payloads: neither the test
suite nor the production verifier imports or executes them. No executable
surface, real manifest, runtime profile or operational `owner_accepted` record
is stored in this fixture directory.

The table has `127` unique cases: one positive synthetic-conformance case and
`126` exact fail-closed mutations. Its diagnostic file SHA-256 is
`99f8c109f5967b1b1f7bb11e12617788b001b63c805626def0642200a901a082`;
that hash is regression evidence, never authority.

The table covers the closed manifest and external-linkage schemas, exact role
and path rules, canonical manifest bytes and domain-separated digest binding,
runtime/import/invocation drift, stale bytecode, native-dependency blockers and
reopened-path claims. The matrix also covers missing, regular-file and symlink
invocation cwd objects. Byte-level invalid JSON, exact/over-size limits, hostile
filesystem objects, physical-identity aliasing, short/premature reads,
metadata/entry replacement and injected read/close failures are generated
directly by the test module because those states cannot be represented
faithfully as ordinary JSON mutations.

For every controlled CLI failure the tests require a non-zero exit, empty
stderr, an allowlisted compact result and no path, input, digest, marker,
exception or traceback leakage. Descriptor lifecycle tests account for every
opened descriptor and use a saved native close only to clean up descriptors
which an intentionally injected close failure leaves open.

Run from the repository root:

```sh
python3 -m unittest tools.research.tests.test_m1b_tcb_contract -v
```

Passing this synthetic matrix means only `SYNTHETIC_CONFORMANCE_ONLY`. A
fixture hash, expected result, Git identity, verifier self-report or
caller-supplied record is not a trust root and cannot grant executable TCB,
provider, Ollama, corpus, benchmark or M2 admission.
