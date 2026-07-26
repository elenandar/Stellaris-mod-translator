# M1B-1A-R1-AUTH v11 — post-merge transport and evidence-provenance remediation authorization

State: `M1B-1A-R1-AUTH-V11-DEFINITION: REVIEWABLE`.
`POSTPUBLICATION_EVIDENCE: REQUIRED`,
`TERMINAL_PUBLICATION_RECEIPT: REQUIRED`,
`PR11_METADATA_RECONCILIATION: REQUIRED`, and `EFFECT: NOT_ACTIVE`.
This contract is authorization-definition-only. R1 remediation remains
`NOT_AUTHORIZED_UNTIL_V11_MERGE`.

The normative machine scope is
[`registry/m1b/m1b-1a-r1-remediation-scope-v11.json`](../../registry/m1b/m1b-1a-r1-remediation-scope-v11.json).
The machine owner decision is
[`M1B-1A-R1-AUTH-owner-authorization.json`](../decisions/M1B-1A-R1-AUTH-owner-authorization.json),
and the human-readable record is
[`M1B-1A-R1-AUTH-owner-signoff.md`](../decisions/M1B-1A-R1-AUTH-owner-signoff.md).
If prose conflicts with either canonical JSON artifact, authority fails closed
and a new owner decision is required.

## 1. Decision boundary

V11 supersedes v10 before effect. Scope v1 was never effective; scopes v2
through v10 were superseded before effect. Evidence v8, v9 and v10 was not
created. V10 stopped before its first child spawn and before any evidence
write boundary because launcher helper identity used `worktree_posix_mode`
where committed rows required `posix_mode`. Its stale parent-launcher SHA,
unbound wrapper that masked child diagnostics, and builder/publisher mechanism
mismatch were independent blockers. No superseded scope authorizes the PR #10
merge retroactively.

V11 retains the bounded future remediation envelope and every v10 transport
and pack-helper correction, while closing the four v10 blockers and adding an
executable no-write proof:

1. all non-launcher/non-Python helpers are finalized first and all transient
   tools share one exact helper identity field set with `posix_mode` and
   `resolved_posix_mode`;
2. final launcher opened bytes are stably hashed, that exact SHA is embedded
   while finalizing Python, and both helpers are frozen before scope
   generation;
3. scope, owner and prose are derived from frozen helper identities; only
   after all six tracked outputs are frozen do two reviews bind the final
   scope SHA and exact six path/byte/SHA identities;
4. the bound launcher has no outer decision wrapper, strictly validates exact
   receipt keysets, schema, types, domains and payload digest, and returns
   canonical sanitized PASS or FAILURE receipts itself;
5. all evidence-publication surfaces use exactly
   `fclonefileat_open_source_fd_CLONE_NOFOLLOW_EXCL`;
6. a complete no-write mode validates reviews, outputs, helper identities,
   implementation-coupled parent-auth/child-diagnostics negatives, parent
   authentication, target exclusion and historical evidence before staging,
   target write-open or publication invocation.

The preserved controls remain:

1. every exact-equality authority array is ASCII-sorted and every action plane
   is rederived from resources, processes, external operations, network and
   writes;
2. the probe process emits one bounded sanitized in-memory observation
   resource, cleans and proves absence of every temporary root, and only then
   the bound launcher performs one terminal atomic ignored-evidence
   publication with no standalone writer action;
3. a public existing-history topology proves the sequential
   `fetch → switch → stage → commit` deltas, including real reflog appends;
4. HTTPS transport, pack/unpack helpers and the credential broker are closed
   through phase-current executable identity and exact process-tree rules;
5. the future draft PR is created once with final validated title/body bytes,
   while authenticated readback binds an exact GitHub ref query;
6. only the exact live HTTPS `index-pack --pack_header=2,N` record may replace
   a fully validated positive object count with
   `<validated-pack-object-count>` before child/parent hashing;
7. command-scoped `fetch.unpackLimit=1` and `transfer.unpackLimit=1` close the
   mutually exclusive `nonzero_pack` and `zero_object_no_pack` helper forms.

Protocol generation `108`, candidate identities, future contract generation
`5`, the historical PR #10 baseline and all preserved blockers are unchanged.
Candidate/provider execution, M1B-1A2, benchmark, M2, active translation and
publishing remain forbidden.

