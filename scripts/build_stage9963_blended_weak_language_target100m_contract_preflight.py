#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9963
NAME = "stage9963_blended_weak_language_target100m_contract_preflight"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9962_blended_weak_language_successor_mix.json"
STRUCTURED = ROOT / "runs/local/artifacts/stage9962_blended_weak_language_successor_mix/blended_weak_language_successor_structured_state.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST_DIR = OUT_DIR / "manifests"
RUNS_DIR = OUT_DIR / "contract_runs"
AUDIT = OUT_DIR / "blended_weak_language_target100m_contract_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BLENDED_WEAK_LANGUAGE_TARGET100M_CONTRACT_PREFLIGHT_STAGE9963.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

SURFACES = {
    "symbol_binding": {"loss": "symbol_binding_ce", "mode": "symbol_binding_probe"},
    "edit_localization": {"loss": "edit_localization_ce", "mode": "edit_localization_probe"},
    "patch_operator_selection": {"loss": "patch_operator_ce", "mode": "patch_operator_probe"},
    "verifier_failure_repair_or_abstain": {"loss": "verifier_repair_ce", "mode": "verifier_repair_probe"},
}

REQUIRED_ARTIFACTS = [
    "probe_contract_audit.json",
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "row_dynamics_history.jsonl",
    "field_exact_by_cell.json",
    "field_label_vocabs.json",
    "structured_confusion_matrix.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def enabled_loss(row: dict[str, Any]) -> str | None:
    mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
    enabled = [key for key, value in mask.items() if value]
    return enabled[0] if len(enabled) == 1 else None


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter(str(row.get("split") or "other") for row in rows)
    return {
        "train": counter.get("train", 0),
        "eval": counter.get("eval", 0),
        "strict_eval": counter.get("strict_eval", 0),
        "other": sum(count for split, count in counter.items() if split not in {"train", "eval", "strict_eval"}),
    }


def materialize_manifests() -> tuple[dict[str, Path], list[str]]:
    rows = read_jsonl(STRUCTURED)
    by_loss: dict[str, list[dict[str, Any]]] = {spec["loss"]: [] for spec in SURFACES.values()}
    failures: list[str] = []
    for row in rows:
        loss = enabled_loss(row)
        if loss in by_loss:
            by_loss[loss].append(row)
        else:
            failures.append(f"unexpected_or_missing_single_loss:{row.get('row_id')}:{loss}")
    manifests: dict[str, Path] = {}
    for surface, spec in SURFACES.items():
        path = MANIFEST_DIR / f"{surface}.jsonl"
        write_jsonl(path, by_loss[spec["loss"]])
        manifests[surface] = path
        if not by_loss[spec["loss"]]:
            failures.append(f"empty_surface_manifest:{surface}")
    return manifests, failures


def trainer_command(surface: str, manifest: Path, rows: list[dict[str, Any]]) -> list[str]:
    counts = split_counts(rows)
    return [
        sys.executable,
        str(TRAINER),
        "--repo-root", str(ROOT),
        "--manifest", str(manifest.relative_to(ROOT)),
        "--mode", str(SURFACES[surface]["mode"]),
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG.relative_to(ROOT)),
        "--tokenizer-json", str(TOKENIZER_JSON.relative_to(ROOT)),
        "--tokenizer-config", str(TOKENIZER_CONFIG.relative_to(ROOT)),
        "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK.relative_to(ROOT)),
        "--max-train-rows", str(counts["train"]),
        "--max-eval-rows", str(counts["eval"]),
        "--max-strict-rows", str(counts["strict_eval"]),
        "--max-steps", "0",
        "--batch-size", "2",
        "--learning-rate", "5e-5",
        "--max-encoder-tokens", "512",
        "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.0",
        "--structured-aux-weight", "1.0",
        "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save", "1",
        "--output-dir", str((RUNS_DIR / surface).relative_to(ROOT)),
        "--run-id", f"{NAME}_{surface}",
        "--contract-only",
    ]


