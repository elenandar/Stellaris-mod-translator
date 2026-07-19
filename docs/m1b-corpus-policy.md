# Политика corpus и privacy для M1B

- Статус: `M1B: protocol under review`; raw corpus не читался в M1B-0
- Scope: будущий локальный benchmark и только synthetic conformance текущей задачи
- Gate state: `M1A: BLOCKED`; `M2: forbidden`

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

Synthetic fixture bytes и их test hashes могут быть публичными, если leakage
gate подтверждает synthetic provenance. Полный model digest является явно
разрешённой provenance identity и не заменяет residency evidence.

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

## M1B-0 boundary

Текущая задача не читает ни один official/private sample, не создаёт prompt,
translation, annotation или model output и не вызывает Ollama. Только synthetic
conformance data может находиться в repository. Успех synthetic validator
доказывает форму контракта, но не privacy реального будущего run и не даёт
`QUALITY_FEASIBLE`.
