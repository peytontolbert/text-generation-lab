#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10482
NAME = "stage10482_python_verifier_dense_probe_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "python_verifier_dense_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASELINE_AUDIT = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
PROBE_AUDIT = ROOT / "runs/local/artifacts/stage10481_python_verifier_dense_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10479_python_verifier_dense_support_package/python_verifier_dense_support_package.json"
REQUEST_JSON = ROOT / "runs/local/artifacts/stage10480_python_verifier_dense_probe_request/python_verifier_dense_probe_request.json"

PYTHON_RESIDUAL = "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::verifier_outcome::reviewed_v27_compact"


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
    baseline = load_json(BASELINE_AUDIT)
    probe = load_json(PROBE_AUDIT)
    package = load_json(PACKAGE_JSON)
    request = load_json(REQUEST_JSON)

    base_rows = {row["row_id"]: row for row in baseline["row_cards"]}
    probe_rows = {row["row_id"]: row for row in probe["row_cards"]}

    changed_rows = []
    regressions = []
    improvements = []
    for row_id, base_row in base_rows.items():
        probe_row = probe_rows[row_id]
        changed = (
            base_row["constrained_choice_top1_label"] != probe_row["constrained_choice_top1_label"]
            or base_row["constrained_choice_match"] != probe_row["constrained_choice_match"]
        )
        if changed:
            card = {
                "row_id": row_id,
                "baseline_label": base_row["constrained_choice_top1_label"],
                "probe_label": probe_row["constrained_choice_top1_label"],
                "baseline_match": base_row["constrained_choice_match"],
                "probe_match": probe_row["constrained_choice_match"],
                "target": probe_row["target_text"],
            }
            changed_rows.append(card)
            if base_row["constrained_choice_match"] and not probe_row["constrained_choice_match"]:
                regressions.append(card)
            if not base_row["constrained_choice_match"] and probe_row["constrained_choice_match"]:
                improvements.append(card)

    base_python = base_rows[PYTHON_RESIDUAL]
    probe_python = probe_rows[PYTHON_RESIDUAL]

    baseline_acc = baseline["constrained_choice_top1_accuracy"]
    probe_acc = probe["constrained_choice_top1_accuracy"]
    delta = probe_acc - baseline_acc

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_verifier_dense_probe_classified",
        "claim_scope": [
            "Classify the Python verifier-only dense probe against the live repaired-overlay baseline.",
            "Report whether the denser verifier-only support changes the remaining Python residual or only preserves the same frontier.",
        ],
        "source_artifacts": {
            "baseline_audit": display(BASELINE_AUDIT),
            "probe_audit": display(PROBE_AUDIT),
            "support_package": display(PACKAGE_JSON),
            "probe_request": display(REQUEST_JSON),
        },
        "accuracy": {
            "baseline": baseline_acc,
            "probe": probe_acc,
            "delta": delta,
        },
        "changed_rows": changed_rows,
        "regressions": regressions,
        "improvements": improvements,
        "python_residual": {
            "row_id": PYTHON_RESIDUAL,
            "baseline_label": base_python["constrained_choice_top1_label"],
            "probe_label": probe_python["constrained_choice_top1_label"],
            "baseline_match": base_python["constrained_choice_match"],
            "probe_match": probe_python["constrained_choice_match"],
            "target": probe_python["target_text"],
            "baseline_full_vocab_target_rank": base_python.get("target_rank_full_vocab"),
            "probe_full_vocab_target_rank": probe_python.get("target_rank_full_vocab"),
            "baseline_full_vocab_top1": base_python.get("full_vocab_top1_text"),
            "probe_full_vocab_top1": probe_python.get("full_vocab_top1_text"),
        },
        "headline": {
            "beats_live_baseline": probe_acc > baseline_acc,
            "zero_regressions": len(regressions) == 0,
            "python_residual_fixed": probe_python["constrained_choice_match"],
        },
        "support_package_row_count": package["rows"],
        "required_honesty_gates": request["required_honesty_gates"],
    }

    write_json(AUDIT_JSON, audit)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": audit["decision"],
            "audit": display(AUDIT_JSON),
        },
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
