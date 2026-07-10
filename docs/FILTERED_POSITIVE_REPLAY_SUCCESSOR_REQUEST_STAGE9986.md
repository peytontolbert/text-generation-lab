# Stage9986 Filtered Positive Replay Successor Request

Passed: `True`
Rows: `117`

Materialized a filtered multilingual successor request that removes only the seven mixed-replay quarantine rows while keeping the four positive replay Gemma-advantage rows available for evaluation.

Next: Run the next direct 100M edit-localization probe on this 124-row filtered manifest to test whether removing mixed-replay quarantine rows recovers python and c_cpp without hurting rust or web.
