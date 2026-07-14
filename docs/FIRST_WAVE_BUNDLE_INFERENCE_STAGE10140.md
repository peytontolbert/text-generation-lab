# Stage10140 First-Wave Bundle Inference

This runner executes the Stage10139 payload.

Use the `trellis` Python interpreter for real 100M execution:

```bash
/home/peyton/miniconda3/envs/trellis/bin/python scripts/run_stage10140_first_wave_bundle_inference.py --skip-gemma
```

It:

1. runs preserved 100M standalone prompt generation
2. runs local Ollama Gemma on the same prompts
3. summarizes bundle predictions
4. writes Stage10081 machine artifacts through the existing adapter

## Commands

Compile payload:

```bash
python scripts/build_stage10139_first_wave_bundle_runtime_payload.py
```

Dry-run inference:

```bash
python scripts/run_stage10140_first_wave_bundle_inference.py --dry-run
```

Full inference:

```bash
/home/peyton/miniconda3/envs/trellis/bin/python scripts/run_stage10140_first_wave_bundle_inference.py
```

Standalone 100M only:

```bash
/home/peyton/miniconda3/envs/trellis/bin/python scripts/run_stage10140_first_wave_bundle_inference.py --skip-gemma
```

## Current Boundary

The runner expects the `trellis` environment or another usable PyTorch runtime for real 100M execution.

If those are not available in the current shell environment, the runner still supports:

- prompt compilation
- Gemma execution
- dry-run machine-artifact writeback validation
