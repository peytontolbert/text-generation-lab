#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DIRECT_TASK = "active_agent_direct_answer"
QUERY_RE = re.compile(r"query=([^ ]+) of ([^ ]+) target for")
DOC_RE = re.compile(r"statement=dslot_([0-9a-f]+) of dslot_([0-9a-f]+) target")


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _direct_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("task_type", "") or "") == DIRECT_TASK
        and str(row.get("retrieval_query_text", "") or "").strip()
        and str(row.get("retrieval_doc_text", "") or "").strip()
    ]


def _unique_doc_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        doc = str(row.get("retrieval_doc_text", "") or "").strip()
        if doc and doc not in seen:
            seen.add(doc)
            docs.append(row)
    return docs


def _load_context(manifest_path: Path) -> dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {}
    for split, key in (
        ("train", "train_dataset_path"),
        ("calibration", "calibration_dataset_path"),
        ("eval", "eval_dataset_path"),
    ):
        rows = _direct_rows(_iter_jsonl(Path(manifest[key])))
        out[split] = (rows, _unique_doc_rows(rows))
    return out


def _query_proof_tokens(query_text: str) -> list[str]:
    match = QUERY_RE.search(str(query_text or ""))
    if not match:
        return []
    field, relation = match.groups()
    return [f"field:{field}", f"relation:{relation}", f"edge:{relation}->{field}"]


def _doc_proof_tokens(doc_text: str, doc_row: dict[str, Any]) -> list[str]:
    match = DOC_RE.search(str(doc_text or ""))
    if not match:
        return []
    field_suffix, relation_suffix = match.groups()
    binding = dict(doc_row.get("stage819_hardened_binding", {}) or {})
    aliases = dict(binding.get("doc_aliases", {}) or {})
    inverse = {str(alias): str(original) for original, alias in aliases.items()}
    field = inverse.get(f"dslot_{field_suffix}")
    relation = inverse.get(f"dslot_{relation_suffix}")
    if not field or not relation:
        return []
    return [f"field:{field}", f"relation:{relation}", f"edge:{relation}->{field}"]


