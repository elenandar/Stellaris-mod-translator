"""Bounded in-memory materialization for explicit inert synthetic cases."""

import copy
import json
import re


MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_PATCHES = 256
MAX_CUMULATIVE_MATERIALIZATION_BYTES = 16 * 1024 * 1024
MAX_CONTAINER_DEPTH = 64
MAX_PATH_COMPONENTS = 64

_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_CASE_FIELDS = frozenset(("base", "expected", "id", "patches"))
_EXPECTED_FIELDS = frozenset(("codes", "status"))
_SIGNED_64_MIN = -(1 << 63)
_SIGNED_64_MAX = (1 << 63) - 1

__all__ = ("MaterializationError", "materialize_case")


class MaterializationError(Exception):
    """A controlled materialization failure containing only an allowlisted code."""

    __slots__ = ("code",)

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _fail(code):
    raise MaterializationError(code)


def _measure_string(value, remaining, oversize_code):
    size = 2
    for character in value:
        codepoint = ord(character)
        if 0xD800 <= codepoint <= 0xDFFF:
            _fail("FIXTURE_INVALID")
        if character in ('"', "\\"):
            size += 2
        elif codepoint <= 0x1F:
            size += 2 if character in "\b\f\n\r\t" else 6
        elif codepoint <= 0x7F:
            size += 1
        elif codepoint <= 0xFFFF:
            size += 6
        else:
            size += 12
        if size > remaining:
            _fail(oversize_code)
    return size


def _measure_json_tree(value, limit, oversize_code):
    stack = [(value, 0)]
    mutable_ids = set()
    size = 0
    while stack:
        current, depth = stack.pop()
        current_type = type(current)
        if current is None:
            size += 4
        elif current_type is bool:
            size += 4 if current else 5
        elif current_type is str:
            size += _measure_string(current, limit - size, oversize_code)
        elif current_type is int:
            if current < _SIGNED_64_MIN or current > _SIGNED_64_MAX:
                _fail("FIXTURE_INVALID")
            size += len(str(current))
        elif current_type in (dict, list):
            if depth >= MAX_CONTAINER_DEPTH:
                _fail("FIXTURE_INVALID")
            identity = id(current)
            if identity in mutable_ids:
                _fail("FIXTURE_INVALID")
            mutable_ids.add(identity)
            size += 2
            if current_type is dict:
                size += max(0, len(current) - 1) + len(current)
                for key, child in current.items():
                    if type(key) is not str:
                        _fail("FIXTURE_INVALID")
                    size += _measure_string(key, limit - size, oversize_code)
                    stack.append((child, depth + 1))
            else:
                size += max(0, len(current) - 1)
                for child in current:
                    stack.append((child, depth + 1))
        else:
            _fail("FIXTURE_INVALID")
        if size > limit:
            _fail(oversize_code)
    return size


def _encode(value, oversize_code):
    measured = _measure_json_tree(value, MAX_INPUT_BYTES, oversize_code)
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (OverflowError, RecursionError, TypeError, ValueError):
        _fail("FIXTURE_INVALID")
    if len(encoded) != measured:
        _fail("FIXTURE_INVALID")
    return encoded


def _require_exact_object(value, fields):
    if type(value) is not dict or set(value) != fields:
        _fail("FIXTURE_INVALID")
    return value


def _require_path(value):
    if type(value) is not list or not value or len(value) > MAX_PATH_COMPONENTS:
        _fail("FIXTURE_INVALID")
    for component in value:
        component_type = type(component)
        if component_type is str:
            if not component:
                _fail("FIXTURE_INVALID")
        elif component_type is int:
            if component < 0:
                _fail("FIXTURE_INVALID")
        else:
            _fail("FIXTURE_INVALID")
    return value


def _require_expected(value):
    expected = _require_exact_object(value, _EXPECTED_FIELDS)
    codes = expected["codes"]
    status = expected["status"]
    if type(codes) is not list or status not in ("error", "ok"):
        _fail("FIXTURE_INVALID")
    if any(type(code) is not str or _CODE.fullmatch(code) is None for code in codes):
        _fail("FIXTURE_INVALID")
    if len(codes) != len(set(codes)):
        _fail("FIXTURE_INVALID")
    if (status == "ok" and codes) or (status == "error" and len(codes) != 1):
        _fail("FIXTURE_INVALID")


