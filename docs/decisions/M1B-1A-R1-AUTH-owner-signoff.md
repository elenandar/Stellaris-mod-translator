# Owner signoff M1B-1A-R1-AUTH v5

Decision: `owner_accepted` for exact authorization bytes only.

Effect: `after_review_and_merge_to_main`.

This signoff does not merge PR #11, does not mark it ready, and does not
authorize R1 remediation before the exact owner-controlled merge. It does not
authorize repository/candidate execution, provider/Ollama/model calls,
M1B-1A2, benchmark, product translation, publishing, M2 or product CLI.

## Accepted exact artifacts

I accept the following exact identities as the complete v5 authorization
decision:

| Artifact | Bytes | Raw SHA-256 |
|---|---:|---|
| `registry/m1b/m1b-1a-r1-remediation-scope-v5.json` | `88725` | `e62a2db0459a78a07974ff14af6703fc20531440131e7168dcc79909b01d26f5` |
| `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json` | `18763` | `6ed5b8490ab678cf614e345de2348f24aa8e04b711e6e8b72757cb35066c41bf` |
| `docs/specs/m1b-1a-r1-remediation-authorization-contract.md` | `16161` | `84ad9a9427da929e02479728f5fa5be6d799d9a2f04d9f625f79ebcd9bfea404` |

The scope schema is `m1b-1a-r1-remediation-scope-v5`, generation `5`.
Its framing domain is `stellaris-m1b-1a-r1-remediation-scope-v5`, with
framing `domain || NUL || u64be(length) || canonical_scope`. The framed
SHA-256 is
`143a8dd1c3bb3b5f80e7450a2fcd319b214c94ffedcefd5ba5f95ed0d982951a`.

The owner schema is
`m1b-1a-r1-remediation-owner-authorization-v5`. The machine owner record is
canonical compact sorted-key ASCII JSON with one LF and is authoritative
together with the canonical scope.

Historical v4 remains:

- `60524` bytes;
- raw SHA-256
  `563a9e7c8e91eaf4d5ae350a392a86099c0c6b1df5acab5f8c288aa343e3f1fb`;
- framed SHA-256
  `3082cd0f403d08b7a0558cda2c6e8ca517456238d73e78df80987c0935cd1015`;
- state `superseded_before_effect`.

## Scope I am accepting

I accept only the v4 authorization baseline plus these five gap closures:

1. persistent object routing and lazy-fetch control;
2. effective repository/worktree/index/config routing;
3. attributes, filter, external diff/textconv and raw no-filter cleanliness;
4. routing/object/config/attribute freshness before fetch, after fetch, and
   immediately before and after the direct transition;
5. minimal adversarial cases and bounded host sentinel evidence for those
   surfaces.

I do not accept the dirty-batch extensions that attempted to create separate
authority for:

- an owner-supplied PAT;
- Basic-auth header construction;
- token/header transport through environment or Git configuration;
- a `sandbox-exec` network supervisor;
- temporary network `HOME`, `CURL_HOME` or netrc handling;
- HTTPS helper hashes or code-signature pins;
- a connector-specific GitHub API execution profile;
- manual merge attestation;
- new post-transition staging, commit, push or final-parity protocols;
- cases and variants that existed only for those surfaces.

Credential handling remains outside tracked authorization bytes, outside
evidence, and outside model context. The existing external user authentication
used by the ordinary bounded Git/GitHub workflow remains the only
authentication route. No credential value or credential construction becomes
a normative input.

I accept the absolute critical Git executable binding:

`/Library/Developer/CommandLineTools/usr/bin/git`.

It is invoked directly without a shell and its path/filesystem identity must be
fresh at each critical process. I explicitly do not accept the current host
build SHA, code signature, helper SHA, helper signature, or codesign snapshot
as a long-lived authorization or credential root.

## Historical PR #10 and exact PR #11 effect

PR #10 remains `MERGED_OWNER_CONTROLLED_SCOPE_DEVIATION`:

- head:
  `66f905cf266b9d1c1f56d0d706184387ffedb36e`;
- merge:
  `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- ordered parents:
  `1f10c151c5adac5fbf765af8093c7eddf8cf0429`,
  `66f905cf266b9d1c1f56d0d706184387ffedb36e`;
- tree:
  `289e2396975c5ef6fe1001a7c5990523edaa06c5`;
- exact paths: `11`;
- candidate: `INERT_NOT_ADMITTED`.

PR #11 is the only authorization PR:

- repository: `elenandar/Stellaris-mod-translator`;
- base: `main`;
- base commit:
  `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- head branch: `agent/m1b-1a-r1-transport-provenance-auth`;
- recovery integration merge:
  `3a57701275914d905f76606cf6db3072c40a17ac`;
- effect requires the final reviewed PR #11 head to be the exact second parent
  of one ordinary two-parent owner-controlled merge;
- first parent must remain exact
  `3c6ca3146d838b977f24bbc6b8c79dfb271e142b`;
- both deltas must contain the exact six authorization outputs;
- scope, owner record, contract and signoff must be byte-identical between the
  final PR head and merge tree.

Any change to `main`, path set, parent order or accepted identity before merge
blocks effect.

## Accepted future gate order

Before the first authoritative Git process, including `ls-remote`, fetch or
revision walk, the trusted host must:

1. bind the repository top-level, worktree, Git dir, common dir, object dir,
   index, local config and absolute Git executable;
2. reject alternate environment, configuration and command-line routing;
3. require `lstat(ENOENT)` for object-store `alternates` and
   `http-alternates`;
4. reject partial-clone/promisor/filter configuration;
5. reject `core.worktree`, `extensions.worktreeConfig` and any
   `config.worktree`;
6. reject sparse, split/alternate or hidden index state;
7. isolate attributes, filters, external diff/textconv and helper surfaces;
8. capture a fresh complete gate snapshot.

`rev-list --alternate-refs` is forbidden before alternates absence is proven.
Any failure is
`INITIAL_WORKTREE_GIT_EXECUTION_SURFACE_UNSAFE`.

Only after that gate may one exact advertisement and one exact bounded fetch
run. Immediately after fetch, the whole gate repeats. Then
`GIT_NO_LAZY_FETCH=1` is set, recursive local commit/tree/blob/gitlink closure
is proven, remote-helper invocations and object-database writes must both
remain zero, complete tree equality and filter-free raw cleanliness are
proven, and freshness is repeated immediately before and after the sole direct
transition.

Only after the transition has zero tracked content delta may the future
`19/19` lifecycle gate begin.

## Accepted attributes and filter boundary

All critical Git processes use:

- `GIT_ATTR_NOSYSTEM=1`;
- global/system config isolation to `/dev/null`;
- `core.attributesFile=/dev/null`;
- `GIT_NO_REPLACE_OBJECTS=1`;
- `GIT_OPTIONAL_LOCKS=0`;
- `GIT_NO_LAZY_FETCH=1` after bounded fetch.

Git-dir/common-dir info attributes and every relevant worktree
`.gitattributes` route must be absent unless separately admitted by a future
owner decision. Local clean, smudge and process filter drivers are forbidden.
External diff and textconv are forbidden. Global Git-LFS configuration is not
read, changed or deleted.

Ordinary `git status` and `git diff` are not authority. Filter-free raw
worktree Git-blob identities are compared to the stage-zero index. A
`--no-ext-diff --no-textconv` diff may be diagnostic only after the filter-free
surface is already proven.

## Accepted adversarial matrix and sentinel evidence

Counts are derived from the final machine enumeration:

- preserved families: `11`;
- new families: `17`;
- total families: `28`;
- unique `case_id × variant_id` rows: `87`.

The row-set SHA-256 is:

`b0d6ce61f98d35d921418d406b88ba8ed4c4cb2b12aeb3116623019137915f84`.

The 17 new families cover only alternates/http-alternates, partial clone and
missing objects, recursive closure/no lazy fetch, core/worktree config,
routing/config/index/common-dir injection, sparse/hidden index state,
Git-dir/common-dir/global/system/nested attributes, clean/smudge/process
filters, external diff/textconv, freshness drift, and the positive complete
local-store same-tree transition.

Families 29–33 do not exist in the accepted scope.

Current AUTH validation ran six isolated host-level synthetic probes:

- targeted probes: `6/6`;
- helper sentinel executions: `0`;
- object-database writes: `0`;
- classification: `TARGETED_HOST_SENTINELS_PASS`.

No repository or candidate code was imported, parsed, tokenized, linted,
compiled or executed. Full future execution of all 87 rows is not granted by
this v5 decision.

## Evidence I require

Final evidence path:

`artifacts/m1b/m1b-1a-r1/auth-v5-evidence.json`.

It must be canonical compact sorted-key ASCII JSON with one LF, regular mode
`0600`, `st_nlink=1`, Git-ignored, not staged and physically unique. It may
contain only booleans, counts, hashes, case/variant identifiers,
classifications and exact public PR identifiers. Absolute paths, credentials,
private configuration values and raw repository/private content are forbidden.

Evidence v1/v2/v3/v4 must remain byte-identical and mode `0600`, `st_nlink=1`.
They may not be changed, deleted, replaced, staged or aliased.

## Publication authority and limits

Before effect, this decision permits only completing and publishing the exact
six-path authorization correction on existing draft PR #11 using one ordinary
follow-up commit and one normal non-force push.

After effect, this decision permits only:

- one branch
  `agent/m1b-1a-r1-postmerge-remediation`;
- exact base: the owner-controlled PR #11 merge commit;
- one direct create-and-switch with zero tracked content delta;
- the existing exact `19`-path remediation allowlist;
- one ordinary commit;
- one normal non-force push;
- one new draft PR to `main`;
- one title/body update of that draft PR;
- read-only reconciliation if a mutation result is ambiguous.

It does not permit another branch or PR, rebase, amend, force-push, merge,
auto-merge, ready-for-review, main mutation, candidate/provider execution,
model/corpus/game/mod reads, benchmark, M1B-1A2 or M2.

## Accepted stop point

The exact PR #11 diff must contain only:

1. `README.md`;
2. `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json`;
3. `docs/decisions/M1B-1A-R1-AUTH-owner-signoff.md`;
4. `docs/roadmap.md`;
5. `docs/specs/m1b-1a-r1-remediation-authorization-contract.md`;
6. `registry/m1b/m1b-1a-r1-remediation-scope-v5.json`.

The v4 scope path is absent. Ignored v5 evidence is not staged.

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
