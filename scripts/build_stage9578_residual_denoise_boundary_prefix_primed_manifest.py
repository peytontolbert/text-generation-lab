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
STAGE = 9578
NAME = "stage9578_residual_denoise_boundary_prefix_primed_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9577_residual_denoise_boundary_discriminator_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9575_residual_denoise_boundary_interleaved_manifest/residual_denoise_boundary_interleaved_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "residual_denoise_boundary_prefix_primed_manifest.jsonl"
CARD = OUT_DIR / "residual_denoise_boundary_prefix_primed_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_BOUNDARY_PREFIX_PRIMED_MANIFEST_STAGE9578.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

GENERATION_PREFIX = "REPAIR_SCOPE="


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


def target_text(cls: str) -> str:
    if cls == "BOUNDARY":
        return "REPAIR_SCOPE=BOUNDARY | VERIFY_OBS=boundary_next_token_miss | ACTION=repair_suffix_continuation"
    if cls == "PREFIX":
        return "REPAIR_SCOPE=PREFIX | VERIFY_OBS=target_prefix_miss | ACTION=repair_suffix_continuation"
    raise ValueError(f"unsupported contrast class: {cls}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(SOURCE_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9577_not_passed")
    metrics = source.get("metrics") or {}
    if metrics.get("evidence_gate_passed") is not True:
        failures.append("stage9577_evidence_gate_not_passed")
    if metrics.get("learned_collapse_confirmed") is not True:
        failures.append("stage9577_did_not_confirm_learned_collapse")
    if len(rows) != 48:
        failures.append("source_manifest_row_count_not_48")

    patched: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        cls = klass(row)
        if cls not in {"BOUNDARY", "PREFIX"}:
            failures.append(f"unsupported_class:{cls}")
            continue
        new_row = json.loads(json.dumps(row))
        new_row["row_id"] = f"stage9578_prefix_primed_{idx:04d}_{str(row.get('row_id'))}"
        model_input = new_row.setdefault("model_input", {})
        boundary_miss = cls == "BOUNDARY"
        model_input.update(
            {
                "repair_decision_prefix": GENERATION_PREFIX,
                "obs_boundary_next_token_miss_observed": boundary_miss,
                "obs_prefix_only_scope_observed": not boundary_miss,
                "obs_boundary_repair_signal": "boundary_next_token_miss_observed" if boundary_miss else "boundary_next_token_match_observed",
                "obs_repair_scope_evidence": "prefix_and_boundary_residual" if boundary_miss else "prefix_only_residual",
                "obs_required_repair_scope_family": "boundary_token_scope" if boundary_miss else "prefix_scope",
                "stage9578_prefix_primed_target_surface": True,
            }
        )
        target = new_row.setdefault("target", {})
        target["decoder_text"] = target_text(cls)
        target["label"] = target_text(cls)
        target["rendered_from"] = ["stage9578_prefix_primed_boundary_observation"]
        target["generation_prefix"] = GENERATION_PREFIX
        target["class_token_after_prefix"] = cls
        patched.append(new_row)

    counts = Counter((row.get("split"), klass(row)) for row in patched)
    class_counts = Counter(klass(row) for row in patched)
    prefix_count = sum(1 for row in patched if (row.get("model_input") or {}).get("repair_decision_prefix") == GENERATION_PREFIX)
    target_prefix_count = sum(1 for row in patched if str((row.get("target") or {}).get("decoder_text") or "").startswith(GENERATION_PREFIX))
    loss_counts = Counter(loss for row in patched for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    authority_rows = [row.get("row_id") for row in patched if any((row.get("authority") or {}).values())]
    copied_target_rows = [
        row.get("row_id")
        for row in patched
        if str((row.get("target") or {}).get("decoder_text") or "") in json.dumps(row.get("model_input") or {}, sort_keys=True)
    ]
    if class_counts != {"BOUNDARY": 24, "PREFIX": 24}:
        failures.append("class_counts_not_balanced")
    if prefix_count != len(patched):
        failures.append("generation_prefix_missing")
    if target_prefix_count != len(patched):
        failures.append("target_prefix_missing")
    if dict(loss_counts) != {"denoise_ce": 48}:
        failures.append("loss_mask_not_denoise_only")
    if authority_rows:
        failures.append("authority_rows_present")
    if copied_target_rows:
        failures.append("full_target_text_copied_into_model_input")

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
        "split_class_counts": {f"{split}:{cls}": count for (split, cls), count in sorted(counts.items())},
        "generation_prefix": GENERATION_PREFIX,
        "generation_prefix_field": "model_input.repair_decision_prefix",
        "target_prefix_rows": target_prefix_count,
        "loss_counts": dict(sorted(loss_counts.items())),
        "authority_rows": len(authority_rows),
        "copied_target_rows": len(copied_target_rows),
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
        "decision": "Converted the residual-denoise boundary contrast surface to a prefix-primed target so the next probe measures the class token after REPAIR_SCOPE=.",
        "next_best_step": "Run a contract-only audit and capped target_100M denoise probe with --generation-prefix-field model_input.repair_decision_prefix, then audit boundary-token recall.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9578 Residual Denoise Boundary Prefix-Primed Manifest",
                "",
                f"Passed: `{card['passed']}`",
                f"Rows: `{len(patched)}`",
                f"Class counts: `{dict(sorted(class_counts.items()))}`",
                f"Generation prefix field: `{card['generation_prefix_field']}`",
                "",
                "The target now starts with a shared `REPAIR_SCOPE=` prefix. The next generated token is the boundary-vs-prefix decision.",
                "",
                "Authorities remain closed and the only enabled loss is `denoise_ce`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(patched), "class_counts": dict(sorted(class_counts.items())), "failures": failures}, indent=2, sort_keys=True))
    if not card["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
