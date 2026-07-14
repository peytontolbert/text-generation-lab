#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10636
NAME = "stage10636_repaired_long_context_successor_probe_request_permuted"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "repaired_long_context_successor_probe_request_permuted.json"
COMMAND_JSON = OUT_DIR / "repaired_long_context_successor_probe_command_permuted.json"
MANIFEST_JSONL = OUT_DIR / "repaired_long_context_successor_probe_manifest_permuted.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10635_repaired_long_context_successor_package_permuted/repaired_long_context_successor_package_permuted.json"
TRAIN_ROWS = ROOT / "runs/local/artifacts/stage10635_repaired_long_context_successor_package_permuted/repaired_long_context_successor_package_permuted_train_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10635_repaired_long_context_successor_package_permuted/repaired_long_context_successor_package_permuted_strict_rows.jsonl"
ROOT_ADMISSION_AUDIT = ROOT / "runs/local/artifacts/stage10628_root_admission_scale_audit/root_admission_scale_audit.json"

INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10611_repaired_v27_fresh_root_probe/runtime_model/runtime_model_bundle.json"
PRESERVATION_REF = ROOT / "runs/local/artifacts/stage10611_repaired_v27_fresh_root_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10636_repaired_long_context_successor_probe_permuted"
OUTPUT_DIR = "runs/local/artifacts/stage10636_repaired_long_context_successor_probe_permuted/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10636_repaired_long_context_successor_probe_permuted/runtime_model"

TRAIN_ROOT_CAPS = {
    "python": 23,
    "c_cpp": 6,
    "rust": 2,
    "web_js_ts_html": 4,
}
EVAL_ROOT_CAPS = {
    "python": 3,
    "c_cpp": 1,
    "rust": 1,
    "web_js_ts_html": 1,
}
REPO_ROOT_CAP = 2
TARGET_100M_MAX_TRAIN_ROWS = 105


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


def root_sort_key(root_id: str, rows: list[dict[str, Any]]) -> tuple[str, str, str]:
    sample = rows[0]
    return (
        str(sample.get("repo_family") or ""),
        str(sample.get("repo_id") or ""),
        root_id,
    )


def grouped_by_root(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("root_id"))].append(row)
    return grouped


def select_root_ids(
    grouped: dict[str, list[dict[str, Any]]],
    *,
    per_language_root_caps: dict[str, int],
    repo_root_cap: int,
    exclude_root_ids: set[str] | None = None,
) -> list[str]:
    exclude = exclude_root_ids or set()
    selected: list[str] = []
    per_language_counts: Counter[str] = Counter()
    per_repo_counts: Counter[tuple[str, str]] = Counter()
    roots = sorted(grouped.items(), key=lambda item: root_sort_key(item[0], item[1]))
    for root_id, root_rows in roots:
        if root_id in exclude:
            continue
        sample = root_rows[0]
        language = str(sample.get("language_family") or "unknown")
        repo_family = str(sample.get("repo_family") or "unknown")
        repo_id = str(sample.get("repo_id") or "unknown")
        if per_language_counts[language] >= per_language_root_caps.get(language, 0):
            continue
        repo_key = (language, repo_family or repo_id)
        if per_repo_counts[repo_key] >= repo_root_cap:
            continue
        selected.append(root_id)
        per_language_counts[language] += 1
        per_repo_counts[repo_key] += 1
    return selected


def with_probe_fields(row: dict[str, Any], split: str) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = split
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    if split == "train":
        updated["disable_losses"] = []
    else:
        updated["disable_losses"] = ["denoise_ce", "runtime_reward", "structured_aux"]
    updated["decoder_text"] = str(updated.get("target_text", ""))
    updated["prompt_text"] = str(updated.get("input_text") or updated.get("prompt_text") or "")
    updated["objective_family"] = "repaired_long_context_successor_decoder_ce_permuted"
    updated["target_token_len"] = max(1, len(str(updated.get("target_text", "")).split()))
    updated["probe_stage"] = STAGE
    return updated


