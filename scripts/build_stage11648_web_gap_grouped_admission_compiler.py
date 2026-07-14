#!/usr/bin/env python3
from __future__ import annotations

import collections
import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11648
NAME = "stage11648_web_gap_grouped_admission_compiler"
OUT = ART / NAME
SUMMARY = OUT / "web_gap_grouped_admission_compiler.json"
ADMITTED = OUT / "web_gap_grouped_admitted_rows.jsonl"
REJECTED = OUT / "web_gap_grouped_rejected_rows.jsonl"
REQUEST = OUT / "web_gap_grouped_probe_request.json"
MANIFEST = OUT / "web_gap_grouped_probe_manifest.jsonl"

STAGE11646_WORK_ITEMS = ART / "stage11646_web_heldout_gap_rollout_mining/web_heldout_gap_materialization_work_items.jsonl"
STAGE11646_GROUPS = ART / "stage11646_web_heldout_gap_rollout_mining/web_heldout_gap_rollout_groups.jsonl"
STAGE11647 = ART / "stage11647_root_group_objective_readiness_audit/root_group_objective_readiness_audit.json"
HELDOUT = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"
ALREADY_FIT_SUPPORT = ART / "stage11638_web_support_schema_normalization/web_support_normalized_admitted_train_rows.jsonl"

CANDIDATE_SOURCES = {
    "stage11590_moderate_task_aware_train": ART / "stage11590_web_moderate_task_aware_contrast_probe_request/web_moderate_task_aware_contrast_train_rows.jsonl",
    "stage11594_repaired_train": ART / "stage11594_web_verifier_attached_repaired_geometry_package/web_verifier_attached_repaired_train_rows.jsonl",
    "stage11597_no_abstain_train": ART / "stage11597_web_answerable_no_abstain_geometry_audit/web_answerable_no_abstain_train_rows.jsonl",
    "stage11615_mutation_admitted": ART / "stage11615_web_mutation_rows_anticheat_audit/web_mutation_rows_admitted_train_support.jsonl",
    "stage11621_fail_to_pass_repaired": ART / "stage11621_web_fail_to_pass_row_geometry_repair/web_fail_to_pass_geometry_repaired_train_support.jsonl",
    "stage11638_normalized_support": ALREADY_FIT_SUPPORT,
    "stage11650_verified_grouped_rows": ART / "stage11650_web_gap_grouped_verified_materialization/web_gap_grouped_verified_rows.jsonl",
}

TASKS = {
    "symptom_localization",
    "evidence_citation",
    "verifier_outcome",
    "minimal_fix_selection",
    "patch_impact",
    "alternative_hypothesis_elimination",
    "abstention_insufficient_evidence",
}
ROLE_REQUIREMENTS = {
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def repo_family(row: dict[str, Any]) -> str:
    return str(row.get("repo_family") or row.get("git_repo_family") or row.get("web_heldout_source") or "unknown")


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("root_lineage_key") or row.get("row_id") or "unknown")


def task_type(row: dict[str, Any]) -> str:
    return str(row.get("task_type") or row.get("perspective") or "unknown")


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    opts = row.get("opaque_options") or ((row.get("standalone_projection_source") or {}).get("opaque_options")) or []
    return [opt for opt in opts if isinstance(opt, dict)]


def option_roles(row: dict[str, Any]) -> set[str]:
    roles: set[str] = set()
    for opt in options(row):
        role = str(opt.get("semantic_role") or "").strip()
        if role:
            roles.add(role)
        value = str(opt.get("value") or opt.get("text") or "").strip()
        if value == "ABSTAIN_INSUFFICIENT_EVIDENCE":
            roles.add("abstain_insufficient_evidence")
    return roles


def selected_verifier(row: dict[str, Any]) -> str:
    bundle = (row.get("standalone_projection_source") or {}).get("bundle") or {}
    verifier_evidence = row.get("verifier_evidence") or bundle.get("verifier_execution_evidence") or {}
    command = verifier_evidence.get("command") if isinstance(verifier_evidence, dict) else None
    if row.get("selected_verifier_path"):
        return str(row["selected_verifier_path"])
    if bundle.get("selected_test_path"):
        return str(bundle["selected_test_path"])
    if isinstance(command, list):
        for part in reversed(command):
            text = str(part)
            if any(token in text for token in (".test", ".spec", "__tests__", "pytest", "cargo")):
                return text
    return ""


