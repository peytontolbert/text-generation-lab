# No Destructive Commands Policy

This workspace is in recovery mode after a destructive cleanup/path-resolution incident.

## Absolute Rules

Do not run commands that can delete or overwrite broad paths:

```text
rm -rf
find ... -delete
shutil.rmtree(repo_root)
shutil.rmtree(".")
shutil.rmtree(output_dir.parent)
git clean -fdx
git reset --hard
```

Do not run cleanup manually through shell commands.

All cleanup must go through:

```text
scripts/safe_cleanup.py
scripts/safe_paths.py
```

## Cleanup Requirements

Cleanup is allowed only when all are true:

```text
repo_root is explicit
output_dir is under repo_root
cleanup target is a child under output_dir/checkpoints
cleanup marker exists
marker contains run_id
candidate is not repo_root
candidate is not output_dir
candidate is not parent of output_dir
candidate is not /
candidate is not /data
candidate is not a symlink escape
```

## Current Test Proof

The current guard is covered by:

```text
pytest -q tests/test_safe_cleanup.py
```

Current recovered result:

```text
8 passed
```

## Recovery Mode Rule

Until the repo, registry, and non-executing audits are rebuilt, no model execution, decoder CE probe, runtime harness, Gemma comparison, checkpoint export, or cleanup-after-probe is authorized.
