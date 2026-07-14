#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11692_web_bridged_miss_family_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_bridged_miss_family_audit.json"
MISS_ROWS = OUT / "web_bridged_100m_miss_rows.jsonl"
GEMMA_MARGIN_ROWS = OUT / "web_bridged_gemma_margin_rows.jsonl"
BOTH_MISS_ROWS = OUT / "web_bridged_both_miss_rows.jsonl"

ROUTE_AUDIT_SCRIPT = ROOT / "scripts/build_stage11688_routed_web_identity_scorer_audit.py"
ROWS = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridged_rows.jsonl"
GEMMA_ROWS = ART / "stage11691_original_web_canonical_bridge_gemma_and_anticheat/original_web_canonical_bridge_gemma_rows.jsonl"
STAGE11691 = ART / "stage11691_original_web_canonical_bridge_gemma_and_anticheat/original_web_canonical_bridge_gemma_and_anticheat.json"


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


route_audit = load_module(ROUTE_AUDIT_SCRIPT, "stage11688_route_audit_for_11692")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("bounded_choice_target_label") or row.get("target_text") or (row.get("target") or {}).get("bounded_choice_target_label") or "").strip()


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("row_id"))


def option_by_label(row: dict[str, Any], label: str) -> dict[str, Any]:
    for option in row.get("opaque_options") or []:
        if isinstance(option, dict) and str(option.get("label")) == str(label):
            return option
    return {}


def option_role(option: dict[str, Any]) -> str:
    obj = option.get("canonical_candidate_object") if isinstance(option.get("canonical_candidate_object"), dict) else {}
    semantic = option.get("semantic_candidate") if isinstance(option.get("semantic_candidate"), dict) else {}
    return str(option.get("role") or obj.get("role") or semantic.get("role") or "unknown")


def option_value(option: dict[str, Any]) -> str:
    obj = option.get("canonical_candidate_object") if isinstance(option.get("canonical_candidate_object"), dict) else {}
    return str(obj.get("value") or option.get("text") or option.get("value") or "")


def eval_routed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    web_model, web_tokenizer, _, _ = route_audit.load_runtime(route_audit.WEB_RUNTIME)
    identity_model, identity_tokenizer, _, _ = route_audit.load_runtime(route_audit.IDENTITY_RUNTIME)
    normalized = [route_audit.base.normalize_row(row) for row in rows]
    enriched: list[dict[str, Any]] = []
    for route_name, model, tokenizer, scorer in [
        ("identity", identity_model, identity_tokenizer, route_audit.IDENTITY_SCORER),
        ("web", web_model, web_tokenizer, route_audit.WEB_SCORER),
    ]:
        route_rows = [row for row in normalized if route_audit.route(row) == route_name]
        if not route_rows:
            continue
        card = route_audit.base._write_bounded_choice_eval_audit(
            OUT,
            model=model,
            rows=route_rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=16,
            split_name=f"stage11692_bridged_web__{route_name}",
            bounded_choice_aux_source=scorer,
            eval_batch_size=8,
        )
        predictions = card.get("row_cards") or card.get("row_predictions") or card.get("predictions") or []
        by_row = {str(item.get("row_id")): item for item in predictions if isinstance(item, dict)}
        for row in route_rows:
            row_id = str(row.get("row_id"))
            pred_item = by_row.get(row_id) or {}
            target = target_label(row)
            pred = str(
                pred_item.get("constrained_choice_top1_label")
                or pred_item.get("predicted_label")
                or pred_item.get("prediction")
                or pred_item.get("predicted")
                or ""
            )
            if "constrained_choice_match" in pred_item:
                correct = pred_item.get("constrained_choice_match") is True
            else:
                correct = pred == target
            enriched.append(
                {
                    "row_id": row_id,
                    "route": route_name,
                    "scorer": scorer,
                    "hundred_m_predicted_label": pred,
                    "hundred_m_correct": correct,
                }
            )
    return enriched


