from __future__ import annotations

import json
import re
from typing import Any

from .checks import Evaluator, SUPPORTED_EVALUATORS, overlap_scan, score_output


SURFACE_NAMES = (
    "specification_identity",
    "objective_definition",
    "risk_classification",
    "traceability",
    "rubric_presence",
    "criterion_identity",
    "criterion_descriptions",
    "weight_integrity",
    "evaluator_support",
    "evaluator_parameters",
    "gate_thresholds",
    "oracle_control",
    "negative_control",
    "control_discrimination",
    "trial_coverage",
    "trial_integrity",
    "evidence_coverage",
    "protected_evidence",
    "process_isolation",
    "corpus_integrity",
    "corpus_novelty",
)


def _surface(name: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "evidence": evidence}


def _control_run(identifier: str, value: Any, review_scores: dict[str, float]) -> dict[str, Any]:
    envelope_fields = {"output", "messages", "tool_calls", "trace", "artifacts"}
    run = dict(value) if isinstance(value, dict) and envelope_fields.intersection(value) else {"output": value}
    run.update({"id": identifier, "review_scores": review_scores})
    return run


def _parameters_valid(criterion: dict[str, Any]) -> bool:
    evaluator = criterion.get("evaluator")
    params = criterion.get("params", {})
    if not isinstance(params, dict):
        return False
    if evaluator in {"contains_all", "contains_any"}:
        return bool(params.get("terms"))
    if evaluator == "regex":
        try:
            re.compile(str(params.get("pattern", "")))
            return bool(params.get("pattern"))
        except re.error:
            return False
    if evaluator == "max_length":
        return isinstance(params.get("characters"), int) and params["characters"] > 0
    if evaluator == "json_keys":
        return bool(params.get("keys"))
    if evaluator == "tool_called":
        return bool(params.get("names")) and params.get("mode", "all") in {"all", "any"}
    if evaluator == "tool_success_rate":
        return isinstance(params.get("minimum", 1.0), (int, float)) and 0 <= params.get("minimum", 1.0) <= 1
    if evaluator == "trace_contains":
        return bool(params.get("events"))
    return evaluator == "manual" or evaluator not in SUPPORTED_EVALUATORS


