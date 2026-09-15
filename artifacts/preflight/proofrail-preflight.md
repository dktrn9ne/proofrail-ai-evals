# Proofrail Preflight Review

**Specification:** ledgerkit-verifier-semantics-v1
**Decision:** PASS
**Coverage:** 21/21 validation surfaces passed

| Validation surface | Result | Evidence |
|---|---:|---|
| specification_identity | PASS | id, name, and version are required |
| objective_definition | PASS | objective must contain at least 20 characters |
| risk_classification | PASS | risk_level=high |
| traceability | PASS | metadata.owner and metadata.source are required |
| rubric_presence | PASS | criteria=4 |
| criterion_identity | PASS | criterion ids must be present and unique |
| criterion_descriptions | PASS | every criterion requires a description |
| weight_integrity | PASS | weight_total=1.000000 |
| evaluator_support | PASS | available=9 evaluators |
| evaluator_parameters | PASS | built-in evaluator parameters must be valid |
| gate_thresholds | PASS | min_trials=3 |
| oracle_control | PASS | known-good control is required |
| negative_control | PASS | NO OP negative control is required |
| control_discrimination | PASS | oracle=1.000; no_op=0.000 |
| trial_coverage | PASS | runs=3; required=3 |
| trial_integrity | PASS | run ids must be unique and telemetry non-negative |
| evidence_coverage | PASS | every run requires output, messages, tool calls, trace, or artifacts |
| protected_evidence | PASS | classification=synthetic; secrets_scanned=True |
| process_isolation | PASS | isolated=True |
| corpus_integrity | PASS | corpus_records=5 |
| corpus_novelty | PASS | maximum_similarity=0.269; limit=0.82 |
