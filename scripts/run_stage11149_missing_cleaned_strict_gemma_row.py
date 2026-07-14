#!/usr/bin/env python3
"""Run local Gemma on cleaned-strict rows missing from prior Gemma artifact."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage11149_missing_cleaned_strict_gemma_row"
CLEAN_STRICT = (
    ROOT
    / "runs/local/artifacts/stage11146_singleton_strict_quarantine_successor/agentkernel_lite_encdec_strict_eval.jsonl"
)
GEMMA_FILTERED = (
    ROOT
    / "runs/local/artifacts/stage11148_cleaned_strict_gemma_rescore/cleaned_strict_gemma_rows.jsonl"
)
MODEL = "gemma3:12b"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_label(output: str, options: list[dict[str, Any]]) -> str | None:
    option_labels = [str(opt.get("label")) for opt in options if isinstance(opt, dict)]
    labels = sorted(option_labels, key=len, reverse=True)
    stripped = output.strip()
    for label in labels:
        if re.match(rf"^\s*{re.escape(label)}(?:\b|[.:\-)])", stripped):
            return label
    patterns = [
        r"(?:final answer|answer|choose|option)\s*[:\-]?\s*([A-Z][A-Z0-9]*)",
        r"\b([A-Z][A-Z0-9]*)\s*[.)]\s*",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, output, flags=re.IGNORECASE):
            value = match.group(1).upper()
            if value in option_labels:
                return value
    for label in labels:
        if re.search(rf"\b{re.escape(label)}\b", output):
            return label
    # Verifier rows often expose target IDs such as T1 inside option values
    # while the bounded answer label is A/B/C/D. Map those IDs back.
    for opt in options:
        if not isinstance(opt, dict):
            continue
        label = str(opt.get("label"))
        value = str(opt.get("value"))
        verifier_id = value.split("|", 1)[0].strip()
        if verifier_id and re.fullmatch(r"[A-Z][0-9]+", verifier_id):
            if re.search(rf"\b{re.escape(verifier_id)}\b", output):
                return label
    return None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    clean_rows = read_jsonl(CLEAN_STRICT)
    existing = read_jsonl(GEMMA_FILTERED)
    existing_ids = {row.get("row_id") for row in existing}
    missing = [row for row in clean_rows if row.get("row_id") not in existing_ids]
    results: list[dict[str, Any]] = []
    for row in missing:
        prompt = (
            "Return only the option label. Do not explain.\n\n"
            + str(row.get("input_text") or row.get("prompt_text") or "")
        )
        proc = subprocess.run(
            ["ollama", "run", MODEL],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        options = row.get("opaque_options") if isinstance(row.get("opaque_options"), list) else []
        predicted = parse_label(proc.stdout, options)
        target = str(row.get("target_text"))
        results.append(
            {
                "row_id": row.get("row_id"),
                "language_family": row.get("language_family"),
                "repo_family": row.get("repo_family"),
                "task_type": row.get("task_type"),
                "target_text": target,
                "opaque_options": options,
                "gemma12b_model": MODEL,
                "gemma12b_returncode": proc.returncode,
                "gemma12b_predicted_label": predicted,
                "gemma12b_correct": predicted == target,
                "gemma12b_raw_output": proc.stdout,
                "gemma12b_stderr": proc.stderr,
            }
        )

    correct = sum(1 for row in results if row.get("gemma12b_correct"))
    summary = {
        "stage": 11149,
        "stage_name": "missing_cleaned_strict_gemma_row",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "clean_strict": str(CLEAN_STRICT.relative_to(ROOT)),
            "existing_filtered_gemma": str(GEMMA_FILTERED.relative_to(ROOT)),
        },
        "model": MODEL,
        "metrics": {
            "missing_rows": len(missing),
            "completed_rows": len(results),
            "correct": correct,
            "accuracy": correct / len(results) if results else None,
            "nonzero_returncodes": [row["row_id"] for row in results if row["gemma12b_returncode"] != 0],
        },
        "decision": "missing_gemma_rows_executed" if results else "no_missing_rows",
        "outputs": {
            "rows_jsonl": str((OUT_DIR / "missing_cleaned_strict_gemma_rows.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "missing_cleaned_strict_gemma_row.json").relative_to(ROOT)),
        },
    }
    with (OUT_DIR / "missing_cleaned_strict_gemma_rows.jsonl").open("w") as f:
        for row in results:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    (OUT_DIR / "missing_cleaned_strict_gemma_row.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
