#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import urllib.request
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


_row_text = _load_symbol(
    'stage9768_training_data',
    ROOT / 'legacy_src/agentkernel_lite/training_data.py',
    '_row_text',
)
SOURCE_BACKED_FIELD_ALIASES = {
    'symbol_binding': ('binding_action',),
    'edit_localization': ('edit_localization_target',),
    'patch_operator': ('patch_operator',),
    'verifier_repair': ('verifier_repair_action',),
}


def _clean_value(row: dict[str, Any], field: str) -> str | None:
    clean = row.get('clean_state') if isinstance(row.get('clean_state'), dict) else {}
    target = row.get('target') if isinstance(row.get('target'), dict) else {}
    value = clean.get(field, target.get(field, row.get(field)))
    if value is None:
        for alias in SOURCE_BACKED_FIELD_ALIASES.get(field, ()):  # source-backed canonical target names
            value = clean.get(alias, target.get(alias, row.get(alias)))
            if value is not None:
                break
    if value is None:
        return None
    if isinstance(value, list):
        return ' > '.join(str(item) for item in value)
    return str(value)


QUEUE = ROOT / "runs/local/artifacts/stage9748_supported_standalone_gemma_queue/supported_standalone_gemma_queue.json"
PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"

SKILL_TO_FIELD = {
    "symbol_binding": "symbol_binding",
    "edit_localization": "edit_localization",
    "patch_operator_selection": "patch_operator",
    "verifier_failure_repair_or_abstain": "verifier_repair",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    stripped_lines = [line for line in text.splitlines() if line.strip()]
    try:
        return [json.loads(line) for line in stripped_lines]
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        rows: list[dict[str, Any]] = []
        idx = 0
        length = len(text)
        while idx < length:
            while idx < length and text[idx].isspace():
                idx += 1
            if idx >= length:
                break
            value, next_idx = decoder.raw_decode(text, idx)
            if not isinstance(value, dict):
                raise ValueError(f"expected object record in {path}")
            rows.append(value)
            idx = next_idx
        return rows


def surface_row_projection(row: dict[str, Any]) -> dict[str, Any]:
    graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    retrieval = row.get("retrieval_control") if isinstance(row.get("retrieval_control"), dict) else {}
    return {
        "clean_state": clean,
        "graph_id": graph.get("graph_id"),
        "graph_query_kind": graph.get("query_kind"),
        "node_count": len(graph.get("nodes") or []),
        "edge_count": len(graph.get("edges") or []),
        "query": query,
        "retrieval_control": retrieval,
        "row_id": row.get("row_id"),
        "semantic_key": row.get("semantic_key"),
        "split": row.get("split"),
    }


def prompt_surface_hash(rows: list[dict[str, Any]]) -> str:
    payload = [surface_row_projection(row) for row in sorted(rows, key=lambda row: str(row.get("row_id") or ""))]
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(text.encode("utf-8")).hexdigest()


def target_field_for_skill(skill_area: str) -> str:
    if skill_area not in SKILL_TO_FIELD:
        raise KeyError(f"unsupported skill area: {skill_area}")
    return SKILL_TO_FIELD[skill_area]


def label_vocab(rows: list[dict[str, Any]], field: str) -> list[str]:
    values = sorted({value for row in rows if (value := _clean_value(row, field)) is not None})
    if not values:
        raise ValueError(f"no labels found for field {field}")
    return values


def build_prompt(*, row: dict[str, Any], field: str, labels: list[str]) -> str:
    encoder_surface = _row_text(row)
    return "\n".join([
        "You are evaluating a structured software-maintenance state.",
        f"Return only the exact label for `{field}`.",
        f"Valid labels: {', '.join(labels)}",
        "Do not explain your answer. Output one label only.",
        "",
        "Structured input surface:",
        encoder_surface,
    ])


def load_packet_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    same_surface = packet.get("same_surface_packet") if isinstance(packet.get("same_surface_packet"), dict) else {}
    manifest_path = ROOT / str(same_surface.get("source_manifest") or "")
    all_rows = load_jsonl(manifest_path)
    wanted = {str(value) for value in same_surface.get("row_ids") or []}
    rows = [row for row in all_rows if str(row.get("row_id") or "") in wanted]
    if not rows and "stage9771_edit_localization_visible_evidence_lift_package" in str(manifest_path):
        builder = _load_symbol(
            'stage9748_stage9771_builder',
            ROOT / 'scripts/build_stage9771_edit_localization_visible_evidence_lift_package.py',
            'lift_rows',
        )
        source_loader = _load_symbol(
            'stage9748_stage9771_source_loader',
            ROOT / 'scripts/build_stage9771_edit_localization_visible_evidence_lift_package.py',
            'load_jsonl',
        )
        source_path = _load_symbol(
            'stage9748_stage9771_source_path',
            ROOT / 'scripts/build_stage9771_edit_localization_visible_evidence_lift_package.py',
            'SOURCE',
        )
        reconstructed_rows = builder(source_loader(source_path))
        rows = [row for row in reconstructed_rows if str(row.get("row_id") or "") in wanted]
    rows.sort(key=lambda row: str(row.get("row_id") or ""))
    return rows


def select_rows(
    rows: list[dict[str, Any]],
    *,
    split: str | None,
    max_rows: int | None,
) -> list[dict[str, Any]]:
    selected = rows
    if split:
        selected = [row for row in selected if str(row.get("split") or "") == split]
    if max_rows is not None:
        selected = selected[:max_rows]
    return selected


def ollama_generate(*, model: str, prompt: str, seed: int = 0, temperature: float = 0.0) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "seed": seed,
            "temperature": temperature,
        },
    }).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


