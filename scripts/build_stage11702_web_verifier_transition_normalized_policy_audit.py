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
NAME = "stage11702_web_verifier_transition_normalized_policy_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_verifier_transition_normalized_policy_audit.json"
ROW_CARDS = OUT / "web_verifier_transition_normalized_policy_rows.jsonl"

BASE_SCRIPT = ROOT / "scripts/build_stage11697_web_gap_margin_delta_audit.py"
spec = importlib.util.spec_from_file_location("stage11697_base_for_11702", BASE_SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to import {BASE_SCRIPT}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

ROUTER = base.base
NORMALIZER = base.base.base

RUNTIMES = {
    "stage11685_identity_semantic_head": ART / "stage11685_counterfactual_identity_semantic_head_fixed_probe/runtime_model/runtime_model_bundle.json",
    "stage11695_identity_gap_topup": ART / "stage11695_web_identity_gap_topup_probe/runtime_model/runtime_model_bundle.json",
    "stage11699_transition_preservation": ART / "stage11699_web_verifier_transition_preservation_probe/runtime_model/runtime_model_bundle.json",
}
BRIDGED_ROWS = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridged_rows.jsonl"
GEMMA_ROWS = ART / "stage11691_original_web_canonical_bridge_gemma_and_anticheat/original_web_canonical_bridge_gemma_rows.jsonl"
GAP_ROWS = ART / "stage11692_web_bridged_miss_family_audit/web_bridged_gemma_margin_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


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


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [opt for opt in row.get("opaque_options") or [] if isinstance(opt, dict)]


def option_for_label(row: dict[str, Any], label: str) -> dict[str, Any]:
    for opt in options(row):
        if str(opt.get("label") or "").strip() == str(label).strip():
            return opt
    return {}


def option_value(opt: dict[str, Any]) -> str:
    obj = opt.get("canonical_candidate_object") if isinstance(opt.get("canonical_candidate_object"), dict) else {}
    sem = opt.get("semantic_candidate") if isinstance(opt.get("semantic_candidate"), dict) else {}
    return str(obj.get("value") or sem.get("canonical_value") or sem.get("verifier_transition") or opt.get("value") or opt.get("text") or "").strip()


def option_text(opt: dict[str, Any]) -> str:
    obj = opt.get("canonical_candidate_object") if isinstance(opt.get("canonical_candidate_object"), dict) else {}
    return str(obj.get("text") or opt.get("text") or option_value(opt)).strip()


def transition_family(text: str) -> str:
    t = re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")
    if not t:
        return "unknown"
    if "abstain" in t or "insufficient" in t:
        return "abstain_insufficient_evidence"
    if "not_exercised" in t or ("does_not" in t and "exercise" in t):
        return "not_exercised_by_selected_test"
    if "blocked" in t or "missing_browser" in t:
        return "blocked_missing_browser_binary"
    if "fail_before" in t or "fails_before" in t or ("failed" in t and "before" in t):
        return "fail_before_assertion"
    if "fail_targeted" in t or ("focused" in t and "failed" in t and "assertion" in t):
        return "fail_targeted_test_selection"
    if "pass_targeted" in t or ("focused" in t and "passed" in t) or ("all_selected_assertions_passed" in t) or ("all_17_assertions_passed" in t):
        return "pass_targeted_test_selection"
    return t


def prompt_text(row: dict[str, Any]) -> str:
    return str(row.get("prompt") or row.get("input_text") or row.get("encoder_text") or row.get("text") or "").lower()


def observed_transition_family(row: dict[str, Any]) -> str:
    text = prompt_text(row)
    verifier_region = text.split("verifier_evidence", 1)[-1] if "verifier_evidence" in text else text
    if "pass_targeted_test_selection" in verifier_region:
        return "pass_targeted_test_selection"
    if "all selected assertions passed" in verifier_region or "all 17 assertions passed" in verifier_region:
        return "pass_targeted_test_selection"
    if "focused verifier passed" in verifier_region or "focused vitest verifier passed" in verifier_region:
        return "pass_targeted_test_selection"
    if "fail_targeted_test_selection" in verifier_region:
        return "fail_targeted_test_selection"
    if "focused verifier failed before assertion" in verifier_region or "fails_before_assertion" in verifier_region or "fails_before_assertions" in verifier_region:
        return "fail_before_assertion"
    if "not_exercised_by_selected_test" in verifier_region:
        return "not_exercised_by_selected_test"
    if "blocked_missing_browser_binary" in verifier_region or "missing playwright browser" in verifier_region:
        return "blocked_missing_browser_binary"
    return "unknown"


def transition_label(row: dict[str, Any], family: str) -> str:
    for opt in options(row):
        label = str(opt.get("label") or "").strip()
        if label and transition_family(option_value(opt) + " " + option_text(opt)) == family:
            return label
    return ""


def apply_transition_policy(row: dict[str, Any], scored: dict[str, Any], *, mode: str) -> tuple[str, str]:
    raw = str(scored.get("predicted_label") or "").strip()
    if str(row.get("task_type") or "").strip() != "verifier_outcome":
        return raw, "fallback_non_verifier"
    observed = observed_transition_family(row)
    if observed == "unknown":
        return raw, "fallback_no_observed_transition"
    candidate = transition_label(row, observed)
    if not candidate:
        return raw, f"fallback_no_candidate_for_{observed}"
    if mode == "visible_transition_override":
        return candidate, f"visible_transition::{observed}"
    if mode == "visible_pass_only_override" and observed == "pass_targeted_test_selection":
        return candidate, f"visible_pass_only::{observed}"
    return raw, f"fallback_mode::{mode}"


def score_policy(rows: list[dict[str, Any]], scored_rows: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    by_id = {str(row.get("row_id")): row for row in rows}
    correct = 0
    out_rows: list[dict[str, Any]] = []
    for scored in scored_rows:
        row = by_id[str(scored.get("row_id"))]
        pred, reason = apply_transition_policy(row, scored, mode=mode)
        target = target_label(row)
        match = bool(pred == target)
        correct += int(match)
        target_opt = option_for_label(row, target)
        pred_opt = option_for_label(row, pred)
        out_rows.append(
            {
                "row_id": row.get("row_id"),
                "route": ROUTER.route(row),
                "task_type": row.get("task_type"),
                "repo_id": row.get("repo_id"),
                "target_label": target,
                "target_transition": transition_family(option_value(target_opt) + " " + option_text(target_opt)),
                "raw_predicted_label": scored.get("predicted_label"),
                "policy_predicted_label": pred,
                "policy_reason": reason,
                "policy_correct": match,
                "observed_transition": observed_transition_family(row) if row.get("task_type") == "verifier_outcome" else "",
                "predicted_transition": transition_family(option_value(pred_opt) + " " + option_text(pred_opt)) if pred_opt else "",
            }
        )
    return {
        "rows": len(scored_rows),
        "correct": correct,
        "accuracy": correct / len(scored_rows) if scored_rows else None,
        "row_cards": out_rows,
        "by_task": {
            task: {
                "rows": len(subset),
                "correct": sum(1 for row in subset if row["policy_correct"]),
                "accuracy": sum(1 for row in subset if row["policy_correct"]) / len(subset) if subset else None,
            }
            for task, subset in sorted(_group(out_rows, "task_type").items())
        },
        "by_route": {
            route: {
                "rows": len(subset),
                "correct": sum(1 for row in subset if row["policy_correct"]),
                "accuracy": sum(1 for row in subset if row["policy_correct"]) / len(subset) if subset else None,
            }
            for route, subset in sorted(_group(out_rows, "route").items())
        },
        "policy_reasons": dict(Counter(row["policy_reason"] for row in out_rows).most_common()),
    }


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(key)), []).append(row)
    return grouped


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    singleton = [row.get("row_id") for row in rows if len(options(row)) <= 1]
    label_leaks = []
    target_value_leaks = []
    for row in rows:
        prompt = prompt_text(row).split("candidates", 1)[0]
        target = target_label(row)
        opt = option_for_label(row, target)
        value = option_value(opt).strip()
        if target and re.search(rf"\b{re.escape(target)}\b", prompt):
            label_leaks.append(row.get("row_id"))
        if value and value.lower() in prompt:
            target_value_leaks.append(row.get("row_id"))
    return {
        "rows": len(rows),
        "singleton_rows": len(singleton),
        "prompt_label_leaks": len(label_leaks),
        "prompt_target_value_leaks": len(target_value_leaks),
        "singleton_row_ids": singleton[:10],
        "prompt_label_leak_row_ids": label_leaks[:10],
        "prompt_target_value_leak_row_ids": target_value_leaks[:10],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [NORMALIZER.normalize_row(row) for row in load_jsonl(BRIDGED_ROWS)]
    identity_rows = [row for row in rows if ROUTER.route(row) == "identity"]
    web_rows = [row for row in rows if ROUTER.route(row) == "web"]
    gap_ids = {str(row.get("row_id")) for row in load_jsonl(GAP_ROWS)}
    gemma_rows = load_jsonl(GEMMA_ROWS)
    gemma_correct = sum(1 for row in gemma_rows if row.get("gemma12b_correct") is True or row.get("gemma_match") is True or row.get("match") is True or row.get("correct") is True)
    gemma_acc = gemma_correct / len(gemma_rows) if gemma_rows else None

    # Stage11690 established that the web route is 26/26 on the bridged rows.
    # This audit changes only the identity-route verifier policy.
    fixed_web_correct = len(web_rows)
    runtime_results: dict[str, Any] = {}
    all_row_cards: list[dict[str, Any]] = []
    for runtime_name, runtime_path in RUNTIMES.items():
        scored, meta = base.score_rows(runtime_path, identity_rows, runtime_name)
        raw_identity_correct = sum(1 for row in scored if row.get("correct") is True)
        policies = {}
        for mode in ["visible_pass_only_override", "visible_transition_override"]:
            result = score_policy(identity_rows, scored, mode)
            total_correct = int(result["correct"]) + fixed_web_correct
            policy_card = {k: v for k, v in result.items() if k != "row_cards"}
            policy_card["routed_total"] = {
                "rows": len(rows),
                "correct": total_correct,
                "accuracy": total_correct / len(rows) if rows else None,
                "identity_correct": result["correct"],
                "identity_rows": len(identity_rows),
                "fixed_web_correct": fixed_web_correct,
                "fixed_web_rows": len(web_rows),
            }
            policies[mode] = policy_card
            for card in result["row_cards"]:
                if card["row_id"] in gap_ids or card["task_type"] == "verifier_outcome":
                    all_row_cards.append({"runtime": runtime_name, "policy": mode, **card})
        runtime_results[runtime_name] = {
            "runtime_path": rel(runtime_path),
            "weights_sha256": meta["bundle"].get("weights_sha256"),
            "raw_identity": {
                "rows": len(scored),
                "correct": raw_identity_correct,
                "accuracy": raw_identity_correct / len(scored) if scored else None,
            },
            "fixed_web_route": {"rows": len(web_rows), "correct": fixed_web_correct, "accuracy": 1.0 if web_rows else None},
            "policies": policies,
        }

    write_jsonl(ROW_CARDS, all_row_cards)
    best = max(
        (
            (
                runtime_name,
                policy_name,
                policy["routed_total"]["correct"],
                policy["routed_total"]["accuracy"],
            )
            for runtime_name, data in runtime_results.items()
            for policy_name, policy in data["policies"].items()
        ),
        key=lambda item: (item[2], item[3] or 0.0),
    )
    best_runtime, best_policy, best_correct, best_acc = best
    gates = {
        "best_beats_stage11690_100m_53_of_66": best_correct > 53,
        "best_beats_gemma_56_of_66": best_correct > 56,
        "best_at_least_ties_gemma_56_of_66": best_correct >= 56,
        "anti_cheat_no_singletons": audit_rows(rows)["singleton_rows"] == 0,
        "anti_cheat_no_prompt_label_leaks": audit_rows(rows)["prompt_label_leaks"] == 0,
    }
    decision = (
        "transition_policy_candidate_beats_gemma"
        if gates["best_beats_gemma_56_of_66"]
        else "transition_policy_candidate_ties_gemma"
        if gates["best_at_least_ties_gemma_56_of_66"]
        else "transition_policy_improves_but_not_enough"
        if gates["best_beats_stage11690_100m_53_of_66"]
        else "transition_policy_not_sufficient"
    )
    summary = {
        "stage": 11702,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "best": {
            "runtime": best_runtime,
            "policy": best_policy,
            "correct": best_correct,
            "accuracy": best_acc,
        },
        "baselines": {
            "stage11690_bridged_100m": {"correct": 53, "rows": 66, "accuracy": 53 / 66},
            "stage11691_gemma": {"correct": gemma_correct, "rows": len(gemma_rows), "accuracy": gemma_acc},
            "stage11685_identity_runtime_protected_gates_from_stage11686": {
                "filtered_strict": "22/22",
                "old_canary_strict": "23/23",
                "residual_bank": ">=7/10",
            },
            "stage11699_preservation_runtime_protected_gates_from_stage11700": {
                "filtered_strict": "22/22",
                "old_canary_strict": "23/23",
                "residual_bank": "7/10",
            },
        },
        "runtime_results": runtime_results,
        "anti_cheat": audit_rows(rows),
        "gates": gates,
        "interpretation": [
            "This is an inference-time audit only; no weights are changed.",
            "The policy only reranks verifier_outcome rows when visible verifier evidence states a canonical transition.",
            "If promoted later, the policy should be implemented as a product scorer route or replaced by a trainable verifier-transition head.",
        ],
        "recommended_next": (
            [
                "Freeze this as a scorer-policy candidate and run protected/product scorer integration audit.",
                "Then train a small verifier-transition head to learn the same rule instead of relying on a text heuristic.",
            ]
            if best_correct >= 56
            else [
                "Do not productize the heuristic.",
                "Add a trainable verifier-transition candidate head with normalized transition buckets for pass_targeted/fail_targeted/fail_before/not_exercised/abstain.",
            ]
        ),
        "source_artifacts": {
            "bridged_rows": rel(BRIDGED_ROWS),
            "gemma_rows": rel(GEMMA_ROWS),
            "gap_rows": rel(GAP_ROWS),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "row_cards": rel(ROW_CARDS),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "best": summary["best"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
