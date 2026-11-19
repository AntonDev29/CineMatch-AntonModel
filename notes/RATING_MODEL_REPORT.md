# CineMatch Rating Model: What We Built and Why

This report explains the rating-prediction model for CineMatch: what it does, how we tested it, what we tried, and why we chose what we chose.

---

## 1. The goal

Users rate films from 1 to 4 stars. The model uses those ratings to recommend films the user is most likely to enjoy.

Two things matter:

1. **Predicting ratings:** given a user's ratings, guess how many stars they would give an unseen film.
2. **Ranking:** show the films most likely to be liked at the top. This is what users actually see, so it matters most.

Everything runs offline first. A change only reaches the iOS app after it has been tested on held-out data.

---

## 2. Data

| Source | What it is | How we use it |
|---|---|---|
| MovieLens (`ratings.csv`, about 22.8 M ratings on films we can map) | Real users rating real films on a 0.5–5 star scale | Training and testing. Ratings are converted to the app's 1–4 scale with `1 + (stars − 0.5) × 2/3`. |
| MovieLens tags (`tags.csv`) | Short user tags such as "heist" or "dark" | Film-to-film similarity (the tag signal) |
| Letterboxd catalogue (in the app index) | Film metadata: cast, crew, keywords, genres | Film-to-film similarity (the Letterboxd signal) |
| `id_mapping.csv` | Links MovieLens films to Letterboxd films | Lets the two sources be combined. 46,534 films map. |

---

## 3. How the model works

The model is a **weighted blend of three signals**. For each film the user has not rated, it:

1. **Finds similar films.** For each signal, it measures how similar the unseen film is to each film the user rated.
2. **Turns similarity into a "lean".** For each signal, it adds up `similarity × (the user's rating − the user's average)`. A film that is similar to films the user loved gets a positive lean. A film similar to films the user disliked gets a negative lean.
3. **Adds a popularity term.** It uses the film's average rating across all users, relative to the overall average.
4. **Combines them with learned weights.**

```
predicted = user's average
          + w_letterboxd × letterboxd_lean
          + w_movielens  × movielens_lean
          + w_tags       × tag_lean
          + w_popularity × film_popularity
          + intercept
(clipped to the 1–4 range)
```

The weights are not hand-picked. They are fitted by least-squares on a separate group of validation users, so we know they generalise.

### The three signals

- **Letterboxd signal:** similarity between films based on Letterboxd metadata (already in the app).
- **MovieLens signal:** similarity from a compressed representation of how MovieLens users rate films together. This is "people who liked X also liked Y."
- **Tag signal:** similarity from the tags MovieLens users gave each film. Films with the same tags look alike.

### Why a blend and not one model?

Each signal alone was worse than the combination. In Step 1 the best single signal was MovieLens (RMSE 0.602) and the blend reached 0.592 at 15 ratings. Each signal covers different films, so combining them helps.

### Why only 10 ratings before personalising?

Below about 10 ratings the personal signal is too thin to beat simple popularity on the top-5 test. The app should show popular, well-rated films until a user has rated 10 films, then switch to the personal blend. The file stores this rule as `personalFromRatings: 10`.

---

## 4. The timeline of what we did

### Step 1: First benchmark (`evaluate_rating_model.py`)

We tested single signals and simple blends on 2,000 held-out users, predicting 30 unseen ratings from a profile of 15 ratings.

| Method | RMSE (lower is better) |
|---|---|
| Global average | 0.702 |
| Film average (ignores the user) | 0.647 |
| User average | 0.645 |
| Letterboxd similarity only | 0.638 |
| MovieLens similarity only | 0.602 |
| Simple blend | 0.592 |

**Conclusion:** both signals help, and combining them is best. Ranking quality (per-user rank correlation) grew with more ratings: 0.407 at 15, 0.414 at 20, 0.417 at 30.

### Step 2: Learned weights (`tune_rating_blend.py`)

Instead of fixed 50/50 weights, we fitted the weights on a separate validation group, then tested on a third group that was never used for fitting. We also checked whether the MovieLens vectors had seen the test users (they had not, to avoid leakage).

| Profile size | Simple blend RMSE | Learned blend RMSE |
|---|---|---|
| 15 | 0.594 | 0.591 |
| 20 | 0.583 | 0.579 |
| 30 | 0.575 | 0.569 |

