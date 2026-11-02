from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from jobs.models import SyncJob
from services.jobs import SYNC, active_jobs, start_profile_analysis


class Command(BaseCommand):
    help = (
        "Queue a profile re-analysis from stored GitHub data (no GitHub requests) for every "
        "active user with a completed sync, or for one user. Users whose sync is running are "
        "skipped (the sync ends in its own analysis). Run after changing evidence weights or "
        "the skill catalog."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--user", type=int, help="Only this user ID.")

    def handle(self, *args: Any, **options: Any) -> None:
        users = User.objects.filter(
            is_active=True,
            sync_jobs__job_type=SyncJob.JobType.GITHUB_PROFILE_SYNC,
            sync_jobs__status=SyncJob.Status.COMPLETED,
        ).distinct()
        if (user_id := options["user"]) is not None:
            if User.objects.filter(pk=user_id, is_active=False).exists():
                raise CommandError(f"User {user_id} is inactive.")
            users = users.filter(pk=user_id)
            if not users.exists():
                raise CommandError(f"User {user_id} has no completed sync.")
        queued = existing = syncing = 0
        for user in users.order_by("pk"):
            if active_jobs(user, SYNC).exists():
                syncing += 1
                continue
            _job, created = start_profile_analysis(user)
            queued += created
            existing += not created
        self.stdout.write(
            f"Queued {queued} analysis job(s); {existing} already active; "
            f"{syncing} syncing (skipped)."
        )
