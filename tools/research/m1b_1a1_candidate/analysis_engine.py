"""Pure deterministic calculations for the frozen M1B analysis policy."""

from fractions import Fraction


ANALYSIS_POLICY_VERSION = "m1b-analysis-policy-v6"
PROTOCOL_VERSION = "m1b-benchmark-contract-v7"
PROTOCOL_GENERATION = 108
REQUEST_SCHEMA = "m1b-1a1-validation-request-v1"

MAX_ANALYSIS_UNITS = 4096
MAX_AGREEMENT_SOURCES = 4096
MAX_RATINGS_PER_SOURCE = 1024
MAX_TOTAL_RATING_PAIRS = 65536
MAX_GATE_STATUSES = 4096
MAX_RESULT_INTEGER_BITS = 4096

AGREEMENT_FLOOR = Fraction(3, 5)
AGREEMENT_MINIMUM_N = 46
CANDIDATE_TAIL_ALPHA = Fraction(1, 120)
CFA_ALPHA = Fraction(1, 60)
CFA_CEILING = Fraction(1, 50)
CFA_MINIMUM_N = 203

_ACTIONS = frozenset(
    {
        "aggregate",
        "agreement",
        "cfa_gate",
        "dimension_gates",
    }
)

_DIMENSIONS = (
    "context_voice_style",
    "literary_russian",
    "meaning_accuracy",
    "schema_atom_stability",
    "terminology_lore",
)

_EDITORIAL_DIMENSIONS = frozenset(
    {
        "context_voice_style",
        "literary_russian",
        "meaning_accuracy",
        "terminology_lore",
    }
)

_STRATA = (
    "dialogue",
    "gender_case",
    "humor_wordplay",
    "lore",
    "mechanics",
    "narrative",
    "typed_atoms",
    "ui",
)

_RISK_CLASSES = frozenset(
    {
        "auto_eligible_candidate",
        "critical_risk",
        "mandatory_human",
    }
)

_DIMENSION_FLOORS = {
    "context_voice_style": Fraction(4, 5),
    "literary_russian": Fraction(4, 5),
    "meaning_accuracy": Fraction(9, 10),
    "schema_atom_stability": Fraction(1, 1),
    "terminology_lore": Fraction(17, 20),
}

_DIMENSION_MINIMUM_N = {
    "context_voice_style": 22,
    "literary_russian": 22,
    "meaning_accuracy": 46,
    "schema_atom_stability": 1,
    "terminology_lore": 30,
}

_AGREEMENT_STATUSES = frozenset(
    {
        "AGREEMENT_APPLICABILITY_DISAGREEMENT",
        "AGREEMENT_INSUFFICIENT_UNITS",
        "AGREEMENT_PASS",
        "AGREEMENT_POINT_BELOW_FLOOR",
        "AGREEMENT_ROBUSTNESS_BELOW_FLOOR",
        "AGREEMENT_UNCERTAINTY_UNDEFINED",
        "AGREEMENT_UNDEFINED_ZERO_EXPECTED_DISAGREEMENT",
    }
)

_CFA_STATUSES = frozenset(
    {
        "CFA_CONFIDENCE_ABOVE_CEILING",
        "CFA_EVENT_OBSERVED",
        "CFA_INSUFFICIENT_UNITS",
        "CFA_PASS",
    }
)


class AnalysisError(Exception):
    """Controlled analysis failure carrying only a closed code."""

    def __init__(self, code):
        self.code = code
        Exception.__init__(self, code)


def _closed_dict(value, fields, code):
    if type(value) is not dict or set(value) != set(fields):
        raise AnalysisError(code)
    return value


def _bounded_int(value, minimum, maximum, code):
    if type(value) is not int or value < minimum or value > maximum:
        raise AnalysisError(code)
    return value


def _bounded_list(value, minimum, maximum, code):
    if type(value) is not list or len(value) < minimum or len(value) > maximum:
        raise AnalysisError(code)
    return value


