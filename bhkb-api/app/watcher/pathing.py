from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from pathspec import PathSpec

from app.watcher.errors import FileChangedError, FileTooLargeError


PATH_REGEX = re.compile(
    r"^inbox/(?P<tenant>[a-z0-9-]{1,64})/"
    r"(?P<case>[0-9a-f-]{8}-[0-9a-f-]{4}-[0-9a-f-]{4}-[0-9a-f-]{4}-[0-9a-f-]{12})/"
    r"(?P<drop>[0-9a-f-]{8}-[0-9a-f-]{4}-[0-9a-f-]{4}-[0-9a-f-]{4}-[0-9a-f-]{12})/"
    r"(?P<filename>.+)$"
)


@dataclass(frozen=True)
class ParsedPath:
    tenant: str
    case: str
    drop: str
    filename: str


def match_path(relpath: Path | str) -> ParsedPath | None:
    path_str = relpath.as_posix() if isinstance(relpath, Path) else relpath
    match = PATH_REGEX.match(path_str)
    if not match:
        return None
    groups = match.groupdict()
    return ParsedPath(
        tenant=groups["tenant"],
        case=groups["case"],
        drop=groups["drop"],
        filename=groups["filename"],
    )


def build_processed_path(inbox_root: Path, processed_dir: str, parsed: ParsedPath) -> Path:
    return inbox_root / processed_dir / parsed.tenant / parsed.case / parsed.drop / parsed.filename


def resolve_and_validate(path: Path, inbox_root: Path) -> Path:
    resolved = path.resolve()
    root_resolved = inbox_root.resolve()
    try:
        is_relative = resolved.is_relative_to(root_resolved)
    except AttributeError:
        # Python <3.9 fallback
        try:
            resolved.relative_to(root_resolved)
            is_relative = True
        except ValueError:
            is_relative = False
    if not is_relative:
        raise ValueError("path escapes inbox root")
    return resolved


def make_ignore_spec(patterns_str: str) -> PathSpec:
    patterns = [p.strip() for p in patterns_str.split(",") if p.strip()]
    return PathSpec.from_lines("gitwildmatch", patterns)


def is_ignored(path: Path, inbox_root: Path, spec: PathSpec) -> bool:
    rel = path.relative_to(inbox_root)
    return spec.match_file(rel.as_posix())


def is_stable(first_seen: dict[Path, tuple[int, float, float]], path: Path, stable_seconds: int, now: float) -> bool:
    """Return True if the file has unchanged size/mtime for >= stable_seconds."""
    stat = path.stat()
    size_mtime = (stat.st_size, stat.st_mtime)
    if path not in first_seen:
        first_seen[path] = (size_mtime[0], size_mtime[1], now)
        return False

    prev_size, prev_mtime, first_ts = first_seen[path]
    if (prev_size, prev_mtime) != size_mtime:
        # reset window if file changed
        first_seen[path] = (size_mtime[0], size_mtime[1], now)
        return False

    return (now - first_ts) >= stable_seconds


def stream_sha256(path: Path, max_file_bytes: int) -> tuple[str, int]:
    pre = path.stat()
    if pre.st_size > max_file_bytes:
        raise FileTooLargeError(f"file too large: {pre.st_size} bytes")

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    post = path.stat()
    if pre.st_size != post.st_size or pre.st_mtime != post.st_mtime:
        raise FileChangedError("file changed during hashing")

    return digest.hexdigest(), post.st_size
