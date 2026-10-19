## Context

See proposal.md for motivation. Rows A-1, A-7, A-8, A-9, A-12, A-19, B-4, E-3, H-8 and H-9 in
`Bug_Backlog.md` (verified; their notes narrow B-4 and A-12).

Current state that shapes the approach:
- `delete_github_data` calls `jobs.cancel_active_syncs(user)` (status UPDATE), then deletes rows
  and the job history in one transaction.
- Job services check cancellation only between units of work (`_check_cancelled` → `heartbeat()`).
  A step that is already running (sync `_step_profile`, `_step_repositories`, …, the analysis
  `_persist`, discovery's candidate writes) commits whatever it fetched, even after the
  deletion.
- `RecommendationService._persist` already does it right: inside its transaction it runs
  `SELECT … FOR UPDATE` on its SyncJob row and raises `JobCancelled` unless the job is RUNNING.
- The standalone analysis job (`developers.extract_developer_skills`) runs
  `ProfileAnalysisService(user).run()` without a job reference. `run()` wraps every exception in
  `ProfileAnalysisError`.
- Users have unusable passwords. Django stores `user.get_session_auth_hash()` (an HMAC of the
  password field) in each session and drops sessions whose hash no longer matches.
- `oauth.revoke_grant` calls `DELETE /applications/{client_id}/grant`, which revokes every token
  of the user for this app. GitHub's `DELETE /applications/{client_id}/token` revokes one token.

## Goals / Non-Goals

**Goals:**
- One mechanism makes every user-data write in a job respect deletion, with no per-step special
  cases.
- Identity scrub on account deletion that keeps the audit trail useful (what happened, when).

**Non-Goals:**
- Stopping GitHub requests mid-step after disconnect. The token is revoked anyway, and the
  guard below stops any write.
- Shared repository rows (search results, analysis). They are not personal data. Orphan cleanup
  already runs at deletion, and a search upsert that lands afterwards is just public data.
- Claim fencing between workers (batch 4).

## Decisions

### D1. A job write guard: lock the job row, require RUNNING
`services/job_guard.py` gets one context manager, `job_write(job_id)`. It is not in `services/jobs.py`, because that module imports the sync service, which needs the guard. `JobCancelled` moves to `services/errors.py` for the same reason:

```python
@contextmanager
def job_write(job_id: int) -> Iterator[None]:
    with transaction.atomic():
        status = SyncJob.objects.select_for_update().filter(pk=job_id)
                       .values_list("status", flat=True).first()
        if status != SyncJob.Status.RUNNING:
            raise JobCancelled()
        yield
```

Every transaction that writes user data in a job body uses it in place of
`transaction.atomic()`:
- sync steps: profile, readme, repositories, languages, topics, dependencies, contributions;
- the analysis `_persist`;
- discovery's candidate and discovery-record writes (the pool step only deletes, so it needs
  no guard);
- ranking's `_persist`, which replaces its inline check.

Why this makes deletion final: `cancel_active_syncs` updates the same row, so it waits for any
guarded transaction in flight.
- A write that commits first is then deleted by `delete_github_data`.
- A write that starts afterwards sees CANCELLED, or no row once the job history is deleted, and
  raises `JobCancelled` before writing.

`run_tracked_job` and the services already treat `JobCancelled` as a cancel. Job progress
writes (`_set_step`, `_update_metadata`) go through `save_progress(job, **fields)` in the same
module: a conditional UPDATE of a RUNNING row that raises `JobCancelled` when nothing matched. A
cancelled or deleted job therefore surfaces as a cancel in every service, never as a failed save.

Steps that write nothing user-specific (pure GitHub fetches, shared repository upserts) need no
guard. The lock is held only for the write transaction, never during network I/O, so a step
must fetch first and then write. That is already how every step is structured.

*Alternatives:*
- More `_check_cancelled` calls before each write: still racy, because the check and the
  write are separate transactions. Rejected.
- Deleting with `SELECT … FOR UPDATE` on the profile row: not every writer touches the profile
  (repository links, GitHub profile). Rejected.

### D2. Analysis takes the job it runs under
`ProfileAnalysisService(user, job_id=...)`:
- `_persist` runs under `job_write(job_id)`.
- `run()` re-raises `JobCancelled` instead of wrapping it in `ProfileAnalysisError`.
- `get_or_create` stays. Under the guard it can only run while the job is RUNNING, which deletion
  rules out.