Before effect, only validation of the six authorization outputs, execution of
the six public synthetic probes in fresh roots outside the project, creation
of ignored v11 evidence, terminal receipt construction, and the single exact
title/body reconciliation of existing draft PR #11 are allowed. The metadata
operation is unavailable until the terminal receipt passes.

## 2. Canonical identities

Both JSON artifacts are strict ASCII sorted-key compact JSON with exactly one
trailing LF. Duplicate keys, floats, `NaN` and Infinity are invalid.

| Artifact | Bytes | Raw SHA-256 |
|---|---:|---|
| `registry/m1b/m1b-1a-r1-remediation-scope-v11.json` | `482701` | `a1e53cdcf8edfbff371562bdb4bf877432cf03f9495acc08927e2cf59e8a693c` |
| `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json` | `35379` | `a465eb255c8e12d6f0a516436d343a231e09203d82f51bd42316a419cc161369` |

Scope framing is:

`SHA-256("stellaris-m1b-1a-r1-remediation-scope-v11" || NUL || u64be(482701) || canonical_scope_bytes)`

The framed SHA-256 is
`6fb87a73aadac4b68f54ee107911cdf64c1815229d36ee927b5959c7c3b744c1`.

## 3. Historical and PR #11 effect binding

PR #10 remains `MERGED_OWNER_CONTROLLED_SCOPE_DEVIATION`:

- head `66f905cf266b9d1c1f56d0d706184387ffedb36e`;
- merge `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- ordered parents
  `1f10c151c5adac5fbf765af8093c7eddf8cf0429`,
  `66f905cf266b9d1c1f56d0d706184387ffedb36e`;
- tree `289e2396975c5ef6fe1001a7c5990523edaa06c5`;
- exact paths `11`;
- candidate `INERT_NOT_ADMITTED`.

This authorization remains on existing draft PR #11:

- repository `elenandar/Stellaris-mod-translator`;
- base `main`;
- historical base and required merge first parent
  `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- head branch `agent/m1b-1a-r1-transport-provenance-auth`;
- recovery integration merge
  `3a57701275914d905f76606cf6db3072c40a17ac`.

Every publication evidence query rebinds exact `baseRefName=main`, exact head
branch, head repository name and owner login in addition to the final OID,
open/draft state and absent auto-merge.

The exact v10-to-v11 transition from initial PR head
`3306b6ac9d8e7729398d7b0808bf5eb715594f4b` contains seven entries: the five
documentation/owner paths are modified, scope v10 is deleted, and scope v11 is
added. The final net PR diff against `origin/main` contains exactly six paths:
`README.md` and `docs/roadmap.md` are modified; owner authorization, owner
signoff, this contract and scope v11 are added. Rename inference is forbidden
for both comparisons.

Effect requires one ordinary external owner-controlled two-parent merge. The
second parent must be the final reviewed PR #11 head. Its net delta must
contain exactly:

1. `README.md`;
2. `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json`;
3. `docs/decisions/M1B-1A-R1-AUTH-owner-signoff.md`;
4. `docs/roadmap.md`;
5. `docs/specs/m1b-1a-r1-remediation-authorization-contract.md`;
6. `registry/m1b/m1b-1a-r1-remediation-scope-v11.json`.

Scopes v1 through v10 must be absent from the final tree. The four normative
artifacts must be byte-identical between the final PR head and merge tree.
Any base, path, parent-order or identity mismatch blocks effect.

## 4. Closed authority model

The machine scope count closure is exact:
`actions=32; resources=106; planes=7; processes=66; external_operations=4`.
Resources are derived from the actual registry. Matrix, recursive evidence
schema, owner, contract, signoff and actual evidence anchors must all match.
For every anchor, `-1`, `+1`, missing and wrong-type mutations fail closed.
The v10-to-v11 composition delta is exactly one action and one resource for
the mandatory no-write result. Processes remain `66`: the already bound
launcher has explicit disjoint `no_write_preflight` and
`terminal_publication_once` resource sets. External operations remain `4`.

