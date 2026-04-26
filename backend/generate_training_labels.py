"""
generate_training_labels.py
============================
Generates high-fidelity synthetic training data for calibrating the Forge
engine's 5 exponent weights [w_domain, w_will, w_avail, w_prox, w_fresh].

The oracle encodes concrete coordinator domain knowledge as labeling rules:
  - Domain expertise is the primary gate (necessary but not sufficient)
  - Severity modifies tolerances: HIGH = more lenient on distance/availability
  - Willingness and proximity are secondary requirements
  - Availability and freshness are soft constraints that soften scores

Joint-distribution correlations encoded:
  - Skilled volunteers (high domain) tend to be less immediately available
  - Local volunteers (high prox) get assigned more, so slightly more overworked
  - HIGH-severity tasks reach more distant volunteers
  - HIGH-severity tasks attract more specialists (shifted domain distribution)

Outputs:
  data/training_labels.csv       -- 25,000 individual volunteer-task pairs
  data/team_training_labels.csv  -- 5,000 team-level assignment labels

Usage:
  python generate_training_labels.py
"""

import csv
import math
import os
import random

random.seed(42)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(_HERE, "..", "data")
PAIRS_OUT = os.path.join(OUT_DIR, "training_labels.csv")
TEAMS_OUT = os.path.join(OUT_DIR, "team_training_labels.csv")

N_PAIRS = 25_000
N_TEAMS = 5_000

SEVERITY_LEVELS  = ["LOW", "NORMAL", "HIGH"]
SEVERITY_WEIGHTS = [0.25,  0.50,    0.25]

AVAIL_LEVELS = {
    "immediately available": 1.00,
    "generally available":   0.70,
    "rarely available":      0.35,
}


# ---------------------------------------------------------------------------
# Sampling helpers
# ---------------------------------------------------------------------------

def _beta(a: float, b: float) -> float:
    return random.betavariate(a, b)


def sample_domain(severity: str) -> float:
    """
    Domain score distribution:
      25% of pairs have zero domain (completely wrong skill set for the task).
      For the rest:
        HIGH-severity tasks attract more specialists -> shift toward higher domain.
        NORMAL/LOW: Beta(2,4), skewed toward lower values (partial matches common).
    """
    if random.random() < 0.25:
        return 0.0
    if severity == "HIGH":
        # More likely to match a specialist; Beta(2.5, 2.5) is near-symmetric
        return min(1.0, _beta(2.5, 2.5))
    if severity == "NORMAL":
        return min(1.0, _beta(2.0, 4.0))
    # LOW: routine tasks get less-specialist volunteers
    return min(1.0, _beta(1.5, 4.5))


def sample_will() -> float:
    """
    Willingness. Most volunteers have moderate-to-good motivation.
    Beta(3, 2) is slightly right-skewed (mean ~0.6).
    """
    return _beta(3.0, 2.0)


def sample_avail(domain: float) -> float:
    """
    Categorical availability, mapped to float.
    Skilled volunteers have more competing commitments, so less likely to be
    'immediately available'.
    """
    if domain > 0.6:
        weights = [0.25, 0.60, 0.15]   # skilled: less immediately available
    elif domain > 0.3:
        weights = [0.35, 0.50, 0.15]
    else:
        weights = [0.45, 0.40, 0.15]   # less skilled: more often free
    level = random.choices(list(AVAIL_LEVELS), weights=weights)[0]
    return AVAIL_LEVELS[level]


def sample_prox(severity: str) -> float:
    """
    Proximity factor, derived by sampling a realistic distance then applying
    the same exponential decay used by the Forge engine.
    HIGH-severity tasks: wider geographic reach, λ=65km.
    NORMAL: λ=40km.
    LOW: λ=25km (coordinator prefers local volunteers).
    """
    decay = {"LOW": 25.0, "NORMAL": 40.0, "HIGH": 65.0}[severity]
    # Mean distances: LOW ~8km, NORMAL ~15km, HIGH ~28km
    mean_d = {"LOW": 8.0, "NORMAL": 15.0, "HIGH": 28.0}[severity]
    d = min(random.expovariate(1.0 / mean_d), 120.0)
    return math.exp(-d / decay)


