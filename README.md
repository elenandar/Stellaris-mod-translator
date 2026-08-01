# Stellaris Mod Translator

Персональный local-only CLI для безопасной работы с переводом модов Stellaris:
создания отдельного русского candidate через уже установленный Ollama и
построения приватной contextual reference memory из read-only vanilla
localisation.

MVP-0 реализован как небольшой Python-пакет без обязательных внешних
runtime-зависимостей. Source mod читается без изменений; CLI не регистрирует
результат в launcher и не пишет в Workshop, Stellaris или active mod paths.

## Статус

`MVP-6C` добавляет default-off подключение строго read-only
`exact_context_v1` к resumable `translate-mod --workspace`. Полный набор из
policy, database path, database SHA-256, logical digest и game version
обязателен целиком; single-pass и частичная конфигурация отклоняются до
workspace/provider writes. Только `exact_key_context` и
`exact_text_consensus` получают contextual prompt с одним `REFERENCE_ONLY`;
остальные terminal statuses сохраняют exact legacy prompt. Context binding
включён в существующий workspace schema-v2 `prompt_profile_hash`, а
contextual report использует schema v4 без raw reference. Обычный запуск без
memory сохраняет прежние request bytes, profile hash и report schema v3.

`MVP-6B` добавил строго read-only
`inspect-vanilla-context-coverage` и typed policy `exact_context_v1` поверх
private schema-v3 memory из MVP-6A. Exact key имеет приоритет; text fallback
разрешён только при полном отсутствии key и exact Russian-byte consensus.
Quarantine, aliases, conflicts и ambiguity остаются terminal exclusions.
Команда выводит только pins, digest и агрегированные counts. Reference не
применяется автоматически и не получает editorial approval.

`MVP-5C` смержен в PR №18, а разрешённое владельцем live-применение полного
decisions set завершилось отдельным private reviewed candidate: application
report schema v2 сохранил `619 accept / 1030 edit / 29 reject`, exact
localisation hash и явный technical residue `11 unsupported / 1 skipped`.
Residue не маскируется: весь мод остаётся `editorially_approved=false`.

`MVP-5H` добавляет `package-reviewed-mod`: команда превращает exact reviewed
candidate в отдельный private no-clobber пакет локального мода. Пакет содержит
только descriptors и `localisation/russian/**`; application report остаётся
metadata authority и не копируется в игровой content. Создание пакета не
устанавливает его, не регистрирует launcher, не меняет playset/load order и не
запускает Stellaris. Первый private NSC3 package smoke прошёл с byte-identical
localisation и нулевыми input/active/launcher mutations. Следующий отдельный
gate — bounded live install, порядок после source dependency и внутриигровой
smoke.

`MVP-5L` добавляет native support только для канонического qualified replace
layer: source `localisation/english/replace/**` проходит тот же lossless parser,
typed renderer, resumable workspace, review/application и packaging pipeline,
а candidate сохраняется как `localisation/russian/replace/**`. Неоднозначный
`localisation/replace/**`, case-варианты и Unicode-confusable написания
`english/replace` остаются fail-closed technical residue. Существующий active
replace-patch автоматически не удаляется, не мигрируется и не
консолидируется.

`MVP-5M` добавляет отдельный `consolidate-reviewed-mod`. Команда принимает
основной reviewed candidate и qualified replace supplement как две независимые
pinned provenance-ветви, заново проверяет canonical source→target mapping и
раздельные technical main-menu evidence и authoritative owner visual
confirmation schema v2 для фиксированного content-free visual scope, после чего
создаёт только новый private no-clobber пакет. Контракт различает `9` технически
и редакционно проверенных replace mappings и ровно `3` подтверждённые владельцем
visual targets. Старые packages, active mod, launcher и playset не меняются;
установка consolidated package остаётся отдельным следующим gate.

Owner decision от 26 июля 2026 года
supersede-ит AUTH-first процесс как зависимость практического MVP; PR №11 не
продолжается этой работой. Старые M1A/M1B записи ниже сохраняются только как
исторический evidence и не являются runtime authority для нового CLI.

Bounded mode предназначен для небольшого детерминированного candidate,
который владелец оценивает вручную. Он не означает полный перевод мода,
литературную готовность или `editorially_approved`.

## Установка и quick start

Требуется Python 3.9+ и локальный Ollama на `http://127.0.0.1:11434`.

