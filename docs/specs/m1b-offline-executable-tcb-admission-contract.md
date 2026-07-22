# Offline executable/TCB admission contract M1B-1A0

- Milestone: `M1B-1A0 — Offline executable/TCB admission contract`
- Contract schema: `m1b-offline-executable-tcb-contract-v4`
- Contract version: `m1b-offline-executable-tcb-admission-v4`
- Contract generation: `4`
- Execution-envelope schema/generation: `m1b-execution-envelope-v4` / `4`
- Runtime-acceptance schema/generation: `m1b-runtime-execution-envelope-acceptance-v1` / `1`
- Execution-plan schema/generation: `m1b-execution-plan-v3` / `3`
- Preserved benchmark protocol: `m1b-benchmark-contract-v7`, generation `108`
- Remediation state: `REMEDIATION: READY_FOR_REVIEW`
- Review state: `M1B-1A0 CONTRACT: READY_FOR_REVIEW`
- Authorization gate: `M1B-1A1-AUTH: OWNER_REVIEW_REQUIRED`
- Candidate construction: `CANDIDATE CONSTRUCTION: NOT_AUTHORIZED`
- Admission state: `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`
- Owner-decision blocker: `EXECUTABLE_TCB_OWNER_DECISION_REQUIRED: PRESERVED`
- Provider-source blocker: `PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN: PRESERVED`
- Identity blocker: `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN: PRESERVED`

Этот contract определяет fail-closed форму будущего доказательства exact
executable bytes, CPython runtime, import closure, execution plan и invocation
state. Он не принимает текущий `m1b_contract.py`, не создаёт реальную four-role
implementation, не разрешает provider execution и не снимает ни один live
blocker. Successful offline verification означает только
`SYNTHETIC_CONFORMANCE_ONLY`.

Generation 2 исправила три связанные ambiguity generation 1: exact envelope
не был связан с external runtime acceptance, invocation не связывала
interpreter и manifest roles, а lexical cache не предотвращал повторное чтение
одного physical inode через case alias. Generation 3 заменяет невыполнимый
pathname script plan на typed descriptor-backed provider transport и отделяет
repository locator, OS exec target, `argv[0]`, process cwd и `sys_path`.
Generation 4 дополнительно закрывает directory-alias, cross-purpose file reuse,
provider-source eligibility и mid-protocol pipe-substitution gaps generation 3.
Generation 1, 2 и 3 не являются допустимой identity для generation-4
semantics.

## Contract identity

Normative machine-readable bytes находятся в
[`registry/m1b/offline-executable-tcb-contract-v4.json`](../../registry/m1b/offline-executable-tcb-contract-v4.json).
Файл — compact sorted-key ASCII JSON плюс ровно один LF. Root closed schema
имеет поля `contract_generation`, `contract_schema`, `contract_version`,
`digest_framing`, `execution_envelope`, `implementation_acceptance`,
`implementation_manifest`, `limits`, `offline_verifier`,
`protocol_generation`, `runtime_acceptance`, `status_policy`.

Contract не содержит self-hash. Его external review identity:

```text
SHA-256(
  ASCII("stellaris-m1b-offline-executable-tcb-contract-v4") || NUL ||
  u64be(len(canonical_contract)) || canonical_contract
)
= ad6bce1a5c516753d79ee0d807f5445e9b860a398e661adfb9730d9c4fee9c31
```

Length включает завершающий LF. Digest фиксируется внешним review document и
не является operational admission. Любое дальнейшее изменение normative bytes
требует новой identity и review; protocol v7/generation 108 не меняется.

## Trust boundary и запрещённые доказательства

Будущий admission требует отдельного owner-controlled решения над уже
известными exact implementation acceptance, runtime acceptance, manifest,
envelope и launcher/opened-byte chain. Caller-supplied records, даже полностью
согласованные и содержащие `owner_accepted`, подтверждают только closed shape
и linkage. Они не становятся trust root и не снимают
`EXECUTABLE_TCB_OWNER_DECISION_REQUIRED`. Задание, создающее candidate bytes,
не может в том же gate принять созданные им identities. Реальный
owner-controlled expected record identity должен поступать из канала, не
контролируемого caller; M1B-1A0 такой operational канал не создаёт.

