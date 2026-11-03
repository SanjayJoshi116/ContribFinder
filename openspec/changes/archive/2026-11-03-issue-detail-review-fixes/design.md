## Context

Findings and verdicts: `Bug_Backlog.md` batch 46 (FI-1…FI-10); motivation in `proposal.md`;
behavior in the three spec deltas. `services/issues/classify.py` writes
`contribution_type_evidence = {"by": "label", "value": <canonical label>}` and difficulty votes
through `_vote(signal, vote, value)` with signals `label`, `body_length`, `technology_count`,
`contribution_type`, `comments`. Batch 45 set the page order pending → no data: error → data.

## Goals / Non-Goals

**Goals:**
- Fix the issue detail page's wording and refetch behavior without a backend change.
- One shared external link, one `Fact`, one date formatter.

**Non-Goals:**
- Storing the raw GitHub label that mapped to a category (FI-1's backend option: evidence
  change plus `ISSUE_TAXONOMY_VERSION` bump; the category wording is already accurate).
- The recommendation detail page's own refetch handling (its module is reviewed later, low
  group); it only gains the shared link and `Fact` here.
- Recording "Open link in new tab" from the context menu (no event reaches the page).

## Decisions

**D1. Category wording (FI-1).** `contributionBasis`: `by: "label"` → `From a ${value} label`
(`documentation`, `bug`, …: the canonical names read as categories); `by: "keyword"` unchanged
(the keyword is quoted from the title, which is accurate). Alternative: store the raw label
(rejected above).

**D2. Known signals only (FI-2, FI-4).** `difficultyBasis` reads `signals` only when
`Array.isArray`, and maps through a `SIGNAL_TEXT` table keyed by signal; an unknown key is
dropped. A backend test (`tests/test_issue_signal_wording.py`) runs `classify.difficulty`,
collects the signals it writes and asserts they equal the `SIGNAL_TEXT` keys read from
`evidence.ts`, so a new backend signal fails until the page gets wording. (Planned as a Vitest
test reading `classify.py`; the app has no Node types and Vite denies files outside its root, so
the check lives on the backend side, which also uses the classifier's real output.)

**D3. Data before dead end (FI-3).** `IssueDetailPage`: pending → loading; error with status 404,
or no data → `DeadEnd` (404 message or the generic one); otherwise the issue. A 404 on refetch
still ends the page because the issue really left the recommendation.

**D4. `ExternalLink` (FI-6)** in `src/components/ExternalLink.tsx`: an `<a target="_blank"
rel="noopener noreferrer">` with an `onOpen` callback called on `click` and on `auxclick` with
`button === 1`. The three GitHub links use it (issue detail, recommendation card, recommendation
detail). One `auxclick` per middle click; a click never fires `auxclick` for button 0.
Alternative: `onMouseUp` for button 1; rejected, `auxclick` is the standard event for it.

**D5. Wording (FI-7).** A `NO_TECHNOLOGIES = 'No technologies mentioned'` next to the page;
`NOT_ENOUGH_EVIDENCE` stays for unknown difficulty and type.

**D6. Shared display (FI-10).** `src/components/Fact.tsx` (`term`, `value`, optional `note`),
`src/lib/format.ts` `formatDate(iso: string)` (medium date). The issue and recommendation detail
pages, `SavedPage` and `SkillGroups` import them; the local copies go.

## Risks / Trade-offs

- [Feedback numbers rise after the release (middle-click opens now counted)] → Noted in the
  changelog; `feedback_report` compares configurations over the same period, so the shift is
  shared.
- [The pinning test reads a frontend file] → Path is fixed in the monorepo; CI's backend job runs
  from a full checkout.
