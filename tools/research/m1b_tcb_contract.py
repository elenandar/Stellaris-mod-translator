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
import fcntl
import os
import re
import stat
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple


MAX_JSON_INPUT_BYTES = 256 * 1024
MAX_EXECUTABLE_FILE_BYTES = 8 * 1024 * 1024
MAX_EXECUTABLE_TOTAL_BYTES = 32 * 1024 * 1024
MAX_ATOMIC_ENTRYPOINT_BYTES = 512
MAX_IMPORT_ENTRIES = 512
MAX_NATIVE_DEPENDENCY_ENTRIES = 256
MAX_STRING_BYTES = 4096
MAX_SEQUENCE_ENTRIES = 1024
MAX_JSON_INTEGER = (1 << 63) - 1
MIN_JSON_INTEGER = -(1 << 63)

CONTRACT_SCHEMA = "m1b-offline-executable-tcb-contract-v4"
CONTRACT_VERSION = "m1b-offline-executable-tcb-admission-v4"
CONTRACT_GENERATION = 4
MANIFEST_SCHEMA = "m1b-executable-implementation-manifest-v1"
ACCEPTANCE_STATE = "owner_accepted"
EXECUTION_ENVELOPE_SCHEMA = "m1b-execution-envelope-v4"
EXECUTION_ENVELOPE_GENERATION = 4
EXECUTION_PLAN_SCHEMA = "m1b-execution-plan-v3"
EXECUTION_PLAN_GENERATION = 3
RUNTIME_ACCEPTANCE_SCHEMA = (
    "m1b-runtime-execution-envelope-acceptance-v1"
)
RUNTIME_ACCEPTANCE_GENERATION = 1
PROTOCOL_GENERATION = 108

# Filled from the canonical normative registry record.  It is deliberately
# external to that record; the record contains no self hash.
EXPECTED_CONTRACT_SHA256 = (
    "ad6bce1a5c516753d79ee0d807f5445e9b860a398e661adfb9730d9c4fee9c31"
)

FileIdentity = Tuple[int, int]

REQUIRED_ROLES = (
    "analysis_engine",
    "contract_validator",
    "provider_request_harness",
    "synthetic_fixture_materializer",
)

_MANIFEST_DOMAIN = b"stellaris-m1b-executable-manifest-v1"
_CONTRACT_DOMAIN = b"stellaris-m1b-offline-executable-tcb-contract-v4"
_ENVELOPE_DOMAIN = b"stellaris-m1b-execution-envelope-v4"
_RUNTIME_ACCEPTANCE_DOMAIN = (
    b"stellaris-m1b-runtime-execution-envelope-acceptance-v1"
)
_ENVELOPE_DIGEST_FRAMING = (
    "sha256_domain_nul_u64be_length_canonical_envelope"
)
_DIGEST = re.compile(r"[0-9a-f]{64}", re.ASCII)
_MODULE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*", re.ASCII)
_CODE = re.compile(r"[A-Z][A-Z0-9_]+", re.ASCII)