def _fraction_record(value):
    if value is None:
        return None
    if (
        abs(value.numerator).bit_length() > MAX_RESULT_INTEGER_BITS
        or value.denominator.bit_length() > MAX_RESULT_INTEGER_BITS
    ):
        raise AnalysisError("ANALYSIS_LIMIT_EXCEEDED")
    return {
        "denominator": value.denominator,
        "numerator": value.numerator,
    }


def _empty_matrix():
    return [[Fraction(0, 1) for _ in range(5)] for _ in range(5)]


def _add_matrix(left, right):
    return [
        [left[row][column] + right[row][column] for column in range(5)]
        for row in range(5)
    ]


def _subtract_matrix(left, right):
    return [
        [left[row][column] - right[row][column] for column in range(5)]
        for row in range(5)
    ]


def _weighted_kappa(matrix):
    total = sum(
        (sum(row, Fraction(0, 1)) for row in matrix),
        Fraction(0, 1),
    )
    if total <= 0:
        return None
    row_totals = [sum(row, Fraction(0, 1)) for row in matrix]
    column_totals = [
        sum((matrix[row][column] for row in range(5)), Fraction(0, 1))
        for column in range(5)
    ]
    observed = sum(
        (
            (16 - (row - column) ** 2) * matrix[row][column]
            for row in range(5)
            for column in range(5)
        ),
        Fraction(0, 1),
    )
    expected = sum(
        (
            (16 - (row - column) ** 2)
            * row_totals[row]
            * column_totals[column]
            for row in range(5)
            for column in range(5)
        ),
        Fraction(0, 1),
    )
    numerator = total * observed - expected
    denominator = 16 * total * total - expected
    if denominator == 0:
        return None
    return numerator / denominator


def _source_matrix(raw_source):
    source = _closed_dict(raw_source, ("pairs",), "AGREEMENT_INPUT_INVALID")
    pairs = _bounded_list(
        source["pairs"],
        1,
        MAX_RATINGS_PER_SOURCE,
        "AGREEMENT_INPUT_INVALID",
    )
    counts = [[0 for _ in range(5)] for _ in range(5)]
    for pair in pairs:
        if type(pair) is not list or len(pair) != 2:
            raise AnalysisError("AGREEMENT_INPUT_INVALID")
        first = _bounded_int(pair[0], 0, 4, "AGREEMENT_INPUT_INVALID")
        second = _bounded_int(pair[1], 0, 4, "AGREEMENT_INPUT_INVALID")
        counts[first][second] += 1
    pair_count = len(pairs)
    return [
        [Fraction(counts[row][column], pair_count) for column in range(5)]
        for row in range(5)
    ], pair_count


