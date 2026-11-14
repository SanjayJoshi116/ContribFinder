## MODIFIED Requirements

### Requirement: Relevance signals
For each candidate, the system SHALL calculate these signals independently, each as a value from 0.0 to 1.0 together with the evidence that produced it:
- **skill match**: how much of the repository's technology set the developer has demonstrated, weighted by the developer's confidence in each skill;
- **language match**: the repository's code share in languages the developer knows, weighted by the developer's confidence in each language;
- **framework match**: overlap between the repository's frameworks and the developer's framework skills; a framework whose weight in the repository is 0 (found only through a source the configuration weights 0) SHALL NOT count;
- **interest match**: overlap between the interests the repository's topics and description express and the developer's detected interests, weighted by interest strength;
- **activity signal**: the repository's activity label at generation time (see `repository-activity` "Activity label"), mapped to a configured value; its evidence gives the days since the last push measured at generation and the latest snapshot's counts;
- **contribution openness**: observable contribution affordances (contribution guidelines, issue templates, `good first issue` and `help wanted` labels), each worth a configured amount; its evidence SHALL name only affordances worth more than 0;
- **issue fit**: the availability of relevant issues for the developer in the repository (see `issue-matching`), growing with their number and scores up to a configured saturation count;
- **difficulty fit**: how well the estimated difficulty of the repository's relevant issues suits the developer's internal experience level; issues with `unknown` difficulty SHALL NOT contribute. The configuration SHALL choose the mode: `best` (the default when the configuration names none) takes the best difficulty-table value among the relevant issues with known difficulty; `weighted` takes the mean of their table values weighted by issue score, multiplied by the issue fit value.

A signal with no supporting data SHALL be 0 with no evidence; it SHALL NOT be guessed. Skills whose only evidence is a README mention SHALL count at their stored (low) confidence and never as full matches. No single signal SHALL determine a recommendation on its own. Signal calculation SHALL NOT call GitHub or any AI service.

#### Scenario: Strong Python/Django match
- **WHEN** the developer has high-confidence Python and Django skills and the repository is mostly Python and depends on Django
- **THEN** language match and framework match are high, and their evidence names Python and Django

#### Scenario: Unknown activity
- **WHEN** a repository has no activity snapshot
- **THEN** its activity signal is 0 with no evidence

#### Scenario: Activity measured at generation
- **WHEN** a repository's latest snapshot was captured 40 days ago with its last push that day, and recommendations are generated now
- **THEN** its activity evidence gives 40 days since the last push, and its activity signal uses the label for that age

#### Scenario: Deterministic
- **WHEN** signals are calculated twice for the same profile, repository data and configuration
- **THEN** the values and evidence are identical

#### Scenario: No relevant issues
- **WHEN** a repository has no relevant issues for the developer
- **THEN** its issue fit and difficulty fit are 0 with no evidence

#### Scenario: Only unknown difficulties
- **WHEN** all of a repository's relevant issues have `unknown` difficulty
- **THEN** its issue fit is above 0 and its difficulty fit is 0

#### Scenario: One weak fitting issue, weighted mode
- **WHEN** a repository has a single relevant beginner issue for a beginner developer, its issue fit is 0.2, and the configuration uses `weighted` difficulty fit
- **THEN** its difficulty fit is 0.2, whereas under `best` it would be 1.0

#### Scenario: Mixed difficulties, weighted mode
- **WHEN** an intermediate developer's repository has two relevant issues with known difficulty, one beginner (table value 0.7, issue score 0.6) and one intermediate (table value 1.0, issue score 0.3), issue fit is 0.3, and the mode is `weighted`
- **THEN** its difficulty fit is ((0.7 × 0.6 + 1.0 × 0.3) / 0.9) × 0.3 = 0.24

#### Scenario: Framework from a source weighted 0
- **WHEN** a configuration weights topic technologies 0, and a repository is tagged `django` without depending on Django, for a developer with a Django skill
- **THEN** its framework match is 0 with no evidence

#### Scenario: Openness point worth 0
- **WHEN** a configuration gives issue templates 0 points and a repository has a contributing guide and issue templates
- **THEN** its openness evidence names the contributing guide only

### Requirement: Recommendation freshness
The system SHALL periodically (configured interval, default 30 minutes) start a generation job for every developer whose recommendations are older than their profile analysis, older than the latest analysis of a repository in their pool, or produced by a configuration that is no longer active; a developer whose last completed generation ran under a configuration that is no longer active SHALL be due even when it stored no recommendations. A repository being marked stale or picked up for a refresh SHALL NOT by itself make recommendations outdated; new data fetched for it (even if it was marked stale since), a completed refresh, a failure or any other analysis SHALL. When the developer's latest finished generation failed, the next one SHALL wait a configured delay (default 6 hours) after that failure unless the user or a pipeline step starts it; a failure followed by a completed generation SHALL NOT delay the sweep. A developer who has recommendations but no candidates left SHALL also get a generation job. It SHALL NOT start a job for a developer whose recommendations are current, or who has an active generation job. A job that cannot be queued for one developer SHALL NOT stop the run for the others.

#### Scenario: Repository refreshed
- **WHEN** the backlog refreshes a pooled repository after the developer's recommendations were generated
- **THEN** the next freshness run starts a generation job for that developer

#### Scenario: New configuration activated
- **WHEN** an operator activates configuration `v2`
- **THEN** the next freshness run regenerates every developer's recommendations under `v2`

#### Scenario: Nothing changed
- **WHEN** nothing relevant changed since the last generation
- **THEN** no job is started

#### Scenario: Marked stale only
- **WHEN** the staleness sweep marks a pooled repository stale and nothing else changed since the last generation
- **THEN** no job is started

#### Scenario: Analyzed, then marked stale before the sweep
- **WHEN** a pooled repository is analyzed after the last generation and marked stale before the next freshness run
- **THEN** that run starts a generation job

#### Scenario: Running generation left alone
- **WHEN** a developer is due and their generation job is running
- **THEN** the freshness run starts nothing and does not ask the running job to run again

#### Scenario: Failed generation backs off
- **WHEN** a developer's latest generation failed 10 minutes ago and they are otherwise due
- **THEN** the freshness run starts no job; after the configured delay it does

#### Scenario: Pool emptied
- **WHEN** a developer has recommendations and their candidate pool became empty
- **THEN** the next freshness run starts a generation job, which leaves them with no recommendations

#### Scenario: Failure followed by a success
- **WHEN** a developer's generation failed 30 minutes ago, a later generation completed 20 minutes ago, and their profile was re-analyzed 10 minutes ago
- **THEN** the next freshness run starts a generation job

#### Scenario: New configuration for a developer with no recommendations
- **WHEN** a developer's last completed generation under `v2` stored no recommendations and an operator activates `v3`
- **THEN** the next freshness run starts a generation job for that developer

#### Scenario: Queuing fails for one developer
- **WHEN** two developers are due and queuing the first one's job fails
- **THEN** the freshness run still starts the second one's job

