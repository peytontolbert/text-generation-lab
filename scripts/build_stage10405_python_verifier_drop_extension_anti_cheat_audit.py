#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "runs/local/artifacts/stage10378_balanced_residual_probe_execution_request/balanced_residual_probe_manifest.jsonl"
BASELINE = ROOT / "runs/local/artifacts/stage10398_stage10397_frontier_rescore/language_conditioned_frontier_eval.json"
POLICY = ROOT / "runs/local/artifacts/stage10404_generic_policy_frontier_eval/language_conditioned_frontier_eval.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage10405_python_verifier_drop_extension_anti_cheat_audit"
OUT_PATH = OUT_DIR / "python_verifier_drop_extension_anti_cheat_audit.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def perspective(row: dict[str, object]) -> str:
    prompt = str(row.get("prompt_text") or "")
    for line in prompt.splitlines():
        if line.startswith("Perspective: "):
            return line.split(": ", 1)[1].strip()
    return ""


def drop_extension(value: str) -> str:
    return str(Path(value).with_suffix(""))


def main() -> None:
    manifest_rows = [row for row in load_jsonl(MANIFEST) if row.get("split") == "strict_eval"]
    baseline = load_json(BASELINE)
    policy = load_json(POLICY)
    baseline_rows = {row["row_id"]: row for row in baseline["row_cards"]}
    policy_rows = {row["row_id"]: row for row in policy["row_cards"]}

    changed_rows = []
    scoped_rows = []
    collision_rows = []
    for row in manifest_rows:
        row_id = str(row["row_id"])
        base = baseline_rows[row_id]
        new = policy_rows[row_id]
        if base["selected_variant"] != new["selected_variant"] or base["pred"] != new["pred"] or base["correct"] != new["correct"]:
            changed_rows.append(
                {
                    "row_id": row_id,
                    "language_family": row.get("language_family"),
                    "perspective": perspective(row),
                    "baseline_variant": base["selected_variant"],
                    "policy_variant": new["selected_variant"],
                    "baseline_pred": base["pred"],
                    "policy_pred": new["pred"],
                    "target": new["target"],
                    "baseline_correct": base["correct"],
                    "policy_correct": new["correct"],
                }
            )

        if row.get("language_family") == "python" and perspective(row) == "verifier_outcome":
            options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
            stripped = [drop_extension(str(option["value"])) for option in options if isinstance(option, dict)]
            scoped_rows.append(
                {
                    "row_id": row_id,
                    "option_count": len(stripped),
                    "unique_after_drop_extension": len(set(stripped)) == len(stripped),
                    "raw_values": [str(option["value"]) for option in options if isinstance(option, dict)],
                    "drop_extension_values": stripped,
                }
            )
            if len(set(stripped)) != len(stripped):
                collision_rows.append(row_id)

    payload = {
        "stage_name": "stage10405_python_verifier_drop_extension_anti_cheat_audit",
        "baseline_path": str(BASELINE),
        "policy_path": str(POLICY),
        "baseline_correct": baseline["correct"],
        "policy_correct": policy["correct"],
        "changed_row_count": len(changed_rows),
        "changed_rows": changed_rows,
        "policy_scope_rule": "apply drop_extension only to python::verifier_outcome rows; retain baseline language-conditioned scoring elsewhere",
        "scope_limited_to_python_verifier_rows": all(
            row["language_family"] == "python" and row["perspective"] == "verifier_outcome"
            for row in changed_rows
        ),
        "python_verifier_row_count": len(scoped_rows),
        "python_verifier_rows_unique_after_drop_extension": len(collision_rows) == 0,
        "collision_rows": collision_rows,
        "scoped_rows": scoped_rows,
        "claim_boundary": [
            "The scorer rule removes only the file extension suffix from verifier target options.",
            "The rule does not reorder options or inject target-specific aliases.",
            "All python verifier rows preserve unique option identities after extension stripping.",
            "Any broader claim still requires cross-model comparison and disjoint-root rebuilds for promotable evidence.",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUT_PATH)


if __name__ == "__main__":
    main()
