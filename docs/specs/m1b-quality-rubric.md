# Независимая quality rubric M1B

- Статус: `M1B: NOT_EVALUATED`; proposal для owner review, human scoring и
  holdout ещё не выполнялись
- Версия proposal: `m1b-quality-rubric-v1`; definition state: `proposed`
- Quality verdict: отсутствует
- Gate state: `M1A: BLOCKED`; `M2: FORBIDDEN`

Rubric фиксируется до раскрытия holdout и оценивает technical integrity,
смысл, терминологию/лор, литературность, контекст/голос независимо. Среднее или
общий score не может скрыть critical defect. `technical_safe` не означает
`editorially_approved`; последнее решение принадлежит только человеку.

Все числовые thresholds и confidence parameters в разделе
«Предложенные hard gates» являются **предложенными и ожидают явного owner
acceptance до holdout**. Они не являются уже принятым project policy.

Конкретные M1B-0 field names/enums проверяются executable schema; их canonical
описание для fixture находится в `fixtures/m1b/README.md`. Эта rubric не
расширяет allowlist и не разрешает более мягкую трактовку поля.

## Единица оценки и statistical independence

Row-level единица — один frozen holdout sample и один candidate/profile result.
Она имеет случайный opaque UUIDv4, primary stratum из закрытого enum, five
independent dimension records и disposition. Findings не содержат raw excerpt;
локальный reviewer видит raw text в private surface, а repository получает
только codes и aggregates.

Статистическая Bernoulli unit — не строка, а заранее определённый independent
`source_unit_cluster`: одно событие/chain, один dialogue context block, один UI
family либо другая минимальная source-unit group, варианты которой имеют общий
контекст или происхождение. Все related lines, paraphrases и variants получают
один cluster ID, остаются в одном split и не считаются независимыми.

Для защиты от доминирования одного мода все clusters одного
`source_mod_generation` внутри одного primary stratum объединяются в одну
statistical unit; один mod/source даёт максимум одну Bernoulli unit на
candidate/profile/gate/stratum. Один mod может участвовать в нескольких strata,
но не создавать несколько `n` внутри одного stratum. Неясная lineage объединяет
units conservative либо блокирует split.

Maximum contribution одного cluster к любому candidate/profile/gate/primary
stratum равен одному Bernoulli observation. Если cluster содержит несколько
rows, для D2–D5 берётся conservative cluster outcome: success только если все
applicable rows успешны; любой failure делает cluster failure. Для ordinal
distribution публикуется худший applicable score cluster. Cluster может иметь
ровно один primary stratum; secondary risk labels не создают новый `n`.

Повторные attempts не создают дополнительные samples или clusters. Initial,
repair и fallback histories связываются с одной assignment и считаются отдельно.
Для critical false-accept statistics один cluster является одним Bernoulli
trial: если в любой его row есть adjudicated critical false accept, весь cluster
считается event. Findings, rows, variants и reviewers нельзя использовать для
искусственного увеличения `n`.

## Независимые dimensions

### D1 — Schema и typed-atom stability

Машинный hard gate, не субъективная языковая оценка:

- exact schema version и allowlisted fields/types;
- каждый expected atom occurrence присутствует ровно в требуемой cardinality;
- atom ID, occurrence ID, type, immutable value и разрешённая position policy
  сохранены;
- нет missing, extra, duplicate, mutated или unbound atom;
- code/key/escape/control structure не появляется в human span;
- unknown syntax не угадывается.

Любой defect D1 делает attempt schema/atom-invalid. Такой result не может быть
`editorially_approved` или считаться human-quality success; repair и terminal fallback
учитываются явно. M1B проверяет benchmark contract, но не объявляет будущий M2
renderer доказанным.

Synthetic D1 representation хранит две независимые закрытые последовательности:
`expected_atoms` и `observed_atoms`. Каждая occurrence содержит:

- opaque `atom_id` и отдельный globally unique `occurrence_id`;
- closed atom `kind`;
- exact `synthetic_value`, написанный специально для fixture и совпадающий с
  ASCII `SYNTHETIC_[A-Z0-9_]+`;