_ALLOWED_CODES = frozenset(
    {
        "ACCEPTANCE_LINKAGE_MISMATCH",
        "ACCEPTANCE_RECORD_INVALID",
        "ACCEPTANCE_STATE_INVALID",
        "BYTECODE_POLICY_INVALID",
        "CLI_ARGUMENT_EXTRA",
        "CLI_ARGUMENT_MISSING",
        "CLI_ARGUMENTS_INVALID",
        "CONTRACT_IDENTITY_MISMATCH",
        "CONTRACT_INVALID",
        "ENVIRONMENT_POLICY_INVALID",
        "ENTRYPOINT_TRANSPORT_BINDING_MISMATCH",
        "ENTRYPOINT_TRANSPORT_CLOSE_FAILED",
        "ENTRYPOINT_TRANSPORT_FD_MISMATCH",
        "ENTRYPOINT_TRANSPORT_INVALID",
        "ENTRYPOINT_TRANSPORT_IO_FAILED",
        "ENTRYPOINT_TRANSPORT_REQUIRED",
        "ENTRYPOINT_TRANSPORT_SIZE_LIMIT",
        "ENTRYPOINT_TRANSPORT_SUBSTITUTED",
        "EXECUTABLE_CHANGED",
        "EXECUTABLE_FILE_INVALID",
        "EXECUTABLE_FILE_SIZE_LIMIT",
        "EXECUTABLE_READ_FAILED",
        "EXECUTABLE_TOTAL_SIZE_LIMIT",
        "EXECUTION_ENVELOPE_INVALID",
        "EXECUTION_ENVELOPE_NONCANONICAL",
        "EXECUTION_FILE_PURPOSE_CONFLICT",
        "EXECUTION_FILE_HASH_MISMATCH",
        "EXECUTION_LINKAGE_MISMATCH",
        "EXECUTION_PLAN_ENTRYPOINT_MISMATCH",
        "EXECUTION_PLAN_IMPORT_BINDING_MISMATCH",
        "EXECUTION_PLAN_INTERPRETER_MISMATCH",
        "EXECUTION_PLAN_INVALID",
        "EXECUTION_PLAN_ROLE_BINDING_MISMATCH",
        "EXECUTION_STATE_MISMATCH",
        "IMPORT_CLOSURE_INVALID",
        "IMPORT_PATH_SHADOWING",
        "INPUT_CHANGED",
        "INPUT_FILE_INVALID",
        "INPUT_READ_FAILED",
        "INPUT_RECORD_ALIAS_FORBIDDEN",
        "INPUT_SIZE_LIMIT",
        "INVALID_TYPE",
        "INVOCATION_ARGV_GRAMMAR_INVALID",
        "INVOCATION_CWD_INVALID",
        "INVOCATION_DIRECTORY_PURPOSE_COLLISION",
        "INVOCATION_ENTRYPOINT_MISMATCH",
        "INVOCATION_FLAGS_MISMATCH",
        "INVOCATION_INTERPRETER_MISMATCH",
        "INVOCATION_LOCATOR_INVALID",
        "INVOCATION_POLICY_INVALID",
        "INVOCATION_SYS_PATH_INVALID",
        "JSON_DUPLICATE_KEY",
        "JSON_FLOAT_FORBIDDEN",
        "JSON_INTEGER_OUT_OF_RANGE",
        "JSON_MALFORMED",
        "JSON_NESTING_LIMIT",
        "JSON_SEQUENCE_SIZE_LIMIT",
        "JSON_STRING_SIZE_LIMIT",
        "JSON_UNICODE_INVALID",
        "LAUNCHER_POLICY_INVALID",
        "MANIFEST_FILE_HASH_INVALID",
        "MANIFEST_FILE_HASH_MISMATCH",
        "MANIFEST_INVALID",
        "MANIFEST_NONCANONICAL",
        "MANIFEST_PATH_INVALID",
        "MANIFEST_ROLE_SET_INVALID",
        "MANIFEST_SELF_ENTRY_FORBIDDEN",
        "NATIVE_DEPENDENCY_CLOSURE_UNPROVEN",
        "NATIVE_DEPENDENCY_POLICY_INVALID",
        "PHYSICAL_IDENTITY_ALIAS",
        "PLATFORM_UNSUPPORTED",
        "REPOSITORY_ROOT_CHANGED",
        "REPOSITORY_ROOT_INVALID",
        "RUNTIME_ACCEPTANCE_ALIAS_FORBIDDEN",
        "RUNTIME_ACCEPTANCE_CONTRACT_DIGEST_MISMATCH",
        "RUNTIME_ACCEPTANCE_CONTRACT_GENERATION_MISMATCH",
        "RUNTIME_ACCEPTANCE_CONTRACT_SCHEMA_MISMATCH",
        "RUNTIME_ACCEPTANCE_CONTRACT_VERSION_MISMATCH",
        "RUNTIME_ACCEPTANCE_DUPLICATE_KEY",
        "RUNTIME_ACCEPTANCE_ENVELOPE_DIGEST_MISMATCH",
        "RUNTIME_ACCEPTANCE_ENVELOPE_DOMAIN_MISMATCH",
        "RUNTIME_ACCEPTANCE_ENVELOPE_FRAMING_MISMATCH",
        "RUNTIME_ACCEPTANCE_ENVELOPE_GENERATION_MISMATCH",
        "RUNTIME_ACCEPTANCE_ENVELOPE_RAW_SHA_FORBIDDEN",
        "RUNTIME_ACCEPTANCE_ENVELOPE_SCHEMA_MISMATCH",
        "RUNTIME_ACCEPTANCE_FIELD_EXTRA",
        "RUNTIME_ACCEPTANCE_FIELD_MISSING",
        "RUNTIME_ACCEPTANCE_GENERATION_MISMATCH",
        "RUNTIME_ACCEPTANCE_IMPLEMENTATION_GENERATION_MISMATCH",
        "RUNTIME_ACCEPTANCE_MALFORMED",
        "RUNTIME_ACCEPTANCE_MANIFEST_DIGEST_MISMATCH",
        "RUNTIME_ACCEPTANCE_MANIFEST_SCHEMA_MISMATCH",
        "RUNTIME_ACCEPTANCE_NONCANONICAL",
        "RUNTIME_ACCEPTANCE_PROTOCOL_GENERATION_MISMATCH",
        "RUNTIME_ACCEPTANCE_SCHEMA_MISMATCH",
        "RUNTIME_ACCEPTANCE_SELF_ASSERTED_PROVEN",
        "RUNTIME_ACCEPTANCE_STATE_INVALID",
        "RUNTIME_ACCEPTANCE_STATE_PROPOSED",
        "RUNTIME_ACCEPTANCE_STATE_RETIRED",
        "RUNTIME_HOOK_POLICY_INVALID",
        "RUNTIME_IDENTITY_INVALID",
        "SYNTHETIC_CONFORMANCE_ONLY",
        "UNEXPECTED_FAILURE",
        "UTF8_INVALID",
    }
)

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
    "runtime_acceptance",
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
    "execution_plan",
    "imports",
    "interpreter",
    "invocation",
    "native_dependencies",
    "runtime_hooks",
)
_EXECUTION_PLAN_FIELDS = (
    "entrypoint",
    "interpreter",
    "launcher",
    "plan_generation",
    "plan_schema",
    "role_imports",
)
_PLAN_INTERPRETER_FIELDS = ("repository_locator", "sha256")
_PLAN_ENTRYPOINT_FIELDS = (
    "mode",
    "repository_locator",
    "role",
    "sha256",
)
_PLAN_ROLE_IMPORT_FIELDS = ("kind", "module", "path", "role", "sha256")
_PLAN_LAUNCHER_FIELDS = ("blockers", "status")
_PLAN_LAUNCHER_BLOCKERS = (
    "INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN",
    "LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN",
    "PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN",
    "ROLE_IMPORT_TRANSPORT_UNPROVEN",
)
_REQUIRED_STATUS_BLOCKERS = (
    "EXECUTABLE_IMPLEMENTATION_IDENTITY_UNPROVEN",
    "EXECUTABLE_TCB_OWNER_DECISION_REQUIRED",
    "PROVIDER_ENTRYPOINT_SOURCE_ELIGIBILITY_UNPROVEN",
    "ROLE_IMPORT_TRANSPORT_UNPROVEN",
    "LAUNCHER_OPENED_BYTE_CHAIN_UNPROVEN",
    "INTERPRETER_PATH_EXEC_IDENTITY_UNPROVEN",
    "NATIVE_DEPENDENCY_CLOSURE_UNPROVEN",
    "CONTEXT_LIMIT_BINDING_UNPROVEN",
    "PROVIDER_PERSISTENCE_UNPROVEN",
    "RESIDENCY_UNPROVEN",
    "OUTPUT_LIMIT_BINDING_UNPROVEN",
    "LIFECYCLE_STATE_UNPROVEN",
    "MISSING_PROMPT_BYTES",
    "MISSING_TEMPLATE_BYTES",
    "MISSING_REAL_CANDIDATE_IDENTITIES",
    "PARTIAL_REPORT_CANNOT_BE_COMPLETE",
)
_STATUS_POLICY_FIELDS = (
    "blockers",
    "contract_state",
    "executable_implementation_identity",
    "executable_tcb_admission",
    "m1a_state",
    "m1b_1a_provider_execution",
    "m1b_state",
    "m2_state",
    "owner_freeze",
    "stable_read_hardening",
)
_PROVIDER_SOURCE_ELIGIBILITY_POLICY = {
    "authority": "exact_admitted_cpython_over_exact_cached_provider_bytes",
    "host_ast_or_compile_is_evidence": False,
    "state": "unproven",
}
_FILE_PURPOSE_COMPATIBILITY = {
    "default": "deny",
    "path_bearing_import_path_policy": (
        "globally_unique_across_module_and_kind"
    ),
    "profiles": {
        "interpreter": {
            "allowed_bindings": [
                "plan_interpreter",
                "invocation_argv0",
                "invocation_os_exec_target",
                "import_builtin_any_unique_module",
                "import_frozen_any_unique_module",
            ],
            "origin": "interpreter",
        },
        "manifest_provider_role": {
            "allowed_bindings": [
                "plan_entrypoint",
                "entrypoint_transport",
            ],
            "origin": "manifest_role_provider_request_harness",
        },
        "manifest_source_role": {
            "allowed_bindings": [
                "matching_plan_role_import",
                "matching_source_import",
            ],
            "matching_keys": ["role", "module"],
            "origins": [
                "manifest_role_analysis_engine",
                "manifest_role_contract_validator",
                "manifest_role_synthetic_fixture_materializer",
            ],
        },
        "native_dependency": {
            "allowed_bindings": [],
            "origin": "one_native_install_name",
        },
        "standalone_extension_import": {
            "allowed_bindings": [],
            "origin": "one_extension_import_module",
        },
        "standalone_source_import": {
            "allowed_bindings": [],
            "origin": "one_source_import_module",
        },
    },
    "reuse_io": "cached_exact_path_digest_no_reopen_no_read",
}
_REQUIRED_IMPORTED_ROLES = (
    "analysis_engine",
    "contract_validator",
    "synthetic_fixture_materializer",
)
_INTERPRETER_FIELDS = (
    "abi_flags",
    "byteorder",
    "cache_tag",
    "executable_sha256",
    "extension_suffix",
    "implementation",
    "machine",
    "max_unicode",
    "platform",
    "pointer_bits",
    "repository_locator",
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
    "argv0",
    "argv_tail",
    "cwd",
    "inherited_fds",
    "mode",
    "os_exec_target",
    "python_flags",
    "stdio",
    "sys_path",
    "warnoptions",
    "xoptions",
)
_LOCATOR_FIELDS = ("base", "path")
_INHERITED_FD_FIELDS = (
    "byte_count",
    "child_fd",
    "mode",
    "process_path",
    "purpose",
    "repository_locator",
    "role",
    "sha256",
    "transport",
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
_RUNTIME_ACCEPTANCE_FIELDS = (
    "contract_generation",
    "contract_schema",
    "contract_sha256",
    "contract_version",
    "envelope_digest_domain",
    "envelope_digest_framing",
    "envelope_generation",
    "envelope_schema",
    "envelope_sha256",
    "implementation_generation",
    "manifest_schema",
    "manifest_sha256",
    "protocol_generation",
    "runtime_acceptance_generation",
    "runtime_acceptance_schema",
    "runtime_acceptance_state",
)


class TCBContractError(RuntimeError):
    """A controlled verifier failure carrying only an allowlisted code."""

    def __init__(self, code: str) -> None:
        if (
            type(code) is not str
            or _CODE.fullmatch(code) is None
            or code not in _ALLOWED_CODES
        ):
            code = "UNEXPECTED_FAILURE"
        self.code = code
        super().__init__(code)


def _file_purpose_profile_allowed(purposes: Set[str]) -> bool:
    """Return whether a partial purpose ledger belongs to one closed profile."""

    if not purposes or any(type(item) is not str for item in purposes):
        return False

    manifest_roles = {
        item.split(":", 1)[1]
        for item in purposes
        if item.startswith("manifest_role:") and item.count(":") == 1
    }
    plan_roles = {
        tuple(item.split(":", 2)[1:])
        for item in purposes
        if item.startswith("plan_role_import:") and item.count(":") == 2
    }
    source_imports = {
        item.split(":", 2)[2]
        for item in purposes
        if item.startswith("import:source:") and item.count(":") == 2
    }
    extension_imports = {
        item.split(":", 2)[2]
        for item in purposes
        if item.startswith("import:extension:") and item.count(":") == 2
    }
    builtin_imports = {
        item.split(":", 2)[2]
        for item in purposes
        if item.startswith("import:builtin:") and item.count(":") == 2
    }
    frozen_imports = {
        item.split(":", 2)[2]
        for item in purposes
        if item.startswith("import:frozen:") and item.count(":") == 2
    }
    native_dependencies = {
        item.split(":", 1)[1]
        for item in purposes
        if item.startswith("native_dependency:") and item.count(":") == 1
    }
    recognized = set()
    recognized.update("manifest_role:{}".format(role) for role in manifest_roles)
    recognized.update(
        "plan_role_import:{}:{}".format(role, module)
        for role, module in plan_roles
    )
    recognized.update("import:source:{}".format(item) for item in source_imports)
    recognized.update(
        "import:extension:{}".format(item) for item in extension_imports
    )
    recognized.update("import:builtin:{}".format(item) for item in builtin_imports)
    recognized.update("import:frozen:{}".format(item) for item in frozen_imports)
    recognized.update(
        "native_dependency:{}".format(item) for item in native_dependencies
    )
    recognized.update(
        purposes
        & {
            "entrypoint_transport",
            "interpreter",
            "invocation_argv0",
            "invocation_os_exec_target",
            "plan_entrypoint",
            "plan_interpreter",
        }
    )
    if recognized != purposes:
        return False

    if manifest_roles:
        if len(manifest_roles) != 1 or native_dependencies:
            return False
        role = next(iter(manifest_roles))
        if role == "provider_request_harness":
            return purposes <= {
                "manifest_role:provider_request_harness",
                "plan_entrypoint",
                "entrypoint_transport",
            }
        if role not in _REQUIRED_IMPORTED_ROLES:
            return False
        if (
            len(plan_roles) > 1
            or len(source_imports) > 1
            or extension_imports
            or builtin_imports
            or frozen_imports
            or purposes
            & {
                "entrypoint_transport",
                "interpreter",
                "invocation_argv0",
                "invocation_os_exec_target",
                "plan_entrypoint",
                "plan_interpreter",
            }
        ):
            return False
        if plan_roles and next(iter(plan_roles))[0] != role:
            return False
        if plan_roles and source_imports:
            return next(iter(plan_roles))[1] == next(iter(source_imports))
        return True

    if "interpreter" in purposes:
        return not (
            plan_roles
            or source_imports
            or extension_imports
            or native_dependencies
            or purposes & {"entrypoint_transport", "plan_entrypoint"}
        )

    if source_imports:
        return len(source_imports) == 1 and len(purposes) == 1
    if extension_imports:
        return len(extension_imports) == 1 and len(purposes) == 1
    if native_dependencies:
        return len(native_dependencies) == 1 and len(purposes) == 1
    return False


class AdmittedFile:
    """One stable file admission retained for exact no-reopen reuse."""

    __slots__ = ("data", "identity", "is_record", "path", "purposes", "sha256")

    def __init__(
        self,
        path: str,
        data: bytes,
        sha256: str,
        identity: FileIdentity,
        *,
        is_record: bool,
        purpose: str,
    ) -> None:
        self.path = path
        self.data = data
        self.sha256 = sha256
        self.identity = identity
        self.is_record = is_record
        self.purposes = {purpose}


class AdmittedFileIndex:
    """Verification-wide lexical and physical identity admission index."""

    def __init__(self, root_descriptor: int) -> None:
        if type(root_descriptor) is not int or root_descriptor < 0:
            raise TCBContractError("INPUT_READ_FAILED")
        self.root_descriptor = root_descriptor
        self.by_path: Dict[str, AdmittedFile] = {}
        self.by_identity: Dict[FileIdentity, AdmittedFile] = {}

    def _publish(self, entry: AdmittedFile) -> AdmittedFile:
        if entry.path in self.by_path or entry.identity in self.by_identity:
            raise TCBContractError("PHYSICAL_IDENTITY_ALIAS")
        self.by_path[entry.path] = entry
        self.by_identity[entry.identity] = entry
        return entry

    @staticmethod
    def _bind_purpose(entry: AdmittedFile, purpose: str) -> None:
        proposed = set(entry.purposes)
        proposed.add(purpose)
        if not _file_purpose_profile_allowed(proposed):
            raise TCBContractError("EXECUTION_FILE_PURPOSE_CONFLICT")
        entry.purposes = proposed

    def admit_record(
        self,
        relative_path: str,
        purpose: str,
        *,
        alias_code: str = "INPUT_RECORD_ALIAS_FORBIDDEN",
    ) -> AdmittedFile:
        _relative_components(relative_path, "INPUT_FILE_INVALID")
        if relative_path in self.by_path:
            raise TCBContractError(alias_code)
        identities: List[FileIdentity] = []
        data = _read_rooted_regular_file(
            self.root_descriptor,
            relative_path,
            MAX_JSON_INPUT_BYTES,
            identity_out=identities,
            known_identities=self.by_identity,
            alias_code=alias_code,
        )
        if len(identities) != 1:
            raise TCBContractError("INPUT_READ_FAILED")
        return self._publish(
            AdmittedFile(
                relative_path,
                data,
                hashlib.sha256(data).hexdigest(),
                identities[0],
                is_record=True,
                purpose=purpose,
            )
        )

    def admit_executable(
        self,
        relative_path: str,
        expected_sha256: str,
        maximum: int,
        *,
        purpose: str,
        size_code: str,
        hash_code: str = "EXECUTION_FILE_HASH_MISMATCH",
        alias_code: str = "PHYSICAL_IDENTITY_ALIAS",
    ) -> Tuple[AdmittedFile, bool]:
        _relative_components(relative_path, "EXECUTABLE_FILE_INVALID")
        digest = _require_digest(expected_sha256, hash_code)
        existing = self.by_path.get(relative_path)
        if existing is not None:
            if existing.is_record:
                raise TCBContractError(alias_code)
            if existing.sha256 != digest:
                raise TCBContractError(hash_code)
            self._bind_purpose(existing, purpose)
            return existing, False
        if not _file_purpose_profile_allowed({purpose}):
            raise TCBContractError("EXECUTION_FILE_PURPOSE_CONFLICT")
        identities: List[FileIdentity] = []
        data = _read_rooted_regular_file(
            self.root_descriptor,
            relative_path,
            maximum,
            size_code=size_code,
            invalid_code="EXECUTABLE_FILE_INVALID",
            read_code="EXECUTABLE_READ_FAILED",
            changed_code="EXECUTABLE_CHANGED",
            identity_out=identities,
            known_identities=self.by_identity,
            alias_code=alias_code,
        )
        if len(identities) != 1:
            raise TCBContractError("EXECUTABLE_READ_FAILED")
        observed_digest = hashlib.sha256(data).hexdigest()
        if observed_digest != digest:
            raise TCBContractError(hash_code)
        entry = AdmittedFile(
            relative_path,
            data,
            observed_digest,
            identities[0],
            is_record=False,
            purpose=purpose,
        )
        return self._publish(entry), True

    def lookup_exact(
        self,
        relative_path: str,
        expected_sha256: str,
        code: str,
        *,
        purpose: Optional[str] = None,
    ) -> AdmittedFile:
        """Resolve only an already admitted exact path; never touch filesystem."""

        entry = self.by_path.get(relative_path)
        if (
            entry is None
            or entry.is_record
            or entry.sha256 != expected_sha256
        ):
            raise TCBContractError(code)
        if purpose is not None:
            self._bind_purpose(entry, purpose)
        return entry


class AdmittedDirectory:
    """One stable directory identity used only during envelope validation."""

    __slots__ = ("identity", "path", "purpose")

    def __init__(
        self, path: str, identity: FileIdentity, purpose: str
    ) -> None:
        self.path = path
        self.identity = identity
        self.purpose = purpose


class AdmittedDirectoryIndex:
    """Separate lexical and physical index for cwd and sys.path directories."""

    def __init__(self, root_descriptor: int) -> None:
        if type(root_descriptor) is not int or root_descriptor < 0:
            raise TCBContractError("INVOCATION_CWD_INVALID")
        self.root_descriptor = root_descriptor
        self.by_path: Dict[str, AdmittedDirectory] = {}
        self.by_identity: Dict[FileIdentity, AdmittedDirectory] = {}

    def admit(self, path: str, purpose: str, code: str) -> AdmittedDirectory:
        existing = self.by_path.get(path)
        if existing is not None:
            if existing.purpose != purpose:
                raise TCBContractError(
                    "INVOCATION_DIRECTORY_PURPOSE_COLLISION"
                )
            raise TCBContractError(code)
        identities: List[FileIdentity] = []
        _verify_rooted_directory(
            self.root_descriptor,
            path,
            code,
            identity_out=identities,
            known_identities=self.by_identity,
        )
        if len(identities) != 1:
            raise TCBContractError(code)
        entry = AdmittedDirectory(path, identities[0], purpose)
        if entry.identity in self.by_identity:
            raise TCBContractError("PHYSICAL_IDENTITY_ALIAS")
        self.by_path[path] = entry
        self.by_identity[entry.identity] = entry
        return entry


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


def _validate_repository_locator(value: Any) -> Dict[str, Any]:
    locator = _require_object(
        value, _LOCATOR_FIELDS, "INVOCATION_LOCATOR_INVALID"
    )
    if locator["base"] != "repository_root":
        raise TCBContractError("INVOCATION_LOCATOR_INVALID")
    _relative_components(locator["path"], "INVOCATION_LOCATOR_INVALID")
    return locator


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


def _physical_identity(identity: os.stat_result) -> FileIdentity:
    """Return the injectable physical file identity used by admission."""

    return (identity.st_dev, identity.st_ino)


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


def _pipe_endpoint_state(descriptor: int, expected_access: int) -> Tuple[Any, ...]:
    """Capture one valid non-inheritable FIFO endpoint state."""

    try:
        identity = os.fstat(descriptor)
        flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
        inheritable = os.get_inheritable(descriptor)
    except BaseException:
        raise TCBContractError("ENTRYPOINT_TRANSPORT_IO_FAILED")
    if (
        not stat.S_ISFIFO(identity.st_mode)
        or flags & os.O_ACCMODE != expected_access
        or inheritable
    ):
        raise TCBContractError("ENTRYPOINT_TRANSPORT_IO_FAILED")
    return (
        _physical_identity(identity),
        stat.S_IFMT(identity.st_mode),
        flags & os.O_ACCMODE,
        inheritable,
    )


def _verify_pipe_endpoint_state(
    descriptor: int, expected: Tuple[Any, ...], expected_access: int
) -> None:
    """Fail closed if a critical endpoint changed after initial admission."""

    try:
        observed = _pipe_endpoint_state(descriptor, expected_access)
    except TCBContractError:
        raise TCBContractError("ENTRYPOINT_TRANSPORT_SUBSTITUTED")
    except BaseException:
        raise TCBContractError("ENTRYPOINT_TRANSPORT_SUBSTITUTED")
    if observed != expected:
        raise TCBContractError("ENTRYPOINT_TRANSPORT_SUBSTITUTED")


def _verify_atomic_entrypoint_snapshot(data: bytes) -> None:
    """Prove the bounded pre-spawn pipe primitive from cached admitted bytes.

    This does not prove a future launcher's identity.  It proves only that the
    declared non-empty snapshot fits the pinned atomic bound, is written in
    one complete write before any child could exist, and is read back exactly
    after the writer has been closed.
    """

    if type(data) is not bytes:
        raise TCBContractError("ENTRYPOINT_TRANSPORT_INVALID")
    if not data or len(data) > MAX_ATOMIC_ENTRYPOINT_BYTES:
        raise TCBContractError("ENTRYPOINT_TRANSPORT_SIZE_LIMIT")

    descriptors: List[int] = []
    primary: Optional[TCBContractError] = None
    observed = b""
    try:
        pair = os.pipe()
        if type(pair) is tuple:
            for item in pair:
                if (
                    type(item) is int
                    and item >= 0
                    and item not in descriptors
                ):
                    descriptors.append(item)
        if (
            type(pair) is not tuple
            or len(pair) != 2
            or any(type(item) is not int or item < 3 for item in pair)
            or pair[0] == pair[1]
        ):
            raise TCBContractError("ENTRYPOINT_TRANSPORT_IO_FAILED")
        read_descriptor, write_descriptor = pair
        read_state = _pipe_endpoint_state(read_descriptor, os.O_RDONLY)
        write_state = _pipe_endpoint_state(write_descriptor, os.O_WRONLY)
        pipe_buf = os.fpathconf(write_descriptor, "PC_PIPE_BUF")
        if type(pipe_buf) is not int or pipe_buf < MAX_ATOMIC_ENTRYPOINT_BYTES:
            raise TCBContractError("ENTRYPOINT_TRANSPORT_SIZE_LIMIT")
        _verify_pipe_endpoint_state(
            read_descriptor, read_state, os.O_RDONLY
        )
        _verify_pipe_endpoint_state(
            write_descriptor, write_state, os.O_WRONLY
        )
        written = os.write(write_descriptor, data)
        if type(written) is not int or written != len(data):
            raise TCBContractError("ENTRYPOINT_TRANSPORT_IO_FAILED")
        _verify_pipe_endpoint_state(
            read_descriptor, read_state, os.O_RDONLY
        )
        _verify_pipe_endpoint_state(
            write_descriptor, write_state, os.O_WRONLY
        )

        # A writer is attempted exactly once.  The future launcher may spawn
        # only after this close returns successfully.
        descriptors.remove(write_descriptor)
        try:
            os.close(write_descriptor)
        except BaseException:
            raise TCBContractError("ENTRYPOINT_TRANSPORT_CLOSE_FAILED")

        chunks: List[bytes] = []
        remaining = len(data)
        while remaining:
            _verify_pipe_endpoint_state(
                read_descriptor, read_state, os.O_RDONLY
            )
            chunk = os.read(read_descriptor, remaining)
            _verify_pipe_endpoint_state(
                read_descriptor, read_state, os.O_RDONLY
            )
            if type(chunk) is not bytes or not chunk:
                raise TCBContractError("ENTRYPOINT_TRANSPORT_IO_FAILED")
            chunks.append(chunk)
            remaining -= len(chunk)
        _verify_pipe_endpoint_state(
            read_descriptor, read_state, os.O_RDONLY
        )
        extra = os.read(read_descriptor, 1)
        _verify_pipe_endpoint_state(
            read_descriptor, read_state, os.O_RDONLY
        )
        if type(extra) is not bytes or extra:
            raise TCBContractError("ENTRYPOINT_TRANSPORT_IO_FAILED")
        observed = b"".join(chunks)
        if observed != data:
            raise TCBContractError("ENTRYPOINT_TRANSPORT_BINDING_MISMATCH")
    except TCBContractError as error:
        primary = error
    except BaseException:
        primary = TCBContractError("ENTRYPOINT_TRANSPORT_IO_FAILED")
    finally:
        primary = _close_descriptors_once(
            descriptors, primary, "ENTRYPOINT_TRANSPORT_CLOSE_FAILED"
        )
    if primary is not None:
        raise primary


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
    *,
    identity_out: Optional[List[FileIdentity]] = None,
    known_identities: Optional[Mapping[FileIdentity, Any]] = None,
    alias_code: str = "PHYSICAL_IDENTITY_ALIAS",
) -> None:
    """Verify one stable rooted directory without following any component."""

    components = _relative_components(relative_path, code)
    if type(root_descriptor) is not int or root_descriptor < 0:
        raise TCBContractError(code)
    descriptors: List[int] = []
    links: List[Tuple[int, str, int, Tuple[int, ...]]] = []
    candidate_identity: Optional[FileIdentity] = None
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
            if current == root_descriptor or current in descriptors:
                raise TCBContractError(code)
            descriptors.append(current)
            current_stat = os.fstat(current)
            if not stat.S_ISDIR(current_stat.st_mode):
                raise TCBContractError(code)
            links.append((parent, component, current, _metadata(current_stat)))
        _verify_open_directory_links(
            links, code, strict_metadata=True
        )
        final_stat = os.fstat(current)
        if not stat.S_ISDIR(final_stat.st_mode):
            raise TCBContractError(code)
        candidate_identity = _physical_identity(final_stat)
        if (
            known_identities is not None
            and candidate_identity in known_identities
        ):
            raise TCBContractError(alias_code)
    except TCBContractError as error:
        primary = error
    except BaseException:
        primary = TCBContractError(code)
    finally:
        primary = _close_descriptors_once(descriptors, primary, code)
    if primary is not None:
        raise primary
    if identity_out is not None:
        if candidate_identity is None:
            raise TCBContractError(code)
        identity_out.append(candidate_identity)


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
    known_identities: Optional[Mapping[FileIdentity, Any]] = None,
    alias_code: str = "PHYSICAL_IDENTITY_ALIAS",
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
        leaf_identity = _physical_identity(leaf_before)
        if known_identities is not None and leaf_identity in known_identities:
            raise TCBContractError(alias_code)
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
        identity_out.append(_physical_identity(leaf_before))
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


