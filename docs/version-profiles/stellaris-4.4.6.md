# Version profile: Stellaris 4.4.6

- Profile ID: `stellaris-4.4.6`
- Статус: `M1A — BLOCKED`; evidence PR #3 merged, transformation/export не разрешены
- Исходная дата evidence: 17 июля 2026 года
- Hardening revalidation: 18 июля 2026 года
- Game version: `Pegasus v4.4.6 (fdde)`
- Platform: Apple Silicon `arm64`, macOS `26.5.2` (`25F84`)

## Provenance

Версия и environment наблюдались локально в [датированном M0R inventory](../evidence/local-environment-2026-07-17.md). Официальный [анонс Stellaris 4.4.6](https://steamcommunity.com/games/281990/announcements/detail/689761349249538499) подтверждает hotfix `4.4.6` с checksum `fdde` от 9 июля 2026 года.

Эти два источника подтверждают identity версии, но не grammar/load-order contract. [Paradox-hosted localisation guide](https://stellaris.paradoxwikis.com/Localisation_modding) используется только как candidate taxonomy: части страницы помечены как проверенные на более старой версии. Profile принимает конструкцию лишь после synthetic fixture, expected classification и локального aggregate census.

Исходные hashes helper, fixture tree, sanitized run и report от 17 июля сохранены как исторический snapshot ниже. Текущие schema v2 identities и результаты hardening фиксируются в [revalidation от 18 июля](../evidence/m1a-format-playset-revalidation-2026-07-18.md); raw source paths, per-file corpus hashes и corpus bytes не публикуются.

## Scope roots

Profile различает identities, а не сохраняет абсолютные пути:

| Root role | Доступ | Output evidence |
|---|---|---|
| game localisation | read-only | count/bytes/generation digest |
| Workshop sources | read-only | count/bytes/opaque source generation digest |
| launcher/playset metadata | read-only stable byte read | schema flags/counts/order digest либо blocker |
| accepted generation | immutable per-file bytes только в process memory | два последовательных aggregate content/topology digest; equality не доказывает atomic cross-file snapshot |
| research candidate | отдельный disposable root | logical manifest/tree digest; удаляется после run |
| repository | только M1A docs/helper/synthetic fixtures | normal Git diff после leakage check |

Equality, ancestor/descendant overlap, symlink/device-inode alias, unresolved traversal и ambiguous case/Unicode identity блокируются до write. Если future disk snapshot появится, он обязан быть отдельным root; M1A пишет только flat synthetic candidate.

## Byte и record profile

| Feature | Research classification | Profile disposition |
|---|---|---|
| UTF-8 BOM at offset 0 | `bom_start` | required для future transform eligibility; exact round trip |
| missing BOM | `bom_missing` | exact round trip, blocker |
| interior `U+FEFF` | `hidden_bom` | exact round trip, blocker |
| invalid UTF-8 | `utf8_invalid` | whole-file opaque blocker |
| LF | `newline_lf` | classified exact |
| CRLF | `newline_crlf` | classified exact |
| bare CR | `newline_cr` | byte-identical round trip, transform blocker |
| два или более вида из CR, LF и CRLF | `newline_mixed` | exact round trip, blocker |
| missing final newline | `final_newline_missing` | classified exact; отсутствие сохраняется |
| first-line language header | `language_header` | required; value не публикуется из private corpus |
| comments/blank/space/tab | aggregate line classes | whole-file bytes exact; record objects не materialize |
| quoted entry | `entry` | classified exact only при однозначных boundaries |
| optional decimal suffix | `version_present` / `version_absent` | оба сохраняются; prevalence — aggregate evidence |
| empty quoted value | `empty_value` | occurrence сохраняется |
| duplicate key | aggregate group/occurrence count | raw file order сохраняется; positions/winner не определяются |
| malformed/unknown line | aggregate counter | opaque blocker, no repair; per-record codes остаются M2 |

Format contract полностью определён в [localisation-format.md](../specs/localisation-format.md). `classified exact` не означает permission to translate.
Physical line boundaries существуют только для CR, LF и CRLF; Unicode/legacy
separators не разделяют records. `mixed` означает любую комбинацию двух или
более из этих трёх newline kinds.

## Markup profile

| Atom | Envelope | Disposition |
|---|---|---|
| localisation reference | `$...$` | balanced count только для nonempty ASCII `[A-Za-z0-9_.:-]+` payload |
| scripted/dynamic localisation | `[...]` | тот же narrow payload; execution semantics unknown |
| icon | `£...£` | тот же narrow payload; asset existence unknown |
| formatting | `§X ... §!` | only fixture-backed code allowlist; balance required |
| escaped newline/tab/quote/backslash | backslash sequence | exact atom only для fixture-backed sequences |
| ordinary human candidate | UTF-8 outside recognized atoms | conceptual only; helper не возвращает spans; no M1A mutation |

Public guide также описывает `\t`, `[[` и icon frame syntax; до отдельного fixture/scanner rule они остаются candidate/unknown, а не принимаются по документации старой версии. Полная taxonomy и malformed policy находятся в [markup-taxonomy.md](../specs/markup-taxonomy.md).

## Descriptor и playset profile

[Paradox-hosted modding docs](https://stellaris.paradoxwikis.com/Modding) перечисляют descriptor fields `name`, `path`, `dependencies`, `picture`, `tags`, `version`, `supported_version`, `remote_file_id`; [tutorial](https://stellaris.paradoxwikis.com/Modding_tutorial) различает внешний `.mod` и внутренний `descriptor.mod`. В M1A значения этих полей никогда не публикуются.

| Feature | M1A treatment |
|---|---|
| descriptor field presence | aggregate count/boolean |
| source identity/path | internal only; published as opaque ID |
| dependency | aggregate field/value counts only; identity/cycle/missing semantics не интерпретируются и дают blocker |
| `supported_version` | compatibility indicator only; не разрешает load |
| `localisation/replace` | отдельный directory-layer observation |
| descriptor `replace_path` | отдельный field; не отождествляется с `localisation/replace` |
| launcher playset/order | read-only sanitized digest; schema semantics должны быть доказаны отдельно |
| effective engine collision winner | unsupported/unproven в текущем profile |

[Paradox Helpdesk](https://support.paradoxplaza.com/hc/en-us/articles/360020841079-My-Mods-or-Playsets-are-not-showing-up-in-the-Launcher) подтверждает `launcher-v2.sqlite`, но не документирует schema. Сам факт чтения numeric position не превращается в versioned engine rule.

## Workshop generation

[Steamworks](https://partner.steamgames.com/doc/features/workshop/implementation) документирует auto-update и removal после unsubscribe. Profile поэтому не считает Workshop directory immutable. M1A принимает фактически прочитанные per-file bytes только в память и делает whole-run clean abort при обнаруженном identity/size/content/topology mismatch. Два равных последовательных manifest не исключают transient/ABA cross-file change, поэтому `CROSS_FILE_GENERATION_COHERENCE_UNPROVEN` остаётся blocker; future content-addressed disk copy потребует отдельного contract. Steam install/download order не является playset/load order.

## Candidate/export profile

- Research policy ID: `synthetic-only`.
- Logical layout и manifest: [artifact-and-publish-contract.md](../specs/artifact-and-publish-contract.md).
- `per-source`, `playset-bundle` и `hybrid` не выбраны.
- Active game path, launcher mutation, activation, smoke, uninstall и rollback не выполнялись.
- Любой real candidate остаётся запрещён до принятого export policy и следующих milestone gates.

## Explicit unsupported space

Profile fail closed для:

- любого markup/escape, не имеющего fixture и expected classification;
- malformed quoting, multiline quoted value, hidden BOM, invalid UTF-8, bare CR и mixed newline;
- неизвестного descriptor/launcher schema и любой dependency graph, пока identity/cycle/missing semantics не доказаны;
- ambiguous path identity, hardlink alias или duplicate relative path;
- arbitrary concurrent same-UID path/ancestor substitution, пока traversal и authorization не descriptor-rooted;
- atomic cross-file source generation, пока нет snapshot/lock/source-generation contract;
- cross-mod duplicate без доказанного effective winner;
- interaction `replace_path`/`localisation/replace`/playset order без current-version evidence;
- active publish, game smoke и rollback;
- любой другой game version, launcher schema/version или platform.

## Invalidation triggers

Profile и все candidate manifests становятся stale при любом событии:

1. game version/checksum отличается от `4.4.6 (fdde)`;
2. launcher либо его schema меняется;
3. меняется source generation, descriptor, dependency graph или playset order digest;
4. census обнаруживает новую category/diagnostic;
5. helper/fixture expected manifest меняется;
6. platform filesystem behavior не соответствует containment assumptions;
7. public documentation не совпадает с local evidence;
8. export policy получает новое owner decision.

После invalidation нужен новый sanitized census и full regression suite. Silent fallback на ближайший profile запрещён.

## Initial evidence identities — 17 июля 2026 года

Все identities ниже относятся только к исходному privacy-safe validation run 17 июля и не описывают текущие worktree bytes после hardening. Local generation и candidate identities имеют domain-separated schema, описанную в research contracts; raw paths и per-source hashes не публикуются. Актуальные final identities публикуются только в датированном revalidation после стабилизации всех bytes.

| Artifact | SHA-256 / identity |
|---|---|
| Base commit | `8d468b7b8ca1f748dda8c072ce02933b15656dc2` |
| `tools/research/README.md` | `c51b4d34c35a1ccbac121367eafaf3a528cdd105a3c7662452355e87e27ec293` |
| `tools/research/__init__.py` | `5fc98b0e6e79b554196f3bef4363eb215895570a518fcef73f4581dcb3435ce7` |
| `tools/research/m1a_harness.py` | `e9537184730a86a23aec07475e8f54a0c3b2d62c4907f72e8a25b6fbde342821` |
| `tools/research/m1a_local_probe.py` | `39170f3f12d6a98ba39d56b7695c8cdca70fca891c8fe780247917fcd80aacbb` |
| `tools/research/validate_m1a_docs.py` | `b3a8fa04b3f30e8653d0f18aa9be286e0601259856e7f7e3c5db7d4bf3dba445` |
| `tools/research/tests/__init__.py` | `8050e3e039146c664a8069e152f58943155e31ac22983679641af43b26a7cec5` |
| `tools/research/tests/test_m1a_harness.py` | `514a16ff356425a9d731f209db9aeab1ed039049efadeceb577961333da91a88` |
| `tools/research/tests/test_m1a_local_probe.py` | `441ef3ae003d6d243d95fabe921379a1731f12136c06b29cb1eaa662db1e94ae` |
| `fixtures/m1a/README.md` | `6e4efd8745429890b7c6e4abf9fa5f0e65e8ba8c687790c65292c97431464bdd` |
| `fixtures/m1a/format-cases.json` | `03328dfb6835c673a2821147aacf9767faa3a6d1665b14b78233f166e0cc1c05` |
| `fixtures/m1a/candidate/source-a.yml` | `7415c2b73b95b8fc47e6a800b521d8fc4d93d5acfcf23ab1274f33efc2380e67` |
| `fixtures/m1a/candidate/source-b.yml` | `680056eea5ea772a7301942d43e65af5295bac5f6ba562e2686e3573599c4148` |
| Sanitized local content/topology generation | `aa64e51eb9ff06921ef4e21a4fdfb5ceb46745f3622690d0726cd0a55cfdb559` |
| Synthetic candidate manifest | `46f50f997b9ac46024d5f94213319fe1f8005eba88e960788b6c78d84e804dfb` |
| Independently observed synthetic candidate tree | `7718d952a307f7e77de375079e65907b971bcd24f063e4353ea5fed073f48225` |
| `docs/evidence/m1a-format-playset-2026-07-17.md` | `59a5eede28c334c33017c6dca010e74284b15453162226265f6002325bdc948b` |

Текущий набор identities и schema decision: [M1A hardening revalidation, 18 июля 2026 года](../evidence/m1a-format-playset-revalidation-2026-07-18.md).
