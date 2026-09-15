from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import Any, Callable


SUPPORTED_EVALUATORS = {
    "contains_all", "contains_any", "regex", "max_length", "json_keys",
    "manual", "tool_called", "tool_success_rate", "trace_contains",
}

Evaluator = Callable[[dict[str, Any], dict[str, Any], str], tuple[float, str]]


def normalize_run_text(run: dict[str, Any]) -> str:
    """Flatten a provider-neutral run envelope into searchable evaluation text."""
    fragments: list[str] = []
    output = run.get("output", "")
    fragments.append(output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, sort_keys=True))
    for message in run.get("messages", []) or []:
        if isinstance(message, dict):
            content = message.get("content", "")
            fragments.append(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, sort_keys=True))
    for key in ("tool_calls", "trace", "artifacts"):
        for item in run.get(key, []) or []:
            if isinstance(item, dict):
                fragments.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
    return "\n".join(fragment for fragment in fragments if fragment)


def validate_spec(spec: dict[str, Any], custom_evaluator_names: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    for key in ("id", "name", "objective", "rubric", "controls", "gate"):
        if key not in spec:
            errors.append(f"missing required field: {key}")

    rubric = spec.get("rubric", [])
    if not isinstance(rubric, list) or not rubric:
        errors.append("rubric must be a non-empty list")
        return errors

    identifiers: list[str] = []
    weights = 0.0
    available = SUPPORTED_EVALUATORS | (custom_evaluator_names or set())
    for index, criterion in enumerate(rubric):
        prefix = f"rubric[{index}]"
        identifier = criterion.get("id")
        if not identifier:
            errors.append(f"{prefix} is missing id")
        else:
            identifiers.append(str(identifier))
        evaluator = criterion.get("evaluator")
        if evaluator not in available:
            errors.append(f"{prefix} uses unsupported evaluator: {evaluator}")
        weight = criterion.get("weight")
        if not isinstance(weight, (int, float)) or weight <= 0:
            errors.append(f"{prefix} weight must be greater than zero")
        else:
            weights += float(weight)

    if len(identifiers) != len(set(identifiers)):
        errors.append("rubric criterion ids must be unique")
    if not math.isclose(weights, 1.0, abs_tol=1e-6):
        errors.append(f"rubric weights must sum to 1.0; found {weights:.6f}")

    controls = spec.get("controls", {})
    if not isinstance(controls, dict) or "oracle" not in controls or "negative" not in controls:
        errors.append("controls must include oracle and negative outputs")
    gate = spec.get("gate", {})
    for key in ("min_score", "min_pass_rate", "max_overlap"):
        value = gate.get(key)
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            errors.append(f"gate.{key} must be between 0 and 1")
    return errors


def validate_runs(runs: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(runs, list) or not runs:
        return ["runs must be a non-empty list"]
    evidence_fields = {"output", "messages", "tool_calls", "trace", "artifacts"}
    for index, run in enumerate(runs):
        prefix = f"runs[{index}]"
        if not isinstance(run, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if not run.get("id"):
            errors.append(f"{prefix} is missing id")
        if not evidence_fields.intersection(run):
            errors.append(f"{prefix} must include at least one evidence field: {', '.join(sorted(evidence_fields))}")
        for field in ("messages", "tool_calls", "trace", "artifacts"):
            if field in run and not isinstance(run[field], list):
                errors.append(f"{prefix}.{field} must be a list")
        for field in ("latency_ms", "cost_usd"):
            if field in run and (not isinstance(run[field], (int, float)) or run[field] < 0):
                errors.append(f"{prefix}.{field} must be a non-negative number")
        for criterion, score in (run.get("review_scores") or {}).items():
            if not isinstance(score, (int, float)) or not 0 <= score <= 1:
                errors.append(f"{prefix}.review_scores.{criterion} must be between 0 and 1")
    return errors


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def cosine_similarity(left: str, right: str) -> float:
    documents = [tokenize(left), tokenize(right)]
    document_frequency: Counter[str] = Counter()
    for tokens in documents:
        document_frequency.update(set(tokens))
    vectors: list[dict[str, float]] = []
    for tokens in documents:
        counts = Counter(tokens)
        total = max(len(tokens), 1)
        vector: dict[str, float] = {}
        for term, count in counts.items():
            inverse_document_frequency = math.log((1 + len(documents)) / (1 + document_frequency[term])) + 1
            vector[term] = (count / total) * inverse_document_frequency
        vectors.append(vector)
    terms = set(vectors[0]) | set(vectors[1])
    dot = sum(vectors[0].get(term, 0) * vectors[1].get(term, 0) for term in terms)
    norms = [math.sqrt(sum(value * value for value in vector.values())) for vector in vectors]
    return dot / (norms[0] * norms[1]) if all(norms) else 0.0


def overlap_scan(spec: dict[str, Any], corpus: list[dict[str, Any]]) -> dict[str, Any]:
    source = f"{spec.get('name', '')} {spec.get('objective', '')}"
    matches = [{
        "id": item.get("id", "unknown"),
        "name": item.get("name", "Unnamed task"),
        "similarity": cosine_similarity(source, f"{item.get('name', '')} {item.get('objective', '')}"),
    } for item in corpus]
    matches.sort(key=lambda item: item["similarity"], reverse=True)
    return {"maximum": matches[0]["similarity"] if matches else 0.0, "matches": matches[:5]}


def evaluate_criterion(
    criterion: dict[str, Any], run: dict[str, Any], custom_evaluators: dict[str, Evaluator] | None = None
) -> tuple[float, str]:
    evaluator = criterion["evaluator"]
    params = criterion.get("params", {})
    output = run.get("output", "")
    normalized_text = normalize_run_text(run)
    if custom_evaluators and evaluator in custom_evaluators:
        return custom_evaluators[evaluator](criterion, run, normalized_text)
    text_output = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, sort_keys=True)
    lowered = normalized_text.lower()

    if evaluator == "contains_all":
        terms = [str(term).lower() for term in params.get("terms", [])]
        missing = [term for term in terms if term not in lowered]
        return (1.0 if not missing else 0.0, "all terms present" if not missing else f"missing: {', '.join(missing)}")
    if evaluator == "contains_any":
        terms = [str(term).lower() for term in params.get("terms", [])]
        found = [term for term in terms if term in lowered]
        return (1.0 if found else 0.0, f"matched: {', '.join(found)}" if found else "no expected term found")
    if evaluator == "regex":
        pattern = str(params.get("pattern", ""))
        matched = bool(re.search(pattern, normalized_text, re.IGNORECASE | re.MULTILINE))
        return (1.0 if matched else 0.0, "pattern matched" if matched else f"pattern not matched: {pattern}")
    if evaluator == "max_length":
        maximum = int(params.get("characters", 0))
        passed = maximum > 0 and len(text_output) <= maximum
        return (1.0 if passed else 0.0, f"{len(text_output)} of {maximum} characters")
    if evaluator == "json_keys":
        keys = [str(key) for key in params.get("keys", [])]
        try:
            value = output if isinstance(output, (dict, list)) else json.loads(str(output))
        except json.JSONDecodeError as exc:
            return 0.0, f"invalid JSON: {exc.msg}"
        missing = [key for key in keys if not isinstance(value, dict) or key not in value]
        return (1.0 if not missing else 0.0, "required keys present" if not missing else f"missing keys: {', '.join(missing)}")
    if evaluator == "manual":
        score = (run.get("review_scores") or {}).get(str(criterion["id"]))
        if not isinstance(score, (int, float)) or not 0 <= score <= 1:
            return 0.0, "missing calibrated review score"
        return float(score), "calibrated external review score"
    if evaluator == "tool_called":
        expected = [str(name) for name in params.get("names", [])]
        mode = str(params.get("mode", "all"))
        actual = [str(call.get("name")) for call in run.get("tool_calls", []) if isinstance(call, dict)]
        matched = [name for name in expected if name in actual]
        passed = bool(expected) and (len(matched) == len(expected) if mode == "all" else bool(matched))
        return (1.0 if passed else 0.0, f"called: {', '.join(actual) or 'none'}")
    if evaluator == "tool_success_rate":
        calls = [call for call in run.get("tool_calls", []) if isinstance(call, dict)]
        if not calls:
            return 0.0, "no tool calls recorded"
        successes = sum(1 for call in calls if call.get("status") == "success")
        rate = successes / len(calls)
        minimum = float(params.get("minimum", 1.0))
        return (1.0 if rate >= minimum else rate, f"{successes}/{len(calls)} successful ({rate:.3f})")
    if evaluator == "trace_contains":
        expected = [str(event) for event in params.get("events", [])]
        actual = [str(event.get("event")) for event in run.get("trace", []) if isinstance(event, dict)]
        missing = [event for event in expected if event not in actual]
        return (1.0 if not missing else 0.0, "all events present" if not missing else f"missing events: {', '.join(missing)}")
    return 0.0, "unsupported evaluator"


def score_output(
    spec: dict[str, Any], run: dict[str, Any], custom_evaluators: dict[str, Evaluator] | None = None
) -> dict[str, Any]:
    normalized_output = normalize_run_text(run)
    criterion_results = []
    weighted_score = 0.0
    for criterion in spec["rubric"]:
        raw_score, evidence = evaluate_criterion(criterion, run, custom_evaluators)
        contribution = raw_score * float(criterion["weight"])
        weighted_score += contribution
        criterion_results.append({
            "id": criterion["id"], "description": criterion.get("description", ""),
            "score": raw_score, "weight": criterion["weight"], "contribution": contribution,
            "evidence": evidence, "passed": raw_score >= float(criterion.get("pass_at", 1.0)),
        })
    forbidden_hits = [str(pattern) for pattern in spec.get("forbidden_patterns", [])
                      if re.search(str(pattern), normalized_output, re.IGNORECASE | re.MULTILINE)]
    if forbidden_hits:
        weighted_score = 0.0
    threshold = float(spec["gate"]["min_score"])
    return {
        "id": run.get("id", "unnamed-run"), "score": round(weighted_score, 6),
        "passed": weighted_score >= threshold and not forbidden_hits, "criteria": criterion_results,
        "forbidden_hits": forbidden_hits, "latency_ms": run.get("latency_ms"),
        "cost_usd": run.get("cost_usd"), "provider": run.get("provider"), "model": run.get("model"),
    }