def canonical_envelope_bytes(value: Any) -> bytes:
    """Return the canonical execution-envelope encoding."""

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii", errors="strict") + b"\n"
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError):
        raise TCBContractError("EXECUTION_ENVELOPE_INVALID")
    if len(encoded) > MAX_JSON_INPUT_BYTES:
        raise TCBContractError("INPUT_SIZE_LIMIT")
    return encoded


def envelope_digest(canonical_bytes: bytes) -> str:
    """Return the v4 domain-separated canonical envelope digest."""

    if type(canonical_bytes) is not bytes:
        raise TCBContractError("INVALID_TYPE")
    return hashlib.sha256(
        _ENVELOPE_DOMAIN
        + b"\x00"
        + len(canonical_bytes).to_bytes(8, "big")
        + canonical_bytes
    ).hexdigest()


def execution_envelope_digest(canonical_bytes: bytes) -> str:
    """Named public helper for the execution-envelope framed digest."""

    return envelope_digest(canonical_bytes)


def canonical_runtime_acceptance_bytes(value: Any) -> bytes:
    """Return the canonical external runtime-acceptance encoding."""

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii", errors="strict") + b"\n"
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError):
        raise TCBContractError("RUNTIME_ACCEPTANCE_MALFORMED")
    if len(encoded) > MAX_JSON_INPUT_BYTES:
        raise TCBContractError("INPUT_SIZE_LIMIT")
    return encoded