```bash
python3 -m pip install -e .

python3 -m stellaris_mod_translator inspect \
  --source-mod /path/to/mod

python3 -m stellaris_mod_translator build-vanilla-memory \
  --english-root /path/to/vanilla/localisation/english \
  --russian-root /path/to/vanilla/localisation/russian \
  --game-version "exact-version-label" \
  --output /path/to/new-private-memory

python3 -m stellaris_mod_translator inspect-vanilla-memory \
  --database /path/to/new-private-memory/vanilla-memory.sqlite3

python3 -m stellaris_mod_translator inspect-vanilla-context-coverage \
  --source-mod /path/to/read-only-mod \
  --database /path/to/private-memory/vanilla-memory.sqlite3 \
  --database-sha256 64-lowercase-hex-database-pin \
  --logical-digest 64-lowercase-hex-logical-pin \
  --game-version "exact-version-label"

python3 -m stellaris_mod_translator translate-mod \
  --source-mod /path/to/mod \
  --output /path/to/new-candidate \
  --model exact-ollama-tag \
  --dry-run

python3 -m stellaris_mod_translator translate-mod \
  --source-mod /path/to/mod \
  --output /path/to/new-candidate \
  --model exact-ollama-tag \
  --max-occurrences-per-file 3

python3 -m stellaris_mod_translator translate-mod \
  --source-mod /path/to/read-only-mod \
  --output /path/to/new-full-candidate \
  --model exact-ollama-tag \
  --workspace /path/to/job.smt-workspace.sqlite3

python3 -m stellaris_mod_translator translate-mod \
  --source-mod /path/to/read-only-mod \
  --output /path/to/new-full-candidate \
  --model exact-ollama-tag \
  --workspace /path/to/job.smt-workspace.sqlite3 \
  --resume

python3 -m stellaris_mod_translator translate-mod \
  --source-mod /path/to/read-only-mod \
  --output /path/to/new-contextual-candidate \
  --model exact-ollama-tag \
  --workspace /path/to/contextual-job.smt-workspace.sqlite3 \
  --context-policy exact_context_v1 \
  --vanilla-memory-database /path/to/private-memory/vanilla-memory.sqlite3 \
  --vanilla-memory-database-sha256 64-lowercase-hex-database-pin \
  --vanilla-memory-logical-digest 64-lowercase-hex-logical-pin \
  --vanilla-memory-game-version "exact-version-label"

python3 -m stellaris_mod_translator build-review-pack \
  --source-mod /path/to/read-only-source-mod \
  --candidate /path/to/read-only-candidate \
  --output /path/to/new-review-pack

python3 -m stellaris_mod_translator build-review-pack \
  --source-mod /path/to/read-only-source-mod \
  --candidate /path/to/read-only-schema-v3-candidate \
  --candidate-report-sha256 64-lowercase-hex-report-pin \
  --output /path/to/new-full-review-pack

python3 -m stellaris_mod_translator apply-review-decisions \
  --source-mod /path/to/read-only-source-mod \
  --candidate /path/to/read-only-candidate \
  --decisions /path/to/exported-decisions.json \
  --output /path/to/new-reviewed-candidate

python3 -m stellaris_mod_translator apply-review-decisions \
  --source-mod /path/to/read-only-source-mod \
  --candidate /path/to/read-only-schema-v3-candidate \
  --candidate-report-sha256 64-lowercase-hex-report-pin \
  --decisions /path/to/final-full-decisions.json \
  --output /path/to/new-full-reviewed-candidate

python3 -m stellaris_mod_translator package-reviewed-mod \
  --reviewed-candidate /path/to/read-only-reviewed-candidate \
  --application-report-sha256 64-lowercase-hex-report-pin \
  --output /path/to/new-private-package \
  --mod-slug example_ru_local \
  --display-name "Example — Русская локализация (локальная)" \
  --dependency-name "Example" \
  --supported-version "4.4.*" \
  --planned-install-root "/path/to/future/Stellaris/mod" \
  --allow-technical-residue
```

`--dry-run` не вызывает Ollama и ничего не записывает. Обычный запуск требует
новый output path и создаёт `localisation/russian/**` вместе с локальным
`translation-report.json`. Fallback остаётся на английском и явно учитывается
в отчёте; candidate не получает `editorially_approved` автоматически.
Qualified replace layer `localisation/english/replace/**` поддерживается и
публикуется в `localisation/russian/replace/**`; суффикс
`_l_english.yml` меняется на `_l_russian.yml`. Неоднозначный immediate layout
`localisation/replace/**` не поддерживается: такие файлы пропускаются без
вызова Ollama и без candidate bytes. Неканонические case/Unicode-варианты
`english/replace`, English input в `other/replace` и вложенный
`english/**/replace` не нормализуются молча и также остаются skipped technical
residue. Файлы с non-English header, как и прежде, не являются translation
input и не добавляют residue только из-за собственного language-specific
`replace`-каталога. Любой fallback, deferred occurrence или пропущенный файл даёт явно
частичный status (`dry_run_partial` либо `technical_safe_partial`). Пустой
источник получает отдельный status `*_no_translatable_content`, а не
изображает завершённый перевод.

Необязательный `--max-occurrences-per-file N` принимает значения от `1` до
`100` и выбирает первые `N` поддержанных occurrences отдельно в каждом
English-файле. Unsupported occurrences не расходуют quota. Остальные
поддержанные occurrences попадают в полный candidate без изменения human text
и учитываются как `deferred`, отдельно от `fallback`. Без флага CLI сохраняет
полный режим MVP-0. Report schema v2 различает исходное число occurrences,
запланированные, принятые модельные результаты, fallback и deferred
occurrences и фиксирует bounded limit. `inspect` не является translation run и
сохраняет прежнюю schema v1 с `blocked_occurrences`; translation dry-run и
обычный запуск используют schema v2.

В translation schema v2 `translated_occurrences` сохраняет совместимость и
означает число model results, принятых после всех технических проверок.
`unchanged_accepted_occurrences` — их подмножество, у которого восстановленный
human span вместе с исходными whitespace и protected atoms byte-identical
входному span. Число фактически изменённых принятых spans равно
`translated_occurrences - unchanged_accepted_occurrences`. Fallback означает
непринятый или неподдержанный result с сохранённым английским текстом, а
deferred — поддержанный occurrence, который bounded run не отправлял модели.
Accepted unchanged не превращается во fallback и, как весь candidate, требует
human review. Наличие кириллицы не является техническим условием принятия:
имена и термины могут законно остаться латиницей.

## Возобновляемый полный перевод

Опциональный `--workspace PATH` включает full-mod режим MVP-4. Первый запуск
требует отсутствующий workspace, а продолжение — тот же существующий файл и
флаг `--resume`. Workspace-режим несовместим с `--dry-run` и
`--max-occurrences-per-file`; source, workspace и intended output не могут
пересекаться. Пока хотя бы один поддержанный occurrence остаётся `pending`,
output отсутствует. `--resume` завершённого workspace работает только как
идемпотентное read-only подтверждение уже опубликованного exact output и
никогда не вызывает модель или повторную публикацию. Expected tree и report
для такой проверки строятся только в памяти: рядом с output не создаются
candidate/recovery/temp paths, поэтому writable output parent не требуется.

Если на первом workspace-запуске найдено ноль reviewable occurrences, SQLite
workspace не создаётся: после повторной проверки того же source snapshot
provider-free single-pass публикует output по schema v2. Он всегда содержит
`translation-report.json` и может также содержать losslessly rendered Russian
localisation files для English inputs без reviewable occurrences. Иной
контракт действует для уже существующего валидного zero-occurrence workspace с
`--resume`: сохранённые model identity и workspace identity остаются
authoritative, а результат публикуется по обычному schema-v3 workspace path
без создания Ollama client.