def run_surface(surface: str, manifest: Path) -> dict[str, Any]:
    rows = read_jsonl(manifest)
    env = dict(os.environ)
    env.update({"TMPDIR": str(TMPDIR), "TEMP": str(TMPDIR), "TMP": str(TMPDIR)})
    run = subprocess.run(trainer_command(surface, manifest, rows), cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    out_dir = RUNS_DIR / surface
    contract = load_json(out_dir / "probe_contract_audit.json")
    missing = [name for name in REQUIRED_ARTIFACTS if not (out_dir / name).exists()]
    failures: list[str] = []
    if run.returncode != 0:
        failures.append("trainer_contract_failed")
    if contract.get("passed") is not True:
        failures.append("probe_contract_not_passed")
    if contract.get("probe_scale") != "target_100m":
        failures.append("probe_scale_not_target_100m")
    if contract.get("implementation") != "transformer":
        failures.append("implementation_not_transformer")
    if contract.get("model_execution_attempted") is not False:
        failures.append("model_execution_attempted")
    if contract.get("authority_rows") != 0:
        failures.append("authority_rows_present")
    if contract.get("unsafe_loss_rows") != 0:
        failures.append("unsafe_loss_rows_present")
    expected_loss = SURFACES[surface]["loss"]
    losses = contract.get("loss_counts") if isinstance(contract.get("loss_counts"), dict) else {}
    if losses.get(expected_loss) != len(rows):
        failures.append("expected_loss_count_mismatch")
    if [key for key, value in losses.items() if value and key != expected_loss]:
        failures.append("forbidden_losses_enabled")
    if missing:
        failures.append("missing_required_contract_artifacts")
    counts = split_counts(rows)
    if counts["other"] != 0:
        failures.append("manifest_has_other_rows")
    tokenizer = contract.get("tokenizer_contract") if isinstance(contract.get("tokenizer_contract"), dict) else {}
    guard = ((contract.get("implementation_contract") or {}).get("target_implementation_guard") or {}) if isinstance(contract.get("implementation_contract"), dict) else {}
    if tokenizer.get("byte_fallback_used_when_unset") is not False:
        failures.append("tokenizer_fell_back_to_byte")
    if tokenizer.get("target_100m_vocab_size") != 1506:
        failures.append("target_vocab_not_1506")
    if guard.get("allowed_for_recovered_100m_target") is not True:
        failures.append("target_implementation_guard_failed")
    return {
        "surface": surface,
        "passed": not failures,
        "failures": failures,
        "manifest": display(manifest),
        "rows": len(rows),
        "split_counts": counts,
        "expected_loss": expected_loss,
        "trainer_returncode": run.returncode,
        "contract_passed": contract.get("passed"),
        "loss_counts": losses,
        "model_execution_attempted": contract.get("model_execution_attempted"),
        "authority_rows": contract.get("authority_rows"),
        "unsafe_loss_rows": contract.get("unsafe_loss_rows"),
        "missing_required_contract_artifacts": missing,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9962_not_passed")
    manifests, manifest_failures = materialize_manifests()
    failures.extend(manifest_failures)
    surface_results: list[dict[str, Any]] = []
    if not failures:
        for surface, manifest in manifests.items():
            result = run_surface(surface, manifest)
            surface_results.append(result)
            if not result["passed"]:
                failures.append(f"surface_contract_failed:{surface}")
    aggregate_loss_counts = Counter()
    for result in surface_results:
        for key, value in (result.get("loss_counts") or {}).items():
            aggregate_loss_counts[key] += int(value or 0)
    audit = {
        "passed": not failures,
        "failures": failures,
        "surface_results": surface_results,
        "total_rows": sum(int(result.get("rows") or 0) for result in surface_results),
        "aggregate_loss_counts": dict(sorted((key, value) for key, value in aggregate_loss_counts.items() if value)),
        "model_execution_attempted_rows": sum(int(result.get("model_execution_attempted") is not False) for result in surface_results),
        "authority_rows": sum(int(result.get("authority_rows") or 0) for result in surface_results),
        "unsafe_loss_rows": sum(int(result.get("unsafe_loss_rows") or 0) for result in surface_results),
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use these preflighted manifests as the next capped blended target-100M structured run contract; the edit-localization leg now carries the web recovery rows plus the stage9961 weak-language recovery roots inside the same contract-only-validated trainer path."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit, "training_execution_authorized_next": False, "model_execution_authorized_next": False},
        "artifacts": {"audit": display(AUDIT), "manifest_dir": display(MANIFEST_DIR), "run_dir": display(RUNS_DIR), "doc": display(DOC)},
        "decision": "Ran target-100M contract-only trainer preflights for the stage9962 weak-language successor mix; this preserves the same no-execution boundary while validating the next run contract after adding the real python, c_cpp, and web recovery roots.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9963 Blended Weak-Language Target100M Contract Preflight",
        "",
        f"Passed: `{summary['passed']}`",
        f"Total rows: `{audit['total_rows']}`",
        f"Aggregate loss counts: `{audit['aggregate_loss_counts']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "total_rows": audit["total_rows"], "loss_counts": audit["aggregate_loss_counts"]}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
