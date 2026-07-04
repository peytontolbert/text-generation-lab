from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

REQUIRED_PHASES = ("prepare", "verify", "normalize_failure", "repair_decision", "reverify_or_abstain")
FORBIDDEN_EXECUTION_FLAGS = (
    "runtime_authorized",
    "source_emission_authorized",
    "body_emission_authorized",
    "gemma_execution_authorized",
    "harness_execution_authorized",
    "scoring_authorized",
)


@dataclass(frozen=True)
class RuntimeVerifierLoopContract:
    phases: list[str]
    verifier_inputs: list[str]
    verifier_outputs: list[str]
    failure_taxonomy: list[str]
    repair_actions: list[str]
    authority: dict[str, bool]
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_runtime_verifier_loop_contract() -> dict[str, Any]:
    authority = {
        "runtime_authorized": False,
        "source_emission_authorized": False,
        "body_emission_authorized": False,
        "gemma_execution_authorized": False,
        "harness_execution_authorized": False,
        "scoring_authorized": False,
        "model_execution_authorized": False,
        "training_authorized": False,
    }
    return RuntimeVerifierLoopContract(
        phases=list(REQUIRED_PHASES),
        verifier_inputs=["candidate_patch", "bounded_decoder_output", "repo_state_packet", "runtime_trace_packet", "dependency_capability_card"],
        verifier_outputs=["syntax_result", "test_result", "runtime_trace_packet", "failure_type", "repair_route", "accept_reject_state"],
        failure_taxonomy=["syntax_failure", "dependency_import_failure", "symbol_binding_failure", "runtime_contract_failure", "test_assertion_failure", "timeout_failure", "unknown_runtime_failure"],
        repair_actions=["REPAIR_PATCH", "REPAIR_IMPORT", "REPAIR_SYMBOL_BINDING", "REPAIR_CONTRACT", "RETRIEVE_MORE", "ABSTAIN_UNSAFE", "ACCEPT_VERIFIED"],
        authority=authority,
        failures=[],
    ).to_dict()


def audit_runtime_verifier_loop_contract(contract: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    phases = list(contract.get("phases") or [])
    for phase in REQUIRED_PHASES:
        if phase not in phases:
            failures.append(f"missing_phase:{phase}")
    authority = dict(contract.get("authority") or {})
    for flag in FORBIDDEN_EXECUTION_FLAGS:
        if authority.get(flag) is True:
            failures.append(f"forbidden_authority_open:{flag}")
    if authority.get("model_execution_authorized") is True or authority.get("training_authorized") is True:
        failures.append("model_or_training_authority_open")
    if not contract.get("failure_taxonomy"):
        failures.append("missing_failure_taxonomy")
    if not contract.get("repair_actions"):
        failures.append("missing_repair_actions")
    if "runtime_trace_packet" not in contract.get("verifier_outputs", []):
        failures.append("missing_runtime_trace_packet_output")
    return {
        "passed": not failures,
        "failures": failures,
        "phase_count": len(phases),
        "failure_taxonomy_count": len(contract.get("failure_taxonomy") or []),
        "repair_action_count": len(contract.get("repair_actions") or []),
        "authority": authority,
    }
