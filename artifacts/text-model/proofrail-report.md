# Proofrail Model Evaluation Review

**Evaluation:** LedgerKit verifier semantics
**Decision:** RELEASE

## Gate summary

| Stage | Result | Evidence |
|---|---:|---|
| Intake scan | PASS | 0 specification errors |
| Overlap scan | PASS | Maximum similarity 0.102 |
| Anchor controls | PASS | Oracle 1.000; negative 0.000 |
| Trial scoring | PASS | 2/3 passed; mean 0.659 |
| Release gate | PASS | RELEASE |

## Trial evidence

| Run | Score | Result | Failed criteria |
|---|---:|---:|---|
| trial-01 | 0.993 | PASS | None |
| trial-02 | 0.985 | PASS | None |
| trial-03 | 0.000 | FAIL | verification_contract, fail_closed, review_quality, forbidden:accept.*without.*verif |

## Failure patterns

- **verification_contract:** 1 occurrence(s)
- **fail_closed:** 1 occurrence(s)
- **review_quality:** 1 occurrence(s)
- **forbidden:accept.*without.*verif:** 1 occurrence(s)

## Performance and spend

- Total recorded cost: $0.036100
- Average recorded cost: $0.012033
- Average latency: 1133.33 ms

## Interpretation

A release decision requires a valid specification, acceptable task originality, discriminating anchor controls, and the configured pass rate across repeated trials. Criterion-level failures remain visible even when the aggregate gate passes.
