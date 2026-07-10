# Stage10059 Hybrid Web Targeted Geometry Successor Packet

Passed: `True`
Fresh source rows: `21`
Successor rows: `124`

Materialized a hybrid successor packet that keeps stage10056 geometry repairs for c_cpp/rust but reverts web to the narrower stage10053 targeted A/C topups, while preserving the stage10047 Python fix.

Next: Run one capped target-100m probe on this hybrid packet to test whether stage10056 rust/cpp recovery can be combined with the stronger stage10053 web behavior without giving back Python.