def _require_patch(value):
    if type(value) is not dict:
        _fail("FIXTURE_INVALID")
    operation = value.get("operation")
    if operation in ("append", "set"):
        patch = _require_exact_object(
            value, frozenset(("operation", "target", "value"))
        )
        _require_path(patch["target"])
    elif operation == "copy_append":
        patch = _require_exact_object(
            value, frozenset(("operation", "source", "target"))
        )
        _require_path(patch["source"])
        _require_path(patch["target"])
    elif operation == "delete":
        patch = _require_exact_object(value, frozenset(("operation", "target")))
        _require_path(patch["target"])
    else:
        _fail("FIXTURE_INVALID")
    return patch


def _require_case(value):
    _encode(value, "INPUT_SIZE_LIMIT")
    case = _require_exact_object(value, _CASE_FIELDS)
    if type(case["base"]) is not dict:
        _fail("FIXTURE_INVALID")
    case_id = case["id"]
    if type(case_id) is not str or _CASE_ID.fullmatch(case_id) is None:
        _fail("FIXTURE_INVALID")
    _require_expected(case["expected"])
    patches = case["patches"]
    if type(patches) is not list:
        _fail("FIXTURE_INVALID")
    if len(patches) > MAX_PATCHES:
        _fail("MATERIALIZATION_WORK_LIMIT")
    for patch in patches:
        _require_patch(patch)
    return case


def _locate(root, path):
    current = root
    for component in path:
        if type(current) is dict and type(component) is str:
            if component not in current:
                _fail("FIXTURE_INVALID")
            current = current[component]
        elif type(current) is list and type(component) is int:
            if component >= len(current):
                _fail("FIXTURE_INVALID")
            current = current[component]
        else:
            _fail("FIXTURE_INVALID")
    return current


def _locate_parent(root, path):
    parent = root if len(path) == 1 else _locate(root, path[:-1])
    return parent, path[-1]


def _set_value(root, path, value):
    parent, leaf = _locate_parent(root, path)
    if type(parent) is dict and type(leaf) is str:
        parent[leaf] = copy.deepcopy(value)
    elif type(parent) is list and type(leaf) is int and leaf < len(parent):
        parent[leaf] = copy.deepcopy(value)
    else:
        _fail("FIXTURE_INVALID")


def _delete_value(root, path):
    parent, leaf = _locate_parent(root, path)
    if type(parent) is dict and type(leaf) is str and leaf in parent:
        del parent[leaf]
    elif type(parent) is list and type(leaf) is int and leaf < len(parent):
        del parent[leaf]
    else:
        _fail("FIXTURE_INVALID")


def _consume_materialization(document, consumed):
    if (
        consumed
        > MAX_CUMULATIVE_MATERIALIZATION_BYTES - MAX_INPUT_BYTES
    ):
        _fail("MATERIALIZATION_WORK_LIMIT")
    encoded = _encode(document, "INPUT_SIZE_LIMIT")
    if len(encoded) > MAX_CUMULATIVE_MATERIALIZATION_BYTES - consumed:
        _fail("MATERIALIZATION_WORK_LIMIT")
    return encoded, consumed + len(encoded)


def materialize_case(case):
    """Return canonical in-memory bytes for one explicit inert case."""

    checked = _require_case(case)
    document = copy.deepcopy(checked["base"])
    encoded, consumed = _consume_materialization(document, 0)
    for patch in checked["patches"]:
        operation = patch["operation"]
        candidate = copy.deepcopy(document)
        if operation == "set":
            _set_value(candidate, patch["target"], patch["value"])
        elif operation == "delete":
            _delete_value(candidate, patch["target"])
        elif operation == "append":
            target = _locate(candidate, patch["target"])
            if type(target) is not list:
                _fail("FIXTURE_INVALID")
            target.append(copy.deepcopy(patch["value"]))
        else:
            source = _locate(document, patch["source"])
            target = _locate(candidate, patch["target"])
            if type(target) is not list:
                _fail("FIXTURE_INVALID")
            target.append(copy.deepcopy(source))
        encoded, consumed = _consume_materialization(candidate, consumed)
        document = candidate
    return encoded
