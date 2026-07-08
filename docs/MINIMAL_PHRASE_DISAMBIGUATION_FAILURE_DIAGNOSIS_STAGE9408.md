# Stage9408 Minimal Phrase Disambiguation Failure Diagnosis

Stage9407 preserved the closed-boundary safety contract, but failed the targeted quality gate.

- Target-pair heldout exact: `0` / `4`
- Target-pair boundary: `2` / `4`
- New support exact: `0` / `2`
- Support repetition rows: `['stage9405_phrase_disambig_001_b7b69cd1deaf3ca8']`
- Short/junk rows: `0`
- Leak rows: `0`

Main findings:

- `safety_contract_held`
- `target_pair_exact_regressed_to_zero`
- `expected_assertion_first_boundary_recovered_but_suffix_copied_support`
- `current_repair_invariant_boundary_still_loses_to_answer_focused`
- `new_phrase_support_row_reintroduced_repetition`
- `new_phrase_support_rows_not_self_stable`

Next contract: branch from Stage9397, not Stage9401 or Stage9405. Do not add more surface phrase-text support rows; switch to structured suffix-route disambiguation or a suffix-choice control surface with shortcut audit.
