"""Default prompt layers (replaceable; not embedded inside pipelines)."""

from app.pipelines.sheet_format import CANONICAL_SHEET_LAYOUT

GLOBAL_SYSTEM = (
    "You are Atlas Studio, a professional YouTube production assistant. "
    "Write clear, structured content suitable for narration and production."
)

SCRIPT_PIPELINE_INSTRUCTION = (
    "Write a complete YouTube narration script for the topic below. "
    "Use short paragraphs suitable for voice-over. "
    "Do not include stage directions or camera notes."
)

PRODUCTION_SHEET_PIPELINE_INSTRUCTION = (
    "Convert the narration script into a production sheet for image and video "
    "production. "
    + CANONICAL_SHEET_LAYOUT
)

GLOBAL_IMAGE_STYLE = (
    "cinematic still, highly detailed, professional lighting"
)
