#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8973
NAME = "stage8973_arxiv_metadata_only_preflight"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ARXIV_METADATA_ONLY_PREFLIGHT_STAGE8973.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8972_real_data_preflight_plan_no_arxiv_access.json"

ARXIV_ROOT = Path("/arxiv")
DATASETS_ROOT = ARXIV_ROOT / "datasets"
REPOSITORIES_ROOT = ARXIV_ROOT / "repositories"

ROOT_CARD = OUT_DIR / "arxiv_root_metadata_card.json"
DATASET_INV = OUT_DIR / "dataset_file_inventory_metadata_only.jsonl"
REPO_INV = OUT_DIR / "repository_root_inventory_metadata_only.jsonl"
POLICY_CARD = OUT_DIR / "protected_path_policy_card.json"
DECISION_CARD = OUT_DIR / "real_data_preflight_decision_card.json"

DATASET_FILE_CAP = 5000
REPOSITORY_DIR_CAP = 2000

FORBIDDEN_OPERATIONS = [
    "open_dataset_file_body",
    "read_json_or_parquet_rows",
    "read_repository_source_body",
    "write_to_arxiv",
    "delete_or_cleanup_arxiv",
    "start_mining",
    "start_training",
    "load_checkpoint",
    "upload_network_artifacts",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def scandir_entries(path: Path) -> list[os.DirEntry[str]]:
    try:
        with os.scandir(path) as iterator:
            return list(iterator)
    except FileNotFoundError:
        return []
    except PermissionError:
        return []


def entry_metadata(entry: os.DirEntry[str], root: Path) -> dict[str, Any]:
    try:
        stat = entry.stat(follow_symlinks=False)
        size = stat.st_size
        mtime = int(stat.st_mtime)
    except OSError:
        size = None
        mtime = None
    path = Path(entry.path)
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = path.name
    return {
        "name": path.name,
        "relative_path": rel,
        "extension": path.suffix.lower(),
        "is_file": entry.is_file(follow_symlinks=False),
        "is_dir": entry.is_dir(follow_symlinks=False),
        "is_symlink": entry.is_symlink(),
        "size_bytes": size,
        "mtime_epoch": mtime,
    }


def iter_dataset_file_metadata(root: Path, *, cap: int = DATASET_FILE_CAP) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    truncated = False
    if not root.exists():
        return rows, truncated
    stack = [root]
    while stack:
        current = stack.pop()
        for entry in sorted(scandir_entries(current), key=lambda item: item.name):
            meta = entry_metadata(entry, root)
            if meta["is_dir"] and not meta["is_symlink"]:
                stack.append(Path(entry.path))
                continue
            if meta["is_file"] or meta["is_symlink"]:
                rows.append(meta)
                if len(rows) >= cap:
                    return rows, True
    return rows, truncated


def iter_repository_root_metadata(root: Path, *, cap: int = REPOSITORY_DIR_CAP) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    if not root.exists():
        return rows, False
    for entry in sorted(scandir_entries(root), key=lambda item: item.name):
        meta = entry_metadata(entry, root)
        if meta["is_dir"] or meta["is_symlink"]:
            rows.append(meta)
            if len(rows) >= cap:
                return rows, True
    return rows, False


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def build_preflight(*, datasets_root: Path = DATASETS_ROOT, repositories_root: Path = REPOSITORIES_ROOT, registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    dataset_rows, dataset_truncated = iter_dataset_file_metadata(datasets_root)
    repo_rows, repo_truncated = iter_repository_root_metadata(repositories_root)
    arxiv_root = datasets_root.parent
    root_card = {
        "arxiv_root": str(arxiv_root),
        "datasets_root": str(datasets_root),
        "repositories_root": str(repositories_root),
        "arxiv_root_exists": arxiv_root.exists(),
        "datasets_root_exists": datasets_root.exists(),
        "repositories_root_exists": repositories_root.exists(),
        "dataset_file_cap": DATASET_FILE_CAP,
        "repository_dir_cap": REPOSITORY_DIR_CAP,
    }
    policy = {
        "metadata_only": True,
        "dataset_rows_loaded": False,
        "repository_source_bodies_loaded": False,
        "arxiv_write_authorized": False,
        "outputs_under": str(OUT_DIR.relative_to(ROOT)),
        "forbidden_operations": FORBIDDEN_OPERATIONS,
    }
    decision = {
        "real_data_preflight_completed": True,
        "compiler_or_training_authorized": False,
        "dataset_inventory_ready_for_route_card_design": bool(dataset_rows),
        "repository_inventory_ready_for_route_card_design": bool(repo_rows),
        "next_best_step": "Design an audit-only route-card selector over metadata inventories before reading any dataset rows or repository source bodies.",
    }
    checks = {
        "source_stage8972_passed": source.get("passed") is True,
        "outputs_under_runs_local_artifacts": str(OUT_DIR.resolve()).startswith(str((ROOT / "runs/local/artifacts").resolve())),
        "metadata_only_policy_true": policy["metadata_only"] is True,
        "dataset_rows_not_loaded": policy["dataset_rows_loaded"] is False,
        "repository_source_bodies_not_loaded": policy["repository_source_bodies_loaded"] is False,
        "arxiv_write_closed": policy["arxiv_write_authorized"] is False,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 9,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8972_or_8973": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8972, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ARXIV_METADATA_ONLY_PREFLIGHT",
        "root_card": root_card,
        "policy": policy,
        "decision_card": decision,
        "checks": checks,
        "metrics": {
            "arxiv_metadata_access_performed": True,
            "dataset_inventory_rows": len(dataset_rows),
            "repository_inventory_rows": len(repo_rows),
            "dataset_inventory_truncated": dataset_truncated,
            "repository_inventory_truncated": repo_truncated,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
        },
        "dataset_rows": dataset_rows,
        "repository_rows": repo_rows,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Metadata-only /arxiv preflight completed. The stage recorded file/directory metadata only, wrote outputs under runs/local/artifacts, and did not read dataset row bodies or repository source bodies.",
    }


def validate_preflight(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8972, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Metadata-only /arxiv preflight. Does not read dataset rows or repository source bodies.")
    parser.add_argument("--datasets-root", type=Path, default=DATASETS_ROOT)
    parser.add_argument("--repositories-root", type=Path, default=REPOSITORIES_ROOT)
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_preflight(datasets_root=args.datasets_root, repositories_root=args.repositories_root, registry=registry)
    failures = validate_preflight(card, registry)
    ROOT_CARD.write_text(json.dumps(card["root_card"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    POLICY_CARD.write_text(json.dumps(card["policy"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DECISION_CARD.write_text(json.dumps(card["decision_card"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(DATASET_INV, card["dataset_rows"])
    write_jsonl(REPO_INV, card["repository_rows"])
    card_for_disk = {key: value for key, value in card.items() if key not in {"dataset_rows", "repository_rows"}}
    (OUT_DIR / "arxiv_metadata_only_preflight.json").write_text(json.dumps(card_for_disk, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **card["metrics"],
        },
        "artifacts": {
            "root_card": str(ROOT_CARD.relative_to(ROOT)),
            "dataset_inventory": str(DATASET_INV.relative_to(ROOT)),
            "repository_inventory": str(REPO_INV.relative_to(ROOT)),
            "policy_card": str(POLICY_CARD.relative_to(ROOT)),
            "decision_card": str(DECISION_CARD.relative_to(ROOT)),
        },
        "decision": card["decision"],
        "next_best_step": "Design an audit-only route-card selector over the metadata inventories. Do not load dataset rows or repository source bodies until that selector passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8973 Arxiv Metadata-Only Preflight",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage inspects `/arxiv` metadata only: path names, extensions, sizes, mtimes, file/dir/symlink type. It does not open dataset files, parse rows, read repository source bodies, write to `/arxiv`, mine, train, or execute runtime.",
        "",
        f"Dataset inventory rows: `{summary['metrics']['dataset_inventory_rows']}`",
        f"Repository inventory rows: `{summary['metrics']['repository_inventory_rows']}`",
        f"Dataset truncated: `{summary['metrics']['dataset_inventory_truncated']}`",
        f"Repository truncated: `{summary['metrics']['repository_inventory_truncated']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8973 Arxiv Metadata-Only Preflight"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8973 performs the first protected metadata-only /arxiv preflight. It inventories file and top-level repository metadata only and keeps data-row reading, source-body reading, mining, and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
