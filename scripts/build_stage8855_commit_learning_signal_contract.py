#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from commit_learning_signal_contract_builder import build_card, build_commit_learning_signal_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8855
NAME = "stage8855_commit_learning_signal_contract"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COMMIT_LEARNING_SIGNAL_CONTRACT_STAGE8855.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_commit_learning_signal_rows()
    card_metrics = build_card(rows)
    manifest = OUT_DIR / "commit_learning_signal_contract_manifest.jsonl"
    card_path = OUT_DIR / "commit_learning_signal_contract_card.json"
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    metrics = {
        **AUTHORITY_CLOSED,
        **card_metrics,
        "authority_rows": card_metrics["authority_open_rows"],
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": card_metrics["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "manifest": str(manifest.relative_to(ROOT)),
            "card": str(card_path.relative_to(ROOT)),
        },
        "decision": "Recovered commit-mining learning-signal contract. It defines causal edit units, relevance filtering, and decoder target gates; it does not mine /arxiv repositories or open training.",
        "next_best_step": "Attach commit-learning-signal contract to graph, then recover a no-mining gate audit. Keep training and decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    card_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8855 Commit Learning Signal Contract",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage records how commits should become learning signals without mining repositories yet.",
        "",
        "Core rule: never train on raw commits as one example. Decompose commits into causal edit units, classify hunks as core/supporting/incidental/noise, and emit structured labels before any bounded decoder target is considered.",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Contract-ready rows: `{metrics['contract_ready_rows']}`",
        f"Commit mining authorized: `{metrics['commit_mining_authorized']}`",
        f"Training authorized: `{metrics['training_authorized']}`",
        f"Decoder CE authorized: `{metrics['decoder_ce_authorized']}`",
        "",
        "Target surfaces:",
        "",
        *[f"- `{surface}`" for surface in metrics["target_surfaces"]],
        "",
        "Commit size policy:",
        "",
        "- small commits: direct structured labels and bounded decoder candidates only if compact and clean",
        "- medium commits: segment into causal units first",
        "- large commits: use for decomposition, retrieval/context, repo graph, and verifier planning; decoder targets stay blocked",
        "",
    ]), encoding="utf-8")

    marker = "## Stage8855 Commit Learning Signal Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Commit mining is now represented as a contract, not an open mining job.",
            "",
            "- Source unit is not `commit`; it is `causal_edit_unit` derived from file clusters, symbol clusters, hunk groups, or test-code pairs.",
            "- Hunk relevance must classify edits as `core`, `supporting`, `incidental`, or `noise`.",
            "- Small commits may provide bounded decoder candidates only after structured labels and gates pass.",
            "- Medium commits require segmentation before use.",
            "- Large commits are primarily retrieval, graph, verifier, and decomposition signal; raw large-patch decoder targets remain blocked.",
            "- Every unit must carry source provenance, contamination status, locked-eval exclusion, gate status, and junk/OOD route.",
            "",
            "No `/arxiv/repositories` walk, commit mining, training, decoder CE, runtime, source/body emission, Gemma, scoring, or promotion is authorized by this contract.",
            "",
        ]), encoding="utf-8")

    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
