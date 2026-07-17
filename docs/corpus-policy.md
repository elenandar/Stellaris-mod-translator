# Политика корпуса M1A

- Статус: `M1A — in review`
- Дата: 17 июля 2026 года
- Владелец raw corpus: владелец репозитория

## Назначение

Политика разрешает исследовать byte-level форму текущей локальной установки, не распространяя игровые или модификационные тексты. Она применяется к research helper, локальным ignored artifacts, Git diff, subagents и PR.

## Классы данных

| Класс | Примеры | Где разрешён | Что можно публиковать |
|---|---|---|---|
| S — synthetic | минимальные вымышленные localisation/descriptors и fault fixtures | `fixtures/m1a/`, tests, Codex, Git, PR | полный fixture и expected classification |
| O — official copyrighted | локальные файлы установленной игры | только read-only source и память локального helper | counts, enums, booleans, sizes, hashes, version |
| P — private mod/playset | Workshop/local mods, launcher/playset metadata, существующие переводы | только локальный helper и его process memory | агрегаты, opaque IDs, order/generation digests, redacted warnings |
| R — repository evidence | contracts, synthetic tests, sanitized report | Codex, Git и PR после leakage check | полный текст |

Raw классов O/P запрещён в prompts, subagent messages, stdout/stderr, traceback, screenshots, fixtures, Git history, PR body и web queries. Названия модов, localisation keys, source excerpts и абсолютные source/launcher paths также считаются raw.

## Выборка и воспроизводимость

M1A использует два разных слоя evidence:

1. **Synthetic conformance set.** По одному минимальному fixture на каждую заявленную конструкцию и отдельные malformed/unknown/adversarial cases. Fixtures доступны review и задают ожидаемую классификацию.
2. **Локальный census.** Helper перечисляет все подходящие localisation files в auto-discovered game и Workshop roots и анализирует каждый файл. Private `path` из local outer descriptors не follow-ится; такой source явно исключается из denominator и создаёт blocker. Это census объявленного scope текущей generation, а не статистическая экстраполяция.

Для дополнительной cross-check census детерминированно делится по первому байту SHA-256 фактически прочитанных bytes: значения `0..51` образуют holdout, остальные — development cohort. Это не статистически независимая внешняя выборка: тот же scanner обрабатывает оба cohort. Evidence публикует cohort-level counts/inventory/round-trip failures, но не membership. Любое изменение taxonomy после просмотра holdout требует нового version profile и полного run.

Corpus manifest включает только:

- дату и profile ID;
- число файлов/bytes и cohort counts;
- aggregate generation digest над отсортированными opaque records;
- count по format/markup categories;
- unsupported/malformed counts;
- round-trip и pre/post manifest equality;
- redacted warning codes.

## Разрешённый output helper

Stdout — один JSON document с фиксированными полями. Разрешены:

- целые counts и byte sizes;
- boolean pass/fail;
- публичные enum/category names;
- SHA-256 и domain-separated opaque IDs;
- нормализованная публичная версия игры;
- redacted diagnostic code без source value.

Запрещены filenames, directory names, descriptor values, DB rows, localisation keys/values, snippets и exception messages, сформированные из raw input. Все ошибки пересекают внешний boundary как стабильный code и класс операции. В обычном режиме traceback отключён.

## Локальное хранение и удаление

- Текущий helper удерживает принятые bytes только в памяти и использует clean-abort strategy; raw snapshot на диске не материализуется.
- Если будущий research helper материализует snapshot, он может писать только в новый `mktemp` root после disjointness gate, отдельно от candidate, и обязан удалить raw bytes после run.
- Sanitized JSON можно сохранить только под уже игнорируемым `artifacts/` для локального audit.
- Git не является backup корпуса. Helper не создаёт SQLite workspace, translation cache или generated bundle.

## Leakage check

Перед commit и перед созданием PR локальный helper:

1. строит в памяти SHA-256 для exact non-header lines длиной от 4 bytes и structured lexical tokens длиной от 64 bytes, а также хранит только внутри процесса descriptor/active values, полные canonical private paths и их непубличные components длиной от 8 bytes;
2. дважды стабильно читает все regular files текущего repository tree, включая synthetic fixtures и подготовленный ignored PR body;
3. исключает только `.git` и tool caches; suffix allowlist не применяется;
4. возвращает только denominators, match counts по типу и `passed`;
5. завершает проверку non-zero при любом match, unreadable candidate или невозможности построить source fingerprints.

Public language-header lines исключены из exact-line fingerprints, чтобы grammar token не давал ложный match. Проверка ловит короткую полную строку и длинный lexical fragment, но не является математическим доказательством отсутствия каждого возможного короткого substring. Поэтому после scan файлы явно stage-ятся без дальнейшего редактирования, выполняется полный cached-diff review, а PR body берётся из уже просканированного файла. Любой post-scan byte change требует повторного scan.

## Web и внешние источники

Web search разрешён только по публичной технической документации. Запросы не содержат private identifiers, hashes для deanonymization или фрагменты corpus. Внешние технические утверждения в specs/report получают прямую ссылку на первичный источник; недокументированное engine behavior остаётся assumption или blocker.

## Stop conditions

Run немедленно прекращается, если:

- raw input попал либо мог попасть в stdout/stderr;
- source generation нестабилен;
- root принадлежность неоднозначна;
- helper для evidence потребовал бы писать в source/Workshop/game/launcher/active path;
- leakage scan не может завершиться fail closed;
- для классификации неизвестного формата пришлось бы угадывать.
