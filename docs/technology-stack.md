# Технологический стек

Baseline рассчитан на персональный local-only CLI для текущего Apple Silicon Mac. Точные версии toolchain и зависимостей закрепляются lock-файлами только после M1 spikes. Снимок решения: 17 июля 2026 года.

## Принятый baseline

| Слой | Технология | Причина |
|---|---|---|
| Интерфейс MVP | Rust CLI | воспроизводимые команды, удобный dry-run и минимальная поверхность до доказательства необходимости UI |
| Доменное ядро | Rust workspace, edition 2024 | строгие типы, byte-safe обработка, один поставляемый runtime и сильная test ecosystem |
| Задания | последовательная persistent queue | локальная модель обычно является bottleneck; пауза и resume нужны, постоянный async runtime — пока нет |
| Данные | SQLite, `rusqlite`, foreign keys, явные migrations | локальное транзакционное состояние, backup и отсутствие отдельного сервера |
| Сериализация | Serde | typed manifests, provider payloads, reports и provenance |
| HTTP | узкий `reqwest` adapter | обращения только к проверенному loopback Ollama endpoint; приложение не слушает порт |
| LLM | установленный локальный Ollama | веса уже доступны на компьютере; модель выбирается benchmark, а не брендом в коде |
| Поиск | SQLite indexes + FTS5 | воспроизводимая база для glossary/memory; vector DB требует отдельного evidence |
| Диагностика | `tracing` с redaction | correlation IDs и стадии без утечки сырых текстов в обычные логи |
| QA | `cargo test`, `proptest`, `cargo-fuzz`, Clippy, rustfmt | unit, round-trip, property, mutation/fuzz и статические проверки |
| Поставка MVP | локально собранный CLI binary | без Tauri, Node.js и Python в пользовательском runtime |
| Research tooling | необязательные одноразовые Python-скрипты | допустимы для corpus analysis, но не становятся продуктовой архитектурой |

Tokio добавляется только после измеренного требования к конкурентным I/O или cancellation, которое нельзя чисто решить синхронным worker и persistent checkpoints. Tauri/React рассматриваются после стабильного M5 по отдельному ADR.

## Предлагаемая структура

```text
crates/cli/             команды, plans и reports
crates/domain/          типы, политики и use cases
crates/stellaris-loc/   lossless parser и renderer
crates/context/         индекс ссылок и context fingerprints
crates/translation/     memory, prompts и provider port
crates/quality/         validators, states и findings
crates/storage/         SQLite repositories, migrations и backup
crates/publisher/       staging, versioned artifacts и rollback
fixtures/               synthetic/minimal licensed cases
tools/research/         необязательные corpus/benchmark helpers
docs/                   decisions, ADR, specs и evidence
```

Имена crates уточняются после M1. Структура не является разрешением создавать пустой scaffolding до утверждённых контрактов.

## Ollama provider policy

Единственный обязательный adapter MVP — локальный Ollama. Provider interface остаётся отделённым от домена для тестируемости, но cloud adapters не реализуются и не входят в текущую дорожную карту.

Перед каждым заданием adapter обязан:

- разрешить endpoint только в loopback и запретить redirects;
- получить локальный inventory и подтвердить выбранный tag;
- отклонить `*-cloud`, неизвестную residency и отсутствующие локальные веса;
- закрепить полный digest, Ollama version, model options, context size, prompt/template и schema versions;
- запретить pull, скрытый fallback и автоматический выбор «похожей» модели;
- проверить structured result собственной строгой схемой независимо от возможностей модели;
- поддержать timeout, cancel и классифицированный retry без доступа модели к инструментам.

Изменение digest или параметров считается изменением quality profile. Уже принятые переводы не перегенерируются автоматически.

## Стартовый benchmark моделей

Локальный inventory содержит несколько семейств. Для первого translation benchmark выбраны только общие модели:

- GLM 4.7 Flash;
- DeepSeek R1 32B;
- GPT-OSS 20B.

Coding-варианты Qwen не являются translation baseline, но сохраняются в inventory как установленные модели. Победитель заранее не назначается.

Все кандидаты получают одинаковый стратифицированный corpus, schema и явно заданные параметры. Начальный `num_ctx` — 8–16K: длинный 64K profile не нужен типичной единице перевода и должен доказывать пользу отдельно. Оцениваются смысл, литературный русский, терминология/лор, atoms, JSON stability, скорость и память.

Полный датированный inventory и сведения о компьютере находятся в [снимке локального окружения](evidence/local-environment-2026-07-17.md). Это evidence, а не вечный канон.

## Parser policy

Localisation Stellaris не передаётся generic YAML-библиотеке: фактический формат имеет собственные правила, дубли ключей, markup и значимую byte-level форму. Нужны небольшой lossless lexer/CST и отдельный typed parser внутритекстовой разметки.

До M2 нельзя обещать поддержку конструкции без fixture, ожидаемой классификации и round-trip test. Context parser scripts может использовать готовую grammar либо консервативный lexer; выбор проходит сравнительный M1 spike по coverage, diagnostics, лицензии и стоимости сопровождения.

## Версии и зависимости

- Rust toolchain фиксируется `rust-toolchain.toml`, зависимости — `Cargo.lock`.
- Production-like проверки используют только lock-файлы и не скачивают модель автоматически.
- Новая dependency получает назначение, license/security review и владельца обновления.
- Version profile Stellaris отделён от версии приложения; обновление игры сначала проходит compatibility suite.
- Parser, SQLite, filesystem и provider dependencies обновляются с полным regression corpus.
- Private fixtures, моды, переводы и базы не передаются в облачный CI.

В текущем окружении Rust toolchain ещё не установлен. M0R ничего не устанавливает; bootstrap и pinning являются явной задачей M1 после принятия baseline.

## Осознанно не выбранные альтернативы

| Альтернатива | Почему не baseline |
|---|---|
| Tauri + React | UI не нужен для проверки ключевых рисков; решение откладывается до стабильного CLI |
| Python/PySide как runtime | второй способ поставки и более слабая единая byte-safe граница; Python остаётся research tool |
| Tauri + Python sidecar/FastAPI | два runtime, IPC и лишний listening surface без пользы для личного CLI |
| Electron/web app | избыточны для локальной работы с filesystem и launcher artifacts |
| Cloud LLM | противоречит принятому local-only scope |
| Microservices, Redis, Celery, PostgreSQL | не соответствуют однопользовательскому локальному инструменту |
| Generic YAML parser | не обеспечивает duplicate semantics и byte-identical round trip |
| Vector DB с первого дня | усложняет систему до измеренного retrieval bottleneck |
| Жёстко заданная модель | модель выбирается по quality evidence и фиксируется digest в конкретном профиле |

## Первые технические spikes

До масштабной реализации нужно отдельно доказать:

1. Byte-identical round trip на репрезентативном и независимом holdout corpus.
2. Typed markup и malformed diagnostics без regex-only shortcuts.
3. Load order, `replace/`, duplicate-key semantics и форма RU-артефакта на реальной установке.
4. Immutable snapshot при обновлении Workshop во время чтения.
5. Local Ollama residency, digest pinning, cancellation и schema stability.
6. Качество GLM/DeepSeek/GPT-OSS на одинаковой человеческой разметке.

Справочные основания стека: [Rust Edition Guide](https://doc.rust-lang.org/edition-guide/editions/creating-a-new-project.html), [SQLite](https://www.sqlite.org/about.html), [Ollama API](https://docs.ollama.com/api/introduction) и [Ollama cloud authentication через локальный API](https://docs.ollama.com/api/authentication). Возможный Tauri UI не является текущим решением.
