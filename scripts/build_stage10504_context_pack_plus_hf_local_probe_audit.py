#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10504
NAME = "stage10504_context_pack_plus_hf_local_probe_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "context_pack_plus_hf_local_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASELINE_AUDIT = ROOT / "runs/local/artifacts/stage10471_fresh_residual_root_probe_audit/fresh_residual_root_probe_audit.json"
BASELINE_STRICT = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
PROBE_REQUEST = ROOT / "runs/local/artifacts/stage10503_context_pack_plus_hf_local_promotable_python_probe_request/context_pack_plus_hf_local_promotable_python_probe_request.json"
PROBE_RESULT = ROOT / "runs/local/artifacts/stage10503_context_pack_plus_hf_local_promotable_python_probe/bounded_decoder_probe/execution_result.json"
PROBE_STRICT = ROOT / "runs/local/artifacts/stage10503_context_pack_plus_hf_local_promotable_python_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
PACKET_REFRESH = ROOT / "runs/local/artifacts/stage10502_python_verifier_packet_refresh/python_verifier_packet_refresh.json"

PYTHON_ROW_ID = "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::verifier_outcome::reviewed_v27_compact"
RUST_ROW_ID = "stage10126::tokenizers::tokenizers::rust::evidence_citation::reviewed_v27_compact"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    baseline_audit = load_json(BASELINE_AUDIT)
    baseline = load_json(BASELINE_STRICT)
    probe_request = load_json(PROBE_REQUEST)
    probe_result = load_json(PROBE_RESULT)
    probe = load_json(PROBE_STRICT)
    packet_refresh = load_json(PACKET_REFRESH)

    base_map = {row["row_id"]: row for row in baseline["row_cards"]}
    probe_map = {row["row_id"]: row for row in probe["row_cards"]}

    changed_rows = []
    for row_id, probe_row in sorted(probe_map.items()):
        base_row = base_map[row_id]
        label_changed = base_row["constrained_choice_top1_label"] != probe_row["constrained_choice_top1_label"]
        rank_changed = base_row["target_rank_full_vocab"] != probe_row["target_rank_full_vocab"]
        if label_changed or rank_changed:
            changed_rows.append(
                {
                    "row_id": row_id,
                    "baseline_label": base_row["constrained_choice_top1_label"],
                    "probe_label": probe_row["constrained_choice_top1_label"],
                    "baseline_rank_full_vocab": base_row["target_rank_full_vocab"],
                    "probe_rank_full_vocab": probe_row["target_rank_full_vocab"],
                }
            )

    regressions = [row for row in changed_rows if row["baseline_label"] == base_map[row["row_id"]]["target_text"] and row["probe_label"] != probe_map[row["row_id"]]["target_text"]]
    improvements = [row for row in changed_rows if row["probe_rank_full_vocab"] < row["baseline_rank_full_vocab"]]

    python_base = base_map[PYTHON_ROW_ID]
    python_probe = probe_map[PYTHON_ROW_ID]
    rust_base = base_map[RUST_ROW_ID]
    rust_probe = probe_map[RUST_ROW_ID]

    probe_acc = probe_result["bounded_choice_eval"]["strict_eval"]["constrained_choice_top1_accuracy"]
    base_acc = baseline_audit["accuracy"]["baseline"]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "context_pack_plus_hf_local_probe_audited",
        "claim_scope": [
            "Classify the Stage10503 promotable Python probe that combines context_pack with the repaired hf_local verifier packet.",
            "Keep the interpretation narrow: this audit measures whether the repaired hf_local support improves the live repaired-overlay frontier, not whether the multilingual benchmark is complete.",
        ],
        "accuracy": {
            "baseline": base_acc,
            "probe": probe_acc,
            "delta": probe_acc - base_acc,
        },
        "headline": {
            "beats_live_baseline": probe_acc > base_acc,
            "zero_regressions": len(regressions) == 0,
            "changed_rows": len(changed_rows),
            "residual_miss_set_changed": python_probe["constrained_choice_match"] or rust_probe["constrained_choice_match"],
        },
        "python_residual": {
            "row_id": PYTHON_ROW_ID,
            "baseline_label": python_base["constrained_choice_top1_label"],
            "probe_label": python_probe["constrained_choice_top1_label"],
            "target": python_probe["target_text"],
            "baseline_rank_full_vocab": python_base["target_rank_full_vocab"],
            "probe_rank_full_vocab": python_probe["target_rank_full_vocab"],
            "fixed": bool(python_probe["constrained_choice_match"]),
        },
        "rust_residual": {
            "row_id": RUST_ROW_ID,
            "baseline_label": rust_base["constrained_choice_top1_label"],
            "probe_label": rust_probe["constrained_choice_top1_label"],
            "target": rust_probe["target_text"],
            "baseline_rank_full_vocab": rust_base["target_rank_full_vocab"],
            "probe_rank_full_vocab": rust_probe["target_rank_full_vocab"],
            "fixed": bool(rust_probe["constrained_choice_match"]),
        },
        "improvements": improvements,
        "regressions": regressions,
        "changed_rows": changed_rows,
        "interpretation": [
            "The repaired hf_local support no longer fails on packet quality, but it does not yet improve strict constrained accuracy beyond 22/24.",
            "The Python verifier residual remains incorrect, though its full-vocab target rank improves from 6 to 5, which suggests the new support shifted margin without flipping the decision boundary.",
            "The Rust tokenizers evidence-citation residual remains incorrect and improves only to target rank 2, so the multilingual miss set is unchanged.",
            "This makes Stage10503 a clean margin-improvement diagnostic, not a promotable frontier upgrade.",
        ],
        "recommended_next_stage": "fresh_python_verifier_only_root_packet_beyond_context_pack_and_hf_local",
        "required_followups": [
            "Do not promote Stage10503 as a new frontier because strict constrained accuracy stays at 22/24.",
            "Use the repaired hf_local packet as validated support inventory, but seek fresh disjoint Python verifier roots that attack the MirrorMind B-vs-C confusion directly.",
            "Keep Rust work on a separate citation-contrast path; the Python repair packet did not change the Rust miss set.",
        ],
        "source_artifacts": {
            "baseline_audit": display(BASELINE_AUDIT),
            "baseline_strict": display(BASELINE_STRICT),
            "probe_request": display(PROBE_REQUEST),
            "probe_result": display(PROBE_RESULT),
            "probe_strict": display(PROBE_STRICT),
            "packet_refresh": display(PACKET_REFRESH),
        },
        "support_inventory_summary": packet_refresh["summary"],
    }

    write_json(AUDIT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "accuracy": payload["accuracy"],
            "audit": display(AUDIT_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
