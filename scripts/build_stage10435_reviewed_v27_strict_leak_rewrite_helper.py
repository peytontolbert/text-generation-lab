#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10435
NAME = "stage10435_reviewed_v27_strict_leak_rewrite_helper"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
HELPER_JSON = OUT_DIR / "reviewed_v27_strict_leak_rewrite_helper.json"
OVERLAY_JSONL = OUT_DIR / "reviewed_v27_strict_leak_rewrite_overlays.jsonl"
PREVIEW_JSONL = OUT_DIR / "reviewed_v27_strict_leak_rewrite_preview.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

REPAIR_REQUEST_JSON = ROOT / "runs/local/artifacts/stage10434_reviewed_v27_strict_leak_repair_request/reviewed_v27_strict_leak_repair_request.json"
STRICT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_strict_eval.jsonl"

LINE_RE = re.compile(r"^([A-Za-z0-9_]+)(\s*\[[^\]]+\]:\s.*)$")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def rewrite_prompt(prompt: str) -> tuple[str, list[dict[str, str]]]:
    sections = prompt.split("\nEvidence:\n", 1)
    if len(sections) != 2:
        return prompt, []
    prefix, rest = sections
    evidence_block, suffix = rest.split("\nOptions:\n", 1)
    rewritten_lines: list[str] = []
    slot_map: list[dict[str, str]] = []
    slot_index = 1
    for line in evidence_block.splitlines():
        match = LINE_RE.match(line)
        if not match:
            rewritten_lines.append(line)
            continue
        original_key = match.group(1)
        tail = match.group(2)
        slot_name = f"visible_evidence_{slot_index}"
        slot_index += 1
        rewritten_lines.append(f"{slot_name}{tail}")
        slot_map.append({"slot_name": slot_name, "original_key": original_key})
    rewritten_prompt = prefix + "\nEvidence:\n" + "\n".join(rewritten_lines) + "\nOptions:\n" + suffix
    return rewritten_prompt, slot_map


def main() -> None:
    request = load_json(REPAIR_REQUEST_JSON)
    strict_rows = {row["row_id"]: row for row in load_jsonl(STRICT_ROWS_JSONL)}

    overlays: list[dict[str, Any]] = []
    previews: list[dict[str, Any]] = []
    for target in request["targets"]:
        row_id = target["row_id"]
        row = strict_rows[row_id]
        original_prompt = str(row.get("prompt_text") or row.get("input_text") or "")
        rewritten_prompt, slot_map = rewrite_prompt(original_prompt)
        overlay = {
            "row_id": row_id,
            "source_bundle_id": row.get("source_bundle_id"),
            "language_family": row.get("language_family"),
            "task_type": row.get("task_type"),
            "rewrite_strategy": "neutralize_evidence_slot_names_keep_option_semantics",
            "original_prompt_text": original_prompt,
            "rewritten_prompt_text": rewritten_prompt,
            "slot_map": slot_map,
            "target_label": row.get("decoder_text"),
            "target_semantic_value": ((row.get("standalone_projection_source") or {}).get("gold_value")),
            "must_preserve": target["must_preserve"],
        }
        overlays.append(overlay)
        previews.append(
            {
                "row_id": row_id,
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "slot_map": slot_map,
                "original_prompt_excerpt": original_prompt[:1800],
                "rewritten_prompt_excerpt": rewritten_prompt[:1800],
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "request_source": display(REPAIR_REQUEST_JSON),
        "rewrite_strategy": [
            "Replace prompt-visible evidence key names with neutral ordered slots such as visible_evidence_1.",
            "Keep opaque choice options, target label, gold answer, root lineage, and split membership unchanged.",
            "Use the overlay as a draft repair artifact; do not mutate the live v2.7 package until the repaired rows are reviewed and re-audited.",
        ],
        "summary": {
            "repair_targets": len(overlays),
            "strategy": "neutral_evidence_slots",
        },
        "outputs": {
            "helper_json": display(HELPER_JSON),
            "overlay_rows": display(OVERLAY_JSONL),
            "preview_rows": display(PREVIEW_JSONL),
        },
        "post_overlay_next_steps": [
            "review the rewritten prompts for maintainer answerability",
            "materialize a repaired strict manifest overlay",
            "rerun stage10429 eval-hacking audit and stage10431 saved-runtime margin audit on the repaired strict rows",
        ],
    }

    write_json(HELPER_JSON, payload)
    write_jsonl(OVERLAY_JSONL, overlays)
    write_jsonl(PREVIEW_JSONL, previews)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
