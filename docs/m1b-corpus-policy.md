# Политика corpus и privacy для M1B

- Статус: `M1B: NOT_EVALUATED`; protocol under review, raw corpus не читался в
  M1B-0
- Scope: будущий локальный benchmark и только synthetic conformance текущей задачи
- Gate state: `M1A: BLOCKED`; `M2: FORBIDDEN`

Эта политика дополняет M1A policy, но не ослабляет её. Она определяет, какие
данные может видеть будущий локальный benchmark, человек-reviewer и публичное
evidence. Codex, subagents, Git и PR получают только synthetic data либо
allowlisted sanitized evidence.

## Классы данных

| Класс | Определение | Где разрешены raw bytes | Что может быть опубликовано |
|---|---|---|---|
| `synthetic` | полностью вымышленные cases, созданные без копирования или перефразирования corpus | repository fixtures и local runner | сами явно synthetic fixtures, controlled codes и агрегаты |
| `official` | copyrighted localisation из локальной установки игры и связанный контекст | только read-only local source и ignored private benchmark storage | только агрегаты и controlled codes после leakage gate |
| `private` | local/Workshop mods, существующие переводы, human annotations и будущие model inputs/outputs | только local ignored storage, Ollama loopback и локальные human-review surfaces | только агрегаты и controlled codes после leakage gate |
| `sanitized evidence` | allowlisted производное evidence без raw/free-text content | repository docs/PR после leakage gate | controlled codes, агрегаты, protocol/profile hashes и полные model digests |

`sanitized evidence` не является corpus и не может возвращаться в tuning или
holdout как текстовый sample. Generated text, старый проект и существующий
перевод не являются истиной; provenance class сохраняется даже после redaction.

Synthetic fixture обязан быть написан с нуля, иметь очевидно вымышленные atoms
и не содержать реальные mod names, localisation keys, excerpts, filenames,
paths, tags/digests из local inventory или стилистическую реконструкцию private
текста. Fixed UUID/digest-shaped values допустимы только как явно synthetic test
values и не используются как identity будущего live run.

Только synthetic fixture может публиковать exact invented atom literal,
occurrence/cardinality и synthetic position. Для official/private corpus exact
atom value и position проверяются только локальным validator по private bytes.
Public report не содержит эти values, positions, row-level IDs или
content-derived hashes; наружу выходят только controlled atom failure codes и
aggregate missing/extra/value/position/multiplicity counts.

## Local-only storage

Raw official/private corpus не коммитится. Если будущему benchmark нужна
локальная копия, она размещается только под уже ignored root
`benchmarks/private/` с owner-only access. Логические зоны разделены как минимум
на:

- `tuning` — доступна только tuning phase;
- `holdout` — закрыта для tuning process и раскрывается только после freeze;
- `review` — raw outputs/annotations для локального human review;
- `scratch` — временные artifacts с обязательным cleanup.

Названия зон являются policy labels, а не разрешением выводить фактический path.
Harness принимает root явно, не выполняет home/environment discovery и не ищет
game, Workshop, launcher или model-store paths. Source остаётся read-only.
Benchmark writes разрешены только внутри заранее созданного ignored benchmark
root; active/source paths и sibling roots запрещены.

## Tuning/holdout separation

Разделение одновременно физическое и логическое:

1. разные directory roots, manifests и file descriptors;
2. disjoint UUIDv4 sample sets, проверяемые до первого request;
3. tuning invocation технически не принимает holdout root;
4. holdout mapping недоступен prompt/schema/profile authors до freeze;
5. holdout runner принимает frozen protocol generation и прекращает работу при
   mismatch;
6. results двух splits не записываются в общий mutable table;
7. cross-split duplicates, derived variants и shared source unit блокируют run.

Один исходный unit и его перефразирование/вариант не могут оказаться в разных
splits. Такая проверка выполняется локально и не публикует content fingerprints.
После первого раскрытия holdout любое изменение pipeline превращает этот corpus
в tuning data; для нового verdict нужен новый независимый holdout.

Каждая analysis row для agreement, D1–D5/statistical gates и CFA явно сохраняет
split provenance из frozen sample. Synthetic-scope materializer повторно
проверяет только analysis-source subset: trusted proposal bundle/protocol,
canonical corpus, candidates, results, findings и HGT. Затем он фиксирует exact
row multiset одного scope; HGT materializer также переносит split в derived
agreement row. Этот capability подтверждает synthetic scope consistency, но не
provider/request/context/implementation/benchmark/coverage/acceptance/aggregate/
execution admission и никогда не даёт `decision_grade_eligible=true`.

