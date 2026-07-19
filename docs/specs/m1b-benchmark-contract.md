# Контракт benchmark M1B

- Статус: `M1B: protocol under review`; benchmark не запускался, feasibility verdict отсутствует
- Версия proposal: `m1b-benchmark-contract-v1`
- Зависимый gate: `M1A: BLOCKED`
- Следствие: `M2: forbidden`

Этот документ фиксирует метод будущего локального M1B benchmark до раскрытия
holdout. Он не является prompt, результатом перевода, capability probe или
разрешением вызвать Ollama. В M1B-0 допустимы только документация и synthetic
conformance evidence; raw corpus, реальные model outputs и active game paths не
используются.

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
поля `winner`, `baseline` и `m1b_verdict` отсутствуют; закрытый
`benchmark_state` M1B-0 допускает только `complete: false`. Candidate labels не
должны раскрывать модель reviewer-ам. Исключение кандидата допустимо только как fail-closed result с
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
точные frozen bytes без newline, Unicode, key-order или whitespace
normalization. `u32be`/`u64be` — unsigned big-endian lengths. Bundle hash
использует domain `stellaris-m1b-bundle-v1`, `NUL`, `u32be` числа components и
отсортированную по raw `(kind, version)` последовательность тех же
length-prefixed `kind`/`version` плюс 32 raw bytes `component_hash`. Duplicate
`(kind, version)` запрещён. Paths, timestamps, locale и directory enumeration в
framing не входят.

Для `m1b-benchmark-contract-v1` public bundle обязан содержать ровно по одному
component каждого kind: `benchmark_contract`, `output_schema`, `prompt_policy`,
`candidate_profile.glm_4_7_flash`, `candidate_profile.deepseek_r1_32b`,
`candidate_profile.gpt_oss_20b`, `corpus_policy`, `split_policy`,
`generation_policy`, `randomization_blinding_policy`, `quality_rubric`,
`measurement_policy`, `retention_leakage_policy`, `validator_policy` и
`analysis_policy`. Missing, extra, duplicate либо unknown kind инвалидирует
bundle до hash comparison; новый kind требует новой contract version.

В public bundle допускаются только public contract bytes. Raw corpus, private
paths/identifiers и их hashes исключены; corpus представлен случайным opaque
generation. Изменение framing или algorithm создаёт новую protocol version и
инвалидирует сравнение с прежними generations.

## Общий generation profile

Все кандидаты получают одинаковые versioned schema, prompt policy, sample
presentation, output contract и scoring path. Actual prompt/template bytes не
создаются в M1B-0 и должны быть приняты отдельно до tuning. Candidate-specific
wording в primary comparison запрещён.

Следующие operational defaults являются **proposal M1B-v1 и ожидают owner
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

Tuning разрешает откалибровать pipeline только до freeze. Holdout раскрывается
локальному runner отдельной фазой после signed/frozen manifest. После первого
holdout response запрещено менять prompt, schema, options, profile, parser,
validator, repair, fallback, rubric, reviewer instructions или acceptance
logic. Любое такое изменение переводит раскрытый holdout в tuning data,
инвалидирует его результаты и требует новой независимой holdout generation.

## Execution lanes

Primary quality lane создаёт один заранее объявленный scored result на
candidate/sample/profile. Sample и candidate order рандомизируются frozen seed,
а mapping хранится только локально. Failed/timeout/schema-invalid result остаётся
в denominator и направляется в repair/fallback accounting; его нельзя молча
перегенерировать.

Performance lane разделяет:

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
metadata, но не меняет bytes оцениваемого output. Если reviewer был раскрыт
внешней metadata/mapping ошибкой, его affected records инвалидируются; повтор
выполняют только новые reviewers, которые ранее не видели identity, с новой
mapping. Если сам output идентифицирует model/profile или иначе делает blind
невозможным без редактирования текста, record получает `BLINDING_FAILED`, не
перегенерируется молча и не входит в primary blinded score; отдельная unblinded
оценка может публиковаться только как secondary evidence.

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

Repair никогда не переписывает историю первой попытки. Fallback на другого
candidate/provider запрещён в primary run; если позднее owner разрешит отдельный
fallback experiment, он получает собственный заранее принятый profile и не
подменяет baseline evidence.

## Reproducibility и invalidation

Run reproducible только при совпадении всех frozen generations и bytes.
Изменение хотя бы одного из следующих элементов создаёт новый run generation:

- corpus bytes, membership, strata или reviewer mapping policy;
- exact model tag/digest, Ollama version или residency evidence;
- endpoint, schema, prompt policy, profile/options/thinking/lifecycle;
- harness, validator, repair/fallback, rubric или analysis code;
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
