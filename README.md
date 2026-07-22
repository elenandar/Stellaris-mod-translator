# Stellaris Mod Translator

Персональный локальный инструмент для качественного и технически безопасного перевода модификаций Stellaris, с которыми владелец проекта играет или планирует играть на macOS.

Основной интерфейс MVP — Rust CLI. Инструмент анализирует выбранные локальные и Workshop-моды только для чтения, хранит состояние переводов в SQLite, использует локальные модели через Ollama и собирает управляемый русский артефакт без изменения оригиналов.

## Статус

Production-реализация ещё не начата. Персональный local-only baseline `M0R` принят и слит в [PR #2](https://github.com/elenandar/Stellaris-mod-translator/pull/2), merge commit [`8d468b7`](https://github.com/elenandar/Stellaris-mod-translator/commit/8d468b7b8ca1f748dda8c072ce02933b15656dc2). Evidence [PR #3](https://github.com/elenandar/Stellaris-mod-translator/pull/3) слит как [`2b51879`](https://github.com/elenandar/Stellaris-mod-translator/commit/2b51879d8e358cf5412f3a6792f33c71ae79d863), hardening [PR #4](https://github.com/elenandar/Stellaris-mod-translator/pull/4) — как [`9cd10d1`](https://github.com/elenandar/Stellaris-mod-translator/commit/9cd10d1fd3c9b52354ea4a5c181b0ecaf9c05240), M1B protocol proposal [PR #5](https://github.com/elenandar/Stellaris-mod-translator/pull/5) — как [`ed07bcc`](https://github.com/elenandar/Stellaris-mod-translator/commit/ed07bcca96945dbb49206c975908e00c832210b5), external owner-freeze [PR #6](https://github.com/elenandar/Stellaris-mod-translator/pull/6) — как [`9f854da`](https://github.com/elenandar/Stellaris-mod-translator/commit/9f854da7501dec6ec9afc5e4bf71dfaa1ea9ecbc), а stable-read hardening [PR #7](https://github.com/elenandar/Stellaris-mod-translator/pull/7) — как [`424a4e4`](https://github.com/elenandar/Stellaris-mod-translator/commit/424a4e45066cfbff3f9b3da2ec2cf6ad62a643fb). Текущий verdict остаётся `M1A: BLOCKED`. Это evidence-этап, а не начало product CLI.

После принятия `M0R` разрешены только два доказательных этапа: исследование реального формата и загрузки модов (`M1A`, сейчас `BLOCKED`) и изолированный benchmark качества локальных моделей (`M1B`). Exact proposal v7/generation 108 принят отдельным external owner-freeze record только как declarative basis записанного `M1B-1A local synthetic provider preflight`; после merge PR #6 exact scope действует со state `OWNER_FREEZE: ACCEPTED`, а merge PR #7 выставил `STABLE_READ_HARDENING: ACCEPTED`. Отдельный contract-only этап теперь определяет будущий executable/runtime admission: `M1B-1A0 CONTRACT: READY_FOR_REVIEW`, `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`, `EXECUTABLE_TCB_OWNER_DECISION_REQUIRED: PRESERVED`, `PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN: PRESERVED`, `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN: PRESERVED`. `M1B-1A PROVIDER EXECUTION: NOT_STARTED`, `M1B: NOT_EVALUATED`; benchmark не запускался. Только принятые verdicts `M1A: GO` и `M1B: QUALITY_FEASIBLE` вместе разрешают `M2`; сейчас `M2: FORBIDDEN`, массовый перевод и active publish запрещены.

Текущая post-contract authorization boundary:
`M1B-1A1-AUTH: OWNER_REVIEW_REQUIRED` и
`CANDIDATE CONSTRUCTION: NOT_AUTHORIZED`.

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
- [External owner-freeze contract M1B-0F](docs/specs/m1b-owner-freeze-contract.md)
- [Owner signoff M1B-0F](docs/decisions/M1B-0F-owner-signoff.md)
- [Offline executable/TCB admission contract M1B-1A0](docs/specs/m1b-offline-executable-tcb-admission-contract.md)
- [Contract review M1B-1A0](docs/decisions/M1B-1A0-contract-review.md)

## Следующий шлюз

Hardening [PR #4](https://github.com/elenandar/Stellaris-mod-translator/pull/4) слит, но исторический report 17 июля и повторная проверка 18 июля честно сохраняют `M1A: BLOCKED`: byte/containment evidence собрано, а atomic cross-file coherence, arbitrary same-UID path-race protection и effective load-order/collision policy недостаточны для `GO`.

External owner-freeze PR #6 и stable-read hardening PR #7 слиты;
`OWNER_FREEZE: ACCEPTED`, `STABLE_READ_HARDENING: ACCEPTED`. M1B-1A0 создаёт
только reviewable v4/generation-4 offline contract и synthetic conformance gate.
Existing five-field implementation acceptance остаётся неизменным, а отдельный
runtime acceptance exact bind-ит canonical envelope без выдачи authority;
synthetic `owner_accepted` — только проверка shape/linkage.

Review и merge этого contract PR фиксируют только M1B-1A0 и не разрешают
создание candidate. После merge доступен только отдельный
`M1B-1A1-AUTH` со state `OWNER_REVIEW_REQUIRED`; до его отдельного явного
принятия `CANDIDATE CONSTRUCTION: NOT_AUTHORIZED`.

`M1B-1A1-AUTH` — ограниченный owner authorization для будущей offline-задачи.
Сам gate не создаёт executable files или real candidate manifest/envelope, не
запускает interpreter/provider, не создаёт operational `owner_accepted`
admission и не снимает `EXECUTABLE_TCB_OWNER_DECISION_REQUIRED`. Он должен exact
перечислить разрешённые repository paths для ролей `analysis_engine`,
`contract_validator`, `provider_request_harness` и
`synthetic_fixture_materializer`, отделить read-only inputs от разрешённых
write outputs и запретить любые не перечисленные reads/writes, execution,
provider/Ollama/model action, private corpus и benchmark.

Только после отдельного explicit owner acceptance M1B-1A1-AUTH может начаться
отдельный `M1B-1A1`: создание proposed four-role candidate bytes и exact offline
manifest/envelope/launcher/import/source-eligibility evidence без acceptance или
execution. M1B-1A1 не может принять созданные identities. После его review
отдельный `M1B-1A2` может зафиксировать owner-controlled решение только над уже
известными exact identities. Даже M1B-1A2 не разрешает Ollama probe,
provider/model call, private corpus или benchmark: для исполнения нужен ещё один
явный gate. `M1B: NOT_EVALUATED`: contract review не является feasibility
verdict. Только позднее принятые verdicts `M1A: GO` и
`M1B: QUALITY_FEASIBLE` вместе разрешат safety kernel; до этого `M1A: BLOCKED`
и `M2: FORBIDDEN`.
