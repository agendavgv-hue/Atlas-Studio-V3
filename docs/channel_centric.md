# Channel-Centric Architecture

Atlas Studio is a collection of **production studios** (channels). Projects inherit.

## Model

| Layer | Owns |
|-------|------|
| **Channel** | Branding, voice, AI provider/model, prompts, image style, movie/export defaults |
| **Project** | Idea + artifacts + **frozen `channel_snapshot`** at create time |
| **App Settings** | Project Root, API keys / Forge machine, developer tools |

## Snapshot rule

1. New project → copy `ChannelProductionProfile.to_dict()` into `project.channel_snapshot`
2. Production reads the snapshot (not live channel)
3. Older projects without a snapshot freeze the live channel on first open

## UI

- **Channels** → Open Channel → **Channel Dashboard**
- **Channel Settings** — General / Branding / Voice / AI / Images / Movie
- **Channel Studio** — advanced creative packs (unchanged)
- **Global Settings** — app-only; production connections under optional fallbacks

## Future

Export / import / duplicate / backup channel can serialize `channel.json` + studio packs + profile without UI redesign.
