#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


INTENT_LABELS = {
    "plan": 0,
    "action_items": 1,
    "rewrite": 2,
    "translation": 3,
    "web_search": 4,
    "casual": 5,
    "source_echo": 6,
    "saved_data": 7,
    "ask_user": 8,
    "summary": 9,
    "title": 10,
    "checklist": 11,
    "risks": 12,
    "json": 13,
    "ranking": 14,
    "extraction": 15,
    "subject": 16,
    "brainstorm": 17,
}


COUNTRIES = [
    ("France", "Paris", "Euro", "Europe"),
    ("Germany", "Berlin", "Euro", "Europe"),
    ("Japan", "Tokyo", "Yen", "Asia"),
    ("Brazil", "Brasilia", "Real", "South_America"),
    ("Canada", "Ottawa", "Canadian_dollar", "North_America"),
    ("Kenya", "Nairobi", "Kenyan_shilling", "Africa"),
]

TOOLS = [
    ("search", "find current information", "needs_network"),
    ("calculator", "compute exact arithmetic", "offline"),
    ("calendar", "inspect schedule conflicts", "private"),
    ("files", "read local documents", "private"),
]


def _stable_id(*parts: object) -> str:
    return hashlib.sha256("\n".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _decision(content: str, task_type: str) -> str:
    return (
        f"<AK_STRUCTURED> <AK_ACTION_RESPOND> <AK_TASK_TYPE> {task_type} "
        f"<AK_CONTENT> {content} </AK_CONTENT> <AK_END>"
    )


def _prompt(*, tape: str, question: str, task_type: str, intent: str) -> str:
    return "\n".join(
        [
            "<AK_CHAT> <AK_RESPOND> PocketPal MDL lookup ladder example.",
            "<AK_AGENT_ACTIVE>",
            "Agent name: Knowledge Lookup Compiler",
            "Agent instruction: Answer from the compressed tape only. Prefer exact table fields over memorized phrases.",
            "Retrieval policy: current_context_only",
            "Tool policy: no_tools",
            "Action policy: respond_or_ask",
            "</AK_AGENT_ACTIVE>",
            f"<AK_TASK_HINT> intent={intent} task={task_type} mdl_lookup_ladder=true",
            "<AK_CONTEXT> Saved user data: none",
            "<AK_COMPRESSED_TAPE>",
            tape,
            "</AK_COMPRESSED_TAPE>",
            f"<AK_USER> {question}",
            "Return AK structured tokens. The content should be the answer only.",
        ]
    )


def _row(
    *,
    source_id: str,
    tape: str,
    question: str,
    answer: str,
    task_type: str = "active_agent_summary",
    intent: str = "summary",
    label: int,
    weight: float,
    negative: str = "",
) -> dict[str, Any]:
    encoder_text = _prompt(tape=tape, question=question, task_type=task_type, intent=intent)
    decoder_text = _decision(answer, task_type)
    return {
        "action": "respond",
        "answer_confidence_target": 0.98,
        "contrastive_label_id": int(label),
        "decoder_loss_weight": 1.0,
        "decoder_text": decoder_text,
        "encoder_text": encoder_text,
        "example_id": _stable_id("stage426", source_id, encoder_text, decoder_text),
        "expected_content": answer,
        "intent_label": intent,
        "intent_label_id": INTENT_LABELS[intent],
        "json_decoder_text": json.dumps(
            {"action": "respond", "content": answer, "proposal_metadata": {"task_type": task_type}},
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ),
        "negative_decoder_text": negative,
        "negative_loss_weight": 1.0 if negative else 0.0,
        "needs_verification_target": 0.05,
        "ood_evidence_target": 0.0,
        "ood_query_target": 0.0,
        "query_confidence_target": 0.98,
        "retrieval_doc_text": tape,
        "retrieval_loss_weight": 0.3,
        "retrieval_query_text": question,
        "source_id": source_id,
        "source_type": "pocketpal_stage426_mdl_lookup_ladder",
        "split": "train",
        "state_text": f"answer={answer}; tape={tape}",
        "task_type": task_type,
        "weight": float(weight),
    }


def _country_tape(rows: list[tuple[str, str, str, str]]) -> str:
    return "\n".join(
        [
            "<schema:country fields=name|capital|currency|continent>",
            *("|".join(row) for row in rows),
            "</schema>",
            "<rule> lookup answers by matching the requested field and row key. </rule>",
        ]
    )


def _tool_tape(rows: list[tuple[str, str, str]]) -> str:
    return "\n".join(
        [
            "<schema:tool fields=name|purpose|privacy>",
            *("|".join(row) for row in rows),
            "</schema>",
            "<rule> choose the tool whose purpose matches the request; preserve privacy label. </rule>",
        ]
    )


def _knowledge_rows(rng: random.Random, repeats: int, weight: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for repeat in range(repeats):
        sample = rng.sample(COUNTRIES, 4)
        tape = _country_tape(sample)
        by_country = {country: (capital, currency, continent) for country, capital, currency, continent in sample}
        by_capital = {capital: country for country, capital, _currency, _continent in sample}
        for index, (country, capital, currency, continent) in enumerate(sample):
            label = 426000 + repeat * 100 + index
            out.extend(
                [
                    _row(
                        source_id=f"country_{repeat}_{country}_capital",
                        tape=tape,
                        question=f"capital of {country}?",
                        answer=capital,
                        label=label,
                        weight=weight,
                        negative=currency,
                    ),
                    _row(
                        source_id=f"country_{repeat}_{country}_currency",
                        tape=tape,
                        question=f"currency of {country}?",
                        answer=currency,
                        label=label,
                        weight=weight,
                        negative=capital,
                    ),
                    _row(
                        source_id=f"country_{repeat}_{capital}_reverse",
                        tape=tape,
                        question=f"country with capital {capital}?",
                        answer=country,
                        label=label,
                        weight=weight,
                    ),
                    _row(
                        source_id=f"country_{repeat}_{country}_json",
                        tape=tape,
                        question=f"json fields for {country}",
                        answer=json.dumps(
                            {
                                "capital": capital,
                                "continent": continent,
                                "country": country,
                                "currency": currency,
                            },
                            ensure_ascii=True,
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        task_type="active_agent_json",
                        intent="json",
                        label=label,
                        weight=weight,
                    ),
                ]
            )
        euro = sorted(country for country, (_capital, currency, _continent) in by_country.items() if currency == "Euro")
        if euro:
            out.append(
                _row(
                    source_id=f"country_{repeat}_euro_list",
                    tape=tape,
                    question="listed countries using Euro?",
                    answer=", ".join(euro),
                    label=426900 + repeat,
                    weight=weight,
                )
            )
        # Deterministic consistency probe from a held field.
        capital = rng.choice(list(by_capital))
        out.append(
            _row(
                source_id=f"country_{repeat}_contrast_{capital}",
                tape=tape,
                question=f"is {capital} the capital of {by_capital[capital]}?",
                answer="yes",
                label=426950 + repeat,
                weight=weight,
                negative="no",
            )
        )

        tool_tape = _tool_tape(TOOLS)
        for index, (name, purpose, privacy) in enumerate(TOOLS):
            label = 427000 + repeat * 10 + index
            out.extend(
                [
                    _row(
                        source_id=f"tool_{repeat}_{name}_purpose",
                        tape=tool_tape,
                        question=f"what is {name} for?",
                        answer=purpose,
                        label=label,
                        weight=weight,
                    ),
                    _row(
                        source_id=f"tool_{repeat}_{name}_privacy",
                        tape=tool_tape,
                        question=f"privacy label for {name}?",
                        answer=privacy,
                        label=label,
                        weight=weight,
                    ),
                ]
            )
    return out


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def _copy_anchor(row: dict[str, Any], *, index: int, weight_cap: float) -> dict[str, Any]:
    copied = deepcopy(row)
    copied["example_id"] = _stable_id("stage426_anchor", index, copied.get("example_id"), copied.get("encoder_text"))
    copied["source_id"] = f"{copied.get('source_id', 'row')}_stage426_anchor_{index:05d}"
    copied["source_type"] = f"stage426_anchor_{copied.get('source_type', 'unknown')}"
    copied["split"] = "train"
    copied["weight"] = min(max(float(copied.get("weight") or 1.0), 1.0), float(weight_cap))
    return copied


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchor-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=426)
    parser.add_argument("--repeats", type=int, default=260)
    parser.add_argument("--knowledge-weight", type=float, default=12.0)
    parser.add_argument("--anchor-sample", type=int, default=12000)
    parser.add_argument("--anchor-weight-cap", type=float, default=8.0)
    parser.add_argument("--eval-ratio", type=float, default=0.05)
    args = parser.parse_args()

    rng = random.Random(int(args.seed))
    rows = _knowledge_rows(rng, int(args.repeats), float(args.knowledge_weight))
    anchor_manifest = json.loads(Path(args.anchor_manifest).read_text(encoding="utf-8"))
    anchors = list(_iter_jsonl(Path(anchor_manifest["train_dataset_path"])))
    rng.shuffle(anchors)
    for index, row in enumerate(anchors[: max(0, int(args.anchor_sample))]):
        rows.append(_copy_anchor(row, index=index, weight_cap=float(args.anchor_weight_cap)))
    rng.shuffle(rows)

    eval_count = max(256, int(len(rows) * float(args.eval_ratio)))
    eval_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        copied = deepcopy(row)
        if index < eval_count:
            copied["example_id"] = _stable_id("stage426_eval", index, copied.get("example_id"))
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
        "anchor_manifest": str(Path(args.anchor_manifest).resolve()),
        "artifact_kind": "agentkernel_lite_encdec_stage426_mdl_lookup_ladder",
        "dataset_format": "jsonl",
        "eval_dataset_path": str(eval_path),
        "eval_examples": len(eval_rows),
        "intent_labels": INTENT_LABELS,
        "manifest_path": str(manifest_path),
        "objective": "pocketpal_stage426_mdl_lookup_ladder",
        "train_dataset_path": str(train_path),
        "train_examples": len(train_rows),
        "total_examples": len(train_rows) + len(eval_rows),
        "training_principle": "easier MDL ladder: short compressed tapes, field lookup, reverse lookup, JSON lookup, and yes/no contrast before multi-step composition",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
