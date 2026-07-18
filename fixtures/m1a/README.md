# M1A synthetic fixtures

Every byte and identifier in this directory is synthetic and intentionally
minimal.  No game, Workshop, launcher, private translation, or prior-project
file was copied to create these fixtures.

`format-cases.json` stores exact byte cases as escaped UTF-8 text or hex so BOM,
CRLF, mixed-newline, missing-final-newline, and invalid-UTF-8 evidence survives
Git and editor newline conversion.  Each case carries the expected aggregate
classification used by the research-only tests.

The manifest contains 26 cases, including isolated record siblings, empty,
unbalanced, orphan and crossing delimiters, formatting-state failures, nested
fixture-backed formatting, delimiter-like Unicode text, unsupported physical
line separators, missing value separators, control characters, and an empty
language header. Table-driven tests also check ambiguous markup and the shared
fail-closed key-extraction boundary independently.

`candidate/` contains two harmless input payloads for deterministic
disposable-root assembly tests. The built research artifact uses generated flat
storage names plus a manifest; it is never installed or written outside a
temporary test directory.
