#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9404
NAME = "stage9404_second_span_support_interference_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9403_suffix_second_span_support_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "second_span_support_interference_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SECOND_SPAN_SUPPORT_INTERFERENCE_AUDIT_STAGE9404.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict) -> None:
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
    source = load_json(SOURCE_SUMMARY)
    metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    failures: list[str] = []
    if source.get("passed") is not False or metrics.get("safety_gate_passed") is not True:
        failures.append("source_stage9403_not_safe_failed_audit")
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": 9403,
        "stage9403_heldout_exact_rows": metrics.get("heldout_exact_rows"),
        "stage9403_heldout_rows": metrics.get("heldout_rows"),
        "stage9403_exact_by_split": metrics.get("exact_by_split"),
        "stage9403_boundary_by_split": metrics.get("boundary_by_split"),
        "stage9403_short_or_junk_rows": metrics.get("short_or_junk_rows"),
        "stage9403_degenerate_repetition_rows": metrics.get("degenerate_repetition_rows"),
        "stage9403_unterminated_rows": metrics.get("unterminated_rows"),
        "stage9403_leak_rows": metrics.get("generated_internal_token_rows"),
        "regression_from_stage9399": {
            "heldout_exact_rows": "5/16 -> 0/16",
            "degenerate_repetition_rows": "0 -> 6",
            "contentful_generation": "regressed; several outputs contain malformed interpolations",
            "eval_loss": "improved numerically but generation quality regressed",
        },
        "decision": "Do not build on Stage9401/9403 second-span support as-is. It adds too much competing phrase mass and reintroduces repetition. Branch next work from the Stage9397/9399 basis instead.",
        "next_patch_contract": {
            "objective": "minimal_residual_phrase_disambiguation_manifest",
            "source_basis": "stage9397_heldout_contrastive_suffix_support_manifest",
            "avoid_source_basis": "stage9401_suffix_second_span_support_manifest",
            "row_strategy": "Add only one or two discriminative train rows for the worst residual class at a time, then probe; do not add broad multi-family support in one step.",
            "first_target": "expected_assertion_behavior vs current_repair_invariant, because these still miss boundary token and confuse semantic route.",
            "closed_authority": ["decoder_ce", "runtime", "gemma", "harness", "source_body_emission", "promotion"],
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"],
        "next_best_step": "Build a minimal residual phrase-disambiguation manifest from the Stage9397/9399 basis, starting with expected_assertion_behavior vs current_repair_invariant.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9404 Second-Span Support Interference Audit",
                "",
                f"Passed: `{audit['passed']}`",
                "",
                "Stage9403 stayed safe but regressed generation quality.",
                "",
                "- Heldout exact: `5/16 -> 0/16` compared with Stage9399.",
                "- Degenerate repetition rows: `0 -> 6`.",
                "- Eval/strict loss improved numerically, but generation quality got worse.",
                "",
                "Decision: do not continue from the Stage9401 broad second-span support manifest.",
                "",
                "Next: branch from Stage9397/9399 and add minimal residual phrase-disambiguation rows, starting with `expected assertion behavior` versus `current repair invariant`.",
                "",
                "Decoder CE, runtime, Gemma, harness, source/body emission, and promotion remain closed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "next": summary["next_best_step"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
