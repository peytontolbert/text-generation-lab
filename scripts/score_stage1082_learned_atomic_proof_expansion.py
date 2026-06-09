#!/usr/bin/env python3
"""Score atomic proof-pool expansion with the learned Stage1062 pair classifier."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import torch


ANSWER_RE = re.compile(r"\banswer=([^\s]+)")
QENT_RE = re.compile(r"\bqent_([A-Za-z0-9]+)\b")
QSLOT_RE = re.compile(r"\bqslot_([A-Za-z0-9]+)\b")
STATEMENT_DENT_RE = re.compile(r"\bstatement=(?:claim\s+)?dent_([A-Za-z0-9]+)\b")
DSLOT_RE = re.compile(r"\bdslot_([A-Za-z0-9]+)\b")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _query_key(query_text: str) -> tuple[str, str] | None:
    ents = QENT_RE.findall(str(query_text))
    slots = QSLOT_RE.findall(str(query_text))
    if not ents or not slots:
        return None
    return ents[0], slots[-1]


def _doc_item(candidate: dict[str, Any]) -> dict[str, Any] | None:
    doc_text = str(candidate.get("doc_text", "") or "")
    if "op=atomic_fact" not in doc_text:
        return None
    ents = STATEMENT_DENT_RE.findall(doc_text)
    slots = DSLOT_RE.findall(doc_text)
    answer = ANSWER_RE.search(doc_text)
    if not ents or not slots or not answer:
        return None
    return {
        "entity": ents[0],
        "slot": slots[-1],
        "answer": answer.group(1),
        "doc_text": doc_text,
        "source_base_score": float(candidate.get("base_score", 0.0) or 0.0),
        "source_rank": int(candidate.get("rank", 9999) or 9999),
    }


def _atomic_pool(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        for candidate in list(row.get("candidates", []) or []):
            item = _doc_item(candidate)
            if item is None or item["doc_text"] in seen:
                continue
            seen.add(item["doc_text"])
            out.append(item)
    return out


def _span_text(prefix: str, value: str) -> str:
    return f"{prefix}_{value}"


def _load_pair_model(stage1052, state_path: Path, repo_root: Path, spans: list[str]):
    state = torch.load(state_path, map_location="cpu")
    retrieval_eval = stage1052._load_retrieval_eval(repo_root)
    bundle_dir = Path(state["summary"]["bundle_dir"]).resolve()
    base_model, tokenizer, _ = retrieval_eval._load_model(bundle_dir, repo_root=repo_root, device=torch.device("cpu"))
    base_model.eval()
    vectors = stage1052._encode_texts(retrieval_eval, tokenizer, base_model, sorted(set(spans)), max_tokens=32, batch_size=128, device=torch.device("cpu"))
    state_dict = state["state_dict"]
    input_dim = int(state_dict["net.0.weight"].shape[1])
    hidden_dim = int(state_dict["net.0.weight"].shape[0])
    model = stage1052.PairClassifier(input_dim, hidden_dim)
    model.load_state_dict(state_dict)
    model.eval()
    return model, vectors


def _pair_prob(stage1052, model, vectors: dict[str, torch.Tensor], *, pair_type: str, query_span: str, doc_span: str, base_score: float, rank: int) -> float:
    example = {
        "pair_type": pair_type,
        "query_span": query_span,
        "doc_span": doc_span,
        "candidate_base_score": float(base_score),
        "candidate_rank": int(rank),
    }
    with torch.no_grad():
        return float(torch.sigmoid(model(stage1052._features(example, vectors).unsqueeze(0))).item())


def _score_split(stage1052, model, vectors: dict[str, torch.Tensor], rows: list[dict[str, Any]]) -> dict[str, Any]:
    pool = _atomic_pool(rows)
    current_answer = current_exact = expanded_answer = expanded_exact = 0
    atomic_current_answer = atomic_current_exact = 0
    atomic_expanded_answer = atomic_expanded_exact = 0
    recovered = 0
    by_operation: dict[str, Counter] = {}
    failures: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        candidates = list(row.get("candidates", []) or [])
        operation = str(row.get("operation", "unknown"))
        stats = by_operation.setdefault(operation, Counter())
        stats["rows"] += 1
        if not candidates:
            continue
        base_idx = max(range(len(candidates)), key=lambda idx: float(candidates[idx].get("base_score", 0.0) or 0.0))
        base_answer, base_exact = _candidate_hit(candidates[base_idx])
        selected_answer, selected_exact = base_answer, base_exact
        selected_doc = str(candidates[base_idx].get("doc_text", ""))
        if operation == "atomic_fact":
            key = _query_key(str(row.get("query_text", "")))
            if key is not None:
                qent, qslot = key
                scored = []
                for item in pool:
                    ent_prob = _pair_prob(
                        stage1052,
                        model,
                        vectors,
                        pair_type="entity_statement",
                        query_span=_span_text("qent", qent),
                        doc_span=f"statement_dent_{item['entity']}",
                        base_score=float(item["source_base_score"]),
                        rank=int(item["source_rank"]),
                    )
                    slot_prob = _pair_prob(
                        stage1052,
                        model,
                        vectors,
                        pair_type="slot",
                        query_span=_span_text("qslot", qslot),
                        doc_span=_span_text("dslot", item["slot"]),
                        base_score=float(item["source_base_score"]),
                        rank=int(item["source_rank"]),
                    )
                    score = min(ent_prob, slot_prob) + 0.1 * (ent_prob + slot_prob)
                    scored.append((score, ent_prob, slot_prob, item))
                scored.sort(key=lambda x: (x[0], x[1], x[2], x[3]["source_base_score"]), reverse=True)
                if scored:
                    best = scored[0][3]
                    selected_doc = best["doc_text"]
                    if (best["entity"], best["slot"]) == key:
                        selected_answer = 1
                        selected_exact = 1
                        recovered += int(not base_answer)
                    elif not base_answer and len(failures) < 30:
                        failures.append(
                            {
                                "row_index": row_index,
                                "query_text": str(row.get("query_text", "")),
                                "expected_key": key,
                                "predicted_key": [best["entity"], best["slot"]],
                                "top5": [
                                    {
                                        "score": float(item[0]),
                                        "entity_prob": float(item[1]),
                                        "slot_prob": float(item[2]),
                                        "answer": item[3]["answer"],
                                        "entity": item[3]["entity"],
                                        "slot": item[3]["slot"],
                                    }
                                    for item in scored[:5]
                                ],
                            }
                        )
        current_answer += base_answer
        current_exact += base_exact
        expanded_answer += selected_answer
        expanded_exact += selected_exact
        stats["base_answer"] += base_answer
        stats["base_exact"] += base_exact
        stats["expanded_answer"] += selected_answer
        stats["expanded_exact"] += selected_exact
        if operation == "atomic_fact":
            atomic_current_answer += base_answer
            atomic_current_exact += base_exact
            atomic_expanded_answer += selected_answer
            atomic_expanded_exact += selected_exact
    return {
        "rows": len(rows),
        "atomic_pool_docs": len(pool),
        "base_answer_exact": [current_answer, current_exact],
        "atomic_base_answer_exact": [atomic_current_answer, atomic_current_exact],
        "atomic_learned_expanded_answer_exact": [atomic_expanded_answer, atomic_expanded_exact],
        "atomic_recovered_rows": recovered,
        "projected_stage1069_plus_learned_atomic_pool_answer_exact": [
            350 + max(0, atomic_expanded_answer - atomic_current_answer),
            333 + max(0, atomic_expanded_exact - atomic_current_exact),
        ],
        "by_operation": {operation: dict(counts) for operation, counts in sorted(by_operation.items())},
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--hidden-jsonl", type=Path, default=Path("runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets.jsonl"))
    parser.add_argument("--classifier-state", type=Path, default=Path("runs/local/artifacts/stage1062_composition_entity_pair_classifier_state.pt"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1082_learned_atomic_proof_expansion_summary.json"))
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    stage1052 = _load_module("stage1052", repo_root / "scripts/train_stage1052_contrastive_span_pair_classifier.py")
    split_rows: dict[str, list[dict[str, Any]]] = {}
    for row in _iter_jsonl(args.targets_jsonl):
        split_rows.setdefault(str(row.get("split", "unknown")), []).append(row)
    hidden_rows = list(_iter_jsonl(args.hidden_jsonl))
    all_rows = split_rows.get("eval", []) + hidden_rows
    spans: list[str] = []
    for row in all_rows:
        key = _query_key(str(row.get("query_text", "")))
        if key:
            spans.extend([_span_text("qent", key[0]), _span_text("qslot", key[1])])
        for candidate in list(row.get("candidates", []) or []):
            item = _doc_item(candidate)
            if item:
                spans.extend([f"statement_dent_{item['entity']}", _span_text("dslot", item["slot"])])
    model, vectors = _load_pair_model(stage1052, args.classifier_state, repo_root, spans)
    eval_score = _score_split(stage1052, model, vectors, split_rows.get("eval", []))
    hidden_score = _score_split(stage1052, model, vectors, hidden_rows)
    summary = {
        "artifact_kind": "stage1082_learned_atomic_proof_expansion",
        "status": "completed_learned_atomic_proof_expansion_probe",
        "targets_jsonl": str(args.targets_jsonl),
        "hidden_jsonl": str(args.hidden_jsonl),
        "classifier_state": str(args.classifier_state),
        "eval": eval_score,
        "hidden_eval": hidden_score,
        "stage1081_typed_projection_answer_exact": [364, 347],
        "decision": (
            "Scores split-local atomic proof-pool expansion with the learned Stage1062 frozen-100M span-pair classifier. "
            "This removes direct typed equality as the selection rule, but still uses rendered atomic proof-pool candidates."
        ),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
