## 1. Aggregation (D1–D3)

- [x] 1.1 `services/evaluation/feedback_report.py`: `Event.match_label` (default ""), `load`
  reads it; shared row helper; `LabelRow`, `LABELS`; `Calibration` and the verdict;
  `ConfigRows.labels` and `.calibration`; `as_dict` adds `labels` and `calibration`.
- [x] 1.2 Tests (`tests/test_feedback_report.py`):
  - shares 0.70 / 0.55 / 0.40 → three label rows, `ordered`;
  - strong 0.45, good 0.60 → `not ordered`, strong below good;
  - strong 0.60, partial 0.70, no good → `not ordered`, strong below partial;
  - ties → `ordered`; one label with a share → `not enough data`;
  - events without a label stay out of the label rows but in the bucket rows;
  - bucket rows, raw and adjusted shares unchanged by labels.

## 2. Command (D4)

- [x] 2.1 `feedback_report`: label table, calibration line, note on rank; JSON keys.
- [x] 2.2 Tests: printed calibration line; JSON `labels` and `calibration` keys; the
  aggregates-only key walk still passes.

## 3. Verification and housekeeping

- [x] 3.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`; run
  `npm run manage -- feedback_report` locally. No frontend or e2e change.
- [x] 3.2 Docs: README "Feedback report" (label rows, calibration, read with user counts);
  CLAUDE.md §7 shipped entry; `ideas.md` §4 label calibration shipped as a report (changing the
  bands stays a ranking change).
- [x] 3.3 Release housekeeping (CLAUDE.md §8): patch 0.12.21; `CHANGELOG.md`, `features.txt`,
  README status line.
