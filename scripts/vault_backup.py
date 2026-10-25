"""Non-destructive local mirror/snapshot/recovery. Caller must hold both guards."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from _common import (SafetyError, checked_path, disjoint, extended, inventory,
                     relative_name, reject_link, run_id, sha256, utc,
                     validate_manifest, write_json_new)


def copy_required(source: Path, target: Path, files: dict) -> None:
    extended(target).mkdir(parents=True, exist_ok=True)
    for name in files:
        relative_name(name)
        destination = target / name
        # Existing mirror directories/files must not redirect writes elsewhere.
        checked_path(destination)
        extended(destination.parent).mkdir(parents=True, exist_ok=True)
        reject_link(extended(destination))
        shutil.copy2(extended(source / name), extended(destination))


def check_required(source: Path, target: Path, before: dict) -> dict:
    after = inventory(source)
    destination = inventory(target)
    if after != before:
        raise SafetyError("Source inventory/content changed during copy; not verified")
    missing = sorted(before.keys() - destination.keys())
    differences = sorted(name for name in before.keys() & destination.keys() if before[name] != destination[name])
    if missing or differences:
        raise SafetyError(f"Required source mismatch: missing={len(missing)}, differences={len(differences)}")
    return {"source_files": len(before), "target_files": len(destination),
            "source_missing_count": 0, "sha256_difference_count": 0,
            "source_drift_count": 0, "extra_history": sorted(destination.keys() - before.keys())}


def perform(mode: str, source: Path, target: Path, receipts: Path,
            manifest: Path | None = None, manifest_sha256: str | None = None) -> dict:
    if mode not in {"mirror", "snapshot", "restore-check"}:
        raise SafetyError("Unknown backup operation")
    source = checked_path(source, directory=True)
    target = checked_path(target)
    receipts = checked_path(receipts)
    disjoint(source, target, receipts)
    if extended(target).exists() and not extended(target).is_dir():
        raise SafetyError("Target is not a directory")
    if mode != "mirror" and extended(target).exists():
        raise SafetyError("Snapshot/recovery target must not already exist")
    expected = None
    if mode == "restore-check":
        if not manifest or not manifest_sha256:
            raise SafetyError("Manifest and independently retained SHA-256 are required")
        manifest = checked_path(manifest)
        disjoint(source, manifest, target)
        if sha256(manifest) != manifest_sha256.upper():
            raise SafetyError("Manifest hash mismatch")
        expected = validate_manifest(json.loads(extended(manifest).read_text(encoding="utf-8-sig")))
    before = inventory(source)
    if expected is not None and before != expected:
        raise SafetyError("Snapshot no longer matches its manifest")
    ident = run_id()
    started = utc()
    # No file is deleted, even when the mirror contains old names.
    copy_required(source, target, before)
    verification = check_required(source, target, before)
    if mode != "mirror" and verification["extra_history"]:
        raise SafetyError("Fresh snapshot/recovery unexpectedly contains extra files")
    manifest_path = receipts / f"{ident}-{mode}-manifest.json"
    payload = {"schema_version": 1, "kind": mode, "status": "VERIFIED",
               "verified_at_utc": utc(), "files": before}
    write_json_new(manifest_path, payload)
    result = {"schema_version": 1, "run_id": ident, "operation": mode,
              "status": "VERIFIED", "started_at_utc": started, "completed_at_utc": utc(),
              "source": str(source), "target": str(target), "manifest": str(manifest_path),
              "manifest_sha256": sha256(manifest_path), "coordination": "CALLER_MUST_HOLD_BOTH_GUARDS",
              "business_fact_validation": "NOT_PERFORMED", "checkpoint_advanced": False, **verification}
    receipt_path = receipts / f"{ident}-{mode}.json"
    write_json_new(receipt_path, result)
    result["receipt"] = str(receipt_path)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("mirror", "snapshot", "restore-check"))
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--receipts", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    try:
        result = perform(args.mode, args.source, args.target, args.receipts, args.manifest, args.manifest_sha256)
    except (SafetyError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "FAILED", "reason": str(exc), "checkpoint_advanced": False}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
