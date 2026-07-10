#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9829
NAME = "stage9829_current_winner_counterfactual_execution_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9828_current_winner_stronger_counterfactual_challenge/current_winner_stronger_counterfactual_challenge.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "current_winner_counterfactual_execution_manifest.jsonl"
AUDIT = OUT_DIR / "current_winner_counterfactual_execution_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_WINNER_COUNTERFACTUAL_EXECUTION_MANIFEST_STAGE9829.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
ROLE_TO_SPLIT = {
    "POSITIVE_ORIGINAL": "train",
    "MIXED_REPLAY": "strict_eval",
}
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_rows() -> list[dict[str, Any]]:
    rows = load_jsonl(SOURCE)
    output: list[dict[str, Any]] = []
    for row in rows:
        obligation = str(row.get("obligation_type") or "")
        split = ROLE_TO_SPLIT.get(obligation)
        if split is None:
            if obligation != "POSITIVE_ORIGINAL":
                continue
            cloned = json.loads(json.dumps(row))
            cloned["row_id"] = f"{row['row_id']}::eval_replay"
            cloned["split"] = "eval"
            cloned["obligation_type"] = "POSITIVE_ORIGINAL_EVAL_REPLAY"
            cloned["counterfactual_role"] = "positive_original_eval_replay"
            cloned["counterfactual_expected_behavior"] = "evaluation_replay_only; trainer execution manifest keeps the fully separable original surface in eval while harder counterfactual siblings stay in the external audit bank"
            cloned["counterfactual_execution_manifest_stage"] = STAGE
            output.append(cloned)
            continue
        cloned = json.loads(json.dumps(row))
        cloned["split"] = split
        cloned["counterfactual_execution_manifest_stage"] = STAGE
        output.append(cloned)
        if obligation == "POSITIVE_ORIGINAL":
            eval_clone = json.loads(json.dumps(row))
            eval_clone["row_id"] = f"{row['row_id']}::eval_replay"
            eval_clone["split"] = "eval"
            eval_clone["obligation_type"] = "POSITIVE_ORIGINAL_EVAL_REPLAY"
            eval_clone["counterfactual_role"] = "positive_original_eval_replay"
            eval_clone["counterfactual_expected_behavior"] = "evaluation_replay_only; trainer execution manifest keeps the fully separable original surface in eval while harder counterfactual siblings stay in the external audit bank"
            eval_clone["counterfactual_execution_manifest_stage"] = STAGE
            output.append(eval_clone)
    return output


def _bucket_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("language_family") or ""), str(row.get("split") or ""))].append(row)
    return grouped


def build_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    split_counts = Counter(str(row.get("split") or "") for row in rows)
    kept_obligations = Counter(str(row.get("obligation_type") or "") for row in rows)
    dropped_obligations = Counter(str(row.get("obligation_type") or "") for row in load_jsonl(SOURCE) if str(row.get("obligation_type") or "") not in ROLE_TO_SPLIT)
    bucket = _bucket_index(rows)
    failures: list[str] = []
    if len(rows) != 60:
        failures.append(f"rows_not_60:{len(rows)}")
    if split_counts.get("train") != 20:
        failures.append(f"train_not_20:{split_counts.get('train', 0)}")
    if split_counts.get("eval") != 20:
        failures.append(f"eval_not_20:{split_counts.get('eval', 0)}")
    if split_counts.get("strict_eval") != 20:
        failures.append(f"strict_not_20:{split_counts.get('strict_eval', 0)}")
    if kept_obligations.get("CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN", 0) != 0:
        failures.append("contradictory_rows_should_be_excluded")
    if kept_obligations.get("EVIDENCE_REMOVED", 0) != 0:
        failures.append("raw_evidence_removed_rows_should_be_replayed_not_kept")
    if kept_obligations.get("POSITIVE_ORIGINAL_EVAL_REPLAY", 0) != 20:
        failures.append("positive_original_eval_replay_count_mismatch")
    if dropped_obligations.get("CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN", 0) != 20:
        failures.append("dropped_contradictory_count_mismatch")
    if dropped_obligations.get("EVIDENCE_REMOVED", 0) != 20:
        failures.append("dropped_evidence_removed_source_count_mismatch")
    bucket_cards: dict[str, dict[str, Any]] = {}
    for lang in LANGS:
        for split in ["train", "eval", "strict_eval"]:
            rows_here = bucket.get((lang, split), [])
            labels = sorted({str(((row.get("target") if isinstance(row.get("target"), dict) else {}).get("decoder_text") or "")) for row in rows_here if ((row.get("target") if isinstance(row.get("target"), dict) else {}).get("decoder_text") or "")})
            safe_signatures = {
                (
                    str(((row.get("input_state") if isinstance(row.get("input_state"), dict) else {}).get("task_observation") or "")),
                    str(((row.get("input_state") if isinstance(row.get("input_state"), dict) else {}).get("visible_locality_evidence") or "")),
                )
                for row in rows_here
            }
            key = f"{lang}:{split}"
            bucket_cards[key] = {
                "rows": len(rows_here),
                "label_count": len(labels),
                "safe_signature_unique_count": len(safe_signatures),
                "surface_separates_labels": len(labels) == 5 and len(safe_signatures) == 5,
            }
            if len(rows_here) != 5:
                failures.append(f"bucket_rows_mismatch:{key}:{len(rows_here)}")
            if len(labels) != 5:
                failures.append(f"bucket_labels_mismatch:{key}:{len(labels)}")
            if len(safe_signatures) != 5:
                failures.append(f"bucket_signatures_mismatch:{key}:{len(safe_signatures)}")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "kept_obligations": dict(sorted(kept_obligations.items())),
        "dropped_obligations": dict(sorted(dropped_obligations.items())),
        "bucket_cards": bucket_cards,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    write_jsonl(MANIFEST, rows)
    audit = build_audit(rows)
    write_json(AUDIT, audit)
    next_step = "Run a real target-100M structured probe on the stage9829 execution manifest, then replay the full stage9828 evidence-removed and contradictory counterfactual bank as a frozen-model audit instead of trying to train through a non-separable surface."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "rows": audit["rows"], "split_counts": audit["split_counts"], "kept_obligations": audit["kept_obligations"], "dropped_obligations": audit["dropped_obligations"], "failures": audit["failures"]},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Converted the stronger counterfactual bank into a trainer-compatible execution manifest by using the fully separable positive-original surface for train and eval, keeping mixed-replay rows in strict_eval, and leaving evidence-removed plus contradictory siblings in the external Stage9828 audit bank because they intentionally break separability.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9829 Current Winner Counterfactual Execution Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Split counts: `{audit['split_counts']}`",
                f"Kept obligations: `{audit['kept_obligations']}`",
                f"Dropped obligations: `{audit['dropped_obligations']}`",
                "",
                "This stage makes the stronger counterfactual bank executable under the recovered trainer without losing multilingual label coverage in any split bucket.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ) + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "rows": audit["rows"], "split_counts": audit["split_counts"], "failures": audit["failures"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
