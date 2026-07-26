# Owner signoff M1B-1A-R1-AUTH v10

Decision: `owner_accepted` for the exact authorization definition bytes below
only.

State: `M1B-1A-R1-AUTH-V10-DEFINITION: REVIEWABLE`.
`POSTPUBLICATION_EVIDENCE: REQUIRED`,
`TERMINAL_PUBLICATION_RECEIPT: REQUIRED`,
`PR11_METADATA_RECONCILIATION: REQUIRED`, and `EFFECT: NOT_ACTIVE`.

This record does not merge PR #11, mark it ready or enable auto-merge. It does
not authorize R1 remediation before the exact owner-controlled v10 merge. It does
not authorize repository/candidate execution, provider/Ollama/model calls,
M1B-1A2, benchmark, product translation, publishing, M2 or product CLI.

## Accepted exact artifacts

I accept these exact identities as the complete v10 authorization definition:

| Artifact | Bytes | Raw SHA-256 |
|---|---:|---|
| `registry/m1b/m1b-1a-r1-remediation-scope-v10.json` | `459346` | `c6d37bcbb2af1c59a5275faadedfd50aa20a40c6e9977756389a9f71f452b547` |
| `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json` | `30530` | `d5576ca40621163593fd77da7f499280864be948b2959fd256a3f91d7c8b59fd` |
| `docs/specs/m1b-1a-r1-remediation-authorization-contract.md` | `28275` | `099b3c46e1fe65b47e732dac5512cf4118491e4c9d196f6660733a708dc6faa1` |

The scope schema is `m1b-1a-r1-remediation-scope-v10`, generation `10`. Its
framing domain is `stellaris-m1b-1a-r1-remediation-scope-v10`; the framed
SHA-256 is:

`a4a064e2a7ffca15630419b9bd63ee527eced3ae7d98636eaf53966b2803180d`.

The owner schema is
`m1b-1a-r1-remediation-owner-authorization-v10`. Scope and owner JSON are strict
ASCII sorted-key compact JSON with one LF. Duplicate keys, floats, `NaN` and
Infinity are rejected.

Scope v1 was never effective. Scopes v2 through v9 were superseded before
effect. V9 is `SUPERSEDED_BEFORE_EFFECT`; evidence v8 and v9 were not created.
None authorizes PR #10 retroactively.

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

Evidence publication rechecks exact base, head branch, head repository and
owner together with final head OID, open/draft state and absent auto-merge.

The transition from initial v9 head
`5e0e024daf86c578ac9e281fe3ff227da5f56f26` contains exactly seven paths:
five modified documents, deleted scope v9, and added scope v10. The final net
PR diff against `origin/main` contains exactly six paths: modified README and
roadmap plus added owner authorization, signoff, contract and scope v10.

Effect requires the final reviewed PR #11 head as the exact second parent of
one ordinary external owner-controlled two-parent merge. The merge delta must
contain exactly the six final net paths listed by the contract. Scopes v1
through v9 must be absent. Any different base, path set, status map, parent
order or identity blocks effect.

## Accepted closure

I accept the exact count tuple:
`actions=31; resources=105; planes=7; processes=66; external_operations=4`.
Resources are derived from the actual registry. Matrix, recursive evidence
schema, owner, contract, signoff and actual evidence anchors must agree.
Each count anchor rejects `-1`, `+1`, missing and wrong-type mutations.
Resource/process/network/write-derived plane validation retains deny
precedence.

Declared plane arrays never grant authority. Every action must match its
independently derived plane set, and every plane allowlist must contain every
and only its derived actions.

I accept the separate identity domains. Git tree/index identity uses only
`git_tree_*` and `git_index_*`; filesystem identity uses only
`worktree_posix_mode`, `worktree_file_type` and `worktree_st_nlink`. Bytes and
SHA-256 bind all tracked observations. Bare `mode` is rejected; POSIX `0644`
is never transformed into Git `100644`.

