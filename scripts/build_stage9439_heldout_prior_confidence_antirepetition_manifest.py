#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9439
NAME = "stage9439_heldout_prior_confidence_antirepetition_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9438_suffix_choice_prior_fusion_residual_diagnosis.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9434_suffix_choice_prior_fusion_denoise_manifest/suffix_choice_prior_fusion_denoise_manifest.jsonl"
HELDOUT_RESIDUALS = ROOT / "runs/local/artifacts/stage9438_suffix_choice_prior_fusion_residual_diagnosis/heldout_prior_fusion_residuals.jsonl"
REPETITION_RESIDUALS = ROOT / "runs/local/artifacts/stage9438_suffix_choice_prior_fusion_residual_diagnosis/repetition_prior_fusion_residuals.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ANTI_REPETITION = OUT_DIR / "anti_repetition_denoise_support_manifest.jsonl"
LOW_CONF_QUARANTINE = OUT_DIR / "low_confidence_heldout_prior_quarantine.jsonl"
HELDOUT_REPETITION_QUARANTINE = OUT_DIR / "heldout_repetition_prior_quarantine.jsonl"
AUDIT = OUT_DIR / "heldout_prior_confidence_antirepetition_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "HELDOUT_PRIOR_CONFIDENCE_ANTIREPETITION_MANIFEST_STAGE9439.md"
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
    source_rows = {str(row.get("row_id")): row for row in load_jsonl(SOURCE_MANIFEST)}
    heldout_residuals = load_jsonl(HELDOUT_RESIDUALS)
    repetition_residuals = load_jsonl(REPETITION_RESIDUALS)

    low_conf_quarantine: list[dict] = []
    heldout_repetition_quarantine: list[dict] = []
    anti_repetition_rows: list[dict] = []

    for residual in heldout_residuals:
        prior = residual.get("suffix_choice_prior") if isinstance(residual.get("suffix_choice_prior"), dict) else {}
        confidence = float(prior.get("confidence") or 0.0)
        if confidence < 0.20 or prior.get("needs_residual_guard"):
            low_conf_quarantine.append(
                {
                    "row_id": f"stage9439_low_conf_quarantine_{len(low_conf_quarantine):04d}",
                    "source_row_id": residual.get("row_id"),
                    "split": residual.get("split"),
                    "route": "QUARANTINE_LOW_CONFIDENCE_SUFFIX_PRIOR",
                    "suffix_choice_prior": prior,
                    "confidence": confidence,
                    "reason": "low_confidence_or_residual_guard_suffix_prior",
                    "loss_mask": {"decoder_ce": False, "denoise_ce": False, "runtime_reward": False},
                    "authority": dict(AUTHORITY_CLOSED),
                }
            )

    for residual in repetition_residuals:
        source_row = source_rows.get(str(residual.get("row_id")))
        if not source_row:
            continue
        split = str(residual.get("split"))
        if split != "train":
            heldout_repetition_quarantine.append(
                {
                    "row_id": f"stage9439_heldout_repetition_quarantine_{len(heldout_repetition_quarantine):04d}",
                    "source_row_id": residual.get("row_id"),
                    "split": split,
                    "route": "QUARANTINE_HELDOUT_REPETITION_SUFFIX_PRIOR",
                    "suffix_choice_prior": residual.get("suffix_choice_prior"),
                    "reason": "heldout_repetition_not_train_support",
                    "loss_mask": {"decoder_ce": False, "denoise_ce": False, "runtime_reward": False},
                    "authority": dict(AUTHORITY_CLOSED),
                }
            )
            continue
        row = copy.deepcopy(source_row)
        row["row_id"] = f"stage9439_antirepetition_denoise_{len(anti_repetition_rows):04d}"
        row["route"] = "USE_FOR_DENOISE_REPAIR_ANTI_REPETITION"
        row["source_stage9437_row_id"] = residual.get("row_id")
        row["corrupted_output"] = residual.get("generated_text") or row.get("corrupted_output")
        row["loss_mask"] = {"decoder_ce": False, "denoise_ce": True, "runtime_reward": False}
        row["authority"] = dict(AUTHORITY_CLOSED)
        row["decoder_ce_authorized"] = False
        row["denoise_ce_authorized_now"] = False
        row["execution_authorized_now"] = False
        model_input = row.setdefault("model_input", {})
        model_input["anti_repetition_repair_mode"] = True
        model_input["anti_repetition_source"] = "stage9437_generated_repetition_residual"
        model_input["suffix_choice_prior_reconnect_allowed"] = False
        anti_repetition_rows.append(row)

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9438_not_passed")
    if len(heldout_residuals) != 7:
        failures.append("unexpected_heldout_residual_count")
    if len(repetition_residuals) != 6:
        failures.append("unexpected_repetition_residual_count")
    if len(low_conf_quarantine) != 6:
        failures.append("unexpected_low_conf_quarantine_count")
    if len(heldout_repetition_quarantine) != 2:
        failures.append("unexpected_heldout_repetition_quarantine_count")
    if len(anti_repetition_rows) != 4:
        failures.append("unexpected_anti_repetition_train_count")
    if any((row.get("loss_mask") or {}).get("decoder_ce") for row in anti_repetition_rows):
        failures.append("decoder_ce_open")
    if any(any(bool((row.get("authority") or {}).get(key)) for key in AUTHORITY_CLOSED) for row in anti_repetition_rows + low_conf_quarantine + heldout_repetition_quarantine):
        failures.append("authority_flags_open")

    write_jsonl(ANTI_REPETITION, anti_repetition_rows)
    write_jsonl(LOW_CONF_QUARANTINE, low_conf_quarantine)
    write_jsonl(HELDOUT_REPETITION_QUARANTINE, heldout_repetition_quarantine)
    split_counts = Counter(str(row.get("split")) for row in anti_repetition_rows)
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9438_suffix_choice_prior_fusion_residual_diagnosis",
        "anti_repetition_rows": len(anti_repetition_rows),
        "anti_repetition_split_counts": dict(sorted(split_counts.items())),
        "low_confidence_quarantine_rows": len(low_conf_quarantine),
        "heldout_repetition_quarantine_rows": len(heldout_repetition_quarantine),
        "decoder_ce_rows": 0,
        "denoise_ce_candidate_rows": sum(1 for row in anti_repetition_rows if (row.get("loss_mask") or {}).get("denoise_ce")),
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
        "artifacts": {
            "anti_repetition_manifest": str(ANTI_REPETITION.relative_to(ROOT)),
            "low_confidence_quarantine": str(LOW_CONF_QUARANTINE.relative_to(ROOT)),
            "heldout_repetition_quarantine": str(HELDOUT_REPETITION_QUARANTINE.relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Split Stage9437 residuals into low-confidence heldout prior quarantine and train-only anti-repetition denoise support.",
        "next_best_step": "Audit whether the 4-row anti-repetition support is enough for a tiny probe, or merge it back into the prior-fusion manifest with heldout low-confidence priors gated off.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join(["# Stage9439 Heldout Prior Confidence And Anti-Repetition Manifest", "", f"Passed: `{audit['passed']}`", f"Anti-repetition train rows: `{len(anti_repetition_rows)}`", f"Low-confidence heldout quarantine rows: `{len(low_conf_quarantine)}`", f"Heldout repetition quarantine rows: `{len(heldout_repetition_quarantine)}`", "", "Decoder CE and execution remain closed.", ""]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"anti_repetition_rows": len(anti_repetition_rows), "low_conf_quarantine": len(low_conf_quarantine)}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