def runtime_acceptance_digest(canonical_bytes: bytes) -> str:
    """Return the external runtime-acceptance framed digest."""

    if type(canonical_bytes) is not bytes:
        raise TCBContractError("INVALID_TYPE")
    return hashlib.sha256(
        _RUNTIME_ACCEPTANCE_DOMAIN
        + b"\x00"
        + len(canonical_bytes).to_bytes(8, "big")
        + canonical_bytes
    ).hexdigest()


def _validate_contract_bytes(contract_bytes: bytes) -> Tuple[Dict[str, Any], str]:
    contract = _require_object(
        parse_json_bytes(contract_bytes), _CONTRACT_FIELDS, "CONTRACT_INVALID"
    )
    if (
        _require_string(contract["contract_schema"], "CONTRACT_INVALID")
        != CONTRACT_SCHEMA
        or _require_string(contract["contract_version"], "CONTRACT_INVALID")
        != CONTRACT_VERSION
        or _require_positive_int(
            contract["contract_generation"], "CONTRACT_INVALID"
        )
        != CONTRACT_GENERATION
        or _require_positive_int(
            contract["protocol_generation"], "CONTRACT_INVALID"
        )
        != PROTOCOL_GENERATION
    ):
        raise TCBContractError("CONTRACT_IDENTITY_MISMATCH")
    status_policy = _require_object(
        contract["status_policy"], _STATUS_POLICY_FIELDS, "CONTRACT_INVALID"
    )
    blockers = _require_list(
        status_policy["blockers"], "CONTRACT_INVALID", 32
    )
    expected_status = {
        "contract_state": "ready_for_review",
        "executable_implementation_identity": "unproven_preserved",
        "executable_tcb_admission": "not_granted",
        "m1a_state": "blocked",
        "m1b_1a_provider_execution": "not_started",
        "m1b_state": "not_evaluated",
        "m2_state": "forbidden",
        "owner_freeze": "accepted",
        "stable_read_hardening": "accepted",
    }
    if tuple(blockers) != _REQUIRED_STATUS_BLOCKERS or any(
        status_policy[field] != expected
        for field, expected in expected_status.items()
    ):
        raise TCBContractError("CONTRACT_IDENTITY_MISMATCH")
    envelope_policy = contract["execution_envelope"]
    runtime_policy = contract["runtime_acceptance"]
    implementation_policy = contract["implementation_acceptance"]
    if (
        type(envelope_policy) is not dict
        or type(runtime_policy) is not dict
        or type(implementation_policy) is not dict
    ):
        raise TCBContractError("CONTRACT_INVALID")
    plan_policy = envelope_policy.get("execution_plan")
    if type(plan_policy) is not dict:
        raise TCBContractError("CONTRACT_INVALID")
    if (
        envelope_policy.get("envelope_schema") != EXECUTION_ENVELOPE_SCHEMA
        or envelope_policy.get("envelope_generation")
        != EXECUTION_ENVELOPE_GENERATION
        or envelope_policy.get("digest_domain")
        != _ENVELOPE_DOMAIN.decode("ascii")
        or plan_policy.get("schema") != EXECUTION_PLAN_SCHEMA
        or plan_policy.get("generation") != EXECUTION_PLAN_GENERATION
        or plan_policy.get("launcher_blockers")
        != list(_PLAN_LAUNCHER_BLOCKERS)
        or plan_policy.get("provider_entrypoint_source_eligibility")
        != _PROVIDER_SOURCE_ELIGIBILITY_POLICY
        or envelope_policy.get("file_purpose_compatibility")
        != _FILE_PURPOSE_COMPATIBILITY
        or runtime_policy.get("schema") != RUNTIME_ACCEPTANCE_SCHEMA
        or runtime_policy.get("generation") != RUNTIME_ACCEPTANCE_GENERATION
        or runtime_policy.get("envelope_digest_domain")
        != _ENVELOPE_DOMAIN.decode("ascii")
        or runtime_policy.get("fields") != list(_RUNTIME_ACCEPTANCE_FIELDS)
        or implementation_policy.get("fields") != list(_ACCEPTANCE_FIELDS)
    ):
        raise TCBContractError("CONTRACT_IDENTITY_MISMATCH")
    canonical = canonical_contract_bytes(contract)
    if canonical != contract_bytes:
        raise TCBContractError("CONTRACT_IDENTITY_MISMATCH")
    digest = contract_digest(canonical)
    if digest != EXPECTED_CONTRACT_SHA256:
        raise TCBContractError("CONTRACT_IDENTITY_MISMATCH")
    return contract, digest


