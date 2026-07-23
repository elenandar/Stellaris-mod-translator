# M1B-1A1-AUTH — bounded candidate-construction authorization contract

- Milestone: `M1B-1A1-AUTH — authorization only`
- Разрешённый слой: owner-controlled scope для будущего offline candidate construction
- Рекомендуемая модель Codex: `GPT-5.6 Sol`
- Уровень рассуждения: `Ultra`
- Contract schema: `m1b-1a1-candidate-construction-scope-v2`
- Generation: `2`
- Owner record: `m1b-1a1-candidate-construction-owner-authorization-v2`
- Review state до effect: `M1B-1A1-AUTH: READY_FOR_OWNER_REVIEW`
- Effect: `after_review_and_merge_to_main`
- Candidate state до effect: `CANDIDATE CONSTRUCTION: NOT_AUTHORIZED_UNTIL_AUTH_MERGE`
- New repository code execution: `NOT_AUTHORIZED`
- Runtime envelope: `RUNTIME_ENVELOPE_CONSTRUCTION: NOT_AUTHORIZED`
- Base provenance: PR #8 head `6a2243ad803bf47056f2577013053b6abc2df020`, merged в `main` как `bfe3faaaf1c13021f4ecc62b7c584bc28ba964bc`

## 1. Назначение и граница решения

Этот contract определяет только узкую будущую возможность создать exact набор
reviewable offline outputs. Текущий AUTH-этап не создаёт candidate source,
manifest, directory, fixture или evidence из будущего scope; ничего не
импортирует, не парсит как code, не компилирует и не исполняет. Candidate
construction начаться в этом PR не может.

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
[`registry/m1b/m1b-1a1-candidate-construction-scope-v2.json`](../../registry/m1b/m1b-1a1-candidate-construction-scope-v2.json).
Его identity:

| Поле | Значение |
|---|---|
| Schema / generation | `m1b-1a1-candidate-construction-scope-v2` / `2` |
| Canonical byte length | `11157` bytes |
| Raw SHA-256 | `c757c7c7c6bd6f35c4c068fa45fc2543ef0f9aaa37f3fe18bb7d7926c1cc6294` |
| Framing domain | `stellaris-m1b-1a1-candidate-construction-scope-v2` |
| Framed SHA-256 | `0c0a277598e1466dc764692dc4fe81abbb264e175a7cdc9205c2fe8e4cc8c9d1` |

Canonical bytes — ASCII JSON с sorted object keys, compact separators и ровно
одним terminal LF. BOM, CRLF, второй LF, duplicate object key, float,
NaN/Infinity, lone surrogate и `bool` вместо generation запрещены. Terminal LF
входит и в raw digest, и в framed length.

Raw digest вычисляется над exact canonical bytes. Framed digest:

```text
SHA-256(
  ASCII("stellaris-m1b-1a1-candidate-construction-scope-v2") ||
  NUL ||
  u64be(11157) ||
  canonical_scope_bytes
)
```

Scope не содержит self-hash. Отдельный
[`owner authorization record`](../decisions/M1B-1A1-AUTH-owner-authorization.json)
bind-ит schema, generation, length, raw digest, framing domain и framed digest.
Exact owner record, этот contract и
[`owner signoff`](../decisions/M1B-1A1-AUTH-owner-signoff.md) связываются
reviewed merge provenance. Такая схема не создаёт circular self-hash.

## 3. Closed schemas и path rules

Scope root closed и имеет ровно поля:

```text
authorization_inputs_after_merge
authorized_action
candidate_roles
constraints
future_directories
future_outputs
generation
git_github_control_plane
host_validation
preserved_blockers
prohibited_actions
read_only_inputs
repository_content_plane
schema
```

Row schemas также closed:

- `authorization_inputs_after_merge`: ровно `identity_binding`, `path`;
- `candidate_roles`: ровно `path`, `role`;
- `future_directories`: ровно `create_only_if_absent`,
  `deletion_authorized`, `mode`, `parent_path`, `parent_relationship`, `path`,
  `purpose`, `replacement_authorized`, `required_type`,
  `symlink_authorized`;
- `future_outputs`: ровно `path`, `tracked`, `write_kind`;
- `read_only_inputs`: ровно `path`, `sha256`.

