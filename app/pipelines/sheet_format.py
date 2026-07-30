"""Canonical Production Sheet format — single contract for generate + parse.

Image Pipeline, Movie duration, and Shorts selection all consume this shape
via ``app.pipelines.sheet_prompts`` only. Do not add parallel parsers.
"""

from __future__ import annotations

# Instruction fragment embedded in PromptAssembler defaults.
# Keep in sync with ``app.pipelines.sheet_prompts``.
CANONICAL_SHEET_LAYOUT = (
    "Use this exact plain-text layout for every scene "
    "(1-based index, zero-padded to two digits):\n"
    "\n"
    "IMAGE 01\n"
    "Duration: <seconds>\n"
    "Narration: <short narration excerpt>\n"
    "Prompt: <one-line Stable Diffusion image prompt>\n"
    "\n"
    "IMAGE 02\n"
    "Duration: <seconds>\n"
    "Narration: <short narration excerpt>\n"
    "Prompt: <one-line Stable Diffusion image prompt>\n"
    "\n"
    "Rules:\n"
    "- Emit one IMAGE block per scene, in order.\n"
    "- Every block MUST include a Prompt: line with a concrete visual prompt.\n"
    "- Do not use markdown headings (###), bullets, or bold markers.\n"
    "- Do not replace Prompt: with Visual: or Suggested Image Prompt:.\n"
    "- Plain text only."
)

# Minimal example used by tests / docs — must yield prompts via extract_image_prompts.
CANONICAL_SHEET_EXAMPLE = (
    "IMAGE 01\n"
    "Duration: 5\n"
    "Narration: Opening over the ruins.\n"
    "Prompt: Aerial view of ancient ocean ruins at dawn, cinematic lighting\n"
    "\n"
    "IMAGE 02\n"
    "Duration: 4\n"
    "Narration: Closer to the statue.\n"
    "Prompt: Close-up of a bronze statue covered in seaweed, dramatic light\n"
    "\n"
    "IMAGE 03\n"
    "Duration: 3\n"
    "Narration: Harbor lights.\n"
    "Prompt: Ancient harbor at dusk with glowing lanterns, wide shot\n"
)
