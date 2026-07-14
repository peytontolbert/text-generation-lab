#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

STAGE = 11497
NAME = "stage11497_candidate_set_evidence_judgment_head_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "candidate_set_evidence_judgment_head_probe_request.json"
BRIDGE_ROWS = OUT / "candidate_set_evidence_judgment_rows.jsonl"
QUARANTINE_ROWS = OUT / "candidate_set_evidence_judgment_quarantine.jsonl"
MANIFEST = OUT / "candidate_set_evidence_judgment_head_probe_manifest.jsonl"
COMMAND_JSON = OUT / "candidate_set_evidence_judgment_head_probe_command.json"

BASE = ART / "stage11436_full_coverage_semantic_candidate_package"
BASE_TRAIN = BASE / "agentkernel_lite_encdec_train.jsonl"
VALIDATION = BASE / "agentkernel_lite_encdec_validation.jsonl"
STRICT = BASE / "agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL = BASE / "semantic_candidate_residual_bank.jsonl"
CANDIDATE_ROWS = ART / "stage11492_residual50_candidate_set_recompiler/residual50_candidate_set_rows.jsonl"
CANDIDATE_SUMMARY = ART / "stage11492_residual50_candidate_set_recompiler/residual50_candidate_set_recompiler.json"
INIT_RUNTIME = ART / "stage11444_targeted_residual_role_support_probe/runtime_model/runtime_model_bundle.json"

RUN_DIR = ART / "stage11498_candidate_set_evidence_judgment_head_probe"
RUNTIME_DIR = RUN_DIR / "runtime_model"
OUTPUT_DIR = RUN_DIR / "bounded_decoder_probe"

ROLE_TO_BUCKET = {
    "candidate_change_surface": "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
    "SUPPORTING_CANDIDATE_CHANGE_SURFACE": "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
    "verifier_and_test_constraint": "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "DECISIVE_VERIFIER_TEST_CONSTRAINT": "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "DECISIVE_SELECTED_TEST_CONSTRAINT": "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "DECISIVE_BUILD_VERIFIER_CONSTRAINT": "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "symptom_or_call_path_analogue": "SUPPORTING_SYMPTOM_OR_CALL_PATH",
    "SUPPORTING_SYMPTOM_OR_CALL_PATH": "SUPPORTING_SYMPTOM_OR_CALL_PATH",
    "OBSERVED_VERIFIER_LOG": "SUPPORTING_SYMPTOM_OR_CALL_PATH",
    "OBSERVED_VERIFIER_PASS_LOG": "SUPPORTING_SYMPTOM_OR_CALL_PATH",
    "OBSERVED_VERIFIER_FAILURE_LOG": "SUPPORTING_SYMPTOM_OR_CALL_PATH",
    "nearby_definition_or_usage_context": "DISTRACTOR_BACKGROUND_CONTEXT",
    "insufficient_or_background_context": "DISTRACTOR_BACKGROUND_CONTEXT",
    "algorithmic_background_reference": "DISTRACTOR_BACKGROUND_CONTEXT",
    "DISTRACTOR_BACKGROUND_CONTEXT": "DISTRACTOR_BACKGROUND_CONTEXT",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def row_key(row: dict[str, Any]) -> str:
    return str(row.get("row_id") or "")


def option_rows(row: dict[str, Any]) -> list[dict[str, str]]:
    source = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    raw = source.get("opaque_options") or row.get("opaque_options") or []
    out: list[dict[str, str]] = []
    for option in raw:
        if not isinstance(option, dict):
            continue
        label = str(option.get("label") or "").strip()
        value = str(option.get("value") or "").strip()
        if label and value:
            out.append({"label": label, "value": value})
    return out


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("bounded_choice_target_label") or row.get("target_text") or row.get("decoder_text") or "").strip()