def _verify_executable_identity(
    admitted_files: AdmittedFileIndex,
    relative_path: str,
    expected_sha256: str,
    total_bytes: int,
    *,
    purpose: str,
    hash_code: str = "EXECUTION_FILE_HASH_MISMATCH",
) -> Tuple[int, bool, AdmittedFile]:
    remaining = MAX_EXECUTABLE_TOTAL_BYTES - total_bytes
    if remaining < 0:
        raise TCBContractError("EXECUTABLE_TOTAL_SIZE_LIMIT")
    limit = min(MAX_EXECUTABLE_FILE_BYTES, remaining)
    size_code = (
        "EXECUTABLE_FILE_SIZE_LIMIT"
        if remaining >= MAX_EXECUTABLE_FILE_BYTES
        else "EXECUTABLE_TOTAL_SIZE_LIMIT"
    )
    entry, added = admitted_files.admit_executable(
        relative_path,
        expected_sha256,
        limit,
        purpose=purpose,
        size_code=size_code,
        hash_code=hash_code,
    )
    return total_bytes + (len(entry.data) if added else 0), added, entry


def _validate_manifest_bytes(
    manifest_bytes: bytes,
    admitted_files: AdmittedFileIndex,
    record_paths: Sequence[str],
    total_bytes: int,
) -> Tuple[Dict[str, Any], str, int, int, Dict[str, AdmittedFile]]:
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
    manifest_bindings: Dict[str, AdmittedFile] = {}
    role_by_path = {
        row["path"]: row["role"] for row in manifest["files"]
    }
    for path, digest in prepared:
        try:
            total_bytes, added, entry = _verify_executable_identity(
                admitted_files,
                path,
                digest,
                total_bytes,
                purpose="manifest_role:{}".format(role_by_path[path]),
                hash_code="MANIFEST_FILE_HASH_MISMATCH",
            )
        except TCBContractError:
            raise
        manifest_bindings[role_by_path[path]] = entry
        if added:
            executable_count += 1
    return (
        manifest,
        manifest_digest(canonical),
        total_bytes,
        executable_count,
        manifest_bindings,
    )


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
    admitted_files: AdmittedFileIndex,
    total_bytes: int,
) -> Tuple[Dict[str, Any], int, AdmittedFile]:
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
    repository_locator = _require_string(
        interpreter["repository_locator"], "RUNTIME_IDENTITY_INVALID"
    )
    _relative_components(repository_locator, "RUNTIME_IDENTITY_INVALID")
    executable_sha256 = _require_digest(
        interpreter["executable_sha256"], "RUNTIME_IDENTITY_INVALID"
    )
    total_bytes, _added, entry = _verify_executable_identity(
        admitted_files,
        repository_locator,
        executable_sha256,
        total_bytes,
        purpose="interpreter",
    )
    return interpreter, total_bytes, entry


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
    if flags != expected:
        raise TCBContractError("INVOCATION_FLAGS_MISMATCH")
    return flags


def _validate_execution_plan_shape(value: Any) -> Dict[str, Any]:
    plan = _require_object(value, _EXECUTION_PLAN_FIELDS, "EXECUTION_PLAN_INVALID")
    if (
        plan["plan_schema"] != EXECUTION_PLAN_SCHEMA
        or _require_positive_int(
            plan["plan_generation"], "EXECUTION_PLAN_INVALID"
        )
        != EXECUTION_PLAN_GENERATION
    ):
        raise TCBContractError("EXECUTION_PLAN_INVALID")

    interpreter = _require_object(
        plan["interpreter"],
        _PLAN_INTERPRETER_FIELDS,
        "EXECUTION_PLAN_INVALID",
    )
    _relative_components(
        interpreter["repository_locator"], "EXECUTION_PLAN_INVALID"
    )
    _require_digest(interpreter["sha256"], "EXECUTION_PLAN_INVALID")

    entrypoint = _require_object(
        plan["entrypoint"],
        _PLAN_ENTRYPOINT_FIELDS,
        "EXECUTION_PLAN_INVALID",
    )
    if (
        entrypoint["mode"] != "descriptor_script_file"
        or entrypoint["role"] != "provider_request_harness"
    ):
        raise TCBContractError("EXECUTION_PLAN_ENTRYPOINT_MISMATCH")
    _relative_components(
        entrypoint["repository_locator"],
        "EXECUTION_PLAN_ENTRYPOINT_MISMATCH",
    )
    if entrypoint["repository_locator"].startswith("-"):
        raise TCBContractError("EXECUTION_PLAN_ENTRYPOINT_MISMATCH")
    _require_digest(
        entrypoint["sha256"], "EXECUTION_PLAN_ENTRYPOINT_MISMATCH"
    )

    launcher = _require_object(
        plan["launcher"], _PLAN_LAUNCHER_FIELDS, "LAUNCHER_POLICY_INVALID"
    )
    blockers = _require_list(
        launcher["blockers"], "LAUNCHER_POLICY_INVALID", 8
    )
    if (
        launcher["status"] != "unproven"
        or tuple(blockers) != _PLAN_LAUNCHER_BLOCKERS
    ):
        raise TCBContractError("LAUNCHER_POLICY_INVALID")

    raw_roles = _require_list(
        plan["role_imports"], "EXECUTION_PLAN_INVALID", MAX_SEQUENCE_ENTRIES
    )
    if len(raw_roles) != len(_REQUIRED_IMPORTED_ROLES):
        raise TCBContractError("EXECUTION_PLAN_ROLE_BINDING_MISMATCH")
    modules: Set[str] = set()
    paths: Set[str] = set()
    observed_roles: List[str] = []
    for raw in raw_roles:
        row = _require_object(
            raw,
            _PLAN_ROLE_IMPORT_FIELDS,
            "EXECUTION_PLAN_INVALID",
        )
        role = _require_string(
            row["role"], "EXECUTION_PLAN_ROLE_BINDING_MISMATCH"
        )
        observed_roles.append(role)
        if row["kind"] != "source":
            raise TCBContractError("EXECUTION_PLAN_ROLE_BINDING_MISMATCH")
        module = _require_string(
            row["module"], "EXECUTION_PLAN_ROLE_BINDING_MISMATCH"
        )
        if _MODULE.fullmatch(module) is None or module in modules:
            raise TCBContractError("EXECUTION_PLAN_ROLE_BINDING_MISMATCH")
        modules.add(module)
        path = _require_string(
            row["path"], "EXECUTION_PLAN_ROLE_BINDING_MISMATCH"
        )
        _relative_components(path, "EXECUTION_PLAN_ROLE_BINDING_MISMATCH")
        if path in paths or path == entrypoint["repository_locator"]:
            raise TCBContractError("EXECUTION_PLAN_ROLE_BINDING_MISMATCH")
        paths.add(path)
        _require_digest(
            row["sha256"], "EXECUTION_PLAN_ROLE_BINDING_MISMATCH"
        )
    if tuple(observed_roles) != _REQUIRED_IMPORTED_ROLES:
        raise TCBContractError("EXECUTION_PLAN_ROLE_BINDING_MISMATCH")
    return plan


