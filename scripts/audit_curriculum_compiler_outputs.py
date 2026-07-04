from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from loss_mask_card import normalize_loss_mask, validate_loss_mask_row
from stage_summary_schema import AUTHORITY_KEYS

OBJECTIVE_ALLOWED = {
    "structured_state": {"surface_role_ce", "repair_surface_ce", "build_mode_ce", "allowed_import_policy_ce", "blocked_import_policy_ce", "repo_dependency_policy_ce", "action_sequence_ce", "file_plan_ce", "symbol_binding_ce", "edit_localization_ce", "patch_operator_ce", "verifier_repair_ce"},
    "bounded_decoder_ce": {"decoder_ce"},
    "denoise_repair": {"denoise_ce"},
    "negative_control": {"action_sequence_ce"},
    "retrieval_control": {"action_sequence_ce"},
    "long_output_holdout": set(),
    "quarantine": set(),
    "drop_duplicate": set(),
    "human_review": set(),
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def audit_dir(path: Path, *, allow_decoder: bool, allow_denoise: bool, allow_runtime: bool) -> dict[str, Any]:
    errors=[]
    objective_cards={}
    total_rows=0
    authority_rows=[]
    forbidden_loss_rows=[]
    for manifest in sorted(path.glob("*.jsonl")):
        objective=manifest.stem
        rows=read_jsonl(manifest)
        total_rows += len(rows)
        allowed=OBJECTIVE_ALLOWED.get(objective, set())
        enabled_counts={}
        for i,row in enumerate(rows):
            rid=str(row.get("row_id") or f"{manifest.name}:{i}")
            mask=normalize_loss_mask(row)
            enabled={k for k,v in mask.items() if v}
            for k in enabled:
                enabled_counts[k]=enabled_counts.get(k,0)+1
            if not enabled.issubset(allowed):
                forbidden_loss_rows.append({"row_id":rid,"objective":objective,"enabled":sorted(enabled),"allowed":sorted(allowed)})
            mask_errors=validate_loss_mask_row(row, allow_decoder_ce=allow_decoder, allow_denoise=allow_denoise, allow_runtime=allow_runtime)
            # holdout/quarantine rows may intentionally have no losses
            mask_errors=[e for e in mask_errors if not (e == "no losses enabled" and not enabled)]
            if mask_errors:
                forbidden_loss_rows.append({"row_id":rid,"objective":objective,"errors":mask_errors})
            authority=row.get("authority") if isinstance(row.get("authority"),dict) else row
            if any(bool(authority.get(k,False)) for k in AUTHORITY_KEYS):
                authority_rows.append(rid)
        objective_cards[objective]={"rows":len(rows),"enabled_loss_counts":enabled_counts}
    if authority_rows:
        errors.append(f"authority rows: {len(authority_rows)}")
    if forbidden_loss_rows:
        errors.append(f"forbidden loss rows: {len(forbidden_loss_rows)}")
    return {
        "passed": not errors,
        "rows": total_rows,
        "objective_cards": objective_cards,
        "authority_rows": len(authority_rows),
        "forbidden_loss_rows": len(forbidden_loss_rows),
        "forbidden_loss_examples": forbidden_loss_rows[:100],
        "errors": errors,
        "gates": {
            "rows_present": total_rows > 0,
            "authority_closed": not authority_rows,
            "losses_match_objective": not forbidden_loss_rows,
        },
        "authority": {k: False for k in AUTHORITY_KEYS},
    }


def parse_args() -> argparse.Namespace:
    p=argparse.ArgumentParser(description="Audit curriculum compiler outputs for authority and objective/loss consistency.")
    p.add_argument("output_dir", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--allow-decoder", action="store_true")
    p.add_argument("--allow-denoise", action="store_true")
    p.add_argument("--allow-runtime", action="store_true")
    return p.parse_args()


def main() -> None:
    args=parse_args()
    card=audit_dir(args.output_dir, allow_decoder=args.allow_decoder, allow_denoise=args.allow_denoise, allow_runtime=args.allow_runtime)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(card, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
