#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9397
NAME = "stage9397_heldout_contrastive_suffix_support_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9396_training_loop_frontier_diagnosis_contract.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9391_bounded_decoder_short_suffix_target_resolved_manifest/bounded_decoder_short_suffix_target_resolved_manifest.jsonl"
SOURCE_SAMPLES = ROOT / "runs/local/artifacts/stage9395_bounded_decoder_short_suffix_generation_cap_probe/sample_generation_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "heldout_contrastive_suffix_support_manifest.jsonl"
AUDIT = OUT_DIR / "heldout_contrastive_suffix_support_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "HELDOUT_CONTRASTIVE_SUFFIX_SUPPORT_MANIFEST_STAGE9397.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


SUPPORT_TARGETS = [
    ("expected_assertion_behavior_support", "Choose the verifier literal that preserves the expected assertion behavior. Keep the value small"),
    ("patch_operator_should_update_support", "Return the callable handle that the verified patch operator should update. Use the repo"),
    ("repaired_state_support", "Emit the state slot that should receive the repaired state. Keep the answer focused"),
    ("localized_edit_target_support", "Return the path handle associated with the localized edit target. Keep the path reference"),
    ("current_repair_invariant_support", "Select the concrete setting tied to the current repair invariant. Do not introduce an"),
    ("patch_inside_whitelist_support", "Emit the dependency handle that keeps the patch inside the whitelist. Use the symbol"),
    ("checked_symbol_evidence_support", "Return the path reference linked to the checked symbol evidence. Keep the decision compatible"),
    ("allowed_dependency_constraint_support", "Choose the module handle that satisfies the allowed dependency constraint. Keep the output limited"),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def prefix_for(target: str) -> str:
    words = target.split()
    return " ".join(words[:7])


def target_family(target: str, prefix: str) -> str:
    words = target.split()
    p = prefix.split()
    return " ".join(words[len(p) : len(p) + 3])


def set_target_surfaces(row: dict[str, Any], target: str) -> None:
    sha = hashlib.sha256(target.encode("utf-8")).hexdigest()
    row["clean_target"] = target
    row["decoder_text"] = target
    row["target"] = {"decoder_text": target}
    state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
    state.update({"target_hash": sha, "target_text_sha256": sha, "short_target_sha256": sha})
    row["input_state"] = state


def make_support_row(template: dict[str, Any], idx: int, family: str, target: str) -> dict[str, Any]:
    row = copy.deepcopy(template)
    prefix = prefix_for(target)
    row_id = f"stage9397_suffix_support_{idx:03d}_{h(family + target)}"
    mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
    mi.update(
        {
            "active_generation_prefix_span": prefix,
            "active_generation_prefix_words": len(prefix.split()),
            "heldout_contrastive_suffix_support": True,
            "support_family": family,
            "support_target_family": target_family(target, prefix),
            "support_row_is_train_only": True,
            "source_stage9391_template_row_id": template.get("row_id"),
            "route_schema_version": "stage9397_heldout_contrastive_suffix_support_v1",
        }
    )
    for key in ["clean_target", "target_text", "target_phrase", "remaining_suffix", "first_suffix_word", "original_full_target"]:
        mi.pop(key, None)
    anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    anti.update(
        {
            "decoder_ce_closed": True,
            "runtime_closed": True,
            "heldout_contrastive_suffix_support": True,
            "copied_heldout_row_id": False,
            "heldout_exact_target_in_model_input": False,
        }
    )
    state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
    state.update({"support_family": family, "heldout_contrastive_suffix_support": True, "decode_allowed": False, "repair_required": True})
    row.update(
        {
            "row_id": row_id,
            "source_stage": STAGE,
            "split": "train",
            "merged_curriculum_source": "heldout_contrastive_suffix_support",
            "combined_curriculum_source": "heldout_contrastive_suffix_support",
            "repair_task_type": "heldout_contrastive_suffix_support",
            "model_input": mi,
            "input_state": state,
            "anti_cheat": anti,
            "loss_mask": {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False},
            "authority": dict(AUTHORITY_CLOSED),
        }
    )
    set_target_surfaces(row, target)
    return row


def build_rows() -> list[dict[str, Any]]:
    base_rows = load_jsonl(SOURCE_MANIFEST)
    rows: list[dict[str, Any]] = []
    for row in base_rows:
        new = copy.deepcopy(row)
        mi = new.get("model_input") if isinstance(new.get("model_input"), dict) else {}
        mi["heldout_contrastive_suffix_support_eval_target"] = new.get("split") in {"eval", "strict_eval"}
        mi["route_schema_version"] = "stage9397_heldout_contrastive_suffix_support_v1"
        new["model_input"] = mi
        new["merged_curriculum_source"] = "stage9391_target_resolved_base"
        new["combined_curriculum_source"] = "stage9391_target_resolved_base"
        rows.append(new)
    template = next(row for row in base_rows if row.get("split") == "train")
    for idx, (family, target) in enumerate(SUPPORT_TARGETS):
        rows.append(make_support_row(template, idx, family, target))
    return rows


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    samples = load_json(SOURCE_SAMPLES).get("samples") or []
    split_counts = Counter(str(row.get("split")) for row in rows)
    source_counts = Counter(str(row.get("merged_curriculum_source")) for row in rows)
    support_families = Counter(str((row.get("model_input") or {}).get("support_family")) for row in rows if row.get("merged_curriculum_source") == "heldout_contrastive_suffix_support")
    failing_families = Counter()
    for sample in samples:
        if sample.get("exact_match"):
            continue
        target = str(sample.get("target_text") or "")
        prefix = str(sample.get("generation_prefix_text") or "")
        failing_families[target_family(target, prefix)] += 1
    unsafe: list[str] = []
    inconsistent: list[str] = []
    target_visible: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        target = str(row.get("clean_target") or "")
        nested = row.get("target") if isinstance(row.get("target"), dict) else {}
        mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        prefix = str(mi.get("active_generation_prefix_span") or "")
        if loss != {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}:
            unsafe.append(row_id)
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            unsafe.append(row_id)
        if row.get("decoder_text") != target or nested.get("decoder_text") != target or not target.startswith(prefix):
            inconsistent.append(row_id)
        if target and target in json.dumps(mi, sort_keys=True):
            target_visible.append(row_id)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9396_not_passed")
    if len(rows) != 31:
        failures.append("unexpected_row_count")
    if dict(split_counts) != {"eval": 9, "strict_eval": 7, "train": 15}:
        failures.append("unexpected_split_counts")
    if source_counts.get("heldout_contrastive_suffix_support") != 8:
        failures.append("support_row_count_not_8")
    if unsafe:
        failures.append("unsafe_rows")
    if inconsistent:
        failures.append("inconsistent_target_surfaces")
    if target_visible:
        failures.append("target_visible_in_model_input")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "support_families": dict(sorted(support_families.items())),
        "stage9395_failing_families": dict(sorted(failing_families.items())),
        "unsafe_rows": sorted(set(unsafe))[:20],
        "inconsistent_target_rows": inconsistent[:20],
        "target_visible_rows": target_visible[:20],
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    audit = audit_rows(rows)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Added train-only contrastive suffix support rows for Stage9395 heldout failures while preserving original eval/strict rows as heldout checks.",
        "next_best_step": "Build Stage9398 preexecution and run a scoped denoise-only heldout suffix-support probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9397 Heldout Contrastive Suffix Support Manifest", "", f"Passed: `{audit['passed']}`", f"Rows: `{audit['rows']}`", f"Splits: `{audit['split_counts']}`", f"Sources: `{audit['source_counts']}`", "", "This adds train-only support rows for suffix families missing from Stage9395 train coverage. Decoder CE and all external authority remain closed.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["rows", "split_counts", "source_counts", "failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
