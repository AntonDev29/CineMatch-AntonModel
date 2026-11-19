"""Offline test: can a user's own star ratings predict the rest of their ratings?

Users are split in two. Test users are kept out of the MovieLens film vectors,
so their ratings never shape the vectors they are scored with. For each test
user the first k rated films form the profile, and the next few are predicted
from it. MovieLens 0.5-5 stars are rescaled to the app's 1-4 scale.

    python evaluate_rating_model.py
    python evaluate_rating_model.py --users 4000 --profile 3 5 10 --alphas 0.25 0.5 0.75
"""

import argparse
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy import sparse, stats

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import cinematch  # noqa: E402
from movielens import MovieLensAudienceModel  # noqa: E402

HOLDOUT = 30  # films predicted per test user
PRIOR = 5     # pulls film averages with few ratings toward the global mean


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def to_four_star(stars):
    """MovieLens 0.5-5 stars -> the app's 1-4 scale."""
    return 1 + (stars - 0.5) * 2 / 3


def load_ratings(rec):
    mapping = pd.read_csv(cinematch.MOVIELENS_MAPPING_PATH, usecols=["letterboxd_id", "movieId"])
    mapping = mapping[mapping["letterboxd_id"].isin(rec.row_of.index)]
    mapping = mapping.drop_duplicates("movieId").drop_duplicates("letterboxd_id")
    ml_to_lb = pd.Series(mapping["letterboxd_id"].to_numpy(), index=mapping["movieId"].to_numpy())
    log(f"Mapped MovieLens films in the Letterboxd index: {len(ml_to_lb):,}")

    ratings = pd.read_csv(
        cinematch.MOVIELENS_DATA_DIR / "ratings.csv",
        usecols=["userId", "movieId", "rating"],
        dtype={"userId": "int32", "movieId": "int32", "rating": "float32"},
    )
    ratings = ratings[ratings["movieId"].isin(ml_to_lb.index)].reset_index(drop=True)
    ratings["film"] = ratings["movieId"].map(ml_to_lb).astype(np.int64)
    ratings["score"] = to_four_star(ratings["rating"].to_numpy(np.float64)).astype(np.float32)
    log(f"Ratings on mapped films: {len(ratings):,}")
    return ratings


def split(ratings, min_ratings, n_test, seed):
    counts = ratings.groupby("userId").size()
    eligible = counts.index[counts >= min_ratings].to_numpy()
    rng = np.random.default_rng(seed)
    test_users = rng.choice(eligible, size=min(n_test, len(eligible)), replace=False)
    is_test = ratings["userId"].isin(test_users).to_numpy()
    return ratings[~is_test], ratings[is_test]


def train_movielens(train, film_ids):
    user_codes, _ = pd.factorize(train["userId"])
    cols = np.searchsorted(film_ids, train["film"].to_numpy())
    matrix = sparse.csr_matrix(
        (train["rating"].to_numpy(dtype=np.float32), (user_codes, cols)),
        shape=(int(user_codes.max()) + 1, len(film_ids)),
    )
    return MovieLensAudienceModel.fit(matrix, film_ids)


def film_averages(train):
    global_mean = float(train["score"].mean())
    grouped = train.groupby("film")["score"].agg(["sum", "count"])
    averages = (grouped["sum"] + PRIOR * global_mean) / (grouped["count"] + PRIOR)
    return averages, global_mean


def predict_knn(similarity, centered, base, shrink, film_dev=None, beta=0.0):
    """User's average, plus the film's own bias (optional), plus similar films' deviations."""
    weight = np.abs(similarity).sum(axis=1) + shrink
    pred = base + similarity @ centered / weight
    if film_dev is not None:
        pred = pred + beta * film_dev
    return np.clip(pred, 1, 4)


