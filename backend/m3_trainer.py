
import argparse
import csv
import os
import pickle
import copy
import math
import re
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.metrics.pairwise import cosine_similarity

from embeddings import embed_texts, embed_with
from path_utils import get_repo_paths
from utils import (
    AVAILABILITY_LEVELS,
    SEVERITY_LABELS,
    SEVERITY_KEYWORDS,
    normalize_phrase,
    load_village_names,
    load_distance_lookup,
    extract_location,
    estimate_severity,
    severity_penalty,
    lookup_distance_km,
    robust_sigmoid as sigmoid, # keeping the name sigmoid for internal compatibility
    read_csv_norm,
    get_any,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("m3_trainer")

@dataclass
class TrainingConfig:
    proposals: str
    people: str
    pairs: str
    out: str = str((get_repo_paths().runtime_dir / "canonical_model.pkl").resolve())
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    village_locations: Optional[str] = None
    village_distances: Optional[str] = None
    distance_scale: float = 50.0
    distance_decay: float = 30.0
    n_estimators: int = 600
    learning_rate: float = 0.03
    subsample: float = 0.85
    max_depth: int = 3
    validation_fraction: float = 0.2
    n_iter_no_change: int = 20
    tol: float = 1e-4
    resume_from_checkpoint: bool = True
    checkpoint_every: int = 1

def as2d(v):
    """Ensure a single sample row is 2D for cosine_similarity."""
    import numpy as np
    from scipy import sparse
    if 'sparse' in str(type(v)) or sparse.issparse(v):
        return v  # already 2D row in sparse format
    v = np.asarray(v)
    return v.reshape(1, -1) if v.ndim == 1 else v


def _checkpoint_paths(out_path: str) -> Dict[str, Path]:
    base = Path(out_path).resolve()
    return {
        "progress": base.with_name(f"{base.stem}.progress.pkl"),
        "best": base.with_name(f"{base.stem}.best.pkl"),
    }


def _save_pickle(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        pickle.dump(payload, handle)


def _load_pickle(path: Path) -> Optional[Dict[str, object]]:
    if not path.exists():
        return None
    with open(path, "rb") as handle:
        return pickle.load(handle)

# -------------- core builder -------------

def build_feature_matrix(props, people, pairs, prop_model, people_model, backend,
                         proposal_locations: Dict[str, str],
                         severity_levels: Dict[str, int],
                         distance_lookup: Dict[Tuple[str, str], Dict[str, float]],
                         distance_scale: float,
                         distance_decay: float):
    # proposals map
    prop_map = {}
    for r in props:
        pid = get_any(r, ["proposal_id", "id"])
        ptxt = get_any(r, ["text", "proposal_text", "description", "body", "content"], "")
        if pid is not None:
            prop_map[pid] = ptxt

    # normalize people
    people_norm = []
    for r in people:
        pid = get_any(r, ["person_id", "student_id", "id"])
        if not pid:
            continue
        txt = get_any(r, ["text", "skills"], "")
        eff = float(get_any(r, ["willingness_eff", "eff", "w_eff"], 0.5))
        bias = float(get_any(r, ["willingness_bias", "bias", "w_bias"], 0.5))
        name = get_any(r, ["name", "person_name", "full_name"], pid)
        people_norm.append({
            "person_id": pid,
            "name": name,
            "text": txt,
            "eff": eff,
            "bias": bias,
            "availability": (get_any(r, ["availability"], "") or "").lower(),
            "home_location": get_any(r, ["home_location", "location", "village"], ""),
        })
    people_map = {r["person_id"]: r for r in people_norm}

    # collect unique ids from pairs
    prop_ids = []
    person_ids = []
    for r in pairs:
        pid = get_any(r, ["proposal_id", "id"])
        sid = get_any(r, ["person_id", "student_id", "id"])
        if pid is not None and sid is not None:
            prop_ids.append(pid)
            person_ids.append(sid)
    prop_ids = sorted(set(prop_ids))
    person_ids = sorted(set(person_ids))

    # embed unique texts
    try:
        prop_texts = [prop_map[pid] for pid in prop_ids]
    except KeyError as e:
        missing = str(e).strip("'")
        raise ValueError(f"pairs.csv references proposal_id '{missing}' which is not found in proposals.csv. Please ensure all proposal IDs in pairs.csv are present in proposals.csv.")

    try:
        person_texts = [people_map[sid]["text"] for sid in person_ids]
    except KeyError as e:
        missing = str(e).strip("'")
        raise ValueError(f"pairs.csv references person_id/student_id '{missing}' which is not found in people.csv. Please ensure all person IDs in pairs.csv are present in people.csv.")

    P = embed_with(prop_model, prop_texts, backend)
    S = embed_with(people_model, person_texts, backend)

    p_index = {pid: i for i, pid in enumerate(prop_ids)}
    s_index = {sid: i for i, sid in enumerate(person_ids)}

    X, y = [], []
    for r in pairs:
        pid = get_any(r, ["proposal_id", "id"])
        sid = get_any(r, ["person_id", "student_id", "id"])
        label = int(get_any(r, ["label", "y", "target"], 0))
        if pid not in p_index or sid not in s_index or sid not in people_map:
            # skip malformed rows
            continue

        pv = as2d(P[p_index[pid]])
        sv = as2d(S[s_index[sid]])
        sim = float(cosine_similarity(pv, sv)[0, 0])

        eff = float(people_map[sid]["eff"])
        bias = float(people_map[sid]["bias"])
        base_W = sigmoid(eff + bias)

        availability_label = people_map[sid]["availability"]
        availability_level = AVAILABILITY_LEVELS.get(availability_label, 1)
        severity_level = severity_levels.get(pid, 1)
        prop_location = proposal_locations.get(pid, "")
        person_location = people_map[sid]["home_location"]
        distance_km = lookup_distance_km(person_location, prop_location, distance_lookup)
        distance_norm = min(distance_km / distance_scale, 1.0) if distance_scale > 0 else 0.0
        distance_penalty = math.exp(-distance_km / distance_decay) if distance_decay > 0 else 1.0
        w_after_severity = max(0.0, base_W - severity_penalty(availability_label, severity_level))
        W = max(0.0, min(1.0, w_after_severity * distance_penalty))

        X.append([
            sim,
            sim * W,
            W,
            distance_norm,
            distance_penalty,
            availability_level / 2.0,
            severity_level / 2.0,
        ])
        y.append(label)

    return np.asarray(X), np.asarray(y)

# --------------- main --------------------

def train_model(config: TrainingConfig) -> float:
    logger.info("Starting training run")
    for path_name, path in (
        ("proposals", config.proposals),
        ("people", config.people),
        ("pairs", config.pairs),
        ("village_locations", config.village_locations),
        ("village_distances", config.village_distances),
    ):
        if path and not os.path.exists(path):
            raise ValueError(f"Not found: {path} ({path_name})")

    logger.info("Loading CSVs")
    props = read_csv_norm(config.proposals)
    people = read_csv_norm(config.people)
    pairs = read_csv_norm(config.pairs)
    logger.info("Loaded %d proposals, %d volunteers, %d labelled pairs", len(props), len(people), len(pairs))

    village_names = load_village_names(config.village_locations)
    distance_lookup = load_distance_lookup(config.village_distances)

    proposal_locations: Dict[str, str] = {}
    severity_levels: Dict[str, int] = {}
    missing_locations = 0
    for r in props:
        pid = get_any(r, ["proposal_id", "id"])
        text = get_any(r, ["text", "proposal_text", "description", "body", "content"], "")
        if pid is None:
            continue
        location = extract_location(text, village_names) if village_names else ""
        if not location:
            missing_locations += 1
        proposal_locations[pid] = location
        severity_levels[pid] = estimate_severity(text)
    if missing_locations and village_names:
        logger.warning("%d proposals did not match a known village name", missing_locations)

    logger.info("Embedding texts using %s", config.model_name)
    prop_texts_all = [get_any(r, ["text","proposal_text","description","body","content"], "") for r in props]
    people_texts_all = [get_any(r, ["text","skills"], "") for r in people]
    prop_model, _, backend = embed_texts(prop_texts_all, model_name=config.model_name)
    people_model, _, backend2 = embed_texts(people_texts_all, model_name=config.model_name)

    if backend == "tfidf" or backend2 == "tfidf":
        logger.info("Falling back to shared TF-IDF vectorizer")
        from embeddings import embed_texts as _embed
        combined = prop_texts_all + people_texts_all
        shared_vec, _, _ = _embed(combined, model_name=config.model_name)
        prop_model = shared_vec
        people_model = shared_vec
        backend = "tfidf"
    else:
        backend = "sentence-transformers"

    X, y = build_feature_matrix(
        props,
        people,
        pairs,
        prop_model,
        people_model,
        backend,
        proposal_locations,
        severity_levels,
        distance_lookup,
        config.distance_scale,
        config.distance_decay,
    )

    n = len(y)
    if n == 0:
        raise ValueError("No training pairs after normalization. Check your CSV headers/values.")

    logger.info("Feature matrix shape: %s, %d labels", X.shape, n)
    rng = np.random.RandomState(42)
    idx = rng.permutation(n)
    split = max(1, int(0.8 * n))
    tr, va = idx[:split], idx[split:]
    Xtr, ytr = X[tr], y[tr]
    Xva, yva = X[va], y[va]

    checkpoint_paths = _checkpoint_paths(config.out)
    max_estimators = max(1, int(config.n_estimators))
    patience_limit = max(1, int(config.n_iter_no_change))
    start_stage = 1
    best_stage = 0
    best_score = float("-inf")
    best_model = None
    clf = None

    if config.resume_from_checkpoint:
        resume_bundle = _load_pickle(checkpoint_paths["best"]) or _load_pickle(checkpoint_paths["progress"])
        if resume_bundle:
            clf = resume_bundle.get("model")
            if clf is not None:
                clf.set_params(warm_start=True)
                best_stage = int(resume_bundle.get("best_stage", resume_bundle.get("stage", 0)))
                best_score = float(resume_bundle.get("best_score", float("-inf")))
                best_model = copy.deepcopy(resume_bundle.get("best_model", clf))
                start_stage = max(1, int(resume_bundle.get("stage", best_stage)) + 1)
                logger.info(
                    "Resuming training from checkpoint %s at stage %d (best stage %d, best score %.4f)",
                    checkpoint_paths["best"] if checkpoint_paths["best"].exists() else checkpoint_paths["progress"],
                    start_stage,
                    best_stage,
                    best_score,
                )

    if clf is None:
        clf = GradientBoostingClassifier(
            random_state=42,
            warm_start=True,
            n_estimators=1,
            learning_rate=config.learning_rate,
            subsample=config.subsample,
            max_depth=config.max_depth,
        )

    logger.info("Training GradientBoostingClassifier with manual early stopping and checkpoints")
    no_improve = 0
    latest_stage = start_stage - 1
    for stage in range(start_stage, max_estimators + 1):
        clf.set_params(n_estimators=stage, warm_start=True)
        clf.fit(Xtr, ytr)
        latest_stage = stage

        if len(Xva) and len(np.unique(yva)) > 1:
            stage_pred = clf.predict_proba(Xva)[:, 1]
            stage_score = roc_auc_score(yva, stage_pred)
        else:
            stage_score = float(clf.score(Xtr, ytr))

        current_bundle = {
            "model": clf,
            "backend": backend,
            "distance_scale": config.distance_scale,
            "distance_decay": config.distance_decay,
            "stage": stage,
            "best_stage": best_stage,
            "best_score": best_score,
            "train_config": {
                "n_estimators": config.n_estimators,
                "learning_rate": config.learning_rate,
                "subsample": config.subsample,
                "max_depth": config.max_depth,
                "validation_fraction": config.validation_fraction,
                "n_iter_no_change": config.n_iter_no_change,
                "tol": config.tol,
                "resume_from_checkpoint": config.resume_from_checkpoint,
            },
        }
        if config.checkpoint_every and stage % max(1, int(config.checkpoint_every)) == 0:
            _save_pickle(checkpoint_paths["progress"], current_bundle)

        if stage_score > best_score + config.tol:
            best_score = float(stage_score)
            best_stage = stage
            best_model = copy.deepcopy(clf)
            best_bundle = dict(current_bundle)
            best_bundle["model"] = best_model
            best_bundle["best_model"] = best_model
            best_bundle["best_stage"] = best_stage
            best_bundle["best_score"] = best_score
            _save_pickle(checkpoint_paths["best"], best_bundle)
            no_improve = 0
            logger.info("Stage %d improved validation score to %.4f", stage, stage_score)
        else:
            no_improve += 1
            logger.info("Stage %d validation score %.4f (best %.4f at stage %d)", stage, stage_score, best_score, best_stage)

        if no_improve >= patience_limit:
            logger.info("Early stopping triggered after %d consecutive non-improving stages", no_improve)
            break

    if best_model is None:
        best_model = copy.deepcopy(clf)
        best_stage = latest_stage
        if len(Xva) and len(np.unique(yva)) > 1:
            best_score = float(roc_auc_score(yva, best_model.predict_proba(Xva)[:, 1]))
        else:
            best_score = float(best_model.score(Xtr, ytr))

    auc = best_score if math.isfinite(best_score) else float("nan")
    logger.info("Validation AUC: %.3f (backend=%s)", auc, backend)

    logger.info("Saving model bundle to %s", config.out)
    with open(config.out, "wb") as f:
        pickle.dump({
            "model": best_model,
            "backend": backend,
            "prop_model": prop_model,
            "people_model": people_model,
            "distance_scale": config.distance_scale,
            "distance_decay": config.distance_decay,
            "n_estimators_used": int(getattr(best_model, "n_estimators_", best_stage)),
            "best_stage": best_stage,
            "best_score": float(auc),
            "checkpoint_paths": {key: str(value) for key, value in checkpoint_paths.items()},
            "train_config": {
                "n_estimators": config.n_estimators,
                "learning_rate": config.learning_rate,
                "subsample": config.subsample,
                "max_depth": config.max_depth,
                "validation_fraction": config.validation_fraction,
                "n_iter_no_change": config.n_iter_no_change,
                "tol": config.tol,
                "resume_from_checkpoint": config.resume_from_checkpoint,
                "checkpoint_every": config.checkpoint_every,
            },
        }, f)
    logger.info("Training run complete")
    return float(auc)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proposals", required=True)
    ap.add_argument("--people", required=True)
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--out", default=str((get_repo_paths().runtime_dir / "canonical_model.pkl").resolve()))
    ap.add_argument("--model_name", default="sentence-transformers/all-MiniLM-L6-v2")
    default_dataset_root = str(get_repo_paths().data_dir.resolve())
    ap.add_argument("--village_locations", default=os.path.join(default_dataset_root, "village_locations.csv"))
    ap.add_argument("--village_distances", default=os.path.join(default_dataset_root, "village_distances.csv"))
    ap.add_argument("--distance_scale", type=float, default=50.0, help="Distance in km mapped to 1.0 in features")
    ap.add_argument("--distance_decay", type=float, default=30.0, help="Decay constant (km) for distance penalty exp(-d/decay)")
    ap.add_argument("--n_estimators", type=int, default=600)
    ap.add_argument("--learning_rate", type=float, default=0.03)
    ap.add_argument("--subsample", type=float, default=0.85)
    ap.add_argument("--max_depth", type=int, default=3)
    ap.add_argument("--validation_fraction", type=float, default=0.2)
    ap.add_argument("--n_iter_no_change", type=int, default=20)
    ap.add_argument("--tol", type=float, default=1e-4)
    ap.add_argument("--resume_from_checkpoint", action="store_true", default=True)
    ap.add_argument("--no-resume_from_checkpoint", dest="resume_from_checkpoint", action="store_false")
    ap.add_argument("--checkpoint_every", type=int, default=1)
    args = ap.parse_args()

    config = TrainingConfig(
        proposals=args.proposals,
        people=args.people,
        pairs=args.pairs,
        out=args.out,
        model_name=args.model_name,
        village_locations=args.village_locations,
        village_distances=args.village_distances,
        distance_scale=args.distance_scale,
        distance_decay=args.distance_decay,
        n_estimators=args.n_estimators,
        learning_rate=args.learning_rate,
        subsample=args.subsample,
        max_depth=args.max_depth,
        validation_fraction=args.validation_fraction,
        n_iter_no_change=args.n_iter_no_change,
        tol=args.tol,
        resume_from_checkpoint=args.resume_from_checkpoint,
        checkpoint_every=args.checkpoint_every,
    )
    train_model(config)

if __name__ == "__main__":
    main()
