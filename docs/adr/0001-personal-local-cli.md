# ADR-0001: персональный local-first CLI

- Статус: принят для M0R; становится baseline репозитория после merge
- Дата: 17 июля 2026 года
- Владелец решения: владелец репозитория

## Контекст

Первоначальная документация описывала кроссплатформенный Tauri desktop-продукт с public-release roadmap, опциональными cloud providers и отдельным companion mod на каждый source. Позже владелец уточнил реальную цель: персональный локальный инструмент для собственных текущих и будущих playsets Stellaris; Ollama с несколькими моделями уже установлен.

Первоначальное направление создавало сложность UI, packaging, платформ, privacy и launcher до проверки двух основных рисков: сохранения байтов localisation Stellaris и получения хорошего русского текста от локальных моделей.

## Решение

Строить модульный Rust monolith, содержащий:

- поддерживаемый CLI;
- независимое от интерфейса domain core;
- локальное состояние SQLite и проверяемые backup/restore;
- единственный loopback Ollama adapter с enforcement residency и digest;
- immutable source generations, lossless parsing, typed atoms, controlled rendering, versioned artifacts, validation и rollback;
- human-only editorial approval;
- versioned export policy, выбранную после реального load-order spike.

Провести format/threat evidence и benchmark качества локальных моделей параллельно до реализации полного translation engine. Не добавлять в baseline GUI, cloud provider, cross-platform packaging или public-release work.

## Последствия

Преимущества:

- усилия направлены на реальный процесс владельца;
- filesystem и translation-quality риски проверяются рано;
- поставляемый runtime остаётся небольшим и локальным;
- для private mod text не требуется network path;
- будущий UI сможет использовать то же ядро, если окажется полезным.

Ограничения и стоимость:

- для MVP владелец использует terminal;
- сначала поддерживается только текущее macOS-окружение;
- Ollama остаётся внешней локальной зависимостью;
- output layout нельзя финализировать до evidence реального launcher/load order;
- высокорисковый текст всё равно требует человеческого review.

## Отклонённые альтернативы baseline

- **Обязательный Tauri/React desktop:** слишком большая продуктовая поверхность до доказательства основных рисков.
- **Python как product runtime:** удобен для экспериментов, но не выбран для поставляемого byte-safe ядра; остаётся допустимым disposable research tooling.
- **Cloud-capable provider layer:** противоречит local-only scope и создаёт consent/secrets/residency работу без текущей потребности.
- **Один companion на source как канон:** может создать десятки launcher entries и не проверен на коллекции владельца.
- **Один универсальный bundle как канон:** тоже преждевременно; нужны evidence по collisions, `replace/`, uninstall и load order.

## Условия пересмотра

ADR можно пересмотреть после M5 либо при противоречащем gate evidence. Изменение требует нового ADR и сохраняет source immutability, typed rendering, provenance, backup/restore и явные editorial states.
