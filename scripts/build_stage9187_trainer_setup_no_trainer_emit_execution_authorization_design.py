#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9187
NAME = "stage9187_trainer_setup_no_trainer_emit_execution_authorization_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9186 = ROOT / "runs/summaries/stage9186_trainer_setup_emit_local_materializer_execution_review_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_SETUP_NO_TRAINER_EMIT_EXECUTION_AUTHORIZATION_DESIGN_STAGE9187.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "trainer_setup_no_trainer_emit_execution_authorization_design.json"

REQUIRED_AUTH_FIELDS = [
    "source_stage9186_audit_ref",
    "emit_execution_review_ref",
    "materializer_entrypoint_ref",
    "materializer_exact_argv_ref",
    "repo_local_output_dir_ref",
    "expected_output_set",
    "expected_output_count",
    "post_emit_output_hash_manifest_ref",
    "post_emit_cardinality_audit_ref",
    "post_emit_provenance_join_audit_ref",
    "cleanup_proof_ref",
    "no_trainer_execution_contract_ref",
]

REQUIRED_AUTH_GUARDS = [
    "authorization_requires_stage9186_passed",
    "authorization_requires_exact_materializer_entrypoint",
    "authorization_requires_exact_materializer_argv",
    "authorization_requires_repo_local_output_dir",
    "authorization_requires_expected_output_set_lock",
    "authorization_requires_expected_output_count_lock",
    "authorization_requires_output_hash_lock",
    "authorization_requires_post_emit_cardinality_audit",
    "authorization_requires_post_emit_provenance_join_audit",
    "authorization_requires_cleanup_proof",
    "authorization_requires_no_trainer_execution_contract",
    "authorization_forbids_trainer_invocation",
    "authorization_forbids_model_forward",
    "authorization_forbids_optimizer_or_backward",
    "authorization_forbids_arxiv_reads",
    "authorization_forbids_source_body_reads",
]

EXPECTED_OUTPUTS = [
    "route_cards.jsonl",
    "loss_mask_cards.jsonl",
    "trainer_rows.jsonl",
    "trainer_dry_run_input.json",
    "route_card_materialization_audit.json",
    "loss_mask_authority_audit.json",
    "loss_mask_enforcement_audit.json",
    "trainer_input_audit.json",
    "post_emit_cardinality_audit.json",
    "post_emit_provenance_join_audit.json",
    "post_emit_output_hash_manifest.json",
    "cleanup_proof.json",
]

STILL_BLOCKED_OUTPUTS = [
    "model_input_rows.jsonl",
    "trainer_execution_report.json",
    "sample_generation_audit.json",
    "checkpoint.pt",
    "optimizer_state.pt",
]

NEGATIVE_CASES = [
    "source_stage_missing",
    "registry_frontier_bad",
    "missing_auth_field",
    "missing_auth_guard",
    "missing_expected_output",
    "missing_blocked_output",
    "authorization_open_now",
    "outputs_emitted_now",
    "trainer_invoked_now",
    "model_forward",
    "optimizer_created",
    "backward_called",
    "arxiv_accessed",
    "source_body_reads",
    "training_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "runtime_authorized",
    "authority_open",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9186) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def build_design(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9186)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "design_type": "trainer_setup_no_trainer_emit_execution_authorization_v1",
        "source_stage9186_passed": source.get("passed") is True,
        "registry_frontier_stage9186": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9186,
        "required_auth_fields": list(REQUIRED_AUTH_FIELDS),
        "required_auth_guards": list(REQUIRED_AUTH_GUARDS),
        "expected_outputs": list(EXPECTED_OUTPUTS),
        "still_blocked_outputs": list(STILL_BLOCKED_OUTPUTS),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "design_only": True,
            "source_stage9186_passed": source.get("passed") is True,
            "registry_frontier_stage9186": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9186,
            "required_auth_fields": len(REQUIRED_AUTH_FIELDS),
            "required_auth_guards": len(REQUIRED_AUTH_GUARDS),
            "expected_outputs": len(EXPECTED_OUTPUTS),
            "still_blocked_outputs": len(STILL_BLOCKED_OUTPUTS),
            "authorization_open_now": False,
            "outputs_emitted_now": False,
            "trainer_invoked_now": False,
            "model_forward_attempted": False,
            "optimizer_created": False,
            "backward_called": False,
            "arxiv_accessed": False,
            "repository_source_bodies_loaded": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "decision": (
            "Designed the deliberate no-trainer emit execution authorization stage. If later instantiated and "
            "audited, it may authorize exact local materializer artifact emission under cleanup/hash/cardinality/"
            "provenance locks while keeping trainer invocation and all model execution paths closed."
        ),
        "next_best_step": "Audit the no-trainer emit execution authorization design; still do not emit outputs.",
    }


