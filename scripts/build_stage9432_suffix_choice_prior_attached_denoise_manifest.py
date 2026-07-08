#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9432
NAME = "stage9432_suffix_choice_prior_attached_denoise_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9431_suffix_choice_denoise_reconnect_contract_preflight.json"
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
SUFFIX_CHOICE_ROWS = (
    ROOT
    / "runs/local/artifacts/stage9417_balanced_suffix_choice_support_manifest/"
    / "balanced_suffix_choice_support_manifest.jsonl"
)
SHORT_SUFFIX_ROWS = (
    ROOT
    / "runs/local/artifacts/stage9391_bounded_decoder_short_suffix_target_resolved_manifest/"
    / "bounded_decoder_short_suffix_target_resolved_manifest.jsonl"
)
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "suffix_choice_prior_attached_denoise_manifest.jsonl"
AUDIT = OUT_DIR / "suffix_choice_prior_attached_denoise_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_PRIOR_ATTACHED_DENOISE_MANIFEST_STAGE9432.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    candidates = load_jsonl(CANDIDATES)
    quarantined = load_jsonl(QUARANTINE)
    suffix_choice_rows = load_jsonl(SUFFIX_CHOICE_ROWS)
    short_suffix_rows = load_jsonl(SHORT_SUFFIX_ROWS)

    quarantine_ids = {str(row.get("source_row_id")) for row in quarantined}
    choice_by_id = {str(row.get("row_id")): row for row in suffix_choice_rows}
    short_by_9388: dict[str, list[dict]] = {}
    for row in short_suffix_rows:
        short_by_9388.setdefault(str(row.get("source_stage9388_row_id")), []).append(row)

    out_rows: list[dict] = []
    join_failures: list[dict] = []
    for index, candidate in enumerate(candidates):
        source_choice_id = str(candidate.get("source_row_id"))
        choice_row = choice_by_id.get(source_choice_id)
        if not choice_row:
            join_failures.append({"source_row_id": source_choice_id, "reason": "missing_suffix_choice_row"})
            continue
        short_matches = short_by_9388.get(str(choice_row.get("source_stage9388_row_id")), [])
        if len(short_matches) != 1:
            join_failures.append(
                {
                    "source_row_id": source_choice_id,
                    "source_stage9388_row_id": choice_row.get("source_stage9388_row_id"),
                    "matches": len(short_matches),
                    "reason": "bad_short_suffix_join_count",
                }
            )
            continue
        base = copy.deepcopy(short_matches[0])
        model_input = base.setdefault("model_input", {})
        model_input["suffix_choice_prior_attached"] = True
        model_input["suffix_choice_prior_schema_version"] = "stage9432_suffix_choice_prior_attachment_v1"
        model_input["suffix_choice_prior_label"] = candidate.get("suffix_choice_pred")
        model_input["suffix_choice_prior_confidence"] = candidate.get("suffix_choice_confidence")
        model_input["suffix_choice_prior_margin"] = candidate.get("suffix_choice_margin")
        model_input["suffix_choice_prior_needs_residual_guard"] = candidate.get("needs_residual_guard")
        model_input["suffix_choice_prior_source_row_id"] = source_choice_id
        model_input["suffix_choice_prior_is_controller_signal"] = True
        base["row_id"] = f"stage9432_suffix_prior_denoise_{index:04d}"
        base["route"] = "USE_FOR_DENOISE_REPAIR_WITH_SUFFIX_CHOICE_PRIOR"
        base["source_stage9432_candidate_row_id"] = candidate.get("row_id")
        base["source_stage9413_suffix_choice_row_id"] = source_choice_id
        base["suffix_choice_prior"] = {
            "label": candidate.get("suffix_choice_pred"),
            "target": candidate.get("suffix_choice_target"),
            "confidence": candidate.get("suffix_choice_confidence"),
            "margin": candidate.get("suffix_choice_margin"),
            "needs_residual_guard": candidate.get("needs_residual_guard"),
            "top_k": candidate.get("suffix_choice_top_k"),
        }
        base["loss_mask"] = {
            "decoder_ce": False,
            "denoise_ce": True,
            "runtime_reward": False,
        }
        base["authority"] = dict(AUTHORITY_CLOSED)
        base["decoder_ce_authorized"] = False
        base["denoise_ce_authorized_now"] = False
        base["execution_authorized_now"] = False
        base["quarantine_source_row_id_present"] = source_choice_id in quarantine_ids
        out_rows.append(base)

    source_ids = {str(row.get("source_stage9413_suffix_choice_row_id")) for row in out_rows}
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9431_not_passed")
    if len(candidates) != 9:
        failures.append("bad_candidate_count")
    if join_failures:
        failures.append("join_failures_present")
    if len(out_rows) != 9:
        failures.append("bad_output_row_count")
    if source_ids & quarantine_ids:
        failures.append("quarantined_suffix_choice_row_attached")
    if any(row.get("quarantine_source_row_id_present") for row in out_rows):
        failures.append("row_self_reports_quarantine_present")
    if any((row.get("loss_mask") or {}).get("decoder_ce") for row in out_rows):
        failures.append("decoder_ce_open")
    if any(not (row.get("loss_mask") or {}).get("denoise_ce") for row in out_rows):
        failures.append("denoise_ce_missing_from_candidate")
    if any(row.get("execution_authorized_now") or row.get("denoise_ce_authorized_now") for row in out_rows):
        failures.append("execution_authority_opened")
    if any(any(bool((row.get("authority") or {}).get(key)) for key in AUTHORITY_CLOSED) for row in out_rows):
        failures.append("authority_flags_open")

    write_jsonl(MANIFEST, out_rows)
    audit = {
        "passed": not failures,
        "failures": failures,
        "join_failures": join_failures,
        "source_stage": "stage9431_suffix_choice_denoise_reconnect_contract_preflight",
        "candidate_rows": len(candidates),
        "attached_rows": len(out_rows),
        "quarantined_rows": len(quarantined),
        "candidate_quarantine_overlap": len(source_ids & quarantine_ids),
        "denoise_ce_candidate_rows": sum(1 for row in out_rows if (row.get("loss_mask") or {}).get("denoise_ce")),
        "decoder_ce_rows": sum(1 for row in out_rows if (row.get("loss_mask") or {}).get("decoder_ce")),
        "execution_authorized_now": False,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "materialized denoise candidate rows with suffix-choice controller priors attached; execution remains closed",
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
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": (
            "Resolved promoted suffix-choice controller priors onto the real Stage9391 short-suffix denoise rows. "
            "This creates denoise candidate rows but does not authorize execution."
        ),
        "next_best_step": (
            "Audit the suffix-choice prior attachment manifest, then design a tiny preexecution card if all "
            "quarantine and authority checks remain closed."
        ),
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9432 Suffix Choice Prior Attached Denoise Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Attached rows: `{len(out_rows)}`",
                f"Candidate/quarantine overlap: `{audit['candidate_quarantine_overlap']}`",
                f"Denoise CE candidate rows: `{audit['denoise_ce_candidate_rows']}`",
                "",
                "This manifest attaches controller-side suffix-choice priors to real short-suffix denoise rows. It does not authorize execution.",
                "",
            ]
        )
    )

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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"attached_rows": len(out_rows), "overlap": len(source_ids & quarantine_ids)}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
