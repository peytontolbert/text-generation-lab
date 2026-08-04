# Deterministic Model Function Replacement Audit

Created: 2026-08-02

Scope: deterministic functions that can supply model-visible state, logits, option scores, route labels, or training/admission features. Hash-only provenance helpers and authority gates are only listed when they feed a model-facing packet or shortcut-prone feature.

## Summary

The highest-risk issue is not ordinary deterministic plumbing. It is deterministic feature construction being wired into trainable heads, especially bounded-choice auxiliary heads and the repo-state compressor. Those paths can let the system learn buckets, labels, roles, status enums, and handcrafted sketches instead of repository state transitions.

Replace priority:

1. `P0`: remove or quarantine from model inputs before further training.
2. `P1`: keep as audit/guardrail only, replace model-visible use with learned encoders or runtime evidence.
3. `P2`: leave as telemetry, but do not use as training labels/features without an explicit learned replacement plan.

Mitigation status as of 2026-08-02:

- P0 deterministic bounded-choice aux scorer and rendered option sources are removed from trainer config choices. Runtime scoring accepts only `decoder_first_step`, `encoder_pooled`, `encoder_pooled_untied_head`, `encoder_option_biencoder`, and `encoder_option_cross_encoder`. Old deterministic and raw legacy retrieval aliases fail closed.
- `state_space_repo_state_compressor.selective_scan_compress` remains available for audit cards. `as_model_input=True` now requires a `LearnedRepoStateEncoder` plus tokenizer and emits `learned_repo_state_embedding` instead of the deterministic 32-dimensional sketch.

## 2026-08-02 Executable Risk Resolution

The earlier Repo And Code Knowledge and Structured Repo State completion claims are invalidated. The current deterministic outputs are not admitted training data. Stage12686 hash-locks the audited source files, classifies every audited row, and is enforced by the canonical trainer manifest loader.

Resolved executable defects:

- Model input serialization no longer exposes oracle chunk IDs, row IDs, labels, targets, rewards, observations, verifier outcomes, or nested target aliases. Mutation tests require target and evidence-ID changes to leave encoder tokens unchanged.
- Byte and BPE target encoding preserves EOS. Generative rows with empty or over-budget targets now fail closed. Generation-only encoder setup no longer creates silently truncated two-token labels.
- Structured-policy checkpoint selection uses `eval` only. Its `strict_eval` metrics are withheld from the training process and cannot affect best-state selection.
- Runtime model initialization rejects raw, unhashed, legacy, malformed, or deterministic-placeholder-contaminated bundles before `torch.load`.
- Parquet JSON strings are decoded before source grouping. Connected source identities cannot cross splits. The leakage audit now checks source IDs, normalized context hashes, target hashes, and lineage groups.
- The current ten-pack long-context artifact fails the corrected audit: 10 blank declared source signatures, 543 source IDs crossing splits, and 4,805 exact context hashes crossing splits. Corrected grouping makes all ten packs one connected component, so an honest three-way split is impossible.

Stage12686 enforced nonadmission:

| Classification | Rows | Disposition |
| --- | ---: | --- |
| Stage12656 deterministic summary copies | 200 | Quarantined |
| Stage12662 constant taxonomy labels | 2,187 | Quarantined |
| Stage12680 source-starved or existing shortcut rows | 120,000 | Quarantined |
| Stage12685 regex, lexical, or indistinguishable pairs | 13,984 | Quarantined |
| Stage12656 symbol-binding candidates | 80 | Independent semantic review required; blocked |
| Stage12685 Python AST candidates | 17,428 | Independent positive and negative endpoint reparse required; blocked |

The 153,879 classified rows have 153,879 distinct ledger IDs and source-dataset row hashes. All five inputs and both generated nonadmission ledgers are pinned by SHA-256 and row count, plaintext source references are excluded from ledgers, and exact rows plus modified copies carrying blocked lineage markers are rejected by `load_manifest`. Training-eligible rows from these audited stages: **0**.

Remaining blockers:

- Bounded-decoder and denoise modes still expose `strict_eval` during their processes; only structured-policy selection is sealed.
- The long-context renderer still caps context at 64 rows, 512 characters per row, and 2,048 encoder tokens. The current supply is narrow and unsplittable.
- The 17,428 AST candidates need independent reparse of both endpoints; the 80 symbol candidates need semantic review. Review-required does not mean admitted.
- Foundational code/repository supervision must be rebuilt with actual bounded source text and source-backed objectives, then independently reviewed.
- The production optimizer recipe, release manifest, license/provenance catalog, and truly external sealed evaluation remain unresolved.

