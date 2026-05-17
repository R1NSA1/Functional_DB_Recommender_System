from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import psycopg
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler


DEFAULT_DATABASE_URL = "postgresql://postgres:1234@127.0.0.1:5433/recsys_lab5"
RANDOM_STATE = 42
SVD_PARAMS = {
    "n_factors": 80,
    "n_epochs": 25,
    "lr_all": 0.005,
    "reg_all": 0.04,
    "random_state": RANDOM_STATE,
}


def connect(database_url: str = DEFAULT_DATABASE_URL) -> psycopg.Connection:
    return psycopg.connect(database_url)


def query_df(con: psycopg.Connection, query: str, params: tuple[Any, ...] | None = None) -> pd.DataFrame:
    with con.cursor() as cur:
        cur.execute(query, params or ())
        rows = cur.fetchall()
        columns = [column.name for column in cur.description]
    return pd.DataFrame(rows, columns=columns)


def load_movies(con: psycopg.Connection) -> pd.DataFrame:
    query = """
        SELECT
            m.movie_id,
            m.title,
            m.release_date,
            m.vote_average,
            m.vote_count,
            m.popularity,
            cf.feature_text
        FROM movies m
        JOIN content_features cf ON cf.movie_id = m.movie_id
        WHERE cf.feature_text IS NOT NULL AND cf.feature_text <> ''
        ORDER BY m.movie_id
    """
    return query_df(con, query)


def load_ratings(
    con: psycopg.Connection,
    max_users: int = 5_000,
    min_user_ratings: int = 20,
    include_user_id: int | None = None,
) -> pd.DataFrame:
    query = """
        WITH active_users AS (
            SELECT user_id
            FROM ratings
            GROUP BY user_id
            HAVING COUNT(*) >= %s
            ORDER BY md5(user_id::text)
            LIMIT %s
        ),
        selected_users AS (
            SELECT user_id FROM active_users
            UNION
            SELECT %s::integer AS user_id
            WHERE %s IS NOT NULL
        )
        SELECT r.user_id, r.movie_id, r.rating
        FROM ratings r
        JOIN selected_users su ON su.user_id = r.user_id
        ORDER BY r.user_id, r.movie_id
    """
    return query_df(con, query, params=(min_user_ratings, max_users, include_user_id, include_user_id))


def load_popular_candidates(con: psycopg.Connection, min_ratings: int = 20) -> pd.DataFrame:
    query = """
        SELECT
            m.movie_id,
            m.title,
            COUNT(r.rating) AS rating_count,
            AVG(r.rating) AS avg_rating
        FROM movies m
        JOIN ratings r ON r.movie_id = m.movie_id
        GROUP BY m.movie_id, m.title
        HAVING COUNT(r.rating) >= %s
        ORDER BY rating_count DESC
    """
    return query_df(con, query, params=(min_ratings,))


