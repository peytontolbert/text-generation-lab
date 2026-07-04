from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from stage_summary_schema import AUTHORITY_KEYS

EXPECTED_LANGUAGES = {"python", "rust", "c_family", "web_js_ts_html"}
EXPECTED_SURFACES = {"MAINTAINER_EXPLANATION_ARGS", "REPAIR_PLAN_ARGS", "PATCH_HUNK_ARGS", "TEST_PLAN_ARGS"}
EXPECTED_SPLITS = {"train", "eval", "strict_eval"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def audit(rows: list[dict[str, Any]], *, max_decoder_tokens: int = 768) -> dict[str, Any]:
    errors=[]
    by_split={}
    by_language={}
    by_surface={}
    copied=[]
    over=[]
    auth=[]
    missing=[]
    for i,row in enumerate(rows):
        rid=str(row.get("row_id") or f"row_{i}")
        for key in ["row_id","split","language_family","surface","target_ref","decoder_token_len","authority"]:
            if key not in row:
                missing.append({"row_id":rid,"key":key})
        by_split[row.get("split")] = by_split.get(row.get("split"),0)+1
        by_language[row.get("language_family")] = by_language.get(row.get("language_family"),0)+1
        by_surface[row.get("surface")] = by_surface.get(row.get("surface"),0)+1
        if row.get("copied_target_text_in_input") or row.get("decoder_text") or row.get("raw_decoder_text"):
            copied.append(rid)
        if int(row.get("decoder_token_len", 999999)) > max_decoder_tokens:
            over.append(rid)
        authority=row.get("authority") if isinstance(row.get("authority"),dict) else row
        if any(bool(authority.get(k,False)) for k in AUTHORITY_KEYS):
            auth.append(rid)
    if len(rows) != 96:
        errors.append(f"candidate rows {len(rows)} != 96")
    if set(by_split) != EXPECTED_SPLITS:
        errors.append(f"split set mismatch: {set(by_split)}")
    if set(by_language) != EXPECTED_LANGUAGES:
        errors.append(f"language set mismatch: {set(by_language)}")
    if set(by_surface) != EXPECTED_SURFACES:
        errors.append(f"surface set mismatch: {set(by_surface)}")
    if any(v != 32 for v in by_split.values()):
        errors.append(f"split counts not 32 each: {by_split}")
    if any(v != 24 for v in by_language.values()):
        errors.append(f"language counts not 24 each: {by_language}")
    if any(v != 24 for v in by_surface.values()):
        errors.append(f"surface counts not 24 each: {by_surface}")
    if copied:
        errors.append(f"copied target/raw decoder rows: {len(copied)}")
    if over:
        errors.append(f"over cap rows: {len(over)}")
    if auth:
        errors.append(f"authority rows: {len(auth)}")
    if missing:
        errors.append(f"missing required fields: {len(missing)}")
    return {
        "stage":8565,
        "stage_name":"stage8565_v27_bounded_decoder_ce_candidate_package_design_audit",
        "passed": not errors,
        "candidate_rows": len(rows),
        "by_split": by_split,
        "by_language": by_language,
        "by_surface": by_surface,
        "copied_target_text_rows": len(copied),
        "over_cap_rows": len(over),
        "current_authority_rows": len(auth),
        "missing_required_field_rows": len(missing),
        "errors": errors,
        "gates": {
            "candidate_plan_rows_expected": len(rows)==96,
            "candidate_split_counts_expected": set(by_split)==EXPECTED_SPLITS and all(v==32 for v in by_split.values()),
            "candidate_language_counts_expected": set(by_language)==EXPECTED_LANGUAGES and all(v==24 for v in by_language.values()),
            "candidate_surface_counts_expected": set(by_surface)==EXPECTED_SURFACES and all(v==24 for v in by_surface.values()),
            "copied_target_text_absent": not copied,
            "budget_caps_still_pass": not over,
            "current_authority_closed": not auth,
        },
        "authority": {k: False for k in AUTHORITY_KEYS},
        "next_best_step": "run loss-mask reopen design on audited candidate rows; no execution authorized",
    }


def parse_args() -> argparse.Namespace:
    p=argparse.ArgumentParser(description="Audit bounded decoder CE candidate package design rows.")
    p.add_argument("rows", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-decoder-tokens", type=int, default=768)
    return p.parse_args()


def main() -> None:
    args=parse_args()
    card=audit(read_jsonl(args.rows), max_decoder_tokens=args.max_decoder_tokens)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(card, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
