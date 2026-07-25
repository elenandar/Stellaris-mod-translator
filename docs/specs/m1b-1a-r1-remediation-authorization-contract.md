# M1B-1A-R1-AUTH v5 — post-merge transport and evidence-provenance remediation authorization

Status: `READY_FOR_OWNER_REVIEW`. This contract is authorization-only. It does
not authorize R1 remediation until external owner review and the exact PR #11
merge defined below.

The normative machine source is
[`registry/m1b/m1b-1a-r1-remediation-scope-v5.json`](../../registry/m1b/m1b-1a-r1-remediation-scope-v5.json).
The machine owner decision is
[`M1B-1A-R1-AUTH-owner-authorization.json`](../decisions/M1B-1A-R1-AUTH-owner-authorization.json),
and the human-readable acceptance record is
[`M1B-1A-R1-AUTH-owner-signoff.md`](../decisions/M1B-1A-R1-AUTH-owner-signoff.md).
If prose conflicts with the canonical machine scope or owner record, the
machine artifacts fail closed and a new owner decision is required.

## 1. Decision boundary

This v5 supersedes v4 before effect and closes only the following gaps in the
future post-merge gate:

1. persistent object routing and lazy fetch;
2. effective repository, worktree, index and configuration routing;
3. attributes, filters, external diff/textconv and raw no-filter cleanliness;
4. freshness of those gates before fetch, after fetch, and immediately before
   and after the sole direct transition;
5. isolated adversarial definitions and bounded host sentinel evidence for
   those surfaces.

Everything else remains at committed v4 semantics. In particular, v5 does not
create a credential authority, a new GitHub API client authority, or a new
post-transition publication protocol.

The owner decision remains:

- `acceptance_state = owner_accepted`;
- effect only `after_review_and_merge_to_main`;
- before effect, only authorization validation and existing draft PR #11
  publication are allowed;
- after effect, only one exact remediation branch, one ordinary commit, one
  normal non-force push, and one new draft PR are allowed;
- candidate/provider execution, M1B-1A2, benchmark and M2 remain forbidden.

## 2. Canonical identities

The final canonical scope is compact sorted-key ASCII JSON with one trailing
LF, no duplicate keys, no floats, and no `NaN` or Infinity.

| Artifact | Bytes | Raw SHA-256 |
|---|---:|---|
| `registry/m1b/m1b-1a-r1-remediation-scope-v5.json` | `88725` | `e62a2db0459a78a07974ff14af6703fc20531440131e7168dcc79909b01d26f5` |
| `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json` | `18763` | `6ed5b8490ab678cf614e345de2348f24aa8e04b711e6e8b72757cb35066c41bf` |

Scope framing is
`SHA-256("stellaris-m1b-1a-r1-remediation-scope-v5" || NUL ||
u64be(88725) || canonical_scope_bytes)`. The resulting framed SHA-256 is
`143a8dd1c3bb3b5f80e7450a2fcd319b214c94ffedcefd5ba5f95ed0d982951a`.

Historical v4 remains byte-identical in the committed parent:

- canonical bytes: `60524`;
- raw SHA-256:
  `563a9e7c8e91eaf4d5ae350a392a86099c0c6b1df5acab5f8c288aa343e3f1fb`;
- framed SHA-256:
  `3082cd0f403d08b7a0558cda2c6e8ca517456238d73e78df80987c0935cd1015`;
- effect state: `superseded_before_effect`.

`SCOPE_V1: NEVER_EFFECTIVE`; v2, v3 and v4 are
`SUPERSEDED_BEFORE_EFFECT`. None may authorize PR #10 retroactively.

## 3. Historical and publication binding

PR #10 remains a historical owner-controlled scope deviation:

- PR: `10`;
- head:
  `66f905cf266b9d1c1f56d0d706184387ffedb36e`;
- merge commit:
  `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- ordered parents:
  `1f10c151c5adac5fbf765af8093c7eddf8cf0429`,
  `66f905cf266b9d1c1f56d0d706184387ffedb36e`;
- merge tree:
  `289e2396975c5ef6fe1001a7c5990523edaa06c5`;
- changed paths: exact `11`;
- candidate state: `INERT_NOT_ADMITTED`.

This authorization remains on existing draft PR #11:

- repository: `elenandar/Stellaris-mod-translator`;
- base: `main`;
- historical base:
  `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- head branch: `agent/m1b-1a-r1-transport-provenance-auth`;
