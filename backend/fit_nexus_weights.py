"""
fit_nexus_weights.py  v3
========================
Model shootout: Logistic Regression vs Random Forest vs XGBoost vs SVM.
Weights derived from the best model per severity via mean |SHAP| values
on log-transformed features (so they are directly comparable to exponents).
All final weights normalised to 0–1 (domain always = 1.0 as the primary gate).

Usage:
  python fit_nexus_weights.py --per-severity   # recommended
  python fit_nexus_weights.py                  # combined model
"""

import argparse, csv, json, math, os, sys

_HERE    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_HERE, "..", "data")
FACTORS  = ["domain", "will", "avail", "prox", "fresh"]
COLS     = ["domain_score", "will_score", "avail_score", "prox_score", "fresh_score"]
EPS      = 1e-6
SEV_LABEL = {0: "LOW", 1: "NORMAL", 2: "HIGH"}

CURRENT_W = {
    2: {"domain": 2.00, "will": 1.65, "avail": 1.37, "prox": 0.10, "fresh": 0.10},
    1: {"domain": 2.00, "will": 1.65, "avail": 1.60, "prox": 0.61, "fresh": 0.10},
    0: {"domain": 2.00, "will": 0.98, "avail": 1.06, "prox": 1.01, "fresh": 0.10},
}


# ── I/O ───────────────────────────────────────────────────────────────────────

