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
STAGE = 9860
NAME = "stage9860_capped_validity_weighted_structured_target_100m_contract_preflight"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9859_validity_weighted_structured_tiny_execution_review.json"
MANIFEST_DIR = ROOT / "runs/local/artifacts/stage9859_validity_weighted_structured_tiny_execution_review/tiny_structured_manifests"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
RUNS_DIR = OUT_DIR / "contract_runs"
AUDIT = OUT_DIR / "capped_multisurface_structured_target_100m_contract_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CAPPED_VALIDITY_WEIGHTED_STRUCTURED_TARGET_100M_CONTRACT_PREFLIGHT_STAGE9860.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
PREFERRED_PYTHON = Path("/home/peyton/miniconda3/envs/ai/bin/python")
CAPS = {"train": 32, "eval": 16, "strict_eval": 16}

SURFACES = {
    "symbol_binding": {"manifest": "symbol_binding_tiny.jsonl", "mode": "symbol_binding_probe", "loss": "symbol_binding_ce"},
    "edit_localization": {"manifest": "edit_localization_tiny.jsonl", "mode": "edit_localization_probe", "loss": "edit_localization_ce"},
    "patch_operator_selection": {"manifest": "patch_operator_selection_tiny.jsonl", "mode": "patch_operator_probe", "loss": "patch_operator_ce"},
    "verifier_failure_repair_or_abstain": {"manifest": "verifier_failure_repair_or_abstain_tiny.jsonl", "mode": "verifier_repair_probe", "loss": "verifier_repair_ce"},
}

REQUIRED_PREFLIGHT_ARTIFACTS = [
    "probe_contract_audit.json",
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("split") or "other") for row in rows)
    known = {"train", "eval", "strict_eval"}
    other = sum(count for split, count in counts.items() if split not in known)
    return {"train": counts.get("train", 0), "eval": counts.get("eval", 0), "strict_eval": counts.get("strict_eval", 0), "other": other}


def trainer_python() -> str:
    return str(PREFERRED_PYTHON if PREFERRED_PYTHON.exists() else Path(sys.executable))


def command(surface: str, manifest: Path) -> list[str]:
    spec = SURFACES[surface]
    return [
        trainer_python(),
        str(TRAINER),
        "--repo-root", str(ROOT),
        "--manifest", str(manifest.relative_to(ROOT)),
        "--mode", str(spec["mode"]),
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG.relative_to(ROOT)),
        "--tokenizer-json", str(TOKENIZER_JSON.relative_to(ROOT)),
        "--tokenizer-config", str(TOKENIZER_CONFIG.relative_to(ROOT)),
        "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK.relative_to(ROOT)),
        "--max-train-rows", str(CAPS["train"]),
        "--max-eval-rows", str(CAPS["eval"]),
        "--max-strict-rows", str(CAPS["strict_eval"]),
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


