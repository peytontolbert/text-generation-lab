#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STAGE='stage12282_normalized_exact_semantic_review_ingest'
OUT=ROOT/f'runs/local/artifacts/{STAGE}'
SUMMARY=ROOT/f'runs/summaries/{STAGE}.json'
review={"candidate_id":"norm_exact_candidate_76abfa53466349c911dd","decision":"QUARANTINE_INSUFFICIENT_EVIDENCE","concise_reason_code":"semantic_relevance_unproven_post_failure_remains","semantic_verifier_relevance_proven":False,"normalized_same_verifier_ok":True,"patch_effective_enough":False,"external_comparable_countable":False}
summary={'stage':STAGE,'decision':'normalized_exact_review_ingested_zero_admission','reviewed_candidates':1,'decision_counts':{'QUARANTINE_INSUFFICIENT_EVIDENCE':1},'external_comparable_patch_trace_rows':0,'external_fail_to_pass_rows':0,'train_support_rows':0,'training_rows_emitted':0,'next_stage':'stage12283_external_patch_effect_source_scout'}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'normalized_exact_semantic_review_results.jsonl').write_text(json.dumps(review,sort_keys=True)+'\n',encoding='utf-8')
(OUT/'NORMALIZED_EXACT_REVIEW_INGEST_STAGE12282.md').write_text('# Stage12282 Normalized Exact Review Ingest\n\n'+json.dumps(summary,indent=2)+'\n',encoding='utf-8')
(OUT/'normalized_exact_semantic_review_ingest_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
SUMMARY.parent.mkdir(parents=True,exist_ok=True); SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
