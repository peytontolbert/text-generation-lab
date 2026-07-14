#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10618
NAME = "stage10618_reviewed_plus_bootstrap_multilingual_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "reviewed_plus_bootstrap_multilingual_probe_request.json"
COMMAND_JSON = OUT_DIR / "reviewed_plus_bootstrap_multilingual_probe_command.json"
MANIFEST_JSONL = OUT_DIR / "reviewed_plus_bootstrap_multilingual_probe_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10617_reviewed_plus_bootstrap_multilingual_training_package_fixed/reviewed_plus_bootstrap_multilingual_training_package_fixed.json"
TRAIN_ROWS = ROOT / "runs/local/artifacts/stage10617_reviewed_plus_bootstrap_multilingual_training_package_fixed/train_rows.jsonl"
VALIDATION_ROWS = ROOT / "runs/local/artifacts/stage10617_reviewed_plus_bootstrap_multilingual_training_package_fixed/validation_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10617_reviewed_plus_bootstrap_multilingual_training_package_fixed/strict_rows.jsonl"
CANARY_ROWS = ROOT / "runs/local/artifacts/stage10617_reviewed_plus_bootstrap_multilingual_training_package_fixed/canary_rows.jsonl"
SUPPLY_AUDIT = ROOT / "runs/local/artifacts/stage10615_multilingual_root_supply_balance_audit/multilingual_root_supply_balance_audit.json"

INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10611_repaired_v27_fresh_root_probe/runtime_model/runtime_model_bundle.json"
PRESERVATION_REF = ROOT / "runs/local/artifacts/stage10611_repaired_v27_fresh_root_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10618_reviewed_plus_bootstrap_multilingual_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10618_reviewed_plus_bootstrap_multilingual_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10618_reviewed_plus_bootstrap_multilingual_probe/runtime_model"

LANGUAGE_CAPS = {
    "python": 96,
    "c_cpp": 24,
    "rust": 16,
    "web_js_ts_html": 8,
}
REPO_CAPS = {
    "python": 8,
    "c_cpp": 8,
    "rust": 16,
    "web_js_ts_html": 8,
}


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
    updated["objective_family"] = "reviewed_plus_bootstrap_multilingual_decoder_ce"
    updated["target_token_len"] = max(1, len(str(updated.get("target_text", "")).split()))
    return updated


def capped_train_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(rows, key=lambda r: (str(r.get("language_family") or ""), str(r.get("repo_family") or ""), str(r.get("row_id") or ""))):
        grouped[str(row.get("language_family") or "unknown")].append(row)

    selected: list[dict[str, Any]] = []
    for language, lang_rows in grouped.items():
        repo_cap = REPO_CAPS.get(language, 8)
        language_cap = LANGUAGE_CAPS.get(language, len(lang_rows))
        repo_counts: Counter[str] = Counter()
        picked = 0
        for row in lang_rows:
            repo = str(row.get("repo_family") or "unknown")
            if repo_counts[repo] >= repo_cap:
                continue
            selected.append(row)
            repo_counts[repo] += 1
            picked += 1
            if picked >= language_cap:
                break
    return sorted(selected, key=lambda r: (str(r.get("language_family") or ""), str(r.get("repo_family") or ""), str(r.get("row_id") or "")))


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
        "--max-generation-rows", "24",
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
    supply_audit = load_json(SUPPLY_AUDIT)
    train_rows = load_jsonl(TRAIN_ROWS)
    validation_rows = load_jsonl(VALIDATION_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)
    canary_rows = load_jsonl(CANARY_ROWS)

    capped_train = [with_probe_fields(row, "train") for row in capped_train_rows(train_rows)]
    eval_rows = [with_probe_fields(row, "eval") for row in validation_rows]
    strict_eval_rows = [with_probe_fields(row, "strict_eval") for row in strict_rows]
    manifest_rows = capped_train + eval_rows + strict_eval_rows
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    command = build_command(len(capped_train), len(eval_rows), len(strict_eval_rows))
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(capped_train) and bool(strict_eval_rows),
        "decision": "reviewed_plus_bootstrap_multilingual_probe_ready",
        "claim_scope": [
            "Launch the next clean multilingual training probe from the corrected admitted-root package only.",
            "Use repo caps and per-language caps to prevent Python-family dominance from swamping the multilingual objective.",
            "Keep repaired v2.7 canary rows outside the main train manifest and require post-run canary evaluation separately.",
        ],
        "source_package": display(PACKAGE_JSON),
        "manifest": display(MANIFEST_JSONL),
        "run_id": RUN_ID,
        "output_dir": OUTPUT_DIR,
        "runtime_model_dir": RUNTIME_MODEL_DIR,
        "rows": len(manifest_rows),
        "split_counts": {
            "train": len(capped_train),
            "eval": len(eval_rows),
            "strict_eval": len(strict_eval_rows),
        },
        "language_counts_by_split": {
            "train": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in capped_train).items())),
            "eval": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in eval_rows).items())),
            "strict_eval": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in strict_eval_rows).items())),
        },
        "source_kind_counts_by_split": {
            "train": dict(sorted(Counter(str(row.get("package_source_kind") or "unknown") for row in capped_train).items())),
            "eval": dict(sorted(Counter(str(row.get("package_source_kind") or "unknown") for row in eval_rows).items())),
            "strict_eval": dict(sorted(Counter(str(row.get("package_source_kind") or "unknown") for row in strict_eval_rows).items())),
        },
        "caps": {
            "language_caps": LANGUAGE_CAPS,
            "repo_caps": REPO_CAPS,
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
            "quarantined roots remain excluded from the probe manifest",
            "repo-family caps stay active for the train split",
            "repaired v2.7 canary stays outside main train counts and is evaluated post-run",
            "post-run headline must separate reviewed strict, bootstrap strict, and canary results",
        ],
        "post_run_required_artifacts": [
            "bounded_decoder_probe/execution_result.json",
            "post-run strict comparison against the 36-row admitted multilingual strict package",
            "post-run repaired-v2.7 canary audit against the 24-row overlay",
            "language-slice and source-kind slice accuracy cards",
        ],
        "known_limits": [
            "Rust and web remain thin enough that this probe is still a packaging step, not final multilingual closure.",
            "Bootstrap strict rows still reflect the current bounded-decision long-context interface, not full maintainer-grade freeform repair.",
            "Quarantined long-context roots still need interface rewrites before true large-scale growth is honest.",
        ],
        "next_best_step": (
            "Launch this capped multilingual probe, then judge it on three separate surfaces: "
            "the 36-row admitted multilingual strict package, the repaired 24-row v2.7 canary, and source-kind slices."
        ),
        "canary_contract": {
            "rows": len(canary_rows),
            "path": display(CANARY_ROWS),
        },
        "supply_context": {
            "package_train_rows_before_caps": ((package.get("splits") or {}).get("train") or {}).get("rows"),
            "package_train_rows_after_caps": len(capped_train),
            "repo_caps_needed": (supply_audit.get("dominance_and_gap_findings") or {}).get("repo_caps_needed"),
        },
        "command": command,
    }

    write_json(COMMAND_JSON, {"command": command, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)})
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY, {"stage": STAGE, "passed": request["passed"], "request": display(REQUEST_JSON), "manifest": display(MANIFEST_JSONL)})
    print(json.dumps({"stage": STAGE, "passed": request["passed"], "run_id": RUN_ID, "rows": len(manifest_rows)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
