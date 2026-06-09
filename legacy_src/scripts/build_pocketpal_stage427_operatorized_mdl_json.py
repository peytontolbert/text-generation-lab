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

STRUCTURED_JSON_PREFIX = "<AK_STRUCTURED> <AK_ACTION_RESPOND> <AK_TASK_TYPE> active_agent_json "

COUNTRIES = [
    ("France", "Paris", "Euro", "Europe"),
    ("Germany", "Berlin", "Euro", "Europe"),
    ("Japan", "Tokyo", "Yen", "Asia"),
    ("Brazil", "Brasilia", "Real", "South_America"),
    ("Canada", "Ottawa", "Canadian_dollar", "North_America"),
    ("Kenya", "Nairobi", "Kenyan_shilling", "Africa"),
    ("India", "New_Delhi", "Rupee", "Asia"),
    ("Norway", "Oslo", "Krone", "Europe"),
]

TOOLS = [
    ("search", "find_current_information", "needs_network"),
    ("calculator", "compute_exact_arithmetic", "offline"),
    ("calendar", "inspect_schedule_conflicts", "private"),
    ("files", "read_local_documents", "private"),
    ("browser", "inspect_web_pages", "needs_network"),
]


def _stable_id(*parts: object) -> str:
    return hashlib.sha256("\n".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _content_json(answer: str, *, key: str = "", field: str = "") -> str:
    payload: dict[str, Any] = {"answer": answer}
    if key:
        payload["key"] = key
    if field:
        payload["field"] = field
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _decoder_tail(answer: str, *, key: str = "", field: str = "") -> str:
    return f"<AK_CONTENT> {_content_json(answer, key=key, field=field)} </AK_CONTENT> <AK_END>"


def _country_tape(rows: list[tuple[str, str, str, str]]) -> str:
    return "\n".join(
        [
            "<schema country fields=name|capital|currency|continent>",
            *("|".join(row) for row in rows),
            "</schema>",
        ]
    )


def _tool_tape(rows: list[tuple[str, str, str]]) -> str:
    return "\n".join(
        [
            "<schema tool fields=name|purpose|privacy>",
            *("|".join(row) for row in rows),
            "</schema>",
        ]
    )


def _prompt(*, tape: str, operator: str, key: str, field: str) -> str:
    return "\n".join(
        [
            "<AK_CHAT> <AK_RESPOND> PocketPal operatorized MDL lookup.",
            "<AK_AGENT_ACTIVE>",
            "Agent name: Knowledge Lookup Compiler",
            "Agent instruction: Use the compressed tape as the only source. Execute the operator and return compact JSON.",
            "Retrieval policy: current_context_only",
            "Tool policy: no_tools",
            "Action policy: respond",
            "</AK_AGENT_ACTIVE>",
            "<AK_TASK_HINT> intent=json task=active_agent_json mdl_operator=true output_schema={answer,key,field}",
            "<AK_COMPRESSED_TAPE>",
            tape,
            "</AK_COMPRESSED_TAPE>",
            f"<AK_OPERATOR> {operator}",
            f"<AK_KEY> {key}",
            f"<AK_FIELD> {field}",
            "<AK_USER> Return the answer JSON only.",
        ]
    )


def _row(
    *,
    source_id: str,
    tape: str,
    operator: str,
    key: str,
    field: str,
    answer: str,
    label: int,
    weight: float,
    negative: str = "",
) -> dict[str, Any]:
    encoder_text = _prompt(tape=tape, operator=operator, key=key, field=field)
    decoder_text = _decoder_tail(answer, key=key, field=field)
    return {
        "action": "respond",
        "answer_confidence_target": 0.99,
        "contrastive_label_id": int(label),
        "decoder_loss_weight": 1.0,
        "decoder_text": decoder_text,
        "decoder_train_prefix": STRUCTURED_JSON_PREFIX,
        "encoder_text": encoder_text,
        "example_id": _stable_id("stage427", source_id, encoder_text, decoder_text),
        "expected_content": answer,
        "intent_label": "json",
        "intent_label_id": INTENT_LABELS["json"],
        "json_decoder_text": json.dumps(
            {
                "action": "respond",
                "content": answer,
                "proposal_metadata": {"field": field, "key": key, "task_type": "active_agent_json"},
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ),
        "negative_decoder_text": _decoder_tail(negative, key=key, field=field) if negative else "",
        "negative_decoder_train_prefix": STRUCTURED_JSON_PREFIX if negative else "",
        "negative_loss_weight": 0.7 if negative else 0.0,
        "needs_verification_target": 0.02,
        "ood_evidence_target": 0.0,
        "ood_query_target": 0.0,
        "query_confidence_target": 0.99,
        "retrieval_doc_text": tape,
        "retrieval_loss_weight": 0.2,
        "retrieval_query_text": f"{operator} {key} {field}",
        "source_id": source_id,
        "source_type": "pocketpal_stage427_operatorized_mdl_json",
        "split": "train",
        "state_text": f"operator={operator}; key={key}; field={field}; answer={answer}",
        "task_type": "active_agent_json",
        "weight": float(weight),
    }


def _knowledge_rows(rng: random.Random, repeats: int, weight: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for repeat in range(repeats):
        sample = rng.sample(COUNTRIES, 3)
        tape = _country_tape(sample)
        for index, (country, capital, currency, continent) in enumerate(sample):
            label = 427000 + repeat * 100 + index
            fields = {
                "capital": capital,
                "currency": currency,
                "continent": continent,
            }
            negatives = {
                "capital": currency,
                "currency": capital,
                "continent": capital,
            }
            for field, answer in fields.items():
                out.append(
                    _row(
                        source_id=f"country_{repeat}_{country}_{field}",
                        tape=tape,
                        operator="lookup_field",
                        key=country,
                        field=field,
                        answer=answer,
                        label=label,
                        weight=weight,
                        negative=negatives.get(field, ""),
                    )
                )
            out.append(
                _row(
                    source_id=f"country_{repeat}_{capital}_reverse",
                    tape=tape,
                    operator="reverse_lookup",
                    key=capital,
                    field="capital_owner",
                    answer=country,
                    label=label,
                    weight=weight,
                )
            )
        euro = sorted(country for country, _capital, currency, _continent in sample if currency == "Euro")
        if euro:
            out.append(
                _row(
                    source_id=f"country_{repeat}_euro_filter",
                    tape=tape,
                    operator="filter_rows",
                    key="currency=Euro",
                    field="countries",
                    answer=", ".join(euro),
                    label=427090 + repeat,
                    weight=weight,
                )
            )

        tool_tape = _tool_tape(TOOLS)
        for index, (name, purpose, privacy) in enumerate(TOOLS):
            label = 428000 + repeat * 10 + index
            out.extend(
                [
                    _row(
                        source_id=f"tool_{repeat}_{name}_purpose",
                        tape=tool_tape,
                        operator="lookup_field",
                        key=name,
                        field="purpose",
                        answer=purpose,
                        label=label,
                        weight=weight,
                        negative=privacy,
                    ),
                    _row(
                        source_id=f"tool_{repeat}_{name}_privacy",
                        tape=tool_tape,
                        operator="lookup_field",
                        key=name,
                        field="privacy",
                        answer=privacy,
                        label=label,
                        weight=weight,
                        negative=purpose,
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
    copied["example_id"] = _stable_id("stage427_anchor", index, copied.get("example_id"), copied.get("encoder_text"))
    copied["source_id"] = f"{copied.get('source_id', 'row')}_stage427_anchor_{index:05d}"
    copied["source_type"] = f"stage427_anchor_{copied.get('source_type', 'unknown')}"
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
    parser.add_argument("--seed", type=int, default=427)
    parser.add_argument("--repeats", type=int, default=320)
    parser.add_argument("--knowledge-weight", type=float, default=14.0)
    parser.add_argument("--anchor-sample", type=int, default=12000)
    parser.add_argument("--anchor-weight-cap", type=float, default=7.0)
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
            copied["example_id"] = _stable_id("stage427_eval", index, copied.get("example_id"))
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
        "artifact_kind": "agentkernel_lite_encdec_stage427_operatorized_mdl_json",
        "dataset_format": "jsonl",
        "eval_dataset_path": str(eval_path),
        "eval_examples": len(eval_rows),
        "intent_labels": INTENT_LABELS,
        "manifest_path": str(manifest_path),
        "objective": "pocketpal_stage427_operatorized_mdl_json",
        "structured_json_prefix": STRUCTURED_JSON_PREFIX,
        "train_dataset_path": str(train_path),
        "train_examples": len(train_rows),
        "total_examples": len(train_rows) + len(eval_rows),
        "training_principle": "operatorized MDL lookup: fixed structured JSON prefix is treated as interface, while loss focuses on answer JSON content after decoder_train_prefix",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