- recovery integration merge:
  `3a57701275914d905f76606cf6db3072c40a17ac`;
- final head is the external reviewed head of PR #11 and the exact second
  parent of the future two-parent owner merge.

Effect requires one ordinary two-parent non-squash, non-rebase owner-controlled
merge. Its first parent is exact
`3c6ca3146d838b977f24bbc6b8c79dfb271e142b`; its second parent is the final
reviewed PR #11 head. Both PR and merge deltas must contain the exact six
authorization-stage outputs, and the scope, owner record, contract and signoff
must be byte-identical between that final head and the merge tree.

Changing `main`, changing the exact path set, or changing any normative identity
before merge blocks effect.

## 4. Removed semantic scope creep

The following dirty-v5 surfaces are explicitly removed and receive no
authority:

- owner-supplied PAT or any other owner credential value;
- Basic-auth header construction;
- token or header transport through environment or Git configuration;
- `sandbox-exec` as a network supervisor;
- temporary network `HOME`, `CURL_HOME` or netrc protocol;
- exact HTTPS-helper hash, code-signature or codesign pins;
- connector-specific GitHub API execution profile;
- manual merge-attestation protocol;
- post-transition `git add`, raw `update-index`, commit-tree, ref update, push
  construction or final-parity hardening not present in v4;
- adversarial families 29–33 and all variants that existed only for those
  surfaces.

Credential handling is outside tracked authorization bytes and outside model
context. Existing external user authentication is used for the same bounded
Git/GitHub publication operations already present in v4. No credential value,
credential source, header construction, helper binary identity, or private
configuration value becomes a normative input.

The critical local executable remains absolutely bound to
`/Library/Developer/CommandLineTools/usr/bin/git`, invoked directly without a
shell. A fresh per-process filesystem identity check is required, but the
current host build SHA, code signature, helper SHA or helper signature is not a
long-lived acceptance root.

## 5. Fail-closed gate order

The single unsafe result for any missing, ambiguous, stale or mismatched
execution-surface condition is:

`INITIAL_WORKTREE_GIT_EXECUTION_SURFACE_UNSAFE`.

Before the first authoritative Git process — including `ls-remote`, fetch, or
any revision walk — the trusted host controller must perform, in order:

1. bind the exact repository top-level, worktree, Git dir, common dir, object
   dir, index route, local config route and absolute system-Git executable;
2. reject alternate environment, command-line and configuration routing;
3. require `lstat(ENOENT)` for
   `<object-dir>/info/alternates` and
   `<object-dir>/info/http-alternates`;
4. reject partial-clone/promisor/filter configuration;
5. require absent `core.worktree`, absent `extensions.worktreeConfig`, and
   `lstat(ENOENT)` for `<common-dir>/config.worktree`;
6. reject sparse checkout, sparse index, split/alternate index, unmerged
   entries, `skip-worktree` and `assume-unchanged`;
7. isolate attributes, filters, external diff/textconv, pager, hooks,
   fsmonitor, submodule and remote-helper surfaces;
8. capture a fresh routing/object/config/index/attribute snapshot.

No Git process is authoritative before all eight checks pass.
`rev-list --alternate-refs` is specifically forbidden before absence of
alternates is proven.

Only then may one exact remote advertisement and one exact bounded atomic fetch
run against
`https://github.com/elenandar/Stellaris-mod-translator.git`, limited to exact
`main`, PR #11 head and future-branch absence bindings.

Immediately after fetch the entire eight-step gate is repeated. Then
`GIT_NO_LAZY_FETCH=1` is mandatory and the host must:

1. prove recursive local commit/tree/blob/gitlink closure for every commit used
   as ancestry or tree authority;
2. recompute every required local object identity;
3. prove zero remote-helper invocations and zero object-database writes after
   bounded fetch through the direct transition;
4. verify effect and future branch/PR absence;
5. compare complete root-tree equality, not only the 19 future outputs;
6. prove filter-free index/worktree cleanliness;
7. repeat freshness immediately before the sole direct transition;
8. perform the exact direct create-and-switch;
9. repeat freshness and prove zero tracked content delta immediately after the
   transition;
