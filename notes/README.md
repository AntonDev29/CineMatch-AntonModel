# CineMatch

A "films like the ones you like" recommender that combines Letterboxd film
features with patterns learned from MovieLens ratings.

## Run it

```powershell
.\.conda\python.exe .\cinematch.py build-movielens
.\.conda\python.exe .\cinematch.py serve
```

Build the MovieLens audience model once, then open http://127.0.0.1:5000,
search for films you like, and add them. The first app run builds the Letterboxd
index (about 35 seconds); later starts load it in a few seconds.

Terminal version: `.\.conda\python.exe .\cinematch.py recommend "Inception" "Heat (1995)"`
Rebuild after changing weights or data: `.\.conda\python.exe .\cinematch.py build`

## How it works

- **Catalog:** the ~91K Letterboxd films that have a Letterboxd rating. These are
  the films people actually watch and have descriptions and posters.
- **Film vector:** weighted blocks for description + tagline keywords (TF-IDF with
  bigrams), themes, genres, top-10 cast, director, writer, composer,
  cinematography, editor, producer, studios, countries, languages and decade.
  Rarer shared features count for more (idf), so sharing an uncommon actor or
  theme matters more than sharing the genre "Drama".
- **Weights:** `WEIGHTS` in `cinematch.py` sets the content block weights;
  `AUDIENCE_WEIGHT` controls the MovieLens block. Content weights were tuned by
  eye; the audience features are learned from ratings.
- **Recommending:** cosine similarity between your liked films and every film.
  The score mixes the average similarity (fits all your films) with the best
  single match (fits at least one), plus a tiny boost for the Letterboxd rating
  and how widely a film was released. The MovieLens block captures films that
  tend to be rated similarly by the same people; the existing genres, themes,
  cast and story features help with unmapped films and explain matches.
- **The % match:** it is a combined similarity score, not a prediction
  probability. The "Why?" button breaks down the content and MovieLens
  contributions, plus similarity to each film you liked.
- **Limits:** MovieLens has 32,000,204 ratings from 200,948 anonymous users and
  includes no demographic profiles. The model learns crowd-level patterns; it
  cannot know an individual new user's preferences with certainty. Films
  without a Letterboxd rating are not in the catalog, and films without a
  MovieLens mapping rely on content features.
- **Dataset terms:** the included MovieLens README prohibits commercial or
  revenue-bearing use without permission from GroupLens. Use this model
  non-commercially unless you obtain permission.

## Files

- `cinematch.py` - index build, recommender, web server, command line
- `movielens.py` - MovieLens model training and loading
- `web/index.html` - the app page
- `index/` - generated indices and the MovieLens audience model
- `Letterboxd_Movies_Data/` - source data and posters
- `Movielens_Data/` - MovieLens ratings and movie data used to train the model
- `archive_movielens_merge/` - Letterboxd-MovieLens ID mapping used by training