Fixture, expected hash, Git SHA, clean tree, merge, `status=ok`, report
self-assertion, `sys.version`, `sys.executable`, `__file__`, mtime/size,
`pip freeze` и same-process token не являются authority. Runtime snapshot того
же процесса не доказывает отсутствие hostile reflection, monkeypatching,
import hooks, debugger или tracing. Verifier не экспортирует admission
capability, live token, `proven` identity или benchmark permission.

## Layer 1: executable manifest v1

Accepted семантика `m1b-implementation-identity-policy-v2` остаётся
byte-identical. Manifest имеет ровно поля:

| Object | Exact fields |
|---|---|
| root | `files`, `implementation_generation`, `manifest_schema` |
| file row | `path`, `role`, `sha256` |

`manifest_schema=m1b-executable-implementation-manifest-v1`.
`implementation_generation` — positive exact JSON integer, не `bool`.
Manifest содержит ровно по одному unique file для ролей:

1. `analysis_engine`;
2. `contract_validator`;
3. `provider_request_harness`;
4. `synthetic_fixture_materializer`.

Paths — unique relative POSIX raw-ASCII strings в raw-ASCII order. Absolute,
empty component, `.`, `..`, repeated separator, backslash, NUL, control и
non-ASCII запрещены. Manifest не включает себя, любой input record, contract
registry или собственный digest. Leaf — regular non-symlink single-link file.

Canonical manifest — compact sorted-key ASCII JSON плюс LF. External digest:

```text
SHA-256(
  ASCII("stellaris-m1b-executable-manifest-v1") || NUL ||
  u64be(len(canonical_manifest)) || canonical_manifest
)
```

Каждый row digest сравнивается с raw SHA-256 exact bytes уже открытого file
descriptor. Pathname check с последующим reopen запрещён.

### Existing external implementation acceptance

Существующий record остаётся ровно пяти-field и не расширяется:

```text
acceptance_state
implementation_generation
manifest_schema
manifest_sha256
protocol_generation
```

Synthetic shape требует `acceptance_state=owner_accepted` и exact linkage к
manifest/generation/protocol 108. Это caller-supplied значение проверяет только
форму и linkage; оно не выражает operational owner decision. `proposed`,
`retired`, mismatched либо self-asserted `proven` отклоняются. Этот record
связывает implementation manifest; он не заменяет новый runtime acceptance и
не снимает `EXECUTABLE_TCB_OWNER_DECISION_REQUIRED`.

## Descriptor-rooted stable bytes и global identity

Verifier принимает ровно пять explicit repository-relative record paths:
contract, manifest, implementation acceptance, execution envelope и runtime
acceptance. Repository root открывается component-wise с `O_NOFOLLOW`,
`O_DIRECTORY`, `O_CLOEXEC`; root symlink, relative root, ambiguity или platform
без primitives fail closed.

Отдельный verifier-wide file index содержит:

- exact lexical relative path;
- physical identity `(st_dev, st_ino)`;
- admitted raw digest, bytes и surface kind.

Политика применяется к пяти records, четырём manifest roles, interpreter,
source/extension imports и native dependencies. Любой reuse executable file
дополнительно проходит closed purpose matrix с default deny:

- matching non-provider manifest role, matching plan role и matching source
  import могут ссылаться на один admitted file;
- provider manifest role, plan entrypoint и descriptor transport могут
  ссылаться на один admitted file;
- interpreter, plan interpreter, invocation `argv0`/`os_exec_target` и
  pathless builtin/frozen imports могут ссылаться на один admitted interpreter;
- standalone source import, standalone extension import и native dependency
  имеют ровно один purpose каждый; два path-bearing import rows не могут иметь
  один lexical path независимо от module/kind.

Любое иное cross-purpose сочетание отклоняется. Разрешённый exact повтор с тем
же expected digest bind-ит новый разрешённый purpose к admitted bytes и
identity без open/read. Exact повтор с другим digest либо запрещённым purpose
отклоняется без reopen. Другой lexical path, чей открытый descriptor имеет уже
известный physical identity, отклоняется после `fstat`, но до чтения content.
`.lower()` и `casefold()` не являются identity evidence. Input record никогда
не переиспользуется как executable surface.

Reader принимает только regular single-link leaf, фиксирует descriptor
metadata до чтения, накапливает short positive reads, выполняет bounded extra
read и post-read `fstat`/directory-entry checks, отклоняет EOF/growth/shrink,
replacement и metadata drift. Каждый успешно открытый descriptor получает
ровно одну production close attempt. Alias primary error сохраняется при
injected close failure; retry отсутствует.

