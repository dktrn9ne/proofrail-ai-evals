# Enterprise Readiness Roadmap

Proofrail is an enterprise-oriented prototype. Its current release is intended for local evaluation, reproducible demonstrations, and CI quality gates. The following capabilities are required before production enterprise deployment.

## Current capabilities

- Provider-neutral evidence envelope
- Text, structured JSON, conversation, tool-call, trace, and artifact metadata support
- Version-controlled evaluation specifications and thresholds
- Oracle and negative controls
- Repeated-trial scoring and failure classification
- Extensible deterministic and calibrated-review evaluators
- Markdown and JSON evidence reports
- GitHub Actions release gating
- Latency and cost summaries

## Next engineering milestones

### Reproducibility and statistics

- Dataset, prompt, rubric, model, and evaluator versioning
- Baseline comparisons and regression-delta reporting
- Confidence intervals, significance tests, and minimum sample-size policies
- Performance slices by market, language, user group, workflow, and risk level
- Judge agreement, calibration sets, and adjudication workflows

### Execution and observability

- Provider adapters and asynchronous trial orchestration
- Concurrency controls, retries, timeouts, and failure isolation
- Durable run storage and immutable evidence manifests
- Production telemetry ingestion and drift monitoring
- Alerts, dashboards, APIs, and scheduled evaluations

### Security and governance

- Authentication, role-based access, and tenant isolation
- Secrets management and configurable retention policies
- PII detection, redaction, and regional data controls
- Signed artifacts, tamper-evident audit records, and approval workflows
- Sandboxed execution for untrusted tools and evaluators

### Agent assurance

- Permission-boundary and least-privilege tests
- Prompt-injection, data-exfiltration, and adversarial tool-use suites
- Recovery, escalation, idempotency, and long-horizon reliability metrics
- Human-override and fail-safe validation

## Maturity statement

The current code demonstrates the evaluation contract and quality-gate design. It should not be represented as a fully operated enterprise service until the security, scale, governance, and statistical milestones above are implemented and validated.
