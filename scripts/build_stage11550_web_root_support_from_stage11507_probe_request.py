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
STAGE = 11550
NAME = "stage11550_web_root_support_from_stage11507_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "web_root_support_from_stage11507_probe_request.json"
MANIFEST = OUT / "web_root_support_from_stage11507_probe_manifest.jsonl"
COMMAND = OUT / "web_root_support_from_stage11507_probe_command.json"
PROBE = ART / "stage11550_web_root_support_from_stage11507_probe/bounded_decoder_probe"
RUNTIME_OUT = ART / "stage11550_web_root_support_from_stage11507_probe/runtime_model"

INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
FILTERED_VALIDATION = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
OLD_VALIDATION = ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl"
OLD_STRICT = ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL = ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl"
WEB_HELDOUT = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"

TRAIN_SOURCES = {
    "stage11347_static": ART / "stage11347_web_static_verifier_maintainer_rows/web_static_verifier_train_support_rows.jsonl",
    "stage11354_executed": ART / "stage11354_web_executed_verifier_support_rows/web_executed_verifier_train_support_rows.jsonl",
    "stage11364_sourcebot": ART / "stage11364_web_sourcebot_executed_support_rows/web_sourcebot_executed_support_rows.jsonl",
    "stage11382_sourcebot_abstention": ART / "stage11382_web_sourcebot_true_abstention_counterfactual_rows/web_sourcebot_true_abstention_counterfactual_rows.jsonl",
    "stage11388_mcp": ART / "stage11388_mcp_fresh_web_verifier_support_rows/mcp_fresh_web_verifier_support_rows.jsonl",
    "stage11394_openhands": ART / "stage11394_openhands_support_unit_verifier_train_rows/openhands_support_unit_verifier_train_rows.jsonl",
    "stage11535_openclaw": ART / "stage11535_openclaw_web_gold_adjudicated_support_rows/openclaw_web_gold_adjudicated_train_support_rows.jsonl",
    "stage11537_openclaw_extra": ART / "stage11537_openclaw_extra_web_gold_support_rows/openclaw_extra_web_gold_train_support_rows.jsonl",
    "stage11545_openclaw_more": ART / "stage11545_openclaw_more_web_gold_train_rows/openclaw_more_web_gold_train_rows.jsonl",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def normalize_row(row: dict[str, Any], split: str, source: str) -> dict[str, Any]:
    out = dict(row)
    out["split"] = split
    out["stage11550_source"] = source
    out.setdefault("prompt_text", out.get("input_text") or "")
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
    out.setdefault("expected_enabled_loss", "bounded_choice" if split == "train" else "decoder_ce")
    if not isinstance(out.get("loss_mask"), dict):
        out["loss_mask"] = {"decoder_ce": True}
    standalone = dict(out.get("standalone_projection_source") or {})
    standalone.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = standalone
    if "target" not in out or not isinstance(out.get("target"), dict):
        out["target"] = {
            "decoder_text": out.get("decoder_text"),
            "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text"),
        }
    return out


def root_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("root_id") or row.get("source_bundle_id") or row.get("row_id", "").split("::")[0]) for row in rows}


def repo_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("repo_family") or "unknown") for row in rows))


def task_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("task_type") or "unknown") for row in rows))


