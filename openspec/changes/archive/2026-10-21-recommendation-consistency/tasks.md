## 1. Scorable pool (D1, D8, D-1, E-4)

- [x] 1.1 `services/repositories/lifecycle.py`: `SCORABLE = (Lifecycle.RECOMMENDABLE, Lifecycle.STALE, Lifecycle.REFRESHING)`
- [x] 1.2 `load_candidates(profile, *, include_dismissed=False)`: filter `repository__is_eligible=True, repository__lifecycle__in=SCORABLE`; exclude dismissals only when `include_dismissed` is false; update the docstring
- [x] 1.3 `export_developer` passes `include_dismissed=True`
- [x] 1.4 Tests (`test_recommendation_generation.py`): a recommended repository marked stale by `mark_stale_repositories`, then regenerated, keeps its recommendation id; a STALE repository whose previous state was INDEXED (ineligible) is not scored; a REFRESHING repository that was RECOMMENDABLE is scored, a FAILED retry claimed as REFRESHING is not
- [x] 1.5 Test (export tests): an eligible STALE candidate and a dismissed candidate are both in the exported file

## 2. One lock order (D2, D-2, D-3, D-4)

- [x] 2.1 New `services/locks.py`: `lock_developer(user_id) -> DeveloperProfile | None` (`select_for_update()`; must run inside a transaction); module docstring states the order: job → profile → dismissals/saves → recommendations → issues by pk → children
- [x] 2.2 `_persist`: `lock_developer` first inside `job_write`, then read dismissals, then lock the developer's `Recommendation` rows, then `Issue.objects.select_for_update().filter(...).order_by("pk")`
- [x] 2.3 `_store_issues`: lock the issues to delete with `select_for_update().order_by("pk")` before deleting them
- [x] 2.4 `delete_github_data`: `lock_developer` before deleting the profile, in the same transaction
- [x] 2.5 Tests (`test_recommendation_generation.py`, `django_db(transaction=True)` with two threads, as in `test_discovery_service.py`): a dismiss committed while persist waits on the profile lock is honored (repository not stored); dismiss and persist running together both finish without a deadlock error; an issue refresh deleting a matched issue while persist runs finishes without a deadlock error

## 3. Feedback under the lock (D3, E-5, E-6, E-7)

- [x] 3.1 `save`: `lock_developer`; if the recommendation no longer exists, raise `Recommendation.DoesNotExist`; the save view maps it to the standard 404
- [x] 3.2 `dismiss`: `lock_developer`; create the dismissal; when a save is deleted, record `unsaved`; delete the recommendation by pk
- [x] 3.3 `record`: for `viewed`, `lock_developer` and run the de-duplication check and insert in one transaction
- [x] 3.4 `unsave`, `restore`: `lock_developer` in their transactions; update the module docstring
- [x] 3.5 Tests (`test_feedback.py`): saving a recommendation deleted by a dismiss answers 404 and stores no save and no event; dismissing a saved repository records `dismissed` and `unsaved` and removes the save; two concurrent `viewed` posts store one event (threads); existing save, dismiss, restore and feedback tests still pass

## 4. Dismissals before the cut, consistent issues (D4, D5, D-6, D-10)

- [x] 4.1 `score.rank` and `pipeline.rank_pool`: `top_n: int | None`, `None` = no cut; evaluation call sites unchanged
- [x] 4.2 `RecommendationService`: rank with `top_n=None`; `_persist` drops dismissed repositories, cuts to `RECOMMENDATIONS_TOP_N`, then numbers ranks
- [x] 4.3 `_persist`: if any matched issue of the kept repositories is missing after locking, raise `IssuesChanged`; `run()` repeats load → rank → persist up to `MAX_ATTEMPTS = 3` with a heartbeat between attempts, then raises `PermanentJobError` code `issues_changed`; drop the old "drop deleted issues" filtering
- [x] 4.4 Tests (`test_recommendation_generation.py`): with top N 20 and 25 qualifying candidates, a repository dismissed after ranking leaves 20 stored; an issue deleted between ranking and persist (patched hook) leads to a second attempt whose stored issue count, signals, label and reasons exclude it; issues deleted before every attempt fail the job `issues_changed` and keep the previous recommendations exactly
- [x] 4.5 `uv run python manage.py evaluate_ranking` matches `baselines.json` (no ranking change)

## 5. Rerun requested during a run (D6, D-5)

- [x] 5.1 Add `SyncJob.rerun_requested` (`BooleanField(default=False)`) and a `jobs` migration
- [x] 5.2 `start_recommendations`: when `_start_job` returns an existing RUNNING job, `filter(pk=..., status=RUNNING).update(rerun_requested=True)`; if no row was updated, call `_start_job` again
- [x] 5.3 `generate_recommendations`: `run_tracked_job(..., on_completed=...)` hook that re-reads `rerun_requested` and calls `start_recommendations(job.user)` when set
- [x] 5.4 Tests (`test_recommendation_generation.py` / `test_feedback.py`): a restore while a generation is RUNNING flags it, and its completion starts a new generation; a start while PENDING adds nothing and sets no flag; a flag update racing completion (job already COMPLETED) creates a new job; `rerun_requested` is not in the job API response

## 6. Freshness (D7, D-14)

- [x] 6.1 `due_profiles`: profiles with candidates or recommendations (`Exists`); `pool_changed` ignores repositories currently STALE or REFRESHING; due also when the profile has recommendations and no candidates
- [x] 6.2 Tests (`test_refresh_pipeline.py` or the freshness tests): a staleness mark alone starts no generation; a completed refresh still does; a profile with recommendations and an emptied pool is due once and, after generation, no longer due

## 7. Frontend (D9, F-4)

- [x] 7.1 `SaveButton`: `disabled={save.isPending || unsave.isPending}`
- [x] 7.2 Test (`feedback.test.tsx`): a double click on Save sends one request and the button ends Saved

## 8. Verification and release

- [x] 8.1 `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`
- [x] 8.2 Frontend: `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`
- [x] 8.3 `npm run api:sync` and confirm the OpenAPI schema and `schema.d.ts` are unchanged
- [x] 8.4 Mark rows D-1, D-2, D-3, D-4, D-5, D-6, D-10, D-14, E-4, E-5, E-6, E-7 and F-4 `fixed (recommendation-consistency)` in `Bug_Backlog.md`
- [x] 8.5 Release housekeeping per CLAUDE.md §8 as patch `0.12.6`: version files and lockfiles, `npm run check:version`, `CHANGELOG.md`, `features.txt`, `README.md` status line, and the CLAUDE.md §7 entry (with K-1 still carried over)
