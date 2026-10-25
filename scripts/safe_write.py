"""Preview or backed-up text replacement. Cooperative guards are required separately."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys

from _common import (SafetyError, checked_path, disjoint, extended, relative_name,
                     run_id, sha256, utc, write_json_new)


def current_hash(target: Path) -> str:
    return sha256(target) if extended(target).exists() else "MISSING"


def perform(vault: Path, relative: str, candidate: Path, expected: str,
            backup_root: Path, *, apply: bool = False) -> dict:
    vault = checked_path(vault, directory=True)
    name = relative_name(relative)
    if Path(name).suffix not in {".md", ".base"}:
        raise SafetyError("Only reviewed Markdown/Base text is supported")
    target = checked_path(vault / name)
    if vault not in target.parents:
        raise SafetyError("Target escaped vault")
    candidate = checked_path(candidate)
    backup_root = checked_path(backup_root)
    disjoint(vault, backup_root)
    if candidate == target or vault in candidate.parents:
        raise SafetyError("Keep the reviewed candidate outside the source vault")
    expected = expected.upper()
    if expected != "MISSING" and (len(expected) != 64 or any(c not in "0123456789ABCDEF" for c in expected)):
        raise SafetyError("Expected must be an actual SHA-256 or MISSING")
    first = current_hash(target)
    if first != expected:
        raise SafetyError("CONFLICT: target differs from the reading-time hash")
    data = extended(candidate).read_bytes()
    text = data.decode("utf-8-sig")
    if "\x00" in text:
        raise SafetyError("Binary/NUL content is not supported")
    wanted = hashlib.sha256(data).hexdigest().upper()
    if first == wanted:
        return {"status": "NO_CHANGE", "sha256": wanted, "written": False}
    old = extended(target).read_bytes() if first != "MISSING" else b""
    old_text = old.decode("utf-8-sig")
    if first != "MISSING" and hashlib.sha256(old).hexdigest().upper() != first:
        raise SafetyError("CONFLICT: changed while reading original")
    result = {"status": "PREVIEW", "before_sha256": first, "candidate_sha256": wanted, "written": False}
    if not apply:
        return result
    folder = backup_root / run_id()
    folder.mkdir(parents=True, exist_ok=False)
    if first != "MISSING":
        backup = folder / "original" / name
        extended(backup.parent).mkdir(parents=True, exist_ok=True)
        with extended(backup).open("xb") as stream:
            stream.write(old)
        if sha256(backup) != first:
            raise SafetyError("Backup verification failed")
    patch = "".join(difflib.unified_diff(old_text.splitlines(True), text.splitlines(True), fromfile="before/" + name, tofile="after/" + name))
    (folder / "change.diff").write_text(patch, encoding="utf-8")
    if current_hash(target) != first:
        raise SafetyError("CONFLICT: target changed after backup; candidate retained")
    extended(target.parent).mkdir(parents=True, exist_ok=True)
    checked_path(target)  # recheck known link/reparse changes before mutation
    if first == "MISSING":
        # Exclusive creation cannot overwrite a concurrently created new file.
        with extended(target).open("xb") as stream:
            stream.write(data)
    else:
        descriptor, temporary_name = tempfile.mkstemp(prefix=".reviewed-candidate-", dir=extended(target.parent))
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if current_hash(target) != first:
            raise SafetyError("CONFLICT before replace; isolated candidate left for inspection")
        os.replace(temporary_name, extended(target))
    final_hash = sha256(target)
    if final_hash != wanted:
        raise SafetyError("Post-write hash mismatch; inspect original backup")
    result.update(status="COMMITTED", written=True, source_sha256=final_hash,
                  backup_folder=str(folder), target_relative=name, committed_at_utc=utc(),
                  atomic_cas_for_uncooperative_writers=False)
    write_json_new(folder / "receipt.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--relative", required=True)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--backup-root", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = perform(args.vault, args.relative, args.candidate, args.expected, args.backup_root, apply=args.apply)
    except (SafetyError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "FAILED", "reason": str(exc), "checkpoint_advanced": False}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
