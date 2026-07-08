#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9440
NAME = "stage9440_antirepetition_support_sufficiency_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9439_heldout_prior_confidence_antirepetition_manifest.json"
ANTI_REPETITION = ROOT / "runs/local/artifacts/stage9439_heldout_prior_confidence_antirepetition_manifest/anti_repetition_denoise_support_manifest.jsonl"
LOW_CONF_QUARANTINE = ROOT / "runs/local/artifacts/stage9439_heldout_prior_confidence_antirepetition_manifest/low_confidence_heldout_prior_quarantine.jsonl"
HELDOUT_REPETITION_QUARANTINE = ROOT / "runs/local/artifacts/stage9439_heldout_prior_confidence_antirepetition_manifest/heldout_repetition_prior_quarantine.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "antirepetition_support_sufficiency_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ANTIREPETITION_SUPPORT_SUFFICIENCY_AUDIT_STAGE9440.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    anti_rows = load_jsonl(ANTI_REPETITION)
    low_conf = load_jsonl(LOW_CONF_QUARANTINE)
    heldout_rep = load_jsonl(HELDOUT_REPETITION_QUARANTINE)
    label_counts = Counter(str((row.get("suffix_choice_prior") or {}).get("label")) for row in anti_rows)
    split_counts = Counter(str(row.get("split")) for row in anti_rows)

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9439_not_passed")
    if len(anti_rows) != 4:
        failures.append("unexpected_anti_repetition_count")
    if split_counts != Counter({"train": 4}):
        failures.append("anti_repetition_not_train_only")
    if len(label_counts) < 3:
        failures.append("anti_repetition_label_coverage_too_narrow")
    if len(low_conf) != 6:
        failures.append("unexpected_low_conf_quarantine_count")
    if len(heldout_rep) != 2:
        failures.append("unexpected_heldout_repetition_quarantine_count")
    if any((row.get("loss_mask") or {}).get("decoder_ce") for row in anti_rows):
        failures.append("decoder_ce_open")
    if any(any(bool((row.get("authority") or {}).get(key)) for key in AUTHORITY_CLOSED) for row in anti_rows + low_conf + heldout_rep):
        failures.append("authority_flags_open")

    standalone_probe_recommended = False
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9439_heldout_prior_confidence_antirepetition_manifest",
        "anti_repetition_rows": len(anti_rows),
        "anti_repetition_split_counts": dict(sorted(split_counts.items())),
        "anti_repetition_label_counts": dict(sorted(label_counts.items())),
        "low_confidence_quarantine_rows": len(low_conf),
        "heldout_repetition_quarantine_rows": len(heldout_rep),
        "standalone_probe_recommended": standalone_probe_recommended,
        "decision": "do not run a 4-row standalone anti-repetition probe; merge support into gated prior-fusion manifest",
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "The 4 anti-repetition rows are useful support but too small as a standalone probe.",
        "next_best_step": "Build a gated prior-fusion rejoin manifest: keep train support, add anti-repetition rows, and exclude low-confidence heldout priors from generation.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join(["# Stage9440 Anti-Repetition Support Sufficiency Audit", "", f"Passed: `{audit['passed']}`", f"Anti-repetition rows: `{len(anti_rows)}`", f"Standalone probe recommended: `{standalone_probe_recommended}`", "", "Use these rows as support inside a gated rejoin manifest instead of running a tiny standalone probe.", ""]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"anti_repetition_rows": len(anti_rows), "standalone_probe_recommended": standalone_probe_recommended}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