def _validate_invocation(
    value: Any,
    interpreter: Mapping[str, Any],
    interpreter_entry: AdmittedFile,
    plan: Mapping[str, Any],
    manifest_bindings: Mapping[str, AdmittedFile],
    admitted_files: AdmittedFileIndex,
    bytecode: Mapping[str, Any],
    environment: Mapping[str, Any],
) -> Tuple[Dict[str, Any], Tuple[str, ...]]:
    invocation = _require_object(
        value, _INVOCATION_FIELDS, "INVOCATION_POLICY_INVALID"
    )
    if invocation["mode"] != "typed_entrypoint_fd_no_repository_reopen":
        raise TCBContractError("INVOCATION_POLICY_INVALID")
    _validate_python_flags(invocation["python_flags"])

    argv0 = _validate_repository_locator(invocation["argv0"])
    os_exec_target = _validate_repository_locator(
        invocation["os_exec_target"]
    )
    interpreter_locator = interpreter["repository_locator"]
    if (
        argv0["path"] != interpreter_locator
        or os_exec_target["path"] != interpreter_locator
        or plan["interpreter"]["repository_locator"] != interpreter_locator
    ):
        raise TCBContractError("INVOCATION_INTERPRETER_MISMATCH")
    if (
        admitted_files.lookup_exact(
            argv0["path"],
            interpreter["executable_sha256"],
            "INVOCATION_INTERPRETER_MISMATCH",
            purpose="invocation_argv0",
        )
        is not interpreter_entry
        or admitted_files.lookup_exact(
            os_exec_target["path"],
            interpreter["executable_sha256"],
            "INVOCATION_INTERPRETER_MISMATCH",
            purpose="invocation_os_exec_target",
        )
        is not interpreter_entry
    ):
        raise TCBContractError("INVOCATION_INTERPRETER_MISMATCH")

    argv_tail = _require_list(
        invocation["argv_tail"],
        "INVOCATION_ARGV_GRAMMAR_INVALID",
        MAX_SEQUENCE_ENTRIES,
    )
    for argument in argv_tail:
        _require_ascii_text(
            argument, "INVOCATION_ARGV_GRAMMAR_INVALID", allow_empty=True
        )
    if tuple(argv_tail) == (
        "-I",
        "-S",
        "-X",
        "utf8",
        "/dev/fd/3",
    ):
        raise TCBContractError("INVOCATION_FLAGS_MISMATCH")
    if (
        len(argv_tail) == 6
        and argv_tail[-1]
        in {entry.path for entry in manifest_bindings.values()}
    ):
        raise TCBContractError("INVOCATION_ENTRYPOINT_MISMATCH")
    if tuple(argv_tail) != (
        "-I",
        "-S",
        "-B",
        "-X",
        "utf8",
        "/dev/fd/3",
    ):
        raise TCBContractError("INVOCATION_ARGV_GRAMMAR_INVALID")

    cwd = _validate_repository_locator(invocation["cwd"])

    sys_path_rows = _require_list(
        invocation["sys_path"],
        "INVOCATION_POLICY_INVALID",
        MAX_SEQUENCE_ENTRIES,
    )
    sys_paths: List[str] = []
    for raw_locator in sys_path_rows:
        locator = _validate_repository_locator(raw_locator)
        sys_paths.append(locator["path"])
    if len(sys_paths) != len(set(sys_paths)):
        raise TCBContractError("INVOCATION_SYS_PATH_INVALID")

    fd_rows = _require_list(
        invocation["inherited_fds"],
        "ENTRYPOINT_TRANSPORT_REQUIRED",
        MAX_SEQUENCE_ENTRIES,
    )
    if len(fd_rows) != 1:
        raise TCBContractError("ENTRYPOINT_TRANSPORT_REQUIRED")
    fd_row = _require_object(
        fd_rows[0], _INHERITED_FD_FIELDS, "ENTRYPOINT_TRANSPORT_INVALID"
    )
    child_fd = _require_nonnegative_int(
        fd_row["child_fd"], "ENTRYPOINT_TRANSPORT_FD_MISMATCH"
    )
    byte_count = _require_positive_int(
        fd_row["byte_count"], "ENTRYPOINT_TRANSPORT_SIZE_LIMIT"
    )
    provider_entry = manifest_bindings.get("provider_request_harness")
    entrypoint = plan["entrypoint"]
    if provider_entry is None:
        raise TCBContractError("ENTRYPOINT_TRANSPORT_BINDING_MISMATCH")
    supplied_digest = _require_digest(
        fd_row["sha256"], "ENTRYPOINT_TRANSPORT_BINDING_MISMATCH"
    )
    supplied_locator = _require_string(
        fd_row["repository_locator"],
        "ENTRYPOINT_TRANSPORT_BINDING_MISMATCH",
    )
    _relative_components(
        supplied_locator, "ENTRYPOINT_TRANSPORT_BINDING_MISMATCH"
    )
    if (
        child_fd != 3
        or fd_row["process_path"] != "/dev/fd/3"
        or child_fd in (0, 1, 2)
    ):
        raise TCBContractError("ENTRYPOINT_TRANSPORT_FD_MISMATCH")
    if (
        fd_row["mode"] != "read"
        or fd_row["purpose"] != "provider_request_harness"
        or fd_row["role"] != "provider_request_harness"
        or fd_row["transport"] != "darwin_pipe_atomic_preload_v1"
    ):
        raise TCBContractError("ENTRYPOINT_TRANSPORT_INVALID")
    if (
        supplied_locator != provider_entry.path
        or supplied_locator != entrypoint["repository_locator"]
        or supplied_digest != provider_entry.sha256
        or supplied_digest != entrypoint["sha256"]
        or byte_count != len(provider_entry.data)
    ):
        raise TCBContractError("ENTRYPOINT_TRANSPORT_BINDING_MISMATCH")
    if byte_count > MAX_ATOMIC_ENTRYPOINT_BYTES:
        raise TCBContractError("ENTRYPOINT_TRANSPORT_SIZE_LIMIT")
    if (
        admitted_files.lookup_exact(
            supplied_locator,
            supplied_digest,
            "ENTRYPOINT_TRANSPORT_BINDING_MISMATCH",
            purpose="entrypoint_transport",
        )
        is not provider_entry
    ):
        raise TCBContractError("ENTRYPOINT_TRANSPORT_BINDING_MISMATCH")
    _verify_atomic_entrypoint_snapshot(provider_entry.data)

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
    if invocation["warnoptions"] != [] or invocation["xoptions"] != ["utf8"]:
        raise TCBContractError("INVOCATION_FLAGS_MISMATCH")
    if (
        bytecode.get("dont_write_bytecode") is not True
        or environment.get("ambient_inheritance") is not False
        or environment.get("policy") != "empty"
        or environment.get("variables") != []
    ):
        raise TCBContractError("INVOCATION_FLAGS_MISMATCH")
    return invocation, tuple(sys_paths)


def _validate_execution_plan_primary_bindings(
    plan: Mapping[str, Any],
    interpreter: Mapping[str, Any],
    interpreter_entry: AdmittedFile,
    manifest_bindings: Mapping[str, AdmittedFile],
    admitted_files: AdmittedFileIndex,
) -> None:
    plan_interpreter = plan["interpreter"]
    if (
        plan_interpreter["repository_locator"]
        != interpreter["repository_locator"]
        or plan_interpreter["sha256"] != interpreter["executable_sha256"]
        or admitted_files.lookup_exact(
            plan_interpreter["repository_locator"],
            plan_interpreter["sha256"],
            "EXECUTION_PLAN_INTERPRETER_MISMATCH",
            purpose="plan_interpreter",
        )
        is not interpreter_entry
    ):
        raise TCBContractError("EXECUTION_PLAN_INTERPRETER_MISMATCH")

    provider_entry = manifest_bindings.get("provider_request_harness")
    entrypoint = plan["entrypoint"]
    if (
        provider_entry is None
        or entrypoint["repository_locator"] != provider_entry.path
        or entrypoint["sha256"] != provider_entry.sha256
        or admitted_files.lookup_exact(
            entrypoint["repository_locator"],
            entrypoint["sha256"],
            "EXECUTION_PLAN_ENTRYPOINT_MISMATCH",
            purpose="plan_entrypoint",
        )
        is not provider_entry
    ):
        raise TCBContractError("EXECUTION_PLAN_ENTRYPOINT_MISMATCH")


