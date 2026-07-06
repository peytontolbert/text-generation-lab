from __future__ import annotations

from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

ALLOWED_MANIFEST_ROOTS = (
    "runs/local/artifacts",
    "runs/local/recovered",
    "runs/local/manifests",
    "datasets/recovered",
)

FORBIDDEN_ABSOLUTE_ROOTS = (
    Path("/"),
    Path("/arxiv"),
    Path("/data"),
)

GLOB_CHARS = frozenset("*?[")


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def allowed_manifest_roots(repo_root: Path = REPO_ROOT) -> dict[str, Path]:
    root = repo_root.resolve(strict=False)
    return {label: (root / label).resolve(strict=False) for label in ALLOWED_MANIFEST_ROOTS}


def _contains_traversal(path: Path) -> bool:
    return any(part == ".." for part in path.parts)


def _contains_glob(raw_path: str) -> bool:
    return any(char in raw_path for char in GLOB_CHARS)


def _forbidden_absolute_root_failure(resolved: Path, repo_root: Path) -> str | None:
    repo = repo_root.resolve(strict=False)
    if resolved == Path("/"):
        return "manifest_path_is_root"
    if resolved == Path("/arxiv") or _is_relative_to(resolved, Path("/arxiv")):
        return "manifest_path_under_arxiv_forbidden"
    if (resolved == Path("/data") or _is_relative_to(resolved, Path("/data"))) and not _is_relative_to(resolved, repo):
        return "manifest_path_under_data_outside_repo_forbidden"
    return None


def validate_manifest_input_path(
    manifest_path: str | Path,
    *,
    repo_root: Path = REPO_ROOT,
    must_exist: bool = True,
) -> dict[str, Any]:
    """Validate an explicit local JSONL manifest input path.

    This is intentionally a path validator, not a dataset discovery helper. It
    forbids globs, traversal, directories, remote-ish strings, `/arxiv`, and
    arbitrary `/data` locations outside the active repository.
    """

    raw = str(manifest_path)
    candidate = Path(manifest_path)
    root = repo_root.resolve(strict=False)
    failures: list[str] = []

    if not raw:
        failures.append("manifest_path_empty")
    if "://" in raw:
        failures.append("remote_manifest_uri_forbidden")
    if _contains_glob(raw):
        failures.append("glob_manifest_path_forbidden")
    if _contains_traversal(candidate):
        failures.append("path_traversal_forbidden")
    if candidate.suffix != ".jsonl":
        failures.append("manifest_must_be_jsonl")

    resolved = candidate.resolve(strict=False) if candidate.is_absolute() else (root / candidate).resolve(strict=False)

    forbidden_failure = _forbidden_absolute_root_failure(resolved, root)
    if forbidden_failure:
        failures.append(forbidden_failure)

    root_label: str | None = None
    for label, allowed_root in allowed_manifest_roots(root).items():
        if _is_relative_to(resolved, allowed_root) and resolved != allowed_root:
            root_label = label
            break
    if root_label is None:
        failures.append("manifest_path_not_under_allowed_input_root")

    exists = resolved.exists()
    if must_exist and not exists:
        failures.append("manifest_path_missing")
    if exists and resolved.is_dir():
        failures.append("manifest_path_is_directory")

    return {
        "allowed": not failures,
        "failures": failures,
        "input_path": raw,
        "resolved_path": str(resolved),
        "root_label": root_label,
        "must_exist": must_exist,
        "exists": exists,
        "allowed_input_roots": list(ALLOWED_MANIFEST_ROOTS),
        "forbidden_absolute_roots": [str(path) for path in FORBIDDEN_ABSOLUTE_ROOTS],
        "data_mining_authorized": False,
        "recursive_scan_authorized": False,
        "training_authorized": False,
        "runtime_authorized": False,
    }
