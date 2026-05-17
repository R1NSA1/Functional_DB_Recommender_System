CREATE TABLE IF NOT EXISTS collections (
    collection_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    poster_path TEXT,
    backdrop_path TEXT
);

CREATE TABLE IF NOT EXISTS movies (
    movie_id INTEGER PRIMARY KEY,
    tmdb_id INTEGER UNIQUE,
    imdb_id TEXT,
    title TEXT NOT NULL,
    original_title TEXT,
    overview TEXT,
    original_language TEXT,
    release_date DATE,
    runtime DOUBLE PRECISION,
    budget BIGINT,
    revenue BIGINT,
    popularity DOUBLE PRECISION,
    vote_average DOUBLE PRECISION,
    vote_count INTEGER,
    adult BOOLEAN NOT NULL DEFAULT FALSE,
    video BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT,
    homepage TEXT,
    poster_path TEXT,
    tagline TEXT,
    collection_id INTEGER REFERENCES collections(collection_id)
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ratings (
    rating_id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    movie_id INTEGER NOT NULL REFERENCES movies(movie_id),
    rating DOUBLE PRECISION NOT NULL CHECK (rating >= 0.5 AND rating <= 5.0),
    rated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (user_id, movie_id)
);

CREATE TABLE IF NOT EXISTS genres (
    genre_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS movie_genres (
    movie_id INTEGER NOT NULL REFERENCES movies(movie_id) ON DELETE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genres(genre_id) ON DELETE CASCADE,
    PRIMARY KEY (movie_id, genre_id)
);

CREATE TABLE IF NOT EXISTS keywords (
    keyword_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS movie_keywords (
    movie_id INTEGER NOT NULL REFERENCES movies(movie_id) ON DELETE CASCADE,
    keyword_id INTEGER NOT NULL REFERENCES keywords(keyword_id) ON DELETE CASCADE,
    PRIMARY KEY (movie_id, keyword_id)
);

CREATE TABLE IF NOT EXISTS people (
    person_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    gender INTEGER
);

CREATE TABLE IF NOT EXISTS movie_cast (
    cast_id BIGSERIAL PRIMARY KEY,
    movie_id INTEGER NOT NULL REFERENCES movies(movie_id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
    character_name TEXT,
    cast_order INTEGER,
    UNIQUE (movie_id, person_id, character_name)
);

CREATE TABLE IF NOT EXISTS movie_crew (
    crew_id BIGSERIAL PRIMARY KEY,
    movie_id INTEGER NOT NULL REFERENCES movies(movie_id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
    department TEXT,
    job TEXT,
    UNIQUE (movie_id, person_id, department, job)
);

CREATE TABLE IF NOT EXISTS production_companies (
    company_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS movie_production_companies (
    movie_id INTEGER NOT NULL REFERENCES movies(movie_id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES production_companies(company_id) ON DELETE CASCADE,
    PRIMARY KEY (movie_id, company_id)
);

CREATE TABLE IF NOT EXISTS production_countries (
    country_code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS movie_production_countries (
    movie_id INTEGER NOT NULL REFERENCES movies(movie_id) ON DELETE CASCADE,
    country_code TEXT NOT NULL REFERENCES production_countries(country_code) ON DELETE CASCADE,
    PRIMARY KEY (movie_id, country_code)
);

CREATE TABLE IF NOT EXISTS spoken_languages (
    language_code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS movie_spoken_languages (
    movie_id INTEGER NOT NULL REFERENCES movies(movie_id) ON DELETE CASCADE,
    language_code TEXT NOT NULL REFERENCES spoken_languages(language_code) ON DELETE CASCADE,
    PRIMARY KEY (movie_id, language_code)
);

CREATE TABLE IF NOT EXISTS content_features (
    movie_id INTEGER PRIMARY KEY REFERENCES movies(movie_id) ON DELETE CASCADE,
    feature_text TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_movies_tmdb_id ON movies(tmdb_id);
CREATE INDEX IF NOT EXISTS idx_movies_imdb_id ON movies(imdb_id);
CREATE INDEX IF NOT EXISTS idx_movies_title ON movies(title);
CREATE INDEX IF NOT EXISTS idx_ratings_user_id ON ratings(user_id);
CREATE INDEX IF NOT EXISTS idx_ratings_movie_id ON ratings(movie_id);
CREATE INDEX IF NOT EXISTS idx_movie_genres_genre_id ON movie_genres(genre_id);
CREATE INDEX IF NOT EXISTS idx_movie_keywords_keyword_id ON movie_keywords(keyword_id);
CREATE INDEX IF NOT EXISTS idx_movie_cast_person_id ON movie_cast(person_id);
CREATE INDEX IF NOT EXISTS idx_movie_crew_person_id ON movie_crew(person_id);
