## MODIFIED Requirements

### Requirement: Relevance signals
For each candidate, the system SHALL calculate these signals independently, each as a value from 0.0 to 1.0 together with the evidence that produced it:
- **skill match**: how much of the repository's technology set the developer has demonstrated, weighted by the developer's confidence in each skill;
- **language match**: the repository's code share in languages the developer knows, weighted by the developer's confidence in each language;
- **framework match**: overlap between the repository's frameworks and the developer's framework skills;
- **interest match**: overlap between the interests the repository's topics and description express and the developer's detected interests, weighted by interest strength;
- **activity signal**: the repository's activity label at generation time (see `repository-activity` "Activity label"), mapped to a configured value; its evidence gives the days since the last push measured at generation and the latest snapshot's counts;
- **contribution openness**: observable contribution affordances (contribution guidelines, issue templates, `good first issue` and `help wanted` labels), each worth a configured amount;
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
