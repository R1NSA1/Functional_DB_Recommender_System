import psycopg2
import json
from datetime import datetime

DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'recsys_lab5',
    'user': 'postgres',
    'password': '1234'
}

def cold_start_solution():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    results = {"timestamp": datetime.now().isoformat(), "solutions": {}}
    
    cur.execute("""
        SELECT title, vote_average, vote_count
        FROM movies WHERE vote_count > 100
        ORDER BY vote_count DESC LIMIT 10
    """)
    results["solutions"]["new_user_popular"] = [
        {"title": r[0], "rating": float(r[1]), "votes": int(r[2])}
        for r in cur.fetchall()
    ]
    
    cur.execute("""
        SELECT m.title, m.vote_average, COUNT(DISTINCT g.name) as genre_match
        FROM movies m
        JOIN movie_genres mg ON m.movie_id = mg.movie_id
        JOIN genres g ON mg.genre_id = g.genre_id
        WHERE g.name IN ('Action', 'Science Fiction') AND m.vote_average >= 7
        GROUP BY m.title, m.vote_average
        ORDER BY genre_match DESC, m.vote_average DESC
        LIMIT 10
    """)
    results["solutions"]["new_user_by_genres"] = [
        {"title": r[0], "rating": float(r[1]), "genre_match": r[2]}
        for r in cur.fetchall()
    ]
    
    cur.execute("""
        SELECT m.title, m.vote_average, COUNT(r.rating) as rating_count
        FROM movies m
        JOIN movie_genres mg ON m.movie_id = mg.movie_id
        JOIN genres g ON mg.genre_id = g.genre_id
        LEFT JOIN ratings r ON m.movie_id = r.movie_id
        WHERE g.name IN ('Action', 'Science Fiction')
        GROUP BY m.title, m.vote_average
        ORDER BY rating_count DESC, m.vote_average DESC
        LIMIT 10
    """)
    results["solutions"]["similar_for_new_movie"] = [
        {"title": r[0], "rating": float(r[1]) if r[1] else 0, "ratings_count": r[2]}
        for r in cur.fetchall()
    ]
    
    cur.close()
    conn.close()
    
    with open("reports/cold_start_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    cold_start_solution()
