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
STAGE = 9885
NAME = "stage9885_current_margin_hybrid_counterfactual_execution_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9881_current_margin_stronger_counterfactual_challenge/current_margin_stronger_counterfactual_challenge.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "current_margin_hybrid_counterfactual_execution_manifest.jsonl"
AUDIT = OUT_DIR / "current_margin_hybrid_counterfactual_execution_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_MARGIN_HYBRID_COUNTERFACTUAL_EXECUTION_MANIFEST_STAGE9885.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
STABLE_STRICT_LABELS = {"K", "T"}


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


def _root_id(row_id: str) -> str:
    return row_id.split("::", 1)[0]


def build_rows() -> list[dict[str, Any]]:
    source_rows = load_jsonl(SOURCE)
    by_root: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in source_rows:
        root = _root_id(str(row.get("row_id") or ""))
        obligation = str(row.get("obligation_type") or "")
        by_root[root][obligation] = row

    roots_by_lang: dict[str, list[str]] = defaultdict(list)
    for root, roles in by_root.items():
        original = roles.get("POSITIVE_ORIGINAL")
        if not isinstance(original, dict):
            continue
        roots_by_lang[str(original.get("language_family") or "")].append(root)
    for lang in roots_by_lang:
        roots_by_lang[lang].sort()

    output: list[dict[str, Any]] = []
    for lang in LANGS:
        for root in roots_by_lang.get(lang, []):
            roles = by_root[root]
            positive = json.loads(json.dumps(roles["POSITIVE_ORIGINAL"]))
            positive["split"] = "train"
            positive["counterfactual_execution_manifest_stage"] = STAGE
            output.append(positive)

            eval_replay = json.loads(json.dumps(roles["POSITIVE_ORIGINAL"]))
            eval_replay["row_id"] = f"{positive['row_id']}::eval_replay"
            eval_replay["split"] = "eval"
            eval_replay["obligation_type"] = "POSITIVE_ORIGINAL_EVAL_REPLAY"
            eval_replay["counterfactual_role"] = "positive_original_eval_replay"
            eval_replay["counterfactual_expected_behavior"] = "evaluation_replay_only; keep a clean same-surface anchor in eval"
            eval_replay["counterfactual_execution_manifest_stage"] = STAGE
            output.append(eval_replay)

            label = str(((positive.get("target") if isinstance(positive.get("target"), dict) else {}).get("decoder_text") or ""))
            if label in STABLE_STRICT_LABELS:
                strict = json.loads(json.dumps(positive))
                strict["row_id"] = f"{positive['row_id']}::strict_anchor"
                strict["split"] = "strict_eval"
                strict["obligation_type"] = "POSITIVE_ORIGINAL_STRICT_ANCHOR"
                strict["counterfactual_role"] = "positive_original_strict_anchor"
                strict["counterfactual_expected_behavior"] = "strict_eval keeps a clean anchor for fragile labels while mixed replay remains in the training bank"
                strict["counterfactual_execution_manifest_stage"] = STAGE
            else:
                strict = json.loads(json.dumps(roles["MIXED_REPLAY"]))
                strict["split"] = "strict_eval"
                strict["counterfactual_execution_manifest_stage"] = STAGE
            output.append(strict)
    return output


def _bucket_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("language_family") or ""), str(row.get("split") or ""))].append(row)
    return grouped


def build_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    split_counts = Counter(str(row.get("split") or "") for row in rows)
    kept_obligations = Counter(str(row.get("obligation_type") or "") for row in rows)
    bucket = _bucket_index(rows)
    strict_labels = Counter(str(((row.get("target") if isinstance(row.get("target"), dict) else {}).get("decoder_text") or "")) for row in rows if str(row.get("split") or "") == "strict_eval")
    failures: list[str] = []
    if len(rows) != 48:
        failures.append(f"rows_not_48:{len(rows)}")
    if split_counts != {"train": 16, "eval": 16, "strict_eval": 16}:
        failures.append(f"unexpected_split_counts:{dict(split_counts)}")
    if kept_obligations.get("POSITIVE_ORIGINAL_STRICT_ANCHOR", 0) != 8:
        failures.append("strict_anchor_count_mismatch")
    if kept_obligations.get("MIXED_REPLAY", 0) != 8:
        failures.append("mixed_replay_count_mismatch")
    if strict_labels != Counter({"K": 4, "M": 4, "R": 4, "T": 4}):
        failures.append(f"strict_label_balance_mismatch:{dict(strict_labels)}")

    bucket_cards: dict[str, dict[str, Any]] = {}
    for lang in LANGS:
        for split in ["train", "eval", "strict_eval"]:
            rows_here = bucket.get((lang, split), [])
            labels = sorted({str(((row.get("target") if isinstance(row.get("target"), dict) else {}).get("decoder_text") or "")) for row in rows_here if ((row.get("target") if isinstance(row.get("target"), dict) else {}).get("decoder_text") or "")})
            key = f"{lang}:{split}"
            bucket_cards[key] = {
                "rows": len(rows_here),
                "label_count": len(labels),
                "labels": labels,
            }
            if len(rows_here) != 4:
                failures.append(f"bucket_rows_mismatch:{key}:{len(rows_here)}")
            if len(labels) != 4:
                failures.append(f"bucket_labels_mismatch:{key}:{len(labels)}")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "kept_obligations": dict(sorted(kept_obligations.items())),
        "strict_label_balance": dict(sorted(strict_labels.items())),
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
    next_step = "Run one target-100M probe on this hybrid manifest to test whether clean strict anchors for K and T preserve frontier strict exact while still exposing mixed-replay pressure on M and R."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "rows": audit["rows"], "split_counts": audit["split_counts"], "kept_obligations": audit["kept_obligations"], "strict_label_balance": audit["strict_label_balance"], "failures": audit["failures"]},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built a hybrid current-frontier execution manifest that keeps positive-original strict anchors for the fragile K and T labels while preserving mixed-replay pressure on M and R.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9885 Current Margin Hybrid Counterfactual Execution Manifest",
            "",
            f"Passed: `{audit['passed']}`",
            f"Rows: `{audit['rows']}`",
            f"Split counts: `{audit['split_counts']}`",
            f"Kept obligations: `{audit['kept_obligations']}`",
            f"Strict label balance: `{audit['strict_label_balance']}`",
            "",
            "This stage preserves current-frontier multilingual label balance while reducing strict-set collapse pressure on the weakest labels.",
            "",
            f"Next: {next_step}",
            "",
        ]) + "\n",
        encoding="utf-8",
    )
    if summary['passed']:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit['passed'], "rows": audit['rows'], "split_counts": audit['split_counts'], "failures": audit['failures']}, indent=2, sort_keys=True))
    if audit['failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
