"""Release allowlist and generic sensitive-content checks, not a secrecy guarantee."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private-key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(?:ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "cloud-key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "model-key": re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}\b"),
    "credential-url": re.compile(r"(?i)[?&](?:token|api_key|signature|authorization|access_token)=[A-Za-z0-9.%_-]{10,}"),
    "windows-user-path": re.compile(r"(?i)[A-Z]:[\\/]Users[\\/](?!Public(?:[\\/]|$))[^\\/\s]+[\\/]"),
    "unix-user-path": re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+/"),
    "email-address": re.compile(r"\b[A-Za-z0-9._%+-]+@(?!example\.(?:com|invalid)\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}


def scan_text(text):
    return [name for name, pattern in PATTERNS.items() if pattern.search(text)]


def check(root=ROOT):
    lines = (root / "PUBLIC_FILES.txt").read_text(encoding="utf-8").splitlines()
    allow = [x for x in lines if x and not x.startswith("#")]
    issues = []
    if len(allow) != len(set(allow)):
        issues.append("duplicate-public-allowlist-entry")
    present = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
               and ".git" not in p.relative_to(root).parts and "__pycache__" not in p.relative_to(root).parts}
    for name in sorted(present - set(allow)):
        issues.append(f"not-allowlisted: {name}")
    for name in sorted(set(allow) - present):
        issues.append(f"missing-public-file: {name}")
    for name in allow:
        path = root / name
        if ".." in Path(name).parts or Path(name).is_absolute() or "\\" in name:
            issues.append("invalid-allowlist-path")
            continue
        if not path.is_file():
            continue
        if path.is_symlink() or path.stat().st_size > 200_000:
            issues.append(f"link-or-oversized: {name}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            issues.append(f"non-utf8: {name}")
            continue
        if "\x00" in text:
            issues.append(f"binary-nul: {name}")
        issues.extend(f"{rule}: {name}" for rule in scan_text(text))
    # Ignored/untracked runtime data is not sufficient protection if explicitly staged.
    if (root / ".git").exists():
        tracked = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout.decode().split("\x00")
        issues.extend("tracked-outside-allowlist: " + x for x in tracked if x and x not in allow)
    return issues, allow


if __name__ == "__main__":
    problems, files = check()
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"public_files={len(files)} findings={len(problems)}; manual review is still required")
    raise SystemExit(1 if problems else 0)
