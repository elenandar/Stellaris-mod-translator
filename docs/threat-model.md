# Модель угроз M1A

- Статус: `M1A — in review`
- Дата снимка: 17 июля 2026 года
- Область: read-only discovery, immutable in-memory generation, research round trip и disposable candidate build
- Вне области: перевод, Ollama, production parser/CLI, activation, publish в игру и Steam Workshop

## Цели безопасности

1. Ни один read-only эксперимент не изменяет игру, Workshop, source mod, launcher state или active mod/output path.
2. Каждый анализ относится к одной воспроизводимой generation фактически прочитанных байтов; смешанная generation запрещена.
3. Неизвестный синтаксис, порядок источников или collision не угадываются и не нормализуются молча.
4. Candidate создаётся только в disposable root, который доказанно не пересекается ни с одним source root; raw disk snapshot в M1A отсутствует.
5. Raw/private/copyrighted corpus не покидает локальный helper и не попадает в Codex context, Git, logs или PR.

## Активы и границы доверия

| Актив | Требуемое свойство | Граница доверия |
|---|---|---|
| Установка игры и официальная локализация | только чтение, неизменные bytes | недоверенный внешний source root |
| Workshop и локальные source mods | только чтение, одна generation | недоверенный и изменяемый внешний source root |
| Launcher/playset metadata | только чтение, без lock/schema migration | недоверенный mutable metadata source |
| Accepted generation | exact bytes immutable в памяти плюс aggregate content/identity manifest | локальный research process; disk snapshot не материализуется |
| Research helper | fail closed, агрегированный output, без traceback с данными | единственный процесс, которому разрешено видеть raw corpus |
| Synthetic fixtures | минимальные, вымышленные, свободные от private content | единственный corpus, доступный Codex и subagents |
| Candidate artifact | детерминированный, неактивный, удаляемый целиком | отдельный disposable output root |
| Git, PR и development logs | только contracts, tests и sanitized evidence | cloud-visible boundary |

Source paths, descriptor values, launcher values, mod names, localisation keys и строки считаются private независимо от того, выглядят ли они безобидно. Мод может намеренно содержать path-like значения, prompt injection, управляющие символы либо очень большие строки.

## Шкала серьёзности

- **Critical** — возможны запись в активные/source paths, смешанная generation, silent data loss или утечка private corpus.
- **High** — candidate или решение load order могут стать невоспроизводимыми либо небезопасными без дополнительного события.
- **Medium** — evidence неполно или диагностика недостаточна, но write/privacy boundary остаётся целой.
- **Low** — операционное неудобство без нарушения канонов.

## Реестр угроз

