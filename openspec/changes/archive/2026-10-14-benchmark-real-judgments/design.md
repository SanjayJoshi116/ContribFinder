## Context

See proposal.md (Why). Current state:

- `export_benchmark_developer --user-id N --as ID --out F` writes a one-developer dataset (format 1) from stored data: features, candidate pool (`load_candidates`: recommendable, eligible, not dismissed), eligible issues, empty judgments. No GitHub calls.
- `services/evaluation/dataset.parse` validates a dataset and requires every developer to have a judgment of 1 or 2; a fresh export therefore does not load until judged (by design).
- `baselines.json` is format 2: one dataset (`benchmark-v1`), per-config `min_score`, `min_score_basis`, metrics. `baseline.entries()` reads formats 1 and 2.
- The local `.env` sets `DISCOVERY_MAX_POOL=10` and `DISCOVERY_MAX_ANALYSES_PER_RUN=10`; defaults are 300 and higher. Only one local user (id 2, the owner) has an analyzed profile.
- The two ranking searches' `search.py` scripts hard-code `benchmark-v1`; they are archived and stay as they are.

## Goals / Non-Goals

**Goals:**
- A judge sees only what a contributor would see when deciding, never what the ranking thinks.
- Real judged developers enter the selection benchmark through validated, repeatable commands.
- Personas and real developers stay distinguishable in every report.

**Non-Goals:**
- Changing any `benchmark-v1` judgment (it stays as the persona record; the real developers are the counterweight).
- A judging UI in the app, multi-judge agreement statistics, or judging issues.
- Any ranking search or configuration change. `holdout-v3` is not needed until the next search.

## Decisions

### D1. Sheet format
CSV (UTF-8 with BOM so spreadsheet apps open it correctly). Leading lines starting with `#` carry the grading guide and the developer id; the reader skips them. Columns:

`repository, url, description, languages, topics, contribution, activity, open_issues, grade, note`

- `languages`: up to three by byte share, e.g. `Python 82%; HTML 12%`.
- `contribution`: present files/labels, e.g. `CONTRIBUTING; good first issue`.
- `open_issues`: count of the export's eligible issues (not their analysis: difficulty and type are ContribFinder's opinion).
- Alphabetical by repository. No signal, score, rank, label or reason column, and nothing derived from the developer's profile.
- Why CSV rather than editing JSON: judges work in a spreadsheet; the round-trip is validated.

### D2. Import
`import_judgments --export F --sheet S [--out F2]` (default in place). Matches rows by `repository`; grades `0|1|2|blank` (whitespace trimmed); sets the developer's `kind` to `real`; validates the result with `dataset.parse` before writing. On any error nothing is written.

### D3. Build
`build_benchmark --name benchmark-v2 --out PATH --input A.json --input B.json ... [--on-conflict error|first]`. Inputs in order; developers concatenated (duplicate id → error); repositories merged by full name: identical JSON → one entry; different → error naming it, or the first input wins with `--on-conflict first` (reported). Real exports taken on different days will differ in activity snapshots for shared repositories, hence the option. The result is validated before writing.

### D4. Kind and subsets
`kind` optional in developer entries (`persona` default, `real`), carried on `BenchmarkDeveloper`. `Report` gains `subsets: dict[str, dict[str, float]]` (means per kind) filled only when both kinds are present; `evaluate_ranking` prints a `persona` and `real` row under each configuration.

### D5. Selection dataset
`dataset.selection_dataset()` returns `benchmark-v2.json` if it exists and contains a `real` developer, else `benchmark-v1.json`. `evaluate_ranking` uses it as the default `--dataset`. The archived search scripts are not touched (they document past runs).

### D6. Baseline format 3
`{"format": 3, "top_n": 50, "datasets": {"benchmark-v1": {"configs": {...}}, "benchmark-v2": {...}}}`, each config entry as in format 2. `--write-baseline` (re)writes the entry for the evaluated dataset only and keeps the others. `entries(data, dataset)` reads formats 1–3. The regression test iterates over every dataset in the file that exists on disk.

### D7. Real export procedure (documented, not code)
1. In the local `.env`, raise `DISCOVERY_MAX_POOL` and `DISCOVERY_MAX_ANALYSES_PER_RUN` to 40 (restore afterwards if desired).
2. `npm start`, sign in as the developer, press Refresh; wait for discovery, analysis and recommendations to finish (the app's stage line).
3. `npm run manage -- export_benchmark_developer --user-id N --as real-a --out ../../judging/real-a.json` (repository `judging/`, gitignored).
4. `npm run manage -- benchmark_sheet --export real-a.json --out real-a.csv`; judge in a spreadsheet; `import_judgments`.
5. Repeat for each consenting developer (`real-b`, ...); then `build_benchmark`.

Identifiers are neutral (`real-a`), never usernames. Exports and sheets stay in the gitignored `judging/` folder, never committed; only the built `benchmark-v2.json` may be committed, on the judge's decision.

## Risks / Trade-offs

- [Only one real developer is available] → it still counts; the subset report shows how much it moves the means. The proposal asks for 2–4.
- [The judge is also the developer being judged (own account)] → that is the most informed judge possible for "would I contribute here"; still one person's view, stated in the CHANGELOG.
- [Real pools are larger and noisier than personas', and unjudged rows count as not relevant] → the sheet asks to judge every row; unjudged counts are reported per developer.
- [Real repository data in a committed file] → public data only, anonymized developer, explicit commit decision; the file can stay local and the baseline test then skips it (D6).

## Outcome (at archive)

The tooling shipped (v0.11.0); the judging did not finish. `real-a` (the judge's own account, 39 candidates) was exported and its sheet written, but only 3 rows were graded (1 relevant), so `benchmark-v2` was not built and `benchmark-v1` stays the selection benchmark. The pool showed a discovery bias: almost every candidate is a very large project (median 906 contributors, 2 of 39 under 50), several are lists or documentation rather than code. Search ranks by GitHub best match with only a star minimum, and the pool cap keeps the best-ranked. Carry-over: fix discovery's project-size mix in its own change, then re-export, judge, build and evaluate (tasks 5.3–5.5).

## Migration Plan

No schema or runtime change. `baselines.json` moves to format 3 (same v1/v2 numbers for `benchmark-v1`).
