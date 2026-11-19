"""Builds the rating-prediction model as a test file for the app catalogue.

Mirrors what the app will hold: the same 8000 films as export_for_app.py, and
for each film its 50 nearest films from each source (Letterboxd and MovieLens),
plus the film average and the fixed weights. The file is reloaded from disk and
scored by the same reader the app will follow, so the reported numbers are
for the exported file itself.

Writes rating_model_test.json by default. The app's cinematch_model.json is not touched.

    python export_rating_model.py
    python export_rating_model.py --profile 15 30 --neighbors 50
"""

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy import sparse

import cinematch
from evaluate_content_blend import movielens_to_letterboxd, tag_features
from evaluate_rating_model import HOLDOUT, film_averages, load_ratings, log, train_movielens
from export_for_app import choose_films
from movielens import MovieLensAudienceModel
from tune_rating_blend import clipped, design, fit_weights, score

ROOT = Path(__file__).resolve().parent
FORMAT_VERSION = 2
PERSONAL_FROM = 10
EXTRA = ("tag",)


def pick_users(counts, min_ratings, n_each, seed):
    eligible = counts.index[counts >= min_ratings].to_numpy()
    rng = np.random.default_rng(seed)
    chosen = rng.choice(eligible, size=min(2 * n_each, len(eligible)), replace=False)
    return chosen[:n_each], chosen[n_each:]


def similarity_matrices(rec, model, cat_ids, rows):
    matrix = rec.matrix[rows].tocsr()
    s_lb = (matrix @ matrix.T).toarray().astype(np.float32)
    features = model.features_for(cat_ids).toarray()
    s_ml = (features @ features.T).astype(np.float32)
    return s_lb, s_ml


def top_neighbors(similarity, k):
    sims = similarity.copy()
    np.fill_diagonal(sims, -np.inf)
    idx = np.argpartition(-sims, k - 1, axis=1)[:, :k]
    vals = np.take_along_axis(sims, idx, axis=1)
    order = np.argsort(-vals, axis=1)
    return np.take_along_axis(idx, order, axis=1), np.take_along_axis(vals, order, axis=1)


def neighbor_lists(idx, vals):
    return [
        [[int(j), round(float(s), 4)] for j, s in zip(row_idx, row_vals) if s > 0]
        for row_idx, row_vals in zip(idx, vals)
    ]


def tag_matrices(tag_row_of, tag_matrix, cat_ids):
    rows = tag_matrix[tag_row_of.loc[cat_ids].to_numpy()].tocsr()
    return rows, (rows @ rows.T).toarray().astype(np.float32)


def make_json(lb_lists, ml_lists, tag_lists, film_dev, gm, names, cat_ids, shrink):
    return {
        "ratingFormatVersion": FORMAT_VERSION,
        "shrink": shrink,
        "globalMean": round(float(gm), 4),
        "personalFromRatings": PERSONAL_FROM,
        "weights": None,
        "films": [
            {"id": int(i), "title": str(t), "filmDeviation": round(float(d), 4)}
            for i, t, d in zip(cat_ids, names, film_dev)
        ],
        "letterboxdNeighbors": lb_lists,
        "movielensNeighbors": ml_lists,
        "tagNeighbors": tag_lists,
    }


def weights_dict(w):
    return {"letterboxd": float(w[0]), "movielens": float(w[1]), "filmDeviation": float(w[2]),
            "intercept": float(w[3]), "tag": float(w[4])}


def sparse_from_lists(lists, n):
    rows = np.repeat(np.arange(n), [len(entries) for entries in lists])
    cols = np.array([j for entries in lists for j, _ in entries], dtype=np.int64)
    vals = np.array([s for entries in lists for _, s in entries], dtype=np.float64)
    return sparse.csr_matrix((vals, (rows, cols)), shape=(n, n))


def reader(data):
    """What the app does: turn the file into neighbour matrices and weights."""
    n = len(data["films"])
    lb = sparse_from_lists(data["letterboxdNeighbors"], n)
    ml = sparse_from_lists(data["movielensNeighbors"], n)
    tg = sparse_from_lists(data["tagNeighbors"], n)
    film_dev = np.array([f["filmDeviation"] for f in data["films"]])
    return lb, ml, tg, film_dev


def user_groups(catalogue_ratings, user_ids):
    sub = catalogue_ratings[catalogue_ratings["userId"].isin(user_ids)]
    return [
        (user_id, group["cidx"].to_numpy(), group["score"].to_numpy(np.float64))
        for user_id, group in sub.groupby("userId", sort=False)
    ]


def deviations(matrix, prof, hold, centered, shrink):
    """Same formula as tune_rating_blend.py: similarity-weighted deviation from the user's average."""
    sub = matrix[hold][:, prof]
    num = np.asarray(sub @ centered).ravel()
    den = np.asarray(abs(sub).sum(axis=1)).ravel() + shrink
    return num / den


def build_rows(groups, profile_size, seed, lb, ml, tg, film_dev, shrink):
    rng = np.random.default_rng(seed)
    out = {key: [] for key in ["user", "truth", "base", "lb", "ml", "film", "tag"]}
    for user_id, cidx, scores in groups:
        if len(cidx) < profile_size + 3:
            continue
        order = rng.permutation(len(cidx))
        cidx, scores = cidx[order], scores[order]
        prof, prof_s = cidx[:profile_size], scores[:profile_size]
        hold = cidx[profile_size : profile_size + HOLDOUT]
        truth = scores[profile_size : profile_size + HOLDOUT]
        base = prof_s.mean()
        centered = prof_s - base

        out["user"].append(np.full(len(truth), user_id))
        out["truth"].append(truth)
        out["base"].append(np.full(len(truth), base))
        out["lb"].append(deviations(lb, prof, hold, centered, shrink))
        out["ml"].append(deviations(ml, prof, hold, centered, shrink))
        out["tag"].append(deviations(tg, prof, hold, centered, shrink))
        out["film"].append(film_dev[hold])
    return {key: np.concatenate(value) for key, value in out.items()}


