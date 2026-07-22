# Owner signoff M1B-0F

- Milestone: `M1B-0F — external owner-freeze admission contract`
- Decision state: `owner_accepted`
- Review state: `OWNER_FREEZE: ACCEPTED`
- Merge provenance: [PR #6](https://github.com/elenandar/Stellaris-mod-translator/pull/6) head `a73555f679b057a07d31a094a38d61b2803e478c`, merged в `main` как `9f854da7501dec6ec9afc5e4bf71dfaa1ea9ecbc`
- Post-merge hardening state: `STABLE_READ_HARDENING: ACCEPTED`; [PR #7](https://github.com/elenandar/Stellaris-mod-translator/pull/7) head `4c849f528a468545f7c5d39d6c7fddf5b23a066d` merged as `424a4e45066cfbff3f9b3da2ec2cf6ad62a643fb`
- Operational effect: exact accepted declarative scope действует с merge PR #6
- Next stage: `M1B-1A0 CONTRACT: READY_FOR_REVIEW`; executable TCB admission не выдан
- Post-contract authorization: `M1B-1A1-AUTH: OWNER_REVIEW_REQUIRED`
- Candidate construction: `CANDIDATE CONSTRUCTION: NOT_AUTHORIZED`
- Executable owner gate: `EXECUTABLE_TCB_OWNER_DECISION_REQUIRED: PRESERVED`
- Provider-source gate: `PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN: PRESERVED`
- M1B verdict: `M1B: NOT_EVALUATED`
- Dependent gates: `M1A: BLOCKED`; `M2: FORBIDDEN`

## Решение владельца

Владелец явно делегировал фиксацию решения в задании M1B-0F. Exact declarative
proposal `m1b-benchmark-contract-v7`, protocol generation `108`, definition
bundle
`50f51b3cf9be042ebc310d1a6c57791dd31a43362778798455d7ea9678c31e06`
принят как основа подготовки будущего M1B-1A.

Принятие атомарно относится к внешнему snapshot schema
`m1b-owner-freeze-registry-snapshot-v1` с 17 exact component identities и
snapshot-level `acceptance_state=owner_accepted`. Existing benchmark-report,
fixture и embedded validator entries остаются историческими `proposed`; они не
переписываются и не становятся источником acceptance.

Canonical registry-snapshot SHA-256:

```text
df84871be332ee52c315d0c0cc1a7a0046251352a2a0131382b5cb994cffcb58
```

Связанные records:

- [external owner-freeze contract](../specs/m1b-owner-freeze-contract.md);
- [immutable registry snapshot](../../registry/m1b/owner-freeze-v7-g108.json);
- [machine-readable owner decision](M1B-0F-owner-freeze.json);
- [separate M1B-1A0 executable/TCB contract](../specs/m1b-offline-executable-tcb-admission-contract.md).

Snapshot не содержит self-hash; digest хранится в отдельном owner decision
record. Git SHA и fixture SHA являются provenance/evidence, но не executable
или protocol trust identity. Accepted declarative freeze действует только с
merge PR #6 в `main`; post-merge hardening не изменяет identity или scope.

## Exact scope

Разрешён только declarative basis `m1b_1a_preparation_basis_only`. Этот signoff
не разрешает:

- model call, Ollama metadata/probe или изменение provider state;
- official/private corpus, prompt/output либо human scoring;
- complete benchmark, tuning, holdout или feasibility verdict;
- executable implementation manifest, live report schema, prompt/template или
  real candidate profile;
- product CLI, M2, translation, activation или publish.

Accepted machine record сохраняет exact next-stage value
`m1b_1a_local_synthetic_provider_preflight`. Его первый отдельно gated
contract-only этап — `M1B-1A0 — Offline executable/TCB admission contract`;
после merge M1B-0F-H1 он начат отдельным заданием и сейчас имеет только state
`M1B-1A0 CONTRACT: READY_FOR_REVIEW`. Новый contract не расширяет scope этого
owner signoff, не принимает executable/runtime bytes и не разрешает provider
execution. Принятое declarative M1B-0F решение не является executable owner
decision и не снимает `EXECUTABLE_TCB_OWNER_DECISION_REQUIRED` либо
`PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN`.
Stored next-stage value — umbrella label declarative preparation scope, а не
owner authorization для M1B-1A1 или создания candidate.

## Preserved blockers

Независимо остаются:

- `EXECUTABLE_TCB_OWNER_DECISION_REQUIRED`;
- `PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN`;
- `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN`;
- `CONTEXT_LIMIT_BINDING_UNPROVEN`;
- `PROVIDER_PERSISTENCE_UNPROVEN`;
- `RESIDENCY_UNPROVEN`;
- `OUTPUT_LIMIT_BINDING_UNPROVEN`;
- `LIFECYCLE_STATE_UNPROVEN`;
- frozen prompt bytes отсутствуют;
- frozen template bytes отсутствуют;
- real candidate identities отсутствуют;
- document schema v4 отклоняет complete benchmark кодом
  `PARTIAL_REPORT_CANNOT_BE_COMPLETE`.

Исторический `OWNER_DECISION_REQUIRED` снят только для exact declarative
owner-freeze identity и scope этого решения. Отдельный exact
`EXECUTABLE_TCB_OWNER_DECISION_REQUIRED` не снят. Он сохраняется для будущих
executable identities; live, report, holdout и feasibility decisions также
остаются отдельными gates.

## Gate statement

Benchmark не запускался; model observations, human scores и quality verdict
отсутствуют. Поэтому states не продвинулись:

- `M1B: NOT_EVALUATED`;
- `M1A: BLOCKED`;
- `M2: FORBIDDEN`.

Post-merge state — `OWNER_FREEZE: ACCEPTED`. M1B-0F-H1 не пересматривает это
решение: `STABLE_READ_HARDENING: ACCEPTED`. M1B-1A0 также не пересматривает
owner-freeze: `EXECUTABLE_TCB_ADMISSION: NOT_GRANTED`,
`M1B-1A1-AUTH: OWNER_REVIEW_REQUIRED`,
`CANDIDATE CONSTRUCTION: NOT_AUTHORIZED`,
`EXECUTABLE_TCB_OWNER_DECISION_REQUIRED: PRESERVED`,
`PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN: PRESERVED`,
`EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN: PRESERVED`,
`M1B-1A PROVIDER EXECUTION: NOT_STARTED`.

Review и merge M1B-1A0 фиксируют только contract и не выдают owner authorization
на создание candidate. После merge доступен только отдельный
`M1B-1A1-AUTH` со state `OWNER_REVIEW_REQUIRED`; до его отдельного явного
принятия `CANDIDATE CONSTRUCTION: NOT_AUTHORIZED`.

M1B-1A1-AUTH сам не создаёт executable files или real candidate
manifest/envelope, не запускает interpreter/provider, не создаёт operational
`owner_accepted` admission и не снимает
`EXECUTABLE_TCB_OWNER_DECISION_REQUIRED`. Он должен exact перечислить
разрешённые repository paths для ролей `analysis_engine`, `contract_validator`,
`provider_request_harness`, `synthetic_fixture_materializer`, отделить
read-only inputs от разрешённых write outputs и запретить любые не перечисленные
reads/writes, execution, provider/Ollama/model action, private corpus и
benchmark.

Только после отдельного explicit owner acceptance M1B-1A1-AUTH отдельный
`M1B-1A1` может создать proposed four-role candidate bytes и exact offline
evidence без acceptance или execution. M1B-1A1 не может принять созданные
identities; отдельный `M1B-1A2` рассматривает owner-controlled решение только
над уже известными exact identities. Даже M1B-1A2 не разрешает Ollama probe,
provider/model call, private corpus или benchmark: для исполнения нужен ещё
один явный gate.
