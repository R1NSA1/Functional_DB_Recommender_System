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

def run_scenarios():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    results = {"timestamp": datetime.now().isoformat(), "scenarios": {}}
    
    cur.execute("""
        SELECT title, vote_average, vote_count
        FROM movies WHERE vote_count > 100
        ORDER BY vote_count DESC LIMIT 10
    """)
    results["scenarios"]["popular_movies"] = [
        {"title": r[0], "rating": float(r[1]), "votes": int(r[2])}
        for r in cur.fetchall()
    ]
    
    cur.execute("""
        SELECT title, vote_average, vote_count
        FROM movies WHERE vote_count > 100 AND vote_average IS NOT NULL
        ORDER BY vote_average DESC LIMIT 10
    """)
    results["scenarios"]["top_rated"] = [
        {"title": r[0], "rating": float(r[1]), "votes": int(r[2])}
        for r in cur.fetchall()
    ]
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN rating_count = 0 THEN 'new'
                WHEN rating_count <= 10 THEN 'beginner'
                WHEN rating_count <= 50 THEN 'active'
                ELSE 'expert'
            END as user_type,
            COUNT(*) as count
        FROM (
            SELECT u.user_id, COUNT(r.rating) as rating_count
            FROM users u LEFT JOIN ratings r ON u.user_id = r.user_id
            GROUP BY u.user_id
        ) t GROUP BY user_type
    """)
    results["scenarios"]["user_stats"] = [{"type": r[0], "count": r[1]} for r in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    with open("reports/scenario_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    run_scenarios()
