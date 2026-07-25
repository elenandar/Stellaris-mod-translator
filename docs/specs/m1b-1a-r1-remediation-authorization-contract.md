# M1B-1A-R1-AUTH v7 — post-merge transport and evidence-provenance remediation authorization

Status: `READY_FOR_OWNER_REVIEW`. This contract is authorization-only. It does
not authorize R1 remediation until external owner review and the exact PR #11
merge defined below.

The normative machine scope is
[`registry/m1b/m1b-1a-r1-remediation-scope-v7.json`](../../registry/m1b/m1b-1a-r1-remediation-scope-v7.json).
The machine owner decision is
[`M1B-1A-R1-AUTH-owner-authorization.json`](../decisions/M1B-1A-R1-AUTH-owner-authorization.json),
and the human-readable record is
[`M1B-1A-R1-AUTH-owner-signoff.md`](../decisions/M1B-1A-R1-AUTH-owner-signoff.md).
If prose conflicts with either canonical JSON artifact, authority fails closed
and a new owner decision is required.

## 1. Decision boundary

V7 supersedes v6 before effect. Scope v1 was never effective; scopes v2 through
v6 were superseded before effect. No superseded scope authorizes the PR #10
merge retroactively.

V7 retains the bounded future remediation envelope and closes three defects in
the provisional draft:

1. `AUTH_V7_RUN_SYNTHETIC_PROBES` now has the exact same write set as
   `synthetic_probe_suite_v7` and the resource registry;
2. `git_commit_ordinary_exact` receives an exact owner-supplied public
   author/committer identity through a closed environment;
3. actual commit reflog, ref, index, object, lock and message-file side effects
   are explicit and were checked in six fresh synthetic repositories.

Protocol generation `108`, candidate identities, future contract generation
`5`, the historical PR #10 baseline and all preserved blockers are unchanged.
Candidate/provider execution, M1B-1A2, benchmark, M2, active translation and
publishing remain forbidden.

Before effect, only validation of the six authorization outputs, execution of
the six public synthetic probes in fresh roots outside the project, creation
of ignored v7 evidence, and one bounded publication to existing draft PR #11
are allowed.

## 2. Canonical identities

Both JSON artifacts are strict ASCII sorted-key compact JSON with exactly one
trailing LF. Duplicate keys, floats, `NaN` and Infinity are invalid.

| Artifact | Bytes | Raw SHA-256 |
|---|---:|---|
| `registry/m1b/m1b-1a-r1-remediation-scope-v7.json` | `249528` | `cb66f117c89fac9888047e894762243ae99ac60b4998c6d77f5350617973ff3d` |
| `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json` | `24603` | `797aab6d7900b76e0de69665ff39ca43f800e7e9fea58c167d10ea58a51bd797` |

Scope framing is:

`SHA-256("stellaris-m1b-1a-r1-remediation-scope-v7" || NUL || u64be(249528) || canonical_scope_bytes)`

The framed SHA-256 is
`09769aab320568e435f96441f3442b268d322d3adddc15abb7e3445d34d8cc2e`.

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

Effect requires one ordinary external owner-controlled two-parent merge. The
second parent must be the final reviewed PR #11 head. The PR and merge deltas
must both contain exactly:

1. `README.md`;
2. `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json`;
3. `docs/decisions/M1B-1A-R1-AUTH-owner-signoff.md`;
4. `docs/roadmap.md`;
5. `docs/specs/m1b-1a-r1-remediation-authorization-contract.md`;
6. `registry/m1b/m1b-1a-r1-remediation-scope-v7.json`.

Scopes v1 through v6 must be absent. The four normative artifacts must be
byte-identical between the final PR head and merge tree. Any base, path,
parent-order or identity mismatch blocks effect.

## 4. Closed authority model

The machine scope contains:

- `30` unique action records;
- `82` exact resources;
- `6` authority planes;
- `7` normative process definitions;
- `4` external GitHub operation definitions.

The governed namespace is exactly `AUTH_V7_*` and `GATE_*`. Declared
`authority_planes` are not an authority source. A validator independently
derives the plane set from phase, resources, process, network and writes, then
requires exact sorted equality. Every plane allowlist must contain every and
only the actions independently derived into that plane. Unknown resources,
missing or extra planes, unresolved process/operation references, phase
mismatches and observed operations wider or narrower than the declaration fail
closed.

For `AUTH_V7_RUN_SYNTHETIC_PROBES`, action, process and resource registry all
bind exactly this write set:

- `temporary_probe_roots`;
- `temporary_probe_public_files`;
- `temporary_probe_git_metadata`.

The writes exist only inside six distinct fresh roots outside the verified
project, use parent umask `0077`, and are deleted after observation.

