#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9310
NAME = "stage9310_prefix_ladder_supported_suffix_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9309_prefix_ladder_curriculum_design.json"
BASE_MANIFEST = ROOT / "runs/local/artifacts/stage9304_operator_suffix_support_manifest/operator_suffix_support_manifest.jsonl"
SAMPLES = ROOT / "runs/local/artifacts/stage9308_copy_prefix_multitoken_probe/sample_generation_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "prefix_ladder_supported_suffix_manifest.jsonl"
AUDIT = OUT_DIR / "prefix_ladder_supported_suffix_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PREFIX_LADDER_SUPPORTED_SUFFIX_MANIFEST_STAGE9310.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def word_prefix(text: str, n: int) -> str:
    words = text.split()
    return " ".join(words[: min(n, len(words))])


def prefix_suffix(text: str, prefix: str) -> str:
    if prefix and text.startswith(prefix):
        return text[len(prefix):].strip()
    words = text.split()
    prefix_words = prefix.split()
    return " ".join(words[len(prefix_words):]).strip()


def failure_kind(generated: str) -> str:
    if "operatch" in generated or "keepside" in generated:
        return "subword_bridge_collapse"
    words = generated.split()
    if len(words) >= 4 and len(set(words[-4:])) <= 2:
        return "late_suffix_repetition"
    return "suffix_drift"


def make_variant(row: dict[str, Any], *, prefix_words: int, variant: str, split: str | None = None, corrupted_output: str | None = None) -> dict[str, Any]:
    target = str(((row.get("target") or {}).get("decoder_text")) or row.get("clean_target") or "")
    prefix = word_prefix(target, prefix_words)
    suffix = prefix_suffix(target, prefix)
    new = copy.deepcopy(row)
    base_id = str(row.get("row_id"))
    new["row_id"] = f"stage9310_{variant}_{prefix_words}w_{base_id}"
    new["split"] = split or row.get("split")
    new["source_stage"] = STAGE
    new["source_manifest_stage"] = STAGE
    new["source_base_row_id"] = base_id
    new["objective_family"] = "prefix_ladder_supported_suffix_denoise"
    new["repair_task_type"] = "prefix_ladder_to_remaining_suffix"
    if corrupted_output is not None:
        new["corrupted_output"] = corrupted_output
        new["repair_task_type"] = "observed_bad_free_run_to_clean_target"
        new["route"] = "USE_FOR_DENOISE_REPAIR"
    mi = new.setdefault("model_input", {})
    mi["target_grounding_mode"] = "prefix_ladder_supported_suffix_v1"
    mi["active_generation_prefix_span"] = prefix
    mi["active_generation_prefix_words"] = prefix_words
    mi[f"prefix_ladder_{prefix_words}w"] = prefix
    mi["remaining_suffix_hidden_from_model_input"] = True
    mi["remaining_suffix_word_count"] = len(suffix.split())
    istate = new.setdefault("input_state", {})
    istate["prefix_ladder_objective"] = True
    istate["active_generation_prefix_word_count"] = prefix_words
    istate["active_generation_prefix_char_count"] = len(prefix)
    istate["remaining_suffix_hidden_from_model_input"] = True
    istate["remaining_suffix_word_count"] = len(suffix.split())
    istate["remaining_suffix_sha256"] = hashlib.sha256(suffix.encode("utf-8")).hexdigest()
    istate["first_suffix_word_hidden_from_model_input"] = True
    ac = new.setdefault("anti_cheat", {})
    ac["decoder_ce_closed"] = True
    ac["runtime_closed"] = True
    ac["first_suffix_word_visible"] = False
    ac["remaining_suffix_visible"] = False
    ac["partial_target_in_model_visible_fields"] = False
    new["authority"] = dict(AUTHORITY_CLOSED)
    new["loss_mask"] = {"decoder_ce": False, "denoise_ce": True, "runtime_reward": False}
    return new


