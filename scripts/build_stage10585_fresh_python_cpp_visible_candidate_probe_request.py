#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10585
NAME = "stage10585_fresh_python_cpp_visible_candidate_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "fresh_python_cpp_visible_candidate_probe_request.json"
COMMAND_JSON = OUT_DIR / "fresh_python_cpp_visible_candidate_probe_command.json"
MANIFEST_JSONL = OUT_DIR / "fresh_python_cpp_visible_candidate_probe_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SUPPORT_PACKAGE = ROOT / "runs/local/artifacts/stage10584_fresh_python_cpp_visible_candidate_package/fresh_python_cpp_visible_candidate_package.json"
SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10584_fresh_python_cpp_visible_candidate_package/support_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10584_fresh_python_cpp_visible_candidate_package/strict_eval_rows.jsonl"
CANARY_AUDIT = ROOT / "runs/local/artifacts/stage10575_visible_candidate_mixed_preservation_canary_audit/visible_candidate_mixed_preservation_canary_audit.json"
FRONTIER_AUDIT = ROOT / "runs/local/artifacts/stage10577_visible_candidate_mixed_preservation_result_audit/visible_candidate_mixed_preservation_result_audit.json"

INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10574_visible_candidate_mixed_preservation_probe/runtime_model/runtime_model_bundle.json"
PRESERVATION_REF = ROOT / "runs/local/artifacts/stage10574_visible_candidate_mixed_preservation_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10586_fresh_python_cpp_visible_candidate_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10586_fresh_python_cpp_visible_candidate_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10586_fresh_python_cpp_visible_candidate_probe/runtime_model"


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


def normalize_rows() -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    split_counts = {"train": 0, "eval": 0, "strict_eval": 0}
    language_counts: dict[str, int] = {}
    for path, out_split in ((SUPPORT_ROWS, "train"), (STRICT_ROWS, "strict_eval")):
        for row in load_jsonl(path):
            copied = json.loads(json.dumps(row))
            copied["split"] = out_split
            copied["loss_mask"] = {"decoder_ce": True}
            copied["expected_enabled_loss"] = "decoder_ce"
            copied["disable_losses"] = [] if out_split == "train" else ["denoise_ce", "runtime_reward", "structured_aux"]
            rows.append(copied)
            split_counts[out_split] += 1
            language = str(copied.get("language_family") or "unknown")
            language_counts[language] = language_counts.get(language, 0) + 1
    return rows, split_counts, dict(sorted(language_counts.items()))


def build_command(split_counts: dict[str, int]) -> list[str]:
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
        "--max-train-rows", str(split_counts["train"]),
        "--max-eval-rows", "0",
        "--max-strict-rows", str(split_counts["strict_eval"]),
        "--max-steps", "96",
        "--batch-size", "1",
        "--learning-rate", "6e-6",
        "--max-encoder-tokens", "1024",
        "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "1.0",
        "--bounded-choice-aux-weight", "1.0",
        "--bounded-choice-aux-source", "decoder_first_step",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "2.0",
        "--enable-generation-audit",
        "--max-generation-rows", "24",
        "--max-generation-tokens", "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(ROOT / RUNTIME_MODEL_DIR),
        "--initialize-from-runtime-model", str(INIT_RUNTIME),
        "--preservation-reference-runtime-model", str(PRESERVATION_REF),
        "--preservation-kl-weight", "1.0",
        "--no-final-checkpoint-export",
        "--skip-final-model-save", "1",
        "--output-dir", str(ROOT / OUTPUT_DIR),
        "--run-id", RUN_ID,
    ]


