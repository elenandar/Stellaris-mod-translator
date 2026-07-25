# M1B-1A-R1-AUTH v6 — post-merge transport and evidence-provenance remediation authorization

Status: `READY_FOR_OWNER_REVIEW`. This contract is authorization-only. It does
not authorize R1 remediation until external owner review and the exact PR #11
merge defined below.

The normative machine source is
[`registry/m1b/m1b-1a-r1-remediation-scope-v6.json`](../../registry/m1b/m1b-1a-r1-remediation-scope-v6.json).
The machine owner decision is
[`M1B-1A-R1-AUTH-owner-authorization.json`](../decisions/M1B-1A-R1-AUTH-owner-authorization.json),
and the human-readable acceptance record is
[`M1B-1A-R1-AUTH-owner-signoff.md`](../decisions/M1B-1A-R1-AUTH-owner-signoff.md).
If prose conflicts with either canonical JSON artifact, authority fails closed
and a new owner decision is required.

## 1. Decision boundary and generation

This v6 supersedes v5 before effect. It changes only the authorization control
plane:

1. every gate action is closed through an explicit action/authority matrix;
2. critical Git processes have one normative argv/environment/cwd source;
3. local configuration and transport routing have closed value predicates;
4. six host probes have reproducible public declarative definitions and
   sanitized result identities;
5. six minimal adversarial families cover the newly closed surfaces.

Protocol generation `108`, candidate identities, future contract generation
`5`, the exact historical PR #10 baseline and all preserved blockers are
unchanged. Candidate/provider execution, M1B-1A2, benchmark, M2, active
translation and publishing remain forbidden.

Before effect, only validation of these authorization bytes, execution of the
six committed public synthetic probe definitions, creation of the ignored v6
evidence, and publication to the existing draft PR #11 are allowed. After
effect, the already bounded one-branch/one-commit/one-push/one-draft-PR R1
workflow is unchanged.

## 2. Canonical identities

Both JSON artifacts use strict ASCII, sorted keys, compact encoding and exactly
one trailing LF. Duplicate keys, floats, `NaN` and Infinity are invalid.

| Artifact | Bytes | Raw SHA-256 |
|---|---:|---|
| `registry/m1b/m1b-1a-r1-remediation-scope-v6.json` | `145625` | `508a16e396fd34bfb598dcbbd7e0680402573b12cd0b9b82ad99680d15ae8249` |
| `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json` | `20869` | `3b046865974be9acbd61729e0dbaff95aa388f55cd2de20220346078b6b9e238` |

Scope framing is
`SHA-256("stellaris-m1b-1a-r1-remediation-scope-v6" || NUL ||
u64be(145625) || canonical_scope_bytes)`. The framed SHA-256 is
`99eba953ec70b0b243cc8cfa31dd859b834ed5a8d66e20ca2d3ab1780dde67ec`.

Scope states are:

- v1: `never_effective`;
- v2, v3, v4, v5: `superseded_before_effect`;
- v6: `not_effective_owner_review_and_merge_required`.

No superseded generation authorizes PR #10 retroactively.

## 3. Historical and PR #11 effect binding

PR #10 remains an owner-controlled historical scope deviation:

- head `66f905cf266b9d1c1f56d0d706184387ffedb36e`;
- merge `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- ordered parents
  `1f10c151c5adac5fbf765af8093c7eddf8cf0429`,
  `66f905cf266b9d1c1f56d0d706184387ffedb36e`;
- tree `289e2396975c5ef6fe1001a7c5990523edaa06c5`;
- exact changed paths `11`;
- candidate state `INERT_NOT_ADMITTED`.

This authorization remains on existing draft PR #11:

- repository `elenandar/Stellaris-mod-translator`;
- base branch `main`;
- historical base `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- head branch `agent/m1b-1a-r1-transport-provenance-auth`;
- recovery integration merge
  `3a57701275914d905f76606cf6db3072c40a17ac`.