def _agreement_result(payload):
    value = _closed_dict(
        payload,
        (
            "bilateral_not_applicable_source_count",
            "sources",
            "unilateral_not_applicable_source_count",
        ),
        "PAYLOAD_INVALID",
    )
    sources = _bounded_list(
        value["sources"],
        1,
        MAX_AGREEMENT_SOURCES,
        "AGREEMENT_INPUT_INVALID",
    )
    bilateral_count = _bounded_int(
        value["bilateral_not_applicable_source_count"],
        0,
        MAX_AGREEMENT_SOURCES,
        "AGREEMENT_INPUT_INVALID",
    )
    unilateral_count = _bounded_int(
        value["unilateral_not_applicable_source_count"],
        0,
        MAX_AGREEMENT_SOURCES,
        "AGREEMENT_INPUT_INVALID",
    )
    if len(sources) + bilateral_count + unilateral_count > MAX_AGREEMENT_SOURCES:
        raise AnalysisError("ANALYSIS_LIMIT_EXCEEDED")

    contributions = []
    total_pairs = 0
    matrix = _empty_matrix()
    for raw_source in sources:
        contribution, pair_count = _source_matrix(raw_source)
        total_pairs += pair_count
        if total_pairs > MAX_TOTAL_RATING_PAIRS:
            raise AnalysisError("ANALYSIS_LIMIT_EXCEEDED")
        contributions.append(contribution)
        matrix = _add_matrix(matrix, contribution)

    point = _weighted_kappa(matrix)
    minimum_delete_one = None
    if unilateral_count:
        gate_status = "AGREEMENT_APPLICABILITY_DISAGREEMENT"
    elif len(contributions) < AGREEMENT_MINIMUM_N:
        gate_status = "AGREEMENT_INSUFFICIENT_UNITS"
    elif point is None:
        gate_status = "AGREEMENT_UNDEFINED_ZERO_EXPECTED_DISAGREEMENT"
    elif point < AGREEMENT_FLOOR:
        gate_status = "AGREEMENT_POINT_BELOW_FLOOR"
    else:
        robustness = []
        for contribution in contributions:
            leave_one = _weighted_kappa(_subtract_matrix(matrix, contribution))
            if leave_one is None:
                gate_status = "AGREEMENT_UNCERTAINTY_UNDEFINED"
                break
            robustness.append(leave_one)
        else:
            minimum_delete_one = min(robustness)
            if minimum_delete_one < AGREEMENT_FLOOR:
                gate_status = "AGREEMENT_ROBUSTNESS_BELOW_FLOOR"
            else:
                gate_status = "AGREEMENT_PASS"

    return {
        "applicable_source_count": len(contributions),
        "bilateral_not_applicable_source_count": bilateral_count,
        "gate_status": gate_status,
        "minimum_delete_one_kappa": _fraction_record(minimum_delete_one),
        "point_kappa": _fraction_record(point),
        "rating_pair_count": total_pairs,
        "threshold": _fraction_record(AGREEMENT_FLOOR),
        "unilateral_not_applicable_source_count": unilateral_count,
    }


def _combination(total, selected):
    selected = min(selected, total - selected)
    value = 1
    for index in range(1, selected + 1):
        value = value * (total - selected + index) // index
    return value


def _clopper_pearson_lower_at_least(successes, total, floor):
    if successes <= 0:
        return False
    floor_numerator = floor.numerator
    floor_denominator = floor.denominator
    failure_numerator = floor_denominator - floor_numerator
    denominator = floor_denominator ** total
    threshold_multiplier = CANDIDATE_TAIL_ALPHA.denominator
    threshold_numerator = CANDIDATE_TAIL_ALPHA.numerator * denominator

    combination = _combination(total, successes)
    success_power = floor_numerator ** successes
    failure_power = failure_numerator ** (total - successes)
    tail_numerator = 0
    for count in range(successes, total + 1):
        tail_numerator += combination * success_power * failure_power
        if tail_numerator * threshold_multiplier > threshold_numerator:
            return False
        if count < total:
            combination = combination * (total - count) // (count + 1)
            success_power *= floor_numerator
            failure_power //= failure_numerator
    return tail_numerator * threshold_multiplier <= threshold_numerator


def _dimension_stratum_result(dimension, raw_row):
    row = _closed_dict(
        raw_row,
        (
            "applicable_count",
            "assigned_count",
            "stratum",
            "success_count",
        ),
        "DIMENSION_INPUT_INVALID",
    )
    assigned = _bounded_int(
        row["assigned_count"],
        0,
        MAX_ANALYSIS_UNITS,
        "DIMENSION_INPUT_INVALID",
    )
    applicable = _bounded_int(
        row["applicable_count"],
        0,
        assigned,
        "DIMENSION_INPUT_INVALID",
    )
    successes = _bounded_int(
        row["success_count"],
        0,
        applicable,
        "DIMENSION_INPUT_INVALID",
    )
    if dimension == "schema_atom_stability" and assigned != applicable:
        raise AnalysisError("D1_APPLICABILITY_INVALID")

    floor = _DIMENSION_FLOORS[dimension]
    minimum_n = _DIMENSION_MINIMUM_N[dimension]
    observed_rate = (
        None if applicable == 0 else Fraction(successes, applicable)
    )
    if dimension == "schema_atom_stability":
        confidence_met = None
    elif applicable == 0:
        confidence_met = False
    else:
        confidence_met = _clopper_pearson_lower_at_least(
            successes,
            applicable,
            floor,
        )

    if applicable < minimum_n:
        gate_status = "DIMENSION_INSUFFICIENT_UNITS"
    elif observed_rate < floor:
        gate_status = "DIMENSION_OBSERVED_BELOW_FLOOR"
    elif dimension != "schema_atom_stability" and not confidence_met:
        gate_status = "DIMENSION_CONFIDENCE_BELOW_FLOOR"
    else:
        gate_status = "DIMENSION_STRATUM_PASS"

    return {
        "applicable_count": applicable,
        "assigned_count": assigned,
        "confidence_floor_met": confidence_met,
        "gate_status": gate_status,
        "not_applicable_count": assigned - applicable,
        "observed_rate": _fraction_record(observed_rate),
        "stratum": row["stratum"],
        "success_count": successes,
    }


