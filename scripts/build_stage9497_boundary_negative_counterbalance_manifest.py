#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9497
NAME = "stage9497_boundary_negative_counterbalance_manifest"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9494_boundary_verifier_isolated_manifest/boundary_verifier_isolated_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9496_boundary_verifier_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9497_boundary_negative_counterbalance_manifest"
MANIFEST = OUT_DIR / "boundary_negative_counterbalance_manifest.jsonl"
CARD = OUT_DIR / "boundary_negative_counterbalance_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDARY_NEGATIVE_COUNTERBALANCE_MANIFEST_STAGE9497.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TARGET_LOSS = "episode_boundary_match_ce"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def boundary_label(row: dict) -> bool:
    return bool(((row.get("episode_transition") or {}).get("observation_t") or {}).get("boundary_next_token_match"))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source_summary = load_json(SOURCE_SUMMARY)
    source_rows = load_jsonl(SOURCE_MANIFEST)
    failures: list[str] = []

    by_split_label: dict[tuple[str, bool], list[dict]] = defaultdict(list)
    for row in source_rows:
        by_split_label[(str(row.get("split", "other")), boundary_label(row))].append(row)

    selected: list[dict] = []
    for split in ["train", "eval", "strict_eval"]:
        false_rows = by_split_label[(split, False)]
        true_rows = by_split_label[(split, True)]
        take = min(len(false_rows), len(true_rows))
        selected.extend(false_rows[:take])
        selected.extend(true_rows[:take])

    rows: list[dict] = []
    for index, row in enumerate(selected):
        patched = copy.deepcopy(row)
        obs = (patched.get("episode_transition") or {}).get("observation_t") or {}
        nxt = (patched.get("episode_transition") or {}).get("state_t_plus_1") or {}
        generated = str(obs.get("generated_text") or "")
        reference = str(nxt.get("decoder_text") or "")
        patched["row_id"] = f"stage9497_boundary_counterbalance_{index:04d}"
        patched["source_stage9494_row_id"] = row.get("row_id")
        patched["objective_family"] = "episode_boundary_match_counterbalanced"
        patched["route"] = "KEEP_EPISODE_BOUNDARY_COUNTERBALANCED"
        model_input = patched.get("model_input") if isinstance(patched.get("model_input"), dict) else {}
        model_input.update({
            "boundary_counterbalance_phase": True,
            "generated_output_preview": generated,
            "reference_output_preview": reference,
            "generated_reference_equal": generated == reference,
            "generated_reference_prefix_equal": reference.startswith(generated) or generated.startswith(reference),
            "generated_output_chars": len(generated),
            "reference_output_chars": len(reference),
            "char_length_delta_abs": abs(len(reference) - len(generated)),
            "boundary_expected_rank_observed": obs.get("boundary_expected_rank"),
            "generation_stopped_on_eos": bool(obs.get("stopped_on_eos")),
            "residual_reason_count_observed": len(obs.get("residual_reasons") or []),
        })
        patched["model_input"] = model_input
        rows.append(patched)

    split_counts = Counter(str(row.get("split", "other")) for row in rows)
    label_counts = Counter(f"{row.get('split')}::{boundary_label(row)}" for row in rows)
    loss_counts = Counter(k for row in rows for k, value in (row.get("loss_mask") or {}).items() if value)
    if source_summary.get("metrics", {}).get("safety_passed") is not True:
        failures.append("source_stage9496_not_safety_passed")
    if loss_counts != Counter({TARGET_LOSS: len(rows)}):
        failures.append("unexpected_loss_counts")
    for split in ["train", "eval", "strict_eval"]:
        if label_counts[f"{split}::False"] != label_counts[f"{split}::True"]:
            failures.append(f"split_not_balanced:{split}")
    if any(any((row.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED) for row in rows):
        failures.append("authority_rows_present")

    card = {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "source_rows": len(source_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "design_note": "Counterbalanced isolated boundary verifier rows after Stage9496 high-confidence false-negative boundary failures.",
        "authority": dict(AUTHORITY_CLOSED),
    }
    write_jsonl(MANIFEST, rows)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **card},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built balanced boundary-negative repair manifest with deterministic comparison features; no execution authorized by this stage.",
        "next_best_step": "Run contract-only preflight for the counterbalanced boundary verifier probe, then execute only if the preflight passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9497 Boundary Negative Counterbalance Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{card['rows']}`",
        f"Splits: `{card['split_counts']}`",
        f"Label counts: `{card['label_counts']}`",
        "",
        "This manifest balances true/false boundary labels per split and adds deterministic comparison features to `model_input`.",
        "",
        "Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "rows": len(rows), "split_counts": card["split_counts"], "label_counts": card["label_counts"], "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
