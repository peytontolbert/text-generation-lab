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
STAGE = 9441
NAME = "stage9441_gated_prior_fusion_rejoin_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9440_antirepetition_support_sufficiency_audit.json"
PRIOR_FUSION = ROOT / "runs/local/artifacts/stage9434_suffix_choice_prior_fusion_denoise_manifest/suffix_choice_prior_fusion_denoise_manifest.jsonl"
ANTI_REPETITION = ROOT / "runs/local/artifacts/stage9439_heldout_prior_confidence_antirepetition_manifest/anti_repetition_denoise_support_manifest.jsonl"
LOW_CONF_QUARANTINE = ROOT / "runs/local/artifacts/stage9439_heldout_prior_confidence_antirepetition_manifest/low_confidence_heldout_prior_quarantine.jsonl"
HELDOUT_REPETITION_QUARANTINE = ROOT / "runs/local/artifacts/stage9439_heldout_prior_confidence_antirepetition_manifest/heldout_repetition_prior_quarantine.jsonl"
HELDOUT_RESIDUALS = ROOT / "runs/local/artifacts/stage9438_suffix_choice_prior_fusion_residual_diagnosis/heldout_prior_fusion_residuals.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "gated_prior_fusion_rejoin_manifest.jsonl"
EXCLUDED = OUT_DIR / "gated_prior_fusion_excluded_heldout_rows.jsonl"
AUDIT = OUT_DIR / "gated_prior_fusion_rejoin_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GATED_PRIOR_FUSION_REJOIN_MANIFEST_STAGE9441.md"
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
    prior_rows = load_jsonl(PRIOR_FUSION)
    anti_rows = load_jsonl(ANTI_REPETITION)
    low_conf = load_jsonl(LOW_CONF_QUARANTINE)
    heldout_rep = load_jsonl(HELDOUT_REPETITION_QUARANTINE)
    heldout_residuals = load_jsonl(HELDOUT_RESIDUALS)
    excluded_ids = {str(row.get("source_row_id")) for row in low_conf + heldout_rep}
    excluded_ids.update(str(row.get("row_id")) for row in heldout_residuals)

    out_rows: list[dict] = []
    excluded_rows: list[dict] = []
    for row in prior_rows:
        row_id = str(row.get("row_id"))
        split = str(row.get("split"))
        if split != "train" and row_id in excluded_ids:
            excluded_rows.append(
                {
                    "row_id": f"stage9441_excluded_{len(excluded_rows):04d}",
                    "source_row_id": row_id,
                    "split": split,
                    "route": "EXCLUDE_HELDOUT_PRIOR_FUSION_RESIDUAL",
                    "reason": "heldout prior fusion row failed Stage9437 or was low-confidence/repetitive",
                    "loss_mask": {"decoder_ce": False, "denoise_ce": False, "runtime_reward": False},
                    "authority": dict(AUTHORITY_CLOSED),
                }
            )
            continue
        if split == "train" or split in {"eval", "strict_eval"}:
            cloned = copy.deepcopy(row)
            cloned["row_id"] = f"stage9441_gated_prior_rejoin_{len(out_rows):04d}"
            cloned["source_stage9434_row_id"] = row_id
            cloned["route"] = "USE_FOR_DENOISE_REPAIR_WITH_GATED_SUFFIX_CHOICE_PRIOR"
            cloned["execution_authorized_now"] = False
            cloned["denoise_ce_authorized_now"] = False
            cloned["decoder_ce_authorized"] = False
            cloned["authority"] = dict(AUTHORITY_CLOSED)
            model_input = cloned.setdefault("model_input", {})
            model_input["suffix_choice_prior_confidence_gate"] = "train_gold" if split == "train" else "heldout_high_confidence_only"
            model_input["low_confidence_heldout_prior_excluded"] = False
            out_rows.append(cloned)

    for row in anti_rows:
        cloned = copy.deepcopy(row)
        cloned["row_id"] = f"stage9441_gated_prior_rejoin_{len(out_rows):04d}"
        cloned["source_stage9439_row_id"] = row.get("row_id")
        cloned["route"] = "USE_FOR_DENOISE_REPAIR_ANTI_REPETITION_WITH_GATED_PRIOR"
        cloned["authority"] = dict(AUTHORITY_CLOSED)
        cloned["execution_authorized_now"] = False
        cloned["denoise_ce_authorized_now"] = False
        cloned["decoder_ce_authorized"] = False
        model_input = cloned.setdefault("model_input", {})
        model_input["suffix_choice_prior_confidence_gate"] = "anti_repetition_train_support"
        out_rows.append(cloned)

    split_counts = Counter(str(row.get("split")) for row in out_rows)
    route_counts = Counter(str(row.get("route")) for row in out_rows)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9440_not_passed")
    if len(out_rows) != 50:
        failures.append("bad_manifest_row_count")
    if dict(split_counts) != {"eval": 1, "strict_eval": 1, "train": 48}:
        failures.append("bad_split_counts")
    if len(excluded_rows) != 7:
        failures.append("bad_excluded_heldout_count")
    if any((row.get("loss_mask") or {}).get("decoder_ce") for row in out_rows):
        failures.append("decoder_ce_open")
    if any(not (row.get("loss_mask") or {}).get("denoise_ce") for row in out_rows):
        failures.append("denoise_ce_missing")
    if any(any(bool((row.get("authority") or {}).get(key)) for key in AUTHORITY_CLOSED) for row in out_rows + excluded_rows):
        failures.append("authority_flags_open")

    write_jsonl(MANIFEST, out_rows)
    write_jsonl(EXCLUDED, excluded_rows)
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9440_antirepetition_support_sufficiency_audit",
        "rows": len(out_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "excluded_heldout_rows": len(excluded_rows),
        "decoder_ce_rows": 0,
        "denoise_ce_candidate_rows": sum(1 for row in out_rows if (row.get("loss_mask") or {}).get("denoise_ce")),
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
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "excluded": str(EXCLUDED.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built a gated prior-fusion rejoin manifest with low-confidence heldout priors excluded and anti-repetition train support included.",
        "next_best_step": "Build preexecution for the 50-row gated prior-fusion rejoin probe; keep decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join(["# Stage9441 Gated Prior Fusion Rejoin Manifest", "", f"Passed: `{audit['passed']}`", f"Rows: `{len(out_rows)}`", f"Splits: `{dict(sorted(split_counts.items()))}`", f"Excluded heldout rows: `{len(excluded_rows)}`", "", "Decoder CE and execution remain closed.", ""]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": len(out_rows), "excluded": len(excluded_rows), "split_counts": dict(sorted(split_counts.items()))}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
