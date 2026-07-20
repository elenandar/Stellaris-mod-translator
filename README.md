# Stellaris Mod Translator

Персональный локальный инструмент для качественного и технически безопасного перевода модификаций Stellaris, с которыми владелец проекта играет или планирует играть на macOS.

Основной интерфейс MVP — Rust CLI. Инструмент анализирует выбранные локальные и Workshop-моды только для чтения, хранит состояние переводов в SQLite, использует локальные модели через Ollama и собирает управляемый русский артефакт без изменения оригиналов.

## Статус

Production-реализация ещё не начата. Персональный local-only baseline `M0R` принят и слит в [PR #2](https://github.com/elenandar/Stellaris-mod-translator/pull/2), merge commit [`8d468b7`](https://github.com/elenandar/Stellaris-mod-translator/commit/8d468b7b8ca1f748dda8c072ce02933b15656dc2). Evidence [PR #3](https://github.com/elenandar/Stellaris-mod-translator/pull/3) слит как [`2b51879`](https://github.com/elenandar/Stellaris-mod-translator/commit/2b51879d8e358cf5412f3a6792f33c71ae79d863), а hardening [PR #4](https://github.com/elenandar/Stellaris-mod-translator/pull/4) — как [`9cd10d1fd3c9b52354ea4a5c181b0ecaf9c05240`](https://github.com/elenandar/Stellaris-mod-translator/commit/9cd10d1fd3c9b52354ea4a5c181b0ecaf9c05240). Текущий verdict остаётся `M1A: BLOCKED`. Это evidence-этап, а не начало product CLI.

После принятия `M0R` разрешены только два доказательных этапа: исследование реального формата и загрузки модов (`M1A`, сейчас `BLOCKED`) и изолированный benchmark качества локальных моделей (`M1B`). Сейчас M1B protocol находится under review: `M1B: NOT_EVALUATED`, feasibility verdict отсутствует и benchmark не запускался. Только принятые verdicts `M1A: GO` и `M1B: QUALITY_FEASIBLE` вместе разрешают `M2`; сейчас `M2: FORBIDDEN`, массовый перевод и active publish запрещены.

Текущая synthetic proposal identity — protocol v4/generation 105 и analysis
policy v4/generation 105. Она закрывает tuning/holdout pooling в decision-grade
statistics, сохраняет reviewer-specific finding outcomes и запрещает content
review отсутствующего output; любые две initial finding reviews требуют
distinct human identities. Synthetic corpus bytes не менялись: corpus
v3/generation 304 остаётся тем же. Это contract hardening, а не запуск M1B-1 и
не quality verdict.

## Контракт MVP

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

## Следующий шлюз

Hardening [PR #4](https://github.com/elenandar/Stellaris-mod-translator/pull/4) слит, но исторический report 17 июля и повторная проверка 18 июля честно сохраняют `M1A: BLOCKED`: byte/containment evidence собрано, а atomic cross-file coherence, arbitrary same-UID path-race protection и effective load-order/collision policy недостаточны для `GO`.

Следующий разрешённый шаг — только owner review M1B protocol. `M1B: NOT_EVALUATED`: review контракта не является feasibility verdict и не разрешает benchmark, active experiment или product implementation. Только позднее принятые verdicts `M1A: GO` и `M1B: QUALITY_FEASIBLE` вместе разрешат safety kernel; до этого `M2: FORBIDDEN`.
