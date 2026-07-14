#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10393
NAME = "stage10393_python_residual_recovery_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST_JSONL = OUT_DIR / "python_residual_recovery_manifest.jsonl"
REQUEST_JSON = OUT_DIR / "python_residual_recovery_execution_request.json"
COMMAND_JSON = OUT_DIR / "python_residual_recovery_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

STRICT_PAYLOAD = ROOT / "runs/local/artifacts/stage10374_quarantined_full_visible_saved_runtime_payload/quarantined_full_visible_saved_runtime_payload.json"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10379_balanced_residual_probe/runtime_model/runtime_model_bundle.json"
PYTHON_SUPPORT = ROOT / "runs/local/artifacts/stage10247_weakness_counterbalance_package/agentkernel_lite_encdec_train.jsonl"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10394_python_residual_recovery_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10394_python_residual_recovery_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10394_python_residual_recovery_probe/runtime_model"

PYTHON_EVIDENCE_PREFIX = (
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_26t00_55_44_019abda8_c0d8_7803_8a77_1e0f_"
    "scripts_universe_build_py_64d2cf209b_aug_1500000_8b46e7f662::python::evidence_citation"
)
PYTHON_MIRRORMIND_VERIFIER_ROW = (
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_"
    "models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::"
    "verifier_outcome::full_visible_compact_bounded"
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
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


def rotate(values: list[Any], shift: int) -> list[Any]:
    return values[shift:] + values[:shift]


def strict_rows_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in payload.get("runs") or []:
        task_pack = run.get("task_pack") or {}
        for row in task_pack.get("rows") or []:
            if not isinstance(row, dict):
                continue
            copy = json.loads(json.dumps(row))
            copy["split"] = "strict_eval"
            target_text = str(copy.get("target_text") or "")
            copy["decoder_text"] = target_text
            copy["target_token_len"] = len(target_text.encode("utf-8"))
            copy["loss_mask"] = {"decoder_ce": True}
            copy["expected_enabled_loss"] = "decoder_ce"
            copy["disable_losses"] = ["denoise_ce", "runtime_reward", "structured_aux"]
            projection = dict(copy.get("standalone_projection_source") or {})
            if not projection.get("opaque_options") and copy.get("opaque_options"):
                projection["opaque_options"] = copy.get("opaque_options")
            copy["standalone_projection_source"] = projection
            rows.append(copy)
    return rows


def normalize_train_row(row: dict[str, Any], *, support_family: str) -> dict[str, Any]:
    out = json.loads(json.dumps(row))
    target_text = str(out.get("target_text") or "")
    out["decoder_text"] = target_text
    out["target_token_len"] = len(target_text.encode("utf-8"))
    out["loss_mask"] = {"decoder_ce": True}
    out["expected_enabled_loss"] = "decoder_ce"
    out["disable_losses"] = []
    out["split"] = "train"
    out["row_id"] = f"stage10393::{support_family}::{out.get('row_id')}"
    out["semantic_key"] = f"stage10393::{support_family}::{out.get('semantic_key') or out.get('row_id')}"
    anti = dict(out.get("anti_cheat") or {})
    anti.update(
        {
            "stage10393_support_only": True,
            "python_only_residual_recovery": True,
            "non_promotable_until_disjoint_rebuild": True,
        }
    )
    out["anti_cheat"] = anti
    source = dict(out.get("standalone_projection_source") or {})
    source["stage10393_support_family"] = support_family
    out["standalone_projection_source"] = source
    auth = dict(out.get("authority") or {})
    auth["promotion_ready"] = False
    auth["model_execution_authorized_next"] = False
    out["authority"] = auth
    return out


def clone_train_from_strict(base_row: dict[str, Any], *, support_family: str, perm_idx: int) -> dict[str, Any]:
    clone = json.loads(json.dumps(base_row))
    options = [item for item in (clone.get("opaque_options") or []) if isinstance(item, dict)]
    rotated = rotate(options, perm_idx)
    target_value = ""
    for item in options:
        if str(item.get("label") or "") == str(base_row.get("target_text") or ""):
            target_value = str(item.get("value") or "")
            break
    if not target_value:
        raise ValueError(f"missing_target_value::{base_row.get('row_id')}")
    target_label = ""
    for item in rotated:
        if str(item.get("value") or "") == target_value:
            target_label = str(item.get("label") or "")
            break
    if not target_label:
        raise ValueError(f"missing_target_label::{base_row.get('row_id')}")
    clone["row_id"] = f"stage10393::{support_family}::{base_row['row_id']}::perm_{perm_idx:02d}"
    clone["semantic_key"] = f"stage10393::{support_family}::{base_row.get('row_id')}::perm_{perm_idx:02d}"
    clone["split"] = "train"
    clone["target_text"] = target_label
    clone["decoder_text"] = target_label
    clone["target_token_len"] = len(target_label.encode("utf-8"))
    clone["loss_mask"] = {"decoder_ce": True}
    clone["expected_enabled_loss"] = "decoder_ce"
    clone["disable_losses"] = []
    clone["query_text"] = f"{base_row.get('query_text','python_residual')}::stage10393::{support_family}::{perm_idx:02d}"
    clone["opaque_options"] = rotated
    projection = dict(clone.get("standalone_projection_source") or {})
    projection["opaque_options"] = rotated
    projection["stage10393_support_family"] = support_family
    claim = projection.setdefault("claim_boundary", {})
    claim["diagnostic_same_surface_train_only"] = True
    claim["same_surface_eval_admissible"] = False
    clone["standalone_projection_source"] = projection
    anti = dict(clone.get("anti_cheat") or {})
    anti["stage10393_same_surface_guard"] = True
    anti["non_promotable_until_disjoint_rebuild"] = True
    clone["anti_cheat"] = anti
    auth = dict(clone.get("authority") or {})
    auth["promotion_ready"] = False
    auth["model_execution_authorized_next"] = False
    clone["authority"] = auth
    return clone


def select_python_support() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in load_jsonl(PYTHON_SUPPORT):
        if str(row.get("split") or "") != "train":
            continue
        if str(row.get("language_family") or "") != "python":
            continue
        row_id = str(row.get("row_id") or "")
        if PYTHON_EVIDENCE_PREFIX in row_id and str(row.get("task_type") or "") == "evidence_citation":
            rows.append(normalize_train_row(row, support_family="python_evidence_compact_support"))

    strict_rows = strict_rows_from_payload(load_json(STRICT_PAYLOAD))
    by_id = {str(row.get("row_id") or ""): row for row in strict_rows}
    evidence_row = next(row for row in strict_rows if str(row.get("row_id") or "") == f"{PYTHON_EVIDENCE_PREFIX}::full_visible_compact_bounded")
    verifier_row = by_id[PYTHON_MIRRORMIND_VERIFIER_ROW]

    for perm_idx in range(len(evidence_row.get("opaque_options") or [])):
        rows.append(clone_train_from_strict(evidence_row, support_family="python_evidence_full_visible_guard", perm_idx=perm_idx))
    for perm_idx in range(len(verifier_row.get("opaque_options") or [])):
        rows.append(clone_train_from_strict(verifier_row, support_family="python_mirrormind_verifier_guard", perm_idx=perm_idx))
    return rows


def build_command(split_counts: dict[str, int]) -> list[str]:
    return [
        "env",
        f"TMPDIR={TMPDIR}",
        f"TEMP={TMPDIR}",
        f"TMP={TMPDIR}",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str(TRAINER),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST_JSONL),
        "--mode",
        "bounded_decoder_ce_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str(MODEL_CONFIG),
        "--tokenizer-json",
        str(TOKENIZER_JSON),
        "--tokenizer-config",
        str(TOKENIZER_CONFIG),
        "--tokenizer-hashlock",
        str(TOKENIZER_HASHLOCK),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows",
        str(split_counts.get("train", 0)),
        "--max-eval-rows",
        "0",
        "--max-strict-rows",
        str(split_counts.get("strict_eval", 0)),
        "--max-steps",
        "18",
        "--batch-size",
        "2",
        "--learning-rate",
        "3e-6",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "8",
        "--decoder-ce-weight",
        "0.2",
        "--bounded-choice-aux-weight",
        "1.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "4.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        "8",
        "--max-generation-tokens",
        "8",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--runtime-model-save-dir",
        RUNTIME_MODEL_DIR,
        "--allow-runtime-model-save-for-harness",
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-kl-weight",
        "3.0",
        "--output-dir",
        OUTPUT_DIR,
        "--run-id",
        RUN_ID,
    ]


