# Owner signoff M1B-1A-R1-AUTH

- Milestone: `M1B-1A-R1-AUTH v3 — post-merge bounded request/result transport and evidence-provenance remediation authorization`
- Decision content: `acceptance_state=owner_accepted`
- Operational review state: `M1B-1A-R1-AUTH-V3: READY_FOR_OWNER_REVIEW`
- Effect: `after_review_and_merge_to_main`
- Historical PR #10 state: `PR10: MERGED_OWNER_CONTROLLED_SCOPE_DEVIATION`
- Candidate state: `PR10_CANDIDATE: INERT_NOT_ADMITTED`
- Scope v1: `SCOPE_V1: NEVER_EFFECTIVE`
- Scope v2: `SCOPE_V2: SUPERSEDED_BEFORE_EFFECT`
- Remediation state: `R1_REMEDIATION: NOT_AUTHORIZED_UNTIL_V3_MERGE`
- Executable admission: `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`
- Provider execution: `M1B-1A PROVIDER EXECUTION: NOT_STARTED`
- Dependent gates: `M1B: NOT_EVALUATED`; `M1A: BLOCKED`; `M2: FORBIDDEN`

## Решение и момент effect

Владелец делегирует только одну будущую bounded static remediation из уже
слитого inert baseline PR #10: новая ветка и один новый draft PR после effect.
Exact
[`owner authorization record`](M1B-1A-R1-AUTH-owner-authorization.json)
содержит `acceptance_state=owner_accepted`, но это значение не активирует
remediation, не принимает future bytes и не является executable trust root.

До отдельного owner review и merge exact authorization PR в `main` никакой
authority на remediation нет. Effect требует внешнее owner-controlled
решение, которое repository bytes не могут создать или самоподтвердить:

- exact PR #11 с head
  `agent/m1b-1a-r1-transport-provenance-auth` и base `main`;
- его external final head наследует recovery integration merge
  `3a57701275914d905f76606cf6db3072c40a17ac` с ordered parents
  `b2db2e612aac29f88f2762cb8bc1d3efbcdb6da6` и
  `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- ordinary two-parent merge, не squash и не rebase;
- first parent merge commit равен exact
  `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- second parent равен external final head PR #11;
- final-head и base-to-merge deltas содержат exact шесть tracked AUTH outputs.
- четыре normative AUTH artifacts byte-identical в external final head и merge
  tree.

Если `main` изменится до owner merge или любая identity/delta не совпадёт,
effect не возникает. Commit, push или создание draft PR сами по себе authority
не дают.

V3 correction началась только после exact preflight: branch/local/upstream/
remote/PR-head `b247a20500b28227e826b9f3c14da8b8d77d48a3`, `origin/main`
и PR base `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`, clean tracked
worktree/index, PR #11 `OPEN / DRAFT / MERGEABLE`, auto-merge absent, exact
six-path v2 diff, future branch absent во всех четырёх namespaces и thread
`PRRT_kwDOTbY5J86TVPjf` unresolved. Этот initial head не является final v3
head или future branch base; final head остаётся external binding, а future
base — только exact PR #11 merge commit после effect.

## Exact scope identity

Владелец принимает на review только
[`m1b-1a-r1-remediation-scope-v3.json`](../../registry/m1b/m1b-1a-r1-remediation-scope-v3.json)
с exact identity:

| Поле | Значение |
|---|---|
| Schema / generation | `m1b-1a-r1-remediation-scope-v3` / `3` |
| Canonical bytes | `44423` |
| Raw SHA-256 | `1b860ee3ce42ba76ee457d9ceca0a2391e0d6a3216892ca77bf235219a9f4944` |
| Framing domain | `stellaris-m1b-1a-r1-remediation-scope-v3` |
| Framed SHA-256 | `fb3f439cfc67707922ddbae2e94a9deec4544336abf8bdace1d56191bad2b6e1` |

Canonical scope — compact sorted-key ASCII JSON плюс один LF. Framed digest
использует domain, NUL, unsigned 64-bit big-endian length canonical bytes
вместе с LF и сами bytes. Scope self-hash не содержит; exact hashes находятся
в отдельном owner record.

Owner record schema — `m1b-1a-r1-remediation-owner-authorization-v3`;
`8146` canonical bytes, raw SHA-256
`06307a2351a75d19b231a4715f51c0de0f4704d4ca7a523005e221d5194c6fc7`.
Полный normative contract:
[`m1b-1a-r1-remediation-authorization-contract.md`](../specs/m1b-1a-r1-remediation-authorization-contract.md).

## Historical merged baseline

