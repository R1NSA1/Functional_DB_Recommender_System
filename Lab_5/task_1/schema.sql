PRAGMA foreign_keys = ON;

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
    runtime REAL,
    budget INTEGER,
    revenue INTEGER,
    popularity REAL,
    vote_average REAL,
    vote_count INTEGER,
    adult INTEGER NOT NULL DEFAULT 0,
    video INTEGER NOT NULL DEFAULT 0,
    status TEXT,
    homepage TEXT,
    poster_path TEXT,
    tagline TEXT,
    collection_id INTEGER,
    FOREIGN KEY (collection_id) REFERENCES collections(collection_id)
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ratings (
    rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    movie_id INTEGER NOT NULL,
    rating REAL NOT NULL CHECK (rating >= 0.5 AND rating <= 5.0),
    rated_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id),
    UNIQUE (user_id, movie_id)
);

CREATE TABLE IF NOT EXISTS genres (
    genre_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS movie_genres (
    movie_id INTEGER NOT NULL,
    genre_id INTEGER NOT NULL,
    PRIMARY KEY (movie_id, genre_id),
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genres(genre_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS keywords (
    keyword_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS movie_keywords (
    movie_id INTEGER NOT NULL,
    keyword_id INTEGER NOT NULL,
    PRIMARY KEY (movie_id, keyword_id),
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (keyword_id) REFERENCES keywords(keyword_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS people (
    person_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    gender INTEGER
);

CREATE TABLE IF NOT EXISTS movie_cast (
    movie_id INTEGER NOT NULL,
    person_id INTEGER NOT NULL,
    character_name TEXT,
    cast_order INTEGER,
    PRIMARY KEY (movie_id, person_id, character_name),
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (person_id) REFERENCES people(person_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS movie_crew (
    movie_id INTEGER NOT NULL,
    person_id INTEGER NOT NULL,
    department TEXT,
    job TEXT,
    PRIMARY KEY (movie_id, person_id, department, job),
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (person_id) REFERENCES people(person_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS production_companies (
    company_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS movie_production_companies (
    movie_id INTEGER NOT NULL,
    company_id INTEGER NOT NULL,
    PRIMARY KEY (movie_id, company_id),
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (company_id) REFERENCES production_companies(company_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS production_countries (
    country_code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS movie_production_countries (
    movie_id INTEGER NOT NULL,
    country_code TEXT NOT NULL,
    PRIMARY KEY (movie_id, country_code),
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (country_code) REFERENCES production_countries(country_code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS spoken_languages (
    language_code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS movie_spoken_languages (
    movie_id INTEGER NOT NULL,
    language_code TEXT NOT NULL,
    PRIMARY KEY (movie_id, language_code),
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (language_code) REFERENCES spoken_languages(language_code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS content_features (
    movie_id INTEGER PRIMARY KEY,
    feature_text TEXT NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE
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
