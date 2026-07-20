# Независимая quality rubric M1B

- Статус: `M1B: NOT_EVALUATED`; proposal для owner review, human scoring и
  holdout ещё не выполнялись
- Версия proposal: `m1b-quality-rubric-v4`; analysis policy
  `m1b-analysis-policy-v4`; protocol generation `104`; definition state:
  `proposed`
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

`source_unit_cluster_id` объединяет одно событие/chain, один dialogue context
block, одну UI family либо другую минимальную группу вариантов с общим
происхождением. Все related lines, paraphrases и variants получают один cluster
ID, остаются в одном split и сами по себе не являются независимыми.

Статистическая Bernoulli unit определяется отдельно для каждого tuple
`(candidate/profile, split, gate или dimension, primary stratum,
source_generation_id)`. Все clusters одной immutable source generation внутри
одного primary stratum сворачиваются в один conservative outcome: success
только если успешны все applicable rows. Поэтому одна source generation даёт не
более одного trial в конкретный stratum claim. Неясная lineage объединяет units
conservative либо блокирует split.

Executable analysis принимает closed `split` (`tuning`/`holdout`) и
`dimension_or_gate`: пять D1-D5 contract
dimensions либо `critical_false_accept`/`editorial_approval`. Unknown token не
создаёт post-hoc gate. CFA input отдельно требует один из closed risk classes и
сворачивает events по source generation внутри
candidate/profile/split/class. Decision-grade helper принимает только frozen
`holdout`; tuning aggregates явно маркируются как diagnostics и имеют
`decision_grade_eligible=false`. Missing/unknown split и mixed-split scope
fail closed; tuning никогда не увеличивает holdout `n`, numerator или gate.

Одна source generation может дать по одному trial нескольким strata, потому что
это разные conjunctive claims. Эти вклады нельзя складывать в общий binomial
`n`: для descriptive overall source generation учитывается не более одного раза
с conservative outcome, а overall confidence/pass gate запрещён.

Cluster не создаёт отдельный denominator: его rows входят в соответствующую
source-generation/stratum unit. Для D2–D5 unit success только если успешны все
applicable rows всех contained clusters; любой failure делает unit failure. Для
ordinal reviewer-agreement distribution source generation получает суммарную
массу ровно `1`, распределённую только между фактически наблюдавшимися paired
ratings; component-wise minimum разных rows запрещён. Cluster может иметь ровно
один primary stratum; secondary risk labels не создают новый `n`.

Повторные attempts не создают дополнительные samples или clusters. Initial,
repair и fallback histories связываются с одной assignment и считаются отдельно.
Для critical false-accept statistics trial — tuple
`(candidate/profile, split, risk class, source_generation_id)`: если в любом contained
cluster/row есть adjudicated critical false accept, вся source-generation/class
unit является одним event. Findings, rows, variants, clusters и reviewers нельзя
использовать для искусственного увеличения `n` либо `x`.

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
`not_applicable`, `not_evaluated`, `blinding_failed`. Последний status допустим
только для D2-D5 self-identifying model output в terminal state
`blinding_failed`; это denominator failure, не missing evidence. В partial
M1B-0 D1 может показывать только
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
оценивать по отсутствующему output; findings, human/model finding reviews и
любая `human_ground_truth` для такой row запрещены. Controlled failure остаётся
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

Каждый holdout output, который прошёл primary blinding и пригоден для blinded
review, получает human ground truth для каждой D2–D5: ordinal score либо
human-confirmed `not_applicable` с frozen reason. Это требование
действует и для class, который будущая production policy предлагает как
auto-eligible. `not_evaluated`, missing record или только model-review evidence
не допускает human-quality или editorial/operational acceptance. Для
`self_identifying_output` действует закрытое исключение: D2–D5=
`blinding_failed`, zero primary success, primary HGT запрещён; optional
`secondary_unblinded` evidence descriptive only и не входит в primary
agreement/quality gate.
Для каждой оцениваемой D2-D5 dimension используются ровно две distinct frozen
initial human records из stable pair `(stratum, dimension)`; critical finding
дополнительно применяет свои exact two-review/adjudication rules. При совпадении
initial outcomes третий adjudicator не создаётся.

Слово output здесь существенно: controlled no-output failure и
`terminal_status=not_applicable` без model attempt не получают findings,
human/model content reviews, D2–D5 labels или `human_ground_truth` и не
исключаются из denominator. Их нельзя
превратить в quality success искусственной записью `not_applicable`.

