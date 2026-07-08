# Stage9237 Source-Backed Bounded Decoder Tiny Package

Passed: `True`

Rows: `64`
Splits: `{'eval': 16, 'strict_eval': 16, 'train': 32}`
Target hash unique rows: `64`
Cross-split duplicate target hashes: `0`
Authority rows: `0`
Unsafe loss rows: `0`
Target-ref placeholder rows: `0`
Target text copied to input rows: `0`

This stage repairs the Stage9236 placeholder-target blocker by compiling real bounded `decoder_text` rows from the Stage8806 source-backed target store. It does not execute the trainer and does not authorize decoder training beyond a future explicit tiny preflight/probe.

Next: Run contract-only preflight on the Stage9237 source-backed tiny bounded decoder manifest; do not execute until preflight passes.

