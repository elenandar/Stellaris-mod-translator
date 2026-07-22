#!/usr/bin/env python3
"""Offline synthetic-conformance verifier for the M1B executable TCB contract.

The verifier consumes only explicitly named repository records beneath an
explicit repository root.  It never imports or executes manifest-listed
files.  Success means that the public synthetic records conform to this
contract; it is not operational admission, executable identity proof, or
authority to contact a provider.
"""

from __future__ import annotations

import hashlib
import json
import errno
import os
import re
import stat
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple


MAX_JSON_INPUT_BYTES = 256 * 1024
MAX_EXECUTABLE_FILE_BYTES = 8 * 1024 * 1024
MAX_EXECUTABLE_TOTAL_BYTES = 32 * 1024 * 1024
MAX_IMPORT_ENTRIES = 512
MAX_NATIVE_DEPENDENCY_ENTRIES = 256
MAX_STRING_BYTES = 4096
MAX_SEQUENCE_ENTRIES = 1024
MAX_JSON_INTEGER = (1 << 63) - 1
MIN_JSON_INTEGER = -(1 << 63)

CONTRACT_SCHEMA = "m1b-offline-executable-tcb-contract-v1"
CONTRACT_VERSION = "m1b-offline-executable-tcb-admission-v1"
CONTRACT_GENERATION = 1
MANIFEST_SCHEMA = "m1b-executable-implementation-manifest-v1"
ACCEPTANCE_STATE = "owner_accepted"
EXECUTION_ENVELOPE_SCHEMA = "m1b-execution-envelope-v1"
EXECUTION_ENVELOPE_GENERATION = 1
PROTOCOL_GENERATION = 108

# Filled from the canonical normative registry record.  It is deliberately
# external to that record; the record contains no self hash.
EXPECTED_CONTRACT_SHA256 = (
    "589cf895c659b57c2f44268acfa0bf33b3c98d6cd5e6b4fea1f2f9b2500d1a5f"
)

FileIdentity = Tuple[int, int]
VerifiedFiles = Dict[str, Tuple[str, FileIdentity]]

REQUIRED_ROLES = (
    "analysis_engine",
    "contract_validator",
    "provider_request_harness",
    "synthetic_fixture_materializer",
)

_MANIFEST_DOMAIN = b"stellaris-m1b-executable-manifest-v1"
_CONTRACT_DOMAIN = b"stellaris-m1b-offline-executable-tcb-contract-v1"
_DIGEST = re.compile(r"[0-9a-f]{64}", re.ASCII)
_MODULE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*", re.ASCII)
_CODE = re.compile(r"[A-Z][A-Z0-9_]+", re.ASCII)

_MANIFEST_FIELDS = ("files", "implementation_generation", "manifest_schema")
_MANIFEST_FILE_FIELDS = ("path", "role", "sha256")
_ACCEPTANCE_FIELDS = (
    "acceptance_state",
    "implementation_generation",
    "manifest_schema",
    "manifest_sha256",
    "protocol_generation",
)
_CONTRACT_FIELDS = (
    "contract_generation",
    "contract_schema",
    "contract_version",
    "digest_framing",
    "execution_envelope",
    "implementation_acceptance",
    "implementation_manifest",
    "limits",
    "offline_verifier",
    "protocol_generation",
    "status_policy",
)
_ENVELOPE_FIELDS = (
    "admitted_state",
    "contract_generation",
    "contract_schema",
    "contract_sha256",
    "contract_version",
    "envelope_generation",
    "envelope_schema",
    "implementation_generation",
    "manifest_schema",
    "manifest_sha256",
    "observed_state",
    "protocol_generation",
)
_STATE_FIELDS = (
    "bytecode",
    "environment",
    "imports",
    "interpreter",
    "invocation",
    "native_dependencies",
    "runtime_hooks",
)
_INTERPRETER_FIELDS = (
    "abi_flags",
    "byteorder",
    "cache_tag",
    "executable_path",
    "executable_sha256",
    "extension_suffix",
    "implementation",
    "machine",
    "max_unicode",
    "platform",
    "pointer_bits",
    "soabi",
    "version_tuple",
)
_IMPORT_FIELDS = ("kind", "module", "path", "sha256")
_BYTECODE_FIELDS = (
    "cache_mode",
    "dont_write_bytecode",
    "executed_bytecode",
    "pycache_prefix",
)
_ENVIRONMENT_FIELDS = ("ambient_inheritance", "policy", "variables")
_INVOCATION_FIELDS = (
    "argv",
    "cwd",
    "inherited_fds",
    "mode",
    "python_flags",
    "stdio",
    "sys_path",
    "warnoptions",
    "xoptions",
)
_PYTHON_FLAG_FIELDS = (
    "bytes_warning",
    "debug",
    "dev_mode",
    "dont_write_bytecode",
    "hash_randomization",
    "ignore_environment",
    "inspect",
    "interactive",
    "isolated",
    "no_site",
    "no_user_site",
    "optimize",
    "quiet",
    "utf8_mode",
    "verbose",
)
_STDIO_FIELDS = ("stderr", "stdin", "stdout")
_STDIO_STREAM_FIELDS = ("fd", "mode", "target")
_NATIVE_FIELDS = ("blocker", "dependencies", "status")
_NATIVE_DEPENDENCY_FIELDS = ("install_name", "path", "sha256")
_HOOK_FIELDS = (
    "debugger_attached",
    "meta_path",
    "path_hooks",
    "profile_hook",
    "startup_hooks",
    "trace_hook",
)


class TCBContractError(RuntimeError):
    """A controlled verifier failure carrying only an allowlisted code."""

    def __init__(self, code: str) -> None:
        if type(code) is not str or _CODE.fullmatch(code) is None:
            code = "UNEXPECTED_FAILURE"
        self.code = code
        super().__init__(code)