def main() -> None:
    support_package = load_json(SUPPORT_PACKAGE)
    canary = load_json(CANARY_AUDIT)
    frontier = load_json(FRONTIER_AUDIT)
    manifest_rows, split_counts, language_counts = normalize_rows()
    command = build_command(split_counts)
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(support_package.get("passed")),
        "decision": "fresh_python_cpp_visible_candidate_probe_ready",
        "source_support_package": display(SUPPORT_PACKAGE),
        "manifest": display(MANIFEST_JSONL),
        "run_id": RUN_ID,
        "output_dir": OUTPUT_DIR,
        "runtime_model_dir": RUNTIME_MODEL_DIR,
        "rows": len(manifest_rows),
        "split_counts": split_counts,
        "language_counts": language_counts,
        "initialize_from_runtime_model": display(INIT_RUNTIME),
        "preservation_reference_runtime_model": display(PRESERVATION_REF),
        "claim_scope": [
            "Fresh-root target-100M probe on the stage10584 repo-disjoint Python/C++ visible-candidate package.",
            "Starts from the current restored stage10574 runtime so any gain measures fresh-root transfer rather than training from a weaker baseline.",
            "Not promotable unless the fresh strict slice improves while the old repaired v2.7 canary and rebuilt 54-row frontier remain non-regressed in post-run audits.",
        ],
        "motivation": {
            "fresh_support_rows": ((support_package.get("rows") or {}).get("support_rows")),
            "fresh_strict_rows": ((support_package.get("rows") or {}).get("strict_eval_rows")),
            "stage10575_canary_bounded_accuracy": ((canary.get("summary") or {}).get("bounded_accuracy")),
            "stage10577_rebuilt_strict_bounded_accuracy": ((frontier.get("current_state") or {}).get("stage10574_strict_bounded_accuracy")),
        },
        "training_deltas": {
            "train_support_manifest": "stage10584_fresh_python_cpp_visible_candidate_package",
            "initialize_from_runtime_model": "stage10574_visible_candidate_mixed_preservation_probe",
            "preservation_reference_runtime_model": "stage10574_visible_candidate_mixed_preservation_probe",
            "max_steps": "96",
            "learning_rate": "6e-6",
            "bounded_choice_aux_source": "decoder_first_step",
        },
        "required_honesty_gates": [
            "stage10584 support rows remain train-only and repo-family-disjoint from the stage10584 strict roots",
            "fresh strict rows are reported separately from the old rebuilt 54-row strict frontier",
            "post-run stage10575 canary must remain at least 22/24 bounded",
            "post-run stage10577 rebuilt strict audit must remain at least 36/54 bounded overall",
            "fresh strict same-manifest comparison versus Gemma must be reported separately from old-frontier comparisons",
            "no claim of Rust/Web uplift can be made from this package because stage10584 only covers Python and C/C++",
        ],
        "post_run_required_artifacts": [
            "bounded_decoder_probe/execution_result.json",
            "post-run repaired v2.7 canary audit against stage10586 runtime",
            "post-run rebuilt 54-row same-manifest comparison against stage10586 runtime",
            "post-run fresh strict same-manifest comparison versus Gemma on stage10584 strict rows",
        ],
        "known_limits": [
            "This probe intentionally only targets fresh Python and C/C++ because stage10582 showed Rust/Web fresh-root supply is still too thin.",
            "Retrieve and verifier rows in stage10584 are preservation-style fixed-choice contracts; the fresh signal is mainly decisive-evidence transfer.",
        ],
        "next_best_step": "Launch the stage10586 probe from this request, then rerun canary and old-frontier audits plus a fresh strict Gemma comparison before deciding whether fresh-root transfer really improves the 100M model.",
        "command": command,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(MANIFEST_JSONL, manifest_rows)
    write_json(COMMAND_JSON, {"command": command, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)})
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY, {
        "stage": STAGE,
        "passed": True,
        "request": display(REQUEST_JSON),
        "manifest": display(MANIFEST_JSONL),
        "split_counts": split_counts,
        "language_counts": language_counts,
    })
    print(json.dumps({"stage": STAGE, "passed": request["passed"], "run_id": RUN_ID, "rows": len(manifest_rows)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