def sample_fresh(prox: float) -> float:
    """
    Fresh score (workload / anti-burnout factor).
    Local volunteers (high prox) get assigned more often and are slightly more
    likely to be near or over the weekly quota.
    """
    if prox > 0.85:
        # Local volunteer: mean overwork_hours = 3 (often busy)
        ow = max(0.0, random.gauss(3.0, 3.5))
    elif prox > 0.5:
        ow = max(0.0, random.gauss(1.5, 2.5))
    else:
        # Distant volunteer: rarely assigned, usually fresh
        ow = max(0.0, random.gauss(0.5, 1.5))

    weekly_quota   = 5.0
    overwork_rate  = 0.10
    excess = max(0.0, ow - weekly_quota)
    return max(0.0, 1.0 - overwork_rate * excess)


# ---------------------------------------------------------------------------
# Oracle labeling (encodes coordinator domain knowledge)
# ---------------------------------------------------------------------------

def oracle_label(
    domain: float,
    will:   float,
    avail:  float,
    prox:   float,
    fresh:  float,
    severity: str,
) -> int:
    """
    Deterministic labeling rules based on coordinator domain knowledge.

    Core philosophy:
      - Domain expertise is a gate: zero domain is always rejected.
      - Severity shifts tolerances:
          HIGH   -> distance/availability constraints relaxed (emergency)
          LOW    -> stricter on proximity, availability, willingness
          NORMAL -> balanced
      - Freshness (workload) is never alone sufficient to reject a strong expert.
      - A single highly-skilled local expert beats a large group of tangentially
        relevant volunteers.
    """
    # Hard gate: no relevant skills at all
    if domain < 0.01:
        return 0

    if severity == "HIGH":
        # Emergency: domain + willingness are critical.
        # Distance and availability are more forgivable.
        if domain < 0.15:
            return 0
        if domain >= 0.55 and will >= 0.40:
            return 1
        if domain >= 0.35 and will >= 0.55 and prox >= 0.25:
            return 1
        if domain >= 0.20 and will >= 0.70 and avail >= 0.70 and prox >= 0.15:
            return 1
        # Highly skilled even if far or low willingness -- field experts worth deploying
        if domain >= 0.75:
            return 1
        return 0

    elif severity == "NORMAL":
        if domain < 0.25:
            return 0
        if domain >= 0.60 and will >= 0.50 and prox >= 0.35:
            return 1
        if domain >= 0.45 and will >= 0.60 and prox >= 0.50 and avail >= 0.70:
            return 1
        # Very high skill: forgive low prox or moderate will
        if domain >= 0.75 and will >= 0.40:
            return 1
        # Good local volunteer with decent skills
        if domain >= 0.35 and will >= 0.65 and prox >= 0.75 and avail >= 0.70:
            return 1
        return 0

    else:  # LOW severity -- routine task, coordinator can afford to be strict
        if domain < 0.35:
            return 0
        if domain >= 0.65 and will >= 0.60 and prox >= 0.60 and avail >= 0.70:
            return 1
        if domain >= 0.55 and will >= 0.75 and prox >= 0.75 and avail >= 1.0:
            return 1
        # Very high skill in low-severity task: still require good proximity
        if domain >= 0.80 and will >= 0.55 and prox >= 0.50:
            return 1
        return 0


def add_noise(label: int, rate: float = 0.08) -> int:
    """
    Flip label with probability `rate` to model coordinator inconsistency.
    Real coordinators occasionally make suboptimal or inconsistent calls.
    """
    return 1 - label if random.random() < rate else label


# ---------------------------------------------------------------------------
# Generate individual volunteer-task pairs
# ---------------------------------------------------------------------------

