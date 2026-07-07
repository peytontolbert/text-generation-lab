from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ALLOWED_SEARCH_ROOTS = ("runs/local/artifacts", "runs/summaries")
FORBIDDEN_SEARCH_ROOTS = ("/", "/data", "/arxiv", "/home", "/tmp")

SEARCH_PATTERNS = {
    "objective_rows_jsonl": ("*objective*.jsonl", "*rows*.jsonl", "*manifest*.jsonl"),
    "judge_rows_jsonl": ("*judge*.jsonl", "*judged*.jsonl"),
    "junk_ranker_rows_jsonl": ("*ranker*.jsonl", "*ranked*.jsonl", "*junk*.jsonl"),
    "shortcut_baseline_card_json": ("*shortcut*baseline*.json", "*shortcut*.json"),
    "counterfactual_obligation_card_json": ("*counterfactual*obligation*.json", "*counterfactual*.json"),
    "source_lineage_card_json": ("*source*lineage*.json", "*lineage*.json"),
}


@dataclass(frozen=True)
class InventoryCandidate:
    candidate_type: str
    path: str
    relative_path: str
    extension: str
    stage_hint: str
    path_allowed: bool
    content_read: bool = False
    row_count_read: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_type": self.candidate_type,
            "path": self.path,
            "relative_path": self.relative_path,
            "extension": self.extension,
            "stage_hint": self.stage_hint,
            "path_allowed": self.path_allowed,
            "content_read": self.content_read,
            "row_count_read": self.row_count_read,
        }


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _stage_hint(path: Path) -> str:
    for part in path.parts:
        if part.startswith("stage"):
            return part
    stem = path.stem
    for token in stem.replace("-", "_").split("_"):
        if token.startswith("stage"):
            return token
    return ""


def path_allowed(path: Path, repo_root: Path, allowed_roots: Iterable[str] = ALLOWED_SEARCH_ROOTS) -> bool:
    resolved = path.resolve()
    if any(_is_under(resolved, repo_root / root) for root in allowed_roots):
        return True
    if any(str(resolved) == root or str(resolved).startswith(root.rstrip("/") + "/") for root in FORBIDDEN_SEARCH_ROOTS):
        return False
    return False


def inventory_paths(paths: Iterable[Path], *, repo_root: Path) -> list[dict[str, object]]:
    rows: list[InventoryCandidate] = []
    seen: set[tuple[str, str]] = set()
    for raw_path in paths:
        path = raw_path if raw_path.is_absolute() else repo_root / raw_path
        allowed = path_allowed(path, repo_root)
        try:
            relative = str(path.resolve().relative_to(repo_root.resolve()))
        except ValueError:
            relative = str(path)
        for candidate_type, patterns in SEARCH_PATTERNS.items():
            if any(path.match(pattern) for pattern in patterns):
                key = (candidate_type, relative)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    InventoryCandidate(
                        candidate_type=candidate_type,
                        path=str(path),
                        relative_path=relative,
                        extension=path.suffix,
                        stage_hint=_stage_hint(path),
                        path_allowed=allowed,
                    )
                )
    return [row.as_dict() for row in sorted(rows, key=lambda item: (item.candidate_type, item.relative_path))]
