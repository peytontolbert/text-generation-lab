#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10726
NAME = "stage10726_rust_citation_semantic_contrast_builder"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "rust_citation_semantic_contrast_builder.json"
SUPPORT_ROWS_JSONL = OUT_DIR / "rust_citation_semantic_contrast_rows.jsonl"
ROOTS_JSONL = OUT_DIR / "rust_citation_semantic_contrast_roots.jsonl"
TRAIN_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
PENDING_JSONL = OUT_DIR / "rust_citation_semantic_pending_roots.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

EXECUTION_PATH = ROOT / "runs/local/artifacts/stage10724_residual_semantic_repair_execution_path/residual_semantic_repair_execution_path.json"
STAGE10476_ROWS = ROOT / "runs/local/artifacts/stage10476_rust_citation_materialized_root_bundle_builder/rust_citation_materialized_bounded_rows.jsonl"
STAGE10646_ROWS = ROOT / "runs/local/artifacts/stage10646_reviewed_v28_candidate_same_manifest_comparison/reviewed_v28_candidate_same_manifest_rows.jsonl"
STAGE10411_ATLAS = ROOT / "runs/local/artifacts/stage10411_fresh_rust_disjoint_root_candidate_atlas/fresh_rust_disjoint_root_candidate_atlas.json"

