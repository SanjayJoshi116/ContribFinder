## MODIFIED Requirements

### Requirement: Candidate pool maintenance
A candidate that no discovery run has found for the configured retention period (default 30 days) SHALL be removed from the pool. On every discovery run, before the size cap applies:
- a candidate whose stored repository data shows it is not a code project (the `not_code` rule of "Candidate eligibility" for an analyzed repository, of "Candidate pre-filtering" otherwise) SHALL be removed from the pool, and the job SHALL record how many were removed;
- every eligibility rule of "Candidate eligibility" SHALL be re-checked on the stored data of the pool's analyzed repositories, with the current settings and time, without waiting for their next analysis. A repository whose eligibility changes SHALL get the new eligibility and reason, and SHALL be RECOMMENDABLE when eligible and INDEXED when not (a STALE repository keeps STALE and returns to the matching state after its refresh). A repository that an analysis currently holds, a FAILED repository and a repository never analyzed SHALL be left unchanged, and an existing reason SHALL be replaced only by the reason the rules give now.

After a run's analysis step has analyzed the repositories it planned, the run SHALL remove from the pool every candidate whose repository it analyzed and whose stored data now shows it is not a code project (the same `not_code` rule), SHALL record how many it removed, and SHALL record the pool size and band counts again. A cancelled or reclaimed run SHALL remove nothing at that point. Shared repository data SHALL NOT be deleted by this removal.

The pool SHALL NOT exceed the configured size (default 300). When it would, the system SHALL keep the candidates first in the pool order (previously interacted, then best search rank, then most recently found, then repository name) and remove the rest. The cap SHALL apply before the run analyzes anything, so the run analyzes only kept candidates, in the same order. Because search ranks are counted per band, the kept pool SHALL contain candidates from every band that returned results. The discovery job SHALL record the number of pool candidates in each star band, counting a repository in the band whose range holds its current stars, under `below` when it has fewer stars than the lowest band, and under `other` when no band holds it. Deleting the developer profile SHALL delete its candidates and discovery records. Shared repository data SHALL NOT be deleted when a candidate is removed.

#### Scenario: Expired candidate
- **WHEN** a candidate was last found 31 days ago and the retention period is 30 days
- **THEN** the next discovery run removes it from the pool

#### Scenario: Pool cap
- **WHEN** a run would bring the pool to 320 candidates and the cap is 300
- **THEN** the 20 candidates with the worst search rank that are not previously interacted are removed

#### Scenario: Small pool for fast runs
- **WHEN** the cap is 10 and a run finds 220 candidates
- **THEN** the pool keeps the 10 best-ranked candidates, and the run analyzes no other candidate

#### Scenario: List found before the rule
- **WHEN** a pool holds `public-apis/public-apis` (topic `lists`, no manifest dependencies) from a run before the `not_code` rule, and its analysis is still fresh
- **THEN** the next discovery run removes it from the pool, marks the repository ineligible with `not_code`, and records one removal

#### Scenario: Settings change re-checked
- **WHEN** the push window is shortened from 180 to 90 days and a RECOMMENDABLE pool repository was last pushed 120 days ago
- **THEN** the next discovery run makes it INDEXED and ineligible with the reason `inactive`

#### Scenario: Failed repository keeps its reason
- **WHEN** a FAILED repository in the pool has the reason `repository_unavailable` and is also a curated list
- **THEN** the discovery run leaves its state and reason unchanged

#### Scenario: Repository under analysis left alone
- **WHEN** a pool repository is REFRESHING for another developer's discovery when the pool step runs
- **THEN** the pool step does not change its eligibility or state, and the refresh decides them

#### Scenario: Mixed sizes kept
- **WHEN** the cap is 40, there are two bands, and every query returns 30 results in each band
- **THEN** the kept pool holds candidates from both bands, and the job metadata records how many are in each

#### Scenario: Band with a gap
- **WHEN** the bands are 20–99 and 200–999 and the pool holds repositories with 150 and 5000 stars
- **THEN** both are counted under `other`, not in a band

#### Scenario: List found by this run's analysis
- **WHEN** a run's search finds `vinta/awesome-python` for the first time, the pool step keeps it (not yet analyzed), and the run's analysis finds no manifest dependency
- **THEN** at the end of the run it is no longer in the pool, the job records one removal after analysis, and the recorded pool size and band counts no longer include it

#### Scenario: Code project analyzed
- **WHEN** a run's analysis finds a suspected list that declares manifest dependencies
- **THEN** it stays in the pool after the run

#### Scenario: Candidate not analyzed this run
- **WHEN** a pool candidate was not in the run's analysis plan
- **THEN** the removal after analysis leaves it to the next run's pool step

