#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10376
NAME = "stage10376_residual_semantic_support_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST_JSONL = OUT_DIR / "residual_semantic_support_manifest.jsonl"
REQUEST_JSON = OUT_DIR / "residual_semantic_support_execution_request.json"
COMMAND_JSON = OUT_DIR / "residual_semantic_support_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

STRICT_PAYLOAD = ROOT / "runs/local/artifacts/stage10374_quarantined_full_visible_saved_runtime_payload/quarantined_full_visible_saved_runtime_payload.json"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10373_honest_frontier_runtime_earlysave/runtime_model/runtime_model_bundle.json"
PYTHON_SUPPORT = ROOT / "runs/local/artifacts/stage10247_weakness_counterbalance_package/agentkernel_lite_encdec_train.jsonl"
CPP_CITATION_SUPPORT = ROOT / "runs/local/artifacts/stage10362_source_backed_cpp_rust_citation_support_execution_request/source_backed_cpp_rust_citation_support_manifest.jsonl"
BASE_TRAIN = ROOT / "runs/local/artifacts/stage10149_v27_standalone_compact_permutation_balanced_package/agentkernel_lite_encdec_train.jsonl"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10377_residual_semantic_support_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10377_residual_semantic_support_probe/bounded_decoder_probe"


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
    out["row_id"] = f"stage10376::{support_family}::{out.get('row_id')}"
    out["semantic_key"] = f"stage10376::{support_family}::{out.get('semantic_key') or out.get('row_id')}"
    anti = dict(out.get("anti_cheat") or {})
    anti.update(
        {
            "stage10376_support_only": True,
            "non_promotable_until_disjoint_rebuild": True,
            "focused_residual_semantic_support": True,
        }
    )
    out["anti_cheat"] = anti
    source = dict(out.get("standalone_projection_source") or {})
    source["stage10376_support_family"] = support_family
    out["standalone_projection_source"] = source
    auth = dict(out.get("authority") or {})
    auth["promotion_ready"] = False
    auth["model_execution_authorized_next"] = False
    out["authority"] = auth
    return out


def select_python_support() -> list[dict[str, Any]]:
    rows = []
    for row in load_jsonl(PYTHON_SUPPORT):
        if str(row.get("split") or "") != "train":
            continue
        if str(row.get("language_family") or "") != "python":
            continue
        task_type = str(row.get("task_type") or "")
        if task_type == "evidence_citation":
            rows.append(normalize_train_row(row, support_family="python_evidence_verifier_constraint"))
        elif task_type == "verifier_outcome":
            rows.append(normalize_train_row(row, support_family="python_verifier_anchor"))
    return rows


def select_cpp_citation_support() -> list[dict[str, Any]]:
    rows = []
    for row in load_jsonl(CPP_CITATION_SUPPORT):
        if str(row.get("split") or "") != "train":
            continue
        if str(row.get("language_family") or "") != "c_cpp":
            continue
        if str(row.get("task_type") or "") != "evidence_citation":
            continue
        source = row.get("standalone_projection_source") or {}
        if str(source.get("gold_value") or "") != "verifier_and_test_constraint":
            continue
        rows.append(normalize_train_row(row, support_family="cpp_citation_verifier_constraint"))
    return rows


def select_base_support() -> list[dict[str, Any]]:
    rows = []
    for row in load_jsonl(BASE_TRAIN):
        if str(row.get("split") or "") != "train":
            continue
        lang = str(row.get("language_family") or "")
        task_type = str(row.get("task_type") or "")
        gold_value = str(((row.get("standalone_projection_source") or {}).get("gold_value")) or "")
        if lang == "c_cpp" and task_type == "abstention_insufficient_evidence" and gold_value == "ABSTAIN_INSUFFICIENT_EVIDENCE":
            rows.append(normalize_train_row(row, support_family="cpp_abstention_anchor"))
        elif lang == "rust" and task_type == "abstention_insufficient_evidence" and gold_value == "ABSTAIN_INSUFFICIENT_EVIDENCE":
            rows.append(normalize_train_row(row, support_family="rust_abstention_anchor"))
        elif lang == "rust" and task_type == "verifier_outcome" and gold_value == "ABSTAIN_INSUFFICIENT_EVIDENCE":
            rows.append(normalize_train_row(row, support_family="rust_verifier_abstain_anchor"))
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
        "16",
        "--batch-size",
        "2",
        "--learning-rate",
        "4e-6",
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
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-kl-weight",
        "2.0",
        "--output-dir",
        OUTPUT_DIR,
        "--run-id",
        RUN_ID,
    ]


def main() -> None:
    strict_rows = strict_rows_from_payload(load_json(STRICT_PAYLOAD))
    python_rows = select_python_support()
    cpp_citation_rows = select_cpp_citation_support()
    base_rows = select_base_support()
    train_rows = python_rows + cpp_citation_rows + base_rows
    combined_rows = train_rows + strict_rows

    split_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    support_counts = {
        "python_support_rows": len(python_rows),
        "cpp_citation_support_rows": len(cpp_citation_rows),
        "base_abstention_support_rows": len(base_rows),
    }
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
        "decision": "focused_residual_semantic_support_probe_ready",
        "manifest": display(MANIFEST_JSONL),
        "strict_payload": display(STRICT_PAYLOAD),
        "initialize_from_runtime_model": display(INIT_RUNTIME),
        "rows": len(combined_rows),
        "split_counts": split_counts,
        "language_counts": language_counts,
        "support_counts": support_counts,
        "claim_scope": "diagnostic train-support-only probe against the repaired 47-row honest frontier; non-promotable until any movement is rebuilt from disjoint roots",
        "required_honesty_gates": [
            "strict eval remains the unchanged 47-row quarantined full-visible frontier",
            "support rows are train-only and this run is non-promotable by design",
            "c_cpp citation support includes same-bundle train-only rows and therefore can only answer whether the residual is learnable at all",
            "success means at least one residual miss moves without creating new frontier regressions",
        ],
        "next_best_step": "run one focused residual-support probe to distinguish a learnable semantic miss from a bounded-choice representation ceiling",
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
                "support_counts": support_counts,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
