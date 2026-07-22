# Owner signoff M1B-1A1-AUTH

- Milestone: `M1B-1A1-AUTH — bounded candidate-construction authorization`
- Decision content: `acceptance_state=owner_accepted`
- Operational review state: `M1B-1A1-AUTH: READY_FOR_OWNER_REVIEW`
- Effect: `after_review_and_merge_to_main`
- Pre-effect candidate state: `CANDIDATE CONSTRUCTION: NOT_AUTHORIZED_UNTIL_AUTH_MERGE`
- Runtime envelope: `RUNTIME_ENVELOPE_CONSTRUCTION: NOT_AUTHORIZED`
- M1B-1A0 provenance: PR #8 exact head `6a2243ad803bf47056f2577013053b6abc2df020`, merged as `bfe3faaaf1c13021f4ecc62b7c584bc28ba964bc`
- Executable admission: `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`
- Provider execution: `M1B-1A PROVIDER EXECUTION: NOT_STARTED`
- Dependent gates: `M1B: NOT_EVALUATED`; `M1A: BLOCKED`; `M2: FORBIDDEN`

## Решение владельца и момент effect

Владелец делегировал подготовку exact machine-readable authorization только на
будущее candidate construction. Отдельный
[`owner authorization record`](M1B-1A1-AUTH-owner-authorization.json) содержит
`acceptance_state=owner_accepted` и
`owner_delegation=explicit_candidate_construction_only`.

Это содержимое решения ещё не является действующим operational authority.
До отдельного owner review и merge exact AUTH artifacts в `main` state остаётся
`owner_review_required`, а candidate construction запрещён. Effect возникает
только после обоих событий. Commit, push, draft PR или один лишь merge без
owner review не заменяют условие решения и не являются executable trust root.

## Exact scope identity

Владелец принимает на review только scope
[`m1b-1a1-candidate-construction-scope-v1.json`](../../registry/m1b/m1b-1a1-candidate-construction-scope-v1.json)
с exact identity:

| Поле | Значение |
|---|---|
| Schema / generation | `m1b-1a1-candidate-construction-scope-v1` / `1` |
| Canonical bytes | `6447` |
| Raw SHA-256 | `443b1ed941dd8516ff91fed4ba6109fa7cd36384b87309dade03a18068d36262` |
| Framing domain | `stellaris-m1b-1a1-candidate-construction-scope-v1` |
| Framed SHA-256 | `f0e044bb52a53ee55eaf35ad189fefd22c10dd3439ba6b102721639713cd9d87` |

Canonical scope — compact sorted-key ASCII JSON плюс один LF. Framed digest
использует domain, NUL, unsigned 64-bit big-endian length exact canonical bytes
вместе с LF и сами bytes. Scope self-hash не содержит; hashes находятся в
отдельном owner record. Owner record и оба Markdown artifacts связываются
reviewed merge provenance, поэтому circular identity отсутствует.

Полный normative contract:
[`m1b-1a1-candidate-construction-authorization-contract.md`](../specs/m1b-1a1-candidate-construction-authorization-contract.md).

## Делегированный scope

После effect отдельный M1B-1A1 сможет создать только четыре inert role files:

- `analysis_engine` → `tools/research/m1b_1a1_candidate/analysis_engine.py`;
- `contract_validator` → `tools/research/m1b_1a1_candidate/contract_validator.py`;
- `provider_request_harness` → `tools/research/m1b_1a1_candidate/provider_request_harness.py`;
- `synthetic_fixture_materializer` → `tools/research/m1b_1a1_candidate/synthetic_fixture_materializer.py`.

Machine scope exact bind-ит `18` read-only base inputs их raw SHA-256,
перечисляет `4` post-merge AUTH inputs и закрывает future write set ровно на
`13` paths. Read и write default deny; status-only read/modify и static
exact-byte readback доступны только перечисленным paths. Proposed manifest —
только reviewable proposal, не admission.

Никакой authority не делегируется на `__init__.py`, дополнительные source или
import helpers, executable bit, symlink/hardlink, `.pyc`, `__pycache__`, import,
`ast.parse`, `compile`, `py_compile`, `exec`, `eval`, `runpy` или subprocess
execution candidate bytes. Future test может только статически читать exact
candidate bytes. UTF-8 или host parse/compile не доказывают interpreter
eligibility.

