#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9587
NAME = "stage9587_residual_denoise_counterbalanced_sidecar_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9586_residual_denoise_sidecar_failure_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9584_residual_denoise_structured_decision_sidecar_manifest/residual_denoise_structured_decision_sidecar_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "residual_denoise_counterbalanced_sidecar_manifest.jsonl"
CARD = OUT_DIR / "residual_denoise_counterbalanced_sidecar_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_COUNTERBALANCED_SIDECAR_MANIFEST_STAGE9587.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def current_choice(row: dict[str, Any]) -> str:
    return str((row.get("target") or {}).get("suffix_choice") or "")


def opposite_choice(choice: str) -> str:
    if choice == "BOUNDARY_NEXT_TOKEN_REPAIR":
        return "PREFIX_ONLY_REPAIR"
    if choice == "PREFIX_ONLY_REPAIR":
        return "BOUNDARY_NEXT_TOKEN_REPAIR"
    raise ValueError(f"unsupported suffix choice: {choice}")


def choice_to_class(choice: str) -> str:
    return "BOUNDARY" if choice == "BOUNDARY_NEXT_TOKEN_REPAIR" else "PREFIX"


def apply_choice(row: dict[str, Any], choice: str) -> None:
    boundary = choice == "BOUNDARY_NEXT_TOKEN_REPAIR"
    target = row.setdefault("target", {})
    target["suffix_choice"] = choice
    target["label"] = choice
    target["contrast_class"] = choice_to_class(choice)
    target["structured_sidecar_field"] = "suffix_choice"
    target["decoder_text"] = ""
    row["decoder_text"] = ""
    row["language_group"] = row.get("language_family")
    model_input = row.setdefault("model_input", {})
    model_input.update(
        {
            "obs_boundary_relation": "boundary_miss" if boundary else "boundary_match",
            "obs_has_boundary_next_token_miss_reason": boundary,
            "obs_boundary_rank_bucket": "rank_counterbalanced_miss" if boundary else "rank_counterbalanced_match",
            "obs_failure_evidence_family": "prefix_and_boundary_miss_evidence" if boundary else "prefix_miss_evidence",
            "sidecar_boundary_next_token_miss_observed": boundary,
            "sidecar_prefix_only_observed": not boundary,
            "sidecar_counterbalanced_pair": True,
            "sidecar_decoder_rendering_closed": True,
            "stage9587_counterbalanced_sidecar": True,
        }
    )


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(SOURCE_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9586_not_passed")
    if (source.get("metrics") or {}).get("sidecar_not_ready_for_denoise_render_gate") is not True:
        failures.append("stage9586_missing_sidecar_failure")
    if len(rows) != 48:
        failures.append("source_manifest_row_count_not_48")

    patched: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        choice = current_choice(row)
        if choice not in {"BOUNDARY_NEXT_TOKEN_REPAIR", "PREFIX_ONLY_REPAIR"}:
            failures.append(f"unsupported_choice:{choice}")
            continue
        pair_id = f"stage9587_pair_{idx:04d}"
        original = json.loads(json.dumps(row))
        original["row_id"] = f"{pair_id}_observed_{str(row.get('row_id'))}"
        original["counterbalance_pair_id"] = pair_id
        original["counterbalance_variant"] = "observed"
        original["objective_family"] = "residual_denoise_counterbalanced_sidecar"
        apply_choice(original, choice)
        flipped = json.loads(json.dumps(row))
        flipped["row_id"] = f"{pair_id}_flipped_{str(row.get('row_id'))}"
        flipped["counterbalance_pair_id"] = pair_id
        flipped["counterbalance_variant"] = "flipped_verifier_observation"
        flipped["objective_family"] = "residual_denoise_counterbalanced_sidecar"
        apply_choice(flipped, opposite_choice(choice))
        patched.extend([original, flipped])

    suffix_counts = Counter((row.get("target") or {}).get("suffix_choice") for row in patched)
    split_suffix_counts = Counter((row.get("split"), (row.get("target") or {}).get("suffix_choice")) for row in patched)
    language_suffix_counts = Counter((row.get("language_family"), (row.get("target") or {}).get("suffix_choice")) for row in patched)
    variant_counts = Counter(row.get("counterbalance_variant") for row in patched)
    loss_counts = Counter(loss for row in patched for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    authority_rows = [row.get("row_id") for row in patched if any((row.get("authority") or {}).values())]
    decoder_text_rows = [row.get("row_id") for row in patched if (row.get("target") or {}).get("decoder_text") or row.get("decoder_text")]
    pair_counts = Counter(row.get("counterbalance_pair_id") for row in patched)
    bad_pairs = [pair for pair, count in pair_counts.items() if count != 2]

    if len(patched) != 96:
        failures.append("row_count_not_96")
    if suffix_counts != {"BOUNDARY_NEXT_TOKEN_REPAIR": 48, "PREFIX_ONLY_REPAIR": 48}:
        failures.append("suffix_choice_counts_not_balanced")
    if variant_counts != {"flipped_verifier_observation": 48, "observed": 48}:
        failures.append("variant_counts_not_balanced")
    if dict(loss_counts) != {"suffix_choice_ce": 96}:
        failures.append("loss_mask_not_suffix_choice_only")
    if authority_rows:
        failures.append("authority_rows_present")
    if decoder_text_rows:
        failures.append("decoder_text_rows_present")
    if bad_pairs:
        failures.append("bad_counterbalance_pairs")
    for (language, choice), count in language_suffix_counts.items():
        other = "PREFIX_ONLY_REPAIR" if choice == "BOUNDARY_NEXT_TOKEN_REPAIR" else "BOUNDARY_NEXT_TOKEN_REPAIR"
        if language_suffix_counts.get((language, other), 0) != count:
            failures.append(f"language_not_counterbalanced:{language}")
            break

    with MANIFEST.open("w", encoding="utf-8") as handle:
        for row in patched:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    card = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_sha256": sha256(MANIFEST),
        "rows": len(patched),
        "suffix_choice_counts": dict(sorted(suffix_counts.items())),
        "split_suffix_counts": {f"{split}:{choice}": count for (split, choice), count in sorted(split_suffix_counts.items())},
        "language_suffix_counts": {f"{language}:{choice}": count for (language, choice), count in sorted(language_suffix_counts.items())},
        "variant_counts": dict(sorted(variant_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "authority_rows": len(authority_rows),
        "decoder_text_rows": len(decoder_text_rows),
        "counterbalance_pairs": len(pair_counts),
        "model_execution_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **card},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built paired counterfactual sidecar rows so each original language/shell has both boundary-next-token and prefix-only suffix choices.",
        "next_best_step": "Run shortcut baselines for the counterbalanced sidecar manifest, then rerun the suffix_choice sidecar probe if non-verifier shortcuts are controlled.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9587 Residual Denoise Counterbalanced Sidecar Manifest", "", f"Passed: `{card['passed']}`", f"Rows: `{len(patched)}`", f"Suffix choice counts: `{dict(sorted(suffix_counts.items()))}`", "", "Each source row now has an observed and flipped verifier-observation pair. Only `suffix_choice_ce` is enabled.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(patched), "suffix_choice_counts": dict(sorted(suffix_counts.items())), "failures": failures}, indent=2, sort_keys=True))
    if not card["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
