# M1A — format and playset evidence, 17 июля 2026 года

> Это исторический отчёт исходного run 17 июля: его counts, test total и hashes
> не переписаны задним числом. Evidence PR #3 впоследствии слит как
> `2b51879d8e358cf5412f3a6792f33c71ae79d863`; текущий hardening и повторная
> validation зафиксированы в [addendum от 18 июля](m1a-format-playset-revalidation-2026-07-18.md).

## 1. Repository, base и evidence head

| Поле | Значение |
|---|---|
| Repository | `https://github.com/elenandar/Stellaris-mod-translator.git` |
| Branch | `agent/m1a-format-playset-evidence` |
| Upstream до публикации | `origin/main` |
| Base | `origin/main` at `8d468b7b8ca1f748dda8c072ce02933b15656dc2` |
| Evidence capture `HEAD` | `8d468b7b8ca1f748dda8c072ce02933b15656dc2` |
| Required M0R merge | ancestor of `origin/main`; в момент preflight совпадал с tip |

Remote refs были получены до создания ветки. Исходный `main` был чист и отставал от remote; ветка создана непосредственно от актуального на preflight `origin/main`. Старый branch `agent/m0-personal-local-ollama` не использовался и не изменялся.

Final commit SHA нельзя поместить внутрь содержащего его report без самоссылки. Immutable PR head фиксируется в draft PR и финальной передаче владельцу; таблица выше точно определяет base и Git `HEAD`, на котором начался evidence capture.

## 2. Версия игры и environment

