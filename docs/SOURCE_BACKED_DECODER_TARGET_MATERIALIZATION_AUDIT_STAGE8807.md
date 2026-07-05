# Stage8807 Source-Backed Decoder Target Materialization Audit

Passed: `True`

Rows: `504`
Materialized rows: `360`
Blocked rows: `144`
Target-store rows: `360`
Target text copied to manifest rows: `0`
CE eligible now rows: `0`
Cross-split duplicate target hashes: `120`

The duplicate target hashes are not an authority failure here because CE remains closed, but they are an explicit future CE blocker until deduped or split-specific materialization is designed.
