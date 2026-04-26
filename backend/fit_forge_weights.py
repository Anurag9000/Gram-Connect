"""
fit_forge_weights.py  v2
========================
Fits per-severity exponent weights from labeled training data.

The multiplicative formula in log-space:
  log(SCORE) = w_d*log(domain) + w_w*log(will) + w_a*log(avail)
             + w_p*log(prox) + w_f*log(fresh)

This is logistic regression on log-transformed features.
Coefficients ARE the exponents — no approximation.

With --per-severity, fits one model per severity level so that
HIGH/NORMAL/LOW each get their own weight vector, which is the correct
thing to do since avail matters far more for HIGH emergencies than LOW
routine tasks.

Usage:
  python fit_forge_weights.py                 # combined model
  python fit_forge_weights.py --per-severity  # 3 separate models (recommended)
"""

import argparse, csv, json, math, os, sys

_HERE        = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(_HERE, "..", "data")
FACTORS      = ["domain", "will", "avail", "prox", "fresh"]
COLS         = ["domain_score", "will_score", "avail_score", "prox_score", "fresh_score"]
CURRENT_W    = {2: {"domain":1.20,"will":0.70,"avail":1.50,"prox":0.40,"fresh":0.15},
                1: {"domain":1.02,"will":0.66,"avail":0.50,"prox":0.60,"fresh":0.15},
                0: {"domain":1.00,"will":0.50,"avail":1.00,"prox":1.20,"fresh":0.15}}
SEV_LABEL    = {0:"LOW", 1:"NORMAL", 2:"HIGH"}
EPS          = 1e-6


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_Xy(rows, domain_min=0.15, domain_max=0.90):
    """
    Log-transform features for logistic regression.
    Filter to the 'competitive zone' (domain_min < domain < domain_max):
      - domain < 0.15: nearly always rejected regardless of other factors → no signal
      - domain > 0.90: nearly always accepted regardless of other factors → no signal
    Only the middle range exposes whether avail/prox/will tip the decision.
    """
    X, y, skipped = [], [], 0
    for r in rows:
        d = float(r["domain_score"])
        if d < EPS or d < domain_min or d > domain_max:
            skipped += 1
            continue
        X.append([math.log(max(float(r[c]), EPS)) for c in COLS])
        y.append(int(r["label"]))
    return X, y, skipped


def fit_one(X, y, label="model"):
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_score, StratifiedKFold
    except ImportError:
        print("ERROR: run  pip install scikit-learn numpy"); sys.exit(1)

    Xa, ya = np.array(X), np.array(y)
    pos = ya.sum()
    print(f"    Samples: {len(Xa):,}  |  pos {pos:,} ({pos/len(ya):.1%})  neg {len(ya)-pos:,}")

    # fit_intercept=True:  log(1.0)=0 means the intercept absorbs baseline rate.
    #   Without it every "best-possible" input maps to P=0.5, biasing all weights down.
    # C=100: nearly unregularised so secondary features (avail, prox) can emerge.
    clf = LogisticRegression(fit_intercept=True, C=100, max_iter=5000,
                             solver="lbfgs", class_weight="balanced", random_state=42)
    clf.fit(Xa, ya)

    cv  = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    roc = cross_val_score(clf, Xa, ya, cv=cv, scoring="roc_auc")
    acc = cross_val_score(clf, Xa, ya, cv=cv, scoring="accuracy")
    print(f"    ROC-AUC : {roc.mean():.4f} ± {roc.std():.4f}")
    print(f"    Accuracy: {acc.mean():.4f} ± {acc.std():.4f}")
    print(f"    Raw coefficients: {dict(zip(FACTORS, [round(c,4) for c in clf.coef_[0]]))}")

    # Clamp to minimum 0.05 (near-zero is valid; negative would be a direction inversion)
    weights = {name: max(0.05, round(float(c), 4))
               for name, c in zip(FACTORS, clf.coef_[0])}
    return weights, {"roc_auc": round(float(roc.mean()), 4),
                     "accuracy": round(float(acc.mean()), 4),
                     "n": len(Xa)}


def print_comparison(sev_int, fitted):
    current = CURRENT_W[sev_int]
    sev     = SEV_LABEL[sev_int]
    print(f"\n  {'Factor':<10} {'Fitted':>10} {'Current':>10} {'Δ':>10}")
    print(f"  {'-'*42}")
    for f in FACTORS:
        d    = fitted[f] - current[f]
        flag = "  ← changed" if abs(d) > 0.15 else ""
        print(f"  {f:<10} {fitted[f]:>10.4f} {current[f]:>10.2f} {d:>+10.4f}{flag}")


def run_per_severity(out_path):
    result = {}
    for sev_int, sev in SEV_LABEL.items():
        path = os.path.join(DATA_DIR, f"training_labels_{sev.lower()}.csv")
        if not os.path.exists(path):
            print(f"  Missing {path} — run generate_training_labels.py first"); sys.exit(1)

        rows = read_csv(path)
        print(f"\n── {sev} severity ({len(rows):,} rows) ──────────────────────────────")
        X, y, skipped = build_Xy(rows)
        print(f"    Excluded {skipped:,} zero-domain rows")
        weights, meta = fit_one(X, y, sev)
        print_comparison(sev_int, weights)
        result[sev_int] = {"weights": weights, "meta": meta}

    # Build the paste-ready SEVERITY_FACTOR_WEIGHTS dict
    print("\n\n" + "="*60)
    print("SEVERITY_FACTOR_WEIGHTS to paste into forge.py:")
    print("="*60)
    print("SEVERITY_FACTOR_WEIGHTS: dict = {")
    for sev_int, sev in SEV_LABEL.items():
        w = result[sev_int]["weights"]
        roc = result[sev_int]["meta"]["roc_auc"]
        print(f"    {sev_int}: {{  # {sev}  ROC-AUC={roc}")
        for f in FACTORS:
            print(f"        \"{f}\": {w[f]},")
        print("    },")
    print("}")

    with open(out_path, "w") as f:
        # convert int keys to str for JSON
        json.dump({str(k): v for k, v in result.items()}, f, indent=2)
    print(f"\nSaved → {os.path.relpath(out_path)}")
    return result


def run_combined(out_path):
    path = os.path.join(DATA_DIR, "training_labels.csv")
    if not os.path.exists(path):
        print(f"Missing {path}"); sys.exit(1)
    rows = read_csv(path)
    print(f"\n── Combined ({len(rows):,} rows) ────────────────────────────────────")
    X, y, skipped = build_Xy(rows)
    print(f"  Excluded {skipped:,} zero-domain rows")
    weights, meta = fit_one(X, y)
    print("\n  Fitted weights (combined):")
    for f in FACTORS:
        print(f"    {f:<10}: {weights[f]:.4f}")
    with open(out_path, "w") as f:
        json.dump({"weights": weights, "meta": meta}, f, indent=2)
    print(f"\nSaved → {os.path.relpath(out_path)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-severity", action="store_true",
                        help="Fit one model per severity level (recommended)")
    args = parser.parse_args()

    if args.per_severity:
        out = os.path.join(DATA_DIR, "fitted_weights_per_severity.json")
        run_per_severity(out)
    else:
        out = os.path.join(DATA_DIR, "fitted_weights.json")
        run_combined(out)
