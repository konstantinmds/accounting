from __future__ import annotations

from enum import Enum


class DLQReason(str, Enum):
    INVALID_PATH = "invalid_path"
    TENANT_NOT_FOUND = "tenant_not_found"
    CASE_TENANT_MISMATCH = "case_tenant_mismatch"
    SNAPSHOT_FAILED = "snapshot_failed"
    UPSERT_FAILED = "upsert_failed"
    FILE_TOO_LARGE = "file_too_large"
    UNSUPPORTED_TYPE = "unsupported_type"
    FILE_CHANGED_OR_MISSING = "file_changed_or_missing"
    MOVE_FAILED = "move_failed"


class FileChangedError(RuntimeError):
    """Raised when a file changes during processing."""


class FileTooLargeError(RuntimeError):
    """Raised when a file exceeds the configured size limit."""