def _validate_execution_plan_bindings(
    plan: Mapping[str, Any],
    interpreter: Mapping[str, Any],
    interpreter_entry: AdmittedFile,
    manifest_bindings: Mapping[str, AdmittedFile],
    imports: Sequence[Mapping[str, Any]],
    import_bindings: Sequence[AdmittedFile],
    admitted_files: AdmittedFileIndex,
) -> None:
    _validate_execution_plan_primary_bindings(
        plan,
        interpreter,
        interpreter_entry,
        manifest_bindings,
        admitted_files,
    )

    if len(imports) != len(import_bindings):
        raise TCBContractError("EXECUTION_PLAN_IMPORT_BINDING_MISMATCH")
    role_by_entry = {
        id(entry): role for role, entry in manifest_bindings.items()
    }
    observed_manifest_roles: List[str] = []
    for import_row, import_entry in zip(imports, import_bindings):
        role = role_by_entry.get(id(import_entry))
        if role is not None:
            if role == "provider_request_harness":
                raise TCBContractError("EXECUTION_PLAN_IMPORT_BINDING_MISMATCH")
            observed_manifest_roles.append(role)

    if tuple(observed_manifest_roles) != _REQUIRED_IMPORTED_ROLES:
        raise TCBContractError("EXECUTION_PLAN_IMPORT_BINDING_MISMATCH")

    for plan_row in plan["role_imports"]:
        role = plan_row["role"]
        manifest_entry = manifest_bindings.get(role)
        if (
            manifest_entry is None
            or plan_row["path"] != manifest_entry.path
            or plan_row["sha256"] != manifest_entry.sha256
            or admitted_files.lookup_exact(
                plan_row["path"],
                plan_row["sha256"],
                "EXECUTION_PLAN_ROLE_BINDING_MISMATCH",
                purpose="plan_role_import:{}:{}".format(
                    role, plan_row["module"]
                ),
            )
            is not manifest_entry
        ):
            raise TCBContractError("EXECUTION_PLAN_ROLE_BINDING_MISMATCH")
        expected_import = {
            "kind": "source",
            "module": plan_row["module"],
            "path": plan_row["path"],
            "sha256": plan_row["sha256"],
        }
        matches = [
            index
            for index, import_row in enumerate(imports)
            if import_row == expected_import
        ]
        if (
            len(matches) != 1
            or import_bindings[matches[0]] is not manifest_entry
        ):
            raise TCBContractError("EXECUTION_PLAN_IMPORT_BINDING_MISMATCH")


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
    admitted_files: AdmittedFileIndex,
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
        total_bytes, _added, _entry = _verify_executable_identity(
            admitted_files,
            path,
            digest,
            total_bytes,
            purpose="native_dependency:{}".format(install_name),
        )
    return native, total_bytes


def _validate_imports(
    value: Any,
    interpreter_sha256: str,
    interpreter_entry: AdmittedFile,
    sys_paths: Sequence[str],
    admitted_files: AdmittedFileIndex,
    total_bytes: int,
) -> Tuple[List[Dict[str, Any]], int, List[AdmittedFile]]:
    raw_rows = _require_list(
        value, "IMPORT_CLOSURE_INVALID", MAX_IMPORT_ENTRIES
    )
    prepared_modules: Set[str] = set()
    prepared_paths: Set[str] = set()
    for raw in raw_rows:
        row = _require_object(raw, _IMPORT_FIELDS, "IMPORT_CLOSURE_INVALID")
        kind = _require_string(row["kind"], "IMPORT_CLOSURE_INVALID")
        if kind not in ("builtin", "extension", "frozen", "source"):
            raise TCBContractError("IMPORT_CLOSURE_INVALID")
        module = _require_string(row["module"], "IMPORT_CLOSURE_INVALID")
        if _MODULE.fullmatch(module) is None or module in prepared_modules:
            raise TCBContractError("IMPORT_CLOSURE_INVALID")
        prepared_modules.add(module)
        _require_digest(row["sha256"], "IMPORT_CLOSURE_INVALID")
        if kind in ("builtin", "frozen"):
            if row["path"] is not None:
                raise TCBContractError("IMPORT_CLOSURE_INVALID")
        else:
            path = _require_string(row["path"], "IMPORT_CLOSURE_INVALID")
            _relative_components(path, "IMPORT_CLOSURE_INVALID")
            if path in prepared_paths:
                raise TCBContractError("IMPORT_CLOSURE_INVALID")
            prepared_paths.add(path)
    rows: List[Dict[str, Any]] = []
    bindings: List[AdmittedFile] = []
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
            entry = admitted_files.lookup_exact(
                interpreter_entry.path,
                interpreter_sha256,
                "IMPORT_CLOSURE_INVALID",
                purpose="import:{}:{}".format(kind, module),
            )
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
            total_bytes, _added, entry = _verify_executable_identity(
                admitted_files,
                path,
                digest,
                total_bytes,
                purpose="import:{}:{}".format(kind, module),
            )
        rows.append(row)
        bindings.append(entry)
    if used_sys_paths != set(sys_paths):
        raise TCBContractError("IMPORT_CLOSURE_INVALID")
    return rows, total_bytes, bindings