def _duplicate_safe_object(
    pairs: Sequence[Tuple[str, Any]],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TCBContractError("JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> None:
    raise TCBContractError("JSON_MALFORMED")


def _reject_json_float(_value: str) -> None:
    raise TCBContractError("JSON_FLOAT_FORBIDDEN")


def _parse_bounded_int(token: str) -> int:
    if type(token) is not str or not token:
        raise TCBContractError("JSON_INTEGER_OUT_OF_RANGE")
    negative = token.startswith("-")
    digits = token[1:] if negative else token
    if not digits or not digits.isascii() or not digits.isdigit():
        raise TCBContractError("JSON_INTEGER_OUT_OF_RANGE")
    limit = "9223372036854775808" if negative else "9223372036854775807"
    if len(digits) > len(limit) or (
        len(digits) == len(limit) and digits > limit
    ):
        raise TCBContractError("JSON_INTEGER_OUT_OF_RANGE")
    value = int(token, 10)
    if value < MIN_JSON_INTEGER or value > MAX_JSON_INTEGER:
        raise TCBContractError("JSON_INTEGER_OUT_OF_RANGE")
    return value


def _assert_unicode_scalars(value: Any) -> None:
    if type(value) is str:
        try:
            encoded = value.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            raise TCBContractError("JSON_UNICODE_INVALID")
        if len(encoded) > MAX_STRING_BYTES:
            raise TCBContractError("JSON_STRING_SIZE_LIMIT")
        return
    if type(value) is list:
        if len(value) > MAX_SEQUENCE_ENTRIES:
            raise TCBContractError("JSON_SEQUENCE_SIZE_LIMIT")
        for item in value:
            _assert_unicode_scalars(item)
        return
    if type(value) is dict:
        if len(value) > MAX_SEQUENCE_ENTRIES:
            raise TCBContractError("JSON_SEQUENCE_SIZE_LIMIT")
        for key, item in value.items():
            _assert_unicode_scalars(key)
            _assert_unicode_scalars(item)


def parse_json_bytes(
    data: bytes, limit: int = MAX_JSON_INPUT_BYTES
) -> Any:
    """Parse one strictly bounded UTF-8 JSON value."""

    if type(data) is not bytes or type(limit) is not int or limit < 0:
        raise TCBContractError("INVALID_TYPE")
    if len(data) > limit:
        raise TCBContractError("INPUT_SIZE_LIMIT")
    if data.startswith(b"\xef\xbb\xbf"):
        raise TCBContractError("JSON_MALFORMED")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise TCBContractError("UTF8_INVALID")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_safe_object,
            parse_constant=_reject_json_constant,
            parse_float=_reject_json_float,
            parse_int=_parse_bounded_int,
        )
    except TCBContractError:
        raise
    except RecursionError:
        raise TCBContractError("JSON_NESTING_LIMIT")
    except (json.JSONDecodeError, TypeError, ValueError):
        raise TCBContractError("JSON_MALFORMED")
    _assert_unicode_scalars(value)
    return value


def _require_object(
    value: Any, fields: Sequence[str], code: str
) -> Dict[str, Any]:
    if type(value) is not dict or set(value) != set(fields):
        raise TCBContractError(code)
    return value


def _require_list(value: Any, code: str, maximum: int) -> List[Any]:
    if type(value) is not list or len(value) > maximum:
        raise TCBContractError(code)
    return value


def _require_string(value: Any, code: str) -> str:
    if type(value) is not str:
        raise TCBContractError(code)
    return value


def _require_bool(value: Any, code: str) -> bool:
    if type(value) is not bool:
        raise TCBContractError(code)
    return value


def _require_positive_int(value: Any, code: str) -> int:
    if type(value) is not int or value < 1 or value > MAX_JSON_INTEGER:
        raise TCBContractError(code)
    return value


def _require_nonnegative_int(value: Any, code: str) -> int:
    if type(value) is not int or value < 0 or value > MAX_JSON_INTEGER:
        raise TCBContractError(code)
    return value


def _require_digest(value: Any, code: str) -> str:
    text = _require_string(value, code)
    if _DIGEST.fullmatch(text) is None:
        raise TCBContractError(code)
    return text


def _relative_components(value: Any, code: str) -> Tuple[str, ...]:
    path = _require_string(value, code)
    if not path or path.startswith("/") or "\\" in path or "\x00" in path:
        raise TCBContractError(code)
    try:
        encoded = path.encode("ascii", errors="strict")
    except UnicodeEncodeError:
        raise TCBContractError(code)
    if any(byte < 0x20 or byte == 0x7F for byte in encoded):
        raise TCBContractError(code)
    components = tuple(path.split("/"))
    if any(component in ("", ".", "..") for component in components):
        raise TCBContractError(code)
    return components


def _absolute_root_components(value: Any) -> Tuple[str, ...]:
    path = _require_string(value, "REPOSITORY_ROOT_INVALID")
    if not path.startswith("/") or path == "/" or "\\" in path or "\x00" in path:
        raise TCBContractError("REPOSITORY_ROOT_INVALID")
    try:
        encoded = path.encode("ascii", errors="strict")
    except UnicodeEncodeError:
        raise TCBContractError("REPOSITORY_ROOT_INVALID")
    if any(byte < 0x20 or byte == 0x7F for byte in encoded):
        raise TCBContractError("REPOSITORY_ROOT_INVALID")
    components = tuple(path[1:].split("/"))
    if any(component in ("", ".", "..") for component in components):
        raise TCBContractError("REPOSITORY_ROOT_INVALID")
    return components


def _metadata(identity: os.stat_result) -> Tuple[int, ...]:
    return (
        identity.st_dev,
        identity.st_ino,
        identity.st_mode,
        identity.st_nlink,
        identity.st_uid,
        identity.st_gid,
        identity.st_size,
        identity.st_mtime_ns,
        identity.st_ctime_ns,
    )


def _nofollow_directory_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    cloexec = getattr(os, "O_CLOEXEC", 0)
    if not nofollow or not directory or not cloexec:
        raise TCBContractError("PLATFORM_UNSUPPORTED")
    return os.O_RDONLY | nofollow | directory | cloexec


def _nofollow_file_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    cloexec = getattr(os, "O_CLOEXEC", 0)
    nonblock = getattr(os, "O_NONBLOCK", 0)
    if not nofollow or not cloexec or not nonblock:
        raise TCBContractError("PLATFORM_UNSUPPORTED")
    return os.O_RDONLY | nofollow | cloexec | nonblock


def _close_descriptors_once(
    descriptors: Sequence[int], primary: Optional[TCBContractError], code: str
) -> Optional[TCBContractError]:
    result = primary
    for descriptor in descriptors:
        try:
            os.close(descriptor)
        except BaseException:
            if result is None:
                result = TCBContractError(code)
    return result


def _open_repository_root(
    repository_root: str,
) -> Tuple[int, Tuple[int, ...], Tuple[Tuple[int, str, int, Tuple[int, ...]], ...]]:
    """Open an absolute root one no-follow component at a time."""

    components = _absolute_root_components(repository_root)
    descriptors: List[int] = []
    links: List[Tuple[int, str, int, Tuple[int, ...]]] = []
    primary: Optional[TCBContractError] = None
    try:
        current = os.open("/", _nofollow_directory_flags())
        descriptors.append(current)
        root_stat = os.fstat(current)
        if not stat.S_ISDIR(root_stat.st_mode):
            raise TCBContractError("REPOSITORY_ROOT_INVALID")
        for component in components:
            parent = current
            current = os.open(
                component, _nofollow_directory_flags(), dir_fd=parent
            )
            descriptors.append(current)
            current_stat = os.fstat(current)
            if not stat.S_ISDIR(current_stat.st_mode):
                raise TCBContractError("REPOSITORY_ROOT_INVALID")
            links.append((parent, component, current, _metadata(current_stat)))
        return current, tuple(descriptors), tuple(links)
    except TCBContractError as error:
        primary = error
    except BaseException:
        primary = TCBContractError("REPOSITORY_ROOT_INVALID")
    primary = _close_descriptors_once(
        descriptors, primary, "REPOSITORY_ROOT_INVALID"
    )
    assert primary is not None
    raise primary


def _verify_open_directory_links(
    links: Sequence[Tuple[int, str, int, Tuple[int, ...]]],
    code: str,
    *,
    strict_metadata: bool = False,
) -> None:
    for parent, component, child, before in links:
        try:
            after_fd = os.fstat(child)
            after_entry = os.stat(
                component, dir_fd=parent, follow_symlinks=False
            )
        except BaseException:
            raise TCBContractError(code)
        if (
            not stat.S_ISDIR(after_fd.st_mode)
            or not stat.S_ISDIR(after_entry.st_mode)
            or after_fd.st_dev != before[0]
            or after_fd.st_ino != before[1]
            or after_fd.st_mode != before[2]
            or after_entry.st_dev != after_fd.st_dev
            or after_entry.st_ino != after_fd.st_ino
            or after_entry.st_mode != after_fd.st_mode
        ):
            raise TCBContractError(code)
        if strict_metadata and (
            _metadata(after_fd) != before
            or _metadata(after_entry) != _metadata(after_fd)
        ):
            raise TCBContractError(code)


def _verify_rooted_directory(
    root_descriptor: int,
    relative_path: str,
    code: str = "INVOCATION_CWD_INVALID",
) -> None:
    """Verify one stable rooted directory without following any component."""

    components = _relative_components(relative_path, code)
    if type(root_descriptor) is not int or root_descriptor < 0:
        raise TCBContractError(code)
    descriptors: List[int] = []
    links: List[Tuple[int, str, int, Tuple[int, ...]]] = []
    primary: Optional[TCBContractError] = None
    try:
        current = root_descriptor
        for component in components:
            parent = current
            try:
                current = os.open(
                    component, _nofollow_directory_flags(), dir_fd=parent
                )
            except BaseException:
                raise TCBContractError(code)
            descriptors.append(current)
            current_stat = os.fstat(current)
            if not stat.S_ISDIR(current_stat.st_mode):
                raise TCBContractError(code)
            links.append((parent, component, current, _metadata(current_stat)))
        _verify_open_directory_links(
            links, code, strict_metadata=True
        )
    except TCBContractError as error:
        primary = error
    except BaseException:
        primary = TCBContractError(code)
    finally:
        primary = _close_descriptors_once(descriptors, primary, code)
    if primary is not None:
        raise primary


def _read_rooted_regular_file(
    root_descriptor: int,
    relative_path: str,
    max_bytes: int,
    *,
    size_code: str = "INPUT_SIZE_LIMIT",
    invalid_code: str = "INPUT_FILE_INVALID",
    read_code: str = "INPUT_READ_FAILED",
    changed_code: str = "INPUT_CHANGED",
    identity_out: Optional[List[FileIdentity]] = None,
) -> bytes:
    """Read stable exact bytes through descriptor-rooted no-follow traversal."""

    components = _relative_components(relative_path, invalid_code)
    if type(root_descriptor) is not int or root_descriptor < 0:
        raise TCBContractError(read_code)
    if type(max_bytes) is not int or max_bytes < 0:
        raise TCBContractError("INVALID_TYPE")
    descriptors: List[int] = []
    links: List[Tuple[int, str, int, Tuple[int, ...]]] = []
    leaf_descriptor = -1
    leaf_parent = root_descriptor
    leaf_name = components[-1]
    leaf_before: Optional[os.stat_result] = None
    data = b""
    primary: Optional[TCBContractError] = None
    try:
        current = root_descriptor
        for component in components[:-1]:
            parent = current
            try:
                current = os.open(
                    component, _nofollow_directory_flags(), dir_fd=parent
                )
            except OSError as error:
                if error.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise TCBContractError(invalid_code)
                raise TCBContractError(read_code)
            descriptors.append(current)
            current_stat = os.fstat(current)
            if not stat.S_ISDIR(current_stat.st_mode):
                raise TCBContractError(invalid_code)
            links.append((parent, component, current, _metadata(current_stat)))
        leaf_parent = current
        try:
            leaf_descriptor = os.open(
                leaf_name, _nofollow_file_flags(), dir_fd=leaf_parent
            )
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise TCBContractError(invalid_code)
            raise TCBContractError(read_code)
        descriptors.append(leaf_descriptor)
        leaf_before = os.fstat(leaf_descriptor)
        if not stat.S_ISREG(leaf_before.st_mode) or leaf_before.st_nlink != 1:
            raise TCBContractError(invalid_code)
        if leaf_before.st_size > max_bytes:
            raise TCBContractError(size_code)
        remaining = leaf_before.st_size
        chunks: List[bytes] = []
        while remaining:
            chunk = os.read(leaf_descriptor, min(remaining, 8192))
            if type(chunk) is not bytes:
                raise TCBContractError(read_code)
            if not chunk:
                raise TCBContractError(changed_code)
            if len(chunk) > remaining:
                raise TCBContractError(changed_code)
            chunks.append(chunk)
            remaining -= len(chunk)
        extra = os.read(leaf_descriptor, 1)
        if type(extra) is not bytes:
            raise TCBContractError(read_code)
        if extra:
            raise TCBContractError(changed_code)
        data = b"".join(chunks)
        after = os.fstat(leaf_descriptor)
        entry = os.stat(
            leaf_name, dir_fd=leaf_parent, follow_symlinks=False
        )
        if (
            _metadata(after) != _metadata(leaf_before)
            or len(data) != leaf_before.st_size
            or not stat.S_ISREG(entry.st_mode)
            or entry.st_nlink != 1
            or entry.st_dev != after.st_dev
            or entry.st_ino != after.st_ino
            or entry.st_mode != after.st_mode
        ):
            raise TCBContractError(changed_code)
        _verify_open_directory_links(links, changed_code)
    except TCBContractError as error:
        primary = error
    except BaseException:
        primary = TCBContractError(read_code)
    finally:
        primary = _close_descriptors_once(descriptors, primary, read_code)
    if primary is not None:
        raise primary
    if leaf_before is None:
        raise TCBContractError(read_code)
    if identity_out is not None:
        identity_out.append((leaf_before.st_dev, leaf_before.st_ino))
    return data


def canonical_manifest_bytes(value: Any) -> bytes:
    """Return the one canonical manifest encoding after shape validation."""

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii", errors="strict") + b"\n"
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError):
        raise TCBContractError("MANIFEST_INVALID")
    if len(encoded) > MAX_JSON_INPUT_BYTES:
        raise TCBContractError("INPUT_SIZE_LIMIT")
    return encoded


