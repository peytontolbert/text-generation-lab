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
STAGE = 9818
NAME = "stage9818_web_only_phase2_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9813_web_isolated_disambiguator_surface/web_isolated_disambiguator_surface.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "web_only_phase2_manifest.jsonl"
AUDIT = OUT_DIR / "web_only_phase2_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WEB_ONLY_PHASE2_MANIFEST_STAGE9818.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
WEB_LANG = "web_js_ts_html"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
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


def build_manifest() -> dict[str, Any]:
    rows = load_jsonl(SOURCE)
    phase2_rows: list[dict[str, Any]] = []
    for row in rows:
        split = str(row.get("split") or "")
        lang = str(row.get("language_family") or "")
        if split == "train" and lang != WEB_LANG:
            continue
        phase2_rows.append(row)
    write_jsonl(MANIFEST, phase2_rows)
    split_counts = Counter(str(row.get("split") or "") for row in phase2_rows)
    train_lang_counts = Counter(str(row.get("language_family") or "") for row in phase2_rows if str(row.get("split") or "") == "train")
    strict_lang_counts = Counter(str(row.get("language_family") or "") for row in phase2_rows if str(row.get("split") or "") == "strict_eval")
    failures: list[str] = []
    if split_counts.get("train") != 5:
        failures.append(f"unexpected_train_rows:{split_counts.get('train', 0)}")
    if split_counts.get("eval") != 20:
        failures.append(f"unexpected_eval_rows:{split_counts.get('eval', 0)}")
    if split_counts.get("strict_eval") != 20:
        failures.append(f"unexpected_strict_rows:{split_counts.get('strict_eval', 0)}")
    if set(train_lang_counts) != {WEB_LANG}:
        failures.append(f"train_not_web_only:{sorted(train_lang_counts)}")
    if len(strict_lang_counts) != 4:
        failures.append(f"strict_not_multilingual:{sorted(strict_lang_counts)}")
    audit = {
        "passed": not failures,
        "rows": len(phase2_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "train_language_counts": dict(sorted(train_lang_counts.items())),
        "strict_language_counts": dict(sorted(strict_lang_counts.items())),
        "failures": failures,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_manifest()
    next_step = "Run a two-phase structured continuation: Stage9790 baseline phase1, then Stage9818 web-only phase2 on the same in-memory model, and compare the final multilingual strict-eval slices against Stage9794 and Gemma."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "rows": audit["rows"], "split_counts": audit["split_counts"], "train_language_counts": audit["train_language_counts"]},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Materialized a phase2 manifest that trains only on web rows while evaluating on the full multilingual isolated-field surface.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9818 Web Only Phase2 Manifest", "", f"Passed: `{audit['passed']}`", f"Rows: `{audit['rows']}`", "", f"Next: {next_step}", ""]) + "\n", encoding="utf-8")
    if audit["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "rows": audit["rows"], "failures": audit["failures"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
