#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9844
NAME = "stage9844_restored_counterfactual_probe_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9828_current_winner_stronger_counterfactual_challenge/current_winner_stronger_counterfactual_challenge.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "restored_counterfactual_probe_manifest.jsonl"
AUDIT = OUT_DIR / "restored_counterfactual_probe_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESTORED_COUNTERFACTUAL_PROBE_MANIFEST_STAGE9844.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
TARGET_SPLITS = ["train", "eval", "strict_eval"]
LABELS = ["A", "B", "C", "D", "E"]
ROLE_TO_SPLIT = {
    "positive_original": "train",
    "evidence_removed": "eval",
    "contradictory_evidence": "strict_eval",
}
OPTION_RE = re.compile(r"^option ([A-E]):\s*(.+)$")
INLINE_OPTION_RE = re.compile(r"option ([A-E])")


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


def _order_to_mapping(order: list[str]) -> dict[str, str]:
    return {old: LABELS[idx] for idx, old in enumerate(order)}


def _inverse_mapping(mapping: dict[str, str]) -> dict[str, str]:
    return {new: old for old, new in mapping.items()}


def _order_for_bucket_row(old_target: str, desired_target: str, variant: int) -> list[str]:
    remaining_old = [label for label in LABELS if label != old_target]
    shift = variant % len(remaining_old)
    if shift == 0:
        shift = 1
    rotated_old = remaining_old[shift:] + remaining_old[:shift]
    order_by_new: dict[str, str] = {desired_target: old_target}
    remaining_new = [label for label in LABELS if label != desired_target]
    for new_label, old_label in zip(remaining_new, rotated_old):
        order_by_new[new_label] = old_label
    return [order_by_new[new_label] for new_label in LABELS]


def _permute_candidate_choices(choices: list[str], mapping: dict[str, str]) -> list[str]:
    original_payloads: dict[str, str] = {}
    for entry in choices:
        match = OPTION_RE.match(str(entry))
        if not match:
            raise ValueError(f"unrecognized candidate choice: {entry}")
        original_payloads[match.group(1)] = match.group(2)
    inverse = _inverse_mapping(mapping)
    return [f"option {new_label}: {original_payloads[inverse[new_label]]}" for new_label in LABELS]


def _remap_inline_options(text: str, mapping: dict[str, str]) -> str:
    return INLINE_OPTION_RE.sub(lambda m: f"option {mapping[m.group(1)]}", text)


def _permute_and_assign(row: dict[str, Any], mapping: dict[str, str], split: str) -> dict[str, Any]:
    cloned = json.loads(json.dumps(row))
    cloned["split"] = split
    input_state = cloned.get("input_state") if isinstance(cloned.get("input_state"), dict) else {}
    choices = input_state.get("candidate_choices") if isinstance(input_state.get("candidate_choices"), list) else []
    input_state["candidate_choices"] = _permute_candidate_choices(choices, mapping)
    for key in ["task_observation", "visible_locality_evidence", "web_surface_disambiguator"]:
        if isinstance(input_state.get(key), str):
            input_state[key] = _remap_inline_options(str(input_state.get(key) or ""), mapping)
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

    if isinstance(cloned.get("counterfactual_wrong_label"), str) and cloned.get("counterfactual_wrong_label") in mapping:
        cloned["counterfactual_wrong_label"] = mapping[str(cloned.get("counterfactual_wrong_label"))]
    cloned["choice_permutation_stage"] = STAGE
    cloned["choice_permutation_map"] = {old: mapping[old] for old in LABELS}
    cloned["choice_permutation_order"] = [mapping[old] for old in LABELS]
    cloned["restored_counterfactual_probe_stage"] = STAGE
    return cloned


