# Contract review M1B-1A0

- Milestone: `M1B-1A0 — Offline executable/TCB admission contract`
- Review state: `M1B-1A0 CONTRACT: READY_FOR_REVIEW`
- Admission state: `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`
- Implementation identity: `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN: PRESERVED`
- Provider execution: `M1B-1A PROVIDER EXECUTION: NOT_STARTED`
- Remediation date: `2026-07-22`

Этот record фиксирует normative review identity contract generation 3 после
remediation трёх исходных findings draft PR #8, option-like entrypoint finding
и нового invocation/launcher finding. Он не является owner acceptance record,
runtime admission, provider capability, benchmark report или feasibility
verdict.

## Approved starting point

- PR #8 approved remediation start:
  `696ca6fe270393bdcec496822f7ef8c193010807`;
- approved base, PR base и merge-base:
  `424a4e45066cfbff3f9b3da2ec2cf6ad62a643fb`;
- branch: `agent/m1b-1a0-offline-executable-tcb-contract`;
- `OWNER_FREEZE: ACCEPTED`;
- `STABLE_READ_HARDENING: ACCEPTED`.

Final remediation HEAD намеренно не встраивается в собственные committed
bytes: после обычного push его фиксируют body draft PR #8 и final handoff.
Git provenance — review context, не trust root для executable identity.

## Normative generation-3 identity

| Surface | Exact identity |
|---|---|
| Contract schema | `m1b-offline-executable-tcb-contract-v3` |
| Contract version / generation | `m1b-offline-executable-tcb-admission-v3` / `3` |
| Canonical contract bytes | `8438` |
| Contract raw SHA-256 | `cf91f64e8fa85dde15e85702199860f62974d86e54163b080a95fe2ac9c7a75d` |
| Contract external framed digest | `c346fdd761ea477a85930c041858e7444a576263f3fb5ca568cc1ab005ef9744` |
| Execution envelope | `m1b-execution-envelope-v3`, generation `3` |
| Envelope digest domain | `stellaris-m1b-execution-envelope-v3` |
| Runtime acceptance | `m1b-runtime-execution-envelope-acceptance-v1`, generation `1` |
| Runtime-acceptance domain | `stellaris-m1b-runtime-execution-envelope-acceptance-v1` |
| Execution plan | `m1b-execution-plan-v2`, generation `2` |
| Manifest | preserved `m1b-executable-implementation-manifest-v1` |
| Existing implementation acceptance | preserved exact five-field record |
| Preserved protocol | `m1b-benchmark-contract-v7`, generation `108` |
| Offline verifier bytes / SHA-256 | `86594` / `0df39292b306afdfd2187ffb554b5ad2714bbe0353ca176f6fe49cf7eb162c10` |
| Public fixture cases / bytes | `218` unique / `61682` |
| Fixture SHA-256 | `0f14d9b28ee41095a2373b02409b288c30959013840d7d1c891538266a84eeaa` |
| Synthetic positive envelope | `9652` bytes; framed SHA-256 `aaf95fced08459ec2ceca5f7bf0080e41dc5e62a4863bb22a937c3f8d0c504ed` |
| Synthetic positive runtime record | `883` bytes, `16` fields; framed SHA-256 `75eaa04963e2f9377180633392cadf15127538fcfb39bd62667be18cfbf7e7b0` |

Canonical contract bytes, raw SHA-256 и external framing пересчитаны
независимо от production verifier. Contract не содержит self-hash. Envelope и
runtime-acceptance framed identities используют отдельные frozen domains,
NUL, unsigned 64-bit big-endian canonical byte length и exact canonical bytes
с завершающим LF.

Normative artifacts:

- [human-readable contract](../specs/m1b-offline-executable-tcb-admission-contract.md);
- [canonical registry](../../registry/m1b/offline-executable-tcb-contract-v3.json);
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

Envelope v3 содержит closed `m1b-execution-plan-v2`: exact interpreter,
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

### 3. Global physical identity and no-reopen

Verifier-wide indices используют exact lexical path и opened physical
`(st_dev, st_ino)` для пяти input records, manifest roles, interpreter,
source/extension imports и native dependencies. Exact accepted reuse с тем же
digest использует cached bytes; digest drift отклоняется без reopen. Другой
lexical path к уже известному inode отклоняется после `fstat`, до content read.
Case folding не используется. Каждый descriptor получает ровно одну production
close attempt, а primary alias error не скрывается close failure.

### Adversarial P1: option-like manifest entrypoint

