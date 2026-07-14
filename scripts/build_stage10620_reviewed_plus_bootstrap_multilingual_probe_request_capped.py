#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10620
NAME = "stage10620_reviewed_plus_bootstrap_multilingual_probe_request_capped"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "reviewed_plus_bootstrap_multilingual_probe_request_capped.json"
COMMAND_JSON = OUT_DIR / "reviewed_plus_bootstrap_multilingual_probe_command_capped.json"
MANIFEST_JSONL = OUT_DIR / "reviewed_plus_bootstrap_multilingual_probe_manifest_capped.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_REQUEST = ROOT / "runs/local/artifacts/stage10619_reviewed_plus_bootstrap_multilingual_probe_request_deempty/reviewed_plus_bootstrap_multilingual_probe_request_deempty.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage10619_reviewed_plus_bootstrap_multilingual_probe_request_deempty/reviewed_plus_bootstrap_multilingual_probe_manifest_deempty.jsonl"
BROKEN_AUDIT = ROOT / "runs/local/artifacts/stage10619_reviewed_plus_bootstrap_multilingual_probe_deempty/bounded_decoder_probe/probe_contract_audit.json"

TMPDIR = Path("/data/tmp")
RUN_ID = "stage10620_reviewed_plus_bootstrap_multilingual_probe_capped"
OUTPUT_DIR = "runs/local/artifacts/stage10620_reviewed_plus_bootstrap_multilingual_probe_capped/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10620_reviewed_plus_bootstrap_multilingual_probe_capped/runtime_model"
MAX_TARGET_100M_TRAIN_ROWS = 105
BOOTSTRAP_PYTHON_ROOTS_TO_KEEP = 17


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


def main() -> None:
    source_request = load_json(SOURCE_REQUEST)
    broken_audit = load_json(BROKEN_AUDIT)
    rows = load_jsonl(SOURCE_MANIFEST)

    train_rows = [row for row in rows if row.get("split") == "train"]
    non_train_rows = [row for row in rows if row.get("split") != "train"]

    train_rows_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in train_rows:
        train_rows_by_root[str(row.get("root_id"))].append(row)

    bootstrap_python_roots: list[tuple[str, list[dict[str, Any]]]] = []
    kept_train_rows: list[dict[str, Any]] = []
    removed_train_rows: list[dict[str, Any]] = []

    for root_id, root_rows in train_rows_by_root.items():
        sample = root_rows[0]
        language = str(sample.get("language_family") or "unknown")
        source_kind = str(sample.get("package_source_kind") or "unknown")
        if language == "python" and source_kind == "compiled_root_state":
            bootstrap_python_roots.append((root_id, root_rows))
        else:
            kept_train_rows.extend(root_rows)

    bootstrap_python_roots.sort(
        key=lambda item: (
            str(item[1][0].get("repo_family") or ""),
            str(item[1][0].get("repo_id") or ""),
            str(item[0]),
        )
    )
    kept_python_roots = bootstrap_python_roots[:BOOTSTRAP_PYTHON_ROOTS_TO_KEEP]
    dropped_python_roots = bootstrap_python_roots[BOOTSTRAP_PYTHON_ROOTS_TO_KEEP:]
    for _, root_rows in kept_python_roots:
        kept_train_rows.extend(root_rows)
    for _, root_rows in dropped_python_roots:
        removed_train_rows.extend(root_rows)

    kept_train_rows.sort(key=lambda row: str(row.get("row_id") or ""))
    cleaned_rows = kept_train_rows + non_train_rows
    cleaned_rows.sort(key=lambda row: (str(row.get("split") or ""), str(row.get("row_id") or "")))
    write_jsonl(MANIFEST_JSONL, cleaned_rows)

    split_counts = Counter(str(row.get("split") or "unknown") for row in cleaned_rows)
    train_language_counts = Counter(str(row.get("language_family") or "unknown") for row in kept_train_rows)
    removed_language_counts = Counter(str(row.get("language_family") or "unknown") for row in removed_train_rows)
    kept_python_root_ids = [root_id for root_id, _ in kept_python_roots]
    dropped_python_root_ids = [root_id for root_id, _ in dropped_python_roots]

    if split_counts.get("train", 0) > MAX_TARGET_100M_TRAIN_ROWS:
        raise SystemExit(
            f"capped train rows still exceed target_100m contract: {split_counts.get('train', 0)} > {MAX_TARGET_100M_TRAIN_ROWS}"
        )

    command = list(source_request["command"])
    manifest_idx = command.index("--manifest") + 1
    command[manifest_idx] = str(ROOT / MANIFEST_JSONL)
    output_idx = command.index("--output-dir") + 1
    command[output_idx] = str(ROOT / OUTPUT_DIR)
    runtime_idx = command.index("--runtime-model-save-dir") + 1
    command[runtime_idx] = str(ROOT / RUNTIME_MODEL_DIR)
    run_idx = command.index("--run-id") + 1
    command[run_idx] = RUN_ID
    train_idx = command.index("--max-train-rows") + 1
    eval_idx = command.index("--max-eval-rows") + 1
    strict_idx = command.index("--max-strict-rows") + 1
    command[train_idx] = str(split_counts.get("train", 0))
    command[eval_idx] = str(split_counts.get("eval", 0))
    command[strict_idx] = str(split_counts.get("strict_eval", 0))

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "reviewed_plus_bootstrap_multilingual_probe_capped_ready",
        "claim_scope": [
            "Repair the stage10619 target_100m contract failure by capping train rows to the hard allowed limit.",
            "Preserve all non-Python train roots and all reviewed Rust support rows.",
            "Downsample only compiled_root_state Python bootstrap train roots, keeping whole roots rather than slicing rows.",
        ],
        "source_request": display(SOURCE_REQUEST),
        "source_broken_contract_audit": display(BROKEN_AUDIT),
        "manifest": display(MANIFEST_JSONL),
        "run_id": RUN_ID,
        "output_dir": OUTPUT_DIR,
        "runtime_model_dir": RUNTIME_MODEL_DIR,
        "rows": len(cleaned_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "train_language_counts": dict(sorted(train_language_counts.items())),
        "target_100m_train_cap": MAX_TARGET_100M_TRAIN_ROWS,
        "kept_bootstrap_python_roots": {
            "count": len(kept_python_root_ids),
            "root_ids": kept_python_root_ids,
        },
        "dropped_bootstrap_python_roots": {
            "count": len(dropped_python_root_ids),
            "root_ids": dropped_python_root_ids,
        },
        "removed_train_rows": {
            "count": len(removed_train_rows),
            "language_counts": dict(sorted(removed_language_counts.items())),
            "sample_row_ids": [str(row.get("row_id") or "") for row in removed_train_rows[:28]],
        },
        "why_removed": (broken_audit.get("errors") or []),
        "required_honesty_gates": source_request.get("required_honesty_gates"),
        "post_run_required_artifacts": source_request.get("post_run_required_artifacts"),
        "known_limits": source_request.get("known_limits"),
        "next_best_step": "Launch this capped successor request and verify that model execution begins before interpreting any result.",
        "command": command,
    }

    write_json(COMMAND_JSON, {"command": command, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)})
    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "request": display(REQUEST_JSON),
            "manifest": display(MANIFEST_JSONL),
        },
    )
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": True,
                "rows": len(cleaned_rows),
                "train_rows": split_counts.get("train", 0),
                "removed_train_rows": len(removed_train_rows),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
