# Contract review M1B-1A0

- Milestone: `M1B-1A0 — Offline executable/TCB admission contract`
- Remediation state: `REMEDIATION: READY_FOR_REVIEW`
- Review state: `M1B-1A0 CONTRACT: READY_FOR_REVIEW`
- Authorization gate: `M1B-1A1-AUTH: OWNER_REVIEW_REQUIRED`
- Candidate construction: `CANDIDATE CONSTRUCTION: NOT_AUTHORIZED`
- Admission state: `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`
- Owner-decision blocker: `EXECUTABLE_TCB_OWNER_DECISION_REQUIRED: PRESERVED`
- Provider-source blocker: `PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN: PRESERVED`
- Implementation identity: `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN: PRESERVED`
- Provider execution: `M1B-1A PROVIDER EXECUTION: NOT_STARTED`
- Remediation date: `2026-07-22`

Этот record фиксирует normative review identity contract generation 4 после
remediation findings draft PR #8. Он не является owner acceptance record,
runtime admission, provider capability, benchmark report или feasibility
verdict.

## Approved starting point

- PR #8 approved remediation start:
  `c6ecad63062018c7fd71d33041901b6fd39b03f0`;
- approved base, PR base и merge-base:
  `424a4e45066cfbff3f9b3da2ec2cf6ad62a643fb`;
- branch: `agent/m1b-1a0-offline-executable-tcb-contract`;
- `OWNER_FREEZE: ACCEPTED`;
- `STABLE_READ_HARDENING: ACCEPTED`.

Final remediation HEAD намеренно не встраивается в собственные committed
bytes: после обычного push его фиксируют body draft PR #8 и final handoff.
Git provenance — review context, не trust root для executable identity.

## Normative generation-4 identity

| Surface | Exact identity |
|---|---|
| Contract schema | `m1b-offline-executable-tcb-contract-v4` |
| Contract version / generation | `m1b-offline-executable-tcb-admission-v4` / `4` |
| Canonical contract bytes | `10264` |
| Contract raw SHA-256 | `fd5e54a8c4b03b6a9c0a62b715ce6d8b2eac070965467bd2de0dbe772808ce6f` |
| Contract external framed digest | `ad6bce1a5c516753d79ee0d807f5445e9b860a398e661adfb9730d9c4fee9c31` |
| Execution envelope | `m1b-execution-envelope-v4`, generation `4` |
| Envelope digest domain | `stellaris-m1b-execution-envelope-v4` |
| Runtime acceptance | `m1b-runtime-execution-envelope-acceptance-v1`, generation `1` |
| Runtime-acceptance domain | `stellaris-m1b-runtime-execution-envelope-acceptance-v1` |
| Execution plan | `m1b-execution-plan-v3`, generation `3` |
| Public fixture schema | `m1b-tcb-admission-cases-v5` |
| Manifest | preserved `m1b-executable-implementation-manifest-v1` |
| Existing implementation acceptance | preserved exact five-field record |
| Preserved protocol | `m1b-benchmark-contract-v7`, generation `108` |
| Offline verifier bytes / SHA-256 | `104137` / `242b115d6eb8f7df143eeeccc94c2b7029dc1a7b601d9a29bd436a183e446551` |
| Public fixture cases / bytes | `241` unique / `73746` |
| Fixture SHA-256 | `b729305612bdf5f3e88d42a90603cf6a10b2100bd31b144c28399a155984d862` |
| Synthetic positive envelope | `9752` bytes; raw SHA-256 `a3e2a53f1520e32181eb40c89b5d8fc170ae40937e169eb6bec950cbb68ab812`; framed SHA-256 `19287150c53ede004966797f49c8d5448f0be435f375deb5065205eed14858f8` |
| Synthetic positive runtime record | `883` bytes, `16` fields; raw SHA-256 `f5974084d9c65709df2fbdd4f319a8311331e9bfe37410a2cfa1badfc321b037`; framed SHA-256 `5c1658d12846f82835cdf19564afb384187261f0111f6d1105967601d414cbdc` |