The governed namespace is exactly `AUTH_V11_*` and `GATE_*`. Declared
`authority_planes` are not an authority source. A validator independently
derives the plane set from phase, resources, process, network and writes, then
requires exact sorted equality. Every plane allowlist must contain every and
only the actions independently derived into that plane. Unknown resources,
missing or extra planes, unresolved process/operation references, phase
mismatches and observed operations wider or narrower than the declaration fail
closed.

### Mode-domain and lifecycle closure

Git identity uses only `git_tree_mode`, `git_tree_type`,
`git_tree_blob_oid`, `git_index_mode`, `git_index_stage` and
`git_index_blob_oid`. Filesystem identity uses only
`worktree_posix_mode`, `worktree_file_type` and `worktree_st_nlink`.
Bytes and SHA-256 bind the domains; a POSIX value is never converted into a
Git mode by prefixing digits. An ambiguous bare `mode` key is unauthorized
and rejected recursively.

The complete governed populations are:

- `6` authorization-stage tracked outputs;
- `11` historical PR #10 paths with Git tree identity only and no invented
  filesystem identity;
- `11` existing tracked future outputs at prewrite, checked independently
  against the PR #11 merge-base tree, stage-zero index and current worktree;
- `18` tracked future outputs after write, staging and commit.

Existing tracked paths require regular POSIX mode `0644`, `st_nlink=1`,
stage-zero Git index mode `100644`, Git tree type `blob`, Git tree mode
`100644`, and tree/index blob OIDs reproduced from the same stable-read bytes.
New tracked paths must be absent before write, use POSIX `0644` afterward, and
receive Git index/tree identity only after staging/commit. Ignored evidence
uses POSIX `0600`, regular-file type and `st_nlink=1`, and remains absent from
the Git index and tree. Directories and helper/script identities are POSIX
only.

The bound `.gitignore` has `733` bytes, SHA-256
`0f36fee465d056ae9373a2aa702e58740f82c99c0fb25e0f24a326318087a82d`,
Git tree/index mode `100644`, stage `0`, tree type `blob`, tree/index blob OID
`a6735caefc0396a4673f461654f61dd8f71bcd30`, POSIX mode `0644`,
regular-file type and `st_nlink=1`. The stage builder reads the expected Git
mode from each exact v11 lifecycle row; hard-coding `100644` in that consumer
is forbidden.

For `AUTH_V11_COLLECT_EVIDENCE_INPUTS`, action and
`authorization_evidence_collector_v11` bind exactly:

- `sanitized_evidence_collector_results`;
- `sanitized_probe_observations`;
- `temporary_probe_roots`;
- `temporary_probe_public_files`;
- `temporary_probe_git_metadata`.

