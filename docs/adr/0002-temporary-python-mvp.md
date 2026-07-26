# ADR-0002: временный Python MVP-0 и прекращение AUTH-first процесса

- Статус: accepted owner direction
- Дата: 26 июля 2026 года
- Владелец решения: владелец репозитория

## Контекст

Предыдущая дорожная карта задерживала практический переводчик за M1B
authorization/evidence контуром. Он стал существенно сложнее продукта, при этом
не дал владельцу отдельный безопасный candidate для ручной проверки.

## Решение

Реализовать MVP-0 как local-only Python 3.9+ CLI без обязательных внешних
runtime-зависимостей. Он поддерживает консервативный lossless subset Stellaris
localisation, вызывает только явно выбранный exact tag локального Ollama на
numeric loopback и создаёт новый отдельный candidate-каталог.

PR №11 и AUTH-first remediation не являются зависимостью MVP-0 и считаются
superseded для этого пути. Их сложный authorization registry и
evidence-generation pipeline не переносятся в продукт.

MVP-0 сохраняет обязательные границы: source immutable, generic YAML запрещён,
модель меняет только human spans, atoms/escapes восстанавливаются из исходных
байтов, unsupported data получает видимый English fallback, output строится во
временном sibling-каталоге и не регистрируется в launcher.

## Последствия

- Python — осознанный временный runtime первого рабочего vertical slice, а не
  обязательство навсегда отказаться от Rust.
- Candidate является техническим результатом для review, но не получает
  `editorially_approved`.
- Реальные моды и private localisation не входят в repository tests и требуют
  отдельного consent владельца.
- Массовая обработка, active publish, launcher registration, cloud endpoints,
  model pull и скрытый fallback остаются вне scope.

## Следующее решение

После synthetic suite выполнить ручной synthetic smoke. Затем владелец может
явно разрешить пробу ровно одного выбранного private мода. Результаты этой пробы
определят минимальные parser/quality улучшения и необходимость будущей миграции
ядра на Rust.