Directory identity хранится отдельно от file identity. `cwd` и каждый
`sys_path` открываются component-wise descriptor-rooted с `O_NOFOLLOW`,
`O_DIRECTORY`, strict pre/post `fstat`, stable parent-entry identity и ровно
одной close attempt. Отдельные lexical и physical directory indices запрещают
exact cwd/sys_path reuse, повтор одного sys_path, case alias и любую другую
physical alias identity. Replacement, metadata drift, stat/open ambiguity и
close failure fail closed. Разные lexical paths с разными physical identities
разрешены. Этот directory snapshot доказывает только stable directory
identity; он не доказывает import transport или bytes, открытые будущим child.

## Layer 2: execution envelope v4

Envelope — closed canonical JSON с exact root fields:

```text
admitted_state
contract_generation
contract_schema
contract_sha256
contract_version
envelope_generation
envelope_schema
implementation_generation
manifest_schema
manifest_sha256
observed_state
protocol_generation
```

Identity fields совпадают с actual canonical contract, actual manifest,
implementation acceptance и protocol 108. `admitted_state` и `observed_state`
имеют одинаковую closed shape и exact semantic canonical equality. Это
обнаруживает drift, но caller, согласованно изменивший обе стороны, не
становится authority.

Canonical envelope — compact sorted-key ASCII JSON плюс ровно один LF. Его
external digest охватывает весь envelope, включая оба state:

```text
SHA-256(
  ASCII("stellaris-m1b-execution-envelope-v4") || NUL ||
  u64be(len(canonical_envelope)) || canonical_envelope
)
```

Verifier сначала доказывает exact canonical input bytes, затем хеширует именно
их. Raw SHA-256, другой domain, пропущенный NUL, другая length encoding или
length без LF не эквивалентны framed digest.

### External runtime/execution-envelope acceptance v1

Отдельный runtime acceptance record имеет ровно 16 fields:

```text
contract_generation
contract_schema
contract_sha256
contract_version
envelope_digest_domain
envelope_digest_framing
envelope_generation
envelope_schema
envelope_sha256
implementation_generation
manifest_schema
manifest_sha256
protocol_generation
runtime_acceptance_generation
runtime_acceptance_schema
runtime_acceptance_state
```

Exact constants:

- `runtime_acceptance_schema=m1b-runtime-execution-envelope-acceptance-v1`;
- `runtime_acceptance_generation=1`;
- `runtime_acceptance_state=owner_accepted` для synthetic closed-shape case;
- `envelope_digest_domain=stellaris-m1b-execution-envelope-v4`;
- `envelope_digest_framing=sha256_domain_nul_u64be_length_canonical_envelope`.

Record atomically связывает actual contract schema/version/generation/framed
digest, actual manifest schema/implementation generation/framed digest, exact
envelope schema/generation/framed digest и protocol 108. Coherent изменение
обоих envelope states при неизменном record даёт digest mismatch.

Record canonicalization — compact sorted-key ASCII JSON плюс LF. Он не содержит
self-hash. Его отдельная external identity domain:

```text
SHA-256(
  ASCII("stellaris-m1b-runtime-execution-envelope-acceptance-v1") || NUL ||
  u64be(len(canonical_runtime_acceptance)) ||
  canonical_runtime_acceptance
)
```

Synthetic verifier не получает owner-controlled expected value этого digest и
поэтому не может выдать admission. `proposed`, `retired`, self-asserted
`proven`, missing/extra/noncanonical/duplicate records и identity drift
отклоняются.

### Execution state

Каждый state имеет ровно поля `bytecode`, `environment`, `execution_plan`,
`imports`, `interpreter`, `invocation`, `native_dependencies`, `runtime_hooks`.

Interpreter object имеет ровно `abi_flags`, `byteorder`, `cache_tag`,
`executable_sha256`, `extension_suffix`, `implementation`, `machine`,
`max_unicode`, `platform`, `pointer_bits`, `repository_locator`, `soabi`,
`version_tuple`. V3 фиксирует exact CPython 3.9 ABI
profile. `repository_locator` — repository-root-relative locator; digest
проверяется по exact opened bytes. Это не доказывает, что macOS pathname-based
OS exec использует те же bytes: такой handoff остаётся явным blocker.

