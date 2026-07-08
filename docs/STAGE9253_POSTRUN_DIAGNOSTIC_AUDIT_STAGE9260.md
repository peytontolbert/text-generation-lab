# Stage9260 Stage9253 Post-Run Diagnostic Audit

Stage9253 executed the authorized target-100M bounded decoder CE probe.

Execution safety passed: True
Decoder quality passed: False
Train loss: 84.26806640625 -> 25.03672981262207
Eval / strict loss: 24.623144149780273 / 24.91276741027832
Contentful generation rate: 0.0
Unterminated generation rate: 1.0
Degenerate repetition rate: 0.4375

Conclusion: the target 100M transformer path is executable and receives CE gradients, but the decoder generation gate still fails. Do not scale rows yet.