def _dimension_gates_result(payload):
    value = _closed_dict(payload, ("dimensions",), "PAYLOAD_INVALID")
    dimensions = _bounded_list(
        value["dimensions"],
        len(_DIMENSIONS),
        len(_DIMENSIONS),
        "DIMENSION_INPUT_INVALID",
    )
    if tuple(
        row.get("dimension") if type(row) is dict else None
        for row in dimensions
    ) != _DIMENSIONS:
        raise AnalysisError("DIMENSION_INPUT_INVALID")

    output_dimensions = []
    dimension_statuses = {}
    for expected_dimension, raw_dimension in zip(_DIMENSIONS, dimensions):
        dimension = _closed_dict(
            raw_dimension,
            ("dimension", "strata"),
            "DIMENSION_INPUT_INVALID",
        )
        if dimension["dimension"] != expected_dimension:
            raise AnalysisError("DIMENSION_INPUT_INVALID")
        strata = _bounded_list(
            dimension["strata"],
            len(_STRATA),
            len(_STRATA),
            "DIMENSION_INPUT_INVALID",
        )
        if tuple(
            row.get("stratum") if type(row) is dict else None
            for row in strata
        ) != _STRATA:
            raise AnalysisError("DIMENSION_INPUT_INVALID")

        output_strata = [
            _dimension_stratum_result(expected_dimension, row)
            for row in strata
        ]
        gate_status = (
            "DIMENSION_PASS"
            if all(
                row["gate_status"] == "DIMENSION_STRATUM_PASS"
                for row in output_strata
            )
            else "DIMENSION_FAIL"
        )
        dimension_statuses[expected_dimension] = gate_status
        output_dimensions.append(
            {
                "dimension": expected_dimension,
                "floor": _fraction_record(
                    _DIMENSION_FLOORS[expected_dimension]
                ),
                "gate_status": gate_status,
                "minimum_n": _DIMENSION_MINIMUM_N[expected_dimension],
                "strata": output_strata,
            }
        )

    technical_outcome = (
        "TECHNICAL_GATE_PASS"
        if dimension_statuses["schema_atom_stability"] == "DIMENSION_PASS"
        else "TECHNICAL_GATE_FAIL"
    )
    editorial_outcome = (
        "EDITORIAL_QUALITY_GATES_PASS"
        if all(
            dimension_statuses[dimension] == "DIMENSION_PASS"
            for dimension in _EDITORIAL_DIMENSIONS
        )
        else "EDITORIAL_QUALITY_GATES_FAIL"
    )
    return {
        "dimensions": output_dimensions,
        "editorial_approval": "HUMAN_DECISION_REQUIRED",
        "editorial_quality_outcome": editorial_outcome,
        "technical_outcome": technical_outcome,
    }


