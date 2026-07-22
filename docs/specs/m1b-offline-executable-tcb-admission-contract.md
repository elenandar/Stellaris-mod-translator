# Offline executable/TCB admission contract M1B-1A0

- Milestone: `M1B-1A0 — Offline executable/TCB admission contract`
- Contract schema: `m1b-offline-executable-tcb-contract-v1`
- Contract version: `m1b-offline-executable-tcb-admission-v1`
- Contract generation: `1`
- Execution-envelope schema/generation: `m1b-execution-envelope-v1` / `1`
- Preserved benchmark protocol: `m1b-benchmark-contract-v7`, generation `108`
- Review state: `M1B-1A0 CONTRACT: READY_FOR_REVIEW`
- Admission state: `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`
- Identity blocker: `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN: PRESERVED`

Этот contract определяет fail-closed форму будущего доказательства exact
executable bytes, CPython runtime, import closure и invocation state. Он не
принимает текущий `m1b_contract.py`, не создаёт four-role implementation, не
разрешает provider execution и не снимает ни один live blocker.

Текущий repository нельзя считать four-role TCB: один исторический module
совмещает несколько логических ролей, отдельный `provider_request_harness`
отсутствует, а manifest v1 сам по себе не связывает runtime, imports и
invocation. Поэтому successful offline verification ниже означает только
synthetic contract conformance.

## Contract identity

Normative machine-readable bytes находятся в
[`registry/m1b/offline-executable-tcb-contract-v1.json`](../../registry/m1b/offline-executable-tcb-contract-v1.json).
Файл — compact sorted-key ASCII JSON плюс ровно один LF; root closed schema имеет
поля `contract_generation`, `contract_schema`, `contract_version`, `digest_framing`,
`execution_envelope`, `implementation_acceptance`, `implementation_manifest`,
`limits`, `offline_verifier`, `protocol_generation`, `status_policy`.

Contract не содержит собственного digest. Его external review identity:

```text
SHA-256(
  ASCII("stellaris-m1b-offline-executable-tcb-contract-v1") || NUL ||
  u64be(len(canonical_contract)) || canonical_contract
)
= 589cf895c659b57c2f44268acfa0bf33b3c98d6cd5e6b4fea1f2f9b2500d1a5f
```

Этот digest фиксируется во внешнем review document и в предъявляемом execution
envelope. Он не является owner-accepted operational admission. После фиксации
этой review identity любое изменение normative contract bytes требует нового
contract generation и нового external review; protocol v7/generation 108 этим
contract-only этапом не изменяется.

## Trust boundary и запрещённые доказательства

Будущий admission требует внешнего owner-controlled решения над exact manifest,
exact envelope и launcher/opened-byte chain. Caller-supplied records, даже
внутренне согласованные и успешно проверенные, не создают authority. Fixture,
expected hash, Git SHA, clean tree, merge, `status=ok`, report self-assertion,
`sys.version`, `sys.executable`, `__file__`, mtime/size, `pip freeze` и
same-process token также не являются trust root.

Runtime snapshot, заявленный тем же процессом, не доказывает отсутствие hostile
reflection, monkeypatching, import hooks, debugger или tracing. Отдельная
hostile-process authority boundary остаётся вне M1B-1A0. Verifier не экспортирует
`_FullDecisionAdmission`, live capability, `proven` implementation identity или
benchmark admission.

## Layer 1: executable manifest v1

Accepted семантика `m1b-implementation-identity-policy-v2` остаётся
byte-identical. Manifest имеет ровно поля:

| Object | Exact fields |
|---|---|
| root | `files`, `implementation_generation`, `manifest_schema` |
| file row | `path`, `role`, `sha256` |

`manifest_schema` равен `m1b-executable-implementation-manifest-v1`, а
`implementation_generation` — positive exact JSON integer, не `bool`.

Manifest содержит ровно по одному file row для каждой роли:

1. `analysis_engine`;
2. `contract_validator`;
3. `provider_request_harness`;
4. `synthetic_fixture_materializer`.