Authority remains false for `implementation_ready`, `training_admitted`, `strict_eval_admitted`, `sealed_eval_admitted`, `replay_trustworthy`, and `level_3_materialized`.

## Stage12687 Source-Backed Foundational Corpus

Stage12687 replaces the quarantined deterministic knowledge rows with parser-verified Python source-span infilling from pinned Git snapshots. Targets are exact source bytes, exact reinsertion reconstructs the source window, and the reconstructed full file has the same CPython AST as the pinned blob. Target-derived fields are excluded from encoder serialization and a target-mutation test requires identical encoder tokens.

Authoritative generation: `594cbbdc08af0cc409eceda1`.

| Published artifact | Rows | SHA-256 |
| --- | ---: | --- |
| `foundational_train_eval_manifest.jsonl` | 18,000 | `3f677fb3d9108632a208b34f9eb98b2ee2a6687b3a401cd5229d653e71ae5994` |
| `train_eval_source_provenance_ledger.jsonl` | 18,000 | `f5b3c921035ea6d5d77c5f3bc06576be3ea556bc8ea49c4669e69fd28664a5c8` |
| `train_eval_source_catalog.jsonl` | 294 | `ec8e5eee9bc7cb366ca3c0f844913ca52ee72fecd920be4fdde764b7b3431b09` |

Verified population:

- 16,000 train rows and 2,000 eval rows are published from 185 contributing repositories; no repository, connected content component, file digest, or source-window digest crosses train/eval.
- 2,000 strict candidates are reserved but not materialized. Only commitment `1b83b9b7ec75c66361c38655299bae28d30f1515116f71ad1e88adca801cdada` is public. Strict rows, proofs, paths, catalog entries, and targets are absent from the generation and must be rebuilt by a separate release evaluator.
- Blank targets, exact or whitespace-normalized target leakage, duplicate model/semantic/window hashes, policy-defined stubs, bare `NotImplementedError`, sole `pass`/ellipsis bodies, TODO/FIXME/TBD targets, secret patterns, and explicit AI-generated markers are all zero.
- The dedicated exact-input renderer audit found maximum lengths of 1,278 encoder tokens and 411 decoder tokens; zero rows exceed the current 2,048/768 bounds.
- The immutable generation is mode `0500`, its files are `0400`, all authority flags remain false, and the canonical and mirror summaries are byte-identical.
- Independent review found and corrected model-visible metadata, zero-weight deterministic auxiliary execution, false execution authority, a direct-call bypass, manifest hash/use reopening, and a false strict-inaccessibility claim. Parent verification of the corrected trainer and serializer paths passed 84 tests.

The invalid generation `4ea398bcbd0d26ea17e77943`, which contained strict plaintext plus stub/placeholder and explicit AI-generated candidates, was deleted with explicit user authorization. No Stage12687 strict plaintext remains materialized.

The dedicated foundational_code_ce integration now validates the exact canonical manifest, companion hashes, exact schema, decoder-CE-only loss contract, full untruncated BPE lengths, and 16,000/2,000 train/eval counts. Its renderer exposes only input_text; strict rows and deterministic choice features are excluded. The user waived license review for this internal corpus.

The production optimizer/checkpoint implementation is now pinned by foundational_code_ce_optimizer_v1.json (SHA-256 36d64f5e1448cfe8d3f24ffa9087598b74ecb4a83741520c45a65a489d7b6125). It implements complete/disjoint AdamW groups, bounded dynamic token accumulation, token-based warmup and cosine decay, CUDA:2 bf16 gating, eval-only selection, exact deterministic resume, complete provenance, and descriptor-safe no-overwrite checkpoint publication. Parent verification passed 107 tests and independent optimizer/resume and checkpoint-security reviews both passed.

