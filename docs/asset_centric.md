# Asset-Centric Production

A project is a **collection of tracked production assets**, not an arbitrary folder of files.

## Inventory

Each project stores `assets.json` beside `project.json`. Every generated item is a tracked asset with:

| Field | Meaning |
|-------|---------|
| Type | Script, Production Sheet, Voice, Image, Movie, Short, Export, Thumbnail… |
| Status | Not started → Queued → In progress → Ready / Failed (Approved reserved) |
| Created / Updated | UTC timestamps |
| Version | Increments on regenerate when already Ready |
| Location | Project-relative path |
| Generator | Pipeline id that produced it |

## Core assets

Script · Production Sheet · Voice-over · Image 01…N · Movie · Short 1 · Short 2 · Export Package · Thumbnail (hidden until V3.1)

Image slots are created when the production sheet succeeds (or when image generation starts).

## Status ownership

1. **First open / empty inventory** — one-time disk reconcile seeds Ready from existing files.
2. **After that** — pipelines update asset status via `AssetRegistry.record_pipeline_result`.
3. Workflow progress (`scan_workflow`) and Project Details cards read **assets**, not folder scans.

Hook points:

- `ProductionEngine.execute` — marks started + records result
- Export verify (TaskManager callable) — records `export` result

## Project Details

Shows **Production Assets** cards with identical actions:

Generate · Regenerate · Open · Reveal Folder

(Version History reserved for a later release.)

## Future-ready (no redesign)

Asset model already carries room for: Approval · Version compare · Asset history · Cloud sync · Publishing.
