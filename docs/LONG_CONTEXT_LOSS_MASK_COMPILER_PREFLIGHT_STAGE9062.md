# Stage9062 Long Context Loss-Mask Compiler Preflight

Passed: `True`

This no-data preflight bridges route-card losses to trainer loss-mask keys. It allows only a future structured-aux preflight after every Stage9061 artifact passes; decoder CE, denoise CE, runtime reward, model execution, and training remain closed.

Route loss keys: `5`
Trainer loss keys: `15`
Negative cases rejected: `True`

Next: Continue no-data recovery by attaching Stage9061-9062 compiler/loss-mask blockers to the central graph and training readiness matrix.
