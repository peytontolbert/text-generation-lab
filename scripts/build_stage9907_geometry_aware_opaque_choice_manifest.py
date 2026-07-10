#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9907
NAME = "stage9907_geometry_aware_opaque_choice_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9893_current_margin_locality_signal_label_remap_manifest/current_margin_locality_signal_label_remap_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "geometry_aware_opaque_choice_manifest.jsonl"
AUDIT = OUT_DIR / "geometry_aware_opaque_choice_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GEOMETRY_AWARE_OPAQUE_CHOICE_MANIFEST_STAGE9907.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
SPLITS = ["train", "eval", "strict_eval"]
OLD_LABELS = ["M", "R", "T", "Z"]
NEW_LABELS = ["A", "B", "C", "D"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


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


def _bucket_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("language_family") or ""), str(row.get("split") or ""))].append(row)
    for key in grouped:
        grouped[key] = sorted(grouped[key], key=lambda row: str(row.get("row_id") or ""))
    return grouped


def _order_for_bucket_row(old_target: str, desired_target: str, variant: int) -> list[str]:
    remaining_old = [label for label in OLD_LABELS if label != old_target]
    shift = variant % len(remaining_old)
    if shift == 0:
        shift = 1
    rotated_old = remaining_old[shift:] + remaining_old[:shift]
    order_by_new: dict[str, str] = {desired_target: old_target}
    remaining_new = [label for label in NEW_LABELS if label != desired_target]
    for new_label, old_label in zip(remaining_new, rotated_old):
        order_by_new[new_label] = old_label
    return [order_by_new[new_label] for new_label in NEW_LABELS]


def _order_to_mapping(order: list[str]) -> dict[str, str]:
    return {old: NEW_LABELS[idx] for idx, old in enumerate(order)}


def _inverse_mapping(mapping: dict[str, str]) -> dict[str, str]:
    return {new: old for old, new in mapping.items()}


def _permute_choices(choices: list[str], mapping: dict[str, str]) -> list[str]:
    original_payloads: dict[str, str] = {}
    for entry in choices:
        text = str(entry)
        prefix, payload = text.split(":", 1)
        label = prefix.replace("option ", "").strip()
        original_payloads[label] = payload.strip()
    inverse = _inverse_mapping(mapping)
    return [f"option {new_label}: {original_payloads[inverse[new_label]]}" for new_label in NEW_LABELS]


