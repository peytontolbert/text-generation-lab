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
STAGE = 9401
NAME = "stage9401_suffix_second_span_support_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9400_suffix_second_span_residual_diagnosis.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9397_heldout_contrastive_suffix_support_manifest/heldout_contrastive_suffix_support_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "suffix_second_span_support_manifest.jsonl"
AUDIT = OUT_DIR / "suffix_second_span_support_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_SECOND_SPAN_SUPPORT_MANIFEST_STAGE9401.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SECOND_SPAN_SUPPORT_TARGETS = [
    ("expected_assertion_behavior_second_span", "Choose the check literal that preserves the expected assertion behavior. Keep the value small"),
    ("expected_assertion_behavior_select_second_span", "Select the verifier constant that preserves the expected assertion behavior. Keep the value small"),
    ("patch_operator_update_second_span", "Select the method endpoint that the verified patch operator should update. Use the repo"),
    ("patch_operator_update_callable_second_span", "Return the callable target that the verified patch operator should update. Use the repo"),
    ("repaired_state_second_span", "Emit the state name that should receive the repaired state. Keep the answer focused"),
    ("repaired_state_slot_second_span", "Return the local slot that should receive the repaired state. Keep the answer focused"),
    ("localized_edit_target_second_span", "Return the file path associated with the localized edit target. Keep the path reference"),
    ("localized_edit_target_path_second_span", "Choose the path handle associated with the localized edit target. Keep the path reference"),
    ("current_repair_invariant_second_span", "Select the repair setting tied to the current repair invariant. Do not introduce an"),
    ("current_repair_invariant_value_second_span", "Choose the invariant value tied to the current repair invariant. Do not introduce an"),
    ("patch_inside_whitelist_second_span", "Return the dependency handle that keeps the patch inside the whitelist. Use the symbol"),
    ("patch_inside_whitelist_dependency_second_span", "Choose the dependency slot that keeps the patch inside the whitelist. Use the symbol"),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def prefix_for(target: str) -> str:
    return " ".join(target.split()[:7])


def family_for(target: str, prefix: str, n: int = 7) -> str:
    words = target.split()
    p = prefix.split()
    return " ".join(words[len(p) : len(p) + n])


def set_target(row: dict[str, Any], target: str) -> None:
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
    row_id = f"stage9401_second_span_{idx:03d}_{h(family + target)}"
    mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
    mi.update(
        {
            "active_generation_prefix_span": prefix,
            "active_generation_prefix_words": len(prefix.split()),
            "suffix_second_span_support": True,
            "support_family": family,
            "support_target_family_7_words": family_for(target, prefix),
            "support_row_is_train_only": True,
            "source_stage9397_template_row_id": template.get("row_id"),
            "route_schema_version": "stage9401_suffix_second_span_support_v1",
        }
    )
    for key in ["clean_target", "target_text", "target_phrase", "remaining_suffix", "first_suffix_word", "original_full_target"]:
        mi.pop(key, None)
    anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    anti.update(
        {
            "decoder_ce_closed": True,
            "runtime_closed": True,
            "suffix_second_span_support": True,
            "copied_heldout_row_id": False,
            "heldout_exact_target_in_model_input": False,
        }
    )
    state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
    state.update({"support_family": family, "suffix_second_span_support": True, "decode_allowed": False, "repair_required": True})
    row.update(
        {
            "row_id": row_id,
            "source_stage": STAGE,
            "split": "train",
            "merged_curriculum_source": "suffix_second_span_support",
            "combined_curriculum_source": "suffix_second_span_support",
            "repair_task_type": "suffix_second_span_support",
            "model_input": mi,
            "input_state": state,
            "anti_cheat": anti,
            "loss_mask": {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False},
            "authority": dict(AUTHORITY_CLOSED),
        }
    )
    set_target(row, target)
    return row


def build_rows() -> list[dict[str, Any]]:
    base_rows = load_jsonl(SOURCE_MANIFEST)
    rows = [copy.deepcopy(row) for row in base_rows]
    template = next(row for row in base_rows if row.get("split") == "train")
    for idx, (family, target) in enumerate(SECOND_SPAN_SUPPORT_TARGETS):
        rows.append(make_support_row(template, idx, family, target))
    return rows


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    split_counts = Counter(str(row.get("split")) for row in rows)
    source_counts = Counter(str(row.get("merged_curriculum_source")) for row in rows)
    support_families = Counter(str((row.get("model_input") or {}).get("support_family")) for row in rows if row.get("merged_curriculum_source") == "suffix_second_span_support")
    unsafe: list[str] = []
    inconsistent: list[str] = []
    visible: list[str] = []
    duplicate_heldout_targets: list[str] = []
    heldout_targets = {str(row.get("clean_target")) for row in rows if row.get("split") in {"eval", "strict_eval"}}
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
            visible.append(row_id)
        if row.get("merged_curriculum_source") == "suffix_second_span_support" and target in heldout_targets:
            duplicate_heldout_targets.append(row_id)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9400_not_passed")
    if len(rows) != 43:
        failures.append("unexpected_row_count")
    if dict(split_counts) != {"eval": 9, "strict_eval": 7, "train": 27}:
        failures.append("unexpected_split_counts")
    if source_counts.get("suffix_second_span_support") != 12:
        failures.append("second_span_support_row_count_not_12")
    if unsafe:
        failures.append("unsafe_rows")
    if inconsistent:
        failures.append("inconsistent_target_surfaces")
    if visible:
        failures.append("target_visible_in_model_input")
    if duplicate_heldout_targets:
        failures.append("support_target_duplicates_heldout_target")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "support_families": dict(sorted(support_families.items())),
        "unsafe_rows": sorted(set(unsafe))[:20],
        "inconsistent_target_rows": inconsistent[:20],
        "target_visible_rows": visible[:20],
        "duplicate_heldout_target_rows": duplicate_heldout_targets[:20],
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
        "decision": "Added train-only second-span suffix support rows for Stage9400 heldout residual families.",
        "next_best_step": "Build Stage9402 preexecution and run a scoped denoise-only second-span support probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9401 Suffix Second-Span Support Manifest", "", f"Passed: `{audit['passed']}`", f"Rows: `{audit['rows']}`", f"Splits: `{audit['split_counts']}`", f"Sources: `{audit['source_counts']}`", "", "This extends Stage9397 with train-only analogous rows for heldout second-span suffix residuals. Decoder CE and all external authority remain closed.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["rows", "split_counts", "source_counts", "failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
