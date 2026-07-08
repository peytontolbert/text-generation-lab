#!/usr/bin/env python3
from __future__ import annotations

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
STAGE = 9309
NAME = "stage9309_prefix_ladder_curriculum_design"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9308_copy_prefix_multitoken_probe_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9308_copy_prefix_multitoken_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "prefix_ladder_curriculum_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PREFIX_LADDER_CURRICULUM_DESIGN_STAGE9309.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def classify_failure(sample: dict[str, Any]) -> str:
    if sample.get("exact_match"):
        return "exact"
    generated = str(sample.get("generated_text") or "")
    target = str(sample.get("target_text") or "")
    if len(generated.strip()) < len(target.strip()) * 0.65:
        return "early_eos_or_short_continuation"
    words = generated.split()
    if len(words) >= 4 and len(set(words[-4:])) <= 2:
        return "late_suffix_repetition"
    if "operatch" in generated or "keepside" in generated:
        return "subword_bridge_collapse"
    return "suffix_drift"


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
    source = load_json(SOURCE_SUMMARY)
    samples = load_json(RUN_DIR / "sample_generation_audit.json")
    sample_rows = samples.get("samples") if isinstance(samples.get("samples"), list) else []
    failures = [sample for sample in sample_rows if not sample.get("exact_match")]
    failure_types = Counter(classify_failure(sample) for sample in failures)
    design = {
        "passed": source.get("passed") is True,
        "source_stage": 9308,
        "source_quality_gate_passed": ((source.get("metrics") or {}).get("quality_gate_passed") is True),
        "diagnosis": "boundary_next_token_is_solved_but_copy_prefix_free_run_suffix_continuation_is_not_stable",
        "generated_rows": samples.get("generated_rows"),
        "exact_match_rows": samples.get("exact_match_rows"),
        "target_prefix_match_rate": samples.get("target_prefix_match_rate"),
        "failure_types": dict(failure_types),
        "recommended_patch": {
            "name": "prefix_ladder_supported_suffix_manifest",
            "intent": "bridge teacher-forced suffix learning to free-run continuation by training/auditing multiple prefix lengths per target",
            "prefix_fields_to_materialize": [
                "model_input.copy_prefix_span",
                "model_input.prefix_ladder_6w",
                "model_input.prefix_ladder_7w",
                "model_input.bridge_priming_span",
            ],
            "row_variants": [
                "copy_prefix_to_full_suffix",
                "six_word_prefix_to_remaining_suffix",
                "seven_word_prefix_to_remaining_suffix",
                "bridge_prefix_to_final_suffix",
                "observed_bad_free_run_to_clean_target",
            ],
            "required_audits": [
                "first_token_boundary_rank_by_prefix_length",
                "exact_generation_by_prefix_length",
                "suffix_repetition_rate",
                "early_eos_rate",
                "subword_bridge_collapse_rows",
                "row_token_loss_on_unmasked_suffix_only",
            ],
            "authority": dict(AUTHORITY_CLOSED),
        },
        "blocked_actions": [
            "do_not_reopen_decoder_ce",
            "do_not_widen_to_real_decoder_rows",
            "do_not_run_runtime_or_harness",
            "do_not_export_checkpoint",
        ],
    }
    DESIGN.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": bool(design["passed"]),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "source_quality_gate_passed": design["source_quality_gate_passed"], "generated_rows": design["generated_rows"], "exact_match_rows": design["exact_match_rows"], "target_prefix_match_rate": design["target_prefix_match_rate"], "failure_types": design["failure_types"]},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Stage9308 proved first-token boundary recovery but not stable multi-token free-run continuation from the shorter copy prefix.",
        "next_best_step": "Build Stage9310 prefix-ladder supported-suffix manifest and audit it before another tiny target-100M denoise probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9309 Prefix-Ladder Curriculum Design",
                "",
                "Stage9308 kept safety closed but failed the multi-token quality gate.",
                "",
                "Finding:",
                "- Boundary next-token rank is solved: expected rank 1 on every row.",
                "- Free-run suffix continuation from `model_input.copy_prefix_span` is unstable.",
                "- Observed failures include `keepside` and `operatch` repetition.",
                "",
                "Next patch:",
                "- Materialize prefix-ladder variants at 5, 6, 7, and bridge word prefixes.",
                "- Add denoise rows from observed bad free-run output to clean target.",
                "- Keep decoder CE, runtime, Gemma, harness, scoring, checkpoint export, and promotion closed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