Effect requires one ordinary external owner-controlled two-parent merge. The
first parent must be exact
`3c6ca3146d838b977f24bbc6b8c79dfb271e142b`, and the second parent must be the
final reviewed PR #11 head. The PR delta and merge delta must both contain the
exact six authorization paths. Scope v1–v5 must be absent, scope v6 must be the
only R1 scope, and the four normative artifacts must be byte-identical between
the final PR head and merge tree. Any change to the base, parent order, path
set or accepted identity blocks effect.

## 4. Closed action/authority matrix

The machine scope contains `21` unique action records across six closed planes:

- `authorization_stage_host_validation`;
- `activation_verification_plane`;
- `git_github_control_plane`;
- `host_validation`;
- `repository_content_plane`;
- `initial_worktree_validation_read_plane`.

The matrix namespace is exactly `AUTH_V6_*` and `GATE_*`. Existing post-gate
publication actions remain separately closed by the exact
`git_github_control_plane.allowed_actions` plus their count, path, branch and
pull-request constraints; v6 neither removes nor expands them.

Every matrix action record contains one exact ID, phase, every applicable plane,
metadata reads, content reads, process authority, network authority,
Git-internal writes and failure classification. Every applicable plane repeats
that ID in its own closed `allowed_action_ids`. A validator must prove exact
two-way closure: no missing plane membership, no extra allowlist member, no
unknown resource and no unresolved process reference. The two namespaces may
not overlap. Deny takes precedence over every allow. Unknown, duplicate,
ambiguous or unlisted action in either namespace is
`INITIAL_WORKTREE_GIT_EXECUTION_SURFACE_UNSAFE`.

The ordered gate actions are:

1. `GATE_BIND_REPOSITORY_LAYOUT`;
2. `GATE_READ_LOCAL_CONFIG`;
3. `GATE_READ_INDEX_AND_SPARSE_METADATA`;
4. `GATE_LSTAT_OBJECT_ALTERNATES`;
5. `GATE_LSTAT_ATTRIBUTES_METADATA`;
6. `GATE_SNAPSHOT_EXECUTABLE_ENVIRONMENT`;
7. `GATE_LS_REMOTE_EXACT`;
8. `GATE_FETCH_EXACT`;
9. `GATE_REPEAT_EXECUTION_SURFACE`;
10. `GATE_VERIFY_LOCAL_OBJECT_CLOSURE`;
11. `GATE_VERIFY_EFFECT_AND_ABSENCE`;
12. `GATE_COMPARE_ROOT_TREE`;
13. `GATE_READ_COMPLETE_TRACKED_INVENTORY`;
14. `GATE_CHECK_RAW_CLEANLINESS`;
15. `GATE_PRE_TRANSITION_FRESHNESS`;
16. `GATE_DIRECT_TRANSITION`;
17. `GATE_POST_TRANSITION_FRESHNESS`;
18. `GATE_EVALUATE_OUTPUT_LIFECYCLE`.

The three authorization-stage actions are separately closed and do not grant
future R1 execution.

## 5. Exact metadata and content resources

The repository content plane defaults to deny. It permits only the named
machine resources and their exact access predicates:

- verified repository-root and worktree filesystem identities;
- verified Git-dir, common-dir and object-dir identities;
- exact local `config` plus `config.worktree` absence;
- exact index and sparse metadata;
- exact `objects/info/alternates` and `http-alternates` absence;
- exact Git-dir/common-dir `info/attributes` absence;
- metadata-only `lstat` of relevant worktree `.gitattributes` and
  `.gitmodules` routes;
- exact `info/grafts` and `shallow` absence;
- descriptor-bound object inventory and canonical object bytes solely for
  local recursive closure;
- exact executable and process-environment snapshots;
- the complete equal-tree tracked set, solely for no-follow identity hashing
  without content output;
- exact authorization outputs and exact ignored v6 evidence.

This is not broad `.git` authority. Untracked content is not readable.
Relevant untracked attribute paths receive metadata-only `lstat`; their bytes
remain forbidden. Symlink, hardlink, alias, escape or route ambiguity blocks
the action.

