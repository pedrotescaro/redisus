from __future__ import annotations

import fnmatch
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


FORBIDDEN_DIRECTORIES = (
    "dataset/",
    "models/",
    "runs/",
    "tmp_images/",
)

FORBIDDEN_EXTENSIONS = (
    ".ckpt",
    ".db",
    ".docx",
    ".h5",
    ".keras",
    ".mp4",
    ".onnx",
    ".pb",
    ".pt",
    ".pth",
    ".pyc",
    ".pyo",
    ".sqlite",
    ".sqlite3",
    ".task",
    ".tflite",
    ".tsbuildinfo",
)

ALLOWED_PATHS = {
    "design/logo.png",
    "examples/synthetic_wound.jpg",
    "web/redisus-frontend/public/images/logo.png",
    "web/redisus-frontend/public/images/logo.svg",
    "web/redisus-frontend/public/videos/.gitkeep",
}

REQUIRED_FILES = (
    ".github/pull_request_template.md",
    ".gitignore",
    "README.md",
    "SECURITY.md",
    "docs/data/artifact-policy.md",
    "docs/dev/setup.md",
    "docs/dev/testing.md",
    "pyproject.toml",
    "requirements-ci.txt",
)

MAX_TRACKED_FILE_SIZE_BYTES = 5 * 1024 * 1024
LARGE_FILE_ALLOWLIST_PATTERNS = (
    "web/redisus-frontend/package-lock.json",
)


@dataclass(frozen=True)
class Finding:
    path: str
    reason: str


def _git_ls_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    return [
        item.decode("utf-8").replace("\\", "/")
        for item in result.stdout.split(b"\0")
        if item
    ]


def _is_allowed(path: str) -> bool:
    return path in ALLOWED_PATHS


def _is_large_file_allowed(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in LARGE_FILE_ALLOWLIST_PATTERNS)


def _artifact_findings(repo_root: Path, tracked_files: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for path in tracked_files:
        if _is_allowed(path):
            continue

        if path.startswith(FORBIDDEN_DIRECTORIES):
            findings.append(Finding(path, "forbidden artifact directory"))
            continue

        suffix = Path(path).suffix.lower()
        if suffix in FORBIDDEN_EXTENSIONS:
            findings.append(Finding(path, f"forbidden extension {suffix}"))
            continue

        full_path = repo_root / path
        if full_path.exists() and full_path.stat().st_size > MAX_TRACKED_FILE_SIZE_BYTES and not _is_large_file_allowed(path):
            findings.append(Finding(path, "tracked file is larger than 5 MiB"))
    return findings


def _required_file_findings(repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in REQUIRED_FILES:
        if not (repo_root / path).is_file():
            findings.append(Finding(path, "required repository governance file is missing"))
    return findings


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    tracked_files = _git_ls_files(repo_root)
    findings = _artifact_findings(repo_root, tracked_files)
    findings.extend(_required_file_findings(repo_root))

    if not findings:
        print("Repository artifact and governance checks passed.")
        return 0

    print("Repository artifact and governance checks failed.")
    print("Move generated assets, datasets, databases, model weights, and clinical artifacts out of Git.")
    print("Keep only metadata, manifests, model cards, dataset cards, and synthetic examples.")
    print()
    for finding in findings:
        print(f"- {finding.path}: {finding.reason}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