| ID | Угроза или отказ | Серьёзность | M1A mitigation и evidence | Следующий владелец | Остаточный gate |
|---|---|---:|---|---|---|
| T-01 | Source меняется во время чтения и образует mixed generation | Critical | один open без follow, два byte pass, `fstat`/path identity до/после, immutable accepted bytes в памяти и full pre/post manifest; любое расхождение завершает run | M2 | regression на каждом reader change |
| T-02 | Файл заменён между metadata check и `open` | Critical | identity сравнивается по descriptor открытого файла, а не по ранее разрешённому имени; synthetic replacement test обязан дать clean abort | M2 | platform-specific identity contract |
| T-03 | Symlink, traversal либо equality/ancestor overlap направляет запись в source | Critical | canonical root-disjointness до создания candidate; equality, оба направления ancestry, symlink alias и `..` fail closed | M2/M3 | повторная проверка перед build и cleanup |
| T-04 | Duplicate, casefold или Unicode-неоднозначные logical paths меняют winner | High | component-wise alias/type checks блокируют build; physical M1A payload layout плоский и generated | M2/M3 | version-profile path rules |
| T-05 | Partial read, I/O error или Workshop update дают неполную generation | Critical | известный ожидаемый byte count, short-read injection и отсутствие silent retry; accepted in-memory generation существует только целиком | M2 | property/fault-injection suite |
| T-06 | Disk-full, process crash либо tamper оставляет частичный candidate | High | flat exclusive writes, actual payload reread/hash, hardlink rejection, manifest-last и post-commit validation; incomplete tree не используется | M3 | power-loss certification до publish |
| T-07 | Cleanup удаляет неправильный каталог | Critical | M1A не реализует произвольный cleanup: synthetic roots принадлежат `TemporaryDirectory`; ownership marker и managed cleanup остаются обязательными для M3 | M3 | platform cleanup tests |
| T-08 | Malformed или unknown localisation молча исправляется | Critical | byte-preserving opaque record либо blocker; research round trip не выполняет normalisation/translation | M2 | CST и controlled renderer tests |
| T-09 | Duplicate keys теряются при map-like parsing | High | whole raw buffer сохраняет исходный order; aggregate inventory считает duplicate groups/occurrences без map replacement, но positions не материализует | M2/M3 | typed occurrence model и collision policy |
| T-10 | Неподтверждённый launcher/load order выбирает неверного winner | Critical | metadata order — evidence, но не доказательство engine collision semantics; неоднозначность блокирует export policy | M1A owner decision/M3 | activation/in-game smoke только отдельным gate |
| T-11 | Source mod отключён, удалён или обновлён после candidate build | High | manifest закрепляет source generations и order digest; mismatch запрещает reuse/activation | M3 | update/uninstall/rollback tests |
| T-12 | `replace_path`, `localisation/replace` или dependency меняет видимый набор данных | High | отдельные aggregate field/directory observations; unknown descriptor schema и наличие неинтерпретированных dependencies дают blockers | M2/M3 | identity/cycle/engine-profile integration tests |
| T-13 | Launcher DB read создаёт journal/lock либо меняет state | Critical | M1A никогда не открывает DB через SQLite; обнаруженный file допускается только в byte-stable manifest, а неизвестный path/schema остаётся blocker | M1A/M3 | platform adapter tests |
| T-14 | Raw localisation, names или paths попадают в stdout/traceback | Critical | whitelist JSON schema, opaque IDs, redacted exception boundary, no excerpts; unexpected exception возвращает только error class | M1A/M2 | leakage regression |
| T-15 | Raw corpus попадает в Git, fixture, report или PR | Critical | stable repository scan сравнивает exact-line, long-token, descriptor/value и private-path fingerprints, возвращая только counts; staged diff и PR body дополнительно review-ятся | каждый milestone | автоматический scan не заменяет full diff review |
| T-16 | Untrusted mod text интерпретируется как инструкция | High | M1A никогда не передаёт raw text модели; будущая модель получает только typed human spans без tools | M4 | provider/renderer adversarial tests |
| T-17 | Hash collision либо слабый opaque ID смешивает sources | Medium | SHA-256 полного содержимого и domain-separated manifest records; ID не заменяет byte comparison там, где нужна целостность | M2/M3 | manifest versioning |
| T-18 | Research spike становится неявным production pipeline | High | helper расположен в `tools/research`, имеет explicit research-only banner, не переводит и не пишет в managed/active paths | M2 owner | production implementation только после совместного gate |

## Протокольные инварианты M1A

1. Сначала разрешаются и сравниваются canonical roots; только затем создаются candidate files. Raw snapshot files в M1A не создаются.
2. In-memory generation принимает только bytes, полученные из открытого non-symlink file descriptor. Source pathname после `open` не считается identity.
3. На generation mismatch run прекращается целиком. Silent retry отдельного файла запрещён, потому что он мог бы смешать поколения.
4. Candidate manifest содержит version профиля, ordered source digest, policy ID, logical paths, generated flat storage names, byte sizes и SHA-256; timestamp и абсолютные пути исключены.
5. Manifest hash и observed payload-tree hash вычисляются независимо; повторная сборка одинаковых synthetic inputs обязана дать одинаковые пары hashes.
6. Любой unsupported syntax, path ambiguity или load-order ambiguity формирует blocker, а не warning.

## Принятый остаточный риск

M1A может доказать read-only inventory, byte preservation, clean abort и детерминированный disposable layout. Он не сертифицирует power-loss behavior или защиту от произвольного concurrent same-UID процесса и не имеет полномочий доказать фактическую активацию candidate. Если публичные current-version evidence и read-only metadata не дают однозначного collision winner, M1A обязан завершиться `BLOCKED`, а не превращать активацию в скрытый эксперимент.