- zero-based `occurrence_index`, задающий identity/cardinality;
- единственную M1B-0 policy `position_policy=exact_utf8_byte_span`;
- half-open UTF-8 byte range `position_start < position_end`, длина которого
  равна exact UTF-8 byte length `synthetic_value`;
- provenance `synthetic`.

Сравнение выполняется по всему tuple, а не только по ID/kind. Один occurrence ID
не может встречаться дважды; cardinality logical atom определяется exact set
уникальных `(atom_id, occurrence_id, occurrence_index)`. Изменение value, kind,
occurrence index/cardinality, start/end position, duplicate occurrence, missing
или extra occurrence получает отдельный D1 failure. Validator не выводит новый
position policy из observed output; expected spans не пересекаются.

Эти literals разрешены только для очевидно synthetic fixture. В live/private
validator exact value и position остаются локальными; publishable report не
содержит literal, position, row-level atom IDs или content-derived hashes, а
только controlled codes и aggregate counts.

### D2 — Точность смысла

Human reviewers независимо оценивают сохранение утверждений, участников,
отношений, причинности, условий, модальности, polarity, чисел, единиц,
comparatives, времён и intended gameplay effect. Meaning inversion, потеря или
добавление negation и числовая ошибка являются hard-fail defects независимо от
гладкости русского текста.

### D3 — Терминология и соответствие лору

Отдельно проверяются approved glossary choice, entity/faction/title identity,
последовательность термина, register мира и отсутствие выдуманного lore.
Формально возможный перевод, который меняет established entity или механическое
значение термина, не получает положительный D3 из-за хорошего D4.

### D4 — Литературность русского текста

Проверяются естественность, грамматика, синтаксис, ритм, idiomatic phrasing,
повторы, канцелярит, кальки и редакционная цельность. Correct schema и буквальная
точность смысла не компенсируют неестественный или непригодный для публикации
русский текст.

### D5 — Контекст, голос и стиль

Проверяются speaker/addressee, gender/case, register, tone, humor/wordplay,
cross-unit context, consistency персонажа и жанровая функция строки. Если
доступного контекста недостаточно, reviewer ставит mandatory-human finding, а не
угадывает.

## Closed finding-to-dimension mapping

Finding category не является свободным text и допускается только в указанной
dimension. Несовпадение category/dimension делает record invalid до score:

| Category | Допустимая dimension |
|---|---|
| `schema_violation`, `atom_missing`, `atom_extra`, `atom_duplicate` | D1 `schema_atom_stability` |
| `atom_kind_mutation`, `atom_value_mutation`, `atom_position_mutation`, `atom_multiplicity_mutation` | D1 `schema_atom_stability` |
| `meaning_inversion`, `negation_error`, `number_error` | D2 `meaning_accuracy` |
| `terminology_error`, `lore_error` | D3 `terminology_lore` |
| `literary_error` | D4 `literary_russian` |
| `context_voice_style_error` | D5 `context_voice_style` |
| `critical_false_accept` | закрыто разрешён в D1–D5 и обязан указывать dimension underlying adjudicated defect |

Новый category либо расширение allowed dimensions требует новой rubric version
и freeze до holdout. `critical_false_accept` остаётся derived metric по
underlying adjudicated defect/editorial disposition даже при наличии contract
finding row; aggregate flag не заменяет dimension-specific evidence.

## Ordinal anchors

D2–D5 получают отдельный ordinal score; усреднение dimensions запрещено:

| Score | Anchor |
|---:|---|
| `4` | принято без содержательного edit в этой dimension |
| `3` | приемлемо; только minor polish, не меняющий смысл/identity/voice |
| `2` | нужен существенный human edit, но исходное намерение восстанавливаемо |
| `1` | непригодно; major rewrite или высокий риск неправильного понимания |
| `0` | critical/hard-fail defect либо оценка невозможна безопасно |

`not_applicable` является отдельным enum и не превращается в zero или success.
Причина applicability фиксируется до aggregation. Missing dimension record
делает sample invalid, а не исключается из denominator.