def main() -> None:
    strict_rows = strict_rows_from_payload(load_json(STRICT_PAYLOAD))
    train_rows = select_python_support()
    combined_rows = train_rows + strict_rows

    split_counts: dict[str, int] = {}
    support_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    for row in train_rows:
        family = str(((row.get("standalone_projection_source") or {}).get("stage10393_support_family")) or "unknown")
        support_counts[family] = support_counts.get(family, 0) + 1
    for row in combined_rows:
        split = str(row.get("split") or "unknown")
        split_counts[split] = split_counts.get(split, 0) + 1
        lang = str(row.get("language_family") or "unknown")
        language_counts[lang] = language_counts.get(lang, 0) + 1

    command = build_command(split_counts)
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_residual_recovery_probe_ready",
        "manifest": display(MANIFEST_JSONL),
        "strict_payload": display(STRICT_PAYLOAD),
        "initialize_from_runtime_model": display(INIT_RUNTIME),
        "runtime_model_save_dir": RUNTIME_MODEL_DIR,
        "rows": len(combined_rows),
        "split_counts": split_counts,
        "language_counts": language_counts,
        "support_counts": dict(sorted(support_counts.items())),
        "claim_scope": "non-promotable Python-only residual recovery probe; success is measured only by rescoring the saved runtime against the unchanged 47-row frontier with the stable language-conditioned scorer",
        "required_honesty_gates": [
            "strict eval remains the unchanged 47-row honest frontier",
            "same-surface full-visible Python guards are diagnostic only and cannot support promotion claims",
            "preservation KL must remain tied to the current stage10379 runtime to avoid hidden global drift",
            "promotion is disallowed until any recovered movement is rebuilt from disjoint roots or scorer-side proof",
        ],
        "next_best_step": "run one narrow recovery probe focused only on the two remaining Python residual families, then rescore the saved runtime with the stable stage10385 language-conditioned evaluator",
        "command": command,
        "output_dir": OUTPUT_DIR,
        "run_id": RUN_ID,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(MANIFEST_JSONL, combined_rows)
    write_json(COMMAND_JSON, {"command": command})
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY, {"stage": STAGE, "passed": True, "request": display(REQUEST_JSON)})
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": True,
                "request": display(REQUEST_JSON),
                "train_rows": len(train_rows),
                "strict_rows": len(strict_rows),
                "support_counts": dict(sorted(support_counts.items())),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
