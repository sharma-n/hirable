from __future__ import annotations

# The full application-stage pipeline (SPEC §9). Stored as a plain string
# column (see Document.type / ProfileVersion.source for the same convention)
# rather than a DB enum.
STAGES: tuple[str, ...] = (
    "Draft",
    "Applied",
    "Recruiter Screen",
    "Technical",
    "Onsite",
    "Offer",
    "Accepted",
    "Declined",
    "Rejected",
    "Stale",
)

# Stages the automation tracks for staleness — a submitted, not-yet-terminal
# application. Draft (never submitted) and the terminal stages are excluded.
ACTIVE_STAGES: frozenset[str] = frozenset(
    {"Applied", "Recruiter Screen", "Technical", "Onsite", "Offer"}
)

# Stages eligible for the auto-reject (ghosted) check — active stages plus
# Stale itself (a Stale application that keeps getting no response eventually
# auto-rejects too).
STALE_OR_ACTIVE: frozenset[str] = ACTIVE_STAGES | {"Stale"}


def validate_stage(stage: str) -> None:
    if stage not in STAGES:
        raise ValueError(f"Invalid stage {stage!r} — valid stages are: {', '.join(STAGES)}")
