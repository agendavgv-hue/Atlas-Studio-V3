"""Scene Director unit tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.channels.models import Channel
from app.channels.studio.service import ChannelStudioService
from app.creative.engine import CreativeDirectorEngine
from app.thumbnail.naming import scene_blueprint_path
from app.thumbnail.pipeline.plan import ThumbnailCompositionPlanner
from app.thumbnail.pipeline.prompt_builder import build_pipeline_prompt_plans
from app.thumbnail.scene_director import SceneDirectorService
from app.thumbnail.scene_director.models import SceneBlueprint
from app.thumbnail.scene_director.store import read_scene_blueprint


class SceneDirectorTests(unittest.TestCase):
    def test_invents_scores_and_writes_blueprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            studio = ChannelStudioService(root)
            channel = Channel.create_default("Night Orchard")
            pack = studio.ensure("Night Orchard", channel=channel)
            pack.brand.primary_color = "#102018"
            pack.thumbnail.emotion = "mystery"
            pack.personality.traits = {
                "mystery": 100,
                "wonder": 90,
                "history": 80,
                "adventure": 70,
                "science": 60,
                "luxury": 40,
                "darkness": 85,
                "fantasy": 10,
                "humor": 0,
                "fear": 40,
                "hope": 30,
                "epic": 75,
            }
            pack.story.mystery = 90
            pack.story.wonder = 80
            studio.save(pack)

            brief = CreativeDirectorEngine(root).build_brief("Night Orchard")
            brief.project.topic = "The Devil's Sea"
            brief.project.idea = "The Devil's Sea"
            brief.project.primary_subject = "compass"
            brief.project.primary_location = "storm ocean"

            project_dir = root / "proj"
            project_dir.mkdir()
            director = SceneDirectorService(text_provider=None)
            blueprint = director.direct(
                brief,
                script_text=(
                    "Sailors feared the Devil's Sea where ships vanished "
                    "into storms and whirlpools without a trace. "
                    "One explorer found a compass that spun toward an impossible direction."
                ),
                topic="The Devil's Sea",
                project_dir=project_dir,
            )

            self.assertGreaterEqual(len(blueprint.candidates), 5)
            self.assertTrue(blueprint.meets_minimum_rules())
            self.assertTrue(blueprint.main_subject)
            self.assertTrue(blueprint.secondary_subject)
            self.assertTrue(blueprint.background)
            self.assertTrue(blueprint.emotion)
            self.assertGreaterEqual(len(blueprint.story.split()), 8)
            self.assertTrue(blueprint.selection_reason)
            self.assertTrue(scene_blueprint_path(project_dir).is_file())

            payload = json.loads(
                scene_blueprint_path(project_dir).read_text(encoding="utf-8")
            )
            self.assertIn("selection_reason", payload)
            self.assertIn("why_this_scene", payload)
            self.assertIn("Main Subject", payload)
            self.assertIn("Story", payload)
            self.assertGreaterEqual(len(payload.get("candidates") or []), 5)

            loaded = read_scene_blueprint(project_dir)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.story, blueprint.story)
            self.assertEqual(loaded.selected_scene_id, blueprint.selected_scene_id)

            plan = ThumbnailCompositionPlanner().plan(
                brief,
                hero_subject=blueprint.main_subject,
                hook=blueprint.title,
                scene_blueprint=blueprint,
            )
            self.assertEqual(plan.main_subject, blueprint.main_subject)
            self.assertEqual(plan.secondary_subject, blueprint.secondary_subject)
            self.assertIn(blueprint.story.split()[0], plan.story_focus)

            prompts = build_pipeline_prompt_plans(
                brief, plan, scene_blueprint=blueprint
            )
            primary = prompts[0].prompt
            self.assertIn("SCENE BLUEPRINT", primary)
            self.assertIn("Do NOT generate a lone object", primary)
            self.assertIn(blueprint.main_subject.split()[0], primary)
            self.assertNotIn("Hollow Atlas", primary)

    def test_rejects_thin_lone_object_blueprint(self) -> None:
        thin = SceneBlueprint(
            main_subject="",
            secondary_subject="compass",
            background="",
            emotion="",
            story="compass",
        )
        self.assertFalse(thin.meets_minimum_rules())


if __name__ == "__main__":
    unittest.main()
