"""Blackout-Brain simulation engine.

Simulates restoring power after a disaster. Every strategy runs on the SAME
scenario (same regions, same repair durations) so the comparison is fair.
"""
from __future__ import annotations

import heapq
import random
from dataclasses import dataclass

import pandas as pd

# Simple English names for the fictional city regions.
REGION_NAMES = [
    "City Center", "North Area", "River Area", "Factory Area", "Old Town",
    "Airport", "University", "Harbor", "East Area", "West Area",
    "Hospital Area", "Green Area",
]


@dataclass
class Region:
    name: str
    load_mw: float
    hospitals: int
    repair_hours: float


@dataclass
class Scenario:
    regions: list[Region]
    crews: int
    travel_hours: float
    severity: int


def generate_scenario(n_regions: int, severity: int, crews: int,
                      travel_hours: float = 0.5, seed: int = 42) -> Scenario:
    rng = random.Random(seed)
    names = REGION_NAMES[:n_regions]
    n_affected = min(n_regions, max(3, round(n_regions * (0.4 + 0.12 * severity))))
    affected = rng.sample(names, n_affected)
    regions = []
    for name in affected:
        base = rng.uniform(2.0, 6.0)
        repair = base * (0.6 + 0.4 * severity) * rng.uniform(0.8, 1.3)
        regions.append(Region(
            name=name,
            load_mw=round(rng.uniform(15, 120), 1),
            hospitals=rng.choice([0, 0, 1, 1, 2, 3]),
            repair_hours=round(repair, 2),
        ))
    return Scenario(regions, crews, travel_hours, severity)


def critical_first(regions):
    return sorted(regions, key=lambda r: (-r.hospitals, r.repair_hours))


def largest_load_first(regions):
    return sorted(regions, key=lambda r: -r.load_mw)


def shortest_repair_first(regions):
    return sorted(regions, key=lambda r: r.repair_hours)


STRATEGIES = {
    "Critical-First": critical_first,
    "Largest-Load-First": largest_load_first,
    "Shortest-Repair-First": shortest_repair_first,
}


def run_strategy(scenario: Scenario, strategy_name: str):
    order = STRATEGIES[strategy_name](scenario.regions)
    crews = [(0.0, c + 1) for c in range(scenario.crews)]
    heapq.heapify(crews)
    rows, events = [], []
    for r in order:
        free_at, crew_id = heapq.heappop(crews)
        start = free_at
        done = start + scenario.travel_hours + r.repair_hours
        heapq.heappush(crews, (done, crew_id))
        rows.append({
            "Region": r.name, "Crew": crew_id, "Load (MW)": r.load_mw,
            "Hospitals": r.hospitals, "Dispatch (h)": round(start, 2),
            "Restored at (h)": round(done, 2),
            "Unserved Energy (MWh)": round(r.load_mw * done, 1),
        })
        events.append((start, "DISPATCH", r.name, crew_id,
                       f"Crew {crew_id} leaves for {r.name} (travel {scenario.travel_hours}h)"))
        events.append((done, "RESTORED", r.name, crew_id,
                       f"{r.name} back online after {r.repair_hours}h repair"))
    details = pd.DataFrame(rows)
    log = pd.DataFrame(sorted(events), columns=["Time (h)", "Event", "Region", "Crew", "Description"])
    log["Time (h)"] = log["Time (h)"].round(2)

    hosp_total = details["Hospitals"].sum()
    hosp_avg = (
        (details["Hospitals"] * details["Restored at (h)"]).sum() / hosp_total
        if hosp_total else 0.0
    )
    summary = {
        "Strategy": strategy_name,
        "Avg Restoration Time (h)": round(details["Restored at (h)"].mean(), 2),
        "Total Restoration Time (h)": round(details["Restored at (h)"].max(), 2),
        "Critical Facilities Avg Restore (h)": round(hosp_avg, 2),
        "Unserved Energy (MWh)": round(details["Unserved Energy (MWh)"].sum(), 1),
    }
    return summary, details, log


def compare_all(scenario: Scenario):
    results = {n: run_strategy(scenario, n) for n in STRATEGIES}
    table = pd.DataFrame([results[n][0] for n in STRATEGIES])
    return table, results