All probe filesystem writes exist only inside seven distinct fresh roots
outside the project under umask `0077`. Each root's descriptors are closed,
each output is read through EOF and identity-rechecked, and that root is
removed and proven absent before its sanitized value is retained.
The collector has two declared Node wrapper children, the exact local
Git/`gh`/`codesign` read children and no repository-persistent write. It sends
one canonical `sanitized_evidence_collector_results` value through a bounded
anonymous pipe. A separate prelaunch record validates the exact Node,
launcher, builder and evidence-I/O script identities before launcher
execution. Launcher, builder, collector, validator, Python and committed scope
use the same exact 19-field helper schema. Key sets must match in both
directions before values; requested and resolved identity, bytes, SHA-256,
resolved size, type, symlink target, device/inode/uid/gid/nlink,
`posix_mode` and `resolved_posix_mode` are all bound.
`worktree_posix_mode` is forbidden on this boundary. Before any child spawn,
the launcher strictly decodes and
round-trips two exact unpadded-base64url canonical ASCII PASS review-record
byte strings, rejects duplicate keys, requires their common frozen scope raw
SHA-256 and identical exact six-output path/byte-count/SHA-256 records, and
compares them with bounded descriptor-stable reads of the current outputs. The
scope, all six outputs and helper identities are rechecked before and after
every successful or failed nonterminal child. All final-head-independent
checks finish before atomic publication. The canonical main evidence contains
only observations available before its own publication plus exact publication
intent; it does not contain or claim its later terminal inspection or receipt.
The launcher also rejects ambient environment or Node options. Before its own
first child spawn, the
validation controller descriptor-stable checks itself, the transient
scope-validator script, Python and exact system Git against their committed
current-scope identities. Bootstrap reads
use no-follow/nonblocking opens, an initial-path-to-descriptor identity match,
a 64 MiB limit, full EOF and a final path/descriptor generation check. The
launcher then runs the bound validation controller itself in exact
`--postpublication` mode and accepts only its single bounded base64url result;
caller-supplied validation metadata is forbidden. The bound Node launcher with
an exact environment starts the collector and childless assembler without a
shell or repository handoff file. Every Node child executes the already
stable-read, hash-bound script bytes through an exact module eval snapshot,
self-checks that snapshot, and rechecks the source identity after every exit,
including failure. A final helper identity pass brackets later Git and GitHub
reads. The
childless `AUTH_V11_ASSEMBLE_EVIDENCE` process consumes only that value plus
the committed outputs, fresh validation workspace metadata and the two frozen
review records. In the same process it constructs the closed
`sanitized_validation_results` value and then bounded canonical in-memory
evidence bytes; no impossible pre-existing validation handoff is claimed.
There is no standalone evidence-writer action, Node writer mode or cleanup
process. The launcher first runs a bound prewrite `git check-ignore` and
index-absence gate. Its bound `authorization_evidence_io_python_v11` child runs
exact `-I -S`, outside the repository cwd, performs no repository, user-site,
`sitecustomize`, `usercustomize` or candidate code execution, and recomputes
the committed Python identity inside the child. It descriptor-binds the
repository root and parent chain, proves v8/v9/v10 absence, and fully hashes and
identity-checks v1–v7. Before any staging creation, the child authenticates
the exact parent Node executable, the SHA-256-bound opened launcher source and
the same two review preimages embedded in the evidence. The positive exact
parent case passes; stale SHA, one-byte launcher mutation and parent/path/argv
drift fail before staging or target write. The Python process definition
authorizes exact read-only `--self-test-parent-auth` and
`--preflight-parent-auth` modes in addition to absence, publish and inspect.
The self-test shares the production parent-argv predicate and executes one
live positive plus seven implementation-coupled negatives; a bound nonzero
validation child separately executes twelve diagnostics/receipt/privacy
negatives. Together all `19` cases preserve classification, stage, child
status and bounded stderr count/hash, strictly reject invalid terminal and
no-write PASS domains, inconsistent failure target/boundary states, private
reviewer text and malformed receipt keysets/digests/retry, and prove no
staging residue or target. No-write mode performs this exact closure
with publication invocation count zero. Its own sanitized FAILURE receipt is
explicitly authorized even though staging, target and terminal private
inspection writes remain forbidden. Terminal mode then opens
`/private/tmp`, descriptor-relatively creates one fresh private mode-`0700`
same-device staging directory and a mode-`0600` source, writes, fsyncs and
fully reads back the complete bytes, and keeps the validated source FD open.
It uses one terminal
`fclonefileat_open_source_fd_CLONE_NOFOLLOW_EXCL` operation to create the
absent descriptor-relative final name exclusively from that descriptor. No
staging pathname selects the published source. This exact literal is shared
by scope, owner, signoff, contract, builder intent, launcher, Python
publisher, validator, terminal receipt and PR body.

After atomic publication the launcher runs the postwrite ignore/index gate and
a descriptor-relative terminal reopen. It requires full-EOF byte equality,
SHA-256 and size, POSIX mode `0600`, regular-file type, `st_nlink=1`, stable
path/open-descriptor identity, preservation of evidence v1–v7, and absence of
evidence v8/v9/v10. Evidence-target device, inode, uid and gid observations
remain only in the anonymous parent/child channel. The closed local-only main
evidence allowlist separately admits phase helper identity fields, sanitized
relative Git routes, commit metadata and exactly two public opaque reviewer
IDs; none of those fields is authorized in the terminal receipt or PR body.

A zero-status publish marks the write boundary conservatively before any
post-child helper read. Lost or malformed success stdout may recover only by
the already-bound exact terminal inspection; canonical-but-wrong success
output fails closed, and nonzero publish never retries. The terminal inspect
self-checks Python before reading the evidence and is the last external
filesystem read before success: the launcher performs only in-memory receipt
validation and emission afterward.

