-- Basic row counts after ETL.
SELECT
    COUNT(*) AS movies,
    (SELECT COUNT(*) FROM users) AS users,
    (SELECT COUNT(*) FROM ratings) AS ratings,
    (SELECT COUNT(*) FROM content_features) AS content_features
FROM movies;

-- Top rated movies with at least 50 user ratings.
SELECT
    m.title,
    ROUND(AVG(r.rating)::numeric, 2) AS avg_rating,
    COUNT(*) AS ratings_count
FROM ratings r
JOIN movies m ON m.movie_id = r.movie_id
GROUP BY m.movie_id, m.title
HAVING COUNT(*) >= 50
ORDER BY avg_rating DESC, ratings_count DESC
LIMIT 10;

-- Most frequent genres in the imported movie catalog.
SELECT
    g.name,
    COUNT(*) AS movies_count
FROM movie_genres mg
JOIN genres g ON g.genre_id = mg.genre_id
GROUP BY g.name
ORDER BY movies_count DESC
LIMIT 10;
