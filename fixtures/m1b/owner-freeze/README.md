# M1B owner-freeze adversarial fixtures

`cases.json` is public, synthetic and explicitly untrusted test material. It
contains only mutation instructions and expected controlled codes; it is not an
owner record, registry snapshot, trust identity, benchmark report or source of
acceptance.

The table has `25` cases: one exact positive case and `24` fail-closed cases.
It covers stale protocol identity, bundle drift, component addition/removal/
duplication/mutation, generation and acceptance-state drift, noncanonical row
order, unknown/missing fields, boolean-as-integer, integer-as-boolean, fake
report/fixture acceptance, blocker/gate drift and a circular self-hash attempt. Byte-level
duplicate-key, malformed UTF-8, oversize and integer-boundary cases live in the
test module because invalid bytes cannot be represented faithfully inside a
JSON fixture.

The fixture materializer exists only in the test module. The production
verifier has no fixture or report mode and accepts only the two explicit
owner-controlled record paths documented in the
[owner-freeze contract](../../../docs/specs/m1b-owner-freeze-contract.md).

Run from the repository root:

```sh
python3 -m unittest tools.research.tests.test_m1b_owner_freeze -v
```

These cases do not change the historical `173` M1B synthetic contract cases or
their `proposed` component states. Passing them does not authorize Ollama,
private corpus access, a complete benchmark or M2.
