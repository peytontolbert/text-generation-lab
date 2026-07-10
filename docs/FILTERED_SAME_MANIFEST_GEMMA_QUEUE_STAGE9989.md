# Stage9989 Filtered Same Manifest Gemma Queue

Passed: `True`
Rows: `117`

Materialized a same-manifest Gemma queue and packet set for the filtered stage9986 successor manifest so the stage9987 frontier can be compared fairly against Gemma3 12B.

Next: Run the local Ollama Gemma comparator on this filtered same-manifest queue, then compare its rows directly against stage9987.