def manifest_digest(canonical_bytes: bytes) -> str:
    """Return the domain-separated digest of canonical manifest bytes."""

    if type(canonical_bytes) is not bytes:
        raise TCBContractError("INVALID_TYPE")
    framed = (
        _MANIFEST_DOMAIN
        + b"\x00"
        + len(canonical_bytes).to_bytes(8, "big")
        + canonical_bytes
    )
    return hashlib.sha256(framed).hexdigest()


def canonical_contract_bytes(value: Any) -> bytes:
    """Return the canonical external contract encoding."""

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii", errors="strict") + b"\n"
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError):
        raise TCBContractError("CONTRACT_INVALID")
    if len(encoded) > MAX_JSON_INPUT_BYTES:
        raise TCBContractError("INPUT_SIZE_LIMIT")
    return encoded


def contract_digest(canonical_bytes: bytes) -> str:
    """Return the domain-separated external normative contract digest."""

    if type(canonical_bytes) is not bytes:
        raise TCBContractError("INVALID_TYPE")
    framed = (
        _CONTRACT_DOMAIN
        + b"\x00"
        + len(canonical_bytes).to_bytes(8, "big")
        + canonical_bytes
    )
    return hashlib.sha256(framed).hexdigest()


def _validate_contract_bytes(contract_bytes: bytes) -> Tuple[Dict[str, Any], str]:
    contract = _require_object(
        parse_json_bytes(contract_bytes), _CONTRACT_FIELDS, "CONTRACT_INVALID"
    )
    _require_string(contract["contract_schema"], "CONTRACT_INVALID")
    _require_string(contract["contract_version"], "CONTRACT_INVALID")
    _require_positive_int(contract["contract_generation"], "CONTRACT_INVALID")
    _require_positive_int(contract["protocol_generation"], "CONTRACT_INVALID")
    canonical = canonical_contract_bytes(contract)
    if canonical != contract_bytes:
        raise TCBContractError("CONTRACT_IDENTITY_MISMATCH")
    digest = contract_digest(canonical)
    if digest != EXPECTED_CONTRACT_SHA256:
        raise TCBContractError("CONTRACT_IDENTITY_MISMATCH")
    return contract, digest