Каждая роль назначается отдельному unique repository file. Paths — unique
relative POSIX raw-ASCII strings в raw-ASCII order. Lexical uniqueness
недостаточна: четыре уже открытых role files обязаны иметь четыре разные
physical identities `(st_dev, st_ino)`, включая case-insensitive filesystem.
Ни один role file не может физически alias-ить contract, manifest, acceptance
или envelope input record. Absolute path, empty component, `.`, `..`, repeated
separator, backslash, NUL, control character и non-ASCII запрещены. Leaf обязан
быть regular non-symlink file с `st_nlink == 1`. Manifest не включает себя,
contract registry или собственный digest.

Canonical manifest — compact sorted-key ASCII JSON плюс ровно один LF. External
manifest digest вычисляется только из этих exact bytes:

```text
SHA-256(
  ASCII("stellaris-m1b-executable-manifest-v1") || NUL ||
  u64be(len(canonical_manifest)) || canonical_manifest
)
```

Каждый `sha256` bind-ит exact bytes фактически прочитанного уже открытого file
descriptor. Проверка pathname с последующим reopen запрещена.

### External implementation acceptance record

Будущий external record имеет ровно пять полей:

```text
acceptance_state
implementation_generation
manifest_schema
manifest_sha256
protocol_generation
```

Для формы будущего acceptance требуется `acceptance_state=owner_accepted` и
exact linkage к manifest/generation/protocol `108`. M1B-1A0 не создаёт реальный
operational record: synthetic fixture проверяет только closed shape и linkage.
`proposed`, `retired`, mismatched либо self-asserted `proven` отклоняются.

## Descriptor-rooted stable bytes

Repository root открывается один раз component-wise с `O_NOFOLLOW`,
`O_DIRECTORY` и `O_CLOEXEC`; root symlink, relative root, path ambiguity и
platform без нужных no-follow primitives fail closed. Все input records,
manifest files, interpreter bytes, source/extension import bytes и declared
invocation `cwd` открываются относительно уже открытых directory descriptors.
`cwd` обязан быть stable directory identity, открытой component-wise с
`O_NOFOLLOW`, `O_DIRECTORY` и `O_CLOEXEC`; missing, regular file, symlink,
replacement или metadata drift fail closed. Containment проверяется на каждом
component.

Reader:

- принимает только regular single-link leaf;
- фиксирует descriptor metadata и physical `(st_dev, st_ino)` до чтения;
- накапливает short positive reads до exact declared size;
- выполняет bounded extra read и post-read `fstat`/directory-entry identity
  checks;
- отклоняет premature EOF, growth, shrink, replacement и metadata drift;
- читает и хеширует bytes уже открытого descriptor;
- выполняет ровно одну production close attempt для каждого открытого FD;
- не возвращает bytes или success после close failure.

Если уже существует controlled primary error, close failure не заменяет его и
не вызывает retry. Intentionally-open descriptors fault-injection tests очищают
сохранённым native close только вне production path.

## Layer 2: execution envelope v1

Envelope — canonical closed JSON с exact root fields:

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

Все identity fields atomically совпадают с canonical contract, manifest,
acceptance record и protocol generation `108`. `admitted_state` и
`observed_state` имеют одинаковую closed shape и должны быть semantically
byte-for-byte equivalent после canonical encoding. Это обнаруживает drift между
принятым profile и observation, но caller, согласованно подменивший обе стороны,
не становится authority.

Каждый state имеет ровно поля `bytecode`, `environment`, `imports`,
`interpreter`, `invocation`, `native_dependencies`, `runtime_hooks`.

### Interpreter identity

Interpreter object имеет ровно:

```text
abi_flags
byteorder
cache_tag
executable_path
executable_sha256
extension_suffix
implementation
machine
max_unicode
platform
pointer_bits
soabi
version_tuple
```

`implementation` равен `cpython`; v1 фиксирует CPython 3.9 runtime family.
`version_tuple` закрыто bind-ит exact `major`, `minor`, `micro`, `releaselevel`,
`serial` через five-element tuple с exact integer/string types; `cache_tag`
обязан соответствовать major/minor. `abi_flags`, `byteorder`, `machine`,
`platform`, `pointer_bits`, `max_unicode`, `soabi` и `extension_suffix` bind-ят
остальную ABI-relevant runtime state. Upgrade runtime family либо изменение
набора ABI fields требует новой contract generation. `executable_path` — только
repository-root-relative locator: verifier обязан открыть его descriptor-rooted
и сравнить SHA-256 exact executable bytes. Path, version string или digest без
opened bytes недостаточны.