10. only then evaluate the `19/19` future-output lifecycle gate.

The fetch exception permits only its exact object and remote-ref consequences.
Missing recursive objects fail closed; root-tree OID equality alone is not
sufficient.

## 6. Repository, configuration and object routing

The critical process environment isolates global and system Git configuration
to `/dev/null`, requires `GIT_CONFIG_NOSYSTEM=1`,
`GIT_NO_REPLACE_OBJECTS=1`, `GIT_OPTIONAL_LOCKS=0`, `LANG=C`, and `LC_ALL=C`.
After fetch it additionally requires `GIT_NO_LAZY_FETCH=1`.

The following effective routes are denied:

- `GIT_DIR`, `GIT_COMMON_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`,
  `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`,
  `GIT_NAMESPACE`, `GIT_EXEC_PATH`;
- `GIT_CONFIG`, `GIT_CONFIG_COUNT`, indexed config key/value injection,
  `GIT_CONFIG_PARAMETERS`, and unapproved global/system config routes;
- local `include` or `includeIf`;
- `core.alternateRefsCommand`, `core.worktree`,
  `extensions.partialClone`, `extensions.worktreeConfig`;
- `remote.*.promisor` and `remote.*.partialclonefilter`.

The local recursive closure is descriptor-rooted, no-follow, local-only and
content-non-output. It handles commits, trees, blobs and required gitlink target
commit objects, recomputes canonical SHA-1 object identities, and emits only
booleans, counts, hashes and classifications. Missing, wrong-type,
hash-mismatched, aliased or ambiguous objects block authority.

## 7. Attributes, filters and raw cleanliness

Every critical process requires `GIT_ATTR_NOSYSTEM=1` and
`core.attributesFile=/dev/null`. Global and system attributes are isolated
without reading, modifying or deleting the user's configuration. Global
Git-LFS configuration is not a semantic input and is not read, modified or
deleted.

Both `<git-dir>/info/attributes` and
`<common-dir>/info/attributes` must be absent by `lstat(ENOENT)`. Relevant
worktree `.gitattributes` ancestors and `.gitmodules` must also be absent unless
a later owner-reviewed exact policy explicitly admits them.

Effective local `filter.*`, `diff.external`, `diff.*.command` and
`diff.*.textconv` are forbidden. Clean, smudge and process drivers cannot run.
Hooks, fsmonitor and submodule checkout are disabled for the transition.

Ordinary `git status` or `git diff` is not authority. Raw cleanliness compares
stage-zero index blob identities with descriptor-rooted, no-follow raw
worktree Git-blob identities without attributes or filters. A secondary
`git diff --no-ext-diff --no-textconv` may be diagnostic only after the
filter-free surface is already proven.

## 8. Adversarial matrix

The final machine scope contains exact counts computed from its enumerations:

| Count | Value |
|---|---:|
| preserved case families | `11` |
| new case families | `17` |
| total case families | `28` |
| unique `case_id × variant_id` rows | `87` |

The row-set digest is SHA-256 over lexicographically sorted UTF-8 rows encoded
as `case_id || NUL || variant_id || LF`:

`b0d6ce61f98d35d921418d406b88ba8ed4c4cb2b12aeb3116623019137915f84`.

Families 1–11 preserve the exact v4 tree/transition cases. Families 12–28 are:

12. regular `objects/info/alternates`;
13. symlink `objects/info/alternates`;
14. unreadable `objects/info/alternates`;
15. regular, symlink or unreadable `objects/info/http-alternates`;
16. partial clone/promisor/filter and missing blob;
17. equal root tree with missing recursive tree/blob/required gitlink object;
18. missing object with no lazy fetch, no helper and no object write;
19. present or redirected `core.worktree`;
20. worktree-config extension, redirect or stray `config.worktree`;
21. executable/repository/config/index/common-dir/object-route injection,
    including a forbidden pre-gate `rev-list --alternate-refs`;
22. sparse checkout/index, skip-worktree or assume-unchanged;
23. Git-dir/common-dir info attributes;
24. isolated global and system attributes;
25. nested attributes, local clean/smudge/process filters or unreviewed
    `.gitmodules`;
