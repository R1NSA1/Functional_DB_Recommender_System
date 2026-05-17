from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import psycopg


ROOT = Path(__file__).resolve().parents[2]
LAB_DIR = ROOT / "Lab_5"
DATA_DIR = LAB_DIR / "datasets"
SCHEMA_PATH = LAB_DIR / "task_2" / "schema_postgres.sql"
DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/recsys_lab5"


DROP_TABLES = [
    "ratings",
    "users",
    "content_features",
    "movie_spoken_languages",
    "spoken_languages",
    "movie_production_countries",
    "production_countries",
    "movie_production_companies",
    "production_companies",
    "movie_crew",
    "movie_cast",
    "people",
    "movie_keywords",
    "keywords",
    "movie_genres",
    "genres",
    "movies",
    "collections",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load Lab 5 CSV files into PostgreSQL.")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
        help="PostgreSQL connection URL. Can also be set via DATABASE_URL.",
    )
    parser.add_argument(
        "--ratings",
        choices=["small", "full"],
        default="small",
        help="Use ratings_small.csv for development or ratings.csv for full import.",
    )
    parser.add_argument(
        "--links",
        choices=["small", "full"],
        default="small",
        help="Use links_small.csv or links.csv for MovieLens/TMDB mapping.",
    )
    parser.add_argument("--recreate", action="store_true", help="Drop and recreate Lab 5 tables.")
    return parser.parse_args()


def connect(database_url: str) -> psycopg.Connection:
    con = psycopg.connect(database_url)
    con.execute("SET timezone = 'UTC'")
    return con


def reset_database(con: psycopg.Connection) -> None:
    with con.cursor() as cur:
        for table in DROP_TABLES:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


def apply_schema(con: psycopg.Connection) -> None:
    with con.cursor() as cur:
        for statement in SCHEMA_PATH.read_text(encoding="utf-8").split(";"):
            statement = statement.strip()
            if statement:
                cur.execute(statement)


