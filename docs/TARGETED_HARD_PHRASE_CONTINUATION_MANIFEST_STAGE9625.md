# Stage9625 Targeted Hard Phrase Continuation Manifest

Passed: `True`
Rows: `22`
Splits: `{'train': 15, 'eval': 4, 'strict_eval': 3}`
Buckets: `{'localized_repair_step': 10, 'relevant_repair_region': 6, 'checked_verifier_condition': 6}`

Rows clone the existing safe suffix-ladder schema and change only the visible generation prefix to the hard phrase boundary. Full clean targets remain hidden from model input; decoder CE/runtime/Gemma/harness/promotion remain closed.

Next: Build Stage9626 tri-phase hard-phrase reconnect contract preflight using Stage9625 as phase2 warm-up and Stage9609 full suffix ladder as phase3.
