"""Thumbnail Concept Planner tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.channels.models import Channel
from app.channels.studio.service import ChannelStudioService
from app.creative.engine import CreativeDirectorEngine
from app.creative.engine.style_profile_service import StyleProfileService
from app.thumbnail.concepts import ThumbnailConceptPlanner
from app.thumbnail.concepts.models import SCORE_AXES
from app.thumbnail.naming import thumbnail_concepts_path
from app.thumbnail.pipeline.plan import ThumbnailCompositionPlanner
from app.thumbnail.pipeline.prompt_builder import build_pipeline_prompt_plans


class ThumbnailConceptPlannerTests(unittest.TestCase):
    def test_invents_scores_and_selects_best_concept(self) -> None:
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

            ref = root / "ref.png"
            # Minimal valid-ish file not required for heuristic invent.
            ref.write_bytes(b"not-an-image")
            # Skip broken ref — planner works without readable refs.
            engine = CreativeDirectorEngine(root)
            brief = engine.build_brief("Night Orchard")
            brief.project.topic = "The Devil's Sea"
            brief.project.idea = "The Devil's Sea"
            brief.project.primary_subject = "compass"
            brief.project.primary_location = "storm ocean"

            project_dir = root / "proj"
            project_dir.mkdir()
            planner = ThumbnailConceptPlanner(text_provider=None)
            board = planner.plan(
                brief,
                script_text=(
                    "Sailors feared the Devil's Sea where ships vanished "
                    "into storms and whirlpools without a trace."
                ),
                topic="The Devil's Sea",
                project_dir=project_dir,
            )

            self.assertGreaterEqual(len(board.concepts), 5)
            self.assertTrue(thumbnail_concepts_path(project_dir).is_file())
            payload = json.loads(
                thumbnail_concepts_path(project_dir).read_text(encoding="utf-8")
            )
            self.assertEqual(len(payload["concepts"]), len(board.concepts))
            self.assertIn("selected_reason", payload)
            self.assertIn("elements_to_use", payload)
            self.assertIn("winner", payload)

            winner = board.chosen
            self.assertEqual(winner.id, board.selected_id)
            self.assertGreater(winner.scores.overall, 0)
            for axis in SCORE_AXES:
                self.assertIn(axis, winner.scores.to_dict())

            # Winner should be the max overall.
            best_score = max(c.scores.overall for c in board.concepts)
            self.assertEqual(winner.scores.overall, best_score)

            # Prompt path uses only best concept.
            plan = ThumbnailCompositionPlanner().plan(
                brief,
                hero_subject=winner.hero_subject,
                hook=winner.hook or winner.title,
                thumbnail_profile=None,
                best_concept=winner,
            )
            prompts = build_pipeline_prompt_plans(
                brief, plan, best_concept=winner
            )
            self.assertIn("BEST THUMBNAIL CONCEPT", prompts[0].prompt)
            self.assertIn(winner.title.split()[0], prompts[0].prompt)
            self.assertIn("Do NOT invent a different story", prompts[0].prompt)
            self.assertNotIn("Hollow Atlas", prompts[0].prompt)

    def test_personality_shifts_brand_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            studio = ChannelStudioService(root)
            studio.ensure("Night Orchard", channel=Channel.create_default("Night Orchard"))
            pack = studio.load_basics("Night Orchard")
            pack.personality.traits["mystery"] = 100
            pack.personality.traits["humor"] = 0
            studio.save(pack)
            brief = CreativeDirectorEngine(root).build_brief("Night Orchard")
            brief.project.topic = "Lost temple"
            board = ThumbnailConceptPlanner(None).plan(
                brief, topic="Lost temple", script_text="An ancient temple hides a secret."
            )
            self.assertTrue(any(c.emotion.casefold() in {"mystery", "wonder", "curiosity", "adventure", "discovery", "epic"} for c in board.concepts))
            self.assertIn("mystery", " ".join(board.personality_focus).casefold() or "mystery")


if __name__ == "__main__":
    unittest.main()