def build_rows(base_rows: list[dict[str, Any]], samples: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in base_rows:
        for n in (5, 6, 7, 8):
            rows.append(make_variant(row, prefix_words=n, variant="ladder"))
    by_row = {str(sample.get("row_id")): sample for sample in samples.get("samples", []) if isinstance(sample, dict)}
    for row in base_rows:
        sample = by_row.get(str(row.get("row_id")))
        if not sample or sample.get("exact_match"):
            continue
        generated = str(sample.get("generated_text") or "")
        if not generated:
            continue
        target = str(sample.get("target_text") or "")
        prefix_words = min(8, max(5, len(generated.split())))
        variant = f"observed_{failure_kind(generated)}"
        rows.append(make_variant(row, prefix_words=prefix_words, variant=variant, corrupted_output=generated))
    return rows


def audit_rows(rows: list[dict[str, Any]], source_summary: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("source_stage9309_not_passed")
    if not rows:
        failures.append("no_rows")
    split_counts = Counter(str(row.get("split")) for row in rows)
    prefix_counts = Counter(int((row.get("model_input") or {}).get("active_generation_prefix_words", -1)) for row in rows)
    variant_counts = Counter(str(row.get("repair_task_type")) for row in rows)
    authority_rows = sum(1 for row in rows if any(bool(v) for v in (row.get("authority") or {}).values()))
    unsafe_loss_rows = sum(1 for row in rows if (row.get("loss_mask") or {}).get("decoder_ce") or not (row.get("loss_mask") or {}).get("denoise_ce"))
    suffix_visible_rows = sum(1 for row in rows if (row.get("anti_cheat") or {}).get("first_suffix_word_visible") or (row.get("anti_cheat") or {}).get("remaining_suffix_visible"))
    missing_prefix_rows = sum(1 for row in rows if not (row.get("model_input") or {}).get("active_generation_prefix_span"))
    by_base: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        if row.get("repair_task_type") == "prefix_ladder_to_remaining_suffix":
            by_base[str(row.get("source_base_row_id"))].add(int((row.get("model_input") or {}).get("active_generation_prefix_words", -1)))
    weak_base_rows = sorted(base for base, values in by_base.items() if values != {5, 6, 7, 8})
    for name, count in {
        "authority_rows_present": authority_rows,
        "unsafe_loss_rows_present": unsafe_loss_rows,
        "suffix_visible_rows_present": suffix_visible_rows,
        "missing_prefix_rows_present": missing_prefix_rows,
    }.items():
        if count:
            failures.append(name)
    if weak_base_rows:
        failures.append("prefix_ladder_incomplete_for_base_rows")
    if not all(prefix_counts.get(n, 0) >= 7 for n in (5, 6, 7, 8)):
        failures.append("prefix_length_coverage_too_low")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(split_counts),
        "language_counts": dict(Counter(str(row.get("language_family")) for row in rows)),
        "prefix_counts": dict(sorted(prefix_counts.items())),
        "variant_counts": dict(variant_counts),
        "authority_rows": authority_rows,
        "unsafe_loss_rows": unsafe_loss_rows,
        "suffix_visible_rows": suffix_visible_rows,
        "missing_prefix_rows": missing_prefix_rows,
        "weak_base_rows": weak_base_rows,
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
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows(load_jsonl(BASE_MANIFEST), load_json(SAMPLES))
    write_jsonl(MANIFEST, rows)
    audit = audit_rows(rows, load_json(SOURCE_SUMMARY))
    audit["manifest_sha256"] = sha256(MANIFEST)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Materialized prefix-ladder denoise rows at 5/6/7/8-word prefixes plus observed bad-output repair rows from Stage9308 failures.",
        "next_best_step": "Build Stage9311 prefix-ladder probe preexecution wrapper; keep decoder CE/runtime/Gemma/harness closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9310 Prefix-Ladder Supported-Suffix Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Prefix counts: `{audit['prefix_counts']}`",
                f"Variant counts: `{audit['variant_counts']}`",
                "",
                "This manifest is still denoise-only. It does not open decoder CE, runtime, Gemma, harness, scoring, checkpoint export, or promotion.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
