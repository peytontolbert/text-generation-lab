#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/local/tmp/stage659_balanced_generalized_8kbpp_surface/agentkernel_lite_encdec_dataset_manifest.json"
OUT = ROOT / "runs/local/tmp/stage726_selector_collision_factor_surface"
ARTIFACT = ROOT / "runs/local/artifacts/stage726_selector_collision_factor_surface.json"
DOC = ROOT / "docs/stage726_selector_collision_factor_surface.md"
TEXT_FIELDS = {
    "decoder_text",
    "encoder_text",
    "json_decoder_text",
    "negative_decoder_text",
    "retrieval_doc_text",
    "retrieval_query_text",
    "state_text",
}
GSEL_RE = re.compile(r"gsel=([^\s]+)")
PARAMS = 16280
TARGET_KBPP = 8.0


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def collision_selector(gsel: str) -> str:
    parts = str(gsel or "").split("|")
    kind = parts[0] if parts else "unknown"
    if len(parts) < 2:
        return f"{kind}grp"
    domain = parts[1]
    if kind == "fact" and len(parts) >= 3:
        return f"factgrp|{domain}|{parts[2]}"
    if kind == "rel" and len(parts) >= 3:
        return f"relgrp|{domain}|{parts[2]}"
    if kind == "compose2" and len(parts) >= 4:
        return f"compose2grp|{domain}|{parts[2]}|{parts[3]}"
    if kind == "setcount" and len(parts) >= 3:
        return f"setcountgrp|{domain}|{parts[2]}"
    if kind == "neg" and len(parts) >= 3:
        return f"neggrp|{domain}|{parts[2]}"
    if kind == "exception" and len(parts) >= 3:
        return f"exceptiongrp|{domain}|{parts[2]}"
    return f"{kind}grp|{domain}"


def rewrite_text(text: str) -> tuple[str, str, str]:
    match = GSEL_RE.search(str(text or ""))
    if not match:
        return str(text or ""), "", ""
    original = match.group(1)
    rewritten = collision_selector(original)
    return GSEL_RE.sub(f"gsel={rewritten}", str(text or ""), count=1), original, rewritten


def rewrite_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    original_gsel = ""
    collision_gsel = ""
    for key in TEXT_FIELDS:
        if key not in out:
            continue
        rewritten, original, collision = rewrite_text(str(out.get(key, "") or ""))
        out[key] = rewritten
        if original and not original_gsel:
            original_gsel = original
            collision_gsel = collision
    out["stage726_original_gsel"] = original_gsel
    out["stage726_collision_gsel"] = collision_gsel
    out["stage726_selector_collision_factor_surface"] = True
    return out


def collision_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(row.get("stage726_collision_gsel", "") or "") for row in rows)
    counts.pop("", None)
    by_operation: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        selector = str(row.get("stage726_collision_gsel", "") or "")
        if selector:
            by_operation[str(row.get("operation", "") or "unknown")][selector] += 1
    return {
        "rows": len(rows),
        "distinct_collision_selectors": len(counts),
        "singleton_selectors": sum(1 for value in counts.values() if value == 1),
        "collision_selectors": sum(1 for value in counts.values() if value > 1),
        "rows_in_collision_selectors": sum(value for value in counts.values() if value > 1),
        "max_candidate_count": max(counts.values()) if counts else 0,
        "mean_candidate_count": (sum(counts.values()) / len(counts)) if counts else 0.0,
        "by_operation": {
            operation: {
                "rows": sum(counter.values()),
                "distinct_collision_selectors": len(counter),
                "singleton_selectors": sum(1 for value in counter.values() if value == 1),
                "collision_selectors": sum(1 for value in counter.values() if value > 1),
                "rows_in_collision_selectors": sum(value for value in counter.values() if value > 1),
                "max_candidate_count": max(counter.values()) if counter else 0,
                "mean_candidate_count": (sum(counter.values()) / len(counter)) if counter else 0.0,
            }
            for operation, counter in sorted(by_operation.items())
        },
    }


def main() -> None:
    source_manifest = json.loads(SOURCE.read_text(encoding="utf-8"))
    train_rows = [rewrite_row(row) for row in iter_jsonl(Path(str(source_manifest["train_dataset_path"])))]
    eval_rows = [rewrite_row(row) for row in iter_jsonl(Path(str(source_manifest["eval_dataset_path"])))]
    OUT.mkdir(parents=True, exist_ok=True)
    train_path = OUT / "agentkernel_lite_encdec_train.jsonl"
    eval_path = OUT / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, train_rows)
    write_jsonl(eval_path, eval_rows)

    total_bits = sum(float(row.get("stage653_verified_bits_if_correct", 0.0) or 0.0) for row in eval_rows)
    manifest = {
        "artifact_kind": "agentkernel_lite_encdec_stage726_selector_collision_factor_surface",
        "timestamp": int(time.time()),
        "source_manifest_path": str(SOURCE),
        "manifest_path": str(OUT / "agentkernel_lite_encdec_dataset_manifest.json"),
        "train_dataset_path": str(train_path),
        "eval_dataset_path": str(eval_path),
        "train_examples": len(train_rows),
        "eval_examples": len(eval_rows),
        "total_eval_verified_bits_available": total_bits,
        "perfect_ceiling_kbpp_at_16280_params": total_bits / PARAMS,
        "target_kbpp": TARGET_KBPP,
        "stage726_goal": "Make selector factors collide so factorized scoring cannot solve generalized KBPP by exact gsel identity.",
        "collision_rule": {
            "fact": "factgrp|domain|field",
            "rel": "relgrp|domain|relation",
            "compose2": "compose2grp|domain|relation|field",
            "setcount": "setcountgrp|domain|field",
            "neg": "neggrp|domain|field",
            "exception": "exceptiongrp|domain|field"
        },
        "train_collision_stats": collision_stats(train_rows),
        "eval_collision_stats": collision_stats(eval_rows),
        "acceptance_gates": {
            "trained_no_filter_answer_kbpp": ">= 8.0",
            "allowed_factor_key_has_collisions": True,
            "full_selector_identity_counts": False
        },
    }
    manifest_path = OUT / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ARTIFACT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage726 Selector-Collision Factor Surface

Artifact: `{ARTIFACT.relative_to(ROOT)}`

Manifest: `{manifest_path.relative_to(ROOT)}`

## Result

- Train rows: `{len(train_rows)}`
- Eval rows: `{len(eval_rows)}`
- Eval collision selectors: `{manifest['eval_collision_stats']['collision_selectors']}`
- Eval rows in collision selectors: `{manifest['eval_collision_stats']['rows_in_collision_selectors']}`
- Mean/max eval candidate count per selector: `{manifest['eval_collision_stats']['mean_candidate_count']}` / `{manifest['eval_collision_stats']['max_candidate_count']}`
- Perfect ceiling: `{manifest['perfect_ceiling_kbpp_at_16280_params']}` KBPP

## Change

Stage726 rewrites `gsel` from singleton row selectors to coarse collision selectors. The natural query/doc text still contains entity and value evidence, but the allowed key factor no longer uniquely isolates the row.

Acceptance requires factorized scoring to improve KBPP under these collisions. Full selector identity does not count.
""",
        encoding="utf-8",
    )
    print(json.dumps({"artifact": str(ARTIFACT), "manifest": str(manifest_path), "eval_collision_stats": manifest["eval_collision_stats"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
