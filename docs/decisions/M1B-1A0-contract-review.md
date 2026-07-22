# Contract review M1B-1A0

- Milestone: `M1B-1A0 — Offline executable/TCB admission contract`
- Review state: `M1B-1A0 CONTRACT: READY_FOR_REVIEW`
- Admission state: `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`
- Implementation identity: `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN: PRESERVED`
- Provider execution: `M1B-1A PROVIDER EXECUTION: NOT_STARTED`
- Review date: `2026-07-22`

Этот record фиксирует review identity отдельного contract-only слоя. Он не
является owner acceptance record, implementation manifest, runtime admission,
provider capability, benchmark report или feasibility verdict.

## Approved starting point

- PR #7 head `4c849f528a468545f7c5d39d6c7fddf5b23a066d` merged в `main` как
  `424a4e45066cfbff3f9b3da2ec2cf6ad62a643fb`;
- approved base и initial branch SHA:
  `424a4e45066cfbff3f9b3da2ec2cf6ad62a643fb`;
- `STABLE_READ_HARDENING: ACCEPTED`;
- `OWNER_FREEZE: ACCEPTED`.

Новая ветка создана непосредственно от approved `origin/main`; commits PR #7
не переносились. Git provenance подтверждает review context, но не является
trust root для executable identity.

## Review identity

| Surface | Exact identity |
|---|---|
| Contract schema | `m1b-offline-executable-tcb-contract-v1` |
| Contract version / generation | `m1b-offline-executable-tcb-admission-v1` / `1` |
| Canonical contract bytes | `4848` |
| Contract raw SHA-256 | `7af6471986e194fd11a9e8cf003e92a8f534c1328b3b15ab00a043067e82a3dc` |
| Contract external framed digest | `589cf895c659b57c2f44268acfa0bf33b3c98d6cd5e6b4fea1f2f9b2500d1a5f` |
| Execution envelope | `m1b-execution-envelope-v1`, generation `1` |
| Preserved protocol | `m1b-benchmark-contract-v7`, generation `108` |
| Offline verifier SHA-256 | `32176a236096dced64587af4173ba2e7a83b514a621a9eb63f61e7b8024f0746` |
| Public fixture | `127` cases, `31521` bytes |
| Fixture SHA-256 | `99f8c109f5967b1b1f7bb11e12617788b001b63c805626def0642200a901a082` |

Canonical contract encoding и external framing независимо пересчитаны без
production verifier. Contract не содержит self-hash. Synthetic canonical
manifest имеет `738` bytes и независимо воспроизведённый framed digest
`f6914a3217e6dba50e40ae9776baf4490689abc5b7ac4ef47ddce5c47a5ca324`;
это diagnostic evidence, не authority.

Normative artifacts:

- [human-readable contract](../specs/m1b-offline-executable-tcb-admission-contract.md);
- [canonical registry](../../registry/m1b/offline-executable-tcb-contract-v1.json);
- [public synthetic fixture](../../fixtures/m1b/tcb-admission/README.md);
- [offline verifier](../../tools/research/m1b_tcb_contract.py).

## Independent review findings

Первый review pass обнаружил две pre-review ambiguity, обе исправлены до
фиксации identity:

1. `cwd` был typed, но не имел отдельной descriptor-rooted directory policy.
   Registry теперь требует `exact_rooted_nofollow_open_directory_identity`, а
   verifier проверяет missing/file/symlink/replacement/metadata drift и close
   lifecycle.
2. Lexically unique role paths могли alias-ить один inode на case-insensitive
   filesystem. Registry теперь требует четыре unique opened `(st_dev, st_ino)`
   identities и запрещает physical alias к contract/manifest/acceptance/envelope
   records; verifier и platform-independent fault tests это проверяют.

Финальный независимый read-only review frozen registry/spec/verifier/fixture
не нашёл оставшихся actionable findings.

## Validation evidence

- new verifier module: `54/54` unit tests;
- public table: `127/127` cases — `1` synthetic success и `126` controlled
  fail-closed outcomes, каждый также проверен через real verifier CLI;
- focused filesystem, cwd, lifecycle, fault-injection и leakage: `26/26` tests;
- historical owner-freeze module: `25/25` tests;
- historical M1B module: `79/79` tests и `173/173` table cases;
- full research discovery: `231/231` unit tests;
- docs validation: `37` Markdown files, `34` fenced blocks, `55` tables,
  `87` relative links, `0` errors.

Для каждого controlled CLI failure проверены non-zero exit, empty stderr,
allowlisted compact output и отсутствие path/content/hash/marker/exception/
traceback leakage. Manifest-listed synthetic role/import payloads не
импортируются и не исполняются. Все успешно открытые descriptors получают ровно
одну production close attempt; injected close failure не возвращает success.
Fixture, registry, docs и verifier содержат `0` privacy sentinels; три ожидаемых
sentinel literals (`/Users/`, `l_russian:`, `localisation/`) существуют только в
negative no-leak assertion test и не являются corpus excerpts.

## Preserved identities

- immutable accepted records/fixtures/validators: `8/8` byte-identical;
- protected M1A surface: `11/11` byte-identical;
- historical M1B proposal surface: `15/15` byte-identical;
- exact owner-freeze snapshot:
  `df84871be332ee52c315d0c0cc1a7a0046251352a2a0131382b5cb994cffcb58`;
- exact accepted definition bundle:
  `50f51b3cf9be042ebc310d1a6c57791dd31a43362778798455d7ea9678c31e06`;
- all `17` accepted component identities and implementation policy v2
  `826d976613f44657c5a2ae9299d3cc80ad21751eb7298989a24653d0849de784`;
- protocol v7/generation `108` unchanged.

## Boundaries and blockers

`SYNTHETIC_CONFORMANCE_ONLY` не выдаёт operational admission. Реальный
four-role manifest и external `owner_accepted` implementation/runtime record не
созданы. Native dependency closure сохраняет явный blocker. Также остаются:

- `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN`;
- `NATIVE_DEPENDENCY_CLOSURE_UNPROVEN`;
- `CONTEXT_LIMIT_BINDING_UNPROVEN`;
- `PROVIDER_PERSISTENCE_UNPROVEN`;
- `RESIDENCY_UNPROVEN`;
- `OUTPUT_LIMIT_BINDING_UNPROVEN`;
- `LIFECYCLE_STATE_UNPROVEN`;
- missing frozen prompt/template bytes;
- missing real candidate identities;
- `PARTIAL_REPORT_CANNOT_BE_COMPLETE`.

## Gate statement

```text
M1B-1A0 CONTRACT: READY_FOR_REVIEW
EXECUTABLE_TCB_ADMISSION: NOT_GRANTED
EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN: PRESERVED
OWNER_FREEZE: ACCEPTED
STABLE_READ_HARDENING: ACCEPTED
M1B-1A PROVIDER EXECUTION: NOT_STARTED
M1B: NOT_EVALUATED
M1A: BLOCKED
M2: FORBIDDEN
```

Следующий разрешённый шаг только после review и merge этого contract PR —
отдельное задание на реальные four-role executable surfaces и external
implementation/runtime admission. Даже merge не разрешает Ollama probe, model
call, private corpus, benchmark execution, product CLI или M2.
