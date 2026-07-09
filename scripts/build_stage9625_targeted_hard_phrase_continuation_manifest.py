#!/usr/bin/env python3
from __future__ import annotations

import copy
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
STAGE = 9625
NAME = "stage9625_targeted_hard_phrase_continuation_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9624_tri_phase_reconnect_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9609_suffix_continuation_ladder_manifest/suffix_continuation_ladder_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "targeted_hard_phrase_continuation_manifest.jsonl"
AUDIT = OUT_DIR / "targeted_hard_phrase_continuation_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TARGETED_HARD_PHRASE_CONTINUATION_MANIFEST_STAGE9625.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

PREFIXES = {
    "localized_repair_step": [
        "Return the method invocation target that",
        "Return the method invocation target that matches",
        "Return the method invocation target that matches the localized",
    ],
    "relevant_repair_region": [
        "Return the project path that owns",
        "Return the project path that owns the",
        "Return the project path that owns the relevant",
        "Return the project path that owns the relevant repair",
    ],
    "checked_verifier_condition": [
        "Return the constant value required by",
        "Return the constant value required by the",
        "Return the constant value required by the checked",
        "Return the constant value required by the checked verifier",
    ],
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def phrase_bucket(target: str) -> str | None:
    lower = target.lower()
    if "localized repair step" in lower:
        return "localized_repair_step"
    if "relevant repair region" in lower:
        return "relevant_repair_region"
    if "checked verifier condition" in lower:
        return "checked_verifier_condition"
    return None


def make_row(source: dict[str, Any], bucket: str, prefix: str, index: int) -> dict[str, Any]:
    row = copy.deepcopy(source)
    digest = hashlib.sha256(f"{source.get('row_id')}|{bucket}|{prefix}".encode("utf-8")).hexdigest()[:16]
    row["row_id"] = f"stage9625_hard_phrase_{index:04d}_{digest}"
    row["source_row_id"] = source.get("row_id")
    row["source_stage9625"] = {
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "source_row_id": source.get("row_id"),
        "phrase_bucket": bucket,
        "hard_prefix": prefix,
    }
    row["objective_family"] = "TARGETED_HARD_PHRASE_CONTINUATION_DENOISE_CANDIDATE_CLOSED"
    row["route"] = "USE_FOR_DENOISE_REPAIR"
    row["residual_repair_route"] = "TARGETED_HARD_PHRASE_SUFFIX_CONTINUATION"
    row["training_candidate"] = True
    row["authority"] = dict(AUTHORITY_CLOSED)
    row.setdefault("anti_cheat", {})
    row["anti_cheat"].update(
        {
            "targeted_hard_phrase_continuation": True,
            "decoder_ce_closed": True,
            "runtime_closed": True,
            "full_clean_target_in_model_input": False,
            "prefix_visible_but_suffix_hidden": True,
            "stage_label_in_opaque_ids": False,
        }
    )
    row.setdefault("model_input", {})
    row["model_input"].update(
        {
            "active_generation_prefix_source": "stage9625_targeted_hard_phrase_patch",
            "active_generation_prefix_span": prefix,
            "active_generation_prefix_words": len(prefix.split()),
            "hard_phrase_bucket": bucket,
            "hard_phrase_patch_stage": STAGE,
            "remaining_suffix_hidden_from_model_input": True,
            "clean_target_hidden_from_model_input": True,
        }
    )
    row["generation_prefix_field"] = "model_input.active_generation_prefix_span"
    row.setdefault("episode_transition", {}).setdefault("state_t", {})
    row["episode_transition"]["state_t"].update(
        {
            "active_generation_prefix_span": "redacted_literal_prefix_for_targeted_hard_phrase",
            "bridge_error_family": "targeted_hard_phrase_continuation",
            "hard_phrase_bucket": bucket,
        }
    )
    row.setdefault("loss_mask", {})["denoise_ce"] = True
    row.setdefault("loss_mask_current", {})["denoise_ce"] = True
    row["phase"] = "targeted_hard_phrase_suffix_support"
    return row


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_summary = load_json(SOURCE_SUMMARY)
    source_rows = load_jsonl(SOURCE_MANIFEST)
    rows: list[dict[str, Any]] = []
    idx = 0
    seen: set[tuple[str, str, str]] = set()
    for source in source_rows:
        target = str(source.get("clean_target") or source.get("decoder_text") or "")
        bucket = phrase_bucket(target)
        if not bucket:
            continue
        for prefix in PREFIXES[bucket]:
            if not target.startswith(prefix):
                continue
            if len(prefix.split()) > 8 or len(prefix) > 96:
                continue
            key = (str(source.get("source_stage9605_row_id") or source.get("source_row_id") or source.get("row_id")), bucket, prefix)
            if key in seen:
                continue
            seen.add(key)
            rows.append(make_row(source, bucket, prefix, idx))
            idx += 1

    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("stage9624_not_passed")
    if not rows:
        failures.append("no_rows")
    split_cycle = ("train", "train", "train", "eval", "strict_eval", "train")
    for row_index, row in enumerate(rows):
        row["split"] = split_cycle[row_index % len(split_cycle)]

    counts = Counter(row.get("split") for row in rows)
    bucket_counts = Counter(row.get("model_input", {}).get("hard_phrase_bucket") for row in rows)
    if any(row.get("authority") != AUTHORITY_CLOSED for row in rows):
        failures.append("authority_not_closed")
    if any(row.get("loss_mask", {}).get("decoder_ce") for row in rows):
        failures.append("decoder_ce_enabled")
    if any(str(row.get("clean_target") or "") == str(row.get("model_input", {}).get("active_generation_prefix_span") or "") for row in rows):
        failures.append("full_target_prefix_visible")
    if len(bucket_counts) != 3:
        failures.append("missing_target_bucket")

    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": dict(counts),
        "bucket_counts": dict(bucket_counts),
        "prefix_counts": dict(Counter(row.get("model_input", {}).get("active_generation_prefix_span") for row in rows)),
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9626 tri-phase hard-phrase reconnect contract preflight using Stage9625 as phase2 warm-up and Stage9609 full suffix ladder as phase3."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Materialized targeted hard phrase continuation rows for the residual suffix buckets that still failed after tri-phase reconnect.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9625 Targeted Hard Phrase Continuation Manifest",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Splits: `{audit['split_counts']}`",
        f"Buckets: `{audit['bucket_counts']}`",
        "",
        "Rows clone the existing safe suffix-ladder schema and change only the visible generation prefix to the hard phrase boundary. Full clean targets remain hidden from model input; decoder CE/runtime/Gemma/harness/promotion remain closed.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "rows": len(rows), "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