Workspace — private local data: он содержит сохранённые переводы и не должен
попадать в Git, backup общего доступа, issue или PR. Файл создаётся с mode
`0600`; `.gitignore` отдельно покрывает `*.smt-workspace.sqlite3` и его SQLite
sidecars. В БД не копируются raw source files или полный English corpus:
сохраняются identities/inventory, source-span hashes, exact model provenance и
только изменивший span проверенный model result. Для `accepted_unchanged`
model result всегда `NULL`, а финальный render воспроизводит original source
span; model echo не создаёт скрытую копию английского корпуса в workspace.
Соседний mode-`0600` файл `<workspace>.lock` хранит process-lifetime advisory
lease. Lease захватывается до SQLite recovery/preflight, `run_count`, создания
клиента, model call и finalization и удерживается до возврата или исключения.
Конкурирующий процесс немедленно получает `workspace_already_in_use`; kernel
автоматически снимает lease при обычном exit и при kill/crash. Сам lock-файл
может безопасно остаться на диске и повторно используется следующим процессом.

После каждого законченного occurrence terminal state
`accepted_changed`, `accepted_unchanged` или `model_fallback` фиксируется
отдельной durable SQLite transaction. `--resume` заново проверяет integrity и
точную schema v2 БД, включая constraints, indexes и foreign keys; после этого
строго проверяются SQLite/Python types, ranges и известные states/error codes.
Также проверяются source bytes/inventory/order, occurrence identities, output
path, parser/order version, prompt profile и exact model tag/digest до первого
нового translation call. Уже committed occurrences модели повторно не
отправляются. Если остановка произошла после model call, но до SQLite commit,
только этот незафиксированный вызов может повториться.

До любого SQLite open preflight проверяет БД и возможные `-journal`, `-wal`,
`-shm` через `lstat` и descriptors с `O_NOFOLLOW`/`O_NONBLOCK`. Для
DELETE-journal workspace любой `-wal` или `-shm` запрещён. Journal должен быть
одиночным regular mode-`0600` файлом и structurally valid hot rollback
journal: проверяются SQLite/database headers, допустимая page geometry,
исходный ненулевой page count и первый journal header. Исходный page count
journal намеренно не сравнивается с потенциально частично записанным current
DB header/размером crash-state файла; padding, record count (`-1` включительно),
records и checksums интерпретирует сама SQLite. FIFO, socket, device, symlink,
hardlink, неверный mode, empty, zero-filled и structurally malformed header
отклоняются до SQLite и не удаляются. Обычный resume затем открывает workspace
read-only с `query_only`; единственное разрешённое изменение до успешной
валидации — authoritative SQLite rollback прошедшего structural preflight hot
`DELETE` journal. Физическая identity БД и journal повторно проверяется вокруг
recovery, а после rollback заново выполняются полные strict
schema/integrity/type/counter проверки.

Сохранённые результаты не считаются доверенными: перед resume и финальным
render каждый `accepted_changed` повторно проходит текущий
`restore_translation` и protected-atom validation, а `accepted_unchanged`
воспроизводится из проверенного immutable source. В workspace-режиме
transport/timeout/inventory failure, malformed provider envelope и model
identity/digest drift немедленно останавливают запуск с сохранением committed
progress. Malformed или unsafe human result одной строки даёт ровно один
`model_fallback`, оставляет английский span и не блокирует остальные
occurrences. В legacy режиме без workspace любой `OllamaError` остаётся
per-entry fallback, чтобы не менять принятую семантику bounded/single-pass CLI.

После `pending=0` CLI заново читает immutable source snapshot, воспроизводит
принятые results, проверяет hashes/counters/source generation и model identity,
строит в памяти logical tree вместе с `translation-report.json` и вычисляет
точную identity всего output: relative paths, file/directory types и file
bytes. После durable finalization intent logical tree отдельно materialize-ится
во временном каталоге только когда действительно нужна новая публикация.
Затем выполняется atomic no-clobber rename, а отдельная завершающая transaction
переводит workspace в `completed`. Перед этой transaction уже опубликованный
tree читается двумя независимыми полными descriptor-checked проходами.
Path/type/bytes и stat identities обоих manifests должны полностью совпасть;
только стабильная logical identity сравнивается с durable intent.

Если процесс остановлен после intent, но до rename, `--resume` без новых model
calls использует durable `model_tag`/`model_digest`, не создаёт Ollama client,
не выполняет inventory/translation calls, заново строит и проверяет тот же
tree, публикует его и завершает workspace. Если rename уже произошёл, resume
независимо воспроизводит expected tree из проверенных source и checkpoints,
требует точного совпадения expected, intent и уже опубликованного tree, не
обращается к Ollama, не публикует его повторно и выполняет только completion
transaction. Missing/extra/changed file, symlink, special file или hardlink
означает fail-closed без изменения output/workspace. Если completion
transaction уже закоммитилась, но успешный ответ процесса потерян, следующий
`--resume` выполняет те же read-only source/config/provenance и stable-tree
проверки, возвращает существующий truthful report как успешный идемпотентный
результат и не меняет `run_count`.

Отчёт честно фиксирует, что в момент создания workspace был `in_progress` и
сам отчёт не аттестует более поздний completion; он содержит resumability
provenance, total/completed/translated/unchanged/fallback/unsupported/pending
counters, число reused occurrences и model calls соответствующего запуска.
Fallback, unsupported syntax или skipped files сохраняют честный partial
status.

MVP-4 пока подтверждён только synthetic data: private mods и live Ollama не
использовались. Candidate остаётся отдельным от active game paths, не
регистрируется в launcher и всегда требует human review. Применение реального
`pilot-02` — отдельный будущий live gate с новым явным разрешением владельца.
Advisory lease и два manifest-прохода закрывают нормальную process concurrency
и обнаруживаемые изменения дерева, но не являются абсолютной защитой от
hostile same-UID процесса, который сознательно обходит lease и успевает
подменять и восстанавливать paths/bytes/stat между проверками.

Текущий synthetic validation baseline: `266 passed` при полном
`python3 -m pytest -W error`; отдельные regressions покрывают unsafe SQLite
sidecars, pre-commit и настоящий commit-phase hot journal, offline post-intent
recovery, read-only completed resume при non-writable parent, parallel resume,
crash/finalization, stable-tree reconciliation и legacy single-pass semantics.

