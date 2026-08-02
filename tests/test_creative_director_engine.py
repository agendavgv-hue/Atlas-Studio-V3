"""Creative Director Engine tests — brief + layered prompts (no AI calls)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.channels.models import Channel
from app.channels.studio.service import ChannelStudioService
from app.creative.engine import CreativeDirectorEngine
from app.pipelines.context import ChannelDefaults, PipelineContext
from app.projects.models import Project
from app.prompts.assembler import PromptAssembler


class CreativeDirectorEngineTests(unittest.TestCase):
    def test_brief_and_thumbnail_prompt_use_channel_studio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            studio = ChannelStudioService(root)
            channel = Channel.create_default("Night Orchard")
            channel.description = "Quiet nocturnal nature documentary"
            pack = studio.ensure("Night Orchard", channel=channel)
            pack.general.niche = "nature mystery"
            pack.brand.primary_color = "#102018"
            pack.thumbnail.emotion = "wonder"
            pack.thumbnail.max_words = 3
            pack.image.lighting = "moonlight"
            pack.image.mood = "mystery"
            pack.personality.traits["mystery"] = 95
            pack.personality.traits["wonder"] = 90
            studio.save(pack)

            sample = root / "ref.png"
            sample.write_bytes(b"png")
            studio.add_reference("Night Orchard", "thumbnails", sample)

            engine = CreativeDirectorEngine(root)
            project = Project.create_default(
                name="The Devil's Sea", channel_name="Night Orchard"
            )
            brief = engine.build_brief("Night Orchard", project=project)
            self.assertEqual(brief.channel_name, "Night Orchard")
            self.assertEqual(brief.thumbnail.emotion, "wonder")
            self.assertGreaterEqual(brief.reference_count, 1)

            prompt = engine.create_thumbnail_prompt(
                brief, subject="The Devil's Sea"
            )
            self.assertIn("Night Orchard", prompt)
            self.assertIn("wonder", prompt.casefold())
            self.assertIn("moonlight", prompt.casefold())
            self.assertIn("CREATIVE RULES", prompt)
            self.assertIn("CHANNEL PERSONALITY", prompt)
            self.assertNotIn("Hollow Atlas", prompt)

            report_path = engine.write_report(
                root / "project",
                brief,
                domain="thumbnail",
                master_prompt_text=prompt,
            )
            self.assertTrue(report_path.is_file())

    def test_prompt_assembler_prefers_creative_brief(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            studio = ChannelStudioService(root)
            studio.ensure("Demo Channel")
            pack = studio.load("Demo Channel")
            pack.image.lighting = "golden_hour"
            pack.image.mood = "adventure"
            studio.save(pack)

            engine = CreativeDirectorEngine(root)
            brief = engine.build_brief("Demo Channel")
            project = Project.create_default(
                name="Ancient Harbor", channel_name="Demo Channel"
            )
            context = PipelineContext(
                project=project,
                project_dir=root / "proj",
                channel_defaults=ChannelDefaults(name="Demo Channel"),
                creative_brief=brief,
                data_root=root,
            )
            assembled = PromptAssembler().image_prompt(
                context, "stone harbor at dusk, wet docks"
            )
            self.assertIn("SUBJECT DIRECTOR", assembled.prompt)
            self.assertIn("CREATIVE DIRECTOR", assembled.prompt)
            self.assertIn("golden", assembled.prompt.casefold())
            self.assertNotIn("Hollow Atlas", assembled.prompt)


if __name__ == "__main__":
    unittest.main()