| Параметр | Проверенное значение | Evidence |
|---|---|---|
| Stellaris | `Pegasus v4.4.6 (fdde)` | [локальный inventory](local-environment-2026-07-17.md) и [официальный анонс 4.4.6](https://steamcommunity.com/games/281990/announcements/detail/689761349249538499) |
| Release date hotfix | 9 июля 2026 года | официальный анонс |
| Architecture | `arm64` | повторный system probe |
| macOS | `26.5.2` (`25F84`) | повторный system probe |
| Research runtime | Python `3.9.6`, standard library only | `python3 --version`; dependencies не устанавливались |

Profile ограничен [`stellaris-4.4.6`](../version-profiles/stellaris-4.4.6.md). Наличие версии не доказывает grammar, markup или load order; эти свойства проверялись отдельно.

## 3. Scope и privacy statement

Выполнен только M1A: format/threat research, synthetic immutable-generation/containment/candidate spikes, публичное technical-source review и локальный агрегированный census. Не выполнялись M1B, Ollama, M2, перевод, game/launcher start, candidate activation, publish, запись в source/Workshop/game/launcher/active paths или установка зависимостей.

Raw official/mod localisation, descriptor values, launcher rows, mod names, keys и private paths не выводились Codex/subagents и не попали в repository evidence. Реальные bytes разрешалось читать только auto-discovery helper внутри локального процесса; наружу выходили counts, booleans, public categories, sizes, SHA-256/opaque digests и redacted codes. Полная политика: [corpus-policy.md](../corpus-policy.md).

## 4. Метод исследования

1. Проверены Git cleanliness, remote ancestry и M0R merge; прочитаны `AGENTS.md` и все входные architecture/roadmap/evidence документы.
2. Публичные sources использовались для candidate taxonomy и ограниченных lifecycle/launcher claims. Paradox-hosted community [localisation guide](https://stellaris.paradoxwikis.com/Localisation_modding), [modding guide](https://stellaris.paradoxwikis.com/Modding) и [tutorial](https://stellaris.paradoxwikis.com/Modding_tutorial) считались устаревающими candidate references, а [Paradox launcher help](https://support.paradoxplaza.com/hc/en-us/articles/360020841079-My-Mods-or-Playsets-are-not-showing-up-in-the-Launcher), [Steam Workshop implementation](https://partner.steamgames.com/doc/features/workshop/implementation) и [ISteamUGC](https://partner.steamgames.com/doc/api/ISteamUGC) — публичными vendor sources в пределах прямо документированных claims.
3. Synthetic fixtures задали expected aggregate classification; research scanner возвращал исходные bytes без transform.
4. Stable reader дважды читал один descriptor, сравнивал path/open-file identity, metadata, byte count и content; mismatch давал whole-run clean abort.
5. Auto-discovery collector выполнял полный локальный census без private CLI arguments, два полных manifest pass и repository leakage comparison.
6. Candidate builder работал только в `TemporaryDirectory`, после root-disjointness seal: flat payloads создавались напрямую через sealed root descriptor, перечитывались/хешировались, а manifest коммитился последним и затем весь tree проверялся снова.
7. Final checks включали 41 hermetic unit test, byte/hash comparisons, docs validation, `git diff --check`, полный diff и независимый read-only review после final evidence.

Публичные документы не принимались за versioned runtime truth: страницы wiki сами указывают более старую verified version и предупреждают о неодинаковых/изменяемых load strategies.

## 5. Corpus size и sampling

| Corpus layer | Files | Bytes | Round-trip failures |
|---|---:|---:|---:|
| Official installation, все найденные language subtrees | 2 318 | 171 100 301 | 0 |
| Workshop, все найденные `localisation/**/*.yml` | 5 653 | 131 563 578 | 0 |
| **Total census** | **7 971** | **302 663 879** | **0** |
| Development cohort | 6 337 | 242 968 168 | 0 |
| Deterministic holdout | 1 634 | 59 695 711 | 0 |

Source manifest дополнительно включал Steam library metadata, descriptors, active-load/version metadata и byte-only launcher database candidates: всего 8 098 observed files. Обнаружено 114 Workshop source directories и 10 local outer descriptors. Private `path` values local descriptors намеренно не разыменовывались: local-source content не входит в census и зафиксирован как blocker, а не как нулевой coverage.

Локальный inventory являлся census найденных files, а не выборочной экстраполяцией. Cohort назначался по первому byte SHA-256 фактически прочитанных bytes: `0..51` — deterministic holdout, остальные — development. Тот же scanner обрабатывал оба cohort, поэтому это cross-check distribution/round trip, а не статистически независимая external validation. Raw membership не публиковался. Synthetic fixtures созданы с нуля и не являются excerpts из game/mod corpus.

## 6. Агрегированный format inventory

| Категория | Aggregate result |
|---|---:|
| UTF-8 valid / invalid files | 7 971 / 0 |
| BOM at start / missing | 7 951 / 20 |
| Hidden BOM | 0 |
| Newlines LF / CRLF / mixed / CR-only | 4 958 / 2 969 / 44 / 0 |
| Final newline present / missing | 6 417 / 1 554 |
| Header lines | 7 860 |
| Header class english / russian / other / misplaced / missing-or-multiple | 860 / 825 / 5 635 / 530 / 121 |
| Comment / blank / whitespace-affected lines | 132 826 / 139 132 / 2 968 201 |
| Entry / quoted value / version suffix / empty value occurrences | 2 768 768 / 2 768 768 / 1 308 023 / 8 271 |
| Escapes total | 534 170 |
| Fixture-backed `\n` / `\"` / `\\` / unknown escape | 502 428 / 31 039 / 137 / 566 |
| Intra-file duplicate groups / occurrences | 973 / 2 050 |
| Malformed / unknown lines | 17 681 / 82 432 |
| Placeholder / icon / `§Y...§!` formatting / scripted counts | 732 865 / 103 187 / 193 168 / 294 823 |
| Unknown-or-ambiguous markup events | 629 547 |
| Opaque construct events | 730 226 |
| Conservative profile blocker events | 730 941 |

Counts описывают текущую локальную generation; они не публикуют language tokens, keys или values. `opaque_constructs` считается blocker для transformation даже при успешном identity round trip.

## 7. Supported и unsupported taxonomy

| Конструкция | Fixture/evidence | M1A disposition |
|---|---|---|
| BOM at offset 0, hidden BOM | `format-cases.json` | exact classification; hidden BOM blocks |
| LF, CRLF, mixed, no final newline | `format-cases.json` | exact bytes; mixed blocks |
| first/single header, comments, blank/whitespace | fixtures + profile classifier | aggregate classes; misplaced/multiple header blocks |
| decimal suffix, quoted/empty value | `format-cases.json` | classified exact |
| duplicate occurrences | `format-cases.json` | preserve occurrences; no winner |
| `$...$`, `[...]`, `£...£`, `§Y...§!` | fixture-backed counts | narrow conservative ASCII/allowlist classification only |
| malformed quote, invalid UTF-8, unknown line/markup | adversarial fixtures | opaque blocker; no repair |
| case/Unicode-colliding relative paths | unit tests | build blocker |
| empty/unbalanced/orphan/crossing delimiters и unknown escapes/codes | isolated diagnostic tests | blocker, not inferred support |

Полный byte contract: [localisation-format.md](../specs/localisation-format.md). Markup contract: [markup-taxonomy.md](../specs/markup-taxonomy.md). M1A не присваивает ни одной конструкции статус `transform_supported`.

Real census содержит 20 files без BOM, 44 mixed-newline files, 530 misplaced и 121 missing/multiple header classifications, 17 681 malformed lines, 82 432 unknown lines, 566 unknown escapes и 629 547 markup events вне крайне узкого fixture-backed allowlist. `format_blocker_count=730 941` — сумма перекрывающихся event categories, а не число уникальных повреждённых строк.

Большой unsupported count ожидаем для research scanner, который положительно принимает только `§Y` formatting и консервативные atom payloads. Он не доказывает повреждение corpus; он доказывает, что текущую taxonomy нельзя расширить по сходству и что M2 transform на этом profile сейчас запрещён.

## 8. Byte-identical round trip

Все 7 971 files и 302 663 879 bytes дали identity equality: 7 971 pass, 0 fail. Development: 6 337/6 337; holdout: 1 634/1 634. Synthetic manifest содержит 22 positive/adversarial cases; все сравнили `render_identity()` с исходными bytes, а ambiguous delimiter cases дополнительно прошли isolated table-driven test.

Identity renderer возвращает сохранённый immutable `bytes` object; он не decode/encode и не normalise line endings. Pass-through сам по себе не является semantic support, поэтому unsupported counts сохраняют blocker status.

## 9. Immutable-generation и adversarial evidence

| Сценарий | Expected disposition | Результат |
|---|---|---|
| in-place change во время первого read | `GENERATION_MISMATCH` | pass |
| replacement между metadata и open | `GENERATION_MISMATCH` | pass |
| symlink source/substitution | reject/clean abort | pass |
| premature EOF | `PARTIAL_READ` | pass |
| short OS reads | accumulate exact size | pass |
| equality и оба ancestry overlap | `PROTECTED_ROOT_OVERLAP` | pass |
| root traversal/relative root | `AMBIGUOUS_ROOT_PATH` | pass |
| symlink/casefold root alias и root replacement | reject/invalidate seal | pass |
| duplicate/case/Unicode logical path | build blocker before write | pass |
| flat target symlink/hardlink substitution | reject, external/source target unchanged | pass |
| payload tamper до manifest commit | actual-tree mismatch, incomplete | pass |
| hardlink substitution complete candidate | reuse rejected | pass |
| disk-full до manifest commit | incomplete, never complete | pass |
| crash at each pre-commit point | no completion manifest | pass |
| crash after manifest commit | validate/reuse exact candidate | pass |
| invalid active/version schema и private CLI arg | fail closed, no echo | pass |
| mutation между discovery passes | whole-run `GENERATION_MISMATCH` | pass |
| metadata-only drift или relocation между принятыми snapshots | observer generation/ID меняется; content-identical logical candidate остаётся тем же | pass |
| identical rebuilds и rerun | same independent manifest/tree hashes; reuse | pass |

Стратегия M1A — clean abort при mismatch плюс immutable in-memory bytes фактически принятых reads. Silent per-file retry запрещён. Workshop mutable по [Steamworks lifecycle](https://partner.steamgames.com/doc/features/workshop/implementation), поэтому directory нельзя считать generation без manifest comparison.

## 10. Threat register

Полный register с severity, mitigation, evidence и milestone owner находится в [threat-model.md](../threat-model.md). Gate-critical итоги:

| Threat | Severity | M1A result | Owner остаточного контроля |
|---|---:|---|---|
| source/active-path write | Critical | helper surface read-only; candidate temp-only | M2/M3 |
| mixed generation/TOCTOU | Critical | synthetic clean-abort + local double-manifest evidence | M2 |
| root escape/symlink/traversal | Critical | fail-closed tests | M2/M3 |
| raw/private leakage | Critical | redacted output + corpus-aware leakage check | каждый milestone |
| unknown syntax/silent normalization | Critical | opaque exact bytes + blocker | M2 |
| duplicate/load-order winner guessed | Critical | не угадывался; export policy blocked | M1A/M3 |
| crash/disk-full/tampered candidate | High | flat actual-tree verification + manifest-last; incomplete rejected | M3 durability |
| stale candidate после update/remove | High | generation/order mismatch invalidates whole candidate | M3 |

## 11. Export policy comparison и load-order evidence

| Policy | Детерминированный disposable build | Provenance | Lifecycle/rollback boundary | Неразрешённое engine evidence | Disposition |
|---|---|---|---|---|---|
| `per-source` | yes, synthetic | naturally per source | many independent companions | exact companion/source precedence | not selected |
| `playset-bundle` | yes, synthetic | manifest keeps every source/generation | one playset artifact | bundle position и cross-source winner | M0R hypothesis only |
| `hybrid` | yes, synthetic | per-source + routing | coordinated multi-artifact rollback | оба precedence rules | not selected |

Sanitized metadata observation:

- 124 descriptors: 114 Workshop sources и 10 local outer descriptors;
- descriptor invalid UTF-8: 0; unknown field occurrences: 0; unsupported syntax occurrences: 0; unterminated blocks: 0;
- `dependencies` найден в 11 descriptors, 18 dependency values; identity/cycles/missing targets не интерпретировались, поэтому `DEPENDENCY_GRAPH_UNPROVEN` остаётся blocker;
- `replace_path` occurrences: 0; отдельно обнаружены 3 `localisation/replace` directories и 29 localisation files в них, но current-version precedence не доказана;
- active-load JSON найден и syntactically valid, но содержит 0 enabled mods; stored empty-order digest — `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`;
- `launcher-v2.sqlite` не обнаружен в auto-discovered standard launcher roots; SQLite schema не открывалась и не угадывалась;
- strict local version-metadata adapter не подтвердил documented field schema (`GAME_VERSION_UNVERIFIED`); identity `4.4.6 (fdde)` остаётся подтверждена отдельным M0R environment evidence и официальным release announcement, но этот fallback не ослабляет collector blocker;
- aggregate key hashing обнаружил 3 010 cross-source candidate groups и 37 542 occurrences, но не различает effective language/runtime winner и потому не используется как collision decision.

Нулевой active order не представляет личный modded playset и не даёт проверить disable/remove/update order. Private local `path` values не follow-ились, поэтому десять local sources также не могут заполнить этот пробел. Activation для получения недостающего evidence запрещена.

Community candidate docs describe `localisation/replace` and descriptor `dependencies`, but do not provide a current complete 4.4.6 precedence contract. Наблюдение directory layer не доказывает его current-version ordering semantics. Launcher metadata can demonstrate stored order only; оно не доказывает effective engine collision winner. `replace_path` и `localisation/replace` не отождествлялись. Полный contract: [artifact-and-publish-contract.md](../specs/artifact-and-publish-contract.md).

## 12. Source immutability proof

Первый и второй full manifest совпали для 8 098 observed files; aggregate content/topology generation SHA-256:

```text
aa64e51eb9ff06921ef4e21a4fdfb5ceb46745f3622690d0726cd0a55cfdb559
```

Каждый manifest pass внутри себя выполнял два reads одного open descriptor и path/descriptor metadata recheck. Generation digest также связывает Steam library metadata, protected-root identities и Workshop source topology. `pre_post_manifest_equal=true`, round-trip failures `0`, source/launcher/active-path write attempts `0`. Четыре protected roots были зарегистрированы до disposable writes.

Две synthetic candidate builds в разных temporary roots дали одинаковые, но независимо вычисленные manifest и observed payload-tree hashes:

```text
manifest: 46f50f997b9ac46024d5f94213319fe1f8005eba88e960788b6c78d84e804dfb
tree:     7718d952a307f7e77de375079e65907b971bcd24f063e4353ea5fed073f48225
```

Доказательство ограничено content/identity manifest тех source objects, которые helper фактически прочитал. Observer generation включает absolute-path-derived identity и identity/time metadata, поэтому обнаруживает drift текущего read. Logical candidate использует отдельно domain-separated content generation и ID synthetic logical path: безвредный metadata-only churn либо relocation checkout не меняет output при тех же принятых bytes/order. Это подтверждает отсутствие обнаруженного byte/namespace change, но не делает абсолютного утверждения об atime или внешних системных metadata, не входящих в source manifest.

Ни game, ни launcher не запускались. Steam API не вызывался: в частности, M1A не использовал `GetItemInstallInfo`, потому что [ISteamUGC documentation](https://partner.steamgames.com/doc/api/ISteamUGC) описывает побочный user-used flag.

## 13. Privacy/leakage result

Corpus-aware stable-read scan проверил 34 regular repository/artifact files, 2 056 868 exact non-header line fingerprints, 51 992 long structured-token fingerprints и 16 402 private descriptor/active/path identifiers. Exact-line/token/private-value matches: `0/0/0`; `match_count=0`, `passed=true`. Source excerpt либо match detail не выводился.

Leakage check не печатает match. Он сравнивает intended repository bytes, synthetic fixtures и подготовленный ignored PR body с exact lines от 4 bytes (кроме public language headers), structured tokens от 64 bytes, private values, полными canonical private paths и их непубличными components от 8 bytes. Это defense in depth, а не доказательство отсутствия каждого короткого substring; после scan обязателен неизменённый explicit stage и полный cached-diff review.

## 14. Ограничения и недоказанные предположения

- Wiki localisation candidate syntax не является versioned grammar 4.4.6; полный актуальный markup vocabulary/nesting неизвестен.
- Launcher DB schema и stored order semantics не имеют опубликованного stable contract; read-only schema observation не превращает их в engine guarantee.
- Обычный cross-mod duplicate winner и current-version semantics candidate layer `localisation/replace` не доказаны без runtime activation.
- Descriptor dependency order, launcher order, filesystem discovery order и effective order остаются отдельными величинами.
- Synthetic deterministic candidate не доказывает game load, activation, uninstall или rollback.
- M1A не проверял hard crash durability/fsync на active filesystem и не имеет права менять launcher/active paths.
- Narrowed profile блокирует unknown input, но не разрешает production transform до M2.
- Census покрывает official installation и Workshop, но не follow private paths десяти local outer descriptors.
- Найденный active-load document valid, но содержит ноль enabled mods; это не evidence modded playset order.
- Launcher database не обнаружена в auto-discovered standard roots; unknown path/schema не угадывались.
- Strict version adapter не смог связать local launcher-settings schema с точными public fields; M0R version evidence остаётся отдельным источником, а collector status — blocker.
- Automated leakage check не покрывает произвольные короткие partial substrings; exact-line/value checks и полный staged diff review образуют дополнительную границу.
- Candidate protocol не сертифицирован против произвольного concurrent same-UID adversary или power-loss; доказаны deterministic process-level fault points в private disposable root.
- Final report-level decision ещё требует owner review; он не является M1A acceptance автоматически.

## 15. Warnings и blockers

Warnings:

- profile привязан к одному датированному Mac/game build и invalidates при version, launcher schema, source generation или new taxonomy;
- ignored sanitized artifact полезен только как audit aid и не заменяет tracked report;
- research helper намеренно консервативен и не должен стать production parser shortcut.

Blockers:

Sanitized collector codes: `DEPENDENCY_GRAPH_UNPROVEN`, `EFFECTIVE_LOAD_ORDER_UNPROVEN`, `EXPORT_POLICY_UNRESOLVED`, `FORMAT_PROFILE_HAS_BLOCKERS`, `GAME_VERSION_UNVERIFIED`, `LAUNCHER_DB_METADATA_UNAVAILABLE`, `LOCAL_SOURCE_CONTENT_NOT_FOLLOWED`, `REPLACE_LAYER_SEMANTICS_UNPROVEN`.

1. Публичные sources не определяют complete current-version load-order/collision contract.
2. Current active-load metadata не содержит enabled mods; launcher DB не найдена, strict version schema не подтверждена, а private paths десяти local descriptors не follow-ились.
3. Dependencies присутствуют, но graph identity/cycles/missing semantics не доказаны; `localisation/replace` обнаружен, но current-version precedence остаётся неизвестной.
4. Conservative format profile имеет unsupported/opaque events; byte-preservation не разрешает их transform.
5. Read-only metadata не может доказать effective engine winner для обычных cross-mod duplicate localisation keys.
6. Ни `per-source`, ни `playset-bundle`, ни `hybrid` нельзя выбрать без guess либо candidate activation; activation запрещена scope этой задачи.
7. Следовательно deterministic candidate layout доказан только как disposable synthetic protocol, не как безопасный game export policy.

`BLOCKED` является полноценным завершением исследовательского M1A report: export policy явно оставлена unresolved. Эти blockers не ослабляют source/containment/round-trip evidence, но не удовлетворяют отдельный `M1A: GO` gate для перехода к M2.

## 16. Следующий разрешённый шаг

Владелец может review/accept этот честный M1A evidence report и оставить format-ветвь заблокированной. M1B остаётся независимым разрешённым evidence milestone, но не выполнялся в этой задаче. Для снятия blocker нужен отдельный будущий M1A decision/experiment с явным scope, который versioned evidence докажет effective 4.4.6 collision/load-order behavior; эта задача не запрашивает и не получает разрешения активировать candidate.

M2 запрещён до одновременно принятого `M1A: GO` и принятого `M1B: QUALITY_FEASIBLE`. После draft PR следующая операция здесь — только owner review; M1B/M2 не начинаются автоматически.

VERDICT: BLOCKED