def build_rows() -> list[dict[str, Any]]:
    source_rows = load_jsonl(SOURCE)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        lang = str(row.get("language_family") or "")
        role = str(row.get("counterfactual_role") or "")
        if role in ROLE_TO_SPLIT:
            grouped[(lang, role)].append(row)
    for key in grouped:
        grouped[key] = sorted(grouped[key], key=lambda row: str(row.get("row_id") or ""))

    output: list[dict[str, Any]] = []
    for lang in LANGS:
        for role, split in ROLE_TO_SPLIT.items():
            bucket = grouped.get((lang, role), [])
            if len(bucket) != 5:
                raise ValueError(f"expected 5 rows in {lang}:{role}, found {len(bucket)}")
            seen_orders: set[tuple[str, ...]] = set()
            for idx, row in enumerate(bucket):
                original_target = str(((row.get("target") or {}).get("decoder_text") or ""))
                desired_target = LABELS[idx]
                selected_order: list[str] | None = None
                for extra in range(1, len(LABELS) + 2):
                    candidate_order = _order_for_bucket_row(original_target, desired_target, idx + extra)
                    candidate_key = tuple(candidate_order)
                    if candidate_key not in seen_orders:
                        selected_order = candidate_order
                        seen_orders.add(candidate_key)
                        break
                if selected_order is None:
                    raise ValueError(f"could not find unique permutation for {lang}:{role}:{row.get('row_id')}")
                mapping = _order_to_mapping(selected_order)
                output.append(_permute_and_assign(row, mapping, split))
    return output


def _safe_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
    return (
        state.get("task_observation"),
        state.get("visible_locality_evidence"),
        state.get("file_extension"),
        state.get("context_config_visible"),
        state.get("context_entrypoint_visible"),
        state.get("context_symbol_names_visible"),
        state.get("context_tests_visible"),
    )


def build_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    split_counts = Counter(str(row.get("split") or "") for row in rows)
    role_counts = Counter(str(row.get("counterfactual_role") or "") for row in rows)
    failures: list[str] = []
    if len(rows) != 60:
        failures.append(f"rows_not_60:{len(rows)}")
    if split_counts != {"train": 20, "eval": 20, "strict_eval": 20}:
        failures.append(f"split_counts_mismatch:{dict(sorted(split_counts.items()))}")
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("language_family") or ""), str(row.get("split") or ""))].append(row)

    bucket_cards: dict[str, dict[str, Any]] = {}
    for lang in LANGS:
        for split in TARGET_SPLITS:
            bucket = sorted(grouped.get((lang, split), []), key=lambda row: str(row.get("row_id") or ""))
            labels = sorted({str(((row.get("target") or {}).get("decoder_text") or "")) for row in bucket})
            signatures = {_safe_signature(row) for row in bucket}
            permutations = {json.dumps(row.get("choice_permutation_map") or {}, sort_keys=True) for row in bucket}
            key = f"{lang}:{split}"
            bucket_cards[key] = {
                "rows": len(bucket),
                "label_count": len(labels),
                "safe_signature_unique_count": len(signatures),
                "permutation_count": len(permutations),
                "roles": sorted({str(row.get("counterfactual_role") or "") for row in bucket}),
                "surface_separates_labels": len(labels) == 5 and len(signatures) == 5,
            }
            if len(bucket) != 5:
                failures.append(f"bucket_rows_mismatch:{key}:{len(bucket)}")

    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "role_counts": dict(sorted(role_counts.items())),
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
    next_step = "Run the restored evidence-removed and contradictory-evidence probe through the direct 100M loop and the same-surface Gemma runner so the missing anti-cheat families are measured instead of inferred."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit, "failures": audit["failures"]},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Restored the stronger ablation-style and contradictory-evidence counterfactual obligations from the stage9828 challenge bank into a trainer-compatible multilingual execution manifest while preserving per-bucket choice permutation.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9844 Restored Counterfactual Probe Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Split counts: `{audit['split_counts']}`",
                f"Role counts: `{audit['role_counts']}`",
                "",
                "This stage restores evidence-removed and contradictory-evidence rows that were intentionally dropped from the earlier trainer execution manifest, while still preventing fixed A-E semantic shortcuts inside each bucket.",
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "rows": audit["rows"], "split_counts": audit["split_counts"], "role_counts": audit["role_counts"]}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
