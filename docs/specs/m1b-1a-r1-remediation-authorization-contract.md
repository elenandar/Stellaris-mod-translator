# M1B-1A-R1-AUTH v9 — post-merge transport and evidence-provenance remediation authorization

Status: `READY_FOR_OWNER_REVIEW`. This contract is authorization-only. It does
not authorize R1 remediation until external owner review and the exact PR #11
merge defined below.

The normative machine scope is
[`registry/m1b/m1b-1a-r1-remediation-scope-v9.json`](../../registry/m1b/m1b-1a-r1-remediation-scope-v9.json).
The machine owner decision is
[`M1B-1A-R1-AUTH-owner-authorization.json`](../decisions/M1B-1A-R1-AUTH-owner-authorization.json),
and the human-readable record is
[`M1B-1A-R1-AUTH-owner-signoff.md`](../decisions/M1B-1A-R1-AUTH-owner-signoff.md).
If prose conflicts with either canonical JSON artifact, authority fails closed
and a new owner decision is required.

## 1. Decision boundary

V9 supersedes v8 before effect. Scope v1 was never effective; scopes v2 through
v8 were superseded before effect. V8 evidence was never created: its
post-publication pipeline failed closed before the writer. No superseded scope
authorizes the PR #10 merge retroactively.

V9 retains the bounded future remediation envelope, preserves the v8 closure,
and fixes the two remaining deterministic fetch-provenance defects:

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
of ignored v9 evidence, and one bounded publication to existing draft PR #11
are allowed.

## 2. Canonical identities

Both JSON artifacts are strict ASCII sorted-key compact JSON with exactly one
trailing LF. Duplicate keys, floats, `NaN` and Infinity are invalid.

| Artifact | Bytes | Raw SHA-256 |
|---|---:|---|
| `registry/m1b/m1b-1a-r1-remediation-scope-v9.json` | `421822` | `df29f40a12e2163afc3e542774d9fdb0fc4542b898880e866c8ecdc4b0a73575` |
| `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json` | `28971` | `c374f9ebad668fd49692aeb25e58419ebfb7c3539c012d4e714559ec4180ae9e` |

Scope framing is:

`SHA-256("stellaris-m1b-1a-r1-remediation-scope-v9" || NUL || u64be(421822) || canonical_scope_bytes)`

The framed SHA-256 is
`092797ab1729359e18e21ff92ee1b0b1f678ce895debf023f2ab50628fb9c292`.

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

Effect requires one ordinary external owner-controlled two-parent merge. The
second parent must be the final reviewed PR #11 head. The PR and merge deltas
must both contain exactly:

1. `README.md`;
2. `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json`;
3. `docs/decisions/M1B-1A-R1-AUTH-owner-signoff.md`;
4. `docs/roadmap.md`;
5. `docs/specs/m1b-1a-r1-remediation-authorization-contract.md`;
6. `registry/m1b/m1b-1a-r1-remediation-scope-v9.json`.

Scopes v1 through v8 must be absent. The four normative artifacts must be
byte-identical between the final PR head and merge tree. Any base, path,
parent-order or identity mismatch blocks effect.

## 4. Closed authority model

The machine scope contains:

- `30` unique action records;
- `101` exact resources;
- `6` authority planes;
- `66` normative parent/child process definitions;
- `3` external GitHub operation definitions.

The governed namespace is exactly `AUTH_V9_*` and `GATE_*`. Declared
`authority_planes` are not an authority source. A validator independently
derives the plane set from phase, resources, process, network and writes, then
requires exact sorted equality. Every plane allowlist must contain every and
only the actions independently derived into that plane. Unknown resources,
missing or extra planes, unresolved process/operation references, phase
mismatches and observed operations wider or narrower than the declaration fail
closed.

For `AUTH_V9_COLLECT_EVIDENCE_INPUTS`, action and
`authorization_evidence_collector_v9` bind exactly:

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
execution. Before any child spawn, the launcher strictly decodes and
round-trips two exact unpadded-base64url canonical ASCII PASS review-record
byte strings, rejects duplicate keys, requires their common frozen scope raw
SHA-256 and identical exact six-output path/byte-count/SHA-256 records, and
compares them with bounded descriptor-stable reads of the current outputs. The
scope, all six outputs and helper identities are rechecked before and after
every successful or failed nonterminal child. Immediately before the terminal
read-only inspector they are rechecked once more; the child rechecks Python
before reading evidence, and no filesystem read follows that inspection. It
then binds the canonical result directly to success. The launcher also
rejects ambient environment or Node options. Before its own first child spawn,
the
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
childless `AUTH_V9_ASSEMBLE_EVIDENCE` process consumes only that value plus
the committed outputs, fresh validation workspace metadata and the two frozen
review records. In the same process it constructs the closed
`sanitized_validation_results` value and then bounded canonical in-memory
evidence bytes; no impossible pre-existing validation handoff is claimed.
There is no standalone evidence-writer action, Node writer mode or cleanup
process. The launcher first runs a bound prewrite `git check-ignore` and
index-absence gate. Its bound `authorization_evidence_io_python_v9` child runs
exact `-I -S`, outside the repository cwd, performs no repository, user-site,
`sitecustomize`, `usercustomize` or candidate code execution, and recomputes
the committed Python identity inside the child. It descriptor-binds the
repository root and parent chain, proves v8/v9 absence, and fully hashes and
identity-checks v1–v7. Before any staging creation, the child authenticates
the exact parent Node executable, the SHA-256-bound opened launcher source and
the same two review preimages embedded in the evidence. It then opens
`/private/tmp`, descriptor-relatively creates one fresh private mode-`0700`
same-device staging directory and a mode-`0600` source, writes, fsyncs and
fully reads back the complete bytes, and keeps the validated source FD open.
It uses one terminal `fclonefileat` with `CLONE_NOFOLLOW` to create the absent
descriptor-relative final name exclusively from that descriptor. No staging
pathname selects the published source.