Executable `dimension_records.status` использует закрытый enum
`synthetic_conformant`, `synthetic_nonconformant`, `human_pass`, `human_fail`,
`not_applicable`, `not_evaluated`. В partial M1B-0 D1 может показывать только
synthetic conformance, а D2–D5 остаются `not_evaluated`; это не human evidence.
Для любой row D2–D5 status `human_pass`, `human_fail` либо `not_applicable`
обязан быть выведен из matching `human_ground_truth`; при отсутствии записи
допустим только `not_evaluated`. Self-asserted human status отклоняется как
`MANDATORY_HUMAN_EVIDENCE_MISSING` независимо от `editorial_status`.
В complete holdout каждая D2–D5 имеет `human_pass`, `human_fail` либо
human-confirmed `not_applicable` и соответствующую `human_ground_truth`.

No-output row является отдельным fail-closed case: executable сочетание
`technical_conformance=not_observed` и `terminal_status=controlled_failure`
требует пустые `observed_atoms` и `not_evaluated` во всех D1–D5. D2–D5 нельзя
оценивать по отсутствующему output, и любая `human_ground_truth` для такой row
отклоняется как `HUMAN_GROUND_TRUTH_WITHOUT_OUTPUT`. Controlled failure остаётся
в denominator с zero human-quality success; `not_evaluated` здесь не означает
missing review успешного output.

## Severity taxonomy

| Severity | Определение | Disposition |
|---|---|---|
| `critical` | inversion/negation/number error; schema/atom mutation; ложный gameplay effect; подмена entity; утечка raw data; принятие неизвестного смысла | hard fail, block; human review не превращает attempt в pass |
| `high` | крупная omission/addition, неверный lore/mechanics term, сломанный voice/context или текст, требующий major rewrite | mandatory human review или fallback; auto-accept запрещён |
| `medium` | заметная локальная неточность/неестественность/непоследовательность без critical meaning change | edit/review по category policy |
| `low` | polish defect без изменения смысла, identity или обязательного style | может быть принят человеком |
| `none` | defect не найден в этой dimension | не является доказательством других dimensions |

Severity определяется максимальным impact, а не числом minor findings.
Несколько low/medium findings могут быть повышены при систематическом pattern;
правило escalation фиксируется на tuning и не меняется после holdout.

## Hard-fail defects и critical false accept

Hard-fail defect включает как минимум:

- invalid schema, missing/extra/mutated atom или изменение code/control bytes;
- meaning inversion, добавленную/утраченную negation или modality;
- неверное число, знак, единицу, comparator, duration или condition;
- перепутанного actor/target/cause/effect;
- подмену lore entity либо уверенно выдуманный fact;
- output, который содержит raw prompt/instruction leakage;
- попытку принять unknown/ambiguous context как однозначный.

`critical model defect` означает наличие такого defect в initial output.
`critical false accept` означает, что frozen pipeline присвоил result
editorial/operational approval, не заблокировав adjudicated critical defect и не
направив его в обязательный human gate. Это разные metrics: безопасно пойманный critical model
defect не является false accept, но остаётся model-quality failure и входит в
repair/fallback rate.

Любой `editorially_approved` result с critical human finding является critical false accept и
hard gate failure. Average score, repair success, model-review approval или
хорошие результаты других samples не могут его компенсировать.

## Human review protocol

Presentation randomized и blinded по
[benchmark contract](m1b-benchmark-contract.md). Reviewer не видит model/profile,
другие оценки и machine/model-review disposition.

Для каждой заранее определённой critical-risk category обязательны две независимые
initial разметки разными human reviewers. Один reviewer под двумя ID недопустим.
Model reviewer, automated checker и автор candidate output не удовлетворяют
human count.

Каждый holdout output получает human ground truth для каждой D2–D5: ordinal
score либо human-confirmed `not_applicable` с frozen reason. Это требование
действует и для class, который будущая production policy предлагает как
auto-eligible. `not_evaluated`, missing record или только model-review evidence
не допускает human-quality или editorial/operational acceptance.

Слово output здесь существенно: controlled no-output failure не получает
D2–D5 labels или `human_ground_truth` и не исключается из denominator. Его нельзя
превратить в quality success искусственной записью `not_applicable`.

