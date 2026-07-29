"""Default write names for newly generated artifacts.

Lookup must never require these names — use ``ArtifactResolver`` instead.
Pipelines may still write these defaults for fresh V3 output.
"""

SCRIPT_FILENAME = "script.txt"
PRODUCTION_SHEET_FILENAME = "production_sheet.txt"
SCRIPT_FOLDER = "script"
