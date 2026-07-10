#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9910
NAME = "stage9910_geometry_aware_opaque_choice_shortcut_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "geometry_aware_opaque_choice_shortcut_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GEOMETRY_AWARE_OPAQUE_CHOICE_SHORTCUT_AUDIT_STAGE9910.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9907_geometry_aware_opaque_choice_manifest/geometry_aware_opaque_choice_manifest.jsonl"
COMPARISON = ROOT / "runs/local/artifacts/stage9909_geometry_aware_opaque_choice_gemma_comparison/geometry_aware_opaque_choice_gemma_comparison.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
FIELD = "edit_localization"


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


build_prompt = _load_symbol(
    "stage9910_stage9909_cmp",
    ROOT / "scripts/build_stage9909_geometry_aware_opaque_choice_gemma_comparison.py",
    "build_prompt",
)
ROW_TEXT = _load_symbol(
    "stage9910_training_data",
    ROOT / "legacy_src/agentkernel_lite/training_data.py",
    "_row_text",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def expected_label(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    return str(target.get("decoder_text") or target.get("edit_localization") or clean.get("edit_localization") or "")


def row_language(row: dict[str, Any]) -> str:
    return str(row.get("language_family") or row.get("language") or "")


def row_split(row: dict[str, Any]) -> str:
    return str(row.get("split") or "")


def _contains_any(text: str, labels: list[str]) -> list[str]:
    return [label for label in labels if label in text]


def build_audit() -> dict[str, Any]:
    rows = load_jsonl(MANIFEST)
    comparison = load_json(COMPARISON)
    failures: list[str] = []
    if not rows:
        failures.append("missing_manifest_rows")
    if comparison.get("passed") is not True:
        failures.append("stage9909_comparison_not_passed")
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        lang = row_language(row)
        split = row_split(row)
        if lang in LANGS and split in {"eval", "strict_eval"}:
            grouped[(lang, split)].append(row)
    for key in grouped:
        grouped[key].sort(key=lambda row: str(row.get("row_id") or ""))
    records: list[dict[str, Any]] = []
    permutation_maps = Counter()
    for lang in LANGS:
        for split in ("eval", "strict_eval"):
            bucket = grouped.get((lang, split), [])
            if len(bucket) != 4:
                failures.append(f"bucket_rows_mismatch:{lang}:{split}:{len(bucket)}")
                continue
            prompt_valid_label_line_mentions = 0
            encoder_any_label_mentions = 0
            row_cards: list[dict[str, Any]] = []
            for row in bucket:
                prompt = build_prompt(row)
                encoder_surface = ROW_TEXT(row)
                labels = sorted({choice.split(":", 1)[0].replace("option ", "").strip() for choice in ((row.get("input_state") or {}).get("candidate_choices") or [])})
                permutation_maps[json.dumps(row.get("choice_permutation_map") or {}, sort_keys=True)] += 1
                prompt_valid_label_line_mentions += int("Valid labels:" in prompt)
                encoder_any_label_mentions += int(bool(_contains_any(encoder_surface, labels)))
                row_cards.append(
                    {
                        "row_id": row.get("row_id"),
                        "expected_label": expected_label(row),
                        "prompt_contains_valid_label_line": "Valid labels:" in prompt,
                        "choice_labels": labels,
                    }
                )
            records.append(
                {
                    "language_family": lang,
                    "split": split,
                    "rows": len(bucket),
                    "row_cards": row_cards,
                    "metrics": {
                        "prompt_rows_with_valid_label_line": prompt_valid_label_line_mentions,
                        "encoder_rows_with_option_labels_visible": encoder_any_label_mentions,
                    },
                }
            )
    metrics = {
        "validated_buckets": len(records),
        "buckets_with_prompt_label_vocab_exposed": sum(1 for row in records if row["metrics"]["prompt_rows_with_valid_label_line"] > 0),
        "unique_permutation_maps": len(permutation_maps),
        "comparison_wins_100m": comparison.get("wins_100m"),
        "comparison_wins_gemma": comparison.get("wins_gemma"),
        "comparison_ties": comparison.get("ties"),
    }
    if metrics["validated_buckets"] != 8:
        failures.append("validated_buckets_not_8")
    if metrics["buckets_with_prompt_label_vocab_exposed"] != 0:
        failures.append("prompt_still_exposes_valid_label_line")
    if metrics["unique_permutation_maps"] < 4:
        failures.append(f"too_few_unique_permutation_maps:{metrics['unique_permutation_maps']}")
    gate = {
        "opaque_label_surface_clean": metrics["buckets_with_prompt_label_vocab_exposed"] == 0,
        "label_proxy_shortcuts_pass_recommended": metrics["buckets_with_prompt_label_vocab_exposed"] == 0,
        "same_surface_claim_hardened": metrics["buckets_with_prompt_label_vocab_exposed"] == 0 and metrics["unique_permutation_maps"] >= 4,
        "reason": "the hardened opaque-choice geometry-aware packet removes the global valid-label prompt line and uses multiple row-local permutation maps across the evaluation buckets",
    }
    return {
        "passed": not failures,
        "failures": failures,
        "records": records,
        "metrics": metrics,
        "gate_recommendation": gate,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    AUDIT.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use Stage9909 plus this shortcut audit as the truthful multilingual edit-localization benchmark entry point, then attach expert-maintainer rubric review and broader capability coverage before claiming a wider v2.7 win."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Audited the hardened geometry-aware opaque-choice surface and verified that the prompt no longer prints the valid-label list while the row-local permutation maps remain diverse enough to block stable global label-proxy shortcuts.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9910 Geometry-Aware Opaque Choice Shortcut Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Validated buckets: `{built['metrics']['validated_buckets']}`",
        f"Buckets with prompt label exposure: `{built['metrics']['buckets_with_prompt_label_vocab_exposed']}`",
        f"Unique permutation maps: `{built['metrics']['unique_permutation_maps']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "validated_buckets": built["metrics"]["validated_buckets"], "buckets_with_prompt_label_vocab_exposed": built["metrics"]["buckets_with_prompt_label_vocab_exposed"], "unique_permutation_maps": built["metrics"]["unique_permutation_maps"]}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
