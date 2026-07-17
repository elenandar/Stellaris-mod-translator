# План разработки

План организован по доказательствам, а не календарю. Каждый этап создаёт проверяемые артефакты и имеет exit criteria. Невыполненный критерий останавливает зависимые работы.

Разделы плана используют те же обозначения `M*`, что и [дорожная карта](roadmap.md).

## M0R. Персональный local-only baseline

Зафиксировать:

- один владелец, текущий Apple Silicon Mac и личные текущие/будущие playsets;
- Rust CLI как интерфейс MVP;
- локальный SQLite workspace и проверяемый backup/export;
- только локальный Ollama, без cloud providers и скрытого fallback;
- четыре редакционных состояния и human-only `editorially_approved`;
- рабочую гипотезу RU bundle per playset без превращения её в канон;
- отсутствие обязательств по UI, Windows/Linux, beta и публичной поставке.

Exit criteria:

- owner decision, ADR, canons, strategy, architecture, stack и roadmap согласованы;
- датированный environment evidence сохранён без private mod content;
- все открытые решения назначены конкретному M1 spike;
- задачи M1 содержат рекомендуемую Codex model/reasoning tier.

## M1A. Формат, угрозы и playset evidence

Работы:

- инвентаризировать BOM, newline, comments, quotes, duplicate keys, version suffixes, escapes, markup и malformed sources;
- проверить descriptors, dependencies, launcher paths, `replace/`, load order и реальные duplicate semantics;
- сравнить `per-source`, `playset-bundle` и `hybrid` по read-only данным реальной установки и в изолированном disposable root;
- определить детерминированный source order, collision policy, uninstall и rollback;
- смоделировать Workshop update во время чтения, symlink/TOCTOU, traversal, disk-full и crash points;
- создать threat model, format/markup specs, version profile и corpus manifest;
- построить synthetic/minimal fixtures и независимый holdout;
- сделать тонкий read-only research harness для inspect/parse/round-trip experiments.

M1A не пишет в Stellaris, Workshop, active mod/output paths или launcher state. Если реальная активация окажется необходимой для решения, она переносится в отдельный поздний gate с явным разрешением владельца.

Exit criteria:

- каждая поддержанная конструкция имеет fixture и ожидаемую классификацию;
- неизвестные варианты перечислены как unsupported, а не молча нормализованы;
- `parse → render` byte-identical на исследовательском корпусе;
- immutable generation либо clean abort доказаны при изменении Workshop;
- layout кандидата детерминированно строится и удаляется только в disposable root; реальная установка остаётся непроверенной и не маскируется;
- export policy выбрана evidence либо явно оставлена blocked;
- threat/format/publish contracts приняты до production implementation.

Отчёт завершается ровно одним verdict: `GO` или `BLOCKED`. Только `GO` может участвовать в gate M2; корректный `BLOCKED`-отчёт принимается как evidence, но не разрешает реализацию.

## M1B. Feasibility качества локального Ollama

Этот этап идёт параллельно с M1A и не пишет в active mod/output paths.

Работы:

- зафиксировать local tags, full digests, residency, Ollama version и capability probes;
- сравнить GLM 4.7 Flash, DeepSeek R1 32B и GPT-OSS 20B без заранее назначенного победителя;
- использовать одинаковые schema, prompt policy и явные `num_ctx` 8–16K, temperature/seed/options;
- собрать стратифицированный corpus: UI, mechanics, narrative, dialogue, humor, gender/case, lore terms и typed atoms;
- отделить tuning set от независимого holdout;
- провести человеческую оценку смысла, русского текста, лора и severity; для критических категорий использовать повторную независимую разметку;
- измерить atom/schema stability, latency, memory и долю repair/fallback;
- проверить, помогает ли независимый model-review, а не предполагать это.

Raw corpus остаётся между локальным benchmark harness, Ollama и человеком-редактором. Codex получает только taxonomy, opaque sample IDs, scores и redacted findings; prompts или excerpts с private/copyrighted текстом не публикуются.

Exit criteria:

- есть воспроизводимый benchmark report с exact model digests/options;
- определён baseline model/profile либо честно зафиксировано `QUALITY_NOT_FEASIBLE`;
- critical false accepts отсутствуют в выборке, а статистическая неопределённость и размер корпуса указаны;
- high-risk категории и обязательная human-review policy определены;
- ни один benchmark output не активирован как игровой перевод.

Отчёт завершается ровно одним verdict: `QUALITY_FEASIBLE` или `QUALITY_NOT_FEASIBLE`. Неуспех M1B останавливает ветку до M2, даже если format evidence положителен.

## M2. Safety kernel и технический CLI

M2 начинается только при совместных verdicts `M1A: GO` и `M1B: QUALITY_FEASIBLE`. Принятие достоверного отрицательного отчёта не является разрешением продолжать.

Работы:

