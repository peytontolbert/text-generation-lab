# Incident And Recovery Safety

This document records the workspace deletion incident and the safety rules required before resuming model execution.

## Incident Summary

During the bounded decoder CE tiny probe, cleanup code attempted to remove the checkpoint directory.

The cleanup path resolved to `.`.

It called:

```python
shutil.rmtree(".")
```

from inside:

```text
/data/agentkernel-seq2seq-text-lab
```

This deleted the workspace contents.

## Unsafe Code Pattern

Never use:

```python
checkpoint_dir = Path(str(manifest.get("training_summary", {}).get("checkpoint_dir", "") or ""))
if checkpoint_dir.exists():
    shutil.rmtree(checkpoint_dir)
```

`Path("")` resolves as `.`.

## Safe Cleanup Contract

Before deleting anything, require:

```text
candidate path is not empty
candidate path is absolute after resolve()
candidate path exists
candidate path.name == "checkpoints"
candidate path is inside output_dir
candidate path != output_dir
candidate path != repo_root
candidate path != "."
candidate path != "/"
candidate path is not a symlink escaping output_dir
```

If any check fails, abort.

## Safer Cleanup Pseudocode

```python
def safe_remove_checkpoint_dir(raw_checkpoint_dir: str, *, output_dir: Path, repo_root: Path) -> dict:
    if not raw_checkpoint_dir:
        raise SystemExit("Refusing cleanup: empty checkpoint path")

    output_dir = output_dir.resolve()
    repo_root = repo_root.resolve()
    checkpoint_dir = Path(raw_checkpoint_dir).resolve()

    if checkpoint_dir.name != "checkpoints":
        raise SystemExit(f"Refusing cleanup: unexpected checkpoint basename {checkpoint_dir.name!r}")
    if checkpoint_dir == output_dir:
        raise SystemExit("Refusing cleanup: checkpoint path is output_dir")
    if checkpoint_dir == repo_root:
        raise SystemExit("Refusing cleanup: checkpoint path is repo_root")
    if checkpoint_dir == Path("/"):
        raise SystemExit("Refusing cleanup: checkpoint path is root")
    if output_dir not in checkpoint_dir.parents:
        raise SystemExit("Refusing cleanup: checkpoint path is outside output_dir")
    if repo_root == checkpoint_dir or repo_root in checkpoint_dir.parents:
        # This should not happen for the intended output-dir/checkpoints path.
        raise SystemExit("Refusing cleanup: checkpoint path includes repo root boundary incorrectly")

    if checkpoint_dir.exists():
        shutil.rmtree(checkpoint_dir)

    return {
        "checkpoint_dir": str(checkpoint_dir),
        "checkpoint_dir_exists_after_cleanup": checkpoint_dir.exists(),
    }
```

The exact implementation should be audited before use.

## Recovery Sources Found

Possible local sources:

```text
/data/agentkernel/scripts/train_agentkernel_lite_encdec.py
/data/agent_kernel_lite/scripts/train_agentkernel_lite_encdec.py
/data/transformer_10/scripts/agent_kernel_lite/train_agentkernel_lite_encdec.py
```

Possible recovery directories:

```text
/data/agentkernel
/data/agent_kernel_lite
/data/transformer_10
/data/tmp
/tmp
```

## No More Execution Until

Do not run any model/training command until:

```text
repo restored
cleanup code patched
cleanup code audited
bounded decoder command regenerated
pre-execution audit passes
output directory is isolated
checkpoint cleanup proof is non-destructive
```

## Immediate Recovery Priorities

1. Restore repository contents from the safest local or remote source.
2. Preserve this recovery docs directory.
3. Patch cleanup safety.
4. Rebuild stage registry if possible.
5. Recreate bounded decoder branch artifacts if missing.
6. Rerun only static audits first.
7. Resume tiny probe only after cleanup hardening.

