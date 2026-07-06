# Stage8936 CLI Manifest Path Validator Wiring

Passed: `True`

The `manifest_no_mining_audit_only` CLI mode now calls the shared manifest path validator before reading rows. This preserves Stage8934/8935 boundaries while making real local manifest audits usable.

No model execution, mining, runtime, decoder CE, denoise CE, checkpoint, source/body emission, Gemma, harness, scoring, controller merge, or promotion authority was opened.
