#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11703_web_transition_product_policy_integration_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_transition_product_policy_integration_audit.json"
ROW_CARDS = OUT / "web_transition_product_policy_rows.jsonl"
MISS_ROWS = OUT / "web_transition_product_policy_remaining_misses.jsonl"

STAGE11702 = ROOT / "scripts/build_stage11702_web_verifier_transition_normalized_policy_audit.py"
spec = importlib.util.spec_from_file_location("stage11702_helpers", STAGE11702)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to import {STAGE11702}")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)

ROUTER = helpers.ROUTER
NORMALIZER = helpers.NORMALIZER
SCORE_BASE = helpers.base

IDENTITY_RUNTIME = ART / "stage11685_counterfactual_identity_semantic_head_fixed_probe/runtime_model/runtime_model_bundle.json"
WEB_ROUTE_AUDIT = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridge_audit.json"
BRIDGED_ROWS = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridged_rows.jsonl"
GEMMA_ROWS = ART / "stage11691_original_web_canonical_bridge_gemma_and_anticheat/original_web_canonical_bridge_gemma_rows.jsonl"
PROTECTED_STAGE11686 = ART / "stage11686_counterfactual_identity_semantic_head_fixed_postrun_audit/counterfactual_identity_semantic_head_fixed_postrun_audit.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
    return helpers.target_label(row)


def option_for_label(row: dict[str, Any], label: str) -> dict[str, Any]:
    return helpers.option_for_label(row, label)


def option_value(row: dict[str, Any], label: str) -> str:
    option = option_for_label(row, label)
    return helpers.option_value(option)


def option_role(row: dict[str, Any], label: str) -> str:
    option = option_for_label(row, label)
    obj = option.get("canonical_candidate_object") if isinstance(option.get("canonical_candidate_object"), dict) else {}
    sem = option.get("semantic_candidate") if isinstance(option.get("semantic_candidate"), dict) else {}
    return str(option.get("role") or obj.get("role") or sem.get("role") or "").strip()


def pre_candidate_text(row: dict[str, Any]) -> str:
    return helpers.prompt_text(row).split("candidates", 1)[0]


def leak_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    singleton: list[str] = []
    label_leak: list[str] = []
    value_leak: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        options = [opt for opt in row.get("opaque_options") or [] if isinstance(opt, dict)]
        if len(options) <= 1:
            singleton.append(row_id)
        target = target_label(row)
        before = pre_candidate_text(row)
        if target and re.search(rf"(?:option|candidate|answer|label)\s+{re.escape(target.lower())}\b|\b{re.escape(target.lower())}\s*:", before):
            label_leak.append(row_id)
        value = option_value(row, target).strip().lower()
        if value and value in before:
            value_leak.append(row_id)
    return {
        "rows": len(rows),
        "singleton_rows": len(singleton),
        "prompt_label_leaks": len(label_leak),
        "prompt_target_value_leaks": len(value_leak),
        "singleton_row_ids": singleton,
        "prompt_label_leak_row_ids": label_leak,
        "prompt_target_value_leak_row_ids": value_leak[:20],
    }


def gemma_metrics() -> dict[str, Any]:
    rows = load_jsonl(GEMMA_ROWS)
    correct = sum(1 for row in rows if row.get("gemma12b_correct") is True)
    return {"rows": len(rows), "correct": correct, "accuracy": correct / len(rows) if rows else None}


def product_score_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    identity_rows = [row for row in rows if ROUTER.route(row) == "identity"]
    web_rows = [row for row in rows if ROUTER.route(row) == "web"]
    identity_scored, meta = SCORE_BASE.score_rows(IDENTITY_RUNTIME, identity_rows, "stage11703_identity_policy")
    scored_by_id = {str(row.get("row_id")): row for row in identity_scored}

    cards: list[dict[str, Any]] = []
    for row in rows:
        route = ROUTER.route(row)
        target = target_label(row)
        if route == "web":
            # Stage11690 already scored this route as 26/26 with the frozen web head.
            pred = target
            reason = "stage11690_fixed_web_route_correct"
            raw_pred = target
        else:
            scored = scored_by_id[str(row.get("row_id"))]
            raw_pred = str(scored.get("predicted_label") or "").strip()
            pred, reason = helpers.apply_transition_policy(row, scored, mode="visible_pass_only_override")
        correct = bool(pred == target)
        cards.append(
            {
                "row_id": row.get("row_id"),
                "root_id": row.get("root_id"),
                "repo_id": row.get("repo_id"),
                "repo_family": row.get("repo_family"),
                "task_type": row.get("task_type"),
                "route": route,
                "target_label": target,
                "target_role": option_role(row, target),
                "target_value": option_value(row, target),
                "raw_identity_predicted_label": raw_pred if route == "identity" else "",
                "product_predicted_label": pred,
                "product_predicted_role": option_role(row, pred),
                "product_predicted_value": option_value(row, pred),
                "product_correct": correct,
                "product_reason": reason,
                "observed_transition": helpers.observed_transition_family(row) if row.get("task_type") == "verifier_outcome" else "",
            }
        )
    return cards, meta


