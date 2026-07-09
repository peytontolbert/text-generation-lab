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
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9617
NAME = "stage9617_integrated_residual_phrase_denoise_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9616_phrase_suffix_probe_audit.json"
FULL_MANIFEST = ROOT / "runs/local/artifacts/stage9609_suffix_continuation_ladder_manifest/suffix_continuation_ladder_manifest.jsonl"
PHRASE_MANIFEST = ROOT / "runs/local/artifacts/stage9613_phrase_level_suffix_support_manifest/phrase_level_suffix_support_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "integrated_residual_phrase_denoise_manifest.jsonl"
AUDIT = OUT_DIR / "integrated_residual_phrase_denoise_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "INTEGRATED_RESIDUAL_PHRASE_DENOISE_MANIFEST_STAGE9617.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
GENERATION_PREFIX_FIELD = "model_input.active_generation_prefix_span"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def nested_value(row: dict[str, Any], path: str) -> Any:
    value: Any = row
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def active_losses(row: dict[str, Any]) -> list[str]:
    loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
    return sorted(key for key, value in loss.items() if bool(value))


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalized_row(row: dict[str, Any], source_family: str) -> dict[str, Any]:
    out = copy.deepcopy(row)
    out["integrated_manifest_stage"] = STAGE
    out["integrated_source_family"] = source_family
    out["route"] = "INTEGRATED_RESIDUAL_PHRASE_DENOISE_CANDIDATE_CLOSED"
    model_input = out.get("model_input") if isinstance(out.get("model_input"), dict) else {}
    model_input = dict(model_input)
    model_input["integrated_source_family"] = source_family
    model_input["integrated_residual_phrase_stage"] = STAGE
    model_input["remaining_suffix_hidden_from_model_input"] = True
    model_input["clean_target_hidden_from_model_input"] = True
    out["model_input"] = model_input
    loss = out.get("loss_mask") if isinstance(out.get("loss_mask"), dict) else {}
    loss = {key: False for key in loss}
    loss["denoise_ce"] = True
    loss.setdefault("decoder_ce", False)
    loss.setdefault("structured_aux", False)
    loss.setdefault("runtime_reward", False)
    out["loss_mask"] = loss
    out["authority"] = dict(AUTHORITY_CLOSED)
    out["generation_prefix_field"] = GENERATION_PREFIX_FIELD
    return out


def build_rows() -> list[dict[str, Any]]:
    full = [normalized_row(row, "full_suffix_ladder") for row in load_jsonl(FULL_MANIFEST)]
    phrase = [normalized_row(row, "phrase_suffix_support") for row in load_jsonl(PHRASE_MANIFEST)]
    rows: list[dict[str, Any]] = []
    by_split_family: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in full + phrase:
        key = (str(row.get("split")), str(row.get("integrated_source_family")))
        by_split_family.setdefault(key, []).append(row)
    # Interleave rows by split and source family so phrase support does not get appended after all full rows.
    for split in ["train", "eval", "strict_eval"]:
        buckets = [by_split_family.get((split, "full_suffix_ladder"), []), by_split_family.get((split, "phrase_suffix_support"), [])]
        max_len = max((len(bucket) for bucket in buckets), default=0)
        for index in range(max_len):
            for bucket in buckets:
                if index < len(bucket):
                    rows.append(bucket[index])
    return rows


def audit_rows(rows: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any]:
    split_counts = Counter(str(row.get("split")) for row in rows)
    family_counts = Counter(str(row.get("integrated_source_family")) for row in rows)
    split_family_counts = Counter(f"{row.get('split')}::{row.get('integrated_source_family')}" for row in rows)
    prefix_bad: list[dict[str, str]] = []
    target_visible: list[str] = []
    unsafe_rows: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        target = str((row.get("target") or {}).get("decoder_text") or row.get("decoder_text") or "")
        prefix = str(nested_value(row, GENERATION_PREFIX_FIELD) or "")
        model_input_text = json.dumps(row.get("model_input") or {}, sort_keys=True)
        if not prefix:
            prefix_bad.append({"row_id": row_id, "reason": "missing_prefix"})
        elif len(prefix.split()) > 8 or len(prefix) > 96:
            prefix_bad.append({"row_id": row_id, "reason": "prefix_over_cap"})
        elif prefix == target:
            prefix_bad.append({"row_id": row_id, "reason": "prefix_is_full_target"})
        elif not target.startswith(prefix):
            prefix_bad.append({"row_id": row_id, "reason": "prefix_not_target_start"})
        if target and target in model_input_text:
            target_visible.append(row_id)
        if active_losses(row) != ["denoise_ce"]:
            unsafe_rows.append(row_id)
        if any(bool((row.get("authority") or {}).get(key)) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(row_id)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9616_not_passed")
    if len(rows) != 80:
        failures.append("integrated_rows_not_80")
    if dict(family_counts) != {"full_suffix_ladder": 52, "phrase_suffix_support": 28}:
        failures.append("unexpected_family_counts")
    if prefix_bad:
        failures.append("prefix_contract_failures")
    if target_visible:
        failures.append("full_target_visible_in_model_input")
    if unsafe_rows:
        failures.append("unsafe_or_wrong_loss_rows")
    return {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "full_manifest": str(FULL_MANIFEST.relative_to(ROOT)),
        "phrase_manifest": str(PHRASE_MANIFEST.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": dict(split_counts),
        "family_counts": dict(family_counts),
        "split_family_counts": dict(split_family_counts),
        "generation_prefix_field": GENERATION_PREFIX_FIELD,
        "prefix_bad_rows": prefix_bad,
        "full_target_visible_rows": target_visible,
        "unsafe_rows": unsafe_rows,
        "decoder_ce_rows": 0,
        "runtime_rows": 0,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = build_rows()
    write_jsonl(MANIFEST, rows)
    audit = audit_rows(rows, source)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Run Stage9618 contract-only preflight for integrated residual-plus-phrase denoise, then a tiny integration probe if it passes."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built an integrated phase-2 denoise manifest combining full residual suffix ladder rows with phrase-level support rows.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9617 Integrated Residual Phrase Denoise Manifest",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Family counts: `{audit['family_counts']}`",
        f"Split counts: `{audit['split_counts']}`",
        "",
        "This manifest tests whether Stage9615 phrase-level suffix support transfers back into full residual suffix repair.",
        "",
        "Decoder CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": audit["failures"], "rows": audit["rows"], "next_best_step": next_step}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
