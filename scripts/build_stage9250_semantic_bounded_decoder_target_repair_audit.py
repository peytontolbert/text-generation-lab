#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
    from build_stage9248_bounded_decoder_target_semantic_diversity_audit import analyze_rows, read_jsonl
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from scripts.build_stage9248_bounded_decoder_target_semantic_diversity_audit import analyze_rows, read_jsonl  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9250
NAME = "stage9250_semantic_bounded_decoder_target_repair_audit"
MANIFEST = ROOT / "runs/local/artifacts/stage9249_semantic_bounded_decoder_target_repair_package/semantic_bounded_decoder_target_repair_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "semantic_bounded_decoder_target_repair_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SEMANTIC_BOUNDED_DECODER_TARGET_REPAIR_AUDIT_STAGE9250.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(MANIFEST)
    audit = analyze_rows(rows)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "supersedes": ["stage9248_bounded_decoder_target_semantic_diversity_audit"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Stage9249 semantic bounded decoder targets pass diversity and anti-template audit; no execution authorized." if audit["passed"] else "Stage9249 semantic bounded decoder targets still fail diversity or anti-template audit.",
        "next_best_step": "Run target-100M contract-only preflight on the Stage9249 repaired manifest, then create a fresh inactive execution review if it passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9250 Semantic Bounded Decoder Target Repair Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Rows: `{audit['rows']}`",
        f"First-token dominance rate: `{audit['first_token_dominance_rate']:.3f}`",
        f"Language-prefix rows: `{audit['language_prefix_rows']}`",
        f"Target contains language rows: `{audit['target_contains_language_rows']}`",
        f"Argument-type echo rows: `{audit['arg_type_echo_rows']}`",
        f"Template phrase rows: `{audit['template_phrase_rows']}`",
        f"Unique normalized target rate: `{audit['unique_normalized_target_rate']:.3f}`",
        f"Unique trigram rate: `{audit['unique_trigram_rate']:.3f}`",
        "",
        "This audit is no-execution. It verifies that Stage9249 repaired the Stage9248 target-rendering blocker without opening model execution, decoder training, runtime, Gemma, harness, scoring, or promotion.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