- byte reader, immutable generations и version profiles;
- lossless lexer/CST;
- typed parser внутритекстовой разметки;
- controlled renderer только для language header и human spans;
- diagnostics `source_warning / output_error / blocker`;
- output containment и versioned staging;
- canonical root-disjointness checks для equality, ancestor/descendant overlap и symlink aliases;
- команды `inspect`, `parse`, `round-trip`, `validate`, `render-dry-run`;
- golden/holdout, property, fuzz/mutation и integration tests.

Exit criteria:

- round trip идентичен для 100% заявленной taxonomy и независимого holdout;
- malformed/unknown input сохранён opaque либо заблокирован с позицией;
- controlled render не меняет неразрешённые байты;
- mutation/fuzz не приводит к panic, escape from root или silent data loss;
- source hashes неизменны во всех integration tests;
- model output физически не может обойти renderer/validator и активировать artifact.

## M3. Инкрементальный engine и playset publishing

Работы:

- discovery manifests, dependencies и stable mod identity;
- SQLite schema/migrations для generations, units, contexts, jobs, findings и artifacts;
- раздельные raw/semantic/context/policy fingerprints, stable duplicate matching и dependency/glossary selection edges для точечной инвалидации;
- diff states и explainable invalidation;
- persistent queue, pause/cancel/resume и idempotency;
- deterministic playset assembly и explicit collision overrides;
- versioned build/publish protocol, crash matrix, last-known-good и rollback;
- exportable backup с integrity manifest и явным privacy warning, выбранное владельцем место хранения и проверяемый restore.

Exit criteria:

- неизменный playset создаёт ноль work units;
- изменение затрагивает только доказанно зависимые units;
- удаление source/key не уничтожает manual history;
- crash на каждой стадии не оставляет частичный active artifact или дубли;
- migrations, backup/restore и rollback проверены на предыдущем snapshot;
- source order и все collision decisions воспроизводимы.

## M4. Локальный translation quality engine

Работы:

- importer официальной English/Russian localisation из локальной установки с version provenance;
- mod-specific glossary/lore packs, forms, aliases и approval history;
- context graph для пилотных типов;
- translation memory с context compatibility;
- Ollama adapter с digest pinning и profile enforcement;
- pipeline `draft → machine review → findings → repair/human review`;
- checks для entities, numbers, polarity, modality, effects, terminology и русского текста;
- editorial queue и защита manual decisions.

Exit criteria:

- provider result не способен изменить code/atoms даже при adversarial input;
- cancel/unavailable model не теряет состояние и не подменяется другой моделью;
- несовместимый контекст не переиспользует перевод автоматически;
- thresholds откалиброваны на M1B corpus и holdout;
- high-risk content попадает в human review;
- только человек может назначить `editorially_approved`.

## M5. Стабильный повседневный CLI-процесс

Поддерживаемый путь:

```text
playset → inspect → plan → translate → review → dry-run build
        → validated RU artifact → publish → in-game smoke → update/rollback
```

Пилоты включают small mechanics mod, narrative/event-heavy mod, крупный glossary-heavy mod, duplicates/malformed source, существующую русскую локализацию и обновления с add/change/delete.

Exit criteria:

- выбранные личные playsets проходят end-to-end;
- blocked/fallback units объяснимы и не нарушают artifact;
- in-game smoke подтверждает load order и отсутствие missing/broken localisation;
- update, disk-full, отмена, restore и rollback проверены;
- владелец может повторить процесс по документации без обхода gates;
- финальный отчёт принят с Codex `GPT-5.6 Sol, Ultra` и человеческим литературно-лорным review.

## Возможные решения после M5

Только после стабильного CLI отдельный ADR может разрешить:

- лёгкий Tauri/React UI, если CLI действительно мешает повседневной работе;
- дополнительную платформу;
- публичное распространение и выбор лицензии;
- cloud provider с отдельной privacy/consent моделью.

Ни один из этих пунктов не является частью текущего обязательства.

## Формат задач Codex

Каждое создаваемое задание содержит:

- текущий milestone и разрешённый слой работы;
- входные evidence и запрет выхода за scope;
- точные deliverables и exit criteria;
- обязательные проверки и stop conditions;
- рекомендуемые Codex model и reasoning tier по [дорожной карте](roadmap.md) и [AGENTS.md](../AGENTS.md).

Codex model — инструмент разработки. Она не становится runtime-моделью переводчика и не меняет local-only контракт Ollama.

## Сквозные правила

- Каждая задача привязана к milestone criterion или defect evidence.
- Parser/validator changes прогоняют полный corpus и holdout.
- Private пользовательские данные не коммитятся и не уходят в Codex/cloud tools. Local research helpers возвращают только metadata, hashes, redacted/aggregate evidence или synthetic fixtures после leakage check.
- Новая dependency получает обоснование, license/security review и update owner.
- Документация меняется вместе с решением.
- Функция, не нужная следующему вертикальному доказательству, остаётся вне scope.
