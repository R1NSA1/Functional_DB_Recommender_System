# =============================================================================
# РЕШЕНИЕ ПРОБЛЕМЫ ХОЛОДНОГО СТАРТА
# =============================================================================

import psycopg2
import pandas as pd
import random
import datetime

DB_CONFIG = {
    'host': 'localhost',
    'database': 'movie_recommender',
    'user': 'ilyshaaaa',
    'password': ''
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# СТРАТЕГИЯ 1: ПОПУЛЯРНЫЕ ФИЛЬМЫ
# =============================================================================

def strategy_popular(user_id, limit=10):
    """Стратегия холодного старта: популярные фильмы"""
    
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n📊 СТРАТЕГИЯ 1: Популярные фильмы")
    print("-" * 40)
    
    cur.execute("""
        SELECT title, vote_average, vote_count
        FROM movies
        WHERE vote_count > 100
        ORDER BY vote_count DESC
        LIMIT %s
    """, (limit,))
    
    recommendations = cur.fetchall()
    
    for i, row in enumerate(recommendations, 1):
        print(f"  {i}. {row[0]} | ⭐ {row[1]:.1f} | {row[2]} оценок")
    
    # Сохраняем в эксперимент
    cur.execute("""
        INSERT INTO cold_start_experiments (user_id, strategy, recommendations_shown)
        VALUES (%s, 'popular', %s)
    """, (user_id, str([r[0] for r in recommendations])))
    conn.commit()
    
    cur.close()
    conn.close()
    
    return recommendations

# =============================================================================
# СТРАТЕГИЯ 2: ОПРОС ЖАНРОВ
# =============================================================================

def strategy_survey(user_id, favorite_genres, min_rating=7, limit=10):
    """Стратегия холодного старта: опрос пользователя"""
    
    conn = get_connection()
    cur = conn.cursor()
    
    print(f"\n📊 СТРАТЕГИЯ 2: Опрос жанров ({', '.join(favorite_genres)})")
    print("-" * 40)
    
    # Сохраняем опрос
    cur.execute("""
        INSERT INTO user_surveys (user_id, favorite_genres, min_rating)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET favorite_genres = EXCLUDED.favorite_genres,
            min_rating = EXCLUDED.min_rating
    """, (user_id, ','.join(favorite_genres), min_rating))
    conn.commit()
    
    # Рекомендации через функцию БД
    placeholders = ','.join([f"'{g}'" for g in favorite_genres])
    query = f"""
        SELECT title, vote_average, genre_name
        FROM movies m
        JOIN movie_genres mg ON m.movie_id = mg.movie_id
        JOIN genres g ON mg.genre_id = g.genre_id
        WHERE g.genre_name IN ({placeholders})
        AND m.vote_average >= {min_rating}/2.0
        ORDER BY m.vote_average DESC
        LIMIT {limit}
    """
    cur.execute(query)
    recommendations = cur.fetchall()
    
    for i, row in enumerate(recommendations, 1):
        print(f"  {i}. {row[0]} | ⭐ {row[1]:.1f} | Жанр: {row[2]}")
    
    # Сохраняем в эксперимент
    cur.execute("""
        INSERT INTO cold_start_experiments (user_id, strategy, recommendations_shown)
        VALUES (%s, 'survey', %s)
    """, (user_id, str([r[0] for r in recommendations])))
    conn.commit()
    
    cur.close()
    conn.close()
    
    return recommendations

# =============================================================================
# СТРАТЕГИЯ 3: КОМБИНИРОВАННАЯ
# =============================================================================

def strategy_hybrid(user_id, favorite_genres=None, limit=10):
    """Стратегия холодного старта: комбинированный подход"""
    
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n📊 СТРАТЕГИЯ 3: Комбинированный подход")
    print("-" * 40)
    
    recommendations = []
    
    # Часть 1: Популярные (40%)
    popular_limit = int(limit * 0.4)
    cur.execute("""
        SELECT title, vote_average, vote_count
        FROM movies
        WHERE vote_count > 100
        ORDER BY vote_count DESC
        LIMIT %s
    """, (popular_limit,))
    recommendations.extend(cur.fetchall())
    
    # Часть 2: Жанровые (60%)
    if favorite_genres:
        genre_limit = limit - len(recommendations)
        placeholders = ','.join([f"'{g}'" for g in favorite_genres])
        query = f"""
            SELECT title, vote_average, vote_count
            FROM movies m
            JOIN movie_genres mg ON m.movie_id = mg.movie_id
            JOIN genres g ON mg.genre_id = g.genre_id
            WHERE g.genre_name IN ({placeholders})
            AND m.movie_id NOT IN (SELECT movie_id FROM trending_movies)
            ORDER BY m.vote_average DESC
            LIMIT {genre_limit}
        """
        cur.execute(query)
        recommendations.extend(cur.fetchall())
    
    for i, row in enumerate(recommendations[:limit], 1):
        print(f"  {i}. {row[0]} | ⭐ {row[1]:.1f}")
    
    cur.close()
    conn.close()
    
    return recommendations

# =============================================================================
# ОЦЕНКА ЭФФЕКТИВНОСТИ СТРАТЕГИЙ
# =============================================================================

def evaluate_strategies():
    """Оценка эффективности стратегий холодного старта"""
    
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n" + "="*60)
    print("ОЦЕНКА ЭФФЕКТИВНОСТИ СТРАТЕГИЙ")
    print("="*60)
    
    # Создаем тестового пользователя
    cur.execute("""
        INSERT INTO users (username, email, registration_date, is_active)
        VALUES ('test_cold_start', 'test@example.com', CURRENT_DATE, TRUE)
        RETURNING user_id
    """)
    test_user = cur.fetchone()[0]
    conn.commit()
    
    print(f"\n✅ Тестовый пользователь: {test_user}")
    
    # Тестируем стратегии
    strategies = {
        'popular': lambda: strategy_popular(test_user, 5),
        'survey': lambda: strategy_survey(test_user, ['Action', 'Sci-Fi'], 7, 5),
        'hybrid': lambda: strategy_hybrid(test_user, ['Action', 'Sci-Fi'], 5)
    }
    
    results = {}
    for name, strategy_func in strategies.items():
        print(f"\n--- Тестирование: {name} ---")
        recommendations = strategy_func()
        results[name] = len(recommendations)
    
    # Вывод результатов
    print("\n" + "="*40)
    print("ИТОГИ ТЕСТИРОВАНИЯ:")
    for name, count in results.items():
        print(f"  {name}: {count} рекомендаций")
    
    # Рекомендация
    print("\n🎯 РЕКОМЕНДАЦИЯ:")
    print("  Для холодного старта новых пользователей рекомендуется:")
    print("  1. Комбинированный подход (гибрид)")
    print("  2. Сбор данных через опрос при регистрации")
    print("  3. A/B тестирование стратегий")
    
    cur.close()
    conn.close()
    
    return results

# =============================================================================
# ЗАПУСК
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("РЕШЕНИЕ ПРОБЛЕМЫ ХОЛОДНОГО СТАРТА")
    print("Рекомендательная система фильмов")
    print("="*60)
    
    # Создаем таблицы если нет
    conn = get_connection()
    cur = conn.cursor()
    
    # Создаем необходимые таблицы
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_surveys (
            survey_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
            favorite_genres TEXT,
            favorite_actors TEXT,
            min_rating INTEGER DEFAULT 7,
            preferred_decades TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cold_start_experiments (
            experiment_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id),
            strategy VARCHAR(50),
            recommendations_shown TEXT,
            clicks INTEGER DEFAULT 0,
            ratings_given INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    
    cur.close()
    conn.close()
    
    # Запуск стратегий
    evaluate_strategies()
    
    print("\n" + "="*60)
    print("✅ Работа завершена!")
    print("="*60)