The governed populations are exactly `6` authorization outputs, `11`
historical Git-tree-only paths, `11` existing tracked prewrite identities and
`18` tracked postwrite identities. Existing tracked paths require POSIX
`0644`, regular-file type and one link independently from Git tree/index
`100644`, tree type `blob`, stage zero and byte-reproduced blob OIDs. New
tracked paths are absent before write. Ignored evidence requires POSIX `0600`,
regular-file type, one link, and absence from tree/index. Directories and
helper identities are POSIX-only. The builder reads Git mode from each exact
lifecycle row and may not hard-code it.

The `.gitignore` identity is `733` bytes, SHA-256
`0f36fee465d056ae9373a2aa702e58740f82c99c0fb25e0f24a326318087a82d`,
tree/index mode `100644`, stage zero, blob OID
`a6735caefc0396a4673f461654f61dd8f71bcd30`, POSIX mode `0644`,
regular-file type and one link.

`AUTH_V10_COLLECT_EVIDENCE_INPUTS` and
`authorization_evidence_collector_v10` have one exact write set:

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
A separate prelaunch record validates Node, launcher, builder and evidence-I/O
script identities. Before any child spawn, the launcher strictly decodes and
round-trips two exact unpadded-base64url canonical ASCII PASS review-record
byte strings, rejects duplicate keys, requires one common frozen scope raw
SHA-256 and one identical exact six-output path/byte-count/SHA-256 set, matches
those anchors against bounded no-follow/nonblocking descriptor-stable
current-output reads, and rechecks them before and after every successful or
failed nonterminal child. All final-head-independent checks finish before
atomic publication. Main evidence contains only prepublication observations
and exact publication intent; it does not claim its own later terminal
inspection or receipt. The launcher rejects ambient environment or Node options.
Before any of its children run, the validation controller descriptor-stable
checks itself, the transient scope validator, Python and exact system Git
against their current-scope identities.
It then runs in exact `--postpublication` mode and accepts only its single
bounded base64url result; caller-supplied validation metadata is forbidden.
The bound Node launcher supplies the exact environment and starts the
collector and childless assembler without a shell or repository handoff file;
Node, Python, Git, `gh`, `codesign` and all transient helper-script bytes are
phase-current identity-bound. Every Node child executes already stable-read
and hash-bound module bytes, self-checks its eval snapshot and rechecks source
identity after every exit, including failure; a final helper pass brackets
later Git/GitHub reads.
`AUTH_V10_ASSEMBLE_EVIDENCE` is a separate childless process that consumes the
fresh workspace metadata, two frozen reviews and collector result, then
creates both the closed `sanitized_validation_results` value and the bounded
canonical in-memory evidence bytes. There is no standalone writer action or
cleanup process. After a prewrite `git check-ignore` and index-absence gate,
the bound `authorization_evidence_io_python_v10` child runs exact `-I -S`. It
descriptor-binds the repository root and evidence-parent chain, fully verifies
v1–v7 and v8/v9 absence, and authenticates the exact parent Node executable,
SHA-256-bound opened launcher source and the same two review preimages before
any staging creation. It then opens `/private/tmp`, descriptor-relatively
creates one fresh private mode-`0700` same-device staging directory and
mode-`0600` source, writes, fsyncs and fully reads back the complete bytes,
keeps that source FD open, and performs one
terminal `fclonefileat(CLONE_NOFOLLOW)` exclusive clone into the absent final
name.

After publication, the launcher performs postwrite ignore/index exclusion and
a descriptor-relative terminal reopen with full-EOF byte equality, SHA-256,
size, POSIX mode `0600`, regular-file type, `st_nlink=1`, stable path/open-FD
identity, v1–v7 preservation and v8/v9 absence. Device, inode, uid and gid
remain private. It then returns one in-memory canonical
`m1b-1a-r1-terminal-evidence-publication-receipt-v10`, hashed over the strict
ASCII sorted compact single-LF payload without its digest field. The receipt
is outside main evidence, exposes only whitelisted relative/sanitized fields,
and has no second file.