Executable v4 `human_ground_truth` row содержит ровно `adjudicates`,
`applicability_reason`, `dimension`, `evidence_tier`, `ground_truth_id`,
`mapping_generation`, `ordinal_score`, `result_id`, `review_stage`,
`reviewer_blinding`, `reviewer_id`, `reviewer_role`, `status`. Ordinal score
имеет closed range `0..4`; `3..4` означает `human_pass`, `0..2` — `human_fail`.
Для `not_applicable` score равен `null`, а reason — exact
`frozen_not_applicable`; для остальных status reason равен `null`.

Evidence tiers разделены: `primary_blinded` участвует в primary gate,
`compromised_primary` сохраняет неизменяемое evidence после external mapping
leak, а `secondary_unblinded` может только информировать owner review. Текущий
M1B-0 v4 report является только partial synthetic contract и всегда отклоняет
`complete_benchmark` кодом `PARTIAL_REPORT_CANNOT_BE_COMPLETE`. Будущий live
report требует отдельной owner-accepted schema/analysis definition; ни один v4
status не подменяет это evidence.

Один reviewer ID имеет одну immutable role во всём document. Reviewer ID не
может совпадать с candidate, sample, source cluster, atom/occurrence, result,
finding, review либо другим opaque ID. Private identity map проверяет, что две
critical initial reviews сделаны разными людьми, а не только разными UUID.

Disagreement включает разные severity, hard-fail flag, dimension score,
applicability либо mandatory-review disposition. До aggregation:

1. initial records замораживаются и не переписываются;
2. disagreement получает отдельный controlled code;
3. третий независимый human adjudicator видит оба frozen initial records, но не
   model identity;
4. top-level `adjudications` либо ground-truth row со stage `adjudication`
   ссылается ровно на два conflicting initial IDs и сохраняется отдельно;
5. unresolved disagreement блокирует verdict для category.

Executable finding-review v4 хранит reviewer-specific closed outcome
`decision`, `severity`, `hard_fail`, `mandatory_review` и повторно bind-ит exact
`finding_id`, category и dimension вместе с mapping/blinding provenance.
Если finding содержит две initial human reviews, их reviewer identities обязаны
быть distinct независимо от category/severity и от того, совпали ли outcomes;
два review IDs одного человека не создают две независимые initial records.
Top-level finding outcome не self-asserted: он обязан совпасть с matching
initial outcomes либо с отдельным outcome третьего adjudicator-а. Два initial
outcome `medium` и `high` всегда являются disagreement; до exact adjudication
validator fail closed, а top-level downgrade отклоняется. Matching initial
outcomes не создают лишнего adjudicator-а. Model-review outcome остаётся
`non_human` и не удовлетворяет human credit.

Калибровка reviewer-ов выполняется только на tuning. Изменение instructions или
anchors после holdout invalidates rubric generation и требует нового holdout.

Для публикуемого source-balanced, case-weighted quadratic Cohen kappa каждый tuple
`(primary stratum, dimension)` имеет заранее назначенную stable pair reviewers,
одинаковую для tuning/holdout и всех трёх candidates/profiles, но kappa
публикуется отдельно для каждого `(split, candidate, profile)` scope. Значения
меняющихся pairs, splits или candidates не
pooling-уются. Вход каждой row ссылается на unique logical
`(result_id, dimension)`, два distinct frozen initial HGT IDs, их exact reviewer
pair и source generation; повтор logical row запрещён. Final adjudicator score
никогда не становится третьим kappa rating. Eligible universe — все
validator-linked distinct frozen initial pairs данного scope; он замораживается
до holdout и не может выбирать rows post-hoc по score.

Для каждой ordinal-applicable source generation `s` пусть `m_s` — число её
actual paired rows, а `count_sij` — сколько из них имеют exact pair `(i,j)`.
Executable equal-source contingency задаётся как
`O_ij = sum_s(count_sij / m_s)`. Поэтому каждая source generation вносит total
mass ровно `1`, все реальные pairings сохраняются, а число contained rows не
увеличивает независимый вес. `n = sum_ij O_ij` равно числу source generations с
хотя бы одной ordinal-applicable pair. Component-wise minima reviewer-ов из
разных rows, synthetic cross-row pairing и row-count weighting запрещены.

Ratings — exact integers `0..4`; для rational counts `O_ij`, row totals `r_i`,
column totals `c_j`, `n` и agreement weights `q_ij = 16 - (i-j)^2` executable
formula равна
`kappa = (n*sum(q_ij*O_ij) - sum(q_ij*r_i*c_j)) /
(16*n^2 - sum(q_ij*r_i*c_j))`. Arithmetic выполняется как exact rational.

