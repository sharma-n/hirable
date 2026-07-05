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

# M8 analytics: stages that unconditionally represent a genuine employer
# response. "Rejected" is deliberately excluded here — it only counts as a
# response when the transition's actor isn't "automation" (an
# automation-caused Rejected means the application was ghosted, not that the
# employer replied) — see analytics/service.py's _is_response_event.
RESPONSE_STAGES: frozenset[str] = frozenset(
    {"Recruiter Screen", "Technical", "Onsite", "Offer", "Accepted", "Declined"}
)

# The ordered pipeline stages tracked by the funnel chart. Declined/Rejected
# are terminal negative outcomes, not further funnel progress, so they're
# excluded here (unlike RESPONSE_STAGES, which is about detecting *any*
# reply).
FUNNEL_STAGES: tuple[str, ...] = (
    "Applied",
    "Recruiter Screen",
    "Technical",
    "Onsite",
    "Offer",
    "Accepted",
)

# Stages that imply an offer was made (Accepted/Declined both presuppose one).
OFFER_STAGES: frozenset[str] = frozenset({"Offer", "Accepted", "Declined"})


def validate_stage(stage: str) -> None:
    if stage not in STAGES:
        raise ValueError(f"Invalid stage {stage!r} — valid stages are: {', '.join(STAGES)}")
