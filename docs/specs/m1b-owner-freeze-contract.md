# Внешний owner-freeze contract M1B-0F

- Milestone: `M1B-0F — external owner-freeze admission contract`
- Snapshot schema: `m1b-owner-freeze-registry-snapshot-v1`
- Owner record schema: `m1b-owner-freeze-decision-v1`
- Acceptance: exact declarative proposal v7/generation 108 принят владельцем
  только как основа подготовки будущего M1B-1A
- Operational effect: только после review и merge owner-freeze PR в `main`
- Gate state: `M1B: NOT_EVALUATED`; `M1A: BLOCKED`; `M2: FORBIDDEN`

Этот contract создаёт отдельную внешнюю фиксацию решения владельца. Он не
изменяет historical M1B-0 registry entries: все 17 entries внутри benchmark
report/fixture и trusted proposal validator остаются `proposed`. Новый
`owner_accepted` относится атомарно к отдельному registry snapshot, который
связывает их exact identities.

Contract не является benchmark report schema, executable implementation
manifest, prompt/template, model profile, provider probe, live admission или
feasibility verdict. Успешная offline-проверка на ветке PR означает только, что
публичные records согласованы и готовы к review.

## Trust boundary

Verifier принимает два явных owner-controlled regular-file path: immutable
registry snapshot и отдельный owner decision record. Default path, stdin,
directory/environment/home discovery, report mode и fixture mode отсутствуют.

Owner decision record является внешней точкой принятия: он хранит canonical
digest snapshot и exact scope решения. Snapshot не хранит собственный digest.
Benchmark report, fixture, Git commit, fixture SHA-256, пересчитанный самим
report hash и self-reported executable identity не являются trust root.
Review и merge дают authority выбранному record; Git SHA остаётся только
provenance.

Offline verifier независимо bind-ит expected proposal identities и проверяет
consistency records. Он не доказывает свои executable bytes, Python runtime,
imports или invocation state и не выдаёт full decision admission. Поэтому
`EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN` остаётся live blocker.

## Registry snapshot schema

Snapshot находится в
[`registry/m1b/owner-freeze-v7-g108.json`](../../registry/m1b/owner-freeze-v7-g108.json)
и содержит ровно семь closed root fields:

| Field | Exact rule |
|---|---|
| `schema_version` | `m1b-owner-freeze-registry-snapshot-v1` |
| `framing` | `m1b-owner-freeze-registry-snapshot-sha256-v1` |
| `protocol_version` | `m1b-benchmark-contract-v7` |
| `protocol_generation` | integer `108`; `bool` запрещён |
| `definition_bundle_sha256` | `50f51b3cf9be042ebc310d1a6c57791dd31a43362778798455d7ea9678c31e06` |
| `acceptance_state` | `owner_accepted` |
| `components` | ровно 17 canonical rows |

Каждая component row имеет только `kind`, `version`, `generation` и
`component_sha256`. Rows уникальны и расположены в строгом raw-ASCII порядке
`(kind, version)`. Reordering отклоняется до admission, даже если сортировка
внутри старого bundle framing дала бы тот же legacy digest.

Snapshot не содержит definition payload, self-hash, report field, fixture
identity, path, Git SHA, prompt/model/corpus bytes или executable claim.

### Exact component identities