Scope неизменно bind-ит PR #10 как historical merged baseline, а не как
будущий remediation target:

| Field | Exact value |
|---|---|
| Repository / PR | `elenandar/Stellaris-mod-translator` / `10` |
| State / classification | `MERGED` / `OWNER_CONTROLLED_SCOPE_DEVIATION` |
| Branch | `agent/m1b-1a1-inert-candidate-construction` |
| Head | `66f905cf266b9d1c1f56d0d706184387ffedb36e` |
| Merge commit | `3c6ca3146d838b977f24bbc6b8c79dfb271e142b` |
| Ordered parents | `1f10c151c5adac5fbf765af8093c7eddf8cf0429`, `66f905cf266b9d1c1f56d0d706184387ffedb36e` |
| Head / merge tree | `289e2396975c5ef6fe1001a7c5990523edaa06c5` / same |
| Exact merged paths | `11` |
| Candidate roles | `4`, total `94473` bytes |

PR #10 был слит внешним owner-controlled действием вопреки собственному stop
rule. Scope v1 не имела effect, не разрешала merge и не получает retroactive
effect. Scope v2 superseded before effect и также не даёт authority. Candidate
bytes остаются inert и reviewable; candidate source не принят как executable.

Historical proposed manifest остаётся только proposal:

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

После effect future remediation обязана fail closed подтвердить PR #11 merge,
ancestry, exact repository и clean tracked worktree/index. Current checkout
может оставаться на external final PR #11 head либо находиться в другом clean
non-target branch/detached state exact repository; текущий `HEAD` не обязан
равняться merge commit. Preliminary checkout/switch не нужен и запрещён.

После bounded fetch и до branch creation exact имя обязано отсутствовать
одновременно в local `refs/heads`, remote-tracking `refs/remotes/origin`,
advertised remote `refs/heads` и среди всех live GitHub PR (`OPEN`, включая
draft, с любым base) с exact head branch. Любое совпадение fail closed; reuse,
delete и reset запрещены. Затем разрешены:

1. bounded fetch exact repository и read-only effect/ancestry verification;
2. единственный branch transition:
   `git switch -c agent/m1b-1a-r1-postmerge-remediation
   <exact-pr11-merge-commit>`;
3. изменение только `19` future outputs: `18` tracked и один ignored sanitized
   evidence file, после общего pre-write gate `19/19`;
4. создание только `4` exact directories;
5. один ordinary remediation commit и один non-force push этой ветки;
6. создание ровно одного нового draft remediation PR в `main`;
7. update title/body только этого нового draft PR.

Номер future PR заранее неизвестен и bind-ится external GitHub metadata после
создания. Четыре normative AUTH artifacts уже присутствуют в base после merge
PR #11 и становятся immutable inputs; они не являются integration
consequences или remediation outputs.

Exact future scope включает текущие `11` PR #10 paths, новый machine/spec
contract v5, contract-v5 review, versioned inert TCB fixture
`fixtures/m1b/tcb-admission-v5/cases.json`, versioned verifier/test, один R1
remediation review и ignored evidence. Fixture использует non-colliding schema
`m1b-tcb-admission-contract-v5-cases-v1`; historical unversioned fixture со
schema `m1b-tcb-admission-cases-v5` остаётся неизменным.

Lifecycle split exact: `11` existing tracked rows требуют bound PR #11
merge-commit-tree bytes, full mode `100644`, `st_nlink == 1`, no symlink,
hardlink/physical alias/deletion и post-write type/mode/link/containment
verification; `7` new tracked rows обязаны отсутствовать в base tree и
worktree, создаваться exclusive/no-follow и завершаться regular `100644`,
`st_nlink == 1`; ignored `remediation-evidence.json` создаётся только при
отсутствии, exclusive/no-follow, regular `0600`, `st_nlink == 1`, с
обязательным close и никогда не stage-ится. Все pre-write existence/type/mode/
link/identity и применимые parent-containment checks завершаются до первой
repository-content записи; post-write checks выполняются после завершения
соответствующего writer. Collision, existing symlink/hardlink/alias или
`st_nlink > 1` fail closed.

Directory chain exact: `artifacts` (`0755`, parent `.`), `artifacts/m1b`
(`0700`), `artifacts/m1b/m1b-1a-r1` (`0700`), затем независимо
`fixtures/m1b/tcb-admission-v5` (`0755`). Каждый путь real,
create-only-if-absent; wrong type/mode или symlink fail closed без `chmod`,
replacement или deletion.

