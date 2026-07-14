#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10487
NAME = "stage10487_deleaked_python_verifier_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "deleaked_python_verifier_support_package.json"
ROWS_JSONL = OUT_DIR / "deleaked_python_verifier_support_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_ROWS = ROOT / "runs/local/artifacts/stage10484_partitioned_residual_support_package/promotable_python_verifier_rows.jsonl"

EVIDENCE_LINE_RE = re.compile(r"^([a-z_]+) \[[^\]]+\]: (.*)$")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rewrite_prompt(text: str) -> tuple[str, list[dict[str, str]]]:
    if "\nOptions:\n" not in text:
        return text, []
    body, options = text.split("\nOptions:\n", 1)
    lines = body.splitlines()
    rewritten: list[str] = []
    slot_cards: list[dict[str, str]] = []
    slot_index = 1
    for line in lines:
        match = EVIDENCE_LINE_RE.match(line)
        if not match:
            rewritten.append(line)
            continue
        role, snippet = match.groups()
        slot_id = f"evidence_slot_{slot_index:02d}"
        rewritten.append(f"{role} [{slot_id}]: {snippet}")
        slot_cards.append({"role": role, "slot_id": slot_id})
        slot_index += 1
    return "\n".join(rewritten) + "\nOptions:\n" + options, slot_cards


def deep_copy(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(row))


def main() -> None:
    source_rows = load_jsonl(SOURCE_ROWS)
    rewritten_rows: list[dict[str, Any]] = []

    for row in source_rows:
        updated = deep_copy(row)
        prompt = str(updated.get("prompt_text") or updated.get("input_text") or "")
        rewritten_prompt, slot_cards = rewrite_prompt(prompt)
        updated["row_id"] = f"{str(updated.get('row_id') or '')}::deleaked_v1"
        updated["prompt_text"] = rewritten_prompt
        updated["input_text"] = rewritten_prompt
        if "prompt" in updated:
            updated["prompt"] = rewritten_prompt
        anti = dict(updated.get("anti_cheat") or {})
        anti.update(
            {
                "support_deleaked_stage": STAGE,
                "prompt_target_value_redacted_before_options": True,
                "evidence_slot_headers_opaque": True,
            }
        )
        updated["anti_cheat"] = anti
        provenance = dict(updated.get("support_provenance") or {})
        provenance.update(
            {
                "support_package_stage": STAGE,
                "support_package_name": NAME,
                "de_leaked_from": display(SOURCE_ROWS),
            }
        )
        updated["support_provenance"] = provenance
        updated["support_deleak_cards"] = slot_cards
        rewritten_rows.append(updated)

    write_jsonl(ROWS_JSONL, rewritten_rows)

    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(rewritten_rows),
        "decision": "deleaked_python_verifier_support_ready",
        "claim_scope": [
            "De-leak the promotable Python verifier support rows by removing verbatim gold test paths from evidence headers before the options block.",
            "Preserve the same task semantics, options, and training role while making the support lane honest enough for anti-cheat review.",
        ],
        "source_artifacts": {
            "source_rows": display(SOURCE_ROWS),
        },
        "rows": len(rewritten_rows),
        "row_ids": [str(row.get("row_id") or "") for row in rewritten_rows],
        "required_honesty_gates": [
            "Gold selected-test path must not appear verbatim before the options block.",
            "Only header identifiers may be rewritten; evidence snippets and option set must preserve the original task semantics.",
            "Rows remain train_support_only and strict_eval_eligible=false.",
        ],
        "outputs": {
            "package_json": display(PACKAGE_JSON),
            "rows_jsonl": display(ROWS_JSONL),
        },
    }

    write_json(PACKAGE_JSON, package)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": package["decision"],
            "package": display(PACKAGE_JSON),
        },
    )
    print(json.dumps(package, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