| kind | version | generation | component SHA-256 |
|---|---|---:|---|
| `analysis_policy` | `m1b-analysis-policy-v6` | 108 | `53fc6ba8bebeb7a872c937b2e5096b9bbee04ff01d2a66d1815ac38365a6ac74` |
| `benchmark_contract` | `m1b-benchmark-contract-v7` | 108 | `4d5a1d1b343cbed19bac4f9d6e58101975a62c2e30d9f6eaa2730b37e8a59532` |
| `candidate_profile.deepseek_r1_32b` | `m1b-primary-common-profile-v1` | 202 | `0a9aecddf4fb4dc4a090434c1b5b7f66cfe69b64392a527bf3c5f5d95b24c3a3` |
| `candidate_profile.glm_4_7_flash` | `m1b-primary-common-profile-v1` | 202 | `1ac428581d95f9862e956da9def260ac6b0de12d960bfb80cf0c4df38d63ad8e` |
| `candidate_profile.gpt_oss_20b` | `m1b-primary-common-profile-v1` | 202 | `2651960755cd898064f48cf5f948c4b00976104b5bcfe54a62fe5bea3ac53933` |
| `context_limit_policy` | `m1b-context-limit-policy-v2` | 105 | `c5e60400a7783c0635d34019d0cb32a3506080297e6f7bae82ce21e4457cc0e5` |
| `corpus_policy` | `m1b-corpus-policy-v3` | 105 | `83943902f422a4ebc00e4e3abb150f7f27496ff71a63b76c33b96eaa84a30ee4` |
| `generation_policy` | `m1b-generation-policy-v2` | 105 | `a9fc7d94a890491945e141fb1e5eefd591d29200220d410991cc9fa4c955b7ce` |
| `implementation_identity_policy` | `m1b-implementation-identity-policy-v2` | 108 | `826d976613f44657c5a2ae9299d3cc80ad21751eb7298989a24653d0849de784` |
| `measurement_policy` | `m1b-measurement-policy-v4` | 106 | `194d87ef56600b13d7171ed8cd54f89acabdf42e1fc51eb3bdecf80b2c53b549` |
| `output_schema` | `m1b-synthetic-output-v4` | 105 | `1be06166d50a33934c40f20916e28db70ce161cb7689defba924a826cb79afd7` |
| `prompt_policy` | `m1b-synthetic-prompt-policy-v1` | 101 | `54e929fd64cab6e20683f2f18ac4408ff30909b7ecff38674fd59395c523859d` |
| `quality_rubric` | `m1b-quality-rubric-v6` | 106 | `220a56232b672ffbe215ee18d067a5a279bbacf2596d3993aac1d2a71eb6f978` |
| `randomization_blinding_policy` | `m1b-randomization-blinding-policy-v3` | 105 | `ce8ea00e77c5650d7e6dc4f105f55c084a90dda6e8f366ecfffd18a336781f34` |
| `retention_leakage_policy` | `m1b-retention-leakage-policy-v1` | 101 | `a13f2b1c342a60dff0c341715708432a77b2fc34354d630b6e50807e4aacb13b` |
| `split_policy` | `m1b-split-policy-v5` | 108 | `16fe20df047eed035507f62f2887ad39746da218babf12c23d4219b0fd8c3ef6` |
| `validator_policy` | `m1b-validator-policy-v7` | 108 | `a3f6399c76d49a31eb9cf542c2850185d23e5f4d53b48ebc010f580b38804201` |

## Canonical registry-snapshot digest

Framing ID — `m1b-owner-freeze-registry-snapshot-sha256-v1`. Для ASCII string
определено `S(x) = u32be(len(ASCII(x))) || ASCII(x)`. Digest вычисляется так:

```text
SHA-256(
  ASCII("stellaris-m1b-owner-freeze-registry-snapshot-v1") || NUL ||
  S(schema_version) ||
  S(framing) ||
  S(protocol_version) ||
  u64be(protocol_generation) ||
  raw32(definition_bundle_sha256) ||
  S(acceptance_state) ||
  u32be(component_count) ||
  for each presented canonical component row:
    S(kind) ||
    S(version) ||
    u64be(generation) ||
    raw32(component_sha256)
)
```

Ни string terminator, ни JSON whitespace/key order, ни path/timestamp/locale в
framing не входят. Перед hash принимаются только closed typed values и exact
canonical row order. Для snapshot v7/g108 canonical digest равен:

```text
df84871be332ee52c315d0c0cc1a7a0046251352a2a0131382b5cb994cffcb58
```

Digest защищает protocol version/generation, old definition bundle identity,
snapshot-level `acceptance_state`, количество rows и каждую exact строку,
включая generation, которую старый component/bundle digest не защищал.

## Owner decision record

Отдельный machine-readable record находится в
[`docs/decisions/M1B-0F-owner-freeze.json`](../decisions/M1B-0F-owner-freeze.json).
Его root closed schema — `m1b-owner-freeze-decision-v1`. Record повторно
связывает exact protocol/generation/bundle, snapshot schema/framing/digest и
component count, а также требует одновременно:

- `acceptance_state=owner_accepted` и
  `acceptance_scope=m1b_1a_preparation_basis_only`;
