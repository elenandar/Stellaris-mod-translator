# Модель угроз M1B

- Статус: `M1B: NOT_EVALUATED`; protocol under review, live benchmark не
  выполнялся
- Assets: raw corpus, holdout secrecy, model identity/residency, protocol bytes,
  human labels и sanitized evidence
- Gate state: `M1A: BLOCKED`; `M2: FORBIDDEN`

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
| `M1B-T01` | Cloud, redirect, DNS или proxy escape выводит raw request за local boundary | Critical | byte-exact ASCII `http://127.0.0.1:<1..65535>/api` либо `http://[::1]:<1..65535>/api`; pre-normalization control/whitespace rejection; redirects/proxy off; peer loopback check; no alternate origin | noncanonical URL даёт `ENDPOINT_NOT_NUMERIC_LOOPBACK`; redirect/proxy/remote peer также fail closed; run invalid |
| `M1B-T02` | Tag присутствует, но local residency не доказана | Critical | exact tag/full digest/version/details, отдельное accepted residency proof, pre/post batch checks; loopback/listing не считается достаточным | unknown residency даёт `RESIDENCY_UNPROVEN`; candidate не запускается |
| `M1B-T03` | Tag substitution либо digest drift между identity check и generation | Critical | frozen tag+digest, controlled single-owner session, pre/post каждого batch, запрет model mutation; response identity сверяется с profile | mismatch/ABA suspicion аннулирует batch; недоказуемая binding остаётся blocker |
| `M1B-T04` | Hidden pull, auto-install или fallback загружает другой model/provider | Critical | только preinstalled allowlist, pull/create/copy/remove paths не вызываются, retry `0`, no fallback, outbound-deny control, full postflight inventory check | попытка pull/fallback или новый digest: `MODEL_SELECTION_VIOLATION`, run invalid |
| `M1B-T05` | Raw prompt/output/translation/annotation уходит в Git, Codex, terminal или telemetry | Critical | local-only ignored storage, no stdout/stderr raw values, opaque IDs, allowlist exporter, corpus-aware leakage scan и staged-diff review | `LEAKAGE_DETECTED`; публикация и run останавливаются без echo совпадения |
| `M1B-T06` | Tuning/holdout overlap, related variants или shared source unit contaminates evaluation | High | физически разные roots/manifests, disjoint random UUID sets, local relationship check, holdout unopened до freeze | synthetic overlap: `CORPUS_SPLIT_OVERLAP`; uncertain live lineage требует новый split |
| `M1B-T07` | Pipeline подстроен после раскрытия holdout | High | byte-frozen protocol/profile/rubric/analysis manifest до holdout, immutable initial records, audit generation | любое изменение превращает holdout в tuning и требует новой holdout generation |
| `M1B-T08` | Model меняет schema, atom, code или control data | Critical | frozen JSON Schema плюс независимый strict validator; exact expected/observed atom ID, occurrence ID, kind, synthetic/private value, cardinality, multiplicity и position policy; unknown syntax blocked | missing/extra/duplicate/kind/value/position/multiplicity mutation учитывается как failure; approved result с defect — hard gate failure |
| `M1B-T09` | Model-review ошибочно засчитан как human review | High | closed reviewer-role enum, human identity mapping local, две разные human identities для critical classes, model experiment separate | synthetic contract: `MODEL_REVIEW_NOT_HUMAN`; future live role violations также invalidируют affected category/verdict |
| `M1B-T10` | Raw exception, traceback, filename или path раскрывает corpus | Critical | все exceptions перехватываются до CLI boundary; controlled codes/counts only; raw exception logging disabled | неизвестная ошибка становится generic controlled failure; leakage blocks publication |
| `M1B-T11` | Benchmark пишет в source, Workshop, game, launcher или active output | Critical | only explicit ignored benchmark root, protected-root disjointness, read-only source descriptors, no discovery, write allowlist and attempt counters | любой ambiguous path/write attempt: `PROTECTED_PATH_WRITE_ATTEMPT`; немедленный abort |
| `M1B-T12` | Corpus/profile/protocol bytes drift, но results объединены | High | trusted closed freeze registry поверх canonical framing; отдельный domain-separated digest exact public synthetic corpus в `corpus_policy`; accepted/proposed state, exact runtime binding, batch pre/post checks, no cross-generation merge; private corpus digest остаётся local-only immutability check | coherent synthetic expected/observed drift даёт `CORPUS_DEFINITION_MISMATCH`; definition mismatch codes либо private generation drift также инвалидируют affected batch |
| `M1B-T13` | Reviewer узнаёт candidate и bias-ит оценку, включая self-identification в output | High | randomized presentation, blinded labels, private mapping, model metadata/latency/thinking hidden; output не редактируется | external leak инвалидирует records и требует fresh never-unblinded reviewers/new mapping; self-identifying output получает `BLINDING_FAILED`, остаётся denominator failure; unblinded review secondary only |
| `M1B-T14` | Среднее, correlated rows либо малая выборка создают ложную уверенность | High | independent source-unit clusters, max one Bernoulli contribution/cluster/gate, closed strata/allocation, exact applicable `n`, preselected confidence bounds | insufficient `n`/bound, row-level pseudoreplication или pooled-only report не получает verdict; `OWNER_DECISION_REQUIRED` до принятия numbers |
| `M1B-T15` | Timeout, repair, fallback либо duplicate assignment исчезает из denominator | High | unique candidate/sample/profile/generation/lane/stage/index tuple, exact declared coverage, retry `0`, max one model call/row, immutable initial attempt, lane-specific exact repair/fallback/terminal equations; fallback rows запрещены при `fallback=false` | duplicate/missing/extra assignment, phantom cross-lane counter или accounting mismatch invalidates report; terminal failure остаётся denominator |
| `M1B-T16` | Cold/warm latency смешаны либо lifecycle не доказан | Medium | separate lanes, frozen warm-up/repetition policy, residency/lifecycle evidence и separate distributions | unknown lifecycle: `LIFECYCLE_STATE_UNPROVEN`; observation excluded as invalid, count retained |
| `M1B-T17` | Thinking/schema/output-limit capability или token accounting отличается, и post-hoc option даёт одному model преимущество | High | common frozen profile; exact output-limit binding; любое model-specific отличие pre-registered with separate hash/results before tuning | unproven output-limit binding: `OUTPUT_LIMIT_BINDING_UNPROVEN`; другая unregistered profile exception: `PROFILE_POLICY_VIOLATION`; no primary ranking |
| `M1B-T18` | Temporary raw artifacts переживают retention или cleanup | Critical | sealed ignored scratch, predeclared retention deadline, cleanup verification и aggregate deletion record | cleanup/deletion failure остаётся privacy blocker; public evidence не выпускается |
| `M1B-T19` | Победитель/baseline объявлен до полного benchmark | High | equal candidate state; поля winner/baseline/verdict отсутствуют в закрытой M1B-0 schema; completed gates и owner acceptance обязательны | premature winner/baseline/verdict: `PREMATURE_SELECTION`; contract invalid |
| `M1B-T20` | Real content попадает в synthetic fixture | Critical | synthetic-only authoring, prohibited-field allowlist, leakage scan against all observed private roles, full diff review | fixture удаляется из publication; `LEAKAGE_DETECTED`, новая clean generation |
| `M1B-T21` | Synthetic conformance либо D1 pass ошибочно изображает editorial acceptance | Critical | отдельные `technical_conformance`, D2–D5 `human_ground_truth` и `editorial_status`; no-output controlled failure требует D1–D5 `not_evaluated` и запрещает ground truth; M1B-0 запрещает `editorially_approved`; high/critical и mandatory-human gates | human quality без output, missing human evidence, role collision/mutation либо auto-accept даёт contract failure; `technical_safe` не означает `editorially_approved` |
| `M1B-T22` | Ollama сохраняет private request/output в logs, history, diagnostics, telemetry или temp storage | Critical | synthetic-only persistence preflight, exact version/config surfaces, retention/cleanup proof до private bytes | unknown sink либо incomplete proof: `PROVIDER_PERSISTENCE_UNPROVEN`; private request запрещён |
| `M1B-T23` | Conversation/context/thinking state переносит content между samples, candidates или splits | Critical | новый stateless request на каждый stage, closed field allowlist, запрет context/history reuse, thinking hidden/discarded by policy | unknown field/state либо continuation reuse останавливает run; affected splits invalid |
| `M1B-T24` | Huge JSON number, float/non-finite либо malformed JSON вызывает pre-validation DoS или неоднозначную coercion | High | bounded input, bounded lexical `parse_int` до integer allocation, float/non-finite reject hooks, strict UTF-8/duplicate-key/closed schema | oversize integer: `JSON_INTEGER_OUT_OF_RANGE`; float: `JSON_FLOAT_FORBIDDEN`; token не echo-ится, no partial parse/traceback |
| `M1B-T25` | Complete benchmark заявлен при partial, missing либо asymmetric coverage | High | explicit partial/complete state, exact assignment cross-product, candidate/profile/stratum row-derived totals | candidate без result, incomplete cross-product, extra row или mixed generation invalidates report; verdict absent |

