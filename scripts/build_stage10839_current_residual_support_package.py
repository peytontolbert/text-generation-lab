#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10839
NAME = "stage10839_current_residual_support_package"
OUT_DIR = ARTIFACTS / NAME
PACKAGE_JSON = OUT_DIR / "current_residual_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

BASE_DIR = ARTIFACTS / "stage10827_evidence_role_augmented_support_package"
PY_READY = ARTIFACTS / "stage10837_hf_local_repaired_support_readiness" / "hf_local_repaired_support_readiness.json"
PY_PACKET = ARTIFACTS / "stage10499_hf_local_multitest_packet_repair" / "hf_local_multitest_repaired_packet.json"
PY_READY_TARGETS = ARTIFACTS / "stage10837_hf_local_repaired_support_readiness" / "hf_local_repaired_support_targets.jsonl"
PY_REPAIRED_PREVIEW_ROWS = ARTIFACTS / "stage10499_hf_local_multitest_packet_repair" / "hf_local_multitest_repaired_preview_rows.jsonl"
RUST_READY = ARTIFACTS / "stage10838_linux_rust_support_readiness" / "linux_rust_support_readiness.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compact(text: str, limit: int = 280) -> str:
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


def render_evidence_lines(bundle: dict[str, Any], visible_keys: list[str]) -> list[str]:
    evidence = bundle["bundle"]["maintainer_visible_evidence"]
    lines: list[str] = []
    for key in visible_keys:
        values = evidence.get(key)
        if not isinstance(values, list) or not values:
            continue
        first = values[0]
        if not isinstance(first, dict):
            continue
        role = str(first.get("surface_role") or key)
        text = compact(str(first.get("text") or ""))
        lines.append(f"{key} [{role}]: {text}")
    return lines[:4]


def prompt_for(bundle: dict[str, Any], preview_row: dict[str, Any]) -> str:
    contract = preview_row["prompt_contract"]
    parts = [
        f"Language: {preview_row['language_family']}",
        f"Perspective: {preview_row['task_type']}",
        f"Task: {contract['task']}",
    ]
    evidence_lines = render_evidence_lines(bundle, contract.get("visible_evidence_keys", []))
    if evidence_lines:
        parts.append("Evidence:")
        parts.extend(evidence_lines)
    parts.append("Options:")
    answer_kind = preview_row["preview_answer_kind"]
    if answer_kind == "verifier_id":
        parts.extend(f"{opt}. {summary['role_summary']}" for opt, summary in zip(preview_row["preview_options"], contract["verifier_options"]))
    elif answer_kind == "candidate_id":
        path_by_id = {entry["id"]: entry["path"] for entry in contract["candidate_options"]}
        parts.extend(f"{opt}. {path_by_id[opt]}" for opt in preview_row["preview_options"])
    else:
        parts.extend(f"{opt}. {opt}" for opt in preview_row["preview_options"])
    parts.append("Answer:")
    return "\n".join(parts) + "\n"