Repository content remains default-deny. This is not broad `.git` authority.
Untracked project content is not readable. Relevant untracked attribute paths
receive metadata-only `lstat`; symlink, hardlink, alias, escape or physical
identity ambiguity blocks the action.

## 5. Normative Git process profile

The only critical executable is:

`/Library/Developer/CommandLineTools/usr/bin/git`

Profile `m1b-1a-r1-git-execution-surface-v3` defines:

- `git_ls_remote_exact`;
- `git_fetch_exact`;
- `git_direct_transition_exact`;
- `git_stage_exact_outputs`;
- `git_commit_ordinary_exact`;
- `git_push_exact_branch`;
- `synthetic_probe_suite_v7`.

Git processes use direct execution without shell, alias, function, wrapper or
repository discovery. Exact argv binds `--git-dir` and `--work-tree`. Global
and system configuration are isolated to `/dev/null`; system attributes,
replacement objects, optional locks, hooks, fsmonitor, submodule recursion,
terminal prompting and pagers are disabled as specified by the process.

All publication Git commands use:

- `core.attributesFile=/dev/null`;
- `core.excludesFile=/dev/null`;
- `core.autocrlf=false`;
- `core.pager=`;
- `core.hooksPath=/dev/null`;
- `core.fsmonitor=false`;
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

These exact literals are part of canonical scope v7 and are corroborated by
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

## 7. Commit side effects

The exact publication-shaped commit command was checked in all six fresh probe
repositories with `core.logAllRefUpdates=false`. Every run produced:

- HEAD reflog delta `0`;
- branch reflog delta `0`;
- post-success lockfile count `0`;
- post-success temporary-object count `0`;
- unchanged stage-zero index entries;
- unchanged tracked worktree;
- exactly two added object rows for the tree and commit;
- exact `COMMIT_EDITMSG` SHA-256
  `6904e055384f68fe37fb043599f6ce095cbacf44c27d92037c2a11c37778e45b`.

The future commit process may touch only `commit_message_file`,
`future_branch_ref`, its lock, `index_lock`, bounded index metadata,
`object_database`, exact temporary object routes, the ordinary commit object,
`packed_refs` and its lock. HEAD and branch reflogs must have zero delta.
Stage-zero entry modes, OIDs, paths and flags must remain exact. All locks and
temporary objects must be absent after success. Any other effect is
`UNEXPECTED_GIT_INTERNAL_WRITE`.

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
executions `0`, object-database write delta `0`, cleanup `6/6`. Only public
synthetic bytes were used. Repository/candidate code was not executed.

## 10. Future remediation envelope

After effect, at most one branch
`agent/m1b-1a-r1-postmerge-remediation` may be created from the exact PR #11
merge. Before branch creation and before the `19/19` lifecycle gate, the
complete current `HEAD^{tree}` must equal the exact merge tree. Comparison of
only the 19 outputs is insufficient.

The allowlist contains 19 outputs and four directories. Publication is limited
to one ordinary commit, one normal non-force push, one new draft PR to `main`
and one title/body update. Uncertain mutation results require read-only
reconciliation before any retry. Rebase, amend, force-push, merge, auto-merge,
Ready, branch deletion/reset and any additional branch or PR are forbidden.

## 11. Evidence

Final evidence path:

`artifacts/m1b/m1b-1a-r1/auth-v7-evidence.json`

It is strict canonical ASCII JSON with one LF, regular mode `0600`,
`st_nlink=1`, Git-ignored and untracked. It contains final scope/owner and
publication identities, all `139` exact matrix rows, action/resource/process
closure, six sanitized observations, observation-hash preimages, commit
side-effect results, cleanup `6/6`, validation results and only leakage-safe
public metadata.

Historical evidence v1 through v6 must remain byte-identical, regular mode
`0600`, `st_nlink=1`, ignored, untracked and on distinct inodes.

## 12. Explicit stop

Repository tests and repository Python are excluded. Candidate/provider
import, parsing, tokenization, linting, compilation or execution are forbidden.
Corpus, mods, Stellaris, Workshop, launcher, model store, Ollama and real
translation inputs/outputs are not read.

This contract ends at:

```text
REMEDIATION: READY_FOR_REVIEW
M1B-1A-R1-AUTH-V7: READY_FOR_OWNER_REVIEW
R1_REMEDIATION: NOT_AUTHORIZED_UNTIL_V7_MERGE
NEW_REPOSITORY_CODE_EXECUTION: NOT_AUTHORIZED
PROVIDER_EXECUTION: NOT_STARTED
EXECUTABLE_TCB_ADMISSION: NOT_GRANTED
M1B: NOT_EVALUATED
M1A: BLOCKED
M2: FORBIDDEN
PR11: DRAFT
```