## Локальный editorial review pack

`build-review-pack` не вызывает Ollama и не переводит текст повторно. Legacy
pilot продолжает использовать прежние exact identities, pack schema v1 и
fingerprint domain. Полный schema-v3 candidate требует точный SHA-256 pin
байтов `translation-report.json`; builder заново проверяет report schema,
resumability/counter algebra, source/candidate hashes, все поддержанные
occurrences, protected atoms, escapes и fallback spans. Он публикует pack
schema v2 с `review_scope=full_candidate` атомарно и без перезаписи.

Полный интерфейс показывает не более 100 строк списка одновременно, exact
localisation key и безопасную навигацию к соседним reviewable entries того же
файла. Поиск включает key; фильтры покрывают файл, status, решение, warning,
признак «Требует внимания», точные повторы и группы, где одинаковый source имеет
разные candidate-варианты. Группа повтора вычисляется локально только из exact
последовательности human segments и protected atoms: она не копирует перевод и
не распространяет решение.

Checkbox-выбор ограничен видимой страницей и только валидными `unreviewed`
entries. Смена страницы или фильтра очищает его. Групповые `accept`/`reject`
требуют подтверждения с точным составом выбранного набора, сначала валидируют
его целиком, меняют только решения и выполняют одно sparse-state сохранение.
Последнее групповое действие можно атомарно отменить; undo привязан к exact pack
fingerprint и не затрагивает посторонние индивидуальные решения. `edit` остаётся
строго индивидуальным; последующее индивидуальное изменение затронутой записи
сбрасывает устаревший undo. Глобального select-all нет. State и last-batch undo
сохраняются одним localStorage envelope, чтобы quota failure не мог связать
новые decisions со старым undo; прежний sparse storage schema v1 по-прежнему
импортируется. Если внешний или повреждённый envelope содержит несовместимый
undo, валидные decisions загружаются, а только undo безопасно отбрасывается.

Локальное состояние sparse: сохраняются только изменения относительно
`unreviewed`; draft export доступен до завершения, а final export — только после
валидного решения по каждой записи. Счётчики отдельно показывают remaining
attention/fallback/unchanged/whitespace и inconsistent-repeat groups.
Unsupported occurrences и skipped files видны в summary как технический
остаток, но не становятся редактируемыми: для них нет безопасного parsed span.

Откройте созданный `index.html` напрямую через `file://`. Pack автономен:
сервер, интернет, CDN, web fonts и внешний frontend runtime не нужны.
Промежуточные решения хранятся в browser `localStorage` с ключом exact pack
fingerprint. Экспорт и импорт decisions JSON выполняются локально; JSON
содержит только occurrence identities, решения, пользовательскую редакцию,
комментарии/теги и span hashes, но не полный source corpus.

Решение `accept` означает принятие человеком только конкретного occurrence.
Для fallback/unchanged оно сохраняет английский; чтобы получить перевод, нужно
выбрать `edit`.
Оно не назначает `editorially_approved` всему моду и не доказывает
литературную или lore-готовность остальных строк. Generated `index.html`,
`review-pack-summary.json` и decisions JSON остаются локальными артефактами
вне Git.

## Применение review decisions

`apply-review-decisions` поддерживает два явно разделённых режима. Без
`--candidate-report-sha256` сохраняется exact legacy bounded pilot. С pin из
ровно 64 lowercase hex символов разрешён только полный schema-v3 candidate;
schema-v3 без pin и legacy schema-v2 с pin отклоняются.

Команда не вызывает Ollama и не использует `index.html`,
`review-pack-summary.json` или browser state как authority. Общий validator
review pack заново вычисляет source/candidate inventories и localisation
hashes, проверяет exact report bytes, schema-v3 count/resumability algebra,
model tag/digest, occurrence order/identities, protected atoms, escapes и pack
schema-v2 fingerprint. Decisions могут идти в любом порядке, но обязаны
содержать каждое reviewable occurrence ровно один раз, без duplicate, unknown,
missing или `unreviewed` entries. Число записей выводится из validated
candidate и не привязано к конкретному full pack.

`accept` оставляет candidate span byte-identical, `edit` меняет только
проверенные human segments, а `reject` восстанавливает их из English source.
Protected atoms и escapes сохраняются в исходном порядке; source, candidate и
decisions перепроверяются до атомарной no-clobber публикации. Результат содержит
только `localisation/russian/**` и `review-application-report.json`. Full report
использует отдельную schema v2 и status `full_candidate_review_applied`, хранит
hashes всех authority inputs и final localisation, исходные candidate
status/counts, decision counts и technical residue. При unsupported
occurrences или skipped files он честно сохраняет
`editorially_approved=false`: эти residue bytes остаются без изменений, но для
них не существовало безопасного editable span.

## Упаковка reviewed candidate

`package-reviewed-mod` принимает только full application report schema v2 со
status `full_candidate_review_applied`, scope `full_candidate` и exact SHA-256
его байтов. Команда заново вычисляет localisation hash и проверяет полный
decision-count algebra, нулевые source/candidate/protected mutations, нулевые
Ollama/network calls и отсутствие `unreviewed`/pending/deferred reviewable
entries. Ненулевой technical residue требует явного
`--allow-technical-residue` и без изменений переносится в
`package-report.json`.

Reviewed candidate имеет закрытый inventory: ровно
`localisation/russian/**/*.yml` и `review-application-report.json`. Symlink,
hardlink и special files запрещены; каждый YML должен иметь первый
`l_russian:` header, не содержать placeholder residue, private paths или
review/workspace/prompt artifacts. До атомарной публикации вход перечитывается
и сравнивается с исходным snapshot.

