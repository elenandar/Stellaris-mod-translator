# Модель угроз M1B

- Статус: `M1B: protocol under review`; live benchmark не выполнялся
- Assets: raw corpus, holdout secrecy, model identity/residency, protocol bytes,
  human labels и sanitized evidence
- Gate state: `M1A: BLOCKED`; `M2: forbidden`

Модель угроз относится к будущему изолированному local benchmark и текущему
synthetic conformance gate. Она не разрешает Ollama access в M1B-0, чтение
corpus/model store или запись в source/Workshop/game/launcher/active paths.

## Trust boundaries

| Boundary | Разрешение | Fail-closed правило |
|---|---|---|
| Repository/Codex | public docs, code, synthetic fixtures, sanitized aggregates | raw/private/copyrighted content запрещён |
| Local corpus runner | explicit local ignored root и immutable accepted bytes | no discovery, no active/source write |
| Ollama adapter | numeric loopback и exact frozen candidate profile | no redirect/proxy/cloud/pull/fallback |
| Human review | raw content только в local private surface | randomized/blinded; raw findings не экспортируются |
| Evidence exporter | allowlisted aggregate schema | unknown/free-text field или leakage останавливает export |

Loopback сам по себе не доказывает local model residency. Structured output сам
по себе не доказывает schema/atom stability. Human review не доказывает
technical safety, а model-review не является human review.

## Severity

- **Critical** — возможны raw/private leakage, remote processing, запись в
  protected paths, schema/atom mutation, critical false accept, подмена benchmark
  identity либо сохранение raw artifacts после обязательного cleanup.
- **High** — contamination, post-holdout tuning, protocol drift, неполное
  accounting или invalid evidence могут дать ложный feasibility verdict.
- **Medium** — performance/lifecycle evidence неполно или biased, но raw/write и
  acceptance boundaries остаются закрытыми; affected measurement всё равно invalid.

Critical/High threat без доказанного control блокирует affected run. Residual
risk не превращается в assumption; он получает controlled blocker либо явное
owner decision до holdout.

## Threat register

| ID | Threat | Severity | Preventive/detective controls | Failure / residual disposition |
|---|---|---:|---|---|
| `M1B-T01` | Cloud, redirect, DNS или proxy escape выводит raw request за local boundary | Critical | только numeric `127.0.0.1`/`::1`, exact URL, redirects off, proxy discovery off, peer loopback check, no alternate origin, outbound-deny defense in depth | любой redirect/proxy/remote peer даёт `ENDPOINT_POLICY_VIOLATION`; run invalid |
| `M1B-T02` | Tag присутствует, но local residency не доказана | Critical | exact tag/full digest/version/details, отдельное accepted residency proof, pre/post batch checks; loopback/listing не считается достаточным | unknown residency даёт `RESIDENCY_UNPROVEN`; candidate не запускается |
| `M1B-T03` | Tag substitution либо digest drift между identity check и generation | Critical | frozen tag+digest, controlled single-owner session, pre/post каждого batch, запрет model mutation; response identity сверяется с profile | mismatch/ABA suspicion аннулирует batch; недоказуемая binding остаётся blocker |
| `M1B-T04` | Hidden pull, auto-install или fallback загружает другой model/provider | Critical | только preinstalled allowlist, pull/create/copy/remove paths не вызываются, retry `0`, no fallback, outbound-deny control, full postflight inventory check | попытка pull/fallback или новый digest: `MODEL_SELECTION_VIOLATION`, run invalid |
| `M1B-T05` | Raw prompt/output/translation/annotation уходит в Git, Codex, terminal или telemetry | Critical | local-only ignored storage, no stdout/stderr raw values, opaque IDs, allowlist exporter, corpus-aware leakage scan и staged-diff review | `LEAKAGE_DETECTED`; публикация и run останавливаются без echo совпадения |
| `M1B-T06` | Tuning/holdout overlap, related variants или shared source unit contaminates evaluation | High | физически разные roots/manifests, disjoint random UUID sets, local relationship check, holdout unopened до freeze | overlap/uncertain lineage: `CORPUS_SPLIT_CONTAMINATION`; новый split |
| `M1B-T07` | Pipeline подстроен после раскрытия holdout | High | byte-frozen protocol/profile/rubric/analysis manifest до holdout, immutable initial records, audit generation | любое изменение превращает holdout в tuning и требует новой holdout generation |
| `M1B-T08` | Model меняет schema, atom, code или control data | Critical | frozen JSON Schema плюс независимый strict validator; exact atom IDs/types/values/cardinality; unknown syntax blocked | invalid attempt учитывается как failure; accepted result с defect — hard gate failure |
| `M1B-T09` | Model-review ошибочно засчитан как human review | High | closed reviewer-role enum, human identity mapping local, две разные human identities для critical classes, model experiment separate | `REVIEW_ROLE_VIOLATION`; affected category/verdict invalid |
| `M1B-T10` | Raw exception, traceback, filename или path раскрывает corpus | Critical | все exceptions перехватываются до CLI boundary; controlled codes/counts only; raw exception logging disabled | неизвестная ошибка становится generic controlled failure; leakage blocks publication |
| `M1B-T11` | Benchmark пишет в source, Workshop, game, launcher или active output | Critical | only explicit ignored benchmark root, protected-root disjointness, read-only source descriptors, no discovery, write allowlist and attempt counters | любой ambiguous path/write attempt: `PROTECTED_PATH_WRITE_ATTEMPT`; немедленный abort |
| `M1B-T12` | Corpus/profile/protocol bytes drift, но results объединены | High | canonical generations/hashes с framing из benchmark contract, batch pre/post checks, no cross-generation merge, public protocol hashes and private corpus immutability check | mismatch: `GENERATION_MISMATCH`; весь affected batch invalid |
| `M1B-T13` | Reviewer узнаёт candidate и bias-ит оценку, включая self-identification в output | High | randomized presentation, blinded labels, private mapping, model metadata/latency/thinking hidden; output не редактируется | external leak инвалидирует records и требует fresh never-unblinded reviewers/new mapping; self-identifying output получает `BLINDING_FAILED` и не входит в primary blinded score |
| `M1B-T14` | Среднее скрывает critical defect или малую выборку | High | independent dimensions/severity, hard-fail precedence, exact sample size and preselected confidence bounds, per-stratum report | missing `n`/bound или pooled-only report не получает verdict |
| `M1B-T15` | Timeout, repair или fallback исчезает из denominator | High | retry `0`, immutable initial attempt, repair/fallback/terminal rejection counts, no winner substitution | accounting mismatch: `ACCOUNTING_MISMATCH`; report invalid |
| `M1B-T16` | Cold/warm latency смешаны либо lifecycle не доказан | Medium | separate lanes, frozen warm-up/repetition policy, residency/lifecycle evidence и separate distributions | unknown lifecycle: `LIFECYCLE_STATE_UNPROVEN`; observation excluded as invalid, count retained |
| `M1B-T17` | Thinking/schema/output-limit capability или token accounting отличается, и post-hoc option даёт одному model преимущество | High | common frozen profile; exact output-limit binding; любое model-specific отличие pre-registered with separate hash/results before tuning | unproven limit либо unregistered exception: `PROFILE_POLICY_VIOLATION`; no primary ranking |
| `M1B-T18` | Temporary raw artifacts переживают retention или cleanup | Critical | sealed ignored scratch, predeclared retention deadline, cleanup verification и aggregate deletion record | cleanup/deletion failure остаётся privacy blocker; public evidence не выпускается |
| `M1B-T19` | Победитель/baseline объявлен до полного benchmark | High | equal candidate state; поля winner/baseline/verdict отсутствуют в закрытой M1B-0 schema; completed gates и owner acceptance обязательны | premature winner/baseline: `PREMATURE_VERDICT`; contract invalid |
| `M1B-T20` | Real content попадает в synthetic fixture | Critical | synthetic-only authoring, prohibited-field allowlist, leakage scan against all observed private roles, full diff review | fixture удаляется из publication; `LEAKAGE_DETECTED`, новая clean generation |

