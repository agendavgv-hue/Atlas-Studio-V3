# Atlas Studio V3 — Workflow Cleanup & UI Simplification

**Date:** 2026-08-03  
**Type:** Simplification (no feature deletion — disconnect + TODO V3.1)

## Goal

Make Atlas feel like a YouTube production studio, not an AI toolbox.

## What changed

### Sidebar (production only)

| Before | After |
|--------|--------|
| Dashboard, Channels, Channel Studio, Projects, AI Workflow, Thumbnail Review, Design Review, AI Providers, Settings | **Dashboard, Channels, Projects, Settings** |

- Channel Studio opens from **Channels → Open Channel Studio**
- AI Providers embedded in **Settings**
- Thumbnail / Design Review / AI Workflow pages kept on disk, factories retained, **not in nav**

### Thumbnail (V3.1)

Disconnected (code kept):

- Sidebar / review pages
- Project Workspace thumbnail card (hidden)
- One-click `PRODUCTION_STEPS` thumbnail step
- Workflow conductor `thumbnail` / `critic_thumbnail` steps
- Settings Thumbnail Studio card
- Channel Studio Thumbnail section
- Project progress / workflow step labels

Services, models, widgets, and UI modules remain.

### Settings = single AI config home

- Gemini + **AI Providers & Roles** (embedded `AIProvidersPage`)
- Image (Forge), Voice, Movie
- Advanced movie encoding behind a toggle
- Developer Mode under **Advanced**
- Thumbnail Studio card not shown

### Channel Setup Wizard

`app/ui/dialogs/channel_setup_wizard.py` — New Channel asks once for:

name, brand colors, logo, voice style, AI provider/model, image style, prompt template, output folder, resolution  

Stored on `Channel.studio` (+ voice / logo). Editable later via Channel Studio / Settings.

### Production path (unchanged intent)

Project → Script → Sheet → Voice → Images → Movie → Shorts → Export  

No provider/model buttons in the workspace.

## Verify

- Phase 0 shell tests: pass  
- One-click queue tests (without thumbnail): pass  
- Settings / Channels / Workspace construct offscreen: pass  

## Restore later

Search: `TODO V3.1` / `Restore Thumbnail Generator`
