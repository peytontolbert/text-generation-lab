#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any


def _stable_id(*parts: object) -> str:
    return hashlib.sha256("\n".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def _decoder_stub(answer: str) -> str:
    return f"<AK_STRUCTURED> <AK_ACTION_RESPOND> <AK_TASK_TYPE> active_agent_json <AK_CONTENT> {answer} </AK_CONTENT> <AK_END>"


def _row(*, index: int, domain: str, entity: str, field: str, answer: str, distractors: list[str]) -> dict[str, Any]:
    query = f"lookup_answer domain={domain} entity={entity} field={field}"
    doc = f"answer_card domain={domain} entity={entity} field={field} answer={answer}"
    if distractors:
        doc += " distractors=" + ",".join(distractors[:4])
    encoder_text = "\n".join(
        [
            "<AK_CHAT> <AK_RESPOND> PocketPal answer-card retrieval.",
            "<AK_AGENT_ACTIVE>",
            "Agent name: Semantic Codec Retriever",
            "Agent instruction: retrieve the answer card matching domain, entity, and field.",
            "Tool policy: no_tools",
            "</AK_AGENT_ACTIVE>",
            f"<AK_QUERY> {query}",
            "<AK_USER> Select the matching semantic answer card.",
        ]
    )
    return {
        "action": "respond",
        "answer_confidence_target": 0.99,
        "contrastive_label_id": 429000 + index,
        "decoder_loss_weight": 0.0,
        "decoder_text": _decoder_stub(answer),
        "encoder_text": encoder_text,
        "example_id": _stable_id("stage429", domain, entity, field, answer),
        "expected_content": answer,
        "intent_label": "json",
        "intent_label_id": 13,
        "json_decoder_text": json.dumps({"action": "respond", "content": answer}, ensure_ascii=True, separators=(",", ":")),
        "negative_decoder_text": "",
        "negative_loss_weight": 0.0,
        "query_confidence_target": 0.99,
        "retrieval_doc_text": doc,
        "retrieval_loss_weight": 1.0,
        "retrieval_query_text": query,
        "source_id": f"stage429_{domain}_{entity}_{field}_{index:05d}",
        "source_type": "pocketpal_stage429_mdl_answer_card_retrieval",
        "split": "train",
        "state_text": doc,
        "task_type": "active_agent_json",
        "weight": 1.0,
    }


def _build_rows(*, domains: int, entities_per_domain: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    fields = ["capital", "currency", "continent", "owner", "status", "priority", "tool", "risk"]
    rows: list[dict[str, Any]] = []
    index = 0
    for domain_idx in range(domains):
        domain = f"domain_{domain_idx:03d}"
        domain_answers = [f"ans_{domain_idx:03d}_{slot:03d}" for slot in range(entities_per_domain * len(fields))]
        rng.shuffle(domain_answers)
        cursor = 0
        for entity_idx in range(entities_per_domain):
            entity = f"entity_{domain_idx:03d}_{entity_idx:03d}"
            for field in fields:
                answer = domain_answers[cursor]
                cursor += 1
                distractors = rng.sample([item for item in domain_answers if item != answer], k=4)
                rows.append(
                    _row(
                        index=index,
                        domain=domain,
                        entity=entity,
                        field=field,
                        answer=answer,
                        distractors=distractors,
                    )
                )
                index += 1
    rng.shuffle(rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=429)
    parser.add_argument("--domains", type=int, default=48)
    parser.add_argument("--entities-per-domain", type=int, default=12)
    parser.add_argument("--eval-ratio", type=float, default=0.12)
    args = parser.parse_args()

    rows = _build_rows(domains=int(args.domains), entities_per_domain=int(args.entities_per_domain), seed=int(args.seed))
    eval_count = max(256, int(len(rows) * float(args.eval_ratio)))
    eval_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        copied = dict(row)
        if index < eval_count:
            copied["example_id"] = _stable_id("stage429_eval", index, row["example_id"])
            copied["split"] = "eval"
            eval_rows.append(copied)
        else:
            copied["split"] = "train"
            train_rows.append(copied)

    output_dir = Path(args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    _write_jsonl(train_path, train_rows)
    _write_jsonl(eval_path, eval_rows)
    manifest = {
        "artifact_kind": "agentkernel_lite_encdec_stage429_mdl_answer_card_retrieval",
        "dataset_format": "jsonl",
        "eval_dataset_path": str(eval_path),
        "eval_examples": len(eval_rows),
        "manifest_path": str(manifest_path),
        "objective": "pocketpal_stage429_mdl_answer_card_retrieval",
        "train_dataset_path": str(train_path),
        "train_examples": len(train_rows),
        "total_examples": len(train_rows) + len(eval_rows),
        "training_principle": "answer-card retrieval isolates semantic access: query must retrieve a unique executable answer card instead of a repeated whole compressed tape",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
