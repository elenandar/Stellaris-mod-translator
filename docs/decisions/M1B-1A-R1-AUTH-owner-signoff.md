# Owner signoff M1B-1A-R1-AUTH v8

Decision: `owner_accepted` for the exact authorization bytes below only.

Effect: `after_review_and_merge_to_main`.

This record does not merge PR #11, mark it ready or enable auto-merge. It does
not authorize R1 remediation before the exact owner-controlled merge. It does
not authorize repository/candidate execution, provider/Ollama/model calls,
M1B-1A2, benchmark, product translation, publishing, M2 or product CLI.

## Accepted exact artifacts

I accept these exact identities as the complete v8 authorization decision:

| Artifact | Bytes | Raw SHA-256 |
|---|---:|---|
| `registry/m1b/m1b-1a-r1-remediation-scope-v8.json` | `372231` | `47a86a8560f35f2a95528e466642f4c4d8538b848efc00d268df6da4c8e3dcf7` |
| `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json` | `27477` | `92f3d2ae13ebe373b352ecb99efd1ff56cc3871d2a57c6aa3f742fdb398a3a34` |
| `docs/specs/m1b-1a-r1-remediation-authorization-contract.md` | `18394` | `17c53e78c7c1f300d5e1f5a71b137279a9b89e1cc7051bf85bacf1a226c8ccb9` |

The scope schema is `m1b-1a-r1-remediation-scope-v8`, generation `8`. Its
framing domain is `stellaris-m1b-1a-r1-remediation-scope-v8`; the framed
SHA-256 is:

`99a778344c2f3e548a91a65c7b1ba56c2a6664fda932e907aa1d79ca55b1892e`.

The owner schema is
`m1b-1a-r1-remediation-owner-authorization-v8`. Scope and owner JSON are strict
ASCII sorted-key compact JSON with one LF. Duplicate keys, floats, `NaN` and
Infinity are rejected.

Scope v1 was never effective. Scopes v2, v3, v4, v5, v6 and v7 were superseded
before effect. None authorizes PR #10 retroactively.

## Exact effect boundary

PR #10 remains `MERGED_OWNER_CONTROLLED_SCOPE_DEVIATION`, with head
`66f905cf266b9d1c1f56d0d706184387ffedb36e`, merge
`3c6ca3146d838b977f24bbc6b8c79dfb271e142b`, tree
`289e2396975c5ef6fe1001a7c5990523edaa06c5`, exact paths `11`, and candidate
state `INERT_NOT_ADMITTED`.

PR #11 is the only authorization PR:

- repository `elenandar/Stellaris-mod-translator`;
- base `main`;
- historical base and required merge first parent
  `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- head branch `agent/m1b-1a-r1-transport-provenance-auth`;
- recovery integration merge
  `3a57701275914d905f76606cf6db3072c40a17ac`.

Effect requires the final reviewed PR #11 head as the exact second parent of
one ordinary external owner-controlled two-parent merge. The PR and merge
deltas must contain exactly the five documentation/owner paths and scope v8
listed by the contract. Scopes v1 through v7 must be absent. Any different
base, path set, parent order or identity blocks effect.

## Accepted closure

I accept:

- `31` unique `AUTH_V8_*` / `GATE_*` actions;
- `99` exact resources;
- `6` closed authority planes;
- `57` normative parent/child process definitions;
- `3` exact external GitHub operations;
- resource/process/network/write-derived plane validation with deny precedence.

Declared plane arrays never grant authority. Every action must match its
independently derived plane set, and every plane allowlist must contain every
and only its derived actions.

`AUTH_V8_COLLECT_EVIDENCE_INPUTS` and
`authorization_evidence_collector_v8` have one exact write set:

- `sanitized_evidence_collector_results`;
- `sanitized_probe_observations`;
- `temporary_probe_roots`;
- `temporary_probe_public_files`;
- `temporary_probe_git_metadata`.

The filesystem writes are limited to seven distinct fresh roots outside the
project under umask `0077`. Each root is closed, read through EOF,
identity-rechecked, cleaned and proven absent before its sanitized result is
retained. The collector declares the two real Node wrapper children plus the
exact local Git, `gh` and `codesign` read children, then sends one canonical
sanitized collector value through a bounded anonymous pipe.
A separate prelaunch record validates Node, launcher and builder identities.
Before any child spawn, the launcher requires two distinct bounded PASS review
records over one common frozen scope raw SHA-256, matches that digest against
a bounded no-follow/nonblocking descriptor-stable current-scope read, then
self-checks Node, launcher, builder and validation-controller identities and
rejects ambient environment or Node options. Before any of its children run,
the validation controller descriptor-stable checks itself, the transient
scope validator, Python and exact system Git against their current-scope
identities. It then runs in exact
`--postpublication` mode and accepts only its single bounded base64url result;
caller-supplied validation metadata is forbidden. The bound Node launcher
supplies the exact environment and starts collector, childless assembler and
writer directly, without a shell or temporary handoff file; Node, Python, Git,
`gh`, `codesign` and all transient helper-script bytes are phase-current
identity-bound.
`AUTH_V8_ASSEMBLE_EVIDENCE` is a separate childless process that consumes the
fresh workspace metadata, two frozen reviews and collector result, then
creates both the closed `sanitized_validation_results` value and the bounded
canonical in-memory evidence bytes. The separate
`AUTH_V8_WRITE_IGNORED_EVIDENCE` action,
`authorization_evidence_writer_v8` process and
`ignored_auth_v8_evidence` resource all declare the singleton evidence write;
the Node writer consumes only the assembled canonical bytes and cannot read a
removed temporary resource. Its bound host-Python standard-library child runs
with exact `-I -S` outside the repository cwd and executes no repository,
user-site or candidate code. It descriptor-binds the verified repository root
and each exact evidence-parent component, creates and reopens the target
relative to that bound parent, re-requires regular `0600`, `nlink=1`, exact
size and inode at every final checkpoint, rewalks the chain before success,
and on failure removes only the exact created inode through the bound parent.

## Accepted Git process and identity boundary

The profile is `m1b-1a-r1-git-execution-surface-v4`. It binds the root Git
executable, `git-remote-https → git-remote-http`, the exact pack/unpack/rev
helpers, stage children, public synthetic transport shell, and
`git-credential-osxkeychain` private broker route. Direct parent/child
execution, exact argv/environment/cwd, explicit repository routes, config
isolation, disabled hooks/fsmonitor/submodule recursion, `gc.auto=0`,
`maintenance.auto=false` and `core.logAllRefUpdates=false` are mandatory.

Each probe phase freshly binds type, mode, owner, symlink chain, realpath,
open-file identity, full-EOF hash and signing identity at phase boundaries;
the full helper set is then rechecked by lstat/readlink/resolved full-EOF hash
immediately before and after each of the `36` sequential parent processes,
while all `31` preserved-sentinel parents and `36` sequential parents have
Trace2 reconciliation; the sequential tree records `37` child launches and independently normalizes each
child argv/class/shell route to the recursively declared effective helper IDs,
including maintenance and receive-side ref enumeration. `PATH`,
`GIT_EXEC_PATH`, aliases, URL rewrites, repository config/bytes and inherited
environment cannot substitute an executable or transport route. Credential
broker reads and writes are not claimed absent; credential values remain in
the external private channel and cannot enter argv, environment, logs,
evidence, tracked bytes or model-visible output.

The owner-supplied public commit identity is:

| Role | Name | Email |
|---|---|---|
| author | `elenandar` | `max.cheba93@gmail.com` |
| committer | `elenandar` | `max.cheba93@gmail.com` |

It is exact public Git metadata, not a credential. The four values are passed
only through the exact `GIT_AUTHOR_*` and `GIT_COMMITTER_*` environment
placeholders. Private config and inherited-environment fallback are forbidden.
NUL, LF, CR, DEL, C0/C1 and other Unicode control characters are rejected.

Local config remains default-deny. `user.name` and `user.email` are explicitly
denied. Credential values are never read by the host controller or model, read
from repository/private config, stored, published, logged, evidenced or made
model-visible; only the declared external broker may exchange them through its
private channel.

## Accepted sequential Git side effects

The public synthetic topology contains existing history, an existing
remote-tracking reflog and an existing `HEAD` reflog. I accept only:

- fetch: exact remote ref/object updates plus one append to the existing
  remote-tracking reflog;
- switch with `--no-guess --no-track`: new loose branch ref, symbolic `HEAD`,
  one `HEAD` reflog append and bounded index metadata, with zero local-config
  or tracked-content delta and no future branch reflog;
- stage: the exact raw blob route and exact stage-zero index entry;
- commit: exact message/tree/commit/ref/index routes plus one `HEAD` reflog
  append, while the future branch reflog remains absent.

The historical recovery commit
`105858b4b4008bd1961316c17510b0ad6e107881` is present in both the real
`HEAD` and current branch reflogs. V8 never describes it as zero-delta.
After-success locks and temporary object routes must be absent; any additional
or missing effective delta fails closed.

## Accepted matrix

Counts are derived from the final enumeration:

- preserved families: `11`;
- new families: `37`;
- total families: `48`;
- unique `case_id × variant_id` rows: `139`.

Row-set SHA-256:

`64760e123f436a47c29007d5a189206d236961cc7429ab1b11df643fa3533fc0`.

The final families cover exact probe write closure and exact public commit
identity. The full exact row set must appear once each in ignored evidence.
Full future matrix execution remains unauthorized.

## Accepted probes

Common construction SHA-256:

`512cede88ea30872631f07aab0d973a81ae0fff0e7c91c06ee9abbb10e661637`.

| Probe | Definition SHA-256 | Observation SHA-256 |
|---|---|---|
| `clean_filter_sentinel_not_executed` | `9a74db5640e190c7c99c1b0e4477fe83c5632860ddce61af8dd0f6b6d63221c4` | `6bc97de77af15f92f87500f13b93a3740be19cc0bae6e5739347fb1f948fa1d3` |
| `process_filter_sentinel_not_executed` | `fa7b5868d1b116e58dc6fc4a8a0ca9023e513bb0fd1c70c88a621d17a046ce8b` | `ef579dde15485c8f571e2727c05e07dd3245c4eee8994ab4876c818b169b0167` |
| `external_diff_sentinel_not_executed` | `ffdb8040044f9ae8fc14c35663eaa9fe28819bc08993b23cacc62e96d383bd49` | `21c22fca1e791c0154ccb2000db77cb75bb0bdc7ce71ee025cfdd7245c14de86` |
| `textconv_sentinel_not_executed` | `68fb859e0458b34837ef4370513969d4e81168855e63fe2f9c18fb7037d2eb49` | `f0fe23aa15fe264ff532d30474f2992d4bac6553fd45812a55375f408252db73` |
| `remote_helper_sentinel_not_executed_after_gate` | `b75d4e97fdbd41581862945bff25c8801465f5fd4f420c9f929ec88d4c3945d9` | `f9fd1ec14feb4f303d0da6b4579f06b1179ae9d60248706938b45c8f70a738a2` |
| `object_database_unchanged_during_local_closure` | `6d9818ddea11d65a108193c22792091ed6f453e1502b2558346f74c1af78de9b` | `a2360821239e693d9337c7e40267ef79e0926f9cb6413e083d927915114eaaf0` |

Aggregate: `TARGETED_HOST_SENTINELS_PASS`, probes `6/6`, helper executions `0`,
object-database final path/mode/size/content delta `0`, cleanup `6/6`. This is
a final-content delta, not a write-event count. Repository/candidate code was
not executed.

## Evidence I require

Final evidence path:

`artifacts/m1b/m1b-1a-r1/auth-v8-evidence.json`

It must be strict canonical ASCII JSON with one LF, regular mode `0600`,
`st_nlink=1`, Git-ignored, untracked and physically distinct. It includes
final scope/owner/publication identities, all 139 exact matrix rows, six
sanitized sentinel observations, exact observation-hash preimages, actual
fetch/switch/stage/commit identities and deltas, helper/process identities,
cleanup, full action/resource/process/external/write closure and validation
results.

Absolute paths, private configuration, credentials and raw
repository/private/copyrighted content are forbidden. Historical evidence v1
through v7 must remain byte-identical, mode `0600`, `st_nlink=1`, ignored,
untracked and physically distinct.

The future PR is created once with final validated title/body bytes. A separate
title/body update is not authorized. Authenticated read-only GitHub operations
read `external_user_authentication`; final remote-head reconciliation uses the
exact GitHub ref query and exact expected commit OID.

## Explicit stop

Validation may use trusted one-shot host validators and exact system Git only.
Repository tests, repository Python, candidate/provider import, parsing,
tokenization, linting, compilation or execution are not authorized. Corpus,
mods, Stellaris, Workshop, launcher, model store, Ollama and real translation
inputs/outputs are not read.

This record ends at:

- `REMEDIATION: READY_FOR_REVIEW`;
- `M1B-1A-R1-AUTH-V8: READY_FOR_OWNER_REVIEW`;
- `R1_REMEDIATION: NOT_AUTHORIZED_UNTIL_V8_MERGE`;
- `NEW_REPOSITORY_CODE_EXECUTION: NOT_AUTHORIZED`;
- `PROVIDER_EXECUTION: NOT_STARTED`;
- `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`;
- `M1B: NOT_EVALUATED`;
- `M1A: BLOCKED`;
- `M2: FORBIDDEN`;
- `PR11: DRAFT`.