def _cfa_gate_result(payload):
    value = _closed_dict(
        payload,
        (
            "event_count",
            "risk_class",
            "source_generation_count",
        ),
        "PAYLOAD_INVALID",
    )
    source_count = _bounded_int(
        value["source_generation_count"],
        0,
        MAX_ANALYSIS_UNITS,
        "CFA_INPUT_INVALID",
    )
    event_count = _bounded_int(
        value["event_count"],
        0,
        source_count,
        "CFA_INPUT_INVALID",
    )
    if type(value["risk_class"]) is not str or value["risk_class"] not in _RISK_CLASSES:
        raise AnalysisError("CFA_INPUT_INVALID")

    confidence_met = (
        event_count == 0
        and (1 - CFA_CEILING) ** source_count <= CFA_ALPHA
    )
    if event_count:
        gate_status = "CFA_EVENT_OBSERVED"
    elif source_count < CFA_MINIMUM_N:
        gate_status = "CFA_INSUFFICIENT_UNITS"
    elif not confidence_met:
        gate_status = "CFA_CONFIDENCE_ABOVE_CEILING"
    else:
        gate_status = "CFA_PASS"
    return {
        "confidence_ceiling_met": confidence_met,
        "event_count": event_count,
        "gate_status": gate_status,
        "minimum_n": CFA_MINIMUM_N,
        "risk_class": value["risk_class"],
        "source_generation_count": source_count,
        "upper_bound_ceiling": _fraction_record(CFA_CEILING),
    }


def _status_list(value, allowed, code):
    statuses = _bounded_list(value, 1, MAX_GATE_STATUSES, code)
    if any(type(status) is not str or status not in allowed for status in statuses):
        raise AnalysisError(code)
    return statuses


def _aggregate_result(payload):
    value = _closed_dict(
        payload,
        (
            "agreement_statuses",
            "approved_critical_finding_count",
            "approved_d1_defect_count",
            "cfa_statuses",
            "dimension_statuses",
            "editorially_approved_count",
            "mandatory_human_evidence_missing_count",
            "result_count",
            "technical_safe_count",
        ),
        "PAYLOAD_INVALID",
    )
    agreement_statuses = _status_list(
        value["agreement_statuses"],
        _AGREEMENT_STATUSES,
        "AGGREGATE_INPUT_INVALID",
    )
    cfa_statuses = _status_list(
        value["cfa_statuses"],
        _CFA_STATUSES,
        "AGGREGATE_INPUT_INVALID",
    )
    dimension_rows = _bounded_list(
        value["dimension_statuses"],
        len(_DIMENSIONS),
        len(_DIMENSIONS),
        "AGGREGATE_INPUT_INVALID",
    )
    if tuple(
        row.get("dimension") if type(row) is dict else None
        for row in dimension_rows
    ) != _DIMENSIONS:
        raise AnalysisError("AGGREGATE_INPUT_INVALID")
    dimension_statuses = {}
    for expected_dimension, raw_row in zip(_DIMENSIONS, dimension_rows):
        row = _closed_dict(
            raw_row,
            ("dimension", "status"),
            "AGGREGATE_INPUT_INVALID",
        )
        if (
            row["dimension"] != expected_dimension
            or row["status"] not in ("DIMENSION_FAIL", "DIMENSION_PASS")
        ):
            raise AnalysisError("AGGREGATE_INPUT_INVALID")
        dimension_statuses[expected_dimension] = row["status"]

    result_count = _bounded_int(
        value["result_count"],
        1,
        MAX_ANALYSIS_UNITS,
        "AGGREGATE_INPUT_INVALID",
    )
    technical_safe_count = _bounded_int(
        value["technical_safe_count"],
        0,
        result_count,
        "AGGREGATE_INPUT_INVALID",
    )
    approved_count = _bounded_int(
        value["editorially_approved_count"],
        0,
        result_count,
        "AGGREGATE_INPUT_INVALID",
    )
    if approved_count > technical_safe_count:
        raise AnalysisError("AGGREGATE_INPUT_INVALID")
    d1_defect_count = _bounded_int(
        value["approved_d1_defect_count"],
        0,
        approved_count,
        "AGGREGATE_INPUT_INVALID",
    )
    approved_critical_count = _bounded_int(
        value["approved_critical_finding_count"],
        0,
        approved_count,
        "AGGREGATE_INPUT_INVALID",
    )
    missing_human_count = _bounded_int(
        value["mandatory_human_evidence_missing_count"],
        0,
        result_count,
        "AGGREGATE_INPUT_INVALID",
    )

    failed_agreement_count = sum(
        status != "AGREEMENT_PASS" for status in agreement_statuses
    )
    failed_cfa_count = sum(status != "CFA_PASS" for status in cfa_statuses)
    failed_dimension_count = sum(
        status != "DIMENSION_PASS" for status in dimension_statuses.values()
    )
    technical_pass = (
        dimension_statuses["schema_atom_stability"] == "DIMENSION_PASS"
        and d1_defect_count == 0
        and technical_safe_count == result_count
    )
    editorial_pass = (
        all(
            dimension_statuses[dimension] == "DIMENSION_PASS"
            for dimension in _EDITORIAL_DIMENSIONS
        )
        and failed_agreement_count == 0
        and failed_cfa_count == 0
        and d1_defect_count == 0
        and approved_critical_count == 0
        and missing_human_count == 0
    )
    aggregate_pass = technical_pass and editorial_pass

    return {
        "aggregate_status": (
            "AGGREGATE_GATES_PASS"
            if aggregate_pass
            else "AGGREGATE_GATES_FAIL"
        ),
        "editorial_approval": "HUMAN_DECISION_REQUIRED",
        "editorial_gate_status": (
            "EDITORIAL_GATES_PASS"
            if editorial_pass
            else "EDITORIAL_GATES_FAIL"
        ),
        "gate_counts": {
            "agreement_failed_count": failed_agreement_count,
            "agreement_scope_count": len(agreement_statuses),
            "cfa_failed_count": failed_cfa_count,
            "cfa_scope_count": len(cfa_statuses),
            "dimension_failed_count": failed_dimension_count,
            "dimension_scope_count": len(dimension_statuses),
        },
        "result_counts": {
            "approved_critical_finding_count": approved_critical_count,
            "approved_d1_defect_count": d1_defect_count,
            "editorially_approved_count": approved_count,
            "mandatory_human_evidence_missing_count": missing_human_count,
            "result_count": result_count,
            "technical_safe_count": technical_safe_count,
        },
        "technical_gate_status": (
            "TECHNICAL_GATES_PASS"
            if technical_pass
            else "TECHNICAL_GATES_FAIL"
        ),
    }


