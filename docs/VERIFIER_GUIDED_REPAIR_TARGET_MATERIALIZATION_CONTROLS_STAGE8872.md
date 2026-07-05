# Stage8872 Verifier-Guided Repair Target Materialization Controls

Passed: `True`

Rows: `648`
Materialized rows: `648`
Target-store rows: `648`
Denoise CE eligible now rows: `0`
Runtime verifier execution eligible now rows: `0`
Training loss rows: `0`
Authority rows: `0`

Verifier repair target text is stored only in the target-store artifact. The model-visible manifest carries target refs, hashes, and lengths only. Denoise CE, runtime, decoder CE, source/body emission, Gemma, harness, scoring, and promotion remain closed.
