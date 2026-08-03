# Workflow-First Project Details

Atlas guides production inside **Project Details** (the former Project Workspace).

## What the user always sees

1. **One primary action** — next step only (`Generate Script`, `Generate Voice-over`, …, `Generate Everything`, `Production Complete`)
2. **Progress panel** — percent bar + checklist (Script → Sheet → Voice → Images → Movie → Shorts → Export)
3. **Production asset cards** — Type · Status · Generate · Open · Reveal Folder · Regenerate

## Stage states

| State | Meaning |
|-------|---------|
| Not started | Asset not Ready yet |
| In progress | Pipeline / TaskManager job running |
| Completed | Tracked asset Ready (or Approved) |
| Failed | Last run failed (retry via Generate) |

Source of truth: `assets.json` via `AssetRegistry` → `scan_workflow()`. See [asset_centric.md](asset_centric.md).

## Surfaces

- **Project Details** — production hub
- **Projects list** — `%` + next step per project
- **Dashboard** — active channel/project next step

## Extending

Add a `ProductionStageDef` / `AssetSpec` row (set `visible=True`). Thumbnail remains `visible=False` for V3.1.
