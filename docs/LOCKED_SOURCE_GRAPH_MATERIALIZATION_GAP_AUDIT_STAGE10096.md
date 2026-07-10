# Stage10096 Locked Source Graph Materialization Gap Audit

Passed: `True`
Locked rows: `18`
Matched source rows: `18`
Rows with `source_graph_materialized=false`: `18`

The locked-source subset is honest about heldout provenance, but it is still not enough to build a maintainer-grade packet directly. Every matched row still marks `source_graph_materialized=false`, and the graph/query handles remain opaque.

Next: build a graph-materialization bridge that resolves those opaque handles into file paths, trace chains, and snippet spans.