def safe_int(value: Any) -> int | None:
    if pd.isna(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> float | None:
    if pd.isna(value) or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def safe_text(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def safe_date(value: Any) -> str | None:
    if pd.isna(value) or value == "":
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def parse_literal(value: Any) -> Any:
    if pd.isna(value) or value == "":
        return None
    if isinstance(value, (list, dict)):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return ast.literal_eval(text)
    except (SyntaxError, ValueError):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None


def parse_list(value: Any) -> list[dict[str, Any]]:
    parsed = parse_literal(value)
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return []


def parse_dict(value: Any) -> dict[str, Any] | None:
    parsed = parse_literal(value)
    return parsed if isinstance(parsed, dict) else None


def insert_many(con: psycopg.Connection, sql: str, rows: Iterable[tuple[Any, ...]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    with con.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


def load_source_frames(links_kind: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    movies = pd.read_csv(DATA_DIR / "movies_metadata.csv", low_memory=False)
    links_name = "links_small.csv" if links_kind == "small" else "links.csv"
    links = pd.read_csv(DATA_DIR / links_name)
    keywords = pd.read_csv(DATA_DIR / "keywords.csv")
    credits = pd.read_csv(DATA_DIR / "credits.csv")

    movies["tmdb_id"] = pd.to_numeric(movies["id"], errors="coerce").astype("Int64")
    links["tmdb_id"] = pd.to_numeric(links["tmdbId"], errors="coerce").astype("Int64")
    links["movie_id"] = pd.to_numeric(links["movieId"], errors="coerce").astype("Int64")
    keywords["tmdb_id"] = pd.to_numeric(keywords["id"], errors="coerce").astype("Int64")
    credits["tmdb_id"] = pd.to_numeric(credits["id"], errors="coerce").astype("Int64")

    movies = movies.dropna(subset=["tmdb_id"])
    links = links.dropna(subset=["tmdb_id", "movie_id"])
    keywords = keywords.dropna(subset=["tmdb_id"])
    credits = credits.dropna(subset=["tmdb_id"])
    return movies, links, keywords, credits


def build_movie_frame(movies: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    merged = links.merge(movies, on="tmdb_id", how="inner")
    return merged.drop_duplicates(subset=["movie_id"])


def load_collections(con: psycopg.Connection, movies: pd.DataFrame) -> int:
    rows: dict[int, tuple[Any, ...]] = {}
    for value in movies["belongs_to_collection"]:
        collection = parse_dict(value)
        if not collection:
            continue
        collection_id = safe_int(collection.get("id"))
        if collection_id is None:
            continue
        rows[collection_id] = (
            collection_id,
            safe_text(collection.get("name")),
            safe_text(collection.get("poster_path")),
            safe_text(collection.get("backdrop_path")),
        )
    return insert_many(
        con,
        """
        INSERT INTO collections (collection_id, name, poster_path, backdrop_path)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (collection_id) DO NOTHING
        """,
        rows.values(),
    )


def load_movies(con: psycopg.Connection, movies: pd.DataFrame) -> int:
    rows = []
    for row in movies.itertuples(index=False):
        collection = parse_dict(getattr(row, "belongs_to_collection"))
        collection_id = safe_int(collection.get("id")) if collection else None
        rows.append(
            (
                safe_int(row.movie_id),
                safe_int(row.tmdb_id),
                safe_text(getattr(row, "imdb_id")),
                safe_text(getattr(row, "title")) or safe_text(getattr(row, "original_title")),
                safe_text(getattr(row, "original_title")),
                safe_text(getattr(row, "overview")),
                safe_text(getattr(row, "original_language")),
                safe_date(getattr(row, "release_date")),
                safe_float(getattr(row, "runtime")),
                safe_int(getattr(row, "budget")),
                safe_int(getattr(row, "revenue")),
                safe_float(getattr(row, "popularity")),
                safe_float(getattr(row, "vote_average")),
                safe_int(getattr(row, "vote_count")),
                safe_bool(getattr(row, "adult")),
                safe_bool(getattr(row, "video")),
                safe_text(getattr(row, "status")),
                safe_text(getattr(row, "homepage")),
                safe_text(getattr(row, "poster_path")),
                safe_text(getattr(row, "tagline")),
                collection_id,
            )
        )
    return insert_many(
        con,
        """
        INSERT INTO movies (
            movie_id, tmdb_id, imdb_id, title, original_title, overview, original_language,
            release_date, runtime, budget, revenue, popularity, vote_average, vote_count,
            adult, video, status, homepage, poster_path, tagline, collection_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (movie_id) DO UPDATE SET
            tmdb_id = EXCLUDED.tmdb_id,
            imdb_id = EXCLUDED.imdb_id,
            title = EXCLUDED.title,
            overview = EXCLUDED.overview
        """,
        rows,
    )


def load_named_relations(
    con: psycopg.Connection,
    movies: pd.DataFrame,
    source_column: str,
    entity_table: str,
    entity_id_column: str,
    entity_name_column: str,
    relation_table: str,
) -> tuple[int, int]:
    entities: dict[int, tuple[Any, ...]] = {}
    relations: set[tuple[int, int]] = set()
    for row in movies[["movie_id", source_column]].itertuples(index=False):
        movie_id = safe_int(row.movie_id)
        if movie_id is None:
            continue
        for item in parse_list(getattr(row, source_column)):
            entity_id = safe_int(item.get("id"))
            name = safe_text(item.get("name"))
            if entity_id is None or not name:
                continue
            entities[entity_id] = (entity_id, name)
            relations.add((movie_id, entity_id))

    entity_count = insert_many(
        con,
        f"""
        INSERT INTO {entity_table} ({entity_id_column}, {entity_name_column})
        VALUES (%s, %s)
        ON CONFLICT ({entity_id_column}) DO NOTHING
        """,
        entities.values(),
    )
    relation_count = insert_many(
        con,
        f"""
        INSERT INTO {relation_table} (movie_id, {entity_id_column})
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        """,
        relations,
    )
    return entity_count, relation_count


def load_keywords(con: psycopg.Connection, movies: pd.DataFrame, keywords: pd.DataFrame) -> tuple[int, int]:
    source = movies[["movie_id", "tmdb_id"]].merge(keywords[["tmdb_id", "keywords"]], on="tmdb_id", how="inner")
    return load_named_relations(con, source, "keywords", "keywords", "keyword_id", "name", "movie_keywords")


def load_people_and_credits(
    con: psycopg.Connection, movies: pd.DataFrame, credits: pd.DataFrame
) -> tuple[int, int, int]:
    source = movies[["movie_id", "tmdb_id"]].merge(credits[["tmdb_id", "cast", "crew"]], on="tmdb_id", how="inner")
    people: dict[int, tuple[Any, ...]] = {}
    cast_rows: set[tuple[Any, ...]] = set()
    crew_rows: set[tuple[Any, ...]] = set()

    for row in source.itertuples(index=False):
        movie_id = safe_int(row.movie_id)
        if movie_id is None:
            continue
        for item in parse_list(row.cast):
            person_id = safe_int(item.get("id"))
            name = safe_text(item.get("name"))
            if person_id is None or not name:
                continue
            people[person_id] = (person_id, name, safe_int(item.get("gender")))
            cast_rows.add((movie_id, person_id, safe_text(item.get("character")), safe_int(item.get("order"))))

        for item in parse_list(row.crew):
            person_id = safe_int(item.get("id"))
            name = safe_text(item.get("name"))
            if person_id is None or not name:
                continue
            people[person_id] = (person_id, name, safe_int(item.get("gender")))
            crew_rows.add((movie_id, person_id, safe_text(item.get("department")), safe_text(item.get("job"))))

    people_count = insert_many(
        con,
        """
        INSERT INTO people (person_id, name, gender)
        VALUES (%s, %s, %s)
        ON CONFLICT (person_id) DO NOTHING
        """,
        people.values(),
    )
    cast_count = insert_many(
        con,
        """
        INSERT INTO movie_cast (movie_id, person_id, character_name, cast_order)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        cast_rows,
    )
    crew_count = insert_many(
        con,
        """
        INSERT INTO movie_crew (movie_id, person_id, department, job)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        crew_rows,
    )
    return people_count, cast_count, crew_count


def load_production_companies(con: psycopg.Connection, movies: pd.DataFrame) -> tuple[int, int]:
    companies: dict[int, tuple[Any, ...]] = {}
    relations: set[tuple[int, int]] = set()
    for row in movies[["movie_id", "production_companies"]].itertuples(index=False):
        movie_id = safe_int(row.movie_id)
        if movie_id is None:
            continue
        for item in parse_list(row.production_companies):
            company_id = safe_int(item.get("id"))
            name = safe_text(item.get("name"))
            if company_id is None or not name:
                continue
            companies[company_id] = (company_id, name)
            relations.add((movie_id, company_id))
    return (
        insert_many(
            con,
            """
            INSERT INTO production_companies (company_id, name)
            VALUES (%s, %s)
            ON CONFLICT (company_id) DO NOTHING
            """,
            companies.values(),
        ),
        insert_many(
            con,
            """
            INSERT INTO movie_production_companies (movie_id, company_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            relations,
        ),
    )


def load_countries_and_languages(con: psycopg.Connection, movies: pd.DataFrame) -> tuple[int, int, int, int]:
    countries: dict[str, tuple[str, str]] = {}
    movie_countries: set[tuple[int, str]] = set()
    languages: dict[str, tuple[str, str]] = {}
    movie_languages: set[tuple[int, str]] = set()

    for row in movies[["movie_id", "production_countries", "spoken_languages"]].itertuples(index=False):
        movie_id = safe_int(row.movie_id)
        if movie_id is None:
            continue
        for item in parse_list(row.production_countries):
            code = safe_text(item.get("iso_3166_1"))
            name = safe_text(item.get("name"))
            if code and name:
                countries[code] = (code, name)
                movie_countries.add((movie_id, code))
        for item in parse_list(row.spoken_languages):
            code = safe_text(item.get("iso_639_1"))
            name = safe_text(item.get("name"))
            if code and name:
                languages[code] = (code, name)
                movie_languages.add((movie_id, code))

    return (
        insert_many(
            con,
            """
            INSERT INTO production_countries (country_code, name)
            VALUES (%s, %s)
            ON CONFLICT (country_code) DO NOTHING
            """,
            countries.values(),
        ),
        insert_many(
            con,
            """
            INSERT INTO movie_production_countries (movie_id, country_code)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            movie_countries,
        ),
        insert_many(
            con,
            """
            INSERT INTO spoken_languages (language_code, name)
            VALUES (%s, %s)
            ON CONFLICT (language_code) DO NOTHING
            """,
            languages.values(),
        ),
        insert_many(
            con,
            """
            INSERT INTO movie_spoken_languages (movie_id, language_code)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            movie_languages,
        ),
    )


def load_content_features(
    con: psycopg.Connection, movies: pd.DataFrame, keywords: pd.DataFrame, credits: pd.DataFrame
) -> int:
    keyword_map: dict[int | None, str] = {}
    for row in keywords.itertuples(index=False):
        names = [item["name"] for item in parse_list(row.keywords) if item.get("name")]
        keyword_map[safe_int(row.tmdb_id)] = " ".join(names)

    credit_map: dict[int | None, str] = {}
    for row in credits.itertuples(index=False):
        cast_names = [item["name"] for item in parse_list(row.cast)[:5] if item.get("name")]
        crew_names = [
            item["name"]
            for item in parse_list(row.crew)
            if item.get("job") in {"Director", "Writer", "Screenplay"} and item.get("name")
        ]
        credit_map[safe_int(row.tmdb_id)] = " ".join(cast_names + crew_names)

    rows = []
    for row in movies.itertuples(index=False):
        movie_id = safe_int(row.movie_id)
        tmdb_id = safe_int(row.tmdb_id)
        genres = " ".join(item["name"] for item in parse_list(row.genres) if item.get("name"))
        parts = [
            safe_text(getattr(row, "title")) or "",
            safe_text(getattr(row, "overview")) or "",
            genres,
            keyword_map.get(tmdb_id, ""),
            credit_map.get(tmdb_id, ""),
        ]
        feature_text = " ".join(part for part in parts if part).strip()
        if movie_id is not None and feature_text:
            rows.append((movie_id, feature_text))
    return insert_many(
        con,
        """
        INSERT INTO content_features (movie_id, feature_text)
        VALUES (%s, %s)
        ON CONFLICT (movie_id) DO UPDATE SET
            feature_text = EXCLUDED.feature_text,
            updated_at = CURRENT_TIMESTAMP
        """,
        rows,
    )


def load_users_and_ratings(
    con: psycopg.Connection, ratings_kind: str, valid_movie_ids: set[int]
) -> tuple[int, int, int]:
    ratings_name = "ratings_small.csv" if ratings_kind == "small" else "ratings.csv"
    inserted_users: set[int] = set()
    inserted_ratings = 0
    skipped_ratings = 0

    for chunk in pd.read_csv(DATA_DIR / ratings_name, chunksize=100_000):
        source_count = len(chunk)
        chunk["movieId"] = pd.to_numeric(chunk["movieId"], errors="coerce").astype("Int64")
        chunk["userId"] = pd.to_numeric(chunk["userId"], errors="coerce").astype("Int64")
        chunk["rating"] = pd.to_numeric(chunk["rating"], errors="coerce")
        chunk = chunk.dropna(subset=["userId", "movieId", "rating", "timestamp"])
        chunk = chunk[chunk["movieId"].isin(valid_movie_ids)]
        skipped_ratings += source_count - len(chunk)

        users = {(int(row.userId),) for row in chunk.itertuples(index=False)}
        inserted_users.update(user_id for (user_id,) in users)
        insert_many(
            con,
            """
            INSERT INTO users (user_id)
            VALUES (%s)
            ON CONFLICT (user_id) DO NOTHING
            """,
            users,
        )

        rating_rows = []
        for row in chunk.itertuples(index=False):
            rated_at = pd.to_datetime(int(row.timestamp), unit="s", utc=True).to_pydatetime()
            rating_rows.append((int(row.userId), int(row.movieId), float(row.rating), rated_at))

        inserted_ratings += insert_many(
            con,
            """
            INSERT INTO ratings (user_id, movie_id, rating, rated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, movie_id) DO UPDATE SET
                rating = EXCLUDED.rating,
                rated_at = EXCLUDED.rated_at
            """,
            rating_rows,
        )
        con.commit()

    return len(inserted_users), inserted_ratings, skipped_ratings


def table_counts(con: psycopg.Connection) -> dict[str, int]:
    tables = [
        "movies",
        "users",
        "ratings",
        "genres",
        "movie_genres",
        "keywords",
        "movie_keywords",
        "people",
        "movie_cast",
        "movie_crew",
        "content_features",
    ]
    return {table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}


def main() -> None:
    args = parse_args()
    with connect(args.database_url) as con:
        if args.recreate:
            reset_database(con)
        apply_schema(con)
        con.commit()

        movies_raw, links, keywords, credits = load_source_frames(args.links)
        movies = build_movie_frame(movies_raw, links)
        valid_movie_ids = {int(movie_id) for movie_id in movies["movie_id"].dropna().unique()}

        report: dict[str, Any] = {
            "database": args.database_url.split("@")[-1],
            "ratings_source": args.ratings,
            "links_source": args.links,
            "source_movies": len(movies_raw),
            "mapped_movies": len(movies),
        }

        report["collections"] = load_collections(con, movies)
        report["movies"] = load_movies(con, movies)
        report["genres"], report["movie_genres"] = load_named_relations(
            con, movies, "genres", "genres", "genre_id", "name", "movie_genres"
        )
        report["keywords"], report["movie_keywords"] = load_keywords(con, movies, keywords)
        report["people"], report["movie_cast"], report["movie_crew"] = load_people_and_credits(con, movies, credits)
        report["production_companies"], report["movie_production_companies"] = load_production_companies(con, movies)
        (
            report["production_countries"],
            report["movie_production_countries"],
            report["spoken_languages"],
            report["movie_spoken_languages"],
        ) = load_countries_and_languages(con, movies)
        report["content_features"] = load_content_features(con, movies, keywords, credits)
        con.commit()

        report["users"], report["ratings"], report["skipped_ratings"] = load_users_and_ratings(
            con, args.ratings, valid_movie_ids
        )
        report["table_counts"] = table_counts(con)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
