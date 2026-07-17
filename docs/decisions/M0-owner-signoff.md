# Решение владельца M0

- Дата: 17 июля 2026 года
- Статус: accepted — [PR #2](https://github.com/elenandar/Stellaris-mod-translator/pull/2), merge commit [`8d468b7`](https://github.com/elenandar/Stellaris-mod-translator/commit/8d468b7b8ca1f748dda8c072ce02933b15656dc2)
- Область: продуктовая стратегия и границы разработки

## Подтверждённые вводные владельца

Владелец уточнил:

1. Это локальный проект для перевода модов, с которыми он играет или будет играть в будущем.
2. Ollama уже установлен локально и содержит несколько LLM.
3. Каждое сгенерированное задание Codex должно указывать рекомендуемую модель Codex.
4. Разрешено выполнить рассмотренную remediation M0.

Эти вводные заменяют первоначальное предположение о публичном кроссплатформенном desktop-продукте.

## Решения

### D-001 — Персональная граница продукта

MVP обслуживает одного владельца, один текущий Apple Silicon Mac и явные личные playsets. Public beta, accounts, telemetry, cross-platform packaging и onboarding массового пользователя не являются требованиями.

### D-002 — CLI раньше GUI

Rust CLI — поддерживаемый интерфейс MVP. Tauri/React можно пересмотреть только после M5, если повседневный процесс покажет реальную проблему удобства.

### D-003 — Только локальный Ollama

MVP реализует один adapter для loopback Ollama и моделей с доказанными локальными весами. Cloud models, remote endpoints, автоматические pulls и скрытый provider/model fallback запрещены.

### D-004 — Явные состояния качества

Техническая безопасность, автоматическое review, обязательное human review и редакционное принятие различаются. Только владелец или другой человек-редактор может назначить `editorially_approved`.

### D-005 — Форма экспорта зависит от evidence

Внутренняя identity и история остаются привязаны к source mod. Рабочая гипотеза MVP — один managed RU bundle на выбранный playset, но варианты `per-source`, `playset-bundle` и `hybrid` проверяются по реальному load order и launcher behavior в M1A.

### D-006 — Feasibility качества проверяется рано

Установленные локальные модели проходят M1B до существенной реализации продукта. Технически безопасного parser недостаточно, если нужное смысловое, литературное и лорное качество недостижимо.

### D-007 — Восстановление является частью продукта

Принятые переводы, glossary decisions и provenance требуют проверяемых export/backup и restore. Git не является backup приватного translation workspace.

### D-008 — Модель задания Codex указывается явно

Будущие задания Codex следуют маршрутизации в `AGENTS.md` и `docs/roadmap.md`. Для safety-critical design и финальных gates требуется `GPT-5.6 Sol, Ultra`; ограниченная механическая работа может использовать более низкий tier с предписанным review.

## Намеренно отложенные решения

- Какая установленная Ollama-модель и profile параметров победит M1B.
- Точная export policy и правила load-order collisions.
- Поддерживаемая markup taxonomy за пределами проверенного M1 corpus.
- Любой GUI, дополнительная платформа, cloud provider, публичная поставка или Steam Workshop publishing.
- Лицензия репозитория. Для частной локальной работы она не блокирует M1, но обязательна до публичного распространения исходников.

## Граница полномочий после M0R

Принятый M0R разрешает только evidence-работы M1A и M1B. Он не разрешает массовый перевод, запись в active game/mod paths, production publishing, UI development или cloud integration.

Codex и другие cloud development tools не получают raw/private/copyrighted localisation. M1 использует только metadata, hashes, redacted summaries и synthetic/minimal fixtures; любое исключение требует отдельного явного consent владельца.