Canonical contract bytes, raw SHA-256 и external framing независимо
пересчитаны отдельно от production verifier. Contract не содержит self-hash.
Envelope и
runtime-acceptance framed identities используют отдельные frozen domains,
NUL, unsigned 64-bit big-endian canonical byte length и exact canonical bytes
с завершающим LF.

Normative artifacts:

- [human-readable contract](../specs/m1b-offline-executable-tcb-admission-contract.md);
- [canonical registry](../../registry/m1b/offline-executable-tcb-contract-v4.json);
- [public synthetic fixture](../../fixtures/m1b/tcb-admission/README.md);
- [offline verifier](../../tools/research/m1b_tcb_contract.py).

## Remediated findings

### 1. Exact envelope external linkage

Новый closed 16-field runtime acceptance связывает собственные
schema/generation/state, actual contract, actual manifest, canonical framed
execution envelope и protocol generation 108. Существующий пяти-field
implementation acceptance не расширен и не переопределён.

Runtime record имеет отдельный external framing domain, но caller-supplied
record не становится authority. Реальный owner-controlled expected identity
остаётся обязательным future trust root. Synthetic success возвращает только
`SYNTHETIC_CONFORMANCE_ONLY`.

### 2. Interpreter, invocation и four-role execution plan

Envelope v4 содержит closed `m1b-execution-plan-v3`: exact interpreter,
manifest-bound `provider_request_harness` entrypoint и ordered source rows для
`analysis_engine`, `contract_validator`, `synthetic_fixture_materializer`.
Все четыре manifest roles связаны с already admitted bytes.

Invocation разделяет repository-root locators, OS exec target, `argv[0]`, cwd,
`sys_path` и entrypoint transport. Допустим только exact argv tail:

```text
["-I", "-S", "-B", "-X", "utf8", "/dev/fd/3"]
```

`argv0` и `os_exec_target` — отдельные typed repository-root locators exact
interpreter bytes. `xoptions=["utf8"]`, `warnoptions=[]`; pathname script,
`-c`, `-m`, stdin, `--`, unknown или reordered flags,
unmanifested/absolute/case-aliased entrypoint fail closed.

`cwd` и каждый `sys_path` теперь проходят отдельный descriptor-rooted stable
directory admission с nofollow, strict pre/post identity и ровно одной close
attempt. Отдельные lexical/physical directory indices запрещают exact и
physical cwd/sys_path reuse, duplicate sys_path, case alias, replacement,
metadata drift, stat ambiguity и close failure. Directory snapshot не является
доказательством future import transport.

### 3. Global physical identity, purpose matrix and no-reopen

Verifier-wide indices используют exact lexical path и opened physical
`(st_dev, st_ino)` для пяти input records, manifest roles, interpreter,
source/extension imports и native dependencies. Exact accepted reuse с тем же
digest использует cached bytes без open/read только после closed
purpose-matrix admission; digest drift и purpose conflict отклоняются без
reopen. Другой
lexical path к уже известному inode отклоняется после `fstat`, до content read.
Case folding не используется. Каждый descriptor получает ровно одну production
close attempt, а primary alias error не скрывается close failure.

Default-deny matrix разрешает только matching non-provider manifest role ↔
matching plan role ↔ matching source import; provider manifest ↔ plan
entrypoint ↔ descriptor transport; interpreter ↔ plan/invocation
`argv0`/`os_exec_target` ↔ pathless builtin/frozen. Standalone source,
extension и native dependency имеют по одному purpose, а path-bearing imports
имеют unique paths независимо от module/kind.

### Adversarial P1: option-like manifest entrypoint

Дополнительный adversarial review показал, что exact argv grammar недостаточно,
если caller согласованно назовёт manifest-bound provider harness относительным
path, начинающимся с `-`. Registry теперь machine-exact требует
`raw_relative_posix_first_ascii_byte_not_hyphen`. Поэтому `-c`, `-m`, `-`,
`--`, `-E` и любое другое option-like raw path отклоняются даже при coherent
manifest, execution plan, admitted/observed envelope и runtime acceptance.
Это normative изменение сохранено в текущей generation-4 registry identity до
commit; operational authority по-прежнему не выдаётся.

