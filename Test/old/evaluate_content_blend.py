"""Step 3: add content signals to the learned blend and check top-of-list quality.

Two content similarities are added, both as deviations from the user's average:

  genre -> cosine similarity of MovieLens genre vectors
  tag   -> cosine similarity of TF-IDF vectors built from MovieLens user tags

Weights are fit on validation users and reported on separate test users, with the
same split and seed as tune_rating_blend.py so the rows are comparable.

    python evaluate_content_blend.py
    python evaluate_content_blend.py --profile 15 30
"""

import argparse

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

import cinematch
from evaluate_factor_model import LIKED, top_hit_rate
from evaluate_rating_model import film_averages, load_ratings, log, train_movielens
from tune_rating_blend import clipped, design, fit_weights, score, signals, split_three


def movielens_to_letterboxd(rec):
    mapping = pd.read_csv(cinematch.MOVIELENS_MAPPING_PATH, usecols=["letterboxd_id", "movieId"])
    mapping = mapping[mapping["letterboxd_id"].isin(rec.row_of.index)]
    mapping = mapping.drop_duplicates("movieId").drop_duplicates("letterboxd_id")
    return pd.Series(mapping["letterboxd_id"].to_numpy(), index=mapping["movieId"].to_numpy())


def aligned(film_ids, keys, matrix):
    """Rows of matrix in film_ids order. Films missing from keys get a zero row."""
    keys = pd.Index(keys)
    position = pd.Series(np.arange(len(keys)), index=keys).reindex(film_ids).fillna(len(keys)).astype(int)
    padded = sparse.vstack([matrix, sparse.csr_matrix((1, matrix.shape[1]))]).tocsr()
    return pd.Series(np.arange(len(film_ids)), index=film_ids), padded[position.to_numpy()]


def genre_features(film_ids, ml_to_lb):
    movies = pd.read_csv(cinematch.MOVIELENS_DATA_DIR / "movies.csv", usecols=["movieId", "genres"])
    movies["film"] = movies["movieId"].map(ml_to_lb)
    movies = movies.dropna(subset=["film"]).drop_duplicates("film")
    genres = normalize(movies["genres"].str.get_dummies(sep="|").to_numpy(np.float64))
    return aligned(film_ids, movies["film"].to_numpy(), sparse.csr_matrix(genres))


def tag_features(film_ids, ml_to_lb):
    tags = pd.read_csv(cinematch.MOVIELENS_DATA_DIR / "tags.csv", usecols=["movieId", "tag"])
    tags["film"] = tags["movieId"].map(ml_to_lb)
    tags = tags.dropna(subset=["film", "tag"])
    tags["tag"] = tags["tag"].astype(str).str.lower().str.strip()
    docs = tags.groupby("film")["tag"].agg(lambda values: "|".join(values))
    vectorizer = TfidfVectorizer(tokenizer=lambda text: text.split("|"), token_pattern=None,
                                 lowercase=False, sublinear_tf=True, min_df=2)
    matrix = normalize(vectorizer.fit_transform(docs.to_numpy()))
    return aligned(film_ids, docs.index.to_numpy(), matrix)


def report(name, pred, data):
    return {"method": name, **score(pred, data), "top-5 liked": top_hit_rate(pred, data)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=int, default=2000, help="users in each of validation and test")
    parser.add_argument("--profile", type=int, nargs="+", default=[15, 30], help="ratings given to the model")
    parser.add_argument("--shrink", type=float, default=0.5)
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

    ml_to_lb = movielens_to_letterboxd(rec)
    content = {"genre": genre_features(film_ids, ml_to_lb), "tag": tag_features(film_ids, ml_to_lb)}
    log(f"Films with at least one tag: {content['tag'][1].getnnz(axis=1).astype(bool).sum():,}")

    variants = {
        "learned blend": (),
        "+ genre": ("genre",),
        "+ tag": ("tag",),
        "+ genre + tag": ("genre", "tag"),
    }
    for profile_size in args.profile:
        val_data = signals(rec, model, val, averages, global_mean, profile_size, args.seed, args.shrink, content)
        test_data = signals(rec, model, test, averages, global_mean, profile_size, args.seed, args.shrink, content)

        rows = [report("item mean", clipped(global_mean + test_data["film"]), test_data)]
        print(f"\n=== Profile of {profile_size} ratings (shrink={args.shrink:g}) ===")
        for name, extra in variants.items():
            weights = fit_weights(val_data, extra)
            print(f"{name:14s} weights: " + "  ".join(f"{v:.3f}" for v in weights))
            pred = clipped(test_data["base"] + design(test_data, extra) @ weights)
            rows.append(report(name, pred, test_data))

        counts = train.groupby("film").size()
        boosted = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, min_samples_leaf=100,
                                                random_state=args.seed)
        boosted.fit(boosted_features(val_data, counts, ("genre", "tag")), val_data["truth"] - val_data["base"])
        pred = clipped(test_data["base"] + boosted.predict(boosted_features(test_data, counts, ("genre", "tag"))))
        rows.append(report("boosted (all signals)", pred, test_data))

        liked = (val_data["truth"] >= LIKED - 1e-9).astype(int)
        classifier = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, min_samples_leaf=100,
                                                    random_state=args.seed)
        classifier.fit(boosted_features(val_data, counts, ("genre", "tag")), liked)
        likelihood = classifier.predict_proba(boosted_features(test_data, counts, ("genre", "tag")))[:, 1]
        rows.append({"method": "liked classifier (rank only)", "RMSE": np.nan, "MAE": np.nan,
                     "rank corr (per user)": np.nan, "top-5 liked": top_hit_rate(likelihood, test_data)})
        print(pd.DataFrame(rows).round(3).to_string(index=False))


def boosted_features(data, counts, extra):
    film_count = counts.reindex(data["hold"]).fillna(0).to_numpy()
    columns = [data["lb"], data["ml"], data["film"], data["lb_mass"], data["ml_mass"],
               np.log1p(film_count), data["base"]]
    return np.column_stack(columns + [data[name] for name in extra])


if __name__ == "__main__":
    main()
