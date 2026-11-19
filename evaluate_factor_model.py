"""Per-user ridge model on MovieLens film vectors, compared with the learned blend.

Each user's profile ratings fit a small weight vector over the film vectors
(plus the film average). That vector then scores the films the user has not
been shown. Two numbers matter: rating error (RMSE) and top-5 hit rate, the
share of a user's five highest-predicted films that they rated 4+ stars.

Users are split as in tune_rating_blend.py: train -> film vectors, validation
-> choose the regularisation, test -> reported numbers.

    python evaluate_factor_model.py
    python evaluate_factor_model.py --dims 20 48 100 --profile 15 30
"""

import argparse

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.decomposition import TruncatedSVD

import cinematch
from evaluate_rating_model import HOLDOUT, film_averages, load_ratings, log, to_four_star, train_movielens
from tune_rating_blend import clipped, design, fit_weights, score, signals, split_three

LIKED = to_four_star(4.0)  # 4 stars or more counts as liked
TOP = 5
MIN_FILM_RATINGS = 5
LAMBDAS = [0.03, 0.1, 0.3, 1.0, 3.0]


def film_vectors(train, film_ids, dims):
    counts = train.groupby("film").size()
    part = train[train["film"].isin(counts.index[counts >= MIN_FILM_RATINGS])]
    user_codes, _ = pd.factorize(part["userId"])
    cols = np.searchsorted(film_ids, part["film"].to_numpy())
    matrix = sparse.csr_matrix(
        (part["rating"].to_numpy(np.float64), (user_codes, cols)),
        shape=(int(user_codes.max()) + 1, len(film_ids)),
    )
    row_counts = np.diff(matrix.indptr)
    row_sums = np.asarray(matrix.sum(axis=1)).ravel()
    means = np.divide(row_sums, row_counts, out=np.zeros_like(row_sums), where=row_counts > 0)
    matrix.data -= np.repeat(means, row_counts)

    svd = TruncatedSVD(n_components=dims, n_iter=5, random_state=0).fit(matrix)
    vectors = svd.components_.T * svd.singular_values_[None, :]
    norms = np.linalg.norm(vectors, axis=1)
    np.divide(vectors, norms[:, None], out=vectors, where=norms[:, None] > 0)
    return vectors


def folds(users, profile_size, seed):
    """Same users and films as tune_rating_blend.signals, so the methods are compared on identical rows."""
    rng = np.random.default_rng(seed)
    for user_id, group in users.groupby("userId", sort=False):
        if len(group) < profile_size + 3:
            continue
        order = rng.permutation(len(group))
        films = group["film"].to_numpy()[order]
        scores = group["score"].to_numpy(np.float64)[order]
        yield (
            user_id,
            films[:profile_size], scores[:profile_size],
            films[profile_size : profile_size + HOLDOUT], scores[profile_size : profile_size + HOLDOUT],
        )


def features(films, vectors, film_dev, film_ids):
    idx = np.searchsorted(film_ids, films)
    return np.column_stack([vectors[idx], film_dev[idx]])


def ridge_rows(users, profile_size, seed, vectors, film_dev, film_ids, lam):
    out = {"user": [], "truth": [], "pred": []}
    for user_id, pf, ps, hf, truth in folds(users, profile_size, seed):
        base = ps.mean()
        x_prof = features(pf, vectors, film_dev, film_ids)
        x_hold = features(hf, vectors, film_dev, film_ids)
        weights = np.linalg.solve(x_prof.T @ x_prof + lam * np.eye(x_prof.shape[1]), x_prof.T @ (ps - base))
        out["user"].append(np.full(len(truth), user_id))
        out["truth"].append(truth)
        out["pred"].append(base + x_hold @ weights)
    data = {key: np.concatenate(value) for key, value in out.items()}
    data["pred"] = clipped(data["pred"])
    return data


def top_hit_rate(pred, data):
    truth = np.asarray(data["truth"])
    frame = pd.DataFrame({
        "user": np.asarray(data["user"]),
        "pred": np.asarray(pred),
        "liked": truth >= LIKED - 1e-9,
    })
    top = frame.sort_values("pred", ascending=False, kind="stable").groupby("user").head(TOP)
    return top.groupby("user")["liked"].mean().mean()


def report(name, pred, data):
    row = score(pred, data)
    row["top-5 liked"] = top_hit_rate(pred, data)
    return {"method": name, **row}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=int, default=2000)
    parser.add_argument("--dims", type=int, nargs="+", default=[20, 48, 100], help="film vector sizes to try")
    parser.add_argument("--profile", type=int, nargs="+", default=[15, 30])
    parser.add_argument("--shrink", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    index = joblib.load(cinematch.INDEX_PATH)
    rec = cinematch.Recommender(index)
    ratings = load_ratings(rec)
    train, val, test = split_three(ratings, max(args.profile) + 5, args.users, args.seed)
    film_ids = np.unique(ratings["film"].to_numpy())
    averages, gm = film_averages(train)
    film_dev = averages.reindex(film_ids).fillna(gm).to_numpy() - gm
    log(f"Train ratings: {len(train):,} | validation: {len(val):,} | test: {len(test):,}")

    log("Training MovieLens model for the blend ...")
    model = train_movielens(train, film_ids)
    base_rate = (test["score"] >= LIKED - 1e-9).mean()
    print(f"\nBase rate: {base_rate:.1%} of test films are 4+ stars (a random top-5 would hit this often).")

    for dims in args.dims:
        log(f"Film vectors with {dims} dimensions ...")
        vectors = film_vectors(train, film_ids, dims)
        for profile_size in args.profile:
            val_scores = {}
            for lam in LAMBDAS:
                fit = ridge_rows(val, profile_size, args.seed, vectors, film_dev, film_ids, lam)
                val_scores[lam] = score(fit["pred"], fit)["RMSE"]
            best = min(val_scores, key=val_scores.get)

            val_data = signals(rec, model, val, averages, gm, profile_size, args.seed, args.shrink)
            test_data = signals(rec, model, test, averages, gm, profile_size, args.seed, args.shrink)
            weights = fit_weights(val_data)
            ridge_test = ridge_rows(test, profile_size, args.seed, vectors, film_dev, film_ids, best)

            table = pd.DataFrame([
                report("item mean", clipped(gm + test_data["film"]), test_data),
                report("learned blend", clipped(test_data["base"] + design(test_data) @ weights), test_data),
                report(f"ridge {dims}d (lambda {best:g})", ridge_test["pred"], ridge_test),
                report("sanity: random", np.random.default_rng(args.seed).random(len(test_data["truth"])), test_data),
                report("sanity: oracle", test_data["truth"], test_data),
            ])
            print(f"\n=== {dims} dimensions, profile of {profile_size} ratings ===")
            print("validation RMSE by lambda: " + "  ".join(f"{k:g}:{v:.3f}" for k, v in val_scores.items()))
            print(table.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
