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
NAME = "stage11695_web_identity_gap_topup_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "web_identity_gap_topup_probe_request.json"
MANIFEST = OUT / "web_identity_gap_topup_train_manifest.jsonl"

VERIFIER_SUPPORT = ART / "stage11693_web_gap_targeted_support_inventory/web_gap_targeted_support_rows.jsonl"
SOURCE_FIX_TOPUP = ART / "stage11694_web_gap_role_normalized_topup_package/web_gap_role_normalized_topup_rows.jsonl"
IDENTITY_REPLAY = ART / "stage11678_web_remaining_miss_counterfactual_builder/web_same_role_identity_counterfactual_train.jsonl"
INIT_RUNTIME = ART / "stage11685_counterfactual_identity_semantic_head_fixed_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ART / "stage11695_web_identity_gap_topup_probe"
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("row_id"))


def include_verifier_support(row: dict[str, Any]) -> bool:
    return str(row.get("stage11693_gap_need_family")) in {
        "verifier_transition_same_role",
        "symptom_verifier_vs_candidate_surface",
    }


def tag(row: dict[str, Any], source: str) -> dict[str, Any]:
    out = dict(row)
    out["stage11695_source"] = source
    out["trainable_now"] = True
    out["strict_eval_eligible_now"] = False
    out["train_support_only"] = True
    out["split"] = "train"
    out["package_split"] = "train"
    out["split_component"] = "stage11695_web_identity_gap_train"
    anti = dict(out.get("anti_cheat") or {})
    anti.update({"stage11695_train_support_only": True, "no_heldout_training": True})
    out["anti_cheat"] = anti
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    verifier_rows = [tag(row, "stage11693_verifier_or_symptom_support") for row in load_jsonl(VERIFIER_SUPPORT) if include_verifier_support(row)]
    topup_rows = [tag(row, "stage11694_source_fix_topup") for row in load_jsonl(SOURCE_FIX_TOPUP)]
    replay_rows = [tag(row, "stage11678_identity_replay") for row in load_jsonl(IDENTITY_REPLAY)]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in verifier_rows + topup_rows + replay_rows:
        row_id = str(row.get("row_id"))
        if row_id in seen:
            continue
        seen.add(row_id)
        rows.append(row)
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
        "1536",
        "--batch-size",
        "8",
        "--learning-rate",
        "3e-4",
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
        "0.2",
        "--bounded-choice-contrast-margin",
        "0.06",
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
        "roots": len({root_key(row) for row in rows}),
        "by_source": dict(Counter(str(row.get("stage11695_source")) for row in rows).most_common()),
        "by_task": dict(Counter(str(row.get("task_type") or "unknown") for row in rows).most_common()),
    }
    gates = {
        "manifest_exists": MANIFEST.exists(),
        "init_runtime_exists": INIT_RUNTIME.exists(),
        "uses_gpu2_mask": "CUDA_VISIBLE_DEVICES=2" in command,
        "uses_semantic_candidate_head": "encoder_option_retrieval_semantic_candidate_head" in command,
        "head_only": "--bounded-choice-train-head-only" in command,
        "identity_replay_present": counts["by_source"].get("stage11678_identity_replay", 0) >= 90,
        "source_fix_topup_present": counts["by_source"].get("stage11694_source_fix_topup", 0) >= 90,
        "verifier_support_present": counts["by_source"].get("stage11693_verifier_or_symptom_support", 0) >= 50,
        "rows_at_least_200": len(rows) >= 200,
    }
    decision = "web_identity_gap_topup_probe_ready" if all(gates.values()) else "web_identity_gap_topup_probe_blocked"
    summary = {
        "stage": 11695,
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
            "canonical-bridged Web > 56/66",
            "canonical heldout >= 53/66",
            "filtered strict 22/22",
            "old canary strict 23/23",
            "residual >= 7/10",
        ],
        "claim_boundary": [
            "This is a head-only semantic identity scorer probe, initialized from Stage11685.",
            "It does not train on the 66 bridged heldout rows or the 13 Gemma-margin rows.",
            "Promotion requires postrun routed audit and same-manifest Gemma comparison remains Stage11691.",
        ],
        "source_artifacts": {
            "verifier_support": rel(VERIFIER_SUPPORT),
            "source_fix_topup": rel(SOURCE_FIX_TOPUP),
            "identity_replay": rel(IDENTITY_REPLAY),
        },
        "outputs": {"summary": rel(SUMMARY), "manifest": rel(MANIFEST)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "row_counts": counts, "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
