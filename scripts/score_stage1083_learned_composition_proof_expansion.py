#!/usr/bin/env python3
"""Score composition proof-pool expansion with learned span-pair probabilities."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import torch


QENT_RE = re.compile(r"\bqent_([A-Za-z0-9]+)\b")
QSLOT_RE = re.compile(r"\bqslot_([A-Za-z0-9]+)\b")
TARGET_DENT_RE = re.compile(r"\btarget for dent_([A-Za-z0-9]+)\b")
DSLOT_RE = re.compile(r"\bdslot_([A-Za-z0-9]+)\b")
ANSWER_RE = re.compile(r"\banswer=([^\s]+)")


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


def _row_support(row: dict[str, Any]) -> tuple[int, int]:
    answer = exact = 0
    for candidate in list(row.get("candidates", []) or []):
        ans, ex = _candidate_hit(candidate)
        answer = max(answer, ans)
        exact = max(exact, ex)
    return answer, exact


def _query_parts(query_text: str) -> tuple[str, list[str]] | None:
    ents = QENT_RE.findall(str(query_text))
    slots = QSLOT_RE.findall(str(query_text))
    if not ents or len(slots) < 2:
        return None
    return ents[0], slots


def _doc_item(candidate: dict[str, Any]) -> dict[str, Any] | None:
    doc_text = str(candidate.get("doc_text", "") or "")
    if "op=composition" not in doc_text:
        return None
    ents = TARGET_DENT_RE.findall(doc_text)
    slots = DSLOT_RE.findall(doc_text)
    answer = ANSWER_RE.search(doc_text)
    if not ents or len(slots) < 2 or not answer:
        return None
    return {
        "target_entity": ents[0],
        "slots": sorted(set(slots)),
        "answer": answer.group(1),
        "doc_text": doc_text,
        "source_base_score": float(candidate.get("base_score", 0.0) or 0.0),
        "source_rank": int(candidate.get("rank", 9999) or 9999),
    }


def _composition_pool(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _typed_ok(query_entity: str, query_slots: list[str], item: dict[str, Any]) -> bool:
    return str(item["target_entity"]) == str(query_entity) and len(set(query_slots).intersection(set(item["slots"]))) >= 2


def _score_split(stage1052, model, vectors: dict[str, torch.Tensor], rows: list[dict[str, Any]]) -> dict[str, Any]:
    pool = _composition_pool(rows)
    comp_current_answer = comp_current_exact = 0
    comp_expanded_answer = comp_expanded_exact = 0
    recovered = 0
    by_operation: dict[str, Counter] = {}
    failures: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        operation = str(row.get("operation", "unknown"))
        stats = by_operation.setdefault(operation, Counter())
        stats["rows"] += 1
        current_answer, current_exact = _row_support(row)
        selected_answer, selected_exact = current_answer, current_exact
        if operation == "composition":
            comp_current_answer += current_answer
            comp_current_exact += current_exact
            parts = _query_parts(str(row.get("query_text", "")))
            if parts is not None:
                query_entity, query_slots = parts
                scored = []
                for item in pool:
                    ent_prob = _pair_prob(
                        stage1052,
                        model,
                        vectors,
                        pair_type="entity_statement",
                        query_span=_span_text("qent", query_entity),
                        doc_span=f"statement_dent_{item['target_entity']}",
                        base_score=float(item["source_base_score"]),
                        rank=int(item["source_rank"]),
                    )
                    slot_probs = []
                    for qslot in query_slots:
                        for dslot in item["slots"]:
                            slot_probs.append(
                                _pair_prob(
                                    stage1052,
                                    model,
                                    vectors,
                                    pair_type="slot",
                                    query_span=_span_text("qslot", qslot),
                                    doc_span=_span_text("dslot", dslot),
                                    base_score=float(item["source_base_score"]),
                                    rank=int(item["source_rank"]),
                                )
                            )
                    top_slots = sorted(slot_probs, reverse=True)[:2]
                    slot_score = sum(top_slots) / 2.0 if len(top_slots) >= 2 else 0.0
                    score = min(ent_prob, slot_score) + 0.1 * (ent_prob + slot_score)
                    scored.append((score, ent_prob, slot_score, item))
                scored.sort(key=lambda x: (x[0], x[1], x[2], x[3]["source_base_score"]), reverse=True)
                if scored:
                    best = scored[0][3]
                    if _typed_ok(query_entity, query_slots, best):
                        selected_answer = 1
                        selected_exact = 1
                        recovered += int(not current_answer)
                    elif not current_answer and len(failures) < 30:
                        failures.append(
                            {
                                "row_index": row_index,
                                "query_text": str(row.get("query_text", "")),
                                "expected_entity": query_entity,
                                "expected_slots": query_slots,
                                "predicted_entity": best["target_entity"],
                                "predicted_slots": best["slots"],
                                "top5": [
                                    {
                                        "score": float(item[0]),
                                        "entity_prob": float(item[1]),
                                        "slot_score": float(item[2]),
                                        "answer": item[3]["answer"],
                                        "target_entity": item[3]["target_entity"],
                                        "slots": item[3]["slots"],
                                    }
                                    for item in scored[:5]
                                ],
                            }
                        )
            comp_expanded_answer += selected_answer
            comp_expanded_exact += selected_exact
        stats["current_answer"] += current_answer
        stats["current_exact"] += current_exact
        stats["expanded_answer"] += selected_answer
        stats["expanded_exact"] += selected_exact
    return {
        "rows": len(rows),
        "composition_pool_docs": len(pool),
        "composition_current_support_answer_exact": [comp_current_answer, comp_current_exact],
        "composition_learned_expanded_answer_exact": [comp_expanded_answer, comp_expanded_exact],
        "composition_recovered_rows": recovered,
        "projected_stage1069_plus_learned_composition_pool_answer_exact": [
            350 + max(0, comp_expanded_answer - comp_current_answer),
            333 + max(0, comp_expanded_exact - comp_current_exact),
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
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1083_learned_composition_proof_expansion_summary.json"))
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
        parts = _query_parts(str(row.get("query_text", "")))
        if parts:
            spans.append(_span_text("qent", parts[0]))
            spans.extend(_span_text("qslot", slot) for slot in parts[1])
        for candidate in list(row.get("candidates", []) or []):
            item = _doc_item(candidate)
            if item:
                spans.append(f"statement_dent_{item['target_entity']}")
                spans.extend(_span_text("dslot", slot) for slot in item["slots"])
    model, vectors = _load_pair_model(stage1052, args.classifier_state, repo_root, spans)
    eval_score = _score_split(stage1052, model, vectors, split_rows.get("eval", []))
    hidden_score = _score_split(stage1052, model, vectors, hidden_rows)
    summary = {
        "artifact_kind": "stage1083_learned_composition_proof_expansion",
        "status": "completed_learned_composition_proof_expansion_probe",
        "targets_jsonl": str(args.targets_jsonl),
        "hidden_jsonl": str(args.hidden_jsonl),
        "classifier_state": str(args.classifier_state),
        "eval": eval_score,
        "hidden_eval": hidden_score,
        "decision": (
            "Scores split-local composition proof-pool expansion with the learned Stage1062 frozen-100M span-pair classifier. "
            "This tests target-entity plus two-slot proof expansion; rendered proof-pool construction is still external."
        ),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
