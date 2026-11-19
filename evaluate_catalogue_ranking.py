"""Step 4: rank the whole app catalogue, and check how the blend does with few ratings.

For each test user, the candidates are every catalogue film they have not rated, plus
their 30 held-out films (which have real ratings). Held-out films rated 4+ stars are the
positives. Unrated candidates count as negatives for every method alike, so the methods
are compared fairly, but the absolute hit rates are understated.

Per user:
  AUC   chance that a liked film ranks above a random candidate (0.5 = chance)
  P@5   share of the top 5 that are liked held-out films
  R@20  share of the liked held-out films that appear in the top 20

    python evaluate_catalogue_ranking.py
    python evaluate_catalogue_ranking.py --profile 3 5 10 15 30
"""

import argparse

import joblib
import numpy as np
import pandas as pd
from scipy import stats

import cinematch
from evaluate_content_blend import movielens_to_letterboxd, tag_features
from evaluate_factor_model import LIKED
from evaluate_rating_model import HOLDOUT, film_averages, load_ratings, log, train_movielens
from export_for_app import choose_films
from export_rating_model import pick_users
from tune_rating_blend import clipped, score

CATALOGUE = 8000
NAMES = ("lb", "ml", "film")
NAMES_TAG = NAMES + ("tag",)
RANK_KEYS = ("AUC", "P@5", "R@20")


def user_items(catalogue, user_ids, profile_size, seed):
    rng = np.random.default_rng(seed)
    sub = catalogue[catalogue["userId"].isin(user_ids)]
    for user_id, group in sub.groupby("userId", sort=False):
        if len(group) < profile_size + 3:
            continue
        order = rng.permutation(len(group))
        yield user_id, group["cidx"].to_numpy()[order], group["score"].to_numpy(np.float64)[order]


def deviations(cidx, scores, profile_size, sims, shrink):
    """Deviation of every catalogue film from the user's average, one per source (same formula as tune_rating_blend)."""
    prof, prof_s = cidx[:profile_size], scores[:profile_size]
    base = prof_s.mean()
    centered = prof_s - base
    out = {"base": base}
    for name, matrix in sims.items():
        similarity = (matrix @ matrix[prof].T).toarray()
        out[name] = (similarity @ centered) / (np.abs(similarity).sum(axis=1) + shrink)
    return out


def features(dev, film_dev, idx, names):
    columns = [film_dev[idx] if name == "film" else dev[name][idx] for name in names]
    return np.column_stack(columns + [np.ones(len(idx))])


def fit_weights_for(groups, profile_size, sims, film_dev, shrink, names):
    xs, ys = [], []
    for _, cidx, scores in groups:
        dev = deviations(cidx, scores, profile_size, sims, shrink)
        hold = cidx[profile_size : profile_size + HOLDOUT]
        xs.append(features(dev, film_dev, hold, names))
        ys.append(scores[profile_size : profile_size + HOLDOUT] - dev["base"])
    weights, *_ = np.linalg.lstsq(np.vstack(xs), np.concatenate(ys), rcond=None)
    return weights


def rank_metrics(values, y):
    n, p = len(y), int(y.sum())
    ranks = stats.rankdata(values)
    auc = (ranks[y].sum() - p * (p + 1) / 2) / (p * (n - p))
    order = np.argsort(-values, kind="stable")
    return auc, y[order[:5]].mean(), y[order[:20]].sum() / p


def summarise(values):
    values = np.asarray(values, dtype=np.float64)
    se = values.std(ddof=1) / np.sqrt(len(values))
    return f"{values.mean():.3f} ±{se:.3f}"


def paired_gain(a, b):
    diff = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    return f"{diff.mean():+.3f} ±{diff.std(ddof=1) / np.sqrt(len(diff)):.3f}"


