# Stage8939 BitNet Layout Decoder Contract

Passed: `True`

This stage defines metadata-only packed BitNet layout assertions. It infers a 2-bit/four-values-per-byte packing from file sizes and target shapes for non-vocab packed rows, isolates the lm_head source-vocab mismatch, and does not read tensor values, decode packed weights, dequantize, load a checkpoint, write a checkpoint, run a model, train, or execute runtime.

Packed rows: `109`
Shape assertion failures: `1`
