# Stage9269 Target-100M Denoise Probe Diagnostic Audit

The denoise-only probe ran on Stage9267 repair rows with decoder CE, runtime, Gemma, harness, scoring, and checkpoint export closed.

Train loss: 81.10128784179688 -> 29.631534576416016
Eval loss: 59.46769332885742
Strict eval loss: 53.38161849975586
Pre-clip grad max: 179.8817138671875
Post-clip grad max: 1.0000003977847067
Structured head delta norm: 0.0

This is a CE-level repair probe only. It does not authorize bounded decoder CE reruns or product/harness integration.
