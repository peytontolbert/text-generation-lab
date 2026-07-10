#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9903
NAME = "stage9903_current_margin_locality_signal_neutral_label_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9891_current_margin_locality_signal_lift_manifest.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9891_current_margin_locality_signal_lift_manifest/current_margin_locality_signal_lift_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "current_margin_locality_signal_neutral_label_manifest.jsonl"
AUDIT = OUT_DIR / "current_margin_locality_signal_neutral_label_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_MARGIN_LOCALITY_SIGNAL_NEUTRAL_LABEL_MANIFEST_STAGE9903.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LABEL_MAP = {"K": "A", "M": "B", "R": "C", "T": "D"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def remap_choice_text(text: str) -> str:
    stripped = text.strip()
    for src, dst in LABEL_MAP.items():
        if stripped.startswith(f"option {src}:"):
            return stripped.replace(f"option {src}:", f"option {dst}:", 1)
    return text


def remap_row(row: dict[str, Any]) -> dict[str, Any]:
    cloned = json.loads(json.dumps(row))
    for key in ["clean_state", "target"]:
        obj = cloned.get(key)
        if isinstance(obj, dict):
            for field in ["edit_localization", "edit_localization_target", "target_ref", "decoder_text"]:
                if field in obj and str(obj[field]) in LABEL_MAP:
                    obj[field] = LABEL_MAP[str(obj[field])]
    for key in ["edit_localization_target", "edit_localization"]:
        if key in cloned and str(cloned[key]) in LABEL_MAP:
            cloned[key] = LABEL_MAP[str(cloned[key])]
    input_state = cloned.get("input_state") if isinstance(cloned.get("input_state"), dict) else {}
    if "candidate_choices" in input_state and isinstance(input_state["candidate_choices"], list):
        input_state["candidate_choices"] = [remap_choice_text(str(choice)) for choice in input_state["candidate_choices"]]
        cloned["input_state"] = input_state
    anti = cloned.get("anti_cheat") if isinstance(cloned.get("anti_cheat"), dict) else {}
    anti["stage9904_neutral_label_remap"] = LABEL_MAP
    anti["stage9904_neutral_label_inventory"] = ["A", "B", "C", "D"]
    cloned["anti_cheat"] = anti
    return cloned


def build_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    remapped = [remap_row(row) for row in rows]
    target_labels = sorted({str(((row.get("target") or {}).get("decoder_text")) or "") for row in remapped})
    choice_prefixes = sorted({str(choice).split(":", 1)[0].strip() for row in remapped for choice in ((row.get("input_state") or {}).get("candidate_choices") or [])})
    audit = {
        "rows": len(remapped),
        "target_labels": target_labels,
        "choice_prefixes": choice_prefixes,
        "label_map": LABEL_MAP,
        "uses_neutral_a_to_d_vocab": target_labels == ["A", "B", "C", "D"],
    }
    return remapped, audit


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = read_jsonl(SOURCE_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9891_not_passed")
    if not rows:
        failures.append("missing_source_rows")
    remapped, audit = build_rows(rows)
    write_jsonl(MANIFEST, remapped)
    if audit["target_labels"] != ["A", "B", "C", "D"]:
        failures.append("unexpected_target_labels_after_remap")
    write_json(AUDIT, {"passed": not failures, "failures": failures, "audit": audit, "authority": dict(AUTHORITY_CLOSED)})
    next_step = "Run Stage9904 on the neutral-label locality-lifted packet and check whether the remaining ties against Gemma convert into wins under a geometry-neutral output vocabulary."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built a locality-lifted current-frontier control packet with a neutral four-label A/B/C/D output vocabulary, preserving row semantics while removing the observed geometry issues tied to the previous label inventory.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text("\n".join([
        "# Stage9903 Current Margin Locality Signal Neutral Label Manifest",
        "",
        f"Passed: `{summary['passed']}`",
        f"Target labels: `{audit['target_labels']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "target_labels": audit["target_labels"]}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
