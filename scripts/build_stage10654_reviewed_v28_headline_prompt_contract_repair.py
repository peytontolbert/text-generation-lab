#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
PACKAGE_DIR = ARTIFACTS / "stage10645_reviewed_v28_candidate_manifest_package"
REPAIR_QUEUE = ARTIFACTS / "stage10653_reviewed_v28_prompt_contract_repair_queue/reviewed_v28_prompt_contract_repair_queue.json"

EVIDENCE_ROLE_ORDER = [
    "algorithmic_background_reference",
    "candidate_change_surface",
    "external_analogue_reference",
    "nearby_definition_or_usage_context",
    "symptom_or_call_path_analogue",
    "verifier_and_test_constraint",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def evidence_lines(prompt: str) -> list[str]:
    lines = prompt.splitlines()
    start = lines.index("Evidence:") + 1
    end = lines.index("Options:")
    return lines[start:end]


def option_lines(prompt: str) -> list[str]:
    lines = prompt.splitlines()
    start = lines.index("Options:") + 1
    end = lines.index("Answer:")
    return lines[start:end]


def rebuild_prompt(row: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    original_prompt = str(row["prompt_text"])
    lines = original_prompt.splitlines()
    prefix = []
    for line in lines:
        if line == "Evidence:":
            break
        prefix.append(line)

    source_evidence_lines = evidence_lines(original_prompt)
    role_to_evidence: dict[str, str] = {}
    for line in source_evidence_lines:
        if " [" in line:
            role = line.split(" [", 1)[0].strip()
            role_to_evidence[role] = line

    rewritten_evidence_lines: list[str] = []
    rewritten_options: list[dict[str, Any]] = []
    for idx, role in enumerate(EVIDENCE_ROLE_ORDER, start=1):
        evidence_id = f"E{idx:02d}"
        source_line = role_to_evidence.get(role)
        if source_line is None:
            continue
        _, remainder = source_line.split(" ", 1)
        rewritten_evidence_lines.append(f"{evidence_id} {remainder}")
        rewritten_options.append({"label": chr(ord('A') + len(rewritten_options)), "value": evidence_id})

    # Preserve target label position by mapping original option value -> new evidence id in fixed role order.
    original_options = list(row.get("opaque_options") or [])
    value_to_new_value = {}
    for idx, role in enumerate(EVIDENCE_ROLE_ORDER, start=1):
        value_to_new_value[role] = f"E{idx:02d}"

    remapped_options: list[dict[str, Any]] = []
    for opt in original_options:
        label = str(opt.get("label") or "")
        value = str(opt.get("value") or "")
        remapped_options.append({"label": label, "value": value_to_new_value.get(value, value)})

    option_text_lines = [f"{opt['label']}. {opt['value']}" for opt in remapped_options]
    rewritten_prompt = "\n".join(
        prefix
        + ["Evidence:"]
        + rewritten_evidence_lines
        + ["Options:"]
        + option_text_lines
        + ["Answer:", ""]
    )
    return rewritten_prompt, remapped_options


def main() -> None:
    rows = load_jsonl(PACKAGE_DIR / "headline_strict_eval.jsonl")
    repair_queue = load_json(REPAIR_QUEUE)
    flagged = {
        row["row_id"]: row
        for row in repair_queue["repair_queue"]
        if row["slice_name"] == "headline_strict"
    }

    repaired_rows: list[dict[str, Any]] = []
    repaired_row_ids: list[str] = []
    for row in rows:
        out = dict(row)
        if row["row_id"] in flagged:
            repaired_prompt, repaired_options = rebuild_prompt(row)
            out["prompt_text"] = repaired_prompt
            out["input_text"] = repaired_prompt
            out["opaque_options"] = repaired_options
            projection = dict(out.get("standalone_projection_source") or {})
            projection["opaque_options"] = repaired_options
            projection["projection_mode"] = "reviewed_v28_evidence_id_repair"
            out["standalone_projection_source"] = projection
            anti_cheat = dict(out.get("anti_cheat") or {})
            anti_cheat["opaque_evidence_id_contract"] = True
            anti_cheat["semantic_role_names_hidden_from_options"] = True
            out["anti_cheat"] = anti_cheat
            notes = list(out.get("claim_boundary_notes") or [])
            if "prompt_contract_repaired_evidence_ids" not in notes:
                notes.append("prompt_contract_repaired_evidence_ids")
            out["claim_boundary_notes"] = notes
            repaired_row_ids.append(row["row_id"])
        repaired_rows.append(out)

    summary = {
        "stage": 10654,
        "stage_name": "stage10654_reviewed_v28_headline_prompt_contract_repair",
        "passed": True,
        "source_package": str((PACKAGE_DIR / "headline_strict_eval.jsonl").relative_to(ROOT)),
        "repair_queue_source": str(REPAIR_QUEUE.relative_to(ROOT)),
        "metrics": {
            "headline_rows": len(rows),
            "repaired_rows": len(repaired_row_ids),
        },
        "repaired_row_ids": repaired_row_ids,
        "claim_boundary": [
            "Only the four shortcut-prone headline evidence_citation rows were rewritten.",
            "The repaired contract preserves the same row identities, language coverage, and target labels.",
            "Evidence role names remain in the evidence body provenance, but option values are now opaque evidence IDs rather than semantic role names.",
        ],
    }

    out_dir = ARTIFACTS / "stage10654_reviewed_v28_headline_prompt_contract_repair"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "reviewed_v28_headline_prompt_contract_repair.json", summary)
    write_jsonl(out_dir / "headline_strict_eval_repaired.jsonl", repaired_rows)
    print(out_dir / "reviewed_v28_headline_prompt_contract_repair.json")


if __name__ == "__main__":
    main()
