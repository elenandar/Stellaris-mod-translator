# M1B-1A1-AUTH — bounded candidate-construction authorization contract

- Milestone: `M1B-1A1-AUTH — authorization only`
- Разрешённый слой: owner-controlled scope для будущего offline candidate construction
- Рекомендуемая модель Codex: `GPT-5.6 Sol`
- Уровень рассуждения: `Ultra`
- Contract schema: `m1b-1a1-candidate-construction-scope-v1`
- Generation: `1`
- Owner record: `m1b-1a1-candidate-construction-owner-authorization-v1`
- Review state до effect: `M1B-1A1-AUTH: READY_FOR_OWNER_REVIEW`
- Effect: `after_review_and_merge_to_main`
- Candidate state до effect: `CANDIDATE CONSTRUCTION: NOT_AUTHORIZED_UNTIL_AUTH_MERGE`
- Runtime envelope: `RUNTIME_ENVELOPE_CONSTRUCTION: NOT_AUTHORIZED`
- Base provenance: PR #8 head `6a2243ad803bf47056f2577013053b6abc2df020`, merged в `main` как `bfe3faaaf1c13021f4ecc62b7c584bc28ba964bc`

## 1. Назначение и граница решения

Этот contract определяет только узкую будущую возможность создать exact набор
reviewable offline outputs. Текущий AUTH-этап не создаёт candidate source,
manifest, execution envelope, invocation plan, test, fixture или evidence из
будущего write set; ничего не импортирует, не компилирует и не исполняет.

Machine owner record содержит `acceptance_state=owner_accepted`, поскольку
фиксирует точное решение, делегированное владельцем. Это значение не активирует
ветку или draft PR. До отдельного owner review и merge этих exact bytes в
`main` operational state остаётся `owner_review_required`. Только совместное
выполнение обоих условий включает effect
`after_review_and_merge_to_main`; ни commit, ни push, ни открытие draft PR по
отдельности authority не создают.

После effect разрешено только candidate construction в exact scope ниже.
Proposed manifest остаётся предложением identity для review и не является
executable admission. Merge provenance связывает exact reviewed AUTH bytes, но
не является executable trust identity.

## 2. Normative scope identity

Authoritative scope —
[`registry/m1b/m1b-1a1-candidate-construction-scope-v1.json`](../../registry/m1b/m1b-1a1-candidate-construction-scope-v1.json).
Его identity:

| Поле | Значение |
|---|---|
| Schema / generation | `m1b-1a1-candidate-construction-scope-v1` / `1` |
| Canonical byte length | `6447` bytes |
| Raw SHA-256 | `443b1ed941dd8516ff91fed4ba6109fa7cd36384b87309dade03a18068d36262` |
| Framing domain | `stellaris-m1b-1a1-candidate-construction-scope-v1` |
| Framed SHA-256 | `f0e044bb52a53ee55eaf35ad189fefd22c10dd3439ba6b102721639713cd9d87` |

Canonical bytes — ASCII JSON с sorted object keys, compact separators и ровно
одним terminal LF. BOM, CRLF, второй LF, duplicate object key, float,
NaN/Infinity, lone surrogate и `bool` вместо generation запрещены. Terminal LF
входит и в raw digest, и в framed length.

Raw digest вычисляется над exact canonical bytes. Framed digest:

```text
SHA-256(
  ASCII("stellaris-m1b-1a1-candidate-construction-scope-v1") ||
  NUL ||
  u64be(6447) ||
  canonical_scope_bytes
)
```

Scope не содержит self-hash. Отдельный
[`owner authorization record`](../decisions/M1B-1A1-AUTH-owner-authorization.json)
bind-ит schema, generation, length, raw digest, framing domain и framed digest.
Exact owner record, этот contract и
[`owner signoff`](../decisions/M1B-1A1-AUTH-owner-signoff.md) связываются
reviewed merge provenance. Такая схема не создаёт circular self-hash.

## 3. Closed schemas и path policy

Scope root closed и имеет ровно поля:

```text
authorization_inputs_after_merge
authorized_action
candidate_roles
constraints
future_outputs
generation
preserved_blockers
prohibited_actions
read_only_inputs
read_policy
schema
write_policy
```

