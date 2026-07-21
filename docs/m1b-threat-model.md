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
| Python benchmark process / TCB | exact manifest-bound validator, analysis engine, scope materializer, runner/harness и фактически использованный runtime/import/invocation state | capability — только same-process misuse guard; reflection, monkeypatching, import hooks, debugger/tracing и любой исполняемый в процессе code считаются trusted, а не hostile boundary |

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
| `M1B-T06` | Tuning/holdout overlap, related variants, shared source unit, caller-relabelled rows или statistical pooling contaminates evaluation | High | физически разные roots/manifests, disjoint random UUID sets, local relationship check, holdout unopened до freeze; exact validator-materialized synthetic scopes в agreement/D1–D5/CFA/HGT-derived rows остаются diagnostic-only; production holdout decision helpers требуют отдельный full admission и не принимают caller rows | synthetic overlap: `CORPUS_SPLIT_OVERLAP`; caller split/UUID membership не являются provenance; missing/unknown/mutated scope fail closed, mixed input даёт `STATISTICAL_SPLIT_MIXED`; tuning/raw/synthetic-scope diagnostics не удовлетворяют holdout gate |
| `M1B-T07` | Pipeline подстроен после раскрытия holdout | High | byte-frozen protocol/profile/rubric/analysis manifest до holdout, immutable initial records, audit generation | любое изменение превращает holdout в tuning и требует новой holdout generation |
| `M1B-T08` | Model меняет schema, atom, code или control data | Critical | frozen JSON Schema плюс независимый strict validator; exact expected/observed atom ID, occurrence ID, kind, synthetic/private value, cardinality, multiplicity и position policy; unknown syntax blocked | missing/extra/duplicate/kind/value/position/multiplicity mutation учитывается как failure; approved result с defect — hard gate failure |
| `M1B-T09` | Model-review ошибочно засчитан как human review | High | closed reviewer-role enum, human identity mapping local, две разные human identities для primary-blinded reviewable critical classes, model experiment separate; self-identifying output primary HGT не получает | synthetic contract: `MODEL_REVIEW_NOT_HUMAN`; future live role violations также invalidируют affected category/verdict; self-identifying output остаётся fail-closed secondary-only exception |
| `M1B-T10` | Raw exception, traceback, filename или path раскрывает corpus | Critical | все exceptions перехватываются до CLI boundary; controlled codes/counts only; raw exception logging disabled | неизвестная ошибка становится generic controlled failure; leakage blocks publication |
| `M1B-T11` | Benchmark пишет в source, Workshop, game, launcher или active output | Critical | only explicit ignored benchmark root, protected-root disjointness, read-only source descriptors, no discovery, write allowlist and attempt counters | любой ambiguous path/write attempt: `PROTECTED_PATH_WRITE_ATTEMPT`; немедленный abort |
| `M1B-T12` | Declarative corpus/profile/protocol drift либо executable byte drift скрыт одним bundle hash | High | trusted closed definition registry и synthetic-corpus digest отдельно от non-circular external executable manifest; no cross-generation merge | definition/corpus mismatch invalidates document; до external manifest действует `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN` |
| `M1B-T13` | Reviewer узнаёт candidate, два initial review IDs маскируют одну human identity, orphan HGT adjudication подменяет evidence либо reviewer-specific severity/hard-fail/mandatory outcome сплющивается в self-asserted top-level finding | High | global reviewer exposure, positive mapping generations, exact finding/category/dimension provenance; любые две initial finding reviews имеют distinct human identities; HGT adjudication связывает ровно два существующих conflicting initial IDs того же result/dimension/current mapping, использует ровно одного distinct third human, все HGT rows consumed; randomized presentation и private mapping | external leak сохраняет compromised records и допускает только fresh never-unblinded reviewers/new mapping; duplicate initial identity, orphan/cross-scope/duplicate HGT link, agreeing initials, extra adjudicator, missing outcome, top-level downgrade и unresolved disagreement fail closed; self-identification даёт `BLINDING_FAILED`, primary HGT forbidden, secondary evidence only |
| `M1B-T14` | Source/cluster rows, repeated strata, findings, tuning rows либо candidate selection раздувают `n`/`x` и создают ложную уверенность | High | unit `(candidate,profile,split,dimension_or_gate,stratum,source_generation)`; conservative row collapse; CFA source-generation/split/class any-event; full-admission-owned holdout decision helpers; Bonferroni `1/20 -> 1/60`, tail `1/120`; conjunctive strata; pooled interval forbidden | duplicate/tuning rows не увеличивают holdout denominator/event count; synthetic scope остаётся ineligible; insufficient per-stratum holdout `n`, failed bound, mixed split/scope или marginal-only evidence не получает verdict |
| `M1B-T15` | Timeout, repair, fallback либо duplicate assignment исчезает из denominator | High | unique candidate/sample/profile/generation/lane/stage/index tuple, exact declared coverage, retry `0` с `attempt_index=0` во всех lanes, max one row per lane/stage и max one model call/row, immutable initial attempt, lane-specific exact repair/fallback/terminal equations; `fallback=false` запрещает hidden/model/provider fallback, но не заранее объявленную human-fallback lane с zero model calls | duplicate/missing/extra assignment, phantom cross-lane counter или accounting mismatch invalidates report; terminal failure остаётся denominator |
| `M1B-T16` | Cold/warm latency смешаны либо lifecycle не доказан | Medium | separate lanes, frozen warm-up/repetition policy, residency/lifecycle evidence и separate distributions | unknown lifecycle: `LIFECYCLE_STATE_UNPROVEN`; observation excluded as invalid, count retained |
| `M1B-T17` | Thinking/schema/output-limit capability или token accounting отличается, и post-hoc option даёт одному model преимущество | High | common frozen profile; exact output-limit binding; любое model-specific отличие pre-registered with separate hash/results before tuning | unproven output-limit binding: `OUTPUT_LIMIT_BINDING_UNPROVEN`; другая unregistered profile exception: `PROFILE_POLICY_VIOLATION`; no primary ranking |
| `M1B-T18` | Temporary raw artifacts переживают retention или cleanup | Critical | sealed ignored scratch, predeclared retention deadline, cleanup verification и aggregate deletion record | cleanup/deletion failure остаётся privacy blocker; public evidence не выпускается |
| `M1B-T19` | Победитель/baseline объявлен до полного benchmark | High | equal candidate state; поля winner/baseline/verdict отсутствуют в закрытой M1B-0 schema; completed gates и owner acceptance обязательны | premature winner/baseline/verdict: `PREMATURE_SELECTION`; contract invalid |
| `M1B-T20` | Real content попадает в synthetic fixture | Critical | synthetic-only authoring, prohibited-field allowlist, leakage scan against all observed private roles, full diff review | fixture удаляется из publication; `LEAKAGE_DETECTED`, новая clean generation |
| `M1B-T21` | Synthetic conformance, D1 pass либо review отсутствующего output ошибочно изображает editorial acceptance | Critical | отдельные `technical_conformance`, D2–D5 `human_ground_truth` и `editorial_status`; no-output/`not_applicable` без attempt требуют technical `not_observed`, empty atoms, D1–D5 `not_evaluated`, zero accounting и запрещают findings/reviews/HGT; technical aggregate считает только output-bearing conformant rows; M1B-0 запрещает `editorially_approved` | contradictory no-attempt state или content evidence без output fail closed; missing human evidence, role collision/mutation либо auto-accept invalid; `technical_safe` не означает `editorially_approved` |
| `M1B-T22` | Ollama сохраняет private request/output в logs, history, diagnostics, telemetry или temp storage | Critical | synthetic-only persistence preflight, exact version/config surfaces, retention/cleanup proof до private bytes | unknown sink либо incomplete proof: `PROVIDER_PERSISTENCE_UNPROVEN`; private request запрещён |
| `M1B-T23` | Conversation/context/thinking state переносит content между samples, candidates или splits | Critical | новый stateless request на каждый stage, closed field allowlist, запрет context/history reuse, thinking hidden/discarded by policy | unknown field/state либо continuation reuse останавливает run; affected splits invalid |
| `M1B-T24` | Huge JSON number, fixture expansion/repeated-work, float/non-finite, malformed JSON либо повторная materialization вызывает pre-validation DoS, неоднозначную coercion или накопление недостижимых synthetic scopes | High | `4 MiB` bound на standalone bytes, fixture manifest и каждый materialized document; максимум `256` patches; cumulative accepted compact-serialization work максимум `16 MiB`, полный `4 MiB` reserve до следующего encoder call и reuse final encoding; bounded lexical `parse_int` до integer allocation; float/non-finite reject hooks; strict UTF-8/duplicate-key/closed schema; synthetic registration использует lifetime-bound weak key без value-to-token back-reference, поэтому живой token сохраняет scope, а недостижимые tokens/rows не накапливаются | oversize input/expansion: `INPUT_SIZE_LIMIT`; patch/work budget: `MATERIALIZATION_WORK_LIMIT` до unreserved encoding; oversize integer: `JSON_INTEGER_OUT_OF_RANGE`; float: `JSON_FLOAT_FORBIDDEN`; token не echo-ится, no partial parse/traceback; repeated success/error materialization после release не оставляет registration |
| `M1B-T25` | Complete benchmark заявлен через partial M1B-0 schema | High | document schema v4 допускает только partial synthetic report; future live report требует новую owner-accepted schema/generation | любой `complete_benchmark` получает `PARTIAL_REPORT_CANNOT_BE_COMPLETE`; verdict absent |
| `M1B-T26` | Tokenizer/effective context limit либо silent left/right truncation не совпадают с profile | Critical | external tokenizer/input-limit binding, boundary canary, prompt-eval/overflow/error/post-response checks до private bytes | self-asserted proof invalid; пока checks `not_probed`, `CONTEXT_LIMIT_BINDING_UNPROVEN` блокирует live observation; controlled overflow не получает human labels |
| `M1B-T27` | Validator сам объявляет hash своей реализации и создаёт circular trust | Critical | external owner-accepted manifest без self digest/entry, exact regular-file paths/roles/hashes и domain framing; отдельно admit-ится runtime/import/invocation state | report self-assertion invalid; v1 file manifest сам по себе не связывает interpreter/import state; `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN` до external verifier/record |
| `M1B-T28` | Stable-pair kappa смешивает splits/reviewers, replay-ит logical rows, создаёт synthetic cross-row pairs, принимает orphan adjudication, перевзвешивает sources, включает final adjudicator ratings либо скрывает undefined/applicability disagreement | High | unique `(result_id,dimension)`, exact complete validator-materialized synthetic split scope, two existing same-result/dimension frozen initial IDs, exact disagreement linkage и distinct third-human adjudicator, full HGT consumption, canonical stable pair, equal-source contingency `O_ij=sum_s(count_sij/m_s)` только из actual pairs; live holdout gate требует full admission | duplicate logical row, mixed/mutated scope/pair, orphan/cross-scope/duplicate link, agreeing initials с adjudicator, extra/missing adjudicator, unilateral NA, synthetic scope ineligible, undefined либо kappa `<3/5` fail closed |
| `M1B-T29` | Same-process reflection, monkeypatching, import hook, debugger/tracing либо иной code изменяет capability registry или analysis control flow | Critical | весь исполняемый Python process, runtime, imports, globals/closures, validator, materializer, analysis engine и harness объявлены TCB; token nominally separates types but не является cryptographic/sandbox boundary; hostile-code protection требует отдельной process/authority boundary | M1B-0 не заявляет resistance к hostile same-process code и не добавляет обфускацию; до external TCB admission действует `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN`, а отдельная process isolation остаётся вне scope |

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
6. schema/prompt/profile/rubric/analysis definitions совпадают с owner-accepted
   registry, exact executable bytes — с отдельным external manifest, а runtime,
   import graph и invocation state входят в явно admitted same-process TCB;
