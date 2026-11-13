## ADDED Requirements

### Requirement: Eligibility re-check stamped when made
A state change made by the pool step's eligibility re-check (see "Candidate pool maintenance") SHALL record the time the change is made as the repository's last transition time, not the time the discovery run started, so that another developer's recommendation freshness (`recommendation-engine` "Recommendation freshness") sees every change made after their last generation started.

#### Scenario: Another developer's generation started during the run
- **WHEN** developer A's discovery run starts at 10:00, developer B's generation starts at 10:10, and A's pool step at 10:20 makes a repository in both pools INDEXED and ineligible
- **THEN** the repository's last transition time is 10:20, and the next freshness run starts a generation for B