Import row имеет ровно `kind`, `module`, `path`, `sha256`; kind — `source`,
`extension`, `builtin` или `frozen`. Rows unique и ordered. Source/extension
bytes открываются один раз. Builtin/frozen имеют `path=null` и bind-ятся к
exact interpreter digest. Missing, extra, reordered, shadowed или empty import
closure fail closed.

Bytecode object имеет `cache_mode`, `dont_write_bytecode`,
`executed_bytecode`, `pycache_prefix`. Единственная policy:
`sealed_empty`, `true`, `[]`, `null`. Stale bytecode запрещён.

### Closed execution plan v3

Execution plan root имеет ровно:

```text
entrypoint
interpreter
launcher
plan_generation
plan_schema
role_imports
```

`plan_schema=m1b-execution-plan-v3`, `plan_generation=3`.

- plan interpreter имеет ровно `repository_locator`, `sha256` и exact
  совпадает с envelope interpreter locator/digest и уже admitted opened bytes;
- entrypoint имеет `mode`, `repository_locator`, `role`, `sha256`; mode равен
  `descriptor_script_file`, role — только `provider_request_harness`, а
  locator/digest/physical identity exact совпадают с manifest row. Первый
  ASCII byte raw relative repository locator не может быть `-`;
- launcher имеет `status=unproven` и exact blockers
  `INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN`,
  `LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN`,
  `PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN`,
  `ROLE_IMPORT_TRANSPORT_UNPROVEN`. Caller не может удалить их либо объявить
  launcher `proven`;
- каждый ordered `role_imports` row имеет `kind`, `module`, `path`, `role`,
  `sha256`; `kind=source`, а unique rows идут строго в порядке
  `analysis_engine`, `contract_validator`, `synthetic_fixture_materializer`.
  Каждый row соответствует ровно одному ordered source import row, exact
  manifest path/digest и уже admitted cache object. Provider harness не может
  одновременно быть import. Каждый role path разрешается ровно под одним
  declared `sys_path`.

Таким образом все четыре manifest roles связаны с declarative execution
surface. Role, path, digest или physical-identity swap, missing role,
unmanifested entrypoint, case alias и попытка repository reopen отклоняются.
Descriptor loader остальных трёх source roles ещё не доказан, поэтому linkage
не выдаёт operational admission.

Provider entrypoint source eligibility остаётся отдельным exact blocker.
Снять `PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN` может только будущий
admitted CPython, проверивший exact cached provider bytes, которые передаются
через descriptor transport. `ast.parse`, `compile` или иная проверка host
Python над pathname/повторно прочитанными bytes не является таким evidence и
не может снять blocker. Поэтому arbitrary synthetic bytes, включая invalid
UTF-8, NUL и синтаксически недопустимый Python, всё ещё могут пройти structural
synthetic conformance при обязательном сохранении blocker; это не утверждение,
что child CPython сможет исполнить их как source.

### Closed invocation

Invocation object имеет ровно `argv0`, `argv_tail`, `cwd`, `inherited_fds`,
`mode`, `os_exec_target`, `python_flags`, `stdio`, `sys_path`, `warnoptions`,
`xoptions`.

`argv0`, `os_exec_target`, `cwd` и каждый `sys_path` row — typed locator с
ровно `base`, `path`. Единственный base — `repository_root`; child cwd никогда
не является неявным base. `argv0.path` и `os_exec_target.path` exact совпадают
с interpreter repository locator, но остаются разными semantic fields.

Единственный `argv_tail`:

```text
[
  "-I",
  "-S",
  "-B",
  "-X",
  "utf8",
  "/dev/fd/3"
]
```

Последний argument — только canonical `/dev/fd/3`; repository locator никогда
не используется как cwd-relative script pathname. `/dev/fd/03`,
`/proc/self/fd`, обычный manifest path, `-c`, `-m`, `-`, `--`, unknown или
reordered flags и extra positionals запрещены. Запрет первого byte `-`
применяется к manifest-bound repository locator до invocation acceptance,
поэтому coherent option-like manifest/plan values не становятся mode switch.
`xoptions=["utf8"]`, `warnoptions=[]`.
`-I`, `-S`, `-B`, `-X utf8`
семантически совпадают с exact `python_flags`, empty environment и sealed
bytecode policy. `sys_path` non-empty и содержит только explicit
repository-root locators. `cwd` и каждый `sys_path` проходят отдельный
descriptor-rooted stable directory admission; exact или physical cwd/sys_path
reuse, duplicate sys_path и case alias запрещены. Эта проверка не заменяет
descriptor import transport.

