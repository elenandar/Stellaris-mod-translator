# Контракт benchmark M1B

- Статус: `M1B: NOT_EVALUATED`; protocol under review, benchmark не запускался,
  feasibility verdict отсутствует
- Версия proposal: `m1b-benchmark-contract-v2`; protocol generation `102`;
  состояние definition:
  `proposed`, не `owner_accepted`
- Зависимый gate: `M1A: BLOCKED`
- Следствие: `M2: FORBIDDEN`

Этот документ фиксирует метод будущего локального M1B benchmark до раскрытия
holdout. Он не является prompt, результатом перевода, capability probe или
разрешением вызвать Ollama. В M1B-0 допустимы только документация и synthetic
conformance evidence; raw corpus, реальные model outputs и active game paths не
используются.

Конкретные field names, enums и supported bytes M1B-0 задают executable schema,
trusted registry validator-а и `fixtures/m1b/README.md`. Этот документ задаёт
их normative meaning; расхождение является contract error, а не разрешением
выбрать более мягкую интерпретацию.

Текущие executable IDs: document schema `m1b-synthetic-contract-v3`, fixture
manifest `m1b-synthetic-contract-cases-v3`, output schema
`m1b-synthetic-output-v3`, corpus `m1b-synthetic-corpus-v3` generation `304`.
Любая другая version unsupported, даже если проходит общий version regex.

## Цель и граница решения

M1B отвечает только на вопрос, достижимо ли приемлемое качество на уже
установленных локальных моделях при воспроизводимом и fail-closed protocol.
Первичный experiment сравнивает три равноправных кандидата:

| Candidate label | Статус до benchmark |
|---|---|
| `GLM 4.7 Flash` | равноправный кандидат |
| `DeepSeek R1 32B` | равноправный кандидат |
| `GPT-OSS 20B` | равноправный кандидат |

Порядок строк не задаёт baseline. До завершения всех заранее объявленных gates
поля `winner`, `baseline` и `m1b_verdict` отсутствуют. Executable v3 schema
распознаёт две exact пары `benchmark_state`:
`(complete=false, report_kind=partial_synthetic_conformance)` и
`(complete=true, report_kind=complete_benchmark)`. Но M1B-0 v3 разрешает только
первую и безусловно отклоняет вторую как
`PARTIAL_REPORT_CANNOT_BE_COMPLETE`. Будущий live benchmark требует новой
owner-accepted report schema/generation, а не смены boolean в v3. Candidate
labels не должны раскрывать модель
reviewer-ам. Исключение кандидата допустимо только как fail-closed result с
контролируемой причиной; оставшийся кандидат не становится победителем
автоматически.

M1B не выбирает export policy, не снимает blockers M1A, не реализует provider
adapter или safety kernel и не разрешает M2, перевод, activation либо publish.

## Provider boundary и live identity

Официальная документация указывает default local API base URL и отдельно
существующий cloud API URL; проект намеренно применяет более строгую
local-only policy. Для benchmark разрешён только заранее закреплённый HTTP URL с
numeric loopback literal:

- `127.0.0.1` либо bracketed `::1`;
- explicit port и точный `/api` base path из принятого profile;
- без hostname/DNS, userinfo, query, fragment, redirect и alternate origin;
- proxy use и ambient proxy discovery отключены;
- peer address после connect остаётся numeric loopback;
- cloud URL, remote address и tag с suffix `-cloud` отклоняются до model load.

Endpoint сравнивается как byte-exact ASCII string до URL parsing. Единственные
допустимые формы — `http://127.0.0.1:<port>/api` и
`http://[::1]:<port>/api`, где `<port>` — canonical decimal без знака и leading
zero, в диапазоне `1..65535`. Scheme/host/path имеют именно показанный регистр;
trailing slash отсутствует. До любого normalization отклоняются leading/trailing
whitespace, Unicode whitespace, все C0/C1 controls, включая CR/LF/TAB, percent
encoding, userinfo, query, fragment, дополнительные path segments, missing port
и alternate IPv4/IPv6 spellings. Parser не исправляет и не canonicalizes вход;
любое такое отклонение получает `ENDPOINT_NOT_NUMERIC_LOOPBACK`.

