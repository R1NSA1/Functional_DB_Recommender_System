-- =============================================================================
-- РЕШЕНИЕ ПРОБЛЕМЫ ХОЛОДНОГО СТАРТА
-- Дополнительные таблицы и запросы
-- =============================================================================

-- 1. Таблица опросов новых пользователей
CREATE TABLE IF NOT EXISTS user_surveys (
    survey_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    favorite_genres TEXT,
    favorite_actors TEXT,
    min_rating INTEGER DEFAULT 7,
    preferred_decades TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Таблица трендов (популярные фильмы по периодам)
CREATE TABLE IF NOT EXISTS trending_movies (
    trend_id SERIAL PRIMARY KEY,
    movie_id INTEGER REFERENCES movies(movie_id) ON DELETE CASCADE,
    period VARCHAR(20),
    score DECIMAL(10,4),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Таблица для A/B тестирования холодного старта
CREATE TABLE IF NOT EXISTS cold_start_experiments (
    experiment_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id),
    strategy VARCHAR(50),
    recommendations_shown TEXT,
    clicks INTEGER DEFAULT 0,
    ratings_given INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Запрос: популярные фильмы для новых пользователей
CREATE OR REPLACE VIEW popular_for_new_users AS
SELECT 
    movie_id,
    title,
    vote_average,
    vote_count,
    ROW_NUMBER() OVER (ORDER BY vote_count DESC, vote_average DESC) as rank
FROM movies
WHERE vote_count > 100
ORDER BY vote_count DESC
LIMIT 50;

-- 5. Запрос: рекомендации на основе жанров
CREATE OR REPLACE FUNCTION recommend_by_genres(genre_list TEXT[], min_rating NUMERIC)
RETURNS TABLE (
    movie_id INTEGER,
    title TEXT,
    vote_average NUMERIC,
    relevance_score NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.movie_id,
        m.title,
        m.vote_average,
        COUNT(DISTINCT g.genre_name)::NUMERIC / array_length(genre_list, 1)::NUMERIC as relevance
    FROM movies m
    JOIN movie_genres mg ON m.movie_id = mg.movie_id
    JOIN genres g ON mg.genre_id = g.genre_id
    WHERE g.genre_name = ANY(genre_list)
        AND m.vote_average >= min_rating
    GROUP BY m.movie_id, m.title, m.vote_average
    ORDER BY relevance DESC, m.vote_average DESC
    LIMIT 20;
END;
$$ LANGUAGE plpgsql;

-- 6. Запрос: рекомендации для новых фильмов
CREATE OR REPLACE FUNCTION recommend_similar_new_movie(genre_list TEXT[])
RETURNS TABLE (
    movie_id INTEGER,
    title TEXT,
    vote_average NUMERIC,
    genre_match INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.movie_id,
        m.title,
        m.vote_average,
        COUNT(DISTINCT g.genre_name)::INTEGER as genre_match
    FROM movies m
    JOIN movie_genres mg ON m.movie_id = mg.movie_id
    JOIN genres g ON mg.genre_id = g.genre_id
    WHERE g.genre_name = ANY(genre_list)
    GROUP BY m.movie_id, m.title, m.vote_average
    ORDER BY genre_match DESC, m.vote_average DESC
    LIMIT 20;
END;
$$ LANGUAGE plpgsql;

-- 7. Проверка работы функций
-- SELECT * FROM recommend_by_genres(ARRAY['Action', 'Sci-Fi'], 7.0);
-- SELECT * FROM recommend_similar_new_movie(ARRAY['Action', 'Sci-Fi']);

-- 8. Индексы для ускорения
CREATE INDEX IF NOT EXISTS idx_user_surveys_user ON user_surveys(user_id);
CREATE INDEX IF NOT EXISTS idx_trending_movies_period ON trending_movies(period, score DESC);
