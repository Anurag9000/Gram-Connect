"""
generate_training_labels.py  v2
================================
50,000 samples per severity level (150,000 total).
Key improvements over v1:
  - Tri-modal domain score (0 / partial / expert)
  - Severity-specific oracle: HIGH weights avail heavily, LOW weights prox heavily
  - Domain-correlated willingness and availability
  - Realistic fresh distribution (60% no overwork, long tail)
  - Separate per-severity CSV files for per-severity weight fitting
  - 7% noise (reduced from 8% for cleaner signal)

Outputs:
  data/training_labels_high.csv    50k HIGH-severity samples
  data/training_labels_normal.csv  50k NORMAL-severity samples
  data/training_labels_low.csv     50k LOW-severity samples
  data/training_labels.csv         150k combined

Usage:
  python generate_training_labels.py
"""

import csv, math, os, random
random.seed(2024)

_HERE   = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(_HERE, "..", "data")

N_PER_SEVERITY = 50_000
SEVERITY_LEVELS = ["LOW", "NORMAL", "HIGH"]
SEVERITY_INT    = {"LOW": 0, "NORMAL": 1, "HIGH": 2}
AVAIL_MAP = {"immediately available": 1.00, "generally available": 0.70, "rarely available": 0.35}


# ── Sampling helpers ──────────────────────────────────────────────────────────

def _beta(a, b):
    return random.betavariate(a, b)

def sample_domain(severity: str) -> float:
    """Tri-modal: 25% zero, 20% partial (0.05-0.30), 55% genuine match."""
    r = random.random()
    if r < 0.25:
        return 0.0
    if r < 0.45:
        return random.uniform(0.05, 0.30)
    # Genuine match — HIGH tasks attract more specialists
    alpha = {"HIGH": 3.2, "NORMAL": 2.5, "LOW": 2.0}[severity]
    beta  = {"HIGH": 1.8, "NORMAL": 2.5, "LOW": 3.2}[severity]
    return min(1.0, _beta(alpha, beta))

def sample_will(domain: float) -> float:
    """Willingness slightly correlated with domain expertise."""
    alpha = 2.5 + domain * 2.0
    return min(1.0, _beta(alpha, 2.0))

def sample_avail(domain: float, severity: str) -> float:
    """
    HIGH emergency: more volunteers step up (more immediately available).
    Skilled volunteers have competing commitments (less immediately available).
    """
    if severity == "HIGH":
        w = [0.40, 0.45, 0.15] if domain > 0.6 else [0.45, 0.40, 0.15]
    elif severity == "NORMAL":
        w = [0.28, 0.52, 0.20] if domain > 0.6 else [0.35, 0.45, 0.20]
    else:  # LOW
        w = [0.22, 0.53, 0.25] if domain > 0.6 else [0.30, 0.48, 0.22]
    level = random.choices(list(AVAIL_MAP.keys()), weights=w)[0]
    return AVAIL_MAP[level]

def sample_prox(severity: str) -> float:
    """20% same-village (prox=1.0). Otherwise distance→exponential decay."""
    if random.random() < 0.20:
        return 1.0
    decay  = {"LOW": 25.0, "NORMAL": 40.0, "HIGH": 65.0}[severity]
    mean_d = {"LOW": 8.0,  "NORMAL": 15.0, "HIGH": 30.0}[severity]
    d = min(random.expovariate(1.0 / mean_d), 120.0)
    return math.exp(-d / decay)

def sample_fresh(prox: float, domain: float) -> float:
    """60% no overwork; local+skilled volunteers more likely to be overworked."""
    r = random.random()
    if r < 0.60:
        return 1.0
    if r < 0.80:
        ow = random.uniform(0.0, 5.0)
    elif r < 0.93:
        ow = random.uniform(5.0, 12.0) if (prox > 0.80 or domain > 0.65) else random.uniform(3.0, 8.0)
    else:
        ow = random.uniform(12.0, 20.0)
    excess = max(0.0, ow - 5.0)
    return max(0.0, 1.0 - 0.10 * excess)


# ── Oracle labeling ───────────────────────────────────────────────────────────

def oracle_label(domain, will, avail, prox, fresh, severity: str) -> int:
    """
    Severity-specific rules that directly encode the coordinator's priorities:

    HIGH  — avail is critical (need someone free NOW); domain mandatory; prox lenient.
    NORMAL — balanced: domain primary, moderate distance, moderate availability.
    LOW   — strict on prox (stay local) AND avail (routine: don't disturb busy people).
    """
    if domain < 0.01:
        return 0  # hard gate

    if severity == "HIGH":
        if domain >= 0.55 and avail >= 0.70 and will >= 0.40:              return 1
        if domain >= 0.70 and avail >= 0.35 and will >= 0.50:              return 1  # rare expert
        if domain >= 0.35 and avail >= 1.00 and will >= 0.55 and prox >= 0.20: return 1
        if domain >= 0.25 and avail >= 1.00 and will >= 0.70:              return 1  # very willing
        return 0

    if severity == "NORMAL":
        if domain >= 0.55 and will >= 0.55 and prox >= 0.40 and avail >= 0.70: return 1
        if domain >= 0.70 and will >= 0.45 and avail >= 0.70:              return 1
        if domain >= 0.40 and will >= 0.65 and prox >= 0.65 and avail >= 0.70: return 1
        if domain >= 0.45 and will >= 0.55 and prox >= 0.55 and avail >= 1.00: return 1
        return 0

    # LOW
    if domain >= 0.60 and will >= 0.60 and prox >= 0.65 and avail >= 0.70: return 1
    if domain >= 0.50 and will >= 0.70 and prox >= 0.80 and avail >= 1.00: return 1
    if domain >= 0.75 and will >= 0.55 and prox >= 0.60 and avail >= 0.70: return 1
    return 0

def add_noise(label: int, rate: float = 0.07) -> int:
    return 1 - label if random.random() < rate else label


# ── Generate + write ──────────────────────────────────────────────────────────

def generate_for_severity(severity: str, n: int) -> list:
    rows = []
    for _ in range(n):
        domain = sample_domain(severity)
        will   = sample_will(domain)
        avail  = sample_avail(domain, severity)
        prox   = sample_prox(severity)
        fresh  = sample_fresh(prox, domain)
        label  = add_noise(oracle_label(domain, will, avail, prox, fresh, severity))
        rows.append({
            "domain_score": round(domain, 4),
            "will_score":   round(will,   4),
            "avail_score":  round(avail,  4),
            "prox_score":   round(prox,   4),
            "fresh_score":  round(fresh,  4),
            "severity":     severity,
            "severity_int": SEVERITY_INT[severity],
            "label":        label,
        })
    return rows

def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"  Written {len(rows):,} rows → {os.path.relpath(path)}")

def stats(rows):
    pos = sum(r["label"] for r in rows)
    return f"{pos:,} pos ({pos/len(rows):.1%}), {len(rows)-pos:,} neg ({(len(rows)-pos)/len(rows):.1%})"

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    all_rows = []
    for sev in SEVERITY_LEVELS:
        rows = generate_for_severity(sev, N_PER_SEVERITY)
        write_csv(os.path.join(OUT_DIR, f"training_labels_{sev.lower()}.csv"), rows)
        print(f"    {sev:6s} balance: {stats(rows)}")
        all_rows.extend(rows)
    write_csv(os.path.join(OUT_DIR, "training_labels.csv"), all_rows)
    print(f"\n  Combined: {stats(all_rows)} | Total: {len(all_rows):,}")
    print("\nDone. Run: python fit_nexus_weights.py --per-severity")