Stage12687 training-eligible rows remain **0** because the authoritative summary still denies training and model execution, the intended Griffin encoder remains implementation/authority blocked, and this lane contains only 12,669,005 train encoder tokens plus 892,050 decoder target tokens. The recipe is therefore a fail-closed recovered-Transformer baseline contract, not authorization to train the intended frontier model. Both the CLI and direct Python wrapper remain blocked; no foundational execution_result.json, checkpoint, or model may be produced. This corpus does not complete structured state, transitions, localization, patch selection, long-horizon, or verifier-conditioned training layers.

## P0: Model-Facing Deterministic Features

| Function or group | Location | Deterministic signal | Why it must be replaced | Replacement target |
| --- | --- | --- | --- | --- |
| `selective_scan_compress` | `scripts/state_space_repo_state_compressor.py:99` | Fixed 32-dim repo-state vector by decay/gate formula. | This is not a learned state-space model; it is a deterministic feature sketch with deterministic event acceptance, budget dropping, ranking, normalization, and hint IDs. | Learned repo-state encoder/state-space module trained on source-backed transition episodes; compressor output should be embeddings from the model, not handcrafted vectors. |
| `event_features` | `scripts/state_space_repo_state_compressor.py:79` | Event type one-hot, scalar scores, token length, SHA256 lexical sketch. | Hash-derived lexical bits and event-type one-hots can become shortcut state. | Learned event encoder over text, trace, graph, and patch context; no hash sketch in model-visible state. |
| `event_score` | `scripts/state_space_repo_state_compressor.py:68` | Weighted sum of type, importance, retrieval, grounding, recency. | Hardcoded relevance score determines scan gates and retrieval hints. | Learned retriever/ranker or calibrated model scorer trained against evidence utility. |
| `contamination_flags` as compressor input gate | `scripts/state_space_repo_state_compressor.py:63` | Rule-based leak marker filtering. | Safe as a guardrail, unsafe as a hidden model state constructor because it changes accepted sequence deterministically. | Keep as external admission gate only; model should receive an explicit guard decision, not a filtered shortcut state. |
| `_bounded_choice_role_bucket` and `_bounded_choice_role_key` | `legacy_src/agentkernel_lite/training_loop.py:562`, `legacy_src/agentkernel_lite/training_loop.py:569` | Role enum to small integer bucket. | Direct role bucket can solve option choice without understanding evidence. | Encode option/evidence text through the same learned cross-encoder as the query. |
| `_bounded_choice_evidence_ledger_role_bucket` | `legacy_src/agentkernel_lite/training_loop.py:618` | Evidence role enum to one-hot index. | Hardcoded role labels are injected into option scoring heads. | Learned role inference from visible evidence text, or supervised role head whose output is not used as a shortcut option feature. |
| `_bounded_choice_evidence_judgment_bucket` | `legacy_src/agentkernel_lite/training_loop.py:614` | Evidence judgment literal to class index. | Directly maps semantic answer strings to logits for `bounded_choice_evidence_judgment_head`. | Learned judgment from evidence spans; remove literal-to-index option scoring. |
| `_bounded_choice_semantic_task_bucket` | `legacy_src/agentkernel_lite/training_loop.py:622` | Task type/perspective enum to bucket. | Provides objective identity as a deterministic feature to candidate scoring heads. | Learned task conditioning from prompt/context tokens. |
| `_bounded_choice_semantic_transition_bucket` | `legacy_src/agentkernel_lite/training_loop.py:627` | Transition status string matching. | Status literals like `FAIL_TO_PASS` and `INSUFFICIENT_EVIDENCE` become shortcut features. | Learned verifier-transition predictor from pre-outcome verifier evidence. |
| `_bounded_choice_transition_candidate_task_bucket` | `legacy_src/agentkernel_lite/training_loop.py:721` | Transition task enum bucket. | Direct task identity is concatenated into transition candidate features. | Learned transition-task representation from rendered state. |
| `_bounded_choice_transition_candidate_status_bucket` | `legacy_src/agentkernel_lite/training_loop.py:726` | Verifier/status literal string matching. | Encodes the answer ontology into candidate scoring. | Learned status head over verifier traces and candidate evidence. |
| `_bounded_choice_transition_candidate_artifact_bucket` | `legacy_src/agentkernel_lite/training_loop.py:735` | Artifact type enum bucket. | Candidate type can leak the correct decision policy. | Learned artifact semantics from candidate text and source context. |
| `_bounded_choice_pairwise_features` | `legacy_src/agentkernel_lite/training_loop.py:645` | Query vector, option vector, product, absolute difference, role one-hot. | The vector ops are normal, but the appended role one-hot is deterministic; the handcrafted pair layout is also a fixed scorer design. | Cross-attention option scorer or bi-encoder plus learned interaction head without role one-hot shortcuts. |
| `_bounded_choice_evidence_ledger_features` | `legacy_src/agentkernel_lite/training_loop.py:837` | Query/option pair features plus evidence role one-hot. | Lets the evidence role label dominate evidence-citation choices. | Learned evidence ledger encoder from visible facts. |
| `_bounded_choice_semantic_candidate_features` | `legacy_src/agentkernel_lite/training_loop.py:858` | Query/option pair features plus role, task, transition one-hots. | Injects labels and task/status ontology into scoring heads. | Learned candidate scorer conditioned only on rendered state, evidence, and option text. |
| `_bounded_choice_transition_candidate_features` | `legacy_src/agentkernel_lite/training_loop.py:768` | Query/option pair features plus role, task, status, language, artifact one-hots. | This is the largest shortcut surface: language, role, status, and artifact metadata are deterministic. | Learned transition candidate scorer; metadata can be text-only evidence, not numeric one-hot features. |
| `_bounded_choice_option_logits` branches using deterministic buckets | `legacy_src/agentkernel_lite/training_loop.py:999` | Adds deterministic feature heads to retrieval logits and indexes role/status heads by bucket IDs. | This is where deterministic buckets become logits. | Restrict `bounded_choice_aux_source` to decoder/logit or learned cross-encoder modes until replacement heads are implemented. |
| Dynamic bounded-choice heads | `legacy_src/agentkernel_lite/training_loop.py:3197` through `legacy_src/agentkernel_lite/training_loop.py:3291` | Creates trainable heads whose inputs are deterministic feature dims. | Trainable weights over deterministic buckets do not make the input learned. | Replace with model-native modules whose input is learned token/evidence representations only. |

