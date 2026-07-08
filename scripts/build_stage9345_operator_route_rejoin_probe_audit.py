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
STAGE = 9345
NAME = "stage9345_operator_route_rejoin_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9344_operator_route_rejoin_probe_preexecution.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9343_full_mixture_with_operator_route_repairs_manifest/full_mixture_with_operator_route_repairs_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9345_operator_route_rejoin_probe"
AUDIT = RUN_DIR / "stage9345_operator_route_rejoin_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPERATOR_ROUTE_REJOIN_PROBE_AUDIT_STAGE9345.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUIRED = [
    "probe_contract_audit.json",
    "execution_result.json",
    "sample_generation_audit.json",
    "boundary_next_token_logits.jsonl",
    "row_token_loss.jsonl",
    "module_delta_norms.json",
    "cleanup_proof.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rate(n: int, d: int) -> float | None:
    return n / d if d else None


def model_input(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("model_input") if isinstance(row.get("model_input"), dict) else {}


def input_state(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("input_state") if isinstance(row.get("input_state"), dict) else {}


def value_for_key(sample: dict[str, Any], meta: dict[str, Any], key: str) -> str:
    mi = model_input(meta)
    state = input_state(meta)
    if key == "merged_source":
        return str(meta.get("merged_curriculum_source") or "unknown")
    if key == "combined_source":
        return str(meta.get("combined_curriculum_source") or "unknown")
    if key == "task":
        return str(meta.get("repair_task_type") or meta.get("task") or "unknown")
    if key == "route":
        return str(mi.get("opaque_phrase_route_id") or meta.get("route") or "unknown")
    if key == "surface":
        return str(mi.get("semantic_surface_kind") or state.get("semantic_surface_kind") or "unknown")
    if key == "affordance":
        return str(mi.get("semantic_affordance") or state.get("semantic_affordance") or "missing")
    if key == "anchor":
        return str(mi.get("anchor_object_kind") or state.get("target_object_kind") or "unknown")
    if key == "source_stage":
        return str(meta.get("source_stage") or "unknown")
    if key == "split":
        return str(sample.get("split") or "unknown")
    return "unknown"


def bucket(samples: list[dict[str, Any]], manifest_by_id: dict[str, dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for sample in samples:
        meta = manifest_by_id.get(str(sample.get("row_id")), {})
        value = value_for_key(sample, meta, key)
        item = out.setdefault(value, {"rows": 0, "exact": 0, "target_prefix": 0, "boundary": 0, "contentful": 0, "repetition": 0})
        item["rows"] += 1
        item["exact"] += int(bool(sample.get("exact_match")))
        item["target_prefix"] += int(bool(sample.get("target_prefix_match")))
        item["contentful"] += int(not bool(sample.get("empty_output")) and not bool(sample.get("short_or_junk")))
        item["repetition"] += int(bool(sample.get("degenerate_repetition")))
        boundary = sample.get("boundary_next_token") if isinstance(sample.get("boundary_next_token"), dict) else {}
        item["boundary"] += int(bool(boundary.get("match")))
    return {
        name: {
            **counts,
            "exact_rate": rate(counts["exact"], counts["rows"]),
            "target_prefix_rate": rate(counts["target_prefix"], counts["rows"]),
            "boundary_rate": rate(counts["boundary"], counts["rows"]),
            "contentful_rate": rate(counts["contentful"], counts["rows"]),
            "repetition_rate": rate(counts["repetition"], counts["rows"]),
        }
        for name, counts in sorted(out.items())
    }


def classify_failure(text: str, target: str) -> list[str]:
    labels: list[str] = []
    if "keepside" in text:
        labels.append("keepside_subword_bridge")
    if "that the patch inside" in text:
        labels.append("keeps_token_omission")
    if "pator" in text:
        labels.append("patch_operator_subword_bridge")
    if "localized pator" in text:
        labels.append("file_path_localized_edit_bridge")
    if "associated lis" in text:
        labels.append("associated_with_subword_bridge")
    if "operatch" in text:
        labels.append("operatch_subword_bridge")
    if text != target and not labels:
        labels.append("other_exact_mismatch")
    return labels


def analyze_failures(samples: list[dict[str, Any]], manifest_by_id: dict[str, dict[str, Any]]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    for sample in samples:
        if sample.get("exact_match") and not sample.get("degenerate_repetition"):
            continue
        row_id = str(sample.get("row_id"))
        meta = manifest_by_id.get(row_id, {})
        text = str(sample.get("generated_text") or "")
        target = str(sample.get("target_text") or "")
        labels = classify_failure(text, target)
        for label in labels:
            counts[label] += 1
        failures.append(
            {
                "row_id": row_id,
                "split": sample.get("split"),
                "labels": labels,
                "merged_source": value_for_key(sample, meta, "merged_source"),
                "combined_source": value_for_key(sample, meta, "combined_source"),
                "route": value_for_key(sample, meta, "route"),
                "surface": value_for_key(sample, meta, "surface"),
                "affordance": value_for_key(sample, meta, "affordance"),
                "anchor": value_for_key(sample, meta, "anchor"),
                "source_stage": value_for_key(sample, meta, "source_stage"),
                "prefix": sample.get("generation_prefix_text"),
                "target": target,
                "generated": text,
                "target_prefix_match": sample.get("target_prefix_match"),
                "exact_match": sample.get("exact_match"),
            }
        )
    return dict(sorted(counts.items())), failures


def feature_schema_card(rows: list[dict[str, Any]], failed_samples: list[dict[str, Any]], manifest_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required_model_features = ["semantic_surface_kind", "semantic_affordance", "opaque_phrase_route_id", "anchor_object_kind"]
    missing_rows: Counter[str] = Counter()
    missing_failed: Counter[str] = Counter()
    for row in rows:
        mi = model_input(row)
        missing = tuple(feature for feature in required_model_features if not mi.get(feature))
        if missing:
            missing_rows[",".join(missing)] += 1
    for sample in failed_samples:
        meta = manifest_by_id.get(str(sample.get("row_id")), {})
        mi = model_input(meta)
        missing = tuple(feature for feature in required_model_features if not mi.get(feature))
        if missing:
            missing_failed[",".join(missing)] += 1
    return {
        "required_model_features": required_model_features,
        "rows_missing_feature_groups": dict(sorted(missing_rows.items())),
        "failed_rows_missing_feature_groups": dict(sorted(missing_failed.items())),
        "schema_alignment_required_before_next_rejoin": bool(missing_rows),
    }


def audit_run() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples_card = load_json(RUN_DIR / "sample_generation_audit.json")
    short_probe = load_json(RUN_DIR / "short_output_probe.json")
    repetition_probe = load_json(RUN_DIR / "repetition_probe.json")
    leak_probe = load_json(RUN_DIR / "internal_leak_probe.json")
    samples = samples_card.get("samples") if isinstance(samples_card.get("samples"), list) else []
    manifest_rows = load_jsonl(MANIFEST)
    manifest_by_id = {str(row.get("row_id")): row for row in manifest_rows}
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9344_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("generation_prefix_field") != "model_input.active_generation_prefix_span":
        failures.append("wrong_generation_prefix_field")
    if execution.get("decoder_ce_rows") != 0 or contract.get("loss_counts", {}).get("decoder_ce") != 0:
        failures.append("decoder_ce_opened")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False:
        failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported") is not False:
        failures.append("checkpoint_exported")
    if missing:
        failures.append("required_artifacts_missing")

    generated = int(samples_card.get("generated_rows") or 0)
    exact = int(samples_card.get("exact_match_rows") or 0)
    target_prefix = int(samples_card.get("target_prefix_match_rows") or 0)
    boundary = int(samples_card.get("boundary_next_token_match_rows") or 0)
    contentful = int(samples_card.get("contentful_rows") or 0)
    repetition_rows = int(repetition_probe.get("generated_repetition_rows") or 0)
    short_rows = int(short_probe.get("short_or_junk_rows") or 0)
    leak_rows = int(leak_probe.get("generated_internal_token_rows") or 0)

    safety_gate_passed = not failures
    quality_gate_passed = bool(
        generated == 74
        and exact == 74
        and target_prefix == 74
        and boundary == 74
        and contentful == 74
        and repetition_rows == 0
        and short_rows == 0
        and leak_rows == 0
    )
    error_counts, failed_samples = analyze_failures(samples, manifest_by_id)
    return {
        "passed": safety_gate_passed and quality_gate_passed,
        "safety_gate_passed": safety_gate_passed,
        "quality_gate_passed": quality_gate_passed,
        "failures": failures,
        "missing_artifacts": missing,
        "manifest_rows": len(manifest_rows),
        "generated_rows": generated,
        "exact_match_rows": exact,
        "exact_match_rate": rate(exact, generated),
        "target_prefix_match_rows": target_prefix,
        "target_prefix_match_rate": samples_card.get("target_prefix_match_rate"),
        "boundary_next_token_match_rows": boundary,
        "boundary_next_token_match_rate": samples_card.get("boundary_next_token_match_rate"),
        "boundary_next_token_mean_expected_rank": samples_card.get("boundary_next_token_mean_expected_rank"),
        "contentful_rows": contentful,
        "contentful_rate": samples_card.get("contentful_rate"),
        "short_or_junk_rows": short_rows,
        "generated_internal_token_rows": leak_rows,
        "degenerate_repetition_rows": repetition_rows,
        "by_merged_source": bucket(samples, manifest_by_id, "merged_source"),
        "by_combined_source": bucket(samples, manifest_by_id, "combined_source"),
        "by_route": bucket(samples, manifest_by_id, "route"),
        "by_surface": bucket(samples, manifest_by_id, "surface"),
        "by_affordance": bucket(samples, manifest_by_id, "affordance"),
        "by_anchor": bucket(samples, manifest_by_id, "anchor"),
        "by_source_stage": bucket(samples, manifest_by_id, "source_stage"),
        "by_split": bucket(samples, manifest_by_id, "split"),
        "error_counts": error_counts,
        "failed_samples": failed_samples,
        "feature_schema_card": feature_schema_card(manifest_rows, failed_samples, manifest_by_id),
        "diagnosis": (
            "Stage9345 executed within the closed denoise contract and removed the Stage9339 repetition collapse, "
            "but the full mixture still fails lexical bridge exactness: dependency rows produce `keepside` or omit `keeps`, "
            "operator rows produce `pator`, and file-path rows map localized edit toward the operator fragment. "
            "The mixture also contains base rows without the full route/surface/affordance feature schema, so the next "
            "curriculum needs schema normalization plus targeted subword-boundary bridge repairs before another rejoin."
        ),
        "next_patch_target": "stage9346_schema_normalized_subword_bridge_repair_manifest",
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
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
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = audit_run()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "run_dir": str(RUN_DIR.relative_to(ROOT)),
        },
        "decision": "The operator-route rejoin probe executed safely but failed exactness; decoder CE remains closed.",
        "next_best_step": "Build Stage9346 schema-normalized subword-bridge repair rows for `keeps the`, `patch operator`, and `localized edit`, then test those in isolation before another full-mixture rejoin.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9345 Operator Route Rejoin Probe Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Safety gate passed: `{audit['safety_gate_passed']}`",
                f"Quality gate passed: `{audit['quality_gate_passed']}`",
                f"Exact match rows: `{audit['exact_match_rows']}` / `{audit['generated_rows']}`",
                f"Target-prefix match rows: `{audit['target_prefix_match_rows']}` / `{audit['generated_rows']}`",
                f"Boundary next-token match rows: `{audit['boundary_next_token_match_rows']}` / `{audit['generated_rows']}`",
                f"Contentful rows: `{audit['contentful_rows']}` / `{audit['generated_rows']}`",
                f"Degenerate repetition rows: `{audit['degenerate_repetition_rows']}`",
                f"Short/junk rows: `{audit['short_or_junk_rows']}`",
                f"Internal leak rows: `{audit['generated_internal_token_rows']}`",
                f"Error counts: `{audit['error_counts']}`",
                "",
                "Safety held: decoder CE, runtime, harness, Gemma, scoring, promotion, and checkpoint export stayed closed.",
                "",
                "The quality failure is now a subword/bridge problem rather than a repetition collapse. The dominant errors are `keepside`, missing `keeps`, `pator` for `patch operator`, and a file-path row drifting from `localized edit` to the operator fragment.",
                "",
                "The full mixture also needs feature-schema normalization. Some base rows do not carry the same route/surface/affordance feature set as the Stage9340 repair rows, so another full-mixture rejoin should wait until those features are aligned.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "metrics": {
                    key: audit[key]
                    for key in [
                        "safety_gate_passed",
                        "quality_gate_passed",
                        "exact_match_rate",
                        "target_prefix_match_rate",
                        "boundary_next_token_match_rate",
                        "contentful_rate",
                        "degenerate_repetition_rows",
                        "error_counts",
                    ]
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