def add_year(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["year"] = pd.to_datetime(result["release_date"], errors="coerce").dt.year
    return result


def remove_hidden_ratings(ratings: pd.DataFrame, hidden_pairs: set[tuple[int, int]]) -> pd.DataFrame:
    if not hidden_pairs:
        return ratings.copy()

    hidden_df = pd.DataFrame(hidden_pairs, columns=["user_id", "movie_id"])
    merged = ratings.merge(hidden_df.assign(_hidden=True), on=["user_id", "movie_id"], how="left")
    return merged[merged["_hidden"].isna()].drop(columns="_hidden").copy()


@dataclass
class ContentBasedRecommender:
    movies: pd.DataFrame
    vectorizer: TfidfVectorizer
    tfidf_matrix: Any
    movie_indices: pd.Series

    @classmethod
    def fit(cls, movies: pd.DataFrame) -> "ContentBasedRecommender":
        movies = add_year(movies).reset_index(drop=True)
        vectorizer = TfidfVectorizer(stop_words="english", min_df=2, max_features=25_000)
        tfidf_matrix = vectorizer.fit_transform(movies["feature_text"].fillna(""))
        movie_indices = pd.Series(movies.index, index=movies["movie_id"])
        return cls(movies=movies, vectorizer=vectorizer, tfidf_matrix=tfidf_matrix, movie_indices=movie_indices)

    def similar_movies(self, movie_id: int, top_n: int = 10) -> pd.DataFrame:
        if movie_id not in self.movie_indices.index:
            return pd.DataFrame()

        row_index = int(self.movie_indices.loc[movie_id])
        scores = cosine_similarity(self.tfidf_matrix[row_index], self.tfidf_matrix).ravel()
        candidate_indices = np.argsort(scores)[::-1]
        candidate_indices = [idx for idx in candidate_indices if idx != row_index][:top_n]

        result = self.movies.iloc[candidate_indices].copy()
        result["content_score"] = scores[candidate_indices]
        return result[
            ["movie_id", "title", "year", "vote_average", "vote_count", "content_score"]
        ].reset_index(drop=True)

    def user_profile_scores(self, liked_movie_ids: list[int]) -> pd.Series:
        indices = [
            int(self.movie_indices.loc[movie_id])
            for movie_id in liked_movie_ids
            if movie_id in self.movie_indices.index
        ]
        if not indices:
            return pd.Series(dtype=float)

        profile_vector = np.asarray(self.tfidf_matrix[indices].mean(axis=0))
        scores = cosine_similarity(profile_vector, self.tfidf_matrix).ravel()
        return pd.Series(scores, index=self.movies["movie_id"].astype(int))

    def recommend_for_liked_movies(
        self,
        liked_movie_ids: list[int],
        excluded_movie_ids: set[int] | None = None,
        top_n: int = 10,
    ) -> pd.DataFrame:
        excluded_movie_ids = excluded_movie_ids or set(liked_movie_ids)
        scores = self.user_profile_scores(liked_movie_ids)
        if scores.empty:
            return pd.DataFrame()

        result = self.movies.copy()
        result["content_score"] = result["movie_id"].map(scores)
        result = result[~result["movie_id"].isin(excluded_movie_ids)]
        return result.sort_values("content_score", ascending=False).head(top_n)[
            ["movie_id", "title", "year", "vote_average", "vote_count", "content_score"]
        ].reset_index(drop=True)


@dataclass
class CollaborativeRecommender:
    ratings: pd.DataFrame
    model: Any

    @classmethod
    def fit(cls, ratings: pd.DataFrame) -> "CollaborativeRecommender":
        from surprise import Dataset, Reader, SVD

        reader = Reader(rating_scale=(0.5, 5.0))
        data = Dataset.load_from_df(ratings[["user_id", "movie_id", "rating"]], reader)
        trainset = data.build_full_trainset()
        model = SVD(**SVD_PARAMS)
        model.fit(trainset)
        return cls(ratings=ratings.copy(), model=model)

    @staticmethod
    def evaluate(ratings: pd.DataFrame) -> dict[str, float]:
        from surprise import Dataset, Reader, SVD
        from surprise.model_selection import KFold, cross_validate

        reader = Reader(rating_scale=(0.5, 5.0))
        data = Dataset.load_from_df(ratings[["user_id", "movie_id", "rating"]], reader)
        splitter = KFold(n_splits=5, random_state=RANDOM_STATE, shuffle=True)
        scores = cross_validate(SVD(**SVD_PARAMS), data, measures=["RMSE", "MAE"], cv=splitter, verbose=False)
        return {
            "rmse_mean": float(np.mean(scores["test_rmse"])),
            "rmse_std": float(np.std(scores["test_rmse"])),
            "mae_mean": float(np.mean(scores["test_mae"])),
            "mae_std": float(np.std(scores["test_mae"])),
            "folds": 5.0,
        }

    def recommend_for_user(
        self,
        user_id: int,
        movies: pd.DataFrame,
        candidates: pd.DataFrame,
        top_n: int = 10,
    ) -> pd.DataFrame:
        rated_ids = set(self.ratings.loc[self.ratings["user_id"] == user_id, "movie_id"].astype(int))
        candidate_ids = [int(movie_id) for movie_id in candidates["movie_id"] if int(movie_id) not in rated_ids]
        predictions = [(movie_id, self.model.predict(user_id, movie_id).est) for movie_id in candidate_ids]
        pred_df = pd.DataFrame(predictions, columns=["movie_id", "predicted_rating"])
        result = pred_df.merge(add_year(movies), on="movie_id", how="left")
        return result.sort_values("predicted_rating", ascending=False).head(top_n)[
            ["movie_id", "title", "year", "vote_average", "vote_count", "predicted_rating"]
        ].reset_index(drop=True)


@dataclass
class HybridRecommender:
    content: ContentBasedRecommender
    collaborative: CollaborativeRecommender
    alpha: float = 0.8

    def recommend_for_user(
        self,
        user_id: int,
        movies: pd.DataFrame,
        candidates: pd.DataFrame,
        top_n: int = 10,
    ) -> pd.DataFrame:
        user_ratings = self.collaborative.ratings[self.collaborative.ratings["user_id"] == user_id]
        rated_ids = set(user_ratings["movie_id"].astype(int))
        liked_ids = user_ratings.loc[user_ratings["rating"] >= 4.0, "movie_id"].astype(int).tolist()
        content_scores = self.content.user_profile_scores(liked_ids)

        rows = []
        for movie_id in candidates["movie_id"].astype(int):
            if movie_id in rated_ids:
                continue
            rows.append(
                {
                    "movie_id": movie_id,
                    "predicted_rating": self.collaborative.model.predict(user_id, movie_id).est,
                    "content_score": float(content_scores.get(movie_id, 0.0)),
                }
            )

        score_df = pd.DataFrame(rows)
        if score_df.empty:
            return pd.DataFrame()

        scaler = MinMaxScaler()
        score_df[["cf_norm", "content_norm"]] = scaler.fit_transform(score_df[["predicted_rating", "content_score"]])
        score_df["hybrid_score"] = self.alpha * score_df["cf_norm"] + (1 - self.alpha) * score_df["content_norm"]
        result = score_df.merge(add_year(movies), on="movie_id", how="left")
        return result.sort_values("hybrid_score", ascending=False).head(top_n)[
            [
                "movie_id",
                "title",
                "year",
                "vote_average",
                "vote_count",
                "predicted_rating",
                "content_score",
                "hybrid_score",
            ]
        ].reset_index(drop=True)


def evaluate_profile_recommender(
    content: ContentBasedRecommender,
    ratings: pd.DataFrame,
    recommender: HybridRecommender | None = None,
    movies: pd.DataFrame | None = None,
    candidates: pd.DataFrame | None = None,
    sample_users: int = 50,
    top_n: int = 10,
) -> dict[str, float]:
    eligible = []
    for user_id, group in ratings.groupby("user_id"):
        liked = group.loc[group["rating"] >= 4.0, "movie_id"].astype(int).tolist()
        if len(group) >= 10 and len(liked) >= 2:
            eligible.append((int(user_id), liked))

    rng = np.random.default_rng(42)
    selected = rng.choice(len(eligible), size=min(sample_users, len(eligible)), replace=False)
    selected_cases = []
    for index in selected:
        user_id, liked = eligible[int(index)]
        hidden_movie_id = int(rng.choice(liked))
        profile_ids = [movie_id for movie_id in liked if movie_id != hidden_movie_id]
        selected_cases.append((user_id, hidden_movie_id, profile_ids))

    if recommender is not None:
        hidden_pairs = {(user_id, hidden_movie_id) for user_id, hidden_movie_id, _profile_ids in selected_cases}
        train_ratings = remove_hidden_ratings(ratings, hidden_pairs)
        eval_collaborative = CollaborativeRecommender.fit(train_ratings)
        eval_recommender = HybridRecommender(content, eval_collaborative, alpha=recommender.alpha)
    else:
        eval_recommender = None

    hits = 0
    evaluated = 0

    for user_id, hidden_movie_id, profile_ids in selected_cases:
        if eval_recommender is None:
            recs = content.recommend_for_liked_movies(profile_ids, excluded_movie_ids=set(profile_ids), top_n=top_n)
        else:
            assert movies is not None and candidates is not None
            recs = eval_recommender.recommend_for_user(user_id, movies, candidates, top_n=top_n)
        if recs.empty:
            continue
        evaluated += 1
        hits += int(hidden_movie_id in set(recs["movie_id"].astype(int)))

    return {
        f"hit_rate_at_{top_n}": hits / evaluated if evaluated else 0.0,
        "evaluated_users": float(evaluated),
    }


def _ndcg_for_rank(rank: int | None) -> float:
    if rank is None:
        return 0.0
    return 1.0 / np.log2(rank + 1)


def evaluate_sampled_topn(
    content: ContentBasedRecommender,
    collaborative: CollaborativeRecommender,
    ratings: pd.DataFrame,
    candidates: pd.DataFrame,
    sample_users: int = 100,
    negative_samples: int = 100,
    top_n: int = 10,
    alpha: float = 0.8,
) -> dict[str, dict[str, float]]:
    eligible = []
    candidate_ids = set(candidates["movie_id"].astype(int))
    all_candidate_ids = np.array(sorted(candidate_ids))

    for user_id, group in ratings.groupby("user_id"):
        liked = [
            movie_id
            for movie_id in group.loc[group["rating"] >= 4.0, "movie_id"].astype(int)
            if movie_id in candidate_ids
        ]
        if len(group) >= 10 and len(liked) >= 2:
            eligible.append((int(user_id), liked, set(group["movie_id"].astype(int))))

    rng = np.random.default_rng(42)
    selected = rng.choice(len(eligible), size=min(sample_users, len(eligible)), replace=False)
    selected_cases = []
    for index in selected:
        user_id, liked, rated_ids = eligible[int(index)]
        hidden_movie_id = int(rng.choice(liked))
        profile_ids = [movie_id for movie_id in liked if movie_id != hidden_movie_id]
        negative_pool = [
            movie_id
            for movie_id in all_candidate_ids
            if movie_id not in rated_ids and movie_id != hidden_movie_id
        ]
        if len(negative_pool) < negative_samples:
            sampled_negatives = negative_pool
        else:
            sampled_negatives = rng.choice(negative_pool, size=negative_samples, replace=False).astype(int).tolist()
        eval_ids = sampled_negatives + [hidden_movie_id]
        selected_cases.append((user_id, hidden_movie_id, profile_ids, eval_ids))

    hidden_pairs = {
        (user_id, hidden_movie_id)
        for user_id, hidden_movie_id, _profile_ids, _eval_ids in selected_cases
    }
    train_ratings = remove_hidden_ratings(ratings, hidden_pairs)
    eval_collaborative = CollaborativeRecommender.fit(train_ratings)

    metrics = {
        "content_based": {"hits": 0.0, "ndcg": 0.0, "evaluated": 0.0},
        "collaborative": {"hits": 0.0, "ndcg": 0.0, "evaluated": 0.0},
        "hybrid": {"hits": 0.0, "ndcg": 0.0, "evaluated": 0.0},
    }

    for user_id, hidden_movie_id, profile_ids, eval_ids in selected_cases:
        content_series = content.user_profile_scores(profile_ids)
        if content_series.empty:
            continue

        rows = []
        for movie_id in eval_ids:
            rows.append(
                {
                    "movie_id": int(movie_id),
                    "content_score": float(content_series.get(int(movie_id), 0.0)),
                    "predicted_rating": eval_collaborative.model.predict(user_id, int(movie_id)).est,
                }
            )
        score_df = pd.DataFrame(rows)
        if score_df.empty:
            continue

        score_df[["cf_norm", "content_norm"]] = MinMaxScaler().fit_transform(
            score_df[["predicted_rating", "content_score"]]
        )
        score_df["hybrid_score"] = alpha * score_df["cf_norm"] + (1 - alpha) * score_df["content_norm"]

        rankings = {
            "content_based": score_df.sort_values("content_score", ascending=False)["movie_id"].astype(int).tolist(),
            "collaborative": score_df.sort_values("predicted_rating", ascending=False)["movie_id"].astype(int).tolist(),
            "hybrid": score_df.sort_values("hybrid_score", ascending=False)["movie_id"].astype(int).tolist(),
        }

        for method, ranked_ids in rankings.items():
            metrics[method]["evaluated"] += 1
            try:
                rank = ranked_ids.index(hidden_movie_id) + 1
            except ValueError:
                rank = None
            hit = rank is not None and rank <= top_n
            metrics[method]["hits"] += float(hit)
            metrics[method]["ndcg"] += _ndcg_for_rank(rank if hit else None)

    result: dict[str, dict[str, float]] = {}
    for method, values in metrics.items():
        evaluated = values["evaluated"] or 1.0
        result[method] = {
            f"hit_rate_at_{top_n}": values["hits"] / evaluated,
            f"precision_at_{top_n}": values["hits"] / evaluated / top_n,
            f"recall_at_{top_n}": values["hits"] / evaluated,
            f"ndcg_at_{top_n}": values["ndcg"] / evaluated,
            "evaluated_users": values["evaluated"],
            "negative_samples": float(negative_samples),
        }
    return result


def build_demo(
    database_url: str,
    user_id: int,
    seed_movie_id: int,
    top_n: int,
    max_users: int = 5_000,
) -> dict[str, Any]:
    with connect(database_url) as con:
        movies = load_movies(con)
        ratings = load_ratings(con, max_users=max_users, include_user_id=user_id)
        candidates = load_popular_candidates(con, min_ratings=20)

    content = ContentBasedRecommender.fit(movies)
    collaborative_metrics = CollaborativeRecommender.evaluate(ratings)
    collaborative = CollaborativeRecommender.fit(ratings)
    hybrid = HybridRecommender(content, collaborative, alpha=0.8)

    content_recs = content.similar_movies(seed_movie_id, top_n=top_n)
    collaborative_recs = collaborative.recommend_for_user(user_id, movies, candidates, top_n=top_n)
    hybrid_recs = hybrid.recommend_for_user(user_id, movies, candidates, top_n=top_n)
    content_metrics = evaluate_profile_recommender(content, ratings, top_n=top_n)
    hybrid_metrics = evaluate_profile_recommender(
        content,
        ratings,
        recommender=hybrid,
        movies=movies,
        candidates=candidates,
        top_n=top_n,
    )
    sampled_topn_metrics = evaluate_sampled_topn(
        content,
        collaborative,
        ratings,
        candidates,
        sample_users=100,
        negative_samples=100,
        top_n=top_n,
        alpha=hybrid.alpha,
    )

    return {
        "dataset": {
            "movies": int(len(movies)),
            "ratings": int(len(ratings)),
            "users": int(ratings["user_id"].nunique()),
            "candidates_with_20_ratings": int(len(candidates)),
            "rating_sample_max_users": int(max_users),
        },
        "parameters": {"user_id": user_id, "seed_movie_id": seed_movie_id, "top_n": top_n},
        "metrics": {
            "collaborative": collaborative_metrics,
            "full_catalog_content_based": content_metrics,
            "full_catalog_hybrid": hybrid_metrics,
            "sampled_topn": sampled_topn_metrics,
        },
        "recommendations": {
            "content_based": content_recs.to_dict(orient="records"),
            "collaborative": collaborative_recs.to_dict(orient="records"),
            "hybrid": hybrid_recs.to_dict(orient="records"),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Lab 5 recommendation demos.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    parser.add_argument("--user-id", type=int, default=15)
    parser.add_argument("--seed-movie-id", type=int, default=318)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--max-users", type=int, default=5_000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_demo(args.database_url, args.user_id, args.seed_movie_id, args.top_n, args.max_users)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
