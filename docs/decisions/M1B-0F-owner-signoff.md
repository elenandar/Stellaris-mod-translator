# Owner signoff M1B-0F

- Milestone: `M1B-0F — external owner-freeze admission contract`
- Decision state: `owner_accepted`
- Review state: `OWNER_FREEZE: READY_FOR_REVIEW`
- Operational effect: только после review и merge этого PR в `main`
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
- [machine-readable owner decision](M1B-0F-owner-freeze.json).

Snapshot не содержит self-hash; digest хранится в отдельном owner decision
record. Git SHA и fixture SHA являются provenance/evidence, но не executable
или protocol trust identity. Operational admission этого freeze начинает
действовать только после review и merge records в `main`.

## Exact scope

Разрешён только declarative basis `m1b_1a_preparation_basis_only`. Этот signoff
не разрешает:

- model call, Ollama metadata/probe или изменение provider state;
- official/private corpus, prompt/output либо human scoring;
- complete benchmark, tuning, holdout или feasibility verdict;
- executable implementation manifest, live report schema, prompt/template или
  real candidate profile;
- product CLI, M2, translation, activation или publish.

Следующий возможный этап после merge — отдельное задание
`M1B-1A local synthetic provider preflight`; оно не начато этим решением.

## Preserved blockers

Независимо остаются:

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

`OWNER_DECISION_REQUIRED` снят только для exact owner-freeze identity и scope
этого решения. Он не снимается для будущих live, executable, report, holdout
или feasibility decisions.

## Gate statement

Benchmark не запускался; model observations, human scores и quality verdict
отсутствуют. Поэтому states не продвинулись:

- `M1B: NOT_EVALUATED`;
- `M1A: BLOCKED`;
- `M2: FORBIDDEN`.

До merge итог этого PR может быть только `OWNER_FREEZE: READY_FOR_REVIEW` либо
fail-closed `OWNER_FREEZE: BLOCKED`.
