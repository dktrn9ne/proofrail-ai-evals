# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub Security Advisories. Do not open a public issue containing exploit details, credentials, private model outputs, or customer data.

## Trust boundaries

Proofrail evaluates supplied evidence and does not require model-provider credentials. Keep collection adapters and secrets outside the repository and pass only the evidence required for evaluation.

Custom evaluator modules execute local Python code with the permissions of the Proofrail process. Load evaluator modules only from trusted, reviewed sources.

Before retaining or publishing evaluation evidence:

- Remove credentials, tokens, personal information, and confidential prompts.
- Apply least-privilege access to reports and datasets.
- Treat model outputs and execution traces as potentially sensitive.
- Review tool arguments and results for embedded secrets.
- Avoid evaluating untrusted artifacts without appropriate isolation.

Proofrail is currently a prototype and has not undergone an independent security audit.
