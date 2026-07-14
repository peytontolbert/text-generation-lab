#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10302
NAME = "stage10302_hf_local_support_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "hf_local_support_execution_request.json"
COMMAND_JSON = OUT_DIR / "hf_local_support_command.json"
MANIFEST = OUT_DIR / "hf_local_support_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_MANIFEST = ROOT / (
    "runs/local/artifacts/"
    "stage10274_frontier_preserving_code_assist_overlay_execution_request/"
    "frontier_preserving_code_assist_overlay_manifest.jsonl"
)
PROJECTION_PAYLOAD = ROOT / (
    "runs/local/artifacts/"
    "stage10301_hf_local_compact_bounded_projection/"
    "hf_local_compact_bounded_projection.json"
)
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
INIT_RUNTIME = ROOT / (
    "runs/local/artifacts/"
    "stage10278_frontier_runtime_bundle_probe/runtime_model/runtime_model_bundle.json"
)
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10303_hf_local_support_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10303_hf_local_support_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10303_hf_local_support_probe/runtime_model"
MAX_STEPS = 48
LEARNING_RATE = "8e-6"

HF_LOCAL_BUNDLE = (
    "stage10300::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_"
    "src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662::python"
)
MIRRORMIND_FAMILY = "models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e"
WEB_F0_FAMILY = "index_html_f0be60dc44"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts[str(row.get("split", "unknown"))] += 1
    return dict(sorted(counts.items()))


def count_focus_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts[str(row.get("task_type") or row.get("perspective") or "unknown")] += 1
    return dict(sorted(counts.items()))


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("row_id", ""))
        if row_id in seen:
            continue
        seen.add(row_id)
        out.append(row)
    return out


def rotate_options(options: list[dict[str, Any]], shift: int) -> list[dict[str, str]]:
    values = [str(option.get("value") or "") for option in options]
    labels = [str(option.get("label") or "") for option in options]
    if not values or len(values) != len(labels):
        return []
    rotated_values = values[shift:] + values[:shift]
    return [{"label": label, "value": value} for label, value in zip(labels, rotated_values)]


def rebuild_prompt(prompt: str, options: list[dict[str, str]]) -> str:
    if "\nOptions:\n" not in prompt or "\nAnswer:\n" not in prompt:
        raise ValueError("compact_prompt_missing_options_block")
    prefix, rest = prompt.split("\nOptions:\n", 1)
    _, suffix = rest.split("\nAnswer:\n", 1)
    option_lines = "\n".join(f"{row['label']}. {row['value']}" for row in options)
    return prefix + "\nOptions:\n" + option_lines + "\nAnswer:\n" + suffix


def projection_rows_for_hf_local() -> list[dict[str, Any]]:
    payload = load_json(PROJECTION_PAYLOAD)
    runs = [row for row in payload.get("runs") or [] if isinstance(row, dict)]
    for run in runs:
        task_pack = run.get("task_pack") if isinstance(run.get("task_pack"), dict) else {}
        if str(task_pack.get("bundle_id") or "") == HF_LOCAL_BUNDLE:
            return [row for row in task_pack.get("rows") or [] if isinstance(row, dict)]
    return []


def build_variant_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for row in rows:
        prompt = str(row.get("prompt_text") or row.get("input_text") or "")
        options = [option for option in (row.get("opaque_options") or []) if isinstance(option, dict)]
        gold_value = str(row.get("gold_value") or "")
        if not prompt or not options or not gold_value:
            continue
        values = [str(option.get("value") or "") for option in options]
        if gold_value not in values:
            continue
        perspective = str(row.get("task_type") or row.get("perspective") or "")
        for shift in range(len(options)):
            rotated = rotate_options(options, shift)
            if not rotated:
                continue
            label_by_value = {str(option["value"]): str(option["label"]) for option in rotated}
            target = label_by_value[gold_value]
            variant_prompt = rebuild_prompt(prompt, rotated)
            suffix = f"support::perm_{shift:02d}"
            variants.append(
                {
                    "row_id": f"{row.get('row_id')}::{suffix}",
                    "language_family": str(row.get("language_family") or ""),
                    "route": "KEEP_BOUNDED_DECODER",
                    "objective_family": "bounded_decoder_ce",
                    "surface": "maintainer_bundle_compact_bounded_choice",
                    "task_type": perspective,
                    "split": "train",
                    "prompt_text": variant_prompt,
                    "input_text": variant_prompt,
                    "query_text": str(row.get("query_text") or "") + f"::{suffix}",
                    "target_text": target,
                    "decoder_text": target,
                    "target_token_len": len(target.encode("utf-8")),
                    "loss_mask": {"decoder_ce": True},
                    "expected_enabled_loss": "decoder_ce",
                    "disable_losses": ["denoise_ce", "runtime_reward", "structured_aux"],
                    "source_skill_area": "maintainer_bundle_compact_bounded_choice",
                    "source_stage": STAGE,
                    "source_row_id": str(row.get("row_id") or ""),
                    "source_bundle_id": HF_LOCAL_BUNDLE,
                    "semantic_key": f"maintainer_bundle_compact_bounded_perm::{HF_LOCAL_BUNDLE}::{perspective}::{suffix}",
                    "anti_cheat": {
                        "opaque_labels": True,
                        "bundle_level_split_preserved": True,
                        "freeform_rows_excluded": True,
                        "compact_prompt_contract": True,
                        "permutation_balanced_labels": True,
                        "standalone_decoder_contract_gate_required": True,
                        "hf_local_support_train_only": True,
                        "derived_from_disjoint_train_root": True,
                    },
                    "authority": {
                        "model_execution_authorized_next": False,
                        "decoder_ce_training_authorized_next": False,
                        "denoise_ce_training_authorized_next": False,
                        "runtime_authorized": False,
                        "source_emission_authorized": False,
                        "body_emission_authorized": False,
                        "gemma_execution_authorized_next": False,
                        "harness_execution_authorized_next": False,
                        "scoring_authorized_next": False,
                        "controller_complete_merge_authorized_next": False,
                        "promotion_ready": False,
                    },
                    "standalone_projection_source": {
                        "projection_stage": 10301,
                        "projection_mode": "compact_bounded_choice_auxiliary",
                        "gold_answers_path": str((row.get("standalone_projection_source") or {}).get("gold_answers_path") or ""),
                        "original_answer_kind": str(row.get("original_answer_kind") or ""),
                        "gold_value": gold_value,
                        "variant_index": shift,
                        "variant_count": len(options),
                        "opaque_options": rotated,
                        "support_stage": STAGE,
                    },
                }
            )
    return variants