## Control invariants

Будущий live runner обязан доказать одновременно:

1. endpoint byte-canonical, peer loopback, redirect/proxy policy совпадают с
   frozen profile;
2. candidate tag, full digest, version и residency доказаны до load;
3. provider logging/history/diagnostics/telemetry/temp retention доказаны либо
   run остановлен с `PROVIDER_PERSISTENCE_UNPROVEN` до private request;
4. каждый request stateless, имеет closed fields и не наследует
   conversation/context/continuation/thinking state;
5. corpus split disjoint, related clusters не разделены и holdout не раскрывался
   до freeze;
6. schema/prompt/profile/rubric exact bytes совпадают с trusted freeze registry,
   а его state owner-accepted;
7. assignments уникальны, declared coverage exact, initial attempts, repairs,
   fallbacks, timeouts и terminal failures полностью учтены;
8. каждый holdout output имеет D2–D5 human ground truth; critical classes имеют
   две независимые initial human reviews и adjudication;
9. high/critical finding, repair/fallback и `BLINDING_FAILED` не прошли
   auto-accept и остались в denominator;
10. applicable cluster-level `n`, strata allocation, stable reviewer pairs и
    confidence methods совпали с pre-holdout owner decision;
11. raw data не вышла за local private boundary;
12. source/active write-attempt count равен нулю;
13. preflight/postflight generations совпали;
14. public report прошёл leakage gate после последнего byte change.

Отсутствие evidence для любого invariant — blocker, а не нулевое наблюдение.

## Residual risks и stop conditions

Provider metadata endpoints документируют tag/digest/details, но не дают сами по
себе project-level guarantee residency или atomic tag-to-digest pinning.
Будущий live protocol обязан доказать эти свойства принятым control; иначе
`RESIDENCY_UNPROVEN` или model-identity blocker сохраняется.

Provider metadata также не доказывает отсутствие persistence. Пока synthetic
canary preflight не охватил logging, history, crash/diagnostic, telemetry,
temporary storage, retention и cleanup surfaces, действует независимый blocker
`PROVIDER_PERSISTENCE_UNPROVEN`.

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

M1B-0 сохраняет `M1B: NOT_EVALUATED` и protocol under review без
`QUALITY_FEASIBLE` / `QUALITY_NOT_FEASIBLE`. Даже будущий положительный M1B
verdict не разрешает M2,
пока M1A остаётся `BLOCKED`.