Closed `repository_content_plane` имеет ровно `metadata_read_policy`,
`semantic_read_policy`, `unlisted_project_content_reads_denied`,
`unlisted_project_content_writes_denied`, `write_policy`. Closed
`git_github_control_plane` имеет ровно `allowed_actions`,
`authorization_pr_number`, `availability`, `branch_base`, `draft_pr_base`,
`draft_pr_count`, `draft_pr_head`, `draft_pr_state`, `future_branch`,
`git_internal_writes`, `network`, `origin`, `prohibited_actions`, `repository`.
Closed `host_validation` имеет ровно `allowed_purposes`, `allowed_tool_classes`,
`authority_classification`, `availability`,
`bounded_system_validation_tool_selection_and_execution_authorized`,
`candidate_source_parse_or_compile_authorized`,
`host_executable_runtime_stdlib_reads`, `new_repository_file_import_authorized`,
`new_repository_file_execution_authorized`,
`persistent_write_policy`, `private_model_game_data_reads_authorized`,
`provider_model_benchmark_runtime_execution_authorized`,
`python_bytecode_policy`.

Owner record closed по exact полям committed JSON; extra или missing field
запрещён. Все permission fields имеют exact JSON boolean, а count, generation и
byte-length fields — non-negative exact integer, не `bool`.

Каждый path — non-empty repository-relative POSIX raw-ASCII string. Запрещены
absolute path, leading/trailing или repeated separator, пустой component, `.` и
`..`, backslash, NUL, ASCII control/DEL и non-ASCII. Внутри каждого
path-bearing array path уникален и rows расположены по
`path.encode("ascii")`; ambient locale не участвует. Symlink не может изменить
lexical или physical target.

## 4. Repository content plane

Content plane default-deny отделён от Git/GitHub control и host-tool mechanics.
Semantic reads разрешены только для:

- `18` exact SHA-bound base inputs;
- `4` exact post-merge AUTH inputs;
- static exact-byte read/readback `12` exact future outputs.

Metadata-only `lstat`/`stat` разрешены только для exact scope paths и их exact
lexical parent closure. Это не semantic read authority. После effect content
writes разрешены только для exact future output files и create-only exact
future directories. Все остальные project-content reads и writes запрещены.

Git status/diff и host implementation dependencies могут механически читать
только то, что необходимо их отдельным закрытым полномочиям ниже; эти bytes не
становятся candidate semantic inputs и не являются скрытым исключением content
plane.

## 5. Exact candidate roles и future directories

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

Scope в raw-ASCII и topological порядке разрешает ровно четыре отсутствующих
каталога:

| Path | Required parent / relationship | Mode | Purpose |
|---|---|---:|---|
| `artifacts/m1b` | `artifacts` / `preexisting_real_directory` | `0700` | sanitized ignored M1B evidence parent |
| `artifacts/m1b/m1b-1a1` | `artifacts/m1b` / `authorized_predecessor_future_directory` | `0700` | sanitized ignored M1B-1A1 evidence parent |
| `fixtures/m1b/candidate-construction` | `fixtures/m1b` / `preexisting_real_directory` | `0755` | tracked inert synthetic fixture parent |
| `tools/research/m1b_1a1_candidate` | `tools/research` / `preexisting_real_directory` | `0755` | tracked inert candidate-role source parent |

Каждый row фиксирует `create_only_if_absent=true`,
`required_type=real_directory`, `symlink_authorized=false`,
`replacement_authorized=false` и `deletion_authorized=false`. Перед созданием
и после него проверяются exact parent и target; mode задаётся при создании.
Recursive или ambient parent creation запрещён. Partial failure остаётся
fail-closed: уже созданный exact directory нельзя удалить или заменить.

## 6. Exact future output allowlist

После effect будущий отдельный M1B-1A1 может read/modify/write только эти `12`
file paths в указанном raw-ASCII порядке:

| Path | Tracked | Write kind |
|---|---:|---|
| `README.md` | `true` | `status_only` |
| `artifacts/m1b/m1b-1a1/candidate-construction-evidence.json` | `false` | `ignored_evidence` |
| `docs/decisions/M1B-1A1-candidate-review.md` | `true` | `candidate_review_record` |
| `docs/roadmap.md` | `true` | `status_only` |
| `fixtures/m1b/candidate-construction/README.md` | `true` | `synthetic_fixture_documentation` |
| `fixtures/m1b/candidate-construction/cases.json` | `true` | `synthetic_fixture_data` |
| `registry/m1b/m1b-1a1-proposed-executable-manifest-v1.json` | `true` | `proposed_manifest` |
| `tools/research/README.md` | `true` | `status_only` |
| `tools/research/m1b_1a1_candidate/analysis_engine.py` | `true` | `candidate_source` |
| `tools/research/m1b_1a1_candidate/contract_validator.py` | `true` | `candidate_source` |
| `tools/research/m1b_1a1_candidate/provider_request_harness.py` | `true` | `candidate_source` |
| `tools/research/m1b_1a1_candidate/synthetic_fixture_materializer.py` | `true` | `candidate_source` |

