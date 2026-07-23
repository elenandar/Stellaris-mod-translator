# Owner signoff M1B-1A1-AUTH

- Milestone: `M1B-1A1-AUTH — bounded candidate-construction authorization`
- Decision content: `acceptance_state=owner_accepted`
- Operational review state: `M1B-1A1-AUTH: READY_FOR_OWNER_REVIEW`
- Effect: `after_review_and_merge_to_main`
- Pre-effect candidate state: `CANDIDATE CONSTRUCTION: NOT_AUTHORIZED_UNTIL_AUTH_MERGE`
- New repository code execution: `NOT_AUTHORIZED`
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

Это содержимое решения ещё не является действующим operational authority. До
отдельного owner review и merge exact AUTH artifacts в `main` state остаётся
`owner_review_required`, а candidate construction запрещён. Effect возникает
только после обоих событий. Commit, push, draft PR или один лишь merge без
owner review не заменяют условие решения и не являются executable trust root.

## Exact scope identity

Владелец принимает на review только scope
[`m1b-1a1-candidate-construction-scope-v2.json`](../../registry/m1b/m1b-1a1-candidate-construction-scope-v2.json)
с exact identity:

| Поле | Значение |
|---|---|
| Schema / generation | `m1b-1a1-candidate-construction-scope-v2` / `2` |
| Canonical bytes | `11157` |
| Raw SHA-256 | `c757c7c7c6bd6f35c4c068fa45fc2543ef0f9aaa37f3fe18bb7d7926c1cc6294` |
| Framing domain | `stellaris-m1b-1a1-candidate-construction-scope-v2` |
| Framed SHA-256 | `0c0a277598e1466dc764692dc4fe81abbb264e175a7cdc9205c2fe8e4cc8c9d1` |

Canonical scope — compact sorted-key ASCII JSON плюс один LF. Framed digest
использует domain, NUL, unsigned 64-bit big-endian length exact canonical bytes
вместе с LF и сами bytes. Scope self-hash не содержит; hashes находятся в
отдельном owner record. Owner record и оба Markdown artifacts связываются
reviewed merge provenance, поэтому circular identity отсутствует.

Полный normative contract:
[`m1b-1a1-candidate-construction-authorization-contract.md`](../specs/m1b-1a1-candidate-construction-authorization-contract.md).

## Делегированный content scope

После effect отдельный M1B-1A1 сможет создать только четыре inert role files:

- `analysis_engine` → `tools/research/m1b_1a1_candidate/analysis_engine.py`;
- `contract_validator` → `tools/research/m1b_1a1_candidate/contract_validator.py`;
- `provider_request_harness` → `tools/research/m1b_1a1_candidate/provider_request_harness.py`;
- `synthetic_fixture_materializer` → `tools/research/m1b_1a1_candidate/synthetic_fixture_materializer.py`.

Machine scope exact bind-ит `18` read-only base inputs, `4` post-merge AUTH
inputs, `4` role paths, `4` future directories и `12` future outputs. Из
outputs `11` tracked, а sanitized ignored evidence остаётся только под
`artifacts/`. Proposed manifest — только reviewable proposal, не admission;
`cases.json` — только inert data.

Exact future-directory authority:

| Path | Required parent | Mode | Purpose |
|---|---|---:|---|
| `artifacts/m1b` | pre-existing real `artifacts` | `0700` | sanitized ignored M1B evidence parent |
| `artifacts/m1b/m1b-1a1` | authorized predecessor `artifacts/m1b` | `0700` | sanitized ignored M1B-1A1 evidence parent |
| `fixtures/m1b/candidate-construction` | pre-existing real `fixtures/m1b` | `0755` | tracked inert synthetic fixture parent |
| `tools/research/m1b_1a1_candidate` | pre-existing real `tools/research` | `0755` | tracked inert candidate-role source parent |

Каждый каталог разрешён только create-if-absent как real directory: symlink,
replacement и deletion запрещены. Другой каталог создавать нельзя. Parent
closure всех `12` outputs полностью покрыт существующими real directories и
этими четырьмя rows.

## Разделённые плоскости полномочий

Repository content plane default-deny. Semantic reads ограничены `18` exact
SHA-bound base inputs, четырьмя exact post-merge AUTH inputs и static-byte
readback exact future outputs. Metadata-only `lstat`/`stat` ограничены exact
scope paths и их exact lexical parent closure. После effect content writes
ограничены `12` future files и четырьмя create-only directories.

