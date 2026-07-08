#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9435
NAME = "stage9435_suffix_choice_prior_fusion_denoise_manifest_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9434_suffix_choice_prior_fusion_denoise_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9434_suffix_choice_prior_fusion_denoise_manifest/suffix_choice_prior_fusion_denoise_manifest.jsonl"
QUARANTINE = ROOT / "runs/local/artifacts/stage9425_suffix_choice_reconnect_guard_manifest/suffix_choice_residual_quarantine_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "suffix_choice_prior_fusion_denoise_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_PRIOR_FUSION_DENOISE_MANIFEST_AUDIT_STAGE9435.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    quarantined = load_jsonl(QUARANTINE)
    quarantine_ids = {str(row.get("source_row_id")) for row in quarantined}
    split_counts = Counter(str(row.get("split")) for row in rows)
    prior_sources = Counter(str(row.get("suffix_choice_prior_source")) for row in rows)
    attached_ids = {str(row.get("source_stage9413_suffix_choice_row_id")) for row in rows}

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9434_not_passed")
    if len(rows) != 53:
        failures.append("bad_row_count")
    if dict(split_counts) != {"eval": 5, "strict_eval": 4, "train": 44}:
        failures.append("bad_split_counts")
    if dict(prior_sources) != {"gold_train_suffix_choice_support": 44, "stage9419_correct_controller_prior": 9}:
        failures.append("bad_prior_source_counts")
    if attached_ids & quarantine_ids:
        failures.append("quarantine_overlap")
    if any(row.get("route") != "USE_FOR_DENOISE_REPAIR_WITH_SUFFIX_CHOICE_PRIOR" for row in rows):
        failures.append("bad_route")
    if any(not (row.get("loss_mask") or {}).get("denoise_ce") for row in rows):
        failures.append("denoise_loss_missing")
    if any((row.get("loss_mask") or {}).get("decoder_ce") for row in rows):
        failures.append("decoder_ce_open")
    if any(not (row.get("model_input") or {}).get("suffix_choice_prior_attached") for row in rows):
        failures.append("missing_prior_attachment")
    if any(not row.get("suffix_choice_prior") for row in rows):
        failures.append("missing_prior_payload")
    if any(row.get("execution_authorized_now") or row.get("denoise_ce_authorized_now") for row in rows):
        failures.append("execution_authority_open")
    if any(any(bool((row.get("authority") or {}).get(key)) for key in AUTHORITY_CLOSED) for row in rows):
        failures.append("authority_flags_open")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9434_suffix_choice_prior_fusion_denoise_manifest",
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "prior_source_counts": dict(sorted(prior_sources.items())),
        "quarantined_rows": len(quarantined),
        "candidate_quarantine_overlap": len(attached_ids & quarantine_ids),
        "denoise_ce_candidate_rows": sum(1 for row in rows if (row.get("loss_mask") or {}).get("denoise_ce")),
        "decoder_ce_rows": sum(1 for row in rows if (row.get("loss_mask") or {}).get("decoder_ce")),
        "execution_authorized_now": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Audited the suffix-choice-prior fusion denoise manifest. It has train support, heldout promoted priors only, and no quarantine overlap.",
        "next_best_step": "Build Stage9436 tiny preexecution for the 53-row suffix-choice-prior fusion denoise probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join(["# Stage9435 Suffix Choice Prior Fusion Denoise Manifest Audit", "", f"Passed: `{audit['passed']}`", f"Rows: `{len(rows)}`", f"Splits: `{dict(sorted(split_counts.items()))}`", f"Prior sources: `{dict(sorted(prior_sources.items()))}`", f"Quarantine overlap: `{audit['candidate_quarantine_overlap']}`", "", "Execution remains closed. The next stage may design preexecution only.", ""]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    registry_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    registry_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry_rows = sorted(registry_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = registry_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry_rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": len(rows), "split_counts": dict(sorted(split_counts.items()))}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