def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_Xy(rows, domain_min=0.15, domain_max=0.90):
    """
    Log-transform features. Filter to competitive zone where secondary
    factors actually decide the outcome.
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


# ── Model zoo ─────────────────────────────────────────────────────────────────

def _make_models():
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    import xgboost as xgb
    import lightgbm as lgb

    lgbm = lgb.LGBMClassifier(
        n_estimators=100, max_depth=7, learning_rate=0.05,
        num_leaves=63, subsample=0.8, colsample_bytree=0.8,
        min_child_samples=20, class_weight="balanced",
        boosting_type="gbdt", n_jobs=-1,
        random_state=42, verbose=-1)

    xgb_clf = xgb.XGBClassifier(
        n_estimators=100, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, n_jobs=-1,
        eval_metric="logloss", random_state=42, verbosity=0)

    rf = RandomForestClassifier(
        n_estimators=100, max_depth=8, min_samples_leaf=20,
        class_weight="balanced", n_jobs=-1, random_state=42)

    lr = LogisticRegression(
        fit_intercept=True, C=100, max_iter=1000,
        solver="lbfgs", class_weight="balanced", n_jobs=-1, random_state=42)

    return {
        "LogReg":       lr,
        "RandomForest": rf,
        "XGBoost":      xgb_clf,
        "LightGBM":     lgbm,
    }


def _cv_auc(clf, Xa, ya):
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    return cross_val_score(clf, Xa, ya, cv=cv, scoring="roc_auc")


# ── Weight extraction ─────────────────────────────────────────────────────────

def _weights_from_shap(clf, Xa, model_name):
    """
    Use mean |SHAP| values on log-features as proxy for exponent magnitude.
    Works for all tree models and linear models via shap.
    """
    try:
        import shap, numpy as np
        if model_name == "LogReg":
            explainer = shap.LinearExplainer(clf, Xa, feature_perturbation="interventional")
        else:
            explainer = shap.TreeExplainer(clf)
        shap_vals = explainer.shap_values(Xa[:3000])  # sample for speed
        if isinstance(shap_vals, list):          # binary: [neg_class, pos_class]
            shap_vals = shap_vals[1]
        mean_abs = np.abs(shap_vals).mean(axis=0)
        raw = {f: float(v) for f, v in zip(FACTORS, mean_abs)}
        return raw
    except Exception:
        return None


def _weights_from_logreg(clf):
    """Logistic regression coefficients = exponents directly."""
    return {f: float(c) for f, c in zip(FACTORS, clf.coef_[0])}


def _weights_from_importance(clf):
    """Tree feature importances (MDI or XGBoost gain)."""
    return {f: float(v) for f, v in zip(FACTORS, clf.feature_importances_)}


def _normalise(raw: dict, floor=0.05) -> dict:
    """Scale to max=1.0, apply floor."""
    m = max(raw.values())
    if m < EPS:
        return {f: floor for f in raw}
    return {f: max(floor, round(v / m, 4)) for f, v in raw.items()}


# ── Main fitter ───────────────────────────────────────────────────────────────

def fit_severity(sev_int: int, rows: list) -> dict:
    import numpy as np
    sev = SEV_LABEL[sev_int]

    X, y, skipped = build_Xy(rows)
    Xa, ya = np.array(X), np.array(y)
    pos = ya.sum()
    print(f"  Rows after filter: {len(Xa):,}  (skipped {skipped:,})")
    print(f"  Class balance: pos {pos:,} ({pos/len(ya):.1%})  neg {len(ya)-pos:,}")

    models   = _make_models()
    results  = {}
    best_auc = 0.0
    best_name = "LogReg"

    print(f"\n  {'Model':<15} {'ROC-AUC':>10} {'±':>8}")
    print(f"  {'-'*35}")

    for name, clf in models.items():
        try:
            clf.fit(Xa, ya)
            roc = _cv_auc(clf, Xa, ya)
            mean_auc = roc.mean()
            print(f"  {name:<15} {mean_auc:>10.4f} {roc.std():>8.4f}")
            results[name] = {"clf": clf, "auc": mean_auc}
            if mean_auc > best_auc:
                best_auc  = mean_auc
                best_name = name
        except Exception as e:
            print(f"  {name:<15} FAILED: {e}")

    print(f"\n  Best model: {best_name} (AUC={best_auc:.4f})")

    # Extract weights from best model via SHAP (preferred) → coef → importance
    best_clf = results[best_name]["clf"]
    raw_w = _weights_from_shap(best_clf, Xa, best_name)

    if raw_w is None:
        if best_name == "LogReg":
            raw_w = _weights_from_logreg(best_clf)
        elif best_name in ("RandomForest", "XGBoost"):
            raw_w = _weights_from_importance(best_clf)
        else:
            # SVM fallback: use LogReg weights
            lr = results.get("LogReg")
            raw_w = _weights_from_logreg(lr["clf"]) if lr else {f: 1.0 for f in FACTORS}

    print(f"  Raw weights ({best_name} SHAP): {raw_w}")

    # Normalise to 0-1
    normed = _normalise(raw_w)
    print(f"\n  Normalised weights (0-1, max=1.0):")
    print(f"  {'Factor':<10} {'Weight':>8}  (rank)")
    ranked = sorted(normed, key=normed.get, reverse=True)
    for r, f in enumerate(ranked, 1):
        print(f"  {f:<10} {normed[f]:>8.4f}  #{r}")

    # Compare to current
    cur = {k: round(v/max(CURRENT_W[sev_int].values()), 4) for k, v in CURRENT_W[sev_int].items()}
    print(f"\n  vs current (normalised): {cur}")

    return {
        "weights": normed,
        "best_model": best_name,
        "best_auc": round(best_auc, 4),
        "all_aucs": {n: round(r["auc"], 4) for n, r in results.items() if "auc" in r},
    }


def run_per_severity(out_path):
    result = {}
    for sev_int, sev in SEV_LABEL.items():
        path = os.path.join(DATA_DIR, f"training_labels_{sev.lower()}.csv")
        if not os.path.exists(path):
            print(f"Missing {path} — run generate_training_labels.py first")
            sys.exit(1)
        print(f"\n{'='*60}")
        print(f"  {sev} SEVERITY")
        print(f"{'='*60}")
        rows = read_csv(path)
        print(f"  Total rows: {len(rows):,}")
        result[sev_int] = fit_severity(sev_int, rows)

    # Print paste-ready block
    print("\n\n" + "="*60)
    print("SEVERITY_FACTOR_WEIGHTS  (0-1 normalised, paste into nexus.py)")
    print("="*60)
    print("SEVERITY_FACTOR_WEIGHTS: dict = {")
    for sev_int, sev in SEV_LABEL.items():
        w   = result[sev_int]["weights"]
        auc = result[sev_int]["best_auc"]
        mdl = result[sev_int]["best_model"]
        print(f"    {sev_int}: {{  # {sev}  best={mdl}  AUC={auc}")
        for f in FACTORS:
            print(f"        \"{f}\": {w[f]},")
        print("    },")
    print("}")

    with open(out_path, "w") as f:
        json.dump({str(k): v for k, v in result.items()}, f, indent=2)
    print(f"\nSaved → {os.path.relpath(out_path)}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-severity", action="store_true")
    args = parser.parse_args()
    out = os.path.join(DATA_DIR, "fitted_weights_per_severity.json")
    if args.per_severity:
        run_per_severity(out)
    else:
        print("Run with --per-severity for the full shootout.")