Only after those checks does the launcher construct the in-memory canonical
`m1b-1a-r1-terminal-evidence-publication-receipt-v11`. Its digest is SHA-256
of the strict ASCII sorted compact single-LF receipt payload without the
digest field. The receipt may expose only its exact positive whitelist,
including relative evidence path, booleans, counts, evidence bytes/SHA-256,
POSIX mode and classification. Absolute paths, device/inode, uid/gid and
private host identifiers are forbidden. The receipt is not embedded in main
evidence and no second receipt file is authorized. Every nonzero path produces
one bounded canonical sanitized FAILURE receipt retaining the allowlisted
classification, stage, child status, stderr count/hash, effect state,
publication invocation count, write-boundary state and target-presence state.
Failure target-presence and write-boundary values are exact booleans when
observed and the literal `UNKNOWN` when exact observation is unavailable;
neither launcher nor publisher may invent presence or absence.
The closed failure-state lattice is: invocation `0` permits only
`NOT_INVOKED_NO_EFFECT` with boundary `false`; invocation `1` permits
`NOT_INVOKED_NO_EFFECT/false`, `MAY_HAVE_EFFECT_DO_NOT_RETRY` with boundary
`true` or `UNKNOWN`, or `VERIFIED_PRESENT/true` with target `true`.
Raw stderr, paths, argv, credentials and private identity metadata are
forbidden.

Any nonzero publisher status, including `EEXIST`, fails closed without retry.
No final-path unlink, stat-then-unlink cleanup, alternate path-based
publication or independently invocable writer route is authorized or
implemented; direct execution of the Python bytes cannot pass parent-launcher
authentication. Descriptor-relative staging cleanup runs in `finally` on
every exit after directory creation, including precondition failures, and
never targets the final path.

After the terminal receipt passes,
`AUTH_V11_UPDATE_AND_RECONCILE_PR11_METADATA` may perform exactly
`GET_precondition → PATCH_once_maximum → GET_readback` on existing PR #11.
The PATCH may change only exact UTF-8 `body` and `title` bytes and never draft
state, base/head, labels, reviewers, milestone, auto-merge, merge/close or
ready state. Preconditions recheck open/draft state, base `main`, exact branch,
exact final pushed head and absent auto-merge. A lost PATCH response permits
GET reconciliation only; a second PATCH is forbidden. Success requires an
authenticated readback of the immutable state and exact title/body hashes.
The title is one committed literal. The body is derived from one committed
UTF-8/LF template and one committed output-row template by replacing each
unique placeholder exactly once. Its closed field selectors admit only final
head/parent/tree/base, the exact six reviewed output identities, scope
raw/framed hashes, terminal receipt/evidence identities, the sanitized fresh
pack count/hash, two exact public reviewer IDs and the two exact diff-status
hashes. Absolute paths, credentials, device/inode/uid/gid, raw stderr, private
content and every unselected evidence field are forbidden. The derived body
SHA-256 is computed before the sole PATCH and must equal authenticated
GET-readback bytes.

Repository content remains default-deny. This is not broad `.git` authority.
Untracked project content is not readable. Relevant untracked attribute paths
receive metadata-only `lstat`; symlink, hardlink, alias, escape or physical
identity ambiguity blocks the action.

## 5. Normative Git process and helper profile

Profile `m1b-1a-r1-git-execution-surface-v4` binds the launcher, collector,
assembler, atomic evidence-I/O child, validation Node/Python/Git children,
`gh`, `codesign`, all
transient helper-script bytes, all parent Git processes, the two exact stage
children and every transport/pack child that can execute. Every one of the
`31` preserved-sentinel and `44` sequential Git parent records carries
its actual Trace2 children; normalized child argv/class/shell roles must equal
the recursively declared effective child IDs, including maintenance and
receive-side ref enumeration. The root executable is
`/Library/Developer/CommandLineTools/usr/bin/git`; the bounded helper set also
contains:

- `git-remote-https`, whose required symlink resolves exactly to
  `git-remote-http`;
- `git-index-pack`, `git-pack-objects`, `git-unpack-objects`,
  `git-rev-list`, `git-upload-pack` and the declared push helper route;
- `git-credential-osxkeychain` only through a private external Keychain
  boundary;
- `/bin/sh` only for the public synthetic local-file transport probe.