def _verify_executable_identity(
    root_descriptor: int,
    relative_path: str,
    expected_sha256: str,
    verified: VerifiedFiles,
    total_bytes: int,
) -> Tuple[int, bool, FileIdentity]:
    existing = verified.get(relative_path)
    if existing is not None:
        existing_sha256, existing_identity = existing
        if existing_sha256 != expected_sha256:
            raise TCBContractError("EXECUTION_FILE_HASH_MISMATCH")
        return total_bytes, False, existing_identity
    remaining = MAX_EXECUTABLE_TOTAL_BYTES - total_bytes
    if remaining < 0:
        raise TCBContractError("EXECUTABLE_TOTAL_SIZE_LIMIT")
    limit = min(MAX_EXECUTABLE_FILE_BYTES, remaining)
    size_code = (
        "EXECUTABLE_FILE_SIZE_LIMIT"
        if remaining >= MAX_EXECUTABLE_FILE_BYTES
        else "EXECUTABLE_TOTAL_SIZE_LIMIT"
    )
    identities: List[FileIdentity] = []
    data = _read_rooted_regular_file(
        root_descriptor,
        relative_path,
        limit,
        size_code=size_code,
        invalid_code="EXECUTABLE_FILE_INVALID",
        read_code="EXECUTABLE_READ_FAILED",
        changed_code="EXECUTABLE_CHANGED",
        identity_out=identities,
    )
    if len(identities) != 1:
        raise TCBContractError("EXECUTABLE_READ_FAILED")
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise TCBContractError("EXECUTION_FILE_HASH_MISMATCH")
    identity = identities[0]
    verified[relative_path] = (expected_sha256, identity)
    return total_bytes + len(data), True, identity


def _validate_manifest_bytes(
    manifest_bytes: bytes,
    root_descriptor: int,
    record_paths: Sequence[str],
    record_identities: Set[FileIdentity],
    verified: VerifiedFiles,
    total_bytes: int,
) -> Tuple[Dict[str, Any], str, int, int]:
    manifest_value = parse_json_bytes(manifest_bytes)
    manifest = _require_object(
        manifest_value, _MANIFEST_FIELDS, "MANIFEST_INVALID"
    )
    if manifest["manifest_schema"] != MANIFEST_SCHEMA:
        raise TCBContractError("MANIFEST_INVALID")
    _require_positive_int(
        manifest["implementation_generation"], "MANIFEST_INVALID"
    )
    rows = _require_list(
        manifest["files"], "MANIFEST_INVALID", MAX_SEQUENCE_ENTRIES
    )
    if len(rows) != len(REQUIRED_ROLES):
        raise TCBContractError("MANIFEST_ROLE_SET_INVALID")
    record_path_set: Set[str] = set()
    for record_path in record_paths:
        _relative_components(record_path, "MANIFEST_PATH_INVALID")
        record_path_set.add(record_path)

    paths: List[str] = []
    roles: List[str] = []
    prepared: List[Tuple[str, str]] = []
    for raw_row in rows:
        row = _require_object(
            raw_row, _MANIFEST_FILE_FIELDS, "MANIFEST_INVALID"
        )
        path = _require_string(row["path"], "MANIFEST_PATH_INVALID")
        _relative_components(path, "MANIFEST_PATH_INVALID")
        if path in record_path_set:
            raise TCBContractError("MANIFEST_SELF_ENTRY_FORBIDDEN")
        role = _require_string(row["role"], "MANIFEST_ROLE_SET_INVALID")
        digest = _require_digest(
            row["sha256"], "MANIFEST_FILE_HASH_INVALID"
        )
        paths.append(path)
        roles.append(role)
        prepared.append((path, digest))
    if len(paths) != len(set(paths)):
        raise TCBContractError("MANIFEST_PATH_INVALID")
    if len(roles) != len(set(roles)) or set(roles) != set(REQUIRED_ROLES):
        raise TCBContractError("MANIFEST_ROLE_SET_INVALID")
    if paths != sorted(paths, key=lambda path: path.encode("ascii")):
        raise TCBContractError("MANIFEST_PATH_INVALID")
    canonical = canonical_manifest_bytes(manifest)
    if manifest_bytes != canonical:
        raise TCBContractError("MANIFEST_NONCANONICAL")

    executable_count = 0
    manifest_identities: Set[FileIdentity] = set()
    for path, digest in prepared:
        try:
            total_bytes, added, identity = _verify_executable_identity(
                root_descriptor, path, digest, verified, total_bytes
            )
        except TCBContractError as error:
            if error.code == "EXECUTION_FILE_HASH_MISMATCH":
                raise TCBContractError("MANIFEST_FILE_HASH_MISMATCH")
            raise
        if identity in record_identities:
            raise TCBContractError("MANIFEST_SELF_ENTRY_FORBIDDEN")
        if identity in manifest_identities:
            raise TCBContractError("MANIFEST_PATH_INVALID")
        manifest_identities.add(identity)
        if added:
            executable_count += 1
    return manifest, manifest_digest(canonical), total_bytes, executable_count


