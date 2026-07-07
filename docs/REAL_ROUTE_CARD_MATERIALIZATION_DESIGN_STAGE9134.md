# Stage9134 Real Route-Card Materialization Design

Passed: `True`

Designs the non-executing bridge from judge/ranker outputs to real route cards.

Required inputs:

- `objective_rows_jsonl`
- `judge_rows_jsonl`
- `junk_ranker_rows_jsonl`
- `shortcut_baseline_card_json`
- `counterfactual_obligation_card_json`
- `source_lineage_card_json`

Required outputs:

- `route_cards.jsonl`
- `route_card_materialization_audit.json`
- `route_reason_counts.json`
- `route_cell_card.json`
- `route_to_loss_ready_blocker_card.json`

Next: Audit real route-card materialization design before implementing any real route-card runner.