def build_command(train_count: int, eval_count: int, strict_count: int) -> list[str]:
    return [
        "env",
        f"TMPDIR={TMPDIR}",
        f"TEMP={TMPDIR}",
        f"TMP={TMPDIR}",
        "AGENTKERNEL_TRAIN_DEVICE=cuda",
        "conda", "run", "-n", "trellis",
        "python", str(TRAINER),
        "--repo-root", str(ROOT),
        "--manifest", str(MANIFEST_JSONL),
        "--mode", "bounded_decoder_ce_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG),
        "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG),
        "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows", str(train_count),
        "--max-eval-rows", str(eval_count),
        "--max-strict-rows", str(strict_count),
        "--max-steps", "128",
        "--batch-size", "2",
        "--learning-rate", "1e-5",
        "--max-encoder-tokens", "1024",
        "--max-decoder-tokens", "256",
        "--decoder-ce-weight", "1.0",
        "--bounded-choice-aux-weight", "0.2",
        "--bounded-choice-aux-source", "encoder_option_retrieval",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "2.0",
        "--enable-generation-audit",
        "--max-generation-rows", "18",
        "--max-generation-tokens", "128",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(ROOT / RUNTIME_MODEL_DIR),
        "--initialize-from-runtime-model", str(INIT_RUNTIME),
        "--preservation-reference-runtime-model", str(PRESERVATION_REF),
        "--preservation-kl-weight", "1.5",
        "--no-final-checkpoint-export",
        "--skip-final-model-save", "1",
        "--output-dir", str(ROOT / OUTPUT_DIR),
        "--run-id", RUN_ID,
    ]