Пакет имеет форму `install/<slug>.mod`,
`install/<slug>/descriptor.mod`, `install/<slug>/localisation/russian/**` и
корневой `package-report.json`. Строгий descriptor renderer разрешает только
`name`, `supported_version`, одну exact dependency и только во внешнем `.mod`
planned absolute `path`. Quote, backslash, control/format Unicode, небезопасный
slug, malformed/duplicate fields, `remote_file_id` и `replace_path`
отклоняются. Публикация atomic no-clobber: занятый output не изменяется.
Файл qualified replace сохраняет nested путь
`install/<slug>/localisation/russian/replace/**` byte-identical reviewed
candidate. Каталог задаёт replace-семантику самостоятельно: descriptor не
получает `replace_path`.

`package-report.json` содержит только hashes, inventory, mod/install metadata,
technical residue и нулевые mutation counters. Он не содержит localisation,
decisions или prompts. Даже валидный пакет остаётся неустановленным: CLI не
пишет в planned install root, launcher или active mod path.
MVP-5L также не удаляет и не мигрирует ранее установленный отдельный
replace-patch; возможная консолидация требует отдельной no-clobber задачи после
owner review/merge.

## Консолидация reviewed package

`consolidate-reviewed-mod` — отдельная строгая граница, а не optional
ослабление legacy packaging. Все arguments обязательны: exact tree прежнего
main package; exact supplement tree, report, payload, reviewed-localisation,
source-replace, owner-mapping и independently вычисляемый content-mapping pin;
read-only source mod; technical main-menu status и отдельная authoritative
owner visual confirmation с exact pins обоих artifacts. Main application
report по-прежнему independently bind-ит `1678` human decisions и
`11 unsupported / 1 skipped`; его historical full-localisation hash обязан
совпасть с текущим canonical inventory всего `localisation/**/*.yml`.
Pinned base translation report обязан называть ровно supplement source как
единственный skipped replace-файл. Supplement bind-ит ещё `9` owner-reviewed
occurrences, а его main-tree fingerprint заново проверяется по прежнему main
package. Consolidated report сохраняет обе authorities и проверяет алгебру
`1678 + 9 + 11 = 1698`, выставляет
`reviewed_occurrences=1687`, `skipped_files=0` и оставляет
`editorially_approved=false`.

Owner confirmation schema v2 имеет закрытый duplicate-free набор полей и
разделяет `package_replace_entry_count=9` от
`verified_visual_target_count=3`. Подтверждение относится только к
content-free scope `nsc3_corvette_core_module_labels_v1`; оно не утверждает,
что владелец визуально проверил все девять replace entries. Supplement
provenance по-прежнему сохраняет `reviewed_occurrences=9` как количество
технически и редакционно проверенных mappings.

Supplement имеет закрытый четырёхфайловый package inventory и ровно один
`localisation/russian/replace/**/_l_russian.yml`; source содержит ровно один
соответствующий `localisation/english/replace/**/_l_english.yml`. Кроме этого,
вся source-mod generation проходит bounded descriptor-bound chunked snapshot:
все directories и regular files, single-link/special-file rejection,
case/NFC-NFD/file-directory collision gate и framed manifest hash. До
temp/output проверяются strict JSON types и duplicate keys, все pins, lexical
и physical containment, BOM/newline/header, key order/version suffixes,
protected atoms/escapes и lossless structure. Полный source snapshot и
остальные inputs повторно сверяются непосредственно перед atomic no-clobber
publication и после неё.

Новый descriptor строится заново и содержит только указанную source dependency:
descriptor supplement не копируется, `replace_path` не добавляется. Report
schema v4 / construction mode v3 добавляет точную область visual authority, не
переопределяя семантику сохранённого schema-v3 package. Он содержит metadata,
relative package inventory, hashes, counts, разделённые smoke authorities и
нулевые mutation counters без localisation text, keys, translations, prompts
или absolute private paths. Для source generation сохраняются только manifest
hash и агрегированные counts, без source filenames. Даже созданный
consolidated package остаётся неустановленным и не меняет текущий порядок
`NSC3 -> LOCALISATION -> REPLACE_PATCH`.

MVP-5C application и MVP-5D ускоренный editorial workflow не принимают решения
автоматически. Synthetic regressions интерфейса исполняют настоящий JavaScript,
включая scale smoke примерно на 1700 entries, batch/undo/import/export и
storage-failure paths. Ни merge интерфейса, ни наличие batch-команд не разрешают
AI-assisted acceptance или применение реальных decisions: каждое решение и
последующий live-application gate остаются действиями владельца.

Известная граница MVP-0: атомарная публикация защищает от появления конечного
destination, но не обещает защиту от злонамеренного конкурирующего процесса
того же macOS UID, который переименовывает output-parent во время выполнения.
Descriptor-bound filesystem framework остаётся вне этого milestone.

Для поставляемого с macOS старого `pip`, если editable install запрашивает
`wheel`, доступен полностью локальный совместимый запуск:
`python3 setup.py develop`.

## Private contextual vanilla memory and retrieval

MVP-6A хранит официальные EN→RU соответствия только локально и с exact
game-version label. Это contextual reference memory, а не глобальный словарь:
одинаковый English text может иметь разные Russian варианты в зависимости от
key, occurrence и file family. Exact relative paths, keys и human values
остаются только в приватной SQLite; CLI и build report выводят лишь hashes и
агрегированные counts. Runtime builder/inspect не проверяют Git и поэтому не
выводят `private_content_in_git` или иной leakage verdict; такой verdict может
появиться только во внешнем validation после отдельного scan.

Builder и immutable inspect применяют одинаковые совокупные ceilings до
следующего крупного read/materialization: `4096` manifest entries, `2048`
directories и `2048` regular files на root; `128 MiB` source bytes на root;
`1024` YML на root и `2048` total; `1,500,000` parsed lines на язык и
`3,000,000` total; `1,000,000` occurrences на язык и `2,000,000` total;
`1,500,000` protected tokens; `500,000` record и `16,384` file quarantines;
`2,000,000` aggregate quarantined key candidates. Превышение даёт только
content-free `SafetyError`; unpublished SQLite/report и temporary output
полностью отсутствуют или очищаются. Parsed-line ceiling относится к source
snapshot/revalidation; остальные persisted ceilings повторно проверяет
immutable inspect до materialization semantic rows.

