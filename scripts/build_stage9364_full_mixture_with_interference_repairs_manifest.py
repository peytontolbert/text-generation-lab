#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9364
NAME = "stage9364_full_mixture_with_interference_repairs_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9363_mixture_interference_residual_probe_audit.json"
BASE = ROOT / "runs/local/artifacts/stage9358_full_mixture_with_non_operator_residual_repairs_manifest/full_mixture_with_non_operator_residual_repairs_manifest.jsonl"
REPAIR = ROOT / "runs/local/artifacts/stage9361_mixture_interference_residual_repair_manifest/mixture_interference_residual_repair_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "full_mixture_with_interference_repairs_manifest.jsonl"
AUDIT = OUT_DIR / "full_mixture_with_interference_repairs_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FULL_MIXTURE_WITH_INTERFERENCE_REPAIRS_MANIFEST_STAGE9364.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def remap(source_name: str, source_stage: int, row: dict[str, Any]) -> dict[str, Any]:
    new = copy.deepcopy(row)
    old_id = str(row.get("row_id"))
    new["row_id"] = f"stage9364_{source_name}_{old_id}"
    new["source_row_id"] = old_id
    new["source_stage"] = source_stage
    new["merged_curriculum_source"] = source_name
    new["objective_family"] = "full_mixture_with_interference_repairs_denoise"
    new["authority"] = dict(AUTHORITY_CLOSED)
    new["loss_mask"] = {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}
    mi = new.get("model_input") if isinstance(new.get("model_input"), dict) else {}
    mi["merged_curriculum_source"] = source_name
    mi["full_mixture_with_interference_repairs"] = True
    mi["route_schema_version"] = mi.get("route_schema_version") or "stage9364_full_mixture_v1"
    new["model_input"] = mi
    anti = new.get("anti_cheat") if isinstance(new.get("anti_cheat"), dict) else {}
    anti.update({"decoder_ce_closed": True, "runtime_closed": True, "full_mixture_with_interference_repairs": True})
    new["anti_cheat"] = anti
    return new


def build_rows() -> list[dict[str, Any]]:
    return [remap("full_mixture_pre_interference_repair", 9358, row) for row in load_jsonl(BASE)] + [remap("mixture_interference_residual_repair", 9361, row) for row in load_jsonl(REPAIR)]


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    split_counts = Counter(str(row.get("split")) for row in rows)
    source_counts = Counter(str(row.get("merged_curriculum_source")) for row in rows)
    route_counts = Counter(str(row.get("model_input", {}).get("opaque_phrase_route_id")) for row in rows)
    unsafe: list[str] = []
    missing_features: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        if loss != {"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False}:
            unsafe.append(row_id)
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            unsafe.append(row_id)
        for feature in ("semantic_surface_kind", "semantic_affordance", "opaque_phrase_route_id", "anchor_object_kind"):
            if not mi.get(feature):
                missing_features.append(row_id)
                break
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9363_not_passed")
    if len(rows) != 209:
        failures.append("unexpected_row_count")
    if dict(split_counts) != {"train": 109, "eval": 61, "strict_eval": 39}:
        failures.append("unexpected_split_counts")
    if dict(source_counts) != {"full_mixture_pre_interference_repair": 154, "mixture_interference_residual_repair": 55}:
        failures.append("unexpected_source_counts")
    if unsafe:
        failures.append("unsafe_rows")
    if missing_features:
        failures.append("missing_required_features")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "unsafe_rows": sorted(set(unsafe))[:20],
        "missing_feature_rows": sorted(set(missing_features))[:20],
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    audit = audit_rows(rows)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Merged Stage9361 mixture-interference residual repairs back into the full denoise mixture.",
        "next_best_step": "Build Stage9365 preexecution and run a 209-row closed rejoin probe before bounded decoder CE.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9364 Full Mixture With Interference Repairs Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Splits: `{audit['split_counts']}`",
                f"Sources: `{audit['source_counts']}`",
                f"Routes: `{audit['route_counts']}`",
                "",
                "Decoder CE, runtime, harness, Gemma, scoring, promotion, and checkpoint export remain closed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["rows", "split_counts", "source_counts", "route_counts", "failures"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
