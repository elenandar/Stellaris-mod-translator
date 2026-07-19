# Независимая quality rubric M1B

- Статус: proposal для owner review; human scoring и holdout ещё не выполнялись
- Версия proposal: `m1b-quality-rubric-v1`
- Quality verdict: отсутствует
- Gate state: `M1A: BLOCKED`; `M2: forbidden`

Rubric фиксируется до раскрытия holdout и оценивает technical integrity,
смысл, терминологию/лор, литературность, контекст/голос независимо. Среднее или
общий score не может скрыть critical defect. `technical_safe` не означает
`editorially_approved`; последнее решение принадлежит только человеку.

Все числовые thresholds и confidence parameters в разделе
«Предложенные hard gates» являются **предложенными и ожидают явного owner
acceptance до holdout**. Они не являются уже принятым project policy.

## Единица оценки

Основная единица — один frozen holdout sample и один candidate/profile result.
Она имеет случайный opaque UUIDv4, category/stratum из заранее принятого enum,
five independent dimension records и disposition. Findings не содержат raw
excerpt; локальный reviewer видит raw text в private surface, а repository
получает только codes и aggregates.

Повторные attempts не создают дополнительные независимые samples. Initial,
repair и fallback histories связываются с одной единицей и считаются отдельно.
Для critical false-accept statistics один sample является одним Bernoulli trial:
если в нём есть хотя бы один adjudicated critical false accept, весь sample
считается event. Findings/reviewers нельзя использовать для искусственного
увеличения `n`.

## Независимые dimensions

### D1 — Schema и typed-atom stability

Машинный hard gate, не субъективная языковая оценка:

- exact schema version и allowlisted fields/types;
- каждый expected atom присутствует ровно в требуемой cardinality;
- atom ID, type, immutable value и разрешённая position policy сохранены;
- нет missing, extra, duplicate, mutated или unbound atom;
- code/key/escape/control structure не появляется в human span;
- unknown syntax не угадывается.

Любой defect D1 делает attempt schema/atom-invalid. Такой result не может быть
accepted или считаться human-quality success; repair и terminal fallback
учитываются явно. M1B проверяет benchmark contract, но не объявляет будущий M2
renderer доказанным.

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
`critical false accept` означает, что frozen pipeline присвоил result принятую
disposition, не заблокировав adjudicated critical defect и не направив его в
обязательный human gate. Это разные metrics: безопасно пойманный critical model
defect не является false accept, но остаётся model-quality failure и входит в
repair/fallback rate.

Любой accepted result с critical human finding является critical false accept и
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

## Mandatory-human-review classes

Независимо от model score обязательный human gate получают:

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

## Предложенные hard gates

Ниже — единый pre-holdout proposal. **Каждое число и сам statistical method
ожидают owner acceptance; до этого M1B benchmark не получает verdict.**

| Gate | Предложение | Статус |
|---|---|---|
| Accepted schema/atoms | `100%` accepted results проходят D1; `0` accepted D1 defects | proposed, pending owner acceptance |
| Critical false accepts | наблюдаемое число `0` для каждого candidate/profile и каждой auto-eligible class | proposed, pending owner acceptance |
| Confidence bound | one-sided `95%` exact Clopper–Pearson upper bound для critical false-accept probability не выше `2%` | proposed, pending owner acceptance |
| Semantic accuracy D2 | не менее `95%` applicable holdout samples имеют score `>=3`; ни один pre-registered stratum ниже `90%` | proposed, pending owner acceptance |
| Terminology/lore D3 | не менее `90%` applicable samples score `>=3`; lore-sensitive stratum не ниже `85%` | proposed, pending owner acceptance |
| Literary Russian D4 | не менее `85%` applicable samples score `>=3`; ни один разрешаемый class ниже `80%` | proposed, pending owner acceptance |
| Context/voice D5 | не менее `85%` applicable samples score `>=3`; ни один context-sensitive stratum ниже `80%` | proposed, pending owner acceptance |
| Reviewer agreement | quadratic-weighted Cohen kappa `>=0.60` по каждой ordinal dimension на double-reviewed subset; critical disagreements всегда adjudicated | proposed, pending owner acceptance |

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

Для proportions D2–D5 публикуются numerator/denominator и two-sided `95%` exact
binomial intervals. Ordinal distributions, category sizes и missing/invalid
counts публикуются отдельно; только mean не используется. Multiple strata не
скрываются pooled result. Statistical unit, exclusions и applicability rules
фиксируются до holdout.

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
