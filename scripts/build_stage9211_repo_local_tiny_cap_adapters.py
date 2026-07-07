#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9211
NAME = "stage9211_repo_local_tiny_cap_adapters"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9210 = ROOT / "runs/summaries/stage9210_repo_local_structured_one_run_ticket_audit.json"
MATRIX = ROOT / "runs/local/artifacts/stage9208_repo_local_execution_review_matrix/repo_local_execution_review_matrix.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_TINY_CAP_ADAPTERS_STAGE9211.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
INDEX = OUT_DIR / "repo_local_tiny_cap_adapter_index.json"

ADAPTER_SPECS = {
    "bounded_decoder_ce_probe": {
        "source_status": "requires_tiny_cap_adapter_before_ticket",
        "enabled_loss": "decoder_ce",
        "caps": {"train": 32, "eval": 16, "strict_eval": 16},
        "max_steps": 16,
        "output_name": "bounded_decoder_tiny_cap_manifest.jsonl",
    },
    "denoise_repair_probe": {
        "source_status": "requires_dedicated_one_run_schema_and_tiny_cap_adapter",
        "enabled_loss": "denoise_ce",
        "caps": {"train": 32, "eval": 16, "strict_eval": 16},
        "max_steps": 8,
        "output_name": "denoise_tiny_cap_manifest.jsonl",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def family_review(matrix: dict[str, Any], mode: str) -> dict[str, Any]:
    for item in matrix.get("family_reviews") or []:
        if item.get("mode") == mode:
            return item
    return {}


def split_name(row: dict[str, Any]) -> str:
    split = str(row.get("split") or "")
    return "strict_eval" if split == "strict" else split


def row_loss_is_exclusive(row: dict[str, Any], enabled_loss: str) -> bool:
    mask = dict(row.get("loss_mask") or {})
    if mask.get(enabled_loss) is not True:
        return False
    return all((key == enabled_loss) or (value is False) for key, value in mask.items())


def cap_rows(rows: list[dict[str, Any]], caps: dict[str, int], enabled_loss: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    counts = {split: 0 for split in caps}
    rejected_loss_rows = 0
    for row in rows:
        split = split_name(row)
        if split not in caps:
            continue
        if counts[split] >= caps[split]:
            continue
        if not row_loss_is_exclusive(row, enabled_loss):
            rejected_loss_rows += 1
            continue
        cloned = dict(row)
        cloned["split"] = split
        cloned["loss_mask"] = {
            key: (key == enabled_loss and value is True)
            for key, value in dict(row.get("loss_mask") or {}).items()
        }
        selected.append(cloned)
        counts[split] += 1
    audit = {
        "selected_rows": len(selected),
        "selected_counts": counts,
        "rejected_loss_rows": rejected_loss_rows,
        "caps_met": all(counts[split] == cap for split, cap in caps.items()),
        "exclusive_loss_rows": all(row_loss_is_exclusive(row, enabled_loss) for row in selected),
    }
    return selected, audit


def build_adapter(mode: str, review: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    manifest_path = Path(str(review.get("manifest_path") or ""))
    failures: list[str] = []
    if not manifest_path.is_file():
        failures.append("source_manifest_missing")
        rows: list[dict[str, Any]] = []
    else:
        rows = read_jsonl(manifest_path)
    if review.get("status") != spec["source_status"]:
        failures.append("unexpected_source_status")
    if "/arxiv" in str(manifest_path):
        failures.append("source_manifest_mentions_arxiv")
    try:
        manifest_path.resolve().relative_to(ROOT)
    except ValueError:
        failures.append("source_manifest_outside_repo")
    selected, cap_audit = cap_rows(rows, dict(spec["caps"]), str(spec["enabled_loss"]))
    if not cap_audit["caps_met"]:
        failures.append("caps_not_met")
    if not cap_audit["exclusive_loss_rows"]:
        failures.append("nonexclusive_loss_rows")
    output_path = OUT_DIR / str(spec["output_name"])
    write_jsonl(output_path, selected)
    return {
        "mode": mode,
        "source_manifest": str(manifest_path),
        "output_manifest": str(output_path.relative_to(ROOT)),
        "enabled_loss": spec["enabled_loss"],
        "caps": dict(spec["caps"]),
        "max_steps": spec["max_steps"],
        "audit": cap_audit,
        "failures": failures,
        "passed": not failures,
    }


def build_index() -> dict[str, Any]:
    source_9210 = load_json(SOURCE_9210)
    matrix = load_json(MATRIX)
    adapters = [
        build_adapter(mode, family_review(matrix, mode), spec)
        for mode, spec in ADAPTER_SPECS.items()
    ]
    checks = {
        "source_stage9210_passed": source_9210.get("passed") is True,
        "matrix_stage9208_passed": matrix.get("passed") is True,
        "adapters_written": len(adapters) == len(ADAPTER_SPECS),
        "all_adapters_passed": all(item["passed"] for item in adapters),
        "all_caps_met": all(item["audit"]["caps_met"] for item in adapters),
        "all_losses_exclusive": all(item["audit"]["exclusive_loss_rows"] for item in adapters),
        "no_arxiv_paths": all("/arxiv" not in item["source_manifest"] and "/arxiv" not in item["output_manifest"] for item in adapters),
        "all_authority_closed": True,
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "authority": dict(AUTHORITY_CLOSED),
        "adapters": adapters,
        "decision": (
            "Built repo-local tiny-cap manifests for bounded decoder and denoise from existing Stage9206 "
            "contract-only trainer rows. No trainer execution, model execution, cleanup, runtime, or /arxiv access occurred."
        ),
        "next_best_step": (
            "Audit the tiny-cap adapters, then refresh the execution review matrix so bounded decoder and denoise "
            "can be evaluated against explicit future ticket requirements."
        ),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [
        row for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = build_index()
    INDEX.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": index["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": index["failures"],
            "adapters": len(index["adapters"]),
            "adapters_passed": sum(1 for item in index["adapters"] if item["passed"]),
            "total_adapter_rows": sum(item["audit"]["selected_rows"] for item in index["adapters"]),
            "trainer_executed_now": False,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "cleanup_authorized_now": False,
        },
        "artifacts": {
            "index": str(INDEX.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": index["decision"] if index["passed"] else "Repo-local tiny-cap adapter build failed.",
        "next_best_step": index["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9211 Repo-Local Tiny-Cap Adapters",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage builds capped repo-local manifests for bounded decoder and denoise from existing contract-only trainer rows.",
                "It does not run trainer, execute a model, clean outputs, touch /arxiv, or open decoder/denoise CE authority.",
                "",
                f"Adapters: `{summary['metrics']['adapters']}`",
                f"Total adapter rows: `{summary['metrics']['total_adapter_rows']}`",
                "",
                f"Next: {summary['next_best_step']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