A separately invoked read-only mode reopens the final target
descriptor-relative, requires exact evidence bytes, regular mode `0600`,
`nlink=1`, size, device and inode, rechecks v1–v7 and v8 absence, and binds its
identity to the publication outcome. Any nonzero publisher status, including
`EEXIST`, fails closed and is never recoverable. Only a confirmed zero exit
with lost or malformed stdout may recover from exact final bytes. A second
bound Git exclusion gate confirms ignored/untracked state, then a fresh
descriptor-relative full-byte/inode inspection is the last validation before
success. No final-path unlink, stat-then-unlink cleanup, source-path rename or
independently invocable writer route is authorized or implemented; direct
execution of the Python bytes cannot pass parent-launcher authentication.
Descriptor-relative staging cleanup runs in `finally` on every exit after
directory creation, including precondition failures, and never targets the
final path.

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

These exact literals are part of canonical scope v9 and are corroborated by
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

The v9 probe uses public bytes only and a topology with existing history,
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
is present in both the real `HEAD` and current branch reflogs; v9 does not make
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

`512cede88ea30872631f07aab0d973a81ae0fff0e7c91c06ee9abbb10e661637`.

| Probe | Definition SHA-256 | Observation SHA-256 | Exit |
|---|---|---|---:|
| `clean_filter_sentinel_not_executed` | `9a74db5640e190c7c99c1b0e4477fe83c5632860ddce61af8dd0f6b6d63221c4` | `6bc97de77af15f92f87500f13b93a3740be19cc0bae6e5739347fb1f948fa1d3` | `0` |
| `process_filter_sentinel_not_executed` | `fa7b5868d1b116e58dc6fc4a8a0ca9023e513bb0fd1c70c88a621d17a046ce8b` | `ef579dde15485c8f571e2727c05e07dd3245c4eee8994ab4876c818b169b0167` | `0` |
| `external_diff_sentinel_not_executed` | `ffdb8040044f9ae8fc14c35663eaa9fe28819bc08993b23cacc62e96d383bd49` | `21c22fca1e791c0154ccb2000db77cb75bb0bdc7ce71ee025cfdd7245c14de86` | `1` |
| `textconv_sentinel_not_executed` | `68fb859e0458b34837ef4370513969d4e81168855e63fe2f9c18fb7037d2eb49` | `f0fe23aa15fe264ff532d30474f2992d4bac6553fd45812a55375f408252db73` | `1` |
| `remote_helper_sentinel_not_executed_after_gate` | `b75d4e97fdbd41581862945bff25c8801465f5fd4f420c9f929ec88d4c3945d9` | `f9fd1ec14feb4f303d0da6b4579f06b1179ae9d60248706938b45c8f70a738a2` | `1` |
| `object_database_unchanged_during_local_closure` | `6d9818ddea11d65a108193c22792091ed6f453e1502b2558346f74c1af78de9b` | `a2360821239e693d9337c7e40267ef79e0926f9cb6413e083d927915114eaaf0` | `0` |

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

`artifacts/m1b/m1b-1a-r1/auth-v9-evidence.json`

It is strict canonical ASCII JSON with one LF, regular mode `0600`,
`st_nlink=1`, Git-ignored and untracked. It contains final scope/owner and
publication identities, all `139` exact matrix rows, action/resource/process
and external-operation closure, six preserved sentinel observations, exact
hash preimages, sequential fetch/switch/stage/commit identities and deltas,
helper/process identities, atomic-publication and exact-inode inspection
proof, 22 validation result preimages and hashes, and only leakage-safe public
metadata. A committed recursive
field/type-path digest rejects every unknown nested field or type.

Historical evidence v1 through v7 must remain byte-identical, regular mode
`0600`, `st_nlink=1`, ignored, untracked and on distinct inodes.

## 12. Explicit stop

Repository tests and repository Python are excluded. Candidate/provider
import, parsing, tokenization, linting, compilation or execution are forbidden.
Corpus, mods, Stellaris, Workshop, launcher, model store, Ollama and real
translation inputs/outputs are not read.

This contract ends at:

```text
REMEDIATION: READY_FOR_REVIEW
M1B-1A-R1-AUTH-V9: READY_FOR_OWNER_REVIEW
R1_REMEDIATION: NOT_AUTHORIZED_UNTIL_V9_MERGE
NEW_REPOSITORY_CODE_EXECUTION: NOT_AUTHORIZED
PROVIDER_EXECUTION: NOT_STARTED
EXECUTABLE_TCB_ADMISSION: NOT_GRANTED
M1B: NOT_EVALUATED
M1A: BLOCKED
M2: FORBIDDEN
PR11: DRAFT
```
