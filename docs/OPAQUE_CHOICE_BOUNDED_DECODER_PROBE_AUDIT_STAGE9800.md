# Stage9800 Opaque Choice Bounded Decoder Probe Audit

Passed: `False`
Generated rows: `20`
Valid label rows: `20`
Exact match rows: `4`
Dominant label: `C`
Dominant label rows: `20`
Collapsed single label: `True`

This task-specific audit treats one-token A-E outputs as valid for opaque-choice classification. The failure here is not shortness by itself; it is collapse to a single label and worse behavior than the structured Stage9794 path.

Next: Do not treat the Stage9799 decoder result as a win. Either revise the decoder target format/objective for opaque-choice labels or keep the structured Stage9794 path as the truthful standalone comparator while heldout and expert review proceed.