Row schemas также closed:

- `authorization_inputs_after_merge`: ровно `identity_binding`, `path`;
- `candidate_roles`: ровно `path`, `role`;
- `future_outputs`: ровно `path`, `write_kind`;
- `read_only_inputs`: ровно `path`, `sha256`.

Owner record closed по exact полям, находящимся в committed JSON; extra или
missing field запрещён. Все permission fields имеют exact JSON boolean, а
`scope_canonical_bytes` и `scope_generation` — positive exact integer, не
`bool`.

Каждый path — non-empty repository-relative POSIX raw-ASCII string. Запрещены
absolute path, leading/trailing или repeated separator, пустой component, `.` и
`..`, backslash, NUL, ASCII control/DEL и non-ASCII. Внутри каждого
path-bearing array path уникален и rows расположены по
`path.encode("ascii")`; ambient locale не участвует. Symlink не может изменить
lexical или physical target.

Read policy — default deny. Разрешены только exact SHA-bound base inputs,
четыре post-merge authorization inputs и static exact-byte read/readback exact
future-output paths. Existing status-only files можно читать только для
ограниченного status/link update и его проверки. Write policy — default deny:
после effect доступны только exact future outputs. Минимальное создание
отсутствующей parent-directory chain допустимо только как необходимый container
для перечисленного output; другие directory entries запрещены.

## 4. Exact candidate roles

После effect допускаются ровно четыре новых inert source-файла:

| Role | Repository path |
|---|---|
| `analysis_engine` | `tools/research/m1b_1a1_candidate/analysis_engine.py` |
| `contract_validator` | `tools/research/m1b_1a1_candidate/contract_validator.py` |
| `provider_request_harness` | `tools/research/m1b_1a1_candidate/provider_request_harness.py` |
| `synthetic_fixture_materializer` | `tools/research/m1b_1a1_candidate/synthetic_fixture_materializer.py` |

Role/path mapping exact и one-to-one. Другой source, import helper или
executable file запрещён. В частности, запрещены `__init__.py`, `.pyc`,
`__pycache__`, executable bit, symlink и hardlink; каждый candidate path должен
быть новым regular file с `st_nlink=1` и без execute bits.

Candidate bytes нельзя импортировать, передавать `ast.parse`, `compile` или
`py_compile`, исполнять через `exec`, `eval`, `runpy` или subprocess либо иным
образом загружать как code. Успешный UTF-8 decode, host-side parse/compile или
static source review не доказывает eligibility для ещё не принятого exact
interpreter.

## 5. Exact future output allowlist

После effect будущий отдельный M1B-1A1 может read/modify/write только эти `13`
file paths в указанном raw-ASCII порядке:

| Path | Write kind |
|---|---|
| `README.md` | `status_only` |
| `artifacts/m1b/m1b-1a1/candidate-construction-evidence.json` | `ignored_evidence` |
| `docs/decisions/M1B-1A1-candidate-review.md` | `candidate_review_record` |
| `docs/roadmap.md` | `status_only` |
| `fixtures/m1b/candidate-construction/README.md` | `synthetic_fixture_documentation` |
| `fixtures/m1b/candidate-construction/cases.json` | `synthetic_fixture_data` |
| `registry/m1b/m1b-1a1-proposed-executable-manifest-v1.json` | `proposed_manifest` |
| `tools/research/README.md` | `status_only` |
| `tools/research/m1b_1a1_candidate/analysis_engine.py` | `candidate_source` |
| `tools/research/m1b_1a1_candidate/contract_validator.py` | `candidate_source` |
| `tools/research/m1b_1a1_candidate/provider_request_harness.py` | `candidate_source` |
| `tools/research/m1b_1a1_candidate/synthetic_fixture_materializer.py` | `candidate_source` |
| `tools/research/tests/test_m1b_1a1_candidate.py` | `static_candidate_test` |