## Control invariants

Будущий live runner обязан доказать одновременно:

1. endpoint, peer, redirect и proxy policy совпадают с frozen profile;
2. candidate tag, full digest, version и residency доказаны до load;
3. corpus split disjoint и holdout не раскрывался до freeze;
4. schema/prompt/profile/rubric bytes совпадают с manifest;
5. initial attempts, repairs, fallbacks, timeouts и rejections полностью учтены;
6. critical classes имеют две независимые human reviews и adjudication;
7. raw data не вышла за local private boundary;
8. source/active write-attempt count равен нулю;
9. preflight/postflight generations совпали;
10. public report прошёл leakage gate после последнего byte change.

Отсутствие evidence для любого invariant — blocker, а не нулевое наблюдение.

## Residual risks и stop conditions

Provider metadata endpoints документируют tag/digest/details, но не дают сами по
себе project-level guarantee residency или atomic tag-to-digest pinning.
Будущий live protocol обязан доказать эти свойства принятым control; иначе
`RESIDENCY_UNPROVEN` или model-identity blocker сохраняется.

Leakage scanner не является математическим доказательством отсутствия каждого
короткого substring. Поэтому publishable allowlist, local corpus fingerprints и
human staged-diff review обязательны вместе. Неожиданный raw/free-text field
останавливает export.

Benchmark немедленно останавливается, если требуется real corpus до принятия
privacy controls, обращение к cloud/remote, model pull, ослабление split/freeze,
чтение model store, запись в protected path либо вывод raw data. Минимальный
следующий шаг в таком случае — owner review конкретного blocker, не обход.

## Gate boundary

Synthetic conformance validator подтверждает только закрытую форму public
contract и обнаружение перечисленных adversarial states. Он не доказывает
provider residency, качество модели, human agreement или безопасность активного
artifact.

M1B-0 сохраняет `M1B: protocol under review` без `QUALITY_FEASIBLE` /
`QUALITY_NOT_FEASIBLE`. Даже будущий положительный M1B verdict не разрешает M2,
пока M1A остаётся `BLOCKED`.