def evaluate(groups, profile_size, sims, film_dev, gm, shrink, models, seed):
    n_films = len(film_dev)
    rng = np.random.default_rng(seed + 1)
    methods = ["random", "item mean", *models]
    ranking = {m: {key: [] for key in RANK_KEYS} for m in methods}
    preds = {m: [] for m in methods if m != "random"}
    truths, users = [], []
    valid_users = 0

    for user_id, cidx, scores in groups:
        hold = cidx[profile_size : profile_size + HOLDOUT]
        truth = scores[profile_size : profile_size + HOLDOUT]
        dev = deviations(cidx, scores, profile_size, sims, shrink)

        truths.append(truth)
        users.append(np.full(len(truth), user_id))
        preds["item mean"].append(clipped(gm + film_dev[hold]))
        for name, (weights, names) in models.items():
            preds[name].append(clipped(dev["base"] + features(dev, film_dev, hold, names) @ weights))

        seen = np.zeros(n_films, dtype=bool)
        seen[cidx] = True
        candidate = ~seen
        candidate[hold] = True
        cand = np.flatnonzero(candidate)
        positive = np.zeros(n_films, dtype=bool)
        positive[hold[truth >= LIKED - 1e-9]] = True
        y = positive[cand]
        if y.sum() == 0 or y.all():
            continue
        valid_users += 1

        full = {"random": rng.random(n_films), "item mean": film_dev}
        for name, (weights, names) in models.items():
            full[name] = features(dev, film_dev, np.arange(n_films), names) @ weights
        for name, values in full.items():
            for key, value in zip(RANK_KEYS, rank_metrics(values[cand], y)):
                ranking[name][key].append(value)

    data = {"user": np.concatenate(users), "truth": np.concatenate(truths)}
    rows = []
    for name in methods:
        row = {"method": name, "RMSE": np.nan, "rank corr": np.nan}
        if name != "random":
            metrics = score(np.concatenate(preds[name]), data)
            row["RMSE"] = metrics["RMSE"]
            row["rank corr"] = metrics["rank corr (per user)"]
        for key in RANK_KEYS:
            row[key] = summarise(ranking[name][key])
        rows.append(row)

    gains = []
    for key in ("AUC", "P@5"):
        gains.append(f"  {key}: learned blend - item mean  {paired_gain(ranking['learned blend'][key], ranking['item mean'][key])}")
        gains.append(f"  {key}: + tag - learned blend     {paired_gain(ranking['learned blend + tag'][key], ranking['learned blend'][key])}")
    return rows, gains, valid_users


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=int, default=2000, help="users in each of validation and test")
    parser.add_argument("--profile", type=int, nargs="+", default=[3, 5, 10, 15, 30], help="ratings given to the model")
    parser.add_argument("--shrink", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    index = joblib.load(cinematch.INDEX_PATH)
    if index.get("version") != cinematch.INDEX_VERSION:
        raise SystemExit("The Letterboxd index is outdated. Run 'python cinematch.py build' first.")
    rec = cinematch.Recommender(index)

    ratings = load_ratings(rec)
    rows = choose_films(rec, CATALOGUE)
    cat_ids = rec.meta["id"].to_numpy()[rows].astype(np.int64)
    cat_index = pd.Series(np.arange(len(rows)), index=cat_ids)
    catalogue = ratings[ratings["film"].isin(cat_ids)].copy()
    catalogue["cidx"] = catalogue["film"].map(cat_index).astype(np.int64)
    log(f"Catalogue: {len(rows):,} films | ratings on catalogue: {len(catalogue):,}")

    val_ids, test_ids = pick_users(catalogue.groupby("userId").size(), max(args.profile) + 5, args.users, args.seed)
    held = ratings["userId"].isin(np.concatenate([val_ids, test_ids])).to_numpy()
    train = ratings[~held]
    film_ids = np.unique(np.concatenate([ratings["film"].to_numpy(), cat_ids]))
    log("Training MovieLens vectors on training users only ...")
    model = train_movielens(train, film_ids)
    averages, gm = film_averages(train)
    film_dev = averages.reindex(cat_ids).fillna(gm).to_numpy() - gm

    ml_to_lb = movielens_to_letterboxd(rec)
    tag_row_of, tag_matrix = tag_features(film_ids, ml_to_lb)
    sims = {
        "lb": rec.matrix[rows].tocsr(),
        "ml": model.features_for(cat_ids).tocsr(),
        "tag": tag_matrix[tag_row_of.loc[cat_ids].to_numpy()].tocsr(),
    }

    for profile_size in args.profile:
        val_groups = list(user_items(catalogue, val_ids, profile_size, args.seed))
        w_plain = fit_weights_for(val_groups, profile_size, sims, film_dev, args.shrink, NAMES)
        w_tag = fit_weights_for(val_groups, profile_size, sims, film_dev, args.shrink, NAMES_TAG)
        models = {"learned blend": (w_plain, NAMES), "learned blend + tag": (w_tag, NAMES_TAG)}
        print(f"\nWeights at {profile_size} ratings (validation users):")
        print("  plain: " + "  ".join(f"{n}={v:.3f}" for n, v in zip(NAMES + ("intercept",), w_plain)))
        print("  + tag: " + "  ".join(f"{n}={v:.3f}" for n, v in zip(NAMES_TAG + ("intercept",), w_tag)))

        groups = user_items(catalogue, test_ids, profile_size, args.seed)
        table, gains, valid = evaluate(groups, profile_size, sims, film_dev, gm, args.shrink, models, args.seed)
        print(f"\n=== Profile of {profile_size} ratings | {valid:,} test users with a liked held-out film ===")
        print(pd.DataFrame(table).round(3).to_string(index=False))
        print("Paired gains (mean ± standard error across users):")
        print("\n".join(gains))


if __name__ == "__main__":
    main()