def evaluate(rec, model, test, averages, global_mean, profile_size, shrink, alphas, betas):
    methods = ["global mean", "item mean", "user mean", "user+film bias", "letterboxd knn", "movielens knn"]
    methods += [f"combined (lb={a:g})" for a in alphas]
    methods += [f"blend (lb={a:g}, film={b:g})" for a in alphas for b in betas]
    preds = {name: [] for name in methods}
    rhos = {name: [] for name in methods}
    truths, lb_cover, ml_cover = [], [], []
    rng = np.random.default_rng(0)

    for _, group in test.groupby("userId", sort=False):
        if len(group) < profile_size + 3:
            continue
        order = rng.permutation(len(group))
        films = group["film"].to_numpy()[order]
        scores = group["score"].to_numpy(np.float64)[order]

        prof_f, prof_s = films[:profile_size], scores[:profile_size]
        hold_f = films[profile_size : profile_size + HOLDOUT]
        truth = scores[profile_size : profile_size + HOLDOUT]
        base = prof_s.mean()
        centered = prof_s - base

        lb_prof = rec.row_of.loc[prof_f].to_numpy()
        lb_hold = rec.row_of.loc[hold_f].to_numpy()
        s_lb = (rec.matrix[lb_hold] @ rec.matrix[lb_prof].T).toarray()
        s_ml = model.features_for(hold_f).toarray() @ model.features_for(prof_f).toarray().T

        film_dev = averages.reindex(hold_f).fillna(global_mean).to_numpy() - global_mean
        candidates = {
            "global mean": np.full(len(truth), global_mean),
            "item mean": film_dev + global_mean,
            "user mean": np.full(len(truth), base),
            "user+film bias": np.clip(base + film_dev, 1, 4),
            "letterboxd knn": predict_knn(s_lb, centered, base, shrink),
            "movielens knn": predict_knn(s_ml, centered, base, shrink),
        }
        for a in alphas:
            candidates[f"combined (lb={a:g})"] = predict_knn(
                a * s_lb + (1 - a) * s_ml, centered, base, shrink
            )
            for b in betas:
                candidates[f"blend (lb={a:g}, film={b:g})"] = predict_knn(
                    a * s_lb + (1 - a) * s_ml, centered, base, shrink, film_dev, b
                )

        for name, pred in candidates.items():
            preds[name].append(pred)
            if np.ptp(pred) > 0:
                rho = stats.spearmanr(pred, truth).correlation
                if np.isfinite(rho):
                    rhos[name].append(rho)
        truths.append(truth)
        lb_cover.append(float((np.abs(s_lb).sum(axis=1) > 0).mean()))
        ml_cover.append(float((np.abs(s_ml).sum(axis=1) > 0).mean()))

    truth_all = np.concatenate(truths)
    rows = []
    for name in methods:
        pred_all = np.concatenate(preds[name])
        error = pred_all - truth_all
        rows.append({
            "method": name,
            "RMSE": np.sqrt(np.mean(error**2)),
            "MAE": np.mean(np.abs(error)),
            "rank corr (per user)": np.mean(rhos[name]) if rhos[name] else np.nan,
        })
    info = {
        "users": len(truths),
        "predictions": len(truth_all),
        "letterboxd coverage": np.mean(lb_cover),
        "movielens coverage": np.mean(ml_cover),
    }
    return pd.DataFrame(rows), info


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=int, default=2000, help="number of held-out test users")
    parser.add_argument("--profile", type=int, nargs="+", default=[3, 5, 10], help="ratings given to the model")
    parser.add_argument("--shrink", type=float, default=0.5, help="how cautiously neighbours are trusted")
    parser.add_argument("--alphas", type=float, nargs="+", default=[0.5],
                        help="Letterboxd share in the combined similarity")
    parser.add_argument("--betas", type=float, nargs="+", default=[0.5, 1.0],
                        help="weight of the film average in the blend")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    index = joblib.load(cinematch.INDEX_PATH)
    if index.get("version") != cinematch.INDEX_VERSION:
        raise SystemExit("The Letterboxd index is outdated. Run 'python cinematch.py build' first.")
    rec = cinematch.Recommender(index)

    ratings = load_ratings(rec)
    min_ratings = max(args.profile) + 5
    train, test = split(ratings, min_ratings, args.users, args.seed)
    log(f"Train ratings: {len(train):,} | test ratings: {len(test):,}")

    film_ids = np.unique(ratings["film"].to_numpy())
    log("Training MovieLens vectors on training users only ...")
    model = train_movielens(train, film_ids)
    log(f"MovieLens vectors for {len(model.letterboxd_ids):,} films")

    averages, global_mean = film_averages(train)
    for profile_size in args.profile:
        table, info = evaluate(
            rec, model, test, averages, global_mean, profile_size, args.shrink, args.alphas, args.betas
        )
        print(f"\n=== Profile of {profile_size} ratings ===")
        print(table.round(3).to_string(index=False))
        print({key: (round(value, 3) if isinstance(value, float) else value) for key, value in info.items()})


if __name__ == "__main__":
    main()