7. assignments уникальны, declared coverage exact, initial attempts, repairs,
   fallbacks, timeouts и terminal failures полностью учтены;
8. каждый primary-blinded holdout output, пригодный для content review, имеет две
   stable-pair initial human records по каждой D2–D5; каждая HGT adjudication
   exact-link-ит два conflicting same-result/dimension initial IDs, distinct
   third human и current mapping, а все HGT rows consumed; critical classes
   сохраняют две независимые finding reviews; self-identifying output
   вместо этого имеет D2–D5=`blinding_failed`, zero primary success, запрет
   primary HGT и только optional secondary evidence;
9. high/critical finding, repair/fallback и `BLINDING_FAILED` не прошли
   auto-accept и остались в denominator;
10. holdout-only source-generation per-stratum denominator/numerator, CFA class
    events, Bonferroni family, stable reviewer pairs и robust exact kappa
    совпали с pre-holdout owner decision; tuning diagnostics не вошли ни в один
    decision denominator;
11. raw data не вышла за local private boundary;
12. source/active write-attempt count равен нулю;
13. preflight/postflight generations совпали;
14. tokenizer/effective context limit и silent-truncation boundary доказаны
    external canary evidence;
15. public report прошёл leakage gate после последнего byte change.
16. synthetic scope provenance использовался только для diagnostics; каждый
    production decision scope получен из отдельного full admission после всех
    report/run/owner/executable gates.

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

M1B-0 не доказывает tokenizer/context binding и exact executable identity.
`CONTEXT_LIMIT_BINDING_UNPROVEN` и
`EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN` остаются независимыми live
pre-request blockers; успешный synthetic validator их не снимает. Internal
synthetic-scope capability предотвращает случайное использование caller rows
только при неизменённом trusted Python process. Он не является opaque/closed
security primitive против reflection или monkeypatching. Manifest schema v1
bind-ит declared file bytes, но не доказывает used interpreter, imports и
invocation state; их admission требует будущего control либо отдельной process
boundary.

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
contract, exact synthetic analysis-scope consistency и обнаружение перечисленных
adversarial states. Он не выдаёт full decision admission и не доказывает provider
residency, качество модели, human agreement или безопасность активного artifact.

M1B-0 сохраняет `M1B: NOT_EVALUATED` и protocol under review без
`QUALITY_FEASIBLE` / `QUALITY_NOT_FEASIBLE`. Даже будущий положительный M1B
verdict не разрешает M2,
пока M1A остаётся `BLOCKED`.