Existing parents для `README.md`, `docs/decisions`, `docs`, `registry/m1b` и
`tools/research` плюс четыре exact directory rows полностью закрывают parent
chain всех outputs. Ignored evidence остаётся только под already-ignored
`artifacts/`. Status-only paths меняют только gate/status и ссылки. Только
`tracked=true` rows разрешено stage-ить; force-add ignored evidence запрещён.

`fixtures/m1b/candidate-construction/cases.json` — только inert data. Scope не
содержит `tools/research/tests/test_m1b_1a1_candidate.py`; replacement `.py`,
shell script, executable fixture или любой иной repository test не разрешён.
Future validation выполняют только existing host tools над inert bytes.

## 7. Exact read-only base inputs

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

## 8. Post-merge authorization inputs

После merge эти четыре AUTH artifacts становятся read-only inputs будущего
M1B-1A1:

| Path | Identity binding |
|---|---|
| `docs/decisions/M1B-1A1-AUTH-owner-authorization.json` | exact reviewed merge bytes |
| `docs/decisions/M1B-1A1-AUTH-owner-signoff.md` | exact reviewed merge bytes |
| `docs/specs/m1b-1a1-candidate-construction-authorization-contract.md` | exact reviewed merge bytes |
| `registry/m1b/m1b-1a1-candidate-construction-scope-v2.json` | owner-record raw/framed SHA-256 plus exact reviewed merge bytes |

Future preflight обязан доказать, что AUTH bytes находятся в reviewed merge в
`main`, scope hashes совпадают, а все `18` base inputs сохранили exact raw
digests. Любой drift, missing/extra path, schema mismatch или неоднозначный
merge provenance останавливает construction.

## 9. Bounded Git/GitHub control plane

Control plane имеет `availability=after_effect_only` и ограничен remote
`origin`, repository `elenandar/Stellaris-mod-translator`, AUTH PR #9 и будущей
веткой `agent/m1b-1a1-inert-candidate-construction`. Разрешены только:

- fetch refs из `origin`;
- read status, refs, commit/tree/object metadata, ancestry и scoped diffs;
- проверка PR #9 и его exact merge commit, reachable from `origin/main`;
- из clean matching worktree создать и переключить ровно одну future branch от
  этого merge commit;
- stage только `tracked=true` future outputs;
- ordinary commit на exact future branch;
- non-force push только exact future branch;
- создать и обновлять ровно один draft PR: head exact future branch, base
  `main`, state `draft`.

Запись `.git` locks, index, objects и refs разрешена только как следствие этих
Git actions. Запрещены main mutation, force-push, branch deletion/reset,
rebase опубликованной ветки, merge, auto-merge, ready-for-review, close или иной
state transition draft PR, изменение других PR, tags, releases, GitHub Actions
mutation, любой unstated Git/GitHub action и network вне Git/GitHub для exact
repository.

## 10. Bounded host validation

После effect разрешено исполнять только system validation tools и exact
SHA-bound pre-existing repository validation tools для:

- Git/GitHub preflight;
- SHA-256 и canonical JSON reproduction;
- file type, mode, link count и path checks;
- static exact-byte analysis future outputs;
- changed-path и diff checks;
- Markdown link checks только изменённых future docs;
- создания sanitized ignored evidence.

Исполнение этих tools классифицируется как validation, а не candidate/provider
runtime authority. Tool может читать собственный executable, runtime и stdlib
только как implementation dependency; эти bytes не являются candidate semantic
input, не доказывают interpreter admission и не разрешают provider/model/
benchmark runtime execution. Выбор и исполнение bounded system validation tool
для exact listed purpose разрешены, но не являются candidate/provider runtime
interpreter selection.

Обязателен `PYTHONDONTWRITEBYTECODE=1`; `.pyc` и `__pycache__` запрещены. Ни один
вновь созданный repository file нельзя импортировать или исполнять; candidate
source дополнительно нельзя передавать `ast.parse`/другому language parser или
компилировать. Это не запрещает exact static data/Markdown parsing в рамках
перечисленных validation purposes. Persistent content writes ограничены exact
future outputs и exact create-only directories, а internal Git writes — только
последствиями разрешённых Git actions. Private corpus, model store, mods,
Workshop, Stellaris, launcher и active playset не читаются.

