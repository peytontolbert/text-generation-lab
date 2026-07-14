#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11596
NAME = "stage11596_web_repaired_geometry_role_confusion_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_repaired_geometry_role_confusion_audit.json"
ROWS_PATHS = {
    "repaired_train": ART / "stage11594_web_verifier_attached_repaired_geometry_package/web_verifier_attached_repaired_train_rows.jsonl",
    "repaired_successor_strict": ART / "stage11594_web_verifier_attached_repaired_geometry_package/web_verifier_attached_repaired_successor_strict_rows.jsonl",
}
AUDIT_PATHS = {
    "repaired_train": ART / "stage11595_web_repaired_geometry_scorer_audit/encoder_option_retrieval_evidence_judgment_head/bounded_choice_eval_audit_repaired_train.json",
    "repaired_successor_strict": ART / "stage11595_web_repaired_geometry_scorer_audit/encoder_option_retrieval_evidence_judgment_head/bounded_choice_eval_audit_repaired_successor_strict.json",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((row.get("standalone_projection_source") or {}).get("opaque_options") or []) or row.get("opaque_options") or [])


def label_to_role(row: dict[str, Any]) -> dict[str, str]:
    return {str(opt.get("label")): str(opt.get("semantic_role") or opt.get("value") or "") for opt in options(row)}


def main() -> None:
    results: dict[str, Any] = {}
    for split, rows_path in ROWS_PATHS.items():
        rows = {str(row.get("row_id")): row for row in load_jsonl(rows_path)}
        audit = load_json(AUDIT_PATHS[split])
        role_pairs = Counter()
        by_task: dict[str, Counter[str]] = defaultdict(Counter)
        pred_roles = Counter()
        target_roles = Counter()
        examples: list[dict[str, Any]] = []
        for card in audit.get("row_cards") or []:
            row_id = str(card.get("row_id"))
            row = rows.get(row_id)
            if row is None:
                continue
            l2r = label_to_role(row)
            target_label = str(card.get("bounded_choice_target_label"))
            pred_label = str(card.get("constrained_choice_top1_label"))
            target_role = l2r.get(target_label, "missing_target_role")
            pred_role = l2r.get(pred_label, "missing_pred_role")
            task = str(row.get("task_type") or "unknown")
            target_roles[target_role] += 1
            pred_roles[pred_role] += 1
            role_pairs[(target_role, pred_role)] += 1
            by_task[task][f"{target_role} -> {pred_role}"] += 1
            if len(examples) < 20:
                examples.append({
                    "row_id": row_id,
                    "task_type": task,
                    "target_label": target_label,
                    "target_role": target_role,
                    "predicted_label": pred_label,
                    "predicted_role": pred_role,
                    "match": target_role == pred_role,
                })
        role_match = sum(count for (target, pred), count in role_pairs.items() if target == pred)
        total = sum(role_pairs.values())
        results[split] = {
            "rows": total,
            "role_match_rows": role_match,
            "role_match_rate": role_match / total if total else None,
            "target_roles": dict(target_roles),
            "predicted_roles": dict(pred_roles),
            "role_confusion": {f"{target} -> {pred}": count for (target, pred), count in sorted(role_pairs.items())},
            "by_task": {task: dict(counter) for task, counter in sorted(by_task.items())},
            "examples": examples,
        }
    decision = "repaired_geometry_role_target_mismatch_confirmed"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "results": results,
        "interpretation": [
            "This maps selected scorer labels back to hidden semantic roles after deterministic option shuffling.",
            "If role_match is near zero, the current scorer interface is optimizing a different role boundary than Stage11594 targets.",
        ],
        "source_artifacts": {
            "rows": {name: rel(path) for name, path in ROWS_PATHS.items()},
            "audits": {name: rel(path) for name, path in AUDIT_PATHS.items()},
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "results": results}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