Любая другая ветка/PR, rebase, force-push, amend, stash/reset/clean, merge,
auto-merge, ready-for-review, close, main mutation, tags/releases/Actions и
другой network запрещены. Повторная публикация после частичного push требует
нового owner decision.

Неопределённый push разрешает только read-only проверку exact advertised remote
ref/SHA; неопределённое создание PR — только read-only проверку ровно одного
live PR с exact head/base. Пока outcome неизвестен, второй push или PR
запрещён. Missing/mismatched SHA, zero/multiple PR, wrong base или сохраняющаяся
неопределённость требуют `NEW_OWNER_DECISION_REQUIRED`.

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

Machine scope bind-ит exact counts:

| Surface | Count |
|---|---:|
| Base inputs | `23` |
| Authorization-stage outputs | `6` |
| Immutable AUTH inputs | `4` |
| Candidate roles | `4` |
| Historical PR #10 paths | `11` |
| Future outputs | `19` (`18` tracked + `1` ignored) |
| Future directories | `4` |
| Blockers | `16` |

23rd input — read-only `.gitignore`, exact `733` bytes, full mode `100644`,
SHA-256
`0f36fee465d056ae9373a2aa702e58740f82c99c0fb25e0f24a326318087a82d`.
Его чтение ограничено проверкой `artifacts/`, `git status`,
`git check-ignore` и доказательством index exclusion; изменение запрещено.

Machine scope разделяет repository content, four exact future directories,
Git/GitHub, host validation, pre-effect activation verification и
candidate/provider runtime authority. Для каждой плоскости всё неуказанное
запрещено. Runtime authority остаётся полностью отрицательной.

Исторические v4 registry/spec/fixture, принятые M1B-1A1-AUTH artifacts и exact
11-path merged baseline PR #10 остаются byte-identical до разрешённой future
remediation. Четыре M1B-1A-R1-AUTH v3 artifacts после merge PR #11 становятся
immutable base inputs. Сохраняются все `16` executable/runtime blockers.

Future remediation всё ещё не разрешает candidate parse, tokenization, lint,
compile, import или execution; новый repository verifier/test также остаётся
inert. Provider/Ollama/model calls, metadata probes, model store, corpus,
prompt/template, mods, Workshop, Stellaris, launcher, playset, translations,
runtime instances, acceptance, admission, M1B-1A2, benchmark, M2, activation и
publishing запрещены.

## Validation boundary

Authorization validation ограничена canonical JSON reproduction,
duplicate-key/type/float/path/order checks, raw/framed SHA-256, exact
PR #10 provenance/tree/path/hash parity, inputs `23/23`, lifecycle rows
`19/19`, directories `4/4`, candidate roles `4/4`, blockers `16/16`, immutable
AUTH inputs `4/4`, exact path/parent closure, fresh-tree reachability,
symlink/hardlink/collision/`st_nlink > 1` fail-closed cases, direct branch
create-and-switch semantics, four-namespace absence, status-only diff review,
Markdown links, `git diff --check`, no `.pyc`/`__pycache__` и
clean-tree/local/upstream/remote/PR parity. Два независимых read-only semantic
review обязаны найти actionable P0–P2 = `0`; иначе publication блокируется и
оба review повторяются. Repository tests намеренно не запускаются.

Historical candidate source проверяется только по Git mode/size/hash и
неизменности exact bytes. Он не передаётся Python
AST/parser/tokenizer/linter/compiler, не импортируется и не исполняется.
Provider/model/private data не читаются.

## Gate

```text
REMEDIATION: READY_FOR_OWNER_REVIEW
PR10: MERGED_OWNER_CONTROLLED_SCOPE_DEVIATION
PR10_CANDIDATE: INERT_NOT_ADMITTED
SCOPE_V1: NEVER_EFFECTIVE
SCOPE_V2: SUPERSEDED_BEFORE_EFFECT
M1B-1A-R1-AUTH-V3: READY_FOR_OWNER_REVIEW
R1_REMEDIATION: NOT_AUTHORIZED_UNTIL_V3_MERGE
NEW_REPOSITORY_CODE_EXECUTION: NOT_AUTHORIZED
PROVIDER_EXECUTION: NOT_STARTED
EXECUTABLE_TCB_ADMISSION: NOT_GRANTED
M1B: NOT_EVALUATED
M1A: BLOCKED
M2: FORBIDDEN
PR11: DRAFT
```

Единственный следующий шаг — owner review этого authorization draft PR с
ordinary two-parent merge только при сохранении exact first parent
`3c6ca3146d838b977f24bbc6b8c79dfb271e142b`. Future remediation branch и PR до
effect запрещены.