The exact `synthetic_side_fetch_https_trace` parent runs into a fresh empty
bare repository with no alternates, shallow state, promisor/filter or
replacement refs. Advertisement stability, fetched-ref equality, full object
closure and equality of the repository and two-ref reachable object sets are
proved before normalization. Pack version is exactly `2`; `N` is canonical
positive unsigned 32-bit decimal and equals both object-set counts. Raw `N`,
raw child digest, object/reachable counts and digests remain separate evidence.
Only that one header count changes; parent/child order, executable, class,
shell flag, `--keep` form and all other argv remain exact.

Both live-fetch forms use command-scoped `fetch.unpackLimit=1` and
`transfer.unpackLimit=1`. `nonzero_pack` requires the observed
`remote-https dispatch → resolved git-remote-http → index-pack → rev-list`
closure and forbids `unpack-objects`. `zero_object_no_pack` requires
`remote-https dispatch → resolved git-remote-http → rev-list`, zero new objects
and exactly unchanged refs, object set, reflogs and Git-dir inventory; both
pack helpers are forbidden. Each dispatch has exactly one resolved child.
Missing, extra or reordered helpers fail closed.
Thirty-nine negative cases cover malformed headers/keep values, object/ref
drift, role/order/identity drift, threshold drift and helper-variant mismatch.
Their preserved exact ID-set SHA-256 is
`b16e3a95b50968cda70764a014c937dd99d5b9cdcc180ed584eb1105e4321d5d`.
The `50` declarative v11 negative IDs exercise domain-confused or malformed
modes, wrong type/OID/stage/link/bytes, builder hard-code and lifecycle drift,
count-anchor mismatch, missing metadata authority, excess PATCH fields or
attempts, invalid receipt placement/private fields, stale active v10 identity,
helper key swaps/missing/extra fields, parent SHA/path/argv drift, unbound
wrapper, masked stderr, publication mismatch, prepublication residue/target,
owner/scope/review mismatch, assembled-evidence absolute-path leakage,
PR-body template or selected-field drift and premature tracked-document
readiness.
They are supplemented by `19` implementation-coupled cases executed by the
bound launcher: seven parent-auth/write-boundary negatives plus twelve
nonzero-child diagnostics, strict-receipt and reviewer-privacy negatives, with
one live positive parent-auth case.

The future authenticated push has one `remote-https` dispatch, exactly one
resolved `git-remote-http` child, two ordered private
`git-credential-osxkeychain` invocations (`get`, then successful `store`), one
`pack-objects` invocation and one external receive-pack boundary. The
authorization collector executes `codesign` exactly `88` times: three complete
passes over `28` bound paths plus four wrapper-boundary checks. The `44`
sequential parents use seven exact named Trace2 paths, including the separate
zero-object HTTPS fetch path, with the closed derived path rule for all others.

At each phase boundary the host binds lstat type, mode, owner, symlink chain,
realpath, opened-file identity, size, full-EOF SHA-256 and Apple signing
identity where present. During the public probe it rechecks the complete
helper lstat/readlink/resolved full-EOF identity immediately before and after
each parent process, and trace2 must bind every child route to that set. The
recorded authorization-stage hashes are observations, not long-lived
acceptance roots: a fresh phase-current bind is mandatory after effect.
`PATH`, `GIT_EXEC_PATH`, Git
aliases, URL rewrites, repository bytes, user/system config and inherited
environment cannot substitute a process or route.

All publication Git commands use:

- `core.attributesFile=/dev/null`;
- `core.excludesFile=/dev/null`;
- `core.autocrlf=false`;
- `core.pager=`;
- `core.hooksPath=/dev/null`;
- `core.fsmonitor=false`;
- `gc.auto=0`;
- `maintenance.auto=false`;
- `submodule.recurse=false`;
- `core.logAllRefUpdates=false`.

Local configuration defaults to deny. `user.name` and `user.email` are
explicitly denied, as are includes, URL rewrites, unexpected remotes,
credential/askpass/protocol/proxy routing, filters, diff/textconv commands,
partial-clone state and all unknown or ambiguous keys.

## 6. Exact public commit identity

The owner-supplied public identity is:

| Role | Name | Email |
|---|---|---|
| author | `elenandar` | `max.cheba93@gmail.com` |
| committer | `elenandar` | `max.cheba93@gmail.com` |

