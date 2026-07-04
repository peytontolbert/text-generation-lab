# Rebuild Control Plane Plan

This is a redundant copy of the high-priority rebuild control-plane plan under the recovery archive.

The immediate recovery order is:

1. Rebuild safety utilities and tests.
2. Rebuild the stage registry and authority flags.
3. Reconstruct stage summaries.
4. Rebuild dataset judge and shortcut audits.
5. Rebuild typed objective manifests.
6. Rebuild trainer modes only after safety passes.
7. Run non-executing audits before any probe.

Hard stop:

```text
No training, decoder CE, runtime, Gemma, harness, checkpoint export, or cleanup-after-probe until safe cleanup tests and final pre-execution audits pass.
```

Central architecture:

```text
safe control plane
-> typed software-state datasets
-> structured transition heads
-> bounded decoder
-> verifier repair loop
-> scale under dataset judge
```

