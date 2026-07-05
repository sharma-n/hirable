"""M8: analytics computations (SPEC §10) over a user's applications/events.

``compute_analytics`` is the single entry point — it fetches this user's
``Application`` rows once (with their ``events``/``documents``/``job``
relationships) and derives every metric from that in Python. A handful of
small, DB-free helpers hold the arithmetic that's easy to get wrong on empty
data (division by zero, empty-list medians).
"""
from __future__ import annotations

import statistics
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.applications.stages import FUNNEL_STAGES, OFFER_STAGES, RESPONSE_STAGES, STAGES, ACTIVE_STAGES
from app.db.models import Application, ApplicationDocument, ApplicationEvent, Document
from app.schemas import (
    AnalyticsOut,
    ApplicationsOverTimePointOut,
    BreakdownGroupOut,
    CvVersionPerformanceOut,
    FunnelStageOut,
    StatusCountsOut,
)


def _pct(numerator: int, denominator: int) -> float:
    """Guarded division — 0.0 rather than raising on an empty cohort."""
    return numerator / denominator if denominator else 0.0


def _as_utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo on readback even for DateTime(timezone=True)
    columns (see app/applications/automation.py's identical pattern)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _is_response_event(to_stage: str, actor: str) -> bool:
    """A genuine employer response — Rejected only counts when it wasn't the
    scheduler's own ghosting-driven transition (see stages.py's
    RESPONSE_STAGES docstring)."""
    if to_stage in RESPONSE_STAGES:
        return True
    return to_stage == "Rejected" and actor != "automation"


def _median_days(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _first_response_event(application: Application):
    """The earliest event matching _is_response_event, or None. Application.events
    is already ordered ascending by `at` (see the model's relationship order_by)."""
    for event in application.events:
        if _is_response_event(event.to_stage, event.actor):
            return event
    return None


def compute_analytics(db: Session, user_id: str) -> AnalyticsOut:
    applications = db.query(Application).filter_by(user_id=user_id).all()
    submitted = [a for a in applications if a.submitted_at is not None]
    # Computed once and reused everywhere "did this application respond?"
    # matters (response rate, median time-to-response, cv-version/breakdown
    # response rates), instead of re-scanning each application's events per use.
    first_response = {a.id: _first_response_event(a) for a in submitted}

    funnel = _compute_funnel(submitted)
    responded_count = sum(1 for event in first_response.values() if event is not None)
    response_rate = _pct(responded_count, len(submitted))
    median_time_to_first_response_days = _median_days(
        [
            (_as_utc(event.at) - _as_utc(a.submitted_at)).total_seconds() / 86400
            for a in submitted
            if (event := first_response[a.id]) is not None
        ]
    )
    applications_over_time = _compute_applications_over_time(submitted)
    status_counts = _compute_status_counts(applications)
    offered = [
        a for a in submitted if any(e.to_stage in OFFER_STAGES for e in a.events)
    ]
    offer_rate = _pct(len(offered), len(submitted))
    cv_version_performance = _compute_cv_version_performance(db, user_id, submitted, first_response)
    by_company_type = _compute_breakdown(submitted, "company_type", first_response)
    by_location = _compute_breakdown(submitted, "location", first_response)

    return AnalyticsOut(
        funnel=funnel,
        response_rate=response_rate,
        median_time_to_first_response_days=median_time_to_first_response_days,
        applications_over_time=applications_over_time,
        status_counts=status_counts,
        offer_rate=offer_rate,
        cv_version_performance=cv_version_performance,
        by_company_type=by_company_type,
        by_location=by_location,
    )


def _compute_funnel(submitted: list[Application]) -> list[FunnelStageOut]:
    total = len(submitted)
    result: list[FunnelStageOut] = []
    for stage in FUNNEL_STAGES:
        if stage == "Applied":
            # submitted_at is only ever set in the same transition_stage call
            # that writes the Applied event, so this is exactly the "ever
            # reached Applied" count without re-scanning events.
            count = total
        else:
            count = sum(1 for a in submitted if any(e.to_stage == stage for e in a.events))
        result.append(FunnelStageOut(stage=stage, count=count, pct_of_applied=_pct(count, total)))
    return result


def _compute_applications_over_time(submitted: list[Application]) -> list[ApplicationsOverTimePointOut]:
    counts = Counter(_as_utc(a.submitted_at).strftime("%Y-%m") for a in submitted)
    return [
        ApplicationsOverTimePointOut(month=month, count=count)
        for month, count in sorted(counts.items())
    ]


def _compute_status_counts(applications: list[Application]) -> StatusCountsOut:
    counts = Counter(a.stage for a in applications)
    by_stage = {stage: counts.get(stage, 0) for stage in STAGES}
    return StatusCountsOut(
        by_stage=by_stage,
        active=sum(by_stage[s] for s in ACTIVE_STAGES),
        stale=by_stage["Stale"],
        rejected=by_stage["Rejected"],
        offers=by_stage["Offer"],
    )


def _compute_cv_version_performance(
    db: Session, user_id: str, submitted: list[Application], first_response: dict[str, ApplicationEvent | None]
) -> list[CvVersionPerformanceOut]:
    cv_docs = (
        db.query(ApplicationDocument, Document.version)
        .join(Document, ApplicationDocument.document_id == Document.id)
        .join(Application, ApplicationDocument.application_id == Application.id)
        .filter(Application.user_id == user_id, ApplicationDocument.doc_type == "cv")
        .all()
    )
    version_by_application_id = {ad.application_id: version for ad, version in cv_docs}

    by_version: dict[int, list[Application]] = {}
    for a in submitted:
        version = version_by_application_id.get(a.id)
        if version is None:
            continue
        by_version.setdefault(version, []).append(a)

    result: list[CvVersionPerformanceOut] = []
    for version, apps in sorted(by_version.items()):
        response_count = sum(1 for a in apps if first_response[a.id] is not None)
        result.append(
            CvVersionPerformanceOut(
                version=version,
                submitted_count=len(apps),
                response_count=response_count,
                response_rate=_pct(response_count, len(apps)),
            )
        )
    return result


def _compute_breakdown(
    submitted: list[Application], parsed_key: str, first_response: dict[str, ApplicationEvent | None]
) -> list[BreakdownGroupOut]:
    groups: dict[str, list[Application]] = {}
    for a in submitted:
        key = a.job.parsed.get(parsed_key) or "Unknown"
        groups.setdefault(key, []).append(a)

    result: list[BreakdownGroupOut] = []
    for key, apps in sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True):
        response_count = sum(1 for a in apps if first_response[a.id] is not None)
        result.append(
            BreakdownGroupOut(
                key=key,
                count=len(apps),
                response_count=response_count,
                response_rate=_pct(response_count, len(apps)),
            )
        )
    return result
