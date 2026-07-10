#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10068
NAME = "stage10068_multilingual_label_semantics_collision_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "multilingual_label_semantics_collision_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MULTILINGUAL_LABEL_SEMANTICS_COLLISION_AUDIT_STAGE10068.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage10062_web_non_b_anticollapse_successor_packet/web_non_b_anticollapse_successor_manifest.jsonl"

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


def build_audit() -> dict[str, Any]:
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    per_language: dict[str, dict[str, str]] = {}
    hidden_to_labels: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    label_to_hidden: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    for row in rows:
        language = str(row.get("language_family") or "")
        if not language:
            continue
        clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
        label = str(clean.get("edit_localization_target") or "")
        hidden = str(clean.get("edit_localization_target_hidden") or "")
        if not label or not hidden:
            failures.append(f"missing_label_or_hidden:{row.get('row_id')}")
            continue
        per_language.setdefault(language, {})
        per_language[language].setdefault(label, hidden)
        if per_language[language][label] != hidden:
            failures.append(f"inconsistent_within_language:{language}:{label}")
        hidden_to_labels[hidden][label].append(language)
        label_to_hidden[label][hidden].append(language)

    collision_rows = []
    for label, hidden_map in sorted(label_to_hidden.items()):
        if len(hidden_map) > 1:
            collision_rows.append({
                "label": label,
                "hidden_targets": {hidden: sorted(languages) for hidden, languages in sorted(hidden_map.items())},
            })

    canonical_mismatches: dict[str, dict[str, str]] = {}
    for language, mapping in sorted(per_language.items()):
        mismatches = {
            label: hidden
            for label, hidden in sorted(mapping.items())
            if CANONICAL_LABEL_MAP.get(hidden) != label
        }
        if mismatches:
            canonical_mismatches[language] = mismatches

    metrics = {
        "rows": len(rows),
        "languages": sorted(per_language),
        "per_language_label_map": {language: dict(sorted(mapping.items())) for language, mapping in sorted(per_language.items())},
        "cross_language_label_collisions": collision_rows,
        "collision_label_count": len(collision_rows),
        "canonical_label_map": dict(sorted(CANONICAL_LABEL_MAP.items())),
        "canonical_mismatch_languages": sorted(canonical_mismatches),
        "canonical_mismatches": canonical_mismatches,
    }
    if len(rows) != 142:
        failures.append("rows_not_142")
    if len(per_language) != 4:
        failures.append("languages_not_4")
    if not collision_rows:
        failures.append("expected_cross_language_collisions_missing")
    if "web_js_ts_html" not in per_language:
        failures.append("missing_web_language")
    return {"passed": not failures, "failures": failures, "metrics": metrics}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    write_json(AUDIT, {"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]})
    next_step = "Build a canonical-label multilingual successor packet so every language maps the same hidden edit-target family to the same opaque label before the next 100M and Gemma same-manifest comparison."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"audit": display(AUDIT), "doc": display(DOC)},
        "decision": "Confirmed that the current multilingual frontier packet assigns different hidden edit-localization semantics to the same opaque labels across languages, which is a direct candidate explanation for the cross-language collapse observed after counter-balance runs.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10068 Multilingual Label Semantics Collision Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Collision labels: `{built['metrics']['collision_label_count']}`",
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