def compile_hf_local_rows(bundle: dict[str, Any], preview_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compiled: list[dict[str, Any]] = []
    candidate_options = preview_rows[0]["prompt_contract"]["candidate_options"]
    path_by_id = {entry["id"]: entry["path"] for entry in candidate_options}
    verifier_options = preview_rows[0]["prompt_contract"]["verifier_options"]
    verifier_role_by_id = {entry["id"]: entry["role_summary"] for entry in verifier_options}
    for row in preview_rows:
        prompt = prompt_for(bundle, row)
        answer_kind = row["preview_answer_kind"]
        gold_value = row["preview_gold_value"]
        if answer_kind == "candidate_id":
            semantic_gold = path_by_id[gold_value]
            opaque_options = [{"label": entry["id"], "value": entry["path"]} for entry in candidate_options]
            original_answer_kind = "candidate_path"
        elif answer_kind == "verifier_id":
            semantic_gold = verifier_role_by_id[gold_value]
            opaque_options = [{"label": entry["id"], "value": entry["role_summary"]} for entry in verifier_options]
            original_answer_kind = "selected_test"
        elif answer_kind == "visible_evidence_key":
            semantic_gold = gold_value
            opaque_options = [{"label": label, "value": label} for label in row["preview_options"]]
            original_answer_kind = "visible_evidence_key"
        else:
            semantic_gold = gold_value
            opaque_options = [{"label": label, "value": label} for label in row["preview_options"]]
            original_answer_kind = "abstain"

        compiled.append(
            {
                "row_id": f"{bundle['bundle']['bundle_id']}::{row['task_type']}::compact_bounded",
                "source_bundle_id": bundle["bundle"]["bundle_id"],
                "source_root_id": bundle["bundle"]["bundle_id"],
                "repo_id": bundle["bundle"]["repo_id"],
                "repo_family": bundle["bundle"]["repo_id"],
                "language_family": row["language_family"],
                "task_type": row["task_type"],
                "split": "train",
                "split_role": "train_support",
                "train_support_only": True,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "selected_test_anchor": True,
                "verifier_anchor": True,
                "abstention_heavy": row["task_type"] == "abstention_insufficient_evidence",
                "surface": "maintainer_bundle_compact_bounded_choice",
                "objective_family": "bounded_decoder_ce",
                "prompt_text": prompt,
                "input_text": prompt,
                "query_text": f"reviewed_v27::{row['language_family']}::{row['task_type']}",
                "target_text": gold_value,
                "decoder_text": gold_value,
                "target_token_len": len(gold_value.encode("utf-8")),
                "expected_enabled_loss": "decoder_ce",
                "loss_mask": {"decoder_ce": True},
                "disable_losses": [],
                "opaque_options": opaque_options,
                "standalone_projection_source": {
                    "projection_mode": "stage10839_hf_local_repaired_train_support",
                    "gold_value": semantic_gold,
                    "original_answer_kind": original_answer_kind,
                    "opaque_options": opaque_options,
                    "repaired_packet": rel(PY_PACKET),
                },
                "anti_cheat": {
                    "reviewed_bundle_source": True,
                    "opaque_labels": True,
                    "compact_prompt_contract": True,
                    "deterministic_option_shuffle": False,
                    "same_surface_eval_admissible": False,
                    "repo_overlap_stress_only": False,
                    "prompt_target_leak_false": True,
                    "opaque_candidate_options": True,
                    "opaque_verifier_options": True,
                },
                "support_package_stage": STAGE,
                "support_provenance": {
                    "support_class": "python_hf_local_repaired_multitest_support",
                    "support_readiness_stage": 10837,
                    "support_role": "train_support_only",
                },
            }
        )
    return compiled


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def main() -> None:
    base_package = load_json(BASE_DIR / "evidence_role_augmented_support_package.json")
    base_train = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_train.jsonl")
    base_validation = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_validation.jsonl")
    base_strict = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl")
    base_stress = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl")
    py_ready = load_json(PY_READY)
    py_packet = load_json(PY_PACKET)
    py_ready_targets = load_jsonl(PY_READY_TARGETS)
    py_preview_rows = load_jsonl(PY_REPAIRED_PREVIEW_ROWS)
    rust_ready = load_json(RUST_READY)

    if len(py_ready_targets) != len(py_preview_rows):
        raise ValueError("hf_local_ready_vs_preview_count_mismatch")

    new_py_rows = compile_hf_local_rows(py_packet, py_preview_rows)
    existing_row_ids = {str(row.get("row_id")) for row in base_train}
    filtered_py_rows = [row for row in new_py_rows if row["row_id"] not in existing_row_ids]
    merged_train = list(base_train) + filtered_py_rows

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "current_residual_support_package_ready",
        "claim_scope": [
            "Extend the current standalone multilingual support package with the cleaned hf_local multitest verifier packet while keeping strict and validation frozen.",
            "Preserve the already-admitted Linux Rust anchored support lane without duplicating its rows.",
        ],
        "source_artifacts": {
            "base_package": rel(BASE_DIR / "evidence_role_augmented_support_package.json"),
            "python_support_readiness": rel(PY_READY),
            "python_repaired_packet": rel(PY_PACKET),
            "rust_support_readiness": rel(RUST_READY),
        },
        "metrics": {
            "base_train_rows": len(base_train),
            "added_hf_local_rows": len(filtered_py_rows),
            "merged_train_rows": len(merged_train),
            "validation_rows": len(base_validation),
            "strict_rows": len(base_strict),
            "stress_rows": len(base_stress),
            "merged_train_by_language": count_by(merged_train, "language_family"),
            "added_rows_by_task": count_by(filtered_py_rows, "task_type"),
        },
        "honesty_gates": [
            "validation and strict rows are byte-for-byte preserved from stage10827",
            "hf_local repaired rows remain train-support only and are not fresh strict evidence",
            "linux Rust support is already present and is not duplicated or upgraded into a headline claim",
            "future probe must report Python verifier_outcome and Rust evidence_citation family deltas explicitly",
        ],
        "lane_state_notes": {
            "python": "stage10499 repaired hf_local multitest verifier packet added as 5 train-support rows",
            "rust": "stage10680 adjudicated Linux Rust support remains present from the base package",
            "c_cpp": "unchanged from base package",
            "web": "unchanged from base package",
        },
        "outputs": {
            "package_json": rel(PACKAGE_JSON),
            "train_rows": rel(TRAIN_JSONL),
            "validation_rows": rel(VALIDATION_JSONL),
            "strict_rows": rel(STRICT_JSONL),
            "stress_rows": rel(STRESS_JSONL),
        },
        "next_best_step": "Run a bounded standalone probe from this package initialized from stage10820, then audit whether the hf_local verifier rows move the Python verifier family without regressing the 24-row strict frontier.",
        "base_metrics_snapshot": base_package.get("metrics"),
    }

    write_json(PACKAGE_JSON, payload)
    write_jsonl(TRAIN_JSONL, merged_train)
    write_jsonl(VALIDATION_JSONL, base_validation)
    write_jsonl(STRICT_JSONL, base_strict)
    write_jsonl(STRESS_JSONL, base_stress)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
