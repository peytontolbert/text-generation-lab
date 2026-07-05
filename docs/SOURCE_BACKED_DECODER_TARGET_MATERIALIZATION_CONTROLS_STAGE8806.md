# Stage8806 Source-Backed Decoder Target Materialization Controls

Passed: `True`

Rows: `504`
Materialized rows: `360`
Blocked rows: `144`
Target-store rows: `360`
Decoder CE eligible now rows: `0`
Training loss rows: `0`
Authority rows: `0`

Decoder target text is stored only in the target-store artifact. The model-visible manifest carries target refs, hashes, and lengths, and all decoder CE/runtime authority remains closed.
