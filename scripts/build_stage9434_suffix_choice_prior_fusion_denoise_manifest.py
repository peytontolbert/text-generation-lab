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
STAGE = 9434
NAME = "stage9434_suffix_choice_prior_fusion_denoise_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9433_suffix_choice_prior_attached_denoise_manifest_audit.json"
SUFFIX_CHOICE_ROWS = ROOT / "runs/local/artifacts/stage9417_balanced_suffix_choice_support_manifest/balanced_suffix_choice_support_manifest.jsonl"
PROMOTED = ROOT / "runs/local/artifacts/stage9425_suffix_choice_reconnect_guard_manifest/suffix_choice_reconnect_guard_manifest.jsonl"
QUARANTINE = ROOT / "runs/local/artifacts/stage9425_suffix_choice_reconnect_guard_manifest/suffix_choice_residual_quarantine_manifest.jsonl"
SHORT_SUFFIX_ROWS = ROOT / "runs/local/artifacts/stage9391_bounded_decoder_short_suffix_target_resolved_manifest/bounded_decoder_short_suffix_target_resolved_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "suffix_choice_prior_fusion_denoise_manifest.jsonl"
AUDIT = OUT_DIR / "suffix_choice_prior_fusion_denoise_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_PRIOR_FUSION_DENOISE_MANIFEST_STAGE9434.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def attach_prior(base_row: dict, choice_row: dict, *, prior_source: str, prior_payload: dict, index: int) -> dict:
    row = copy.deepcopy(base_row)
    model_input = row.setdefault("model_input", {})
    model_input["suffix_choice_prior_attached"] = True
    model_input["suffix_choice_prior_schema_version"] = "stage9434_suffix_choice_prior_fusion_v1"
    model_input["suffix_choice_prior_label"] = prior_payload["label"]
    model_input["suffix_choice_prior_confidence"] = prior_payload.get("confidence")
    model_input["suffix_choice_prior_margin"] = prior_payload.get("margin")
    model_input["suffix_choice_prior_source"] = prior_source
    model_input["suffix_choice_prior_is_controller_signal"] = True
    model_input["suffix_choice_prior_source_row_id"] = choice_row.get("row_id")
    row["row_id"] = f"stage9434_suffix_prior_fusion_{index:04d}"
    row["route"] = "USE_FOR_DENOISE_REPAIR_WITH_SUFFIX_CHOICE_PRIOR"
    row["split"] = choice_row.get("split")
    row["source_stage9413_suffix_choice_row_id"] = choice_row.get("row_id")
    row["suffix_choice_prior"] = prior_payload
    row["suffix_choice_prior_source"] = prior_source
    row["loss_mask"] = {"decoder_ce": False, "denoise_ce": True, "runtime_reward": False}
    row["authority"] = dict(AUTHORITY_CLOSED)
    row["decoder_ce_authorized"] = False
    row["denoise_ce_authorized_now"] = False
    row["execution_authorized_now"] = False
    return row


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    choice_rows = load_jsonl(SUFFIX_CHOICE_ROWS)
    promoted = load_jsonl(PROMOTED)
    quarantined = load_jsonl(QUARANTINE)
    short_rows = load_jsonl(SHORT_SUFFIX_ROWS)
    promoted_by_choice_id = {str(row.get("source_row_id")): row for row in promoted}
    quarantine_ids = {str(row.get("source_row_id")) for row in quarantined}
    short_by_9388: dict[str, list[dict]] = {}
    for row in short_rows:
        short_by_9388.setdefault(str(row.get("source_stage9388_row_id")), []).append(row)

    out_rows: list[dict] = []
    join_failures: list[dict] = []
    skipped_heldout = 0
    for choice in choice_rows:
        split = str(choice.get("split"))
        choice_id = str(choice.get("row_id"))
        if split != "train" and choice_id not in promoted_by_choice_id:
            skipped_heldout += 1
            continue
        if choice_id in quarantine_ids:
            join_failures.append({"row_id": choice_id, "reason": "quarantined_choice_included"})
            continue
        matches = short_by_9388.get(str(choice.get("source_stage9388_row_id")), [])
        if len(matches) != 1:
            join_failures.append({"row_id": choice_id, "source_stage9388_row_id": choice.get("source_stage9388_row_id"), "matches": len(matches)})
            continue
        if split == "train":
            prior_source = "gold_train_suffix_choice_support"
            prior_payload = {
                "label": (choice.get("clean_state") or {}).get("suffix_choice"),
                "target": (choice.get("clean_state") or {}).get("suffix_choice"),
                "confidence": 1.0,
                "margin": None,
                "needs_residual_guard": False,
                "top_k": [],
            }
        else:
            promoted_row = promoted_by_choice_id[choice_id]
            prior_source = "stage9419_correct_controller_prior"
            prior_payload = {
                "label": promoted_row.get("suffix_choice_pred"),
                "target": promoted_row.get("suffix_choice_target"),
                "confidence": promoted_row.get("confidence"),
                "margin": promoted_row.get("margin"),
                "needs_residual_guard": promoted_row.get("needs_residual_guard"),
                "top_k": promoted_row.get("top_k"),
            }
        out_rows.append(attach_prior(matches[0], choice, prior_source=prior_source, prior_payload=prior_payload, index=len(out_rows)))

    split_counts = Counter(str(row.get("split")) for row in out_rows)
    prior_source_counts = Counter(str(row.get("suffix_choice_prior_source")) for row in out_rows)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9433_not_passed")
    if join_failures:
        failures.append("join_failures_present")
    if split_counts.get("train") != 44 or split_counts.get("eval") != 5 or split_counts.get("strict_eval") != 4:
        failures.append("unexpected_split_counts")
    if len(out_rows) != 53:
        failures.append("bad_output_row_count")
    if any(str(row.get("source_stage9413_suffix_choice_row_id")) in quarantine_ids for row in out_rows):
        failures.append("quarantined_choice_included")
    if any((row.get("loss_mask") or {}).get("decoder_ce") for row in out_rows):
        failures.append("decoder_ce_open")
    if any(not (row.get("loss_mask") or {}).get("denoise_ce") for row in out_rows):
        failures.append("denoise_ce_missing")
    if any(row.get("execution_authorized_now") or row.get("denoise_ce_authorized_now") for row in out_rows):
        failures.append("execution_authority_open")
    if any(any(bool((row.get("authority") or {}).get(key)) for key in AUTHORITY_CLOSED) for row in out_rows):
        failures.append("authority_flags_open")

    write_jsonl(MANIFEST, out_rows)
    audit = {
        "passed": not failures,
        "failures": failures,
        "join_failures": join_failures,
        "source_stage": "stage9433_suffix_choice_prior_attached_denoise_manifest_audit",
        "rows": len(out_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "prior_source_counts": dict(sorted(prior_source_counts.items())),
        "skipped_unpromoted_heldout_rows": skipped_heldout,
        "quarantined_rows": len(quarantined),
        "denoise_ce_candidate_rows": sum(1 for row in out_rows if (row.get("loss_mask") or {}).get("denoise_ce")),
        "decoder_ce_rows": sum(1 for row in out_rows if (row.get("loss_mask") or {}).get("decoder_ce")),
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
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built a train/eval/strict suffix-choice-prior fusion denoise manifest: gold priors for train support, Stage9419-correct priors for heldout, quarantined residuals excluded.",
        "next_best_step": "Build a tiny preexecution card for the 53-row suffix-choice-prior fusion denoise probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join(["# Stage9434 Suffix Choice Prior Fusion Denoise Manifest", "", f"Passed: `{audit['passed']}`", f"Rows: `{len(out_rows)}`", f"Splits: `{dict(sorted(split_counts.items()))}`", f"Prior sources: `{dict(sorted(prior_source_counts.items()))}`", "", "Train rows use gold suffix-choice support priors. Heldout rows use only Stage9419-correct controller priors. Quarantined residuals are excluded.", ""]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": len(out_rows), "split_counts": dict(sorted(split_counts.items()))}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
