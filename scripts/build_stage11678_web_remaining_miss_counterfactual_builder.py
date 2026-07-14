#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import random
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11678_web_remaining_miss_counterfactual_builder"
OUT = ART / NAME
TRAIN_OUT = OUT / "web_same_role_identity_counterfactual_train.jsonl"
HELDOUT_DIAG = OUT / "web_remaining_canonical_miss_sealed_diagnostics.jsonl"
PACKAGE = OUT / "web_remaining_miss_counterfactual_package.json"

RENDERER_PATH = ROOT / "scripts/build_stage11663_web_canonical_renderer_package.py"
spec = importlib.util.spec_from_file_location("stage11663_renderer", RENDERER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to load canonical renderer: {RENDERER_PATH}")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)

CANONICAL_TRAIN = ART / "stage11663_web_canonical_renderer_package/web_canonical_train_support.jsonl"
CANONICAL_HELDOUT = ART / "stage11663_web_canonical_renderer_package/web_canonical_heldout.jsonl"
DECISION = ART / "stage11677_web_same_role_listwise_decision/web_same_role_listwise_decision.json"

LABELS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
TARGET_TASKS = {"symptom_localization", "minimal_fix_selection", "verifier_outcome", "patch_impact"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def option_role(option: dict[str, Any]) -> str:
    obj = option.get("canonical_candidate_object") if isinstance(option.get("canonical_candidate_object"), dict) else {}
    semantic = option.get("semantic_candidate") if isinstance(option.get("semantic_candidate"), dict) else {}
    return str(option.get("role") or obj.get("role") or semantic.get("role") or "")


def option_value(option: dict[str, Any]) -> str:
    obj = option.get("canonical_candidate_object") if isinstance(option.get("canonical_candidate_object"), dict) else {}
    semantic = option.get("semantic_candidate") if isinstance(option.get("semantic_candidate"), dict) else {}
    return str(obj.get("value") or semantic.get("canonical_value") or option.get("text") or option.get("value") or "")


def relabel_option(option: dict[str, Any], label: str) -> dict[str, Any]:
    updated = copy.deepcopy(option)
    updated["label"] = label
    if isinstance(updated.get("canonical_candidate_object"), dict):
        updated["canonical_candidate_object"]["candidate_id"] = label
    return updated


def same_role_target_options(row: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]] | None:
    target = str(row.get("bounded_choice_target_label") or row.get("target_text") or "")
    options = [opt for opt in row.get("opaque_options") or [] if isinstance(opt, dict)]
    by_label = {str(opt.get("label")): opt for opt in options}
    if target not in by_label:
        return None
    target_role = option_role(by_label[target])
    if not target_role or target_role == "abstain_insufficient_evidence":
        return None
    same_role = [opt for opt in options if option_role(opt) == target_role]
    if len(same_role) < 2:
        return None
    values = {option_value(opt) for opt in same_role}
    if len(values) < 2:
        return None
    return target, target_role, options


def shuffled_copy(row: dict[str, Any], *, variant_idx: int, target_label: str, target_role: str, options: list[dict[str, Any]]) -> dict[str, Any]:
    rng = random.Random(f"{row.get('row_id')}::{variant_idx}::stage11678")
    shuffled = copy.deepcopy(options)
    rng.shuffle(shuffled)
    relabeled = [relabel_option(option, LABELS[idx]) for idx, option in enumerate(shuffled)]
    old_to_new = {str(option.get("label")): LABELS[idx] for idx, option in enumerate(shuffled)}
    new_target = old_to_new[target_label]
    out = copy.deepcopy(row)
    out["row_id"] = f"{row['row_id']}::stage11678_same_role_identity_cf{variant_idx}"
    out["opaque_options"] = relabeled
    source = out.get("standalone_projection_source")
    if isinstance(source, dict):
        source = dict(source)
        source["opaque_options"] = copy.deepcopy(relabeled)
        out["standalone_projection_source"] = source
    out["bounded_choice_target_label"] = new_target
    out["target_text"] = new_target
    out["decoder_text"] = new_target
    out["target"] = {"bounded_choice_target_label": new_target, "decoder_text": new_target}
    out["semantic_target_value"] = option_value(next(opt for opt in relabeled if str(opt.get("label")) == new_target))
    out["split"] = "train"
    out["package_split"] = "train"
    out["split_component"] = "stage11678_same_role_identity_counterfactual_train"
    out["trainable_now"] = True
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["strict_eval_eligible_now"] = False
    out["stage11678_counterfactual_source_row_id"] = row.get("row_id")
    out["stage11678_counterfactual_variant"] = variant_idx
    out["stage11678_target_same_role"] = target_role
    # The manifest safety gate recognizes decoder_ce as the row-level trainability
    # signal; bounded-choice losses are enabled by CLI and use the same rows.
    out["loss_mask"] = {"decoder_ce": True, "bounded_choice_aux": True}
    anti = dict(out.get("anti_cheat") or {})
    anti.update(
        {
            "deterministic_option_shuffle": True,
            "stage11678_label_permutation": True,
            "same_role_identity_counterfactual": True,
            "gold_label_visible_before_options": False,
            "target_label_not_visible_before_options": True,
            "root_split_preserved_from_canonical_train": True,
        }
    )
    out["anti_cheat"] = anti
    prompt = renderer.render_prompt(out, relabeled)
    insertion = (
        "\nSAME_ROLE_DECISION_RULE\n"
        "Candidates can share the same role. Do not answer from role name alone. "
        "Choose the candidate identity whose artifact/value is directly supported by the visible source, verifier, and execution evidence.\n"
    )
    marker = "\nCANDIDATES\n"
    if marker in prompt:
        prompt = prompt.replace(marker, insertion + marker, 1)
    else:
        prompt = prompt + insertion
    out["prompt_text"] = prompt
    out["input_text"] = prompt
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    train_rows = load_jsonl(CANONICAL_TRAIN)
    heldout_rows = load_jsonl(CANONICAL_HELDOUT)
    decision = load_json(DECISION)
    miss_ids = {miss["row_id"] for miss in decision.get("remaining_canonical_misses", [])}
    protected_roots = {row.get("root_id") for row in heldout_rows if row.get("row_id") in miss_ids}

    selected: list[tuple[dict[str, Any], str, str, list[dict[str, Any]]]] = []
    skipped = Counter()
    for row in train_rows:
        if row.get("task_type") not in TARGET_TASKS:
            skipped["non_target_task"] += 1
            continue
        if row.get("root_id") in protected_roots:
            skipped["protected_heldout_root"] += 1
            continue
        parsed = same_role_target_options(row)
        if parsed is None:
            skipped["no_nontrivial_same_role_target"] += 1
            continue
        selected.append((row, *parsed))

    counterfactual_rows: list[dict[str, Any]] = []
    for row, target_label, target_role, options in selected:
        counterfactual_rows.append(shuffled_copy(row, variant_idx=0, target_label=target_label, target_role=target_role, options=options))
        counterfactual_rows.append(shuffled_copy(row, variant_idx=1, target_label=target_label, target_role=target_role, options=options))

    heldout_diag = []
    for row in heldout_rows:
        if row.get("row_id") in miss_ids:
            diag = copy.deepcopy(row)
            diag["split"] = "diagnostic"
            diag["package_split"] = "diagnostic"
            diag["split_component"] = "stage11678_sealed_remaining_canonical_miss_diagnostic"
            diag["trainable_now"] = False
            diag["train_support_only"] = False
            diag["strict_eval_eligible"] = False
            diag["strict_eval_eligible_now"] = False
            diag["stage11678_sealed_heldout_diagnostic"] = True
            heldout_diag.append(diag)

    train_root_ids = {row.get("root_id") for row in counterfactual_rows}
    diag_root_ids = {row.get("root_id") for row in heldout_diag}
    root_overlap = sorted(root for root in train_root_ids & diag_root_ids if root)
    role_counts = Counter(row.get("stage11678_target_same_role") for row in counterfactual_rows)
    task_counts = Counter(row.get("task_type") for row in counterfactual_rows)
    source_root_counts = Counter(row.get("root_id") for row in counterfactual_rows)
    label_counts = Counter(row.get("bounded_choice_target_label") for row in counterfactual_rows)
    gates = {
        "counterfactual_rows_nonzero": len(counterfactual_rows) > 0,
        "sealed_diag_rows_match_remaining_misses": len(heldout_diag) == len(miss_ids),
        "no_train_diag_root_overlap": not root_overlap,
        "all_train_rows_support_only": all(row.get("trainable_now") and not row.get("strict_eval_eligible_now") for row in counterfactual_rows),
        "all_diag_rows_not_trainable": all(not row.get("trainable_now") for row in heldout_diag),
        "all_counterfactual_rows_shuffled": all((row.get("anti_cheat") or {}).get("stage11678_label_permutation") for row in counterfactual_rows),
    }
    decision_label = "stage11678_ready_for_probe_request" if all(gates.values()) else "stage11678_blocked_package_gate_failure"
    write_jsonl(TRAIN_OUT, counterfactual_rows)
    write_jsonl(HELDOUT_DIAG, heldout_diag)
    summary = {
        "stage": 11678,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision_label,
        "train_counterfactual_rows": len(counterfactual_rows),
        "source_train_rows": len(selected),
        "sealed_remaining_miss_diagnostic_rows": len(heldout_diag),
        "protected_remaining_miss_roots": sorted(root for root in protected_roots if root),
        "root_overlap": root_overlap,
        "gates": gates,
        "skipped": dict(skipped),
        "train_counts": {
            "task_type": dict(task_counts),
            "target_same_role": dict(role_counts),
            "target_label": dict(label_counts),
            "unique_roots": len(source_root_counts),
            "top_roots": source_root_counts.most_common(20),
        },
        "source_artifacts": {
            "canonical_train": rel(CANONICAL_TRAIN),
            "canonical_heldout": rel(CANONICAL_HELDOUT),
            "stage11677_decision": rel(DECISION),
        },
        "outputs": {
            "train_counterfactual_rows": rel(TRAIN_OUT),
            "sealed_diagnostic_rows": rel(HELDOUT_DIAG),
            "summary": rel(PACKAGE),
        },
        "claim_boundary": [
            "These rows are train-support-only label-shuffled same-role candidate identity counterfactuals from canonical train roots.",
            "The remaining canonical misses are included only as sealed diagnostics and are not trainable.",
            "This package is not a frontier result; it is data geometry for a guarded probe.",
        ],
    }
    write_json(PACKAGE, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PACKAGE, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision_label, "gates": gates, "train_counterfactual_rows": len(counterfactual_rows), "sealed_diag_rows": len(heldout_diag), "train_counts": summary["train_counts"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
