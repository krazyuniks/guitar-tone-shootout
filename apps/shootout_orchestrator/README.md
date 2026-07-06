# gts-shootout-orchestrator

Shootout orchestrator: consumes `start_shootout` commands from the
`shootout_commands` queue, spawns one SHOOTOUT_AUDIO child job per signal
chain, dispatches them to `audio_commands`, and reconciles the parent shootout
as children complete. Contains no video code (video composition is deferred,
ADR-0007).
