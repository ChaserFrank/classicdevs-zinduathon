"""python manage.py seed_demo — a complete, idempotent demo dataset.

1 admin, 2 companies, 3 recruiters (1 pending), 6 job seekers whose analyses are produced by the
real pipeline from the demo personas (no network), 2 job postings, shortlists, feedback,
profile views and notifications. Running it again changes nothing. No email or SMS is sent.
"""

import os

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import GithubAccount, JobSeekerProfile, Role, User
from apps.accounts.services import record_consents
from apps.analysis import demo
from apps.analysis.models import Analysis, ClaimedSkill
from apps.analysis.services import pipeline
from apps.analysis.services.github import GithubClient, NullCache
from apps.companies.models import ApprovalStatus, Company, RecruiterProfile
from apps.notifications.services import ensure_defaults, outbound_muted
from apps.recruiting.models import (
    Feedback,
    JobPosting,
    JobRequiredSkill,
    ProfileView,
    ShortlistEntry,
)
from apps.recruiting.services import feedback as feedback_service
from apps.skills.models import Skill

ADMIN = ("admin@skillproof.demo", "Demo Admin")
COMPANIES = [
    ("Savanna Fintech", "https://savanna.example", "Nairobi", True),
    ("Mawingu Labs", "https://mawingu.example", "Kisumu", False),
]
RECRUITERS = [
    (
        "grace@savanna.demo",
        "Grace Achieng",
        "Savanna Fintech",
        "Engineering manager",
        ApprovalStatus.APPROVED,
    ),
    (
        "david@mawingu.demo",
        "David Mutua",
        "Mawingu Labs",
        "Talent partner",
        ApprovalStatus.APPROVED,
    ),
    ("pending@mawingu.demo", "Peter Pending", "Mawingu Labs", "Recruiter", ApprovalStatus.PENDING),
]
SEEKERS = {
    "amina-demo": (
        "Full-stack developer",
        "Nairobi",
        ["React", "TypeScript", "Django", "Kubernetes"],
    ),
    "brian-demo": ("Aspiring data analyst", "Nakuru", ["Python", "Data analysis", "SQL"]),
    "chebet-demo": (
        "Machine learning engineer",
        "Eldoret",
        ["Python", "Machine learning", "FastAPI", "Docker"],
    ),
    "kipkorir-demo": ("Backend engineer (Go)", "Nairobi", ["Go", "PostgreSQL", "Docker"]),
    "njeri-demo": ("Junior frontend developer", "Mombasa", ["React", "TypeScript", "Vue.js"]),
    "otieno-demo": ("Node.js developer", "Kisumu", ["Node.js", "Express", "MongoDB", "NestJS"]),
}


