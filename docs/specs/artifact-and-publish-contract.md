# Контракт candidate artifact и publish boundary

- Статус: `M1A — BLOCKED`; evidence PR #3 merged, hardening revalidation in review
- Export policy: **не выбрана**
- Active publish: **не исследовался и запрещён этой задачей**

## Что именно доказуемо в M1A

M1A может построить только synthetic candidate в новом disposable root, сравнить повторные сборки и удалить созданный root. Это доказывает воспроизводимость builder protocol, но не загрузку candidate игрой, не precedence duplicate keys и не безопасность launcher activation.

Public evidence ограничено:

- [Paradox-hosted localisation guide](https://stellaris.paradoxwikis.com/Localisation_modding) описывает `localisation/replace` как поздний слой для duplicate keys, но страница не является versioned grammar 4.4.6;
- [Paradox-hosted modding guide](https://stellaris.paradoxwikis.com/Modding) описывает descriptor `dependencies`, но предупреждает, что общий load order недокументирован, изменяем и имеет разные стратегии по типам данных;
- [Paradox Helpdesk](https://support.paradoxplaza.com/hc/en-us/articles/360020841079-My-Mods-or-Playsets-are-not-showing-up-in-the-Launcher) подтверждает playsets и `launcher-v2.sqlite`, но не документирует schema/order semantics;
- [Steamworks Workshop documentation](https://partner.steamgames.com/doc/features/workshop/implementation) подтверждает автоматические updates/removal lifecycle, но не обещает атомарный filesystem snapshot.

Поэтому launcher order, dependency edges, directory discovery order, `localisation/replace`, descriptor `replace_path` и effective engine winner являются отдельными evidence fields. Ни одно не подменяет другое.

## Root containment

До любой записи collector регистрирует как protected roots обнаруженные game,
Workshop, Documents/active и launcher roots; synthetic candidate builder отдельно
добавляет fixture root. Private local-mod `path` values M1A намеренно не follow-ит,
поэтому их content roots не заявляются защищёнными или прочитанными. Candidate
output — отдельный sealed disposable write root, а не ещё один protected input.
M1A не создаёт raw snapshot на диске; отдельный snapshot root в этом разделе
является только будущим условным требованием. Для каждого существующего root
выполняются:

1. absolute lexical validation: пустой path, NUL и unresolved `..` отклоняются;
2. canonical resolution существующих ancestors без следования создаваемому leaf;
3. equality и ancestor/descendant comparison в обоих направлениях;
4. symlink alias и `samefile`/device-inode comparison для существующих objects;
5. case-fold/Unicode-normalization collision check для зарегистрированных path identities;
6. повторная проверка перед file creation и после protocol checkpoints.

Ambiguous identity блокирует run. Builder никогда не выбирает «наиболее вероятный» root. Если future disk snapshot появится, snapshot и candidate должны быть разными sibling disposable roots. В M1A accepted bytes остаются только в памяти.

## Research candidate layout

Единственный проверяемый layout M1A не является принятым game layout:

```text
candidate-root/
  payload-000000.bin
  payload-000001.bin
  manifest.json
```

- Candidate root создаётся и удаляется владельцем `TemporaryDirectory`; helper не имеет cleanup API для произвольного path.
- Payload в M1A создаётся только из synthetic fixture bytes. Physical layout намеренно плоский: это не game-ready tree и не accepted export layout.
- Logical relative paths хранятся только в manifest и заранее проверены на strict UTF-8 encodability, traversal, ancestry/type conflict, casefold и Unicode-normalization collisions. Unpaired surrogate отклоняется как controlled `INVALID_RELATIVE_PATH` до source read, candidate layout и write; корректный non-ASCII UTF-8 не запрещается. Physical storage names генерируются builder-ом.
- `manifest.json` записывается canonical JSON после payload и является единственным completion marker.
- Candidate без manifest, с staged manifest, лишним file, несовпадающим manifest или неизвестным schema считается incomplete и не может перейти к publish.

Случайное имя внешнего temporary root исключается из logical artifact digest. Реальный future builder обязан заменить этот research layout отдельным versioned export profile; наличие `.yml` само по себе не делает artifact допустимым для игры.

## Manifest schema

Logical manifest содержит только sanitized/provenance поля:

```json
{
  "schema": "m1a-research-candidate-v1",
  "profile_id": "stellaris-4.4.6-research",
  "policy_id": "synthetic-only",
  "source_order_digest": "<sha256-hex>",
  "source_order": [
    {"position": 0, "opaque_id": "src-<hex>", "generation": "<hex>"}
  ],
  "files": [
    {"logical_path": "localisation/opaque-a.yml", "storage": "payload-000000.bin", "size": 0, "sha256": "<hex>", "source": "src-<hex>", "generation": "<hex>"}
  ],
  "file_count": 1
}
```

Canonical encoding — UTF-8 without BOM, sorted object keys, compact separators и final LF. Запрещены timestamps, absolute/private paths, mod names, raw localisation keys/values, nondeterministic directory order и ambient locale. Arrays, где порядок семантичен, уже должны быть расположены по explicit source order; остальные сортируются по stable tuple.

Поле `generation` в synthetic candidate — domain-separated content identity из byte size и SHA-256 уже принятого stable read. Candidate `opaque_id` — отдельный domain-separated SHA-256 нормализованного synthetic logical path. Device/inode/mtime/ctime и absolute-path-derived observer ID входят только в source observation/snapshot digest, который обнаруживает replacement, relocation или metadata drift между source passes; они намеренно не входят в logical artifact. Поэтому одинаковые immutable bytes/logical paths/order/policy дают тот же manifest после безвредного metadata churn или relocation checkout, но текущий read всё равно целиком прерывается при observer mismatch. Изменение bytes меняет и content identity, и payload hash.

Collision record может содержать только opaque key ID, ordered opaque source IDs и disposition. `implicit_winner` запрещён: разрешены `blocked` либо future `explicit_owner_decision` с provenance.

## Build protocol и fault points

1. Verify roots и создать новый empty candidate root.
2. Проверить immutable input generation и explicit source order.
3. Отклонить не кодируемые строго в UTF-8, duplicate либо ambiguous relative paths до первого source read и candidate layout/write; semantic key collisions остаются отдельным export-policy blocker.
4. Писать плоские payload names только непосредственно через sealed root descriptor, exclusive create и `O_NOFOLLOW` там, где его предоставляет platform; nested output directories запрещены M1A protocol.
5. Перечитать фактические payload bytes через root descriptor, отклонить hardlinks/extra entries и вычислить отдельный observed payload-tree hash.
6. На partial write/disk-full/process crash оставить root incomplete; silent retry внутри того же logical build запрещён.
7. Записать staged canonical manifest, снова проверить payload tree, затем переименовать manifest последним и `fsync` root descriptor.
8. После commit перечитать manifest и payload tree, пересчитать каждый content `generation` из заявленных `size` и payload SHA-256; при повторном вызове complete candidate полностью сверить actual bytes без rewrite.
9. Повторить сборку в другом disposable root и сравнить независимые manifest и payload-tree hashes.

M1A fault injection проверяет process-stop ordering и выполняет file/root `fsync`, но не является power-loss certification. Last-known-good и active switch относятся к M3. Теоретическая гонка с произвольным concurrent same-UID process остаётся residual threat; M1A candidate root должен быть private disposable root.

## Source order contract

Допустимый future order должен состоять из explicit records:

```text
playset position
opaque source identity
immutable generation hash
dependency constraints
launcher-enabled flag
effective-engine-order evidence version
```

Future production builder должен блокироваться при duplicate position, missing source, dependency cycle, order/dependency contradiction, unknown disabled state, generation mismatch или отсутствии доказанного effective winner для collision. M1A helper фиксирует только explicit synthetic source-order array/digest и aggregate dependency counts; он не строит или валидирует dependency graph. Filesystem enumeration никогда не считается effective source order.

В synthetic M1A manifest `position` имеет exact JSON-integer contract: `bool` и
float запрещены даже при числовом равенстве, а records обязаны образовывать
непрерывный диапазон `0..file_count-1`. До path processing и первой candidate
write каждый `SnapshotBlob` проверяется как exact immutable bytes/inventory
shape; byte count, content hash, observer/content generations и inventory
identity должны быть согласованы, иначе наружу выходит только
`SNAPSHOT_BLOB_MISMATCH`.

Read-only launcher metadata способно доказать сохранённую конфигурацию, но без versioned schema/runtime evidence не доказывает фактическую engine precedence. Download/install order Workshop также не считается mod load order.

## Сравнение export policies

| Критерий | `per-source` | `playset-bundle` | `hybrid` |
|---|---|---|---|
| Provenance | естественно изолирована по source | manifest обязан сохранять каждый source/generation | два уровня provenance и routing |
| Launcher entries | потенциально одна на source | одна на playset | bundle плюс exceptions |
| Требуемый order | companion должен однозначно переопределять свой source и не ломать другие | bundle должен иметь доказанную позицию после всех нужных winners | нужны оба правила |
| Cross-source duplicates | локализуются, но всё равно требуют engine winner | централизованы, но builder не может угадать winner | наиболее сложная collision matrix |
| Disable/delete source | удалить/не включать конкретный companion | rebuild bundle без source; старый bundle stale | rebuild routing и exceptions |
| Workshop update | invalidate один generation | invalidate общий bundle | invalidate затронутые части и общий routing |
| Rollback boundary | много independent artifacts | один versioned artifact | несколько согласованных artifacts |
| Playset isolation | нужна отдельная identity каждого companion/playset | естественная при отдельном bundle на playset | явная в обоих слоях |
| M1A candidate determinism | синтетически достижима | синтетически достижима | синтетически достижима |
| Effective engine evidence 4.4.6 | недостаточно | недостаточно | недостаточно |
| Disposition | не выбрана | рабочая гипотеза M0R, не принята | не выбрана |

Детерминированный synthetic build не снимает последнюю строку. Без однозначного current-version winner/export evidence ни одна policy не может получить accepted status.

## Update, uninstall и rollback

- **Unchanged rerun:** одинаковые generation/order/policy inputs дают тот же logical manifest и payload hashes.
- **Workshop update:** любое изменение фактически прочитанных bytes создаёт новую generation; candidate старой generation становится stale целиком.
- **Disable/remove:** отсутствие source из текущего explicit playset invalidates candidate. History может сохраняться в будущем workspace, но payload этого source не остаётся активным по умолчанию.
- **Cleanup research root:** выполняется только владельцем `TemporaryDirectory`; helper не предоставляет cleanup API для произвольного path.
- **Uninstall future artifact:** должен удалять только managed version, не source и не чужой output. Этот protocol не реализован в M1A.
- **Rollback:** M1A определяет logical boundary «целый versioned artifact», но не активирует и не проверяет last-known-good. Полная crash matrix принадлежит M3.

## Запрещённые выводы M1A

- Descriptor `dependencies` не доказывает полную order graph semantics.
- `localisation/replace` не тождествен descriptor `replace_path`.
- Порядок строк в launcher DB не доказывает effective engine winner.
- Успешное создание disposable tree не доказывает, что игра его загрузит.
- Read-only metadata не разрешает изменить launcher state или active mod path.
- Ни одна policy не становится accepted без owner review и достаточного evidence.

## Текущий decision boundary

Контракт candidate reproducibility может быть принят как исследовательский результат. Export policy остаётся unresolved, потому что публичные источники не дают versioned 4.4.6 collision/load-order contract, а M1A не имеет права активировать candidate для runtime проверки. Этот unresolved факт является blocker для перехода format-ветви к M2, независимо от успеха synthetic tests.