Source без ordinal-applicable rows, у которого все rows bilateral
`not_applicable`, входит только в отдельный applicability-agreement count.
Любой unilateral `not_applicable` связывается с exact двумя initial IDs и
distinct third adjudicator, исключает source из ordinal contingency и даёт
fail-closed `AGREEMENT_APPLICABILITY_DISAGREEMENT`; наличие adjudication не
превращает исчезнувшую ordinal pair в agreement success. Missing
pair/provenance record invalidates run. Если denominator formula равен
нулю, результат `AGREEMENT_UNDEFINED_ZERO_EXPECTED_DISAGREEMENT`, а не perfect
agreement. Proposed gate требует `n >= 46`, point kappa `>= 3/5` и каждую
delete-one-whole-source kappa defined и `>= 3/5`; при delete-one удаляется вся
fractional contribution source и заново вычисляются `n`, marginals и kappa.
Этот every-delete-one test — influence robustness criterion, не sampling
confidence interval. Недостаток units, applicability disagreement, point
failure, undefined robustness и threshold failure имеют отдельные controlled
statuses; они не заменяются приблизительным score.

Closed result set ровно такой: `AGREEMENT_APPLICABILITY_DISAGREEMENT`,
`AGREEMENT_INSUFFICIENT_UNITS`,
`AGREEMENT_UNDEFINED_ZERO_EXPECTED_DISAGREEMENT`,
`AGREEMENT_POINT_BELOW_FLOOR`, `AGREEMENT_UNCERTAINTY_UNDEFINED`,
`AGREEMENT_ROBUSTNESS_BELOW_FLOOR`, `AGREEMENT_PASS`. Порядок initial ratings
детерминирован raw ASCII ascending reviewer UUID: linked record первого UUID
формирует первую ось, linked record второго — вторую; перестановка не зависит от
score либо candidate.
Decision-grade rows materialize только внутри HGT validator из уже связанных
frozen initial records и сохраняют split исходного sample. Agreement gate
принимает только однородный holdout scope; tuning доступен лишь через отдельный
split-marked diagnostic helper. Generic row helper принимает только public
synthetic math vectors и сам по себе не является live/selection evidence.

При external mapping leak affected initial records сохраняются как
`compromised_primary`; replacement использует новую mapping generation и только
новых reviewers, никогда не видевших прежнюю либо текущую identity. Reviewer ID
нельзя переиспользовать между compromised и fresh mapping. Self-identifying
output не переоценивается и не регенерируется: result в любой model-output lane получает
`blinding_status=self_identifying_output`, `failure_code=BLINDING_FAILED`,
ровно один `model_call_count`, terminal `blinding_failed`, остаётся в assigned
denominator и даёт zero success
для каждой D2–D5; sibling generation при недоказанной chronology запрещена.
Human-fallback row не является model output и не может получить этот status.
Primary HGT запрещён. Unblinded review допустим только как
`secondary_unblinded`, не восстанавливает primary success и не участвует в
primary agreement/quality gate.

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

| Primary stratum | Minimum source-generation units per candidate/profile | Состояние |
|---|---:|---|
| `ui` | `46` | proposed |
| `mechanics` | `46` | proposed |
| `narrative` | `46` | proposed |
| `dialogue` | `46` | proposed |
| `humor_wordplay` | `46` | proposed |
| `gender_case` | `46` | proposed |
| `lore` | `46` | proposed |
| `typed_atoms` | `46` | proposed |
| **Stratum quota slots** | **`368`** | proposed; не pooled `n` |

`368` — сумма восьми отдельных stratum quotas. Если одна source generation
представлена в нескольких strata, она может занять несколько quota slots, но не
становится несколькими independent overall trials. Overall binomial confidence
gate отсутствует; descriptive overall distinct-source count сворачивает одну
source generation ровно один раз.

### Confidence family и minima

Решение сравнивает заранее фиксированную family из трёх candidates. Family-wise
error равен `alpha_family = 1/20` (`95%` simultaneous confidence). Bonferroni
даёт каждому candidate `alpha_candidate = 1/60`; для two-sided exact
Clopper–Pearson interval каждая tail равна `1/120`. Strata внутри candidate
образуют intersection-union gate: candidate проходит только если проходит
каждый required stratum, поэтому failed stratum нельзя компенсировать другим и
post-hoc pooling запрещён.

Обычный marginal `95%` interval для одного candidate/stratum может публиковаться
только как descriptive diagnostic. Он не является simultaneous decision
evidence, не поддерживает winner/selection claim и не заменяет Bonferroni family.

