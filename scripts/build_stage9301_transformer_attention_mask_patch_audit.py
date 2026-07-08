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
STAGE = 9301
NAME = "stage9301_transformer_attention_mask_patch_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9300_post_prefix_boundary_probe_audit.json"
MODEL = ROOT / "legacy_src/agentkernel_lite/modeling_transformer.py"
TEST = ROOT / "tests/test_transformer_attention_masks.py"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "transformer_attention_mask_patch_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRANSFORMER_ATTENTION_MASK_PATCH_STAGE9301.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED_SNIPPETS = [
    "masked_fill(future_block, float(\"-inf\"))",
    "padding_mask = torch.zeros",
    "attn_mask = attn_mask[None, None, :, :] + padding_mask",
    "is_causal=False",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def audit_patch() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    text = MODEL.read_text(encoding="utf-8") if MODEL.exists() else ""
    test_text = TEST.read_text(encoding="utf-8") if TEST.exists() else ""
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9300_not_passed")
    if metrics.get("quality_gate_passed") is not False:
        failures.append("source_stage9300_did_not_record_quality_failure")
    if missing:
        failures.append("attention_mask_patch_snippets_missing")
    if "test_causal_attention_uses_additive_negative_infinity_mask" not in test_text:
        failures.append("causal_mask_test_missing")
    if "test_padding_attention_uses_additive_negative_infinity_mask" not in test_text:
        failures.append("padding_mask_test_missing")
    return {
        "passed": not failures,
        "failures": failures,
        "missing_snippets": missing,
        "source_stage": 9300,
        "source_boundary_match_rate": metrics.get("boundary_match_rate"),
        "source_boundary_mean_expected_rank": metrics.get("boundary_mean_expected_rank"),
        "uses_additive_future_mask": "masked_fill(future_block, float(\"-inf\"))" in text,
        "uses_additive_padding_mask": "padding_mask = torch.zeros" in text,
        "has_causal_mask_test": "test_causal_attention_uses_additive_negative_infinity_mask" in test_text,
        "has_padding_mask_test": "test_padding_attention_uses_additive_negative_infinity_mask" in test_text,
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
        "decision": "Patched transformer attention to use additive -inf causal/padding masks for PyTorch SDPA, preventing teacher-forced future-token leakage from a backwards boolean mask.",
        "next_best_step": "Build a final pre-execution audit and rerun the six-row post-prefix boundary probe with corrected causal masking.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9301 Transformer Attention Mask Patch", "", f"Passed: `{audit['passed']}`", f"Uses additive future mask: `{audit['uses_additive_future_mask']}`", f"Uses additive padding mask: `{audit['uses_additive_padding_mask']}`", f"Has causal mask test: `{audit['has_causal_mask_test']}`", f"Has padding mask test: `{audit['has_padding_mask_test']}`", "", "No execution authority is opened in this stage.", ""]) , encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