Ignored evidence остаётся только под уже ignored `artifacts/`. Status-only
paths могут менять только текущий gate/status и ссылки на новые records. Test
может исполняться как host-side test harness, но candidate paths он только
статически читает как bytes: import, parse, compile или execution candidate
запрещены. Все остальные repository или filesystem writes запрещены.

## 6. Exact read-only base inputs

Следующие `18` exact files читаются только при совпадении raw SHA-256 с
проверенным post-merge PR #8 base:

| Path | Raw SHA-256 |
|---|---|
| `AGENTS.md` | `b8f2b659152ba6a4405081ff003a4a4f54c956868004163d06c794c74a022137` |
| `docs/decisions/M1B-0F-owner-freeze.json` | `880dacd664894c9be6c924cda79108f7ae36176177d26d5e4bb8efbe4952fb2d` |
| `docs/decisions/M1B-0F-owner-signoff.md` | `79a6b6d6ff55d7d409c515c5c068d552e6be840bbe8d687b9f1e431b57bae6a4` |
| `docs/decisions/M1B-1A0-contract-review.md` | `26ddc28ed1671138c1981be52b81871e4ad5e3980e58c64d8841bc204411d26a` |
| `docs/m1b-corpus-policy.md` | `8afc2c27ec3555918522c1f4d26133e7f765f449bc39b9a5dbbb2316b5f224a8` |
| `docs/m1b-threat-model.md` | `20542bc8580fb35a9d7118c485300d10d64a9c88725ddab71ad198ddf5a4b469` |
| `docs/specs/m1b-benchmark-contract.md` | `2c46b1e22d49806529166fb56e42ea364bcda1364fcf26bda8d7d47184718669` |
| `docs/specs/m1b-offline-executable-tcb-admission-contract.md` | `8cfee3b0e28dac105bd9d51114288f9f70ef849ec45e8afb3ad72681f13b5d34` |
| `docs/specs/m1b-owner-freeze-contract.md` | `de5b05f21d604707d76cf1385b19adf84576e430ae3bf6a6da728f85ab1d3914` |
| `docs/specs/m1b-quality-rubric.md` | `b31e626be6ed1453ab21f7d74d5e7b1a79919e1f69f821fdacd158366bc2c6ad` |
| `fixtures/m1b/contract-cases.json` | `ec2f958ce90fd5e97036b3658ae0a5a3f946aebe75c83b02b6998c3639133cb2` |
| `fixtures/m1b/tcb-admission/cases.json` | `b729305612bdf5f3e88d42a90603cf6a10b2100bd31b144c28399a155984d862` |
| `registry/m1b/offline-executable-tcb-contract-v4.json` | `fd5e54a8c4b03b6a9c0a62b715ce6d8b2eac070965467bd2de0dbe772808ce6f` |
| `registry/m1b/owner-freeze-v7-g108.json` | `1326e7a181e63aea66ead1735297fc8d0330c8b86860d5ddd9b360752e43fe02` |
| `tools/research/m1b_contract.py` | `b8cf9eab49b6bf65c1548f6dc9cefb5241aa9d6c73f46995ca1fe5174ef35353` |
| `tools/research/m1b_tcb_contract.py` | `242b115d6eb8f7df143eeeccc94c2b7029dc1a7b601d9a29bd436a183e446551` |
| `tools/research/tests/test_m1b_contract.py` | `25b5b277a7c25a2053db757e18b1ae65622775fceb859c73ee1d2192d652bc0c` |
| `tools/research/tests/test_m1b_tcb_contract.py` | `ebf121bb34a34dedd908c91a9cc414e8aff0ffe71b3146448cd689a37d54edb0` |

`df84871be332ee52c315d0c0cc1a7a0046251352a2a0131382b5cb994cffcb58`
остаётся semantic owner-freeze snapshot identity, а не raw file SHA. Поэтому
row для `registry/m1b/owner-freeze-v7-g108.json` правильно использует raw digest
`1326e7a1…`.

## 7. Post-merge authorization inputs

После merge эти четыре AUTH artifacts становятся read-only inputs будущего
M1B-1A1:

| Path | Identity binding |
|---|---|
| `docs/decisions/M1B-1A1-AUTH-owner-authorization.json` | exact reviewed merge bytes |
| `docs/decisions/M1B-1A1-AUTH-owner-signoff.md` | exact reviewed merge bytes |
| `docs/specs/m1b-1a1-candidate-construction-authorization-contract.md` | exact reviewed merge bytes |
| `registry/m1b/m1b-1a1-candidate-construction-scope-v1.json` | owner-record raw/framed SHA-256 plus exact reviewed merge bytes |

Future preflight обязан доказать, что AUTH bytes находятся в reviewed merge в
`main`, scope hashes совпадают, а все `18` base inputs сохранили exact raw
digests. Любой drift, missing/extra path, schema mismatch или неоднозначный
merge provenance останавливает construction.

## 8. Explicit non-authority

Даже после effect этот AUTH не разрешает:

- execution envelope, runtime envelope или invocation plan;
- implementation/runtime acceptance record и executable TCB admission;
- operational `owner_accepted` executable identity;
- выбор, копирование или admission interpreter;
- импорт, compile или execution candidate role bytes;
- provider, Ollama или model call, metadata probe либо model-store read;
- official/private corpus, mods, Workshop, Stellaris, launcher или active playset;
- реальные prompt/template bytes, translation inputs/outputs;
- benchmark, tuning, holdout, human scoring или feasibility verdict;
- product CLI, M2, activation или publishing.

Earlier umbrella prose о возможном future envelope evidence этим более поздним
exact AUTH не активируется: write allowlist не содержит envelope path, а
`RUNTIME_ENVELOPE_CONSTRUCTION: NOT_AUTHORIZED` имеет приоритет для M1B-1A1.

## 9. Preserved artifacts, identities и blockers

M1B-1A0 machine surfaces остаются byte-identical к exact PR #8 head: contract
registry, TCB fixture v5, verifier и verifier tests. Execution-envelope v4,
execution-plan v3 и runtime-acceptance v1 synthetic identities внутри этих
surfaces не меняются. M1B-0F и historical protected group также неизменны.

Контрольные identities:

- contract raw SHA-256: `fd5e54a8c4b03b6a9c0a62b715ce6d8b2eac070965467bd2de0dbe772808ce6f`;
- contract framed SHA-256: `ad6bce1a5c516753d79ee0d807f5445e9b860a398e661adfb9730d9c4fee9c31`;
- owner-freeze registry snapshot: `df84871be332ee52c315d0c0cc1a7a0046251352a2a0131382b5cb994cffcb58`;
- definition bundle: `50f51b3cf9be042ebc310d1a6c57791dd31a43362778798455d7ea9678c31e06`.

Ни один blocker не снят, включая:

- `EXECUTABLE_TCB_OWNER_DECISION_REQUIRED`;
- `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN`;
- `PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN`;
- `INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN`;
- `LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN`;
- `ROLE_IMPORT_TRANSPORT_UNPROVEN`;
- native dependency, context/output, persistence, residency и lifecycle blockers;
- missing frozen prompt/template bytes, real candidate identities и
  `PARTIAL_REPORT_CANNOT_BE_COMPLETE`.

## 10. Required validation and stop conditions

Перед publication обязательны Python `3.9.6`, независимая canonical/hash
reproduction, closed root/row and exact path-set validation, targeted TCB suite
`89/89`, full research discovery `266/266`, Markdown validation с `0` errors,
`git diff --check`, exact six-path AUTH diff allowlist, M1B-1A0 `4/4` и protected
M1B `8/8` byte parity, repository sentinel/leakage review и clean committed
local/upstream/remote/PR-head parity. Targeted TCB suite остаётся targeted и не
называется full canonical/provider/benchmark validation.

Любой hash/schema/path/count drift, unexpected skip, дополнительный tracked
path, leakage sentinel, dirty tree, remote divergence или не-draft PR даёт
fail-closed stop. AUTH не создаёт fixture или executable, не запускает Ollama и
не читает private corpus для leakage proof; repository-only sentinel scan и
полный diff review честно не называются private-corpus proof.

## 11. Gate state

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

Единственный следующий шаг — owner review draft PR. Candidate construction в
этом AUTH-задании запрещён.