Executable `human_ground_truth` row содержит ровно `applicability_reason`,
`dimension`, `ground_truth_id`, `result_id`, `review_stage`, `reviewer_id`,
`reviewer_role`, `status`. Role/stage обязаны быть
`human_reviewer`/`initial`; status — `human_pass`, `human_fail` либо
`not_applicable`. Последний требует exact reason `frozen_not_applicable`, для
остальных reason равен `null`.

M1B-0 v2 проверяет только synthetic shape этого gate и не содержит public
ordinal-score/distribution fields. Поэтому его `complete_benchmark` shape не
может сам доказать proposed quality/statistical gates и при текущем proposed
registry остаётся заблокирован `OWNER_DECISION_REQUIRED`. До holdout отдельная
новая owner-accepted report/schema definition обязана связать private ordinal
records с publishable aggregates и confidence calculations; M1B-0 statuses не
подменяют это evidence.

Один reviewer ID имеет одну immutable role во всём document. Reviewer ID не
может совпадать с candidate, sample, source cluster, atom/occurrence, result,
finding, review либо другим opaque ID. Private identity map проверяет, что две
critical initial reviews сделаны разными людьми, а не только разными UUID.

Disagreement включает разные severity, hard-fail flag, dimension score,
applicability либо mandatory-review disposition. До aggregation:

1. initial records замораживаются и не переписываются;
2. disagreement получает отдельный controlled code;
3. третий независимый human adjudicator видит оба finding records, но не model
   identity;
4. adjudication сохраняется рядом с обеими исходными оценками;
5. unresolved disagreement блокирует verdict для category.

Калибровка reviewer-ов выполняется только на tuning. Изменение instructions или
anchors после holdout invalidates rubric generation и требует нового holdout.

Для публикуемого Cohen kappa каждый primary stratum имеет заранее назначенную
стабильную пару reviewers, одинаковую для всех трёх candidates/profiles и всего
double-reviewed subset этого stratum. Kappa считается отдельно для каждой exact
pair и dimension; значения разных либо меняющихся pairs не pooling-уются.
Missing record делает run invalid. Если оба reviewer-а ставят
`not_applicable`, record входит в отдельный applicability-agreement count, но не
в ordinal kappa; односторонний `not_applicable` является disagreement и проходит
adjudication. Proposal minimum для публикуемого pair/dimension kappa — `36`
both-applicable independent clusters; меньшее `n` даёт insufficient agreement
evidence. Невозможность обеспечить stable pair, minimum `n` или выбранный метод
до holdout даёт `OWNER_DECISION_REQUIRED`, а не приблизительный agreement score.

Если mapping/metadata раскрыли candidate reviewer-у, affected review records
замораживаются как compromised и заменяются только reviews новых людей, никогда
не видевших identity. Self-identifying output получает `BLINDING_FAILED`,
остаётся в assigned denominator и считается failure для каждой applicable
D2–D5. Unblinded review допустим только как secondary evidence и не восстанавливает
primary success.

## Risk и operational classes

Классы образуют отдельную closed axis и не заменяют primary corpus stratum:

- `critical_risk` — number/sign/comparator/duration, negation/modality,
  condition/cause/effect, actor/target identity, lore entity/title, unknown
  syntax либо typed-atom/control mutation risk; требует две разные initial human
  reviews и не допускает auto-accept;
- `mandatory_human` — все narrative, dialogue, humor/wordplay, ambiguous
  gender/case, unresolved lore/terminology/context classes, любой critical-risk,
  disagreement, repair/fallback и любой `high`/`critical` finding;
- `auto_eligible_candidate` — только заранее перечисленный до holdout UI либо
  mechanics class без critical-risk/ambiguity/repair/fallback; это лишь
  benchmark label, не разрешение production auto-accept. Даже он получает human
  ground truth в holdout.

В текущей executable synthetic taxonomy ограничение уже closed: risk class
`auto_eligible_candidate` допустим только при primary stratum `ui` или
`mechanics`. Его сочетание с `narrative`, `dialogue`, `humor_wordplay`,
`gender_case`, `lore` либо `typed_atoms` отклоняется
`RISK_CLASS_STRATUM_MISMATCH`. Это conformance invariant M1B-0, а не принятое
решение о будущей production auto-eligibility.

