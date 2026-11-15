## Context

Findings and verdicts are in `Bug_Backlog.md` (batch 66, FBK-1…FBK-10). Relevant facts:

- `snapshot()` captures every cached recommendation list page and the detail entry. `rollback()`
  writes all of them back. `SaveButton` disables only its own card, so actions on different
  cards overlap. Neither save nor dismiss invalidates the lists on settle, so a wrong rollback
  persists until the data versions refetch. (`recommendations-view-review-fixes` D2 adds a list
  invalidation after a dismissal.)
- `RecommendationList` renders `<DismissUndo project={dismissed} … />` without a key, so
  `useRestore` state survives a project change. The timer effect depends on `[project]`.
- `DismissButton.run` calls `onDismissed` after `mutateAsync` resolves, on purpose: the list card
  unmounts optimistically, and its callback (setting the undo notice in the list) must still run.
  On the detail page the callback is `navigate(...)`.
- `useRestore` is called with `mutate(id, { onSuccess: onClose })`. The timer calls `close()`
  regardless of `restore.isPending`.
- `SavedPage` hand-writes `isPending ? … : !data ? …` twice.

## Goals / Non-Goals

**Goals:** the behavior in the spec delta, with no change to the optimistic feel of the actions.

**Non-Goals:** a toast system; retrying failed actions automatically; disabling all cards while
one action runs.

## Decisions

### D1. Per-item rollback (FBK-1)

`onMutate` returns `{ id, pages: [key, index][] , item, detail }` instead of whole pages.
- Save/unsave: on error, `setQueriesData` flips `saved` back for `id` only, and sets the detail
  entry's `saved` back.
- Dismiss: `onMutate` records, per list key, the removed item and its index. On error, each
  page that does not hold `id` gets the item re-inserted at that index (clamped) and its count
  incremented. The detail entry is restored from the snapshot.

Rejected alternative: invalidating the lists on error. That is simpler, but the card flickers
out and back, and it refetches every cached page.

### D2. Undo notice (FBK-2, FBK-4)

- `RecommendationList` renders `<DismissUndo key={dismissed.repositoryId} …>`.
- `DismissUndo` keeps a `deadline` in state, initially `dismissedAt + 10 s`. The effect sets the
  timer to `deadline - now`. When it fires while `restore.isPending`, it does nothing.
  `restore.mutate` gets `onSuccess: onClose` and `onError: () => setDeadline(Date.now() + 10_000)`.
  The effect re-arms on `deadline` and `isPending` changes, so a restore that settles after the
  deadline closes the notice (success) or extends it (failure).

### D3. Detail-page navigation guard (FBK-3)

`RecommendationDetailPage` keeps `const mounted = useRef(true)`, set to false in an effect
cleanup. `onDismissed` navigates only when `mounted.current`. `DismissButton` is unchanged, so the
list card's after-unmount callback still runs.

### D4. Inline errors (FBK-5)

- Cards and the detail page: `SaveButton` and `DismissButton` render
  `<span role="status" className="text-destructive text-xs">…</span>` when their mutation
  `isError`. `mutate`/`mutateAsync` calls `reset()` first, so a retry clears the message.
- Dismiss: the card is restored by rollback, so the message shows on the restored card.
- Saved page: `SavedEntry` and `HiddenEntry` show the message from their own mutation, and
  `ShowMore` shows it when `isFetchNextPageError`.
- `messages.ts` holds the strings.

### D5. Cleanups (FBK-8, FBK-9, FBK-10)

- `Loaded` with `failed` set to the existing alert text. The empty-list branch stays inside
  `children`.
- `export const recommendationsRootKey = ROOT` from recommendations `api.ts`.
- `await Promise.all([...cancelQueries])`.

## Risks / Trade-offs

- D1 re-insertion uses the index recorded at mutate time. If the page refetched in between, the
  item may land one place off. The list invalidation after the dismissal settles (REC-2) corrects
  the order.
- D2 lets a failed undo keep the notice longer than 10 s from the dismissal. The spec permits this,
  so the result is always visible.
