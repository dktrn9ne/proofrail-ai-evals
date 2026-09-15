# Proofrail Model Evaluation Review

Proofrail is a provider-neutral quality gate for reviewing any AI model or agent before release. It converts an evaluation specification, a comparison corpus, and repeated model runs into a traceable pass or fail decision. It does not depend on a particular vendor SDK or API.

> **Maturity:** Proofrail is an enterprise-oriented prototype for local evaluation and CI quality gates. It is not yet a fully operated enterprise service. See the [enterprise readiness roadmap](docs/enterprise-roadmap.md).

## What it checks

1. **Intake scan** validates rubric weights, evaluator configuration, identifiers, and release thresholds.
2. **Overlap scan** detects evaluation tasks that are too similar to an existing corpus using TF-IDF cosine similarity.
3. **Anchor controls** require a known-good oracle to pass and a deliberately empty negative control to fail.
4. **Trial scoring** evaluates every run against deterministic rubric criteria and records criterion-level evidence.
5. **Evidence audit** summarizes recurring failure classes rather than reporting only an aggregate score.
6. **Release gate** combines specification validity, originality, control discrimination, score, and pass-rate requirements.
7. **Spend summary** reports total and average latency and cost when run metadata is available.

The included evaluators are deliberately deterministic and dependency-free. They are suitable for structural, policy, tool-use, agent-trace, and expected-content checks. Subjective criteria can be supplied as review scores in each run, allowing a calibrated human or model judge to plug into the same gate.

## Universal run envelope

Proofrail evaluates a common JSON envelope, so the source can be OpenAI, Anthropic, Google, Meta, Mistral, an open-source local model, a multimodal system, or a custom agent framework. A run can contain any combination of:

```json
{
  "id": "trial-01",
  "provider": "any-provider-or-local",
  "model": "any-model-name",
  "input": {"messages": []},
  "output": "text or any JSON value",
  "messages": [{"role": "assistant", "content": "optional transcript"}],
  "tool_calls": [{"name": "search", "arguments": {}, "status": "success", "result": {}}],
  "trace": [{"event": "plan_created", "timestamp": "optional"}],
  "artifacts": [{"type": "image", "uri": "result.png", "metadata": {}}],
  "review_scores": {"subjective_criterion": 0.9},
  "latency_ms": 1200,
  "cost_usd": 0.012
}
```

Provider-specific collection stays outside the scoring engine. This separation lets the same tests compare hosted APIs, local models, new model versions, and agent frameworks without rewriting the gate. Multimodal predictions and artifact metadata can travel in `output` or `artifacts`; use a custom evaluator when the artifact itself must be inspected.

Anchor controls may use the same complete envelope. An agent evaluation can therefore prove that the oracle uses the required tools and emits the required trace, while the negative control omits them and fails.

## Quick start

From this directory:

```powershell
python -m proofrail review --spec examples/ledgerkit/spec.json --runs examples/ledgerkit/runs.json --corpus examples/corpus.json --out artifacts
```

The command writes:

- `artifacts/proofrail-report.md`
- `artifacts/proofrail-results.json`

It exits with code `0` when the release gate passes and `1` when it fails, so the same command can protect a pull request.

## Evaluation specification

Each rubric item has an ID, description, weight, evaluator, and parameters. Supported evaluators are:

- `contains_all`
- `contains_any`
- `regex`
- `max_length`
- `json_keys`
- `manual`
- `tool_called`
- `tool_success_rate`
- `trace_contains`

For `manual`, a run supplies a value from `0.0` to `1.0` in `review_scores`. This keeps external judging explicit and auditable instead of hiding it inside the pipeline.

## Custom evaluators

Domain-specific requirements can be added without modifying Proofrail. Supply a trusted Python module containing an `EVALUATORS` dictionary:

```python
def reserve_floor(criterion, run, normalized_text):
    reserve = run["output"]["reserve_percent"]
    minimum = criterion["params"]["minimum"]
    return (1.0 if reserve >= minimum else 0.0, f"reserve={reserve}; minimum={minimum}")

EVALUATORS = {"reserve_floor": reserve_floor}
```

Then run:

```powershell
python -m proofrail review --spec spec.json --runs runs.json --evaluators custom_evaluators.py --out artifacts
```

Custom evaluator modules execute local Python code and should only be loaded from trusted sources.

## GitHub Actions

The workflow at `.github/workflows/proofrail-review.yml` runs unit tests and the sample review on pull requests. Replace the sample paths with the evaluation assets used by the repository.

## Design principles

- A passing candidate is insufficient if the evaluation itself cannot reject a null response.
- Aggregate scores never replace criterion-level evidence.
- Release thresholds live in version-controlled specifications.
- Repeated trials reveal reliability that a single answer cannot.
- Automated graders should be calibrated against anchors and reviewed for disagreement.

## Architecture and scope

The [architecture overview](docs/architecture.md) explains the provider-neutral evidence contract and release semantics. The [enterprise readiness roadmap](docs/enterprise-roadmap.md) distinguishes implemented capabilities from the security, statistical, execution, and governance work still required for production deployment.

## Security

Never commit model-provider credentials, confidential prompts, client data, or unredacted production traces. Custom evaluators are executable code and should only be loaded from trusted sources. See [SECURITY.md](SECURITY.md).

## License

MIT
