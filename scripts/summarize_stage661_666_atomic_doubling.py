#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main() -> None:
    eval661 = load_json("runs/local/artifacts/stage661_atomic_binding_capacity_eval_fast.json")
    train661 = load_json("runs/local/artifacts/stage661_atomic_binding_capacity_train_fast.json")
    eval662 = load_json("runs/local/artifacts/stage662_atomic_overfit_1k_fast_eval.json")
    eval663 = load_json("runs/local/artifacts/stage663_atomic_overfit_1k_keyhash_fast_eval.json")
    sweep664 = load_json("runs/local/artifacts/stage664_atomic_binding_overfit_sweep.json")
    eval664 = load_json("runs/local/artifacts/stage664_atomic_overfit_64_fast_eval.json")
    eval665 = load_json("runs/local/artifacts/stage665_atomic_overfit_128_fast_eval.json")
    eval666 = load_json("runs/local/artifacts/stage666_atomic_overfit_128_polish_fast_eval.json")

    solved64_bits = float(eval664["total"]["answer_verified_bits"])
    best128_bits = float(eval666["total"]["answer_verified_bits"])
    summary = {
        "artifact_kind": "stage661_666_atomic_binding_doubling_summary",
        "decision": "recursive_atomic_doubling_positive_but_not_clean_2x",
        "stage661_full_atomic_relation_probe": {
            "train_answer_kbpp": train661["answer_kbpp"],
            "train_answer_accuracy": train661["total"]["answer_accuracy"],
            "eval_answer_kbpp": eval661["answer_kbpp"],
            "eval_answer_accuracy": eval661["total"]["answer_accuracy"],
            "finding": "Broad atomic/relation binding training cannot recover even train rows with the current path.",
        },
        "stage662_1k_atomic_overfit": {
            "answer_kbpp": eval662["answer_kbpp"],
            "answer_accuracy": eval662["total"]["answer_accuracy"],
            "answer_correct": eval662["total"]["answer_correct"],
            "total": eval662["total"]["total"],
            "finding": "One-shot 1024-row atomic overfit fails.",
        },
        "stage663_1k_keyhash_overfit": {
            "answer_kbpp": eval663["answer_kbpp"],
            "answer_accuracy": eval663["total"]["answer_accuracy"],
            "answer_correct": eval663["total"]["answer_correct"],
            "parameter_count": eval663["parameter_count"],
            "finding": "Learned key-hash side-channel does not solve 1024-row overfit and worsens KBPP via larger denominator.",
        },
        "stage664_sweep": sweep664,
        "stage664_64_overfit": {
            "answer_kbpp": eval664["answer_kbpp"],
            "answer_accuracy": eval664["total"]["answer_accuracy"],
            "answer_correct": eval664["total"]["answer_correct"],
            "answer_verified_bits": solved64_bits,
            "parameter_count": eval664["parameter_count"],
            "finding": "The existing initialized 16k geometry can perfectly solve the 64-row atomic binding cell.",
        },
        "stage665_128_from64": {
            "answer_kbpp": eval665["answer_kbpp"],
            "answer_accuracy": eval665["total"]["answer_accuracy"],
            "answer_correct": eval665["total"]["answer_correct"],
            "answer_verified_bits": eval665["total"]["answer_verified_bits"],
            "finding": "Naive recursive doubling to 128 recovers more bits than 64 but forgets old rows and misses new rows.",
        },
        "stage666_128_polish": {
            "answer_kbpp": eval666["answer_kbpp"],
            "answer_accuracy": eval666["total"]["answer_accuracy"],
            "answer_correct": eval666["total"]["answer_correct"],
            "answer_verified_bits": best128_bits,
            "multiple_vs_stage664_64_bits": best128_bits / solved64_bits if solved64_bits else None,
            "finding": "Consolidation improves 128-row recovery but reaches 1.578x verified bits, not a clean 2x.",
        },
        "next_algorithmic_change": {
            "label": "stage667_full_corpus_negative_or_memory_bank_consolidation",
            "rationale": "Batch-local contrastive training solves one 64-row batch but weakens when the corpus spans multiple batches. The next doubling primitive should expose cross-batch negatives or a full-corpus/memory-bank loss during each consolidation phase.",
            "acceptance": "128-row atomic overfit exact/answer recovery near 1.0, then continue 256, 512, 1024 recursively.",
        },
        "timestamp": int(time.time()),
    }

    out = ROOT / "runs/local/artifacts/stage661_666_atomic_binding_doubling_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
