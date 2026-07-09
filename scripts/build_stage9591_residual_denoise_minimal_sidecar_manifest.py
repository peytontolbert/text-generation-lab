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
STAGE = 9591
NAME = "stage9591_residual_denoise_minimal_sidecar_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9590_residual_denoise_counterbalanced_sidecar_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9587_residual_denoise_counterbalanced_sidecar_manifest/residual_denoise_counterbalanced_sidecar_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "residual_denoise_minimal_sidecar_manifest.jsonl"
CARD = OUT_DIR / "residual_denoise_minimal_sidecar_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_MINIMAL_SIDECAR_MANIFEST_STAGE9591.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LOSS_KEYS = ["surface_role_ce","repair_surface_ce","build_mode_ce","allowed_import_policy_ce","blocked_import_policy_ce","repo_dependency_policy_ce","action_sequence_ce","file_plan_ce","symbol_binding_ce","edit_localization_ce","patch_operator_ce","verifier_repair_ce","suffix_choice_ce","episode_repair_outcome_ce","episode_failure_type_ce","episode_boundary_match_ce","episode_target_prefix_match_ce","episode_step_value_mse","structured_aux","decoder_ce","denoise_ce","runtime_reward"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


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
        failures.append("stage9590_not_passed")
    if len(rows) != 96:
        failures.append("source_manifest_row_count_not_96")
    patched: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        choice = str(target.get("suffix_choice") or "")
        if choice not in {"BOUNDARY_NEXT_TOKEN_REPAIR", "PREFIX_ONLY_REPAIR"}:
            failures.append(f"unsupported_choice:{choice}")
            continue
        boundary = choice == "BOUNDARY_NEXT_TOKEN_REPAIR"
        new_row = {
            "row_id": f"stage9591_minimal_sidecar_{idx:04d}_{row.get('row_id')}",
            "split": row.get("split"),
            "language_family": row.get("language_family"),
            "route": "RESIDUAL_DENOISE_CANDIDATE_CLOSED",
            "objective_family": "residual_denoise_minimal_sidecar",
            "counterbalance_pair_id": row.get("counterbalance_pair_id"),
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": {key: key == "suffix_choice_ce" for key in LOSS_KEYS},
            "model_input": {
                "minimal_sidecar_surface": True,
                "verifier_boundary_next_token_miss": boundary,
                "verifier_prefix_only_repair": not boundary,
                "repair_route_family": "residual_suffix_continuation",
                "language_family": row.get("language_family"),
            },
            "target": {
                "suffix_choice": choice,
                "label": choice,
                "structured_sidecar_field": "suffix_choice",
                "decoder_text": "",
            },
            "decoder_text": "",
        }
        patched.append(new_row)

    counts = Counter((r.get("target") or {}).get("suffix_choice") for r in patched)
    split_counts = Counter((r.get("split"), (r.get("target") or {}).get("suffix_choice")) for r in patched)
    lang_counts = Counter((r.get("language_family"), (r.get("target") or {}).get("suffix_choice")) for r in patched)
    loss_counts = Counter(loss for row in patched for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    if counts != {"BOUNDARY_NEXT_TOKEN_REPAIR": 48, "PREFIX_ONLY_REPAIR": 48}:
        failures.append("suffix_choice_counts_not_balanced")
    if dict(loss_counts) != {"suffix_choice_ce": 96}:
        failures.append("loss_mask_not_suffix_choice_only")
    if any(any((row.get("authority") or {}).values()) for row in patched):
        failures.append("authority_rows_present")
    if any((row.get("target") or {}).get("decoder_text") or row.get("decoder_text") for row in patched):
        failures.append("decoder_text_rows_present")
    for (lang, choice), count in lang_counts.items():
        other = "PREFIX_ONLY_REPAIR" if choice == "BOUNDARY_NEXT_TOKEN_REPAIR" else "BOUNDARY_NEXT_TOKEN_REPAIR"
        if lang_counts.get((lang, other), 0) != count:
            failures.append(f"language_not_balanced:{lang}")
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
        "suffix_choice_counts": dict(sorted(counts.items())),
        "split_suffix_counts": {f"{split}:{choice}": count for (split, choice), count in sorted(split_counts.items())},
        "language_suffix_counts": {f"{lang}:{choice}": count for (lang, choice), count in sorted(lang_counts.items())},
        "loss_counts": dict(sorted(loss_counts.items())),
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
        "decision": "Built a minimal verifier-evidence sidecar manifest that removes noisy residual context keys and keeps only suffix_choice CE.",
        "next_best_step": "Run shortcut baselines on the minimal sidecar manifest, then rerun the closed suffix_choice sidecar probe if clean.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9591 Residual Denoise Minimal Sidecar Manifest", "", f"Passed: `{card['passed']}`", f"Rows: `{len(patched)}`", "", "The model input contains only language, route family, and verifier decision booleans. Only `suffix_choice_ce` is enabled.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(patched), "failures": failures}, indent=2, sort_keys=True))
    if not card["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