These exact literals are part of canonical scope v11 and are corroborated by
public PR #11 head commit metadata. They are not credentials. Private config
is not read and inherited environment is forbidden.

`git_commit_ordinary_exact` expands only:

- `GIT_AUTHOR_NAME=<owner-public-author-name>`;
- `GIT_AUTHOR_EMAIL=<owner-public-author-email>`;
- `GIT_COMMITTER_NAME=<owner-public-committer-name>`;
- `GIT_COMMITTER_EMAIL=<owner-public-committer-email>`.

Each exact UTF-8 literal must be non-empty, at most 256 bytes and contain no
NUL, LF, CR, DEL, C0/C1 or other Unicode control character. Trimming,
normalization, fallback or substitution is forbidden. The values may appear
only as public Git commit metadata.

## 7. Sequential Git side effects

The v11 probe uses public bytes only and a topology with existing history,
existing `HEAD` reflog, and an existing remote-tracking reflog. Its exact
sequence is:

1. `fetch`: update the existing remote-tracking ref, append exactly once to its
   existing reflog, and write only the received public objects and exact
   transient ref/object routes;
2. `switch --no-guess --no-track -c`: create the future loose branch ref,
   update symbolic `HEAD`, append exactly once to the existing `HEAD` reflog
   and permit only bounded index metadata change; local config, tracked content
   and future branch reflog remain unchanged/absent;
3. `stage`: compute the raw `blob <length>\0<bytes>` identity without filters,
   create only that exact object route and update the exact stage-zero index
   entry;
4. `commit`: create the exact tree and commit, update the future branch ref,
   append exactly once to the existing `HEAD` reflog, write the exact commit
   message and bounded index metadata, while the future branch reflog remains
   absent.

All after-success locks and temporary object routes must be absent. The
historical recovery commit `105858b4b4008bd1961316c17510b0ad6e107881`
is present in both the real `HEAD` and current branch reflogs; v11 does not make
the false zero-delta claim about that commit.

## 8. Adversarial matrix

The exact static matrix contains:

- preserved families: `11`;
- new families: `37`;
- total families: `48`;
- unique `case_id × variant_id` rows: `139`.

The row-set SHA-256 is
`64760e123f436a47c29007d5a189206d236961cc7429ab1b11df643fa3533fc0`,
computed from ASCII-sorted `case_id || NUL || variant_id || LF` rows.

The final families explicitly cover probe write-set mismatch and missing,
invalid, ambient or overexposed commit identity. The complete exact row set is
stored in ignored evidence. The rows are normative static definitions; full
future per-row execution remains unauthorized.

## 9. Six public probes

Common fixture construction SHA-256:

`d69af1008f961440e70c1aad6480c64a4affc0abae9e962e3d0c6aff71b88b2a`.

| Probe | Definition SHA-256 | Observation SHA-256 | Exit |
|---|---|---|---:|
| `clean_filter_sentinel_not_executed` | `67d754e868a8da0330940935a10cf9a34f40b9e03148de06b0fec951f926838e` | `37257de8ada7eccdd7083857a80014df911688566de8e786138bf1fa90073bed` | `0` |
| `process_filter_sentinel_not_executed` | `5df49a082efaf999cc39035fa666e13861d12ee863f73c0a8f01e59567d9fe26` | `b97892400773cd5f98bf48fb0d678937a96832d9a3cadcc58adcfb5420b2f8c5` | `0` |
| `external_diff_sentinel_not_executed` | `058cba3c13d558a861fec2a5d127493932ebe9dc4ed55b235c899024f2706d1e` | `7de4f9630ad7994348aaeacb92dbf3ad5cd097c9e81e22a57953c94b8cfefac9` | `1` |
| `textconv_sentinel_not_executed` | `48add433df7fc087c7c1c775bcec923a08e8313b8f7daf7bf8890e837ddc05b9` | `0bef614a3547341a9347227bb23d06b829512f813072614eecaf20d2c08b5dfe` | `1` |
| `remote_helper_sentinel_not_executed_after_gate` | `a0452f1e1dded18fc65ea4985895f74f1b72a6a10a05eebb99903648e1b9b7a4` | `4897ca86958a1dbcb3bcde5958ad385b573f97df7b0a1bad4deef2dd9467eedf` | `1` |
| `object_database_unchanged_during_local_closure` | `7afa3144ad9821d3c1a0d9e77ca82ed2f41aff2c2519158861558834949dad8b` | `44f06a34beffa2bbb48bd580f6c5d74ddca52dbebe39778195b78ff5ef7f202c` | `0` |

