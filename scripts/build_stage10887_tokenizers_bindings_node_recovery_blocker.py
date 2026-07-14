#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10887
NAME = "stage10887_tokenizers_bindings_node_recovery_blocker"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "tokenizers_bindings_node_recovery_blocker.json"

PREVIEW_JSON = ARTIFACTS / "stage10885_tokenizers_bindings_node_preview" / "tokenizers_bindings_node_preview.json"
HONESTY_JSON = ARTIFACTS / "stage10886_tokenizers_bindings_node_honesty_audit" / "tokenizers_bindings_node_honesty_audit.json"
SESSION_TRACES = ARTIFACTS / "session_like_source_inventory_real" / "current_recent96_session_execution_traces" / "session_execution_traces.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    preview = load_json(PREVIEW_JSON)
    honesty = load_json(HONESTY_JSON)
    stage5418_related = sorted(
        str(path.relative_to(ROOT))
        for path in ROOT.rglob("*")
        if path.is_file() and any(tag in path.name or tag in str(path) for tag in ["stage5418", "stage5419", "stage5420", "stage5421", "stage5422", "stage5423"])
    )

    bindings_node_failure_specific_matches = []
    for row in load_jsonl(SESSION_TRACES):
        refs = row.get("file_path_refs") or []
        cmd = str(row.get("command") or "")
        if "bindings/node/" not in " ".join(refs):
            continue
        if any(marker in cmd for marker in ["cargo check", "panic!", "Error::from_reason", "No provided input"]):
            bindings_node_failure_specific_matches.append(
                {
                    "command": cmd[:260],
                    "failure_type": str(((row.get("runtime_trace") or {}).get("failure_type")) or "unknown"),
                    "refs": refs[:10],
                }
            )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "bindings_node_needs_new_failure_specific_anchor_for_heldout_use",
        "claim_scope": [
            "Prove whether tokenizers::bindings/node can be upgraded further from the current local state into a heldout Rust maintainer eval root.",
            "Separate missing historical bridge artifacts from the surviving local evidence so the next recovery step is explicit rather than speculative.",
        ],
        "headline_findings": [
            "The bindings/node preview bundle is real and root-disjoint, but the current verifier signal is still only build-anchored.",
            "The stage5418-era bridge parquet and related local artifacts referenced in old traces are not present in the current workspace, so they cannot be used as authoritative evidence now.",
            "The surviving session inventory does not contain a concrete bindings/node failing test or execution transition that uniquely narrows the edit surface.",
        ],
        "metrics": {
            "missing_stage5418_related_artifacts_locally": len(stage5418_related) == 0,
            "stage5418_related_artifact_count": len(stage5418_related),
            "bindings_node_failure_specific_trace_matches": len(bindings_node_failure_specific_matches),
        },
        "remaining_blockers": [
            "no local failure-specific bindings/node verifier/test transition",
            "no surviving authoritative stage5418 bridge artifact in current workspace",
            "current packet still underdetermines singleton localization and evidence citation",
        ],
        "required_recovery_delta": [
            "recover or generate one concrete failing bindings/node build/test transition tied to a visible candidate path",
            "store the resulting verifier artifact inside the repo-local artifact tree",
            "rerun gold adjudication and anti-cheat review after that anchor exists",
        ],
        "next_best_steps": [
            "Treat bindings/node as support/stress or abstention-honesty material for now, not heldout headline evidence.",
            "Search other external repo/session stores for a real bindings/node failing transition if available.",
            "Otherwise focus Rust heldout recovery on a different root-disjoint candidate with a stronger verifier anchor.",
        ],
        "source_artifacts": {
            "preview_summary": rel(PREVIEW_JSON),
            "honesty_audit": rel(HONESTY_JSON),
            "session_inventory": rel(SESSION_TRACES),
        },
        "missing_artifact_search_results": stage5418_related[:20],
        "surviving_failure_specific_trace_matches": bindings_node_failure_specific_matches[:10],
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