def _validate_acceptance_record(
    acceptance_bytes: bytes,
    manifest: Mapping[str, Any],
    digest: str,
) -> Dict[str, Any]:
    acceptance = _require_object(
        parse_json_bytes(acceptance_bytes),
        _ACCEPTANCE_FIELDS,
        "ACCEPTANCE_RECORD_INVALID",
    )
    if acceptance["acceptance_state"] != ACCEPTANCE_STATE:
        raise TCBContractError("ACCEPTANCE_STATE_INVALID")
    generation = _require_positive_int(
        acceptance["implementation_generation"],
        "ACCEPTANCE_RECORD_INVALID",
    )
    protocol_generation = _require_positive_int(
        acceptance["protocol_generation"], "ACCEPTANCE_RECORD_INVALID"
    )
    supplied_digest = _require_digest(
        acceptance["manifest_sha256"], "ACCEPTANCE_RECORD_INVALID"
    )
    if (
        generation != manifest["implementation_generation"]
        or acceptance["manifest_schema"] != MANIFEST_SCHEMA
        or acceptance["manifest_schema"] != manifest["manifest_schema"]
        or supplied_digest != digest
        or protocol_generation != PROTOCOL_GENERATION
    ):
        raise TCBContractError("ACCEPTANCE_LINKAGE_MISMATCH")
    return acceptance


def _require_ascii_text(
    value: Any, code: str, *, allow_empty: bool = False
) -> str:
    text = _require_string(value, code)
    if not text and not allow_empty:
        raise TCBContractError(code)
    try:
        encoded = text.encode("ascii", errors="strict")
    except UnicodeEncodeError:
        raise TCBContractError(code)
    if any(byte < 0x20 or byte == 0x7F for byte in encoded) or "\x00" in text:
        raise TCBContractError(code)
    return text


def _validate_interpreter(
    value: Any,
    root_descriptor: int,
    verified: VerifiedFiles,
    total_bytes: int,
) -> Tuple[Dict[str, Any], int]:
    interpreter = _require_object(
        value, _INTERPRETER_FIELDS, "EXECUTION_ENVELOPE_INVALID"
    )
    if interpreter["implementation"] != "cpython":
        raise TCBContractError("RUNTIME_IDENTITY_INVALID")
    version = _require_list(
        interpreter["version_tuple"], "RUNTIME_IDENTITY_INVALID", 5
    )
    if len(version) != 5:
        raise TCBContractError("RUNTIME_IDENTITY_INVALID")
    for item in (version[0], version[1], version[2], version[4]):
        _require_nonnegative_int(item, "RUNTIME_IDENTITY_INVALID")
    if (
        version[0] != 3
        or version[1] != 9
        or version[3] not in ("alpha", "beta", "candidate", "final")
    ):
        raise TCBContractError("RUNTIME_IDENTITY_INVALID")
    cache_tag = _require_ascii_text(
        interpreter["cache_tag"], "RUNTIME_IDENTITY_INVALID"
    )
    if cache_tag != "cpython-{}{}".format(version[0], version[1]):
        raise TCBContractError("RUNTIME_IDENTITY_INVALID")
    abi_flags = _require_ascii_text(
        interpreter["abi_flags"], "RUNTIME_IDENTITY_INVALID", allow_empty=True
    )
    byteorder = _require_ascii_text(
        interpreter["byteorder"], "RUNTIME_IDENTITY_INVALID"
    )
    extension_suffix = _require_ascii_text(
        interpreter["extension_suffix"], "RUNTIME_IDENTITY_INVALID"
    )
    machine = _require_ascii_text(
        interpreter["machine"], "RUNTIME_IDENTITY_INVALID"
    )
    max_unicode = _require_nonnegative_int(
        interpreter["max_unicode"], "RUNTIME_IDENTITY_INVALID"
    )
    platform = _require_ascii_text(
        interpreter["platform"], "RUNTIME_IDENTITY_INVALID"
    )
    pointer_bits = _require_positive_int(
        interpreter["pointer_bits"], "RUNTIME_IDENTITY_INVALID"
    )
    soabi = _require_ascii_text(
        interpreter["soabi"], "RUNTIME_IDENTITY_INVALID"
    )
    if (
        abi_flags != ""
        or byteorder != "little"
        or extension_suffix != ".cpython-39-darwin.so"
        or machine != "arm64"
        or max_unicode != 1114111
        or platform != "darwin"
        or pointer_bits != 64
        or soabi != "cpython-39-darwin"
    ):
        raise TCBContractError("RUNTIME_IDENTITY_INVALID")
    executable_path = _require_string(
        interpreter["executable_path"], "RUNTIME_IDENTITY_INVALID"
    )
    _relative_components(executable_path, "RUNTIME_IDENTITY_INVALID")
    executable_sha256 = _require_digest(
        interpreter["executable_sha256"], "RUNTIME_IDENTITY_INVALID"
    )
    total_bytes, _added, _identity = _verify_executable_identity(
        root_descriptor,
        executable_path,
        executable_sha256,
        verified,
        total_bytes,
    )
    return interpreter, total_bytes


def _validate_bytecode(value: Any) -> Dict[str, Any]:
    bytecode = _require_object(
        value, _BYTECODE_FIELDS, "BYTECODE_POLICY_INVALID"
    )
    if (
        bytecode["cache_mode"] != "sealed_empty"
        or _require_bool(
            bytecode["dont_write_bytecode"], "BYTECODE_POLICY_INVALID"
        )
        is not True
        or bytecode["executed_bytecode"] != []
        or bytecode["pycache_prefix"] is not None
    ):
        raise TCBContractError("BYTECODE_POLICY_INVALID")
    return bytecode


