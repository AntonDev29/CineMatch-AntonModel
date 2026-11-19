"""Step 2: learn how much each signal counts, then check on users it never saw.

Users are split three ways and kept apart, so no ratings leak between sets:

  train       -> MovieLens film vectors and film averages
  validation  -> learn the weight of each signal
  test        -> final numbers, reported once per profile size

Each signal is a deviation from the user's own average rating. The learned
blend is a least-squares fit of (truth - user average) on those deviations.

    python tune_rating_blend.py
    python tune_rating_blend.py --profile 15 20 30 --users 2000
"""

import argparse

import joblib
import numpy as np
import pandas as pd
from scipy import stats

import cinematch
from evaluate_rating_model import HOLDOUT, film_averages, load_ratings, log, train_movielens

MIX = 0.5      # Letterboxd share of the previous blend, kept as the reference


def split_three(ratings, min_ratings, n_each, seed):
    counts = ratings.groupby("userId").size()
    eligible = counts.index[counts >= min_ratings].to_numpy()
    rng = np.random.default_rng(seed)
    chosen = rng.choice(eligible, size=min(2 * n_each, len(eligible)), replace=False)
    val_ids, test_ids = chosen[:n_each], chosen[n_each:]
    train = ratings[~ratings["userId"].isin(chosen).to_numpy()]
    val = ratings[ratings["userId"].isin(val_ids).to_numpy()]
    test = ratings[ratings["userId"].isin(test_ids).to_numpy()]
    return train, val, test


def deviation(similarity, centered, shrink):
    """Similarity-weighted average of the user's ratings on similar films, minus their average."""
    return (similarity @ centered) / (np.abs(similarity).sum(axis=1) + shrink)


def signals(rec, model, users, averages, global_mean, profile_size, seed, shrink, content=None):
    """One row per predicted film: the truth, the user's average, and each signal.

    content maps a name to (row lookup, feature matrix) for extra similarity signals.
    """
    rng = np.random.default_rng(seed)
    cols = {key: [] for key in ["user", "truth", "base", "lb", "ml", "mix", "film", "hold", "lb_mass", "ml_mass"]}
    for user_id, group in users.groupby("userId", sort=False):
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

        cols["user"].append(np.full(len(truth), user_id))
        cols["truth"].append(truth)
        cols["base"].append(np.full(len(truth), base))
        cols["lb"].append(deviation(s_lb, centered, shrink))
        cols["ml"].append(deviation(s_ml, centered, shrink))
        cols["mix"].append(deviation(MIX * s_lb + (1 - MIX) * s_ml, centered, shrink))
        cols["film"].append(averages.reindex(hold_f).fillna(global_mean).to_numpy() - global_mean)
        cols["hold"].append(hold_f)
        cols["lb_mass"].append(np.abs(s_lb).sum(axis=1))
        cols["ml_mass"].append(np.abs(s_ml).sum(axis=1))
        for name, (row_of, features) in (content or {}).items():
            similarity = (features[row_of.loc[hold_f].to_numpy()] @ features[row_of.loc[prof_f].to_numpy()].T).toarray()
            cols.setdefault(name, []).append(deviation(similarity, centered, shrink))
    return {key: np.concatenate(value) for key, value in cols.items()}


def design(data, extra=()):
    columns = [data["lb"], data["ml"], data["film"], np.ones(len(data["truth"]))]
    return np.column_stack(columns + [data[name] for name in extra])


def fit_weights(data, extra=()):
    target = data["truth"] - data["base"]
    weights, *_ = np.linalg.lstsq(design(data, extra), target, rcond=None)
    return weights


def clipped(pred):
    return np.clip(pred, 1, 4)


def score(pred, data):
    error = pred - data["truth"]
    frame = pd.DataFrame({"user": data["user"], "pred": pred, "truth": data["truth"]})
    rhos = []
    for _, group in frame.groupby("user"):
        if group["pred"].nunique() > 1 and group["truth"].nunique() > 1:
            rho = stats.spearmanr(group["pred"], group["truth"]).correlation
            if np.isfinite(rho):
                rhos.append(rho)
    return {
        "RMSE": np.sqrt(np.mean(error**2)),
        "MAE": np.mean(np.abs(error)),
        "rank corr (per user)": np.mean(rhos),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=int, default=2000, help="users in each of validation and test")
    parser.add_argument("--profile", type=int, nargs="+", default=[15, 20, 30], help="ratings given to the model")
    parser.add_argument("--shrink", type=float, default=0.5, help="how cautiously neighbours are trusted")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    index = joblib.load(cinematch.INDEX_PATH)
    if index.get("version") != cinematch.INDEX_VERSION:
        raise SystemExit("The Letterboxd index is outdated. Run 'python cinematch.py build' first.")
    rec = cinematch.Recommender(index)

    ratings = load_ratings(rec)
    train, val, test = split_three(ratings, max(args.profile) + 5, args.users, args.seed)
    log(f"Train ratings: {len(train):,} | validation: {len(val):,} | test: {len(test):,}")

    film_ids = np.unique(ratings["film"].to_numpy())
    log("Training MovieLens vectors on training users only ...")
    model = train_movielens(train, film_ids)
    averages, global_mean = film_averages(train)

    fixed_weights = None
    for profile_size in args.profile:
        val_data = signals(rec, model, val, averages, global_mean, profile_size, args.seed, args.shrink)
        test_data = signals(rec, model, test, averages, global_mean, profile_size, args.seed, args.shrink)
        weights = fit_weights(val_data)
        if fixed_weights is None:
            fixed_weights = weights

        print(f"\n=== Profile of {profile_size} ratings (shrink={args.shrink:g}) ===")
        print("learned weights  lb={:.3f}  ml={:.3f}  film={:.3f}  intercept={:.3f}".format(*weights))

        val_learned = clipped(val_data["base"] + design(val_data) @ weights)
        val_previous = clipped(val_data["base"] + val_data["mix"] + 0.5 * val_data["film"])
        print("validation RMSE  learned={:.3f}  previous blend={:.3f}".format(
            score(val_learned, val_data)["RMSE"], score(val_previous, val_data)["RMSE"]))

        methods = {
            "item mean": clipped(global_mean + test_data["film"]),
            "movielens knn": clipped(test_data["base"] + test_data["ml"]),
            "letterboxd knn": clipped(test_data["base"] + test_data["lb"]),
            "previous blend (lb=0.5, film=0.5)": clipped(test_data["base"] + test_data["mix"] + 0.5 * test_data["film"]),
            "learned blend": clipped(test_data["base"] + design(test_data) @ weights),
            f"fixed weights from {args.profile[0]} ratings": clipped(
                test_data["base"] + design(test_data) @ fixed_weights),
        }
        table = pd.DataFrame([{"method": name, **score(pred, test_data)} for name, pred in methods.items()])
        print(table.round(3).to_string(index=False))
        print({"test users": len(np.unique(test_data["user"])), "predictions": len(test_data["truth"])})


if __name__ == "__main__":
    main()