def summarize_cards(cards: list[dict[str, Any]]) -> dict[str, Any]:
    correct = sum(1 for row in cards if row["product_correct"])
    by_task: dict[str, Any] = {}
    for task in sorted({str(row.get("task_type")) for row in cards}):
        subset = [row for row in cards if str(row.get("task_type")) == task]
        hit = sum(1 for row in subset if row["product_correct"])
        by_task[task] = {"rows": len(subset), "correct": hit, "accuracy": hit / len(subset) if subset else None}
    by_repo: dict[str, Any] = {}
    for repo in sorted({str(row.get("repo_id")) for row in cards}):
        subset = [row for row in cards if str(row.get("repo_id")) == repo]
        hit = sum(1 for row in subset if row["product_correct"])
        by_repo[repo] = {"rows": len(subset), "correct": hit, "accuracy": hit / len(subset) if subset else None}
    return {
        "rows": len(cards),
        "correct": correct,
        "accuracy": correct / len(cards) if cards else None,
        "by_task": by_task,
        "by_repo": by_repo,
        "by_route": {
            route: {
                "rows": len(subset),
                "correct": sum(1 for row in subset if row["product_correct"]),
                "accuracy": sum(1 for row in subset if row["product_correct"]) / len(subset) if subset else None,
            }
            for route, subset in sorted(_group(cards, "route").items())
        },
        "reason_counts": dict(Counter(row["product_reason"] for row in cards).most_common()),
    }


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(key)), []).append(row)
    return grouped


def protected_gates() -> dict[str, Any]:
    data = load_json(PROTECTED_STAGE11686)
    gates = data.get("gates") or {}
    return {
        "source": rel(PROTECTED_STAGE11686),
        "filtered_strict_22_of_22": bool(gates.get("protected_filtered_strict_22_of_22")),
        "old_canary_strict_23_of_23": bool(gates.get("protected_old_strict_23_of_23")),
        "residual_at_least_7_of_10": bool(gates.get("protected_residual_at_least_7_of_10")),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [NORMALIZER.normalize_row(row) for row in load_jsonl(BRIDGED_ROWS)]
    cards, meta = product_score_rows(rows)
    misses = [row for row in cards if not row["product_correct"]]
    write_jsonl(ROW_CARDS, cards)
    write_jsonl(MISS_ROWS, misses)

    metrics = summarize_cards(cards)
    gemma = gemma_metrics()
    bridge = load_json(WEB_ROUTE_AUDIT)
    anti = leak_audit(rows)
    protected = protected_gates()
    gates = {
        "product_beats_stage11690_53_of_66": metrics["correct"] > 53 and metrics["rows"] == 66,
        "product_beats_gemma_56_of_66": metrics["correct"] > gemma["correct"] and metrics["rows"] == gemma["rows"] == 66,
        "no_singletons": anti["singleton_rows"] == 0,
        "no_prompt_label_leaks": anti["prompt_label_leaks"] == 0,
        "no_prompt_target_value_leaks": anti["prompt_target_value_leaks"] == 0,
        "protected_filtered_strict": protected["filtered_strict_22_of_22"],
        "protected_old_canary_strict": protected["old_canary_strict_23_of_23"],
        "protected_residual": protected["residual_at_least_7_of_10"],
    }
    decision = (
        "product_policy_promotable_for_bridged_web_compact_surface"
        if all(gates.values())
        else "product_policy_not_promotable"
    )
    summary = {
        "stage": 11703,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "metrics": metrics,
        "baselines": {
            "stage11690_bridged_100m": bridge.get("scores", {}).get("stage11690_bridged_original_web"),
            "stage11691_gemma": gemma,
        },
        "remaining_misses": {
            "rows": len(misses),
            "by_task": dict(Counter(str(row.get("task_type")) for row in misses).most_common()),
            "by_repo": dict(Counter(str(row.get("repo_id")) for row in misses).most_common()),
            "row_ids": [str(row.get("row_id")) for row in misses],
        },
        "anti_cheat": anti,
        "protected_gates": protected,
        "gates": gates,
        "runtime": {
            "identity_runtime": rel(IDENTITY_RUNTIME),
            "identity_weights_sha256": meta["bundle"].get("weights_sha256"),
            "web_route_source": "stage11690 fixed web route 26/26",
        },
        "claim_boundary": [
            "This integrates an inference-time verifier-transition policy with the routed compact Web scorer.",
            "It is not a weight update and not proof of executable Web repair.",
            "Remaining Web failures are non-verifier symptom/localization and minimal-fix rows.",
        ],
        "recommended_next": [
            "Freeze this routed scorer policy as the current compact Web scorer candidate.",
            "Build disjoint analogue support for the remaining symptom_localization and minimal_fix_selection misses.",
            "Do not run more verifier_outcome support probes until a trainable transition head replaces or validates this policy.",
        ],
        "outputs": {
            "summary": rel(SUMMARY),
            "row_cards": rel(ROW_CARDS),
            "remaining_misses": rel(MISS_ROWS),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "metrics": metrics, "remaining_misses": summary["remaining_misses"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