`synthetic_scope_*` helpers возвращают только явно помеченные diagnostics.
Caller UUID/split labels, relabel, subset, extra либо изменённые rows не становятся
scope evidence. Production decision helpers не принимают caller rows или
synthetic-scope token: они получают rows только из отдельного full decision
admission и принимают лишь `holdout`. Document schema v4 является partial M1B-0
и такой admission не выдаёт. Missing/unknown split отклоняется, mixed-split
scope получает controlled `STATISTICAL_SPLIT_MIXED`, а tuning никогда не
удовлетворяет holdout minimum, confidence bound, agreement либо verdict gate.

## Source-unit clusters, strata и allocation

До split каждый sample получает локальный `source_unit_cluster_id` по общей
source/event/dialogue/context lineage. Related lines, paraphrases и variants
одного cluster обязаны оставаться в одном split; один cluster не может появиться
под разными opaque IDs как независимое evidence. Private mapping проверяет
lineage локально и не публикует source names либо relationship hashes.

Каждая immutable source generation получает случайный opaque
`source_generation_id`, не производный от mod name, path или content hash. Все
её clusters внутри одного primary stratum сворачиваются в одну statistical unit
для tuple `(candidate/profile, gate или dimension, stratum,
source_generation_id)`. Поэтому одна source generation даёт максимум один trial
конкретному stratum claim, даже если содержит много files, events или context
blocks. Ambiguous common lineage объединяется conservative либо даёт split
blocker.

Один cluster имеет ровно один primary stratum; его перенос в другой stratum
блокируется как `SOURCE_CLUSTER_STRATUM_MISMATCH`. Несколько rows внутри
source-generation/stratum unit агрегируются conservative: success только если
успешны все applicable rows. Secondary risk labels не увеличивают `n`.
Один cluster также навсегда связан ровно с одной source generation; повторение
того же cluster ID с другим `source_generation_id` блокируется как
`SOURCE_CLUSTER_GENERATION_MISMATCH`. Одна source generation может содержать
несколько clusters, но обратное переименование не создаёт новую statistical
unit.

Одна source generation может участвовать в нескольких strata и дать один trial
каждому отдельному stratum claim. Эти trials нельзя суммировать как независимый
overall binomial denominator. Descriptive overall distinct-source count
сворачивает source generation ровно один раз с conservative outcome; overall
confidence/pass gate запрещён.

