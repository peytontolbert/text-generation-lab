#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9579
NAME = "stage9579_residual_denoise_boundary_prefix_primed_capped_probe"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9578_residual_denoise_boundary_prefix_primed_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9578_residual_denoise_boundary_prefix_primed_manifest/residual_denoise_boundary_prefix_primed_manifest.jsonl"
RUN_ROOT = ROOT / "runs/local/artifacts" / NAME
CONTRACT_DIR = RUN_ROOT / "contract_preflight"
RUN_DIR = RUN_ROOT / "denoise_repair_probe"
AUDIT = RUN_ROOT / "residual_denoise_boundary_prefix_primed_capped_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_BOUNDARY_PREFIX_PRIMED_CAPPED_PROBE_STAGE9579.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
GENERATION_PREFIX_FIELD = "model_input.repair_decision_prefix"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def bucket(text: str) -> str:
    value = str(text)
    if value.startswith("REPAIR_SCOPE=BOUNDARY"):
        return "BOUNDARY"
    if value.startswith("REPAIR_SCOPE=PREFIX"):
        return "PREFIX"
    return "OTHER"


def command(*, output_dir: Path, run_id: str, contract_only: bool) -> list[str]:
    cmd = [
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
        "denoise_repair_probe",
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
        "--max-train-rows",
        "30",
        "--max-eval-rows",
        "8",
        "--max-strict-rows",
        "10",
        "--max-steps",
        "80",
        "--batch-size",
        "2",
        "--learning-rate",
        "5e-5",
        "--max-encoder-tokens",
        "512",
        "--max-decoder-tokens",
        "96",
        "--decoder-ce-weight",
        "0.0",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "1.0",
        "--eos-loss-weight",
        "1.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        "16",
        "--max-generation-tokens",
        "48",
        "--generation-audit-splits",
        "train,eval,strict_eval",
        "--generation-prefix-field",
        GENERATION_PREFIX_FIELD,
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(output_dir),
        "--run-id",
        run_id,
    ]
    cmd.append("--contract-only" if contract_only else "--execution-authorized-for-recovery-probe")
    return cmd


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9578_not_passed")
    if (source.get("metrics") or {}).get("generation_prefix_field") != GENERATION_PREFIX_FIELD:
        failures.append("stage9578_generation_prefix_field_mismatch")
    if len(rows) != 48:
        failures.append("manifest_row_count_not_48")
    if any(any((row.get("authority") or {}).values()) for row in rows):
        failures.append("authority_rows_present")
    if any((row.get("loss_mask") or {}).get("denoise_ce") is not True for row in rows):
        failures.append("missing_denoise_ce_rows")

    if not failures:
        contract = subprocess.run(command(output_dir=CONTRACT_DIR, run_id="stage9579_contract_preflight", contract_only=True), cwd=ROOT, text=True, capture_output=True, check=False)
        if contract.returncode != 0:
            failures.append("contract_preflight_failed")
    else:
        contract = None
    contract_card = load_json(CONTRACT_DIR / "probe_contract_audit.json")
    if contract_card and contract_card.get("passed") is not True:
        failures.append("contract_card_not_passed")

    if not failures:
        run = subprocess.run(command(output_dir=RUN_DIR, run_id="stage9579_boundary_prefix_primed_probe", contract_only=False), cwd=ROOT, text=True, capture_output=True, check=False)
        if run.returncode != 0:
            failures.append("execution_failed")
    else:
        run = None

    execution = load_json(RUN_DIR / "execution_result.json")
    quality = load_json(RUN_DIR / "denoise_repair_quality_audit.json")
    samples = (load_json(RUN_DIR / "sample_generation_audit.json").get("samples") or [])
    target_counts: Counter[str] = Counter()
    pred_counts: Counter[str] = Counter()
    confusion: dict[str, Counter[str]] = {}
    exact_rows = 0
    boundary_next_token_matches = 0
    boundary_next_token_available = 0
    for row in samples:
        target = bucket(str(row.get("target_text") or ""))
        pred = bucket(str(row.get("generated_text") or ""))
        target_counts[target] += 1
        pred_counts[pred] += 1
        confusion.setdefault(target, Counter())[pred] += 1
        exact_rows += int(bool(row.get("exact_match")))
        boundary_next = row.get("boundary_next_token") if isinstance(row.get("boundary_next_token"), dict) else {}
        if boundary_next.get("available"):
            boundary_next_token_available += 1
            boundary_next_token_matches += int(bool(boundary_next.get("match")))
    boundary_target = target_counts.get("BOUNDARY", 0)
    boundary_recall = confusion.get("BOUNDARY", Counter()).get("BOUNDARY", 0) / boundary_target if boundary_target else None
    prefix_target = target_counts.get("PREFIX", 0)
    prefix_recall = confusion.get("PREFIX", Counter()).get("PREFIX", 0) / prefix_target if prefix_target else None
    exact_rate = exact_rows / len(samples) if samples else 0.0
    next_token_match_rate = boundary_next_token_matches / boundary_next_token_available if boundary_next_token_available else None
    sample_balanced = target_counts.get("BOUNDARY") == target_counts.get("PREFIX") == 8
    class_gate_passed = (
        sample_balanced
        and boundary_recall is not None
        and boundary_recall >= 0.85
        and prefix_recall is not None
        and prefix_recall >= 0.85
        and next_token_match_rate is not None
        and next_token_match_rate >= 0.85
    )
    if run is not None and not execution:
        failures.append("missing_execution_result")
    if execution and execution.get("denoise_ce_rows") != 48:
        failures.append("denoise_ce_rows_not_48")
    if execution and execution.get("decoder_ce_rows") != 0:
        failures.append("decoder_ce_rows_present")
    if execution and execution.get("runtime_executed") is not False:
        failures.append("runtime_executed")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "run_dir": str(RUN_DIR.relative_to(ROOT)),
        "contract_returncode": None if contract is None else contract.returncode,
        "execution_returncode": None if run is None else run.returncode,
        "train_rows": execution.get("train_rows"),
        "eval_rows": execution.get("eval_rows"),
        "strict_rows": execution.get("strict_rows"),
        "max_steps": execution.get("max_steps"),
        "generated_rows": execution.get("generated_rows"),
        "contentful_generation_rate": execution.get("contentful_generation_rate"),
        "target_prefix_match_rate": execution.get("target_prefix_match_rate"),
        "short_or_junk_rate": execution.get("short_or_junk_rate"),
        "degenerate_repetition_rate": execution.get("degenerate_repetition_rate"),
        "exact_rows": exact_rows,
        "exact_rate": exact_rate,
        "sample_balanced": sample_balanced,
        "target_counts": dict(sorted(target_counts.items())),
        "pred_counts": dict(sorted(pred_counts.items())),
        "confusion": {key: dict(sorted(value.items())) for key, value in sorted(confusion.items())},
        "boundary_recall": boundary_recall,
        "prefix_recall": prefix_recall,
        "boundary_next_token_available": boundary_next_token_available,
        "boundary_next_token_matches": boundary_next_token_matches,
        "boundary_next_token_match_rate": next_token_match_rate,
        "generation_prefix_field": GENERATION_PREFIX_FIELD,
        "class_gate_passed": class_gate_passed,
        "widening_authorized": False,
        "quality": quality,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Ran a capped target_100M denoise probe with the shared REPAIR_SCOPE= prefix primed so the first generated token measures boundary-vs-prefix discrimination.",
        "next_best_step": "If the class gate passed, integrate prefix-primed boundary repair into the residual-denoise curriculum; otherwise inspect boundary-next-token ranks and add harder contrastive rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9579 Residual Denoise Boundary Prefix-Primed Capped Probe",
                "",
                f"Passed: `{audit['passed']}`",
                f"Sample balanced: `{sample_balanced}`",
                f"Boundary recall: `{boundary_recall}`",
                f"Prefix recall: `{prefix_recall}`",
                f"Boundary next-token match rate: `{next_token_match_rate}`",
                f"Class gate passed: `{class_gate_passed}`",
                "",
                "The probe remains denoise-only and authority-closed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "sample_balanced": sample_balanced, "boundary_recall": boundary_recall, "prefix_recall": prefix_recall, "boundary_next_token_match_rate": next_token_match_rate, "class_gate_passed": class_gate_passed, "failures": failures}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