def main() -> None:
    package = load_json(PACKAGE_JSON)
    root_admission_audit = load_json(ROOT_ADMISSION_AUDIT)
    support_rows = load_jsonl(TRAIN_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)

    support_grouped = grouped_by_root(support_rows)
    strict_grouped = grouped_by_root(strict_rows)
    strict_root_ids = set(strict_grouped)

    eval_root_ids = set(
        select_root_ids(
            support_grouped,
            per_language_root_caps=EVAL_ROOT_CAPS,
            repo_root_cap=1,
            exclude_root_ids=strict_root_ids,
        )
    )
    train_root_ids = set(
        select_root_ids(
            support_grouped,
            per_language_root_caps=TRAIN_ROOT_CAPS,
            repo_root_cap=REPO_ROOT_CAP,
            exclude_root_ids=eval_root_ids | strict_root_ids,
        )
    )

    train_rows = [with_probe_fields(row, "train") for row in support_rows if str(row.get("root_id")) in train_root_ids]
    eval_rows = [with_probe_fields(row, "eval") for row in support_rows if str(row.get("root_id")) in eval_root_ids]
    strict_eval_rows = [with_probe_fields(row, "strict_eval") for row in strict_rows]

    manifest_rows = train_rows + eval_rows + strict_eval_rows
    manifest_rows.sort(key=lambda row: (str(row.get("split") or ""), str(row.get("row_id") or "")))
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    if len(train_rows) > TARGET_100M_MAX_TRAIN_ROWS:
        raise SystemExit(f"target_100m train cap exceeded: {len(train_rows)} > {TARGET_100M_MAX_TRAIN_ROWS}")
    if train_root_ids & eval_root_ids:
        raise SystemExit("train/eval root overlap detected")
    if train_root_ids & strict_root_ids:
        raise SystemExit("train/strict root overlap detected")
    if eval_root_ids & strict_root_ids:
        raise SystemExit("eval/strict root overlap detected")

    command = build_command(len(train_rows), len(eval_rows), len(strict_eval_rows))
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(train_rows) and bool(strict_eval_rows),
        "decision": "repaired_long_context_successor_probe_permuted_ready",
        "claim_scope": [
            "Launch the repaired long-context support probe on the label-position-permuted decisive-evidence strict slice.",
            "Keep headline strict scoring limited to decisive_evidence_option.",
            "Require the strict slice to remain nonconstant in both target label and gold candidate position.",
            "Keep verifier_outcome_option and retrieve_answer_abstain_option support-only.",
        ],
        "source_package": display(PACKAGE_JSON),
        "source_root_admission_audit": display(ROOT_ADMISSION_AUDIT),
        "manifest": display(MANIFEST_JSONL),
        "run_id": RUN_ID,
        "output_dir": OUTPUT_DIR,
        "runtime_model_dir": RUNTIME_MODEL_DIR,
        "rows": len(manifest_rows),
        "split_counts": {
            "train": len(train_rows),
            "eval": len(eval_rows),
            "strict_eval": len(strict_eval_rows),
        },
        "root_counts_by_split": {
            "train": len(train_root_ids),
            "eval": len(eval_root_ids),
            "strict_eval": len(strict_root_ids),
        },
        "language_counts_by_split": {
            "train": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in train_rows).items())),
            "eval": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in eval_rows).items())),
            "strict_eval": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in strict_eval_rows).items())),
        },
        "target_subtype_counts_by_split": {
            "train": dict(sorted(Counter(str(row.get("target_subtype") or "unknown") for row in train_rows).items())),
            "eval": dict(sorted(Counter(str(row.get("target_subtype") or "unknown") for row in eval_rows).items())),
            "strict_eval": dict(sorted(Counter(str(row.get("target_subtype") or "unknown") for row in strict_eval_rows).items())),
        },
        "selection_policy": {
            "train_root_caps": TRAIN_ROOT_CAPS,
            "eval_root_caps": EVAL_ROOT_CAPS,
            "repo_root_cap": REPO_ROOT_CAP,
            "target_100m_max_train_rows": TARGET_100M_MAX_TRAIN_ROWS,
            "strict_headline_subtypes": ["decisive_evidence_option"],
            "support_only_subtypes": ["verifier_outcome_option", "retrieve_answer_abstain_option"],
            "strict_target_label_unique_count_required_gt": 1,
            "strict_gold_position_unique_count_required_gt": 1,
        },
        "training_deltas": {
            "initialize_from_runtime_model": display(INIT_RUNTIME),
            "preservation_reference_runtime_model": display(PRESERVATION_REF),
            "max_steps": 128,
            "learning_rate": "1e-5",
            "bounded_choice_aux_weight": 0.2,
            "max_encoder_tokens": 1024,
            "max_decoder_tokens": 256,
        },
        "required_honesty_gates": [
            "prompt_target_leak remains false for all included repaired rows",
            "same_root_train_eval_forbidden remains true across train, eval, and strict splits",
            "headline strict claim is limited to decisive_evidence_option only",
            "strict target labels must not be constant across the strict slice",
            "strict gold candidate positions must not be constant across the strict slice",
            "verifier_outcome_option and retrieve_answer_abstain_option stay outside promotable strict scoring",
        ],
        "post_run_required_artifacts": [
            "bounded_decoder_probe/execution_result.json",
            "strict comparison against the 18-row permuted repaired long-context decisive-evidence strict slice",
            "support-eval slice accuracy by language and target subtype",
            "post-run repaired-v2.7 canary audit against the 24-row overlay",
            "label-position audit proving the strict slice stayed nonconstant",
        ],
        "known_limits": [
            "This request still does not make verifier_outcome_option a promotable heldout result.",
            "retrieve_answer_abstain_option remains single-class support-only and cannot support headline claims.",
            "The repaired long-context interface is still compact bounded decision supervision, not full maintainer-grade freeform repair.",
        ],
        "package_context": {
            "combined_rows": ((package.get("metrics") or {}).get("combined_rows")),
            "train_support_rows_before_caps": ((package.get("metrics") or {}).get("train_support_rows")),
            "promotable_strict_rows": ((package.get("metrics") or {}).get("promotable_strict_rows")),
            "strict_target_label_unique_count": ((package.get("metrics") or {}).get("strict_target_label_unique_count")),
            "strict_gold_position_unique_count": ((package.get("metrics") or {}).get("strict_gold_position_unique_count")),
            "quarantined_root_ratio": ((root_admission_audit.get("metrics") or {}).get("quarantined_root_ratio")),
        },
        "next_best_step": "Launch this corrected probe and compare its honest strict result against the invalid stage10632 constant-slot run.",
        "command": command,
    }

    write_json(COMMAND_JSON, {"command": command, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)})
    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": request["passed"],
            "request": display(REQUEST_JSON),
            "manifest": display(MANIFEST_JSONL),
        },
    )
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": request["passed"],
                "rows": len(manifest_rows),
                "train_rows": len(train_rows),
                "eval_rows": len(eval_rows),
                "strict_rows": len(strict_eval_rows),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
