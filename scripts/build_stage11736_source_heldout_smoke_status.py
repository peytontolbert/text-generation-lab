#!/usr/bin/env python3
"""Combined status card for the current source-heldout smoke frontier."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11736
NAME = "stage11736_source_heldout_smoke_status"
OUT = ART / NAME
SUMMARY = OUT / "source_heldout_smoke_status.json"

LANGUAGE_DECISIONS = {
    "c_cpp": ART
    / "stage11724_sentencepiece_cpp_source_heldout_decision/sentencepiece_cpp_source_heldout_decision.json",
    "python": ART
    / "stage11731_bigram_python_source_heldout_decision/bigram_python_source_heldout_decision.json",
    "rust": ART
    / "stage11735_tokenizers_rust_source_heldout_decision/tokenizers_rust_source_heldout_decision.json",
}

PRODUCT_FREEZE = ART / "stage11711_product_policy_freeze_and_claim_boundary/product_policy_freeze_and_claim_boundary.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    decisions = {language: load_json(path) for language, path in LANGUAGE_DECISIONS.items()}
    product_freeze = load_json(PRODUCT_FREEZE) if PRODUCT_FREEZE.exists() else {}

    language_status: dict[str, Any] = {}
    for language, artifact in decisions.items():
        status = artifact.get("status") or {}
        gates = artifact.get("gates") or {}
        admitted = gates.get("admitted_source_heldout_smoke")
        if admitted is None:
            admitted = gates.get("compact_smoke_admitted")
        language_status[language] = {
            "decision": artifact.get("decision"),
            "compact_admission": status.get("compact_admission"),
            "hundred_m_source_heldout_smoke": status.get("hundred_m_source_heldout_smoke"),
            "miss_tasks": status.get("miss_tasks", []),
            "gemma_same_manifest": status.get("gemma_same_manifest"),
            "full_product": status.get("full_product"),
            "admitted_source_heldout_smoke": admitted,
            "source_artifact": rel(LANGUAGE_DECISIONS[language]),
        }

    gates = {
        "has_c_cpp_smoke": language_status["c_cpp"]["admitted_source_heldout_smoke"] is True,
        "has_python_smoke": language_status["python"]["admitted_source_heldout_smoke"] is True,
        "has_rust_smoke": language_status["rust"]["admitted_source_heldout_smoke"] is True,
        "all_100m_smoke_rows_correct": all(
            status["hundred_m_source_heldout_smoke"] in {"4/4", "100%"} for status in language_status.values()
        ),
        "all_gemma_same_manifest_attached": all(
            status["gemma_same_manifest"] not in {None, "not_run_gpu2_safe_backend_required"}
            for status in language_status.values()
        ),
        "all_full_product_ready": all(status["full_product"] == "ready" for status in language_status.values()),
        "web_compact_policy_frozen": bool(product_freeze),
    }

    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "source_heldout_smoke_inventory_complete_for_python_cpp_rust_but_not_claim_ready",
        "passed": True,
        "gates": gates,
        "selected_frontier": {
            "compact_frontier": "stage11507 + encoder_option_retrieval_evidence_judgment_head",
            "web_product_policy": "stage11709 routed compact web policy",
            "freeze_card": rel(PRODUCT_FREEZE) if PRODUCT_FREEZE.exists() else None,
        },
        "language_status": language_status,
        "interpretation": [
            "Python, C/C++ and Rust now have admitted compact source-heldout smoke packets with exact-root/source-snapshot checks.",
            "The smoke inventory is useful, but it does not yet support a source-heldout multilingual win claim.",
            "C/C++ fails the current product scorer at 0/4, mainly through abstain/nearby-surface geometry.",
            "Python and Rust both pass 3/4 and expose the same verifier_outcome selected-test discrimination weakness.",
            "Gemma same-manifest evidence is not attached for these smoke roots because a GPU2-safe Gemma backend has not been run.",
            "The full-product harness remains unready because executable verifier, patch/minimality, trace, and writeback artifacts are missing for these roots.",
        ],
        "next_actions": [
            "Attach executable verifier logs for pytest, cargo test, and the sentencepiece C++ test surface.",
            "Run Gemma same-manifest on the three smoke packets only through a GPU2-safe backend.",
            "Target verifier_outcome selected-test discrimination for Python and Rust with executable transition evidence.",
            "Target C/C++ abstain/nearby-surface geometry with a real sentencepiece verifier or fresh C++ analogue roots.",
            "Do not promote a broad source-heldout claim until all languages have same-manifest Gemma evidence and full smoke rows improve.",
        ],
        "claim_boundary": [
            "Supported: compact product-policy frontier remains frozen and strong on its locked compact packet.",
            "Supported: Python/C++/Rust source-heldout smoke packets now exist and reveal concrete next failure families.",
            "Not supported: broad source-heldout superiority over Gemma.",
            "Not supported: full-product executable patch/verifier repair.",
            "Not supported: freeform software-maintenance generation.",
        ],
        "outputs": {"summary": rel(SUMMARY)},
    }

    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "gates": gates, "language_status": language_status}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
