## Context

The evaluation tooling is offline: management commands over JSON datasets in `apps/backend/evaluation/`, plus `services/evaluation/`. The baseline file `evaluation/baselines.json` (format 3) has one global `top_n` and a `datasets` map of `{configs: {version: {min_score, min_score_basis, metrics}}}`. `test_baseline_metrics_unchanged` re-evaluates every recorded dataset whose file exists:
- at `baseline.MIN_SCORE`, with each configuration's own minimum score winning;
- at the global `top_n`;
- requiring both v1 and v2.

Judging sheets are CSV files edited in a spreadsheet, with `#` guide lines on top. See proposal.md for the failures.

## Goals / Non-Goals

**Goals:**
- `--write-baseline` produces a file the baseline test accepts, whatever combination of options is allowed.
- A filled sheet imports exactly what the judge wrote, or fails naming the row.
- The commands report bad input as `CommandError`, never as a traceback.

**Non-Goals:**
- Ranking or metric changes. The recorded numbers must stay identical.
- Pruning recorded configurations that no longer exist in the database. The test already fails on them through `stored_config`.
- E-4 (export depends on lifecycle): batch 6.

## Decisions

**D1. Default baseline datasets (R-1).** With no `--dataset`, `--write-baseline` evaluates and writes, in order:
1. `benchmark-v1`;
2. every dataset already recorded in `baselines.json` whose file exists in `evaluation/`;
3. the selection dataset.

Duplicates are removed. This is exactly the set the test checks plus the selection benchmark, so writing and checking cannot disagree.

The command loops over the datasets. Per dataset it prints the same report as today. `--require-improvement` applies to every dataset's verdicts. Without `--write-baseline`, the default stays the selection dataset only.
- Alternative: require `--dataset` with `--write-baseline`. Rejected: the documented one-liner (`evaluate_ranking --write-baseline`) would stop working, and refreshing v1 and v2 would need two runs.

**D2. Format 4, top N per dataset (R-2).** The format 4 file looks like `{"format": 4, "datasets": {name: {"top_n": N, "configs": {...}}}}`.
- `baseline.read` keeps accepting formats 1–3. For those, the old global `top_n` (or `TOP_N` when absent) applies to every dataset. A new `baseline.top_n(data, dataset)` returns the per-dataset value.
- The test reads it instead of `recorded["top_n"]`.
- The committed file is rewritten to format 4 by running the command. The numbers are unchanged because nothing about ranking changes.

**D3. Merge, with a top N guard (E-1).** `baseline.write(reports)` groups reports by dataset. For each dataset it starts from that dataset's recorded configs, replaces the entries of the evaluated configs, and keeps the rest.
- If the run's top N differs from the recorded one, the evaluated set must include every recorded config. Otherwise `write` raises `BaselineError` before touching the file, and the command turns it into `CommandError`.
- All checks run before the single write, so a failure leaves the file as it was.
- Alternative: drop configs not evaluated in this run. Rejected, because that is the E-1 failure itself.

**D4. No `--min-score` with `--write-baseline` (E-2).** It is rejected in `_specs` next to the existing `--config-file` rule, as a `ConfigError`, so nothing is evaluated. `--top-n` stays allowed: D2 records it.

**D5. Sheet reading (R-7, R-8).**
- `read_sheet` removes the BOM, then removes leading lines that start with `#` (and blank lines among them) up to the first other line, which must be the header. It parses the rest with `csv.DictReader` over a `StringIO`, so quoted multi-line fields stay whole.
- Rows with every cell blank are skipped.
- A row with no repository but a non-blank grade or note raises `SheetError("Row N: ...")`, using the CSV line number.
- A repository seen twice raises, naming the repository.
- The return type stays `{repository: grade text}`.

**D6. Judged description (R-14).** `import_sheet` sets the developer's description, and the export's top-level description, to a fixed text: `JUDGED` = "Real developer judged blind from a judging sheet." The judgment count is not included: it can be derived, and the text stays stable when a sheet is re-imported. `build_benchmark` uses its own `--description` for the dataset, so only the developer text reaches `benchmark-v2`.

**D7. `build` input checks (R-13).** Before merging, each input must be a `dict` whose `format` equals `FORMAT`. Otherwise it raises `BuildError` naming the label (the path). The command already maps `BuildError` to `CommandError`, so nothing is written.

**D8. `--json` output (E-8).** `out.parent.mkdir(parents=True, exist_ok=True)`, then the write, inside `try/except OSError` → `CommandError("Report not written: ...")`. This is the same pattern as `import_judgments` and `build_benchmark`. The report is written before the baseline.

**D9. Missing byte counts (E-9).** In `_languages`, `None` counts as 0. If the total is 0, the first three names are listed in their given order, without percentages. This fixes the cause rather than catching `TypeError` in the command.

## Risks / Trade-offs

- [Format 4 makes older checkouts unable to read the file] → `baselines.json` is read only by this repository's code, which ships with the file.
- [D1 makes `--write-baseline` slower: it evaluates up to three datasets] → each is small (dozens of developers), and it takes seconds.
- [D3 lets a stale recorded config survive a rewrite] → the baseline test re-evaluates every recorded config, so a stale one fails the test and is noticed.
- [D5 rejects sheets that the old reader accepted silently (duplicates)] → this is intended. The error names the row so the judge can fix it.

## Migration Plan

1. Implement, then run `npm run manage -- evaluate_ranking --write-baseline` to rewrite `baselines.json` as format 4.
2. Check the diff: only the structure changes (`top_n` moves into the `benchmark-v1` entry), and the numbers are identical.

Rollback: revert the commit, which restores the format 3 file.
