#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9709
NAME = "stage9709_symbol_binding_visible_evidence_target100m_contract_preflight_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9708_symbol_binding_visible_evidence_manifest.json"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage9708_symbol_binding_visible_evidence_manifest/symbol_binding_visible_evidence_audit.json"
CONTRACT_DIR = ROOT / "runs/local/artifacts/stage9709_symbol_binding_visible_evidence_target100m_contract_preflight/contract_only"
CONTRACT_CARD = CONTRACT_DIR / "probe_contract_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "symbol_binding_visible_evidence_target100m_contract_preflight_audit.json"
CANDIDATE = OUT_DIR / "stage9710_symbol_binding_visible_evidence_target100m_execution_candidate.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYMBOL_BINDING_VISIBLE_EVIDENCE_TARGET100M_CONTRACT_PREFLIGHT_STAGE9709.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def contract_only_command() -> list[str]:
    return [
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        "legacy_src/scripts/train_agentkernel_lite_encdec.py",
        "--repo-root",
        str(ROOT),
        "--manifest",
        "runs/local/artifacts/stage9708_symbol_binding_visible_evidence_manifest/symbol_binding_visible_evidence.jsonl",
        "--mode",
        "symbol_binding_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        "configs/model/agentkernel_100m_seq2seq_recovered_target.json",
        "--tokenizer-json",
        "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
        "--tokenizer-config",
        "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
        "--tokenizer-hashlock",
        "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json",
        "--max-train-rows",
        "48",
        "--max-eval-rows",
        "22",
        "--max-strict-rows",
        "22",
        "--max-steps",
        "8",
        "--batch-size",
        "2",
        "--learning-rate",
        "5e-5",
        "--max-encoder-tokens",
        "512",
        "--max-decoder-tokens",
        "8",
        "--decoder-ce-weight",
        "0.0",
        "--structured-aux-weight",
        "1.0",
        "--denoise-weight",
        "0.0",
        "--require-loss-mask-enforcement-audit",
        "--require-native-feature-ablation-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        "runs/local/artifacts/stage9709_symbol_binding_visible_evidence_target100m_contract_preflight/contract_only",
        "--run-id",
        "stage9709_symbol_binding_visible_evidence_target100m_contract_preflight",
        "--contract-only",
    ]


def execution_candidate_command() -> list[str]:
    command = [part for part in contract_only_command() if part != "--contract-only"]
    command[-3] = "runs/local/artifacts/stage9710_symbol_binding_visible_evidence_target100m_execution/symbol_binding_probe"
    command[-1] = "stage9710_symbol_binding_visible_evidence_target100m_execution"
    command.append("--execution-authorized-for-recovery-probe")
    return command


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
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    source_audit = load_json(SOURCE_AUDIT)
    card = load_json(CONTRACT_CARD)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9708_not_passed")
    if source_audit.get("query_kind_action_baseline_exact", 1.0) >= source_audit.get("query_kind_action_baseline_ceiling", 0.60):
        failures.append("stage9708_query_kind_baseline_over_ceiling")
    if source_audit.get("strongest_single_feature_baseline_exact", 1.0) >= source_audit.get("single_feature_baseline_ceiling", 0.80):
        failures.append("stage9708_single_feature_baseline_over_ceiling")
    if card.get("passed") is not True:
        failures.append("contract_card_not_passed")
    if card.get("probe_scale") != "target_100m":
        failures.append("probe_scale_not_target_100m")
    if card.get("mode") != "symbol_binding_probe":
        failures.append("mode_not_symbol_binding_probe")
    if card.get("native_feature_ablation_audit_required") is not True:
        failures.append("native_feature_ablation_not_required")
    if card.get("model_execution_attempted") is not False:
        failures.append("contract_only_attempted_model_execution")
    if card.get("loss_counts", {}).get("symbol_binding_ce") != 92:
        failures.append(f"symbol_binding_loss_count_not_92:{card.get('loss_counts')}")
    forbidden_losses = {key: value for key, value in (card.get("loss_counts") or {}).items() if key != "symbol_binding_ce" and value}
    if forbidden_losses:
        failures.append(f"forbidden_losses_nonzero:{forbidden_losses}")
    if card.get("split_counts") != {"train": 48, "eval": 22, "strict_eval": 22, "other": 0}:
        failures.append(f"unexpected_split_counts:{card.get('split_counts')}")
    tokenizer = card.get("tokenizer_contract") or {}
    if tokenizer.get("byte_fallback_used_when_unset") is not False:
        failures.append("target100m_tokenizer_fallback_used")
    candidate = {
        "future_stage": 9710,
        "future_run_id": "stage9710_symbol_binding_visible_evidence_target100m_execution",
        "command": execution_candidate_command(),
        "requires_stage9709_passed": True,
        "requires_explicit_operator_intent": True,
        "expected_boundary": {
            "decoder_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "gemma_execution_authorized_next": False,
            "harness_execution_authorized_next": False,
            "final_checkpoint_export": False,
            "native_feature_ablation_required": True,
        },
    }
    CANDIDATE.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Run Stage9710 target-100M visible-evidence symbol-binding execution only if explicitly continuing execution; "
        "audit whether import/test/retrieve exactness improves before any decoder work."
    )
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": False,
        "promotion_ready": False,
        "execution_authorized_next": False,
        "failures": failures,
        "source_stage9708_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_stage9708_audit": str(SOURCE_AUDIT.relative_to(ROOT)),
        "contract_dir": str(CONTRACT_DIR.relative_to(ROOT)),
        "contract_card": str(CONTRACT_CARD.relative_to(ROOT)),
        "candidate_command": str(CANDIDATE.relative_to(ROOT)),
        "metrics": {
            "probe_scale": card.get("probe_scale"),
            "native_feature_ablation_audit_required": card.get("native_feature_ablation_audit_required"),
            "symbol_binding_loss_count": card.get("loss_counts", {}).get("symbol_binding_ce"),
            "split_counts": card.get("split_counts"),
            "model_execution_attempted": card.get("model_execution_attempted"),
            "stage9708_query_kind_action_baseline_exact": source_audit.get("query_kind_action_baseline_exact"),
            "stage9708_strongest_single_feature_baseline_exact": source_audit.get("strongest_single_feature_baseline_exact"),
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": False,
        "promotion_ready": False,
        "execution_authorized_next": False,
        "created_at_unix": int(time.time()),
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "contract_dir": str(CONTRACT_DIR.relative_to(ROOT)),
            "candidate_command": str(CANDIDATE.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "metrics": audit["metrics"],
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9709 Symbol-Binding Visible-Evidence Target-100M Contract Preflight",
                "",
                "Stage9709 validates the target-100M trainer command for the Stage9708 visible-evidence symbol-binding manifest without model execution.",
                "",
                "## Result",
                "",
                f"- Passed: `{not failures}`",
                f"- Probe scale: `{card.get('probe_scale')}`",
                f"- Native ablation required: `{card.get('native_feature_ablation_audit_required')}`",
                f"- Model execution attempted: `{card.get('model_execution_attempted')}`",
                f"- Split counts: `{card.get('split_counts')}`",
                f"- Stage9708 query-kind baseline: `{source_audit.get('query_kind_action_baseline_exact')}`",
                f"- Stage9708 strongest single-feature baseline: `{source_audit.get('strongest_single_feature_baseline_exact')}`",
                "",
                "## Next",
                "",
                next_step,
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
