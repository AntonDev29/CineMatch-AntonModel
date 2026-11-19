import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
from scipy import sparse

import cinematch
from movielens import MovieLensAudienceModel, build_movielens_model


class MovieLensRecommendationTests(unittest.TestCase):
    def test_api_prefers_films_liked_by_users_with_similar_ratings(self):
        ratings = sparse.csr_matrix(
            np.array(
                [
                    [5, 5, 1, 1],
                    [5, 5, 1, 1],
                    [5, 5, 1, 1],
                    [5, 5, 1, 1],
                    [1, 1, 5, 5],
                    [1, 1, 5, 5],
                    [1, 1, 5, 5],
                    [1, 1, 5, 5],
                ],
                dtype=np.float32,
            )
        )
        audience = MovieLensAudienceModel.fit(
            ratings, [101, 102, 103, 104], n_components=2, min_ratings=1
        )
        recommender = cinematch.Recommender(
            self.make_index([101, 102, 103, 104]), audience_model=audience
        )
        response = cinematch.create_app(recommender).test_client().post(
            "/api/recommend", json={"liked": [101], "limit": 3}
        )

        self.assertEqual(response.status_code, 200)
        results = response.get_json()
        self.assertEqual(results[0]["id"], 102)
        result_ids = [film["id"] for film in results]
        self.assertNotIn(101, result_ids)
        self.assertEqual(len(result_ids), len(set(result_ids)))
        self.assertIn(
            "MovieLens rating patterns",
            [part["label"] for part in results[0]["breakdown"]],
        )

    def test_unmatched_liked_film_still_uses_content_recommendations(self):
        audience = self.make_audience_model()
        recommender = cinematch.Recommender(
            self.make_index(
                [101, 102, 103, 104, 105, 106],
                keyword_rows=[0, 0, 0, 0, 1, 1],
            ),
            audience_model=audience,
        )
        response = cinematch.create_app(recommender).test_client().post(
            "/api/recommend", json={"liked": [105], "limit": 3}
        )

        self.assertEqual(response.status_code, 200)
        results = response.get_json()
        self.assertEqual(results[0]["id"], 106)

    def test_training_reads_rating_csv_and_applies_the_existing_movie_mapping(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            mapping_path = root / "id_mapping.csv"
            ratings_path = root / "ratings.csv"
            mapping_path.write_text(
                "letterboxd_id,movieId\n101,1\n102,2\n103,3\n104,4\n",
                encoding="utf-8",
            )
            ratings = ["userId,movieId,rating,timestamp"]
            profiles = [[5, 5, 1, 1]] * 4 + [[1, 1, 5, 5]] * 4
            for user_id, profile in enumerate(profiles, start=1):
                ratings.extend(
                    f"{user_id},{movie_id},{rating},0"
                    for movie_id, rating in enumerate(profile, start=1)
                )
                ratings.append(f"{user_id},999,5,0")
            ratings_path.write_text("\n".join(ratings) + "\n", encoding="utf-8")

            audience = build_movielens_model(
                ratings_path,
                mapping_path,
                n_components=2,
                min_ratings=1,
                chunksize=3,
            )
            features = audience.features_for([101, 102, 999])

        self.assertEqual(features.shape, (3, 2))
        self.assertGreater(features[0].nnz, 0)
        self.assertEqual(features[2].nnz, 0)

    @staticmethod
    def make_audience_model():
        ratings = sparse.csr_matrix(
            np.array(
                [
                    [5, 5, 1, 1],
                    [5, 5, 1, 1],
                    [5, 5, 1, 1],
                    [5, 5, 1, 1],
                    [1, 1, 5, 5],
                    [1, 1, 5, 5],
                    [1, 1, 5, 5],
                    [1, 1, 5, 5],
                ],
                dtype=np.float32,
            )
        )
        return MovieLensAudienceModel.fit(
            ratings, [101, 102, 103, 104], n_components=2, min_ratings=1
        )

    @staticmethod
    def make_index(film_ids, keyword_rows=None):
        meta = pd.DataFrame(
            {
                "id": film_ids,
                "name": [f"Film {film_id}" for film_id in film_ids],
                "key": [f"film {film_id}" for film_id in film_ids],
                "year": [2000] * len(film_ids),
                "rating": [3.5] * len(film_ids),
                "minute": [100] * len(film_ids),
                "genres": ["Drama"] * len(film_ids),
                "director": [""] * len(film_ids),
                "cast": [""] * len(film_ids),
                "tagline": [""] * len(film_ids),
                "description": [""] * len(film_ids),
                "popularity": [0.0] * len(film_ids),
            }
        )
        blocks = {
            name: sparse.csr_matrix((len(film_ids), 0), dtype=np.float32)
            for name in cinematch.BLOCK_LABELS
            if name != "audience"
        }
        if keyword_rows is not None:
            blocks["keywords"] = sparse.csr_matrix(
                np.asarray(keyword_rows, dtype=np.float32).reshape(-1, 1)
            )
        vocab = {name: [] for name in blocks}
        if blocks["keywords"].shape[1]:
            vocab["keywords"] = ["adventure"]
        return {"meta": meta, "blocks": blocks, "vocab": vocab}


if __name__ == "__main__":
    unittest.main()
