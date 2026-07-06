#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.manifest_path_validator import ALLOWED_MANIFEST_ROOTS
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from manifest_path_validator import ALLOWED_MANIFEST_ROOTS  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8961
NAME = "stage8961_repo_local_manifest_inventory_no_mining"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_MANIFEST_INVENTORY_NO_MINING_STAGE8961.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
INVENTORY = OUT_DIR / "repo_local_manifest_inventory_no_mining.json"
INVENTORY_ROWS = OUT_DIR / "repo_local_manifest_inventory_rows.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8960_registry_spine_reconciliation_after_training_readiness_refresh.json"

MAX_DEPTH_BY_ROOT = {
    "runs/local/artifacts": 2,
    "runs/local/recovered": 2,
    "runs/local/manifests": 2,
    "datasets/recovered": 2,
}

CATEGORY_RULES = [
    ("central_graph", "central_research_graph"),
    ("bounded_decoder", "bounded_decoder"),
    ("symbol_binding", "symbol_binding"),
    ("edit_localization", "edit_localization"),
    ("patch_operator", "patch_operator"),
    ("verifier_repair", "verifier_repair"),
    ("denoise_repair", "denoise"),
    ("intent_to_build", "intent_to_build"),
    ("telemetry", "loss_by_step"),
    ("telemetry", "row_token_loss"),
    ("telemetry", "eval_loss_by_checkpoint"),
    ("manifest", "manifest"),
    ("recovery", "recovery"),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def classify(path: Path) -> str:
    text = str(path)
    for category, needle in CATEGORY_RULES:
        if needle in text:
            return category
    return "other_jsonl"


def inventory_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    repo = ROOT.resolve(strict=False)
    for root_label in ALLOWED_MANIFEST_ROOTS:
        root = (ROOT / root_label).resolve(strict=False)
        if not root.exists():
            continue
        max_depth = MAX_DEPTH_BY_ROOT[root_label]
        for path in sorted(root.rglob("*.jsonl")):
            resolved = path.resolve(strict=False)
            if not _is_relative_to(resolved, root):
                continue
            rel_to_root = resolved.relative_to(root)
            if len(rel_to_root.parts) > max_depth + 1:
                continue
            stat = resolved.stat()
            rows.append({
                "path": str(resolved.relative_to(repo)),
                "root_label": root_label,
                "category": classify(resolved),
                "bytes": stat.st_size,
                "audit_only_inventory": True,
                "content_rows_counted": False,
                "content_loaded": False,
                "data_mining_authorized": False,
                "training_authorized": False,
            })
    return rows


def build_inventory(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    rows = inventory_rows()
    root_counts = Counter(row["root_label"] for row in rows)
    category_counts = Counter(row["category"] for row in rows)
    checks = {
        "source_stage8960_passed": source.get("passed") is True,
        "allowed_roots_only": set(root_counts).issubset(set(ALLOWED_MANIFEST_ROOTS)),
        "arxiv_not_scanned": all(not row["path"].startswith("/arxiv") and not row["path"].startswith("arxiv/") for row in rows),
        "content_not_loaded": all(row["content_loaded"] is False for row in rows),
        "content_rows_not_counted": all(row["content_rows_counted"] is False for row in rows),
        "inventory_rows_present": len(rows) > 0,
        "focused_manifest_root_counted": "runs/local/manifests" in root_counts,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8960": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 8960,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REPO_LOCAL_MANIFEST_INVENTORY_NO_MINING",
        "allowed_manifest_roots": list(ALLOWED_MANIFEST_ROOTS),
        "max_depth_by_root": MAX_DEPTH_BY_ROOT,
        "checks": checks,
        "metrics": {
            "inventory_rows": len(rows),
            "root_counts": dict(sorted(root_counts.items())),
            "category_counts": dict(sorted(category_counts.items())),
            "content_files_opened_for_row_count": 0,
            "arxiv_paths_scanned": 0,
            "actual_execution_authorized_next": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "rows": rows,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Repo-local JSONL manifest inventory is metadata-only: it lists files under allowed manifest roots without loading row content, counting data rows, scanning /arxiv, mining, model execution, decoder CE, denoise CE, runtime, or training.",
    }


def validate_inventory(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8960, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["actual_execution_authorized_next", "model_execution_attempted", "runtime_authorized_flag", "training_authorized", "data_mining_authorized", "decoder_ce_authorized", "denoise_ce_authorized", "arxiv_read_authorized_for_compiler", "arxiv_write_authorized"]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("content_files_opened_for_row_count") != 0:
        failures.append("content_files_opened_for_row_count")
    if card["metrics"].get("arxiv_paths_scanned") != 0:
        failures.append("arxiv_paths_scanned")
    return failures


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_inventory(registry)
    failures = validate_inventory(card, registry)
    rows = card.pop("rows")
    INVENTORY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(INVENTORY_ROWS, rows)
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
        "artifacts": {"inventory": str(INVENTORY.relative_to(ROOT)), "inventory_rows": str(INVENTORY_ROWS.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Choose a focused repo-local manifest for audit-only compiler inspection, or continue no-execution recovery. Do not mine /arxiv or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8961 Repo-Local Manifest Inventory No-Mining",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage inventories repo-local JSONL manifests under allowed roots without loading row content or counting data rows.",
        "",
        f"Inventory rows: `{card['metrics']['inventory_rows']}`",
        f"/arxiv paths scanned: `{card['metrics']['arxiv_paths_scanned']}`",
        f"Data mining authorized: `{card['metrics']['data_mining_authorized']}`",
        f"Training authorized: `{card['metrics']['training_authorized']}`",
        "",
        "No mining, model execution, decoder CE, denoise CE, runtime, checkpoint export, or training is authorized.",
        "",
    ]), encoding="utf-8")
    rows_registry = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows_registry.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows_registry = sorted(rows_registry, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows_registry
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows_registry),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8961 Repo-Local Manifest Inventory No-Mining"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8961 inventories repo-local JSONL manifests under allowed roots only. It does not load row content, count data rows, scan /arxiv, mine, execute models, or train.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
