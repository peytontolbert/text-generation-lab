# Stage8653 Support Systems Recovery Index

This index recovers support systems for the 100M software-maintainer curriculum compiler and training loop. It is no-authority: no model execution, training, decoder CE, denoise CE, runtime, scoring, source/body emission, or promotion is opened.

## Why This Matters

The maintainer will not improve by scaling raw rows. It needs a support layer that detects evidence, shortcuts, junk, OOD cases, missing retrieval, duplicate clusters, label conflicts, and verifier disagreements before rows reach loss.

## Components
- `lexical_bm25_retrieval`: Cheap source grounding baseline over repo files, symbols, tests, docs, and logs. Must beat/compare against embedding retrieval before neural retrieval is trusted.
  Status: not_implemented_as_first_class_gate
  Next: Create a no-training BM25/source-grounding baseline card for repo_state_graph and symbol_binding rows.
- `embedding_retrieval`: Dense evidence retrieval for semantically similar code, issue text, test failures, and docs.
  Status: references_recovered_not_wired_to_curriculum_rows
  Next: Attach retrieval evidence packets plus evidence-removed controls to every scaled curriculum row.
- `cross_encoder_reranker`: Re-rank retrieved file/symbol/test/log candidates against the exact user intent or verifier failure.
  Status: schema_only
  Next: Use after BM25+dense recall baseline exists; never let reranker confidence authorize decode alone.
- `feature_detectors_static`: Deterministic feature extraction from rows: budget flags, leak flags, long blob, internal token, missing evidence, import policy, graph degree, surface markers.
  Status: partially_implemented
  Next: Promote feature extraction to a shared library so all builders use identical feature names and avoid Stage8058-style feature drift.
- `ngram_repetition_style_detectors`: Detect local syntax/style priors, repetition loops, degenerate spans, unusual token transitions, and repo-style mismatches.
  Status: reference_recovered_not_integrated
  Next: Add as non-authority junk/ranker features for decoder and denoise rows.
- `junk_risk_ood_ranker`: Route rows/candidates as keep, denoise, retrieve, quarantine, hold-long, or negative using transparent features.
  Status: missing_unified_ranker
  Next: Build the first ranker as deterministic/logistic/GBDT card over judged rows before any large 1M expansion.
- `cluster_slice_detection`: Find repeated failure clusters, duplicate semantic keys, near-duplicate data islands, and undercovered curriculum cells.
  Status: not_implemented
  Next: Cluster row embeddings/features after source-backed graph/symbol-binding rows exist; use clusters to guide expansion, not to label targets.
- `bias_shortcut_audit`: Detect metadata-only, count-only, label-proxy, surface-marker, graph-degree, node-id, and target-leak shortcuts.
  Status: implemented_for_current_recovered_objectives
  Next: Generalize shortcut audit config per objective and require it in every scale-import PR.
- `dataset_cartography_dynamics`: Track confidence/variability/forgetting/token-loss over training to identify easy, ambiguous, hard, mislabeled, and high-value rows.
  Status: concept_recovered_no_current_probe_authority
  Next: Add to next tiny probe telemetry only after graph/symbol/ranker gates pass.
- `training_data_attribution`: Map failed evals back to helpful/harmful/missing training rows for targeted dataset edits.
  Status: concept_recovered_not_implemented
  Next: Start with nearest-neighbor attribution over row features/embeddings before expensive influence-function methods.
- `confidence_margin_entropy_calibration`: Convert logits/margins/entropy/evidence state into abstention thresholds and no-wrong-accept gates.
  Status: telemetry_contract_only
  Next: Add to structured finite-head probes before decode; learned confidence cannot authorize source/body emission.
- `symbolic_verifier_stack`: Exact external checks: parser, AST, lint, type, import resolution, test selection, verifier logs, and patch acceptance signals.
  Status: objective_rows_restored_but_runtime_closed
  Next: Keep runtime closed; use verifier-shaped rows until sandbox execution contracts are rebuilt.
- `curriculum_compiler`: Compile eval failures and dataset gaps into row operations: add, remove, relabel, rebalance, quarantine, counterfactual, or route change.
  Status: partially_implemented_scaffold
  Next: Connect it to the Stage8653 support features and require one compiler patch per training-data expansion.
- `reservoir_source_sampler`: Sample from large /arxiv and public datasets into balanced objective cells without raw-volume drift.
  Status: missing_for_1m_scale
  Next: Build source inventory cards and per-objective sampling quotas before any 1M expansion.
- `teacher_verifier_disagreement_detector`: Detect conflicts between teacher labels, verifier signals, source evidence, and deterministic judges.
  Status: judge_signal_exists_not_full_detector
  Next: Require disagreement rows to quarantine or human-review, never train as positives.

## Required Build Order

1. Promote deterministic feature extraction into one shared feature library.
2. Build BM25 + dense retrieval baseline cards for source-backed graph and symbol-binding rows.
3. Add n-gram/repetition/style detector features as non-authority junk/ranker inputs.
4. Build a transparent junk/risk/OOD ranker using linear/tree/MLP classifier references.
5. Add cluster/near-duplicate/slice-gap detection after row embeddings/features exist.
6. Attach curriculum compiler dataset patches to every expansion step.
7. Only after this support layer passes should training candidates reopen.
