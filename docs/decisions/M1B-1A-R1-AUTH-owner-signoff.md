# Owner signoff M1B-1A-R1-AUTH

- Milestone: `M1B-1A-R1-AUTH — bounded request/result transport and evidence-provenance remediation authorization`
- Decision content: `acceptance_state=owner_accepted`
- Operational review state: `M1B-1A-R1-AUTH: READY_FOR_OWNER_REVIEW`
- Effect: `after_review_and_merge_to_main`
- Pre-effect PR #10 state: `PR10: CHANGES_REQUIRED_UNCHANGED`
- Candidate state: `M1B-1A1: BLOCKED_PENDING_R1_AUTH`
- Executable admission: `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`
- Provider execution: `M1B-1A PROVIDER EXECUTION: NOT_STARTED`
- Dependent gates: `M1B: NOT_EVALUATED`; `M1A: BLOCKED`; `M2: FORBIDDEN`

## Решение и момент effect

Владелец делегирует только подготовку одной bounded static remediation уже
существующего draft PR #10. Exact
[`owner authorization record`](M1B-1A-R1-AUTH-owner-authorization.json)
содержит `acceptance_state=owner_accepted`, но это значение не активирует
remediation, не принимает future bytes и не является executable trust root.

До отдельного owner review и merge exact authorization PR в `main` никакой
authority на изменение PR #10 нет. Effect требует внешнее owner-controlled
решение, которое repository bytes не могут создать или самоподтвердить:

- ровно один PR с head
  `agent/m1b-1a-r1-transport-provenance-auth` и base `main`;
- creation base
  `1f10c151c5adac5fbf765af8093c7eddf8cf0429`;
- ordinary two-parent merge, не squash и не rebase;
- first parent merge commit равен exact creation base;
- second parent равен external final head authorization PR;
- final-head и base-to-merge deltas содержат exact шесть tracked AUTH outputs.

Если `main` изменится до owner merge или любая identity/delta не совпадёт,
effect не возникает. Commit, push или создание draft PR сами по себе authority
не дают.

## Exact scope identity

Владелец принимает на review только
[`m1b-1a-r1-remediation-scope-v1.json`](../../registry/m1b/m1b-1a-r1-remediation-scope-v1.json)
с exact identity:

| Поле | Значение |
|---|---|
| Schema / generation | `m1b-1a-r1-remediation-scope-v1` / `1` |
| Canonical bytes | `27399` |
| Raw SHA-256 | `86741260ac3b6338d4d8df5855a9d34e6ae4007d8d0aaa671b22b2e5a481742b` |
| Framing domain | `stellaris-m1b-1a-r1-remediation-scope-v1` |
| Framed SHA-256 | `26121585897212dd54732a29245858cc856a334d6b421a946273f0f2708bb74b` |

Canonical scope — compact sorted-key ASCII JSON плюс один LF. Framed digest
использует domain, NUL, unsigned 64-bit big-endian length canonical bytes
вместе с LF и сами bytes. Scope self-hash не содержит; exact hashes находятся
в отдельном owner record.

Owner record — `5112` canonical bytes, raw SHA-256
`84d43e5b4f5d90cd10f3b0137db47923c92a14c119aeea27a88cd7d9b8fa101d`.
Полный normative contract:
[`m1b-1a-r1-remediation-authorization-contract.md`](../specs/m1b-1a-r1-remediation-authorization-contract.md).

## Immutable remediation target

Scope bind-ит существующий PR #10 как read-only pre-remediation input:

| Field | Exact value |
|---|---|
| Repository / PR | `elenandar/Stellaris-mod-translator` / `10` |
| State | `OPEN / DRAFT`, auto-merge absent |
| Branch | `agent/m1b-1a1-inert-candidate-construction` |
| Head | `66f905cf266b9d1c1f56d0d706184387ffedb36e` |
| Base | `1f10c151c5adac5fbf765af8093c7eddf8cf0429` |
| Current changed paths | `11` |
| Candidate roles | `4`, total `94473` bytes |

Current proposed manifest remains only a proposal:

| Field | Exact value |
|---|---|
| Canonical bytes | `814` |
| Raw SHA-256 | `3d2daab0211fb7a4e3e40cdcdb0fddeb6087b1fb0e640f1e2925557ff8ec48cd` |
| Framed SHA-256 | `38c710987da74369d26883cfa33a7587a98746f1eb7129716a5d8315a23cd391` |
| Implementation generation | `1` |
| Source linkage | `4/4` |

Candidate fixture identity remains `42` cases, `22394` canonical bytes, raw
SHA-256
`a7f13de146722edf6af167ce63b7c33bf650fad3ab66339e73d902b047859ec7`.
Ни одна из этих identities не принимается как executable.

## Делегированный future scope

После effect future remediation обязана начать уже в clean tracked worktree и
index на exact PR #10 branch/head. Scope не разрешает switch, checkout,
tracking setup или иной worktree materialization. Затем разрешены:

1. read-only verification exact main authorization merge;
2. один ordinary integration merge с first parent exact `66f905cf…` и second
   parent exact main authorization merge commit;
3. изменение только `19` future outputs: `18` tracked и один ignored sanitized
   evidence file;