def run_preflight(
    spec: dict[str, Any],
    runs: list[dict[str, Any]],
    corpus: list[dict[str, Any]],
    custom_evaluators: dict[str, Evaluator] | None = None,
) -> dict[str, Any]:
    rubric = spec.get("rubric", []) if isinstance(spec.get("rubric", []), list) else []
    controls = spec.get("controls", {}) if isinstance(spec.get("controls", {}), dict) else {}
    gate = spec.get("gate", {}) if isinstance(spec.get("gate", {}), dict) else {}
    metadata = spec.get("metadata", {}) if isinstance(spec.get("metadata", {}), dict) else {}
    available_evaluators = SUPPORTED_EVALUATORS | set((custom_evaluators or {}).keys())
    surfaces: list[dict[str, Any]] = []

    identity_ok = all(isinstance(spec.get(key), str) and spec[key].strip() for key in ("id", "name", "version"))
    surfaces.append(_surface("specification_identity", identity_ok, "id, name, and version are required"))
    objective_ok = isinstance(spec.get("objective"), str) and len(spec["objective"].strip()) >= 20
    surfaces.append(_surface("objective_definition", objective_ok, "objective must contain at least 20 characters"))
    risk_ok = spec.get("risk_level") in {"low", "medium", "high", "critical"}
    surfaces.append(_surface("risk_classification", risk_ok, f"risk_level={spec.get('risk_level')}"))
    traceability_ok = all(isinstance(metadata.get(key), str) and metadata[key].strip() for key in ("owner", "source"))
    surfaces.append(_surface("traceability", traceability_ok, "metadata.owner and metadata.source are required"))

    surfaces.append(_surface("rubric_presence", bool(rubric), f"criteria={len(rubric)}"))
    criterion_ids = [criterion.get("id") for criterion in rubric if isinstance(criterion, dict)]
    criterion_identity_ok = len(criterion_ids) == len(rubric) and all(criterion_ids) and len(criterion_ids) == len(set(criterion_ids))
    surfaces.append(_surface("criterion_identity", criterion_identity_ok, "criterion ids must be present and unique"))
    descriptions_ok = bool(rubric) and all(isinstance(c.get("description"), str) and c["description"].strip() for c in rubric)
    surfaces.append(_surface("criterion_descriptions", descriptions_ok, "every criterion requires a description"))
    weights = [c.get("weight") for c in rubric]
    weights_ok = bool(weights) and all(isinstance(weight, (int, float)) and weight > 0 for weight in weights) and abs(sum(weights) - 1.0) <= 1e-6
    surfaces.append(_surface("weight_integrity", weights_ok, f"weight_total={sum(w for w in weights if isinstance(w, (int, float))):.6f}"))
    evaluator_support_ok = bool(rubric) and all(c.get("evaluator") in available_evaluators for c in rubric)
    surfaces.append(_surface("evaluator_support", evaluator_support_ok, f"available={len(available_evaluators)} evaluators"))
    evaluator_parameters_ok = bool(rubric) and all(_parameters_valid(c) for c in rubric)
    surfaces.append(_surface("evaluator_parameters", evaluator_parameters_ok, "built-in evaluator parameters must be valid"))

    threshold_values_ok = all(isinstance(gate.get(key), (int, float)) and 0 <= gate[key] <= 1 for key in ("min_score", "min_pass_rate", "max_overlap"))
    min_trials_ok = isinstance(gate.get("min_trials"), int) and gate["min_trials"] >= 1
    surfaces.append(_surface("gate_thresholds", threshold_values_ok and min_trials_ok, f"min_trials={gate.get('min_trials')}"))

    oracle_present = "oracle" in controls
    negative_present = "negative" in controls
    surfaces.append(_surface("oracle_control", oracle_present, "known-good control is required"))
    surfaces.append(_surface("negative_control", negative_present, "NO OP negative control is required"))
    discrimination_ok = False
    discrimination_evidence = "controls could not be scored"
    if oracle_present and negative_present and rubric and threshold_values_ok:
        oracle = score_output(spec, _control_run("oracle", controls["oracle"], controls.get("oracle_review_scores", {})), custom_evaluators)
        negative = score_output(spec, _control_run("negative", controls["negative"], controls.get("negative_review_scores", {})), custom_evaluators)
        discrimination_ok = oracle["passed"] and not negative["passed"]
        discrimination_evidence = f"oracle={oracle['score']:.3f}; no_op={negative['score']:.3f}"
    surfaces.append(_surface("control_discrimination", discrimination_ok, discrimination_evidence))

    min_trials = gate.get("min_trials", 1) if isinstance(gate.get("min_trials", 1), int) else 1
    surfaces.append(_surface("trial_coverage", isinstance(runs, list) and len(runs) >= min_trials, f"runs={len(runs) if isinstance(runs, list) else 0}; required={min_trials}"))
    run_ids = [run.get("id") for run in runs if isinstance(run, dict)] if isinstance(runs, list) else []
    telemetry_ok = all(
        (field not in run or isinstance(run[field], (int, float)) and run[field] >= 0)
        for run in runs if isinstance(run, dict) for field in ("latency_ms", "cost_usd")
    )
    run_integrity_ok = len(run_ids) == len(runs) and all(run_ids) and len(run_ids) == len(set(run_ids)) and telemetry_ok
    surfaces.append(_surface("trial_integrity", run_integrity_ok, "run ids must be unique and telemetry non-negative"))
    evidence_fields = {"output", "messages", "tool_calls", "trace", "artifacts"}
    evidence_ok = bool(runs) and all(isinstance(run, dict) and bool(evidence_fields.intersection(run)) for run in runs)
    surfaces.append(_surface("evidence_coverage", evidence_ok, "every run requires output, messages, tool calls, trace, or artifacts"))

    evidence_policy = spec.get("evidence_policy", {}) if isinstance(spec.get("evidence_policy", {}), dict) else {}
    protected_ok = evidence_policy.get("classification") in {"synthetic", "public", "internal", "confidential"} and evidence_policy.get("secrets_scanned") is True
    surfaces.append(_surface("protected_evidence", protected_ok, f"classification={evidence_policy.get('classification')}; secrets_scanned={evidence_policy.get('secrets_scanned')}"))
    execution = spec.get("execution", {}) if isinstance(spec.get("execution", {}), dict) else {}
    isolation_ok = execution.get("isolated") is True
    surfaces.append(_surface("process_isolation", isolation_ok, f"isolated={execution.get('isolated')}"))

    corpus_ids = [item.get("id") for item in corpus if isinstance(item, dict)] if isinstance(corpus, list) else []
    corpus_fields_ok = bool(corpus) and all(
        isinstance(item, dict) and all(isinstance(item.get(key), str) and item[key].strip() for key in ("id", "name", "objective", "failure_class"))
        for item in corpus
    )
    corpus_integrity_ok = corpus_fields_ok and len(corpus_ids) == len(set(corpus_ids))
    surfaces.append(_surface("corpus_integrity", corpus_integrity_ok, f"corpus_records={len(corpus) if isinstance(corpus, list) else 0}"))
    overlap = overlap_scan(spec, corpus if isinstance(corpus, list) else [])
    novelty_ok = threshold_values_ok and overlap["maximum"] <= gate["max_overlap"]
    surfaces.append(_surface("corpus_novelty", novelty_ok, f"maximum_similarity={overlap['maximum']:.3f}; limit={gate.get('max_overlap')}"))

    assert len(surfaces) == 21
    passed_count = sum(1 for surface in surfaces if surface["passed"])
    return {
        "framework": "Proofrail",
        "spec_id": spec.get("id", "unknown"),
        "decision": "PASS" if passed_count == len(surfaces) else "BLOCK",
        "passed_count": passed_count,
        "total_count": len(surfaces),
        "surfaces": surfaces,
    }


def markdown_preflight(result: dict[str, Any]) -> str:
    lines = [
        "# Proofrail Preflight Review", "",
        f"**Specification:** {result['spec_id']}",
        f"**Decision:** {result['decision']}",
        f"**Coverage:** {result['passed_count']}/{result['total_count']} validation surfaces passed", "",
        "| Validation surface | Result | Evidence |", "|---|---:|---|",
    ]
    for surface in result["surfaces"]:
        lines.append(f"| {surface['name']} | {'PASS' if surface['passed'] else 'FAIL'} | {surface['evidence']} |")
    return "\n".join(lines) + "\n"