Фактический future launcher дополнительно обязан bind-ить platform/loader ABI и
использовать именно admitted opened bytes либо доказанный immutable equivalent.
Текущий contract-only verifier ничего не запускает.

### Exact import closure

Import row имеет ровно `kind`, `module`, `path`, `sha256`. `kind` — один из
`source`, `extension`, `builtin`, `frozen`; module names unique, а rows идут в
exact declared execution order.

- `source`: relative path открывается один раз; `sha256` bind-ит exact source
  bytes, которые будущий launcher обязан исполнить без path reopen;
- `extension`: relative path открывается один раз; `sha256` bind-ит exact native
  binary bytes;
- `builtin` и `frozen`: `path=null`, а `sha256` равен exact interpreter digest;
  их code identity тем самым связана с interpreter bytes.

Повторный path использует уже admitted in-memory bytes/digest и не открывается
заново. Missing, extra, reordered или duplicate module, source/extension hash
drift, builtin/frozen interpreter mismatch и path shadowing fail closed.
Фактический import order остаётся внешним launcher evidence; равенство двух
caller fields не доказывает, что Python исполнил именно их.

### Bytecode policy

Bytecode object имеет `cache_mode`, `dont_write_bytecode`,
`executed_bytecode`, `pycache_prefix`. V1 выбирает только fail-closed policy:

- `cache_mode=sealed_empty`;
- `dont_write_bytecode=true`;
- `executed_bytecode=[]`;
- `pycache_prefix=null`.

`-B` запрещает запись `.pyc`, но не доказывает, что stale bytecode не читался.
Поэтому non-empty cache, `.pyc` import или caller-claimed `-B` без sealed empty
cache отклоняются. Поддержка bind-инга фактически исполненного bytecode потребует
новой contract generation.

### Invocation, environment и hooks

Invocation object имеет ровно `argv`, `cwd`, `inherited_fds`, `mode`,
`python_flags`, `stdio`, `sys_path`, `warnoptions`, `xoptions`.

- `mode=verified_open_descriptors_no_reopen`;
- `argv`, `cwd` и ordered `sys_path` exact, closed и одинаковы в admitted и
  observed states; relative `cwd` дополнительно открывается descriptor-rooted
  как stable no-follow directory identity и не переоткрывается по pathname;
- `sys_path` содержит только declared rooted runtime/repository entries;
  ambient cwd, user site, system site и unknown entry запрещены;
- `python_flags` закрыто bind-ит exact CPython 3.9 `sys.flags` fields:
  `bytes_warning`, `debug`, `dev_mode`, `dont_write_bytecode`,
  `hash_randomization`, `ignore_environment`, `inspect`, `interactive`,
  `isolated`, `no_site`, `no_user_site`, `optimize`, `quiet`, `utf8_mode`,
  `verbose`; integer fields требуют exact `int`, а единственный boolean
  `dev_mode` — exact `bool`;
- `warnoptions` empty; `xoptions` содержит только frozen allowlist;
- каждый `stdio` stream закрыто bind-ит exact `fd`, access `mode` и target
  (`devnull` либо captured pipe); v1 требует `inherited_fds=[]`, поэтому любой
  дополнительный inherited FD запрещён.

Environment object имеет `ambient_inheritance=false`, `policy=empty`,
`variables=[]`. `PYTHONPATH`, `PYTHONHOME`, user/site/startup configuration и
любая неизвестная ambient variable не наследуются.

Runtime-hooks object имеет `debugger_attached`, `meta_path`, `path_hooks`,
`profile_hook`, `startup_hooks`, `trace_hook`. Debugger/trace/profile должны быть
false, startup hooks empty, а import hooks — exact frozen builtin allowlist,
связанный с interpreter identity. Любой extra/missing/reordered hook fail closed.

### Native/dyld closure

Native dependency object имеет `blocker`, `dependencies`, `status`; row —
`install_name`, `path`, `sha256`.

V1 различает:

- `bound`: every exact dependency byte externally admitted и использован без
  reopen;
