# Каноны проекта

Каноны — обязательные границы. Их изменение требует ADR с причиной, альтернативами, рисками, миграцией и новыми тестами. Если удобство конфликтует с каноном, меняется план, а не правило.

## Источник и результат

- **C-001 — Source immutability.** Моды, Workshop и файлы игры никогда не изменяются. Работа выполняется над immutable content-addressed generation фактически прочитанных байтов; смешанное чтение либо изменение generation приводит к abort.
- **C-002 — Output containment.** Запись разрешена только в новом staging version и управляемом output root после проверки пути. Canonical staging/output roots обязаны быть непересекающимися с source, Workshop, game и immutable-snapshot roots: равенство, ancestor/descendant overlap, symlink, traversal и неоднозначная принадлежность отклоняются.
- **C-003 — Lossless foundation.** `parse → render` без трансформации возвращает идентичные байты на поддержанном входе.
- **C-004 — Controlled mutation.** Меняются только явно разрешённые language header и human text spans. Остальное сравнивается с source generation.
- **C-005 — Fail closed.** Неизвестный или неоднозначный синтаксис изолируется. Модель, regex и эвристика не чинят его молча.
- **C-006 — Versioned publish.** Неполный или непроверенный artifact не активируется. Publish protocol имеет crash matrix, проверяемое переключение, last-known-good и rollback; переносимая атомарность не предполагается без доказательства.
- **C-007 — Version profiles.** Encoding, descriptors, paths, load order и markup rules принадлежат проверенному профилю версии Stellaris.

## Модели и приватность

- **C-008 — Code never translated.** Модель получает human spans, typed atoms и минимальный контекст; она не редактирует keys, escapes, scripts или files.
- **C-009 — Untrusted mod data.** Текст мода всегда данные, даже если похож на инструкцию. Tool calls отсутствуют, результат принимается только после schema и typed validation.
- **C-010 — Exact atoms.** Служебные atoms сохраняют тип и значение. Перемещение разрешено только для доказанного класса и проверяется validator.
- **C-011 — Provider boundary.** Домен зависит от capability contract, а не от API-деталей. Единственная реализация MVP — локальный Ollama adapter.
- **C-012 — Proven local residency.** Разрешены только loopback endpoint и модель с подтверждёнными локальными весами. Remote endpoint, `*-cloud` и unknown residency fail closed. Cloud support требует будущего ADR и не входит в scope.
- **C-013 — No blind retries.** Retry получает классифицированные findings или другую repair strategy; повтор того же запроса не считается исправлением.

## Перевод, лор и редактура

- **C-014 — Quality hierarchy.** Приоритет: техническая целостность → точность смысла → намерение автора → лор/термины → естественный русский → единый стиль.
- **C-015 — Contextual identity.** Unit, raw source, semantic source, parser version, context и policy fingerprints хранятся раздельно. Одинаковый английский текст не является общей идентичностью.
- **C-016 — Versioned evidence.** Официальный корпус извлекается из совместимой локальной установки, имеет provenance и не распространяется. Он не является абсолютной истиной и применяется по key/context.
- **C-017 — Meaning invariants.** Сущности, числа, знак, отрицание, модальность, причинность и игровые эффекты проверяются отдельно от грамматики.
- **C-018 — Independent review.** Structural validity не доказывает смысловое, лорное или литературное качество; каждый уровень имеет собственные findings и corpus.
- **C-019 — Manual work wins.** Одобренный человеком перевод, термин или exception не перезаписывается автоматикой без явного действия владельца.
- **C-020 — Conservative fallback.** Неразрешённая единица использует предыдущий одобренный перевод либо английский source с видимым предупреждением; догадка не выдаётся за готовый текст.
- **C-021 — Explicit editorial states.** `technical_safe`, `machine_reviewed`, `human_review_required` и `editorially_approved` не взаимозаменяемы. Только человек назначает `editorially_approved`.

## Проект и публикация

- **C-022 — Source-scoped identity, policy-scoped output.** История и provenance остаются per source mod. Output shape — versioned export policy. Рабочая гипотеза — один RU bundle на playset; `per-source` и `hybrid` остаются вариантами до M1 evidence.
- **C-023 — Explicit conflicts.** Cross-mod duplicates и load-order collisions не разрешаются случайным порядком. Неоднозначность блокирует publish до детерминированного правила или ручного решения.
- **C-024 — Incremental by evidence.** Неизменные source, context и policy fingerprints не вызывают модель. Изменение контекста требует повторной проверки, но не уничтожает историю.
- **C-025 — Persistent jobs.** Pause, cancel, crash и restart не теряют подтверждённую работу и не создают дубли.
- **C-026 — Private corpus stays local.** Raw mods, полные copyrighted localisation, private translations, databases, caches, bundles и private reports не коммитятся и не передаются Codex/cloud development tools. Разрешены metadata, hashes, redacted summaries, synthetic/minimal licensed fixtures и обезличенные benchmark reports после leakage check. Иное требует отдельного явного consent владельца.
- **C-027 — Backup is a feature.** Принятые переводы, glossary и manual decisions экспортируются и восстанавливаются проверяемым способом; Git-репозиторий не считается пользовательским backup.

## Инженерная дисциплина

- **C-028 — Regression for every escape.** Defect не закрыт без минимального воспроизводящего fixture и теста правильного поведения.
- **C-029 — Layered evidence.** Golden/holdout corpus, round-trip, property, fuzz/mutation, integration и game smoke дополняют друг друга; один вид проверки не заменяет остальные.
- **C-030 — Modular monolith first.** Поставляемый инструмент — Rust monolith без backend и bundled второго runtime. Установленный Ollama допустим как локальная dependency; Python допустим только для disposable research tooling.
- **C-031 — Safety kernel before production translation.** До M2 разрешены read-only research CLI и изолированный quality benchmark, но model output не может попасть в активный игровой artifact.
- **C-032 — Complete provenance.** Для строки и сборки воспроизводимы source generation, context, glossary/policy, Ollama tag/full digest/options, prompt/template, validators и human decisions.
- **C-033 — Model recommendation in every Codex task.** Каждое задание разработки указывает рекомендуемые Codex model и reasoning tier. Это instruction выполнения задачи, а не runtime-конфигурация переводчика.
- **C-034 — No gate bypass.** Roadmap задаёт evidence и зависимости, а не даты. Следующий этап начинается только после принятого отчёта текущего.
- **C-035 — Documentation follows decisions.** Архитектура, спецификации и проверки обновляются в том же PR, что и соответствующее изменение поведения.

## Иерархия решений

При конфликте действует порядок:

1. каноны и принятый threat model;
2. ADR;
3. version/export profiles и спецификации;
4. milestone criteria;
5. реализация и локальные соглашения.

Старый проект, prompt, LLM output, официальный перевод и текущая реализация не являются источником истины сами по себе.