**Conclusion:** learned weights give a small but consistent gain on unseen users.

We also tried a different smoothing setting (`shrink`). It made no meaningful difference, so we kept 0.5. One fixed set of weights worked well from 15 to 30 ratings, so we did not need separate weights per profile size.

### Step 3: Trying to beat the blend

We tested several other approaches. Results compare against the learned blend.

| Approach | Result | Decision |
|---|---|---|
| **Tag signal** (MovieLens tags) | Small consistent gain. Best linear result at 30 ratings: RMSE 0.565 vs 0.569. | **Kept.** |
| **Genre signal** (MovieLens genres) | No gain | Dropped |
| **Per-user regression on compressed vectors (ridge)** | Lost to the blend on every metric | Dropped |
| **Boosted trees (HistGradientBoosting)** | Best RMSE: 0.578 at 15 ratings, 0.560 at 30 | Not shipped. Gain (about 0.005–0.01 RMSE) does not justify a tree evaluator in Swift and a new file format. Anton chose the linear blend. |
| **Classifier for "will like"** | No better than the regression | Dropped |

### Step 4: Ranking tests (`evaluate_catalogue_ranking.py`)

RMSE measures how close the star predictions are. It does not measure whether the top of the list is good. So we tested ranking directly.

For each test user we ranked the whole 8,000-film catalogue (minus films they had already rated) and checked whether their held-out liked films (4 stars) came near the top.

Metrics (higher is better unless noted):
- **AUC:** chance a liked film is ranked above an unliked one. 0.5 is random, 1.0 is perfect.
- **P@5:** share of the top 5 that the user actually liked.
- **R@20:** share of the user's liked films that appear in the top 20.

| Ratings | Method | RMSE | AUC | P@5 | R@20 |
|---|---|---|---|---|---|
| 3 | Popularity only | 0.638 | 0.847 | 0.056 | 0.099 |
| 3 | Blend + tags | 0.667 | 0.849 | 0.057 | 0.109 |
| 5 | Popularity only | 0.639 | 0.847 | 0.056 | 0.100 |
| 5 | Blend + tags | 0.627 | 0.853 | 0.063 | 0.118 |
| 10 | Popularity only | 0.639 | 0.846 | 0.054 | 0.102 |
| 10 | Blend + tags | 0.590 | 0.853 | 0.069 | 0.124 |
| 30 | Popularity only | 0.633 | 0.842 | 0.045 | 0.100 |
| 30 | Blend + tags | 0.553 | 0.858 | 0.058 | 0.120 |

Random ranking gives AUC 0.5 and P@5 about 0.002.

**Conclusions:**
- Most of the ranking quality comes from popularity. AUC of about 0.85 is reached by showing well-liked films.
- With 3–5 ratings, personalisation does not reliably beat popularity. That is why the app uses popularity until 10 ratings.
- From 10 ratings onward the blend with tags beats popularity on hit rate and recall.
- The plain blend (without tags) predicts stars better but ranks the top 5 slightly worse than popularity at 30 ratings. Tags fixed that.

### Step 5: Export test (`export_rating_model.py`)

We wrote the model as a JSON file, `rating_model_test.json`, the same way the app will read it. We then reloaded the file and scored held-out users with it, so the numbers reflect the file itself.

| Ratings | Popularity RMSE | Model RMSE (exact) | Model RMSE (app, 50 neighbours) | Model rank corr (app) |
|---|---|---|---|---|
| 10 | 0.639 | 0.593 | 0.600 | 0.391 |
| 15 | 0.636 | 0.578 | 0.583 | 0.401 |
| 30 | 0.633 | 0.562 | 0.562 | 0.410 |

"Exact" uses every catalogue film as a neighbour. "App" uses only the 50 most similar films per film, which is what the file stores. The gap is small (0.000–0.007 RMSE).

---

## 5. Decisions and reasons

