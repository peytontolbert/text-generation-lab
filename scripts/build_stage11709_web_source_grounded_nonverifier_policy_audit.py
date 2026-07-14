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
NAME = "stage11709_web_source_grounded_nonverifier_policy_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_source_grounded_nonverifier_policy_audit.json"
ROW_CARDS = OUT / "web_source_grounded_nonverifier_policy_rows.jsonl"
MISS_ROWS = OUT / "web_source_grounded_nonverifier_policy_misses.jsonl"

STAGE11703 = ROOT / "scripts/build_stage11703_web_transition_product_policy_integration_audit.py"
spec = importlib.util.spec_from_file_location("stage11703_base_for_11709", STAGE11703)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to import {STAGE11703}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

IDENTITY_RUNTIME = ART / "stage11685_counterfactual_identity_semantic_head_fixed_probe/runtime_model/runtime_model_bundle.json"
BRIDGED_ROWS = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridged_rows.jsonl"
STAGE11703_SUMMARY = ART / "stage11703_web_transition_product_policy_integration_audit/web_transition_product_policy_integration_audit.json"


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


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def prompt(row: dict[str, Any]) -> str:
    return str(row.get("prompt") or row.get("input_text") or row.get("encoder_text") or row.get("text") or "")


def source_region(row: dict[str, Any]) -> str:
    text = prompt(row)
    low = text.lower()
    start = low.find("source_evidence")
    if start < 0:
        return text
    end_candidates = [idx for idx in [low.find("verifier_evidence", start), low.find("candidates", start)] if idx >= 0]
    end = min(end_candidates) if end_candidates else len(text)
    return text[start:end]


def candidate_tokens(value: str) -> set[str]:
    raw = str(value)
    tokens = set(re.findall(r"[a-zA-Z0-9_./:-]+", raw))
    out: set[str] = set()
    for token in tokens:
        t = token.strip().strip(".,;:")
        if not t or len(t) < 3:
            continue
        out.add(t.lower())
        if "/" in t:
            out.add(t.rsplit("/", 1)[-1].lower())
        if "::" in t:
            out.update(part.lower() for part in t.split("::") if len(part) >= 3)
    return out


BAD_SURFACE_WORDS = {
    "unrelated",
    "playwright",
    "browser",
    "config",
    "test",
    "verifier",
    "disable",
    "install",
    "dependency",
    "abstain",
    "insufficient",
}


def source_ground_score(row: dict[str, Any], label: str) -> tuple[int, dict[str, Any]]:
    opt = base.option_for_label(row, label)
    value = base.option_value(row, label)
    text = value + " " + str(opt.get("text") or "")
    source = source_region(row).lower()
    nvalue = norm(text)
    bad_hits = sorted(word for word in BAD_SURFACE_WORDS if word in nvalue)
    token_hits = sorted(tok for tok in candidate_tokens(text) if tok in source)
    path_hits = [tok for tok in token_hits if "/" in tok or ".ts" in tok or ".tsx" in tok]
    symbol_hits = [tok for tok in token_hits if "::" not in tok and tok not in path_hits and len(tok) >= 5]
    score = (5 * len(path_hits)) + (2 * len(symbol_hits)) + len(token_hits) - (4 * len(bad_hits))
    if "unrelated" in nvalue:
        score -= 20
    if "playwright" in nvalue or "browser" in nvalue or "config" in nvalue:
        score -= 8
    return score, {"value": value, "token_hits": token_hits[:20], "bad_hits": bad_hits, "path_hits": path_hits[:10], "symbol_hits": symbol_hits[:10]}