def _validate_environment(value: Any) -> Dict[str, Any]:
    environment = _require_object(
        value, _ENVIRONMENT_FIELDS, "ENVIRONMENT_POLICY_INVALID"
    )
    if (
        _require_bool(
            environment["ambient_inheritance"], "ENVIRONMENT_POLICY_INVALID"
        )
        is not False
        or environment["policy"] != "empty"
        or environment["variables"] != []
    ):
        raise TCBContractError("ENVIRONMENT_POLICY_INVALID")
    return environment


def _validate_python_flags(value: Any) -> Dict[str, Any]:
    flags = _require_object(
        value, _PYTHON_FLAG_FIELDS, "INVOCATION_POLICY_INVALID"
    )
    expected = {
        "bytes_warning": 0,
        "debug": 0,
        "dev_mode": False,
        "dont_write_bytecode": 1,
        "hash_randomization": 1,
        "ignore_environment": 1,
        "inspect": 0,
        "interactive": 0,
        "isolated": 1,
        "no_site": 1,
        "no_user_site": 1,
        "optimize": 0,
        "quiet": 0,
        "utf8_mode": 1,
        "verbose": 0,
    }
    if flags != expected:
        raise TCBContractError("INVOCATION_POLICY_INVALID")
    if type(flags["dev_mode"]) is not bool:
        raise TCBContractError("INVOCATION_POLICY_INVALID")
    for field in (
        "bytes_warning",
        "debug",
        "dont_write_bytecode",
        "hash_randomization",
        "ignore_environment",
        "inspect",
        "interactive",
        "isolated",
        "no_site",
        "no_user_site",
        "optimize",
        "quiet",
        "utf8_mode",
        "verbose",
    ):
        _require_nonnegative_int(flags[field], "INVOCATION_POLICY_INVALID")
    return flags


def _validate_invocation(value: Any) -> Tuple[Dict[str, Any], Tuple[str, ...]]:
    invocation = _require_object(
        value, _INVOCATION_FIELDS, "INVOCATION_POLICY_INVALID"
    )
    if invocation["mode"] != "verified_open_descriptors_no_reopen":
        raise TCBContractError("INVOCATION_POLICY_INVALID")
    _validate_python_flags(invocation["python_flags"])

    argv = _require_list(
        invocation["argv"], "INVOCATION_POLICY_INVALID", MAX_SEQUENCE_ENTRIES
    )
    if not argv:
        raise TCBContractError("INVOCATION_POLICY_INVALID")
    for argument in argv:
        _require_ascii_text(
            argument, "INVOCATION_POLICY_INVALID", allow_empty=True
        )
    cwd = _require_string(invocation["cwd"], "INVOCATION_POLICY_INVALID")
    _relative_components(cwd, "INVOCATION_POLICY_INVALID")

    sys_path_rows = _require_list(
        invocation["sys_path"],
        "INVOCATION_POLICY_INVALID",
        MAX_SEQUENCE_ENTRIES,
    )
    sys_paths: List[str] = []
    for path in sys_path_rows:
        path = _require_string(path, "INVOCATION_POLICY_INVALID")
        _relative_components(path, "INVOCATION_POLICY_INVALID")
        sys_paths.append(path)
    if len(sys_paths) != len(set(sys_paths)):
        raise TCBContractError("INVOCATION_POLICY_INVALID")

    if invocation["inherited_fds"] != []:
        raise TCBContractError("INVOCATION_POLICY_INVALID")

    stdio = _require_object(
        invocation["stdio"], _STDIO_FIELDS, "INVOCATION_POLICY_INVALID"
    )
    expected_stdio = {
        "stderr": {"fd": 2, "mode": "write", "target": "captured_pipe"},
        "stdin": {"fd": 0, "mode": "read", "target": "devnull"},
        "stdout": {"fd": 1, "mode": "write", "target": "captured_pipe"},
    }
    if stdio != expected_stdio:
        raise TCBContractError("INVOCATION_POLICY_INVALID")
    for stream in ("stdin", "stdout", "stderr"):
        row = _require_object(
            stdio[stream], _STDIO_STREAM_FIELDS, "INVOCATION_POLICY_INVALID"
        )
        _require_nonnegative_int(row["fd"], "INVOCATION_POLICY_INVALID")
        _require_ascii_text(row["mode"], "INVOCATION_POLICY_INVALID")
        _require_ascii_text(row["target"], "INVOCATION_POLICY_INVALID")
    if invocation["warnoptions"] != [] or invocation["xoptions"] != []:
        raise TCBContractError("INVOCATION_POLICY_INVALID")
    return invocation, tuple(sys_paths)


def _validate_runtime_hooks(value: Any) -> Dict[str, Any]:
    hooks = _require_object(value, _HOOK_FIELDS, "RUNTIME_HOOK_POLICY_INVALID")
    for field in (
        "debugger_attached",
        "profile_hook",
        "trace_hook",
    ):
        if _require_bool(hooks[field], "RUNTIME_HOOK_POLICY_INVALID"):
            raise TCBContractError("RUNTIME_HOOK_POLICY_INVALID")
    if (
        hooks["meta_path"]
        != ["BuiltinImporter", "FrozenImporter", "PathFinder"]
        or hooks["path_hooks"] != ["FileFinder"]
        or hooks["startup_hooks"] != []
    ):
        raise TCBContractError("RUNTIME_HOOK_POLICY_INVALID")
    return hooks


def _validate_native_dependencies(
    value: Any,
    root_descriptor: int,
    verified: VerifiedFiles,
    total_bytes: int,
) -> Tuple[Dict[str, Any], int]:
    native = _require_object(
        value, _NATIVE_FIELDS, "NATIVE_DEPENDENCY_POLICY_INVALID"
    )
    if native["status"] == "unproven":
        if (
            native["blocker"] != "NATIVE_DEPENDENCY_CLOSURE_UNPROVEN"
            or native["dependencies"] != []
        ):
            raise TCBContractError("NATIVE_DEPENDENCY_CLOSURE_UNPROVEN")
        return native, total_bytes
    if native["status"] != "bound" or native["blocker"] is not None:
        raise TCBContractError("NATIVE_DEPENDENCY_CLOSURE_UNPROVEN")
    dependencies = _require_list(
        native["dependencies"],
        "NATIVE_DEPENDENCY_POLICY_INVALID",
        MAX_NATIVE_DEPENDENCY_ENTRIES,
    )
    if not dependencies:
        raise TCBContractError("NATIVE_DEPENDENCY_CLOSURE_UNPROVEN")
    install_names: Set[str] = set()
    paths: Set[str] = set()
    for raw in dependencies:
        row = _require_object(
            raw,
            _NATIVE_DEPENDENCY_FIELDS,
            "NATIVE_DEPENDENCY_POLICY_INVALID",
        )
        install_name = _require_ascii_text(
            row["install_name"], "NATIVE_DEPENDENCY_POLICY_INVALID"
        )
        path = _require_string(
            row["path"], "NATIVE_DEPENDENCY_POLICY_INVALID"
        )
        _relative_components(path, "NATIVE_DEPENDENCY_POLICY_INVALID")
        digest = _require_digest(
            row["sha256"], "NATIVE_DEPENDENCY_POLICY_INVALID"
        )
        if install_name in install_names or path in paths:
            raise TCBContractError("NATIVE_DEPENDENCY_POLICY_INVALID")
        install_names.add(install_name)
        paths.add(path)
        total_bytes, _added, _identity = _verify_executable_identity(
            root_descriptor, path, digest, verified, total_bytes
        )
    return native, total_bytes


