#!/usr/bin/env python3
"""Train a candidate composer over learned span-pair probability aggregates."""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F


PAIR_TYPES = ["entity_statement", "slot", "default_answer_kind", "default_policy_kind"]
OPS = ["atomic_fact", "composition", "counterfactual_false_claim", "exception", "relation"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_stage1052(repo_root: Path):
    path = repo_root / "scripts/train_stage1052_contrastive_span_pair_classifier.py"
    spec = importlib.util.spec_from_file_location("stage1052", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load stage1052: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _rows_by_split(path: Path) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {"train": [], "calibration": [], "eval": []}
    for row in _iter_jsonl(path):
        split = str(row.get("split", ""))
        if split in rows:
            rows[split].append(row)
    return rows


def _candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _label(candidates: list[dict[str, Any]]) -> int:
    for index, candidate in enumerate(candidates):
        if int(candidate.get("teacher_stage1040_selected", 0) or 0) == 1:
            return index
    for index, candidate in enumerate(candidates):
        if bool(candidate.get("is_exact")):
            return index
    for index, candidate in enumerate(candidates):
        if bool(candidate.get("is_answer_match")):
            return index
    return -1


def _load_pair_classifier(stage1052, state_path: Path, repo_root: Path):
    state = torch.load(state_path, map_location="cpu")
    pair_examples = list(_iter_jsonl(Path(state["summary"]["targets_jsonl"])))
    all_spans = sorted({str(ex["query_span"]) for ex in pair_examples} | {str(ex["doc_span"]) for ex in pair_examples})
    retrieval_eval = stage1052._load_retrieval_eval(repo_root)
    base_model, tokenizer, _ = retrieval_eval._load_model(Path(state["summary"]["bundle_dir"]).resolve(), repo_root=repo_root, device=torch.device("cpu"))
    base_model.eval()
    vectors = stage1052._encode_texts(retrieval_eval, tokenizer, base_model, all_spans, max_tokens=32, batch_size=128, device=torch.device("cpu"))
    sample_features = stage1052._features(pair_examples[0], vectors)
    model = stage1052.PairClassifier(int(sample_features.shape[-1]), 128)
    model.load_state_dict(state["state_dict"])
    model.eval()
    return model, pair_examples, vectors


def _pair_probabilities(stage1052, model, pair_examples: list[dict[str, Any]], vectors: dict[str, torch.Tensor]) -> dict[tuple[str, int, int], dict[str, list[float]]]:
    out: dict[tuple[str, int, int], dict[str, list[float]]] = {}
    with torch.no_grad():
        for example in pair_examples:
            if int(example.get("is_hidden_transfer", 0)) == 1:
                continue
            split = str(example.get("split", ""))
            if split not in {"train", "calibration", "eval"}:
                continue
            features = stage1052._features(example, vectors).unsqueeze(0)
            prob = float(torch.sigmoid(model(features)).item())
            key = (split, int(example["row_index"]), int(example["candidate_index"]))
            out.setdefault(key, {}).setdefault(str(example["pair_type"]), []).append(prob)
    return out


def _aggregate_features(row: dict[str, Any], candidate: dict[str, Any], probs: dict[str, list[float]]) -> torch.Tensor:
    operation = str(row.get("operation", ""))
    values: list[float] = []
    for pair_type in PAIR_TYPES:
        xs = [float(x) for x in probs.get(pair_type, [])]
        values.extend(
            [
                max(xs) if xs else 0.0,
                sum(xs) / float(len(xs) or 1),
                sum(1.0 for x in xs if x >= 0.5),
                sum(1.0 for x in xs if x >= 0.7),
                float(len(xs)),
            ]
        )
    values.extend(
        [
            float(candidate.get("base_score", 0.0) or 0.0),
            1.0 / max(1.0, float(candidate.get("rank", 9999) or 9999)),
        ]
    )
    values.extend([1.0 if operation == op else 0.0 for op in OPS])
    return torch.tensor(values, dtype=torch.float32)


def _build_features(rows: dict[str, list[dict[str, Any]]], pair_probs: dict[tuple[str, int, int], dict[str, list[float]]]) -> dict[str, list[torch.Tensor]]:
    out: dict[str, list[torch.Tensor]] = {}
    for split, split_rows in rows.items():
        split_features: list[torch.Tensor] = []
        for row_index, row in enumerate(split_rows):
            for candidate_index, candidate in enumerate(list(row.get("candidates", []) or [])):
                split_features.append(_aggregate_features(row, candidate, pair_probs.get((split, row_index, candidate_index), {})))
        out[split] = split_features
    return out


class CandidateComposer(torch.nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(int(input_dim), int(hidden_dim)),
            torch.nn.GELU(),
            torch.nn.Linear(int(hidden_dim), 1),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.net(features).squeeze(-1)


def _score_split(model: CandidateComposer, rows: list[dict[str, Any]], features: list[torch.Tensor], alpha: float) -> dict[str, Any]:
    answer = exact = base_answer = base_exact = 0
    by_operation: dict[str, dict[str, int]] = {}
    offset = 0
    model.eval()
    with torch.no_grad():
        for row in rows:
            candidates = list(row.get("candidates", []) or [])
            row_features = torch.stack(features[offset : offset + len(candidates)], dim=0)
            offset += len(candidates)
            scores = model(row_features)
            base_scores = torch.tensor([float(c.get("base_score", 0.0) or 0.0) for c in candidates], dtype=torch.float32)
            blend = base_scores + float(alpha) * scores
            pred_idx = int(torch.argmax(blend).item())
            base_idx = int(torch.argmax(base_scores).item())
            ans, ex = _candidate_hit(candidates[pred_idx])
            bans, bex = _candidate_hit(candidates[base_idx])
            op = str(row.get("operation", "unknown"))
            stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0})
            stats["rows"] += 1
            stats["answer"] += ans
            stats["exact"] += ex
            stats["base_answer"] += bans
            stats["base_exact"] += bex
            answer += ans
            exact += ex
            base_answer += bans
            base_exact += bex
    return {"rows": len(rows), "answer": answer, "exact": exact, "base_answer": base_answer, "base_exact": base_exact, "alpha": float(alpha), "by_operation": by_operation}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--classifier-state", type=Path, default=Path("runs/local/artifacts/stage1052_contrastive_span_pair_classifier_state.pt"))
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--batch-rows", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=0.003)
    parser.add_argument("--alpha-sweep", default="0,0.05,0.1,0.2,0.3,0.5,0.75,1.0,1.5,2.0")
    parser.add_argument("--seed", type=int, default=1056)
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1056_pair_probability_candidate_composer_summary.json"))
    parser.add_argument("--output-state", type=Path, default=Path("runs/local/artifacts/stage1056_pair_probability_candidate_composer_state.pt"))
    args = parser.parse_args()

    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    stage1052 = _load_stage1052(args.repo_root.resolve())
    pair_model, pair_examples, vectors = _load_pair_classifier(stage1052, args.classifier_state, args.repo_root.resolve())
    pair_probs = _pair_probabilities(stage1052, pair_model, pair_examples, vectors)
    rows = _rows_by_split(args.targets_jsonl)
    features = _build_features(rows, pair_probs)
    model = CandidateComposer(int(features["train"][0].shape[-1]), int(args.hidden_dim))
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=0.01)
    train_rows = rows["train"]
    row_feature_offsets = []
    offset = 0
    for row in train_rows:
        row_feature_offsets.append(offset)
        offset += len(list(row.get("candidates", []) or []))
    history = []
    for step in range(1, int(args.steps) + 1):
        selected_rows = random.choices(range(len(train_rows)), k=min(int(args.batch_rows), len(train_rows)))
        losses = []
        for row_index in selected_rows:
            row = train_rows[row_index]
            candidates = list(row.get("candidates", []) or [])
            label = _label(candidates)
            if label < 0:
                continue
            start = row_feature_offsets[row_index]
            row_features = torch.stack(features["train"][start : start + len(candidates)], dim=0)
            logits = model(row_features)
            losses.append(F.cross_entropy(logits.unsqueeze(0), torch.tensor([label], dtype=torch.long)))
        if not losses:
            continue
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % 50 == 0:
            history.append({"step": step, "loss": float(loss.detach().item())})
    alphas = [float(x) for x in str(args.alpha_sweep).split(",") if x.strip()]
    calibration_scores = [_score_split(model, rows["calibration"], features["calibration"], alpha) for alpha in alphas]
    selected = max(calibration_scores, key=lambda item: (item["answer"], item["exact"]))
    summary = {
        "artifact_kind": "stage1056_pair_probability_candidate_composer",
        "status": "completed_pair_probability_candidate_composer_probe",
        "targets_jsonl": str(args.targets_jsonl),
        "classifier_state": str(args.classifier_state),
        "head_parameter_count": sum(p.numel() for p in model.parameters()),
        "history": history,
        "calibration_selected": selected,
        "eval_for_calibration_selected": _score_split(model, rows["eval"], features["eval"], float(selected["alpha"])),
        "stage1054_answer_exact": [311, 294],
        "qwen3_8b_answer_exact": [317, 300],
        "decision": "Candidate composer trained over learned Stage1052 pair-probability aggregates and base/rank/operation features. No bridge fields, char comparator, suffix set intersection, or pair anchors are candidate-scoring inputs.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    torch.save({"summary": summary, "state_dict": model.state_dict()}, args.output_state)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