Closed primary-stratum enum состоит ровно из `ui`, `mechanics`, `narrative`,
`dialogue`, `humor_wordplay`, `gender_case`, `lore`, `typed_atoms`. Proposal
allocation — по `46` applicable source-generation units каждого stratum, то
есть `368` stratum quota slots на candidate/profile; это не pooled independent
`n`. Все три candidates получают один frozen manifest. Exact Bonferroni family,
per-dimension minima `46/30/22/22` и дополнительный zero-event minimum `203` на
каждый proposed auto-eligible class заданы в
[quality rubric](specs/m1b-quality-rubric.md#closed-strata-и-coverage-proposal).

В executable synthetic schema `auto_eligible_candidate` разрешён только для
primary stratum `ui` либо `mechanics`; любая иная комбинация получает
`RISK_CLASS_STRATUM_MISMATCH`. Narrative/dialogue/humor/gender/lore/typed-atoms
row не становится auto-eligible сменой label. Это closed M1B-0 conformance rule,
но не owner acceptance production routing policy.

Эти числа, taxonomy assignment, auto-eligible list и reviewer allocation
остаются proposal. До их отдельного owner acceptance holdout blocked с
`OWNER_DECISION_REQUIRED`; недостаток coverage не исправляется pooling строк,
clusters, candidates, profiles либо generations.

## Opaque identities

Live sample и reviewer IDs создаются криптографически случайными UUIDv4. Они:

- не производны от content, key, filename, path, mod, source hash, reviewer name
  или model;
- не кодируют split, category, sequence или candidate;
- уникальны во всём run и не переиспользуются между generations;
- имеют локальную private mapping к source/reviewer identity;
- проверяются на duplicate и tuning/holdout overlap до обработки.

Reviewer UUID не доказывает независимость: private mapping дополнительно
гарантирует, что две обязательные human reviews выполнили разные люди. Model
reviewer получает отдельную role и никогда не считается человеком.

Reviewer role immutable во всём run. Reviewer ID не совпадает с candidate,
sample, source-cluster, atom/occurrence, result, finding, review или другим
opaque ID. Каждый primary-blinded holdout output, пригодный для content review,
получает human D2–D5 ground truth, включая будущие auto-eligible classes;
critical-risk получает две разные initial human identities. Закрытое исключение
— `self_identifying_output`: D2–D5=`blinding_failed`, zero primary success,
primary HGT запрещён; optional `secondary_unblinded` evidence не заменяет HGT и
не входит в primary agreement/quality gate.

Finding-review records не содержат raw annotations, но сохраняют exact
finding/category/dimension, reviewer-specific closed severity/hard-fail/
mandatory-review outcome и mapping/blinding provenance. Эти initial outcomes
immutable; любые две initial human reviews требуют distinct human identities,
а top-level downgrade без matching outcome либо third-human adjudication не
является sanitized evidence.

Public evidence для official/private corpus не публикует row-level sample или
reviewer mapping. Synthetic conformance fixtures могут содержать только явно
synthetic opaque IDs.

## Запрещённые sinks

Для `official` и `private` запрещено помещать raw prompts, inputs, outputs,
translations, annotations, keys, excerpts, filenames или paths в:

- Git, commits, branches, issues, PR body/comments и CI artifacts;
- Codex/cloud development context, subagent messages или screenshots;
- stdout, stderr, progress output, traceback, raw exception messages и logs;
- benchmark filenames, directory names, database names или report labels;
- telemetry, clipboard automation или remote service.

Ошибки пересекают CLI boundary только как controlled code и агрегированные
counts. Diagnostic record использует opaque UUID и enum fields; свободного raw
text поля нет. Даже local terminal не является допустимым sink для raw content.

## Provider persistence admission

До допуска official/private bytes будущий M1B-1 использует только synthetic
canaries и доказывает либо fail-closed блокирует daemon/request logging,
history/continuation persistence, crash reports/diagnostics, telemetry,
temporary prompt/output storage, retention и cleanup. Exact version,
configuration, проверенные storage/reporting surfaces, observation window и
cleanup outcome входят в private preflight manifest.

Неизвестный sink, неполная inventory, ambient diagnostics либо отсутствие
проверяемой retention/cleanup policy дают `PROVIDER_PERSISTENCE_UNPROVEN` до
первого private request. M1B-0 не выполняет live probe и не читает Ollama/model
store. Даже после admission каждый sample отправляется stateless: новый request,
без history/context reuse, continuation между candidates/splits/stages и
thinking trace в следующем request или human presentation.

## Hash и publish policy

Content-derived hashes official/private corpus полезны только как локальный
immutability control внутри ignored storage. Они запрещены в public evidence,
поскольку могут использоваться для confirmation/deanonymization. Это включает
whole-file, line, token, prompt, output, filename/path и set-membership hashes.

Публикуемый `protocol_hash` вычисляется только по public/frozen contract bytes и
не включает raw corpus, private path, private identifier или их hashes. Public
evidence для live benchmark ограничено:

- controlled error/status codes;
- агрегированными counts, rates, distributions и confidence bounds;
- hashes public protocol/schema/profile bytes;
- полными exact model digests;
- случайным opaque corpus generation без content-derived semantics.

Executable `definition_bundle.components[].definition` M1B-0 содержит только
public synthetic UTF-8 definitions из trusted registry. Это поле не является
универсальным payload channel: official/private corpus bytes, prompt/output,
private model/profile metadata, paths, identifiers и их content-derived hashes
в нём запрещены.

Exact public synthetic corpus является явным исключением из запрета на public
corpus digests: trusted `corpus_policy` bind-ит его version/generation и digest
`SHA-256(ASCII("stellaris-m1b-synthetic-corpus-v1") || NUL ||
u64be(len(canonical_json)) || canonical_json)`. `canonical_json` — ASCII JSON
exact closed `corpus` object с escaped non-ASCII, sorted object keys и compact
separators. Validator сравнивает также сами canonical bytes. Поэтому coherent
drift expected atoms/splits/metadata вместе с matching observed atoms получает
`CORPUS_DEFINITION_MISMATCH`, а не новый pass под старой generation.

Эта binding безопасна для публикации только потому, что corpus полностью
synthetic. Для official/private live corpus content-derived digest остаётся
local-only immutability control и не попадает в `corpus_policy`, public bundle,
report или sanitized evidence; наружу выходит только случайный opaque corpus
generation. Полный model digest является отдельно разрешённой provenance
identity и не заменяет residency evidence.

Algorithm, domain separation, exact-byte framing и deterministic bundle order
для public protocol hashes заданы в
[benchmark contract](specs/m1b-benchmark-contract.md#canonical-public-hash-framing).
Это framing никогда не получает raw official/private corpus bytes либо их local
immutability hashes.

## Retention и deletion

Canonical official/private sources остаются read-only inputs и не удаляются
benchmark cleanup. Для artifacts, созданных самим benchmark, действует policy:

1. request buffers и transient parse objects живут только в process memory;
2. scratch artifacts удаляются при нормальном завершении и после controlled
   failure; cleanup failure блокирует публикацию evidence;
3. raw outputs и human annotations сохраняются только в sealed ignored run root
   до завершения adjudication и owner decision;
4. retention deadline фиксируется до run; **предложенный default — удалить
   benchmark-created raw outputs/annotations не позднее 30 дней после финального
   owner decision, ожидает owner acceptance**;
5. продление retention принимается до deadline отдельным локальным owner record;
6. deletion report содержит только generation, aggregate deleted/failed counts
   и controlled codes, без names/paths/hashes;
7. неуспешное подтверждение deletion оставляет privacy blocker.

Accepted private translations и их backup не являются временным M1B artifact.
Их lifecycle относится к будущим M3/M4 и не может быть удалён этой policy.

## Leakage gate

Перед любым commit, PR update или передачей evidence в Codex локальный exporter:

1. строит новый report исключительно из publishable allowlist schema;
2. запрещает free-text, filename/path и unknown fields;
3. локально сравнивает candidate evidence с nonempty whole-file, physical-line и
   long-token fingerprints всех наблюдавшихся raw roles;
4. проверяет private identifiers, absolute paths, prompt/output/annotation fields
   и content-derived corpus hashes;
5. возвращает наружу только `passed`, aggregate counts и controlled code;
6. после pass выполняется полный staged-diff review;
7. при любом post-scan byte change повторяет gate с нуля.

Scanner не доказывает отсутствие каждого короткого substring, поэтому allowlist
export и human diff review обязательны одновременно. Match, неизвестное поле,
raw exception или сомнение в provenance дают `LEAKAGE_DETECTED` и немедленную
остановку без вывода совпавшего значения.

Blinding failure не является основанием удалить assigned output из denominator.
Self-identifying output остаётся aggregate failure в candidate/profile/stratum
coverage; primary HGT запрещён, а unblinded review хранится только как secondary
local evidence, не заменяет primary blinded ground truth, не восстанавливает
success и не участвует в primary agreement/quality gate.

## M1B-0 boundary

Текущая задача не читает ни один official/private sample, не создаёт prompt,
translation, annotation или model output и не вызывает Ollama. Только synthetic
conformance data может находиться в repository. Успех synthetic validator
доказывает форму контракта, но не privacy реального будущего run и не даёт
`QUALITY_FEASIBLE`.

Controlled no-output failure и `terminal_status=not_applicable` без model
attempt не могут иметь content/quality findings, human/model finding reviews или
human ground truth. Они требуют `technical_conformance=not_observed`, пустые
`observed_atoms` и D1–D5 `not_evaluated`; technical aggregate считает success
только для output-bearing `synthetic_conformant` row. Controlled failure остаётся
denominator failure, а canonical no-attempt row — explicit non-observation без
success. И synthetic diagnostic-scope materialization, и будущая full-admission
decision materialization сохраняют любую no-output row как applicable failure во
всех quality/gate scopes и не добавляют её в CFA event-rate denominator;
synthetic результат остаётся diagnostic/ineligible, production decision требует
отдельного full admission, а controlled error никогда не echo-ит input, content
или path.

M1B-0 sample schema v4 включает `source_generation_id`,
`source_unit_cluster_id`, stratum и risk class и проверяет только synthetic
split/collapse invariants, включая запрет split overlap и stratum drift одного
cluster. Эти fields не доказывают real mod lineage, source-generation identity,
independence или достаточный `n`; до holdout controls должны войти в новую
owner-accepted corpus/analysis definition и пройти local private verification.