def _validate_imports(
    value: Any,
    interpreter_sha256: str,
    sys_paths: Sequence[str],
    root_descriptor: int,
    verified: VerifiedFiles,
    total_bytes: int,
) -> Tuple[List[Dict[str, Any]], int]:
    raw_rows = _require_list(
        value, "IMPORT_CLOSURE_INVALID", MAX_IMPORT_ENTRIES
    )
    rows: List[Dict[str, Any]] = []
    modules: Set[str] = set()
    used_sys_paths: Set[str] = set()
    for raw in raw_rows:
        row = _require_object(raw, _IMPORT_FIELDS, "IMPORT_CLOSURE_INVALID")
        kind = _require_string(row["kind"], "IMPORT_CLOSURE_INVALID")
        if kind not in ("builtin", "extension", "frozen", "source"):
            raise TCBContractError("IMPORT_CLOSURE_INVALID")
        module = _require_string(row["module"], "IMPORT_CLOSURE_INVALID")
        if _MODULE.fullmatch(module) is None or module in modules:
            raise TCBContractError("IMPORT_CLOSURE_INVALID")
        modules.add(module)
        digest = _require_digest(row["sha256"], "IMPORT_CLOSURE_INVALID")
        if kind in ("builtin", "frozen"):
            if row["path"] is not None or digest != interpreter_sha256:
                raise TCBContractError("IMPORT_CLOSURE_INVALID")
        else:
            path = _require_string(row["path"], "IMPORT_CLOSURE_INVALID")
            _relative_components(path, "IMPORT_CLOSURE_INVALID")
            matching_roots = tuple(
                candidate
                for candidate in sys_paths
                if path.startswith(candidate + "/")
            )
            if len(matching_roots) != 1:
                raise TCBContractError("IMPORT_PATH_SHADOWING")
            used_sys_paths.add(matching_roots[0])
            total_bytes, _added, _identity = _verify_executable_identity(
                root_descriptor,
                path,
                digest,
                verified,
                total_bytes,
            )
        rows.append(row)
    if used_sys_paths != set(sys_paths):
        raise TCBContractError("IMPORT_CLOSURE_INVALID")
    return rows, total_bytes


def _validate_execution_state(
    value: Any,
    root_descriptor: int,
    verified: VerifiedFiles,
    total_bytes: int,
) -> Tuple[Dict[str, Any], int, int]:
    state = _require_object(
        value, _STATE_FIELDS, "EXECUTION_ENVELOPE_INVALID"
    )
    _validate_bytecode(state["bytecode"])
    _validate_environment(state["environment"])
    interpreter, total_bytes = _validate_interpreter(
        state["interpreter"], root_descriptor, verified, total_bytes
    )
    invocation, sys_paths = _validate_invocation(state["invocation"])
    _verify_rooted_directory(root_descriptor, invocation["cwd"])
    imports, total_bytes = _validate_imports(
        state["imports"],
        interpreter["executable_sha256"],
        sys_paths,
        root_descriptor,
        verified,
        total_bytes,
    )
    _native, total_bytes = _validate_native_dependencies(
        state["native_dependencies"],
        root_descriptor,
        verified,
        total_bytes,
    )
    _validate_runtime_hooks(state["runtime_hooks"])
    return state, total_bytes, len(imports)


def _semantic_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii", errors="strict")
    except BaseException:
        raise TCBContractError("EXECUTION_ENVELOPE_INVALID")


def _validate_execution_envelope(
    envelope_bytes: bytes,
    contract_sha256: str,
    manifest: Mapping[str, Any],
    manifest_sha256: str,
    root_descriptor: int,
    verified: VerifiedFiles,
    total_bytes: int,
) -> Tuple[Dict[str, Any], int, int]:
    parsed_envelope = parse_json_bytes(envelope_bytes)
    envelope = _require_object(
        parsed_envelope,
        _ENVELOPE_FIELDS,
        "EXECUTION_ENVELOPE_INVALID",
    )
    if envelope_bytes != _semantic_json_bytes(envelope) + b"\n":
        raise TCBContractError("EXECUTION_ENVELOPE_NONCANONICAL")
    for field in (
        "contract_generation",
        "envelope_generation",
        "implementation_generation",
        "protocol_generation",
    ):
        _require_positive_int(envelope[field], "EXECUTION_ENVELOPE_INVALID")
    supplied_contract_sha256 = _require_digest(
        envelope["contract_sha256"], "EXECUTION_ENVELOPE_INVALID"
    )
    supplied_manifest_sha256 = _require_digest(
        envelope["manifest_sha256"], "EXECUTION_ENVELOPE_INVALID"
    )
    if (
        envelope["contract_generation"] != CONTRACT_GENERATION
        or envelope["contract_schema"] != CONTRACT_SCHEMA
        or envelope["contract_version"] != CONTRACT_VERSION
        or supplied_contract_sha256 != contract_sha256
        or envelope["envelope_generation"] != EXECUTION_ENVELOPE_GENERATION
        or envelope["envelope_schema"] != EXECUTION_ENVELOPE_SCHEMA
        or envelope["implementation_generation"]
        != manifest["implementation_generation"]
        or envelope["manifest_schema"] != manifest["manifest_schema"]
        or envelope["manifest_schema"] != MANIFEST_SCHEMA
        or supplied_manifest_sha256 != manifest_sha256
        or envelope["protocol_generation"] != PROTOCOL_GENERATION
    ):
        raise TCBContractError("EXECUTION_LINKAGE_MISMATCH")

    if _semantic_json_bytes(envelope["admitted_state"]) != _semantic_json_bytes(
        envelope["observed_state"]
    ):
        raise TCBContractError("EXECUTION_STATE_MISMATCH")
    admitted, total_bytes, admitted_imports = _validate_execution_state(
        envelope["admitted_state"], root_descriptor, verified, total_bytes
    )
    return envelope, total_bytes, admitted_imports