def main() -> None:
    train: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    seen: set[str] = set()
    for source, path in TRAIN_SOURCES.items():
        rows = load_jsonl(path)
        source_counts[source] = len(rows)
        for row in rows:
            row_id = str(row.get("row_id"))
            if row_id in seen:
                continue
            seen.add(row_id)
            train.append(normalize_row(row, "train", source))
    validation = [normalize_row(row, "eval", "filtered_validation") for row in load_jsonl(FILTERED_VALIDATION)]
    strict = [normalize_row(row, "strict_eval", "filtered_strict") for row in load_jsonl(FILTERED_STRICT)]
    old_validation = load_jsonl(OLD_VALIDATION)
    old_strict = load_jsonl(OLD_STRICT)
    residual = load_jsonl(RESIDUAL)
    heldout = load_jsonl(WEB_HELDOUT)
    train_roots = root_ids(train)
    overlaps = {
        "train_vs_filtered_validation": sorted(train_roots & root_ids(validation)),
        "train_vs_filtered_strict": sorted(train_roots & root_ids(strict)),
        "train_vs_old_validation": sorted(train_roots & root_ids(old_validation)),
        "train_vs_old_strict": sorted(train_roots & root_ids(old_strict)),
        "train_vs_residual": sorted(train_roots & root_ids(residual)),
        "train_vs_web_heldout": sorted(train_roots & root_ids(heldout)),
    }
    manifest_rows = train + validation + strict
    command = [
        "env",
        "CUDA_VISIBLE_DEVICES=2",
        "NVIDIA_VISIBLE_DEVICES=2",
        "AGENTKERNEL_EVAL_DEVICE=cuda:0",
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
        str(len(train)),
        "--max-eval-rows",
        str(len(validation)),
        "--max-strict-rows",
        str(len(strict)),
        "--max-steps",
        "96",
        "--batch-size",
        "4",
        "--learning-rate",
        "1.5e-6",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.05",
        "--bounded-choice-aux-weight",
        "2.5",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_evidence_judgment_head",
        "--bounded-decoder-train-sampler",
        "cyclic",
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
        "16",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_OUT),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--bounded-choice-contrast-weight",
        "0.5",
        "--bounded-choice-contrast-margin",
        "0.06",
        "--preservation-kl-weight",
        "2.0",
        "--no-final-checkpoint-export",
        "--output-dir",
        str(PROBE),
    ]
    gates = {
        "train_rows_present": len(train) >= 120,
        "train_roots_at_least_20": len(train_roots) >= 20,
        "heldout_roots_at_least_10": len(root_ids(heldout)) >= 10,
        "no_train_eval_strict_or_heldout_root_overlap": all(not values for values in overlaps.values()),
        "all_train_rows_have_options": all(((row.get("standalone_projection_source") or {}).get("opaque_options")) for row in train),
        "all_train_rows_web": all(row.get("language_family") == "web_js_ts_html" for row in train),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(MANIFEST, manifest_rows)
    write_json(COMMAND, {"command": command})
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "web_root_support_stage11507_probe_ready" if all(gates.values()) else "web_root_support_stage11507_probe_blocked",
        "metrics": {
            "train_rows": len(train),
            "train_roots": len(train_roots),
            "train_repo_counts": repo_counts(train),
            "train_task_counts": task_counts(train),
            "filtered_validation_rows": len(validation),
            "filtered_strict_rows": len(strict),
            "web_heldout_rows": len(heldout),
            "web_heldout_roots": len(root_ids(heldout)),
            "source_counts": source_counts,
            "root_overlaps": overlaps,
        },
        "gates": gates,
        "command": command,
        "claim_boundary": [
            "Diagnostic Web transfer probe from Stage11507.",
            "Train rows include repo-family overlap with heldout families, so this cannot establish repo-family-heldout Web generalization.",
            "Promotion still requires preserving old/filtered canaries and improving the sealed 66-row Web heldout same-manifest comparison.",
        ],
        "source_artifacts": {
            "init_runtime": rel(INIT_RUNTIME),
            "web_heldout": rel(WEB_HELDOUT),
            "filtered_validation": rel(FILTERED_VALIDATION),
            "filtered_strict": rel(FILTERED_STRICT),
            **{f"train_{key}": rel(path) for key, path in TRAIN_SOURCES.items()},
        },
        "outputs": {
            "manifest": rel(MANIFEST),
            "command": rel(COMMAND),
            "probe_dir": rel(PROBE),
            "runtime_model": rel(RUNTIME_OUT),
            "summary": rel(SUMMARY),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "passed": summary["passed"], "metrics": summary["metrics"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
