#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from contamination_leakage_detector import AUTHORITY_CLOSED, detect_card


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8746
NAME = "stage8746_contamination_leakage_detector_readiness"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONTAMINATION_LEAKAGE_DETECTOR_READINESS_STAGE8746.md"


def sample_rows() -> list[dict]:
    clean = {
        "row_id": "row_clean_001",
        "split": "train",
        "semantic_key": "sem_clean_001",
        "source_id": "src_clean_001",
        "input_state": {"intent": "repair parser branch", "evidence_state": "direct_present"},
        "target": {"action": "PATCH_OPERATOR"},
    }
    target_leak = {
        "row_id": "row_target_leak_001",
        "split": "train",
        "semantic_key": "sem_target_leak_001",
        "source_id": "src_target_leak_001",
        "input_state": {"intent": "repair parser branch", "expected_answer": "PATCH_OPERATOR"},
        "target": {"action": "PATCH_OPERATOR"},
    }
    label_id = {
        "row_id": "row_REPAIR_SHORT_OUTPUT_001",
        "split": "eval",
        "semantic_key": "sem_label_id_001",
        "source_id": "src_label_id_001",
        "input_state": {"intent": "repair bad output"},
        "target": {"action": "REPAIR_SHORT_OUTPUT"},
    }
    body_leak = {
        "row_id": "row_body_leak_001",
        "split": "strict_eval",
        "semantic_key": "sem_body_leak_001",
        "source_id": "src_body_leak_001",
        "input_state": {"intent": "inspect source", "raw_source": "def hidden_target(): pass"},
        "target": {"action": "ABSTAIN_UNSAFE"},
    }
    heldout = {
        "row_id": "row_heldout_001",
        "split": "train",
        "semantic_key": "sem_heldout_001",
        "source_id": "locked_src_001",
        "input_state": {"intent": "train on locked source"},
        "target": {"action": "PATCH_OPERATOR"},
    }
    proxy = {
        "row_id": "row_proxy_001",
        "split": "train",
        "semantic_key": "sem_proxy_001",
        "source_id": "src_proxy_001",
        "input_state": {"intent": "surface discriminator"},
        "target": {"action": "PATCH_OPERATOR"},
        "shortcut_dominated_feature": True,
    }
    overlap = {
        "row_id": "row_clean_002",
        "split": "strict_eval",
        "semantic_key": "sem_clean_001",
        "source_id": "src_clean_002",
        "input_state": {"intent": "same semantic key in strict split"},
        "target": {"action": "PATCH_OPERATOR"},
    }
    return [clean, target_leak, label_id, body_leak, heldout, proxy, overlap]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = sample_rows()
    card = detect_card(rows, locked_eval_ids={"locked_src_001"})
    sample_path = OUT_DIR / "contamination_leakage_detector_sample_card.json"
    decisions_path = OUT_DIR / "contamination_leakage_detector_decisions.jsonl"
    sample_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    decisions_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in card["decisions"]), encoding="utf-8")
    passed = (
        card["rows"] == 7
        and card["pass_rows"] == 2
        and card["target_leak_rows"] == 1
        and card["label_coded_id_rows"] == 1
        and card["body_leak_rows"] == 1
        and card["heldout_overlap_rows"] == 1
        and card["split_overlap_rows"] == 1
        and card["route_counts"].get("REVIEW_SUSPICIOUS_PROXY") == 1
        and card["authority"]["training_authorized_next"] is False
    )
    summary = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "artifacts": {"sample_card": str(sample_path.relative_to(ROOT)), "decisions": str(decisions_path.relative_to(ROOT))},
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "rows": card["rows"],
            "pass_rows": card["pass_rows"],
            "blocked_rows": card["blocked_rows"],
            "review_rows": card["review_rows"],
            "target_leak_rows": card["target_leak_rows"],
            "heldout_overlap_rows": card["heldout_overlap_rows"],
            "label_coded_id_rows": card["label_coded_id_rows"],
            "body_leak_rows": card["body_leak_rows"],
            "split_overlap_rows": card["split_overlap_rows"],
            "routes": card["route_counts"],
        },
        "decision": "Recovered unified contamination/leakage detector. It blocks visible target leaks, label-coded identifiers, heldout overlap, and body/source leakage while routing suspicious proxies and split overlap to review.",
        "next_best_step": "Attach contamination_leakage_detector to central graph, then recover hybrid_retrieval_fusion.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8746 Contamination Leakage Detector Readiness",
        "",
        f"Passed: `{passed}`",
        "",
        "Recovered a reusable contamination/leakage detector for objective rows and source-backed manifests.",
        "",
        "Blocked signals:",
        "",
        "- visible target-like fields in model input",
        "- copied target text in visible input",
        "- label-coded row/node/source identifiers",
        "- heldout or locked-eval overlap",
        "- raw body/source leakage into model-visible fields",
        "",
        "Review signals:",
        "",
        "- cross-split semantic overlap",
        "- suspicious shortcut/proxy features",
        "",
        "Authority remains closed. This detector can block or review rows but cannot authorize training, decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
