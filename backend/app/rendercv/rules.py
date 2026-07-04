"""Shared loader for docs/good_resume.md — used by both CV tailoring
(tailor.py) and cover-letter tailoring (letter.py) so the rulebook text and
its path-resolution quirk (Docker mount vs. repo-root-relative, see CLAUDE.md's
M5 gotchas) live in exactly one place.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def good_resume_rules() -> str:
    # Docker: docs/ mounted at /app/docs (see docker-compose.yml); local dev:
    # docs/ lives at the repo root, three levels above this file.
    here = Path(__file__).parent
    for candidate in (here.parent.parent / "docs" / "good_resume.md", here.parent.parent.parent / "docs" / "good_resume.md"):
        if candidate.exists():
            return candidate.read_text()
    raise RuntimeError(
        "docs/good_resume.md not found. In Docker it should be mounted at /app/docs; "
        "locally it should be at <repo root>/docs/good_resume.md."
    )