| Decision | Why |
|---|---|
| Blend of three signals | Each signal alone was worse. The blend was best in every test. |
| Learned weights from validation users | Fixed guesses are worse. Validation keeps the test users clean. |
| Add tags | Small but consistent gain in both RMSE and top-5 hit rate. |
| Drop genres | Added nothing. |
| Drop ridge/matrix-style per-user model | Lost to the blend on all metrics. |
| Do not ship boosted trees | Small gain, but needs a new tree evaluator in Swift and a more complex file. Not worth it yet. |
| Popularity until 10 ratings, then personal blend | Personalisation at 3–5 ratings did not beat popularity reliably. |
| 8,000-film catalogue | Matches the films the app already holds. |
| 50 neighbours per film per signal | Keeps the file at 13 MB and loses little accuracy (0.000–0.007 RMSE). |
| `AUDIENCE_WEIGHT = 0.7` in [cinematch.py](../cinematch.py) | Anton's choice. **Not benchmarked.** It affects the existing mood recommender, not the rating model. |

---

## 6. How good is it?

- **RMSE 0.55–0.60 ≈ 0.85–0.90 stars** of average error on a 4-star scale. This beats the popularity baseline (0.63 ≈ 0.95 stars) by about 0.04–0.08 RMSE at 10–30 ratings.
- **Ranking:** from 10 ratings the blend beats popularity on top-5 hit rate (0.069 vs 0.054) and recall at 20 (0.124 vs 0.102). These gains are modest. Random ranking is far worse, so the signal is real.
- **Honest verdict:** a useful improvement over popularity from about 10 ratings. Not a strong result. More training is unlikely to help much, because the features (not the fitting) limit accuracy.

---

## 7. Limitations and things to be aware of

1. **MovieLens users are not CineMatch users.** The test assumes similar rating habits. Real users may behave differently.
2. **Ranking test counts unrated films as "not liked".** This is the same for every method, so comparisons are fair, but absolute hit rates are understated.
3. **Some choices were made after seeing test results.** The tag signal and the 10-rating cutoff were both chosen after looking at results on the test users. The effect is probably small, but a fresh group of users (or real app data) should confirm it.
4. **Noise.** With 2,000 users, top-5 hit rates vary by about ±0.005. Differences smaller than that should not be read as real.
5. **Not tested on device.** The Swift side has not been built or run. Peter needs to update the app to read format v2 (`tagNeighbors`, the `tag` weight, and the 10-rating rule).
6. **No external benchmark.** [MODEL_TESTING_PLAN.md](./MODEL_TESTING_PLAN.md) has precision targets (≥75% overall, ≥50% "excellent" for 4–5 star films). Those belong to the older mood recommender and use a different measure, so they are not directly comparable. The plan also still refers to `tmdbId`, which we removed.
7. **`AUDIENCE_WEIGHT` change is untested** (see section 5).

---

## 8. Where things are

| File | Purpose |
|---|---|
| [evaluate_rating_model.py](../evaluate_rating_model.py) | Step 1: first benchmark |
| [tune_rating_blend.py](../tune_rating_blend.py) | Step 2: learned weights, shared helpers |
| [evaluate_factor_model.py](../evaluate_factor_model.py) | Ridge test (rejected) |
| [evaluate_content_blend.py](../evaluate_content_blend.py) | Genre, tag, boosted, and classifier tests |
| [evaluate_catalogue_ranking.py](../evaluate_catalogue_ranking.py) | Ranking tests across the catalogue and low-profile sizes |
| [export_rating_model.py](../export_rating_model.py) | Writes the test file |
| [rating_model_test.json](../rating_model_test.json) | Test export (format v2). Not for the app yet. |
| [cinematch_model.json](../cinematch_model.json) | The mood-recommender export Peter is using. **Not changed.** |

---

## 9. Glossary

- **RMSE (root mean squared error):** typical size of the prediction error, in rating points. Lower is better. Multiply by 1.5 for an approximate star count on the 0.5–5 scale.
- **Rank correlation:** how well the predicted order of a user's films matches their real order. 1 is perfect, 0 is random. Higher is better.
- **AUC:** chance a liked film is ranked above an unliked one. 0.5 is random, 1 is perfect.
- **P@5 (precision at 5):** share of the top 5 recommendations the user liked.
- **R@20 (recall at 20):** share of all liked films that appear in the top 20.
- **Popularity:** the film's average rating across all users, relative to the overall average.
- **Shrink:** a smoothing term that stops films with few similar neighbours from getting extreme scores.