4. один ordinary remediation commit и один non-force push existing PR #10
   branch;
5. status/body update только того же open draft PR #10.

Четыре AUTH artifacts могут появиться в PR #10 только как immutable consequence
integration merge. Их нельзя независимо редактировать или stage-ить.

Exact future scope включает текущие `11` PR #10 paths, новый machine/spec
contract v5, contract-v5 review, versioned inert TCB fixture
`fixtures/m1b/tcb-admission-v5/cases.json`, versioned verifier/test, один R1
remediation review и ignored evidence. Fixture использует non-colliding schema
`m1b-tcb-admission-contract-v5-cases-v1`; historical unversioned fixture со
schema `m1b-tcb-admission-cases-v5` остаётся неизменным.

Новая ветка/PR, rebase, force-push, amend, stash/reset/clean, PR #10 merge,
auto-merge, ready-for-review, close, main mutation, tags/releases/Actions и
другой network запрещены.

## Обязательная remediation semantics

Contract/envelope/plan получают новые generations `5 / 5 / 4`. Нормативные
definitions обязаны закрепить:

- один bounded anonymous request pipe, максимум `4194304` bytes, ровно один
  request и обязательное закрытие writer;
- отсутствие ambient argv/environment/cwd discovery и repository input file;
- отдельный bounded anonymous private-result pipe, ровно один result, writer
  close и read-through-EOF;
- private result не-public и запрещён в Git, PR, evidence, logs и public
  outcomes;
- overflow, truncation или writer/EOF failure после assignment создаёт ровно
  одну controlled terminal-failure row и сохраняет assigned denominator;
- private translation сохраняется для local human review либо request
  завершается controlled failure.

Raw/direct/synthetic vectors всегда имеют
`decision_grade_eligible=false`, explicit scope/split; mixed запрещён, tuning
не становится holdout. Decision-looking aggregate PASS невозможен без отдельной
caller-nonconstructible full-decision admission, которой этот scope не создаёт.

Provider/model JSON не назначает technical conformance, D2–D5 human statuses,
authoritative findings, gates, accounting или runtime measurements. D1 pass
возможен только через local deterministic exact expected/observed atom
comparison; без validator D1 остаётся `not_evaluated`. Critical D1 finding
исключает D1 pass и technical success. D2–D5 требуют отдельно связанное human
evidence.

После assignment каждый timeout, network/HTTP failure, truncation, malformed
JSON, schema error или provider error создаёт одну terminal row и остаётся в
denominator. Retry, repair и fallback запрещены; closed codes и все counters
вычисляет harness. Pre-dispatch invalid request остаётся отдельной фазой.

Любое изменение candidate source требует `implementation_generation=2`,
пересчёта четырёх source hashes, нового canonical/framed manifest digest и
обновления fixture, reviews, evidence и PR body. Protocol остаётся
v7/generation 108; изменение frozen semantics требует отдельного owner-freeze.
Никакая неизвестная future identity этим signoff не принимается.

## Default-deny и исторические bytes

Machine scope разделяет repository content, three exact future directories,
Git/GitHub, host validation, pre-effect activation verification и
candidate/provider runtime authority. Для каждой плоскости всё неуказанное
запрещено. Runtime authority остаётся полностью отрицательной.

Исторические v4 registry/spec/fixture и принятые M1B-1A1-AUTH/scope-v2 artifacts
остаются byte-identical. Сохраняются все `16` executable/runtime blockers.

Future remediation всё ещё не разрешает candidate parse, tokenization, lint,
compile, import или execution; новый repository verifier/test также остаётся
inert. Provider/Ollama/model calls, metadata probes, model store, corpus,
prompt/template, mods, Workshop, Stellaris, launcher, playset, translations,
runtime instances, acceptance, admission, M1B-1A2, benchmark, M2, activation и
publishing запрещены.

## Validation boundary

Authorization validation ограничена canonical JSON reproduction,
duplicate-key/type/float/path/order checks, raw/framed SHA-256, exact
path/parent closure, status-only diff review, Markdown links,
`git diff --check` и clean-tree/local/upstream/remote/PR parity. Тесты не
запускаются.

Candidate source читался только как raw bytes для SHA/size и line-oriented
static review. Он не передавался Python AST/parser/tokenizer/linter/compiler,
не импортировался и не исполнялся. Provider/model/private data не читались.

## Gate

```text
AUTHORIZATION: READY_FOR_OWNER_REVIEW
M1B-1A-R1-AUTH: READY_FOR_OWNER_REVIEW
EFFECT: NOT_ACTIVE_UNTIL_OWNER_REVIEW_AND_MERGE
PR10: CHANGES_REQUIRED_UNCHANGED
M1B-1A1: BLOCKED_PENDING_R1_AUTH
M1B-1A2: FORBIDDEN
EXECUTABLE_TCB_ADMISSION: NOT_GRANTED
M1B-1A PROVIDER EXECUTION: NOT_STARTED
M1B: NOT_EVALUATED
M1A: BLOCKED
M2: FORBIDDEN
PR: DRAFT
```

Единственный следующий шаг — owner review этого authorization draft PR с
ordinary merge только при сохранении exact base. Remediation PR #10 до effect
запрещена.