Duplicate, missing, suffix/atom-mismatched и malformed rows не входят в strict
eligible set. Whole-file quarantine сохраняет отдельный консервативный
key-occupancy inventory: он не восстанавливает строки, но не позволяет
скрытому duplicate ошибочно стать strict reference. Даже strict pairs имеют
только `REFERENCE_ONLY` и никогда не получают `editorially_approved`
автоматически. Builder не вызывает Ollama; opt-in translation использует
memory только через полный pinned набор MVP-6C, а ambiguous или quarantined
rows никогда не выбираются автоматически.

`exact_context_v1` принимает exact relative localisation path, case-sensitive
key, version suffix (`None`, `"0"` и `"007"` различаются), English Unicode
bytes и ordered `(token kind, exact bytes)` tuple. Каждая query получает ровно
один terminal status: `exact_key_context`, `exact_text_consensus`,
`excluded_key_conflict`, `excluded_quarantined_key`, `excluded_key_alias`,
`excluded_ambiguous_text`, `excluded_candidate_overflow` или `no_match`.
Exact-key reference разрешён только при совпадении value/suffix/tokens;
`global_text_ambiguous` допустим только в этом exact-key контексте. Text
fallback требует единственного exact Russian-byte value среди всех strict,
alias-free references. Несколько одинаковых references сворачиваются в один
candidate с лучшим provenance.

Ranking лексикографический и не использует heuristic score: exact key раньше
exact text, совпадающий canonical path family раньше несовпадающего, затем
persistent `pair_id`. Default ceilings одного batch: `100000` queries, `256`
examined references на query, максимум `3` returned candidates, `100000`
materialized index units и `8192` bytes aggregate stdout. Index unit — один
релевантный key fact, strict reference или protected token; строки вне текущих
query key/value-suffix signatures не материализуются. Batch/index overflow
остаётся content-free per-occurrence status. Source-localisation snapshot имеет
отдельные ceilings: `8192` manifest entries, `4096` directories, `4096` files,
`256 MiB` aggregate bytes, `128 MiB` на file, `2048` YML, `1,500,000` parsed
lines, `250000` supported occurrences и `500000` protected tokens.

Validation memory и extraction index выполняются в одном открытии SQLite с
`mode=ro&immutable=1`, `query_only=ON`, `trusted_schema=OFF` и temporary state
только в памяти. До/после сверяются точные database/report hashes и stat
identities; source manifest проходит terminal revalidation, а один drift
разрешает только один полный retry. Candidate остаётся process-local
`REFERENCE_ONLY`, `editorially_approved=false`, `auto_applied=false`; CLI не
создаёт candidate, context pack, workspace или report artifact и не выводит
keys, paths, filenames, IDs либо human text. `PRIVATE_CONTENT_IN_GIT` остаётся
только внешним leakage-scan verdict, не runtime claim.

## Optional contextual translation and blind A/B

Contextual prompt передаёт source и reference как два canonical JSON data
fields. Оба объявлены недоверенными данными, source meaning имеет приоритет,
а protected placeholders должны сохраниться byte-exact и в исходном порядке.
Localisation key, path, occurrence/pair IDs, SQLite metadata и conflict details
в model request не попадают. Ошибка contextual result даёт тот же безопасный
English fallback одним вызовом, без скрытого retry legacy prompt.

До client creation и workspace creation выполняется один retrieval batch по
уже проверенному translation plan. Canonical binding содержит memory pins,
retrieval limits, source/inventory hashes и для каждой occurrence только
sequence, source-span hash, terminal status и hash process-local reference
bytes либо typed absence. Resume заново получает тот же batch и обязан
воспроизвести binding до нового provider call. Source и memory identities
повторно проверяются перед finalization и publication.

`context_ab.run_context_ab_pilot` предназначен только для owner-authorized
bounded private validation и принимает не более `23` eligible occurrences,
хотя generic pack builder сохраняет отдельный технический максимум `100`.
Значение `24` отклоняется до private input reads, client creation и output
writes. Pilot вызывает contextual model только для eligible
occurrences, переиспользует exact совместимый baseline либо при digest drift
перестраивает обе стороны на одном текущем digest. Совместимость baseline
включает exact legacy prompt-profile hash. Обязательный `evaluation_root`
фиксирует разрешённую область записи: pack должен быть её прямым дочерним
каталогом и лексически и физически не пересекаться с source, memory, baseline
или reviewed candidate. Offline pack имеет каталог `0700`, файлы `0600`,
автономный CSP, stable hidden mapping, local draft, JSON export/import и
отдельный reviewed-candidate reference. Review/storage/decisions protocol v2
не раскрывает reference при tentative radio selection: владелец отдельно
фиксирует выбор, после чего radio controls блокируются навсегда, а note остаётся
редактируемым. Export включает только зафиксированные decisions; valid import
считает все decisions зафиксированными и атомарно отклоняет malformed,
duplicate, unknown, incompatible или конфликтующий с уже locked choice JSON.
V1 localStorage/decisions не принимаются как v2 и используют другой storage
key/fingerprint. Pack не
выставляет quality verdict:
`AB_QUALITY_STATUS: HUMAN_REVIEW_REQUIRED`.

## Исторический контекст до MVP-0