Repository reads and writes are also phase-bound. During v6 authoring, only
the exact six tracked authorization outputs and exact ignored v6 evidence are
writable. Activation is read-only apart from exact fetch internals. Post-effect
writes retain the existing exact future-output and consequential-Git-internal
limits. A host-validation action outside its declared phase is denied.

## 6. Normative Git processes

The only critical executable is:

`/Library/Developer/CommandLineTools/usr/bin/git`

The machine profile contains exactly three process definitions:

- `git_ls_remote_exact`;
- `git_fetch_exact`;
- `git_direct_transition_exact`.

Each definition stores a full argv array, exact environment map, exact denied
environment set, pre-check action IDs, post-check action IDs, network scope and
Git-internal write set. Direct `execve` is required. Shells, aliases, functions,
wrappers, path substitution and repository discovery from an arbitrary cwd
are forbidden.

Every process cwd is the prevalidated repository-root filesystem identity.
Before and after execution, the host revalidates cwd, repository root,
worktree, Git-dir, common-dir, object-dir, index and local-config routes. A
rename, replacement, identity change or ambiguity fails closed.

All three argv arrays contain these exact command-scoped entries:

- `core.attributesFile=/dev/null`;
- `core.excludesFile=/dev/null`;
- `core.autocrlf=false`;
- `core.pager=`;
- `core.hooksPath=/dev/null`;
- `core.fsmonitor=false`;
- `submodule.recurse=false`.

Their exact base environment isolates global and system config to `/dev/null`
and requires `GIT_CONFIG_NOSYSTEM=1`, `GIT_ATTR_NOSYSTEM=1`,
`GIT_NO_REPLACE_OBJECTS=1`, `GIT_OPTIONAL_LOCKS=0`,
`GIT_TERMINAL_PROMPT=0`, empty Git/system pagers, and `LANG=LC_ALL=C`.
After bounded fetch, `GIT_NO_LAZY_FETCH=1` is additionally mandatory.

No independent display command is normative or stored. A display form may be
produced only by the committed POSIX single-quote derivation over the exact
environment map and argv array, and its round trip must reproduce both
structures byte-for-byte.

## 7. Local config and transport closure

The local policy defaults to deny and accepts only:

- the six exact repository-core key/value predicates recorded in the machine
  scope;
- exact `remote.origin.url =
  https://github.com/elenandar/Stellaris-mod-translator.git`;
- exact standard `remote.origin.fetch`;
- validated local branch `remote=origin` and matching
  `merge=refs/heads/<same-branch>`.

Deny wins for all of:

- `include.*` and `includeIf.*`;
- `url.*.insteadOf` and `url.*.pushInsteadOf`;
- unexpected remote URL/fetch, `pushurl`, VCS/helper/uploadpack or proxy keys;
- `credential.*` and `core.askPass`;
- `protocol.*`;
- external diff, textconv, filter and pager commands;
- `core.alternateRefsCommand`, worktree redirection, partial clone, promisor
  and filter configuration;
- unknown, duplicate, malformed or ambiguous keys/values.

Askpass, SSH-command, Git-proxy and upper/lower-case HTTP proxy environment
routes are absent from every exact process environment. Credential keys fail
at key recognition without value decoding, storage or output. Credential
values are never a tracked input, evidence field or model-visible value.
Existing external user authentication remains outside tracked bytes and model
context; this contract creates no credential authority.

## 8. Reproducible six-probe suite

Every probe definition binds the same canonical public construction profile,
object inventory algorithm, system Git executable, direct argv, exact
environment, verified synthetic cwd, modes, no-symlink topology, sentinel
mechanism, expected exit, expected helper count, expected object-write delta,
sanitized fields and cleanup.

The common fixture uses only public bytes `baseline\n`, `changed\n`, an exact
public `.gitattributes` string, an empty sentinel, and a committed helper whose
only possible effect is appending one public `executed\n` record before exit
`97`. Temporary repositories are freshly created outside the project and
deleted after observation. No repository or candidate code participates.

