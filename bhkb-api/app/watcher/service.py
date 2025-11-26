from __future__ import annotations

import json
import logging
import signal
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path

import psycopg
from minio import Minio
from prometheus_client import Counter, Histogram

from app.watcher.config import WatcherSettings
from app.watcher.db import (
    authorize_case,
    fetch_tenant_by_slug,
    open_conn,
    upsert_artifact_and_task,
    write_dead_letter,
)
from app.watcher.errors import DLQReason, FileChangedError, FileTooLargeError
from app.watcher.pathing import (
    ParsedPath,
    build_processed_path,
    is_ignored,
    is_stable,
    make_ignore_spec,
    match_path,
    resolve_and_validate,
    stream_sha256,
)
from app.watcher.snapshot import SnapshotError, build_raw_key, snapshot_file


FILES_SEEN = Counter("watcher_files_seen_total", "Files observed by watcher")
ARTIFACTS_CREATED = Counter(
    "watcher_artifacts_created_total",
    "Artifacts created by watcher",
    labelnames=("tenant",),
)
ERRORS_TOTAL = Counter(
    "watcher_errors_total",
    "Errors encountered by watcher",
    labelnames=("type",),
)
SCAN_SECONDS = Histogram("watcher_scan_seconds", "Scan processing time seconds")
SNAPSHOT_SECONDS = Histogram("watcher_snapshot_seconds", "Snapshot time seconds")


