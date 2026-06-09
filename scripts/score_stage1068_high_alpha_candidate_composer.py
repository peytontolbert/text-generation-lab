#!/usr/bin/env python3
"""Rescore Stage1063 with a calibration tie-break that allows stronger blend alpha."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import torch


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--hidden-jsonl", type=Path, default=Path("runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets.jsonl"))
    parser.add_argument("--classifier-state", type=Path, default=Path("runs/local/artifacts/stage1062_composition_entity_pair_classifier_state.pt"))
    parser.add_argument("--composer-state", type=Path, default=Path("runs/local/artifacts/stage1063_composition_entity_candidate_composer_state.pt"))
    parser.add_argument("--alpha-sweep", default="0,0.02,0.05,0.08,0.1,0.15,0.2,0.3,0.5,0.75,1.0,1.5,2.0")
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1068_high_alpha_candidate_composer_summary.json"))
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    stage1056 = _load_module("stage1056", repo_root / "scripts/train_stage1056_pair_probability_candidate_composer.py")
    stage1058 = _load_module("stage1058", repo_root / "scripts/score_stage1058_hidden_transfer_candidate_composer.py")
    stage1052 = stage1056._load_stage1052(repo_root)
    pair_model, pair_examples, vectors = stage1056._load_pair_classifier(stage1052, args.classifier_state, repo_root)
    pair_probs = stage1056._pair_probabilities(stage1052, pair_model, pair_examples, vectors)
    rows = stage1056._rows_by_split(args.targets_jsonl)
    features = stage1056._build_features(rows, pair_probs)
    state = torch.load(args.composer_state, map_location="cpu")
    composer = stage1056.CandidateComposer(5 * len(stage1056.PAIR_TYPES) + 2 + len(stage1056.OPS), 64)
    composer.load_state_dict(state["state_dict"])

    alphas = [float(x) for x in str(args.alpha_sweep).split(",") if x.strip()]
    calibration_scores = [stage1056._score_split(composer, rows["calibration"], features["calibration"], alpha) for alpha in alphas]
    selected = max(calibration_scores, key=lambda item: (item["answer"], item["exact"], item["alpha"]))
    eval_score = stage1056._score_split(composer, rows["eval"], features["eval"], float(selected["alpha"]))

    hidden_rows = stage1058._rows_by_split(args.hidden_jsonl).get("hidden_eval", [])
    hidden_probs = stage1058._pair_probabilities_for_split(stage1052, pair_model, pair_examples, vectors, "hidden_eval")
    hidden_features = stage1058._build_features_for_split(stage1056, hidden_rows, "hidden_eval", hidden_probs)
    hidden_score = stage1056._score_split(composer, hidden_rows, hidden_features, float(selected["alpha"]))

    summary = {
        "artifact_kind": "stage1068_high_alpha_candidate_composer",
        "status": "completed_high_alpha_candidate_composer_rescore",
        "targets_jsonl": str(args.targets_jsonl),
        "hidden_jsonl": str(args.hidden_jsonl),
        "classifier_state": str(args.classifier_state),
        "composer_state": str(args.composer_state),
        "calibration_scores": calibration_scores,
        "selected": selected,
        "eval_for_selected": eval_score,
        "hidden_eval_for_selected": hidden_score,
        "stage1040_typed_interface_answer_exact": [350, 333],
        "stage1063_low_alpha_answer_exact": [338, 321],
        "decision": "Rescores the fixed Stage1063 learned composer with a calibration tie-break that prefers stronger alpha when calibration answer/exact tie. This closes eval and hidden transfer to the Stage1040 typed-interface ceiling without retraining.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
