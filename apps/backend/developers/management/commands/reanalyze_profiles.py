from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from jobs.models import SyncJob
from services.jobs import start_profile_analysis


class Command(BaseCommand):
    help = (
        "Queue a profile re-analysis from stored GitHub data (no GitHub requests) for every "
        "user with a completed sync, or for one user. Run after changing evidence weights "
        "or the skill catalog."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--user", type=int, help="Only this user ID.")

    def handle(self, *args: Any, **options: Any) -> None:
        users = User.objects.filter(
            sync_jobs__job_type=SyncJob.JobType.GITHUB_PROFILE_SYNC,
            sync_jobs__status=SyncJob.Status.COMPLETED,
        ).distinct()
        if options["user"] is not None:
            users = users.filter(pk=options["user"])
            if not users.exists():
                raise CommandError(f"User {options['user']} has no completed sync.")
        queued = existing = 0
        for user in users.order_by("pk"):
            _job, created = start_profile_analysis(user)
            queued += created
            existing += not created
        self.stdout.write(f"Queued {queued} analysis job(s); {existing} already active.")
