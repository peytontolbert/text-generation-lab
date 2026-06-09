#!/usr/bin/env python3
"""Audit Stage959 relation query-slot hardener patch."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def load_builder():
    path = Path(__file__).resolve().parent / "build_stage819_hardened_binding_surface.py"
    spec = importlib.util.spec_from_file_location("stage819_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    builder = load_builder()
    examples = [
        "<AK_OP_RELATION> op=relation family=relations_and_sets domain=gdom_000 query=gdom_000_e001 linked_to",
        "<AK_OP_RELATION> op=relation family=relations_and_sets domain=gdom_000 query=gdom_000_e002 owned_by",
        "<AK_OP_RELATION> op=relation family=relations_and_sets domain=gdom_000 query=gdom_000_e003 overrides",
    ]
    rows = []
    for text in examples:
        hardened, mapping = builder._harden_text(text, side="query", salt="stage959_audit", harden_values=False)
        rows.append(
            {
                "input": text,
                "hardened": hardened,
                "mapping": mapping,
                "has_qslot": "qslot_" in hardened,
                "relation_aliases": {k: v for k, v in mapping.items() if k in {"linked_to", "owned_by", "overrides"}},
            }
        )
    summary = {
        "artifact_kind": "stage959_relation_query_slot_hardener_patch_audit",
        "status": "accepted_infrastructure_patch",
        "patched_file": "scripts/build_stage819_hardened_binding_surface.py",
        "examples": rows,
        "decision": "Relation query text now contributes qslot aliases through RELATION_QUERY_RE before split-local hashing. Next full rebuild should regenerate Stage917/918-style targets and rerun equality primitive under Stage957 contract.",
    }
    out = Path("runs/local/artifacts/stage959_relation_query_slot_hardener_patch_audit.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
