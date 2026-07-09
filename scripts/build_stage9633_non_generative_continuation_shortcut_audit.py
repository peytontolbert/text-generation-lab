#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9633
NAME = "stage9633_non_generative_continuation_shortcut_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9632_non_generative_repetition_eos_continuation_preflight.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9632_non_generative_repetition_eos_continuation_preflight/non_generative_repetition_eos_continuation_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "non_generative_continuation_shortcut_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NON_GENERATIVE_CONTINUATION_SHORTCUT_AUDIT_STAGE9633.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
FORBIDDEN_ENCODER_MARKERS = [
    "target_prefix_match=",
    "boundary_next_token_match=",
    "prefix_start_match=",
    "stopped_on_eos=",
    "repair_outcome=",
    "failure_type=",
    "reward=",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def label(row: dict[str, Any], target: str) -> str:
    tr = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    if target == "repair_outcome":
        return str((tr.get("state_t_plus_1") or {}).get("repair_outcome"))
    if target == "failure_type":
        return str((tr.get("reward_or_verifier") or {}).get("failure_type"))
    if target == "boundary_match":
        return str((tr.get("observation_t") or {}).get("boundary_next_token_match"))
    if target == "target_prefix_match":
        return str((tr.get("observation_t") or {}).get("target_prefix_match"))
    return ""


def feature(row: dict[str, Any], name: str) -> str:
    tr = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    state = tr.get("state_t") if isinstance(tr.get("state_t"), dict) else {}
    obs = tr.get("observation_t") if isinstance(tr.get("observation_t"), dict) else {}
    if name == "source_stage":
        return str(state.get("source_stage"))
    if name == "guard_event_count_bucket":
        count = int(state.get("guard_event_count") or 0)
        return "zero" if count == 0 else ("one" if count == 1 else "many")
    if name == "generated_len_bucket":
        n = len(str(obs.get("generated_text") or ""))
        return "short" if n < 60 else ("medium" if n < 100 else "long")
    if name == "prefix_token_count_bucket":
        n = len(str(state.get("generation_prefix_text") or "").split())
        return "short" if n <= 5 else "long"
    return ""


def baseline_exact(rows: list[dict[str, Any]], feature_name: str, target_name: str) -> float:
    table: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        table[feature(row, feature_name)][label(row, target_name)] += 1
    mapping = {key: counts.most_common(1)[0][0] for key, counts in table.items() if counts}
    if not rows:
        return 0.0
    return sum(1 for row in rows if mapping.get(feature(row, feature_name)) == label(row, target_name)) / len(rows)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9632_not_passed")
    forbidden_rows = []
    for row in rows:
        text = str(row.get("encoder_text") or "")
        hits = [marker for marker in FORBIDDEN_ENCODER_MARKERS if marker in text]
        if hits:
            forbidden_rows.append({"row_id": row.get("row_id"), "hits": hits})
    if forbidden_rows:
        failures.append("forbidden_encoder_label_markers_present")
    features = ["source_stage", "guard_event_count_bucket", "generated_len_bucket", "prefix_token_count_bucket"]
    targets = ["repair_outcome", "failure_type", "boundary_match", "target_prefix_match"]
    baselines = {f"{feat}->{tgt}": baseline_exact(rows, feat, tgt) for feat in features for tgt in targets}
    strongest = max(baselines.values()) if baselines else 0.0
    strongest_key = max(baselines, key=baselines.get) if baselines else None
    if strongest >= 0.90:
        failures.append("single_feature_baseline_too_high")
    label_counts = {target: dict(Counter(label(row, target) for row in rows)) for target in targets}
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "forbidden_encoder_label_marker_rows": len(forbidden_rows),
        "forbidden_encoder_label_marker_examples": forbidden_rows[:20],
        "single_feature_baselines": baselines,
        "strongest_single_feature_baseline": strongest,
        "strongest_single_feature_baseline_key": strongest_key,
        "label_counts": label_counts,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If execution remains authorized, run a tiny episode-step structured probe only if the baseline ceiling is acceptable; otherwise build counterbalanced observe-phase rows first."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Shortcut audit passed for forbidden direct label markers; remaining single-feature baselines are telemetry for the next execution decision.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9633 Non-Generative Continuation Shortcut Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Forbidden encoder marker rows: `{audit['forbidden_encoder_label_marker_rows']}`",
        f"Strongest single-feature baseline: `{strongest}` via `{strongest_key}`",
        "",
        "The manifest no longer exposes direct target-prefix or boundary-match labels in encoder text. Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "strongest_single_feature_baseline": strongest, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