def command(counts: dict[str, int]) -> list[str]:
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
        str(MANIFEST),
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
        str(counts.get("train", 0)),
        "--max-eval-rows",
        "0",
        "--max-strict-rows",
        str(counts.get("strict_eval", 0)),
        "--max-steps",
        str(MAX_STEPS),
        "--batch-size",
        "2",
        "--learning-rate",
        LEARNING_RATE,
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "8",
        "--decoder-ce-weight",
        "0.25",
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
        "24",
        "--max-generation-tokens",
        "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(ROOT / RUNTIME_MODEL_DIR),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--no-final-checkpoint-export",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(ROOT / OUTPUT_DIR),
        "--run-id",
        RUN_ID,
    ]


def build_request() -> dict[str, Any]:
    base_rows = load_jsonl(BASE_MANIFEST)
    base_train = [row for row in base_rows if row.get("split") == "train"]
    strict_eval = [row for row in base_rows if row.get("split") == "strict_eval"]
    other_rows = [row for row in base_rows if row.get("split") not in {"train", "strict_eval"}]

    hf_local_projection = projection_rows_for_hf_local()
    hf_local_train = build_variant_rows(hf_local_projection)

    train_rows = dedupe_rows([*hf_local_train, *base_train])
    rows = [*train_rows, *strict_eval, *other_rows]
    counts = split_counts(rows)

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": (
            "Build a narrow successor from the current frontier that preserves the strict packet unchanged and adds only one new honest train-side root: "
            "the disjoint code_assist hf_local Python replenishment bundle projected into permutation-balanced bounded-choice support rows."
        ),
        "next_best_step": (
            "Run this 48-step hf_local support probe, then compare it against the existing lower-cue and hard-perspective audits. "
            "Promote only if Python improves without weakening the broader multilingual frontier or leaking unsupported holdout families."
        ),
        "source_manifests": {
            "frontier_manifest": display(BASE_MANIFEST),
            "hf_local_projection_payload": display(PROJECTION_PAYLOAD),
        },
        "manifest": display(MANIFEST),
        "rows": len(rows),
        "split_counts": counts,
        "output_dir": OUTPUT_DIR,
        "run_id": RUN_ID,
        "initialize_from_runtime_model": display(INIT_RUNTIME),
        "learning_rate": LEARNING_RATE,
        "max_steps": MAX_STEPS,
        "focus_families": {
            "python_supported_new_root": "src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2",
            "python_unsupported_holdout": MIRRORMIND_FAMILY,
            "web_unsupported_holdout": WEB_F0_FAMILY,
        },
        "frontloaded_focus_counts": {
            "hf_local_added": len(hf_local_train),
            "hf_local_by_perspective": count_focus_rows(hf_local_train),
        },
        "required_honesty_gates": [
            "strict eval rows remain identical to stage10274/stage10278",
            "no Mirrormind or web_f0 holdout rows are moved into train",
            "the new support rows come only from the disjoint stage10300 hf_local replenishment bundle",
            "any gain must be described as support-family generalization, not as direct repair of unsupported holdout families",
        ],
        "command": command(counts),
    }
    write_jsonl(MANIFEST, rows)
    write_json(REQUEST, request)
    write_json(COMMAND_JSON, {"command": request["command"], "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)})
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": True,
            "request": display(REQUEST),
            "manifest": display(MANIFEST),
            "frontloaded_focus_counts": request["frontloaded_focus_counts"],
        },
    )
    return request


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    payload = build_request()
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": True,
                "request": display(REQUEST),
                "manifest": display(MANIFEST),
                "frontloaded_focus_counts": payload["frontloaded_focus_counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
