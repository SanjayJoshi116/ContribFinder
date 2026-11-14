## Context

Findings and verdicts are in `Bug_Backlog.md` (batch 64, EVL-1…EVL-10), each checked by reading
the code against `openspec/specs/recommendation-evaluation/spec.md`. Relevant facts:

- `bootstrap.paired` uses a percentile interval. `Interval.marked` is `low > 0 or high < 0`. The
  spec requires a zero-width interval for one developer, which today is always marked when the
  difference is not 0. `benchmark-v1` has 6 developers; `holdout-v1` and `holdout-v2` have 4.
- `feedback_report.build` adds every event to its bucket and label groups. `services/feedback.record`
  deduplicates only `viewed`. `RecommendationFeedback` has `repository_full_name` and
  `created_at`; `load` reads neither.
- `baseline.write` uses `path.write_text(json.dumps(data, indent=2) + "\n")`.
  `core.reports.json_text` is `json.dumps(indent=2, ensure_ascii=False) + "\n"`, which gives
  the same bytes for the ASCII-only baselines file, and `write_json` writes with `newline=""`.
- Baseline entries are keyed by `Report.dataset` (the dataset's `name` field). The test and
  `default_datasets` look for `DATASETS_DIR/<name>.json` and skip it when missing.
- `matching/issues.py` sorts issues by `updated_at.timestamp()`; a naive time is read as local
  time. All 72 committed `updated_at` values end in `+00:00`.

## Goals / Non-Goals

**Goals:** the behavior in the spec delta; no ranking change (`baselines.json` byte-identical);
every error path of the offline commands ends as a command error, not a traceback.

**Non-Goals:** a different interval method (BCa, t-interval) or a significance test in the
report; deduplicating events at write time (`record` keeps the raw log); faster bootstrap code
(EVL-8 accepted).

## Decisions

### D1. Minimum developers for a mark (EVL-1)

`MIN_MARKED_DEVELOPERS = 6` in `bootstrap.py`. The exact two-sided sign-test p for n of n is
2·0.5ⁿ: 0.0625 at 5 and 0.031 at 6, so 6 is the fewest developers that can ever support a 5%
claim. `Interval` gets `developers: int`. `marked` is false below the minimum, and
`as_dict` adds `developers` and `too_few` (true below the minimum). The command prints
`(too few developers to mark: n < 6)` under the block instead of the `*` legend line when that
applies. Alternatives: a sign test or BCa interval. Both were rejected because they change what
the interval means, and the figures are information only.

### D2. Coverage of the adjusted share (EVL-2)

`coverage = Σ weight[shared buckets] / Σ weight[all buckets]`, rounded like shares and None when
there is no adjusted share. It goes in `ConfigRows`, `as_dict` and the printed config line.
Renormalization stays as specified. Rejected alternative: no adjusted share unless every
weighted bucket has a share. Configurations with sparse lower ranks would then never get one.

### D3. One outcome per user, repository and version (EVL-3)

`load` also reads `repository_full_name` and `created_at`, ordered by `created_at, id` (one
query, still streamed). `build` keeps:
- raw action counts per bucket and label group, as today, from every event (the `counts` in
  rows), and distinct users;
- outcomes: a dict keyed by `(user_id, repository_full_name, config_version)` holding a stack
  of the non-undone decisive events (`saved`/opened push a positive, `dismissed` pushes a
  dismissal; `unsaved` removes the latest `saved` in the stack, `undismissed` the latest
  `dismissed`). The outcome is the top of the stack, if any. Opened events cannot be undone.

Shares (bucket, label, raw, adjusted) and their minimum use outcome tallies (positive, decisive),
placed in the bucket and label of the outcome's event. `BucketRow` and `LabelRow` gain
`positive` and `decisive` fields instead of deriving them from `counts`. Unattributed events
(no version or rank) are unchanged. Events are attributed per version, so one repository can
have an outcome under v1 and another under v2. Memory is bounded by distinct keys, which is
fine for an offline report.

### D4. Baseline writes (EVL-4, EVL-5)

`baseline.write` calls `core.reports.write_json(path, data, what="Baseline")`. The
`evaluate_ranking` command, when `--write-baseline` is set, checks each dataset path before
evaluating: `path.resolve() == (DATASETS_DIR / f"{dataset.name}.json").resolve()`, otherwise
`CommandError` naming the path and the expected file. `baseline.write` repeats the check by name
(`BaselineError` when `DATASETS_DIR/<name>.json` does not exist), so a direct caller cannot
record a dataset the test cannot find.

### D5. Input hardening (EVL-6, EVL-9, EVL-10)

- `sheet._cell(value)`: a string starting with one of `= + - @ \t \r` gets a leading `'`.
  Applied to every text cell (`name`, description, languages, topics). URL and counts are
  never affected.
- `dataset._issue`: `updated_at` must parse and have `tzinfo`; the error is "updated_at must be
  an ISO 8601 time with a UTC offset".
- `build`: `repositories` must be an object, `developers` a list of objects, otherwise
  `BuildError` naming the input. `resolved` is kept as an ordered set.
- `write_sheet`: `repositories` must be an object and hold every candidate, otherwise
  `SheetError` naming the repository.

### D6. Unknown reasons and labels (EVL-7)

`_reasons` lists the known reasons by count, then any other stored values by count, then
`none`. Label rows list `LABELS` first, then other stored labels in name order. `calibration`
only looks at `LABELS`.

## Risks / Trade-offs

- EVL-3 lowers the shares of configurations whose users open repeatedly. Feedback has never
  driven a decision (aggregates only, information for calibration), so no decision is
  reinterpreted. The CHANGELOG says that shares before and after this release are not comparable.
- EVL-1 means holdout comparisons (4 developers) are never marked. That is the honest result;
  holdouts gate on the improvement rule, not on marks.
