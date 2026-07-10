#!/usr/bin/env python3
from __future__ import annotations

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
STAGE = 9804
NAME = "stage9804_opaque_choice_option_token_probe_audit"
RUN_DIR = ROOT / "runs/local/artifacts/stage9803_opaque_choice_option_token_probe"
AUDIT = RUN_DIR / "opaque_choice_option_token_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPAQUE_CHOICE_OPTION_TOKEN_PROBE_AUDIT_STAGE9804.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
GEN_AUDIT = RUN_DIR / "sample_generation_audit.json"
PREEXEC = ROOT / "runs/summaries/stage9802_opaque_choice_option_token_preexecution.json"
STRUCTURED_COMPARE = ROOT / "runs/local/artifacts/stage9793_edit_localization_opaque_choice_gemma_comparison/edit_localization_opaque_choice_gemma_comparison.json"
PRIOR_DECODER_AUDIT = ROOT / "runs/local/artifacts/stage9799_opaque_choice_bounded_decoder_probe/opaque_choice_bounded_decoder_probe_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_audit() -> dict[str, Any]:
    preexec = load_json(PREEXEC)
    generated = load_json(GEN_AUDIT)
    compare = load_json(STRUCTURED_COMPARE)
    prior = load_json(PRIOR_DECODER_AUDIT)
    failures: list[str] = []
    samples = generated.get("samples") if isinstance(generated.get("samples"), list) else []
    if preexec.get("passed") is not True:
        failures.append("source_stage9802_not_passed")
    if not samples:
        failures.append("missing_generation_samples")
    predicted = [str(row.get("generated_text") or "") for row in samples]
    targets = [str(row.get("target_text") or "") for row in samples]
    label_counts = Counter(predicted)
    exact_rows = sum(1 for pred, target in zip(predicted, targets) if pred == target)
    dominant_label, dominant_count = ("", 0)
    if label_counts:
        dominant_label, dominant_count = sorted(label_counts.items(), key=lambda item: (-item[1], str(item[0])))[0]
    collapsed_single_label = dominant_count == len(predicted) and len(predicted) > 0
    compare_results = compare.get("results") if isinstance(compare.get("results"), list) else []
    passed = not failures and exact_rows >= 16 and not collapsed_single_label
    return {
        "passed": passed,
        "failures": failures,
        "generated_rows": len(predicted),
        "exact_match_rows": exact_rows,
        "exact_match_rate": (exact_rows / len(predicted)) if predicted else None,
        "dominant_label": dominant_label,
        "dominant_label_rows": dominant_count,
        "dominant_label_rate": (dominant_count / len(predicted)) if predicted else None,
        "collapsed_single_label": collapsed_single_label,
        "predicted_label_counts": dict(sorted(label_counts.items())),
        "generated_split_set": sorted({str(row.get("split") or "") for row in samples}),
        "contentful_rate": generated.get("contentful_rate"),
        "short_or_junk_rate": load_json(RUN_DIR / "short_output_probe.json").get("short_or_junk_rate"),
        "prior_decoder_collapse": {
            "dominant_label": prior.get("dominant_label"),
            "dominant_label_rate": prior.get("dominant_label_rate"),
            "exact_match_rate": prior.get("exact_match_rate"),
        },
        "structured_baseline_summary": {
            "wins_100m": compare.get("wins_100m"),
            "wins_gemma": compare.get("wins_gemma"),
            "ties": compare.get("ties"),
            "per_language": compare_results,
        },
        "diagnosis": (
            "The revised `option X` decoder target format fixed the Stage9799 junk-output failure and enabled both eval and strict-eval generation, "
            "but it still collapsed to a single dominant class and did not beat the structured Stage9794 path."
        ),
        "next_patch_target": "opaque_choice_decoder_objective_or_sampling_revision",
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Keep the structured Stage9794 path as the truthful standalone comparator. If decoder-side work continues, revise the objective again rather than repeating the same collapsed class-token training pattern."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Audited the Stage9803 revised decoder-target probe and compared it against both the prior Stage9799 decoder run and the structured Stage9794 standalone baseline.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9804 Opaque Choice Option Token Probe Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Generated rows: `{audit['generated_rows']}`",
                f"Exact match rows: `{audit['exact_match_rows']}`",
                f"Dominant label: `{audit['dominant_label']}`",
                f"Dominant label rows: `{audit['dominant_label_rows']}`",
                f"Collapsed single label: `{audit['collapsed_single_label']}`",
                f"Contentful rate: `{audit['contentful_rate']}`",
                f"Short/junk rate: `{audit['short_or_junk_rate']}`",
                "",
                "This audit shows that `option X` targets are better than bare A-E for generation cleanliness, but still not sufficient to outperform the structured multilingual comparator.",
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"exact_match_rate": audit["exact_match_rate"], "dominant_label": audit["dominant_label"], "dominant_label_rate": audit["dominant_label_rate"], "collapsed_single_label": audit["collapsed_single_label"], "contentful_rate": audit["contentful_rate"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