def _validate_execution_state(
    value: Any,
    root_descriptor: int,
    admitted_files: AdmittedFileIndex,
    manifest_bindings: Mapping[str, AdmittedFile],
    total_bytes: int,
) -> Tuple[Dict[str, Any], int, int]:
    if (
        type(value) is dict
        and set(value) == set(_STATE_FIELDS) - {"execution_plan"}
    ):
        raise TCBContractError("EXECUTION_PLAN_INVALID")
    state = _require_object(value, _STATE_FIELDS, "EXECUTION_ENVELOPE_INVALID")
    bytecode = _validate_bytecode(state["bytecode"])
    environment = _validate_environment(state["environment"])
    plan = _validate_execution_plan_shape(state["execution_plan"])
    interpreter, total_bytes, interpreter_entry = _validate_interpreter(
        state["interpreter"], admitted_files, total_bytes
    )
    _validate_execution_plan_primary_bindings(
        plan,
        interpreter,
        interpreter_entry,
        manifest_bindings,
        admitted_files,
    )
    invocation, sys_paths = _validate_invocation(
        state["invocation"],
        interpreter,
        interpreter_entry,
        plan,
        manifest_bindings,
        admitted_files,
        bytecode,
        environment,
    )
    admitted_directories = AdmittedDirectoryIndex(root_descriptor)
    admitted_directories.admit(
        invocation["cwd"]["path"], "cwd", "INVOCATION_CWD_INVALID"
    )
    for path in sys_paths:
        admitted_directories.admit(
            path, "sys_path", "INVOCATION_SYS_PATH_INVALID"
        )
    if state["imports"] == []:
        raise TCBContractError("EXECUTION_PLAN_IMPORT_BINDING_MISMATCH")
    imports, total_bytes, import_bindings = _validate_imports(
        state["imports"],
        interpreter["executable_sha256"],
        interpreter_entry,
        sys_paths,
        admitted_files,
        total_bytes,
    )
    _validate_execution_plan_bindings(
        plan,
        interpreter,
        interpreter_entry,
        manifest_bindings,
        imports,
        import_bindings,
        admitted_files,
    )
    _native, total_bytes = _validate_native_dependencies(
        state["native_dependencies"],
        admitted_files,
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


def _validate_execution_envelope_identity(
    envelope_bytes: bytes,
    contract_sha256: str,
    manifest: Mapping[str, Any],
    manifest_sha256: str,
) -> Tuple[Dict[str, Any], str, str]:
    parsed_envelope = parse_json_bytes(envelope_bytes)
    envelope = _require_object(
        parsed_envelope,
        _ENVELOPE_FIELDS,
        "EXECUTION_ENVELOPE_INVALID",
    )
    canonical = canonical_envelope_bytes(envelope)
    if envelope_bytes != canonical:
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

    return (
        envelope,
        envelope_digest(canonical),
        hashlib.sha256(canonical).hexdigest(),
    )


def _validate_runtime_acceptance_record(
    runtime_acceptance_bytes: bytes,
    contract_sha256: str,
    manifest: Mapping[str, Any],
    manifest_sha256: str,
    envelope: Mapping[str, Any],
    envelope_sha256: str,
    envelope_raw_sha256: str,
) -> Dict[str, Any]:
    try:
        parsed = parse_json_bytes(runtime_acceptance_bytes)
    except TCBContractError as error:
        if error.code == "JSON_DUPLICATE_KEY":
            raise TCBContractError("RUNTIME_ACCEPTANCE_DUPLICATE_KEY")
        raise TCBContractError("RUNTIME_ACCEPTANCE_MALFORMED")
    if type(parsed) is not dict:
        raise TCBContractError("RUNTIME_ACCEPTANCE_MALFORMED")
    fields = set(parsed)
    required = set(_RUNTIME_ACCEPTANCE_FIELDS)
    if required - fields:
        raise TCBContractError("RUNTIME_ACCEPTANCE_FIELD_MISSING")
    if fields - required:
        raise TCBContractError("RUNTIME_ACCEPTANCE_FIELD_EXTRA")
    runtime_acceptance = parsed
    if runtime_acceptance_bytes != canonical_runtime_acceptance_bytes(
        runtime_acceptance
    ):
        raise TCBContractError("RUNTIME_ACCEPTANCE_NONCANONICAL")

    if runtime_acceptance["runtime_acceptance_schema"] != RUNTIME_ACCEPTANCE_SCHEMA:
        raise TCBContractError("RUNTIME_ACCEPTANCE_SCHEMA_MISMATCH")
    if (
        _require_positive_int(
            runtime_acceptance["runtime_acceptance_generation"],
            "RUNTIME_ACCEPTANCE_GENERATION_MISMATCH",
        )
        != RUNTIME_ACCEPTANCE_GENERATION
    ):
        raise TCBContractError("RUNTIME_ACCEPTANCE_GENERATION_MISMATCH")
    state = runtime_acceptance["runtime_acceptance_state"]
    if state == "proposed":
        raise TCBContractError("RUNTIME_ACCEPTANCE_STATE_PROPOSED")
    if state == "retired":
        raise TCBContractError("RUNTIME_ACCEPTANCE_STATE_RETIRED")
    if state == "proven":
        raise TCBContractError("RUNTIME_ACCEPTANCE_SELF_ASSERTED_PROVEN")
    if state != ACCEPTANCE_STATE:
        raise TCBContractError("RUNTIME_ACCEPTANCE_STATE_INVALID")

    for field in (
        "contract_generation",
        "envelope_generation",
        "implementation_generation",
        "protocol_generation",
    ):
        _require_positive_int(
            runtime_acceptance[field], "RUNTIME_ACCEPTANCE_MALFORMED"
        )
    supplied_contract_sha256 = _require_digest(
        runtime_acceptance["contract_sha256"],
        "RUNTIME_ACCEPTANCE_CONTRACT_DIGEST_MISMATCH",
    )
    supplied_manifest_sha256 = _require_digest(
        runtime_acceptance["manifest_sha256"],
        "RUNTIME_ACCEPTANCE_MANIFEST_DIGEST_MISMATCH",
    )
    supplied_envelope_sha256 = _require_digest(
        runtime_acceptance["envelope_sha256"],
        "RUNTIME_ACCEPTANCE_ENVELOPE_DIGEST_MISMATCH",
    )
    if runtime_acceptance["contract_schema"] != CONTRACT_SCHEMA:
        raise TCBContractError("RUNTIME_ACCEPTANCE_CONTRACT_SCHEMA_MISMATCH")
    if runtime_acceptance["contract_version"] != CONTRACT_VERSION:
        raise TCBContractError("RUNTIME_ACCEPTANCE_CONTRACT_VERSION_MISMATCH")
    if runtime_acceptance["contract_generation"] != CONTRACT_GENERATION:
        raise TCBContractError("RUNTIME_ACCEPTANCE_CONTRACT_GENERATION_MISMATCH")
    if supplied_contract_sha256 != contract_sha256:
        raise TCBContractError("RUNTIME_ACCEPTANCE_CONTRACT_DIGEST_MISMATCH")
    if runtime_acceptance["manifest_schema"] != MANIFEST_SCHEMA:
        raise TCBContractError("RUNTIME_ACCEPTANCE_MANIFEST_SCHEMA_MISMATCH")
    if supplied_manifest_sha256 != manifest_sha256:
        raise TCBContractError("RUNTIME_ACCEPTANCE_MANIFEST_DIGEST_MISMATCH")
    if (
        runtime_acceptance["implementation_generation"]
        != manifest["implementation_generation"]
    ):
        raise TCBContractError(
            "RUNTIME_ACCEPTANCE_IMPLEMENTATION_GENERATION_MISMATCH"
        )
    if runtime_acceptance["envelope_schema"] != EXECUTION_ENVELOPE_SCHEMA:
        raise TCBContractError("RUNTIME_ACCEPTANCE_ENVELOPE_SCHEMA_MISMATCH")
    if (
        runtime_acceptance["envelope_generation"]
        != EXECUTION_ENVELOPE_GENERATION
    ):
        raise TCBContractError("RUNTIME_ACCEPTANCE_ENVELOPE_GENERATION_MISMATCH")
    if runtime_acceptance["envelope_digest_domain"] != _ENVELOPE_DOMAIN.decode(
        "ascii"
    ):
        raise TCBContractError("RUNTIME_ACCEPTANCE_ENVELOPE_DOMAIN_MISMATCH")
    if (
        runtime_acceptance["envelope_digest_framing"]
        != _ENVELOPE_DIGEST_FRAMING
    ):
        raise TCBContractError("RUNTIME_ACCEPTANCE_ENVELOPE_FRAMING_MISMATCH")
    if supplied_envelope_sha256 == envelope_raw_sha256:
        raise TCBContractError("RUNTIME_ACCEPTANCE_ENVELOPE_RAW_SHA_FORBIDDEN")
    if supplied_envelope_sha256 != envelope_sha256:
        raise TCBContractError("RUNTIME_ACCEPTANCE_ENVELOPE_DIGEST_MISMATCH")
    if runtime_acceptance["protocol_generation"] != PROTOCOL_GENERATION:
        raise TCBContractError("RUNTIME_ACCEPTANCE_PROTOCOL_GENERATION_MISMATCH")
    if (
        envelope["envelope_schema"] != runtime_acceptance["envelope_schema"]
        or envelope["envelope_generation"]
        != runtime_acceptance["envelope_generation"]
    ):
        raise TCBContractError("RUNTIME_ACCEPTANCE_ENVELOPE_SCHEMA_MISMATCH")
    return runtime_acceptance


def _validate_execution_envelope_state(
    envelope: Mapping[str, Any],
    root_descriptor: int,
    admitted_files: AdmittedFileIndex,
    manifest_bindings: Mapping[str, AdmittedFile],
    total_bytes: int,
) -> Tuple[int, int]:
    if _semantic_json_bytes(envelope["admitted_state"]) != _semantic_json_bytes(
        envelope["observed_state"]
    ):
        raise TCBContractError("EXECUTION_STATE_MISMATCH")
    _admitted, total_bytes, import_entries = _validate_execution_state(
        envelope["admitted_state"],
        root_descriptor,
        admitted_files,
        manifest_bindings,
        total_bytes,
    )
    return total_bytes, import_entries


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
        codes = [
            code
            if type(code) is str and code in _ALLOWED_CODES
            else "UNEXPECTED_FAILURE"
        ]
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
    runtime_acceptance_bytes: bytes,
    admitted_files: AdmittedFileIndex,
    root_descriptor: int,
    contract_path: str,
    manifest_path: str,
    acceptance_path: str,
    envelope_path: str,
    runtime_acceptance_path: str,
) -> Dict[str, Any]:
    _contract, contract_sha256 = _validate_contract_bytes(contract_bytes)
    (
        manifest,
        manifest_sha256,
        total_bytes,
        _manifest_files,
        manifest_bindings,
    ) = (
        _validate_manifest_bytes(
            manifest_bytes,
            admitted_files,
            (
                contract_path,
                manifest_path,
                acceptance_path,
                envelope_path,
                runtime_acceptance_path,
            ),
            0,
        )
    )
    _validate_acceptance_record(acceptance_bytes, manifest, manifest_sha256)
    envelope, envelope_sha256, envelope_raw_sha256 = (
        _validate_execution_envelope_identity(
            envelope_bytes, contract_sha256, manifest, manifest_sha256
        )
    )
    _validate_runtime_acceptance_record(
        runtime_acceptance_bytes,
        contract_sha256,
        manifest,
        manifest_sha256,
        envelope,
        envelope_sha256,
        envelope_raw_sha256,
    )
    _total_bytes, import_entries = _validate_execution_envelope_state(
        envelope,
        root_descriptor,
        admitted_files,
        manifest_bindings,
        total_bytes,
    )
    executable_files = sum(
        not entry.is_record for entry in admitted_files.by_path.values()
    )
    return _result(
        "ok",
        contract_records=1,
        executable_files=executable_files,
        import_entries=import_entries,
        linkage_records=3,
    )


def verify_paths(
    contract_path: str,
    manifest_path: str,
    acceptance_path: str,
    envelope_path: str,
    runtime_acceptance_path: str,
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
        admitted_files = AdmittedFileIndex(root_descriptor)
        contract_entry = admitted_files.admit_record(
            contract_path, "contract_record"
        )
        _validate_contract_bytes(contract_entry.data)
        manifest_entry = admitted_files.admit_record(
            manifest_path, "manifest_record"
        )
        acceptance_entry = admitted_files.admit_record(
            acceptance_path, "implementation_acceptance_record"
        )
        envelope_entry = admitted_files.admit_record(
            envelope_path, "execution_envelope_record"
        )
        runtime_acceptance_entry = admitted_files.admit_record(
            runtime_acceptance_path,
            "runtime_acceptance_record",
            alias_code="RUNTIME_ACCEPTANCE_ALIAS_FORBIDDEN",
        )
        result = _verify_bytes_with_root(
            contract_entry.data,
            manifest_entry.data,
            acceptance_entry.data,
            envelope_entry.data,
            runtime_acceptance_entry.data,
            admitted_files,
            root_descriptor,
            contract_path,
            manifest_path,
            acceptance_path,
            envelope_path,
            runtime_acceptance_path,
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
        if type(argv) not in (list, tuple):
            raise TCBContractError("CLI_ARGUMENTS_INVALID")
        if len(argv) < 7:
            raise TCBContractError("CLI_ARGUMENT_MISSING")
        if len(argv) > 7:
            raise TCBContractError("CLI_ARGUMENT_EXTRA")
        if argv[0] != "verify" or any(type(value) is not str for value in argv):
            raise TCBContractError("CLI_ARGUMENTS_INVALID")
        return verify_paths(
            argv[1], argv[2], argv[3], argv[4], argv[5], argv[6]
        )
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
            or any(type(code) is not str or code not in _ALLOWED_CODES for code in codes)
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