def _empty_counts() -> Dict[str, int]:
    return {
        "contract_records": 0,
        "executable_files": 0,
        "import_entries": 0,
        "linkage_records": 0,
    }


def _result(
    status: str,
    *,
    code: Optional[str] = None,
    contract_records: int = 0,
    executable_files: int = 0,
    import_entries: int = 0,
    linkage_records: int = 0,
) -> Dict[str, Any]:
    if status == "ok":
        codes = ["SYNTHETIC_CONFORMANCE_ONLY"]
    else:
        status = "error"
        codes = [code if type(code) is str and _CODE.fullmatch(code) else "UNEXPECTED_FAILURE"]
    return {
        "codes": codes,
        "counts": {
            "contract_records": contract_records,
            "executable_files": executable_files,
            "import_entries": import_entries,
            "linkage_records": linkage_records,
        },
        "status": status,
    }


def _verify_bytes_with_root(
    contract_bytes: bytes,
    manifest_bytes: bytes,
    acceptance_bytes: bytes,
    envelope_bytes: bytes,
    record_identities: Set[FileIdentity],
    root_descriptor: int,
    contract_path: str,
    manifest_path: str,
    acceptance_path: str,
    envelope_path: str,
) -> Dict[str, Any]:
    _contract, contract_sha256 = _validate_contract_bytes(contract_bytes)
    verified: VerifiedFiles = {}
    manifest, manifest_sha256, total_bytes, _manifest_files = (
        _validate_manifest_bytes(
            manifest_bytes,
            root_descriptor,
            (
                contract_path,
                manifest_path,
                acceptance_path,
                envelope_path,
            ),
            record_identities,
            verified,
            0,
        )
    )
    _validate_acceptance_record(acceptance_bytes, manifest, manifest_sha256)
    _envelope, _total_bytes, import_entries = (
        _validate_execution_envelope(
            envelope_bytes,
            contract_sha256,
            manifest,
            manifest_sha256,
            root_descriptor,
            verified,
            total_bytes,
        )
    )
    return _result(
        "ok",
        contract_records=1,
        executable_files=len(verified),
        import_entries=import_entries,
        linkage_records=2,
    )


def verify_paths(
    contract_path: str,
    manifest_path: str,
    acceptance_path: str,
    envelope_path: str,
    repository_root: str,
) -> Dict[str, Any]:
    """Verify explicitly named rooted records; never discover input paths."""

    root_descriptors: Tuple[int, ...] = ()
    root_links: Tuple[Tuple[int, str, int, Tuple[int, ...]], ...] = ()
    primary: Optional[TCBContractError] = None
    result: Optional[Dict[str, Any]] = None
    try:
        root_descriptor, root_descriptors, root_links = _open_repository_root(
            repository_root
        )
        record_identities: List[FileIdentity] = []
        contract_bytes = _read_rooted_regular_file(
            root_descriptor,
            contract_path,
            MAX_JSON_INPUT_BYTES,
            identity_out=record_identities,
        )
        _validate_contract_bytes(contract_bytes)
        manifest_bytes = _read_rooted_regular_file(
            root_descriptor,
            manifest_path,
            MAX_JSON_INPUT_BYTES,
            identity_out=record_identities,
        )
        acceptance_bytes = _read_rooted_regular_file(
            root_descriptor,
            acceptance_path,
            MAX_JSON_INPUT_BYTES,
            identity_out=record_identities,
        )
        envelope_bytes = _read_rooted_regular_file(
            root_descriptor,
            envelope_path,
            MAX_JSON_INPUT_BYTES,
            identity_out=record_identities,
        )
        if len(record_identities) != 4:
            raise TCBContractError("INPUT_READ_FAILED")
        result = _verify_bytes_with_root(
            contract_bytes,
            manifest_bytes,
            acceptance_bytes,
            envelope_bytes,
            set(record_identities),
            root_descriptor,
            contract_path,
            manifest_path,
            acceptance_path,
            envelope_path,
        )
        _verify_open_directory_links(root_links, "REPOSITORY_ROOT_CHANGED")
    except TCBContractError as error:
        primary = error
    except BaseException:
        primary = TCBContractError("UNEXPECTED_FAILURE")
    finally:
        primary = _close_descriptors_once(
            root_descriptors, primary, "INPUT_READ_FAILED"
        )
    if primary is not None:
        return _result("error", code=primary.code)
    if type(result) is not dict:
        return _result("error", code="UNEXPECTED_FAILURE")
    return result


def _execute(argv: Sequence[str]) -> Dict[str, Any]:
    try:
        if type(argv) not in (list, tuple) or len(argv) != 6:
            raise TCBContractError("CLI_ARGUMENTS_INVALID")
        if argv[0] != "verify" or any(type(value) is not str for value in argv):
            raise TCBContractError("CLI_ARGUMENTS_INVALID")
        return verify_paths(argv[1], argv[2], argv[3], argv[4], argv[5])
    except TCBContractError as error:
        return _result("error", code=error.code)
    except BaseException:
        return _result("error", code="UNEXPECTED_FAILURE")


_ENCODER_FALLBACK = (
    b'{"codes":["UNEXPECTED_FAILURE"],"counts":{"contract_records":0,'
    b'"executable_files":0,"import_entries":0,"linkage_records":0},'
    b'"status":"error"}\n'
)


def _encode_result(result: Mapping[str, Any]) -> bytes:
    try:
        if type(result) is not dict or set(result) != {"codes", "counts", "status"}:
            raise TCBContractError("UNEXPECTED_FAILURE")
        counts = result["counts"]
        codes = result["codes"]
        if (
            type(counts) is not dict
            or set(counts) != set(_empty_counts())
            or any(type(value) is not int or value < 0 for value in counts.values())
            or type(codes) is not list
            or len(codes) != 1
            or any(type(code) is not str or _CODE.fullmatch(code) is None for code in codes)
            or result["status"] not in ("ok", "error")
        ):
            raise TCBContractError("UNEXPECTED_FAILURE")
        return (
            json.dumps(
                result,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii", errors="strict")
            + b"\n"
        )
    except BaseException:
        return _ENCODER_FALLBACK


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = tuple(sys.argv[1:]) if argv is None else argv
    result = _execute(arguments)
    encoded = _encode_result(result)
    try:
        written = sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
    except BaseException:
        return 2
    return (
        0
        if type(result) is dict
        and result.get("status") == "ok"
        and encoded != _ENCODER_FALLBACK
        and written == len(encoded)
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
