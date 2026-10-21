import { Link } from 'react-router'

/** A page that cannot show what was asked for: what happened, and the way back. */
export function DeadEnd({ message }: { message: string }) {
  return (
    <div className="space-y-2">
      <p role="alert">{message}</p>
      <Link to="/app" className="text-sm underline">
        Back to your dashboard
      </Link>
    </div>
  )
}
