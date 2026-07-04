from __future__ import annotations

import json
from pathlib import Path


class ArtifactPathError(ValueError):
    """Raised when an artifact path violates focused storage policy."""


REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "configs" / "storage" / "focused_storage_policy_v1.json"


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def load_storage_policy() -> dict[str, object]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def allowed_write_roots() -> dict[str, Path]:
    policy = load_storage_policy()
    raw = policy.get("allowed_write_locations", {})
    if not isinstance(raw, dict):
        raise ArtifactPathError("storage policy missing allowed_write_locations")
    roots: dict[str, Path] = {}
    for key, rel in raw.items():
        if not isinstance(key, str) or not isinstance(rel, str):
            raise ArtifactPathError("storage policy roots must be string mappings")
        candidate = (REPO_ROOT / rel).resolve()
        if not _is_relative_to(candidate, REPO_ROOT):
            raise ArtifactPathError(f"policy root escapes repo: {key}={rel}")
        roots[key] = candidate
    return roots


def assert_allowed_storage_path(path: Path | str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    resolved = candidate.resolve()
    if resolved in {Path('/').resolve(), Path('/data').resolve(), Path('/arxiv').resolve(), REPO_ROOT}:
        raise ArtifactPathError(f"refusing unfocused storage path: {resolved}")
    for root in allowed_write_roots().values():
        if _is_relative_to(resolved, root):
            return resolved
    raise ArtifactPathError(f"path is outside focused storage roots: {resolved}")


def _safe_stage_name(stage_name: str) -> str:
    if not stage_name or '/' in stage_name or '\\' in stage_name or stage_name in {'.', '..'}:
        raise ArtifactPathError(f"unsafe stage name: {stage_name!r}")
    return stage_name


def stage_summary_path(stage_name: str) -> Path:
    name = _safe_stage_name(stage_name)
    return assert_allowed_storage_path(allowed_write_roots()["stage_summaries"] / f"{name}.json")


def stage_artifact_dir(stage_name: str) -> Path:
    name = _safe_stage_name(stage_name)
    return assert_allowed_storage_path(allowed_write_roots()["stage_artifacts"] / name)


def probe_output_dir(stage_name: str) -> Path:
    name = _safe_stage_name(stage_name)
    return assert_allowed_storage_path(allowed_write_roots()["probe_outputs"] / name)


def config_path(*parts: str) -> Path:
    if not parts or any(not part or '/' in part or '\\' in part or part in {'.', '..'} for part in parts):
        raise ArtifactPathError("config_path requires simple path parts")
    return assert_allowed_storage_path(allowed_write_roots()["configs"].joinpath(*parts))


def doc_path(*parts: str) -> Path:
    if not parts or any(not part or '/' in part or '\\' in part or part in {'.', '..'} for part in parts):
        raise ArtifactPathError("doc_path requires simple path parts")
    return assert_allowed_storage_path(allowed_write_roots()["docs"].joinpath(*parts))


def arxiv_is_backup_only() -> bool:
    policy = load_storage_policy()
    backup = policy.get("backup_locations", {})
    if not isinstance(backup, dict):
        return False
    arxiv = backup.get("/arxiv")
    return isinstance(arxiv, dict) and arxiv.get("cleanup_allowed") is False and arxiv.get("delete_allowed") is False
