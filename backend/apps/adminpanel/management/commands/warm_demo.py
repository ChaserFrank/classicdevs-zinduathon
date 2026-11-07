"""python manage.py warm_demo --logins a,b,c [--force]

Runs real analyses (GitHub API, needs GITHUB_TOKEN) synchronously before judging, so cards load
instantly and the ETag cache is warm. Results are attached to the job seeker who owns each login,
if any; otherwise they are admin-run analyses.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import GithubAccount, Role, User
from apps.analysis.models import Analysis
from apps.analysis.services import pipeline
from apps.analysis.services.runner import ACTIVE, expire_stale


class Command(BaseCommand):
    help = "Pre-run analyses for the given GitHub logins (real GitHub API)."

    def add_arguments(self, parser):
        parser.add_argument("--logins", required=True, help="Comma-separated GitHub logins")
        parser.add_argument(
            "--force", action="store_true", help="Re-run even if a fresh card exists"
        )

    def handle(self, *args, **options):
        logins = [login.strip().lower() for login in options["logins"].split(",") if login.strip()]
        if not logins:
            raise CommandError("Give at least one login.")
        admin = User.objects.filter(role=Role.ADMIN).first()
        failures = 0
        for login in logins:
            expire_stale(login)
            if Analysis.objects.filter(github_login=login, status__in=ACTIVE).exists():
                self.stdout.write(self.style.WARNING(f"{login}: already running, skipped"))
                continue
            fresh = Analysis.objects.filter(
                github_login=login,
                status="completed",
                completed_at__gte=timezone.now() - timezone.timedelta(hours=24),
            ).exists()
            if fresh and not options["force"]:
                self.stdout.write(f"{login}: fresh card exists (use --force to re-run)")
                continue
            account = (
                GithubAccount.objects.select_related("user__job_seeker_profile")
                .filter(login=login)
                .first()
            )
            profile = getattr(account.user, "job_seeker_profile", None) if account else None
            analysis = Analysis.objects.create(
                github_login=login, job_seeker=profile, triggered_by=admin
            )
            pipeline.run(analysis)
            analysis.refresh_from_db()
            if analysis.status == "completed":
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{login}: Signal Score {analysis.signal_score} "
                        f"({analysis.repos_analysed} repos)"
                    )
                )
            else:
                failures += 1
                self.stdout.write(
                    self.style.ERROR(f"{login}: {analysis.error_code} — {analysis.error_message}")
                )
        if failures:
            raise CommandError(f"{failures} analysis(es) failed.")
