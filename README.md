# AgentKernel Seq2Seq Text Lab Recovery

This workspace is in recovery mode after a destructive cleanup incident during the v2.7 100M bounded decoder branch.

Start here:

- [Recovery rebuild plan](docs/RECOVERY_REBUILD_PLAN.md)
- [Current reconstructed research spine](docs/CURRENT_RESEARCH_SPINE_RECONSTRUCTED.md)
- [Recovery checklist](docs/RECOVERY_CHECKLIST.md)
- [No destructive commands policy](docs/NO_DESTRUCTIVE_COMMANDS_POLICY.md)
- [Stage8587 reconstructed incident audit](runs/summaries/stage8587_reconstructed_workspace_loss_incident_audit.json)
- [Archived session recovery](docs/ARCHIVED_SESSION_RECOVERY.md)
- [Recovered Stage8530-8587 timeline](docs/RECOVERED_STAGE8530_8587_TIMELINE.md)
- [Scripts and configs recovery inventory](docs/SCRIPTS_AND_CONFIGS_RECOVERY_INVENTORY.md)
- [Recovery progress: control loop rebuild](docs/RECOVERY_PROGRESS_CONTROL_LOOP_REBUILD.md)
- [Session recovery hit summary](runs/local/artifacts/session_recovery/stage8530_8589_session_hit_summary.json)
- [Session recovery hit index](runs/local/artifacts/session_recovery/stage8530_8589_session_hit_index.jsonl)

Current rule: rebuild safety and control-plane artifacts before any trainer, model execution, decoder CE, runtime harness, Gemma comparison, checkpoint export, or dataset scale-up.

## Recovery Source Notes

External read-only recovery snapshots from GitHub and Hugging Face are documented in `docs/GITHUB_HF_RECOVERY_SOURCES.md`. These sources help recover legacy trainer/dataset/timeline material, but they do not open training/runtime/decode authority and they do not replace the Stage8580+ safety contracts recovered from local sessions.

