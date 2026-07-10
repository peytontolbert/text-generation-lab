# Stage10039 Expanded Source-Heldout Same-Manifest Gemma Queue

Passed: `True`
Rows: `95`

Materialized a same-manifest Gemma queue and packet set for the expanded 95-row source-heldout manifest so the next rerun can answer whether the 100M still beats Gemma after adding fresh Python and c_cpp heldout rows.

Next: Run the local Ollama Gemma comparator on this expanded source-heldout same-manifest queue, then compare its rows directly against the matching 100M rerun on the exact 95-row manifest.
