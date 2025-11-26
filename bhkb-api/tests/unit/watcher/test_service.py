from __future__ import annotations

import time
from pathlib import Path
from unittest import mock

import pytest

pytest.importorskip("prometheus_client")

from app.watcher.config import WatcherSettings
from app.watcher.errors import DLQReason
from app.watcher.service import Watcher


class FakeConn:
    def close(self):
        return None


@pytest.fixture(autouse=True)
def reset_metrics():
    # Prometheus client counters persist; no strict reset, but we isolate by calling in order.
    yield


def make_watcher(tmp_path: Path, monkeypatch, dlq_records, artifact_new=True):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    settings = WatcherSettings(
        DATABASE_URL="postgresql://user:pass@localhost:5432/postgres",
        S3_ENDPOINT="minio:9000",
        S3_ACCESS_KEY="k",
        S3_SECRET_KEY="s",
        INBOX_ROOT=inbox,
        FILE_STABLE_SECONDS=0,
        SCAN_INTERVAL_SECONDS=1,
        MAX_CONCURRENCY=1,
        MAX_FILE_BYTES=1024 * 1024,
    )

    monkeypatch.setattr("app.watcher.service.open_conn", lambda dsn: FakeConn())
    monkeypatch.setattr("app.watcher.service.fetch_tenant_by_slug", lambda conn, slug: "tenant-1")
    monkeypatch.setattr("app.watcher.service.authorize_case", lambda conn, case_id, tenant_id: True)
    monkeypatch.setattr("app.watcher.service.snapshot_file", lambda *args, **kwargs: "s3://raw/key")

    def fake_upsert(*args, **kwargs):
        return ("art-1", "task-1") if artifact_new else (None, None)

    monkeypatch.setattr("app.watcher.service.upsert_artifact_and_task", fake_upsert)

    def fake_dlq(conn=None, *, target, reason, error, blob):
        dlq_records.append((target, reason, error, blob))

    monkeypatch.setattr("app.watcher.service.write_dead_letter", fake_dlq)

    watcher = Watcher(settings, stop_event=mock.Mock(is_set=lambda: False, wait=lambda timeout: None))
    return watcher, inbox


def test_happy_path_moves_file_and_counts(monkeypatch, tmp_path):
    dlq_records: list = []
    watcher, inbox = make_watcher(tmp_path, monkeypatch, dlq_records, artifact_new=True)
    file_path = inbox / "acme" / "22222222-2222-2222-2222-222222222222" / "33333333-3333-3333-3333-333333333333" / "file.txt"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("hello")

    watcher.first_seen[file_path] = (file_path.stat().st_size, file_path.stat().st_mtime, time.time() - 5)
    watcher._process_file(file_path)

    processed = inbox / ".processed" / "acme" / "22222222-2222-2222-2222-222222222222" / "33333333-3333-3333-3333-333333333333" / "file.txt"
    assert processed.exists()
    assert not dlq_records


def test_invalid_path_goes_to_dlq(monkeypatch, tmp_path):
    dlq_records: list = []
    watcher, inbox = make_watcher(tmp_path, monkeypatch, dlq_records, artifact_new=True)
    bad = inbox / "file.txt"
    bad.write_text("x")
    watcher.first_seen[bad] = (bad.stat().st_size, bad.stat().st_mtime, time.time() - 5)
    watcher._process_file(bad)

    assert dlq_records
    assert dlq_records[0][1] == DLQReason.INVALID_PATH


def test_snapshot_failure_dlq(monkeypatch, tmp_path):
    dlq_records: list = []
    watcher, inbox = make_watcher(tmp_path, monkeypatch, dlq_records, artifact_new=True)
    monkeypatch.setattr("app.watcher.service.snapshot_file", mock.Mock(side_effect=Exception("fail")))
    file_path = inbox / "acme" / "22222222-2222-2222-2222-222222222222" / "33333333-3333-3333-3333-333333333333" / "file.txt"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("hello")
    watcher.first_seen[file_path] = (file_path.stat().st_size, file_path.stat().st_mtime, time.time() - 5)
    watcher._process_file(file_path)

    assert any(rec[1] == DLQReason.SNAPSHOT_FAILED for rec in dlq_records)


def test_move_failure_records_dlq(monkeypatch, tmp_path):
    dlq_records: list = []
    watcher, inbox = make_watcher(tmp_path, monkeypatch, dlq_records, artifact_new=True)
    file_path = inbox / "acme" / "22222222-2222-2222-2222-222222222222" / "33333333-3333-3333-3333-333333333333" / "file.txt"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("hello")
    watcher.first_seen[file_path] = (file_path.stat().st_size, file_path.stat().st_mtime, time.time() - 5)

    monkeypatch.setattr(Path, "rename", mock.Mock(side_effect=OSError("nope")))
    watcher._process_file(file_path)

    assert any(rec[1] == DLQReason.MOVE_FAILED for rec in dlq_records)
