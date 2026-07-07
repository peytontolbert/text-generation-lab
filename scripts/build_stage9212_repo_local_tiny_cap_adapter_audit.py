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
STAGE = 9212
NAME = "stage9212_repo_local_tiny_cap_adapter_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9211 = ROOT / "runs/summaries/stage9211_repo_local_tiny_cap_adapters.json"
SOURCE_INDEX = ROOT / "runs/local/artifacts/stage9211_repo_local_tiny_cap_adapters/repo_local_tiny_cap_adapter_index.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_TINY_CAP_ADAPTER_AUDIT_STAGE9212.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "repo_local_tiny_cap_adapter_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"train": 0, "eval": 0, "strict_eval": 0}
    for row in rows:
        split = str(row.get("split") or "")
        if split in counts:
            counts[split] += 1
    return counts


def exclusive_loss_rows(rows: list[dict[str, Any]], enabled_loss: str) -> bool:
    for row in rows:
        mask = dict(row.get("loss_mask") or {})
        if mask.get(enabled_loss) is not True:
            return False
        for key, value in mask.items():
            if key != enabled_loss and value is not False:
                return False
    return True


def path_ok(path_text: str) -> bool:
    if "/arxiv" in path_text:
        return False
    try:
        (ROOT / path_text).resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def audit_adapter(adapter: dict[str, Any]) -> dict[str, Any]:
    output_rel = str(adapter.get("output_manifest") or "")
    output_path = ROOT / output_rel
    failures: list[str] = []
    if not path_ok(output_rel):
        failures.append("output_path_not_repo_local")
    if not output_path.is_file():
        failures.append("output_manifest_missing")
        rows: list[dict[str, Any]] = []
    else:
        rows = read_jsonl(output_path)
    counts = split_counts(rows)
    expected_caps = dict(adapter.get("caps") or {})
    if counts != expected_caps:
        failures.append("split_counts_do_not_match_caps")
    if len(rows) != sum(int(value) for value in expected_caps.values()):
        failures.append("row_count_does_not_match_caps")
    enabled_loss = str(adapter.get("enabled_loss") or "")
    if not exclusive_loss_rows(rows, enabled_loss):
        failures.append("loss_mask_not_exclusive")
    if "/arxiv" in str(adapter.get("source_manifest") or ""):
        failures.append("source_manifest_mentions_arxiv")
    if (adapter.get("audit") or {}).get("caps_met") is not True:
        failures.append("source_adapter_caps_not_met")
    if (adapter.get("audit") or {}).get("exclusive_loss_rows") is not True:
        failures.append("source_adapter_loss_not_exclusive")
    return {
        "mode": adapter.get("mode"),
        "output_manifest": output_rel,
        "rows": len(rows),
        "split_counts": counts,
        "expected_caps": expected_caps,
        "enabled_loss": enabled_loss,
        "failures": failures,
        "passed": not failures,
    }


def build_audit() -> dict[str, Any]:
    source_9211 = load_json(SOURCE_9211)
    index = load_json(SOURCE_INDEX)
    adapter_audits = [audit_adapter(adapter) for adapter in index.get("adapters") or []]
    checks = {
        "source_stage9211_passed": source_9211.get("passed") is True,
        "source_index_passed": index.get("passed") is True,
        "adapter_audits_present": len(adapter_audits) == 2,
        "all_adapter_audits_passed": all(item["passed"] for item in adapter_audits),
        "bounded_decoder_adapter_present": any(item["mode"] == "bounded_decoder_ce_probe" for item in adapter_audits),
        "denoise_adapter_present": any(item["mode"] == "denoise_repair_probe" for item in adapter_audits),
        "all_authority_closed": not any((index.get("authority") or {}).values()),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "authority": dict(AUTHORITY_CLOSED),
        "adapter_audits": adapter_audits,
        "decision": (
            "Tiny-cap adapter manifests pass independent audit for row counts, split caps, exclusive loss masks, "
            "repo-local paths, and closed authority. No trainer/model execution occurred."
        ),
        "next_best_step": (
            "Refresh the execution review matrix against the tiny-cap adapter manifests. Keep execution closed."
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
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": audit["failures"],
            "adapter_audits": len(audit["adapter_audits"]),
            "adapter_audits_passed": sum(1 for item in audit["adapter_audits"] if item["passed"]),
            "trainer_executed_now": False,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "cleanup_authorized_now": False,
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": audit["decision"] if audit["passed"] else "Repo-local tiny-cap adapter audit failed.",
        "next_best_step": audit["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9212 Repo-Local Tiny-Cap Adapter Audit",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage independently audits the Stage9211 capped bounded-decoder and denoise manifests.",
                "It does not run trainer, execute a model, clean outputs, touch /arxiv, or open decoder/denoise CE authority.",
                "",
                f"Adapter audits: `{summary['metrics']['adapter_audits']}`",
                f"Adapter audits passed: `{summary['metrics']['adapter_audits_passed']}`",
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
