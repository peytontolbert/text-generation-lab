# Stage10103 Real Session Candidate Competition Bootstrap Packet

Passed: `True`
Materialized rows: `33`
Dropped rows: `6`
Template counts: `{'cpp_file_vs_file': 3, 'python_file_vs_test': 30}`
Drop reasons: `{'insufficient_cpp_code_candidates': 1, 'missing_web_implementation_path': 5}`

This stage turns the stage10102 request into a provisional packet with real source snippets and opaque candidate IDs. It remains review-only: there are still no adjudicated gold labels, Web only partially survives the two-candidate requirement, and Rust is still absent.

Next: Attach maintainer adjudication and gold labels to the materialized packet, then rerun a shortcut baseline on the adjudicated packet before any training or Gemma comparison uses it.