All-success planning minima для lower confidence bound:

| Dimension | Per-stratum floor | Minimum applicable source generations |
|---|---:|---:|
| D2 meaning accuracy | `90%` | `46` |
| D3 terminology/lore | `85%` | `30` |
| D4 literary Russian | `80%` | `22` |
| D5 context/voice/style | `80%` | `22` |

Эти minima — первые integers `n`, для которых `floor^n <= 1/120`; они только
показывают, когда all-success lower bound может достичь floor. Унифицированная
allocation `46` на stratum покрывает самый строгий D2 minimum. При failures
нужен больший `n`, определённый actual exact bound. Human-confirmed
`not_applicable` не входит в applicable `n`, поэтому до holdout обязательны
preregistered reserves и deterministic replacement rule. Исчерпание reserves
даёт insufficient coverage, не удобный post-hoc denominator.

До явного owner acceptance exact allocation, thresholds, confidence method,
stable reviewer pairs и auto-eligible class list имеют состояние
`OWNER_DECISION_REQUIRED`. Holdout runner обязан остановиться до первого request,
если хотя бы одно значение не принято и не связано с freeze bundle. Недостаток
`n` любого required stratum, candidate/profile coverage либо class-specific `n`
после run является hard failure; descriptive overall percentage, один успешный
sample и post-hoc pooling не дают pass.

| Gate | Предложение | Статус |
|---|---|---|
| Editorially approved schema/atoms | `100%` `editorially_approved` results проходят D1; `0` approved D1 defects | proposed, pending owner acceptance |
| Critical false accepts | наблюдаемое число `0` для каждого candidate/profile и каждой auto-eligible class | proposed, pending owner acceptance |
| CFA confidence bound | при `x=0`, one-sided exact upper bound с `alpha_candidate=1/60` не выше `2%`; `n >= 203` на class/candidate | proposed, pending owner acceptance |
| Semantic accuracy D2 | каждый required stratum exact lower bound `>=90%` | proposed, pending owner acceptance |
| Terminology/lore D3 | каждый required stratum exact lower bound `>=85%` | proposed, pending owner acceptance |
| Literary Russian D4 | каждый required stratum exact lower bound `>=80%` | proposed, pending owner acceptance |
| Context/voice D5 | каждый required stratum exact lower bound `>=80%` | proposed, pending owner acceptance |
| Reviewer agreement | exact quadratic-weighted kappa `>=3/5`, `n >=46`, и каждая delete-one-source kappa defined и `>=3/5` для каждой stable pair/stratum/dimension | proposed, pending owner acceptance |

Threshold применяется к каждому candidate/profile отдельно. Overall pass не
может компенсировать failed stratum; candidate может получить
`QUALITY_FEASIBLE` только для явно ограниченного набора classes, а остальные
остаются mandatory-human либо infeasible.

Для critical false accepts заранее выбран one-sided exact binomial upper bound.
Публикуются observed events `x`, independent class-level source-generation `n`,
`alpha_candidate=1/60` и bound. При `x = 0` он равен
`1 - (1/60)^(1/n)`. Для proposed предела `2%` требуется минимум `203`
zero-event holdout units на candidate/profile/class; меньшее holdout `n` не
проходит gate. Tuning units публикуются только как separate diagnostics и не
могут довести denominator до `203`.

Для proportions D2–D5 публикуются holdout-only per-stratum source-generation
numerator/denominator и two-sided exact intervals с tail `1/120`. Pass требует
одновременно observed proportion и lower bound не ниже соответствующего
per-stratum floor. Candidate-level simultaneous claim существует только при
pass всех required strata; pooled overall interval запрещён. Descriptive overall
distinct-source count, ordinal distributions, category sizes,
`BLINDING_FAILED`, terminal failures и missing/invalid counts публикуются
отдельно; только mean не используется. Terminal и blinding failures остаются в
assigned denominator с zero success. Statistical unit, exclusions и
applicability rules фиксируются до holdout; exclusions после assignment
запрещены, кроме заранее перечисленной protocol-invalidity, которая всё равно
сохраняется в coverage/accounting.

Clopper–Pearson boundary conventions explicit: lower bound равен `0` при
`successes=0`, иначе используется beta quantile
`BetaQuantile(1/120; successes, n-successes+1)`; upper bound равен `1` при
`successes=n`, иначе
`BetaQuantile(119/120; successes+1, n-successes)`. Shape parameter `0` никогда
не передаётся beta-quantile implementation.

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