## 11. Explicit non-authority и preserved blockers

Даже после effect этот AUTH не разрешает:

- candidate source import, parse, compile, `py_compile`, `exec`, `eval`,
  `runpy`, subprocess или иное execution;
- provider/model/benchmark runtime execution;
- execution/runtime envelope или invocation plan;
- implementation/runtime acceptance record и executable TCB admission;
- operational `owner_accepted` executable identity;
- candidate/provider runtime interpreter selection/copy и любой interpreter
  admission; bounded validation-tool selection остаётся только validation;
- provider/Ollama/model call, metadata probe либо model-store read;
- official/private corpus, mods, Workshop, Stellaris, launcher, active playset;
- реальные prompt/template bytes, translation inputs/outputs;
- benchmark, tuning, holdout, human scoring или feasibility verdict;
- product CLI, M2, activation или publishing.

Earlier umbrella prose о возможном future envelope evidence этим более поздним
exact AUTH не активируется: write allowlist не содержит envelope path, а
`RUNTIME_ENVELOPE_CONSTRUCTION: NOT_AUTHORIZED` имеет приоритет для M1B-1A1.

M1B-1A0 machine surfaces остаются byte-identical к exact PR #8 head: contract
registry, TCB fixture v5, verifier и verifier tests. Execution-envelope v4,
execution-plan v3 и runtime-acceptance v1 synthetic identities внутри этих
surfaces не меняются. M1B-0F и historical protected group также неизменны.

Контрольные identities:

- contract raw SHA-256: `fd5e54a8c4b03b6a9c0a62b715ce6d8b2eac070965467bd2de0dbe772808ce6f`;
- contract framed SHA-256: `ad6bce1a5c516753d79ee0d807f5445e9b860a398e661adfb9730d9c4fee9c31`;
- owner-freeze registry snapshot: `df84871be332ee52c315d0c0cc1a7a0046251352a2a0131382b5cb994cffcb58`;
- definition bundle: `50f51b3cf9be042ebc310d1a6c57791dd31a43362778798455d7ea9678c31e06`.

Scope сохраняет все `16` blockers:

- `CONTEXT_LIMIT_BINDING_UNPROVEN`;
- `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN`;
- `EXECUTABLE_TCB_OWNER_DECISION_REQUIRED`;
- `INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN`;
- `LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN`;
- `LIFECYCLE_STATE_UNPROVEN`;
- `MISSING_PROMPT_BYTES`;
- `MISSING_REAL_CANDIDATE_IDENTITIES`;
- `MISSING_TEMPLATE_BYTES`;
- `NATIVE_DEPENDENCY_CLOSURE_UNPROVEN`;
- `OUTPUT_LIMIT_BINDING_UNPROVEN`;
- `PARTIAL_REPORT_CANNOT_BE_COMPLETE`;
- `PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN`;
- `PROVIDER_PERSISTENCE_UNPROVEN`;
- `RESIDENCY_UNPROVEN`;
- `ROLE_IMPORT_TRANSPORT_UNPROVEN`.

## 12. Required validation and stop conditions

Перед publication обязательны Python `3.9.6`, independent canonical
reproduction, raw/framed digest reproduction минимум двумя способами, closed
root/row/object schemas, raw-ASCII sort/uniqueness, all `18` input hashes, exact
counts `18 / 4 / 4 / 4 / 12`, full parent-chain closure, отсутствие executable
test authority и semantic host/runtime consistency. Далее обязательны targeted
TCB suite `89/89`, full research discovery `266/266`, Markdown validation с `0`
errors, `git diff --check`, exact six-path AUTH diff, M1B-1A0 `4/4` и protected
M1B `8/8` byte parity, repository sentinel/leakage review и clean committed
local/upstream/remote/PR-head parity. Targeted suite остаётся targeted и не
называется full canonical/provider/benchmark validation.

Любой hash/schema/path/count/parent drift, unexpected skip, дополнительный
tracked path, executable replacement, leakage sentinel, dirty tree, remote
divergence или не-draft PR даёт fail-closed stop. AUTH не создаёт fixture или
executable, не запускает Ollama и не читает private corpus для leakage proof;
repository-only sentinel scan и полный diff review честно не называются
private-corpus proof.

## 13. Gate state

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

Единственный следующий шаг — owner review draft PR. Candidate construction в
этом AUTH-задании запрещён.