Отдельный bounded Git/GitHub control plane после effect разрешает только
`origin`/`elenandar/Stellaris-mod-translator`: fetch/read preflight, проверку PR
#9 и merge commit, одну ветку
`agent/m1b-1a1-inert-candidate-construction` от этого exact merge commit,
staging только `tracked=true` outputs, ordinary commit, non-force push и один
draft PR этой ветки. `.git` locks/index/objects/refs могут меняться только как
следствие этих операций. Main mutation, force, published-branch rebase,
merge/auto-merge, ready-for-review, другие PR, tags/releases/Actions и другой
network запрещены. Выбор и исполнение bounded system validation tool по
перечисленной цели разрешены, но не являются candidate/provider interpreter
selection и не создают admission evidence.

Bounded host validation после effect разрешает pre-existing SHA-bound или
system tools только для Git/GitHub preflight, SHA/canonical reproduction,
type/mode/link/path checks, static exact-byte analysis, scoped diff checks,
Markdown links в изменённых future docs и sanitized ignored evidence. Их
executable/runtime/stdlib bytes — только implementation dependencies, не
candidate semantic inputs и не interpreter-admission evidence. Обязательны
`PYTHONDONTWRITEBYTECODE=1`, отсутствие `.pyc`/`__pycache__`, отсутствие import
или execution любого вновь созданного repository file и отдельный запрет
parse/compile candidate source. Static data/Markdown validation остаётся
разрешённой только для перечисленных host-validation purposes.

## Явно не принято

Scope не содержит `tools/research/tests/test_m1b_1a1_candidate.py` и не
разрешает replacement `.py`, shell script или executable fixture. Никакой
authority не делегируется на `__init__.py`, дополнительные source/import files,
execute bits, symlink/hardlink, `.pyc`, `__pycache__`, `ast.parse`, language
parse, `compile`, `py_compile`, import, `exec`, `eval`, `runpy`, subprocess или
любое другое execution созданных repository bytes.

Этот signoff также не принимает и даже после effect не разрешает:

- execution/runtime envelope или invocation plan;
- implementation/runtime acceptance record;
- operational `owner_accepted` executable identity или TCB admission;
- candidate/provider runtime interpreter selection/copy и любой interpreter
  admission; bounded validation-tool selection остаётся только validation;
- provider/model/benchmark runtime execution;
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

Сохраняются все `16` machine blockers: executable owner/identity/source,
interpreter path, launcher byte chain, role transport, native dependency,
context/output, persistence, residency и lifecycle blockers, а также
`MISSING_PROMPT_BYTES`, `MISSING_TEMPLATE_BYTES`,
`MISSING_REAL_CANDIDATE_IDENTITIES` и `PARTIAL_REPORT_CANNOT_BE_COMPLETE`.

## Validation boundary

AUTH remediation требует Python `3.9.6`, независимую canonical reproduction,
две raw/framed hash reproductions, closed schema/path/parent checks, targeted
TCB `89/89`, full research discovery `266/266`, Markdown `0` errors,
`git diff --check`, exact six-path AUTH diff, M1B-1A0 `4/4` и protected M1B
`8/8` byte parity, repository sentinel/leakage review и final
local/upstream/remote/PR-head parity. Targeted suite не называется полной
canonical/provider/benchmark validation. Private corpus не читался, поэтому
repository sentinel и полный diff review не выдаются за private-corpus proof.

Prepared remediation validation на exact AUTH working bytes:

- Python: `3.9.6`; canonical scope и raw/framed identities независимо
  воспроизведены двумя methods;
- closed sets и hashes: `18 / 4 / 4 / 4 / 12`, base SHA rows `18/18`;
- parent-chain closure: `12/12`; executable test output: absent;
- targeted M1B TCB suite: `89/89`;
- full research discovery: `266/266`;
- Markdown: `39` files, `44` fenced blocks, `63` tables, `101` relative links,
  `0` errors;
- M1B-1A0 machine parity: `4/4`; protected M1B parity: `8/8`;
- exact six-path diff, diff check, no-bytecode и repository sentinels: `PASS`.

Final commit/upstream/remote/PR-head parity и exact committed changed-path range
фиксируются внешним handoff и draft PR body: committed signoff намеренно не
содержит собственный будущий Git SHA.

## Gate

```text
REMEDIATION: READY_FOR_REVIEW
M1B-1A1-AUTH: READY_FOR_OWNER_REVIEW
CANDIDATE CONSTRUCTION: NOT_AUTHORIZED_UNTIL_AUTH_MERGE
NEW REPOSITORY CODE EXECUTION: NOT_AUTHORIZED
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
