# План разработки

План организован по доказательствам, а не по календарю. Каждый этап создаёт проверяемый артефакт и имеет exit criteria. Невыполненный критерий останавливает зависимые работы.

## P0. Подтвердить рамки проекта

Результат:

- выбранная лицензия репозитория и политика использования тестовых модов;
- первая поддерживаемая версия Stellaris и минимальная версия macOS;
- 5–8 пилотных модов разных классов с разрешённым использованием для локального тестирования;
- подтверждение стратегии «один companion на один source» и cloud opt-in;
- начальный threat model и ADR-0001 о modular monolith.

Exit criteria: открытые продуктовые решения не меняют устройство parser, хранения или публикации.

## P1. Исследование форматов и упаковочный spike

Работы:

- инвентаризировать реальные варианты localisation: BOM, newline, comments, quotes, duplicate keys, version suffixes, escapes, markup и malformed sources;
- проверить descriptors, dependencies, launcher paths и load order на реальной установке;
- построить обезличенный fixture corpus и compatibility matrix;
- проверить Tauri build/signing, filesystem permissions и packaged smoke на Apple Silicon;
- сравнить варианты parser контекста scripts и зафиксировать решение ADR.

Exit criteria:

- каждая заявленная конструкция имеет fixture и ожидаемую классификацию;
- неизвестные варианты перечислены как unsupported, а не потеряны;
- пустой companion mod устанавливается и удаляется без изменения источника;
- packaging spike воспроизводится из чистого checkout.

## P2. Ядро технической безопасности

Работы:

- byte reader и version profiles;
- lossless lexer/CST локализации;
- typed parser внутритекстовой разметки;
- controlled renderer только для language header и human spans;
- diagnostics с source warning/output error/blocker;
- round-trip, property, fuzz/mutation и golden tests;
- path containment и source snapshot checks.

Exit criteria:

- `parse → render` byte-identical для 100% поддержанного fixture corpus;
- malformed/unknown input либо сохранён как opaque, либо заблокирован с точной позицией;
- controlled render не меняет ни одного неразрешённого байтового участка;
- fuzz/mutation не приводит к panic, выходу за root или молчаливой потере данных;
- исходные хэши неизменны во всех integration tests.

Это первый жёсткий шлюз. До него не строится массовый LLM-конвейер.

## P3. Модель проекта и инкрементальность

Работы:

- discovery manifest, dependencies и stable mod identity;
- SQLite schema/migrations для snapshots, units, contexts, jobs, findings и artifacts;
- unit/source/context identity;
- diff states: unchanged, new, changed, moved, deleted, context-changed, blocked;
- persistent queue, pause/cancel/resume, idempotency;
- staging, atomic publish, last-known-good и rollback.

Exit criteria:

- повторный запуск неизменного корпуса создаёт ноль work units;
- одно изменение затрагивает только доказанно зависимые units;
- удалённый ключ исчезает из нового артефакта, не уничтожая manual history;
- crash на каждой стадии восстанавливается без частичного publish и дублей;
- миграция БД и rollback проверены на предыдущем schema snapshot.

## P4. Контекст, терминология и перевод

Работы:

- importer официальной английской и русской локализации из локальной установки с привязкой к версии;
- versioned glossary, формы, aliases, source и approval workflow;
- context graph для событий и других пилотных типов;
- translation memory с context compatibility;
- provider interface, Ollama adapter, consent и secrets;
- benchmark облачного baseline на том же golden corpus;
- draft → semantic/lore review → Russian editor → repair;
- проверки entities, numbers, polarity, modality, effects и terminology.

Exit criteria:

- provider result не способен изменить code/atoms даже при adversarial input;
- недоступная или отменённая модель не теряет состояние;
- одинаковый текст в несовместимых контекстах не переиспользуется автоматически;
- на вручную проверенном golden corpus нет критических semantic defects;
- пороги confidence откалиброваны на человеческой разметке, включая false positive/negative.

## P5. Вертикальный CLI-срез

Один внутренний CLI выполняет полный путь `folder → analysis → translation → validated companion → update`. Он нужен для воспроизводимых тестов и не заменяет конечный UI.

Пилотный набор обязательно включает:

- маленький механический мод;
- event-heavy narrative mod;
- большой мод с повторяющимися терминами;
- duplicate keys и malformed source;
- существующую/устаревшую русскую локализацию;
- обновление с добавлением, изменением и удалением строк;
- хотя бы один мод с нестандартным, но поддержанным markup.

Exit criteria: все пилоты проходят end-to-end, а blocked/fallback единицы объяснимы и не нарушают целостность компаньона.

## P6. Desktop UX

Работы:

- onboarding и auto-detection;
- folder picker и явный список source/output;
- экран анализа до запуска;
- прогресс по модам и стадиям, pause/cancel/resume;
- review только для проблемных единиц, glossary decisions и manual override;
- результаты, activation guidance, update и rollback;
- доступный интерфейс, клавиатура, русские тексты UI и понятные ошибки.

Exit criteria: новый пользователь выполняет основной сценарий без терминала; UI не может обойти domain gates; закрытие приложения во время работы безопасно.

## P7. Production hardening

Работы:

- signed/notarized macOS packages и update policy;
- Windows/Linux packaged smoke в CI;
- native secret storage, privacy review и diagnostic export preview;
- backup/restore SQLite, migration recovery, disk-space checks;
- performance profiling на большой коллекции;
- SBOM, dependency/license audit и release reproducibility;
- пользовательская документация и troubleshooting.

Exit criteria: чистая установка, обновление, откат и удаление проверены; критические threat-model сценарии закрыты; release artifact воспроизводим.

## P8. Закрытая beta и релизное решение

Beta расширяет corpus, а не функциональный scope. Собираются только обезличенные metrics и добровольные diagnostic bundles.

Exit criteria для решения о публичном релизе:

- ноль source mutations и технически повреждённых опубликованных artifacts;
- все blocker/correctness defects имеют regression tests;
- compatibility matrix подтверждена на заявленных версиях и платформах;
- semantic/lore quality достигла откалиброванного порога;
- известные ограничения описаны и имеют безопасный fallback;
- поддержка и обновление version profiles реалистичны по трудозатратам.

## Сквозные правила выполнения

- Каждая задача привязана к milestone criterion или defect evidence.
- Parser/validator changes всегда прогоняют полный corpus.
- Generated пользовательские данные не коммитятся.
- Новая зависимость получает объяснение, license/security проверку и владельца обновлений.
- Документация архитектуры меняется в том же PR, что и соответствующее решение.
- Функция, не нужная для следующего вертикального доказательства, остаётся вне scope.

