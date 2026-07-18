# M1A hardening revalidation — 18 июля 2026 года

- Статус: `M1A — BLOCKED`
- Разрешённый слой: M1A research harness, synthetic fixtures/tests, contracts и privacy-safe aggregate evidence
- Вне scope: M1B, M2, translation, Ollama, game/launcher start, activation, publish и любые записи в source/Workshop/game/launcher/active paths

## 1. Git provenance и recovery

| Поле | Значение |
|---|---|
| Merged evidence PR | [PR #3](https://github.com/elenandar/Stellaris-mod-translator/pull/3) |
| Merge commit / `origin/main` at preflight | `2b51879d8e358cf5412f3a6792f33c71ae79d863` |
| Разрешённый pre-recovery HEAD | `4353cfd97ccfd1df422e57cbe0b379768b431b60` |
| Recovery branch, local-only | `recovery/m1a-uncommitted-20260718` |
| Immutable recovery commit | `7e91918a942bc3ce49c6c0b476bc579b57f862af` |
| Follow-up branch | `agent/m1a-hardening-followup` |

Перед recovery committed trees исходного HEAD и `origin/main` совпали. Пять
разрешённых worktree blobs совпали с owner-provided identities, были сохранены
отдельным неизменяемым commit без предварительного редактирования и затем
cherry-pick в follow-up от `origin/main`. Recovery и первоначальный follow-up
trees совпали как `e09e2c93c1bdddc61e4bf9ace83069dc99664b09`.

## 2. Hardening delta

- Исправлена рассинхронизация: control-bearing line, которую `inspect_bytes()`
  относит к opaque/unknown, больше не может добавить key hash в same-source либо
  cross-source duplicate statistics.
- Один shared fail-closed line-codepoint guard применяется к inventory и key
  extraction. Regression включает NUL, другие C0/C1 classes, unsupported line
  separators, CR/LF/CRLF boundaries и обязательный separator перед quoted value.
- Collector сопоставляет preflight inode с фактически открытым descriptor и
  отвергает hardlink identity aliases как в первом, так и во втором observation.
- Snapshot/manifest provenance, partial writes, disk-full, final `fsync`, static
  repository symlinks и manifest-last semantics покрыты synthetic tests.
- Complete-manifest validation пересчитывает content `generation` из payload
  size/SHA-256; согласованный, но не связанный с bytes generation отвергается.
- `source_order.position` теперь принимает только exact integer, исключает
  `bool`/float и требует непрерывный диапазон `0..file_count-1`.
- Malformed `SnapshotBlob` проверяется до path processing и первой write:
  immutable bytes, inventory, observer/content generations и strict scalar
  types либо controlled `SNAPSHOT_BLOB_MISMATCH` при пустом candidate root.
- Leakage fingerprints создаются до role-specific parsing для каждого
  observed private input: exact nonempty whole-file, physical-line и long-token
  fingerprints покрывают localisation, descriptor, active-load, version,
  launcher DB и Steam discovery metadata. Invalid UTF-8 остаётся byte-level.
- Public language-header exception ограничена первой localisation line после
  optional BOM; metadata и последующие header-shaped lines не исключаются.
- Отдельный BOM-backed `bare-cr` fixture подтверждает byte-identical round trip;
  CR остаётся самостоятельным transform blocker, а `mixed` означает два или
  более вида из CR, LF и CRLF.
- Защита от arbitrary concurrent same-UID path/ancestor substitution не
  заявляется: discovery и repository walk ещё не descriptor-rooted. Это остаётся
  явным blocker, а не скрытым safety claim.

## 3. Public schema decision

Additive-compatibility policy для collector v1 отсутствовала, а public output
получил same-source cross-file duplicate fields и новые обязательные blockers.
Поэтому collector schema повышена до `m1a-local-redacted-evidence-v2`.
Candidate, content-generation и Markdown-validator schemas не менялись.

Новые leakage поля финализируются внутри ещё не merged schema v2, а не требуют
механического v3. Exact public shape содержит только counts/booleans:
`checked_repository_files`, `private_input_file_count`,
`nonempty_private_input_file_count`, `source_file_fingerprint_count`,
`source_line_fingerprint_count`, `source_token_fingerprint_count`,
`private_identifier_count`, `match_count`, `exact_file_match_count`,
`exact_line_match_count`, `token_match_count`, `private_value_match_count`,
`passed`, `minimum_line_bytes`, `minimum_token_bytes`. Fingerprint counts —
unique digests, не occurrences; сами digests и совпавшие данные не публикуются.

Duplicate metrics имеют три пересекающиеся оси:

1. intra-file groups/occurrences в `inventory`;
2. same-source cross-file groups/occurrences в `duplicates`;
3. cross-source groups/occurrences в `duplicates`.

Их нельзя суммировать; они не являются partition и не доказывают collision
winner. Аналогично, два равных последовательных manifests доказывают только
observed pre/post equality, но не атомарную cross-file generation.

## 4. Final validation

| Проверка | Результат |
|---|---|
| Synthetic fixture cases | `27` |
| `python3 -m unittest discover -s tools/research/tests -v` | `67/67 passed` |
| `python3 tools/research/validate_m1a_docs.py` | passed; 24 Markdown files, 15 fenced blocks, 38 tables, 41 relative links, 0 errors |
| `git diff --check` | `passed` |
| Path-free `m1a_local_probe.py collect` | schema v2, `status=ok`; полный blocker set сохранён |
| Leakage check | `passed=true`, `match_count=0` |

Write evidence имеет буквальное field-to-value mapping:

| Public field | Final value | Граница утверждения |
|---|---:|---|
| `containment.source_write_attempts` | `0` | зарегистрированные game и Workshop source roots |
| `containment.launcher_write_attempts` | `0` | launcher protected roots |
| `containment.active_path_write_attempts` | `0` | Documents/active protected roots |
| `launcher.source_writes` | `0` | launcher metadata/database имеет только read entrypoints |
| `candidate.active_path_writes` | `0` | candidate writes ограничены disposable roots |

Это protocol-level counters/claims об отсутствии write entrypoints, а не
OS-wide syscall audit. Synthetic candidate действительно пишет payload/manifest
только в disposable root.

## 5. Sanitized local evidence v2

Полный fixed-schema JSON хранится только в ignored
`artifacts/m1a/m1a-local-redacted-evidence-v2-2026-07-18-pr4-remediation-final.json`.
Ни raw corpus, ни private/source filenames или paths, ни private/source
localisation keys или values в Git или PR не сохраняются. Repository-relative
и synthetic fixture paths/keys/values намеренно разрешены.

| Поле | Aggregate result |
|---|---|
| Schema / collector status | `m1a-local-redacted-evidence-v2` / `ok` |
| Corpus files / bytes | `7 971` / `302 663 879` |
| Observed files including metadata | `8 098` |
| Round-trip pass / failure | `7 971` / `0` |
| Pre/post manifests equal | `true` |
| Content/topology generation SHA-256 | `a19929ef0ed147066fe193dfc9acde31e6059a5589a7d7f94494726ed2415f21` |
| Intra-file duplicate groups / occurrences | `973` / `2 050` |
| Same-source cross-file groups / occurrences | `283 704` / `2 746 988` |
| Cross-source groups / occurrences | `2 804` / `35 174` |
| Synthetic candidate manifest / tree SHA-256 | `46f50f997b9ac46024d5f94213319fe1f8005eba88e960788b6c78d84e804dfb` / `7718d952a307f7e77de375079e65907b971bcd24f063e4353ea5fed073f48225` |
| Leakage passed / match count | `true` / `0` |
| Leakage private inputs / nonempty inputs | `8 098` / `8 098` |
| Whole-file / line / token fingerprints | `8 083` / `2 057 356` / `51 992` unique digests |
| Parsed private/path identifiers | `16 402` |
| Checked repository files | `41` |
| Blockers | `CONCURRENT_SAME_UID_PATH_RACE_UNPROVEN`, `CROSS_FILE_GENERATION_COHERENCE_UNPROVEN`, `DEPENDENCY_GRAPH_UNPROVEN`, `EFFECTIVE_LOAD_ORDER_UNPROVEN`, `EXPORT_POLICY_UNRESOLVED`, `FORMAT_PROFILE_HAS_BLOCKERS`, `GAME_VERSION_UNVERIFIED`, `LAUNCHER_DB_METADATA_UNAVAILABLE`, `LOCAL_SOURCE_CONTENT_NOT_FOLLOWED`, `REPLACE_LAYER_SEMANTICS_UNPROVEN` |

`status=ok` означает только успешное завершение aggregate collection. Наличие
blockers сохраняет gate verdict `M1A: BLOCKED`.

## 6. Final repository identities

Hashes ниже вычисляются только после стабилизации всех соответствующих bytes.
Сам addendum намеренно не включает self-hash; final Git commit идентифицирует
полный tracked tree.

| Artifact | SHA-256 |
|---|---|
| `tools/research/README.md` | `375b93dabaa452bab8ac7811038396029f3b2bb32fd982083ab4434b796044ec` |
| `tools/research/m1a_harness.py` | `cf4864be4925d99ce7b12074059eae6a446b788f1d5b294f7474bbc465e8b369` |
| `tools/research/m1a_local_probe.py` | `27109cfa6177fa8c49c026c2488a67d3f6443a11b4aee9e0328f4d90e998b264` |
| `tools/research/validate_m1a_docs.py` | `b3a8fa04b3f30e8653d0f18aa9be286e0601259856e7f7e3c5db7d4bf3dba445` |
| `tools/research/tests/test_m1a_harness.py` | `88dfc79bf720b915e38212b7dc7edbac773420b195b45d28da63599a949f27bc` |
| `tools/research/tests/test_m1a_local_probe.py` | `f2b60a31664d9d9a801fba5a4712ecb7ec5a34b985112e99fe82c9cf2b724d30` |
| `fixtures/m1a/README.md` | `dc982347668856f253e59e7fcf3c1fce9c7c52bb0a19aa9f161b591f74012ed9` |
| `fixtures/m1a/format-cases.json` | `1a20edc6c4c593ca7aeee4bfa2deae331198cb5c73bc01f3dc7be7b27693e4f4` |
| `fixtures/m1a/candidate/source-a.yml` | `7415c2b73b95b8fc47e6a800b521d8fc4d93d5acfcf23ab1274f33efc2380e67` |
| `fixtures/m1a/candidate/source-b.yml` | `680056eea5ea772a7301942d43e65af5295bac5f6ba562e2686e3573599c4148` |
| `docs/evidence/m1a-format-playset-2026-07-17.md` | `59a5eede28c334c33017c6dca010e74284b15453162226265f6002325bdc948b` |

## 7. Остаточные blockers и следующий gate

Обязательные blockers включают недоказанные atomic cross-file generation,
effective engine load order/collision winner, export policy и arbitrary
concurrent same-UID path-race protection. Fresh collector может добавить другие
controlled blocker codes для текущего локального environment.

M2 запрещён. После публикации draft follow-up PR разрешён только owner review и
отдельное решение о минимальном новом evidence, необходимом для будущего M1A
gate. M1B остаётся независимым evidence milestone и не меняет этот verdict.

VERDICT: BLOCKED