def verifier_transition(row: dict[str, Any]) -> str:
    bundle = (row.get("standalone_projection_source") or {}).get("bundle") or {}
    verifier_evidence = row.get("verifier_evidence") or bundle.get("verifier_execution_evidence") or {}
    if row.get("observed_verifier_transition"):
        return str(row["observed_verifier_transition"])
    if row.get("verifier_transition"):
        return str(row["verifier_transition"])
    if isinstance(verifier_evidence, dict) and verifier_evidence.get("transition"):
        return str(verifier_evidence["transition"])
    if isinstance(verifier_evidence, dict) and verifier_evidence.get("status"):
        return str(verifier_evidence["status"])
    return ""


def target_label(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    return str(row.get("bounded_choice_target_label") or target.get("bounded_choice_target_label") or row.get("target_text") or row.get("decoder_text") or "").strip()


def anti_cheat_ok(row: dict[str, Any]) -> bool:
    anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    if anti.get("requires_prompt_target_leak_review_before_training") is True:
        return False
    if anti.get("prompt_target_leak") is True:
        return False
    if anti.get("target_label_not_visible_before_options") is False:
        return False
    if anti.get("no_gold_label_in_prompt_before_options") is False:
        return False
    return True


def canonicalize_row(row: dict[str, Any], *, source_name: str) -> dict[str, Any]:
    out = dict(row)
    out["stage11648_source"] = source_name
    out["repo_family"] = repo_family(row)
    out["root_id"] = root_id(row)
    out["task_type"] = task_type(row)
    out["selected_verifier_path"] = selected_verifier(row)
    out["observed_verifier_transition"] = verifier_transition(row)
    out["bounded_choice_target_label"] = target_label(row)
    out["decoder_text"] = target_label(row)
    out["rollout_group_id"] = f"stage11648::{out['repo_family']}::{out['root_id']}"
    out["root_group_id"] = out["rollout_group_id"]
    out["split"] = "train"
    out["package_split"] = "train"
    out["loss_mask"] = {"decoder_ce": True, "bounded_choice_aux": True}
    out["stage11648_grouped_admission"] = True
    source = dict(out.get("standalone_projection_source") or {})
    source.setdefault("opaque_options", options(row))
    out["standalone_projection_source"] = source
    return out


def rejection_reasons(
    row: dict[str, Any],
    *,
    source_name: str,
    heldout_roots: set[str],
    already_fit_row_ids: set[str],
    work_item_keys: set[tuple[str, str]],
) -> list[str]:
    reasons: list[str] = []
    row_id = str(row.get("row_id") or "")
    repo = repo_family(row)
    task = task_type(row)
    if (repo, task) not in work_item_keys:
        reasons.append("not_targeted_by_stage11646_repo_task_gap")
    if source_name == "stage11638_normalized_support" or row_id in already_fit_row_ids:
        reasons.append("already_fit_by_stage11643_support_geometry")
    if root_id(row) in heldout_roots:
        reasons.append("direct_web_heldout_root_do_not_train")
    if task not in TASKS:
        reasons.append("unsupported_or_missing_task_type")
    if str(row.get("language_family") or "web_js_ts_html") != "web_js_ts_html":
        reasons.append("not_web_language_family")
    if len(options(row)) < 2:
        reasons.append("missing_competing_opaque_options")
    if not target_label(row):
        reasons.append("missing_bounded_choice_target_label")
    if not selected_verifier(row):
        reasons.append("missing_selected_verifier_path")
    if not verifier_transition(row):
        reasons.append("missing_observed_verifier_transition")
    roles = option_roles(row)
    if task in {"evidence_citation", "verifier_outcome", "minimal_fix_selection", "symptom_localization", "patch_impact"}:
        if not (roles & ROLE_REQUIREMENTS):
            reasons.append("missing_role_distinct_candidate_geometry")
    if not anti_cheat_ok(row):
        reasons.append("anti_cheat_or_prompt_leak_review_failed")
    return reasons


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    work_items = load_jsonl(STAGE11646_WORK_ITEMS)
    groups = load_jsonl(STAGE11646_GROUPS)
    stage11647 = load_json(STAGE11647)
    heldout = load_jsonl(HELDOUT)
    already_fit = load_jsonl(ALREADY_FIT_SUPPORT)
    heldout_roots = {root_id(row) for row in heldout}
    already_fit_row_ids = {str(row.get("row_id")) for row in already_fit}
    work_item_keys = {(str(item.get("repo_family")), str(item.get("task_type"))) for item in work_items}

    admitted_by_row_id: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    for source_name, path in CANDIDATE_SOURCES.items():
        rows = load_jsonl(path)
        source_counts[source_name] = len(rows)
        for row in rows:
            reasons = rejection_reasons(
                row,
                source_name=source_name,
                heldout_roots=heldout_roots,
                already_fit_row_ids=already_fit_row_ids,
                work_item_keys=work_item_keys,
            )
            row_id = str(row.get("row_id") or f"{source_name}::{len(rejected)}")
            if reasons:
                rejected.append(
                    {
                        "row_id": row_id,
                        "root_id": root_id(row),
                        "repo_family": repo_family(row),
                        "task_type": task_type(row),
                        "source": source_name,
                        "reasons": reasons,
                    }
                )
                continue
            admitted_by_row_id.setdefault(row_id, canonicalize_row(row, source_name=source_name))
    admitted = list(admitted_by_row_id.values())

    by_repo_task = collections.Counter((row["repo_family"], row["task_type"]) for row in admitted)
    by_root = collections.defaultdict(list)
    for row in admitted:
        by_root[row["root_id"]].append(row)
    complete_roots = [root for root, rows in by_root.items() if len({row["task_type"] for row in rows}) >= 4]
    total_requested_roots = sum(int(item.get("recommended_new_disjoint_roots") or 0) for item in work_items)
    min_probe_rows = 60
    gates = {
        "stage11647_ready": stage11647.get("decision") == "root_group_objective_ready_for_materialized_web_gap_probe",
        "has_stage11646_work_items": len(work_items) > 0,
        "admitted_rows_at_least_60": len(admitted) >= min_probe_rows,
        "admitted_roots_at_least_20": len(by_root) >= 20,
        "complete_or_multi_task_roots_at_least_8": len(complete_roots) >= 8,
        "no_direct_heldout_roots": not any(row["root_id"] in heldout_roots for row in admitted),
        "no_already_fit_stage11638_rows": not any(str(row.get("row_id")) in already_fit_row_ids for row in admitted),
        "covers_openhands_or_llama_gap": any(row["repo_family"] in {"openhands_openhands_frontend", "llama_stack_ui"} for row in admitted),
    }
    can_emit_training_request = all(gates.values())

    command = None
    if can_emit_training_request:
        # This request is intentionally conservative and should still be postrun-gated.
        command = [
            "env",
            "CUDA_VISIBLE_DEVICES=2",
            "NVIDIA_VISIBLE_DEVICES=2",
            "AGENTKERNEL_EVAL_DEVICE=cuda:0",
            "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
            "TMPDIR=/data/tmp",
            "TEMP=/data/tmp",
            "TMP=/data/tmp",
            "conda",
            "run",
            "-n",
            "trellis",
            "python",
            str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
            "--repo-root",
            str(ROOT),
            "--manifest",
            str(MANIFEST),
            "--mode",
            "bounded_decoder_ce_probe",
            "--probe-scale",
            "target_100m",
            "--implementation",
            "transformer",
            "--model-config",
            str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
            "--tokenizer-json",
            str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
            "--tokenizer-config",
            str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
            "--tokenizer-hashlock",
            str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
            "--execution-authorized-for-recovery-probe",
            "--max-train-rows",
            str(len(admitted)),
            "--max-eval-rows",
            "0",
            "--max-strict-rows",
            "0",
            "--max-steps",
            "512",
            "--batch-size",
            "8",
            "--learning-rate",
            "2e-7",
            "--max-encoder-tokens",
            "768",
            "--max-decoder-tokens",
            "16",
            "--decoder-ce-weight",
            "0.04",
            "--bounded-choice-aux-weight",
            "1.0",
            "--bounded-choice-root-group-aux-weight",
            "2.0",
            "--bounded-choice-aux-source",
            "encoder_option_retrieval_web_task_candidate_head",
            "--bounded-decoder-train-sampler",
            "web_gap_root_balanced",
            "--bounded-choice-contrast-weight",
            "0.5",
            "--bounded-choice-contrast-margin",
            "0.08",
            "--structured-aux-weight",
            "0.0",
            "--denoise-weight",
            "0.0",
            "--eos-loss-weight",
            "4.0",
            "--require-loss-mask-enforcement-audit",
            "--allow-runtime-model-save-for-harness",
            "--runtime-model-save-dir",
            str(ART / "stage11649_web_gap_grouped_probe/runtime_model"),
            "--initialize-from-runtime-model",
            str(ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"),
            "--preservation-reference-runtime-model",
            str(ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"),
            "--preservation-kl-weight",
            "8.0",
            "--no-final-checkpoint-export",
            "--output-dir",
            str(ART / "stage11649_web_gap_grouped_probe/bounded_decoder_probe"),
        ]

    write_jsonl(ADMITTED, admitted)
    write_jsonl(REJECTED, rejected)
    manifest_rows = list(admitted)
    write_jsonl(MANIFEST, manifest_rows if can_emit_training_request else [])
    decision = "web_gap_grouped_training_request_ready" if can_emit_training_request else "blocked_waiting_for_new_grouped_analogue_rows"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "source_counts": source_counts,
        "metrics": {
            "work_items": len(work_items),
            "gap_groups": len(groups),
            "requested_disjoint_roots": total_requested_roots,
            "candidate_rows_seen": sum(source_counts.values()),
            "admitted_rows": len(admitted),
            "admitted_roots": len(by_root),
            "multi_task_roots_ge_4_tasks": len(complete_roots),
            "rejected_rows": len(rejected),
        },
        "gates": gates,
        "admitted_by_repo_task": {f"{repo}::{task}": count for (repo, task), count in sorted(by_repo_task.items())},
        "rejection_reasons": dict(collections.Counter(reason for row in rejected for reason in row["reasons"])),
        "training_request": {
            "command": command,
            "manifest": rel(MANIFEST),
            "runtime_stage_if_run": "stage11649_web_gap_grouped_probe",
            "note": "Only emitted when enough new grouped analogue rows pass admission; never train direct heldout or already-fit Stage11638 support rows.",
        },
        "source_artifacts": {
            "stage11646_work_items": rel(STAGE11646_WORK_ITEMS),
            "stage11646_groups": rel(STAGE11646_GROUPS),
            "stage11647": rel(STAGE11647),
            "heldout": rel(HELDOUT),
            "already_fit_support": rel(ALREADY_FIT_SUPPORT),
            "candidate_sources": {name: rel(path) for name, path in CANDIDATE_SOURCES.items()},
        },
        "outputs": {"summary": rel(SUMMARY), "admitted": rel(ADMITTED), "rejected": rel(REJECTED), "request": rel(REQUEST), "manifest": rel(MANIFEST)},
        "next_actions": [
            "Materialize new disjoint analogue roots for the Stage11646 work items; current legacy sources are insufficient if this stage is blocked.",
            "Rerun this compiler after new rows exist; only then run Stage11649 grouped probe.",
            "Keep Stage11507 protected gates and routed Web/Gemma comparisons as postrun promotion gates.",
        ],
        "claim_boundary": [
            "This stage is an admission compiler and may intentionally block.",
            "Blocked status means the trainer is ready but new grouped analogue data has not been admitted.",
            "No Web heldout row is converted into training data by this stage.",
        ],
    }
    write_json(REQUEST, summary["training_request"])
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "metrics": summary["metrics"], "gates": gates, "top_rejection_reasons": dict(collections.Counter(reason for row in rejected for reason in row["reasons"]).most_common(10))}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