def summarize(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    correct = sum(1 for row in rows if row.get(field) is True)
    return {"rows": len(rows), "correct": correct, "accuracy": correct / len(rows) if rows else None}


def group(rows: list[dict[str, Any]], key: str, field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(key) or "unknown")].append(row)
    return {name: summarize(bucket, field) for name, bucket in sorted(buckets.items())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(ROWS)
    gemma_rows = {str(row.get("row_id")): row for row in load_jsonl(GEMMA_ROWS)}
    stage11691 = load_json(STAGE11691)
    pred_rows = {row["row_id"]: row for row in eval_routed(rows)}
    joined: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        target = target_label(row)
        hundred = pred_rows.get(row_id, {})
        gemma = gemma_rows.get(row_id, {})
        target_opt = option_by_label(row, target)
        h_pred = str(hundred.get("hundred_m_predicted_label") or "")
        g_pred = str(gemma.get("gemma12b_predicted_label") or "")
        h_opt = option_by_label(row, h_pred)
        g_opt = option_by_label(row, g_pred)
        joined.append(
            {
                "row_id": row_id,
                "root_id": row.get("root_id"),
                "root_lineage_key": row.get("root_lineage_key"),
                "repo_id": row.get("repo_id"),
                "repo_family": row.get("repo_family"),
                "task_type": row.get("task_type"),
                "target_label": target,
                "target_role": option_role(target_opt),
                "target_value": option_value(target_opt),
                "hundred_m_predicted_label": h_pred,
                "hundred_m_predicted_role": option_role(h_opt) if h_opt else "missing_prediction",
                "hundred_m_predicted_value": option_value(h_opt) if h_opt else "",
                "hundred_m_correct": hundred.get("hundred_m_correct") is True,
                "hundred_m_route": hundred.get("route"),
                "hundred_m_scorer": hundred.get("scorer"),
                "gemma12b_predicted_label": g_pred,
                "gemma12b_predicted_role": option_role(g_opt) if g_opt else "missing_prediction",
                "gemma12b_predicted_value": option_value(g_opt) if g_opt else "",
                "gemma12b_correct": gemma.get("gemma12b_correct") is True,
                "miss_family": None,
            }
        )
    for row in joined:
        if row["hundred_m_correct"] and row["gemma12b_correct"]:
            family = "both_correct"
        elif row["hundred_m_correct"] and not row["gemma12b_correct"]:
            family = "hundred_m_only_correct"
        elif not row["hundred_m_correct"] and row["gemma12b_correct"]:
            family = "gemma_margin_row"
        else:
            family = "both_miss"
        row["miss_family"] = family
        if not row["hundred_m_correct"]:
            row["role_confusion"] = f"{row['target_role']} -> {row['hundred_m_predicted_role']}"
        else:
            row["role_confusion"] = "correct"
    hundred_m_misses = [row for row in joined if row["hundred_m_correct"] is not True]
    gemma_margin = [row for row in joined if row["miss_family"] == "gemma_margin_row"]
    both_miss = [row for row in joined if row["miss_family"] == "both_miss"]
    write_jsonl(MISS_ROWS, hundred_m_misses)
    write_jsonl(GEMMA_MARGIN_ROWS, gemma_margin)
    write_jsonl(BOTH_MISS_ROWS, both_miss)
    miss_task_counts = Counter(row["task_type"] for row in hundred_m_misses)
    miss_role_confusions = Counter(row["role_confusion"] for row in hundred_m_misses)
    margin_task_counts = Counter(row["task_type"] for row in gemma_margin)
    root_miss_counts = Counter(root_key(row) for row in hundred_m_misses)
    recommended = []
    if margin_task_counts:
        for task, count in margin_task_counts.most_common():
            recommended.append(f"Build disjoint canonical Web analogue roots for task_type={task}; Gemma is correct where 100M misses on {count} row(s).")
    if miss_role_confusions:
        for confusion, count in miss_role_confusions.most_common():
            if confusion != "correct":
                recommended.append(f"Add same-role/listwise support for role confusion {confusion}; observed on {count} bridged 100M miss row(s).")
    recommended.append("Do not train on these 66 heldout rows; use this as a worklist for fresh disjoint analogue materialization.")
    gates = {
        "same_manifest_joined_66_rows": len(joined) == 66,
        "hundred_m_count_matches_stage11691": summarize(joined, "hundred_m_correct")["correct"] == (stage11691.get("comparison") or {}).get("hundred_m_correct"),
        "gemma_count_matches_stage11691": summarize(joined, "gemma12b_correct")["correct"] == (stage11691.get("comparison") or {}).get("gemma12b_correct"),
        "has_gemma_margin_rows": len(gemma_margin) > 0,
        "has_worklist_outputs": MISS_ROWS.exists() and GEMMA_MARGIN_ROWS.exists() and BOTH_MISS_ROWS.exists(),
    }
    decision = "web_bridged_gap_worklist_ready" if all(gates.values()) else "web_bridged_gap_worklist_needs_review"
    summary = {
        "stage": 11692,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "scores": {
            "hundred_m": summarize(joined, "hundred_m_correct"),
            "gemma12b": summarize(joined, "gemma12b_correct"),
            "by_task_hundred_m": group(joined, "task_type", "hundred_m_correct"),
            "by_task_gemma12b": group(joined, "task_type", "gemma12b_correct"),
            "by_route_hundred_m": group(joined, "hundred_m_route", "hundred_m_correct"),
            "by_repo_hundred_m": group(joined, "repo_id", "hundred_m_correct"),
        },
        "miss_summary": {
            "hundred_m_miss_rows": len(hundred_m_misses),
            "gemma_margin_rows": len(gemma_margin),
            "both_miss_rows": len(both_miss),
            "hundred_m_only_correct_rows": sum(1 for row in joined if row["miss_family"] == "hundred_m_only_correct"),
            "miss_task_counts": dict(miss_task_counts.most_common()),
            "gemma_margin_task_counts": dict(margin_task_counts.most_common()),
            "miss_role_confusions": dict(miss_role_confusions.most_common()),
            "roots_with_100m_misses": dict(root_miss_counts.most_common()),
        },
        "gates": gates,
        "recommended_next": recommended,
        "claim_boundary": [
            "This is a miss-family audit and worklist; it does not train or promote a new runtime.",
            "Heldout rows remain heldout. Any support package should be built from disjoint analogue roots.",
            "The Web gap is now 3 rows versus Gemma on the canonical-bridged surface, but the 100M still has 13 absolute misses.",
        ],
        "source_artifacts": {
            "bridged_rows": rel(ROWS),
            "gemma_rows": rel(GEMMA_ROWS),
            "stage11691_summary": rel(STAGE11691),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "hundred_m_misses": rel(MISS_ROWS),
            "gemma_margin_rows": rel(GEMMA_MARGIN_ROWS),
            "both_miss_rows": rel(BOTH_MISS_ROWS),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "scores": summary["scores"]["hundred_m"], "miss_summary": summary["miss_summary"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
