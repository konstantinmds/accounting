from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

pytest.importorskip("pathspec")

from app.watcher.errors import FileChangedError, FileTooLargeError
from app.watcher.pathing import (
    build_processed_path,
    is_ignored,
    is_stable,
    make_ignore_spec,
    match_path,
    resolve_and_validate,
    stream_sha256,
)


def test_match_path_valid_and_invalid():
    parsed = match_path(
        "inbox/acme/22222222-2222-2222-2222-222222222222/33333333-3333-3333-3333-333333333333/file.txt"
    )
    assert parsed
    assert parsed.tenant == "acme"
    assert parsed.drop.startswith("3333")

    assert match_path("inbox/acme/not-a-uuid/x/file") is None


def test_resolve_guard_rejects_traversal(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    outside = tmp_path / "escape.txt"
    outside.write_text("x")
    link = inbox / "acme"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)

    with pytest.raises(ValueError):
        resolve_and_validate(link, inbox)


def test_ignore_with_gitwildmatch(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    f = inbox / "ignore.tmp"
    f.write_text("x")
    spec = make_ignore_spec("**/*.tmp")
    assert is_ignored(f, inbox, spec) is True


def test_stability_requires_unchanged_window(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    f = inbox / "file.txt"
    f.write_text("x")
    seen = {}
    now = time.time()
    assert is_stable(seen, f, 1, now) is False
    # unchanged and after window
    assert is_stable(seen, f, 0, now + 2) is True


def test_stream_sha256_errors(tmp_path: Path):
    f = tmp_path / "big.bin"
    f.write_bytes(b"0" * 10)
    with pytest.raises(FileTooLargeError):
        stream_sha256(f, max_file_bytes=1)

    f.write_bytes(b"0" * (1024 * 1024 * 5))

    def mutate():
        time.sleep(0.01)
        f.write_bytes(b"1" * (1024 * 1024 * 6))

    import threading

    t = threading.Thread(target=mutate)
    t.start()
    with pytest.raises(FileChangedError):
        stream_sha256(f, max_file_bytes=1024 * 1024 * 10)
    t.join()


def test_build_processed_path(tmp_path: Path):
    from app.watcher.pathing import ParsedPath

    inbox = tmp_path / "inbox"
    parsed = ParsedPath("acme", "c", "d", "file.txt")
    assert build_processed_path(inbox, ".processed", parsed).as_posix().endswith("/.processed/acme/c/d/file.txt")
