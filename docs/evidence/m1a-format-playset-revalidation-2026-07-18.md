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
- Защита от arbitrary concurrent same-UID path/ancestor substitution не
  заявляется: discovery и repository walk ещё не descriptor-rooted. Это остаётся
  явным blocker, а не скрытым safety claim.

## 3. Public schema decision

Additive-compatibility policy для collector v1 отсутствовала, а public output
получил same-source cross-file duplicate fields и новые обязательные blockers.
Поэтому collector schema повышена до `m1a-local-redacted-evidence-v2`.
Candidate, content-generation и Markdown-validator schemas не менялись.

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
| Synthetic fixture cases | `26` |
| `python3 -m unittest discover -s tools/research/tests -v` | `60/60 passed` |
| `python3 tools/research/validate_m1a_docs.py` | `passed`; 24 Markdown files, 42 relative links, 15 fenced blocks, 37 tables, 0 errors |
| `git diff --check` | `passed` |
| Path-free `m1a_local_probe.py collect` | schema v2, `status=ok`; полный blocker set сохранён |
| Leakage check | `passed=true`, `match_count=0` |
| Source/Workshop/game/launcher/active-path writes | `0 / 0 / 0 / 0` |

## 5. Sanitized local evidence v2

Полный fixed-schema JSON хранится только в ignored
`artifacts/m1a/m1a-local-redacted-evidence-v2-2026-07-18-final-reviewed.json`. Ни raw corpus,
ни filenames/paths, ни localisation keys/values в Git или PR не сохраняются.

| Поле | Aggregate result |
|---|---|
| Schema / collector status | `m1a-local-redacted-evidence-v2` / `ok` |
| Corpus files / bytes | `7 971` / `302 663 879` |
| Observed files including metadata | `8 098` |
| Round-trip pass / failure | `7 971` / `0` |
| Pre/post manifests equal | `true` |
| Content/topology generation SHA-256 | `aa64e51eb9ff06921ef4e21a4fdfb5ceb46745f3622690d0726cd0a55cfdb559` |
| Intra-file duplicate groups / occurrences | `973` / `2 050` |
| Same-source cross-file groups / occurrences | `283 704` / `2 746 988` |
| Cross-source groups / occurrences | `2 804` / `35 174` |
| Synthetic candidate manifest / tree SHA-256 | `46f50f997b9ac46024d5f94213319fe1f8005eba88e960788b6c78d84e804dfb` / `7718d952a307f7e77de375079e65907b971bcd24f063e4353ea5fed073f48225` |
| Leakage passed / match count | `true` / `0` |
| Blockers | `CONCURRENT_SAME_UID_PATH_RACE_UNPROVEN`, `CROSS_FILE_GENERATION_COHERENCE_UNPROVEN`, `DEPENDENCY_GRAPH_UNPROVEN`, `EFFECTIVE_LOAD_ORDER_UNPROVEN`, `EXPORT_POLICY_UNRESOLVED`, `FORMAT_PROFILE_HAS_BLOCKERS`, `GAME_VERSION_UNVERIFIED`, `LAUNCHER_DB_METADATA_UNAVAILABLE`, `LOCAL_SOURCE_CONTENT_NOT_FOLLOWED`, `REPLACE_LAYER_SEMANTICS_UNPROVEN` |

`status=ok` означает только успешное завершение aggregate collection. Наличие
blockers сохраняет gate verdict `M1A: BLOCKED`.

## 6. Final repository identities

Hashes ниже вычисляются только после стабилизации всех соответствующих bytes.
Сам addendum намеренно не включает self-hash; final Git commit идентифицирует
полный tracked tree.

| Artifact | SHA-256 |
|---|---|
| `tools/research/README.md` | `36f5608df277669409d6b02963571903df5c642e0e3485ec3d116be8b6415388` |
| `tools/research/m1a_harness.py` | `63484a4ebfb2bca6f795bf6e5a5728a7449b039ed8adf0069aace63c29d1d49a` |
| `tools/research/m1a_local_probe.py` | `f02f04ceced2edda9c625041f3e15bdccb1cda37c7b07ce4a6e71fda2fb168ae` |
| `tools/research/validate_m1a_docs.py` | `b3a8fa04b3f30e8653d0f18aa9be286e0601259856e7f7e3c5db7d4bf3dba445` |
| `tools/research/tests/test_m1a_harness.py` | `9b811db692ff313fbb917e35cac37dcbbd0bc88e2a7ae7d1267529ebbc35849b` |
| `tools/research/tests/test_m1a_local_probe.py` | `47736e02554154cde6abbdfe9308322da0b22eba5c317d9b2d83a6c548438667` |
| `fixtures/m1a/README.md` | `e1f3bc59f6ee17c921e8d51122e842b10769f638478376bfcb2e923faac1b6b8` |
| `fixtures/m1a/format-cases.json` | `55d575c70f66d5036ed9f8b667de4dc9e1b4125ddc64c8f12405d552ba67d53a` |
| `fixtures/m1a/candidate/source-a.yml` | `7415c2b73b95b8fc47e6a800b521d8fc4d93d5acfcf23ab1274f33efc2380e67` |
| `fixtures/m1a/candidate/source-b.yml` | `680056eea5ea772a7301942d43e65af5295bac5f6ba562e2686e3573599c4148` |
| `docs/evidence/m1a-format-playset-2026-07-17.md` | `f392814865748c738f055243756651d64104788bc5fae2c065977f267dfc0aba` |

## 7. Остаточные blockers и следующий gate

Обязательные blockers включают недоказанные atomic cross-file generation,
effective engine load order/collision winner, export policy и arbitrary
concurrent same-UID path-race protection. Fresh collector может добавить другие
controlled blocker codes для текущего локального environment.

M2 запрещён. После публикации draft follow-up PR разрешён только owner review и
отдельное решение о минимальном новом evidence, необходимом для будущего M1A
gate. M1B остаётся независимым evidence milestone и не меняет этот verdict.

VERDICT: BLOCKED
