# Evaluation Lifecycle

Proofrail treats evaluation assets as a continuously improving quality system rather than a one-time score.

## 1 Define the evaluation

Write a versioned specification containing the objective, risk classification, ownership, rubric, evaluator parameters, release thresholds, evidence policy, and execution-isolation declaration.

## 2 Run the 21-surface preflight

Preflight blocks incomplete or weak evaluation designs before candidate outputs are scored. Each surface produces a Boolean result and human-readable evidence.

The surfaces are:

1. Specification identity
2. Objective definition
3. Risk classification
4. Traceability
5. Rubric presence
6. Criterion identity
7. Criterion descriptions
8. Weight integrity
9. Evaluator support
10. Evaluator parameters
11. Gate thresholds
12. Oracle control
13. Negative control
14. Control discrimination
15. Trial coverage
16. Trial integrity
17. Evidence coverage
18. Protected evidence
19. Process isolation
20. Corpus integrity
21. Corpus novelty

## 3 Prove the controls

The Oracle is a known-good response expected to pass. NO OP is a deliberately empty response expected to fail. If the evaluation cannot separate them, the suite is blocked regardless of candidate performance.

## 4 Score repeated trials

Repeated runs reveal reliability and variance. Proofrail preserves criterion-level evidence, prohibited-pattern hits, model identity, provider identity, latency, and cost.

## 5 Classify failures

Failures are assigned to reusable classes such as grounding, unsafe instruction, traceability, tool execution, or infrastructure. Infrastructure faults remain separate from model-quality defects.

## 6 Adjudicate and promote

Reviewed failures, corrected edge cases, successful controls, and infrastructure classifications can be promoted into the regression corpus. Only synthetic, public, or properly governed evidence belongs in a public corpus.

## 7 Enforce the release gate

CI blocks release when preflight fails, controls do not discriminate, overlap exceeds the novelty threshold, or too few repeated trials meet the configured score.
