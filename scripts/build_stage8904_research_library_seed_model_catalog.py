#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8904
NAME = "stage8904_research_library_seed_model_catalog"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESEARCH_LIBRARY_SEED_MODEL_CATALOG_STAGE8904.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CATALOG = OUT_DIR / "research_library_seed_model_catalog.json"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
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

HF_COLLECTION = "https://huggingface.co/collections/PeytonT/research-library-6a49c589ef4d763f7539b50d"
LOCAL_ROOT = "/data/repository_library"

CANDIDATES = [
    {
        "name": "local_agentkernel_lite_100m_bitnet_v11",
        "source": "local",
        "path_or_repo": "/data/repository_library/exports/agent_kernel/models/agentkernel_lite_100m_bitnet_v11",
        "role": "primary_seed_candidate",
        "use_for": ["100m_seq2seq_initialization_review", "tokenizer/special-token lineage review", "bounded_decoder_prior_if_compatible"],
        "why": "113.5M encoder-decoder AgentKernel Lite export, closest local artifact to the target model size and architecture.",
        "risk": "Must not be loaded/trained until architecture/tokenizer/loss-mask compatibility and provenance are audited.",
    },
    {
        "name": "PeytonT/repo-state-grounding",
        "source": "huggingface_collection",
        "path_or_repo": "PeytonT/repo-state-grounding",
        "role": "frozen_or_distilled_structured_teacher",
        "use_for": ["repo_state_grounding", "state_before/retrieval_context scoring", "VTR gate feature"],
        "why": "MiniLM-style text-classification model trained for repo-state grounding; directly aligned with verified_transition_record state evidence.",
        "risk": "Use as side teacher/ranker first, not as core generator.",
    },
    {
        "name": "PeytonT/jepa-repo-state",
        "source": "huggingface_collection",
        "path_or_repo": "PeytonT/jepa-repo-state",
        "role": "repo_state_representation_teacher",
        "use_for": ["state embedding targets", "modality dropout audit", "repo graph compressed representation"],
        "why": "Feature-extraction model for repo-state representation; useful for representation distillation into structured heads.",
        "risk": "Embedding compatibility/calibration required before fusion.",
    },
    {
        "name": "PeytonT/cross-encoder-reranker",
        "source": "huggingface_collection",
        "path_or_repo": "PeytonT/cross-encoder-reranker",
        "role": "retrieval_reranker_tool",
        "use_for": ["evidence ranking", "retrieval_context validation", "high-confidence-wrong audit"],
        "why": "Cross-encoder reranker maps task/evidence pairs to relevance; matches recovered Stage8721/8722 calibration direction.",
        "risk": "Must be calibrated; never use as sole truth source.",
    },
    {
        "name": "PeytonT/candidate-row-reranker",
        "source": "huggingface_collection",
        "path_or_repo": "PeytonT/candidate-row-reranker",
        "role": "dataset_judge_support",
        "use_for": ["candidate route prior", "junk/risk ranking", "active learning queue"],
        "why": "Can support objective-aware dataset ranking before rows create gradients.",
        "risk": "Must remain advisory behind deterministic junk/authority gates.",
    },
    {
        "name": "PeytonT/verifier-accept-policy",
        "source": "huggingface_collection",
        "path_or_repo": "PeytonT/verifier-accept-policy",
        "role": "verifier_policy_teacher",
        "use_for": ["verifier_result/value prior", "accept/reject policy", "repair loop scoring"],
        "why": "Text-classification model aligned with verification acceptance; useful for reward/value targets after exact verifier checks.",
        "risk": "Cannot replace tests/static analyzers; use only as learned prior.",
    },
    {
        "name": "PeytonT/span-infill-gate",
        "source": "huggingface_collection",
        "path_or_repo": "PeytonT/span-infill-gate",
        "role": "bounded_decode_gate_teacher",
        "use_for": ["decode_allowed refinement", "bounded argument gate", "edit span safety"],
        "why": "Classifier for whether span infill is appropriate; aligns with bounded decoder and patch-operator phases.",
        "risk": "Must obey deterministic budget/source authority overlays.",
    },
    {
        "name": "PeytonT/bug-localization",
        "source": "huggingface_collection",
        "path_or_repo": "PeytonT/bug-localization",
        "role": "edit_localization_teacher",
        "use_for": ["failure_to_symbol/file priors", "edit localization objective", "repair episode attribution"],
        "why": "Repo classifier over bug localization; maps directly to maintenance cognition spine.",
        "risk": "Needs repo graph symbol-binding calibration.",
    },
    {
        "name": "PeytonT/cross-modal-retrieval",
        "source": "huggingface_collection",
        "path_or_repo": "PeytonT/cross-modal-retrieval",
        "role": "paper_repo_retrieval_teacher",
        "use_for": ["research_transfer retrieval", "paper_to_repo alignment", "operator card evidence"],
        "why": "Feature-extraction model for paper/code retrieval, useful for knowledge-transfer policy.",
        "risk": "Retrieval evidence only; not target truth.",
    },
    {
        "name": "PeytonT/paper-to-code",
        "source": "huggingface_collection/local_adapter_family",
        "path_or_repo": "PeytonT/paper-to-code or /data/repository_library/models/checkpoints/C1",
        "role": "research_transfer_teacher_not_core_seed",
        "use_for": ["teacher candidate plans", "research_operator_card generation", "paper_to_implementation sketch"],
        "why": "FLAN-T5 adapter trained for paper-to-code transfer; useful as synthetic teacher into verified transition records.",
        "risk": "Do not distill unverified outputs directly; verifier/source grounding required.",
    },
    {
        "name": "PeytonT/repo-conditioned-adapter",
        "source": "huggingface_collection/local_adapter_family",
        "path_or_repo": "PeytonT/repo-conditioned-adapter or /data/repository_library/models/checkpoints/C4",
        "role": "repo_conditioned_teacher_not_core_seed",
        "use_for": ["repo-conditioned bounded plan/argument suggestions", "adapter-fusion experiments"],
        "why": "T5 adapter conditioned on repository information; likely helpful for proposal generation after gates pass.",
        "risk": "Base is FLAN-T5-base, not the 100M target; use as teacher/advisory source.",
    },
    {
        "name": "PeytonT/query-rewriter",
        "source": "huggingface_collection/local_adapter_family",
        "path_or_repo": "PeytonT/query-rewriter or /data/repository_library/models/checkpoints/L1",
        "role": "retrieval_policy_teacher",
        "use_for": ["search query generation", "retrieve_context action target", "evidence acquisition traces"],
        "why": "Directly supports transition action RETRIEVE_CONTEXT and repository/library search.",
        "risk": "Queries must be judged by retrieval utility, not copied into target truth.",
    },
    {
        "name": "PeytonT/world-planner-adapter",
        "source": "huggingface_collection/local_adapter_family",
        "path_or_repo": "PeytonT/world-planner-adapter or /data/repository_library/models/checkpoints/U2",
        "role": "planner_teacher_not_core_seed",
        "use_for": ["multi-step transition trace proposals", "action sequence prior", "curriculum candidate generation"],
        "why": "Planning adapter can propose action traces for verification/mining.",
        "risk": "Use behind verifier and transition-record schema; not a runtime controller yet.",
    },
    {
        "name": "PeytonT/unified-knowledge-model",
        "source": "huggingface_collection/local_adapter_family",
        "path_or_repo": "PeytonT/unified-knowledge-model or /data/repository_library/models/checkpoints/U1",
        "role": "broad_teacher_reference",
        "use_for": ["teacher comparison", "adapter-fusion baseline", "curriculum candidate proposals"],
        "why": "Broad T5 adapter over research-library objectives; may provide useful proposals.",
        "risk": "Too broad for direct student seed; verify outputs and avoid shortcut teacher leakage.",
    },
    {
        "name": "local_m1_lite_and_scibert_onnx",
        "source": "local",
        "path_or_repo": "/data/repository_library/exports/huggingface/m1_lite_onnx and m1_scibert_merged_onnx",
        "role": "paper_embedding_retrieval_tool",
        "use_for": ["paper/research operator retrieval", "paper universe semantic search", "research_transfer evidence"],
        "why": "Distilled/scibert paper embedding models with documented M1 vector space; useful for external retrieval, not generator weights.",
        "risk": "Embedding-only; does not replace compiler/verifier.",
    },
]

