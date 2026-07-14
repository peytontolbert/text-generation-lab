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
NAME = "stage11699_web_verifier_transition_preservation_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "web_verifier_transition_preservation_probe_request.json"
MANIFEST = OUT / "web_verifier_transition_preservation_train_manifest.jsonl"

BASE_MANIFEST = ART / "stage11695_web_identity_gap_topup_probe_request/web_identity_gap_topup_train_manifest.jsonl"
INIT_RUNTIME = ART / "stage11695_web_identity_gap_topup_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ART / "stage11699_web_verifier_transition_preservation_probe"
RUNTIME_DIR = RUN_DIR / "runtime_model"
OUTPUT_DIR = RUN_DIR / "bounded_decoder_probe"


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


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("bounded_choice_target_label") or row.get("target_text") or (row.get("target") or {}).get("bounded_choice_target_label") or "").strip()


def is_preservation_row(row: dict[str, Any]) -> bool:
    if str(row.get("task_type")) != "verifier_outcome":
        return False
    repo = str(row.get("repo_id") or row.get("repo_family") or "").lower()
    target = target_label(row)
    return target == "C" or "modelcontextprotocol" in repo or repo.startswith("@modelcontextprotocol")


def tag(row: dict[str, Any], source: str, copy_idx: int | None = None) -> dict[str, Any]:
    out = dict(row)
    if copy_idx is not None:
        out["row_id"] = f"{row.get('row_id')}::stage11699_preserve_copy_{copy_idx:02d}"
    out["stage11699_source"] = source
    out["trainable_now"] = True
    out["strict_eval_eligible_now"] = False
    out["train_support_only"] = True
    out["split"] = "train"
    out["package_split"] = "train"
    out["split_component"] = "stage11699_web_verifier_transition_preservation_train"
    anti = dict(out.get("anti_cheat") or {})
    anti.update({"stage11699_train_support_only": True, "no_heldout_training": True})
    out["anti_cheat"] = anti
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base_rows = load_jsonl(BASE_MANIFEST)
    rows = [tag(row, "stage11695_base_replay") for row in base_rows]
    preservation = [row for row in base_rows if is_preservation_row(row)]
    for copy_idx in range(3):
        for row in preservation:
            rows.append(tag(row, "stage11699_verifier_c_mcp_preservation", copy_idx))
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
        "512",
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
        "0.05",
        "--bounded-choice-contrast-margin",
        "0.04",
        "--bounded-choice-verifier-value-listwise-weight",
        "1.0",
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
        "base_rows": len(base_rows),
        "preservation_source_rows": len(preservation),
        "preservation_extra_rows": len(preservation) * 3,
        "by_source": dict(Counter(str(row.get("stage11699_source")) for row in rows).most_common()),
        "verifier_targets": dict(Counter(target_label(row) for row in rows if str(row.get("task_type")) == "verifier_outcome").most_common()),
    }
    gates = {
        "manifest_exists": MANIFEST.exists(),
        "init_runtime_exists": INIT_RUNTIME.exists(),
        "uses_gpu2": "CUDA_VISIBLE_DEVICES=2" in command,
        "head_only": "--bounded-choice-train-head-only" in command,
        "initializes_from_stage11695": INIT_RUNTIME.exists(),
        "preservation_rows_at_least_30": len(preservation) >= 30,
        "short_low_lr_probe": "--max-steps" in command and command[command.index("--max-steps") + 1] == "512",
    }
    summary = {
        "stage": 11699,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "web_verifier_transition_preservation_probe_ready" if all(gates.values()) else "web_verifier_transition_preservation_probe_blocked",
        "manifest": rel(MANIFEST),
        "init_runtime": rel(INIT_RUNTIME),
        "runtime_dir": rel(RUNTIME_DIR),
        "output_dir": rel(OUTPUT_DIR),
        "row_counts": counts,
        "command": command,
        "command_string": " ".join(command),
        "gates_before_execution": gates,
        "postrun_gate": [
            "retain Stage11695 OpenHands verifier gains",
            "recover MCP C-target regressions",
            "bridged Web >56/66",
            "protected gates preserved",
        ],
        "claim_boundary": [
            "This is a short head-only preservation pass initialized from Stage11695.",
            "It uses train-support analogues only; heldout bridged Web rows remain excluded.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "row_counts": counts, "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