Only after that receipt passes may
`AUTH_V10_UPDATE_AND_RECONCILE_PR11_METADATA` perform
`GET_precondition → PATCH_once_maximum → GET_readback`. The one PATCH may
change exact UTF-8 `body` and `title` only. It cannot change draft/base/head,
labels, reviewers, milestone, auto-merge, merge/close or ready state. A lost
PATCH response permits authenticated GET reconciliation only; a second PATCH
is forbidden. Exact open/draft/base/branch/final-head/auto-merge state and
title/body hashes must read back.

Any nonzero publisher status, including `EEXIST`, fails closed. Only a
confirmed zero exit with malformed or lost stdout may use exact final bytes as
its recovery record. No final-path unlink, stat-then-unlink cleanup,
source-path rename, partial final-path write or independently invocable writer
route exists. Descriptor-relative staging cleanup runs in `finally` on every
exit after creation and never targets the final path.

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
immediately before and after each of the `44` sequential parent processes,
while all `31` preserved-sentinel parents and `44` sequential parents have
Trace2 reconciliation; the sequential tree records `45` child launches and independently normalizes each
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
`HEAD` and current branch reflogs. V10 never describes it as zero-delta.
After-success locks and temporary object routes must be absent; any additional
or missing effective delta fails closed.

For the live public HTTPS fetch I accept exactly one normalization:
`synthetic_side_fetch_https_trace` /
`git_index_pack_synthetic_helper` /
`--pack_header=2,N`. The fresh empty bare repository, stable advertisement,
exact fetched refs, full closure, repository/reachable object-set equality and
canonical positive unsigned 32-bit `N` must all pass before replacing only
`N` with `<validated-pack-object-count>`. Raw `N`, raw child hash and both
object-set counts/digests remain evidence.

Both normative and evidence fetches pin `fetch.unpackLimit=1` and
`transfer.unpackLimit=1`. A nonzero fetch permits the exact normalized
`remote-https dispatch → resolved git-remote-http → index-pack → rev-list`
sequence; a zero-object fetch permits only
`remote-https dispatch → resolved git-remote-http → rev-list` with zero
ref/object/reflog/inventory delta. Each dispatch has exactly one resolved child.
Live HTTPS `unpack-objects` is forbidden. All `39` committed negative cases
must fail closed. Their preserved ID-set SHA-256 is
`b16e3a95b50968cda70764a014c937dd99d5b9cdcc180ed584eb1105e4321d5d`.
All `30` v10 mode/metadata/receipt negative cases and all `128` mutations over
the `32` count anchors must also fail closed.

The future authenticated push has exactly one `remote-https` dispatch and one
resolved `git-remote-http` child, two ordered private credential-helper
invocations (`get`, then successful `store`), one pack producer and one
external receive-pack boundary. Collector identity binding performs exactly
`88` `codesign` children: three full `28`-path passes and four wrapper-boundary
checks. The `44` sequential parents bind seven named Trace2 paths, including
the distinct zero-object HTTPS fetch trace.

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

`d69af1008f961440e70c1aad6480c64a4affc0abae9e962e3d0c6aff71b88b2a`.