`mode=typed_entrypoint_fd_no_repository_reopen`. `inherited_fds` содержит
ровно один closed typed row с полями `byte_count`, `child_fd`, `mode`,
`process_path`, `purpose`, `repository_locator`, `role`, `sha256`, `transport`.
Он требует `child_fd=3`, `mode=read`, `process_path=/dev/fd/3`,
`purpose=role=provider_request_harness`,
`transport=darwin_pipe_atomic_preload_v1` и exact manifest/plan/cache object.
`byte_count` равен длине cached admitted provider bytes и лежит в `1..512`.

Verifier materializes только synthetic transport primitive: fresh anonymous
pipe, non-inheritable read/write ends с правильными access modes, observed
`PC_PIPE_BUF >= 512`, один полный atomic write cached bytes, затем successful
writer close до любого возможного child и exact readback/EOF. До и после write
verifier повторно проверяет оба ends; после единственной successful close writer
он проверяет read end до и после каждого read и после EOF. Каждая проверка
связывает FIFO type, access mode, non-inheritability и stable physical identity
`(st_dev, st_ino)`. Controlled descriptor substitution в середине write/read
protocol fail closed. Short/zero write, wrong end/type/access/inheritability,
reused/duplicate descriptor, wrong bytes, extra/early EOF и любой close failure
тоже fail closed. Source pathname после admission не читается повторно и его
mutation не меняет snapshot bytes.

Это доказывает bounded primitive против проверяемой controlled substitution,
но не security boundary против hostile same-process monkeypatching/reflection.
JSON `child_fd=3` также не доказывает будущий live launcher handoff. macOS
interpreter exec остаётся
`INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN`, полный opened-byte handoff —
`LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN`, source eligibility —
`PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN`, а descriptor loader
остальных roles — `ROLE_IMPORT_TRANSPORT_UNPROVEN`. Launcher остаётся
`unproven`. Stdio exact bind-ит fd/mode/target: stdin — devnull, stdout/stderr —
captured pipes.

Environment имеет `ambient_inheritance=false`, `policy=empty`, `variables=[]`.
Runtime hooks запрещают debugger/trace/profile/startup и требуют exact builtin
import-hook allowlist.

### Native dependency closure

Native dependency object имеет `blocker`, `dependencies`, `status`; row —
`install_name`, `path`, `sha256`. `bound` требует every exact admitted
dependency byte без reopen. `unproven` требует `dependencies=[]` и blocker
`NATIVE_DEPENDENCY_CLOSURE_UNPROVEN`. Synthetic positive сохраняет `unproven`,
поэтому operational success невозможен.

## Independent offline verifier

[`tools/research/m1b_tcb_contract.py`](../../tools/research/m1b_tcb_contract.py)
использует только Python 3.9 stdlib и имеет единственный CLI:

```sh
python3 tools/research/m1b_tcb_contract.py verify \
  EXPLICIT_CONTRACT_RELATIVE_PATH \
  EXPLICIT_MANIFEST_RELATIVE_PATH \
  EXPLICIT_IMPLEMENTATION_ACCEPTANCE_RELATIVE_PATH \
  EXPLICIT_EXECUTION_ENVELOPE_RELATIVE_PATH \
  EXPLICIT_RUNTIME_ACCEPTANCE_RELATIVE_PATH \
  EXPLICIT_ABSOLUTE_REPOSITORY_ROOT
```

Аргументов всегда ровно шесть после `verify`; missing/extra fail closed.
Defaults, stdin, fixture/materialize/report, cwd/home/environment discovery
отсутствуют. Verifier не импортирует/исполняет manifest/import files, не
вызывает subprocess, network, provider, Ollama, corpus, game или Workshop.

Finite limits из registry:

| Surface | Limit |
|---|---:|
| each JSON input | `262144` bytes |
| each executable/import file | `8388608` bytes |
| total unique executable/import bytes | `33554432` bytes |
| atomic cached provider entrypoint | `512` bytes |
| import rows | `512` |
| native dependency rows | `256` |
| JSON sequence entries | `1024` |
| one JSON string | `4096` UTF-8 bytes |

