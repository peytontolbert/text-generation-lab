#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9428
NAME = "stage9428_suffix_choice_denoise_reconnect_design_audit"
SOURCE = ROOT / "runs/summaries/stage9427_suffix_choice_denoise_reconnect_design.json"
CANDIDATES = (
    ROOT
    / "runs/local/artifacts/stage9427_suffix_choice_denoise_reconnect_design/"
    / "suffix_choice_denoise_reconnect_candidate_manifest.jsonl"
)
QUARANTINE = (
    ROOT
    / "runs/local/artifacts/stage9425_suffix_choice_reconnect_guard_manifest/"
    / "suffix_choice_residual_quarantine_manifest.jsonl"
)
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "suffix_choice_denoise_reconnect_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_DENOISE_RECONNECT_DESIGN_AUDIT_STAGE9428.md"
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

    source = load_json(SOURCE)
    candidates = load_jsonl(CANDIDATES)
    quarantined = load_jsonl(QUARANTINE)
    candidate_ids = {str(row.get("source_row_id")) for row in candidates}
    quarantine_ids = {str(row.get("source_row_id")) for row in quarantined}

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9427_not_passed")
    if len(candidates) != 9:
        failures.append("bad_candidate_count")
    if len(quarantined) != 7:
        failures.append("bad_quarantine_count")
    if candidate_ids & quarantine_ids:
        failures.append("quarantined_row_in_candidate_manifest")
    if any(row.get("route") != "DENOISE_RECONNECT_CANDIDATE_CONTROLLER_PRIOR" for row in candidates):
        failures.append("bad_candidate_route")
    if any(not row.get("requires_suffix_choice_prior") for row in candidates):
        failures.append("missing_suffix_choice_prior_requirement")
    if any(not row.get("requires_quarantine_exclusion") for row in candidates):
        failures.append("missing_quarantine_exclusion_requirement")
    if any(row.get("quarantine_source_row_id_present") for row in candidates):
        failures.append("candidate_self_reports_quarantine_present")
    if any(not row.get("candidate_only_no_loss") for row in candidates):
        failures.append("candidate_loss_flag_open")
    if any(any(bool(value) for value in (row.get("loss_mask") or {}).values()) for row in candidates):
        failures.append("loss_mask_open")
    if any(row.get("generation_reconnect_allowed_now") for row in candidates):
        failures.append("generation_reconnect_open")
    if any(
        row.get("decoder_ce_authorized")
        or row.get("denoise_ce_authorized")
        or row.get("model_execution_authorized")
        or row.get("runtime_authorized")
        or row.get("gemma_authorized")
        or row.get("harness_authorized")
        for row in candidates
    ):
        failures.append("forbidden_execution_authority_open")
    if any(any(bool((row.get("authority") or {}).get(key)) for key in AUTHORITY_CLOSED) for row in candidates):
        failures.append("authority_flags_open")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9427_suffix_choice_denoise_reconnect_design",
        "candidate_rows": len(candidates),
        "quarantined_rows": len(quarantined),
        "candidate_quarantine_overlap": len(candidate_ids & quarantine_ids),
        "candidate_only_no_loss_rows": sum(1 for row in candidates if row.get("candidate_only_no_loss")),
        "generation_reconnect_allowed_rows": 0,
        "decoder_ce_authorized_rows": 0,
        "denoise_ce_authorized_rows": 0,
        "future_execution_authorization_required": True,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Stage9427 design is a valid no-execution reconnect package if passed; execution remains closed.",
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": (
            "Audited the suffix-choice denoise reconnect design. It remains no-execution, excludes quarantined "
            "residuals, and opens no decoder, denoise, runtime, Gemma, harness, or promotion authority."
        ),
        "next_best_step": (
            "Design a contract-only denoise reconnect wrapper that consumes the Stage9427 candidate manifest, "
            "fails on quarantine overlap, and still requires a separate execution authorization review."
        ),
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9428 Suffix Choice Denoise Reconnect Design Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Candidate rows: `{len(candidates)}`",
                f"Quarantined rows: `{len(quarantined)}`",
                f"Candidate/quarantine overlap: `{audit['candidate_quarantine_overlap']}`",
                "",
                "Execution remains closed. The next stage may design a contract-only wrapper, but must not run generation or training without a separate authorization review.",
                "",
            ]
        )
    )

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [
        row
        for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
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
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "metrics": {
                    "candidate_rows": len(candidates),
                    "quarantined_rows": len(quarantined),
                    "overlap": len(candidate_ids & quarantine_ids),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