`developers/tasks.py` passes the job id and returns on `JobCancelled`: the job is already
CANCELLED, or deleted by the data deletion, so there is nothing to finish.

Batch 4 (B-18) will move this task onto `run_tracked_job`; this change keeps the edit minimal.

### D3. End every session by rotating the password hash
On disconnect, `user.set_unusable_password()` (a new random unusable value) and save, then
`logout(request)`. Every other session's stored auth hash stops matching, so Django treats
those sessions as anonymous on their next request.

*Alternative:* scanning or deleting `Session` rows by user. Django keeps no user index, and
`cached_db` would need the cache purged too. Rejected.

Account deletion already removes the user, so its sessions are dead.

### D4. Display name cleared with GitHub data
`delete_github_data` sets `user.display_name = ""`. It is GitHub-derived, so it is cleared for
delete-data, disconnect and account deletion alike. The next sign-in sets it again.

### D5. Audit scrub on account deletion
`audit.anonymize_user_entries(user)` runs in account deletion after the `account_deleted` entry
is recorded and before the user row is deleted:
- `ip_hash = ""`;
- `metadata` minus `github_id` and `github_username`. An allowlist of identifying keys lives
  next to `ALLOWED_METADATA_KEYS`.

The FK then goes to NULL through the existing `SET_NULL`. One UPDATE per metadata shape; the
user has few entries.

### D6. Revoke only the replaced token
`oauth.revoke_token(access_token)` calls `DELETE /applications/{client_id}/token`. A 404 means
already gone.

`link_github_account` reads the stored (encrypted) token before overwriting it and, on commit,
queues the Celery task `github.revoke_replaced_token(github_id, previous_encrypted)`. The
sign-in request never waits on GitHub, and a rolled-back sign-in revokes nothing. Only ciphertext
is queued; it is useless without the server's keys. The task decrypts it, skips it when it
equals the token now stored (GitHub reissued the same one), and revokes it best effort: failures
are logged by type only, never raised or retried.

Revoking the whole grant is wrong here, because it would kill the new token too.

### D7. Export leaves out interacted repositories
`export_developer(..., include_interacted=False)` drops candidates whose repository either:
- has a `CandidateDiscovery` with source `previously_interacted` for this profile, or
- is linked to the user by `UserRepository` (contributor).

The command reports how many it dropped and gets `--include-interacted`. The dataset format is
unchanged.

### D8. Single cancellation
`_revoke_and_unlink` stops calling `cancel_active_syncs`; `delete_github_data` already does,
first thing.

Disconnect and account deletion still call `_revoke_and_unlink` before `delete_github_data`. A
job running between the two can still use the token. That is harmless: the token is being
revoked, and its writes are guarded.

### D9. Privacy page text
`PrivacyPage.tsx` categories follow the spec list:
- Split the identifier row: account ID until account deletion; username, avatar and display name
  until disconnect or data deletion.
- Add rows for candidate pool and search queries, job history and sessions.
- Audit entries: kept without user link, GitHub identifiers or address hash.

The frontend test that renders the page gets assertions for the new rows.

## Risks / Trade-offs

- [The guard adds one row lock per write transaction] → it is a lock on the job's own row,
  taken only by that job, deletion and recovery. There is no contention in normal operation.
- [A write transaction that is accidentally long holds the lock and delays deletion] → the
  guard wraps only the write block, never network I/O. A test asserts that deletion completes
  while a step is between fetch and write.
- [Rotating the password value on disconnect] → users have no usable password, so nothing else
  depends on it.
- [Excluding interacted repositories changes what a judged real developer covers] → those
  repositories are trivially relevant and say little about ranking quality. `real-a-v2` has not
  been judged yet, so nothing has to be redone.

## Migration Plan

- No schema change. Deploy and the guard is active.
- Existing audit entries of already-deleted accounts keep identifiers: there is no back-fill.
  Those accounts no longer exist to link them to, and a one-off scrub of `user IS NULL` entries
  can be run with `manage.py shell` if wanted.
- Rollback: revert. Nothing is persisted that the old code cannot read.
