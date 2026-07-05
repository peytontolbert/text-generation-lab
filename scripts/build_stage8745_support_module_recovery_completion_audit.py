#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8745
NAME = "stage8745_support_module_recovery_completion_audit"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUPPORT_MODULE_RECOVERY_COMPLETION_AUDIT_STAGE8745.md"
BACKUP_ROOT = Path("/arxiv/agentkernel_recovery/stage8745_support_module_recovery_completion_audit")
REGISTRY = ROOT / "runs" / "local" / "artifacts" / "reconstructed_stage_registry.json"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "training_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_body_authorized": False,
    "gemma_authorized": False,
    "promotion_ready": False,
}

MODULES: list[dict[str, Any]] = [
    {
        "module_id": "cross_encoder_reranker_calibration",
        "script": "scripts/cross_encoder_reranker_calibration.py",
        "test": "tests/test_cross_encoder_reranker_calibration.py",
        "readiness_summary": "runs/summaries/stage8721_cross_encoder_reranker_calibration_readiness.json",
        "graph_summary": "runs/summaries/stage8722_cross_encoder_reranker_calibration_graph_attachment.json",
        "graph": "runs/local/artifacts/stage8722_cross_encoder_reranker_calibration_graph_attachment/central_research_graph_with_cross_encoder_reranker_calibration.json",
    },
    {
        "module_id": "dataset_cartography_active_learning",
        "script": "scripts/dataset_cartography_active_learning.py",
        "test": "tests/test_dataset_cartography_active_learning.py",
        "readiness_summary": "runs/summaries/stage8723_dataset_cartography_active_learning_readiness.json",
        "graph_summary": "runs/summaries/stage8724_dataset_cartography_active_learning_graph_attachment.json",
        "graph": "runs/local/artifacts/stage8724_dataset_cartography_active_learning_graph_attachment/central_research_graph_with_dataset_cartography_active_learning.json",
    },
    {
        "module_id": "training_data_attribution_influence",
        "script": "scripts/training_data_attribution_influence.py",
        "test": "tests/test_training_data_attribution_influence.py",
        "readiness_summary": "runs/summaries/stage8725_training_data_attribution_influence_readiness.json",
        "graph_summary": "runs/summaries/stage8726_training_data_attribution_influence_graph_attachment.json",
        "graph": "runs/local/artifacts/stage8726_training_data_attribution_influence_graph_attachment/central_research_graph_with_training_data_attribution_influence.json",
    },
    {
        "module_id": "fusion_logits_forward_pass_contract",
        "script": "scripts/fusion_logits_forward_pass_contract.py",
        "test": "tests/test_fusion_logits_forward_pass_contract.py",
        "readiness_summary": "runs/summaries/stage8727_fusion_logits_forward_pass_contract_readiness.json",
        "graph_summary": "runs/summaries/stage8728_fusion_logits_forward_pass_contract_graph_attachment.json",
        "graph": "runs/local/artifacts/stage8728_fusion_logits_forward_pass_contract_graph_attachment/central_research_graph_with_fusion_logits_forward_pass_contract.json",
    },
    {
        "module_id": "moe_lora_adapter_router_contract",
        "script": "scripts/moe_lora_adapter_router_contract.py",
        "test": "tests/test_moe_lora_adapter_router_contract.py",
        "readiness_summary": "runs/summaries/stage8729_moe_lora_adapter_router_contract_readiness.json",
        "graph_summary": "runs/summaries/stage8730_moe_lora_adapter_router_contract_graph_attachment.json",
        "graph": "runs/local/artifacts/stage8730_moe_lora_adapter_router_contract_graph_attachment/central_research_graph_with_moe_lora_adapter_router_contract.json",
    },
    {
        "module_id": "denoise_diffusion_repair_contract",
        "script": "scripts/denoise_diffusion_repair_contract.py",
        "test": "tests/test_denoise_diffusion_repair_contract.py",
        "readiness_summary": "runs/summaries/stage8731_denoise_diffusion_repair_contract_readiness.json",
        "graph_summary": "runs/summaries/stage8732_denoise_diffusion_repair_contract_graph_attachment.json",
        "graph": "runs/local/artifacts/stage8732_denoise_diffusion_repair_contract_graph_attachment/central_research_graph_with_denoise_diffusion_repair_contract.json",
    },
    {
        "module_id": "adversarial_hard_negative_generator",
        "script": "scripts/adversarial_hard_negative_generator.py",
        "test": "tests/test_adversarial_hard_negative_generator.py",
        "readiness_summary": "runs/summaries/stage8733_adversarial_hard_negative_generator_readiness.json",
        "graph_summary": "runs/summaries/stage8734_adversarial_hard_negative_generator_graph_attachment.json",
        "graph": "runs/local/artifacts/stage8734_adversarial_hard_negative_generator_graph_attachment/central_research_graph_with_adversarial_hard_negative_generator.json",
    },
    {
        "module_id": "confidence_ood_head_contract",
        "script": "scripts/confidence_ood_head_contract.py",
        "test": "tests/test_confidence_ood_head_contract.py",
        "readiness_summary": "runs/summaries/stage8735_confidence_ood_head_contract_readiness.json",
        "graph_summary": "runs/summaries/stage8736_confidence_ood_head_contract_graph_attachment.json",
        "graph": "runs/local/artifacts/stage8736_confidence_ood_head_contract_graph_attachment/central_research_graph_with_confidence_ood_head_contract.json",
    },
    {
        "module_id": "structured_data_operation_curriculum",
        "script": "scripts/structured_data_operation_curriculum.py",
        "test": "tests/test_structured_data_operation_curriculum.py",
        "readiness_summary": "runs/summaries/stage8737_structured_data_operation_curriculum_readiness.json",
        "graph_summary": "runs/summaries/stage8738_structured_data_operation_curriculum_graph_attachment.json",
        "graph": "runs/local/artifacts/stage8738_structured_data_operation_curriculum_graph_attachment/central_research_graph_with_structured_data_operation_curriculum.json",
    },
    {
        "module_id": "semantic_equivalence_metamorphic_verifier",
        "script": "scripts/semantic_equivalence_metamorphic_verifier.py",
        "test": "tests/test_semantic_equivalence_metamorphic_verifier.py",
        "readiness_summary": "runs/summaries/stage8739_semantic_equivalence_metamorphic_verifier_readiness.json",
        "graph_summary": "runs/summaries/stage8740_semantic_equivalence_metamorphic_verifier_graph_attachment.json",
        "graph": "runs/local/artifacts/stage8740_semantic_equivalence_metamorphic_verifier_graph_attachment/central_research_graph_with_semantic_equivalence_metamorphic_verifier.json",
    },
]


def exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def load_json(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def summary_authority_closed(summary: dict[str, Any]) -> bool:
    authority = summary.get("authority")
    metrics = summary.get("metrics")
    checks: list[dict[str, Any]] = []
    if isinstance(authority, dict):
        checks.append(authority)
    if isinstance(metrics, dict):
        checks.append(metrics)
    forbidden_true_keys = {
        "model_execution_authorized_next",
        "training_authorized_next",
        "decoder_ce_training_authorized_next",
        "denoise_ce_training_authorized_next",
        "runtime_authorized",
        "source_body_authorized",
        "source_emission_authorized",
        "body_emission_authorized",
        "gemma_authorized",
        "gemma_execution_authorized_next",
        "harness_execution_authorized_next",
        "scoring_authorized_next",
        "promotion_ready",
    }
    for card in checks:
        for key in forbidden_true_keys:
            if card.get(key) is True:
                return False
    return True


def module_card(module: dict[str, Any]) -> dict[str, Any]:
    readiness = load_json(module["readiness_summary"])
    graph = load_json(module["graph_summary"])
    files = [module["script"], module["test"], module["readiness_summary"], module["graph_summary"], module["graph"]]
    missing = [rel for rel in files if not exists(rel)]
    failures: list[str] = []
    if missing:
        failures.append("missing_required_files")
    if readiness and readiness.get("passed") is not True:
        failures.append("readiness_not_passed")
    if graph and graph.get("passed") is not True:
        failures.append("graph_not_passed")
    if readiness and not summary_authority_closed(readiness):
        failures.append("readiness_authority_open")
    if graph and not summary_authority_closed(graph):
        failures.append("graph_authority_open")
    return {
        "module_id": module["module_id"],
        "passed": not failures,
        "failures": failures,
        "missing": missing,
        "files": files,
        "readiness_stage": readiness.get("stage"),
        "graph_stage": graph.get("stage"),
    }


def copy_artifacts(cards: list[dict[str, Any]]) -> dict[str, Any]:
    copied: list[str] = []
    missing: list[str] = []
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    for card in cards:
        for rel in card["files"]:
            src = ROOT / rel
            if not src.exists():
                missing.append(rel)
                continue
            dst = BACKUP_ROOT / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(rel)
    spine = ROOT / "docs/MODEL_STACK_SPINE.md"
    if spine.exists():
        dst = BACKUP_ROOT / "docs/MODEL_STACK_SPINE.md"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(spine, dst)
        copied.append("docs/MODEL_STACK_SPINE.md")
    return {"backup_root": str(BACKUP_ROOT), "copied": len(set(copied)), "missing": sorted(set(missing))}


def write_registry(summary: dict[str, Any]) -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {"passed": True, "rows": []}
    rows = list(registry.get("rows", []))
    rows = [row for row in rows if int(row.get("stage", -1)) != STAGE]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": AUTHORITY_CLOSED,
        "next_best_step": summary["next_best_step"],
    })
    rows = sorted(rows, key=lambda row: int(row.get("stage", -1)))
    registry["passed"] = all(row.get("passed") is True for row in rows)
    registry["rows"] = rows
    registry["metrics"] = {
        **registry.get("metrics", {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    cards = [module_card(module) for module in MODULES]
    backup = copy_artifacts(cards)
    failed = [card for card in cards if not card["passed"]]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failed and not backup["missing"],
        "authority": AUTHORITY_CLOSED,
        "artifacts": {
            "module_cards": str((OUT_DIR / "support_module_recovery_completion_cards.json").relative_to(ROOT)),
            "backup_root": backup["backup_root"],
        },
        "metrics": {
            **AUTHORITY_CLOSED,
            "modules_expected": len(MODULES),
            "modules_passed": len(MODULES) - len(failed),
            "modules_failed": len(failed),
            "backup_files_copied": backup["copied"],
            "backup_missing_files": len(backup["missing"]),
        },
        "module_cards": cards,
        "backup": backup,
        "decision": "Stage8720 forgotten-module queue is complete at contract/scaffold level." if not failed and not backup["missing"] else "Support-module recovery completion audit found gaps; fix before mining/training decisions.",
        "next_best_step": "Run a no-training support-stack integration audit over source lineage, provenance filters, queue modules, and curriculum compiler.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "support_module_recovery_completion_cards.json").write_text(json.dumps(cards, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_registry(summary)
    DOC.write_text(
        "\n".join([
            "# Stage8745 Support Module Recovery Completion Audit",
            "",
            f"Passed: `{summary['passed']}`",
            "",
            f"Modules passed: `{summary['metrics']['modules_passed']}/{summary['metrics']['modules_expected']}`",
            f"Backup root: `{backup['backup_root']}`",
            "",
            "This audit verifies the Stage8720 forgotten-module queue at contract/scaffold level. It does not authorize mining, training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, or promotion.",
            "",
        ]),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
