# Regression Corpus

The regression corpus turns evaluation history into reusable quality coverage. Each record identifies the scenario, objective, failure class, evidence classification, and promotion status.

The public example corpus is entirely synthetic and demonstrates five record types:

- Successful Oracle control
- NO OP negative control
- Unsafe failed run
- Adjudicated rework
- Infrastructure failure classification

## Promotion requirements

A record should be promoted only when:

- Its expected result has been adjudicated.
- Its failure class is stable and actionable.
- It adds coverage rather than duplicating an existing case.
- Sensitive evidence has been removed or governed appropriately.
- The record is versioned and traceable to an owner and source.
- Infrastructure failures are not mislabeled as model failures.

Corpus novelty is checked before release so near-duplicate tasks do not create misleading test-volume growth.
