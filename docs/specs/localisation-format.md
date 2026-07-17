# Research-спецификация формата localisation

- Статус: `M1A — in review`
- Profile: [`stellaris-4.4.6`](../version-profiles/stellaris-4.4.6.md)
- Реализация: только byte-preserving helper в [`tools/research`](../../tools/research/)

## Область утверждения

Эта спецификация описывает безопасную классификацию и round trip, а не production parser и не разрешение переводить строки. В M1A существуют три разных результата:

- `classified_roundtrip` — конструкция имеет synthetic fixture, ожидаемую классификацию и возвращается byte-identical;
- `opaque_blocker` — bytes сохраняются целиком, но документ нельзя преобразовывать;
- `invalid_generation` — snapshot/run отвергается до анализа формата.

Ни один статус M1A не означает `transform_supported`. Controlled mutation начинается не раньше M2 и только после совместного milestone gate.

## Byte envelope

Helper читает файл как bytes из уже открытого non-symlink descriptor и не выполняет universal-newline, Unicode normalization или decode-with-replacement.

| Свойство | Классификация | M1A действие |
|---|---|---|
| UTF-8 BOM в offset 0 | `bom_start` | сохранить ровно три bytes |
| BOM отсутствует | `bom_missing` | сохранить, но block profile eligibility |
| `U+FEFF` после offset 0 | `hidden_bom` | сохранить и block |
| valid UTF-8 | `utf8_valid` | разрешить line/markup inventory |
| invalid UTF-8 | `utf8_invalid` | opaque whole-file blocker; не печатать offending bytes |
| только LF | `newline_lf` | сохранить каждый terminator |
| только CRLF | `newline_crlf` | сохранить каждый terminator |
| LF и CRLF | `newline_mixed` | сохранить, но block |
| последний record без newline | `final_newline_missing` | сохранить отсутствие terminator |

Round trip реализован как возврат исходного immutable whole-file byte buffer. Декодированный text используется только для aggregate classification; renderer M1A не реконструирует строку и не выполняет повторное кодирование.

## Records

После удаления только стартового BOM из classification view helper последовательно классифицирует lines. Он не материализует CST, record objects или byte spans: точность обеспечивает только неизменяемый whole-file buffer, который возвращается целиком.

| Record | Минимальное правило profile | Сохраняемая форма |
|---|---|---|
| language header | первая line после optional BOM — один conservative ASCII token `l_<language>:` без surrounding whitespace; ровно один header-like record во всём file | aggregate count/class; whole-file bytes unchanged |
| blank | до terminator только space/tab | aggregate count; whole-file bytes unchanged |
| comment | первый non-whitespace character — `#` | aggregate count; whole-file bytes unchanged |
| entry | leading whitespace, conservative ASCII key token, `:`, optional decimal version, whitespace, quoted value, trailing horizontal whitespace | aggregate counters only; whole-file bytes unchanged |
| unknown | всё, что не удовлетворяет одному правилу без догадки | aggregate blocker; whole-file bytes unchanged |

Scanner считает header-like lines независимо, а local probe отдельно проверяет first-line/single-header contract. Header после comment, multiple headers и header с whitespace поэтому дают profile blocker, даже если raw buffer остаётся byte-identical.

M1A не объявляет inline comment синтаксисом: `#` внутри quoted value является text byte, а bytes после closing quote делают record unsupported до отдельного fixture/rule.

### Entry classification

Research scanner движется слева направо и не использует generic YAML parser:

1. классифицирует leading whitespace, не отделяя его от raw buffer;
2. находит первый structural colon вне quoted value;
3. отделяет key bytes от decimal version suffix;
4. требует opening и однозначный unescaped closing quote;
5. использует decoded classification view только для counters; value span наружу не возвращается;
6. передаёт decoded value markup classifier, не меняя сохранённый raw buffer;
7. требует, чтобы остаток состоял только из горизонтального whitespace.

Key временно используется только как локальный counting token и не попадает в output. Whole-file buffer сохраняет две одинаковые entries в исходном порядке, но M1A helper не публикует occurrence positions и не связывает collision с effective source order. Он считает intra-file duplicate groups/occurrences, а local probe — aggregate cross-source candidate collisions через domain-separated SHA-256.

## Quotes, escapes и пустые значения

| Конструкция | Класс | Правило |
|---|---|---|
| `\"` | `escape_quote` | два исходных bytes сохраняются |
| `\\` | `escape_backslash` | два исходных bytes сохраняются |
| `\n` | `escape_newline` | два исходных bytes сохраняются; это не physical newline |
| другой backslash sequence | `escape_unknown` | opaque blocker до fixture/profile update |
| `""` как value | `empty_value` | допустимая классификация, occurrence не удаляется |
| незакрытая quote | `malformed_unclosed_quote` | opaque blocker |
| physical newline внутри quote | `malformed_multiline_value` | opaque blocker в profile 4.4.6 |

Таблица показывает синтаксические tokens, а не разрешение менять human text рядом с ними.

## Whitespace и comments