DIRECT_CORE_SEED = ["local_agentkernel_lite_100m_bitnet_v11"]
TEACHER_OR_TOOL_ONLY = [item["name"] for item in CANDIDATES if item["name"] not in DIRECT_CORE_SEED]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_catalog() -> dict[str, Any]:
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "hf_collection": HF_COLLECTION,
        "local_root": LOCAL_ROOT,
        "decision": {
            "best_core_seed": DIRECT_CORE_SEED,
            "default_use": "teacher/tool/ranker/retrieval sidecar unless explicit compatibility audit promotes a model",
            "do_not_do": [
                "do not initialize the 100M maintainer from arbitrary T5/LLM adapters",
                "do not let teacher outputs bypass verified_transition_record_v1 gates",
                "do not download or execute models in this stage",
            ],
        },
        "candidates": CANDIDATES,
        "integration_order": [
            "inventory local AgentKernel Lite architecture/tokenizer compatibility",
            "register frozen side teachers/rankers as non-authoritative evidence providers",
            "add VTR provenance refs for teacher/tool suggestions",
            "calibrate rerankers/verifier policies before use",
            "only then consider representation distillation or adapter fusion",
        ],
        "authority": AUTHORITY_CLOSED,
    }


def validate_catalog(catalog: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not catalog.get("candidates"):
        failures.append("empty_catalog")
    if DIRECT_CORE_SEED != ["local_agentkernel_lite_100m_bitnet_v11"]:
        failures.append("unexpected_core_seed")
    for item in catalog["candidates"]:
        for key in ["name", "source", "path_or_repo", "role", "use_for", "why", "risk"]:
            if key not in item:
                failures.append(f"candidate_missing_{key}:{item.get('name')}")
    if any(c["role"] == "primary_seed_candidate" for c in catalog["candidates"]) is False:
        failures.append("missing_primary_seed_candidate")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = (registry.get("metrics") or {}).get("latest_stage")
    if latest not in {8903, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    catalog = build_catalog()
    failures = validate_catalog(catalog, registry)
    CATALOG.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            "candidate_count": len(CANDIDATES),
            "direct_core_seed_count": len(DIRECT_CORE_SEED),
            "teacher_or_tool_only_count": len(TEACHER_OR_TOOL_ONLY),
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_walk_authorized": False,
            "data_mining_authorized": False,
            "download_authorized": False,
        },
        "artifacts": {"catalog": str(CATALOG.relative_to(ROOT))},
        "decision": "Cataloged research-library/local model seeds and side teachers; only AgentKernel Lite is a direct core-seed candidate pending compatibility audit." if not failures else "Research-library seed catalog failed validation.",
        "next_best_step": "Build a no-execution compatibility audit for local AgentKernel Lite tokenizer/architecture and register other models as non-authoritative teacher/tool candidates.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8904 Research Library Seed Model Catalog",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage catalogs useful models from the Hugging Face research-library collection and local `/data/repository_library` exports without downloading, loading, or executing any model.",
        "",
        "Decision: the only direct core-seed candidate is the local AgentKernel Lite 100M-ish encoder-decoder export, pending tokenizer/architecture compatibility audit. The other models are useful as frozen teachers, retrievers, rerankers, verifier priors, planner proposal sources, or representation-distillation sidecars.",
        "",
        "Most useful side candidates: repo-state-grounding, jepa-repo-state, cross-encoder-reranker, candidate-row-reranker, verifier-accept-policy, span-infill-gate, bug-localization, cross-modal-retrieval, paper-to-code, repo-conditioned-adapter, query-rewriter, world-planner-adapter, M1 paper embeddings.",
        "",
        "This opens no model execution, downloads, training, decoder CE, denoise CE, runtime, `/arxiv` walk, data mining, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, or promotion.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8904 Research Library Seed Model Catalog"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8902 catalogs research-library/local model candidates. The only direct 100M core-seed candidate is the local AgentKernel Lite encoder-decoder export, pending compatibility audit. Collection models should first be used as frozen teachers, rerankers, retrieval tools, verifier priors, proposal sources, or representation sidecars behind verified-transition-record gates.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