Дополнительный adversarial review показал, что exact argv grammar недостаточно,
если caller согласованно назовёт manifest-bound provider harness относительным
path, начинающимся с `-`. Registry теперь machine-exact требует
`raw_relative_posix_first_ascii_byte_not_hyphen`. Поэтому `-c`, `-m`, `-`,
`--`, `-E` и любое другое option-like raw path отклоняются даже при coherent
manifest, execution plan, admitted/observed envelope и runtime acceptance.
Это normative изменение сохранено в текущей generation-3 registry identity до
commit; operational authority по-прежнему не выдаётся.

### 4. Operationally satisfiable entrypoint transport

Generation 2 одновременно объявляла no-reopen mode и передавала provider
harness как cwd-relative pathname без descriptor transport. CPython должен был
бы повторно открыть pathname, а declared cwd делал repository-relative строки
неразрешимыми. Generation 3 устраняет этот противоречивый positive profile.

Provider entrypoint теперь передаётся только через typed inherited FD row:
`child_fd=3`, `process_path=/dev/fd/3`,
`transport=darwin_pipe_atomic_preload_v1`, exact provider role,
repository locator, digest и admitted byte count. Synthetic primitive делает
ровно один полный write cached admitted bytes размером `1..512` при
`PC_PIPE_BUF >= 512`, закрывает writer до любого возможного child и требует
exact readback с EOF. Wrong/reused/duplicate/closed FD, wrong pipe type/access/
inheritability, missing/extra transport, short write, early/extra EOF, byte или
digest mismatch и любой close failure отклоняются. Mutation source pathname
после admission не меняет cached transport bytes.

Это доказывает bounded transport primitive, но не реальный macOS launcher.
Closed plan поэтому обязан сохранять blockers
`INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN`,
`LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN` и
`ROLE_IMPORT_TRANSPORT_UNPROVEN`. Synthetic success остаётся только
`SYNTHETIC_CONFORMANCE_ONLY`; executable admission не выдан.

## Validation evidence

Final validation results:

- targeted M1B TCB-contract suite: `72/72`;
- public fixture in-process and through production CLI: `218/218` each;
- platform-independent physical-alias fault injection: `6/6`;
- atomic entrypoint transport, FD lifecycle and close-failure matrix: `11/11`;
- every public controlled CLI failure: non-zero, empty stderr and leakage-free;
- historical owner-freeze suite: `25/25`;
- historical M1B suite: `79/79`;
- full research discovery: `249/249`;
- docs validation: `37` Markdown files, `39` fenced blocks, `55` tables,
  `87` relative links, `0` errors;
- protected explicit identity comparison: `8/8` byte-identical to base;
- independent Python and Ruby contract framing: exact agreement;
- final HEAD/upstream/remote/PR parity: required post-push evidence recorded
  outside these self-referential committed bytes.

Controlled failures обязаны иметь non-zero exit, empty stderr, fixed
allowlisted compact output и не раскрывать path/content/hash/marker/exception/
traceback. Manifest-listed bytes не импортируются и не исполняются.

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

Explicit protected comparison: `8/8` files byte-identical to approved base.
Accepted protocol, owner-freeze and historical test identities remain covered
by the green `25/25`, `79/79` and full `249/249` results above.

## Boundaries and blockers

`SYNTHETIC_CONFORMANCE_ONLY` не выдаёт operational admission. Реальные
four-role bytes, owner-controlled implementation/runtime acceptance, proven
interpreter path exec, launcher opened-byte handoff, descriptor transport для
остальных role imports, native dependency closure, context/output binding,
persistence, residency, lifecycle, prompt/template bytes и real candidate
identities отсутствуют.
`PARTIAL_REPORT_CANNOT_BE_COMPLETE` сохраняется.

```text
M1B-1A0 CONTRACT: READY_FOR_REVIEW
EXECUTABLE_TCB_ADMISSION: NOT_GRANTED
EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN: PRESERVED
OWNER_FREEZE: ACCEPTED
STABLE_READ_HARDENING: ACCEPTED
M1B-1A PROVIDER EXECUTION: NOT_STARTED
M1B: NOT_EVALUATED
M1A: BLOCKED
M2: FORBIDDEN
```

Следующий разрешённый gate только после review и merge PR #8 — отдельное
задание на реальные four-role surfaces и owner-controlled implementation/runtime
admission. Даже merge не разрешает Ollama probe, model call, private corpus,
benchmark execution, product CLI или M2.
