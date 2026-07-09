#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9715
NAME = "stage9715_software_maintenance_context_sufficiency_audit"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
TRAINING_DATA = ROOT / "legacy_src/agentkernel_lite/training_data.py"
SYMBOL_BINDING_MANIFEST = ROOT / "runs/local/artifacts/stage9714_isolated_symbol_binding_objectives/symbol_binding_test_coverage_binary.jsonl"
FIVE_WAY_SYMBOL_BINDING = ROOT / "runs/local/artifacts/stage9711_symbol_binding_retrieval_test_evidence_repair/symbol_binding_retrieval_test_evidence.jsonl"
LONG_CONTEXT_ROWS = ROOT / "runs/local/artifacts/session_like_source_inventory_real/augmented_session_packs_v3_5m/long_context_pack_training_rows.jsonl"
EXTERNAL_COMMIT_PACK_ROWS = ROOT / "runs/local/artifacts/external_repo_commit_family_scale/augmented_selected_repo_commit_packs_testtouch_top40_strict_realindex_10m_family_reuse/long_context_pack_training_rows.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "software_maintenance_context_sufficiency_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOFTWARE_MAINTENANCE_CONTEXT_SUFFICIENCY_STAGE9715.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUIRED_CONTEXT_ROLES = {
    "seed_change",
    "verification_constraint",
    "test_neighbor",
    "repo_graph_neighbor",
    "trace_analogue",
    "algorithm_grounding",
    "cross_repo_analogue",
}
LOCAL_FIRST_SOURCE_TYPES = {"repo", "code", "git", "test", "source"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
                if limit is not None and len(rows) >= limit:
                    break
    return rows


def trainer_default_max_encoder_tokens() -> int | None:
    text = TRAINER.read_text(encoding="utf-8")
    match = re.search(r'--max-encoder-tokens",\s*type=_positive_int,\s*default=(\d+)', text)
    return int(match.group(1)) if match else None


def build_batch_default_max_encoder_tokens() -> int | None:
    tree = ast.parse(TRAINING_DATA.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build_batch":
            args = node.args
            defaults = args.defaults + args.kw_defaults
            names = [arg.arg for arg in args.args] + [arg.arg for arg in args.kwonlyargs]
            for name, default in zip(names[-len(defaults) :], defaults):
                if name == "max_encoder_tokens" and isinstance(default, ast.Constant):
                    return int(default.value)
    return None


def row_text_serializes_context_rows() -> bool:
    text = TRAINING_DATA.read_text(encoding="utf-8")
    start = text.index("def _row_text")
    end = text.index("def build_batch", start)
    return "context_rows" in text[start:end]


def context_pack_card(path: Path) -> dict[str, Any]:
    rows = load_jsonl(path, limit=3)
    if not rows:
        return {"path": str(path.relative_to(ROOT)), "exists": path.exists(), "rows_sampled": 0}
    first = rows[0]
    context_rows = first.get("context_rows") if isinstance(first.get("context_rows"), list) else []
    roles = Counter(str(row.get("role")) for row in context_rows if isinstance(row, dict) and row.get("role") is not None)
    source_types = Counter(str(row.get("source_type")) for row in context_rows if isinstance(row, dict))
    first_context = context_rows[0] if context_rows and isinstance(context_rows[0], dict) else {}
    local_first = str(first_context.get("source_type")) in LOCAL_FIRST_SOURCE_TYPES
    return {
        "path": str(path.relative_to(ROOT)),
        "exists": True,
        "rows_sampled": len(rows),
        "first_pack_id": first.get("pack_id"),
        "first_pack_token_count": first.get("pack_token_count"),
        "first_context_row_count": len(context_rows),
        "context_role_counts": dict(roles),
        "context_roles_preserved": bool(roles),
        "missing_required_roles": sorted(REQUIRED_CONTEXT_ROLES - set(roles)),
        "source_type_counts_top": dict(source_types.most_common(8)),
        "first_context_source_type": first_context.get("source_type"),
        "first_context_path": first_context.get("path"),
        "first_context_has_role": "role" in first_context,
        "first_context_local_evidence_first": local_first,
        "first_context_text_prefix": str(first_context.get("text") or "")[:160],
    }


def manifest_context_card(path: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    context_rows = sum(1 for row in rows if row.get("context_rows"))
    model_input_rows = sum(1 for row in rows if row.get("model_input"))
    graph_node_types: Counter[str] = Counter()
    for row in rows:
        graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
        for node in graph.get("nodes") if isinstance(graph.get("nodes"), list) else []:
            if isinstance(node, dict):
                graph_node_types[str(node.get("node_type"))] += 1
    return {
        "path": str(path.relative_to(ROOT)),
        "rows": len(rows),
        "context_rows_present": context_rows,
        "model_input_rows": model_input_rows,
        "graph_node_types": dict(graph_node_types),
        "has_candidate_symbol_nodes": graph_node_types.get("symbol_candidate", 0) > 0,
        "has_test_coverage_nodes": graph_node_types.get("coverage_evidence", 0) > 0,
        "has_raw_context_rows": context_rows > 0,
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    trainer_default = trainer_default_max_encoder_tokens()
    batch_default = build_batch_default_max_encoder_tokens()
    serializes_context = row_text_serializes_context_rows()
    long_context_cards = [context_pack_card(LONG_CONTEXT_ROWS), context_pack_card(EXTERNAL_COMMIT_PACK_ROWS)]
    manifest_cards = [manifest_context_card(SYMBOL_BINDING_MANIFEST), manifest_context_card(FIVE_WAY_SYMBOL_BINDING)]

    blockers: list[str] = []
    if trainer_default is None or trainer_default <= 256:
        blockers.append(f"trainer_default_max_encoder_tokens_toy:{trainer_default}")
    if batch_default is None or batch_default <= 256:
        blockers.append(f"build_batch_default_max_encoder_tokens_toy:{batch_default}")
    if not serializes_context:
        blockers.append("row_text_does_not_serialize_context_rows")
    if any(not card.get("context_roles_preserved") for card in long_context_cards):
        blockers.append("long_context_pack_training_rows_drop_context_roles")
    if any(not card.get("first_context_local_evidence_first") for card in long_context_cards):
        blockers.append("long_context_pack_first_context_not_local_evidence")
    if any(card.get("context_rows_present") == 0 for card in manifest_cards):
        blockers.append("active_symbol_binding_manifests_have_no_context_rows")

    next_step = (
        "Patch the context compiler/trainer handoff so maintenance rows carry role-preserved, task-closed context_rows into encoder text; then rerun this sufficiency audit before more target-100M probes."
    )
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": True,
        "quality_passed": False,
        "training_blocked_by_context_sufficiency": bool(blockers),
        "promotion_ready": False,
        "blockers": blockers,
        "trainer": {
            "trainer_default_max_encoder_tokens": trainer_default,
            "build_batch_default_max_encoder_tokens": batch_default,
            "row_text_serializes_context_rows": serializes_context,
            "training_data_path": str(TRAINING_DATA.relative_to(ROOT)),
            "trainer_path": str(TRAINER.relative_to(ROOT)),
        },
        "long_context_packs": long_context_cards,
        "active_manifests": manifest_cards,
        "required_context_roles": sorted(REQUIRED_CONTEXT_ROLES),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": True,
        "quality_passed": False,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "metrics": {
            "training_blocked_by_context_sufficiency": bool(blockers),
            "blocker_count": len(blockers),
            "trainer_default_max_encoder_tokens": trainer_default,
            "row_text_serializes_context_rows": serializes_context,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9715 Software Maintenance Context Sufficiency Audit",
                "",
                "Stage9715 checks whether the current trainer path actually gives the 100M maintainer model task-closed software evidence.",
                "",
                "## Finding",
                "",
                f"- Training blocked by context sufficiency: `{bool(blockers)}`",
                f"- Trainer default max encoder tokens: `{trainer_default}`",
                f"- `build_batch` default max encoder tokens: `{batch_default}`",
                f"- `_row_text` serializes `context_rows`: `{serializes_context}`",
                "",
                "## Blockers",
                "",
                *[f"- `{blocker}`" for blocker in blockers],
                "",
                "## Next",
                "",
                next_step,
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
