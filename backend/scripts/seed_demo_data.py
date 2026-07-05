#!/usr/bin/env python3
"""
Seed hirable's demo account with realistic M8 analytics data.

Usage:
    cd backend && uv run python scripts/seed_demo_data.py

Creates/overwrites app/data/hirable.db with a single admin account (demo@hirable.dev),
a master profile (Jordan Kim / Staff ML Engineer from examples/mle_engineer.yaml),
28 seeded jobs, and 25 submitted applications distributed across a realistic funnel
with CV-version performance variance, automation ghosting, and non-trivial breakdowns.

The script is idempotent: running it again will cleanly wipe and recreate the demo account.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

# Add app/ to path so we can import
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.auth.password import hash_password
from app.applications.service import finalize_documents
from app.applications.stages import ACTIVE_STAGES
from app.config import rendercv_theme, tracking_stale_after_days, tracking_auto_reject_after_days
from app.db.engine import SessionLocal
from app.db.migrate import run_migrations
from app.db.models import (
    Application, ApplicationEvent, ApplicationDocument, Document, Job, Profile, Resume, User
)
from app.llm.schemas import (
    ContactInfo, EducationItem, EnrichmentItem, ExperienceItem, ExtrasItem,
    ProfileModel, ProjectItem, SkillItem, TailoredCoverLetter, TailoredCV,
    TailoredEducationEntry, TailoredExperienceEntry, TailoredEntry,
)
from app.rendercv.build import build_rendercv_yaml
from app.rendercv.letter import build_cover_letter_yaml


def load_mle_profile_yaml() -> dict:
    """Load examples/mle_engineer.yaml (relative to the repo root)."""
    repo_root = Path(__file__).parent.parent.parent
    yaml_path = repo_root / "examples" / "mle_engineer.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Could not find {yaml_path}")
    return yaml.safe_load(yaml_path.read_text())


def yaml_to_profile_model(cv_dict: dict) -> ProfileModel:
    """Convert RenderCV YAML to ProfileModel shape."""
    cv = cv_dict.get("cv", {})
    sections = cv.get("sections", {})

    contact = ContactInfo(
        name=cv.get("name", ""),
        headline=cv.get("headline", ""),
        email=cv.get("email", ""),
        phone=cv.get("phone", ""),
        location=cv.get("location", ""),
        website=cv.get("website", ""),
        social_networks=[
            {"network": n.get("network", ""), "username": n.get("username", "")}
            for n in cv.get("social_networks", [])
        ],
    )

    summary_lines = sections.get("Summary", sections.get("summary", []))
    summary = " ".join(summary_lines) if isinstance(summary_lines, list) else str(summary_lines)

    experience = [
        ExperienceItem(
            company=e.get("company", ""),
            position=e.get("position", ""),
            start_date=e.get("start_date", ""),
            end_date=e.get("end_date", ""),
            date=e.get("date", ""),
            location=e.get("location", ""),
            summary=e.get("summary", ""),
            highlights=e.get("highlights", []),
            tech=[],
        )
        for e in sections.get("Experience", [])
    ]

    projects = [
        ProjectItem(
            name=p.get("name", ""),
            link=p.get("link", ""),
            start_date=p.get("start_date", ""),
            end_date=p.get("end_date", ""),
            date=p.get("date", ""),
            location=p.get("location", ""),
            summary=p.get("summary", ""),
            highlights=p.get("highlights", []),
            tech=[],
        )
        for p in sections.get("Projects", [])
    ]

    education = [
        EducationItem(
            institution=e.get("institution", ""),
            area=e.get("area", ""),
            degree=e.get("degree", ""),
            start_date=e.get("start_date", ""),
            end_date=e.get("end_date", ""),
            date=e.get("date", ""),
            location=e.get("location", ""),
            highlights=e.get("highlights", []),
        )
        for e in sections.get("Education", [])
    ]

    skills = [
        SkillItem(label=s.get("label", ""), details=s.get("details", ""))
        for s in sections.get("Skills", [])
    ]

    extras = [
        ExtrasItem(title=e.get("name", ""), highlights=e.get("highlights", []))
        for e in sections.get("Extras", [])
    ]

    # Add enrichment items to showcase that feature
    enrichment = [
        EnrichmentItem(key="Target Role", value="Staff/Principal ML Engineer, Infrastructure focus"),
        EnrichmentItem(key="Work Authorization", value="US Citizen, no sponsorship needed"),
        EnrichmentItem(key="Salary Expectation", value="$250K–$350K + equity (top-of-band)"),
    ]

    return ProfileModel(
        contact=contact,
        summary=summary,
        experience=experience,
        projects=projects,
        education=education,
        skills=skills,
        extras=extras,
        enrichment=enrichment,
    )


def create_synthetic_job_models() -> list[tuple[str, dict]]:
    """Return (company, parsed_dict) tuples for 28 realistic MLE target jobs."""
    jobs_data = [
        ("OpenAI", "Senior ML Infrastructure Engineer", "San Francisco, CA", "startup"),
        ("Anthropic", "Staff ML Systems Engineer", "San Francisco, CA", "startup"),
        ("Google", "Senior ML Infrastructure Engineer", "Mountain View, CA", "enterprise"),
        ("Google", "Staff ML Engineer, Google Cloud", "Mountain View, CA", "enterprise"),
        ("Meta", "Senior ML Systems Engineer", "Menlo Park, CA", "enterprise"),
        ("Meta", "Staff ML Engineer", "Menlo Park, CA", "enterprise"),
        ("Microsoft", "Principal ML Engineer", "Redmond, WA", "enterprise"),
        ("Microsoft", "Senior ML Infrastructure Engineer", "Redmond, WA", "enterprise"),
        ("Apple", "Senior ML Engineer", "Cupertino, CA", "enterprise"),
        ("Tesla", "Staff ML Engineer", "Palo Alto, CA", "enterprise"),
        ("DeepSeek", "Senior ML Systems Engineer", "Hangzhou, China", "startup"),
        ("xAI", "Staff ML Engineer", "Memphis, TN", "startup"),
        ("Hugging Face", "Senior ML Engineer", "San Francisco, CA", "scaleup"),
        ("Perplexity", "Staff ML Engineer", "San Francisco, CA", "scaleup"),
        ("Together AI", "Senior ML Systems Engineer", "San Francisco, CA", "scaleup"),
        ("Modal", "Senior ML Infrastructure Engineer", "San Francisco, CA", "startup"),
        ("Replicate", "Staff ML Engineer", "San Francisco, CA", "startup"),
        ("Scale AI", "Senior ML Engineer", "San Francisco, CA", "scaleup"),
        ("Weights & Biases", "Staff ML Systems Engineer", "San Francisco, CA", "scaleup"),
        ("Ray (Anyscale)", "Senior ML Engineer", "San Francisco, CA", "scaleup"),
        ("Lambda Labs", "Senior ML Engineer", "San Francisco, CA", "startup"),
        ("CoreWeave", "Staff ML Infrastructure Engineer", "New York, NY", "scaleup"),
        ("Crusoe Energy", "Senior ML Engineer", "San Francisco, CA", "scaleup"),
        ("Lightning AI", "Senior ML Systems Engineer", "San Francisco, CA", "startup"),
        ("Fireworks AI", "Staff ML Engineer", "San Francisco, CA", "startup"),
        ("Mistral AI", "Senior ML Engineer", "Paris, France", "startup"),
        ("Databricks", "Staff ML Engineer", "San Francisco, CA", "scaleup"),
        ("Nvidia", "Principal ML Architect", "Santa Clara, CA", "enterprise"),
    ]

    jobs_models = []
    for company, title, location, company_type in jobs_data:
        parsed = {
            "company": company,
            "title": title,
            "location": location,
            "responsibilities": [
                "Design and implement production ML infrastructure",
                "Optimize model serving for scale and cost",
                "Lead ML platform engineering initiatives",
            ],
            "must_have": [
                "7+ years ML systems/infrastructure experience",
                "Production deployment experience",
                "Python, C++, or Go proficiency",
            ],
            "nice_to_have": [
                "ML frameworks (PyTorch, TensorFlow) expertise",
                "Kubernetes and distributed systems knowledge",
                "Research background",
            ],
            "keywords": ["ML Infrastructure", "Model Serving", "Distributed Systems", "Python", "Kubernetes"],
            "why_opened_guess": "Building next-generation ML infrastructure",
            "seniority": "staff",
            "company_type": company_type,
            "team_name": "ML Infrastructure / AI Platform",
            "team_description": "Building the infrastructure that powers AI at scale",
        }
        jobs_models.append((f"{company} - {title}", parsed))

    return jobs_models


def backdated_transition_stage(
    db: Session,
    application: Application,
    to_stage: str,
    at: datetime,
    actor: str = "user",
    note: str | None = None,
) -> None:
    """Transition application stage with a custom timestamp (unlike the real transition_stage)."""
    from_stage = application.stage

    if from_stage != to_stage:
        db.add(
            ApplicationEvent(
                application_id=application.id,
                from_stage=from_stage,
                to_stage=to_stage,
                at=at,
                note=note,
                actor=actor,
            )
        )
        application.stage = to_stage

    if actor != "automation":
        application.last_activity_at = at
        stale_days = tracking_stale_after_days()
        application.auto_stale_at = (
            at + timedelta(days=stale_days) if to_stage in ACTIVE_STAGES else None
        )

    if to_stage == "Applied" and application.submitted_at is None:
        application.submitted_at = at
        finalize_documents(db, application)

    application.updated_at = at
    db.commit()


def create_demo_account(db: Session) -> tuple[User, Profile]:
    """Create or recreate the demo account. Idempotent — deletes existing if found."""
    existing = db.query(User).filter_by(email="demo@hirable.dev").first()
    if existing:
        db.delete(existing)
        db.commit()

    user = User(email="demo@hirable.dev", password_hash=hash_password("DemoPass123!"), role="admin")
    db.add(user)
    db.commit()
    db.refresh(user)

    # Load profile from example YAML
    yaml_dict = load_mle_profile_yaml()
    profile_model = yaml_to_profile_model(yaml_dict)

    profile_data = profile_model.model_dump()
    profile = Profile(user_id=user.id, version=1, data=profile_data)
    db.add(profile)

    # Add a resume row so the account looks like it went through the normal flow
    resume = Resume(
        user_id=user.id,
        filename="Jordan_Kim_Resume.pdf",
        format="pdf",
        raw_text="Senior ML Engineer resume — 9+ years ML systems & infrastructure (Google/Lyft/Uber)",
    )
    db.add(resume)

    db.commit()
    db.refresh(profile)
    return user, profile


def create_seeded_jobs(db: Session, user_id: str) -> list[Job]:
    """Create 28 job rows with full parsed JobModel data."""
    job_models = create_synthetic_job_models()
    jobs = []

    for job_title, parsed_dict in job_models:
        job = Job(
            user_id=user_id,
            source_url=f"https://example.com/jobs/{len(jobs) + 1}",
            raw_text=f"Exciting opportunity: {job_title} at {parsed_dict['company']}. "
                    f"Help us build the next-generation {parsed_dict['team_description']}. "
                    f"Join a team of world-class engineers.",
            parsed=parsed_dict,
        )
        db.add(job)
        jobs.append(job)

    db.commit()
    for job in jobs:
        db.refresh(job)

    return jobs


def create_seeded_applications(
    db: Session,
    user_id: str,
    jobs: list[Job],
    profile: Profile,
) -> None:
    """Create 28 applications: 3 Draft, 25 submitted with engineered funnel stages."""
    today = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)
    theme = rendercv_theme()

    # Helper to create "include everything" TailoredCV
    def make_tailored_cv(profile_data: dict, job_parsed: dict) -> TailoredCV:
        return TailoredCV(
            summary="",  # Fall back to profile's summary
            section_order=["experience", "projects", "education", "skills"],
            skills=profile_data.get("skills", []),
            experience=[
                TailoredExperienceEntry(index=i, include=True)
                for i in range(len(profile_data.get("experience", [])))
            ],
            projects=[
                TailoredEntry(index=i)
                for i in range(len(profile_data.get("projects", [])))
            ],
            education=[
                TailoredEducationEntry(index=i)
                for i in range(len(profile_data.get("education", [])))
            ],
            publications=list(range(len(profile_data.get("publications", [])))),
            extras=list(range(len(profile_data.get("extras", [])))),
        )

    # Helper to create synthetic cover letter
    def make_tailored_letter(job_parsed: dict) -> TailoredCoverLetter:
        company = job_parsed.get("company", "Company")
        title = job_parsed.get("title", "Role")
        return TailoredCoverLetter(
            worth_it=company not in ["Meta", "Google", "Microsoft"],  # Smaller/not mega-corp
            recipient="Hiring Manager",
            salutation="Dear Hiring Manager,",
            body_paragraphs=[
                f"I am excited about the opportunity to join {company}'s team as a {title}. "
                f"Your work on {job_parsed.get('team_description', 'ML infrastructure')} aligns perfectly with my career goals.",
                f"In my 9+ years building ML systems at scale (Google, Lyft, Uber), I have specialized in the exact areas your role covers: "
                f"{', '.join(job_parsed.get('keywords', [])[:3])}. At Uber, I built ensemble forecasting models handling 10B+ trips; "
                f"at Lyft, I architected real-time feature pipelines with 100K events/sec throughput; at Google, I led a team optimizing Vertex AI's inference orchestration.",
                f"I would relish the opportunity to bring this expertise to {company} and help accelerate your ML infrastructure evolution. "
                f"Thank you for considering my application.",
            ],
            closing="Best regards,",
        )

    # Funnel distribution: 3 Draft, then 25 submitted across a realistic pipeline
    draft_jobs = jobs[:3]
    submitted_jobs = jobs[3:]

    # Create draft applications
    for job in draft_jobs:
        app = Application(user_id=user_id, job_id=job.id, stage="Draft")
        db.add(app)

    db.commit()

    # Funnel stages for submitted jobs (ordered by time and outcome)
    funnel_spec = [
        # Successful outcomes
        ("Accepted", submitted_jobs[0], today - timedelta(days=3)),
        ("Declined", submitted_jobs[1], today - timedelta(days=5)),
        # Pending offers
        ("Offer", submitted_jobs[2], today - timedelta(days=1)),
        # In-process pipeline
        ("Onsite", submitted_jobs[3], today - timedelta(days=0)),
        ("Onsite", submitted_jobs[4], today - timedelta(days=0)),
        ("Technical", submitted_jobs[5], today - timedelta(days=2)),
        ("Technical", submitted_jobs[6], today - timedelta(days=2)),
        ("Recruiter Screen", submitted_jobs[7], today - timedelta(days=4)),
        ("Recruiter Screen", submitted_jobs[8], today - timedelta(days=4)),
        ("Recruiter Screen", submitted_jobs[9], today - timedelta(days=5)),
        # Fresh applications (no response yet)
        ("Applied", submitted_jobs[10], today - timedelta(days=3)),
        ("Applied", submitted_jobs[11], today - timedelta(days=5)),
        ("Applied", submitted_jobs[12], today - timedelta(days=8)),
        ("Applied", submitted_jobs[13], today - timedelta(days=10)),
        # Rejections (real, count as responses)
        ("Rejected", submitted_jobs[14], today - timedelta(days=15)),  # After Recruiter Screen
        ("Rejected", submitted_jobs[15], today - timedelta(days=15)),  # After Recruiter Screen
        ("Rejected", submitted_jobs[16], today - timedelta(days=20)),  # After Technical
        ("Rejected", submitted_jobs[17], today - timedelta(days=20)),  # After Technical
        ("Rejected", submitted_jobs[18], today - timedelta(days=25)),  # After Onsite
        ("Rejected", submitted_jobs[19], today - timedelta(days=28)),  # Quick ATS rejection
        # Stale (ghosted, 15–30 days)
        ("Stale", submitted_jobs[20], today - timedelta(days=20)),  # Marked stale
        ("Stale", submitted_jobs[21], today - timedelta(days=25)),  # Marked stale
        # Automation-rejected (ghosted >30 days, excludes from response rate)
        ("Rejected", submitted_jobs[22], today - timedelta(days=35)),  # Auto-rejected
        ("Rejected", submitted_jobs[23], today - timedelta(days=35)),  # Auto-rejected
        ("Rejected", submitted_jobs[24], today - timedelta(days=40)),  # Auto-rejected
    ]

    # CV version tracking: 8 of the 25 have v2 revisions (with better outcomes)
    v2_indices = {0, 1, 2, 3, 4, 5, 6, 13}  # High-outcome + one fresh

    created_apps = []
    for stage, job, submit_time in funnel_spec:
        app = Application(user_id=user_id, job_id=job.id, stage="Draft")
        db.add(app)
        db.commit()
        db.refresh(app)
        created_apps.append((app, stage, job, submit_time))

    # Now populate documents and stage transitions
    for idx, (app, final_stage, job, submit_time) in enumerate(created_apps):
        # Create CV(s) — v1 for all, v2 for some
        tailored = make_tailored_cv(profile.data, job.parsed)
        cv_yaml = build_rendercv_yaml(profile.data, tailored, job.parsed, theme)

        cv_v1 = Document(
            user_id=user_id,
            job_id=job.id,
            type="cv",
            source_text=cv_yaml,
            version=1,
        )
        db.add(cv_v1)
        db.commit()

        # Create v2 for selected jobs (before Applied transition, so finalize_documents picks it up)
        cv_version_for_submit = 1
        if idx in v2_indices:
            cv_v2 = Document(
                user_id=user_id,
                job_id=job.id,
                type="cv",
                source_text=cv_yaml,  # Same YAML for simplicity
                version=2,
            )
            db.add(cv_v2)
            db.commit()
            cv_version_for_submit = 2

        # Create cover letter (always v1)
        tailored_letter = make_tailored_letter(job.parsed)
        letter_yaml = build_cover_letter_yaml(profile.data, tailored_letter, theme)
        letter = Document(
            user_id=user_id,
            job_id=job.id,
            type="cover_letter",
            source_text=letter_yaml,
            version=1,
        )
        db.add(letter)
        db.commit()

        # Transition: Draft → Applied (with backdated submission)
        backdated_transition_stage(db, app, "Applied", submit_time, actor="user")

        # Then transition to final stage(s)
        if final_stage == "Accepted":
            backdated_transition_stage(db, app, "Recruiter Screen", submit_time + timedelta(days=2))
            backdated_transition_stage(db, app, "Technical", submit_time + timedelta(days=5))
            backdated_transition_stage(db, app, "Onsite", submit_time + timedelta(days=10))
            backdated_transition_stage(db, app, "Offer", submit_time + timedelta(days=15))
            backdated_transition_stage(db, app, "Accepted", submit_time + timedelta(days=16))
        elif final_stage == "Declined":
            backdated_transition_stage(db, app, "Recruiter Screen", submit_time + timedelta(days=2))
            backdated_transition_stage(db, app, "Technical", submit_time + timedelta(days=5))
            backdated_transition_stage(db, app, "Onsite", submit_time + timedelta(days=9))
            backdated_transition_stage(db, app, "Offer", submit_time + timedelta(days=13))
            backdated_transition_stage(db, app, "Declined", submit_time + timedelta(days=14))
        elif final_stage == "Offer":
            backdated_transition_stage(db, app, "Recruiter Screen", submit_time + timedelta(days=2))
            backdated_transition_stage(db, app, "Technical", submit_time + timedelta(days=4))
            backdated_transition_stage(db, app, "Onsite", submit_time + timedelta(days=8))
            backdated_transition_stage(db, app, "Offer", submit_time + timedelta(days=11))
        elif final_stage == "Onsite":
            backdated_transition_stage(db, app, "Recruiter Screen", submit_time + timedelta(days=2))
            backdated_transition_stage(db, app, "Technical", submit_time + timedelta(days=4))
            backdated_transition_stage(db, app, "Onsite", submit_time + timedelta(days=8))
        elif final_stage == "Technical":
            backdated_transition_stage(db, app, "Recruiter Screen", submit_time + timedelta(days=2))
            backdated_transition_stage(db, app, "Technical", submit_time + timedelta(days=5))
        elif final_stage == "Recruiter Screen":
            backdated_transition_stage(db, app, "Recruiter Screen", submit_time + timedelta(days=2))
        elif final_stage == "Rejected":
            # Determine which stage the rejection came after
            if idx == 19:  # Quick ATS rejection
                pass  # Stay at Applied
            elif idx in {14, 15}:  # After Recruiter Screen
                backdated_transition_stage(db, app, "Recruiter Screen", submit_time + timedelta(days=2))
                backdated_transition_stage(db, app, "Rejected", submit_time + timedelta(days=3))
            elif idx in {16, 17}:  # After Technical
                backdated_transition_stage(db, app, "Recruiter Screen", submit_time + timedelta(days=2))
                backdated_transition_stage(db, app, "Technical", submit_time + timedelta(days=5))
                backdated_transition_stage(db, app, "Rejected", submit_time + timedelta(days=6))
            elif idx == 18:  # After Onsite
                backdated_transition_stage(db, app, "Recruiter Screen", submit_time + timedelta(days=2))
                backdated_transition_stage(db, app, "Technical", submit_time + timedelta(days=4))
                backdated_transition_stage(db, app, "Onsite", submit_time + timedelta(days=8))
                backdated_transition_stage(db, app, "Rejected", submit_time + timedelta(days=9))
            else:  # Auto-rejected
                reject_time = submit_time + timedelta(days=tracking_auto_reject_after_days())
                backdated_transition_stage(db, app, "Rejected", reject_time, actor="automation")
        elif final_stage == "Stale":
            stale_time = submit_time + timedelta(days=tracking_stale_after_days())
            backdated_transition_stage(db, app, "Stale", stale_time, actor="automation")


def main():
    """Seed the demo database."""
    print("🌱 Seeding hirable demo account...")

    # 1. Initialize database
    print("  ✓ Running migrations...")
    run_migrations()

    # 2. Create session
    db = SessionLocal()

    try:
        # 3. Create user + profile
        print("  ✓ Creating demo account (demo@hirable.dev)...")
        user, profile = create_demo_account(db)

        # 4. Create jobs
        print("  ✓ Creating 28 job postings...")
        jobs = create_seeded_jobs(db, user.id)

        # 5. Create applications with funnel
        print("  ✓ Seeding applications with realistic funnel...")
        create_seeded_applications(db, user.id, jobs, profile)

        # Summary
        print("\n" + "=" * 60)
        print("✅ Demo account created successfully!")
        print("=" * 60)
        print(f"\nLogin credentials:")
        print(f"  Email:    demo@hirable.dev")
        print(f"  Password: DemoPass123!")
        print(f"\nProfile: {profile.data['contact']['name']}")
        print(f"  {profile.data['contact']['headline']}")
        print(f"\nApplications seeded:")
        print(f"  Total jobs:         28")
        print(f"  Draft applications: 3")
        print(f"  Submitted:          25")
        print(f"\nFunnel (submitted apps):")
        print(f"  Applied:            25 (100%)")
        print(f"  Recruiter Screen:   15 (60%)")
        print(f"  Technical:          10 (40%)")
        print(f"  Onsite:             6 (24%)")
        print(f"  Offer:              3 (12%)")
        print(f"  Accepted:           1 (4%)")
        print(f"\nOutcomes:")
        print(f"  Accepted:           1")
        print(f"  Declined by user:   1")
        print(f"  Offer (pending):    1")
        print(f"  In-process:         12 (Screen/Technical/Onsite)")
        print(f"  Too recent:         4 (Applied, <15 days)")
        print(f"  Rejected:           4 (real rejections)")
        print(f"  Stale/Ghosted:      2")
        print(f"  Auto-rejected:      3 (>30 days idle)")
        print(f"\nCV Versions:")
        print(f"  v1 only:           17 applications")
        print(f"  v1 + v2:           8 applications (higher success rate)")
        print(f"\nStart the app: cd backend && uv run uvicorn app.main:app --port 8000 --reload")

    finally:
        db.close()


if __name__ == "__main__":
    main()
