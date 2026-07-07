from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


class UnsafePathError(ValueError):
    """Raised when a cleanup target violates repository safety rules."""


@dataclass(frozen=True)
class SafeCleanupPlan:
    repo_root: Path
    output_dir: Path
    checkpoint_dir: Path
    marker_file: Path
    run_id: str
    deletable_children: tuple[Path, ...]


FORBIDDEN_CLEANUP_ROOTS = (
    Path("/").resolve(),
    Path("/data").resolve(),
    Path("/arxiv").resolve(),
)


def _resolve_existing_or_parent(path: Path) -> Path:
    """Resolve a path even when its leaf may not exist yet."""
    path = Path(path).expanduser()
    if path.exists():
        return path.resolve()
    parent = path.parent
    if not parent.exists():
        return parent.resolve() / path.name
    return parent.resolve() / path.name


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_forbidden_root_or_descendant(path: Path, *, allow_under_repo: Path | None = None) -> bool:
    resolved = path.resolve(strict=False)
    if resolved == Path("/").resolve():
        return True
    arxiv = Path("/arxiv").resolve()
    data = Path("/data").resolve()
    if resolved == arxiv or _is_relative_to(resolved, arxiv):
        if allow_under_repo is not None and _is_relative_to(resolved, allow_under_repo.resolve(strict=False)):
            return False
        return True
    if resolved == data:
        return True
    return False


def require_safe_child_path(*, repo_root: Path, output_dir: Path, candidate: Path) -> Path:
    repo = Path(repo_root).expanduser().resolve()
    out = Path(output_dir).expanduser().resolve()
    cand = _resolve_existing_or_parent(Path(candidate))

    forbidden = {repo, repo.parent, out.parent}
    if cand in forbidden or _is_forbidden_root_or_descendant(cand, allow_under_repo=repo):
        raise UnsafePathError(f"refusing cleanup target {cand}: forbidden root/parent path")
    if not _is_relative_to(out, repo):
        raise UnsafePathError(f"output_dir {out} is not under repo_root {repo}")
    if not _is_relative_to(cand, out):
        raise UnsafePathError(f"cleanup target {cand} is not under output_dir {out}")
    if cand == out:
        raise UnsafePathError("refusing to delete output_dir itself")
    if cand.is_symlink():
        raise UnsafePathError(f"refusing symlink cleanup target {cand}")
    if cand.exists():
        real = cand.resolve()
        if not _is_relative_to(real, out):
            raise UnsafePathError(f"cleanup target {cand} resolves outside output_dir")
    return cand


def build_safe_cleanup_plan(*, repo_root: Path, output_dir: Path, run_id: str, marker_name: str = '.agentkernel_probe_output') -> SafeCleanupPlan:
    repo = Path(repo_root).expanduser().resolve()
    out = Path(output_dir).expanduser().resolve()
    if not run_id or '/' in run_id or '\\' in run_id or run_id in {'.', '..'}:
        raise UnsafePathError("cleanup requires a non-empty simple run_id")
    if _is_forbidden_root_or_descendant(repo):
        raise UnsafePathError(f"refusing unsafe repo_root {repo}")
    if not _is_relative_to(out, repo):
        raise UnsafePathError(f"output_dir {out} is not under repo_root {repo}")
    if out in {repo, repo.parent} or _is_forbidden_root_or_descendant(out, allow_under_repo=repo):
        raise UnsafePathError(f"refusing unsafe output_dir {out}")
    marker = out / marker_name
    if not marker.is_file():
        raise UnsafePathError(f"cleanup marker missing: {marker}")
    marker_text = marker.read_text(encoding='utf-8', errors='replace')
    if run_id not in marker_text:
        raise UnsafePathError("cleanup marker does not contain run_id")
    checkpoint_dir = require_safe_child_path(repo_root=repo, output_dir=out, candidate=out / 'checkpoints')
    deletable: list[Path] = []
    if checkpoint_dir.exists():
        for child in checkpoint_dir.iterdir():
            deletable.append(require_safe_child_path(repo_root=repo, output_dir=out, candidate=child))
    return SafeCleanupPlan(repo_root=repo, output_dir=out, checkpoint_dir=checkpoint_dir, marker_file=marker, run_id=run_id, deletable_children=tuple(deletable))


def assert_no_destructive_command_tokens(argv: list[str] | tuple[str, ...]) -> None:
    text = ' '.join(str(x) for x in argv)
    forbidden_fragments = [
        'rm -rf /',
        'rm -rf /data',
        'rm -rf /arxiv',
        'rm -rf .',
        'rm -rf *',
        'shutil.rmtree(.)',
        "shutil.rmtree('.')",
        'shutil.rmtree(repo_root)',
        'shutil.rmtree(output_dir.parent)',
        "os.remove('/data')",
        "os.remove('/arxiv')",
        "Path('/data').unlink",
        "Path('/arxiv').unlink",
    ]
    compact = text.replace(' ', '')
    for frag in forbidden_fragments:
        if frag.replace(' ', '') in compact:
            raise UnsafePathError(f"refusing destructive command fragment: {frag}")
