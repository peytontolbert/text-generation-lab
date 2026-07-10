#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10069
NAME = "stage10069_canonical_label_aligned_multilingual_successor_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "canonical_label_aligned_multilingual_successor_packet.json"
MANIFEST = OUT_DIR / "canonical_label_aligned_multilingual_manifest.jsonl"
ROWS = OUT_DIR / "canonical_label_aligned_multilingual_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_LABEL_ALIGNED_MULTILINGUAL_SUCCESSOR_PACKET_STAGE10069.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10062_web_non_b_anticollapse_successor_packet/web_non_b_anticollapse_successor_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage10068_multilingual_label_semantics_collision_audit.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"

CANONICAL_LABEL_MAP = {
    "TARGET_TEST": "A",
    "TARGET_ENTRYPOINT": "B",
    "TARGET_SYMBOL": "C",
    "TARGET_FILE": "D",
    "TARGET_CONFIG": "E",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_readiness():
    spec = importlib.util.spec_from_file_location("train_agentkernel_lite_encdec", TRAINER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return getattr(module, "assess_multilingual_surface_readiness")


def _canonicalize_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(row)
    clean = updated.get("clean_state") if isinstance(updated.get("clean_state"), dict) else {}
    target = updated.get("target") if isinstance(updated.get("target"), dict) else {}
    hidden = str(clean.get("edit_localization_target_hidden") or "")
    if not hidden:
        raise KeyError(f"missing hidden target for {row.get('row_id')}")
    canonical = CANONICAL_LABEL_MAP[hidden]
    clean["edit_localization"] = canonical
    clean["edit_localization_target"] = canonical
    target["decoder_text"] = canonical
    target["edit_localization"] = canonical
    target["target_ref"] = canonical
    updated["clean_state"] = clean
    updated["target"] = target
    if "stage10047_expected_label" in updated:
        updated["stage10047_expected_label"] = canonical
    if "stage10056_expected_label" in updated:
        updated["stage10056_expected_label"] = canonical
    if "stage10062_expected_label" in updated:
        updated["stage10062_expected_label"] = canonical
    if "stage10065_expected_label" in updated:
        updated["stage10065_expected_label"] = canonical
    updated["stage10069_canonical_label"] = canonical
    updated["stage10069_hidden_target"] = hidden
    return updated


def build_packet() -> dict[str, Any]:
    base_rows = load_jsonl(BASE_MANIFEST)
    source_summary = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    remapped_rows: list[dict[str, Any]] = []
    remap_counts: Counter[str] = Counter()
    per_language_hidden: dict[str, dict[str, str]] = {}

    for row in base_rows:
        try:
            updated = _canonicalize_row(row)
        except Exception:
            failures.append(f"canonicalize_failed:{row.get('row_id')}")
            continue
        remapped_rows.append(updated)
        language = str(updated.get("language_family") or "")
        label = str((updated.get("clean_state") or {}).get("edit_localization_target") or "")
        hidden = str((updated.get("clean_state") or {}).get("edit_localization_target_hidden") or "")
        per_language_hidden.setdefault(language, {})[label] = hidden
        remap_counts[f"{language}:{label}"] += 1

    write_jsonl(ROWS, remapped_rows)
    write_jsonl(MANIFEST, remapped_rows)

    assess_multilingual_surface_readiness = _load_readiness()
    readiness = assess_multilingual_surface_readiness("edit_localization_probe", remapped_rows)
    if not readiness or readiness.get("passed") is not True:
        failures.append("canonical_manifest_readiness_failed")

    language_counts = Counter(str(row.get("language_family") or "") for row in remapped_rows)
    split_counts = Counter(str(row.get("split") or "") for row in remapped_rows)
    metrics = {
        "rows": len(remapped_rows),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "remap_counts": dict(sorted(remap_counts.items())),
        "per_language_label_map": {language: dict(sorted(mapping.items())) for language, mapping in sorted(per_language_hidden.items())},
        "canonical_label_map": dict(sorted(CANONICAL_LABEL_MAP.items())),
        "readiness_passed": bool(readiness and readiness.get("passed")),
        "readiness_failed_buckets": list((readiness or {}).get("failed_buckets") or []),
    }
    if source_summary.get("passed") is not True:
        failures.append("stage10068_not_passed")
    if metrics["rows"] != 142:
        failures.append("rows_not_142")
    if split_counts.get("train") != 87:
        failures.append("train_rows_not_87")
    if split_counts.get("eval") != 38:
        failures.append("eval_rows_not_38")
    if split_counts.get("strict_eval") != 17:
        failures.append("strict_rows_not_17")
    if language_counts.get("python") != 27:
        failures.append("python_rows_not_27")
    if language_counts.get("c_cpp") != 38:
        failures.append("c_cpp_rows_not_38")
    if language_counts.get("rust") != 17:
        failures.append("rust_rows_not_17")
    if language_counts.get("web_js_ts_html") != 60:
        failures.append("web_rows_not_60")
    expected_map = {
        "A": "TARGET_TEST",
        "B": "TARGET_ENTRYPOINT",
        "C": "TARGET_SYMBOL",
        "D": "TARGET_FILE",
        "E": "TARGET_CONFIG",
    }
    for language, mapping in per_language_hidden.items():
        if language == "python":
            # Python does not cover every label family in the selected train rows, but heldout rows should still align where present.
            for label, hidden in mapping.items():
                if expected_map[label] != hidden:
                    failures.append(f"python_canonical_mismatch:{label}")
        else:
            for label, hidden in expected_map.items():
                if mapping.get(label) != hidden:
                    failures.append(f"canonical_mismatch:{language}:{label}")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "policy": {
            "preserve_stage10062_row_composition": True,
            "canonicalize_label_semantics_only": True,
            "no_new_train_rows_added": True,
            "same_visible_encoder_surface": True,
        },
        "inputs": {
            "base_manifest": display(BASE_MANIFEST),
            "collision_audit": display(Path("runs/local/artifacts/stage10068_multilingual_label_semantics_collision_audit/multilingual_label_semantics_collision_audit.json")),
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    write_json(PACKET, built)
    next_step = "Run the target-100m probe and local Gemma queue on this canonical-label multilingual manifest, then compare them on the same 55 heldout rows."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "packet": display(PACKET),
            "rows": display(ROWS),
            "manifest": display(MANIFEST),
            "doc": display(DOC),
        },
        "decision": "Materialized a canonical-label multilingual successor packet by remapping the stage10062 frontier manifest so every hidden edit-target family uses the same opaque label across languages while preserving the visible encoder surface.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10069 Canonical Label Aligned Multilingual Successor Packet",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{built['metrics']['rows']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
