"""Hybrid AI engine for Blackout-Brain.

Educational prototype:
1) Random Forest learns which baseline strategy has the lowest weighted score
   across synthetic training scenarios.
2) A local-search optimizer searches for a better region order for the current
   scenario using the same repair scheduling simulator.
"""
from __future__ import annotations

import random
from itertools import combinations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from simulation import (
    Scenario, Region, STRATEGIES, run_strategy, generate_scenario
)

STRATEGY_NAMES = list(STRATEGIES.keys())


def _score(summary: dict) -> float:
    """Lower is better. All terms are normalized to make them comparable."""
    # A simple, explicit educational objective: balance energy not served,
    # total restoration duration, and critical-facility restoration time.
    energy = float(summary["Unserved Energy (MWh)"])
    total = float(summary["Total Restoration Time (h)"])
    critical = float(summary["Critical Facilities Avg Restore (h)"])
    # Scaling constants keep terms on similar numeric ranges for this toy model.
    return 0.50 * (energy / 1000.0) + 0.30 * (total / 20.0) + 0.20 * (critical / 20.0)


def _features(scenario: Scenario) -> list[float]:
    regions = scenario.regions
    n = max(len(regions), 1)
    hospitals = sum(r.hospitals for r in regions)
    return [
        float(scenario.severity),
        float(len(regions)),
        float(scenario.crews),
        float(scenario.travel_hours),
        sum(r.load_mw for r in regions) / n,
        max((r.load_mw for r in regions), default=0.0),
        sum(r.repair_hours for r in regions) / n,
        max((r.repair_hours for r in regions), default=0.0),
        float(hospitals),
        float(sum(1 for r in regions if r.hospitals > 0)),
    ]


def _make_training_set(n_samples: int = 180, seed: int = 2026):
    rng = random.Random(seed)
    X, y = [], []
    for i in range(n_samples):
        n_regions = rng.randint(4, 12)
        severity = rng.randint(1, 5)
        crews = rng.randint(1, min(6, n_regions))
        travel = rng.choice([0.0, 0.25, 0.5, 0.75, 1.0, 1.5])
        scenario = generate_scenario(
            n_regions=n_regions,
            severity=severity,
            crews=crews,
            travel_hours=travel,
            seed=rng.randint(0, 1_000_000),
        )
        summaries = []
        for name in STRATEGY_NAMES:
            summary, _, _ = run_strategy(scenario, name)
            summaries.append((_score(summary), name))
        best_name = min(summaries, key=lambda item: item[0])[1]
        X.append(_features(scenario))
        y.append(best_name)
    return X, y


def train_recommender(n_samples: int = 180, seed: int = 2026):
    """Train a Random Forest on reproducible synthetic scenarios."""
    X, y = _make_training_set(n_samples=n_samples, seed=seed)
    model = RandomForestClassifier(
        n_estimators=100, max_depth=8, random_state=seed, class_weight="balanced"
    )
    model.fit(X, y)
    return model


def recommend_strategy(scenario: Scenario, model=None):
    """Return model recommendation, confidence, and explicit objective score."""
    if model is None:
        model = train_recommender()
    features = [_features(scenario)]
    prediction = model.predict(features)[0]
    probabilities = model.predict_proba(features)[0]
    confidence = float(max(probabilities))
    # Explain the target by showing the measured baseline scores too.
    baseline_scores = {}
    for name in STRATEGY_NAMES:
        summary, _, _ = run_strategy(scenario, name)
        baseline_scores[name] = round(_score(summary), 4)
    return {
        "strategy": str(prediction),
        "confidence": confidence,
        "scores": baseline_scores,
        "model": model,
    }


def _evaluate_order(scenario: Scenario, order: list[Region]):
    """Simulate a custom ordering and return score + task detail rows."""
    import heapq

    crews = [(0.0, c + 1) for c in range(scenario.crews)]
    heapq.heapify(crews)
    rows = []
    for region in order:
        free_at, crew_id = heapq.heappop(crews)
        start = free_at
        done = start + scenario.travel_hours + region.repair_hours
        heapq.heappush(crews, (done, crew_id))
        rows.append({
            "Region": region.name,
            "Crew": crew_id,
            "Load (MW)": region.load_mw,
            "Hospitals": region.hospitals,
            "Dispatch (h)": round(start, 2),
            "Restored at (h)": round(done, 2),
            "Unserved Energy (MWh)": round(region.load_mw * done, 1),
        })
    details = pd.DataFrame(rows)
    hosp_total = details["Hospitals"].sum()
    critical = (
        (details["Hospitals"] * details["Restored at (h)"]).sum() / hosp_total
        if hosp_total else 0.0
    )
    summary = {
        "Unserved Energy (MWh)": float(details["Unserved Energy (MWh)"].sum()),
        "Total Restoration Time (h)": float(details["Restored at (h)"].max()),
        "Critical Facilities Avg Restore (h)": float(critical),
    }
    return _score(summary), details


def optimize_schedule(scenario: Scenario, initial_strategy: str, iterations: int = 250, seed: int = 7):
    """Improve the predicted strategy's ordering with randomized swap local search."""
    rng = random.Random(seed)
    initial_order = STRATEGIES[initial_strategy](scenario.regions)
    best_order = list(initial_order)
    best_score, best_details = _evaluate_order(scenario, best_order)
    current_order = list(best_order)
    current_score = best_score

    if len(current_order) >= 2:
        for _ in range(iterations):
            candidate = list(current_order)
            i, j = rng.sample(range(len(candidate)), 2)
            candidate[i], candidate[j] = candidate[j], candidate[i]
            candidate_score, candidate_details = _evaluate_order(scenario, candidate)
            # Greedy local search; accept only improvements.
            if candidate_score < current_score:
                current_order, current_score = candidate, candidate_score
            if candidate_score < best_score:
                best_order, best_score, best_details = candidate, candidate_score, candidate_details

    baseline_summary, _, _ = run_strategy(scenario, initial_strategy)
    baseline_score = _score(baseline_summary)
    return {
        "initial_strategy": initial_strategy,
        "initial_score": round(baseline_score, 4),
        "optimized_score": round(best_score, 4),
        "improvement_percent": round(
            max(0.0, (baseline_score - best_score) / baseline_score * 100.0)
            if baseline_score > 0 else 0.0, 2
        ),
        "details": best_details.sort_values("Restored at (h)").reset_index(drop=True),
        "order": [r.name for r in best_order],
    }
