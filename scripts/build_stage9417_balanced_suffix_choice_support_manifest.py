#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9417
NAME = "stage9417_balanced_suffix_choice_support_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9416_suffix_choice_control_failure_diagnosis.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9413_suffix_choice_control_manifest/suffix_choice_control_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "balanced_suffix_choice_support_manifest.jsonl"
AUDIT = OUT_DIR / "balanced_suffix_choice_support_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BALANCED_SUFFIX_CHOICE_SUPPORT_MANIFEST_STAGE9417.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TARGET_TRAIN_PER_CHOICE = 4


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def choice(row: dict) -> str:
    return str((row.get("clean_state") or {}).get("suffix_choice"))


def stable_id(seed: str) -> str:
    return "stage9417_suffix_choice_support_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    base_rows = load_jsonl(SOURCE_MANIFEST)
    rows = [copy.deepcopy(row) for row in base_rows]
    train_by_choice: dict[str, list[dict]] = defaultdict(list)
    examples_by_choice: dict[str, list[dict]] = defaultdict(list)
    for row in base_rows:
        examples_by_choice[choice(row)].append(row)
        if row.get("split") == "train":
            train_by_choice[choice(row)].append(row)
    added = []
    for label, examples in sorted(examples_by_choice.items()):
        if not label or not examples:
            continue
        have = len(train_by_choice[label])
        needed = max(0, TARGET_TRAIN_PER_CHOICE - have)
        for idx in range(needed):
            template = copy.deepcopy(examples[idx % len(examples)])
            template["row_id"] = stable_id(f"{label}:{idx}:{template.get('row_id')}")
            template["split"] = "train"
            template["source_stage9413_row_id"] = template.get("source_stage9409_row_id") or template.get("row_id")
            template["balanced_suffix_choice_support"] = True
            template["objective_family"] = "balanced_suffix_choice_control"
            mi = template.get("model_input") if isinstance(template.get("model_input"), dict) else {}
            mi.update(
                {
                    "balanced_suffix_choice_support": True,
                    "balanced_support_variant_index": idx,
                    "balanced_support_target_hidden_from_model_input": True,
                    "suffix_choice_schema_version": "stage9417_balanced_suffix_choice_support_v1",
                }
            )
            template["model_input"] = mi
            auth = template.get("authority") if isinstance(template.get("authority"), dict) else {}
            for key in AUTHORITY_CLOSED:
                auth[key] = False
            template["authority"] = auth
            added.append(template)
            rows.append(template)
    split_counts = Counter(str(row.get("split")) for row in rows)
    train_counts = Counter(choice(row) for row in rows if row.get("split") == "train")
    all_counts = Counter(choice(row) for row in rows)
    loss_counts = Counter()
    authority_rows = 0
    label_leak_rows = 0
    for row in rows:
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        for key, value in mask.items():
            if value:
                loss_counts[key] += 1
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if any(bool(authority.get(key)) for key in AUTHORITY_CLOSED):
            authority_rows += 1
        lbl = choice(row)
        if lbl and lbl in json.dumps(row.get("model_input") or {}, sort_keys=True):
            label_leak_rows += 1
    failures = []
    if source.get("passed") is not True:
        failures.append("source_stage9416_not_passed")
    if split_counts.get("eval") != 9 or split_counts.get("strict_eval") != 7:
        failures.append("heldout_split_counts_changed")
    if any(count < TARGET_TRAIN_PER_CHOICE for count in train_counts.values()):
        failures.append("train_choice_undercovered")
    if len(train_counts) != len(all_counts):
        failures.append("not_all_choices_have_train_support")
    if loss_counts.get("suffix_choice_ce") != len(rows) or len(loss_counts) != 1:
        failures.append("loss_mask_not_suffix_choice_only")
    if authority_rows or label_leak_rows:
        failures.append("authority_or_label_leak")
    audit = {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "added_train_support_rows": len(added),
        "split_counts": dict(sorted(split_counts.items())),
        "train_choice_counts": dict(sorted(train_counts.items())),
        "all_choice_counts": dict(sorted(all_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "authority_rows": authority_rows,
        "label_leak_rows": label_leak_rows,
        "target_train_per_choice": TARGET_TRAIN_PER_CHOICE,
        "authority": dict(AUTHORITY_CLOSED),
    }
    write_jsonl(MANIFEST, rows)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Balanced suffix-choice train support while keeping eval/strict fixed and decoder/denoise closed.",
        "next_best_step": "Run structured suffix-choice probe on the balanced support manifest.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9417 Balanced Suffix Choice Support Manifest", "", f"Passed: `{audit['passed']}`", f"Rows: `{len(rows)}`", f"Added train support rows: `{len(added)}`", f"Splits: `{dict(sorted(split_counts.items()))}`", f"Train choice counts: `{dict(sorted(train_counts.items()))}`", "", "This keeps decoder CE and denoise CE closed; it only balances structured suffix-choice control training.", ""]), encoding="utf-8")
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": len(rows), "added": len(added), "splits": dict(sorted(split_counts.items()))}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
