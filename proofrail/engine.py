from __future__ import annotations

from collections import Counter
from typing import Any

from .checks import Evaluator, overlap_scan, score_output, validate_runs, validate_spec


def _control_run(identifier: str, value: Any, review_scores: dict[str, float]) -> dict[str, Any]:
    envelope_fields = {"output", "messages", "tool_calls", "trace", "latency_ms", "cost_usd", "provider", "model"}
    if isinstance(value, dict) and envelope_fields.intersection(value):
        run = dict(value)
        run["id"] = identifier
    else:
        run = {"id": identifier, "output": value}
    run["review_scores"] = review_scores
    return run


def run_review(
    spec: dict[str, Any],
    runs: list[dict[str, Any]],
    corpus: list[dict[str, Any]] | None = None,
    custom_evaluators: dict[str, Evaluator] | None = None,
) -> dict[str, Any]:
    intake_errors = validate_spec(spec, set((custom_evaluators or {}).keys())) + validate_runs(runs)
    if intake_errors:
        return {
            "framework": "Proofrail",
            "spec_id": spec.get("id", "unknown"),
            "decision": "BLOCK",
            "stages": {"intake_scan": {"passed": False, "errors": intake_errors}},
        }

    overlap = overlap_scan(spec, corpus or [])
    overlap_passed = overlap["maximum"] <= float(spec["gate"]["max_overlap"])

    oracle = score_output(spec, _control_run("oracle", spec["controls"]["oracle"], spec["controls"].get("oracle_review_scores", {})), custom_evaluators)
    negative = score_output(spec, _control_run("negative", spec["controls"]["negative"], spec["controls"].get("negative_review_scores", {})), custom_evaluators)
    controls_passed = oracle["passed"] and not negative["passed"]

    scored_runs = [score_output(spec, run, custom_evaluators) for run in runs]
    passed_count = sum(1 for run in scored_runs if run["passed"])
    pass_rate = passed_count / len(scored_runs) if scored_runs else 0.0
    mean_score = sum(run["score"] for run in scored_runs) / len(scored_runs) if scored_runs else 0.0

    failures: Counter[str] = Counter()
    for run in scored_runs:
        for criterion in run["criteria"]:
            if not criterion["passed"]:
                failures[str(criterion["id"])] += 1
        for pattern in run["forbidden_hits"]:
            failures[f"forbidden:{pattern}"] += 1

    costs = [float(run["cost_usd"]) for run in scored_runs if isinstance(run.get("cost_usd"), (int, float))]
    latencies = [float(run["latency_ms"]) for run in scored_runs if isinstance(run.get("latency_ms"), (int, float))]

    trial_gate_passed = bool(scored_runs) and pass_rate >= float(spec["gate"]["min_pass_rate"])
    release_passed = overlap_passed and controls_passed and trial_gate_passed

    return {
        "framework": "Proofrail",
        "spec_id": spec["id"],
        "spec_name": spec["name"],
        "decision": "RELEASE" if release_passed else "BLOCK",
        "stages": {
            "intake_scan": {"passed": True, "errors": []},
            "overlap_scan": {"passed": overlap_passed, **overlap},
            "anchor_controls": {"passed": controls_passed, "oracle": oracle, "negative": negative},
            "trial_scoring": {
                "passed": trial_gate_passed,
                "pass_rate": round(pass_rate, 6),
                "mean_score": round(mean_score, 6),
                "passed_count": passed_count,
                "total_count": len(scored_runs),
                "runs": scored_runs,
            },
            "evidence_audit": {"failure_classes": dict(failures.most_common())},
            "spend_summary": {
                "total_cost_usd": round(sum(costs), 6),
                "average_cost_usd": round(sum(costs) / len(costs), 6) if costs else None,
                "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
            },
            "release_gate": {"passed": release_passed},
        },
    }
