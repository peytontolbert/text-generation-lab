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
STAGE = 9427
NAME = "stage9427_suffix_choice_denoise_reconnect_design"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9426_suffix_choice_reconnect_guard_audit.json"
PROMOTION = (
    ROOT
    / "runs/local/artifacts/stage9425_suffix_choice_reconnect_guard_manifest/"
    / "suffix_choice_reconnect_guard_manifest.jsonl"
)
QUARANTINE = (
    ROOT
    / "runs/local/artifacts/stage9425_suffix_choice_reconnect_guard_manifest/"
    / "suffix_choice_residual_quarantine_manifest.jsonl"
)
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CANDIDATES = OUT_DIR / "suffix_choice_denoise_reconnect_candidate_manifest.jsonl"
DESIGN_AUDIT = OUT_DIR / "suffix_choice_denoise_reconnect_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_DENOISE_RECONNECT_DESIGN_STAGE9427.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def closed_loss_mask() -> dict[str, bool]:
    return {
        "decoder_ce": False,
        "denoise_ce": False,
        "suffix_choice_ce": False,
        "structured_aux_ce": False,
        "runtime_reward": False,
        "gemma_distill": False,
        "harness_score": False,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    promoted = load_jsonl(PROMOTION)
    quarantined = load_jsonl(QUARANTINE)
    quarantine_ids = {str(row.get("source_row_id")) for row in quarantined}

    candidates: list[dict] = []
    for idx, row in enumerate(promoted):
        source_row_id = str(row.get("source_row_id"))
        candidates.append(
            {
                "row_id": f"stage9427_suffix_choice_reconnect_candidate_{idx:04d}",
                "source_stage": row.get("source_stage"),
                "source_row_id": source_row_id,
                "split": row.get("split"),
                "route": "DENOISE_RECONNECT_CANDIDATE_CONTROLLER_PRIOR",
                "suffix_choice_target": row.get("suffix_choice_target"),
                "suffix_choice_pred": row.get("suffix_choice_pred"),
                "suffix_choice_confidence": row.get("confidence"),
                "suffix_choice_margin": row.get("margin"),
                "suffix_choice_top_k": row.get("top_k"),
                "requires_suffix_choice_prior": True,
                "requires_quarantine_exclusion": True,
                "quarantine_source_row_id_present": source_row_id in quarantine_ids,
                "needs_residual_guard": bool(row.get("needs_residual_guard")),
                "candidate_only_no_loss": True,
                "generation_reconnect_allowed_now": False,
                "decoder_ce_authorized": False,
                "denoise_ce_authorized": False,
                "model_execution_authorized": False,
                "runtime_authorized": False,
                "gemma_authorized": False,
                "harness_authorized": False,
                "loss_mask": closed_loss_mask(),
                "authority": dict(AUTHORITY_CLOSED),
                "future_probe_requirements": [
                    "must consume only this candidate manifest",
                    "must reject every quarantined source_row_id",
                    "must remain no-generation until a separate execution authorization stage",
                    "must report raw suffix-choice prior telemetry before any denoise reconnect",
                ],
            }
        )

    candidate_ids = {row["source_row_id"] for row in candidates}
    split_counts = Counter(row.get("split") for row in candidates)
    choice_counts = Counter(row.get("suffix_choice_target") for row in candidates)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9426_not_passed")
    if len(promoted) != 9 or len(quarantined) != 7:
        failures.append("bad_guard_manifest_counts")
    if len(candidates) != 9:
        failures.append("bad_candidate_count")
    if candidate_ids & quarantine_ids:
        failures.append("quarantined_row_included")
    if any(row["quarantine_source_row_id_present"] for row in candidates):
        failures.append("candidate_marks_quarantine_present")
    if any(row.get("route") != "DENOISE_RECONNECT_CANDIDATE_CONTROLLER_PRIOR" for row in candidates):
        failures.append("bad_candidate_route")
    if any(not row.get("candidate_only_no_loss") for row in candidates):
        failures.append("candidate_loss_enabled")
    if any(any(bool(value) for value in row["loss_mask"].values()) for row in candidates):
        failures.append("loss_mask_opened")
    if any(row.get("generation_reconnect_allowed_now") for row in candidates):
        failures.append("generation_reconnect_opened")
    if any(
        row.get("decoder_ce_authorized")
        or row.get("denoise_ce_authorized")
        or row.get("model_execution_authorized")
        or row.get("runtime_authorized")
        or row.get("gemma_authorized")
        or row.get("harness_authorized")
        for row in candidates
    ):
        failures.append("forbidden_execution_authority_opened")
    if any(any(bool((row.get("authority") or {}).get(key)) for key in AUTHORITY_CLOSED) for row in candidates):
        failures.append("authority_flags_opened")

    write_jsonl(CANDIDATES, candidates)
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9426_suffix_choice_reconnect_guard_audit",
        "candidate_rows": len(candidates),
        "promoted_rows": len(promoted),
        "quarantined_rows": len(quarantined),
        "candidate_quarantine_overlap": len(candidate_ids & quarantine_ids),
        "generation_reconnect_allowed_rows": 0,
        "decoder_ce_authorized_rows": 0,
        "denoise_ce_authorized_rows": 0,
        "candidate_only_no_loss_rows": sum(1 for row in candidates if row.get("candidate_only_no_loss")),
        "residual_guard_rows": sum(1 for row in candidates if row.get("needs_residual_guard")),
        "split_counts": dict(sorted(split_counts.items())),
        "suffix_choice_counts": dict(sorted(choice_counts.items())),
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "no-execution denoise reconnect design only; future probe must request separate authorization",
    }
    DESIGN_AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "candidate_manifest": str(CANDIDATES.relative_to(ROOT)),
            "design_audit": str(DESIGN_AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": (
            "Created a no-execution suffix-choice denoise reconnect candidate package from Stage9425 promoted "
            "controller priors only. Quarantined residual source rows are excluded and all losses remain closed."
        ),
        "next_best_step": (
            "Audit the no-execution denoise reconnect design and verify that any future wrapper rejects quarantined "
            "source_row_ids before considering execution authorization."
        ),
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9427 Suffix Choice Denoise Reconnect Design",
                "",
                f"Passed: `{audit['passed']}`",
                f"Candidate rows: `{len(candidates)}`",
                f"Quarantined residual rows excluded: `{len(quarantined)}`",
                f"Candidate/quarantine overlap: `{audit['candidate_quarantine_overlap']}`",
                "",
                "This is a no-execution design package. It does not authorize decoder CE, denoise CE, generation, runtime, Gemma, harness, scoring, promotion, or checkpoint export.",
                "",
                "Future reconnect work must consume only the candidate manifest and must fail closed if any quarantined source row appears.",
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