## Явно не принято

Этот signoff не принимает и даже после effect не разрешает:

- execution/runtime envelope или invocation plan;
- implementation/runtime acceptance record;
- operational `owner_accepted` executable identity или TCB admission;
- interpreter selection/copy/admission или candidate execution;
- provider/Ollama/model call, metadata probe или model-store read;
- official/private corpus, mods, Workshop, Stellaris, launcher, active playset;
- prompt/template bytes, translation input/output;
- benchmark, tuning, holdout, human scoring или feasibility verdict;
- product CLI, M2, activation или publishing.

## Preserved identities and blockers

M1B-1A0 machine group должен остаться `4/4` byte-identical к exact PR #8 head,
а M1B-0F/historical protected group — `8/8` byte-identical. Неизменные
контрольные identities:

- contract raw SHA-256 `fd5e54a8c4b03b6a9c0a62b715ce6d8b2eac070965467bd2de0dbe772808ce6f`;
- contract framed SHA-256 `ad6bce1a5c516753d79ee0d807f5445e9b860a398e661adfb9730d9c4fee9c31`;
- owner-freeze snapshot `df84871be332ee52c315d0c0cc1a7a0046251352a2a0131382b5cb994cffcb58`;
- definition bundle `50f51b3cf9be042ebc310d1a6c57791dd31a43362778798455d7ea9678c31e06`.

Сохраняются `EXECUTABLE_TCB_OWNER_DECISION_REQUIRED`,
`EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN`,
`PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN`,
`INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN`,
`LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN`, `ROLE_IMPORT_TRANSPORT_UNPROVEN`, native
dependency, context/output, persistence, residency и lifecycle blockers,
missing frozen prompt/template bytes, real candidate identities и
`PARTIAL_REPORT_CANNOT_BE_COMPLETE`.

## Validation boundary

AUTH review требует Python `3.9.6`, independent canonical/hash reproduction,
closed schema и exact path-set checks, targeted TCB `89/89`, full research
discovery `266/266`, Markdown `0` errors, clean diff check, exact changed-path
allowlist, protected parity, repository sentinel/leakage review и final
local/upstream/remote/PR-head parity. Targeted suite не называется полной
canonical/provider/benchmark validation. Private corpus не читался, поэтому
repository sentinel и полный diff review не выдаются за private-corpus proof.

Prepared review validation на exact AUTH bytes:

- canonical scope и raw/framed identities независимо воспроизведены;
- closed sets: `18` base inputs, `4` AUTH inputs, `4` roles, `13` outputs;
- targeted M1B TCB suite: `89/89`;
- full research discovery: `266/266`;
- Markdown: `39` files, `44` fenced blocks, `61` tables, `101` relative links,
  `0` errors;
- M1B-1A0 machine parity: `4/4`; protected M1B parity: `8/8`;
- worktree diff check и repository leakage sentinels: `PASS`.

Final commit/upstream/remote/PR-head parity и exact committed changed-path range
фиксируются внешним handoff и draft PR body: committed signoff намеренно не
содержит собственный будущий Git SHA.

## Gate

```text
M1B-1A0 CONTRACT: ACCEPTED/MERGED
M1B-1A1-AUTH: READY_FOR_OWNER_REVIEW
CANDIDATE CONSTRUCTION: NOT_AUTHORIZED_UNTIL_AUTH_MERGE
RUNTIME_ENVELOPE_CONSTRUCTION: NOT_AUTHORIZED
EXECUTABLE_TCB_ADMISSION: NOT_GRANTED
EXECUTABLE_TCB_OWNER_DECISION_REQUIRED: PRESERVED
PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN: PRESERVED
EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN: PRESERVED
INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN: PRESERVED
LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN: PRESERVED
ROLE_IMPORT_TRANSPORT_UNPROVEN: PRESERVED
M1B-1A PROVIDER EXECUTION: NOT_STARTED
M1B: NOT_EVALUATED
M1A: BLOCKED
M2: FORBIDDEN
PR: DRAFT
```

Единственный следующий шаг — owner review этого draft PR. Candidate
construction в AUTH-задании запрещён.
