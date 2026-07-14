#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


DEFAULT_POLICY = "current_retrieval"
POLICY_OVERRIDE_BY_TASK = {
    "verifier_outcome_semantic_transition": "decoder_on_transition_only",
}


def policy_for_row(*, row: dict[str, Any], default_policy: str = DEFAULT_POLICY, override_by_task: dict[str, str] | None = None) -> str:
    task_type = str(row.get("task_type") or "")
    overrides = override_by_task or POLICY_OVERRIDE_BY_TASK
    return str(overrides.get(task_type) or default_policy)


def choose_bounded_choice_label(
    *,
    row: dict[str, Any],
    constrained_label: str | None,
    decoder_label: str | None,
    policy: str,
) -> str | None:
    task_type = str(row.get("task_type") or "")
    if policy == "current_retrieval":
        return constrained_label
    if policy == "decoder_on_all_verifier":
        if task_type in {"verifier_outcome", "verifier_outcome_semantic_transition"}:
            return decoder_label
        return constrained_label
    if policy == "decoder_on_transition_only":
        if task_type == "verifier_outcome_semantic_transition":
            return decoder_label
        return constrained_label
    raise ValueError(f"unsupported bounded choice policy: {policy}")


def policy_correct(*, target_label: str, predicted_label: str | None) -> bool | None:
    if predicted_label is None:
        return None
    return str(predicted_label) == str(target_label)
