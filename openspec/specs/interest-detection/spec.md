# interest-detection Specification

## Purpose

Identifies which problem domains a developer appears interested in, such as AI, developer tooling, web or security. It uses what they write and build, matched through synonyms rather than exact keywords, and records evidence for every interest so matching can explain it.

## Requirements

### Requirement: Interest catalog
The system SHALL detect interests only against a canonical interest catalog. It covers at least AI / machine learning, developer tooling, open source, web development, databases, infrastructure / cloud, security, data engineering, mobile development, DevOps, systems programming, game development, scientific computing and education. Each interest SHALL have a stable identifier, a display name, synonym phrases and topic mappings, so that different wordings of the same domain resolve to one interest.

#### Scenario: Synonyms resolve to one interest
- **WHEN** one repository description says "machine learning pipeline", another has the topic `llm` and the README mentions "deep learning"
- **THEN** the developer has one AI / machine learning interest with three pieces of evidence

### Requirement: Interest sources
The system SHALL collect interest evidence from:
- the profile README;
- descriptions of the user's owned non-fork repositories;
- topics of those repositories;
- topics and descriptions of repositories the user contributed to.

Each evidence record SHALL state its source (readme, repo_description, topic or contribution), the supporting repository when there is one, the matched phrase or topic, and when it was observed. Phrases SHALL match on word boundaries, case-insensitively. Forked repositories SHALL NOT provide evidence.

#### Scenario: Topic evidence
- **WHEN** an owned repository has the topic `developer-tools`
- **THEN** the developer tooling interest has topic evidence naming that repository and topic

#### Scenario: Word boundary
- **WHEN** a repository description contains "maintain" but no AI-related phrase
- **THEN** it provides no AI evidence (the synonym "ai" does not match inside "maintain")

#### Scenario: Contributed repository
- **WHEN** the user has a merged pull request to a repository with the topic `security`
- **THEN** the security interest has contribution evidence naming that repository

### Requirement: Interest strength and threshold
Each interest SHALL have a strength between 0 and 1, computed from its evidence with configurable per-source weights and the same diminishing-returns rule as skill confidence. An interest SHALL be part of the profile only when its strength reaches a configured minimum or it has evidence from at least two distinct repositories. Interests SHALL be ordered by strength.

#### Scenario: Single weak mention excluded
- **WHEN** the only evidence for mobile development is a single README phrase and its strength is below the minimum
- **THEN** mobile development is not among the developer's interests

#### Scenario: Repeated across repositories
- **WHEN** developer tooling has topic evidence from three different repositories
- **THEN** developer tooling is among the developer's interests