class Watcher:
    def __init__(self, settings: WatcherSettings, stop_event: threading.Event):
        self.settings = settings
        self.stop_event = stop_event
        self.logger = logging.getLogger("watcher")
        self.run_id = uuid.uuid4().hex
        self.first_seen: dict[Path, tuple[int, float, float]] = {}
        self.change_attempts: dict[Path, int] = {}
        ignore_patterns = settings.IGNORE_GLOB + f",{settings.PROCESSED_DIR_NAME}/**"
        self.ignore_spec = make_ignore_spec(ignore_patterns)
        endpoint = (settings.S3_ENDPOINT or "").replace("http://", "").replace("https://", "")
        self.minio = Minio(
            endpoint,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            secure=settings.S3_ENDPOINT.startswith("https") if settings.S3_ENDPOINT else False,
        )
        self.dsn = settings.DATABASE_URL
        self.executor = ThreadPoolExecutor(max_workers=settings.MAX_CONCURRENCY)
        self.processing_now: set[Path] = set()
        self.processing_lock = threading.Lock()

    def run_forever(self) -> None:
        while not self.stop_event.is_set():
            start = time.time()
            try:
                self.scan_once()
            except Exception as exc:  # pragma: no cover - catch-all to keep loop alive
                self.logger.exception("scan failed", extra={"run_id": self.run_id, "error": str(exc)})
            elapsed = time.time() - start
            # wait for next scan respecting stop_event
            self.stop_event.wait(timeout=max(0, self.settings.SCAN_INTERVAL_SECONDS - elapsed))
        self.executor.shutdown(wait=True)

    def scan_once(self) -> None:
        inbox_root = self.settings.INBOX_ROOT
        now = time.time()
        paths = [p for p in inbox_root.rglob("*") if p.is_file() and self.settings.PROCESSED_DIR_NAME not in p.parts]
        current_paths = set(paths)
        futures: list[Future] = []
        for path in paths:
            try:
                resolved = resolve_and_validate(path, inbox_root)
            except ValueError:
                # Path traversal attempt: send to DLQ
                self._dlq_direct(
                    target=str(path),
                    reason=DLQReason.INVALID_PATH,
                    error="path escapes inbox root",
                    blob={"path": str(path)},
                )
                continue

            if is_ignored(resolved, inbox_root, self.ignore_spec):
                continue

            if not resolved.exists():
                continue

            try:
                if not is_stable(self.first_seen, resolved, self.settings.FILE_STABLE_SECONDS, now):
                    continue
            except FileNotFoundError:
                continue

            with self.processing_lock:
                if resolved in self.processing_now:
                    continue
                self.processing_now.add(resolved)
            futures.append(self.executor.submit(self._process_file, resolved))

        for fut in futures:
            fut.result()

        stale = set(self.first_seen.keys()) - current_paths
        for p in stale:
            self.first_seen.pop(p, None)
            self.change_attempts.pop(p, None)

    def _process_file(self, path: Path) -> None:
        trace_id = uuid.uuid4().hex
        try:
            with SCAN_SECONDS.time():
                rel = path.relative_to(self.settings.INBOX_ROOT)
                parsed = match_path(f"inbox/{rel.as_posix()}")
                if not parsed:
                    self._dlq_direct(
                        target=str(rel),
                        reason=DLQReason.INVALID_PATH,
                        error="invalid path pattern",
                        blob={"relpath": rel.as_posix()},
                    )
                    self._log_event("invalid_path", trace_id, extra={"path": str(rel)})
                    return

                FILES_SEEN.inc()

                try:
                    sha256, size_bytes = stream_sha256(path, self.settings.MAX_FILE_BYTES)
                except FileTooLargeError as exc:
                    self._dlq_direct(
                        target=str(rel),
                        reason=DLQReason.FILE_TOO_LARGE,
                        error=str(exc),
                        blob={"size": path.stat().st_size if path.exists() else None},
                    )
                    ERRORS_TOTAL.labels(type=DLQReason.FILE_TOO_LARGE.value).inc()
                    return
                except FileChangedError:
                    attempts = self.change_attempts.get(path, 0) + 1
                    self.change_attempts[path] = attempts
                    if attempts >= self.settings.FILE_CHANGE_ATTEMPT_LIMIT:
                        self._dlq_direct(
                            target=str(rel),
                            reason=DLQReason.FILE_CHANGED_OR_MISSING,
                            error="file changed during hashing",
                            blob={"attempts": attempts},
                        )
                        ERRORS_TOTAL.labels(type=DLQReason.FILE_CHANGED_OR_MISSING.value).inc()
                    return
                except FileNotFoundError:
                    attempts = self.change_attempts.get(path, 0) + 1
                    self.change_attempts[path] = attempts
                    if attempts >= self.settings.FILE_CHANGE_ATTEMPT_LIMIT:
                        self._dlq_direct(
                            target=str(rel),
                            reason=DLQReason.FILE_CHANGED_OR_MISSING,
                            error="file missing during hashing",
                            blob={"attempts": attempts},
                        )
                        ERRORS_TOTAL.labels(type=DLQReason.FILE_CHANGED_OR_MISSING.value).inc()
                    return

                try:
                    conn = open_conn(self.dsn)
                except Exception as exc:  # pragma: no cover - defensive
                    self.logger.exception("db connect failed", extra={"run_id": self.run_id, "trace_id": trace_id, "error": str(exc)})
                    return

                tenant_id = None
                try:
                    tenant_id = fetch_tenant_by_slug(conn, parsed.tenant)
                    if not tenant_id:
                        self._dlq(conn, target=str(rel), reason=DLQReason.TENANT_NOT_FOUND, error="tenant not found", blob={"tenant": parsed.tenant})
                        ERRORS_TOTAL.labels(type=DLQReason.TENANT_NOT_FOUND.value).inc()
                        return

                    if not authorize_case(conn, parsed.case, tenant_id):
                        self._dlq(
                            conn,
                            target=str(rel),
                            reason=DLQReason.CASE_TENANT_MISMATCH,
                            error="case not authorized for tenant",
                            blob={"case": parsed.case, "tenant": parsed.tenant},
                        )
                        ERRORS_TOTAL.labels(type=DLQReason.CASE_TENANT_MISMATCH.value).inc()
                        return

                    with SNAPSHOT_SECONDS.time():
                        s3_uri = snapshot_file(
                            self.minio,
                            self.settings.MINIO_BUCKET_RAW,
                            build_raw_key(sha256),
                            str(path),
                            retries=self.settings.SNAPSHOT_RETRIES,
                            backoff=self.settings.SNAPSHOT_BACKOFF,
                        )

                    artifact_id, task_id = upsert_artifact_and_task(
                        conn,
                        tenant_id=tenant_id,
                        case_id=parsed.case,
                        drop_id=parsed.drop,
                        filename=parsed.filename,
                        src_path=str(rel),
                        s3_uri=s3_uri,
                        sha256=sha256,
                        size_bytes=size_bytes,
                    )

                    if artifact_id:
                        ARTIFACTS_CREATED.labels(tenant=parsed.tenant).inc()

                    self._move_to_processed(path, parsed)
                    self._log_event(
                        "artifact_created" if artifact_id else "artifact_exists",
                        trace_id,
                        extra={
                            "tenant": parsed.tenant,
                            "case_id": parsed.case,
                            "drop_id": parsed.drop,
                            "sha256": sha256,
                            "s3_uri": s3_uri,
                            "filename": parsed.filename,
                            "artifact_id": artifact_id,
                            "task_id": task_id,
                        },
                    )
                except SnapshotError as exc:
                    self._dlq(
                        conn,
                        target=str(rel),
                        reason=DLQReason.SNAPSHOT_FAILED,
                        error=str(exc),
                        blob={"sha": sha256},
                    )
                    ERRORS_TOTAL.labels(type=DLQReason.SNAPSHOT_FAILED.value).inc()
                except (psycopg.Error, ValueError, KeyError) as exc:
                    self._dlq(
                        conn,
                        target=str(rel),
                        reason=DLQReason.UPSERT_FAILED,
                        error=str(exc),
                        blob={"exc": str(exc)},
                    )
                    ERRORS_TOTAL.labels(type=DLQReason.UPSERT_FAILED.value).inc()
                except Exception as exc:  # pragma: no cover - unexpected
                    self.logger.error("unexpected error", exc_info=True, extra={"run_id": self.run_id, "trace_id": trace_id})
                    self._dlq(
                        conn,
                        target=str(rel),
                        reason=DLQReason.UPSERT_FAILED,
                        error=str(exc),
                        blob={"exc": str(exc)},
                    )
                    ERRORS_TOTAL.labels(type=DLQReason.UPSERT_FAILED.value).inc()
                finally:
                    conn.close()
        finally:
            self.first_seen.pop(path, None)
            self.change_attempts.pop(path, None)
            with self.processing_lock:
                self.processing_now.discard(path)

    def _move_to_processed(self, path: Path, parsed: ParsedPath) -> None:
        dest = build_processed_path(self.settings.INBOX_ROOT, self.settings.PROCESSED_DIR_NAME, parsed)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.rename(dest)
        except Exception as exc:
            # The artifact may already be recorded; log + DLQ for visibility
            self._dlq_direct(
                target=str(path.relative_to(self.settings.INBOX_ROOT)),
                reason=DLQReason.MOVE_FAILED,
                error=str(exc),
                blob={"dest": str(dest)},
            )
            ERRORS_TOTAL.labels(type=DLQReason.MOVE_FAILED.value).inc()

    def _dlq(self, conn, *, target: str, reason: DLQReason, error: str | None, blob: dict | None) -> None:
        write_dead_letter(
            conn,
            target=target,
            failed_activity=reason.value,
            last_error=error,
            error_blob=blob,
        )

    def _dlq_direct(self, *, target: str, reason: DLQReason, error: str | None, blob: dict | None) -> None:
        conn = None
        try:
            conn = open_conn(self.dsn)
            self._dlq(conn, target=target, reason=reason, error=error, blob=blob)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _log_event(self, event: str, trace_id: str, extra: dict | None = None) -> None:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": "info",
            "component": "watcher",
            "run_id": self.run_id,
            "trace_id": trace_id,
            "event": event,
        }
        if extra:
            payload.update(extra)
        self.logger.info(json.dumps(payload))


def install_signal_handlers(stop_event: threading.Event) -> None:
    def handler(signum, frame):  # pragma: no cover - signal tests are flaky
        stop_event.set()

    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