## P1: Deterministic Text/Packet Builders That Must Not Be Model Authority

| Function or group | Location | Deterministic signal | Required action |
| --- | --- | --- | --- |
| `_option_text_variant`, `_option_texts_for_source`, `_evidence_fact_option_texts` | `legacy_src/agentkernel_lite/training_loop.py:909`, `legacy_src/agentkernel_lite/training_loop.py:935`, `legacy_src/agentkernel_lite/training_loop.py:964` | Templates option text using task, language, role maps, and visible evidence lines. | Keep only as renderer for explicit prompts; do not treat templated variants as separate learned capability evidence. |
| `normalize_features`, `normalize_manifest_rows` | `scripts/feature_normalizer.py:47`, `scripts/feature_normalizer.py:58` | Alias-path extraction into canonical feature maps. | Keep as schema adapter only; prevent `normalized_features` from becoming direct model features without learned encoding. |
| `pack_context`, `evidence_value`, `lost_in_middle_order` | `scripts/context_packer_v1.py:110`, `scripts/context_packer_v1.py:65`, `scripts/context_packer_v1.py:94` | Hardcoded evidence ranking, token budgeting, and ordering. | Use as audit-time packer only; replace training/runtime context selection with learned retrieval/reranking or explicit non-learning guard decisions. |
| `normalize_runtime_trace`, `classify_failure` | `scripts/runtime_trace_normalizer.py:58`, `scripts/runtime_trace_normalizer.py:41` | Regex frames and failure buckets. | Keep normalized trace spans as evidence; replace failure bucket labels with learned verifier/failure classifier if used as targets or features. |
| `detect_bad_output_features`, `choose_repair_route`, `mask_spans`, `build_repair_plan` | `scripts/denoise_diffusion_repair_contract.py:32`, `scripts/denoise_diffusion_repair_contract.py:43`, `scripts/denoise_diffusion_repair_contract.py:57`, `scripts/denoise_diffusion_repair_contract.py:72` | Regex output features and rule-based repair routing. | Keep as safety contract; do not train denoise/repair policy as if this were discovered behavior. |
| `pair_features`, `reranker_logit`, `calibrate_pair` | `scripts/cross_encoder_reranker_calibration.py:49`, `scripts/cross_encoder_reranker_calibration.py:81`, `scripts/cross_encoder_reranker_calibration.py:103` | Jaccard overlap and weighted deterministic reranker. | Replace with actual cross-encoder/reranker; keep this only as baseline telemetry. |
| `normalize_prediction`, `confidence_decision` | `scripts/confidence_ood_head_contract.py:56`, `scripts/confidence_ood_head_contract.py:108` | Softmax/margin/entropy/OOD thresholds and route labels. | Keep as post-hoc calibration audit; do not use threshold route as model training target. |
| `detect_row`, `detect_card` | `scripts/contamination_leakage_detector.py:253`, `scripts/contamination_leakage_detector.py:293` | Rule-based contamination route, label-coded ID detection, heldout overlap flags. | Keep as hard admission guard; never expose route labels as model-visible predictive features. |
| `select_tests`, `candidate_tests_for_change` | `scripts/coverage_test_selection.py:68`, `scripts/coverage_test_selection.py:32` | Path/symbol matching for candidate tests. | Replace test selection policy with learned repo/test relation model or runtime coverage evidence; keep rules as fallback/audit. |
| `scan_text`, `scan_row`, `scan_rows` | `scripts/static_analysis_security_scanner.py:32`, `scripts/static_analysis_security_scanner.py:50`, `scripts/static_analysis_security_scanner.py:55` | Regex security findings and route labels. | Keep as external security gate; do not let route labels become model action labels without independent evidence. |
| `audit_row`, `audit_rows` | `scripts/schema_drift_detector.py:41`, `scripts/schema_drift_detector.py:90` | Schema drift route labels and alias collision detection. | Keep for data validation only. |
| `rank_row_v1` | `scripts/dataset_junk_ood_ranker_v1.py:112` | Rule-based row admission, loss mask, OOD/junk routes. | Keep as quarantine gate; remove from model-supervised objectives unless labels are independently adjudicated. |
| `style_features`, `detect_text`, `detect_row` | `scripts/ngram_repetition_style_detectors.py:32`, `scripts/ngram_repetition_style_detectors.py:59`, `scripts/ngram_repetition_style_detectors.py:103` | N-gram repetition/style metrics and route labels. | Keep as diagnostic; do not train style/repetition behavior directly from route labels. |
| `failure_bucket`, `summarize_failure_buckets`, confidence telemetry helpers | `scripts/training_telemetry_metrics.py:75`, `scripts/training_telemetry_metrics.py:87` | Deterministic failure categories from confidence and output flags. | Keep as telemetry only; not replacement for learned error diagnosis. |

