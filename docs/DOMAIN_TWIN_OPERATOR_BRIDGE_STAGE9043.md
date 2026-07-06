# Stage9043 Domain/Twin Operator Bridge

Passed: `True`

This contract reconnects recovered DomainGraph, RepoTwin/PaperTwin, episodic/semantic memory, and critical operator-phase work to the 100M maintainer spine.
It is contract-only: no corpus scan, no memory materialization, no retrieval eval execution, no model execution, no training, no `/arxiv` write.

## Domain Graph Variables

- `concept_id`
- `concept_name`
- `concept_embedding`
- `edge_types`
- `appears_in_same_repo_as`
- `co_occurs_with`
- `is_subconcept_of_future`
- `cross_domain_connector_future`
- `repo_to_concept_map`
- `paper_to_concept_map`
- `repo_frequency_score`
- `concept_local_degree_score`
- `expert_repo_score`
- `expert_paper_score`

## Twin And Memory Variables

- `repo_twin_id`
- `paper_twin_id`
- `semantic_summary_scope`
- `episodic_time_window`
- `recency_boost`
- `test_type_weight`
- `doc_type_weight`
- `commit_issue_type_weight`
- `context_dedup_key`
- `semantic_context_limit`
- `episodic_context_limit`
- `consistency_report`
- `uncertainty_flags`
- `evidence_map`

## Critical Operator Bridge

- `OP030`: `repository_retrieval` -> `retrieval_recall_at_k`
- `OP053`: `list_aware_candidate_quality` -> `rerank_mrr_or_pairwise_accuracy`
- `OP048`: `verifier_backed_equivalence` -> `verifier_backed_equivalence_accuracy`
- `OP059`: `template_infill_slot_completion` -> `template_slot_accuracy`
- `OP086`: `phase_controller_policy` -> `phase_routing_accuracy`

## Recovered Stage Sequence

- `stage1272_failure_decomposition_eval`
- `stage1273_repository_retrieval_candidates_v2`
- `stage1274_list_aware_candidate_quality`
- `stage1275_op048_verifier_rows`
- `stage1276_op059_template_infill_rows`
- `stage1277_phase_controller_policy`

Next: Use this bridge as a checklist when designing future metadata-only DomainGraph/Twin manifests; do not scan /arxiv or repository_library until a separate active source ticket passes.