Неперечисленная комбинация получает `mandatory_human`. Exact class rules и
auto-eligible list остаются proposal до owner acceptance и freeze. Независимо от
model score обязательный human gate получают:

- narrative/dialogue, humor/wordplay и character voice;
- lore entity/title либо термин без accepted glossary decision;
- неоднозначные gender/case, speaker/addressee или cross-unit references;
- mechanics text с number, negation, modality, condition, duration или effect;
- unknown/insufficient context и любой reviewer disagreement;
- любой `high`/`critical` finding;
- output после repair, retry, fallback или schema coercion;
- class, для которого holdout threshold/coverage не принят владельцем.

Schema/atom-invalid и unknown-syntax attempts блокируются; human review не
разрешает считать их technical pass. Owner может расширить список до holdout, но
не сузить его после просмотра результатов без новой protocol generation.

`high` и `critical` findings никогда не проходят auto-accept, в том числе после
repair/fallback. `technical_safe` подтверждает только D1 и не означает
`editorially_approved`. Последнее назначает только human reviewer после полной
applicable D2–D5 evaluation и обязательных gates.

## Предложенные hard gates

Ниже — единый pre-holdout proposal. **Каждое число и сам statistical method
ожидают owner acceptance; до этого M1B benchmark не получает verdict.**

### Closed strata и coverage proposal

Primary stratum принимает ровно одно из восьми значений: `ui`, `mechanics`,
`narrative`, `dialogue`, `humor_wordplay`, `gender_case`, `lore`,
`typed_atoms`. Ни один catch-all `other` не допускается; новый stratum требует
новой corpus/rubric generation. Related variants одного source cluster имеют
один split и один primary stratum.

Предлагаемая allocation для каждого candidate/profile идентична:

| Primary stratum | Minimum independent clusters per candidate/profile | Состояние |
|---|---:|---|
| `ui` | `36` | proposed |
| `mechanics` | `36` | proposed |
| `narrative` | `36` | proposed |
| `dialogue` | `36` | proposed |
| `humor_wordplay` | `36` | proposed |
| `gender_case` | `36` | proposed |
| `lore` | `36` | proposed |
| `typed_atoms` | `36` | proposed |
| **Всего** | **`288`** | proposed |

`36` — минимальный размер, при котором all-success stratum может иметь
two-sided `95%` exact Clopper–Pearson lower bound не ниже proposed `90%` floor;
это не гарантия pass. Фактический pass требует, чтобы confidence bound прошёл
со всеми наблюдавшимися failures. Для каждого proposed auto-eligible class
critical false-accept gate дополнительно требует минимум `149` independent
clusters на candidate/profile: при `x=0` это позволяет one-sided `95%` upper
bound не выше `2%`. Если базовая allocation не даёт `149` для class, до holdout
нужно либо заранее добавить clusters, либо оставить class mandatory-human.

Для **каждой** D2, D3, D4 и D5 отдельно, каждого required stratum и каждого
candidate/profile proposal требует applicable independent `n >= 36`; overall
applicable `n >= 288` на dimension/candidate/profile. Human-confirmed
`not_applicable` публикуется, но в applicable `n` не входит. До holdout manifest
обязан иметь preregistered oversampling/reserve allocation и deterministic
selection rule, достаточные для этих minima; post-hoc replacement после
раскрытия outcome запрещён. Если reserves исчерпаны, gate получает insufficient
coverage, а не denominator из одного либо нескольких удобных samples.

Proposed confidence lower-bound floors одинаково применяются к каждому из восьми
strata, где dimension applicable:

| Dimension | Overall floor | Floor каждого required stratum |
|---|---:|---:|
| D2 meaning accuracy | `95%` | `90%` |
| D3 terminology/lore | `90%` | `85%` |
| D4 literary Russian | `85%` | `80%` |
| D5 context/voice/style | `85%` | `80%` |