JSON strict: one UTF-8 value, no BOM, duplicate key, trailing data, float,
NaN/Infinity, lone surrogate, oversized integer или out-of-range signed 64-bit
integer. Closed integers require exact `int`, не `bool`.

Stdout — один compact ASCII JSON object с fixed allowlisted `status`, `codes`,
`counts`; unknown uppercase internal code нормализуется в
`UNEXPECTED_FAILURE`. Stderr empty. Controlled failure non-zero и не выводит
path, hash, bytes, marker, numeric token, exception или traceback. Success
возвращает только `SYNTHETIC_CONFORMANCE_ONLY`, не capability или admission.

Global `status_policy.blockers` — exact ordered list; deletion, rename,
addition либо reorder fail closed:

```text
EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN
EXECUTABLE_TCB_OWNER_DECISION_REQUIRED
PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN
ROLE_IMPORT_TRANSPORT_UNPROVEN
LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN
INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN
NATIVE_DEPENDENCY_CLOSURE_UNPROVEN
CONTEXT_LIMIT_BINDING_UNPROVEN
PROVIDER_PERSISTENCE_UNPROVEN
RESIDENCY_UNPROVEN
OUTPUT_LIMIT_BINDING_UNPROVEN
LIFECYCLE_STATE_UNPROVEN
MISSING_PROMPT_BYTES
MISSING_TEMPLATE_BYTES
MISSING_REAL_CANDIDATE_IDENTITIES
PARTIAL_REPORT_CANNOT_BE_COMPLETE
```

Plan launcher отдельно сохраняет exact ordered subset:
`INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN`,
`LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN`,
`PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN`,
`ROLE_IMPORT_TRANSPORT_UNPROVEN`.

## Public synthetic fixture

[`fixtures/m1b/tcb-admission/cases.json`](../../fixtures/m1b/tcb-admission/cases.json)
и его [README](../../fixtures/m1b/tcb-admission/README.md) содержат только
synthetic mutations под schema `m1b-tcb-admission-cases-v5`. Four role files,
interpreter и imports материализуются
тестом во временном root и не исполняются.

Final fixture identity: `241` unique cases, `73746` exact compact sorted-key
UTF-8 JSON bytes plus one LF,
SHA-256
`b729305612bdf5f3e88d42a90603cf6a10b2100bd31b144c28399a155984d862`.
Final verifier identity: `104137` bytes, SHA-256
`242b115d6eb8f7df143eeeccc94c2b7029dc1a7b601d9a29bd436a183e446551`.
Они независимо пересчитаны после завершения normative bytes; generation-1,
generation-2 и generation-3 values не являются evidence v4.

Matrix обязана покрыть runtime acceptance binding, closed execution plan,
typed repository locators, exact `/dev/fd/3` argv, atomic cached-byte pipe
transport, pre/post FD type/access/inheritability/physical identity,
mid-protocol substitution и close lifecycle, explicit launcher blockers,
provider source-eligibility preservation, all-role linkage, closed file-purpose
matrix, global file alias/no-reopen, separate cwd/sys_path lexical/physical
directory identity, stable-read lifecycle и controlled no-leak output. Deep envelope
mutations explicitly обновляют runtime acceptance digest, чтобы проверять deep
validator; отдельный stale-binding case оставляет record неизменным.

## Preserved identities, blockers и gate

Byte-identical сохраняются accepted owner-freeze records, historical M1B
validator/fixtures/tests и protected M1A surface. Также сохраняются protocol
v7/generation 108, 17 component identities, bundle
`50f51b3cf9be042ebc310d1a6c57791dd31a43362778798455d7ea9678c31e06`
и owner-freeze snapshot
`df84871be332ee52c315d0c0cc1a7a0046251352a2a0131382b5cb994cffcb58`.

Независимо остаются blockers:
`EXECUTABLE_TCB_OWNER_DECISION_REQUIRED`, executable implementation identity,
`PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN`,
`INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN`,
`LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN`, `ROLE_IMPORT_TRANSPORT_UNPROVEN`, native
dependency closure, context/output binding, persistence, residency, lifecycle,
missing frozen prompt/template bytes, real candidate identities и
`PARTIAL_REPORT_CANNOT_BE_COMPLETE`.

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
на создание candidate. После merge доступен только отдельный
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
provider/model call, private corpus или benchmark: для исполнения нужен ещё
один явный gate.