| Probe | Definition SHA-256 | Observation SHA-256 |
|---|---|---|
| `clean_filter_sentinel_not_executed` | `67d754e868a8da0330940935a10cf9a34f40b9e03148de06b0fec951f926838e` | `37257de8ada7eccdd7083857a80014df911688566de8e786138bf1fa90073bed` |
| `process_filter_sentinel_not_executed` | `5df49a082efaf999cc39035fa666e13861d12ee863f73c0a8f01e59567d9fe26` | `b97892400773cd5f98bf48fb0d678937a96832d9a3cadcc58adcfb5420b2f8c5` |
| `external_diff_sentinel_not_executed` | `058cba3c13d558a861fec2a5d127493932ebe9dc4ed55b235c899024f2706d1e` | `7de4f9630ad7994348aaeacb92dbf3ad5cd097c9e81e22a57953c94b8cfefac9` |
| `textconv_sentinel_not_executed` | `48add433df7fc087c7c1c775bcec923a08e8313b8f7daf7bf8890e837ddc05b9` | `0bef614a3547341a9347227bb23d06b829512f813072614eecaf20d2c08b5dfe` |
| `remote_helper_sentinel_not_executed_after_gate` | `a0452f1e1dded18fc65ea4985895f74f1b72a6a10a05eebb99903648e1b9b7a4` | `4897ca86958a1dbcb3bcde5958ad385b573f97df7b0a1bad4deef2dd9467eedf` |
| `object_database_unchanged_during_local_closure` | `7afa3144ad9821d3c1a0d9e77ca82ed2f41aff2c2519158861558834949dad8b` | `44f06a34beffa2bbb48bd580f6c5d74ddca52dbebe39778195b78ff5ef7f202c` |

Aggregate: `TARGETED_HOST_SENTINELS_PASS`, probes `6/6`, helper executions `0`,
object-database final path/mode/size/content delta `0`, cleanup `6/6`. This is
a final-content delta, not a write-event count. Repository/candidate code was
not executed.

## Evidence I require

Final evidence path:

`artifacts/m1b/m1b-1a-r1/auth-v10-evidence.json`

It must be strict canonical ASCII JSON with one LF, regular mode `0600`,
`st_nlink=1`, Git-ignored, untracked and physically distinct. It includes
final scope/owner/publication identities, all 139 exact matrix rows, six
sanitized sentinel observations, exact observation-hash preimages, actual
fetch/switch/stage/commit identities and deltas, helper/process identities,
atomic-publication intent, full action/resource/process/external/write closure
and exactly `31` validation result records. It does not include proof of its
own terminal inspection or the terminal receipt.

Absolute paths, private configuration, credentials and raw
repository/private/copyrighted content are forbidden. Historical evidence v1
through v7 must remain byte-identical, mode `0600`, `st_nlink=1`, ignored,
untracked and physically distinct. Evidence v8 and v9 must remain absent.

The later post-effect remediation PR is created once with final validated
title/body bytes and has no later metadata-update authority. Separately, the
v10 authorization-stage exception permits the exact one-PATCH/GET-readback
operation on existing PR #11 only after main evidence and terminal receipt
pass on the final pushed head. Both routes use
`external_user_authentication`; credential values remain private.

## Explicit stop

Validation may use trusted one-shot host validators and exact system Git only.
Repository tests, repository Python, candidate/provider import, parsing,
tokenization, linting, compilation or execution are not authorized. Corpus,
mods, Stellaris, Workshop, launcher, model store, Ollama and real translation
inputs/outputs are not read.

This record ends at:

- `REMEDIATION: DEFINITION_REVIEWABLE`;
- `M1B-1A-R1-AUTH-V9: SUPERSEDED_BEFORE_EFFECT`;
- `M1B-1A-R1-AUTH-V10-DEFINITION: REVIEWABLE`;
- `POSTPUBLICATION_EVIDENCE: REQUIRED`;
- `TERMINAL_PUBLICATION_RECEIPT: REQUIRED`;
- `PR11_METADATA_RECONCILIATION: REQUIRED`;
- `EFFECT: NOT_ACTIVE`;
- `R1_REMEDIATION: NOT_AUTHORIZED_UNTIL_V10_MERGE`;
- `NEW_REPOSITORY_CODE_EXECUTION: NOT_AUTHORIZED`;
- `PROVIDER_EXECUTION: NOT_STARTED`;
- `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`;
- `M1B: NOT_EVALUATED`;
- `M1A: BLOCKED`;
- `M2: FORBIDDEN`;
- `PR11: DRAFT`.