def predict(rows, weights):
    return clipped(rows["base"] + design(rows, EXTRA) @ weights)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--catalogue", type=int, default=8000, help="films in the app (as export_for_app.py)")
    parser.add_argument("--neighbors", type=int, default=50, help="neighbours kept per film and source")
    parser.add_argument("--profile", type=int, nargs="+", default=[10, 15, 30],
                        help="ratings given to the model; weights are fit at the first size")
    parser.add_argument("--users", type=int, default=2000, help="users in each of validation and test")
    parser.add_argument("--shrink", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=str(ROOT / "rating_model_test.json"))
    args = parser.parse_args()

    index = joblib.load(cinematch.INDEX_PATH)
    rec = cinematch.Recommender(index)

    ratings = load_ratings(rec)
    rows = choose_films(rec, args.catalogue)
    cat_ids = rec.meta["id"].to_numpy()[rows].astype(np.int64)
    names = rec.meta["name"].to_numpy()[rows]
    cat_index = pd.Series(np.arange(len(rows)), index=cat_ids)
    catalogue = ratings[ratings["film"].isin(cat_ids)].copy()
    catalogue["cidx"] = catalogue["film"].map(cat_index).astype(np.int64)
    log(f"Catalogue: {len(rows):,} films | ratings on catalogue: {len(catalogue):,}")

    min_ratings = max(args.profile) + 5
    val_ids, test_ids = pick_users(catalogue.groupby("userId").size(), min_ratings, args.users, args.seed)
    held = ratings["userId"].isin(np.concatenate([val_ids, test_ids])).to_numpy()
    train = ratings[~held]

    film_ids = np.unique(np.concatenate([ratings["film"].to_numpy(), cat_ids]))
    log("Evaluation model: MovieLens vectors on training users only ...")
    model_eval = train_movielens(train, film_ids)
    averages, gm = film_averages(train)
    film_dev = averages.reindex(cat_ids).fillna(gm).to_numpy() - gm

    tag_row_of, tag_matrix = tag_features(film_ids, movielens_to_letterboxd(rec))
    s_lb, s_ml = similarity_matrices(rec, model_eval, cat_ids, rows)
    _, s_tg = tag_matrices(tag_row_of, tag_matrix, cat_ids)
    lb_idx, lb_val = top_neighbors(s_lb, args.neighbors)
    ml_idx, ml_val = top_neighbors(s_ml, args.neighbors)
    tg_idx, tg_val = top_neighbors(s_tg, args.neighbors)
    data = json.loads(json.dumps(make_json(
        neighbor_lists(lb_idx, lb_val), neighbor_lists(ml_idx, ml_val), neighbor_lists(tg_idx, tg_val),
        film_dev, gm, names, cat_ids, args.shrink)))
    lb_t, ml_t, tg_t, film_t = reader(data)
    gm_t = data["globalMean"]

    val_groups = user_groups(catalogue, val_ids)
    test_groups = user_groups(catalogue, test_ids)
    fit_profile = args.profile[0]
    val_rows = build_rows(val_groups, fit_profile, args.seed, lb_t, ml_t, tg_t, film_t, args.shrink)
    weights = np.round(fit_weights(val_rows, EXTRA), 4)
    data["weights"] = weights_dict(weights)
    log(f"Weights fit on validation users at {fit_profile} ratings: {data['weights']}")

    for profile_size in args.profile:
        test_t = build_rows(test_groups, profile_size, args.seed, lb_t, ml_t, tg_t, film_t, args.shrink)
        test_e = build_rows(test_groups, profile_size, args.seed, s_lb, s_ml, s_tg, film_dev, args.shrink)
        methods = {
            "item mean": gm_t + test_t["film"],
            "exact blend (all catalogue films)": predict(test_e, weights),
            "app blend (50 neighbours per film)": predict(test_t, weights),
        }
        table = pd.DataFrame([{"method": name, **score(pred, test_t)} for name, pred in methods.items()])
        print(f"\n=== Profile of {profile_size} ratings ===")
        print(table.round(3).to_string(index=False))
        print({"test users": len(np.unique(test_t["user"])), "predictions": len(test_t["truth"])})

    log("Final model: MovieLens vectors and film averages on all ratings ...")
    model_full = MovieLensAudienceModel.load(cinematch.MOVIELENS_MODEL_PATH)
    averages_full, gm_full = film_averages(ratings)
    film_dev_full = averages_full.reindex(cat_ids).fillna(gm_full).to_numpy() - gm_full
    _, s_ml_full = similarity_matrices(rec, model_full, cat_ids, rows)
    ml_idx_full, ml_val_full = top_neighbors(s_ml_full, args.neighbors)
    final = make_json(
        neighbor_lists(lb_idx, lb_val), neighbor_lists(ml_idx_full, ml_val_full), neighbor_lists(tg_idx, tg_val),
        film_dev_full, gm_full, names, cat_ids, args.shrink)
    final["weights"] = data["weights"]

    out = Path(args.out)
    out.write_text(json.dumps(final, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"Saved {out} ({out.stat().st_size / 1e6:.1f} MB): {len(cat_ids):,} films")


if __name__ == "__main__":
    main()