def run_packet(
    packet: dict[str, Any],
    *,
    model: str,
    dry_run: bool,
    split: str | None,
    max_rows: int | None,
) -> dict[str, Any]:
    all_rows = load_packet_rows(packet)
    rows = select_rows(all_rows, split=split, max_rows=max_rows)
    same_surface = packet.get("same_surface_packet") if isinstance(packet.get("same_surface_packet"), dict) else {}
    skill_area = str(packet.get("skill_area") or "")
    field = target_field_for_skill(skill_area)
    if not rows:
        raise ValueError(f"no rows selected for packet {packet.get('cell_key')}")
    labels = label_vocab(all_rows, field)
    predicted_rows: list[dict[str, Any]] = []
    correct = 0
    full_packet_surface_hash = prompt_surface_hash(all_rows)
    executed_surface_hash = prompt_surface_hash(rows)
    for row in rows:
        prompt = build_prompt(row=row, field=field, labels=labels)
        expected = _clean_value(row, field)
        raw_output = "[dry-run]" if dry_run else ollama_generate(model=model, prompt=prompt, seed=0, temperature=0.0)
        normalized = raw_output.splitlines()[0].strip() if raw_output else ""
        is_correct = (normalized == expected) if not dry_run else None
        if is_correct:
            correct += 1
        predicted_rows.append({
            "row_id": row.get("row_id"),
            "split": row.get("split"),
            "prompt": prompt,
            "expected_label": expected,
            "raw_output": raw_output,
            "predicted_label": None if dry_run else normalized,
            "correct": is_correct,
        })
    output_path = ROOT / str(packet.get("review_packet_paths", {}).get("same_prompt_surface_gemma12b_outputs") or "")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    per_row_path = output_path.with_name(output_path.stem + "_rows.jsonl")
    if predicted_rows:
        per_row_path.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in predicted_rows),
            encoding="utf-8",
        )
    score = None if dry_run or not predicted_rows else (correct / len(predicted_rows))
    result = {
        "cell_key": packet.get("cell_key"),
        "status": "dry_run_prompt_surface_ready" if dry_run else "completed_gemma_execution",
        "authorized_now": not dry_run,
        "model_runtime": "ollama",
        "model_id": model,
        "executed_split": split,
        "executed_row_count": len(predicted_rows),
        "label_vocab_scope": "full_packet",
        "decoder_temperature": 0.0,
        "decoder_seed": 0,
        "prompt_wrapper_version": "ollama_structured_label_v1",
        "same_surface_verified": full_packet_surface_hash == same_surface.get("surface_hash"),
        "prompt_surface_hash_gemma12b": executed_surface_hash,
        "full_packet_surface_hash_gemma12b": full_packet_surface_hash,
        "executed_subset_matches_full_packet": split is None and max_rows is None,
        "score_gemma12b": score,
        "output_artifact_paths": [str(per_row_path.relative_to(ROOT))] if predicted_rows else [],
        "notes": [
            "Uses the recovered 100M encoder surface from legacy_src/agentkernel_lite/training_data.py::_row_text",
            "Uses canonical structured labels from legacy_src/agentkernel_lite/training_loop.py::_clean_value",
        ],
        "authority": {
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "source_emission_authorized": False,
            "body_emission_authorized": False,
            "gemma_execution_authorized_next": not dry_run,
            "harness_execution_authorized_next": False,
            "scoring_authorized_next": False,
            "controller_complete_merge_authorized_next": False,
            "promotion_ready": False,
        },
    }
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--packets", type=Path, default=PACKETS)
    parser.add_argument("--model", default="gemma3:12b")
    parser.add_argument("--cell-key")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--split")
    parser.add_argument("--max-rows", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    queue = load_json(args.queue)
    packets = load_jsonl(args.packets)
    packet_index = {str(row.get("cell_key") or ""): row for row in packets}
    entries = queue.get("queue_entries") if isinstance(queue.get("queue_entries"), list) else []
    selected = [row for row in entries if row.get("ready_for_gemma_when_authorized") is True]
    if args.cell_key:
        selected = [row for row in selected if str(row.get("cell_key") or "") == args.cell_key]
    if args.limit is not None:
        selected = selected[: args.limit]
    results = []
    for entry in selected:
        packet = packet_index.get(str(entry.get("cell_key") or ""))
        if packet is None:
            raise SystemExit(f"missing review packet for {entry.get('cell_key')}")
        results.append(
            run_packet(
                packet,
                model=args.model,
                dry_run=args.dry_run,
                split=args.split,
                max_rows=args.max_rows,
            )
        )
    print(json.dumps({
        "model": args.model,
        "dry_run": args.dry_run,
        "split": args.split,
        "max_rows": args.max_rows,
        "executed_cells": [row.get("cell_key") for row in results],
        "result_paths": [packet_index[row.get("cell_key")]["review_packet_paths"]["same_prompt_surface_gemma12b_outputs"] for row in results],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
