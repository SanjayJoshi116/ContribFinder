import { Link } from 'react-router'

interface Category {
  name: string
  purpose: string
  retention: string
}

const UNTIL_DELETED = 'Until you delete your GitHub data, disconnect GitHub or delete your account.'

const CATEGORIES: Category[] = [
  {
    name: 'GitHub account ID',
    purpose:
      'The number GitHub gives your account. It links you back to your ContribFinder account when you sign in again.',
    retention: 'Until you delete your account.',
  },
  {
    name: 'GitHub username, avatar and display name',
    purpose: 'To show who is signed in.',
    retention: UNTIL_DELETED,
  },
  {
    name: 'GitHub access credential (encrypted)',
    purpose:
      'To read your public GitHub data in the background. It grants no extra permissions and is never shown or sent to your browser.',
    retention: 'Until you disconnect GitHub or delete your account; it is revoked on GitHub too.',
  },
  {
    name: 'Public profile information',
    purpose: 'Name, bio, company, location and similar, to describe your profile.',
    retention: UNTIL_DELETED,
  },
  {
    name: 'Profile README',
    purpose: 'To detect skills and interests you describe yourself.',
    retention: UNTIL_DELETED,
  },
  {
    name: 'Public repository metadata and README content',
    purpose:
      'Languages, topics, dependencies, activity and contribution guidelines of your repositories and of candidate projects, to build your profile and match projects.',
    retention:
      'Your links to repositories: until deleted. Public project data shared with other users is removed once no one references it.',
  },
  {
    name: 'Public contribution information',
    purpose: 'Merged pull requests and recent public pushes, as evidence for your skills.',
    retention: UNTIL_DELETED,
  },
  {
    name: 'Derived developer profile',
    purpose: 'Skills, interests and the evidence behind them, used only for matching.',
    retention: UNTIL_DELETED,
  },
  {
    name: 'Candidate projects and search queries',
    purpose:
      'Projects found for you, and the GitHub searches built from your skills and interests that found them.',
    retention: UNTIL_DELETED,
  },
  {
    name: 'Recommendations',
    purpose: 'Matched projects and the reasons they match.',
    retention: UNTIL_DELETED,
  },
  {
    name: 'Saved and hidden projects',
    purpose:
      'To keep the projects you saved and never recommend the ones you hid, with the reason you gave for hiding one, if any.',
    retention: UNTIL_DELETED,
  },
  {
    name: 'Feedback events',
    purpose:
      'Which recommendations you viewed, saved, hid (with the optional reason) or opened, to evaluate recommendation quality. They do not change your ranking.',
    retention: UNTIL_DELETED,
  },
  {
    name: 'Sync and job history',
    purpose: 'When your data was last synced, analyzed and matched, and whether a step failed.',
    retention: UNTIL_DELETED,
  },
  {
    name: 'Sign-in sessions',
    purpose: 'To keep you signed in on this device.',
    retention:
      'Until you sign out, or for 14 days. Disconnecting GitHub ends your sessions on every device.',
  },
  {
    name: 'Audit entries',
    purpose:
      'A record of sign-ins, disconnects and deletions, with a one-way hash of the network address, for security. They never contain credentials.',
    retention:
      'Kept after account deletion, without any link to you: your GitHub ID, username and address hash are removed from them.',
  },
]

/** Public: what ContribFinder stores, why, for how long, and how to delete it. */
export function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl space-y-8 px-4 py-10 sm:px-6">
      <Link to="/" className="text-muted-foreground text-sm hover:underline">
        ← ContribFinder
      </Link>
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Your data in ContribFinder</h1>
        <p className="text-muted-foreground">
          ContribFinder reads only public GitHub data and stores what it needs to recommend
          open-source projects. Nothing is sold or shared, and no AI service receives your data.
        </p>
      </header>

      <section className="space-y-4" aria-labelledby="stored-heading">
        <h2 id="stored-heading" className="font-medium">
          What we store
        </h2>
        <dl className="space-y-4">
          {CATEGORIES.map((category) => (
            <div key={category.name} className="space-y-1 rounded-md border p-4">
              <dt className="font-medium">{category.name}</dt>
              <dd className="text-sm">{category.purpose}</dd>
              <dd className="text-muted-foreground text-sm">Kept: {category.retention}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="space-y-2" aria-labelledby="delete-heading">
        <h2 id="delete-heading" className="font-medium">
          How to delete it
        </h2>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>
            <strong>Delete GitHub data</strong> (dashboard, &ldquo;Your data&rdquo;) removes
            everything derived from GitHub at once. Your account and connection stay, so you can
            sync again.
          </li>
          <li>
            <strong>Disconnect GitHub</strong> revokes access on GitHub, deletes the credential and
            your GitHub data, and signs you out.
          </li>
          <li>
            <strong>Delete account</strong> does all of the above and deletes the account itself.
          </li>
        </ul>
        <p className="text-muted-foreground text-sm">
          Deletion is immediate. Cached GitHub responses fetched with your access are removed with
          it, or expire within 24 hours.
        </p>
      </section>
    </main>
  )
}