def _remap_row(row: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    cloned = json.loads(json.dumps(row))
    input_state = cloned.get("input_state") if isinstance(cloned.get("input_state"), dict) else {}
    choices = input_state.get("candidate_choices") if isinstance(input_state.get("candidate_choices"), list) else []
    input_state["candidate_choices"] = _permute_choices(choices, mapping)
    cloned["input_state"] = input_state

    target = cloned.get("target") if isinstance(cloned.get("target"), dict) else {}
    for key in ["decoder_text", "edit_localization", "target_ref"]:
        if isinstance(target.get(key), str) and target.get(key) in mapping:
            target[key] = mapping[str(target[key])]
    cloned["target"] = target

    clean = cloned.get("clean_state") if isinstance(cloned.get("clean_state"), dict) else {}
    for key in ["edit_localization", "edit_localization_target"]:
        if isinstance(clean.get(key), str) and clean.get(key) in mapping:
            clean[key] = mapping[str(clean[key])]
    cloned["clean_state"] = clean

    if isinstance(cloned.get("edit_localization_target"), str) and cloned.get("edit_localization_target") in mapping:
        cloned["edit_localization_target"] = mapping[str(cloned.get("edit_localization_target"))]
    if isinstance(cloned.get("edit_localization"), str) and cloned.get("edit_localization") in mapping:
        cloned["edit_localization"] = mapping[str(cloned.get("edit_localization"))]

    anti = cloned.get("anti_cheat") if isinstance(cloned.get("anti_cheat"), dict) else {}
    anti["stage9907_opaque_choice_map"] = {old: mapping[old] for old in OLD_LABELS}
    anti["stage9907_opaque_choice_inventory"] = list(NEW_LABELS)
    anti["stage9907_hides_global_label_identity"] = True
    cloned["anti_cheat"] = anti
    cloned["choice_permutation_stage"] = STAGE
    cloned["choice_permutation_map"] = {old: mapping[old] for old in OLD_LABELS}
    return cloned


def build_rows() -> list[dict[str, Any]]:
    rows = load_jsonl(SOURCE)
    grouped = _bucket_rows(rows)
    output: list[dict[str, Any]] = []
    for lang in LANGS:
        for split in SPLITS:
            bucket = grouped.get((lang, split), [])
            if len(bucket) != 4:
                raise ValueError(f"expected 4 rows in {lang}:{split}, found {len(bucket)}")
            seen_orders: set[tuple[str, ...]] = set()
            for idx, row in enumerate(bucket):
                target = str(((row.get("target") or {}).get("decoder_text") or ""))
                desired_target = NEW_LABELS[idx]
                selected_order: list[str] | None = None
                for extra in range(1, len(NEW_LABELS) + 3):
                    candidate_order = _order_for_bucket_row(target, desired_target, idx + extra)
                    key = tuple(candidate_order)
                    if key not in seen_orders:
                        selected_order = candidate_order
                        seen_orders.add(key)
                        break
                if selected_order is None:
                    raise ValueError(f"could not find unique permutation for {lang}:{split}:{row.get('row_id')}")
                mapping = _order_to_mapping(selected_order)
                output.append(_remap_row(row, mapping))
    return output


def build_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    split_counts = Counter(str(row.get("split") or "") for row in rows)
    grouped = _bucket_rows(rows)
    bucket_cards: dict[str, dict[str, Any]] = {}
    for lang in LANGS:
        for split in SPLITS:
            bucket = grouped.get((lang, split), [])
            labels = sorted({str(((row.get("target") or {}).get("decoder_text") or "")) for row in bucket})
            perms = {json.dumps(row.get("choice_permutation_map") or {}, sort_keys=True) for row in bucket}
            choice_lists = {tuple((row.get("input_state") or {}).get("candidate_choices") or []) for row in bucket}
            bucket_cards[f"{lang}:{split}"] = {
                "rows": len(bucket),
                "label_count": len(labels),
                "permutation_count": len(perms),
                "choice_list_unique_count": len(choice_lists),
            }
            if len(bucket) != 4:
                failures.append(f"bucket_rows_mismatch:{lang}:{split}:{len(bucket)}")
            if labels != NEW_LABELS:
                failures.append(f"bucket_labels_mismatch:{lang}:{split}:{labels}")
            if len(perms) != 4:
                failures.append(f"bucket_permutation_mismatch:{lang}:{split}:{len(perms)}")
        if split_counts != {"train": 16, "eval": 16, "strict_eval": 16}:
            failures.append(f"split_counts_mismatch:{dict(sorted(split_counts.items()))}")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "bucket_cards": bucket_cards,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    write_jsonl(MANIFEST, rows)
    audit = build_audit(rows)
    write_json(AUDIT, audit)
    next_step = "Run a fresh target-100M probe and same-surface Gemma comparison on this opaque-choice geometry-aware packet without exposing the global valid-label list in the prompt."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "rows": audit["rows"], "split_counts": audit["split_counts"], "failures": audit["failures"]},
        "artifacts": {
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Built a geometry-aware opaque-choice manifest from the current Stage9893 packet, permuting the local option-to-semantic mapping independently per row so same-surface evaluation no longer relies on a globally exposed label identity.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9907 Geometry-Aware Opaque Choice Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Split counts: `{audit['split_counts']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "rows": audit["rows"], "split_counts": audit["split_counts"], "failures": audit["failures"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
