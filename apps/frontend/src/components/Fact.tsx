/** One term and value of a `<dl>` on a detail page, with an optional note under the value. */
export function Fact({ term, value, note }: { term: string; value: string; note?: string | null }) {
  return (
    <div className="flex justify-between gap-4 border-b py-1 text-sm last:border-0">
      <dt className="text-muted-foreground">{term}</dt>
      <dd className="text-right">
        {value}
        {note && <span className="text-muted-foreground block text-xs">{note}</span>}
      </dd>
    </div>
  )
}