def run_surface(surface: str) -> dict[str, Any]:
    manifest = MANIFEST_DIR / str(SURFACES[surface]["manifest"])
    rows = read_jsonl(manifest)
    env = dict(os.environ)
    env.update({"TMPDIR": str(TMPDIR), "TEMP": str(TMPDIR), "TMP": str(TMPDIR)})
    run = subprocess.run(command(surface, manifest), cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    out_dir = RUNS_DIR / surface
    contract = load_json(out_dir / "probe_contract_audit.json")
    missing = [name for name in REQUIRED_PREFLIGHT_ARTIFACTS if not (out_dir / name).exists()]
    failures: list[str] = []
    if run.returncode != 0:
        failures.append("trainer_contract_failed")
    counts = split_counts(rows)
    if counts.get("other") != 0:
        failures.append("manifest_has_other_rows")
    if sum(int(value or 0) for key, value in counts.items() if key != "other") != len(rows):
        failures.append("manifest_row_total_mismatch")
    for split, cap in CAPS.items():
        if int(counts.get(split, 0) or 0) > cap:
            failures.append(f"manifest_split_cap_exceeded:{split}")
    if contract.get("passed") is not True:
        failures.append("probe_contract_not_passed")
    if contract.get("probe_scale") != "target_100m" or contract.get("implementation") != "transformer":
        failures.append("target100m_transformer_contract_mismatch")
    if contract.get("model_execution_attempted") is not False:
        failures.append("model_execution_attempted")
    if contract.get("authority_rows") != 0 or contract.get("unsafe_loss_rows") != 0:
        failures.append("authority_or_unsafe_loss_rows_present")
    expected_loss = str(SURFACES[surface]["loss"])
    losses = contract.get("loss_counts") if isinstance(contract.get("loss_counts"), dict) else {}
    if losses.get(expected_loss) != len(rows):
        failures.append("expected_loss_count_mismatch")
    if [key for key, value in losses.items() if value and key != expected_loss]:
        failures.append("forbidden_loss_enabled")
    tokenizer = contract.get("tokenizer_contract") if isinstance(contract.get("tokenizer_contract"), dict) else {}
    impl = contract.get("implementation_contract") if isinstance(contract.get("implementation_contract"), dict) else {}
    guard = impl.get("target_implementation_guard") if isinstance(impl.get("target_implementation_guard"), dict) else {}
    if tokenizer.get("byte_fallback_used_when_unset") is not False or tokenizer.get("target_100m_vocab_size") != 1506:
        failures.append("tokenizer_contract_bad")
    if guard.get("allowed_for_recovered_100m_target") is not True:
        failures.append("implementation_guard_failed")
    if missing:
        failures.append("missing_required_artifacts")
    return {
        "surface": surface,
        "passed": not failures,
        "failures": failures,
        "manifest": str(manifest.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": split_counts(rows),
        "mode": SURFACES[surface]["mode"],
        "expected_loss": expected_loss,
        "trainer_returncode": run.returncode,
        "trainer_stdout_tail": run.stdout[-3000:],
        "trainer_stderr_tail": run.stderr[-3000:],
        "contract_passed": contract.get("passed"),
        "loss_counts": losses,
        "authority_rows": contract.get("authority_rows"),
        "unsafe_loss_rows": contract.get("unsafe_loss_rows"),
        "model_execution_attempted": contract.get("model_execution_attempted"),
        "probe_scale": contract.get("probe_scale"),
        "implementation": contract.get("implementation"),
        "missing_required_preflight_artifacts": missing,
        "tokenizer_contract": tokenizer,
        "target_implementation_guard": guard,
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9859_not_passed")
    surface_results = []
    if not failures:
        for surface in SURFACES:
            result = run_surface(surface)
            surface_results.append(result)
            if not result["passed"]:
                failures.append(f"surface_contract_failed:{surface}")
    loss_counts = Counter()
    for result in surface_results:
        for key, value in (result.get("loss_counts") or {}).items():
            loss_counts[key] += int(value or 0)
    audit = {
        "passed": not failures,
        "failures": failures,
        "surface_results": surface_results,
        "total_rows": sum(int(result.get("rows") or 0) for result in surface_results),
        "aggregate_loss_counts": dict(sorted((key, value) for key, value in loss_counts.items() if value)),
        "model_execution_attempted_rows": sum(int(result.get("model_execution_attempted") is not False) for result in surface_results),
        "authority_rows": sum(int(result.get("authority_rows") or 0) for result in surface_results),
        "unsafe_loss_rows": sum(int(result.get("unsafe_loss_rows") or 0) for result in surface_results),
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If disk/safe-cleanup preflight is clean and execution is explicitly confirmed, run one tiny target-100M structured probe surface first on the validity-weighted package; otherwise build the next execution-readiness gate before any probe."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit, "training_execution_authorized_next": False, "model_execution_authorized_next": False},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "run_dir": str(RUNS_DIR.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Validated capped Stage9859 tiny structured manifests under target-100M contract-only preflight for the validity-weighted package. This does not execute model training.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9860 Capped Validity-Weighted Structured Target-100M Contract Preflight",
        "",
        f"Passed: `{summary['passed']}`",
        f"Total rows: `{audit['total_rows']}`",
        f"Aggregate loss counts: `{audit['aggregate_loss_counts']}`",
        f"Failures: `{failures}`",
        "",
        "This is contract-only and validates the capped tiny structured manifests from Stage9695. It does not run model execution or training.",
        "",
        "No runtime, source/body emission, Gemma, harness, scoring, model execution, decoder CE, denoise CE, checkpoint export, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "total_rows": audit["total_rows"], "loss_counts": audit["aggregate_loss_counts"], "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
