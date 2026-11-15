## MODIFIED Requirements

### Requirement: Profile page
The signed-in profile page SHALL show:
- the summary;
- skills grouped by category, each with a bar whose label describes its evidence (for example "8 repositories · dependencies · README") rather than a percentage or an expertise claim;
- each skill's evidence records on demand, with links to supporting repositories;
- interests with their evidence, each record with its source, supporting repository, detail and when it was observed, as for skills;
- a languages chart;
- the repository list, the last-synced time and Refresh.

The page SHALL NOT display numeric confidence values or the experience level. Every skill SHALL be shown under its category, whatever the category; a skill whose evidence names no repository and no other kind SHALL still have a non-empty label. A skill's full name SHALL be readable even when the bar truncates it. Expanded skills and interests SHALL stay expanded when the profile is refreshed by a new analysis and the skill or interest is still detected. Each list on the page SHALL have a distinct accessible name (for example "Language skills" and "Languages by code"). The languages chart SHALL show the top languages by bytes, ordered by bytes whatever order the API returns, and fold the rest into "Other" only when two or more languages are left over; a single leftover language SHALL be shown by name. Every share in the chart, "Other" included, SHALL be computed from bytes, so the shown rows always account for all of the user's code. A language with a nonzero share under 1% SHALL be shown as "<1%", never as "0%".

#### Scenario: Evidence label
- **WHEN** Python has evidence from 8 repositories including dependency and README evidence
- **THEN** its bar is labeled with those evidence facts and no percentage is shown

#### Scenario: Evidence detail
- **WHEN** the user expands the Django skill
- **THEN** the page lists each evidence record with its source and a link to the supporting repository

#### Scenario: Profile not yet analyzed
- **WHEN** the user has synced data but no analyzed profile
- **THEN** the page shows the synced repositories and a message that the profile is being prepared, instead of an error

#### Scenario: Many small languages
- **WHEN** the user has 8 large languages and 12 more that each hold 0.3% of their bytes
- **THEN** the chart shows the 8 languages plus "Other" at 4%

#### Scenario: Tiny language in the top rows
- **WHEN** one of the top languages holds 0.2% of the bytes
- **THEN** it is shown as "<1%"

#### Scenario: Nine languages
- **WHEN** the user has exactly 9 languages
- **THEN** the chart shows all 9 by name and no "Other" row

#### Scenario: Expanded skill survives a refresh
- **WHEN** the user has Django's evidence expanded and a re-analysis that still detects Django finishes
- **THEN** Django's evidence stays expanded with the new records

#### Scenario: Distinct list names
- **WHEN** a screen-reader user lists the page's lists
- **THEN** the language skills and the languages chart have different names