После принятия `M0R` разрешены только два доказательных этапа: исследование реального формата и загрузки модов (`M1A`, сейчас `BLOCKED`) и изолированный benchmark качества локальных моделей (`M1B`). Exact proposal v7/generation 108 принят отдельным external owner-freeze record только как declarative basis записанного `M1B-1A local synthetic provider preflight`; после merge PR #6 exact scope действует со state `OWNER_FREEZE: ACCEPTED`, merge PR #7 выставил `STABLE_READ_HARDENING: ACCEPTED`, merge PR #8 — `M1B-1A0 CONTRACT: ACCEPTED/MERGED`, а merge PR #9 — `M1B-1A1-AUTH: ACCEPTED/MERGED`. Executable admission по-прежнему не выдан. Текущая граница: `M1B-1A1 CANDIDATE: READY_FOR_OWNER_REVIEW`, `CANDIDATE CONSTRUCTION: COMPLETE_WITHIN_EXACT_INERT_SCOPE`, `CANDIDATE SOURCE: NOT_PARSED_NOT_COMPILED_NOT_IMPORTED_NOT_EXECUTED`, `PROPOSED EXECUTABLE MANIFEST: REVIEWABLE_PROPOSAL_ONLY_NOT_ADMISSION`, `NEW REPOSITORY CODE EXECUTION: NOT_AUTHORIZED`, `RUNTIME_ENVELOPE_CONSTRUCTION: NOT_AUTHORIZED`, `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`, `EXECUTABLE_TCB_OWNER_DECISION_REQUIRED: PRESERVED`, `PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN: PRESERVED`, `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN: PRESERVED`. `M1B-1A PROVIDER EXECUTION: NOT_STARTED`, `M1B: NOT_EVALUATED`; benchmark не запускался. Только принятые verdicts `M1A: GO` и `M1B: QUALITY_FEASIBLE` вместе разрешают `M2`; сейчас `M2: FORBIDDEN`, массовый перевод и active publish запрещены.

Текущая synthetic proposal identity — protocol v7/generation 108 и analysis
policy v6/generation 108. PR #5 смержен; historical 17 report/fixture entries
остаются `proposed`. Отдельный owner-freeze snapshot atomically bind-ит их exact
kind/version/generation/component hashes и snapshot-level
`acceptance_state=owner_accepted`; его canonical SHA-256 —
`df84871be332ee52c315d0c0cc1a7a0046251352a2a0131382b5cb994cffcb58`.
Он принят только как declarative basis подготовки M1B-1A и не является
benchmark admission. Protocol по-прежнему разделяет exact frozen synthetic-scope provenance
и полный live decision admission: первый capability разрешает только
diagnostic math с `decision_grade_eligible=false`, второй M1B-0 не выдаёт.
Protocol v7 и validator policy v7 byte-bind lifetime ownership: registry не
владеет token, не вытесняет живые registrations и освобождает недостижимые
tokens вместе с frozen rows без value-to-token back-reference.
Provider/request/context/implementation/benchmark/coverage/acceptance/aggregate/
execution gates остаются обязательными для будущего полного admission.
Same-process Python runtime, imports, globals/closures и analysis code входят в
TCB; capability предотвращает случайное смешение raw rows, но не является
security boundary против reflection или monkeypatching внутри TCB. Existing
reviewer/HGT/no-output invariants сохранены. Synthetic corpus bytes не менялись:
corpus v3/generation 304 остаётся тем же. M1B-1A0 contract v4/generation 4
имеет envelope v4/generation 4, execution plan v3/generation 3 и отдельную
runtime-acceptance v1 identity. Closed file-purpose matrix, descriptor-rooted
stable nofollow admission cwd/каждого sys_path и отдельные lexical/physical
directory indices запрещают ambiguous reuse; directory snapshot сам по себе не
доказывает import transport. Cached provider bytes проходят exact `/dev/fd/3`
pipe transport с pre/post FIFO/access/inheritability/physical-identity checks,
но это не защита от hostile same-process patching и launcher остаётся blocked.
Interpreter exec, launcher opened-byte handoff, exact admitted-CPython provider
source eligibility и descriptor imports остальных roles остаются explicit
blockers; host `ast`/`compile` не являются eligibility evidence. Caller-supplied
`owner_accepted` и runtime record доказывают только shape/linkage, не заменяют
external owner-controlled trust root и не снимают executable owner blocker.
Contract не принимает текущие executable bytes, runtime или invocation state.
Это contract evidence, а не model call или quality verdict.

## Исторический целевой контракт до MVP-0

- один владелец, один текущий Mac и выбранные игровые наборы модов;
- Rust CLI — поддерживаемый интерфейс; графический интерфейс не обязателен;
- исходные моды, Workshop-каталоги и файлы игры доступны только для чтения;
- снимок строится из фактически прочитанных байтов; смешанная версия мода при обновлении блокирует задание;
- SQLite хранит задания, происхождение, память перевода и историю решений;
- Ollama на loopback — единственный LLM-провайдер MVP;
- разрешена только явно выбранная модель с локальными весами; tag, полный digest и параметры фиксируются в provenance;
- remote endpoint, `*-cloud`, неизвестная residency, auto-pull и скрытая подмена модели отклоняются;
- модель получает только человеческие сегменты, защищённые атомы и минимальный контекст, без файловых инструментов;
- неизвестный синтаксис не угадывается и блокирует затронутую единицу;
- техническая целостность проверяется до публикации, а литературность и соответствие лору имеют отдельные статусы и человеческое подтверждение;
- форма результата (`per-source`, один RU bundle на playset или hybrid) определяется доказательствами M1, а не предположением.

## Что не входит в baseline

- облачные LLM и автоматический fallback между провайдерами;
- Tauri/React UI;
- Windows/Linux, публичная beta и универсальная поставка;
- аккаунты, синхронизация и удалённый backend;
- публикация в Steam Workshop;
- изменение логики, баланса, графики, звука или исполняемого кода модов.

## Качество результата

Результат использует независимый технический gate и редакционный статус; это не простая линейная шкала:

1. `technical_safe` — независимый технический gate: структура и служебные атомы сохранены;
2. `machine_reviewed` — текущий review status после автоматических смысловых и языковых проверок;
3. `human_review_required` — review status/branch для неоднозначности, лора или литературного качества;
4. `editorially_approved` — review status после принятия человеком.

`human_review_required` переходит в ручное решение, fallback или отклонение, а не автоматически в approval. Runtime-модель Ollama не может назначить `editorially_approved`. Формально корректный русский текст не считается литературно готовым без соответствующего evidence. Точная state machine фиксируется до реализации quality schema.

## Документы

