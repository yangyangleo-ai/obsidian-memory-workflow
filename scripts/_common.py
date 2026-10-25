"""Local file primitives. No model, network client, scheduler, or credentials."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat
import uuid


class SafetyError(RuntimeError):
    pass


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run_id() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]


def extended(path: Path) -> Path:
    value = str(path.absolute())
    if os.name == "nt" and not value.startswith("\\\\?\\"):
        value = "\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value
    return Path(value)


def reject_link(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise SafetyError("Links and reparse points are not supported")


def checked_path(raw: str | Path, *, directory: bool = False) -> Path:
    original = Path(os.path.abspath(raw))
    for item in [original, *original.parents]:
        reject_link(extended(item))
    path = original.resolve()
    if path == Path(path.anchor) or path == Path.home().resolve():
        raise SafetyError("Refusing a filesystem root or home directory")
    if directory and not path.is_dir():
        raise SafetyError("Required directory does not exist")
    return path


def disjoint(*paths: Path) -> None:
    for n, a in enumerate(paths):
        for b in paths[n + 1:]:
            if a == b or a in b.parents or b in a.parents:
                raise SafetyError("Source, destination and control paths must not overlap")


def relative_name(name: str) -> str:
    parts = PurePosixPath(name)
    if not name or "\\" in name or ":" in name or parts.is_absolute() or PureWindowsPath(name).is_absolute():
        raise SafetyError("Invalid relative path")
    if any(x in {"", ".", ".."} for x in name.split("/")):
        raise SafetyError("Path traversal or ambiguous relative path")
    return parts.as_posix()


def sha256(path: Path) -> str:
    with extended(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def inventory(root: Path) -> dict:
    top = extended(root)
    result = {}

    def visit(folder):
        with os.scandir(folder) as entries:
            for entry in sorted(entries, key=lambda x: x.name):
                path = Path(entry.path)
                reject_link(path)
                if entry.is_dir(follow_symlinks=False):
                    visit(path)
                elif entry.is_file(follow_symlinks=False):
                    rel = relative_name(path.relative_to(top).as_posix())
                    result[rel] = {"sha256": sha256(path), "bytes": path.stat().st_size}
                else:
                    raise SafetyError("Special files are not supported")

    visit(top)
    if not result:
        raise SafetyError("Refusing to certify an empty source")
    return result


def write_json_new(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with extended(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def validate_manifest(payload: dict) -> dict:
    if payload.get("kind") != "snapshot" or payload.get("status") != "VERIFIED":
        raise SafetyError("A verified snapshot manifest is required")
    files = payload.get("files")
    if not isinstance(files, dict) or not files:
        raise SafetyError("Missing or empty file manifest")
    for name, item in files.items():
        relative_name(name)
        value = item.get("sha256", "")
        if len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value):
            raise SafetyError("Invalid manifest hash")
        if type(item.get("bytes")) is not int or item["bytes"] < 0:
            raise SafetyError("Invalid manifest size")
    return files
