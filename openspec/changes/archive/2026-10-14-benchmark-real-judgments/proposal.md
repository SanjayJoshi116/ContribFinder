## Why

Two ranking searches (v0.9.0, v0.10.0) ended on the same finding: `benchmark-v1` and both holdouts disagree about relevance scaling, and the disagreement rests on two judgments in `benchmark-v1` (repositories with a relevance part near 0.008 judged relevant for the beginner persona). All three datasets are personas judged by the same author who designed the ranking. Before another search, the benchmark needs judgments that do not come from that author: real developers, with their real profiles and candidate pools, judged by a person who knows what they would contribute to.

## What Changes

- **Blind judging sheet**: a command turns an anonymized export (`export_benchmark_developer`) into a CSV sheet listing every candidate with the facts a judge needs (repository link, description, main languages, topics, contribution files, activity label, open issue count), in alphabetical order, **without** any score, rank, match label or reason from any configuration, plus a grading guide. The judge fills a grade (0, 1, 2) per row.
- **Import judgments**: a command reads a filled sheet back into the export, rejecting unknown repositories, invalid grades and sheets without a relevant grade; blank rows stay unjudged.
- **Build `benchmark-v2`**: a command merges `benchmark-v1` (personas) and one or more judged real exports into one dataset, with unique developer identifiers, merged repository catalogs (identical entries deduplicated, conflicting ones reported), and a marker on each developer saying whether it is a persona or real.
- **Selection benchmark**: once `benchmark-v2` exists with at least one judged real developer, it replaces `benchmark-v1` as the dataset on which candidate configurations are chosen. The regression baseline records metrics on both. Reports show the real-developer subset separately.
- **Larger export pools**: documented local procedure to raise the discovery pool for the developers being exported (the local `.env` caps it at 10), so a real pool has enough candidates (target 25–40) to judge.
- **Human step**: you judge 2–4 real developers (your own account first; others only with their consent). This change cannot complete without those judgments; implementation pauses for them.
- No ranking change, no new configuration, no search. v1 and v2 are only *reported* on `benchmark-v2`.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `recommendation-evaluation`: blind judging sheet and judgment import; `benchmark-v2` built from personas plus real judged developers; the selection benchmark and the regression baseline cover `benchmark-v2`; persona/real subset reporting.

## Impact

- **Backend**: `services/evaluation/` gains `sheet` (write and read the CSV) and `build` (merge datasets); `dataset` accepts an optional `kind` per developer (`persona` | `real`); `runner`/`evaluate_ranking` report per-kind means; `baseline` keyed by dataset (format 3). Commands `benchmark_sheet`, `import_judgments`, `build_benchmark`.
- **Data**: `apps/backend/evaluation/benchmark-v2.json` (committed only with your approval, since it holds real public repository names and anonymized real skill profiles). Exports and sheets live in the gitignored `judging/` folder.
- **Privacy**: exports stay anonymized (no username, email, GitHub id, token). Volunteers' data is exported only with their consent; their sign-in happens through the normal app flow.
- **Tests**: sheet round-trip and blindness (no score, rank or label in the sheet), import validation, build merge and conflicts, kind subsets, baseline format 3.