## Structured Head Label Surface To Recheck

`legacy_src/agentkernel_lite/modeling_transformer.py` defines structured heads for fields such as `decoder_budget_ok`, `decode_allowed`, import policies, repo dependency policy, repair surfaces, patch operators, verifier repair, and episode failure fields. These heads are learned modules, but their target labels may come from deterministic functions elsewhere. Before training, verify each label source is source-backed or human/runtime-adjudicated, not generated by the P0/P1 functions above.

Key location: `legacy_src/agentkernel_lite/modeling_transformer.py:12` through `legacy_src/agentkernel_lite/modeling_transformer.py:34`.

## Current Training Args

Deterministic bounded-choice aux sources are no longer exposed as trainer config choices. Current accepted sources:

- `--bounded-choice-aux-source decoder_first_step`
- `--bounded-choice-aux-source encoder_pooled`
- `--bounded-choice-aux-source encoder_pooled_untied_head`
- `--bounded-choice-aux-source encoder_option_biencoder`
- `--bounded-choice-aux-source encoder_option_cross_encoder`

`encoder_option_biencoder` encodes raw option text with the model encoder and scores normalized query/option embeddings. `encoder_option_cross_encoder` adds a learned MLP over query, option, product, and absolute-difference vectors, with no role/task/status/language/artifact one-hot metadata.

## Replacement Acceptance Criteria

- No SHA/hash-derived lexical sketches in model-visible state vectors.
- No role/task/status/language/artifact one-hot metadata concatenated to learned vectors for option scoring.
- No rule route labels used as supervised targets unless they are external guard decisions, not model behavior labels.
- Every structured target has a source provenance tag: `runtime_observed`, `human_adjudicated`, `source_backed_transition`, or `audit_guard_only`.
- Ablation must show performance survives removal of role/status/task/language metadata.
- Any deterministic guard retained must sit outside the model path and log `authority: guard_only`.