- [Решение владельца M0](docs/decisions/M0-owner-signoff.md)
- [ADR-0001: персональная local-first архитектура](docs/adr/0001-personal-local-cli.md)
- [Аудит старого проекта](docs/legacy-project-audit.md)
- [Продуктовая стратегия](docs/product-strategy.md)
- [Архитектура](docs/architecture.md)
- [Технологический стек](docs/technology-stack.md)
- [Каноны проекта](docs/project-canons.md)
- [План разработки](docs/development-plan.md)
- [Дорожная карта](docs/roadmap.md)
- [Снимок локального окружения](docs/evidence/local-environment-2026-07-17.md)
- [Модель угроз M1A](docs/threat-model.md)
- [Спецификация формата localisation](docs/specs/localisation-format.md)
- [Taxonomy markup](docs/specs/markup-taxonomy.md)
- [Контракт candidate artifact и publish boundary](docs/specs/artifact-and-publish-contract.md)
- [Политика корпуса M1A](docs/corpus-policy.md)
- [Version profile Stellaris 4.4.6](docs/version-profiles/stellaris-4.4.6.md)
- [Итоговое evidence M1A](docs/evidence/m1a-format-playset-2026-07-17.md)
- [Hardening revalidation M1A, 18 июля](docs/evidence/m1a-format-playset-revalidation-2026-07-18.md)
- [Benchmark contract M1B](docs/specs/m1b-benchmark-contract.md)
- [Политика корпуса M1B](docs/m1b-corpus-policy.md)
- [Quality rubric M1B](docs/specs/m1b-quality-rubric.md)
- [Модель угроз M1B](docs/m1b-threat-model.md)
- [External owner-freeze contract M1B-0F](docs/specs/m1b-owner-freeze-contract.md)
- [Owner signoff M1B-0F](docs/decisions/M1B-0F-owner-signoff.md)
- [Offline executable/TCB admission contract M1B-1A0](docs/specs/m1b-offline-executable-tcb-admission-contract.md)
- [Contract review M1B-1A0](docs/decisions/M1B-1A0-contract-review.md)
- [Candidate-construction authorization scope M1B-1A1-AUTH](registry/m1b/m1b-1a1-candidate-construction-scope-v2.json)
- [Candidate-construction authorization contract M1B-1A1-AUTH](docs/specs/m1b-1a1-candidate-construction-authorization-contract.md)
- [Machine owner authorization M1B-1A1-AUTH](docs/decisions/M1B-1A1-AUTH-owner-authorization.json)
- [Owner signoff M1B-1A1-AUTH](docs/decisions/M1B-1A1-AUTH-owner-signoff.md)
- [Candidate review M1B-1A1](docs/decisions/M1B-1A1-candidate-review.md)
- [Proposed executable manifest M1B-1A1](registry/m1b/m1b-1a1-proposed-executable-manifest-v1.json)
- [Inert synthetic candidate fixture M1B-1A1](fixtures/m1b/candidate-construction/README.md)

## Исторический AUTH-first шлюз (superseded для MVP-0)

Hardening [PR #4](https://github.com/elenandar/Stellaris-mod-translator/pull/4) слит, но исторический report 17 июля и повторная проверка 18 июля честно сохраняют `M1A: BLOCKED`: byte/containment evidence собрано, а atomic cross-file coherence, arbitrary same-UID path-race protection и effective load-order/collision policy недостаточны для `GO`.

External owner-freeze PR #6, stable-read hardening PR #7 и contract PR #8 слиты;
`OWNER_FREEZE: ACCEPTED`, `STABLE_READ_HARDENING: ACCEPTED`,
`M1B-1A0 CONTRACT: ACCEPTED/MERGED`. M1B-1A0 создал только reviewable
v4/generation-4 offline contract и synthetic conformance gate.
Existing five-field implementation acceptance остаётся неизменным, а отдельный
runtime acceptance exact bind-ит canonical envelope без выдачи authority;
synthetic `owner_accepted` — только проверка shape/linkage.

Review и merge PR #9 завершили exact M1B-1A1-AUTH effect. Текущие states:
`M1B-1A1-AUTH: ACCEPTED/MERGED`,
`M1B-1A1 CANDIDATE: READY_FOR_OWNER_REVIEW`,
`CANDIDATE CONSTRUCTION: COMPLETE_WITHIN_EXACT_INERT_SCOPE`,
`CANDIDATE SOURCE: NOT_PARSED_NOT_COMPILED_NOT_IMPORTED_NOT_EXECUTED` и
`PROPOSED EXECUTABLE MANIFEST: REVIEWABLE_PROPOSAL_ONLY_NOT_ADMISSION`.

`M1B-1A1-AUTH` — ограниченный owner authorization для будущей offline-задачи.
Сам gate не создаёт executable files или real candidate manifest/envelope, не
запускает interpreter/provider, не создаёт operational `owner_accepted`
admission и не снимает `EXECUTABLE_TCB_OWNER_DECISION_REQUIRED`. Scope v2 exact
перечисляет четыре inert role path, `18` SHA-bound base inputs, `4` post-merge
AUTH inputs, `4` create-only future directories и `12` future outputs. Он
разделяет default-deny repository content plane, bounded Git/GitHub control
plane и bounded host validation; никакая из последних двух плоскостей не
расширяет candidate/provider authority.

Отдельный `M1B-1A1` завершил construction в exact inert scope. Его
[candidate review](docs/decisions/M1B-1A1-candidate-review.md),
[proposed manifest](registry/m1b/m1b-1a1-proposed-executable-manifest-v1.json)
и [synthetic fixture](fixtures/m1b/candidate-construction/README.md) имеют state
`READY_FOR_OWNER_REVIEW`. Candidate validation ограничена static-byte checks:
новый repository test, другой executable fixture, import или execution любого
нового repository file, а также parse/compile candidate source не выполнялись.
Execution/runtime envelope, invocation plan и
runtime acceptance record также запрещены. M1B-1A1 не может принять созданные identities. После его review
отдельный `M1B-1A2` может зафиксировать owner-controlled решение только над уже
известными exact identities. Даже M1B-1A2 не разрешает Ollama probe,
provider/model call, private corpus или benchmark: для исполнения нужен ещё один
явный gate. `M1B: NOT_EVALUATED`: contract review не является feasibility
verdict. Только позднее принятые verdicts `M1A: GO` и
`M1B: QUALITY_FEASIBLE` вместе разрешат safety kernel; до этого `M1A: BLOCKED`
и `M2: FORBIDDEN`.
