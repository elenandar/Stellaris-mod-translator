# Research taxonomy markup Stellaris

- Статус: `M1A — in review`
- Profile: [`stellaris-4.4.6`](../version-profiles/stellaris-4.4.6.md)
- Связанный byte contract: [localisation format](localisation-format.md)

## Принцип

Markup всегда является недоверенными code-like bytes внутри quoted value. M1A считает только fixture-backed aggregate classes; он не возвращает atom/value spans. Exactness обеспечивает whole-file byte buffer, а не markup CST. Helper не выполняет scripted localisation, не раскрывает reference, не загружает icon и не решает, где atom можно разместить.

`classified` означает «есть scanner rule, fixture и exact round trip», а не «разрешено изменение окружающего текста».

Все M-01…M-08 являются non-editable и non-movable в M1A. M-09 — только концептуальный human-text candidate: helper не materialize его boundaries, а изменение bytes запрещено. Future movement rule может появиться лишь в typed M2 contract с отдельным validator.

## Классы

| ID | Syntactic envelope | M1A класс | Проверяемый инвариант | При нарушении |
|---|---|---|---|---|
| M-01 | `$...$` | localisation reference / placeholder | два delimiters; непустой conservative ASCII payload; исходные bytes неизменны | unknown/ambiguous count и blocker |
| M-02 | `[ ... ]` | scripted/dynamic localisation | balanced delimiters; непустой conservative ASCII payload | unknown/ambiguous count и blocker |
| M-03 | `£...£` | icon atom | два delimiters; непустой conservative ASCII payload | unknown/ambiguous count и blocker |
| M-04 | `§X` | formatting opener | в M1A allowlisted только fixture-backed code `Y` | unknown/ambiguous count и blocker |
| M-05 | `§!` | formatting reset | reset закрывает ранее открытый formatting state | unknown/ambiguous count и blocker |
| M-06 | `\n` | escaped line break | два bytes остаются внутри value | unknown escape blocker |
| M-07 | `\"` | escaped quote | quote не закрывает value | malformed quote blocker |
| M-08 | `\\` | escaped backslash | pair не открывает иной escape | unknown escape blocker |
| M-09 | ordinary UTF-8 outside recognized atoms | conceptual human-text candidate | границы наружу не возвращаются; bytes M1A не меняет | invalid UTF-8 blocker |

Содержимое atom payloads не публикуется в evidence. Inventory возвращает только пять aggregate counts: placeholders, icons, formatting spans, scripted localisation и unknown-or-ambiguous. Отдельных balanced flags и per-case diagnostic codes текущий helper не имеет.

## Placeholder/reference

Содержимое между `$` допускается classifier только как непустой ASCII `[A-Za-z0-9_.:-]+`. Это намеренно уже public candidate syntax. Nested `$`, одиночный delimiter и crossing с другим atom увеличивают unknown counter и блокируют profile.

Helper не проверяет существование referenced key и не заменяет reference его значением. Эта семантика относится к будущему context/validator layer.

## Scripted/dynamic localisation

Содержимое `[...]` не публикуется; positive classification допускает только тот же conservative ASCII payload. M1A не делает предположений о object scope, getter chain, parameter syntax или результате выполнения игры. Nested/crossing brackets либо closing delimiter без opener получают blocker.

## Icons

`£...£` считается atom только с conservative ASCII payload. M1A не проверяет наличие asset и не normalise token case. Пустой, незакрытый или nested icon atom блокируется.

## Formatting spans

`§X` открывает formatting state, `§!` его сбрасывает. Конкретный набор допустимых code bytes закрепляется только version profile и fixture manifest; неизвестный code не принимается по сходству. Scanner считает depth, а исходная последовательность сохраняется только whole-file buffer. Profile запрещает:

- reset без opener;
- незакрытый state в конце value;
- delimiter без code byte;
- code, отсутствующий в profile allowlist;
- crossing с незакрытым `$`, `[]` или `££` atom.

Даже balanced formatting не доказывает возможность переместить opener/reset при переводе. M1A проверяет только exact preservation.

## Escapes

Research profile различает только `\n`, `\"` и `\\`. Backslash перед любым другим byte классифицируется `escape_unknown` и блокирует mutation. Helper не превращает `\n` в physical LF и не выполняет unescape/re-escape cycle.

[Paradox-hosted candidate documentation](https://stellaris.paradoxwikis.com/Localisation_modding) также упоминает `\t`, `[[` и icon frame syntax. Страница не является grammar 4.4.6, а текущий synthetic manifest не содержит отдельных положительных cases для этих форм, поэтому profile оставляет их unknown/blocking.

## Ambiguity policy

Scanner проходит value один раз. Delimiter внутри candidate payload делает atom unknown; aggregate scan затем продолжает с определённой scanner position и может посчитать дополнительные ambiguous markers. Ненулевой unknown-or-ambiguous count блокирует весь file для будущей mutation, но helper не создаёт отдельный «opaque value» object.

Unknown marker count, unbalanced state и unsupported escape являются blockers даже при byte-identical round trip. Byte preservation защищает source, но не делает неизвестный markup безопасным для модели или renderer.

## Synthetic coverage

Fixture suite в совокупности обязана покрывать:

- каждый класс M-01…M-09;
- несколько atoms в одном value;
- adjacent atoms и formatting вокруг reference;
- пустой human span;
- каждый unbalanced/orphan case;
- unknown formatting code и unknown escape;
- delimiter-like ordinary Unicode text, который не должен быть silently stripped.

Expected manifest перечисляет category counts без real source values. Grouped fixtures покрывают positives; ambiguous/unbalanced members дополнительно проверяются по одному в table-driven test. Тест сравнивает classification и byte-identical `render_identity()`; отдельные diagnostic codes и atom spans остаются M2 work.

## Граница M2

Только будущий typed parser может решить, какие atoms immutable, movable или context-dependent, а controlled renderer — доказать, что меняются лишь human spans. Эта taxonomy не является обходным translation pipeline и не разрешает вызовы Ollama.