- `owner_delegation=explicit`;
- effect только `after_review_and_merge_to_main`;
- следующий возможный отдельный этап
  `m1b_1a_local_synthetic_provider_preflight`;
- `model_calls_authorized=false`, `private_corpus_authorized=false` и
  `complete_benchmark_authorized=false`;
- `complete_benchmark_schema_v4=PARTIAL_REPORT_CANNOT_BE_COMPLETE`;
- отсутствие `frozen_prompt_bytes`, `frozen_template_bytes` и
  `real_candidate_identities`;
- exact gates `m1b_state=not_evaluated`, `m1a_state=blocked`,
  `m2_state=forbidden`;
- полный ordered список шести независимых live blockers.

Удаление blocker, расширение scope, смена gate, разрешение model/private/live
действия или coherent подмена snapshot вместе с report/fixture acceptance
делают record недопустимым.

Все три authorization fields имеют exact JSON boolean type. Integer `0` не
равен `false` для schema admission и отклоняется.

## Strict offline verification

[`m1b_owner_freeze.py`](../../tools/research/m1b_owner_freeze.py) — отдельный
Python 3.9 standard-library verifier и не импортирует benchmark validator.
Каждый input отдельно ограничен `64 KiB`. Reader использует explicit open с
no-follow, non-blocking и close-on-exec там, где ОС предоставляет flags, принимает только
regular file с одной hard link и требует неизменность descriptor identity,
size и timestamps на протяжении bounded read.

JSON обязан быть strict UTF-8 без duplicate keys, lone surrogate, float,
NaN/Infinity или integer вне signed 64-bit lexical range. Все objects closed;
integer fields требуют exact `int`, поэтому `bool` не принимается.

Verifier независимо пересчитывает legacy bundle из предъявленных 17 component
identities, сравнивает exact allowlist, проверяет snapshot digest против
отдельного owner record и возвращает только compact `status`, controlled
`codes` и safe aggregate `counts`. Controlled failure не выводит input, path,
record content, case ID, numeric token, exception text или traceback; stderr
остаётся пустым.

```sh
python3 tools/research/m1b_owner_freeze.py verify \
  registry/m1b/owner-freeze-v7-g108.json \
  docs/decisions/M1B-0F-owner-freeze.json
```

Success здесь означает byte-valid owner-freeze evidence. Он не снимает ни один
live blocker и не создаёт benchmark admission.

## Adversarial evidence

Отдельная untrusted table в
[`fixtures/m1b/owner-freeze/cases.json`](../../fixtures/m1b/owner-freeze/cases.json)
покрывает positive exact record и fail-closed drift/add/remove/duplicate/order/
field/self-hash/report/fixture cases. Invalid UTF-8, duplicate JSON keys,
oversize, float/nonfinite, lone-surrogate и signed-integer boundaries создаются
тестом как exact bytes.

Fixture materializer существует только в test module. Production verifier не
имеет fixture/report command и не может получить acceptance из этих объектов.
Historical `fixtures/m1b/contract-cases.json` остаётся byte-identical: его 173
cases и все 17 `proposed` entries не меняются.

## Preserved blockers and next gate

Owner-freeze не снимает:

- `EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN`;
- `CONTEXT_LIMIT_BINDING_UNPROVEN`;
- `PROVIDER_PERSISTENCE_UNPROVEN`;
- `RESIDENCY_UNPROVEN`;
- `OUTPUT_LIMIT_BINDING_UNPROVEN`;
- `LIFECYCLE_STATE_UNPROVEN`;
- отсутствие frozen prompt/template bytes;
- отсутствие real candidate identities;
- запрет complete benchmark в document schema v4;
- `M1B: NOT_EVALUATED`;
- `M1A: BLOCKED`;
- `M2: FORBIDDEN`.

`OWNER_DECISION_REQUIRED` разрешён только для exact declarative freeze,
описанного этим record. Любой последующий prompt/profile/provider/live/holdout,
report-schema, executable-TCB или feasibility owner decision остаётся отдельным
gate.

После review и merge этого PR следующий возможный шаг — новое отдельное задание
`M1B-1A local synthetic provider preflight`. Текущий contract не запускает его.
