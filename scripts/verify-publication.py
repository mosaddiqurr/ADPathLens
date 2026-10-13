"""Review publishable files and reachable Git history without printing secret values."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = [
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{36,}"),
    re.compile(rb"sk-[A-Za-z0-9_-]{32,}"),
]
DATA_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".dump",
    ".backup",
    ".zip",
    ".log",
    ".pid",
}
GIT = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]


def private_path(relative: str) -> bool:
    path = Path(relative)
    return path.name != ".gitkeep" and (
        path.suffix.lower() in DATA_SUFFIXES
        or relative.startswith(
            ("var/", "release/", "secrets/", "frontend/test-results/")
        )
        or path.name.startswith(".env")
        and path.name != ".env.example"
    )


def scan_history(problems: list[str]) -> int:
    listing = subprocess.run(
        GIT + ["rev-list", "--objects", "--all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.splitlines()
    paths = (
        subprocess.run(
            GIT + ["log", "--all", "--format=", "--name-only", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        .stdout.decode("utf-8")
        .split("\0")
    )
    for relative in sorted(set(path.strip("\n") for path in paths) - {""}):
        if private_path(relative):
            problems.append(f"Historical private/runtime artifact: {relative}")
    reviewed = 0
    with subprocess.Popen(
        GIT + ["cat-file", "--batch"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    ) as process:
        if process.stdin is None or process.stdout is None:
            raise RuntimeError("Could not read Git objects.")
        for item in listing:
            oid, _, path = item.partition(b" ")
            process.stdin.write(oid + b"\n")
            process.stdin.flush()
            header = process.stdout.readline().split()
            if len(header) != 3:
                raise RuntimeError("Could not read a reachable Git object.")
            data = process.stdout.read(int(header[2]))
            process.stdout.read(1)
            if header[1] != b"blob":
                continue
            reviewed += 1
            if any(pattern.search(data) for pattern in SECRET_PATTERNS):
                label = path.decode("utf-8", errors="replace") or oid.decode("ascii")
                problems.append(f"Historical possible credential: {label}")
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("Git history scanning failed.")
    return reviewed


def main() -> int:
    listing = subprocess.run(
        GIT + ["ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    problems: list[str] = []
    reviewed = 0
    for relative in sorted(set(listing.stdout.decode("utf-8").split("\0")) - {""}):
        path = ROOT / relative
        if not path.is_file():
            continue  # Source removals remain in the index until the user's own commit.
        if not path.resolve().is_relative_to(ROOT):
            problems.append(f"External symlink: {relative}")
            continue
        reviewed += 1
        if path.name == ".gitkeep":
            continue
        if private_path(relative):
            problems.append(f"Private/runtime artifact: {relative}")
        data = path.read_bytes()
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):
            problems.append(f"Possible credential: {relative}")
    historical = scan_history(problems)
    if problems:
        print("Publication check failed:")
        print("\n".join(sorted(set(problems))))
        return 1
    print(f"Publication check passed: {reviewed} present tracked/non-ignored files.")
    print(f"Reachable historical blobs reviewed: {historical}.")
    print(
        "No detected private/runtime artifacts or recognizable credentials. Detection is best effort."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
