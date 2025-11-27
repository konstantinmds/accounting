from __future__ import annotations

from unittest import mock

import pytest

from app.watcher.snapshot import SnapshotError, build_raw_key, snapshot_file


def test_build_raw_key():
    key = build_raw_key("a" * 64)
    assert key == "raw/aa/" + ("a" * 64)


def test_snapshot_retry_and_fail():
    client = mock.Mock()
    client.fput_object.side_effect = [Exception("net"), None]
    uri = snapshot_file(client, "raw", "key", "/tmp/file", retries=2, backoff=0)
    assert uri == "s3://raw/key"
    assert client.fput_object.call_count == 2


def test_snapshot_exceeds_retries():
    client = mock.Mock()
    client.fput_object.side_effect = Exception("boom")
    with pytest.raises(SnapshotError):
        snapshot_file(client, "raw", "key", "/tmp/file", retries=1, backoff=0)
