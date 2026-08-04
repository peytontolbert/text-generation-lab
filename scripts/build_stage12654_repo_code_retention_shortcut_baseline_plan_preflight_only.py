#!/usr/bin/env python3
# Materialize a retention-eval and shortcut-baseline plan for repo/code stage-01 training, without training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12654_repo_code_retention_shortcut_baseline_plan_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12653 = ROOT / "runs/local/artifacts/stage12653_repo_code_training_run_authorization_preflight_only"
S12653_SUMMARY = ROOT / "runs/summaries/stage12653_repo_code_training_run_authorization_preflight_only.json"
S12653_SCRIPT = ROOT / "scripts/build_stage12653_repo_code_training_run_authorization_preflight_only.py"
S12653_TESTS = ROOT / "tests/test_stage12653_repo_code_training_run_authorization_preflight_only.py"
S12651_MANIFEST = ROOT / "runs/local/artifacts/stage12651_repo_code_curriculum_ingestion_contract_preflight_only/private/repo_code_curriculum_ingest_manifest.jsonl"

EXPECTED_HASHES = {
    "stage12653_summary": "28e65a0e358803e1041f4bfe6bd3993ec45487b2efb8686ae2b4a2f3bfb4c51f",
    "stage12653_contract": "9fb0409edc829565dc2632f882fe89d2071f16a71daab80d348f11edc03c074f",
    "stage12653_pointer": "9b5f83a181d6a36b1165e59bde51254f6ed3a4f7e6ec10fe8b74e76eb3c335a8",
    "stage12653_private_packet": "8d763ee8a809627e7ce1c1dd276c94b173813e7679ae12e94cce22ff66e8267a",
    "stage12653_script_bytes": "f77b019caf881bf0e1702c152ae23c42f09ff86c9a2558ac7bb82a1b865f4a22",
    "stage12653_tests_bytes": "ac6179fe43b120b5b8ca1f8bcfd4b20e7c030d8f2bcc9ea1456eef169b68ad4e",
    "stage12651_manifest_bytes": "d19e8b0139d1dd179ca369b7db8c4252b8ac4e711855208fd273ec9419a46cb1",
    "stage12651_manifest_semantic": "21b3d427575a7883950600ab93e0980d3f74ad52f146bde58d6eba27144ead79",
}
EXPECTED_STAGE12653_ARTIFACTS = ["contract.json", "digest_pointer.json", "private/repo_code_training_run_authorization_preflight.json", "summary.json"]
EXPECTED_SPLITS = {"eval": 64, "strict_eval": 63, "train": 153}
EXPECTED_LANES = {"repo_code_knowledge.repo_capability_profile": 200, "repo_code_knowledge.symbol_reference_prediction": 80}
FALSE_FIELDS = (
    "training_admission_allowed", "training_allowed", "training_run_allowed", "training_admitted",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "implementation_ready", "stage12595_allowed", "replay_trustworthy", "level_3_materialized",
    "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed", "runtime_authorized",
    "model_execution_authorized_next", "source_emission_authorized", "body_emission_authorized",
    "decoder_ce_training_authorized_next", "transition_head_training_authorized_next", "promotion_ready", "optimizer_step_authorized",
)
FORBIDDEN = ("/data/", "/arxiv/", '"model_input":', '"target_text":', "source_lineage", "source_row_id", "source_ref", "repo_graph_and_symbol_binding", "PLACEHOLDER", "TODO", "TBD", "<fill")

class Stage12654BaselinePlanError(RuntimeError):
    pass

def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12654BaselinePlanError("json_object_required:" + path.name)
    return value

def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows=[]
    for i,line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if line:
            value=json.loads(line)
            if not isinstance(value, dict):
                raise Stage12654BaselinePlanError(f"jsonl_object_required:{i}")
            rows.append(value)
    return rows

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data=json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii")+b"\n"
    with path.open("wb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())

def fsync_dir(path: Path) -> None:
    fd=os.open(str(path), os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

def false_fields() -> dict[str, bool]:
    return {k: False for k in FALSE_FIELDS}

def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if record.get(field) is not False:
            raise Stage12654BaselinePlanError(f"{label}_gate_drift:{field}")

def assert_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded=json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in FORBIDDEN:
        if needle in encoded:
            raise Stage12654BaselinePlanError(f"{label}_leak_or_drift:{needle}")

def count_by(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(r.get(field)) for r in rows).items()))

def load_inputs() -> dict[str, Any]:
    emitted=sorted(p.relative_to(S12653).as_posix() for p in S12653.rglob("*") if p.is_file())
    if emitted != EXPECTED_STAGE12653_ARTIFACTS:
        raise Stage12654BaselinePlanError("stage12653_artifact_manifest_drift")
    summary=read_json(S12653/"summary.json")
    if summary != read_json(S12653_SUMMARY):
        raise Stage12654BaselinePlanError("stage12653_external_summary_mismatch")
    contract=read_json(S12653/"contract.json")
    pointer=read_json(S12653/"digest_pointer.json")
    private=read_json(S12653/"private/repo_code_training_run_authorization_preflight.json")
    manifest_bytes=S12651_MANIFEST.read_bytes()
    manifest=read_jsonl_bytes(manifest_bytes)
    for label,value in (("stage12653_summary",summary),("stage12653_contract",contract),("stage12653_pointer",pointer),("stage12653_private_packet",private)):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise Stage12654BaselinePlanError("pin_drift:"+label)
    for label,data in (("stage12653_script_bytes",S12653_SCRIPT.read_bytes()),("stage12653_tests_bytes",S12653_TESTS.read_bytes()),("stage12651_manifest_bytes",manifest_bytes)):
        if sha256_bytes(data) != EXPECTED_HASHES[label]:
            raise Stage12654BaselinePlanError("pin_drift:"+label)
    if stable_hash(manifest) != EXPECTED_HASHES["stage12651_manifest_semantic"]:
        raise Stage12654BaselinePlanError("pin_drift:stage12651_manifest_semantic")
    if summary.get("decision") != "BLOCKED_EXPLICIT_TRAINING_AUTHORIZATION_AND_RUNTIME_CONTRACT_REQUIRED":
        raise Stage12654BaselinePlanError("stage12653_not_training_preflight")
    if "retention_eval_and_shortcut_baseline_plan_not_materialized" not in summary.get("authorization_blockers", []):
        raise Stage12654BaselinePlanError("stage12653_missing_target_blocker")
    for label,record in (("summary",summary),("contract",contract),("pointer",pointer),("private",private)):
        check_false(record,"stage12653_"+label); assert_sanitized(record,"stage12653_"+label)
    return {"summary": summary, "manifest": manifest}

