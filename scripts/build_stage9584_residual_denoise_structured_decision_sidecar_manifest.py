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
STAGE = 9584
NAME = "stage9584_residual_denoise_structured_decision_sidecar_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9583_residual_denoise_decision_surface_collapse_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9575_residual_denoise_boundary_interleaved_manifest/residual_denoise_boundary_interleaved_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "residual_denoise_structured_decision_sidecar_manifest.jsonl"
CARD = OUT_DIR / "residual_denoise_structured_decision_sidecar_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_STRUCTURED_DECISION_SIDECAR_MANIFEST_STAGE9584.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

LOSS_KEYS = [
    "surface_role_ce",
    "repair_surface_ce",
    "build_mode_ce",
    "allowed_import_policy_ce",
    "blocked_import_policy_ce",
    "repo_dependency_policy_ce",
    "action_sequence_ce",
    "file_plan_ce",
    "symbol_binding_ce",
    "edit_localization_ce",
    "patch_operator_ce",
    "verifier_repair_ce",
    "suffix_choice_ce",
    "episode_repair_outcome_ce",
    "episode_failure_type_ce",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
    "episode_step_value_mse",
    "structured_aux",
    "decoder_ce",
    "denoise_ce",
    "runtime_reward",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def klass(row: dict[str, Any]) -> str:
    return str((row.get("target") or {}).get("contrast_class") or "UNKNOWN")


def suffix_choice(cls: str) -> str:
    if cls == "BOUNDARY":
        return "BOUNDARY_NEXT_TOKEN_REPAIR"
    if cls == "PREFIX":
        return "PREFIX_ONLY_REPAIR"
    raise ValueError(f"unsupported class: {cls}")


def structured_loss_mask() -> dict[str, bool]:
    return {key: key == "suffix_choice_ce" for key in LOSS_KEYS}


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
        failures.append("stage9583_not_passed")
    if (source.get("metrics") or {}).get("structured_decision_sidecar_required") is not True:
        failures.append("stage9583_sidecar_not_required")
    if len(rows) != 48:
        failures.append("source_manifest_row_count_not_48")

    patched: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        cls = klass(row)
        if cls not in {"BOUNDARY", "PREFIX"}:
            failures.append(f"unsupported_class:{cls}")
            continue
        new_row = json.loads(json.dumps(row))
        new_row["row_id"] = f"stage9584_sidecar_{idx:04d}_{str(row.get('row_id'))}"
        new_row["objective_family"] = "residual_denoise_structured_decision_sidecar"
        new_row["loss_mask"] = structured_loss_mask()
        new_row["decoder_text"] = ""
        model_input = new_row.setdefault("model_input", {})
        model_input.update(
            {
                "sidecar_decision_surface": "suffix_choice",
                "sidecar_decoder_rendering_closed": True,
                "sidecar_boundary_next_token_miss_observed": cls == "BOUNDARY",
                "sidecar_prefix_only_observed": cls == "PREFIX",
                "stage9584_structured_sidecar": True,
            }
        )
        target = new_row.setdefault("target", {})
        target["suffix_choice"] = suffix_choice(cls)
        target["structured_sidecar_field"] = "suffix_choice"
        target["decoder_text"] = ""
        target["label"] = suffix_choice(cls)
        patched.append(new_row)

    counts = Counter((row.get("split"), klass(row)) for row in patched)
    suffix_counts = Counter((row.get("target") or {}).get("suffix_choice") for row in patched)
    class_counts = Counter(klass(row) for row in patched)
    loss_counts = Counter(loss for row in patched for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    authority_rows = [row.get("row_id") for row in patched if any((row.get("authority") or {}).values())]
    decoder_text_rows = [row.get("row_id") for row in patched if (row.get("target") or {}).get("decoder_text") or row.get("decoder_text")]
    if class_counts != {"BOUNDARY": 24, "PREFIX": 24}:
        failures.append("class_counts_not_balanced")
    if suffix_counts != {"BOUNDARY_NEXT_TOKEN_REPAIR": 24, "PREFIX_ONLY_REPAIR": 24}:
        failures.append("suffix_choice_counts_not_balanced")
    if dict(loss_counts) != {"suffix_choice_ce": 48}:
        failures.append("loss_mask_not_suffix_choice_only")
    if authority_rows:
        failures.append("authority_rows_present")
    if decoder_text_rows:
        failures.append("decoder_text_rows_present")

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
        "class_counts": dict(sorted(class_counts.items())),
        "suffix_choice_counts": dict(sorted(suffix_counts.items())),
        "split_class_counts": {f"{split}:{cls}": count for (split, cls), count in sorted(counts.items())},
        "loss_counts": dict(sorted(loss_counts.items())),
        "authority_rows": len(authority_rows),
        "decoder_text_rows": len(decoder_text_rows),
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
        "decision": "Built a suffix_choice structured sidecar manifest for residual-denoise boundary-vs-prefix repair routing with decoder and denoise CE closed.",
        "next_best_step": "Run a capped target_100M structured_policy_probe with suffix_choice_ce only and audit sidecar exactness by split/class.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9584 Residual Denoise Structured Decision Sidecar Manifest", "", f"Passed: `{card['passed']}`", f"Rows: `{len(patched)}`", f"Suffix choice counts: `{dict(sorted(suffix_counts.items()))}`", "", "Only `suffix_choice_ce` is enabled. Decoder and denoise CE stay closed.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(patched), "suffix_choice_counts": dict(sorted(suffix_counts.items())), "failures": failures}, indent=2, sort_keys=True))
    if not card["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
