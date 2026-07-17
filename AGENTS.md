# Инструкции Codex

## Область проекта

Репозиторий создаёт персональный local-only процесс перевода модов Stellaris для одного владельца и его текущих/будущих playset.

- Интерфейс MVP — Rust CLI на текущем Mac владельца.
- Исходные моды, Steam Workshop, файлы игры и существующие переводы — read-only inputs.
- Единственный runtime LLM-provider в scope — уже установленный локальный Ollama на loopback.
- Cloud providers, remote endpoints, модели `*-cloud`, скрытый fallback и автоматический pull моделей запрещены.
- Tauri/React, другие ОС, публичная поставка и Steam Workshop publishing требуют отдельного будущего решения владельца и ADR.
- Старый репозиторий и generated text не являются источниками истины.

## Соблюдение этапов

Перед работой прочитать `docs/roadmap.md` и определить текущий milestone. Не переходить через gate неявно.

- M0R — только решения и документация.
- M1A — read-only evidence формата, угроз, load order и артефакта.
- M1B — изолированный benchmark локальных моделей; его output не попадает в active game files.
- M2 — первый этап реализации safety kernel.
- Publishing и активный перевод запрещены до прохождения их prerequisites.

Если задача просит анализ или диагностику, не реализовывать исправление без явного запроса. При отсутствии обязательного evidence остановиться безопасно и назвать минимальный следующий шаг.

## Обязательные правила безопасности

- Никогда не изменять source mod, Workshop или файлы установки Stellaris.
- Работать с immutable copy прочитанных байтов либо прерываться при изменении source generation.
- Не коммитить raw mods, полную copyrighted localisation, private translations, SQLite workspaces и generated bundles.
- Codex и другие cloud development tools получают только repository code/docs, metadata, hashes, redacted summaries и synthetic/minimal fixtures. Не выводить raw/private/copyrighted localisation в prompts, tool output, screenshots, logs, subagent messages или PR без отдельного явного consent владельца.
- Если исследование требует локального чтения private corpus, локальный helper выводит только агрегированное или обезличенное evidence; до отправки результата в Codex выполняется leakage check.
- Runtime-модель Ollama меняет только human text spans через typed renderer; файловых и иных инструментов у неё нет.
- Unknown syntax, ambiguous duplicate/load-order behavior, unknown model residency и path ambiguity являются blockers.
- `technical_safe` никогда не означает `editorially_approved`; литературное/лорное принятие выполняет только человек.
- До массовой обработки должен быть доказан backup/restore принятых переводов.

## Обязательный заголовок задания

Каждое создаваемое задание Codex начинается с блока:

```text
Milestone:
Разрешённый слой:
Рекомендуемая модель Codex:
Уровень рассуждения:
Входные evidence:
Результаты:
Обязательные проверки:
Условия остановки:
Вне scope:
```

Выбор модели — инструкция для разработки. Это не Ollama-модель переводчика.

## Маршрутизация моделей Codex

- `GPT-5.6 Sol, Ultra`: архитектура, threat model, format contracts, parser design, filesystem containment, provider privacy/residency, identity, publish/rollback, методология benchmark, semantic/lore policy и каждый финальный safety/acceptance gate.
- `GPT-5.6 Sol, High` или `Max`: ограниченная реализация после утверждения контрактов. Gate-critical изменения всё равно проходят отдельный Sol Ultra review.
- `GPT-5.6 Terra, Medium` или `High`: механическое создание fixtures, повторяющиеся тесты, inventories, форматирование документации и возможный будущий UI. Terra не принимает финальное gate-решение.
- Максимальный tier резервируется для сложной quality-first работы; не выбирать его механически для ограниченной задачи с принятым контрактом.
- Если указанный tier недоступен, зафиксировать точные фактические model/tier, выбрать ближайший доступный уровень и не снижать acceptance criteria.

Текущее официальное руководство относит Sol к frontier-capability tier, а Terra — к сбалансированным задачам. Доступность моделей меняется, поэтому при генерации задания нового этапа сверяться с [OpenAI model guidance](https://developers.openai.com/api/docs/guides/model-guidance?model=gpt-5.6).

## Definition of done

Сообщить точные изменённые файлы, выполненные проверки, evidence paths, warnings/blockers и следующий разрешённый gate. Успешная генерация не доказывает завершение: нужны проверки байтов, контрактов, тестов, backup/rollback или человеческое review согласно слою задачи.
