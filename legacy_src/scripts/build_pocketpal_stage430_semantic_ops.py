#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any


FIELDS = ["capital", "currency", "continent", "owner", "status", "priority", "tool", "risk"]


def _stable_id(*parts: object) -> str:
    return hashlib.sha256("\n".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def _decoder(answer: str) -> str:
    return f"<AK_STRUCTURED> <AK_ACTION_RESPOND> <AK_TASK_TYPE> active_agent_json <AK_CONTENT> {answer} </AK_CONTENT> <AK_END>"


def _row(
    *,
    index: int,
    op: str,
    query: str,
    card: str,
    answer: str,
    support: str,
    split: str = "train",
    operation_token_prefix: bool = False,
) -> dict[str, Any]:
    op_token = f"<AK_OP_{op.upper()}>"
    model_query = f"{op_token} {query}" if operation_token_prefix else query
    model_card = f"{op_token} {card}" if operation_token_prefix else card
    encoder_text = "\n".join(
        [
            "<AK_CHAT> <AK_RESPOND> PocketPal semantic compression operation.",
            "<AK_AGENT_ACTIVE>",
            "Agent name: Semantic Codec Operator",
            "Agent instruction: answer by using the compressed card, schema, rule, exception, or composition path.",
            "Tool policy: no_tools",
            "</AK_AGENT_ACTIVE>",
            f"<AK_QUERY> {model_query}",
            f"<AK_SUPPORT> {support}",
            "<AK_USER> Return only the verified semantic answer.",
        ]
    )
    return {
        "action": "respond",
        "answer_confidence_target": 0.99,
        "contrastive_label_id": 430000 + index,
        "decoder_loss_weight": 1.0,
        "decoder_text": _decoder(answer),
        "encoder_text": encoder_text,
        "example_id": _stable_id("stage430", op, query, answer, index),
        "expected_content": answer,
        "intent_label": "json",
        "intent_label_id": 13,
        "json_decoder_text": json.dumps({"action": "respond", "content": answer}, ensure_ascii=True, separators=(",", ":")),
        "negative_decoder_text": "",
        "negative_loss_weight": 0.0,
        "operation": op,
        "operation_token": op_token if operation_token_prefix else "",
        "query_confidence_target": 0.99,
        "retrieval_doc_text": model_card,
        "retrieval_loss_weight": 1.0,
        "retrieval_query_text": model_query,
        "source_id": f"stage430_{op}_{index:06d}",
        "source_type": "pocketpal_stage430_semantic_ops",
        "split": split,
        "state_text": model_card,
        "task_type": "active_agent_json",
        "weight": 1.0,
    }


def _membership_answer_card(op: str, member: bool) -> str:
    label = "true" if member else "false"
    return f"membership_answer_card op={op} member={label}"


def _build_rows(
    *,
    domains: int,
    entities_per_domain: int,
    seed: int,
    reverse_lookup_mode: str,
    operation_token_prefix: bool,
    reverse_lookup_key_prefix: bool,
    compact_reverse_set_cards: bool,
    direct_fact_key_prefix: bool,
    false_claim_key_prefix: bool,
    compact_false_claim_cards: bool,
    semantic_key_prefix: bool,
    extended_set_ops: bool,
    compact_set_op_cards: bool,
    compact_direct_fact_cards: bool,
    direct_fact_selected_prefix: bool,
    factorized_direct_fact_cards: bool,
    compact_rule_cards: bool,
    rule_selected_prefix: bool,
    rule_key_prefix: bool,
    composition_key_prefix: bool,
    count_answer_prefix: bool,
    membership_answer_targets: bool,
    compact_membership_cards: bool,
    anchored_compact_membership_cards: bool,
    rule_set_ops: bool,
    rule_case_intersection_ops: bool,
    derived_set_ops: bool,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    index = 0
    for domain_idx in range(domains):
        domain = f"domain_{domain_idx:03d}"
        default_currency = f"currency_default_{domain_idx % 7:02d}"
        default_risk = f"risk_default_{domain_idx % 5:02d}"
        region_by_owner = {f"owner_{domain_idx:03d}_{i:03d}": f"region_{domain_idx % 9:02d}_{i % 4:02d}" for i in range(entities_per_domain)}
        entities: list[dict[str, str]] = []
        for entity_idx in range(entities_per_domain):
            entity = f"entity_{domain_idx:03d}_{entity_idx:03d}"
            owner = f"owner_{domain_idx:03d}_{entity_idx:03d}"
            values = {
                "capital": f"capital_{domain_idx:03d}_{entity_idx:03d}",
                "currency": default_currency if entity_idx % 5 else f"currency_exception_{domain_idx:03d}_{entity_idx:03d}",
                "continent": f"continent_{domain_idx % 6:02d}",
                "owner": owner,
                "status": f"status_{(domain_idx + entity_idx) % 8:02d}",
                "priority": f"priority_{entity_idx % 4:02d}",
                "tool": f"tool_{domain_idx:03d}_{entity_idx % 6:02d}",
                "risk": default_risk if entity_idx % 4 else f"risk_exception_{domain_idx:03d}_{entity_idx:03d}",
            }
            entities.append({"entity": entity, **values})

        schema_card = (
            f"schema_card domain={domain} entity_fields={','.join(FIELDS)} "
            f"rule currency_default={default_currency} unless currency_exception "
            f"rule risk_default={default_risk} unless risk_exception"
        )
        reverse_groups: dict[tuple[str, str], list[tuple[str, str]]] = {}
        for item in entities:
            entity = item["entity"]
            fact_card = "answer_card domain={domain} entity={entity} ".format(domain=domain, entity=entity)
            fact_card += " ".join(f"{field}={item[field]}" for field in FIELDS)
            if factorized_direct_fact_cards:
                context_query = f"op=entity_context domain={domain} entity={entity}"
                context_card = f"entity_context_card domain={domain} entity={entity} " + " ".join(
                    f"{field}={item[field]}" for field in FIELDS
                )
                rows.append(
                    _row(
                        index=index,
                        op="entity_context",
                        query=context_query,
                        card=context_card,
                        answer=entity,
                        support=schema_card,
                        operation_token_prefix=operation_token_prefix,
                    )
                )
                index += 1
            for field in FIELDS:
                answer = item[field]
                reverse_groups.setdefault((field, answer), []).append((entity, fact_card))
                direct_query = f"op=direct_fact domain={domain} entity={entity} field={field}"
                direct_card = f"{fact_card} answer={answer}"
                if compact_direct_fact_cards or factorized_direct_fact_cards:
                    direct_card = (
                        f"direct_fact_card domain={domain} entity={entity} field={field} "
                        f"answer={answer}"
                    )
                elif direct_fact_selected_prefix:
                    direct_card = (
                        f"selected_field={field} selected_answer={answer} "
                        f"{direct_card}"
                    )
                if direct_fact_key_prefix or semantic_key_prefix:
                    direct_key_name = "semantic_key" if semantic_key_prefix else "fact_key"
                    direct_key = f"{direct_key_name}=direct_fact|{domain}|{entity}|{field}"
                    direct_query = f"op=direct_fact {direct_key} domain={domain} entity={entity} field={field}"
                    direct_card = f"{direct_key} {direct_card}"
                rows.append(
                    _row(
                        index=index,
                        op="direct_fact",
                        query=direct_query,
                        card=direct_card,
                        answer=answer,
                        support=schema_card,
                        operation_token_prefix=operation_token_prefix,
                    )
                )
                index += 1
                if reverse_lookup_mode == "single":
                    reverse_key = f"lookup_key={domain}|{field}|{answer}"
                    reverse_query = f"op=reverse_lookup domain={domain} field={field} answer={answer}"
                    reverse_card = f"{fact_card} reverse field={field} answer={answer} entity={entity}"
                    if reverse_lookup_key_prefix or semantic_key_prefix:
                        reverse_query = f"op=reverse_lookup {reverse_key} domain={domain} field={field} answer={answer}"
                        reverse_card = f"{reverse_key} {reverse_card}"
                    rows.append(
                        _row(
                            index=index,
                            op="reverse_lookup",
                            query=reverse_query,
                            card=reverse_card,
                            answer=entity,
                            support=schema_card,
                            operation_token_prefix=operation_token_prefix,
                        )
                    )
                    index += 1

            claimed_field = rng.choice(FIELDS)
            wrong_answer = f"wrong_{domain_idx:03d}_{entity_idx:03d}_{claimed_field}"
            false_query = f"op=false_claim domain={domain} entity={entity} field={claimed_field} claimed={wrong_answer}"
            false_card = f"{fact_card} claimed={wrong_answer} correct={item[claimed_field]}"
            if compact_false_claim_cards:
                false_card = (
                    f"false_claim_card domain={domain} entity={entity} field={claimed_field} "
                    f"claimed={wrong_answer} correct={item[claimed_field]}"
                )
            if false_claim_key_prefix or semantic_key_prefix:
                false_key_name = "semantic_key" if semantic_key_prefix else "false_key"
                false_key = f"{false_key_name}=false_claim|{domain}|{entity}|{claimed_field}|{wrong_answer}"
                false_query = f"op=false_claim {false_key} domain={domain} entity={entity} field={claimed_field} claimed={wrong_answer}"
                false_card = f"{false_key} {false_card}"
            rows.append(
                _row(
                    index=index,
                    op="false_claim",
                    query=false_query,
                    card=false_card,
                    answer=f"false_correct_{item[claimed_field]}",
                    support=schema_card,
                    operation_token_prefix=operation_token_prefix,
                )
            )
            index += 1

            for field, default_value in (("currency", default_currency), ("risk", default_risk)):
                actual = item[field]
                op = "exception" if actual != default_value else "rule_default"
                rule_query = f"op={op} domain={domain} entity={entity} field={field}"
                rule_card = f"{schema_card} entity={entity} field={field} actual={actual}"
                if compact_rule_cards:
                    rule_card = (
                        f"rule_value_card domain={domain} entity={entity} field={field} "
                        f"default={default_value} actual={actual} rule_type={op}"
                    )
                elif rule_selected_prefix:
                    rule_card = (
                        f"selected_rule_field={field} selected_default={default_value} "
                        f"selected_actual={actual} rule_type={op} {rule_card}"
                    )
                if rule_key_prefix:
                    rule_key = f"rule_key={op}|{domain}|{entity}|{field}"
                    rule_query = f"op={op} {rule_key} domain={domain} entity={entity} field={field}"
                    rule_card = f"{rule_key} {rule_card}"
                if semantic_key_prefix:
                    rule_key = f"semantic_key={op}|{domain}|{entity}|{field}"
                    rule_query = f"op={op} {rule_key} domain={domain} entity={entity} field={field}"
                    rule_card = f"{rule_key} {rule_card}"
                rows.append(
                    _row(
                        index=index,
                        op=op,
                        query=rule_query,
                        card=rule_card,
                        answer=actual,
                        support=f"default={default_value} actual={actual}",
                        operation_token_prefix=operation_token_prefix,
                    )
                )
                index += 1

            owner = item["owner"]
            region = region_by_owner[owner]
            two_hop_query = f"op=two_hop_owner_region domain={domain} entity={entity}"
            two_hop_card = f"composition_card domain={domain} entity={entity} owner={owner} owner_region={region}"
            if composition_key_prefix:
                composition_key = f"composition_key=two_hop_owner_region|{domain}|{entity}"
                two_hop_query = f"op=two_hop_owner_region {composition_key} domain={domain} entity={entity}"
                two_hop_card = f"{composition_key} {two_hop_card}"
            if semantic_key_prefix:
                two_hop_key = f"semantic_key=two_hop_owner_region|{domain}|{entity}"
                two_hop_query = f"op=two_hop_owner_region {two_hop_key} domain={domain} entity={entity}"
                two_hop_card = f"{two_hop_key} {two_hop_card}"
            rows.append(
                _row(
                    index=index,
                    op="two_hop_owner_region",
                    query=two_hop_query,
                    card=two_hop_card,
                    answer=region,
                    support=f"entity_owner={owner}; owner_region={region}",
                    operation_token_prefix=operation_token_prefix,
                )
            )
            index += 1

        if rule_set_ops:
            for field, default_value in (("currency", default_currency), ("risk", default_risk)):
                cases = {
                    "default": sorted(item["entity"] for item in entities if item[field] == default_value),
                    "exception": sorted(item["entity"] for item in entities if item[field] != default_value),
                }
                for case, case_entities in cases.items():
                    if not case_entities:
                        continue
                    entity_set = "|".join(case_entities)
                    case_key = f"rule_case_key={domain}|{field}|{case}"
                    count_card = (
                        f"rule_case_count_card {case_key} domain={domain} field={field} "
                        f"case={case} default={default_value} count={len(case_entities)}"
                    )
                    if count_answer_prefix:
                        count_card = f"count_answer={len(case_entities)} {count_card}"
                    rows.append(
                        _row(
                            index=index,
                            op="rule_case_count",
                            query=f"op=rule_case_count {case_key} domain={domain} field={field} case={case}",
                            card=count_card,
                            answer=str(len(case_entities)),
                            support=f"{schema_card} count entities matching the rule case",
                            operation_token_prefix=operation_token_prefix,
                        )
                    )
                    index += 1

                    true_member = case_entities[0]
                    true_key = f"{case_key}|member|{true_member}"
                    true_card = (
                        f"rule_case_member_card {true_key} domain={domain} field={field} "
                        f"case={case} entity={true_member} member=true count={len(case_entities)}"
                    )
                    if compact_membership_cards:
                        true_card = f"rule_case_member_card {true_key} member=true count={len(case_entities)}"
                    if anchored_compact_membership_cards:
                        true_card = (
                            f"rule_case_member_card {true_key} domain={domain} field={field} "
                            f"case={case} entity={true_member} member=true count={len(case_entities)}"
                        )
                    rows.append(
                        _row(
                            index=index,
                            op="rule_case_member",
                            query=f"op=rule_case_member {true_key} domain={domain} field={field} case={case} entity={true_member}",
                            card=_membership_answer_card("rule_case_member", True) if membership_answer_targets else true_card,
                            answer="member_true",
                            support=f"{schema_card} test whether entity belongs to the rule case",
                            operation_token_prefix=operation_token_prefix,
                        )
                    )
                    index += 1

                    false_candidates = [item["entity"] for item in entities if item["entity"] not in set(case_entities)]
                    if false_candidates:
                        false_member = false_candidates[0]
                        false_key = f"{case_key}|member|{false_member}"
                        false_card = (
                            f"rule_case_member_card {false_key} domain={domain} field={field} "
                            f"case={case} entity={false_member} member=false count={len(case_entities)}"
                        )
                        if compact_membership_cards:
                            false_card = f"rule_case_member_card {false_key} member=false count={len(case_entities)}"
                        if anchored_compact_membership_cards:
                            false_card = (
                                f"rule_case_member_card {false_key} domain={domain} field={field} "
                                f"case={case} entity={false_member} member=false count={len(case_entities)}"
                            )
                        rows.append(
                            _row(
                                index=index,
                                op="rule_case_member",
                                query=f"op=rule_case_member {false_key} domain={domain} field={field} case={case} entity={false_member}",
                                card=_membership_answer_card("rule_case_member", False) if membership_answer_targets else false_card,
                                answer="member_false",
                                support=f"{schema_card} test whether entity is outside the rule case",
                                operation_token_prefix=operation_token_prefix,
                            )
                        )
                        index += 1

        if rule_case_intersection_ops:
            entity_by_name = {item["entity"]: item for item in entities}
            for rule_field, default_value in (("currency", default_currency), ("risk", default_risk)):
                cases = {
                    "default": sorted(item["entity"] for item in entities if item[rule_field] == default_value),
                    "exception": sorted(item["entity"] for item in entities if item[rule_field] != default_value),
                }
                for case, case_entities in cases.items():
                    if not case_entities:
                        continue
                    case_set = set(case_entities)
                    for filter_field in ("continent", "priority", "status", "tool"):
                        answer_values = sorted({item[filter_field] for item in entities})
                        for filter_answer in answer_values:
                            intersection = sorted(
                                entity for entity in case_set if entity_by_name[entity][filter_field] == filter_answer
                            )
                            if not intersection:
                                continue
                            count = len(intersection)
                            base_key = (
                                f"rule_case_intersection_key={domain}|{rule_field}|{case}"
                                f"&{filter_field}|{filter_answer}"
                            )
                            count_query = (
                                f"op=rule_case_intersection_count {base_key}|count domain={domain} "
                                f"rule_field={rule_field} case={case} filter_field={filter_field} "
                                f"filter_answer={filter_answer}"
                            )
                            count_card = (
                                f"rule_case_intersection_count_card {base_key}|count domain={domain} "
                                f"rule_field={rule_field} case={case} default={default_value} "
                                f"filter_field={filter_field} filter_answer={filter_answer} count={count}"
                            )
                            if count_answer_prefix:
                                count_card = f"count_answer={count} {count_card}"
                            rows.append(
                                _row(
                                    index=index,
                                    op="rule_case_intersection_count",
                                    query=count_query,
                                    card=count_card,
                                    answer=str(count),
                                    support=f"{schema_card} count entities matching the rule case and field constraint",
                                    operation_token_prefix=operation_token_prefix,
                                )
                            )
                            index += 1

                            true_member = intersection[0]
                            true_key = f"{base_key}|member|{true_member}"
                            true_card = (
                                f"rule_case_intersection_member_card {true_key} domain={domain} "
                                f"rule_field={rule_field} case={case} default={default_value} "
                                f"filter_field={filter_field} filter_answer={filter_answer} "
                                f"entity={true_member} member=true count={count}"
                            )
                            if compact_membership_cards:
                                true_card = f"rule_case_intersection_member_card {true_key} member=true count={count}"
                            if anchored_compact_membership_cards:
                                true_card = (
                                    f"rule_case_intersection_member_card {true_key} domain={domain} "
                                    f"rule_field={rule_field} case={case} default={default_value} "
                                    f"filter_field={filter_field} filter_answer={filter_answer} "
                                    f"entity={true_member} member=true count={count}"
                                )
                            rows.append(
                                _row(
                                    index=index,
                                    op="rule_case_intersection_member",
                                    query=(
                                        f"op=rule_case_intersection_member {true_key} domain={domain} "
                                        f"rule_field={rule_field} case={case} filter_field={filter_field} "
                                        f"filter_answer={filter_answer} entity={true_member}"
                                    ),
                                    card=_membership_answer_card("rule_case_intersection_member", True) if membership_answer_targets else true_card,
                                    answer="member_true",
                                    support=f"{schema_card} test entity membership in the rule case and field constraint",
                                    operation_token_prefix=operation_token_prefix,
                                )
                            )
                            index += 1

                            false_candidates = [item["entity"] for item in entities if item["entity"] not in set(intersection)]
                            if false_candidates:
                                false_member = false_candidates[0]
                                false_key = f"{base_key}|member|{false_member}"
                                false_card = (
                                    f"rule_case_intersection_member_card {false_key} domain={domain} "
                                    f"rule_field={rule_field} case={case} default={default_value} "
                                    f"filter_field={filter_field} filter_answer={filter_answer} "
                                    f"entity={false_member} member=false count={count}"
                                )
                                if compact_membership_cards:
                                    false_card = f"rule_case_intersection_member_card {false_key} member=false count={count}"
                                if anchored_compact_membership_cards:
                                    false_card = (
                                        f"rule_case_intersection_member_card {false_key} domain={domain} "
                                        f"rule_field={rule_field} case={case} default={default_value} "
                                        f"filter_field={filter_field} filter_answer={filter_answer} "
                                        f"entity={false_member} member=false count={count}"
                                    )
                                rows.append(
                                    _row(
                                        index=index,
                                        op="rule_case_intersection_member",
                                        query=(
                                            f"op=rule_case_intersection_member {false_key} domain={domain} "
                                            f"rule_field={rule_field} case={case} filter_field={filter_field} "
                                            f"filter_answer={filter_answer} entity={false_member}"
                                        ),
                                        card=_membership_answer_card("rule_case_intersection_member", False) if membership_answer_targets else false_card,
                                        answer="member_false",
                                        support=f"{schema_card} test entity exclusion from the rule case and field constraint",
                                        operation_token_prefix=operation_token_prefix,
                                    )
                                )
                                index += 1

        if reverse_lookup_mode == "set":
            for (field, answer), matches in sorted(reverse_groups.items()):
                entities_for_value = sorted(entity for entity, _fact_card in matches)
                entity_set = "|".join(entities_for_value)
                reverse_key = f"lookup_key={domain}|{field}|{answer}"
                reverse_query = f"op=reverse_lookup_set domain={domain} field={field} answer={answer}"
                card = (
                    f"reverse_set_card domain={domain} field={field} answer={answer} "
                    f"entities={entity_set} count={len(entities_for_value)}"
                )
                if reverse_lookup_key_prefix or semantic_key_prefix:
                    reverse_query = f"op=reverse_lookup_set {reverse_key} domain={domain} field={field} answer={answer}"
                    card = f"reverse_set_card {reverse_key} domain={domain} field={field} answer={answer} entities={entity_set} count={len(entities_for_value)}"
                if compact_reverse_set_cards:
                    card = (
                        f"reverse_set_card {reverse_key} domain={domain} field={field} "
                        f"answer={answer} count={len(entities_for_value)}"
                    )
                rows.append(
                    _row(
                        index=index,
                        op="reverse_lookup_set",
                        query=reverse_query,
                        card=card,
                        answer=entity_set,
                        support=f"{schema_card} reverse lookup is set-valued when multiple entities share a field value",
                        operation_token_prefix=operation_token_prefix,
                    )
                )
                index += 1
                if extended_set_ops:
                    count_key = f"lookup_key={domain}|{field}|{answer}|count"
                    count_card = (
                        f"set_count_card {count_key} domain={domain} field={field} "
                        f"answer={answer} count={len(entities_for_value)} entities={entity_set}"
                    )
                    if compact_set_op_cards:
                        count_card = (
                            f"set_count_card {count_key} domain={domain} field={field} "
                            f"answer={answer} count={len(entities_for_value)}"
                        )
                    if count_answer_prefix:
                        count_card = f"count_answer={len(entities_for_value)} {count_card}"
                    rows.append(
                        _row(
                            index=index,
                            op="set_count",
                            query=f"op=set_count {count_key} domain={domain} field={field} answer={answer}",
                            card=count_card,
                            answer=str(len(entities_for_value)),
                            support=f"{schema_card} count members of the reverse lookup set",
                            operation_token_prefix=operation_token_prefix,
                        )
                    )
                    index += 1

                    true_member = entities_for_value[0]
                    true_key = f"lookup_key={domain}|{field}|{answer}|member|{true_member}"
                    true_card = (
                        f"set_member_card {true_key} domain={domain} field={field} answer={answer} "
                        f"entity={true_member} member=true entities={entity_set}"
                    )
                    if compact_set_op_cards:
                        true_card = (
                            f"set_member_card {true_key} domain={domain} field={field} answer={answer} "
                            f"entity={true_member} member=true count={len(entities_for_value)}"
                        )
                    if compact_membership_cards:
                        true_card = f"set_member_card {true_key} member=true count={len(entities_for_value)}"
                    if anchored_compact_membership_cards:
                        true_card = (
                            f"set_member_card {true_key} domain={domain} field={field} answer={answer} "
                            f"entity={true_member} member=true count={len(entities_for_value)}"
                        )
                    rows.append(
                        _row(
                            index=index,
                            op="set_member",
                            query=f"op=set_member {true_key} domain={domain} field={field} answer={answer} entity={true_member}",
                            card=_membership_answer_card("set_member", True) if membership_answer_targets else true_card,
                            answer="member_true",
                            support=f"{schema_card} test whether the entity is in the reverse lookup set",
                            operation_token_prefix=operation_token_prefix,
                        )
                    )
                    index += 1

                    candidate_indices = {int(entity.rsplit("_", 1)[1]) for entity in entities_for_value}
                    false_indices = [i for i in range(entities_per_domain) if i not in candidate_indices]
                    if false_indices:
                        false_member = f"entity_{domain_idx:03d}_{false_indices[0]:03d}"
                        false_key = f"lookup_key={domain}|{field}|{answer}|member|{false_member}"
                        false_card = (
                            f"set_member_card {false_key} domain={domain} field={field} answer={answer} "
                            f"entity={false_member} member=false entities={entity_set}"
                        )
                        if compact_set_op_cards:
                            false_card = (
                                f"set_member_card {false_key} domain={domain} field={field} answer={answer} "
                                f"entity={false_member} member=false count={len(entities_for_value)}"
                            )
                        if compact_membership_cards:
                            false_card = f"set_member_card {false_key} member=false count={len(entities_for_value)}"
                        if anchored_compact_membership_cards:
                            false_card = (
                                f"set_member_card {false_key} domain={domain} field={field} answer={answer} "
                                f"entity={false_member} member=false count={len(entities_for_value)}"
                            )
                        rows.append(
                            _row(
                                index=index,
                                op="set_member",
                                query=f"op=set_member {false_key} domain={domain} field={field} answer={answer} entity={false_member}",
                                card=_membership_answer_card("set_member", False) if membership_answer_targets else false_card,
                                answer="member_false",
                                support=f"{schema_card} test whether the entity is outside the reverse lookup set",
                                operation_token_prefix=operation_token_prefix,
                            )
                        )
                        index += 1

            if derived_set_ops:
                grouped: dict[tuple[str, str], set[str]] = {
                    key: {entity for entity, _fact_card in matches}
                    for key, matches in reverse_groups.items()
                }
                field_pairs = (
                    ("continent", "priority"),
                    ("continent", "status"),
                    ("currency", "risk"),
                    ("tool", "priority"),
                )
                for left_field, right_field in field_pairs:
                    left_groups = sorted((answer, members) for (field, answer), members in grouped.items() if field == left_field)
                    right_groups = sorted((answer, members) for (field, answer), members in grouped.items() if field == right_field)
                    for left_answer, left_members in left_groups:
                        for right_answer, right_members in right_groups:
                            intersection = sorted(left_members & right_members)
                            if not intersection:
                                continue
                            entity_set = "|".join(intersection)
                            count = len(intersection)
                            pair_key = f"lookup_key={domain}|{left_field}|{left_answer}&{right_field}|{right_answer}"
                            count_key = f"{pair_key}|count"
                            count_query = (
                                f"op=set_intersection_count {count_key} domain={domain} "
                                f"field_a={left_field} answer_a={left_answer} field_b={right_field} answer_b={right_answer}"
                            )
                            count_card = (
                                f"set_intersection_count_card {count_key} domain={domain} "
                                f"field_a={left_field} answer_a={left_answer} field_b={right_field} "
                                f"answer_b={right_answer} count={count}"
                            )
                            if count_answer_prefix:
                                count_card = f"count_answer={count} {count_card}"
                            rows.append(
                                _row(
                                    index=index,
                                    op="set_intersection_count",
                                    query=count_query,
                                    card=count_card,
                                    answer=str(count),
                                    support=f"{schema_card} count entities satisfying both field constraints",
                                    operation_token_prefix=operation_token_prefix,
                                )
                            )
                            index += 1

                            true_member = intersection[0]
                            true_key = f"{pair_key}|member|{true_member}"
                            true_card = (
                                f"set_intersection_member_card {true_key} domain={domain} "
                                f"field_a={left_field} answer_a={left_answer} field_b={right_field} "
                                f"answer_b={right_answer} entity={true_member} member=true count={count}"
                            )
                            if compact_membership_cards:
                                true_card = f"set_intersection_member_card {true_key} member=true count={count}"
                            if anchored_compact_membership_cards:
                                true_card = (
                                    f"set_intersection_member_card {true_key} domain={domain} "
                                    f"field_a={left_field} answer_a={left_answer} field_b={right_field} "
                                    f"answer_b={right_answer} entity={true_member} member=true count={count}"
                                )
                            rows.append(
                                _row(
                                    index=index,
                                    op="set_intersection_member",
                                    query=(
                                        f"op=set_intersection_member {true_key} domain={domain} "
                                        f"field_a={left_field} answer_a={left_answer} field_b={right_field} "
                                        f"answer_b={right_answer} entity={true_member}"
                                    ),
                                    card=_membership_answer_card("set_intersection_member", True) if membership_answer_targets else true_card,
                                    answer="member_true",
                                    support=f"{schema_card} test whether the entity satisfies both field constraints",
                                    operation_token_prefix=operation_token_prefix,
                                )
                            )
                            index += 1

                            false_candidates = [
                                item["entity"]
                                for item in entities
                                if item["entity"] not in set(intersection)
                            ]
                            if false_candidates:
                                false_member = false_candidates[0]
                                false_key = f"{pair_key}|member|{false_member}"
                                false_card = (
                                    f"set_intersection_member_card {false_key} domain={domain} "
                                    f"field_a={left_field} answer_a={left_answer} field_b={right_field} "
                                    f"answer_b={right_answer} entity={false_member} member=false count={count}"
                                )
                                if compact_membership_cards:
                                    false_card = f"set_intersection_member_card {false_key} member=false count={count}"
                                if anchored_compact_membership_cards:
                                    false_card = (
                                        f"set_intersection_member_card {false_key} domain={domain} "
                                        f"field_a={left_field} answer_a={left_answer} field_b={right_field} "
                                        f"answer_b={right_answer} entity={false_member} member=false count={count}"
                                    )
                                rows.append(
                                    _row(
                                        index=index,
                                        op="set_intersection_member",
                                        query=(
                                            f"op=set_intersection_member {false_key} domain={domain} "
                                            f"field_a={left_field} answer_a={left_answer} field_b={right_field} "
                                            f"answer_b={right_answer} entity={false_member}"
                                        ),
                                        card=_membership_answer_card("set_intersection_member", False) if membership_answer_targets else false_card,
                                        answer="member_false",
                                        support=f"{schema_card} test whether the entity violates at least one field constraint",
                                        operation_token_prefix=operation_token_prefix,
                                    )
                                )
                                index += 1

    rng.shuffle(rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=430)
    parser.add_argument("--domains", type=int, default=32)
    parser.add_argument("--entities-per-domain", type=int, default=10)
    parser.add_argument("--eval-ratio", type=float, default=0.12)
    parser.add_argument(
        "--reverse-lookup-mode",
        choices=("set", "single"),
        default="set",
        help="Use set-valued reverse lookup targets by default; single preserves the original under-specified row-per-entity task.",
    )
    parser.add_argument(
        "--operation-token-prefix",
        type=int,
        choices=(0, 1),
        default=0,
        help="Prefix retrieval queries/docs with explicit operation tokens to test operation-conditioned routing.",
    )
    parser.add_argument(
        "--reverse-lookup-key-prefix",
        type=int,
        choices=(0, 1),
        default=0,
        help="Prefix reverse lookup rows with a compact composite lookup_key=domain|field|answer key.",
    )
    parser.add_argument(
        "--compact-reverse-set-cards",
        type=int,
        choices=(0, 1),
        default=0,
        help="For reverse_lookup_set rows, omit full entity lists from retrieval docs while preserving lookup key and count.",
    )
    parser.add_argument(
        "--semantic-key-prefix",
        type=int,
        choices=(0, 1),
        default=0,
        help="Prefix every operation row with a compact semantic_key that encodes the exact binding being queried.",
    )
    parser.add_argument(
        "--direct-fact-key-prefix",
        type=int,
        choices=(0, 1),
        default=0,
        help="Prefix direct fact rows with fact_key=direct_fact|domain|entity|field to reduce same-entity wrong-field confusions.",
    )
    parser.add_argument(
        "--false-claim-key-prefix",
        type=int,
        choices=(0, 1),
        default=0,
        help="Prefix false_claim rows with false_key=false_claim|domain|entity|field|claimed.",
    )
    parser.add_argument(
        "--compact-false-claim-cards",
        type=int,
        choices=(0, 1),
        default=0,
        help="For false_claim rows, target only field/claimed/correct bindings instead of the full entity card.",
    )
    parser.add_argument(
        "--extended-set-ops",
        type=int,
        choices=(0, 1),
        default=0,
        help="Add set_count and set_member operations over reverse lookup sets.",
    )
    parser.add_argument(
        "--compact-set-op-cards",
        type=int,
        choices=(0, 1),
        default=0,
        help="For set_count/set_member rows, omit full entity lists from the retrieval doc target.",
    )
    parser.add_argument(
        "--compact-direct-fact-cards",
        type=int,
        choices=(0, 1),
        default=0,
        help="For direct_fact rows, omit unrelated fields from the retrieval doc target.",
    )
    parser.add_argument(
        "--direct-fact-selected-prefix",
        type=int,
        choices=(0, 1),
        default=0,
        help="For direct_fact rows, keep the full entity card but prefix selected_field and selected_answer before the full card.",
    )
    parser.add_argument(
        "--factorized-direct-fact-cards",
        type=int,
        choices=(0, 1),
        default=0,
        help="Use compact direct value cards and add separate entity_context cards with full entity fields.",
    )
    parser.add_argument(
        "--compact-rule-cards",
        type=int,
        choices=(0, 1),
        default=0,
        help="For rule_default/exception rows, use compact domain/entity/field/default/actual cards instead of the full schema text.",
    )
    parser.add_argument(
        "--rule-selected-prefix",
        type=int,
        choices=(0, 1),
        default=0,
        help="For rule_default/exception rows, keep full schema text but prefix the queried field/default/actual binding.",
    )
    parser.add_argument(
        "--rule-key-prefix",
        type=int,
        choices=(0, 1),
        default=0,
        help="Prefix rule_default/exception rows with rule_key=op|domain|entity|field.",
    )
    parser.add_argument(
        "--composition-key-prefix",
        type=int,
        choices=(0, 1),
        default=0,
        help="Prefix two_hop_owner_region rows with composition_key=two_hop_owner_region|domain|entity.",
    )
    parser.add_argument(
        "--count-answer-prefix",
        type=int,
        choices=(0, 1),
        default=0,
        help="Prefix count target cards with count_answer=N so tiny retrieval heads bind cardinality before long keys.",
    )
    parser.add_argument(
        "--membership-answer-targets",
        type=int,
        choices=(0, 1),
        default=0,
        help="Use compact operation+member=true/false target cards for membership operations instead of exact proof cards.",
    )
    parser.add_argument(
        "--compact-membership-cards",
        type=int,
        choices=(0, 1),
        default=0,
        help="Keep unique membership proof keys but omit repeated domain/field/entity text from membership target cards.",
    )
    parser.add_argument(
        "--anchored-compact-membership-cards",
        type=int,
        choices=(0, 1),
        default=0,
        help="Keep compact membership proof cards while preserving domain/entity/constraint anchors needed for near-neighbor binding.",
    )
    parser.add_argument(
        "--rule-set-ops",
        type=int,
        choices=(0, 1),
        default=0,
        help="Add rule_case_count and rule_case_member operations for default/exception sets.",
    )
    parser.add_argument(
        "--rule-case-intersection-ops",
        type=int,
        choices=(0, 1),
        default=0,
        help="Add rule_case_intersection_count/member operations over rule cases plus one field constraint.",
    )
    parser.add_argument(
        "--derived-set-ops",
        type=int,
        choices=(0, 1),
        default=0,
        help="Add two-constraint set_intersection_count and set_intersection_member operations.",
    )
    args = parser.parse_args()

    rows = _build_rows(
        domains=int(args.domains),
        entities_per_domain=int(args.entities_per_domain),
        seed=int(args.seed),
        reverse_lookup_mode=str(args.reverse_lookup_mode),
        operation_token_prefix=bool(args.operation_token_prefix),
        reverse_lookup_key_prefix=bool(args.reverse_lookup_key_prefix),
        compact_reverse_set_cards=bool(args.compact_reverse_set_cards),
        direct_fact_key_prefix=bool(args.direct_fact_key_prefix),
        false_claim_key_prefix=bool(args.false_claim_key_prefix),
        compact_false_claim_cards=bool(args.compact_false_claim_cards),
        semantic_key_prefix=bool(args.semantic_key_prefix),
        extended_set_ops=bool(args.extended_set_ops),
        compact_set_op_cards=bool(args.compact_set_op_cards),
        compact_direct_fact_cards=bool(args.compact_direct_fact_cards),
        direct_fact_selected_prefix=bool(args.direct_fact_selected_prefix),
        factorized_direct_fact_cards=bool(args.factorized_direct_fact_cards),
        compact_rule_cards=bool(args.compact_rule_cards),
        rule_selected_prefix=bool(args.rule_selected_prefix),
        rule_key_prefix=bool(args.rule_key_prefix),
        composition_key_prefix=bool(args.composition_key_prefix),
        count_answer_prefix=bool(args.count_answer_prefix),
        membership_answer_targets=bool(args.membership_answer_targets),
        compact_membership_cards=bool(args.compact_membership_cards),
        anchored_compact_membership_cards=bool(args.anchored_compact_membership_cards),
        rule_set_ops=bool(args.rule_set_ops),
        rule_case_intersection_ops=bool(args.rule_case_intersection_ops),
        derived_set_ops=bool(args.derived_set_ops),
    )
    eval_count = max(256, int(len(rows) * float(args.eval_ratio)))
    train_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    for position, row in enumerate(rows):
        copied = dict(row)
        if position < eval_count:
            copied["example_id"] = _stable_id("stage430_eval", position, row["example_id"])
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
        "artifact_kind": "agentkernel_lite_encdec_stage430_semantic_ops",
        "dataset_format": "jsonl",
        "eval_dataset_path": str(eval_path),
        "eval_examples": len(eval_rows),
        "manifest_path": str(manifest_path),
        "objective": "pocketpal_stage430_semantic_ops",
        "operations": [
            "direct_fact",
            *(["entity_context"] if bool(args.factorized_direct_fact_cards) else []),
            "reverse_lookup_set" if args.reverse_lookup_mode == "set" else "reverse_lookup",
            "false_claim",
            "rule_default",
            "exception",
            "two_hop_owner_region",
            *(["set_count", "set_member"] if bool(args.extended_set_ops) else []),
            *(["rule_case_count", "rule_case_member"] if bool(args.rule_set_ops) else []),
            *(["rule_case_intersection_count", "rule_case_intersection_member"] if bool(args.rule_case_intersection_ops) else []),
            *(["set_intersection_count", "set_intersection_member"] if bool(args.derived_set_ops) else []),
        ],
        "reverse_lookup_mode": str(args.reverse_lookup_mode),
        "operation_token_prefix": bool(args.operation_token_prefix),
        "reverse_lookup_key_prefix": bool(args.reverse_lookup_key_prefix),
        "compact_reverse_set_cards": bool(args.compact_reverse_set_cards),
        "direct_fact_key_prefix": bool(args.direct_fact_key_prefix),
        "false_claim_key_prefix": bool(args.false_claim_key_prefix),
        "compact_false_claim_cards": bool(args.compact_false_claim_cards),
        "semantic_key_prefix": bool(args.semantic_key_prefix),
        "extended_set_ops": bool(args.extended_set_ops),
        "compact_set_op_cards": bool(args.compact_set_op_cards),
        "compact_direct_fact_cards": bool(args.compact_direct_fact_cards),
        "direct_fact_selected_prefix": bool(args.direct_fact_selected_prefix),
        "factorized_direct_fact_cards": bool(args.factorized_direct_fact_cards),
        "compact_rule_cards": bool(args.compact_rule_cards),
        "rule_selected_prefix": bool(args.rule_selected_prefix),
        "rule_key_prefix": bool(args.rule_key_prefix),
        "composition_key_prefix": bool(args.composition_key_prefix),
        "count_answer_prefix": bool(args.count_answer_prefix),
        "membership_answer_targets": bool(args.membership_answer_targets),
        "compact_membership_cards": bool(args.compact_membership_cards),
        "anchored_compact_membership_cards": bool(args.anchored_compact_membership_cards),
        "rule_set_ops": bool(args.rule_set_ops),
        "rule_case_intersection_ops": bool(args.rule_case_intersection_ops),
        "derived_set_ops": bool(args.derived_set_ops),
        "train_dataset_path": str(train_path),
        "train_examples": len(train_rows),
        "total_examples": len(train_rows) + len(eval_rows),
        "training_principle": "semantic compression operations test direct access, inverse access, rule defaults, exceptions, false-claim rejection, and two-hop composition with both decoder and retrieval supervision",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