Redirect не follow-ится даже обратно на loopback. Network error завершает
sample; он не разрешает retry через другую модель, endpoint или provider.
Политика строже provider default и является проектным control, а не утверждением
о встроенной защите Ollama. См. [API introduction](https://docs.ollama.com/api/introduction).

Каждый будущий live run до первого запроса и после последнего запроса обязан
получить и сохранить в локальном private run manifest:

1. точную Ollama version;
2. exact installed tag;
3. полный lowercase 64-hex model digest согласно принятой contract shape;
4. model details/capabilities, значимые для schema и thinking profile;
5. доказательство local residency по принятому M1B control;
6. exact endpoint/profile generation и факт отключённых redirect, proxy,
   auto-pull и fallback.

List-models response документирует model name и digest, а show-model-details —
parameters, template, capabilities и metadata. Ни один из этих ответов по
отдельности не считается доказательством residency. Если exact tag, full digest
или residency нельзя доказать, candidate получает controlled blocker, а не
assumed identity. См. [List models](https://docs.ollama.com/api/tags) и
[Show model details](https://docs.ollama.com/api-reference/show-model-details).

Tag/digest проверяются также на границах каждого batch. Любая подмена, исчезновение
или drift аннулирует весь затронутый batch. Во время run запрещены pull, create,
copy, remove и изменение Ollama configuration. Наличие отсутствующего tag не
разрешает pull; скрытый pull или model fallback делает run invalid.

### Provider persistence blocker

Loopback не доказывает, что daemon не сохраняет request bytes. До первого
private/official request будущий M1B-1 обязан зафиксировать exact Ollama version,
launch/configuration и получить локальное evidence для каждого sink:

- daemon и request logging;
- conversation/request history и continuation state;
- crash reports и diagnostics;
- telemetry и любые remote reporters;
- temporary prompt/output files, caches, swap-sensitive artifacts и retention;
- cleanup procedure и проверку, что benchmark-created raw artifacts удалены.

Evidence строится только на synthetic canary data до допуска private corpus. Оно
обязано перечислять проверенные surfaces, exact configuration, observation
window, cleanup result и remaining uncertainty без raw values. Непроверенный,
неперечисленный либо неограниченный sink останавливает private run с
`PROVIDER_PERSISTENCE_UNPROVEN`; отсутствие найденного файла не подменяет
положительное доказательство policy. В M1B-0
`provider_policy.persistence_status=not_probed`; все provider observations и
model-call counts равны нулю. M1B-0 не выполняет эти проверки live.

### Stateless request boundary

Каждый initial sample, repair и отдельно разрешённый experiment stage получает
новый независимый request. Conversation/history/context reuse между samples,
candidates, tuning/holdout и stages запрещён; response continuation/context
state не передаётся в следующий request. Executable M1B-0 boundary фиксирует
`independent_request_per_sample=true`, `conversation_reuse=false`,
`context_reuse=false`, `continuation_reuse=false` и
`thinking_trace_reuse=false`. `allowed_request_fields` — closed proposal
allowlist в exact порядке `format`, `keep_alive`, `model`, `options`, `prompt`,
`stream`, `think`; unknown fields и ambient client state отклоняются до
dispatch. Это public synthetic request shape, а не доказанная output-limit
binding. Exact nested provider options, включая ещё не принятый output-limit
field, входят в frozen candidate profile до live request.

Context overflow, response truncation, incomplete JSON и достигнутый output
limit требуют `truncation_policy=controlled_failure` и
`context_overflow_policy=controlled_failure`; partial text не оценивается и
не продолжается скрытым request. Thinking trace хранится только в sealed private
measurement surface согласно retention policy, не включается в следующий
request, human presentation, prompt repair или public evidence.

M1B-0 v3 содержит отдельный closed object `context_limit_binding`. Его exact
initial state: `status=not_probed`, blocker
`CONTEXT_LIMIT_BINDING_UNPROVEN`, canary
`required_before_first_private_request`, а `tokenizer_binding`,
`input_limit_binding`, `left_truncation_probe`, `right_truncation_probe`,
`prompt_eval_count_binding`, `overflow_response_binding` и
`post_response_verification` равны `not_probed`. Report не может self-assert
`proven`; external owner-accepted preflight должен bind-ить tokenizer и effective
input limit, обнаружить silent left/right truncation, проверить
`prompt_eval_count`, explicit overflow/error response и post-response bytes.
Любое live observation до этого evidence блокируется.

Единственный closed M1B-0 no-output code —
`CONTEXT_OVERFLOW_CONTROLLED`: `technical_conformance=not_observed`, пустые
`observed_atoms`, D1–D5 `not_evaluated`, terminal `controlled_failure`, один
terminal failure в denominator и отсутствие human ground truth. Unknown uppercase
failure code не становится допустимым transition.

### Bounded JSON input

Synthetic validator читает только explicit path. Лимит `4 MiB` применяется
отдельно к standalone document, fixture manifest и повторно к materialized
fixture document; `copy_append`/`append`/`set` не могут расширить малый manifest
за этим byte-boundary. Fixture дополнительно допускает не более `256` patches;
cumulative materialization work — compact bytes принятого начального document
плюс compact bytes каждого принятого post-patch состояния — не превышает
`16 MiB`, а последнее
budgeted encoding переиспользуется как result. До каждого следующего encoding
резервируются полные `4 MiB`; если остатка нет, `MATERIALIZATION_WORK_LIMIT`
возвращается до вызова encoder. Вход — strict UTF-8 JSON без duplicate keys либо
lone surrogates. Schema использует только integers: `parse_float` отклоняет
любой decimal/exponent token, а `parse_constant` — NaN/Infinity до schema
validation.

`parse_int` сначала проверяет lexical token без создания Python integer. Более
`19` decimal digits без optional leading `-` либо значение вне signed 64-bit range
получает `JSON_INTEGER_OUT_OF_RANGE`; только затем вызывается integer
conversion. Field-level schema дополнительно требует свой closed non-negative
range и отвергает `bool`. Любой decimal/exponent получает
`JSON_FLOAT_FORBIDDEN`. Oversize token, parse error и exception никогда не
выводят token, path, traceback или raw input; public CLI возвращает только
controlled code и zero/safe aggregate counts.

## Freeze bundle

До первого tuning request владелец принимает byte-frozen protocol bundle. Он
содержит только versioned contracts и private local manifests, но не
публикует raw corpus:

- `protocol_version` и canonical protocol hash;
- `schema_version` и hash точных schema bytes;
- `prompt_policy_version` и hash принятых policy/template bytes;
- три candidate profiles с exact tag/digest после live preflight;
- corpus generation, split manifest и strata definition;
- generation options, client timeout/retry и lifecycle policy;
- randomization/blinding plan и заранее выбранные seeds;
- rubric version, reviewer roles, gates и statistical method;
- harness/runtime/OS measurement versions;
- retention deadline и leakage policy version.

Executable representation называется `definition_bundle` и содержит ровно
`components`, `framing`, `sha256`. `framing` обязан быть
`m1b-length-framed-sha256-v1`. Каждый component содержит ровно
`acceptance_state`, `definition`, `generation`, `kind`, `sha256`, `version`.
Поле `definition` в M1B-0 — только public synthetic UTF-8 definition string;
private corpus/profile payload, private path/identifier и content-derived hash
никогда не помещаются в это поле. Исключение по классу данных — явно public
digest самой synthetic corpus definition внутри trusted `corpus_policy`; он не
является digest official/private corpus. Component и bundle `sha256` —
lowercase 64-hex strings.

Protocol hash не включает private corpus bytes, private paths или производные от
них hashes в публикуемом evidence. Локальная private manifest может проверять
immutability raw corpus, но наружу выходит только случайный opaque generation,
агрегаты и protocol hashes по правилам [M1B corpus policy](../m1b-corpus-policy.md).

### Canonical public hash framing

Public protocol/schema/prompt-policy/profile hashes используют проектный
алгоритм `SHA-256` и versioned binary framing; это не утверждение об алгоритме
provider model digest. Для каждого public component:

```text
component_hash = SHA-256(
  ASCII("stellaris-m1b-component-v1") || NUL ||
  u32be(len(kind)) || ASCII(kind) ||
  u32be(len(version)) || ASCII(version) ||
  u64be(len(payload)) || payload
)
```

`kind` и `version` обязаны соответствовать ASCII `[a-z0-9._-]+`; `payload` —
exact UTF-8 bytes поля `definition`. В trusted M1B-0 registry definitions лежат
в ASCII subset UTF-8. Newline, Unicode, key order и whitespace никогда не
нормализуются. `u32be`/`u64be` — unsigned big-endian lengths. Bundle hash
использует domain `stellaris-m1b-bundle-v1`, `NUL`, `u32be` числа components и
отсортированную по raw `(kind, version)` последовательность тех же
length-prefixed `kind`/`version` плюс 32 raw bytes `component_hash`. Duplicate
`(kind, version)` запрещён. Paths, timestamps, locale и directory enumeration в
framing не входят.

Component digest намеренно покрывает `kind`, `version` и exact `definition`
bytes. Поля `generation` и `acceptance_state` не входят в этот digest, но
проверяются byte/typed-exact против отдельного trusted registry до pass; входной
document не может изменить их вместе с self-rehash.

Public synthetic corpus получает отдельную binding, не совпадающую с component
framing. Validator canonicalizes exact closed `corpus` object как ASCII JSON с
`ensure_ascii=true`, lexicographically sorted object keys и separators `,`/`:`
без пробелов, затем вычисляет:

```text
synthetic_corpus_sha256 = SHA-256(
  ASCII("stellaris-m1b-synthetic-corpus-v1") || NUL ||
  u64be(len(canonical_corpus_json)) || canonical_corpus_json
)
```

Trusted `corpus_policy` component связывает этот digest с exact synthetic
`corpus_version`, generation и framing. Root `corpus` дополнительно должен
совпасть с canonical trusted bytes. Поэтому согласованная подмена expected atoms,
split/risk/stratum metadata и соответствующих `observed_atoms` не становится
новой допустимой fixture: она заканчивается `CORPUS_DEFINITION_MISMATCH`, даже
если D1 expected/observed comparison сам по себе согласован. Эта public binding
применяется только к вымышленному M1B-0 corpus. Digest live official/private
corpus остаётся только локальным immutability evidence и не входит в report,
component definition либо public bundle.

Для `m1b-benchmark-contract-v2` public bundle обязан содержать ровно `17`
components, по одному каждого kind: `benchmark_contract`, `output_schema`, `prompt_policy`,
`candidate_profile.glm_4_7_flash`, `candidate_profile.deepseek_r1_32b`,
`candidate_profile.gpt_oss_20b`, `corpus_policy`, `split_policy`,
`generation_policy`, `context_limit_policy`, `randomization_blinding_policy`, `quality_rubric`,
`measurement_policy`, `retention_leakage_policy`, `validator_policy` и
`analysis_policy`, `implementation_identity_policy`. Missing, extra, duplicate
либо unknown kind инвалидирует
bundle до hash comparison; новый kind требует новой contract version.

`definition_bundle.sha256` содержит lowercase 64-hex bundle hash. В public
bundle допускаются только public contract bytes. Для synthetic M1B-0 это
включает описанную выше canonical corpus binding. Raw official/private corpus,
private paths/identifiers и их hashes исключены; будущий live corpus представлен
только случайным opaque generation. Изменение framing или algorithm создаёт
новую protocol version и инвалидирует сравнение с прежними generations.

### Trusted freeze registry и version state

Hash, пересчитанный из самого входного документа, не доказывает его принятую
identity. До проверки report существует отдельный closed freeze registry. Для
каждой поддерживаемой пары `(kind, version)` он содержит expected component
`sha256`, а для protocol version — exact member set и expected
`definition_bundle.sha256`. Validator сравнивает input с этим trusted registry;
report не может добавить либо изменить registry entry. Неизвестная syntactically
valid version отклоняется.

M1B-0 registry встроен в offline validator как immutable allowlist exact
proposal definitions/hashes; fixture лишь предъявляет component bytes и не
является trust root. Будущий owner-accepted registry должен быть выбран как
отдельный immutable local input до run и закреплён owner decision; benchmark
report остаётся untrusted относительно него.

Текущие `quality_rubric`/`analysis_policy` definitions byte-bind-ят proposed
thresholds, family-wise method, exact source-generation collapse, CFA estimator,
Clopper–Pearson conventions, robust kappa/NA/adjudication semantics и состояние
`owner_decision_required`. Они не являются owner acceptance и не создают live
report implementation. После принятия definitions и full live report fields
создаются новые definition version/generation и hashes; reuse текущего version с
другими bytes запрещён.

Каждая registry entry имеет одно из состояний:

- `proposed` — byte-exact definition пригодна только для synthetic review;
- `owner_accepted` — владелец отдельным решением принял именно указанный
  `definition_bundle.sha256` до первого tuning request;
- `retired` — syntactically recognized historical state, но не допускается
  текущим trusted proposal registry для нового run.

Все entries M1B-0 остаются `proposed`. Merge документа или успешный synthetic
validator не меняет state и не выставляет feasibility verdict. Owner acceptance
фиксируется вне проверяемого report и ссылается на exact registry version и
`definition_bundle.sha256`; input не может self-assert `owner_accepted`.
Попытка завершить `complete_benchmark` в M1B-0 v3 заканчивается раньше кодом
`PARTIAL_REPORT_CANNOT_BE_COMPLETE`; `OWNER_DECISION_REQUIRED` остаётся
pre-request blocker будущей owner-accepted live generation.

Freeze ownership M1B-0 разделён между components и не переносится на соседние
definitions:

| Component | Что именно bind-ит trusted definition |
|---|---|
| `candidate_profile.<candidate>` | closed candidate-row field set и exact values всех row fields, кроме значения opaque `candidate_id`: candidate label, component/profile version, profile generation, synthetic model ref/full placeholder digest и digest kind, selection state, полный `runtime` и `thinking_profile` |
| `generation_policy` | canonical endpoint grammar, `fallback=false`, `retry_limit=0`, request-boundary field set, exact ordered request-field allowlist и stateless/reuse policy |
| `context_limit_policy` | exact unproven binding object, required canary и запрет live observation/silent truncation до external proof |
| `output_schema` | result/sample/atom/accounting/finding/review/adjudication/count fields, quality dimensions и закрытые technical/editorial/terminal/dimension/failure/blinding enums |
| `analysis_policy` | source-generation estimator, candidate family correction, CP boundary conventions, CFA collapse и exact robust kappa inputs/statuses |
| `implementation_identity_policy` | non-circular future executable-manifest admission contract; не exact bytes текущей реализации |
| `validator_policy` | input-size и signed-integer limits, strict JSON modes, closed/offline fixture schema и controlled public output fields |

Declarative bundle bind-ит canonical definitions и synthetic corpus, но не exact
bytes validator/harness/materializer/analysis implementation. Поэтому root
`implementation_identity` остаётся `status=unproven`, schema
`m1b-executable-implementation-manifest-v1`, null generation/digest и blocker
`EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN`. Report не может self-assert
`proven`.

Будущий admission использует внешний owner-accepted manifest, а не self-hash.
Manifest имеет ровно root fields `files`, `implementation_generation`,
`manifest_schema`; каждый file row — `path`, `role`, `sha256`. Ровно по одному
regular non-symlink repository file назначается ролям `analysis_engine`,
`contract_validator`, `provider_request_harness`,
`synthetic_fixture_materializer`. Paths — unique repository-relative ASCII POSIX
strings в raw-ASCII order, без empty segment, `.`, `..`, backslash, NUL,
absolute/symlink ambiguity. `sha256` считается по exact file bytes.

Canonical manifest bytes — sorted-key compact ASCII JSON плюс LF. External digest:

```text
SHA-256(
  ASCII("stellaris-m1b-executable-manifest-v1") || NUL ||
  u64be(len(canonical_manifest)) || canonical_manifest
)
```

Manifest не содержит свой digest и не включает себя file row. Digest,
implementation generation, manifest schema, protocol generation и
`acceptance_state=owner_accepted` живут в отдельном owner record вне report.
Любое изменение executable file bytes требует новой implementation и run
generation. Пока такого record и verifier нет, live observation запрещён.

Сам candidate-profile component не bind-ит endpoint, request allowlist,
fallback policy, result schema либо parser limits; их покрывают указанные
отдельные components и соответствующая executable validation. Coherent изменение
всех трёх candidate profiles под прежними version/generation всё равно даёт
registry mismatch. Изменение payload требует нового component hash и нового
version/generation; изменение member set либо любого component hash требует
нового bundle hash и protocol generation. Proposal version не может обозначать
разные bytes.

## Общий generation profile

Все кандидаты получают одинаковые versioned schema, prompt policy, sample
presentation, output contract и scoring path. Actual prompt/template bytes не
создаются в M1B-0 и должны быть приняты отдельно до tuning. Candidate-specific
wording в primary comparison запрещён.

Следующие operational defaults являются **proposal M1B-v2 и ожидают owner
acceptance до любого live request**:

| Поле | Предложенное значение | Freeze rule |
|---|---:|---|
| `num_ctx` | `8192` | одинаково для трёх primary profiles |
| `temperature` | `0` | exact numeric type; `bool` недопустим |
| `seed` | `424242` | одинаково для соответствующего sample trial |
| output limit | proposal: `2048` final-response tokens | exact request field, enforcement и thinking-token accounting должны быть приняты и frozen |
| client deadline | `300 s` | timeout учитывается, не скрывается retry |
| retry count | `0` | repair является отдельным измеряемым stage |
| streaming | disabled | один complete schema-bound response |
| schema | один frozen JSON Schema object | exact bytes/version для всех кандидатов |
| thinking | frozen candidate-profile field | значение обязательно до tuning |
| cold lifecycle | unload after measured request | отдельная lane |
| warm lifecycle | fixed `10m` keep-alive | отдельная lane и один unscored warm-up |

Ollama generate API документирует schema object в `format`, generation options,
`think`, `keep_alive`, output-token count и отдельные timing fields. Structured
output остаётся лишь provider capability: strict local validator всё равно
проверяет результат и schema failure учитывается как failure. См.
[Generate API](https://docs.ollama.com/api/generate) и
[Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs).

Разрешённая Generate API page не документирует конкретное request field для
output limit и не определяет, включает ли её `eval_count` thinking tokens.
Поэтому до первого tuning request owner-accepted profile обязан отдельно
зафиксировать документированное request field, exact JSON type/value, единицу,
scope final-response/thinking accounting, client-side enforcement и
disposition для truncation. Если эту binding нельзя доказать разрешённой
provider documentation либо отдельным будущим synthetic preflight, live run
останавливается с `OUTPUT_LIMIT_BINDING_UNPROVEN`. Поле
`output_token_limit` synthetic M1B-0 fixture проверяет только contract shape и
не изображает такую live binding.

Thinking capabilities различаются по моделям; официальная документация, в
частности, описывает model-specific levels для GPT-OSS и отдельный thinking
output. Поэтому actual thinking literal фиксируется в каждом candidate profile
после разрешённого будущего metadata preflight, но до первого tuning request.
См. [Thinking](https://docs.ollama.com/capabilities/thinking).

Недоступная capability не разрешает тихо менять profile. Model-specific
исключение допустимо только как отдельный заранее зарегистрированный profile с:

- причиной и provider evidence;
- всеми отличающимися bytes/options;
- отдельным profile hash;
- отдельными результатами и limitations;
- запретом смешивать его score с primary common-profile ranking.

Если сравнимый primary profile невозможно определить до tuning, protocol
останавливается для owner decision. Seed и temperature не считаются обещанием
bit-identical output между versions/hardware; повторяемость доказывается
измерениями, а не предполагается.

## Corpus phases и запрет holdout tuning

Tuning и holdout физически и логически разделены по
[M1B corpus policy](../m1b-corpus-policy.md). До holdout замораживаются:

- sample membership и strata;
- prompt/schema/profile bytes;
- validators, repair/fallback routing и acceptance disposition;
- quality rubric и statistical gates;
- randomization, reviewer assignment и analysis code.

Evaluation thresholds и minimum coverage калибруются только на tuning, затем
получают owner acceptance и входят в freeze до первого holdout request.
Production routing/acceptance thresholds могут быть выбраны только после M1B и
не изменяют задним числом evaluation gates либо holdout score.

Tuning разрешает откалибровать pipeline только до freeze. Holdout раскрывается
локальному runner отдельной фазой после signed/frozen manifest. После первого
holdout response запрещено менять prompt, schema, options, profile, parser,
validator, repair, fallback, rubric, reviewer instructions или acceptance
logic. Любое такое изменение переводит раскрытый holdout в tuning data,
инвалидирует его результаты и требует новой независимой holdout generation.

## Assignment, coverage и execution lanes

Assignment identity — closed tuple
`(candidate_id, sample_id, profile_version, profile_generation,
experiment_lane, attempt_stage, attempt_index)`. Новый `result_id` не создаёт
нового assignment.
Tuple уникален во всём report; duplicate либо неизвестный
candidate/sample/profile/generation/lane/stage member отклоняет document.

Executable result v3 содержит только `accounting`, `attempt_index`,
`attempt_stage`, `blinding_status`, `candidate_id`, `corpus_generation`,
`dimension_records`, `editorial_status`, `experiment_lane`, `failure_code`,
`initial_result_id`, `mapping_generation`, `observed_atoms`, `profile_generation`,
`profile_version`, `protocol_generation`, `result_id`, `sample_id`,
`technical_conformance`, `terminal_status`. Sample v3 дополнительно bind-ит
`source_generation_id` отдельно от `source_unit_cluster_id`.

Primary quality lane содержит ровно один `initial` assignment для каждого
объявленного candidate/sample/profile. Failed, timeout, truncation,
schema-invalid и provider-error result сохраняется как controlled terminal row,
остаётся в assigned denominator и не заменяется regeneration. Если repair
моделируется отдельной row, она имеет lane/stage `repair`, ссылается на
единственный lane/stage `primary`/`initial` result и не стирает его. Fallback
использует только lane/stage `fallback`/`fallback`, если policy его заранее
разрешила. Другие pairings invalid. При frozen `retry_count=0`
`attempt_index=0` обязателен во всех трёх lanes; поэтому для одного
candidate/sample/profile допустима не более чем одна row каждого lane/stage.
Repair и fallback остаются отдельными объявленными stages, а не скрытыми retry
indexes. Cold/warm performance observations считаются отдельно и не увеличивают
независимый quality `n`.

Состояния отчёта разделены строго:

- **partial synthetic conformance** —
  `report_kind=partial_synthetic_conformance`, `complete=false`, exact declared
  coverage и только synthetic assignments; не является benchmark, quality
  evaluation, editorial acceptance либо model observation;
- **complete future benchmark** — пара `report_kind=complete_benchmark`,
  `complete=true` зарезервирована, но v3 всегда возвращает
  `PARTIAL_REPORT_CANNOT_BE_COMPLETE`. Exact cross-product, live aggregates и
  owner acceptance определит только новая schema/generation.

В partial report каждый перечисленный candidate/profile имеет хотя бы один
declared result; непокрытые assignments явно отсутствуют из declared coverage,
а не подразумеваются успешными. Primary human ground truth и top-level
adjudications в partial report запрещены. Узкое исключение — только
`secondary_unblinded` evidence для self-identifying synthetic output; оно не
получает primary credit. Candidate без result, смешанные generations либо
несогласованная partial coverage invalid.
`coverage.required_primary_assignment_count`,
`declared_primary_assignment_count`, `per_candidate` и `per_stratum`
вычисляются из row-level records и обязаны совпадать с aggregates.
`per_candidate` rows имеют только `candidate_id`/`primary_result_count`, а
`per_stratum` — только `stratum`/`primary_result_count`; обе closed tables
покрывают весь соответствующий enum, включая zero-count strata в partial report.

Canonical positive M1B-0 fixture объявляет `6` required future primary
assignments для двух samples и трёх candidates, но содержит только `3` declared
partial results: один synthetic tuning sample для каждого candidate. Findings,
reviews, `human_ground_truth` и все live/model observation counts равны нулю.
Каждая row имеет `terminal_status=not_applicable`, поскольку model attempt не
выполнялся. Это declared partial coverage, не incomplete benchmark pass.

Accounting сохраняет следующие равенства и нулевые инварианты:

`accounting` имеет ровно 13 counters:
`cold_latency_observation_count`, `fallback_attempt_count`,
`human_fallback_count`, `initial_attempt_count`,
`memory_observation_count`, `model_call_count`, `model_fallback_count`,
`repair_attempt_count`, `repair_failure_count`, `repair_success_count`,
`retry_attempt_count`, `terminal_failure_count`,
`warm_latency_observation_count`.

- Synthetic primary row с `terminal_status=not_applicable` допускается только с
  нулями во всех 13 counters. Это ровно canonical M1B-0 case без model attempt;
  он не создаёт phantom initial/repair/fallback observation.
- Для live primary row terminal `success` либо `controlled_failure` требует
  `initial_attempt_count=1`; repair/fallback counters в primary row равны нулю.
- Repair row имеет только lane/stage `repair`/`repair`,
  `initial_attempt_count=0`, `repair_attempt_count=1` и ровно один из
  `repair_success_count=1` или `repair_failure_count=1` согласно terminal status;
  fallback counters там равны нулю. `not_applicable` repair row запрещена.
- Fallback row имеет только lane/stage `fallback`/`fallback`,
  `initial_attempt_count=0`, `fallback_attempt_count=1` и
  `human_fallback_count + model_fallback_count = 1`; repair counters там равны
  нулю. Human fallback требует `model_call_count=0`, а `not_applicable` fallback
  row запрещена.
- `provider_policy.fallback=false` запрещает hidden/model/provider fallback и
  ненулевой `model_fallback_count`, но не заранее объявленную human fallback
  lane. Успешный human fallback имеет `human_fallback_count=1` и
  `model_call_count=0`; успешный model fallback требует ровно один model call.
- При `retry_limit=0` каждая primary/repair/fallback row имеет
  `attempt_index=0`, `retry_attempt_count=0`, а `model_call_count <= 1`.
  Дополнительный sibling той же lane/stage становится duplicate assignment.
  Terminal `success` требует `model_call_count=1`, кроме явно объявленной
  human-fallback row, где он обязан быть `0`; latency/memory observation count
  не может превышать model-call count.
- `terminal_failure_count=1` для terminal `controlled_failure` либо
  `blinding_failed`; иначе он равен нулю. Оба остаются в assignment/quality
  denominator.
- Row-level равенства
  `repair_success_count + repair_failure_count = repair_attempt_count` и
  `human_fallback_count + model_fallback_count = fallback_attempt_count`
  сохраняются также при aggregation; aggregates должны быть точной суммой rows.
- При `residency_status=not_probed` live model-call/cold/warm/memory observations
  равны нулю; synthetic transition cases могут проверять только closed
  initial/repair/fallback denominator accounting без утверждения live execution.
  Results разных protocol/profile/corpus generations не агрегируются.

Sample и candidate order рандомизируются frozen seed, а mapping хранится только
локально.

Performance measurement разделяет:

- **cold latency** — client wall time и provider timing для запроса после
  подтверждённого non-resident lifecycle state;
- **warm latency** — те же метрики после одного заранее объявленного unscored
  warm-up и подтверждённого resident state.

Cold и warm samples, порядок, число repetitions и lifecycle evidence
фиксируются до tuning. Cold и warm distributions публикуются отдельно; среднее
по смешанным состояниям запрещено. Неудачная подготовка lifecycle state даёт
controlled invalid measurement, а не перенос observation в другую lane.

## Blinded human review

Review выполняется локально людьми по
[независимой rubric](m1b-quality-rubric.md). Для reviewer-а рандомизируются
candidate order и presentation order. Reviewer не видит model label, tag,
digest, profile, latency, thinking trace, model-review result или disposition
другого reviewer-а.

Критические категории получают две независимые initial human reviews от разных
людей; disagreement проходит отдельную human adjudication. Случайные UUIDv4
reviewer/sample IDs не заменяют локальную проверку, что это действительно разные
люди. Model-review допускается только как отдельный blinded experiment с ролью
`model_reviewer`; его findings не удовлетворяют human-review count, не меняют
human labels и не назначают `editorially_approved`.

Presentation wrapper проходит local preflight на отсутствие model/profile
metadata, но не меняет bytes оцениваемого output. `blinding_status` имеет ровно
`not_observed`, `passed`, `external_mapping_leak`,
`self_identifying_output`.

При external metadata/mapping leak affected initial records замораживаются как
`compromised_primary`; fresh primary evidence использует большую positive
`mapping_generation` и только новых `never_unblinded` reviewers. Reviewer ID не
переиспользуется между compromised и fresh evidence, а новая model generation
запрещена. Из-за отсутствия доказуемой chronology любой sibling repair/fallback
result того же candidate/sample после blinding incident также отклоняется
`BLINDING_REGENERATION_FORBIDDEN`.

Self-identifying output в primary, repair или model-output fallback lane получает
`blinding_status=self_identifying_output`, `failure_code=BLINDING_FAILED`,
ровно один `model_call_count`, terminal `blinding_failed`, D2–D5
`blinding_failed`, zero primary success и увеличивает
`blinding_failure_count`. Human-fallback row с zero model calls не может быть
self-identifying output. Primary ground truth, editorial approval и любая
дальнейшая generation запрещены. `secondary_unblinded` review допустим только
для такого result, остаётся descriptive и не восстанавливает primary success.

Aggregate `blinding_failure_count` равен точной сумме rows со status
`external_mapping_leak` либо `self_identifying_output`; это число incidents, а
не число reviews/findings. `terminal_status=not_applicable` означает отсутствие
model attempt и допускает только `blinding_status=not_observed`, mapping `0`,
D2-D5/editorial `not_evaluated` и zero accounting.
Model-call row с returned output не может оставаться `not_observed`: terminal
success обязан иметь `passed` либо `external_mapping_leak`, а
`self_identifying_output` обязан завершиться `blinding_failed`. `not_observed`
success допустим только для объявленного human fallback с zero model calls.

Эти provenance rules одинаково действуют для `human_ground_truth`, finding
reviews и finding adjudications. Review/adjudication rows несут
`evidence_tier`, positive human `mapping_generation` и `reviewer_blinding`;
global reviewer exposure не позволяет одному UUID быть одновременно
`unblinded` и `never_unblinded`. Critical finding имеет ровно две primary
initial human reviews. Только при disagreement adjudicator является третьим
distinct never-unblinded человеком, связывает ровно два frozen review IDs и
задаёт final confirmation, не переписывая initial evidence.

## Три слоя результата и human evidence

Contract не объединяет три разных утверждения:

1. **synthetic technical conformance** — fixture соответствует закрытой schema и
   synthetic D1 checks;
2. **human quality evaluation** — D2–D5 имеют полные blinded human records и
   frozen applicability/ground truth;
3. **editorial/operational acceptance** — только будущая policy может направить
   human-evaluated result в approved/fallback/rejected state; статус
   `editorially_approved` назначает только человек.

M1B-0 может утверждать только первый слой. Поле `technical_conformance` принимает
`synthetic_conformant`, `synthetic_nonconformant` либо `not_observed`, а
closed `editorial_status` принимает `not_evaluated`, `editorially_approved` либо
`editorially_rejected`. Canonical positive M1B-0 использует `not_evaluated`; при
`complete=false` значение `editorially_approved` запрещено, а synthetic
`editorially_rejected` является только fail-closed contract disposition и не
доказывает human editorial decision. `technical_safe` никогда не означает editorial
approval. `not_observed` допустим только при
`terminal_status=controlled_failure`, требует пустые `observed_atoms`, D1–D5
`not_evaluated` и полностью запрещает `human_ground_truth` для этой row. Такой
no-output result остаётся в denominator и никогда не является technical либо
human-quality pass. Для любой row каждое D2–D5 значение `human_pass`,
`human_fail` или `not_applicable` обязано иметь matching `human_ground_truth`;
если такой записи нет, единственный допустимый status — `not_evaluated`.
Self-asserted human status отклоняется как `MANDATORY_HUMAN_EVIDENCE_MISSING`.
Future `editorially_approved` запрещён, если хотя бы одна applicable
D2–D5 не имеет `human_pass`/human-confirmed `not_applicable`, отсутствует
обязательная `human_ground_truth` либо не пройден требуемый human gate.
`high`/`critical` в initial/repair/fallback history никогда не разрешает
auto-accept; critical attempt остаётся failed, а отдельный repaired/fallback
result требует собственной полной human evaluation. Repair/fallback не снижает
severity исходного evidence.

Каждый holdout output получает human ground truth по D2–D5, даже если будущая
production policy считает его class auto-eligible. Для mandatory-human class
нужен предусмотренный policy human gate; model-review его не удовлетворяет.
Critical-risk classes получают две разные initial human identities. Reviewer ID
имеет одну стабильную role во всём document и не совпадает ни с candidate,
sample, atom/occurrence, result, finding, review либо другим opaque-ID class.
Closed mapping finding category -> dimension задана rubric; mismatch invalidates
record до aggregation.

## Обязательные measurements

Для каждого candidate/profile и каждого corpus stratum отчёт раздельно содержит:

- schema validity и exact typed-atom preservation: missing, extra, type/value,
  multiplicity и mutation counts;
- независимые quality dimensions и severity distributions;
- critical model defects и critical false accepts;
- randomized/blinded human disagreement и adjudication counts;
- client wall latency, provider total/load/evaluation timings, отдельно cold/warm;
- peak/resident memory с versioned measurement method;
- first-pass success, schema/atom repair attempt/success/failure;
- human fallback, model fallback и terminal rejection counts;
- timeout, cancellation и controlled provider-error counts;
- model-review experiment metrics отдельно от primary human result.

Exact atom value/position verification выполняется по
[typed-atom contract](m1b-quality-rubric.md#d1--schema-и-typed-atom-stability).
В synthetic fixture expected/observed tuples могут содержать только явно
вымышленные literals. Для official/private sample exact literals, positions и
content-derived hashes остаются только в local private validator; public report
выводит controlled codes и aggregate missing/extra/value/position/multiplicity
counts без row-level content.

Repair никогда не переписывает историю первой попытки. Fallback на другого
candidate/provider запрещён в primary run; если позднее owner разрешит отдельный
fallback experiment, он получает собственный заранее принятый profile и не
подменяет baseline evidence.

## Reproducibility и invalidation

Declarative run identity требует совпадения frozen generations/definitions.
Exact executable reproducibility пока не доказана и остаётся заблокирована
`EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN` до external manifest admission.
После его принятия изменение хотя бы одного из следующих элементов создаёт новый
run generation:

- corpus bytes, membership, strata или reviewer mapping policy;
- exact model tag/digest, Ollama version или residency evidence;
- endpoint, schema, prompt policy, profile/options/thinking/lifecycle;
- exact manifest-bound harness, validator, materializer или analysis bytes;
- repair/fallback, rubric либо analysis definition;
- timeout/retry, randomization/blinding или statistical method.

Private content equality проверяется только локально. Public report указывает
protocol/profile hashes, opaque corpus generation, exact full model digests и
aggregate counts; он не содержит private content-derived hashes. Partial results
из разных generations не объединяются. Drift между preflight и postflight
аннулирует batch. Любая correction после holdout требует нового holdout, если
она могла повлиять на output, routing или score.

## Verdict contract

M1B report завершается ровно одним из двух verdicts только после owner-accepted
rubric и полного holdout:

- `QUALITY_FEASIBLE` — указывает exact baseline model/profile digest, разрешённые
  content classes, обязательные human-review classes, limitations, sample sizes,
  confidence bounds, repairs/fallbacks и все gate results;
- `QUALITY_NOT_FEASIBLE` — не назначает baseline и перечисляет controlled failure
  classes, scope и воспроизводимое evidence.

Protocol-invalid, leaked, drifted или неполный run не получает ни один из этих
verdicts. M1B-0 также не получает feasibility verdict: его результат — только
protocol under review и synthetic conformance gate.

Даже будущий `QUALITY_FEASIBLE` не разрешит M2, пока M1A остаётся `BLOCKED`.
Переход возможен только при одновременно принятых `M1A: GO` и
`M1B: QUALITY_FEASIBLE`.
