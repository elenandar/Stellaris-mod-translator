# Owner signoff M1B-1A-R1-AUTH v7

Decision: `owner_accepted` for the exact authorization bytes below only.

Effect: `after_review_and_merge_to_main`.

This record does not merge PR #11, mark it ready or enable auto-merge. It does
not authorize R1 remediation before the exact owner-controlled merge. It does
not authorize repository/candidate execution, provider/Ollama/model calls,
M1B-1A2, benchmark, product translation, publishing, M2 or product CLI.

## Accepted exact artifacts

I accept these exact identities as the complete v7 authorization decision:

| Artifact | Bytes | Raw SHA-256 |
|---|---:|---|
| `registry/m1b/m1b-1a-r1-remediation-scope-v7.json` | `249528` | `cb66f117c89fac9888047e894762243ae99ac60b4998c6d77f5350617973ff3d` |
| `docs/decisions/M1B-1A-R1-AUTH-owner-authorization.json` | `24603` | `797aab6d7900b76e0de69665ff39ca43f800e7e9fea58c167d10ea58a51bd797` |
| `docs/specs/m1b-1a-r1-remediation-authorization-contract.md` | `12883` | `3b2d5442b00fffa289229951dc35c25679be25727f067dd934a3b5fdbcf52d50` |

The scope schema is `m1b-1a-r1-remediation-scope-v7`, generation `7`. Its
framing domain is `stellaris-m1b-1a-r1-remediation-scope-v7`; the framed
SHA-256 is:

`09769aab320568e435f96441f3442b268d322d3adddc15abb7e3445d34d8cc2e`.

The owner schema is
`m1b-1a-r1-remediation-owner-authorization-v7`. Scope and owner JSON are strict
ASCII sorted-key compact JSON with one LF. Duplicate keys, floats, `NaN` and
Infinity are rejected.

Scope v1 was never effective. Scopes v2, v3, v4, v5 and v6 were superseded
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
deltas must contain exactly the five documentation/owner paths and scope v7
listed by the contract. Scopes v1 through v6 must be absent. Any different
base, path set, parent order or identity blocks effect.

## Accepted closure

I accept:

- `30` unique `AUTH_V7_*` / `GATE_*` actions;
- `82` exact resources;
- `6` closed authority planes;
- `7` normative process definitions;
- `4` exact external GitHub operations;
- resource/process/network/write-derived plane validation with deny precedence.

Declared plane arrays never grant authority. Every action must match its
independently derived plane set, and every plane allowlist must contain every
and only its derived actions.

`AUTH_V7_RUN_SYNTHETIC_PROBES`, `synthetic_probe_suite_v7` and the resource
registry have one exact write set:

- `temporary_probe_roots`;
- `temporary_probe_public_files`;
- `temporary_probe_git_metadata`.

These writes are limited to six distinct fresh roots outside the project under
umask `0077`, followed by cleanup and absence proof.

## Accepted Git process and identity boundary

The only critical executable is:

`/Library/Developer/CommandLineTools/usr/bin/git`

The profile is `m1b-1a-r1-git-execution-surface-v3`. Direct execution, exact
argv/environment/cwd, explicit `--git-dir` and `--work-tree`, config isolation,
disabled hooks/fsmonitor/submodule recursion and
`core.logAllRefUpdates=false` are mandatory.

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
denied. Credential values are never read, stored, published or model-visible.

## Accepted commit side effects

The publication-shaped commit was checked in all six fresh repositories:

- HEAD reflog delta `0`;
- branch reflog delta `0`;
- post-success lockfile count `0`;
- post-success temporary-object count `0`;
- stage-zero index entries unchanged;
- tracked worktree unchanged;
- exact tree and commit object additions only;
- `COMMIT_EDITMSG` SHA-256
  `6904e055384f68fe37fb043599f6ce095cbacf44c27d92037c2a11c37778e45b`.

The future commit may touch only the exact commit message, branch ref/lock,
index lock and bounded index metadata, object database and temporary object
routes, ordinary commit object, and packed-refs/lock resources. Any reflog
delta or additional effect fails closed.

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
object-database write delta `0`, cleanup `6/6`. Repository/candidate code was
not executed.

## Evidence I require

Final evidence path:

`artifacts/m1b/m1b-1a-r1/auth-v7-evidence.json`

It must be strict canonical ASCII JSON with one LF, regular mode `0600`,
`st_nlink=1`, Git-ignored, untracked and physically distinct. It includes
final scope/owner/publication identities, all 139 exact matrix rows, six
sanitized observations, exact observation-hash preimages, commit side effects,
cleanup, closure and validation results.

Absolute paths, private configuration, credentials and raw
repository/private/copyrighted content are forbidden. Historical evidence v1
through v6 must remain byte-identical, mode `0600`, `st_nlink=1`, ignored,
untracked and physically distinct.

## Explicit stop

Validation may use trusted one-shot host validators and exact system Git only.
Repository tests, repository Python, candidate/provider import, parsing,
tokenization, linting, compilation or execution are not authorized. Corpus,
mods, Stellaris, Workshop, launcher, model store, Ollama and real translation
inputs/outputs are not read.

This record ends at:

- `REMEDIATION: READY_FOR_REVIEW`;
- `M1B-1A-R1-AUTH-V7: READY_FOR_OWNER_REVIEW`;
- `R1_REMEDIATION: NOT_AUTHORIZED_UNTIL_V7_MERGE`;
- `NEW_REPOSITORY_CODE_EXECUTION: NOT_AUTHORIZED`;
- `PROVIDER_EXECUTION: NOT_STARTED`;
- `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`;
- `M1B: NOT_EVALUATED`;
- `M1A: BLOCKED`;
- `M2: FORBIDDEN`;
- `PR11: DRAFT`.