26. external diff, diff command or textconv;
27. routing/config snapshot drift;
28. positive complete-local-store same-tree direct transition.

Every row resolves to exactly one closed classification. Missing, duplicate,
overlapping or uncovered rows fail closed. Full future execution of all 87 rows
is not authorized by v5 and requires a separate owner gate.

## 9. Authorization-stage sentinel evidence

Current AUTH validation executed exactly six allowed host-level probes in fresh
temporary synthetic Git repositories:

1. clean-filter sentinel not executed;
2. process-filter sentinel not executed;
3. external-diff sentinel not executed;
4. textconv sentinel not executed;
5. post-gate no-lazy remote-helper sentinel not executed;
6. local-closure object database unchanged.

Observed counts:

- targeted probes: `6/6`;
- helper sentinel executions: `0`;
- object-database writes: `0`;
- classification: `TARGETED_HOST_SENTINELS_PASS`.

These probes executed no repository or candidate code. They prove only the
bounded helper/filter containment claims above and do not authorize future
candidate execution or substitute for future remediation acceptance.

Final ignored evidence is
`artifacts/m1b/m1b-1a-r1/auth-v5-evidence.json`. It must be canonical compact
JSON, regular mode `0600`, `st_nlink=1`, Git-ignored and not staged. It may
contain only booleans, counts, hashes, case/variant identifiers,
classifications and exact public PR identifiers. Absolute local paths,
credentials, private configuration values and raw repository/private content
are forbidden.

Evidence v1, v2, v3 and v4 must remain byte-identical, regular mode `0600`,
`st_nlink=1`, physically unique, contained and unstaged.

## 10. Preserved publication semantics

After effect, and only after every initial gate succeeds, the scope permits:

- one new branch
  `agent/m1b-1a-r1-postmerge-remediation`;
- exact branch base: the owner-controlled PR #11 merge commit;
- exactly one direct create-and-switch with zero tracked content delta;
- the existing closed `19`-path future-output allowlist;
- one ordinary remediation commit;
- one normal non-force push;
- one new draft PR to `main`;
- one title/body update of that new draft PR;
- read-only reconciliation if the push or PR mutation result is ambiguous.

Credential handling remains external. The tracked scope does not define PAT,
Basic-auth, environment-header, netrc, connector or helper-identity protocols.

The scope does not permit rebase, amend, force-push, another branch or PR,
merge, auto-merge, ready-for-review, main mutation, candidate execution,
provider/Ollama/model calls, corpus/game/mod/Workshop/launcher reads,
M1B-1A2, benchmark, product CLI or M2.

## 11. Authorization-stage outputs and stop point

The final PR #11 diff against `main` must contain exactly:

1. `README.md`;
2. `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json`;
3. `docs/decisions/M1B-1A-R1-AUTH-owner-signoff.md`;
4. `docs/roadmap.md`;
5. `docs/specs/m1b-1a-r1-remediation-authorization-contract.md`;
6. `registry/m1b/m1b-1a-r1-remediation-scope-v5.json`.

Scope v4 must be absent. The ignored v5 evidence must not be staged or appear in
the PR diff.

The stop point is owner review of draft PR #11:

```text
SCOPE_CREEP: REMOVED
CANONICAL_IDENTITIES: PASS
REMEDIATION: READY_FOR_REVIEW
PR10: MERGED_OWNER_CONTROLLED_SCOPE_DEVIATION
PR10_CANDIDATE: INERT_NOT_ADMITTED
SCOPE_V1: NEVER_EFFECTIVE
SCOPE_V2: SUPERSEDED_BEFORE_EFFECT
SCOPE_V3: SUPERSEDED_BEFORE_EFFECT
SCOPE_V4: SUPERSEDED_BEFORE_EFFECT
M1B-1A-R1-AUTH-V5: READY_FOR_OWNER_REVIEW
R1_REMEDIATION: NOT_AUTHORIZED_UNTIL_V5_MERGE
NEW_REPOSITORY_CODE_EXECUTION: NOT_AUTHORIZED
PROVIDER_EXECUTION: NOT_STARTED
EXECUTABLE_TCB_ADMISSION: NOT_GRANTED
M1B: NOT_EVALUATED
M1A: BLOCKED
M2: FORBIDDEN
PR11: DRAFT
```