- Leading/trailing spaces, tabs, blank lines и comment bytes сохраняются точно.
- Helper считает records с tabs и необычным отступом, но не исправляет их.
- Unicode whitespace внутри value является text и не нормализуется.
- Trailing spaces перед newline входят в record hash.
- Отсутствие final newline — наблюдаемая форма, не ошибка round trip.

## Duplicate semantics

Форматная спецификация доказывает только наличие duplicate occurrences и byte-identical сохранение исходного file order. Она намеренно не задаёт winner:

- intra-file duplicates сохраняются и диагностируются;
- duplicates между файлами одного source диагностируются отдельно;
- cross-source duplicates считаются по opaque key hashes, но не связываются с effective engine order;
- collision winner остаётся export/load-order contract, а не побочным эффектом parser map.

Если engine winner не доказан для текущего profile, candidate build с затронутой collision получает blocker.

## Malformed и unknown

Следующие случаи fail closed: header не первый; несколько headers; invalid UTF-8; hidden BOM; mixed newline; non-decimal suffix; unquoted value; непарная quote; trailing syntax; неизвестный markup; physical multiline value. Helper может продолжить aggregate inventory других файлов, но run не может дать profile-wide transform eligibility.

Текущий helper публикует aggregate counters и top-level stable blocker codes. Per-record diagnostic codes, severity и occurrence positions относятся к будущему M2 contract. Ни один output не содержит filename, key, line, source excerpt или raw exception message.

## Round-trip invariant

Для каждого успешно прочитанного файла:

```text
sha256(input_bytes) == sha256(identity_render_bytes)
input_size == rendered_size
```

Равенство проверяется по bytes, а не по декодированным строкам. Unknown/malformed records тоже сохраняются byte-identical; наличие blockers запрещает любую будущую mutation, но не разрешает helper «починить» source.

## Fixture admission

Конструкция добавляется в `classified_roundtrip` только одним PR, который содержит:

1. минимальный synthetic fixture;
2. expected category/diagnostic;
3. byte-for-byte test;
4. malformed sibling case;
5. обновление taxonomy и version profile;
6. новый полный local census с development/holdout aggregate inventory; это deterministic cross-check, а не независимая внешняя выборка.

Research fixtures находятся в [`fixtures/m1a`](../../fixtures/m1a/) и не извлечены из игры или модов.

Текущий expected manifest связывает каждый claim с case ID:

| Case ID | Доказанный класс |
|---|---|
| `bom-lf-matrix` | start BOM, LF, header/comment/blank, quoted/versioned/empty/duplicate entries и базовые atoms |
| `crlf-no-final-newline` | CRLF и отсутствие final newline |
| `mixed-newlines` | mixed classification с будущим profile blocker |
| `unknown-markup-is-opaque` | unknown line и unbalanced placeholder |
| `malformed-entry-is-opaque` | unclosed quoted value |
| `hidden-bom` | interior `U+FEFF` |
| `fixture-backed-escapes` | exact `\n`, `\"`, `\\` classification |
| `escaped-markup-is-ambiguous` | escaped delimiter не угадывается |
| `unknown-escape-is-opaque` | неизвестный escape блокирует |
| `unknown-formatting-code-is-opaque` | только fixture-backed formatting code разрешён classifier |
| `adjacent-atoms-empty-human-span` | adjacent mixed atoms без human span |
| `trailing-comment-is-unsupported` | trailing syntax блокируется |
| `record-variants-positive` | indented comment/blank/tab/trailing whitespace и Unicode text inside value |
| `record-malformed-siblings` | non-decimal suffix, unquoted и physical multiline siblings блокируются |
| `empty-delimiters-are-opaque` | пустые `$`, bracket и icon envelopes блокируются |
| `unbalanced-and-orphan-delimiters` | unbalanced/orphan bracket/icon cases блокируются |
| `nested-and-crossing-atoms` | nested/crossing atom delimiters блокируются |
| `formatting-state-errors` | orphan reset, unclosed opener и bare delimiter блокируются |
| `formatting-crossing` | formatting/placeholder crossing блокируется |
| `formatting-nested-balanced` | fixture-backed nested `§Y...§!` counts |
| `delimiter-like-unicode-is-text` | похожие Unicode glyphs остаются ordinary text |
| `invalid-utf8` | whole-file opaque bytes |

Все cases проходят единый test `test_fixture_classifications_and_identity_round_trip`; expected fields проверяются рекурсивно, а `render_identity()` сравнивается с исходными bytes. Отдельный table-driven test изолирует каждый ambiguous delimiter и исключает компенсацию grouped counters. Suite в целом покрывает positive classes и malformed siblings; M1A не утверждает, что каждый positive atom хранится отдельным file fixture.

## Не доказано этой спецификацией

- фактическое engine precedence между duplicate keys;
- семантика выполнения scripted localisation;
- возможность перемещать markup atoms в переводе;
- поддержка другой версии игры или другой платформы;
- корректность active publish/rollback;
- литературная или смысловая корректность текста.
