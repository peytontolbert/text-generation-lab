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
NAME = "stage11705_web_nonverifier_guarded_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "web_nonverifier_guarded_probe_request.json"
MANIFEST = OUT / "web_nonverifier_guarded_train_manifest.jsonl"

SUPPORT_ROWS = ART / "stage11704_web_remaining_nonverifier_support_package/web_remaining_nonverifier_support_rows.jsonl"
SUPPORT_SUMMARY = ART / "stage11704_web_remaining_nonverifier_support_package/web_remaining_nonverifier_support_package.json"
INIT_RUNTIME = ART / "stage11685_counterfactual_identity_semantic_head_fixed_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ART / "stage11705_web_nonverifier_guarded_probe"
RUNTIME_DIR = RUN_DIR / "runtime_model"
OUTPUT_DIR = RUN_DIR / "bounded_decoder_probe"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("row_id") or "")


def tag(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["stage11705_source"] = "stage11704_remaining_nonverifier_support"
    out["trainable_now"] = True
    out["strict_eval_eligible_now"] = False
    out["train_support_only"] = True
    out["split"] = "train"
    out["package_split"] = "train"
    out["split_component"] = "stage11705_web_nonverifier_guarded_train"
    anti = dict(out.get("anti_cheat") or {})
    anti.update({"stage11705_train_support_only": True, "no_heldout_training": True})
    out["anti_cheat"] = anti
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    support_summary = load_json(SUPPORT_SUMMARY)
    rows = [tag(row) for row in load_jsonl(SUPPORT_ROWS)]
    write_jsonl(MANIFEST, rows)
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
        str(len(rows)),
        "--max-eval-rows",
        "0",
        "--max-strict-rows",
        "0",
        "--max-steps",
        "768",
        "--batch-size",
        "8",
        "--learning-rate",
        "1e-4",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.0",
        "--bounded-choice-aux-weight",
        "3.0",
        "--bounded-choice-root-group-aux-weight",
        "2.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_semantic_candidate_head",
        "--bounded-choice-train-head-only",
        "--bounded-decoder-train-sampler",
        "web_gap_same_root_grouped",
        "--bounded-choice-contrast-weight",
        "0.1",
        "--bounded-choice-contrast-margin",
        "0.05",
        "--bounded-choice-same-role-listwise-weight",
        "1.0",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "4.0",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_DIR),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--no-final-checkpoint-export",
        "--output-dir",
        str(OUTPUT_DIR),
    ]
    counts = {
        "rows": len(rows),
        "roots": len({root_key(row) for row in rows}),
        "by_lane": dict(Counter(str(row.get("stage11704_lane") or "") for row in rows).most_common()),
        "by_task": dict(Counter(str(row.get("task_type") or "") for row in rows).most_common()),
        "by_repo": dict(Counter(str(row.get("repo_id") or row.get("repo_family") or "") for row in rows).most_common()),
    }
    gates = {
        "support_summary_ready": support_summary.get("decision") == "remaining_nonverifier_support_ready_for_guarded_probe",
        "manifest_exists": MANIFEST.exists(),
        "init_runtime_exists": INIT_RUNTIME.exists(),
        "uses_gpu2": "CUDA_VISIBLE_DEVICES=2" in command,
        "head_only": "--bounded-choice-train-head-only" in command,
        "semantic_candidate_head": "encoder_option_retrieval_semantic_candidate_head" in command,
        "rows_match_stage11704": len(rows) == int((support_summary.get("counts") or {}).get("admitted_rows") or -1),
        "rows_at_least_100": len(rows) >= 100,
        "roots_at_least_40": counts["roots"] >= 40,
    }
    decision = "web_nonverifier_guarded_probe_ready" if all(gates.values()) else "web_nonverifier_guarded_probe_blocked"
    summary = {
        "stage": 11705,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "manifest": rel(MANIFEST),
        "init_runtime": rel(INIT_RUNTIME),
        "run_dir": rel(RUN_DIR),
        "runtime_dir": rel(RUNTIME_DIR),
        "output_dir": rel(OUTPUT_DIR),
        "row_counts": counts,
        "command": command,
        "command_string": " ".join(command),
        "gates_before_execution": gates,
        "postrun_gate": [
            "Stage11703 product Web >= 60/66",
            "remaining Web misses < 6",
            "filtered strict 22/22",
            "old canary strict 23/23",
            "residual >= 7/10",
            "no anti-cheat regression",
        ],
        "claim_boundary": [
            "This is a guarded diagnostic/probe request, not a promotion result.",
            "It trains only the semantic candidate head from Stage11685 on disjoint train-support rows.",
            "It excludes the 66 bridged Web heldout rows and uses Stage11703 only as postrun evaluation.",
        ],
        "source_artifacts": {
            "support_rows": rel(SUPPORT_ROWS),
            "support_summary": rel(SUPPORT_SUMMARY),
        },
        "outputs": {"summary": rel(SUMMARY), "manifest": rel(MANIFEST)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "row_counts": counts, "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
