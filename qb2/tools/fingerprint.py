"""qb2's own fingerprint -- separate from v1's, on purpose.

v1's fingerprint (tools/engine_fingerprint.py) proves the frozen engine has not
moved. It covers v1's nine folders and nothing else: if qb2 were inside it, every
day of ordinary v2 work would break v1's proof, and a proof that breaks constantly
is a proof everybody learns to ignore.

So qb2 gets its own. Same idea, different scope: a SHA-256 per file, sorted by
path, folded into one combined hash, with the path hashed alongside the digest so
a rename is caught as loudly as an edit. Deterministic -- no timestamps -- so two
runs of unchanged code produce identical output and a plain diff is the whole
proof.

CLI: ``python -m qb2.tools.fingerprint [--root DIR] [--out FILE] [--expect HASH]``
"""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# What qb2 is. Its pinned requirements count: a library version is part of what
# produces a result, so a changed pin should show up here.
QB2_DIRS: tuple[str, ...] = ("qb2",)
QB2_FILES: tuple[str, ...] = ("requirements-qb2.txt",)

EXCLUDED_DIRS = frozenset({"__pycache__"})
EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo"})


class FingerprintError(RuntimeError):
    """Something the fingerprint must cover is missing."""


def qb2_paths(root: Path) -> list[Path]:
    found: list[Path] = []
    for name in QB2_DIRS:
        folder = root / name
        if not folder.is_dir():
            raise FingerprintError(f"qb2 folder missing: {name}")
        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if EXCLUDED_DIRS.intersection(relative.parts):
                continue
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            found.append(path)
    for name in QB2_FILES:
        path = root / name
        if not path.is_file():
            raise FingerprintError(f"qb2 file missing: {name}")
        found.append(path)
    return sorted(found, key=lambda p: p.relative_to(root).as_posix())


def fingerprint(root: Path) -> tuple[str, list[tuple[str, str, int]]]:
    combined = hashlib.sha256()
    rows: list[tuple[str, str, int]] = []
    for path in qb2_paths(root):
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        rows.append((relative, digest, len(payload)))
        combined.update(relative.encode("utf-8"))
        combined.update(b"\0")
        combined.update(digest.encode("ascii"))
        combined.update(b"\n")
    return combined.hexdigest(), rows


def report(root: Path) -> str:
    combined, rows = fingerprint(root)
    lines = [
        "qb2 FINGERPRINT (v2 only -- v1 has its own, deliberately separate)",
        "",
        f"folders: {', '.join(QB2_DIRS)}",
        f"files:   {', '.join(QB2_FILES)}",
        "excluded: __pycache__, *.pyc, *.pyo (generated, not source)",
        "",
        f"files: {len(rows)}   bytes: {sum(size for _, _, size in rows)}",
        "",
    ]
    lines += [f"{digest}  {size:>9}  {path}" for path, digest, size in rows]
    lines += ["", f"COMBINED: {combined}", ""]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qb2.tools.fingerprint",
        description="SHA-256 fingerprint of qb2 and its pinned requirements.")
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--expect", default=None,
                        help="combined hash to require; exit 1 on mismatch")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    combined, _ = fingerprint(root)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report(root), encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
    print(f"COMBINED: {combined}")
    if args.expect is not None and args.expect != combined:
        print(f"MISMATCH: expected {args.expect}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
