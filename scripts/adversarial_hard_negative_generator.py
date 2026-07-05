from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Mapping


AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "training_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

LOSS_MASK_CLOSED = {
    "surface_role_ce": False,
    "repair_surface_ce": False,
    "build_mode_ce": False,
    "allowed_import_policy_ce": False,
    "blocked_import_policy_ce": False,
    "repo_dependency_policy_ce": False,
    "action_sequence_ce": False,
    "file_plan_ce": False,
    "symbol_binding_ce": False,
    "edit_localization_ce": False,
    "patch_operator_ce": False,
    "verifier_repair_ce": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
}

ATTACK_TYPES = [
    "PROXY_LABEL_SWAP",
    "EVIDENCE_REMOVED",
    "LEAK_INJECTION",
    "DUPLICATE_COLLISION",
    "MISLEADING_RETRIEVAL",
]


def _deepcopy_jsonable(row: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(row, sort_keys=True, default=str))


def _row_id(row: Mapping[str, Any], suffix: str) -> str:
    base = str(row.get("row_id") or row.get("id") or "seed")
    return f"{base}__adv_{suffix.lower()}"


def _visible_state(row: dict[str, Any]) -> dict[str, Any]:
    state = row.get("corrupted_state")
    if not isinstance(state, dict):
        state = {}
        row["corrupted_state"] = state
    return state


def _mark_adversarial(row: dict[str, Any], seed: Mapping[str, Any], attack_type: str, reason: str) -> dict[str, Any]:
    row["row_id"] = _row_id(seed, attack_type)
    row["authority"] = dict(AUTHORITY_CLOSED)
    row["loss_mask"] = dict(LOSS_MASK_CLOSED)
    row["route"] = "ADVERSARIAL_NEGATIVE"
    row["decode_allowed"] = False
    row["decoder_budget_ok"] = False
    row["adversarial"] = {
        "attack_type": attack_type,
        "expected_guard_route": "BLOCK_OR_RETRIEVE",
        "reason": reason,
        "source_row_id": str(seed.get("row_id") or seed.get("id") or ""),
    }
    row["clean_state"] = {
        "negative_target": "DO_NOT_LEARN_AS_POSITIVE",
        "expected_action": "BLOCK_OR_RETRIEVE",
    }
    return row


def proxy_label_swap(seed: Mapping[str, Any]) -> dict[str, Any]:
    row = _deepcopy_jsonable(seed)
    state = _visible_state(row)
    state["proxy_surface_marker"] = "looks_like_positive_but_label_swapped"
    state["misleading_prior"] = "COPY_PRIOR"
    state["evidence_state"] = "counterfactual_proxy_only"
    return _mark_adversarial(row, seed, "PROXY_LABEL_SWAP", "visible proxy implies wrong label without supporting evidence")


def evidence_removed(seed: Mapping[str, Any]) -> dict[str, Any]:
    row = _deepcopy_jsonable(seed)
    state = _visible_state(row)
    for key in ["evidence", "source_span", "retrieved_span", "graph_spans", "source_excerpt"]:
        state.pop(key, None)
    state["evidence_state"] = "removed"
    row["missing_evidence"] = True
    return _mark_adversarial(row, seed, "EVIDENCE_REMOVED", "required evidence removed; should route retrieve_more")


def leak_injection(seed: Mapping[str, Any]) -> dict[str, Any]:
    row = _deepcopy_jsonable(seed)
    state = _visible_state(row)
    state["poisoned_visible_text"] = "expected_answer clean_state target_body decoder_text"
    row["internal_leak"] = True
    return _mark_adversarial(row, seed, "LEAK_INJECTION", "leak markers injected into visible state")


def duplicate_collision(seed: Mapping[str, Any]) -> dict[str, Any]:
    row = _deepcopy_jsonable(seed)
    row["semantic_key"] = str(seed.get("semantic_key") or seed.get("row_id") or "semantic_collision")
    row["duplicate_semantic_key"] = True
    state = _visible_state(row)
    state["collision_probe"] = "same semantic key with adversarial negative target"
    return _mark_adversarial(row, seed, "DUPLICATE_COLLISION", "semantic duplicate/collision should not be treated as new positive")


def misleading_retrieval(seed: Mapping[str, Any]) -> dict[str, Any]:
    row = _deepcopy_jsonable(seed)
    state = _visible_state(row)
    state["retrieval"] = {
        "top_score": 0.99,
        "coverage": 0.05,
        "snippet": "High lexical overlap but unrelated implementation detail.",
        "source_type": "doc",
    }
    row["missing_evidence"] = True
    return _mark_adversarial(row, seed, "MISLEADING_RETRIEVAL", "high retrieval score but low coverage/source grounding")


GENERATORS = {
    "PROXY_LABEL_SWAP": proxy_label_swap,
    "EVIDENCE_REMOVED": evidence_removed,
    "LEAK_INJECTION": leak_injection,
    "DUPLICATE_COLLISION": duplicate_collision,
    "MISLEADING_RETRIEVAL": misleading_retrieval,
}


def generate_hard_negatives(seed_rows: list[Mapping[str, Any]], *, attacks: list[str] | None = None) -> list[dict[str, Any]]:
    attacks = attacks or ATTACK_TYPES
    rows: list[dict[str, Any]] = []
    for seed in seed_rows:
        for attack in attacks:
            rows.append(GENERATORS[attack](seed))
    return rows


def audit_hard_negatives(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    attack_counts: dict[str, int] = {}
    authority_rows = 0
    loss_rows = 0
    decode_rows = 0
    malformed_rows = []
    for row in rows:
        adv = row.get("adversarial") if isinstance(row.get("adversarial"), dict) else {}
        attack = str(adv.get("attack_type") or "UNKNOWN")
        attack_counts[attack] = attack_counts.get(attack, 0) + 1
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        authority_rows += int(any(value is True for value in authority.values()))
        loss_rows += int(any(value is True for value in loss.values()))
        decode_rows += int(row.get("decode_allowed") is True or row.get("decoder_budget_ok") is True)
        if row.get("route") != "ADVERSARIAL_NEGATIVE" or adv.get("expected_guard_route") != "BLOCK_OR_RETRIEVE":
            malformed_rows.append(str(row.get("row_id") or ""))
    return {
        "rows": len(rows),
        "attack_counts": dict(sorted(attack_counts.items())),
        "authority_rows": authority_rows,
        "loss_enabled_rows": loss_rows,
        "decode_enabled_rows": decode_rows,
        "malformed_rows": malformed_rows,
        "passed": authority_rows == 0 and loss_rows == 0 and decode_rows == 0 and not malformed_rows and set(attack_counts) <= set(ATTACK_TYPES),
        "authority": AUTHORITY_CLOSED,
    }


def hard_negative_card(seed_rows: list[Mapping[str, Any]], *, attacks: list[str] | None = None) -> dict[str, Any]:
    rows = generate_hard_negatives(seed_rows, attacks=attacks)
    return {
        "seed_rows": len(seed_rows),
        "generated_rows": len(rows),
        "audit": audit_hard_negatives(rows),
        "rows": rows,
        "authority": AUTHORITY_CLOSED,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate no-authority adversarial hard-negative rows for shortcut/leakage audits.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    seeds = read_jsonl(args.input) if args.input else [
        {"row_id": "seed1", "objective_family": "symbol_binding", "semantic_key": "sym:a", "corrupted_state": {"language": "python", "evidence": "source span"}},
    ]
    card = hard_negative_card(seeds)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