- `unproven`: `dependencies=[]` и blocker
  `NATIVE_DEPENDENCY_CLOSURE_UNPROVEN` обязательно сохраняется.

Текущий synthetic positive case использует `unproven`. Поэтому даже valid
envelope не является operational success. Silent empty/bound claim, unbound
extension dependency или удаление blocker отклоняются.

## Independent offline verifier

[`tools/research/m1b_tcb_contract.py`](../../tools/research/m1b_tcb_contract.py)
поддерживает Python 3.9 standard library only и имеет единственный CLI:

```sh
python3 tools/research/m1b_tcb_contract.py verify \
  EXPLICIT_CONTRACT_RELATIVE_PATH \
  EXPLICIT_MANIFEST_RELATIVE_PATH \
  EXPLICIT_ACCEPTANCE_RELATIVE_PATH \
  EXPLICIT_ENVELOPE_RELATIVE_PATH \
  EXPLICIT_ABSOLUTE_REPOSITORY_ROOT
```

Default paths, stdin, fixture/materialize/report mode, cwd/home/environment
discovery отсутствуют. Verifier не импортирует historical M1B validators, не
импортирует и не исполняет manifest/import files, не вызывает subprocess,
network, provider, Ollama, corpus, game или Workshop.

Finite limits из registry:

| Surface | Limit |
|---|---:|
| each JSON input | `262144` bytes |
| each executable/import file | `8388608` bytes |
| total unique executable/import bytes | `33554432` bytes |
| import rows | `512` |
| native dependency rows | `256` |
| JSON sequence entries | `1024` |
| one JSON string | `4096` UTF-8 bytes |

JSON parser принимает только strict UTF-8 single value, отклоняет BOM,
duplicate keys, trailing data, float, NaN/Infinity, lone surrogate, oversized
integer и integer outside signed 64-bit lexical range. Closed integer fields
требуют exact `int`; `bool` не принимается.

Stdout — один compact ASCII JSON object с allowlisted `status`, `codes`,
`counts`; stderr всегда empty. Failure возвращает non-zero и не выводит path,
hash, input bytes, marker, numeric token, exception или traceback. Success
возвращает controlled code `SYNTHETIC_CONFORMANCE_ONLY`, а не admission token.

## Public synthetic fixture

[`fixtures/m1b/tcb-admission/cases.json`](../../fixtures/m1b/tcb-admission/cases.json)
и его [README](../../fixtures/m1b/tcb-admission/README.md) содержат только
вымышленные metadata и mutations. Four role files, interpreter placeholder и
source/extension bytes материализуются тестом только во временном repository
root и никогда не импортируются или исполняются. Production verifier не имеет
fixture materializer.

Matrix покрывает strict input, manifest roles/paths/canonical bytes/digest,
external linkage, runtime/import/invocation drift, stale bytecode,
native-closure blocker, descriptor replacement, lifecycle/fault injection и
no-leak output. Case ID, expected result, fixture digest и Git provenance —
test evidence, не trust root.

## Preserved identities, blockers и gate

Byte-identical сохраняются accepted owner-freeze records, historical M1B
validator/fixtures/tests и protected M1A surface. Также сохраняются protocol
v7/generation 108, 17 component identities, bundle
`50f51b3cf9be042ebc310d1a6c57791dd31a43362778798455d7ea9678c31e06`
и owner-freeze snapshot
`df84871be332ee52c315d0c0cc1a7a0046251352a2a0131382b5cb994cffcb58`.

Независимо остаются:

- `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN`;
- `NATIVE_DEPENDENCY_CLOSURE_UNPROVEN`;
- `CONTEXT_LIMIT_BINDING_UNPROVEN`;
- `PROVIDER_PERSISTENCE_UNPROVEN`;
- `RESIDENCY_UNPROVEN`;
- `OUTPUT_LIMIT_BINDING_UNPROVEN`;
- `LIFECYCLE_STATE_UNPROVEN`;
- missing frozen prompt/template bytes;
- missing real candidate identities;
- `PARTIAL_REPORT_CANNOT_BE_COMPLETE`.

Gate после review этого contract-only change:

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

После review и merge разрешено только отдельное задание на реальные four-role
surfaces и external implementation/runtime admission. Даже merge этого contract
не разрешает Ollama probe или model call.
