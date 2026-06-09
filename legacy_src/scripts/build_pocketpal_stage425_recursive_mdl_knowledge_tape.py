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


def _stable_id(*parts: object) -> str:
    return hashlib.sha256("\n".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _compact(text: object, *, limit: int = 1600) -> str:
    if text is None:
        return ""
    if isinstance(text, (dict, list)):
        value = json.dumps(text, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    else:
        value = str(text)
    return " ".join(value.replace("\r\n", "\n").replace("\r", "\n").split())[:limit].rstrip()


def _decision(content: str, task_type: str) -> str:
    return (
        f"<AK_STRUCTURED> <AK_ACTION_RESPOND> <AK_TASK_TYPE> {task_type} "
        f"<AK_CONTENT> {_compact(content, limit=1400)} </AK_CONTENT> <AK_END>"
    )


def _json_decision(content: str, task_type: str) -> str:
    return json.dumps(
        {"action": "respond", "content": _compact(content, limit=1400), "proposal_metadata": {"task_type": task_type}},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _prompt(*, tape: str, question: str, task_type: str, intent: str) -> str:
    return "\n".join(
        [
            "<AK_CHAT> <AK_RESPOND> PocketPal recursive-MDL knowledge tape example.",
            "<AK_AGENT_ACTIVE>",
            "Agent name: Knowledge Compiler",
            "Agent instruction: Answer only from the compressed knowledge tape. Use schemas, rules, tables, exceptions, and residual facts before surface wording.",
            "Retrieval policy: current_context_only",
            "Tool policy: no_tools",
            "Action policy: respond_or_ask",
            "</AK_AGENT_ACTIVE>",
            f"<AK_TASK_HINT> intent={intent} task={task_type} compressed_knowledge_tape=true residual_mdl=true",
            "<AK_CONTEXT> Saved user data: none",
            "<AK_COMPRESSED_KNOWLEDGE_TAPE>",
            tape,
            "</AK_COMPRESSED_KNOWLEDGE_TAPE>",
            f"<AK_USER> {question}",
            "Return AK structured tokens for the active agent decision.",
        ]
    )


def _row(
    *,
    source_id: str,
    tape: str,
    question: str,
    answer: str,
    task_type: str,
    intent: str,
    contrastive_label_id: int,
    weight: float,
    negative: str = "",
) -> dict[str, Any]:
    encoder_text = _prompt(tape=tape, question=question, task_type=task_type, intent=intent)
    decoder_text = _decision(answer, task_type)
    return {
        "action": "respond",
        "answer_confidence_target": 0.96,
        "contrastive_label_id": int(contrastive_label_id),
        "decoder_loss_weight": 1.0,
        "decoder_text": decoder_text,
        "encoder_text": encoder_text,
        "example_id": _stable_id("stage425", source_id, encoder_text, decoder_text),
        "expected_content": _compact(answer, limit=1400),
        "intent_label": intent,
        "intent_label_id": INTENT_LABELS[intent],
        "json_decoder_text": _json_decision(answer, task_type),
        "negative_decoder_text": negative,
        "negative_loss_weight": 1.0 if negative else 0.0,
        "needs_verification_target": 0.1,
        "ood_evidence_target": 0.0,
        "ood_query_target": 0.0,
        "query_confidence_target": 0.96,
        "retrieval_doc_text": tape,
        "retrieval_loss_weight": 0.4,
        "retrieval_query_text": question,
        "source_id": source_id,
        "source_type": "pocketpal_stage425_recursive_mdl_knowledge_tape",
        "split": "train",
        "state_text": f"tape={_compact(tape, limit=900)} answer={_compact(answer, limit=500)}",
        "task_type": task_type,
        "weight": float(weight),
    }


def _geo_family() -> tuple[str, list[tuple[str, str, str, str, str]]]:
    rows = [
        ("France", "Paris", "Euro", "Europe", "Indo-European"),
        ("Germany", "Berlin", "Euro", "Europe", "Indo-European"),
        ("Japan", "Tokyo", "Yen", "Asia", "Japonic"),
        ("Brazil", "Brasilia", "Real", "South_America", "Indo-European"),
        ("Canada", "Ottawa", "Canadian_dollar", "North_America", "Indo-European"),
    ]
    tape = "\n".join(
        [
            "<domain:geo>",
            "<schema:country fields=name|capital|currency|continent|language_family>",
            *("|".join(row) for row in rows),
            "</schema>",
            "<rule id=euro_zone> listed countries with continent=Europe use currency=Euro unless exception.</rule>",
            "<residual> Japan uses Yen. Brazil uses Real. Canada uses Canadian_dollar. </residual>",
        ]
    )
    return tape, rows


def _project_family() -> tuple[str, list[tuple[str, str, str, str, str]]]:
    rows = [
        ("Alpha", "Avery", "client deck", "Friday", "design feedback"),
        ("Beta", "Blake", "budget sheet", "Tuesday", "finance review"),
        ("Gamma", "Casey", "release notes", "tomorrow", "QA signoff"),
        ("Delta", "Devon", "invoice packet", "Thursday", "vendor confirmation"),
    ]
    tape = "\n".join(
        [
            "<domain:project>",
            "<schema:launch_item fields=project|owner|artifact|due|blocker>",
            *("|".join(row) for row in rows),
            "</schema>",
            "<rule id=launch_ready> a project is launch-ready only after its artifact is delivered and blocker is resolved.</rule>",
            "<program id=next_action> ask owner to deliver artifact by due date; then resolve blocker.</program>",
        ]
    )
    return tape, rows


def _materials_family() -> tuple[str, list[tuple[str, str, str, str]]]:
    rows = [
        ("glass", "fragile", "falls", "breaks"),
        ("metal", "durable", "falls", "does_not_break"),
        ("rubber", "elastic", "falls", "bounces"),
        ("ceramic", "fragile", "falls", "breaks"),
    ]
    tape = "\n".join(
        [
            "<domain:counterfactual_materials>",
            "<schema:material fields=name|property|event|outcome>",
            *("|".join(row) for row in rows),
            "</schema>",
            "<rule id=fragile_fall> if property=fragile and event=falls then outcome=breaks.</rule>",
            "<exception> rubber bounces after falling. metal does_not_break after falling. </exception>",
        ]
    )
    return tape, rows


def _sequence_family() -> str:
    return "\n".join(
        [
            "<domain:program_sequence>",
            "<program id=square> f(n)=n*n for positive integers.</program>",
            "<table:n|f(n)> 1|1 2|4 3|9 4|16 5|25 6|36 </table>",
            "<rule id=derive> unseen values should be computed from the program, not memorized from the table.</rule>",
        ]
    )


def _knowledge_rows(weight: float, repeats: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    label = 425000
    geo_tape, geo = _geo_family()
    project_tape, projects = _project_family()
    material_tape, materials = _materials_family()
    seq_tape = _sequence_family()

    for repeat in range(repeats):
        for country, capital, currency, continent, family in geo:
            label += 1
            rows.extend(
                [
                    _row(
                        source_id=f"geo_{repeat}_{country}_capital",
                        tape=geo_tape,
                        question=f"What is the capital of {country}?",
                        answer=capital,
                        task_type="active_agent_summary",
                        intent="summary",
                        contrastive_label_id=label,
                        weight=weight,
                        negative=f"{country} has capital {currency}.",
                    ),
                    _row(
                        source_id=f"geo_{repeat}_{country}_json",
                        tape=geo_tape,
                        question=f"Return compact JSON for {country}.",
                        answer=json.dumps(
                            {
                                "country": country,
                                "capital": capital,
                                "currency": currency,
                                "continent": continent,
                                "language_family": family,
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        task_type="active_agent_json",
                        intent="json",
                        contrastive_label_id=label,
                        weight=weight,
                    ),
                    _row(
                        source_id=f"geo_{repeat}_{capital}_reverse",
                        tape=geo_tape,
                        question=f"Which listed country has {capital} as its capital?",
                        answer=country,
                        task_type="active_agent_extraction",
                        intent="extraction",
                        contrastive_label_id=label,
                        weight=weight,
                    ),
                ]
            )
        euro = ", ".join(country for country, _capital, currency, _continent, _family in geo if currency == "Euro")
        rows.append(
            _row(
                source_id=f"geo_{repeat}_euro_rule",
                tape=geo_tape,
                question="Which listed countries use the Euro, and why?",
                answer=f"{euro}. They are the listed European countries covered by the euro_zone rule.",
                task_type="active_agent_summary",
                intent="summary",
                contrastive_label_id=label + 1000,
                weight=weight,
            )
        )

        for project, owner, artifact, due, blocker in projects:
            label += 1
            rows.extend(
                [
                    _row(
                        source_id=f"project_{repeat}_{project}_plan",
                        tape=project_tape,
                        question=f"Make the next-action plan for project {project}.",
                        answer=f"1. Ask {owner} to deliver the {artifact} by {due}. 2. Resolve {blocker}. 3. Confirm launch readiness after both are done.",
                        task_type="active_agent_plan",
                        intent="plan",
                        contrastive_label_id=label,
                        weight=weight,
                    ),
                    _row(
                        source_id=f"project_{repeat}_{project}_extract",
                        tape=project_tape,
                        question=f"Extract owner, artifact, due date, and blocker for {project}.",
                        answer=f"- Owner: {owner}\n- Artifact: {artifact}\n- Due: {due}\n- Blocker: {blocker}",
                        task_type="active_agent_extraction",
                        intent="extraction",
                        contrastive_label_id=label,
                        weight=weight,
                    ),
                ]
            )

        for material, prop, event, outcome in materials:
            label += 1
            rows.append(
                _row(
                    source_id=f"material_{repeat}_{material}",
                    tape=material_tape,
                    question=f"The {material} object {event}. What happens?",
                    answer=outcome.replace("_", " "),
                    task_type="active_agent_summary",
                    intent="summary",
                    contrastive_label_id=label,
                    weight=weight,
                    negative="breaks" if outcome != "breaks" else "does not break",
                )
            )

        for n in (7, 8, 9, 10):
            rows.append(
                _row(
                    source_id=f"sequence_{repeat}_{n}",
                    tape=seq_tape,
                    question=f"Use the program to compute f({n}).",
                    answer=str(n * n),
                    task_type="active_agent_summary",
                    intent="summary",
                    contrastive_label_id=label + n,
                    weight=weight,
                )
            )
    return rows


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
    copied["example_id"] = _stable_id("stage425_anchor", index, copied.get("example_id"), copied.get("encoder_text"))
    copied["source_id"] = f"{copied.get('source_id', 'row')}_stage425_anchor_{index:05d}"
    copied["source_type"] = f"stage425_anchor_{copied.get('source_type', 'unknown')}"
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
    parser.add_argument("--seed", type=int, default=425)
    parser.add_argument("--repeats", type=int, default=160)
    parser.add_argument("--knowledge-weight", type=float, default=9.0)
    parser.add_argument("--anchor-sample", type=int, default=18000)
    parser.add_argument("--anchor-weight-cap", type=float, default=10.0)
    parser.add_argument("--eval-ratio", type=float, default=0.04)
    args = parser.parse_args()

    rng = random.Random(int(args.seed))
    rows = _knowledge_rows(float(args.knowledge_weight), int(args.repeats))
    anchor_manifest = json.loads(Path(args.anchor_manifest).read_text(encoding="utf-8"))
    anchors = list(_iter_jsonl(Path(anchor_manifest["train_dataset_path"])))
    rng.shuffle(anchors)
    for index, row in enumerate(anchors[: max(0, int(args.anchor_sample))]):
        rows.append(_copy_anchor(row, index=index, weight_cap=float(args.anchor_weight_cap)))
    rng.shuffle(rows)

    eval_count = max(128, int(len(rows) * float(args.eval_ratio)))
    eval_rows = []
    train_rows = []
    for index, row in enumerate(rows):
        copied = deepcopy(row)
        if index < eval_count:
            copied["example_id"] = _stable_id("stage425_eval", index, copied.get("example_id"))
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
        "artifact_kind": "agentkernel_lite_encdec_stage425_recursive_mdl_knowledge_tape",
        "contrastive_label": "same schema/table/rule state across forward, reverse, JSON, negative, and compositional probes",
        "dataset_format": "jsonl",
        "eval_dataset_path": str(eval_path),
        "eval_examples": len(eval_rows),
        "intent_labels": INTENT_LABELS,
        "manifest_path": str(manifest_path),
        "objective": "pocketpal_stage425_recursive_mdl_knowledge_tape",
        "train_dataset_path": str(train_path),
        "train_examples": len(train_rows),
        "total_examples": len(train_rows) + len(eval_rows),
        "training_principle": "schemas + rules + programs + residual facts + probes; train decoder on verified residual access paths instead of raw documents",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
