# Stage9609 Suffix Continuation Ladder Manifest

Passed: `True`
Rows: `52`
Ladder counts: `{'prefix_5_words': 26, 'prefix_8_words': 26}`
Splits: `{'train': 40, 'eval': 6, 'strict_eval': 6}`

This manifest extends Stage9605 with two active prefix lengths per clean row. It targets the Stage9608 failure mode: the model gets the prefix and first suffix token but repeats local fragments before completing the suffix.

Decoder CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: Run Stage9610 contract-only preflight for the suffix-continuation ladder manifest before another tiny execution.
