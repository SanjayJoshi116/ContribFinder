## ADDED Requirements

### Requirement: Difficulty signals are declared in the API schema

The OpenAPI schema of the issue detail endpoint SHALL describe the difficulty evidence: a list of
signals, each with a signal name from a declared set (`label`, `body_length`, `technology_count`,
`contribution_type`, `comments`), the difficulty it voted for or null, and its value; the vote
count per difficulty; and the thresholds used. The classifier SHALL write only signal names from
that set, and every name in the set SHALL have words on the issue detail page. The response body
SHALL be unchanged, and the page SHALL still skip a stored signal it does not know.

#### Scenario: Schema names the signals

- **WHEN** a client reads the OpenAPI schema
- **THEN** the issue detail's difficulty evidence lists its signals with the declared signal
  names as an enumeration

#### Scenario: New signal without words

- **WHEN** the declared set gains a signal name and the issue page has no words for it
- **THEN** the frontend type check fails

#### Scenario: Classifier writes an undeclared signal

- **WHEN** the classifier writes a signal name outside the declared set
- **THEN** the backend tests fail

#### Scenario: Unknown stored signal

- **WHEN** stored evidence holds a signal name the page does not know
- **THEN** the page leaves it out and shows the others
