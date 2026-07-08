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
STAGE = 9298
NAME = "stage9298_post_prefix_denoise_loss_patch_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9297_boundary_next_token_probe_audit.json"
TRAINING_LOOP = ROOT / "legacy_src/agentkernel_lite/training_loop.py"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "post_prefix_denoise_loss_patch_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "POST_PREFIX_DENOISE_LOSS_PATCH_STAGE9298.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUIRED_SNIPPETS = [
    "def _post_prefix_loss_mask",
    "token_loss_mask: torch.Tensor | None = None",
    "nonpad = nonpad * token_loss_mask.to",
    "suffix_loss_mask = _post_prefix_loss_mask(batch.labels, batch_rows",
    "suffix_loss_mask = _post_prefix_loss_mask(batch.labels, split_rows",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def audit_patch() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    text = TRAINING_LOOP.read_text(encoding="utf-8") if TRAINING_LOOP.exists() else ""
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9297_not_passed")
    if metrics.get("boundary_match_rate") != 0.0:
        failures.append("source_boundary_failure_not_present")
    if missing:
        failures.append("post_prefix_loss_patch_snippets_missing")
    return {
        "passed": not failures,
        "failures": failures,
        "missing_snippets": missing,
        "source_stage": 9297,
        "source_boundary_match_rate": metrics.get("boundary_match_rate"),
        "source_boundary_mean_expected_rank": metrics.get("boundary_mean_expected_rank"),
        "post_prefix_loss_mask_present": "def _post_prefix_loss_mask" in text,
        "decoder_loss_accepts_token_mask": "token_loss_mask: torch.Tensor | None = None" in text,
        "train_loop_uses_post_prefix_mask": "suffix_loss_mask = _post_prefix_loss_mask(batch.labels, batch_rows" in text,
        "eval_loop_uses_post_prefix_mask": "suffix_loss_mask = _post_prefix_loss_mask(batch.labels, split_rows" in text,
        "execution_authorized_next": False,
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = audit_patch()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Patched denoise CE to mask copied bridge-prefix target positions and train only post-prefix suffix/EOS positions when a generation prefix is configured.",
        "next_best_step": "Build a final pre-execution audit and rerun the six-row one-next-token probe to test whether suffix-token rank improves under post-prefix loss masking.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9298 Post-Prefix Denoise Loss Patch", "", f"Passed: `{audit['passed']}`", f"Post-prefix loss mask present: `{audit['post_prefix_loss_mask_present']}`", f"Train loop uses mask: `{audit['train_loop_uses_post_prefix_mask']}`", f"Eval loop uses mask: `{audit['eval_loop_uses_post_prefix_mask']}`", "", "No execution authority is opened in this stage.", ""]) , encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