FLASH_ATTN_EVIDENCE_ROW = "stage10413::candle::candle-flash-attn::rust::evidence_citation::reviewed_v27_compact"
FLASH_ATTN_ABSTAIN_ROW = "stage10413::candle::candle-flash-attn::rust::abstention_insufficient_evidence::reviewed_v27_compact"


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    load_json(EXECUTION_PATH)
    stage10476_rows = load_jsonl(STAGE10476_ROWS)
    stage10646_rows = load_jsonl(STAGE10646_ROWS)
    atlas = load_json(STAGE10411_ATLAS)

    selected_rows: list[dict[str, Any]] = []

    # Candle-core executable auxiliary rows.
    for row in stage10476_rows:
        if row.get("task_type") == "evidence_citation":
            row = dict(row)
            row["semantic_repair_role"] = "auxiliary_executable_citation_support"
            row["builder_stage"] = STAGE
            row["train_support_only"] = True
            row["strict_eval_eligible"] = False
            selected_rows.append(row)

    # Reviewed flash-attn rows provide a real fresh semantic contrast root.
    for row in stage10646_rows:
        if row.get("row_id") not in {FLASH_ATTN_EVIDENCE_ROW, FLASH_ATTN_ABSTAIN_ROW}:
            continue
        adapted = {
            "row_id": str(row["row_id"]),
            "source_bundle_id": str(row["source_bundle_id"]),
            "repo_id": str(row["repo_id"]),
            "repo_family": str(row["repo_family"]),
            "language_family": str(row["language_family"]),
            "task_type": str(row["task_type"]),
            "decoder_text": str(row["target_text"]),
            "target_text": str(row["target_text"]),
            "target_token_len": len(str(row["target_text"])),
            "prompt_text": str(row["prompt_text"]),
            "input_text": str(row["prompt_text"]),
            "opaque_options": row["opaque_options"],
            "selected_test_anchor": bool(row.get("selected_test_anchor")),
            "verifier_anchor": bool(row.get("verifier_anchor")),
            "source_heldout_admissible": False,
            "strict_eval_eligible": False,
            "train_support_only": True,
            "split": "train",
            "split_role": "train_support",
            "disable_losses": [],
            "expected_enabled_loss": "decoder_ce",
            "loss_mask": {"decoder_ce": True},
            "objective_family": "bounded_decoder_ce",
            "surface": "maintainer_bundle_compact_bounded_choice",
            "query_text": f"reviewed_v27::rust::{str(row['task_type'])}",
            "semantic_repair_role": "fresh_reviewed_semantic_contrast_seed" if row["row_id"] == FLASH_ATTN_EVIDENCE_ROW else "honesty_abstention_seed",
            "builder_stage": STAGE,
            "abstention_heavy": bool(row.get("abstention_heavy", False)),
        }
        selected_rows.append(adapted)

    selected_rows.sort(key=lambda r: str(r["row_id"]))

    roots: dict[str, dict[str, Any]] = {}
    for row in selected_rows:
        root_id = str(row.get("source_bundle_id") or "")
        rec = roots.setdefault(
            root_id,
            {
                "root_id": root_id,
                "repo_id": str(row.get("repo_id") or "unknown"),
                "repo_family": str(row.get("repo_family") or row.get("repo_id") or "unknown"),
                "language_family": "rust",
                "row_ids": [],
                "roles": set(),
                "task_types": set(),
                "selected_test_anchor": bool(row.get("selected_test_anchor")),
                "verifier_anchor": bool(row.get("verifier_anchor")),
            },
        )
        rec["row_ids"].append(str(row["row_id"]))
        rec["roles"].add(str(row["semantic_repair_role"]))
        rec["task_types"].add(str(row.get("task_type") or "unknown"))

    root_rows = []
    for rec in roots.values():
        rec["roles"] = sorted(rec["roles"])
        rec["task_types"] = sorted(rec["task_types"])
        rec["row_count"] = len(rec["row_ids"])
        root_rows.append(rec)
    root_rows.sort(key=lambda r: r["root_id"])

    pending = []
    for candidate in atlas.get("top_fresh_candidates") or []:
        root_id = str(candidate.get("candidate_root_id") or "")
        if root_id in {"candle::candle-flash-attn", "candle::candle-core"}:
            continue
        pending.append(
            {
                "candidate_root_id": root_id,
                "repo_id": str(candidate.get("repo_id") or "unknown"),
                "package_root": str(candidate.get("package_root") or "unknown"),
                "review_ready_for_bundle_construction": bool(candidate.get("review_ready_for_bundle_construction")),
                "competition_geometries": candidate.get("competition_geometries") or [],
                "test_file_count": int(candidate.get("test_file_count") or 0),
                "priority_score": int(candidate.get("priority_score") or 0),
                "required_next_action": "materialize evidence_citation rows with real symptom-vs-verifier contrast",
            }
        )

    rust_target = next(t for t in load_jsonl(OUT_DIR.parent / "stage10724_residual_semantic_repair_execution_path" / "residual_semantic_repair_targets.jsonl") if t["language_family"] == "rust")

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "rust_semantic_citation_seed_ready",
        "claim_scope": [
            "Build the immediate Rust semantic citation seed package specified by stage10724.",
            "Separate auxiliary executable rows from the fresh reviewed semantic-contrast root and the still-pending fresh roots.",
        ],
        "current_residual_target": rust_target,
        "metrics": {
            "selected_row_count": len(selected_rows),
            "auxiliary_seed_row_count": sum(1 for row in selected_rows if row["semantic_repair_role"] == "auxiliary_executable_citation_support"),
            "fresh_reviewed_seed_row_count": sum(1 for row in selected_rows if row["semantic_repair_role"] == "fresh_reviewed_semantic_contrast_seed"),
            "honesty_seed_row_count": sum(1 for row in selected_rows if row["semantic_repair_role"] == "honesty_abstention_seed"),
            "root_count": len(root_rows),
            "pending_fresh_root_count": len(pending),
        },
        "interpretation": [
            "Flash-attn provides a real reviewed fresh root with the same symptom-vs-verifier evidence opposition needed by the tokenizers residual.",
            "Candle-core remains useful only as auxiliary executable citation support because it does not by itself prove the exact non-tokenizers E-vs-F style contrast.",
            "The pending queue still needs more fresh non-tokenizers roots before the Rust lane is scaled enough for a broad promotion claim.",
        ],
        "anti_cheat_contract": [
            "All selected rows remain train_support_only and strict_eval_eligible=false.",
            "No tokenizers strict row is copied into train.",
            "Flash-attn is included as a reviewed fresh root, not as a same-surface replay.",
            "Any follow-on execution request must keep tokenizers rows diagnostic-only and use the repaired overlay as the regression gate.",
        ],
        "next_best_step": "Merge these rows into the next stage10727 semantic contrast support package and keep the pending fresh-root queue active for additional non-tokenizers Rust roots.",
        "source_artifacts": {
            "execution_path": display(EXECUTION_PATH),
            "stage10476_rows": display(STAGE10476_ROWS),
            "stage10646_rows": display(STAGE10646_ROWS),
            "stage10411_atlas": display(STAGE10411_ATLAS),
        },
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "support_rows": display(SUPPORT_ROWS_JSONL),
            "root_manifest": display(ROOTS_JSONL),
            "train_rows": display(TRAIN_ROWS_JSONL),
            "pending_queue": display(PENDING_JSONL),
        },
    }

    write_jsonl(SUPPORT_ROWS_JSONL, selected_rows)
    write_jsonl(ROOTS_JSONL, root_rows)
    write_jsonl(TRAIN_ROWS_JSONL, selected_rows)
    write_jsonl(PENDING_JSONL, pending)
    write_json(SUMMARY_JSON, payload)
    write_json(
        SUMMARY_CARD,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "selected_row_count": payload["metrics"]["selected_row_count"],
            "artifact": display(SUMMARY_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
