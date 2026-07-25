# Owner signoff M1B-1A-R1-AUTH v6

Decision: `owner_accepted` for the exact authorization bytes below only.

Effect: `after_review_and_merge_to_main`.

This signoff does not merge PR #11, mark it ready or enable auto-merge. It does
not authorize R1 remediation before the exact owner-controlled merge. It does
not authorize repository/candidate execution, provider/Ollama/model calls,
M1B-1A2, benchmark, product translation, publishing, M2 or product CLI.

## Accepted exact artifacts

I accept these exact identities as the complete v6 authorization decision:

| Artifact | Bytes | Raw SHA-256 |
|---|---:|---|
| `registry/m1b/m1b-1a-r1-remediation-scope-v6.json` | `145625` | `508a16e396fd34bfb598dcbbd7e0680402573b12cd0b9b82ad99680d15ae8249` |
| `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json` | `20869` | `3b046865974be9acbd61729e0dbaff95aa388f55cd2de20220346078b6b9e238` |
| `docs/specs/m1b-1a-r1-remediation-authorization-contract.md` | `15331` | `5424c111002b71b26c49ad619022ad9630523ad8c09ee0378b8a184e04b4ce3c` |

The scope schema is `m1b-1a-r1-remediation-scope-v6`, generation `6`.
Its framing domain is `stellaris-m1b-1a-r1-remediation-scope-v6`, with framing
`domain || NUL || u64be(length) || canonical_scope`. The framed SHA-256 is:

`99eba953ec70b0b243cc8cfa31dd859b834ed5a8d66e20ca2d3ab1780dde67ec`.

The owner schema is
`m1b-1a-r1-remediation-owner-authorization-v6`. Scope and owner JSON are strict
ASCII sorted-key compact JSON with one LF. Duplicate keys, floats, `NaN` and
Infinity are rejected.

Scope v1 was never effective. Scope v2, v3, v4 and v5 were superseded before
effect. None authorizes PR #10 retroactively.

## Exact decision boundary

I accept the v5 semantics only after these v6 closures:

1. an explicit machine-checkable action/authority matrix;
2. one normative argv/environment/cwd source for every critical Git process;
3. closed local-config and transport-routing predicates;
4. reproducible definitions and sanitized observations for exactly six public
   synthetic sentinel probes;
5. six minimal adversarial families for the new closure.

Protocol generation `108`, candidate identities, future contract generation
`5`, the historical PR #10 baseline and preserved blockers do not change.

Before effect, authority is limited to validation of exact authorization bytes,
the exact six public synthetic probes in fresh temporary repositories outside
the project, ignored v6 evidence creation, and one bounded publication to the
existing draft PR #11. After effect, the previous exact one-branch,
one-commit, one-normal-push and one-new-draft-PR remediation envelope remains
the maximum.

## Historical PR #10 and exact PR #11 effect

PR #10 remains `MERGED_OWNER_CONTROLLED_SCOPE_DEVIATION`:

- head `66f905cf266b9d1c1f56d0d706184387ffedb36e`;
- merge `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- ordered parents
  `1f10c151c5adac5fbf765af8093c7eddf8cf0429`,
  `66f905cf266b9d1c1f56d0d706184387ffedb36e`;
- tree `289e2396975c5ef6fe1001a7c5990523edaa06c5`;
- exact paths `11`;
- candidate `INERT_NOT_ADMITTED`.

PR #11 is the only authorization PR:

- repository `elenandar/Stellaris-mod-translator`;
- base `main`;
- historical base
  `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- head branch `agent/m1b-1a-r1-transport-provenance-auth`;
- recovery integration merge
  `3a57701275914d905f76606cf6db3072c40a17ac`.

Effect requires the final reviewed PR #11 head as the exact second parent of one
ordinary external owner-controlled two-parent merge. The first parent must be
exact `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`. PR and merge deltas must both
contain the exact six authorization paths. Scope v1–v5 must be absent, scope v6
must be the only R1 scope, and the four normative artifacts must remain
byte-identical. Any different base, path set, parent order or identity blocks
effect.

## Accepted authority closure

I accept the `m1b-r1-action-authority-matrix-v1` only with:

- `21` unique action IDs;
- six exact closed authority planes;
- exact metadata/content/process/network/write/failure fields on every action;
- exact two-way membership between each action and every applicable plane;
- deny precedence;
- default deny for unknown, duplicate, missing or ambiguous actions;
- fully resolved resource and process references.

Its exact namespace is `AUTH_V6_*` and `GATE_*`. Existing post-gate publication
actions remain separately closed by the exact
`git_github_control_plane.allowed_actions` and their existing count, path,
branch and pull-request constraints. The namespaces may not overlap, and v6
does not implicitly add, remove or widen a publication action.

I accept only the exact resource routes for the verified repository root,
worktree, Git-dir, common-dir, object-dir, local config, `config.worktree`,
index, sparse metadata, alternates, HTTP alternates, info attributes, relevant
worktree attribute metadata, object database, executable/environment snapshots,
complete equal-tree tracked identities, exact authorization outputs and exact
ignored evidence.

This is not broad `.git` authority. It does not permit untracked content reads.
Relevant untracked attribute paths receive `lstat` metadata only. Alias,
symlink, hardlink, escape or filesystem-identity ambiguity fails closed.

Host validation is phase-bound. During v6 authoring, only the exact six tracked
authorization outputs and exact ignored v6 evidence are writable. Activation
is read-only except for exact bounded-fetch internals. Post-effect writes retain
the exact future-output and consequential-Git-internal boundary. A phase
mismatch is denied.

## Accepted Git process profile

The only accepted critical executable is:

`/Library/Developer/CommandLineTools/usr/bin/git`

The accepted profile ID is `m1b-1a-r1-git-execution-surface-v2`. Its only
critical process definitions are:

- `git_ls_remote_exact`;
- `git_fetch_exact`;
- `git_direct_transition_exact`.

Each process is direct, without shell, alias, function or wrapper. Cwd is the
prevalidated repository-root filesystem identity; discovery from another cwd
is forbidden. Cwd, Git-dir, common-dir, object-dir, index and config routes are
rechecked before and after execution.

Each exact argv contains:

- `core.attributesFile=/dev/null`;
- `core.excludesFile=/dev/null`;
- `core.autocrlf=false`;
- `core.pager=`;
- `core.hooksPath=/dev/null`;
- `core.fsmonitor=false`;
- `submodule.recurse=false`.

Every exact environment isolates global/system config to `/dev/null`, disables
system attributes, replacement objects, optional locks, terminal prompting and
pagers, and sets the C locale. `GIT_NO_LAZY_FETCH=1` is additionally required
after the bounded fetch.

No display command string is accepted as a second normative source. Any display
must be derived from the exact environment and argv arrays and round-trip back
to them without change.

## Accepted local config and transport boundary

The local policy defaults to deny. It accepts only exact repository-core
values, exact standard `origin` fetch, validated branch tracking, and this
exact origin:

`https://github.com/elenandar/Stellaris-mod-translator.git`

Deny wins for includes, conditional includes, URL rewrites, unexpected remote
URLs or helper/uploadpack/push routes, credential and askpass keys,
`protocol.*`, proxy routing, alternate-ref commands, external diff/textconv,
filters, attributes commands, partial clone/promisor/filter configuration, and
all unknown, duplicate, malformed or ambiguous keys.

Askpass, SSH-command, Git-proxy and HTTP proxy environment routes are absent
from the process maps. Credential keys fail at key recognition. Credential
values may not be decoded, stored, published or shown to a model. Existing
external user authentication remains outside tracked bytes and model context;
this decision creates no credential authority.

## Accepted matrix

Counts are derived from the exact final enumeration:

- preserved families: `11`;
- new families: `23`;
- total families: `34`;
- unique `case_id × variant_id` rows: `103`.

The row-set SHA-256 is:

`ec114a7f11825e889b1cd5fe578ac3f293a6c542fb23abc5ccfcb5f916b32e63`.

The six added families cover missing action/plane membership, wrong or replaced
cwd, each missing mandatory command-scoped value, URL transport rewrite,
credential/askpass/protocol routing, and derived-display mismatch. Full matrix
execution remains unauthorized.

## Accepted reproducible probe definitions

I accept exactly six declarative public probe definitions:

| Probe ID | Definition SHA-256 |
|---|---|
| `clean_filter_sentinel_not_executed` | `48b7a6dd201bf4b0b33538b63fb37e9563ff861947f4a920d0c32e5d32b03bdb` |
| `process_filter_sentinel_not_executed` | `2e4773cf8d159ddd7cc99e6db53a8f31b785c8d7c349b9f8103b8b791bb69d81` |
| `external_diff_sentinel_not_executed` | `824003584ae87987f7214643ca0f32a3d3e9c7f9a58e64a742b12738933b3baf` |
| `textconv_sentinel_not_executed` | `1a2ac0758560d02eac5bd4f37143ad3ee095f96fe16649ae87013ba731889bdc` |
| `remote_helper_sentinel_not_executed_after_gate` | `cf73ffacddf648ad528e08f27335c730ed11d84974d8d54661adb0dff6d8052e` |
| `object_database_unchanged_during_local_closure` | `e8f6c58ae75a110878b9f75b6584affe762539ddc2f1a8c44754da1c7b34b6c1` |

The suite uses only exact public fixture/sentinel bytes, exact modes, no
symlinks, direct system Git, a bound synthetic cwd, one committed object
inventory algorithm, expected exit classifications, helper count `0`, and
object-write delta `0`. Fresh temporary repositories must be outside the
project and deleted after observation. Repository/candidate code must not be
executed.

## Evidence I require

Final evidence path:

`artifacts/m1b/m1b-1a-r1/auth-v6-evidence.json`

It must be canonical ASCII JSON with one LF, regular mode `0600`,
`st_nlink=1`, Git-ignored, untracked and physically distinct. Each probe must
record only its ID, definition/result hashes, exit classification, stdout and
stderr byte counts/hashes, sentinel pre/post counts, object inventory
pre/post digests and object-write delta.

Absolute paths, private configuration, credentials and raw repository/private
content are forbidden. Historical evidence v1–v5 must remain byte-identical,
regular mode `0600`, `st_nlink=1`, ignored, untracked and physically distinct.

## Explicit exclusions and stop

Validation may use only trusted one-shot host validators and the system Git
bound above. Repository tests, repository Python, candidate/provider import,
parsing, tokenization, linting, compilation or execution are not authorized.
Corpus, mods, Stellaris, Workshop, launcher, model store, Ollama and real
translation data are not read.

This record ends at:

- `REMEDIATION: READY_FOR_REVIEW`;
- `M1B-1A-R1-AUTH-V6: READY_FOR_OWNER_REVIEW`;
- `R1_REMEDIATION: NOT_AUTHORIZED_UNTIL_V6_MERGE`;
- `NEW_REPOSITORY_CODE_EXECUTION: NOT_AUTHORIZED`;
- `PROVIDER_EXECUTION: NOT_STARTED`;
- `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`;
- `M1B: NOT_EVALUATED`;
- `M1A: BLOCKED`;
- `M2: FORBIDDEN`;
- `PR11: DRAFT`.