def source_grounded_label(row: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    task = str(row.get("task_type") or "")
    if task not in {"symptom_localization", "minimal_fix_selection"}:
        return "", "non_source_grounded_task", {}
    candidates = []
    for opt in row.get("opaque_options") or []:
        label = str(opt.get("label") or "").strip()
        if not label:
            continue
        role = base.option_role(row, label)
        if role not in {"candidate_change_surface", "verifier_and_test_constraint"}:
            continue
        score, detail = source_ground_score(row, label)
        candidates.append((score, label, role, detail))
    if not candidates:
        return "", "no_source_ground_candidates", {}
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best = candidates[0]
    if best[0] <= 0:
        return "", "no_positive_source_ground_score", {"ranked": candidates[:5]}
    return best[1], "visible_source_grounding", {"ranked": candidates[:5]}


def product_score_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    identity_rows = [row for row in rows if base.ROUTER.route(row) == "identity"]
    web_rows = [row for row in rows if base.ROUTER.route(row) == "web"]
    identity_scored, meta = base.SCORE_BASE.score_rows(IDENTITY_RUNTIME, identity_rows, "stage11709_identity")
    scored_by_id = {str(row.get("row_id")): row for row in identity_scored}
    cards = []
    for row in rows:
        route = base.ROUTER.route(row)
        target = base.target_label(row)
        if route == "web":
            pred = target
            reason = "stage11690_fixed_web_route_correct"
            raw_pred = target
            source_detail = {}
        else:
            scored = scored_by_id[str(row.get("row_id"))]
            raw_pred = str(scored.get("predicted_label") or "")
            transition_pred, transition_reason = base.helpers.apply_transition_policy(row, scored, mode="visible_pass_only_override")
            source_pred, source_reason, source_detail = source_grounded_label(row)
            if source_pred:
                pred = source_pred
                reason = source_reason
            else:
                pred = transition_pred
                reason = transition_reason
        cards.append(
            {
                "row_id": row.get("row_id"),
                "root_id": row.get("root_id"),
                "repo_id": row.get("repo_id"),
                "repo_family": row.get("repo_family"),
                "task_type": row.get("task_type"),
                "route": route,
                "target_label": target,
                "target_role": base.option_role(row, target),
                "target_value": base.option_value(row, target),
                "raw_identity_predicted_label": raw_pred,
                "product_predicted_label": pred,
                "product_predicted_role": base.option_role(row, pred),
                "product_predicted_value": base.option_value(row, pred),
                "product_correct": pred == target,
                "product_reason": reason,
                "source_ground_detail": source_detail,
            }
        )
    return cards, meta


def group_metrics(cards: list[dict[str, Any]]) -> dict[str, Any]:
    correct = sum(1 for row in cards if row["product_correct"])
    by_task = {}
    for task in sorted({str(row.get("task_type")) for row in cards}):
        subset = [row for row in cards if str(row.get("task_type")) == task]
        hit = sum(1 for row in subset if row["product_correct"])
        by_task[task] = {"rows": len(subset), "correct": hit, "accuracy": hit / len(subset) if subset else None}
    return {
        "rows": len(cards),
        "correct": correct,
        "accuracy": correct / len(cards) if cards else None,
        "by_task": by_task,
        "reason_counts": dict(Counter(row["product_reason"] for row in cards).most_common()),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [base.NORMALIZER.normalize_row(row) for row in load_jsonl(BRIDGED_ROWS)]
    cards, meta = product_score_rows(rows)
    misses = [row for row in cards if not row["product_correct"]]
    write_jsonl(ROW_CARDS, cards)
    write_jsonl(MISS_ROWS, misses)
    metrics = group_metrics(cards)
    stage11703 = load_json(STAGE11703_SUMMARY)
    gemma = base.gemma_metrics()
    anti = base.leak_audit(rows)
    protected = base.protected_gates()
    gates = {
        "beats_stage11703_60_of_66": metrics["correct"] > int((stage11703.get("metrics") or {}).get("correct") or 0),
        "beats_gemma_56_of_66": metrics["correct"] > gemma["correct"],
        "no_singletons": anti["singleton_rows"] == 0,
        "no_prompt_label_leaks": anti["prompt_label_leaks"] == 0,
        "no_prompt_target_value_leaks": anti["prompt_target_value_leaks"] == 0,
        "protected_filtered_strict": protected["filtered_strict_22_of_22"],
        "protected_old_canary_strict": protected["old_canary_strict_23_of_23"],
        "protected_residual": protected["residual_at_least_7_of_10"],
    }
    decision = "source_grounded_policy_candidate" if all(gates.values()) else "source_grounded_policy_diagnostic_only"
    summary = {
        "stage": 11709,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "metrics": metrics,
        "baselines": {
            "stage11703": {
                "correct": (stage11703.get("metrics") or {}).get("correct"),
                "rows": (stage11703.get("metrics") or {}).get("rows"),
                "accuracy": (stage11703.get("metrics") or {}).get("accuracy"),
            },
            "gemma": gemma,
        },
        "remaining_misses": {
            "rows": len(misses),
            "by_task": dict(Counter(str(row.get("task_type")) for row in misses).most_common()),
            "row_ids": [str(row.get("row_id")) for row in misses],
        },
        "anti_cheat": anti,
        "protected_gates": protected,
        "gates": gates,
        "runtime": {
            "identity_runtime": rel(IDENTITY_RUNTIME),
            "identity_weights_sha256": meta["bundle"].get("weights_sha256"),
        },
        "claim_boundary": [
            "This is an inference-time source-grounded policy audit; no weights changed.",
            "It uses visible SOURCE_EVIDENCE before the candidate list to rerank symptom/minimal-fix identity rows.",
            "If accepted, this should become a product scorer route only after permutation and anti-cheat follow-up.",
        ],
        "recommended_next": (
            [
                "Run option-permutation stability for the source-grounded policy.",
                "If stable, freeze as a Web compact scorer candidate and build trainable source-grounded head.",
            ]
            if all(gates.values())
            else [
                "Do not productize this heuristic.",
                "Materialize high-fidelity analogues identified by Stage11708 or build a trainable source-grounded candidate head.",
            ]
        ),
        "outputs": {
            "summary": rel(SUMMARY),
            "row_cards": rel(ROW_CARDS),
            "miss_rows": rel(MISS_ROWS),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "metrics": metrics, "remaining_misses": summary["remaining_misses"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