def validate_design(design: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    metrics = design.get("metrics") or {}
    if design.get("source_stage9186_passed") is not True or metrics.get("source_stage9186_passed") is not True:
        failures.append("source_stage9186_not_passed")
    if design.get("registry_frontier_stage9186") is not True or metrics.get("registry_frontier_stage9186") is not True:
        failures.append("registry_frontier_stage9186")
    for item in REQUIRED_AUTH_FIELDS:
        if item not in design.get("required_auth_fields", []):
            failures.append(f"missing_auth_field:{item}")
    for item in REQUIRED_AUTH_GUARDS:
        if item not in design.get("required_auth_guards", []):
            failures.append(f"missing_auth_guard:{item}")
    for item in EXPECTED_OUTPUTS:
        if item not in design.get("expected_outputs", []):
            failures.append(f"missing_expected_output:{item}")
    for item in STILL_BLOCKED_OUTPUTS:
        if item not in design.get("still_blocked_outputs", []):
            failures.append(f"missing_blocked_output:{item}")
    if any((design.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "authorization_open_now",
        "outputs_emitted_now",
        "trainer_invoked_now",
        "model_forward_attempted",
        "optimizer_created",
        "backward_called",
        "arxiv_accessed",
        "repository_source_bodies_loaded",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
    ]:
        if metrics.get(key) is not False:
            failures.append(key)
    return failures


def run_negative_cases() -> dict[str, Any]:
    negatives: dict[str, Any] = {}
    for case in NEGATIVE_CASES:
        design = copy.deepcopy(build_design(registry()))
        if case == "source_stage_missing":
            design["source_stage9186_passed"] = False
            design["metrics"]["source_stage9186_passed"] = False
        elif case == "registry_frontier_bad":
            design["registry_frontier_stage9186"] = False
            design["metrics"]["registry_frontier_stage9186"] = False
        elif case == "missing_auth_field":
            design["required_auth_fields"].remove("no_trainer_execution_contract_ref")
        elif case == "missing_auth_guard":
            design["required_auth_guards"].remove("authorization_forbids_trainer_invocation")
        elif case == "missing_expected_output":
            design["expected_outputs"].remove("trainer_rows.jsonl")
        elif case == "missing_blocked_output":
            design["still_blocked_outputs"].remove("model_input_rows.jsonl")
        elif case == "authorization_open_now":
            design["metrics"]["authorization_open_now"] = True
        elif case == "outputs_emitted_now":
            design["metrics"]["outputs_emitted_now"] = True
        elif case == "trainer_invoked_now":
            design["metrics"]["trainer_invoked_now"] = True
        elif case == "model_forward":
            design["metrics"]["model_forward_attempted"] = True
        elif case == "optimizer_created":
            design["metrics"]["optimizer_created"] = True
        elif case == "backward_called":
            design["metrics"]["backward_called"] = True
        elif case == "arxiv_accessed":
            design["metrics"]["arxiv_accessed"] = True
        elif case == "source_body_reads":
            design["metrics"]["repository_source_bodies_loaded"] = True
        elif case == "training_authorized":
            design["metrics"]["training_authorized"] = True
        elif case == "decoder_ce_authorized":
            design["metrics"]["decoder_ce_authorized"] = True
        elif case == "denoise_ce_authorized":
            design["metrics"]["denoise_ce_authorized"] = True
        elif case == "runtime_authorized":
            design["metrics"]["runtime_authorized_flag"] = True
        elif case == "authority_open":
            design["authority"]["model_execution_authorized_next"] = True
        negatives[case] = {"failures": validate_design(design), "rejected": bool(validate_design(design))}
    return negatives


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    design = build_design(registry_json)
    failures = validate_design(design)
    negatives = run_negative_cases()
    passed = not failures and all(item["rejected"] for item in negatives.values())
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "design": design,
        "failures": failures,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **design["metrics"],
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
        },
        "decision": design["decision"] if passed else "No-trainer emit execution authorization design failed validation.",
        "next_best_step": design["next_best_step"],
    }
    DESIGN.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **artifact["metrics"], "failures": artifact["failures"]},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": artifact["decision"],
        "next_best_step": artifact["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9187 Trainer Setup No-Trainer Emit Execution Authorization Design",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "Designs the no-trainer emit execution authorization boundary without emitting outputs.",
                "",
                f"Expected outputs: `{artifact['metrics']['expected_outputs']}`",
                f"Negative cases rejected: `{artifact['metrics']['negative_cases_rejected']}/{artifact['metrics']['negative_cases']}`",
                "",
                f"Next: {summary['next_best_step']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = summary["passed"]
    registry_json["metrics"] = {
        **(registry_json.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