### 4. Operationally satisfiable entrypoint transport

Generation 2 одновременно объявляла no-reopen mode и передавала provider
harness как cwd-relative pathname без descriptor transport. CPython должен был
бы повторно открыть pathname, а declared cwd делал repository-relative строки
неразрешимыми. Generation 3 устранила этот противоречивый positive profile;
generation 4 сохраняет descriptor transport и усиливает его lifecycle checks.

Provider entrypoint теперь передаётся только через typed inherited FD row:
`child_fd=3`, `process_path=/dev/fd/3`,
`transport=darwin_pipe_atomic_preload_v1`, exact provider role,
repository locator, digest и admitted byte count. Synthetic primitive делает
ровно один полный write cached admitted bytes размером `1..512` при
`PC_PIPE_BUF >= 512`, закрывает writer до любого возможного child и требует
exact readback с EOF. Перед и после write verifier повторно проверяет оба ends;
после единственной successful close writer он проверяет read end перед и после
каждого read и после EOF. Проверки связывают FIFO type, access mode,
non-inheritability и physical identity. Controlled mid-write/mid-read descriptor
substitution, wrong/reused/duplicate/closed FD, missing/extra transport, short
write, early/extra EOF, byte или digest mismatch и любой close failure
отклоняются. Mutation source pathname после admission не меняет cached
transport bytes.

Это доказывает bounded transport primitive и обнаруживает controlled
substitution, но не защищает от hostile same-process monkeypatching/reflection
и не доказывает реальный macOS launcher.
Closed plan поэтому обязан сохранять blockers
`INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN`,
`LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN` и
`PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN` и
`ROLE_IMPORT_TRANSPORT_UNPROVEN`. Synthetic success остаётся только
`SYNTHETIC_CONFORMANCE_ONLY`; executable admission не выдан.

### 5. Provider entrypoint source eligibility

Exact plan launcher и global status policy обязаны сохранять
`PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN`. Снять его может только
будущий admitted CPython над exact cached bytes descriptor transport. Host
`ast.parse`, `compile`, pathname reopen или проверка другим interpreter не
являются evidence. Поэтому invalid UTF-8, NUL и syntax-invalid synthetic bytes
могут structural-conform только при сохранённом blocker; такой результат не
утверждает executable source eligibility.

### 6. Separate executable owner decision

Global status policy теперь также exact сохраняет
`EXECUTABLE_TCB_OWNER_DECISION_REQUIRED`. Caller-supplied
`acceptance_state=owner_accepted` проверяется только как synthetic closed shape
и linkage. Задание, создающее candidate bytes, не может одновременно принять
их; owner-controlled decision над уже известными exact identities является
отдельным будущим gate.

## Validation evidence

Final post-remediation validation:

- targeted TCB suite: `89/89`;
- public fixture: `241/241` in-process и `241/241` через production CLI;
- directory/pipe lifecycle matrix: `23/23`, включая injected physical aliases,
  cwd/sys_path replacement, metadata/stat/close failures и mid-write/mid-read
  descriptor substitution;
- реальный Darwin case-insensitive APFS smoke: `PASS`, не skipped;
- closed purpose matrix: три allowed cached profiles и `13` incompatible
  profiles без дополнительного open/read; role/module mismatch также fail closed;
- exact owner/provider blocker matrix: deletion, rename, order drift и coherent
  envelope/runtime rebinding отклонены; invalid UTF-8, NUL и syntax-invalid
  provider bytes остаются только `SYNTHETIC_CONFORMANCE_ONLY` при обоих blockers;
- owner-freeze suite: `25/25`; historical M1B suite: `79/79`;
- full research discovery: `266/266`;
- docs/link validation: `37` Markdown files, `40` fenced blocks, `55` tables,
  `87` relative links, `0` errors;
- registry/verifier exact field, schema, generation, blocker и matrix consistency:
  `16/16`;
- protected owner-freeze/validator comparison: `8/8` byte-identical к approved
  base `424a4e45066cfbff3f9b3da2ec2cf6ad62a643fb`;
- independent raw/framed identity reproduction, Python compile и
  `git diff --check`: `PASS`.

