# Технологический стек

Стек зафиксирован на уровне поддерживаемых major/minor-линий. Точные patch-версии будут закреплены lock-файлами при старте M1. Снимок решения: 17 июля 2026 года.

## Принятый стек

| Слой | Технология | Причина |
|---|---|---|
| Desktop shell | Tauri 2, Rust stable | нативные dialogs и permissions, кроссплатформенная упаковка, малый runtime и Rust-граница для опасных файловых операций |
| UI | React 19, TypeScript strict, Vite | зрелый компонентный UI, типизированные контракты, быстрый локальный build без отдельного web-сервера в поставке |
| Доменное ядро | Rust workspace, edition 2024 | один бинарный runtime, строгие типы, безопасная работа с байтами, property/fuzz testing и отсутствие Python-sidecar |
| Async и задачи | Tokio + внутренняя persistent queue | пауза, отмена и возобновление без внешнего broker |
| Данные | SQLite, `rusqlite`, foreign keys, WAL, явные SQL migrations | локальная транзакционная база без отдельного сервера; прозрачная схема и простой backup |
| Сериализация | Serde | единые типизированные команды, события, manifests и provider payloads |
| HTTP | `reqwest` с ограниченными adapters | исходящие вызовы только к выбранному provider; приложение не открывает listening-порт |
| Локальная модель | Ollama native API | локальный opt-in runtime, модель можно менять без изменения ядра |
| Поиск памяти | точные индексы + SQLite FTS5 | воспроизводимо и достаточно для первой версии; vector database добавляется только после измеренного выигрыша |
| Наблюдаемость | `tracing`, структурированные локальные события | диагностика заданий с correlation ID и редактированием чувствительного текста |
| Rust QA | `cargo test`, `proptest`, `cargo-fuzz`, Clippy, rustfmt | unit, round-trip, property, mutation/fuzz и статическая дисциплина |
| UI QA | Vitest, Testing Library, Playwright | компоненты, пользовательские сценарии и packaged smoke tests |
| CI | GitHub Actions: macOS, Windows, Linux | раннее обнаружение платформенных различий; macOS остаётся первым release target |
| Упаковка | Tauri bundler; подпись и notarization macOS | единая поставка без требования установить Python или Node.js |

Конкретные Rust crates, кроме перечисленных базовых, добавляются по необходимости. В частности, библиотека контекстного парсера Clausewitz/Jomini выбирается только после M1-spike на реальном корпусе; каноном является её поведение, а не имя зависимости.

## Структура исходников

Предлагаемая форма monorepo:

```text
apps/desktop/           React UI и Tauri host
crates/domain/          типы, политики, use cases
crates/stellaris-loc/   lossless parser и renderer
crates/context/         индекс ссылок и context signatures
crates/translation/     memory, prompts, provider ports
crates/quality/         validators и findings
crates/storage/         SQLite repositories и migrations
crates/publisher/       staging, companion artifacts, rollback
fixtures/               маленькие обезличенные и лицензируемые cases
docs/                   решения, спецификации, ADR
```

## Provider policy

Первый обязательный adapter — Ollama. Облачный adapter не выбирается по популярности заранее: в M4 одинаковый golden corpus сравнивает качество русского, structured-output надёжность, privacy, цену и latency. После этого один adapter становится baseline, остальные остаются plugins за единым capability-интерфейсом.

Ядро требует от adapter:

- schema-constrained result либо эквивалентную строгую проверку;
- идентификаторы units и atoms без передачи файловых путей;
- timeout, cancel, rate limit, usage accounting и повторяемую классификацию ошибок;
- отсутствие tool calls;
- явное описание того, какие данные уходят за пределы компьютера.

Модель и её версия не являются архитектурной константой. Они выбираются профилем качества и сохраняются в provenance.

## Parser policy

Файлы Stellaris не передаются generic YAML-библиотеке: фактический формат локализации имеет собственные правила, дубли ключей и значимую byte-level форму. Реализуется небольшой lossless lexer/CST и отдельный parser внутритекстовой разметки.

До M2 запрещено обещать поддержку конструкции, для которой нет fixture и round-trip теста. Контекстный parser scripts может быть основан на готовой grammar либо на консервативном lexer, но его выбор проходит сравнительный spike: coverage, сохранение исходника, diagnostics, лицензия и maintenance.

## Управление зависимостями и версиями

- Rust toolchain фиксируется `rust-toolchain.toml`, зависимости — `Cargo.lock`, frontend — lock-файлом package manager.
- Production build воспроизводим и использует только проверенные lock-файлы.
- Dependabot/Renovate может предлагать обновления, но parser, SQLite, Tauri и provider SDK обновляются только с полным regression corpus.
- Version profile игры отделён от версии приложения. Новая версия Stellaris сначала проходит compatibility suite.
- Критическая уязвимость может ускорить обновление, но не отменяет технических gates.

## Осознанно не выбранные альтернативы

| Альтернатива | Почему не baseline |
|---|---|
| Python/PySide | быстрый прототип, но слабее единая byte-safe граница и сложнее воспроизводимая поставка; старый Python-код используется как источник тестовых случаев, не runtime |
| Tauri + Python sidecar/FastAPI | два runtime, IPC, упаковка и лишняя локальная поверхность атаки без доказанной пользы |
| Electron | больше runtime и полномочий Node.js, чем нужно локальному переводчику |
| Полностью web-приложение | browser sandbox неудобен для больших локальных коллекций, launcher paths и атомарной публикации |
| Microservices, Redis, Celery, PostgreSQL | не соответствуют однопользовательскому локальному продукту |
| Generic YAML parser | не даёт нужной модели дублей, malformed-source diagnostics и lossless round trip |
| Vector DB с первого дня | повышает сложность до появления доказанного retrieval bottleneck |
| Жёстко заданная LLM | качество и доступность моделей меняются; фиксируется benchmark и контракт, а не бренд модели |

## Первые технические spikes

До масштабной реализации должны быть отдельно доказаны:

1. Tauri build, подпись и доступ к выбранным каталогам на Apple Silicon macOS.
2. Byte-identical round trip на репрезентативных локализациях.
3. Безопасное распознавание markup и malformed строк без regex-only shortcuts.
4. Companion descriptor/load order на реальной поддерживаемой версии Stellaris.
5. Ollama cancellation, structured result и обработка недоступного runtime.

Официальные основания выбора: [Tauri 2 и кроссплатформенность](https://v2.tauri.app/), [архитектура Tauri](https://v2.tauri.app/concept/architecture/), [актуальные линии React](https://react.dev/versions), [SQLite как встраиваемая БД без отдельного процесса](https://www.sqlite.org/about.html), [Ollama API](https://docs.ollama.com/api/introduction).