def _score_composition(rows: list[dict[str, Any]], split: str) -> dict[str, Any]:
    total = base_answer = base_exact = proof_answer = proof_exact = 0
    recoverable_answer = recoverable_exact = proof_present = proof_exact_present = 0
    for row in rows:
        if row.get("split") != split or row.get("operation") != "composition":
            continue
        candidates = list(row.get("candidates", []) or [])
        if not candidates:
            continue
        total += 1
        base_order = sorted(range(len(candidates)), key=lambda idx: (-float(candidates[idx].get("base_score", 0.0) or 0.0), idx))
        base_top = candidates[base_order[0]]
        base_answer += int(bool(base_top.get("is_exact") or base_top.get("is_answer_match")))
        base_exact += int(bool(base_top.get("is_exact")))

        def proof_match(idx: int) -> int:
            bridge = dict(candidates[idx].get("bridge", {}) or {})
            return int(bool(bridge.get("proof_edge_match")))

        if any(proof_match(idx) for idx in range(len(candidates))):
            proof_present += 1
            proof_exact_present += int(any(proof_match(idx) and bool(candidates[idx].get("is_exact")) for idx in range(len(candidates))))
        proof_order = sorted(
            range(len(candidates)),
            key=lambda idx: (-proof_match(idx), -float(candidates[idx].get("base_score", 0.0) or 0.0), idx),
        )
        proof_top = candidates[proof_order[0]]
        proof_answer += int(bool(proof_top.get("is_exact") or proof_top.get("is_answer_match")))
        proof_exact += int(bool(proof_top.get("is_exact")))
        recoverable_answer += int(any(bool(c.get("is_exact") or c.get("is_answer_match")) for c in candidates))
        recoverable_exact += int(any(bool(c.get("is_exact")) for c in candidates))
    return {
        "rows": total,
        "base_answer_exact": [base_answer, base_exact],
        "proof_bonus_answer_exact": [proof_answer, proof_exact],
        "recoverable_answer_exact": [recoverable_answer, recoverable_exact],
        "proof_present": proof_present,
        "proof_exact_present": proof_exact_present,
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    source_rows = [json.loads(line) for line in Path(args.stage907_jsonl).read_text(encoding="utf-8").splitlines() if line.strip()]
    context = _load_context(Path(args.dataset_manifest))
    augmented: list[dict[str, Any]] = []
    proof_positive_candidates = 0
    for row in source_rows:
        split = str(row.get("split", ""))
        text_rows, doc_rows = context[split]
        out = dict(row)
        query_text = str(out.get("query_text", "") or "")
        qproof = _query_proof_tokens(query_text) if out.get("operation") == "composition" else []
        candidates = []
        for candidate in list(out.get("candidates", []) or []):
            cand = dict(candidate)
            bridge = dict(cand.get("bridge", {}) or {})
            dproof: list[str] = []
            if out.get("operation") == "composition":
                doc_index = int(cand["doc_index"])
                dproof = _doc_proof_tokens(str(cand.get("doc_text", "") or ""), doc_rows[doc_index])
            qset = set(qproof)
            dset = set(dproof)
            bridge["qproof"] = qproof
            bridge["dproof"] = dproof
            bridge["proof_token_match"] = bool(qset and qset == dset)
            bridge["proof_edge_match"] = bool(qset and f"edge:{qproof[-1].split(':', 1)[-1]}" in dset)
            proof_positive_candidates += int(bool(bridge["proof_edge_match"]) and bool(cand.get("is_exact") or cand.get("is_answer_match")))
            cand["bridge"] = bridge
            candidates.append(cand)
        out["candidates"] = candidates
        if qproof:
            out["query_bridge"] = {**dict(out.get("query_bridge", {}) or {}), "qproof": qproof}
        augmented.append(out)

    output_jsonl = Path(args.output_jsonl)
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl.open("w", encoding="utf-8") as handle:
        for row in augmented:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    summary = {
        "artifact_kind": "stage913_composition_proof_bridge_targets",
        "output_jsonl": str(output_jsonl),
        "stage907_jsonl": str(Path(args.stage907_jsonl).resolve()),
        "dataset_manifest": str(Path(args.dataset_manifest).resolve()),
        "decision": "Diagnostic target materialization. Side-invariant composition proof labels can identify useful eval edges, but they are metadata-derived targets, not accepted eval-time features.",
        "interpretation": "Stage819 hardening missed composition query proof slots. Stage913 reconstructs semantic proof-edge targets from query text plus doc alias metadata so the next route can supervise proof-edge prediction without memorizing split-local dslot ids.",
        "proof_positive_candidates": proof_positive_candidates,
        "composition_scores": {
            split: _score_composition(augmented, split) for split in ("train", "calibration", "eval")
        },
        "next_steps": [
            "Use this artifact to train a proof-edge auxiliary head, then evaluate without qproof/dproof features at inference.",
            "Patch the hardening builder to parse composition query fields/relations if explicit typed-access experiments are desired.",
            "Do not accept metadata-derived proof-edge scoring as model-owned KBPP.",
        ],
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage907-jsonl", default="runs/local/artifacts/stage907_broad_bridge_curriculum_targets.jsonl")
    parser.add_argument("--dataset-manifest", default="runs/local/tmp/stage846_external_alias_calibration50_retained_train_surface/agentkernel_lite_encdec_dataset_manifest.json")
    parser.add_argument("--output-jsonl", default="runs/local/artifacts/stage913_composition_proof_bridge_targets.jsonl")
    parser.add_argument("--summary-json", default="runs/local/artifacts/stage913_composition_proof_bridge_targets_summary.json")
    build(parser.parse_args())


if __name__ == "__main__":
    main()