class Command(BaseCommand):
    help = "Create (or top up) the demo dataset. Idempotent; sends no email or SMS."

    def handle(self, *args, **options):
        password = os.environ.get("DEMO_PASSWORD", "SkillProof-demo-2026")
        with outbound_muted():
            with transaction.atomic():
                admin = self._user(*ADMIN, Role.ADMIN, password)
                companies = self._companies()
                recruiters = self._recruiters(password, companies, admin)
                seekers = self._seekers(password)
            self._analyses(seekers, admin)  # each analysis commits on its own
            with transaction.atomic():
                jobs = self._jobs(recruiters, companies)
                self._activity(recruiters, seekers, jobs)
        self._print(password)

    # --- Users ---

    def _user(self, email, name, role, password, **extra) -> User:
        user = User.objects.filter(email=email).first()
        if user is None:
            create = (
                User.objects.create_superuser if role == Role.ADMIN else User.objects.create_user
            )
            user = create(
                email,
                password,
                full_name=name,
                role=role,
                email_verified_at=timezone.now(),
                **extra,
            )
            record_consents(
                user, {"terms": True, "email_feedback": True, "sms_feedback": "phone" in extra}
            )
            ensure_defaults(user)
        return user

    def _companies(self) -> dict[str, Company]:
        out = {}
        for name, website, location, verified in COMPANIES:
            out[name], _ = Company.objects.get_or_create(
                name=name,
                defaults={"website": website, "location": location, "is_verified": verified},
            )
        return out

    def _recruiters(self, password, companies, admin) -> dict[str, User]:
        out = {}
        for email, name, company, title, status in RECRUITERS:
            user = self._user(email, name, Role.RECRUITER, password)
            RecruiterProfile.objects.get_or_create(
                user=user,
                defaults={
                    "company": companies[company],
                    "job_title": title,
                    "approval_status": status,
                    "reviewed_by": admin if status == ApprovalStatus.APPROVED else None,
                    "reviewed_at": timezone.now() if status == ApprovalStatus.APPROVED else None,
                },
            )
            out[email] = user
        return out

    def _seekers(self, password) -> dict[str, JobSeekerProfile]:
        out = {}
        for i, login in enumerate(demo.persona_names()):
            persona = demo.load_persona(login)
            headline, location, claims = SEEKERS.get(login, ("Developer", "Nairobi", []))
            first = login.split("-")[0]
            phone = (
                {"phone": f"+2547000000{i + 10:02d}", "phone_verified_at": timezone.now()}
                if i % 2 == 0
                else {}
            )
            user = self._user(
                f"{first}@jobseeker.demo",
                persona.get("name") or first.title(),
                Role.JOB_SEEKER,
                password,
                **phone,
            )
            profile, _ = JobSeekerProfile.objects.get_or_create(
                user=user, defaults={"headline": headline, "location": location}
            )
            GithubAccount.objects.get_or_create(
                user=user, defaults={"github_id": 9_000_000 + persona.get("id", i), "login": login}
            )
            if not profile.claimed_skills.exists():
                names = dict(Skill.objects.values_list("name", "name"))
                for position, text in enumerate(claims):
                    ClaimedSkill.objects.create(
                        job_seeker=profile,
                        raw_text=text,
                        position=position,
                        skill=Skill.objects.filter(name=names.get(text)).first(),
                    )
            out[login] = profile
        return out

    def _analyses(self, seekers, admin) -> None:
        session = demo.ReplaySession([demo.load_persona(n) for n in seekers])
        for login, profile in seekers.items():
            if Analysis.objects.filter(
                github_login=login, status="completed", job_seeker=profile
            ).exists():
                continue
            Analysis.objects.filter(github_login=login, status__in=("queued", "running")).delete()
            analysis = Analysis.objects.create(
                github_login=login, job_seeker=profile, triggered_by=admin
            )
            pipeline.run(analysis, client=GithubClient("", session=session, cache=NullCache()))
            analysis.refresh_from_db()
            self.stdout.write(
                f"  analysed {login}: {analysis.status} "
                f"{analysis.signal_score or analysis.error_code}"
            )

    # --- Recruiting activity ---

    def _jobs(self, recruiters, companies) -> dict[str, JobPosting]:
        specs = [
            (
                "grace@savanna.demo",
                "Backend engineer (Python/Django)",
                "hybrid",
                [
                    ("Python", "strong", 3),
                    ("Django", "moderate", 2),
                    ("Testing", "moderate", 2),
                    ("Docker", "emerging", 1),
                ],
            ),
            (
                "david@mawingu.demo",
                "Frontend developer (React)",
                "remote",
                [
                    ("React", "moderate", 3),
                    ("TypeScript", "moderate", 2),
                    ("Testing", "emerging", 1),
                ],
            ),
        ]
        out = {}
        for email, title, remote, skills in specs:
            recruiter = recruiters[email]
            job, created = JobPosting.objects.get_or_create(
                title=title,
                company=recruiter.recruiter_profile.company,
                defaults={
                    "created_by": recruiter,
                    "status": "open",
                    "remote_policy": remote,
                    "location": "Nairobi",
                    "description": "Demo posting created by seed_demo.",
                },
            )
            if created:
                for name, label, weight in skills:
                    JobRequiredSkill.objects.create(
                        job_posting=job,
                        skill=Skill.objects.get(name=name),
                        minimum_label=label,
                        weight=weight,
                    )
            out[title] = job
        return out

    def _activity(self, recruiters, seekers, jobs) -> None:
        grace, david = recruiters["grace@savanna.demo"], recruiters["david@mawingu.demo"]
        backend = jobs["Backend engineer (Python/Django)"]
        frontend = jobs["Frontend developer (React)"]
        shortlist = [
            (grace, "amina-demo", backend, "interview"),
            (grace, "chebet-demo", backend, "saved"),
            (david, "njeri-demo", frontend, "contacted"),
        ]
        for recruiter, login, job, stage in shortlist:
            ShortlistEntry.objects.get_or_create(
                recruiter=recruiter,
                job_seeker=seekers[login],
                job_posting=job,
                defaults={"stage": stage},
            )
        feedback = [
            (
                grace,
                "amina-demo",
                backend,
                "interview",
                "Your duka-api tests and CI setup stood out. "
                "Could you do a 30-minute call on Thursday?",
            ),
            (
                david,
                "njeri-demo",
                frontend,
                "general",
                "Nice progress on portfolio-site. Adding a few component tests would make "
                "your React work even easier to judge.",
            ),
        ]
        for recruiter, login, job, status, message in feedback:
            if not Feedback.objects.filter(
                recruiter=recruiter, job_seeker=seekers[login], message=message
            ).exists():
                feedback_service.send_feedback(
                    recruiter, seekers[login], status=status, message=message, job_posting=job
                )
        if not ProfileView.objects.exists():
            for recruiter in (grace, david):
                for login in ("amina-demo", "chebet-demo", "kipkorir-demo"):
                    ProfileView.objects.create(recruiter=recruiter, job_seeker=seekers[login])

    def _print(self, password) -> None:
        rows = [("admin", ADMIN[0])] + [
            ("recruiter" + (" (pending)" if s == ApprovalStatus.PENDING else ""), e)
            for e, _, _, _, s in RECRUITERS
        ]
        rows += [
            ("job seeker", f"{login.split('-')[0]}@jobseeker.demo  (GitHub: {login})")
            for login in demo.persona_names()
        ]
        self.stdout.write(
            self.style.SUCCESS("\nDemo data ready. Password for every account: " + password)
        )
        for role, who in rows:
            self.stdout.write(f"  {role:<20} {who}")
        self.stdout.write(
            "\nSwagger: /api/v1/docs/  ·  Django admin: /django-admin/  ·  "
            "Public card: /api/v1/cards/amina-demo"
        )