def build_baseline_plan(manifest: list[Mapping[str, Any]]) -> dict[str, Any]:
    if len(manifest) != 280 or count_by(manifest,"split") != EXPECTED_SPLITS or count_by(manifest,"curriculum_lane") != EXPECTED_LANES:
        raise Stage12654BaselinePlanError("manifest_distribution_drift")
    eval_rows=[r for r in manifest if r.get("split")=="eval"]
    strict_rows=[r for r in manifest if r.get("split")=="strict_eval"]
    train_rows=[r for r in manifest if r.get("split")=="train"]
    plan={
        "record_type": "stage12654_private_retention_shortcut_baseline_plan_v1",
        "baseline_plan_materialized": True,
        "retention_eval_rows": len(eval_rows),
        "strict_eval_rows_reserved_not_admitted": len(strict_rows),
        "train_rows_for_shortcut_shadow_baseline": len(train_rows),
        "retention_metrics": ["eval_loss_by_objective", "eval_loss_by_lane", "row_loss_regression", "symbol_binding_retention"],
        "shortcut_baseline_checks": ["lane_label_ablation", "loss_mask_flip_probe", "source_hash_permutation_probe", "split_leak_sentinel", "constant_target_probe"],
        "acceptance_thresholds": {
            "eval_loss_regression_max_relative": 0.05,
            "shortcut_probe_accuracy_max": 0.58,
            "loss_mask_flip_delta_required": True,
            "strict_eval_used_for_training": False,
        },
        "excluded_from_training": ["eval", "strict_eval"],
        "training_allowed": False,
        "optimizer_step_authorized": False,
        "model_forward_allowed": False,
    }
    assert_sanitized(plan, "baseline_plan")
    return plan

def build_packet(inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    plan=build_baseline_plan(list(inputs["manifest"]))
    remaining=[b for b in inputs["summary"].get("authorization_blockers", []) if b != "retention_eval_and_shortcut_baseline_plan_not_materialized"]
    true_fields={
        "repo_code_knowledge_stage_complete": True,
        "repo_code_curriculum_layer_complete": True,
        "curriculum_ingest_manifest_review_passed": True,
        "stage12653_training_run_authorization_preflight_performed": True,
        "retention_eval_and_shortcut_baseline_plan_materialized": True,
        "separate_training_admission_required": True,
    }
    audit={
        "retention_eval_and_shortcut_baseline_plan_materialized": True,
        "retention_eval_rows": 64,
        "strict_eval_rows_reserved_not_admitted": 63,
        "train_rows_for_shortcut_shadow_baseline": 153,
        "baseline_plan_sha256": stable_hash(plan),
        "resolved_authorization_blocker": "retention_eval_and_shortcut_baseline_plan_not_materialized",
        "remaining_authorization_blocker_count": len(remaining),
        "remaining_authorization_blockers": remaining,
    }
    private={"record_type":"stage12654_private_retention_shortcut_baseline_plan_packet_v1", **false_fields(), **true_fields, "reviewed_input_hashes": EXPECTED_HASHES, "baseline_plan": plan, "baseline_audit": audit}
    contract={"record_type":"stage12654_public_retention_shortcut_baseline_plan_contract_v1", **false_fields(), **true_fields, **audit, "private_packet_sha256": stable_hash(private), "next_required_action":"stage12655_repo_code_optimizer_context_trainer_binding_preflight_only"}
    summary={"record_type":"stage12654_public_retention_shortcut_baseline_plan_summary_v1", **false_fields(), **true_fields, **audit, "stage": STAGE, "decision":"RETENTION_SHORTCUT_BASELINE_PLAN_MATERIALIZED_NO_TRAINING", "private_packet_sha256": stable_hash(private), "contract_sha256": stable_hash(contract), "next_required_action":"stage12655_repo_code_optimizer_context_trainer_binding_preflight_only"}
    pointer={"record_type":"stage12654_public_retention_shortcut_baseline_plan_pointer_v1", **false_fields(), **true_fields, "contract_sha256": stable_hash(contract), "private_packet_sha256": stable_hash(private), "baseline_plan_sha256": stable_hash(plan)}
    for label,record in (("summary",summary),("contract",contract),("pointer",pointer),("private",private)):
        check_false(record,label); assert_sanitized(record,label)
    return summary, contract, private, pointer

def build(out: Path=OUT, summary_path: Path=SUMMARY) -> dict[str, Any]:
    summary,contract,private,pointer=build_packet(load_inputs())
    write_json(out/"contract.json", contract)
    write_json(out/"digest_pointer.json", pointer)
    write_json(out/"private/repo_code_retention_shortcut_baseline_plan_packet.json", private)
    write_json(out/"summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out/"private"); fsync_dir(out); fsync_dir(summary_path.parent)
    return summary

if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