def bridge_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    opts = option_rows(row)
    mapped_options: list[dict[str, str]] = []
    duplicate_buckets: list[str] = []
    seen_buckets: set[str] = set()
    target = target_label(row)
    mapped_target = ""
    for option in opts:
        bucket = ROLE_TO_BUCKET.get(option["value"], "")
        if not bucket:
            return None, {"row": row, "reasons": [f"unsupported_option_value::{option['value']}"]}
        if bucket in seen_buckets:
            duplicate_buckets.append(bucket)
        seen_buckets.add(bucket)
        mapped_options.append({"label": option["label"], "value": bucket})
        if option["label"] == target:
            mapped_target = option["label"]
    if duplicate_buckets:
        return None, {"row": row, "reasons": ["duplicate_judgment_bucket_values"], "duplicate_buckets": sorted(set(duplicate_buckets))}
    if not mapped_target:
        return None, {"row": row, "reasons": ["missing_target_label_after_mapping"]}
    source = dict(row.get("standalone_projection_source") or {})
    source["opaque_options"] = mapped_options
    source["judgment_head_bridge_source_row_id"] = row_key(row)
    source["judgment_head_bridge_from_stage"] = "stage11492"
    source["candidate_set_id"] = row.get("candidate_set_id") or source.get("candidate_set_id")
    payload = dict(row)
    payload["row_id"] = f"{row_key(row)}::judgment_head_bridge"
    payload["task_type"] = "evidence_candidate_judgment"
    payload["bounded_choice_target_label"] = mapped_target
    payload["decoder_text"] = mapped_target
    payload["target_text"] = mapped_target
    payload["opaque_options"] = mapped_options
    payload["standalone_projection_source"] = source
    payload["expected_enabled_loss"] = "decoder_ce"
    payload["loss_mask"] = {"decoder_ce": True}
    payload["anti_cheat"] = dict(payload.get("anti_cheat") or {})
    payload["anti_cheat"].update(
        {
            "judgment_head_bridge": True,
            "candidate_set_id_present": bool(source.get("candidate_set_id")),
            "duplicate_judgment_buckets_rejected": True,
            "train_support_only": True,
        }
    )
    text = str(payload.get("input_text") or payload.get("prompt_text") or "")
    if "Perspective:" in text:
        text = text.replace("Perspective: evidence_citation", "Perspective: evidence_candidate_judgment")
    payload["input_text"] = text
    payload["prompt_text"] = text
    return payload, None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candidate_summary = read_json(CANDIDATE_SUMMARY)
    base_train = read_jsonl(BASE_TRAIN)
    validation = read_jsonl(VALIDATION)
    strict = read_jsonl(STRICT)
    residual = read_jsonl(RESIDUAL)
    candidate_rows = read_jsonl(CANDIDATE_ROWS)

    bridge_rows: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    for row in candidate_rows:
        bridged, blocked = bridge_row(row)
        if bridged is not None:
            bridge_rows.append(bridged)
        elif blocked is not None:
            q = dict(blocked["row"])
            q["judgment_bridge_quarantine_reasons"] = blocked["reasons"]
            if blocked.get("duplicate_buckets"):
                q["duplicate_buckets"] = blocked["duplicate_buckets"]
            quarantine.append(q)

    write_jsonl(BRIDGE_ROWS, bridge_rows)
    write_jsonl(QUARANTINE_ROWS, quarantine)

    protected_rows = {row_key(row) for row in validation + strict + residual}
    protected_roots = {root_key(row) for row in validation + strict + residual}
    added_rows = {row_key(row) for row in bridge_rows}
    added_roots = {root_key(row) for row in bridge_rows}
    row_overlaps = sorted(added_rows & protected_rows)
    root_overlaps = sorted(root for root in (added_roots & protected_roots) if root)

    candidate_ready = candidate_summary.get("decision") == "residual50_candidate_sets_ready_for_listwise_probe"
    role_counts = Counter(str(row.get("listwise_target_role") or "") for row in bridge_rows)
    language_counts = Counter(str(row.get("language_family") or "unknown") for row in bridge_rows)
    ready = candidate_ready and len(bridge_rows) >= 30 and not row_overlaps and not root_overlaps and not any(not row.get("candidate_set_id") for row in bridge_rows)

    train_rows_by_id: dict[str, dict[str, Any]] = {}
    for row in base_train + bridge_rows:
        payload = dict(row)
        payload["split"] = "train"
        train_rows_by_id[row_key(payload)] = payload
    train_rows = list(train_rows_by_id.values())

    manifest_rows: list[dict[str, Any]] = []
    for split, rows in (("train", train_rows), ("eval", validation), ("strict_eval", strict)):
        for row in rows:
            payload = dict(row)
            payload["split"] = split
            manifest_rows.append(payload)
    write_jsonl(MANIFEST, manifest_rows)

    command = [
        "env",
        "CUDA_VISIBLE_DEVICES=2",
        "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
        "TMPDIR=/data/tmp",
        "TEMP=/data/tmp",
        "TMP=/data/tmp",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST),
        "--mode",
        "bounded_decoder_ce_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows",
        str(len(train_rows)),
        "--max-eval-rows",
        str(len(validation)),
        "--max-strict-rows",
        str(len(strict)),
        "--max-steps",
        "192",
        "--batch-size",
        "4",
        "--learning-rate",
        "6e-6",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.1",
        "--bounded-choice-aux-weight",
        "2.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_evidence_judgment_head",
        "--bounded-decoder-train-sampler",
        "residual_family_balanced",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "4.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        "12",
        "--max-generation-tokens",
        "16",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_DIR),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-kl-weight",
        "0.5",
        "--no-final-checkpoint-export",
        "--output-dir",
        str(OUTPUT_DIR),
    ]
    write_json(COMMAND_JSON, {"command": command, "allowed_to_run": ready})
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": ready,
        "decision": "candidate_set_evidence_judgment_head_probe_requested" if ready else "candidate_set_evidence_judgment_head_probe_blocked",
        "hypothesis": {
            "failure_family": "Residual evidence/candidate role boundary",
            "single_changed_variable": "product scorer architecture: encoder_option_retrieval_evidence_judgment_head",
            "intervention": "Bridge Stage11492 candidate-set rows into evidence_candidate_judgment rows with supported judgment buckets.",
        },
        "metrics": {
            "base_train_rows": len(base_train),
            "bridge_rows": len(bridge_rows),
            "quarantined_rows": len(quarantine),
            "train_rows_after_dedupe": len(train_rows),
            "validation_rows": len(validation),
            "strict_rows": len(strict),
            "residual_rows_for_postrun": len(residual),
            "protected_row_overlaps": len(row_overlaps),
            "protected_root_overlaps": len(root_overlaps),
            "role_counts": dict(sorted(role_counts.items())),
            "language_counts": dict(sorted(language_counts.items())),
        },
        "postrun_required_gates": {
            "old_canary_strict": "23/23 under product scorer",
            "filtered_strict": "22/22 under product scorer",
            "filtered_validation": ">=20/22",
            "old_canary_validation": ">=21/23",
            "residual_bank": ">=6/10",
            "full_bounded_choice_coverage": True,
        },
        "blockers": {
            "candidate_summary_not_ready": not candidate_ready,
            "too_few_bridge_rows": len(bridge_rows) < 30,
            "protected_row_overlaps": row_overlaps,
            "protected_root_overlaps": root_overlaps,
            "rows_missing_candidate_set_id": [row_key(row) for row in bridge_rows if not row.get("candidate_set_id")],
        },
        "source_artifacts": {
            "base_train": rel(BASE_TRAIN),
            "validation": rel(VALIDATION),
            "strict": rel(STRICT),
            "residual_bank": rel(RESIDUAL),
            "candidate_rows": rel(CANDIDATE_ROWS),
            "candidate_summary": rel(CANDIDATE_SUMMARY),
            "initialize_from_runtime": rel(INIT_RUNTIME),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "bridge_rows": rel(BRIDGE_ROWS),
            "quarantine_rows": rel(QUARANTINE_ROWS),
            "manifest_jsonl": rel(MANIFEST),
            "command_json": rel(COMMAND_JSON),
            "probe_output_dir": rel(OUTPUT_DIR),
            "runtime_model_dir": rel(RUNTIME_DIR),
        },
        "command": command,
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"passed": ready, "decision": summary["decision"], "metrics": summary["metrics"], "blockers": summary["blockers"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