def _success(action, result):
    return {
        "action": action,
        "analysis_policy_version": ANALYSIS_POLICY_VERSION,
        "protocol_generation": PROTOCOL_GENERATION,
        "result": result,
        "status": "ok",
    }


def _failure(action, code):
    return {
        "action": action,
        "analysis_policy_version": ANALYSIS_POLICY_VERSION,
        "code": code,
        "protocol_generation": PROTOCOL_GENERATION,
        "status": "error",
    }


def analyze_validated_request(request):
    """Analyze one closed, already-validated request without external reads."""

    safe_action = "unrecognized"
    try:
        root = _closed_dict(
            request,
            (
                "action",
                "payload",
                "protocol_generation",
                "protocol_version",
                "request_schema",
            ),
            "REQUEST_INVALID",
        )
        action = root["action"]
        if type(action) is not str or action not in _ACTIONS:
            raise AnalysisError("REQUEST_INVALID")
        safe_action = action
        if (
            root["request_schema"] != REQUEST_SCHEMA
            or root["protocol_version"] != PROTOCOL_VERSION
            or type(root["protocol_generation"]) is not int
            or root["protocol_generation"] != PROTOCOL_GENERATION
        ):
            raise AnalysisError("REQUEST_IDENTITY_MISMATCH")
        if type(root["payload"]) is not dict:
            raise AnalysisError("PAYLOAD_INVALID")

        if action == "agreement":
            result = _agreement_result(root["payload"])
        elif action == "dimension_gates":
            result = _dimension_gates_result(root["payload"])
        elif action == "cfa_gate":
            result = _cfa_gate_result(root["payload"])
        else:
            result = _aggregate_result(root["payload"])
        return _success(action, result)
    except AnalysisError as error:
        return _failure(safe_action, error.code)
    except Exception:
        return _failure(safe_action, "UNEXPECTED_FAILURE")