До явного owner acceptance exact allocation, thresholds, confidence method,
stable reviewer pairs и auto-eligible class list имеют состояние
`OWNER_DECISION_REQUIRED`. Holdout runner обязан остановиться до первого request,
если хотя бы одно значение не принято и не связано с freeze bundle. Недостаток
общего `n`, `n` stratum, candidate/profile coverage либо class-specific `n`
после run является hard failure; observed percentage, один успешный sample и
post-hoc pooling не дают pass.

| Gate | Предложение | Статус |
|---|---|---|
| Editorially approved schema/atoms | `100%` `editorially_approved` results проходят D1; `0` approved D1 defects | proposed, pending owner acceptance |
| Critical false accepts | наблюдаемое число `0` для каждого candidate/profile и каждой auto-eligible class | proposed, pending owner acceptance |
| Confidence bound | one-sided `95%` exact Clopper–Pearson upper bound для critical false-accept probability не выше `2%` | proposed, pending owner acceptance |
| Semantic accuracy D2 | overall `>=95%` score `>=3`; каждый required stratum `>=90%` | proposed, pending owner acceptance |
| Terminology/lore D3 | overall `>=90%` score `>=3`; каждый required stratum `>=85%` | proposed, pending owner acceptance |
| Literary Russian D4 | overall `>=85%` score `>=3`; каждый required stratum `>=80%` | proposed, pending owner acceptance |
| Context/voice D5 | overall `>=85%` score `>=3`; каждый required stratum `>=80%` | proposed, pending owner acceptance |
| Reviewer agreement | quadratic-weighted Cohen kappa `>=0.60` отдельно для каждой stable reviewer pair/dimension на double-reviewed subset; critical disagreements всегда adjudicated | proposed, pending owner acceptance |

Threshold применяется к каждому candidate/profile отдельно. Overall pass не
может компенсировать failed stratum; candidate может получить
`QUALITY_FEASIBLE` только для явно ограниченного набора classes, а остальные
остаются mandatory-human либо infeasible.

Для critical false accepts заранее выбран exact binomial Clopper–Pearson method.
Публикуются observed events `x`, число независимых samples `n`, confidence level
и upper bound. При `x = 0` one-sided upper bound вычисляется как
`1 - 0.05^(1/n)`; нулевое наблюдение без `n` и bound запрещено. Для предложенного
предела `2%` требуется минимум `149` независимых zero-event samples; меньшее `n`
не проходит confidence gate даже при `x = 0`.

Для proportions D2–D5 публикуются cluster-level numerator/denominator и
two-sided `95%` exact binomial intervals. Pass требует одновременно observed
proportion не ниже threshold и confidence lower bound не ниже соответствующего
overall/stratum floor. Ordinal distributions, category sizes,
`BLINDING_FAILED`, terminal failures и missing/invalid counts публикуются
отдельно; только mean не используется. Terminal и blinding failures остаются в
assigned denominator с zero success. Multiple strata не скрываются pooled
result. Statistical unit, exclusions и applicability rules фиксируются до
holdout; exclusions после assignment запрещены, кроме заранее перечисленной
protocol-invalidity, которая всё равно сохраняется в coverage/accounting.

## Model-review experiment

Model-review — отдельный secondary experiment с собственным profile, randomized
mapping и metrics:

- sensitivity/specificity к frozen human-adjudicated findings;
- false-negative rate для critical/high findings;
- extra latency/memory и leakage surface;
- disagreement с людьми по dimension/severity.

Его output не показывается initial human reviewer-ам, не меняет primary score,
не заменяет две human reviews и не назначает editorial state. Даже идеальное
совпадение на holdout не отменяет mandatory-human classes без нового будущего
owner decision.

## Verdict contribution

Rubric даёт вход в `QUALITY_FEASIBLE` только при всех owner-accepted hard gates,
полном split/protocol evidence и явно перечисленных разрешённых classes.
Невыполненный quality gate даёт `QUALITY_NOT_FEASIBLE` либо более узкий новый
protocol на новом holdout; post-hoc снижение threshold запрещено.

Synthetic conformance pass проверяет только shape rubric records и adversarial
contract cases. Он не измеряет русскую литературность, смысл или lore и не
является M1B verdict.