def generate_pairs(n: int) -> list:
    rows = []
    for _ in range(n):
        severity = random.choices(SEVERITY_LEVELS, weights=SEVERITY_WEIGHTS)[0]
        domain   = sample_domain(severity)
        will     = sample_will()
        avail    = sample_avail(domain)
        prox     = sample_prox(severity)
        fresh    = sample_fresh(prox)

        label = oracle_label(domain, will, avail, prox, fresh, severity)
        label = add_noise(label)

        rows.append({
            "domain_score": round(domain, 4),
            "will_score":   round(will,   4),
            "avail_score":  round(avail,  4),
            "prox_score":   round(prox,   4),
            "fresh_score":  round(fresh,  4),
            "severity":     severity,
            "severity_int": {"LOW": 0, "NORMAL": 1, "HIGH": 2}[severity],
            "label":        label,
        })
    return rows


# ---------------------------------------------------------------------------
# Generate team-level labels
# ---------------------------------------------------------------------------

def _generate_one_team(severity: str) -> dict:
    team_size = random.choices([2, 3, 4, 5], weights=[0.25, 0.40, 0.25, 0.10])[0]
    members = []
    for _ in range(team_size):
        d = sample_domain(severity)
        w = sample_will()
        a = sample_avail(d)
        p = sample_prox(severity)
        f = sample_fresh(p)
        members.append({"domain": d, "will": w, "avail": a, "prox": p, "fresh": f})

    avg_domain  = sum(m["domain"] for m in members) / team_size
    avg_will    = sum(m["will"]   for m in members) / team_size
    avg_prox    = sum(m["prox"]   for m in members) / team_size
    min_domain  = min(m["domain"] for m in members)
    # Coverage = fraction of members who actually contribute a relevant skill
    coverage    = sum(1 for m in members if m["domain"] > 0.01) / team_size

    # Team oracle: the team's collective capability matters
    if min_domain == 0.0 and avg_domain < 0.20:
        # More than half have zero relevance -- poor team
        label = 0
    elif avg_domain >= 0.50 and avg_will >= 0.50 and coverage >= 0.60:
        label = 1
    elif avg_domain >= 0.40 and avg_will >= 0.60 and avg_prox >= 0.45 and coverage >= 0.55:
        label = 1
    elif avg_domain >= 0.65 and coverage >= 0.65:
        label = 1
    elif avg_domain < 0.25:
        label = 0
    else:
        label = 0

    label = add_noise(label, rate=0.07)

    return {
        "team_size":   team_size,
        "avg_domain":  round(avg_domain, 4),
        "avg_will":    round(avg_will,   4),
        "avg_prox":    round(avg_prox,   4),
        "min_domain":  round(min_domain, 4),
        "coverage":    round(coverage,   4),
        "severity":    severity,
        "severity_int": {"LOW": 0, "NORMAL": 1, "HIGH": 2}[severity],
        "label":       label,
    }


def generate_teams(n: int) -> list:
    rows = []
    for _ in range(n):
        severity = random.choices(SEVERITY_LEVELS, weights=SEVERITY_WEIGHTS)[0]
        rows.append(_generate_one_team(severity))
    return rows


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def write_csv(path: str, rows: list) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Written {len(rows):,} rows -> {os.path.relpath(path)}")


def _class_stats(rows: list) -> str:
    pos = sum(r["label"] for r in rows)
    n   = len(rows)
    return f"{pos:,} positive ({pos/n:.1%}), {n-pos:,} negative ({(n-pos)/n:.1%})"


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Generating individual volunteer-task pair labels ...")
    pairs = generate_pairs(N_PAIRS)
    write_csv(PAIRS_OUT, pairs)
    print(f"  Class balance: {_class_stats(pairs)}")

    # Severity breakdown
    for sev in SEVERITY_LEVELS:
        sub = [r for r in pairs if r["severity"] == sev]
        print(f"    {sev:6s}: {_class_stats(sub)}")

    print()
    print("Generating team-level assignment labels ...")
    teams = generate_teams(N_TEAMS)
    write_csv(TEAMS_OUT, teams)
    print(f"  Class balance: {_class_stats(teams)}")
    print()
    print("Done. Run fit_forge_weights.py to learn optimal exponent weights.")
