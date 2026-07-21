#!/usr/bin/env python3
"""Build Stage12259 Codex tool-call observation pairs.

Pairs tool calls from Stage12258 with corresponding output observations by
chat_id/call_id. Emits metadata and digests only, not raw arguments or output.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12259_codex_tool_call_observation_pairer"
SRC_DIR = ROOT / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index"
EVENTS = SRC_DIR / "chat_event_index.jsonl"
TOOLS = SRC_DIR / "chat_tool_call_index.jsonl"


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            yield line_no, json.loads(line)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def main() -> int:
    calls_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    outputs_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for _, row in iter_jsonl(TOOLS) or []:
        call_id = row.get("call_id")
        if not call_id:
            continue
        calls_by_key[(row["chat_id"], call_id)].append(row)
    for _, row in iter_jsonl(EVENTS) or []:
        call_id = row.get("call_id")
        if not call_id or not row.get("has_output"):
            continue
        outputs_by_key[(row["chat_id"], call_id)].append(row)

    pairs: list[dict[str, Any]] = []
    unpaired_calls: list[dict[str, Any]] = []
    unpaired_outputs: list[dict[str, Any]] = []
    tool_counts: Counter[str] = Counter()
    paired_tool_counts: Counter[str] = Counter()
    command_heads: Counter[str] = Counter()
    output_payload_types: Counter[str] = Counter()

    all_keys = set(calls_by_key) | set(outputs_by_key)
    for key in sorted(all_keys):
        calls = sorted(calls_by_key.get(key, []), key=lambda r: int(r.get("line_number") or 0))
        outputs = sorted(outputs_by_key.get(key, []), key=lambda r: int(r.get("line_number") or 0))
        if not calls:
            for out in outputs:
                unpaired_outputs.append(
                    {
                        "chat_id": key[0],
                        "call_id": key[1],
                        "output_event_id": out.get("event_id"),
                        "output_line_number": out.get("line_number"),
                        "payload_type": out.get("payload_type"),
                        "reason": "output_without_indexed_call",
                    }
                )
            continue
        for call in calls:
            tool_counts[str(call.get("tool_name") or "")] += 1
            if call.get("command_head"):
                command_heads[str(call["command_head"])] += 1
            matching_outputs = [out for out in outputs if int(out.get("line_number") or 0) >= int(call.get("line_number") or 0)]
            out = matching_outputs[0] if matching_outputs else (outputs[0] if outputs else None)
            if not out:
                unpaired_calls.append(
                    {
                        "chat_id": key[0],
                        "call_id": key[1],
                        "tool_record_id": call.get("tool_record_id"),
                        "tool_name": call.get("tool_name"),
                        "call_line_number": call.get("line_number"),
                        "command_head": call.get("command_head"),
                        "reason": "call_without_output",
                    }
                )
                continue
            paired_tool_counts[str(call.get("tool_name") or "")] += 1
            output_payload_types[str(out.get("payload_type") or "")] += 1
            pairs.append(
                {
                    "chat_id": key[0],
                    "call_id": key[1],
                    "tool_name": call.get("tool_name"),
                    "command_head": call.get("command_head"),
                    "call_event_id": call.get("event_id"),
                    "call_line_number": call.get("line_number"),
                    "output_event_id": out.get("event_id"),
                    "output_line_number": out.get("line_number"),
                    "output_payload_type": out.get("payload_type"),
                    "arguments_digest": call.get("arguments_digest"),
                    "output_digest": out.get("payload_digest_redacted"),
                    "call_before_output": int(call.get("line_number") or 0) <= int(out.get("line_number") or 0),
                    "raw_arguments_emitted": False,
                    "raw_output_emitted": False,
                    "pairer_version": "stage12259_v1",
                }
            )

    summary = {
        "stage": STAGE,
        "artifact_type": "codex_tool_call_observation_pairer",
        "decision": "tool_call_observation_pairs_ready_for_task_boundary_mining",
        "training_allowed": False,
        "claim_boundary": "Metadata/digest pair index only. No raw arguments, raw output, patch bodies, root admission, or training.",
        "counts": {
            "indexed_calls": sum(len(v) for v in calls_by_key.values()),
            "indexed_outputs": sum(len(v) for v in outputs_by_key.values()),
            "paired_calls": len(pairs),
            "unpaired_calls": len(unpaired_calls),
            "unpaired_outputs": len(unpaired_outputs),
            "tool_counts": dict(tool_counts),
            "paired_tool_counts": dict(paired_tool_counts),
            "command_head_counts_top": dict(command_heads.most_common(40)),
            "output_payload_type_counts": dict(output_payload_types),
        },
        "guardrails": {
            "raw_arguments_emitted": False,
            "raw_output_emitted": False,
            "raw_patch_body_emitted": False,
            "training_rows_emitted_now": False,
        },
        "next_stage": {
            "stage": "stage12260_codex_chat_task_boundary_miner",
            "purpose": "Mine per-chat task windows using paired commands/observations, patch events, and user/assistant turns.",
            "training_allowed": False,
        },
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_jsonl(out_dir / "tool_call_observation_pairs.jsonl", pairs)
    if unpaired_calls:
        write_jsonl(out_dir / "unpaired_tool_calls.jsonl", unpaired_calls)
    if unpaired_outputs:
        write_jsonl(out_dir / "unpaired_tool_outputs.jsonl", unpaired_outputs)
    write_json(out_dir / "tool_call_observation_pair_summary.json", summary)
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", summary)
    md = f"""# Stage12259 Codex Tool Call Observation Pairer

## Decision

`{summary["decision"]}`

No training is allowed.

## Counts

- indexed calls: `{summary["counts"]["indexed_calls"]}`
- indexed outputs: `{summary["counts"]["indexed_outputs"]}`
- paired calls: `{summary["counts"]["paired_calls"]}`
- unpaired calls: `{summary["counts"]["unpaired_calls"]}`

This fixes the Stage12258 interpretation bug where outputs were separate `function_call_output` rows rather than fields on tool call rows.
"""
    write_text(out_dir / "CODEX_TOOL_CALL_OBSERVATION_PAIRER_STAGE12259.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "tool_call_observation_pairs.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