| Probe ID | Definition SHA-256 | Expected result |
|---|---|---|
| `clean_filter_sentinel_not_executed` | `48b7a6dd201bf4b0b33538b63fb37e9563ff861947f4a920d0c32e5d32b03bdb` | blob OID, helper `0`, object delta `0` |
| `process_filter_sentinel_not_executed` | `2e4773cf8d159ddd7cc99e6db53a8f31b785c8d7c349b9f8103b8b791bb69d81` | blob OID, helper `0`, object delta `0` |
| `external_diff_sentinel_not_executed` | `824003584ae87987f7214643ca0f32a3d3e9c7f9a58e64a742b12738933b3baf` | expected difference, helper `0`, object delta `0` |
| `textconv_sentinel_not_executed` | `1a2ac0758560d02eac5bd4f37143ad3ee095f96fe16649ae87013ba731889bdc` | expected difference, helper `0`, object delta `0` |
| `remote_helper_sentinel_not_executed_after_gate` | `cf73ffacddf648ad528e08f27335c730ed11d84974d8d54661adb0dff6d8052e` | missing object, helper `0`, object delta `0` |
| `object_database_unchanged_during_local_closure` | `e8f6c58ae75a110878b9f75b6584affe762539ddc2f1a8c44754da1c7b34b6c1` | local object present, helper `0`, object delta `0` |

The object inventory walks only regular no-follow files under the synthetic
`.git/objects`, sorts ASCII relative paths, and hashes rows containing relative
path, mode, size and content SHA-256. Persisted observations contain only
counts, hashes and classifications. Absolute paths, private configuration,
credentials and raw repository content are prohibited.

## 9. Adversarial matrix

Counts are derived from the final enumeration:

| Count | Value |
|---|---:|
| preserved case families | `11` |
| new case families | `23` |
| total case families | `34` |
| unique `case_id × variant_id` rows | `103` |

The row-set digest is SHA-256 over lexicographically sorted UTF-8 rows encoded
as `case_id || NUL || variant_id || LF`:

`ec114a7f11825e889b1cd5fe578ac3f293a6c542fb23abc5ccfcb5f916b32e63`.

Families 29–34 minimally add: missing action/plane membership; wrong or
substituted cwd; each missing required command-scoped config entry; URL
rewrite; credential/askpass/protocol routing; and argv/environment display
derivation mismatch. All fail before transition.

The authorization stage validates all 103 static definitions but executes only
the exact six public probe definitions. Full execution of the future matrix,
repository code or candidate code is not authorized by v6.

## 10. Evidence and validation boundary

The ignored evidence path is:

`artifacts/m1b/m1b-1a-r1/auth-v6-evidence.json`

It must be strict canonical JSON, regular mode `0600`, `st_nlink=1`, ignored,
untracked and physically distinct from historical evidence. Each probe stores
its ID, definition hash, sanitized observation hash, exit classification,
stdout/stderr byte counts and hashes, sentinel pre/post counts, object
inventory pre/post digests and object-write delta.

Historical v1–v5 evidence is immutable. Required validation uses only trusted
one-shot host validators: two independent canonical/framed reproductions,
duplicate/float/non-finite rejection, action/plane closure, argv/env/cwd
closure, config policy closure, matrix recomputation, the six synthetic probes,
historical evidence identity, exact input closure, exact six-path diff,
Markdown-link and leakage checks, and final Git/GitHub parity.

Repository tests and repository Python, candidate/provider import, parsing,
tokenization, linting, compilation or execution are deliberately excluded.
Corpus, mods, Stellaris, Workshop, launcher, model store, Ollama and real
translation data are not read.

## 11. Status after publication

`REMEDIATION: READY_FOR_REVIEW`

`M1B-1A-R1-AUTH-V6: READY_FOR_OWNER_REVIEW`

`R1_REMEDIATION: NOT_AUTHORIZED_UNTIL_V6_MERGE`

`NEW_REPOSITORY_CODE_EXECUTION: NOT_AUTHORIZED`

`PROVIDER_EXECUTION: NOT_STARTED`

`EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`

`M1B: NOT_EVALUATED`

`M1A: BLOCKED`

`M2: FORBIDDEN`

`PR11: DRAFT`
