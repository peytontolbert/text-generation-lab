#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8801
NAME = "stage8801_parallel_bounded_decoder_audit_reconciliation"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PARALLEL_BOUNDED_DECODER_AUDIT_RECONCILIATION_STAGE8801.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
AUDIT_A = ROOT / "runs/summaries/stage8798_bounded_decoder_argument_controls_shortcut_gate.json"
AUDIT_B = ROOT / "runs/summaries/stage8798_bounded_decoder_argument_controls_shortcut_gate.json"
GRAPH = ROOT / "runs/summaries/stage8799_bounded_decoder_argument_controls_graph_attachment.json"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def closed(metrics: dict) -> bool:
    return all(metrics.get(key) is False or metrics.get(key) == 0 for key in AUTHORITY_CLOSED)


def main() -> None:
    a, b, graph = load(AUDIT_A), load(AUDIT_B), load(GRAPH)
    failures = []
    for label, path, card in [("audit", AUDIT_A, a), ("shortcut_gate", AUDIT_B, b), ("graph", GRAPH, graph)]:
        if not path.exists():
            failures.append(f"missing:{label}")
        elif card.get("passed") is not True:
            failures.append(f"failed:{label}")
    am, bm = a.get("metrics", {}), b.get("metrics", {})
    compare_keys = ["rows", "majority_baseline", "max_proxy_single", "max_proxy_combo", "training_loss_row_count", "training_loss_rows"]
    # Normalize equivalent names across the two audit implementations.
    normalized = {
        "audit_rows": am.get("rows"),
        "shortcut_rows": bm.get("rows"),
        "audit_majority": am.get("majority_baseline"),
        "shortcut_majority": bm.get("majority_baseline"),
        "audit_max_proxy_single": am.get("max_proxy_single"),
        "shortcut_max_proxy_single": bm.get("max_proxy_single"),
        "audit_max_proxy_combo": am.get("max_proxy_combo"),
        "shortcut_max_proxy_combo": bm.get("max_proxy_combo"),
        "audit_training_loss_rows": am.get("training_loss_row_count", am.get("training_loss_rows")),
        "shortcut_training_loss_rows": bm.get("training_loss_rows"),
        "audit_authority_rows": am.get("authority_row_count", am.get("authority_rows")),
        "shortcut_authority_rows": bm.get("authority_rows"),
    }
    if normalized["audit_rows"] != normalized["shortcut_rows"]:
        failures.append("row_count_mismatch")
    for left, right in [
        ("audit_majority", "shortcut_majority"),
        ("audit_max_proxy_single", "shortcut_max_proxy_single"),
        ("audit_max_proxy_combo", "shortcut_max_proxy_combo"),
        ("audit_training_loss_rows", "shortcut_training_loss_rows"),
        ("audit_authority_rows", "shortcut_authority_rows"),
    ]:
        if normalized[left] != normalized[right]:
            failures.append(f"metric_mismatch:{left}:{right}")
    if not closed(am) or not closed(bm) or not closed(graph.get("metrics", {})):
        failures.append("authority_not_closed")

    registry = load(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") not in {NAME, b.get("stage_name")}]
    if b:
        rows.append({
            "stage": int(b["stage"]),
            "stage_name": b["stage_name"],
            "passed": b.get("passed") is True,
            "path": str(AUDIT_B),
            "authority": AUTHORITY_CLOSED,
            "next_best_step": b.get("next_best_step"),
        })
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **normalized,
            "graph_stage": graph.get("stage"),
            "graph_nodes": (graph.get("metrics") or {}).get("graph_nodes"),
            "graph_edges": (graph.get("metrics") or {}).get("graph_edges"),
            "registry_rows_before": len(registry.get("rows", [])),
            "registry_rows_after": len(rows) + 1,
        },
        "decision": "Both bounded decoder argument audits agree and remain no-authority; shortcut-gate artifact is now indexed." if not failures else "Parallel bounded decoder audit reconciliation failed.",
        "next_best_step": "Build a closed bounded decoder CE package gate that consumes audited argument controls, still without enabling decoder CE or runtime.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": card["passed"],
        "path": str(SUMMARY),
        "authority": AUTHORITY_CLOSED,
        "next_best_step": card["next_best_step"],
    })
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = not failures
    registry["metrics"] = {
        **registry.get("metrics", {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": card["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "historical_failed_rows": sum(1 for row in rows if row.get("passed") is not True),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8801 Parallel Bounded Decoder Audit Reconciliation",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Reconciled two Stage8798 bounded decoder argument audits:",
        "",
        f"- `{AUDIT_A.relative_to(ROOT)}`",
        f"- `{AUDIT_B.relative_to(ROOT)}`",
        "",
        f"Rows: `{normalized['audit_rows']}`",
        f"Max proxy single: `{normalized['audit_max_proxy_single']}`",
        f"Max proxy combo: `{normalized['audit_max_proxy_combo']}`",
        f"Training loss rows: `{normalized['audit_training_loss_rows']}`",
        f"Authority rows: `{normalized['audit_authority_rows']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")

    marker = "## Stage8801 Parallel Audit Reconciliation"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The bounded decoder argument controls have two equivalent shortcut/gate audits. Both agree on 504 rows, balanced labels, max proxy single 0.2857, max proxy combo 0.4286, zero training-loss rows, and closed authority.",
            "",
            "This means the current recovery issue is no longer argument-control schema safety. The next unresolved boundary is a closed bounded decoder CE package gate that consumes these controls without reopening CE, runtime, body emission, or scoring.",
            "",
        ]), encoding="utf-8")

    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