Все `240` fixture controlled failures через CLI имеют non-zero exit, empty
stderr, fixed allowlisted compact output и не раскрывают
path/content/hash/marker/exception/traceback; generated fault cases применяют
тот же leakage boundary. Manifest-listed bytes не импортируются, не
компилируются и не исполняются. Final commit/remote/PR-head parity фиксируется
внешним handoff и draft PR body, потому что committed review record намеренно не
содержит собственный будущий Git SHA.

## Preserved identities

Remediation не меняет:

- восемь explicit immutable owner-freeze/validator files;
- protected M1A surface;
- historical M1B proposal/owner-freeze semantics;
- owner-freeze snapshot
  `df84871be332ee52c315d0c0cc1a7a0046251352a2a0131382b5cb994cffcb58`;
- accepted definition bundle
  `50f51b3cf9be042ebc310d1a6c57791dd31a43362778798455d7ea9678c31e06`;
- all 17 accepted component identities;
- implementation policy v2
  `826d976613f44657c5a2ae9299d3cc80ad21751eb7298989a24653d0849de784`;
- protocol v7/generation 108.

Explicit protected comparison подтверждён: `8/8` byte-identical к approved
base. Accepted protocol, owner-freeze и historical test identities покрыты
final green runs `25/25`, `79/79` и полным discovery `266/266`.

## Boundaries and blockers

`SYNTHETIC_CONFORMANCE_ONLY` не выдаёт operational admission. Реальные
four-role bytes, owner-controlled implementation/runtime acceptance, proven
interpreter path exec, launcher opened-byte handoff, descriptor transport для
остальных role imports, native dependency closure, context/output binding,
persistence, residency, lifecycle, prompt/template bytes и real candidate
identities отсутствуют.
`PARTIAL_REPORT_CANNOT_BE_COMPLETE` сохраняется.

```text
REMEDIATION: READY_FOR_REVIEW
M1B-1A0 CONTRACT: READY_FOR_REVIEW
M1B-1A1-AUTH: OWNER_REVIEW_REQUIRED
CANDIDATE CONSTRUCTION: NOT_AUTHORIZED
EXECUTABLE_TCB_ADMISSION: NOT_GRANTED
EXECUTABLE_TCB_OWNER_DECISION_REQUIRED: PRESERVED
PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN: PRESERVED
EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN: PRESERVED
OWNER_FREEZE: ACCEPTED
STABLE_READ_HARDENING: ACCEPTED
M1B-1A PROVIDER EXECUTION: NOT_STARTED
M1B: NOT_EVALUATED
M1A: BLOCKED
M2: FORBIDDEN
```

Review и merge PR #8 фиксируют только M1B-1A0 и не выдают owner authorization
на создание candidate. После merge доступен только отдельный gate
`M1B-1A1-AUTH` со state `OWNER_REVIEW_REQUIRED`; до его отдельного явного
принятия `CANDIDATE CONSTRUCTION: NOT_AUTHORIZED`.

M1B-1A1-AUTH сам не создаёт executable files или real candidate
manifest/envelope, не запускает interpreter/provider, не создаёт operational
`owner_accepted` admission и не снимает
`EXECUTABLE_TCB_OWNER_DECISION_REQUIRED`. Он должен exact перечислить
разрешённые repository paths для ролей `analysis_engine`, `contract_validator`,
`provider_request_harness`, `synthetic_fixture_materializer`, отделить
read-only inputs от разрешённых write outputs и запретить любые не перечисленные
reads/writes, execution, provider/Ollama/model action, private corpus и
benchmark.

Только после отдельного explicit owner acceptance M1B-1A1-AUTH отдельный
`M1B-1A1` может создать proposed four-role candidate bytes и exact offline
manifest/envelope/launcher/import/source-eligibility evidence без acceptance или
execution. M1B-1A1 не может принять созданные identities. После его review
отдельный `M1B-1A2` может зафиксировать owner-controlled решение только над уже
известными exact identities. Даже M1B-1A2 не разрешает Ollama probe,
provider/model call, private corpus, benchmark execution, product CLI или M2:
для исполнения нужен ещё один явный gate.