Aggregate result is `TARGETED_HOST_SENTINELS_PASS`: probes `6/6`, helper
executions `0`, object-database final path/mode/size/content delta `0`,
cleanup `6/6`. This is a final-content delta, not a write-event count. Only public
synthetic bytes were used. Repository/candidate code was not executed.

## 10. Future remediation envelope

After effect, at most one branch
`agent/m1b-1a-r1-postmerge-remediation` may be created from the exact PR #11
merge. Before branch creation and before the `19/19` lifecycle gate, the
complete current `HEAD^{tree}` must equal the exact merge tree. Comparison of
only the 19 outputs is insufficient.

The allowlist contains 19 outputs and four directories. Publication is limited
to one ordinary commit, one normal non-force push and one new draft PR to
`main`. The PR is created with its final deterministic validated title/body
bytes; later title/body mutation is forbidden. Final reconciliation uses the
exact authenticated GitHub ref query for
`refs/heads/agent/m1b-1a-r1-postmerge-remediation` and requires `object.sha`
to equal the created commit. Both authenticated read-only GitHub operations
declare `external_user_authentication`; credential values never enter evidence.
Uncertain mutation results require only read-only reconciliation before retry.
Rebase, amend, force-push, merge, auto-merge, Ready, branch deletion/reset and
any additional branch or PR are forbidden.

## 11. Evidence

Final evidence path:

`artifacts/m1b/m1b-1a-r1/auth-v11-evidence.json`

It is strict canonical ASCII JSON with one LF, regular mode `0600`,
`st_nlink=1`, Git-ignored and untracked. It contains final scope/owner and
publication identities, all `139` exact matrix rows, action/resource/process
and external-operation closure, six preserved sentinel observations, exact
hash preimages, sequential fetch/switch/stage/commit identities and deltas,
helper/process identities, exact atomic-publication intent, `38` validation
result preimages and hashes, and only leakage-safe public metadata. It does
not contain proof of its own final publication or the terminal receipt. A
committed recursive field/type-path digest rejects every unknown nested field
or type. After complete assembly and before any evidence output, the bound
builder recursively scans every string value, including validation records,
and requires zero absolute-path, private-host, credential or private-key
matches; failure is sanitized and emits no offending value.

Historical evidence v1 through v7 must remain byte-identical, regular mode
`0600`, `st_nlink=1`, ignored, untracked and on distinct inodes. Evidence v8,
v9 and v10 must remain absent. The decision-grade result additionally requires the
sanitized terminal receipt and exact authenticated PR #11 metadata readback.

## 12. Explicit stop

Repository tests and repository Python are excluded. Candidate/provider
import, parsing, tokenization, linting, compilation or execution are forbidden.
Corpus, mods, Stellaris, Workshop, launcher, model store, Ollama and real
translation inputs/outputs are not read.

This contract ends at:

```text
REMEDIATION: DEFINITION_REVIEWABLE
M1B-1A-R1-AUTH-V9: SUPERSEDED_BEFORE_EFFECT
M1B-1A-R1-AUTH-V10: SUPERSEDED_BEFORE_EFFECT
M1B-1A-R1-AUTH-V11-DEFINITION: REVIEWABLE
POSTPUBLICATION_EVIDENCE: REQUIRED
TERMINAL_PUBLICATION_RECEIPT: REQUIRED
PR11_METADATA_RECONCILIATION: REQUIRED
EFFECT: NOT_ACTIVE
R1_REMEDIATION: NOT_AUTHORIZED_UNTIL_V11_MERGE
NEW_REPOSITORY_CODE_EXECUTION: NOT_AUTHORIZED
PROVIDER_EXECUTION: NOT_STARTED
EXECUTABLE_TCB_ADMISSION: NOT_GRANTED
M1B: NOT_EVALUATED
M1A: BLOCKED
M2: FORBIDDEN
PR11: DRAFT
```
